import asyncio
import logging
import signal

from openai import APIConnectionError, APIStatusError, RateLimitError
from app.db.jobs import ClaimedJob, claim, finish, heartbeat, release, record_event
from app.observability import event_sink
from app.db.session import engine
from app.config import get_settings
from app.graph.workflow import build_graph
from app.schemas.models import BusinessIdeaInput

log = logging.getLogger("worker")


class LeaseLost(Exception):
    pass


def is_retryable(exc: Exception) -> bool:
    # SDK retries are bounded too; quota and authentication errors need user action.
    if isinstance(exc, RateLimitError):
        return exc.code != "insufficient_quota"
    return isinstance(exc, APIConnectionError) or (
        isinstance(exc, APIStatusError) and exc.status_code >= 500)


def public_error(exc: Exception) -> str:
    if isinstance(exc, RateLimitError) and exc.code == "insufficient_quota":
        return "The AI service quota is exhausted. Check the service account before trying again."
    if is_retryable(exc):
        return "The AI service is temporarily unavailable. Please try again later."
    # Exception text can include request contents or provider details. Keep it in logs.
    return "The plan could not be generated. Please check the inputs or contact the administrator."


async def keep_lease(item: ClaimedJob):
    interval = get_settings().worker_lease_seconds / 3
    while True:
        await asyncio.sleep(interval)
        if not await heartbeat(item):
            raise LeaseLost()


async def process_job(item: ClaimedJob):
    async def sink(kind, node, details, message):
        if not await record_event(item, kind, node, details, message):
            raise LeaseLost()
    context_token = event_sink.set(sink)
    work = None
    lease = None
    try:
        # Preserve the mode selected when the task was submitted, even after a restart.
        mode = item.agent_mode if item.agent_mode in ("mock", "openai") else get_settings().agent_mode
        graph = build_graph(mode)
        work = asyncio.create_task(graph.ainvoke({"idea": BusinessIdeaInput.model_validate(item.payload)}))
        lease = asyncio.create_task(keep_lease(item))
        done, _ = await asyncio.wait((work, lease), return_when=asyncio.FIRST_COMPLETED)
        if lease in done:
            # A failed heartbeat makes ownership uncertain. Let the lease expire.
            await lease
            raise LeaseLost()
        state = await work
        if not await finish(item, state["plan"].model_dump(mode="json")):
            log.warning("Discarded result for stale attempt of job %s", item.id)
    except asyncio.CancelledError:
        # Stop local work before returning ownership to the queue.
        if work is not None:
            work.cancel()
            await asyncio.gather(work, return_exceptions=True)
        try:
            await release(item)
        except Exception:
            log.exception("Could not release job %s; lease recovery will handle it", item.id)
        raise
    except LeaseLost:
        log.warning("Lease lost for job %s; stopping this attempt", item.id)
    except Exception as exc:
        log.exception("Job %s attempt failed", item.id)
        # A heartbeat failure must not be persisted as a generation failure.
        if lease is None or not lease.done():
            await finish(item, error=public_error(exc), retryable=is_retryable(exc))
    finally:
        for task in (work, lease):
            if task is not None:
                task.cancel()
        await asyncio.gather(*(task for task in (work, lease) if task is not None), return_exceptions=True)
        event_sink.reset(context_token)


async def run_worker():
    settings = get_settings()
    if settings.agent_mode == "openai" and not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for openai mode")
    while True:
        try:
            item = await claim()
            if item is None:
                await asyncio.sleep(settings.worker_poll_seconds)
            else:
                await process_job(item)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Worker polling failed")
            await asyncio.sleep(3)


async def main():
    task = asyncio.create_task(run_worker())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, task.cancel)
        except NotImplementedError:
            # Windows event loops do not implement add_signal_handler.
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(task.cancel))
    try:
        await task
    except asyncio.CancelledError:
        log.info("Worker stopped")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
