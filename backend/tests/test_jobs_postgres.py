"""Integration tests against a dedicated, migrated PostgreSQL database."""
import asyncio
import os
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError
from sqlalchemy import select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api import jobs as routes
from app.config import get_settings
from app.db import jobs
from app.db.models import PlanJob
from app.main import app
from app.schemas.models import BusinessIdeaInput
from app import worker

IDEA = BusinessIdeaInput(name="Coffee kiosk", description="Takeaway coffee for office workers",
                         target_audience="Office workers", initial_budget=2000000,
                         unit_price=1500, estimated_monthly_units=1000).model_dump(mode="json")




async def expire(db, item):
    async with db.begin() as session:
        await session.execute(update(PlanJob).where(PlanJob.id == item.id).values(
            lease_until=datetime.now(timezone.utc) - timedelta(seconds=1)))


def test_submit_worker_result_and_history_survive_new_client(db):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/auth/register", json={"email":"queue@example.test","password":"test-password-123"})
            cookies = client.cookies
            response = await client.post("/jobs", json=IDEA)
            assert response.status_code == 202
            job_id = response.json()["id"]
            assert response.json()["agent_mode"] == "mock"
        item = await jobs.claim()
        assert str(item.id) == job_id
        await worker.process_job(item)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", cookies=cookies) as client:
            saved = (await client.get(f"/jobs/{job_id}")).json()
            assert saved["status"] == "completed"
            assert saved["result_data"]["finance"]["monthly_revenue"] == 1500000
            assert (await client.get("/jobs")).json()[0]["id"] == job_id
            events = (await client.get(f"/jobs/{job_id}/events")).json()
            assert [event["kind"] for event in events if not event["kind"].startswith("node_")] == ["queued", "running", "completed"]
            assert any(event["node"] == "market" and event["kind"] == "node_completed" for event in events)
            assert (await client.get(f"/jobs/{uuid.uuid4()}")).status_code == 404
            assert (await client.get("/jobs?limit=101")).status_code == 422
            assert (await client.post("/jobs", json={})).status_code == 422
            assert "attempt_token" not in saved
    asyncio.run(scenario())


def test_missing_openai_key_does_not_enqueue(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_mode", "openai")
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/auth/register", json={"email":"key@example.test","password":"test-password-123"})
            assert (await client.post("/jobs", json=IDEA)).status_code == 503
        assert await jobs.claim() is None
    asyncio.run(scenario())


def test_concurrent_claims_have_one_owner(db):
    async def scenario():
        await jobs.enqueue(IDEA)
        results = await asyncio.gather(*(jobs.claim() for _ in range(5)))
        assert len([item for item in results if item]) == 1
    asyncio.run(scenario())


def test_locked_job_is_skipped(db):
    async def scenario():
        first = await jobs.enqueue(IDEA)
        second = await jobs.enqueue(IDEA)
        async with db.begin() as session:
            await session.execute(select(PlanJob).where(PlanJob.id == first.id).with_for_update())
            claimed = await asyncio.wait_for(jobs.claim(), 2)
            assert claimed.id == second.id
    asyncio.run(scenario())


def test_expired_attempt_cannot_finish_renew_or_release(db):
    async def scenario():
        await jobs.enqueue(IDEA)
        old = await jobs.claim()
        await expire(db, old)
        assert not await jobs.heartbeat(old)
        assert not await jobs.finish(old, {"stale": True})
        new = await jobs.claim()
        assert new.id == old.id and new.token != old.token
        assert not await jobs.finish(old, {"stale": True})
        assert not await jobs.release(old)
        assert await jobs.finish(new, {"current": True})
        async with db() as session:
            assert (await session.get(PlanJob, new.id)).result_data == {"current": True}
    asyncio.run(scenario())


def test_expired_tasks_stop_after_attempt_limit(db):
    async def scenario():
        saved = await jobs.enqueue(IDEA)
        for _ in range(3):
            item = await jobs.claim()
            await expire(db, item)
        assert await jobs.claim() is None
        async with db() as session:
            row = await session.get(PlanJob, saved.id)
            assert row.status == "failed" and row.attempts == 3
            assert row.finished_at is not None and row.attempt_token is None
    asyncio.run(scenario())


def test_retry_backoff_and_limit(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "worker_retry_base_seconds", 10)
    async def scenario():
        await jobs.enqueue(IDEA)
        for attempt in range(1, 4):
            item = await jobs.claim()
            before = datetime.now(timezone.utc)
            assert await jobs.finish(item, error="Temporary service failure", retryable=True)
            async with db.begin() as session:
                row = await session.get(PlanJob, item.id)
                if attempt < 3:
                    assert row.status == "queued"
                    assert row.available_at >= before + timedelta(seconds=10 * 2 ** (attempt - 1))
                    assert await jobs.claim() is None
                    row.available_at = before - timedelta(seconds=1)
                else:
                    assert row.status == "failed" and row.attempts == 3
        assert await jobs.claim() is None
    asyncio.run(scenario())


def test_heartbeat_prevents_reclaim_of_long_job(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "worker_lease_seconds", 0.9)
    started = asyncio.Event()
    complete = asyncio.Event()
    async def slow_graph(state):
        started.set()
        await complete.wait()
        from app.graph.workflow import build_graph
        return await build_graph("mock").ainvoke(state)
    monkeypatch.setattr(worker, "build_graph", lambda mode: SimpleNamespace(ainvoke=slow_graph))
    async def scenario():
        saved = await jobs.enqueue(IDEA)
        task = asyncio.create_task(worker.process_job(await jobs.claim()))
        try:
            await asyncio.wait_for(started.wait(), 2)
            await asyncio.sleep(1.2)
            assert await jobs.claim() is None
            complete.set()
            await asyncio.wait_for(task, 3)
            async with db() as session:
                row = await session.get(PlanJob, saved.id)
                assert row.status == "completed" and row.attempts == 1
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())


def test_shutdown_requeues_and_new_worker_finishes(db, monkeypatch):
    started = asyncio.Event()
    real_build = worker.build_graph
    async def slow_graph(state):
        started.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(worker, "build_graph", lambda mode: SimpleNamespace(ainvoke=slow_graph))
    async def scenario():
        saved = await jobs.enqueue(IDEA)
        task = asyncio.create_task(worker.process_job(await jobs.claim()))
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        monkeypatch.setattr(worker, "build_graph", real_build)
        await worker.process_job(await jobs.claim())
        async with db() as session:
            row = await session.get(PlanJob, saved.id)
            assert row.status == "completed" and row.attempts == 2
    asyncio.run(scenario())


@pytest.mark.parametrize("temporary", [True, False])
def test_worker_retries_only_temporary_errors_and_hides_details(db, monkeypatch, temporary):
    async def failing_graph(state):
        if temporary:
            raise APIConnectionError(request=httpx.Request("POST", "https://example.test/private"))
        raise ValueError("private request data")
    monkeypatch.setattr(worker, "build_graph", lambda mode: SimpleNamespace(ainvoke=failing_graph))
    async def scenario():
        saved = await jobs.enqueue(IDEA)
        await worker.process_job(await jobs.claim())
        async with db() as session:
            row = await session.get(PlanJob, saved.id)
            assert row.status == ("queued" if temporary else "failed")
            assert "private" not in row.error and "ValueError" not in row.error
    asyncio.run(scenario())


def test_heartbeat_failure_cancels_work_without_finishing(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "worker_lease_seconds", 0.3)
    stopped = asyncio.Event()
    async def slow_graph(state):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
    async def broken_heartbeat(item):
        raise ConnectionError("Database unavailable")
    monkeypatch.setattr(worker, "build_graph", lambda mode: SimpleNamespace(ainvoke=slow_graph))
    monkeypatch.setattr(worker, "heartbeat", broken_heartbeat)
    async def scenario():
        saved = await jobs.enqueue(IDEA)
        await asyncio.wait_for(worker.process_job(await jobs.claim()), 2)
        assert stopped.is_set()
        async with db() as session:
            row = await session.get(PlanJob, saved.id)
            assert row.status == "running" and row.result_data is None
        await expire(db, SimpleNamespace(id=saved.id))
        assert (await jobs.claim()).id == saved.id
    asyncio.run(scenario())
