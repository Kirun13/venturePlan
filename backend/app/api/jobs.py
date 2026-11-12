import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from app.auth import current_user
from app.db.session import Session
from app.db.models import PlanJob, JobEvent, Project, User
from app.db.jobs import enqueue, ProjectMissing, QueueLimit
from app.schemas.models import BusinessIdeaInput
from app.config import get_settings

router = APIRouter(tags=["workspace"])

async def session_dep():
    async with Session() as session:
        yield session


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: Literal["queued", "running", "completed", "failed"]
    attempts: int
    max_attempts: int
    agent_mode: str
    project_id: uuid.UUID | None
    version: int
    available_at: datetime
    input_data: dict
    result_data: dict | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    created_at: datetime


class ProjectUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


async def owned_job(session, job_id, user):
    job = await session.scalar(select(PlanJob).where(PlanJob.id == job_id, PlanJob.owner_id == user.id))
    if job is None:
        raise HTTPException(404, "Task not found")
    return job


@router.post("/jobs", response_model=JobOut, status_code=202)
async def submit(idea: BusinessIdeaInput, project_id: uuid.UUID | None = None,
                 user: User = Depends(current_user)):
    settings = get_settings()
    if settings.agent_mode == "openai" and not settings.openai_api_key:
        raise HTTPException(503, "OpenAI API key not configured on backend")
    try:
        return await enqueue(idea.model_dump(mode="json"), user.id, project_id)
    except ProjectMissing:
        raise HTTPException(404, "Project not found")
    except QueueLimit as exc:
        raise HTTPException(429, str(exc))


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                    project_id: uuid.UUID | None = None, user: User = Depends(current_user),
                    session: AsyncSession = Depends(session_dep)):
    query = select(PlanJob).where(PlanJob.owner_id == user.id)
    if project_id:
        query = query.where(PlanJob.project_id == project_id)
    result = await session.execute(query.order_by(PlanJob.created_at.desc()).limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, user: User = Depends(current_user),
                  session: AsyncSession = Depends(session_dep)):
    return await owned_job(session, job_id, user)


@router.get("/jobs/{job_id}/events")
async def get_events(job_id: uuid.UUID, user: User = Depends(current_user),
                     session: AsyncSession = Depends(session_dep)):
    await owned_job(session, job_id, user)
    result = await session.execute(select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.id))
    return [{"id": e.id, "kind": e.kind, "message": e.message, "created_at": e.created_at,
             "node": e.node, "attempt": e.attempt, "details": e.details} for e in result.scalars()]


@router.get("/jobs/{job_id}/export/{format}")
async def export_job(job_id: uuid.UUID, format: Literal["pdf", "docx", "json"],
                     user: User = Depends(current_user), session: AsyncSession = Depends(session_dep)):
    from app.exports import export_plan
    job = await owned_job(session, job_id, user)
    if job.status != "completed" or not job.result_data:
        raise HTTPException(409, "Wait until the plan is completed")
    data, media = await run_in_threadpool(export_plan, job.result_data, format, job.version, job.agent_mode)
    return Response(data, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="ventureplan-{job.id}-v{job.version}.{format}"'})


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(user: User = Depends(current_user), session: AsyncSession = Depends(session_dep)):
    return (await session.scalars(select(Project).where(Project.owner_id == user.id)
                                   .order_by(Project.created_at.desc()))).all()


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def rename_project(project_id: uuid.UUID, data: ProjectUpdate, user: User = Depends(current_user)):
    async with Session.begin() as session:
        project = await session.scalar(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
        if project is None:
            raise HTTPException(404, "Project not found")
        project.name = data.name.strip()
        if len(project.name) < 2:
            raise HTTPException(422, "Project name is too short")
        return project
