from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.config import get_settings
from app.db.session import Session
from app.auth import router as auth_router
from app.api.jobs import router as jobs_router

settings = get_settings()
origins = [value.strip() for value in settings.cors_origins.split(",") if value.strip()]
app = FastAPI(title="VenturePlan", version="1.0.0")


@app.middleware("http")
async def request_boundary(request, call_next):
    if request.method in ("POST", "PATCH", "DELETE") and request.headers.get("origin") not in (None, *origins):
        return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    try:
        async with Session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        raise HTTPException(503, "Database unavailable")


@app.get("/config")
def config():
    return {"agent_mode": settings.agent_mode, "openai_configured": bool(settings.openai_api_key),
            "web_search_enabled": settings.openai_web_search}


@app.post("/plans/generate", deprecated=True)
async def legacy_generate():
    raise HTTPException(410, "Use POST /jobs to generate and save a plan")


app.include_router(auth_router)
app.include_router(jobs_router)
