"""AI Bureaucracy Navigator — FastAPI app.

Run from the repo root:
    uvicorn backend.main:app --reload
Then open http://localhost:8000
"""
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.agents.coordinator import run_pipeline
from backend.auth import require_user, router as auth_router
from backend.models import UserProfile

app = FastAPI(title="AI Bureaucracy Navigator", version="0.2.0")
app.include_router(auth_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


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
