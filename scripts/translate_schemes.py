"""Translate scheme content (name, benefit, description, documents, apply_mode,
criteria) into Hindi, Bengali, Tamil, and Telugu, and store the results in the
`schemes.translations` JSONB column.

Idempotent-ish: re-run any time after editing schemes.json / rules.py; it will
overwrite existing translations for the schemes it processes. Safe to run
repeatedly.

Requires the same LLM env vars as the rest of the app:
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL   (see README "Quick start")

Run:
    python scripts/translate_schemes.py
    python scripts/translate_schemes.py --only pmkisan pmjay   # just a few
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))
from backend.database import db_connection
from backend.rules import describe_rules

LANGUAGES = {
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
}

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


def translate_fields(fields: dict, lang_name: str, max_retries: int = 5) -> dict:
    """One LLM call per scheme per language. Sends a JSON object of fields to
    translate, asks for the same JSON shape back with values translated.
    Retries with exponential backoff on 429 (rate limit)."""
    system = (
        f"You translate Indian government scheme information from English into {lang_name}. "
        "You will receive a JSON object. Translate every string value naturally and accurately "
        "into the target language, preserving meaning exactly (this is official government "
        "scheme information — accuracy matters more than style). Do NOT translate proper nouns "
        "like scheme names' acronyms if they are commonly used untranslated (e.g. 'PM-KISAN'), "
        "but do translate descriptive text. Keep numbers, currency amounts (₹), and percentages "
        "as-is. Preserve the exact same JSON structure and keys — only translate the string "
        "values. Lists must stay the same length and order. "
        "Respond with ONLY the translated JSON object, no markdown fences, no commentary."
    )
    delay = 5
    for attempt in range(max_retries):
        resp = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(fields, ensure_ascii=False)},
                ],
                "temperature": 0.2,
            },
            timeout=60,
        )
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            wait = float(retry_after) if retry_after else delay
            print(f"    rate limited, waiting {wait:.0f}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(wait)
            delay *= 2
            continue
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    raise RuntimeError(f"gave up after {max_retries} retries (still rate limited)")


def main():
    if not LLM_API_KEY:
        print("LLM_API_KEY is not set — cannot translate. See README 'Quick start' for the env vars.")
        raise SystemExit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="only these scheme IDs")
    args = parser.parse_args()

    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, data, translations FROM schemes ORDER BY id")
        schemes = cur.fetchall()

        for scheme in schemes:
            scheme_id = scheme["id"]
            if args.only and scheme_id not in args.only:
                continue
            data = scheme["data"]
            translations = scheme["translations"] or {}

            source_fields = {
                "name": data["name"],
                "benefit": data["benefit"],
                "description": data.get("description", ""),
                "apply_mode": data.get("apply_mode", ""),
                "documents": data.get("documents", []),
                "criteria": describe_rules(data["rules"]),
            }

            changed = False
            for lang_code, lang_name in LANGUAGES.items():
                if lang_code in translations:
                    continue  # already done — resumable
                print(f"Translating {scheme_id} -> {lang_name}...")
                try:
                    translations[lang_code] = translate_fields(source_fields, lang_name)
                    changed = True
                except Exception as e:
                    print(f"  FAILED ({lang_code}): {e}")
                    continue
                time.sleep(2)  # stay under Groq free-tier rate limits

            if changed:
                cur.execute(
                    "UPDATE schemes SET translations = %s WHERE id = %s",
                    (json.dumps(translations, ensure_ascii=False), scheme_id),
                )
                conn.commit()
            print(f"  done: {scheme_id} ({len(translations)}/4 languages)")

    print("\nAll translations saved. Re-run this script anytime to fill in any gaps.")


if __name__ == "__main__":
    main()