"""AI Bureaucracy Navigator — FastAPI app.

Run from the repo root:
    uvicorn backend.main:app --reload

Then open http://localhost:8000
"""
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Query
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

SUPPORTED_LANGS = {"en", "hi", "bn", "ta", "te"}


@app.on_event("startup")
def initialise_database():
    init_db()


def _localize(scheme_data: dict, translations: dict, lang: str) -> dict:
    """Overlay translated fields onto the English base. Falls back to English
    for any field missing from the translation (e.g. if a translation call
    failed for one scheme)."""
    if lang == "en" or lang not in translations:
        return scheme_data
    t = translations[lang]
    merged = dict(scheme_data)
    for key in ("name", "benefit", "description", "apply_mode", "documents"):
        if t.get(key):
            merged[key] = t[key]
    return merged


@app.get("/api/schemes")
async def list_schemes(lang: str = Query("en")):
    """Public scheme catalogue (summary fields only)."""
    lang = lang if lang in SUPPORTED_LANGS else "en"
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id, name, category, level, benefit, official_url,
                              last_verified, translations
                       FROM schemes ORDER BY name""")
        rows = cur.fetchall()

    results = []
    for row in rows:
        t = row.pop("translations") or {}
        if lang != "en" and lang in t:
            row["name"] = t[lang].get("name", row["name"])
            row["benefit"] = t[lang].get("benefit", row["benefit"])
        results.append(row)
    return results


@app.get("/api/schemes/{scheme_id}")
async def scheme_detail(scheme_id: str, lang: str = Query("en")):
    """Full record for one scheme + human-readable eligibility criteria."""
    lang = lang if lang in SUPPORTED_LANGS else "en"
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT data, translations FROM schemes WHERE id = %s", (scheme_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Scheme not found")

        scheme = _localize(row["data"], row["translations"] or {}, lang)
        translated = (row["translations"] or {}).get(lang, {})
        criteria = translated.get("criteria") or describe_rules(scheme["rules"])
        return {**scheme, "criteria": criteria}


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