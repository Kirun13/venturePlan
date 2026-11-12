"""Explicit, single-job provider smoke test. Never run as part of pytest."""
import asyncio
import json
import logging
from pathlib import Path
from sqlalchemy import select
from app.config import get_settings
from app.db.jobs import enqueue, claim
from app.db.models import PlanJob, JobEvent
from app.db.session import Session, engine
from app.schemas.models import BusinessIdeaInput
from app.worker import process_job

async def main():
    settings = get_settings()
    if settings.agent_mode != "openai" or not settings.openai_api_key:
        raise RuntimeError("Configure AGENT_MODE=openai and OPENAI_API_KEY before this explicit smoke test")
    settings.worker_max_attempts = 1
    settings.openai_max_retries = 0
    settings.openai_max_output_tokens = min(settings.openai_max_output_tokens, 4000)
    idea = BusinessIdeaInput(name="Кофейный киоск", description="Небольшой киоск кофе навынос рядом с офисами в Астане",
        target_audience="Сотрудники офисов", initial_budget=2000000, unit_price=1500, estimated_monthly_units=1000)
    saved = await enqueue(idea.model_dump(mode="json"))
    item = await claim()
    if item is None or item.id != saved.id:
        raise RuntimeError("Run the smoke test against an isolated empty queue")
    await asyncio.wait_for(process_job(item), timeout=600)
    async with Session() as session:
        job = await session.get(PlanJob, saved.id)
        events = (await session.scalars(select(JobEvent).where(JobEvent.job_id==saved.id).order_by(JobEvent.id))).all()
        report = {"status":job.status, "model":settings.openai_model, "error":job.error,
                  "events":[{"kind":e.kind,"node":e.node,"details":e.details} for e in events]}
        out=Path("../output/verification")
        out.mkdir(parents=True,exist_ok=True)
        (out/"openai-smoke.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        if job.result_data:
            (out/"openai-plan.json").write_text(json.dumps(job.result_data,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({"status":job.status,"model":settings.openai_model,"error":job.error,
                          "provider_calls":sum(e.kind=="usage" for e in events),
                          "total_tokens":sum(e.details.get("total_tokens",0) for e in events if e.kind=="usage")},ensure_ascii=False))
    await engine.dispose()

if __name__=="__main__":
    logging.basicConfig(filename="../output/verification/openai-smoke.log",level=logging.ERROR)
    asyncio.run(main())
