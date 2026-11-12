import asyncio
import io
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, update
from app.main import app
from app.config import get_settings
from app.db import jobs
from app.db.models import UserSession, User
from app import worker
from test_jobs_postgres import IDEA


def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def register(c, email):
    response = await c.post("/auth/register", json={"email": email, "password": "test-password-123"})
    assert response.status_code == 201
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "password_hash" not in response.json()
    return response.json()


def test_authentication_session_revocation_and_origin(db):
    async def scenario():
        async with client() as c:
            assert (await c.get("/jobs")).status_code == 401
            assert (await c.post("/auth/register", json={"email":"a@example.test", "password":"test-password-123"},
                                 headers={"origin":"https://attacker.test"})).status_code == 403
            await register(c, "first@example.test")
            assert (await c.get("/auth/me")).status_code == 200
            assert (await c.post("/auth/register", json={"email":"FIRST@example.test", "password":"test-password-123"})).status_code == 409
            old = dict(c.cookies)
            await c.post("/auth/logout")
            assert (await c.get("/auth/me")).status_code == 401
            c.cookies.update(old)
            assert (await c.get("/auth/me")).status_code == 401
            assert (await c.post("/auth/login", json={"email":"first@example.test", "password":"wrong-password-12"})).status_code == 401
            assert (await c.post("/auth/login", json={"email":"first@example.test", "password":"test-password-123"})).status_code == 200
            async with db.begin() as session:
                await session.execute(update(UserSession).values(expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)))
            assert (await c.get("/auth/me")).status_code == 401
    asyncio.run(scenario())


def test_ownership_for_history_events_versions_and_exports(db):
    async def scenario():
        async with client() as alice, client() as bob:
            await register(alice, "alice@example.test")
            await register(bob, "bob@example.test")
            saved = (await alice.post("/jobs", json=IDEA)).json()
            job_id, project_id = saved["id"], saved["project_id"]
            assert (await bob.get("/jobs")).json() == []
            assert (await bob.get("/projects")).json() == []
            for suffix in ("", "/events", "/export/pdf", "/export/docx", "/export/json"):
                assert (await bob.get(f"/jobs/{job_id}{suffix}")).status_code == 404
            assert (await bob.post(f"/jobs?project_id={project_id}", json=IDEA)).status_code == 404
            assert (await bob.patch(f"/projects/{project_id}", json={"name":"Stolen"})).status_code == 404
            assert (await alice.get(f"/jobs/{job_id}/export/pdf")).status_code == 409
            await worker.process_job(await jobs.claim())
            for format in ("pdf", "docx", "json"):
                response = await alice.get(f"/jobs/{job_id}/export/{format}")
                assert response.status_code == 200
                if format == "pdf":
                    assert response.content.startswith(b"%PDF")
                elif format == "docx":
                    doc = zipfile.ZipFile(io.BytesIO(response.content))
                    assert b"Financial model" in doc.read("word/document.xml")
                else:
                    assert response.json()["finance"]["scenarios"]
            second = (await alice.post(f"/jobs?project_id={project_id}", json={**IDEA,"unit_price":1700})).json()
            assert second["version"] == 2
            assert second["project_id"] == project_id
            assert (await alice.get(f"/jobs/{job_id}")).json()["input_data"]["unit_price"] == 1500
            assert (await alice.patch(f"/projects/{project_id}", json={"name":"Renamed project"})).json()["name"] == "Renamed project"
            assert len((await alice.get(f"/jobs?project_id={project_id}")).json()) == 2
    asyncio.run(scenario())


def test_generation_limit_is_atomic_and_version_numbers_are_unique(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_active_jobs", 2)
    async def scenario():
        async with client() as c:
            await register(c, "limits@example.test")
            first = (await c.post("/jobs", json=IDEA)).json()
            results = await asyncio.gather(*(c.post(f"/jobs?project_id={first['project_id']}", json=IDEA) for _ in range(4)))
            assert sorted(r.status_code for r in results) == [202,429,429,429]
            versions = (await c.get("/jobs")).json()
            assert sorted(row["version"] for row in versions) == [1,2]
            # Completing one task permits another active task, but hourly limit still applies.
            await worker.process_job(await jobs.claim())
            monkeypatch.setattr(get_settings(), "generation_limit_hour", 2)
            assert (await c.post("/jobs", json=IDEA)).status_code == 429
    asyncio.run(scenario())


def test_stale_worker_cannot_write_node_events(db):
    async def scenario():
        await jobs.enqueue(IDEA)
        item = await jobs.claim()
        assert await jobs.record_event(item, "node_started", "market", {}, "Started")
        await jobs.finish(item, {"done":True})
        assert not await jobs.record_event(item, "node_completed", "market", {}, "Stale")
    asyncio.run(scenario())
