"""Integration tests against a dedicated, migrated PostgreSQL database."""
import asyncio
import os
os.environ["AGENT_MODE"] = "mock"
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

@pytest.fixture(scope="session")
def postgres_factory():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL or run compose.test.yml")
    if make_url(url).database != "ventureplan_test":
        pytest.fail("Integration tests require the dedicated ventureplan_test database")
    env = {**os.environ, "DATABASE_URL": url}
    # Exercise a fresh migration, an upgrade with existing data, and an idempotent upgrade.
    subprocess.run(["alembic", "downgrade", "base"], env=env, check=True)
    subprocess.run(["alembic", "upgrade", "0001"], env=env, check=True)
    engine = create_async_engine(url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    legacy_id = uuid.uuid4()

    async def insert_legacy():
        async with engine.begin() as conn:
            await conn.execute(text("INSERT INTO plan_jobs (id, input_data) VALUES (:id, '{}')"), {"id": legacy_id})
    asyncio.run(insert_legacy())
    for _ in range(2):
        subprocess.run(["alembic", "upgrade", "head"], env=env, check=True)

    async def check_migration():
        async with factory() as session:
            row = await session.get(PlanJob, legacy_id)
            assert row.agent_mode == "unknown" and row.max_attempts == 3
            assert await session.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
    asyncio.run(check_migration())
    yield factory
    asyncio.run(engine.dispose())


@pytest.fixture
def db(postgres_factory, monkeypatch):
    async def clean():
        async with postgres_factory.begin() as session:
            await session.execute(text("TRUNCATE job_events, plan_jobs, projects, user_sessions, users, auth_limits RESTART IDENTITY CASCADE"))
    asyncio.run(clean())
    monkeypatch.setattr(jobs, "Session", postgres_factory)
    monkeypatch.setattr(routes, "Session", postgres_factory)
    from app import auth
    monkeypatch.setattr(auth, "Session", postgres_factory)
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_mode", "mock")
    monkeypatch.setattr(settings, "worker_lease_seconds", 60)
    monkeypatch.setattr(settings, "worker_retry_base_seconds", 0)
    monkeypatch.setattr(settings, "worker_max_attempts", 3)
    return postgres_factory
