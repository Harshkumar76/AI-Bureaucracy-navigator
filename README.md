# 🇮🇳 AI Bureaucracy Navigator

A multi-agent AI platform that helps users **discover, understand, apply for, and track** government schemes, scholarships, and benefits.

> **Discover → Check Eligibility → Prepare Documents → Apply → Track → Resolve**

This MVP covers the first three stages end-to-end: a user fills a simple profile form (plus an optional free-text note), watches specialized agents coordinate in real time, and gets matched schemes with **explainable eligibility verdicts, a consolidated document checklist, and verified official links**.

## Demo flow

1. **Profile form** — every field optional; a free-text box catches anything the form misses ("my father passed away last year").
2. **Agents work live** — the UI streams each agent's progress over Server-Sent Events:
   - 📝 **Intake Agent** — merges form fields + LLM-extracted facts from the free-text note
   - 🔍 **Discovery Agent** — pulls candidates from the indexed scheme database
   - ⚖️ **Eligibility Agent** — runs a **deterministic rule engine** (no LLM guessing) → eligible / possibly eligible / not eligible, with reasons
   - 📄 **Document Agent** — builds a deduplicated document checklist, marks what you already have
   - 🔗 **Verification Agent** — every link comes from the curated database with a last-verified date; optional live link-check
3. **Findings** — one card per scheme: benefit, verdict **with reasons**, required documents, official portal link + provenance.

## Architecture

```
frontend/  (vanilla HTML/CSS/JS — form, SSE agent panel, findings cards)
    │  POST /api/navigate  →  text/event-stream
backend/
    main.py                 FastAPI app (serves frontend + API)
    models.py               UserProfile / Finding (pydantic)
    rules.py                deterministic eligibility rule engine
    llm.py                  optional OpenAI-compatible LLM layer
    agents/
        coordinator.py      pipeline orchestration + SSE
        intake.py  discovery.py  eligibility.py  documents.py  verification.py
    data/schemes.json       seed DB: 16 central schemes with rules + official URLs
scripts/check_links.py      link checker (keeps "verified <date>" honest)
```

**Design principles**

- **The LLM never decides eligibility.** Scheme rules are structured JSON evaluated in code — consistent, explainable, free. The LLM only mines free text into profile fields and writes the results summary.
- **The LLM never writes URLs.** Links come from the curated database with `last_verified` provenance; `scripts/check_links.py` keeps them honest.
- **Unknown ≠ ineligible.** Blank profile fields make a scheme "possibly eligible" with the exact question that would resolve it.

## Quick start

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
# open http://localhost:8000
```

Works fully offline with no API key. Optional extras:

```bash
# enable free-text extraction + AI summary (any OpenAI-compatible endpoint)
export LLM_API_KEY=sk-...
export LLM_BASE_URL=https://api.openai.com/v1   # default
export LLM_MODEL=gpt-4o-mini                    # default

# live-check official links during the Verification stage
export VERIFY_LINKS=1
```

Verify scheme links (run before demos; `--stamp` updates the verified dates):

```bash
python scripts/check_links.py --stamp
```

## Roadmap

- [ ] Vector search (pgvector) over scheme descriptions for fuzzy discovery
- [ ] Ingestion pipeline: crawl myScheme / NSP / department portals, LLM-extract rules JSON at ingestion time
- [ ] State-specific scheme packs
- [ ] Application guidance + deadline tracking (Postgres + cron)
- [ ] DigiLocker integration — auto-verify issued documents, catch word-vs-certificate mismatches before applying
- [ ] Resolution agent — RTI templates, grievance-portal guidance
- [ ] CrewAI Flows for the long-running Apply → Track → Resolve journey

## Disclaimer

Results are **indicative**, based on self-declared information. Final eligibility is decided by the concerned department against submitted documents. Always confirm on the official portal linked with each scheme.
