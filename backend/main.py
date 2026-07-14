"""AI Bureaucracy Navigator — FastAPI app.

Run from the repo root:
    uvicorn backend.main:app --reload
Then open http://localhost:8000
"""
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from backend.agents.coordinator import run_pipeline
from backend.auth import require_user, router as auth_router
from backend.models import UserProfile, Scheme
from backend.rules import describe_rules
from backend.database import AsyncSessionLocal

app = FastAPI(title="AI Bureaucracy Navigator", version="0.2.0")
app.include_router(auth_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# ============================================================
# POSTGRESQL IMPLEMENTATION (single source of truth)
# ============================================================
async def _load_schemes_db():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Scheme))
        return result.scalars().all()

@app.get("/api/schemes")
async def list_schemes():
    """Public scheme catalogue (summary fields only)."""
    schemes = await _load_schemes_db()
    keep = ("id", "name", "category", "level", "benefit", "official_url", "last_verified")
    return [{k: getattr(s, k) for k in keep} for s in schemes]

@app.get("/api/schemes/{scheme_id}")
async def scheme_detail(scheme_id: int):
    """Full record for one scheme + human-readable eligibility criteria."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Scheme).where(Scheme.id == scheme_id))
        scheme = result.scalar_one_or_none()

        if not scheme:
            raise HTTPException(404, "Scheme not found")

        return {
            "id": scheme.id,
            "name": scheme.name,
            "category": scheme.category,
            "level": scheme.level,
            "benefit": scheme.benefit,
            "official_url": scheme.official_url,
            "last_verified": scheme.last_verified,
            "rules": scheme.rules,
            "criteria": describe_rules(scheme.rules),
        }

@app.post("/api/navigate")
async def navigate(profile: UserProfile, user: dict = Depends(require_user)):
    """Run the agent pipeline; streams Server-Sent Events. Sign-in required."""
    return StreamingResponse(
        run_pipeline(profile),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.get("/api/health")
async def health():
    return {"status": "ok"}

# serve the frontend (must be mounted last so /api routes win)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
