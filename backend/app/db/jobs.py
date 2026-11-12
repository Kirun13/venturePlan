import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, update
from app.db.models import JobEvent, PlanJob, Project, User
from app.db.session import Session
from app.config import get_settings


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    token: uuid.UUID
    payload: dict
    agent_mode: str


class QueueLimit(Exception):
    pass

class ProjectMissing(Exception):
    pass

async def enqueue(payload: dict, owner_id: uuid.UUID | None = None,
                  project_id: uuid.UUID | None = None) -> PlanJob:
    settings = get_settings()
    async with Session.begin() as session:
        version = 1
        if owner_id is not None:
            # Serialize submissions per owner, including limits and version assignment.
            await session.execute(select(User).where(User.id == owner_id).with_for_update())
            active = await session.scalar(select(func.count()).select_from(PlanJob).where(
                PlanJob.owner_id == owner_id, PlanJob.status.in_(("queued", "running"))))
            recent = await session.scalar(select(func.count()).select_from(PlanJob).where(
                PlanJob.owner_id == owner_id,
                PlanJob.created_at > datetime.now(timezone.utc) - timedelta(hours=1)))
            if active >= settings.max_active_jobs or recent >= settings.generation_limit_hour:
                raise QueueLimit("Generation limit reached. Wait for active tasks or try again later")
            if project_id is None:
                project = Project(owner_id=owner_id, name=payload["name"])
                session.add(project)
                await session.flush()
                project_id = project.id
            else:
                project = await session.scalar(select(Project).where(
                    Project.id == project_id, Project.owner_id == owner_id).with_for_update())
                if project is None:
                    raise ProjectMissing()
                version = (await session.scalar(select(func.max(PlanJob.version)).where(
                    PlanJob.project_id == project_id)) or 0) + 1
        job = PlanJob(input_data=payload, max_attempts=settings.worker_max_attempts,
                      agent_mode=settings.agent_mode, owner_id=owner_id, project_id=project_id, version=version)
        session.add(job)
        await session.flush()
        session.add(JobEvent(job_id=job.id, kind="queued", message="Job queued"))
        await session.refresh(job)
        return job


async def claim() -> ClaimedJob | None:
    async with Session.begin() as session:
        while True:
            now = datetime.now(timezone.utc)
            query = (select(PlanJob).where(or_(
                (PlanJob.status == "queued") & (PlanJob.available_at <= now),
                (PlanJob.status == "running") & (PlanJob.lease_until < now),
            )).order_by(PlanJob.available_at, PlanJob.created_at)
                .with_for_update(skip_locked=True).limit(1))
            job = (await session.execute(query)).scalar_one_or_none()
            if job is None:
                return None
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.error = "The task could not finish after several attempts. Please submit it again."
                job.finished_at = now
                job.lease_until = None
                job.attempt_token = None
                session.add(JobEvent(job_id=job.id, kind="failed", message=job.error))
                await session.flush()
                continue
            recovered = job.status == "running"
            job.status = "running"
            job.attempts += 1
            job.started_at = now
            job.error = None
            job.attempt_token = uuid.uuid4()
            job.lease_until = now + timedelta(seconds=get_settings().worker_lease_seconds)
            session.add(JobEvent(job_id=job.id, kind="running", message=(
                "Recovering interrupted task" if recovered else "Processing started")))
            return ClaimedJob(job.id, job.attempt_token, job.input_data, job.agent_mode)


def _ownership(item: ClaimedJob, now: datetime):
    return (PlanJob.id == item.id, PlanJob.status == "running",
            PlanJob.attempt_token == item.token, PlanJob.lease_until > now)


async def heartbeat(item: ClaimedJob) -> bool:
    now = datetime.now(timezone.utc)
    async with Session.begin() as session:
        result = await session.execute(update(PlanJob).where(*_ownership(item, now)).values(
            lease_until=now + timedelta(seconds=get_settings().worker_lease_seconds)))
        return result.rowcount == 1


async def record_event(item: ClaimedJob, kind: str, node: str | None, details: dict, message: str):
    async with Session.begin() as session:
        job = await session.scalar(select(PlanJob).where(
            *_ownership(item, datetime.now(timezone.utc))).with_for_update())
        if job is None:
            return False
        session.add(JobEvent(job_id=item.id, kind=kind, node=node, details=details,
                             attempt=job.attempts, message=message))
        return True


async def finish(item: ClaimedJob, result: dict | None = None, *,
                 error: str | None = None, retryable: bool = False) -> bool:
    async with Session.begin() as session:
        job = (await session.execute(select(PlanJob).where(
            *_ownership(item, datetime.now(timezone.utc))).with_for_update())).scalar_one_or_none()
        if job is None:
            return False
        now = datetime.now(timezone.utc)
        retry = error is not None and retryable and job.attempts < job.max_attempts
        job.status = "queued" if retry else ("failed" if error else "completed")
        job.result_data = result if not error else None
        job.error = error
        job.finished_at = None if retry else now
        job.lease_until = None
        job.attempt_token = None
        if retry:
            delay = min(3600, get_settings().worker_retry_base_seconds * 2 ** (job.attempts - 1))
            job.available_at = now + timedelta(seconds=delay)
        session.add(JobEvent(job_id=job.id, kind="retrying" if retry else job.status,
                             message=("Temporary failure; retry scheduled" if retry else
                                      error or "Plan generated")))
        return True


async def release(item: ClaimedJob) -> bool:
    """Return interrupted work to the queue, preserving the attempt limit."""
    return await finish(item, error="Processing was interrupted. Please try again.", retryable=True)
