"""Optional LLM layer (OpenAI-compatible endpoint).

Used ONLY for:
  1. mining the free-text box into structured profile fields (intake)
  2. writing a friendly summary of the findings

Eligibility itself is decided by the deterministic rule engine in rules.py.
If no API key is configured, both features degrade gracefully and the
whole pipeline still works end-to-end.

Configure via environment variables:
  LLM_API_KEY   (or OPENAI_API_KEY)
  LLM_BASE_URL  default https://api.openai.com/v1
  LLM_MODEL     default gpt-4o-mini
"""
import json
import os
import re
from typing import Optional

import requests


def _cfg():
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    return {
        "key": key,
        "base": (os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
        "model": os.getenv("LLM_MODEL") or "gpt-4o-mini",
    }


def available() -> bool:
    return bool(_cfg()["key"])


def _chat(messages, max_tokens=600) -> Optional[str]:
    cfg = _cfg()
    if not cfg["key"]:
        return None
    try:
        r = requests.post(
            f"{cfg['base']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['key']}"},
            json={"model": cfg["model"], "messages": messages,
                  "temperature": 0, "max_tokens": max_tokens},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None  # never let the LLM layer break the pipeline


EXTRACT_PROMPT = """You extract facts from a user's note into profile fields for an Indian government-scheme finder.
Allowed fields and values:
  age (int), gender (male/female/other), residence (rural/urban), annual_income (int, INR),
  category (General/OBC/SC/ST/EWS), religion (Hindu/Muslim/Christian/Sikh/Buddhist/Jain/Parsi/Other),
  occupation (student/farmer/salaried/self_employed/unemployed/unorganised_worker/artisan/other),
  education_level (below_10th/10th_pass/12th_pass/ug/pg/not_studying),
  marital_status (single/married/widowed/divorced), disability_pct (int),
  has_bpl_card (bool), owns_cultivable_land (bool), owns_pucca_house (bool),
  has_girl_child_under_10 (bool)
Return ONLY a JSON object with the fields you are confident about. Empty object if none."""


def extract_facts(text: str) -> dict:
    """Mine the optional free-text box for structured profile fields."""
    raw = _chat([
        {"role": "system", "content": EXTRACT_PROMPT},
        {"role": "user", "content": text},
    ])
    if not raw:
        return {}
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def summarize(profile_dict: dict, findings: list) -> Optional[str]:
    """One friendly paragraph summarising results. None if no LLM configured."""
    brief = [
        {"name": f["name"], "status": f["status"], "benefit": f["benefit"]}
        for f in findings if f["status"] in ("eligible", "possible")
    ]
    return _chat([
        {"role": "system", "content":
            "You are a helpful assistant for Indian government schemes. In 3-4 warm, plain sentences, "
            "summarise the findings for the user: what they qualify for, the standout benefit, and what to do next. "
            "Do NOT invent schemes, amounts, or links."},
        {"role": "user", "content":
            f"Profile: {json.dumps(profile_dict)}\nFindings: {json.dumps(brief, ensure_ascii=False)}"},
    ], max_tokens=250)
