"""AI Bureaucracy Navigator — FastAPI app.

Run from the repo root:
    uvicorn backend.main:app --reload

Then open http://localhost:8000
"""
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.agents.coordinator import run_pipeline
from backend.auth import require_user, router as auth_router
from backend.database import db_connection, init_db
from backend.models import UserProfile
from backend.rules import describe_rules

app = FastAPI(title="AI Bureaucracy Navigator", version="0.3.0")
app.include_router(auth_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.on_event("startup")
def initialise_database():
    init_db()


@app.get("/api/schemes")
async def list_schemes():
    """Public scheme catalogue (summary fields only)."""
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id, name, category, level, benefit, official_url, last_verified
                       FROM schemes ORDER BY name""")
        return cur.fetchall()


@app.get("/api/schemes/{scheme_id}")
async def scheme_detail(scheme_id: str):
    """Full record for one scheme + human-readable eligibility criteria."""
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT data FROM schemes WHERE id = %s", (scheme_id,))
        row = cur.fetchone()
        if row:
            scheme = row["data"]
            return {**scheme, "criteria": describe_rules(scheme["rules"])}
    raise HTTPException(404, "Scheme not found")


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