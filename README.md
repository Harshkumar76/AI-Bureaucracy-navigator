# 🇮🇳 AI Bureaucracy Navigator

**A multi-agent AI platform that helps people discover, understand, and apply for Indian government schemes, scholarships, and benefits — with explainable eligibility verdicts and links you can trust.**

> **Discover → Check Eligibility → Prepare Documents → Apply → Track → Resolve**

Describe your situation once. Five specialized agents find what you qualify for, explain *why*, build your document checklist, and hand you the verified official portal to apply on. Available in English, Hindi, Bengali, Tamil, and Telugu.

![Landing page](docs/landing.png)

## How the agents work

A user submits a profile form (every field optional) plus a free-text note. The Coordinator runs five agents in sequence, streaming each agent's live progress to the browser over Server-Sent Events:

```mermaid
flowchart TD
    U["👤 User<br/>form + free-text note"] -->|"POST /api/navigate"| C["🎯 Coordinator<br/>orchestrates pipeline, streams SSE"]

    C --> A1["📝 Intake Agent<br/>merges form fields with facts the LLM<br/>mines from the free-text note"]
    A1 --> P[("Structured profile<br/>(nullable fields)")]

    P --> A2["🔍 Discovery Agent<br/>structural state filter +<br/>semantic ranking (pgvector)"]
    DB[("PostgreSQL + pgvector<br/>16 schemes, rules, embeddings,<br/>documents, official URLs")] --> A2

    A2 -->|"ALL candidate schemes,<br/>ranked by relevance"| A3["⚖️ Eligibility Agent<br/>deterministic rule engine —<br/>no LLM guessing"]
    A3 -->|"verdicts + reasons"| A4["📄 Document Agent<br/>consolidated checklist,<br/>marks what you already have"]
    A4 --> A5["🔗 Verification Agent<br/>attaches provenance: official URL +<br/>last-verified date; optional live check"]

    A5 --> F["📋 Findings<br/>verdict cards + reasons + checklist<br/>+ AI summary"]
    F --> U

    C -.->|"live agent progress (SSE)"| U
```

### How a verdict is decided

The LLM **never** decides eligibility. Each scheme's rules are structured JSON evaluated in code — consistent, explainable, and free to run. Unknown answers are never treated as "no":

```mermaid
flowchart LR
    R["Scheme rules<br/>(structured JSON)"] --> E{"Evaluate each condition<br/>against the profile"}
    E -->|"all conditions pass"| EL["✅ Eligible<br/>with the reasons"]
    E -->|"any condition fails"| IN["❌ Not eligible<br/>with the exact rule that failed"]
    E -->|"any field unknown"| PO["❓ Possibly eligible<br/>+ the question that resolves it"]
```

### Where the LLM *is* used (optional, degrades gracefully)

| Task | Without API key | With API key (any OpenAI-compatible endpoint) |
|---|---|---|
| Free-text note → profile fields | note is saved, skipped | "*19yo girl from a farming family, 1.5L income*" → 8 structured fields |
| Results summary | deterministic template | warm, plain summary (length scales with number of findings) |
| Scheme content translation | English only | pre-translated into hi/bn/ta/te, stored in Postgres |
| Eligibility decisions | **rule engine — always** | **rule engine — always** |
| Links shown to users | **curated DB — always** | **curated DB — always** |

## Semantic Discovery (RAG)

The Discovery Agent combines two retrieval strategies:

1. **Structural filtering** — matches schemes by state applicability.
2. **Semantic ranking** — the free-text note is embedded locally via `sentence-transformers/all-MiniLM-L6-v2` (no external API call, so sensitive profile text never leaves the server) and compared against pre-computed scheme embeddings using pgvector cosine similarity, computed directly in PostgreSQL.

**Design principle: semantic search ranks, it never filters.** Every structurally-eligible scheme is still passed to the deterministic Eligibility Agent — similarity score only changes *display order*, never *membership*. This guarantees a scheme the user genuinely qualifies for can never be silently hidden just because their free-text phrasing didn't closely match that scheme's description. Top-K filtering before eligibility was considered and deliberately rejected: the rule engine is effectively free to run (microseconds, pure Python, no I/O), so there's no performance reason to narrow its input, and doing so trades away correctness for no real benefit — even at hundreds of schemes.

User Profile + Free Text
│
├── Structural filter (state match) — full candidate set
│
└── Local embedding → pgvector cosine similarity → similarity scores
│
▼
Full candidate set, RANKED by similarity (never narrowed)
│
▼
Deterministic Rule Engine (rules.py) — evaluates EVERY candidate
│
▼
LLM Summary (backend/llm.py) — explains results, never decides them


### Setup
```bash
pip install -r requirements.txt   # includes sentence-transformers, pgvector
python scripts/setup_pgvector_schema.py       # enables pgvector, adds embedding + tracking columns
python scripts/generate_scheme_embeddings.py  # embeds all schemes (idempotent, content-hash skipped)
python scripts/verify_embeddings.py           # sanity-checks stored vectors + dimensions
python scripts/test_retrieval.py              # manual interactive retrieval test
```

Re-run `generate_scheme_embeddings.py` any time schemes are added or edited — it embeds only new/changed content, skipping anything unchanged (tracked via content hash + embedding model version).

### Configuration (`.env`)

EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RAG_TOP_K=8
RAG_MIN_SIMILARITY=0.3
ENABLE_HNSW_INDEX=false # flip to true once the catalogue grows well past a few hundred schemes


### Scaling beyond 16 schemes: what's proven vs. what's designed-for

**Already built and verified to scale:**
- Embedding generation is idempotent and batched (32 at a time), with zero hardcoded assumptions about catalogue size.
- Retrieval computes cosine similarity inside PostgreSQL (`<=>` operator), not in Python, so query cost stays low regardless of table size.
- The rule engine's cost is negligible at any scale (pure Python, no I/O) — by design it evaluates every structurally-eligible candidate rather than a pre-filtered subset, so correctness never degrades as the catalogue grows.

**Designed for, not yet built:** an ingestion pipeline for safely adding hundreds of new scheme records — schema validation, duplicate-ID detection, and a review step before new schemes reach the live catalogue. Today, adding a scheme means manually writing a JSON record matching `schemes.json`'s shape and running `seed_schemes.py`; there's no automated scraping, LLM-assisted extraction, or validation layer yet. This is the correct next step for expanding the dataset, intentionally scoped separately from the retrieval/embedding work above so that expanding data quality and volume never risks the already-verified correctness of the existing pipeline.

## Evaluation System

Rather than relying on manual spot-checks, the project includes an automated evaluation harness covering every stage of the pipeline against 15 curated test cases spanning central schemes, edge cases (empty profiles, income boundaries, gender/residence exclusions), and free-text discovery.

### What's evaluated

| Stage | Metric | Threshold | Why |
|---|---|---|---|
| **Retrieval** | Precision@k, Recall@k, MRR, Hit Rate | Hit rate ≥ 0.7, MRR ≥ 0.5 | Does semantic search surface the right schemes for a free-text description? |
| **Eligibility** | Accuracy | **== 1.0 (exact)** | The rule engine is deterministic — any inaccuracy is a real bug, not noise |
| **Recommendation** | Precision/Recall on the final shown set | ≥ 80% of cases meet minimum relevance | Catches cases where a scheme is retrieved but the user is actually ineligible for it |
| **Explanation** | Grounding checks (no invented figures/schemes) | ≥ 85% pass rate | The LLM summary should never state a figure not present in the actual findings or the user's own profile |

**Note on thresholds:** deterministic components (the rule engine) are held to an exact bar, since any deviation is a genuine bug. LLM-dependent and API-rate-limited components (retrieval ranking quality, explanation grounding) use statistical thresholds instead, since they depend on factors outside the codebase's control (model non-determinism, free-tier rate limits) — demanding perfection there would make the test suite flaky rather than meaningful.

### Running the evaluation
```bash
python -m eval.run_evaluation
```
Prints a summary to the console and writes a full per-case breakdown to `eval/eval_report.json`.

### Running as automated tests (CI-ready)
```bash
pytest tests/test_metrics.py -v      # pure metric-math unit tests, no DB needed
pytest tests/test_rule_engine.py -v  # rule engine unit tests
pytest tests/test_evaluation.py -v   # full pipeline evaluation with pass/fail thresholds
```

### Actual results
============================================================
EVALUATION SUMMARY

Total cases: 15

Retrieval:
Precision@k: 0.275 Recall@k: 0.927
MRR: 0.838 Hit rate: 1.000

Eligibility:
Accuracy: 1.000 (15/15 cases fully correct)

Recommendation:
Meeting minimum relevance: 15/15
Avg precision: 0.160 Avg recall: 0.961

Explanation:
LLM available: True
Passed grounding checks: 14/15

**Note on precision@k (0.275) vs. hit rate (1.000):** at only 16 total schemes with `top_k=5`, retrieval always fills 5 slots even when just 1–2 schemes are truly relevant to a query — precision is naturally diluted at this catalogue size. Hit rate (1.000) and recall (0.927) are the metrics that matter here, and both are strong; precision should improve as the scheme count grows and categories become more distinct.

### Real bugs the evaluation caught

This isn't a decorative test suite — building it surfaced genuine defects:

- **A test-case authoring error, not a code bug:** an early eligibility test expected a 16-year-old to show `"possible"` for a scheme requiring `min_age: 18`. The rule engine correctly returned `"ineligible"` — a confirmed age below a stated minimum is a known fact, not missing data, so `"ineligible"` was the right verdict per `rules.py`'s own documented contract. The fix was correcting the test's expectation, not the code.
- **A vector-decoding chain across three failure modes** during pgvector integration (raw text vs. `Vector` object vs. correct numpy conversion) — each one only visible by actually running retrieval against a live database, not by code review alone.
- **A blind field-flattening bug** in the scheme-to-embedding document builder: an early version dumped every field (including `id`, `official_url`, raw document lists) into the embedded text with no curation, diluting semantic signal so badly that an insurance scheme outranked actual scholarships for an education-support query. Fixed by rebuilding the document from curated fields plus `rules.describe_rules()`'s plain-language eligibility sentences.
- **A confirmed LLM hallucination:** for a skill-training scheme with only a general benefit description (no monthly contribution figure), the model stated *"the first contribution can be as low as ₹42 per month"* — a specific number never present in the scheme data it was given. The grounding check correctly flagged it. This is the clearest evidence that the evaluation system does real work: it caught the model inventing a plausible-sounding but unverified fact.

## Screenshots

| Results with live agent panel | Scheme detail page |
|---|---|
| ![Results](docs/results.png) | ![Scheme detail](docs/scheme-detail.png) |

## Design principles

1. **Rules, not guesses.** Eligibility comes from a deterministic rule engine (`backend/rules.py`). Every verdict carries human-readable reasons; nothing is a black box.
2. **The LLM never writes URLs.** Links come from a curated database with a `last_verified` date stamped by `scripts/check_links.py` — hallucinated government links are the fastest way to lose user trust.
3. **Unknown ≠ ineligible.** A blank profile field makes a scheme "possibly eligible" and tells the user exactly which answer would settle it.
4. **Semantic search ranks, never filters.** RAG-based discovery reorders candidates by relevance but never removes a structurally-eligible scheme from evaluation — correctness always wins over neatness.
5. **Every claim is checked, not assumed.** An automated evaluation harness validates retrieval quality, rule-engine accuracy, and LLM explanation grounding on every run — not just "it looked right in a manual test."
6. **Honest by default.** Results are labeled indicative; final eligibility always rests with the concerned department against submitted documents.

## Architecture

frontend/ (vanilla HTML/CSS/JS, dark theme)
index.html landing page (public)
signin.html sign in / create account (public)
app.html + app.js the navigator app (session required)
scheme.html per-scheme detail page
i18n.js language switcher — loads locale JSON, applies data-i18n text
locales/ UI translations: en, hi, bn, ta, te
│ POST /api/navigate → text/event-stream (SSE)
backend/
main.py FastAPI app (serves frontend + API)
auth.py email/password auth — PostgreSQL + PBKDF2 + JWT cookies
models.py UserProfile / Finding (pydantic)
rules.py deterministic eligibility rule engine + criteria describer
llm.py optional OpenAI-compatible LLM layer
embeddings.py EmbeddingService — local sentence-transformer embeddings
scheme_document.py curated text builder for embedding (name, description, rules → plain language)
retrieval_service.py RetrievalService — pgvector cosine similarity search
rag_config.py RAG settings: EMBEDDING_MODEL, RAG_TOP_K, RAG_MIN_SIMILARITY
agents/
coordinator.py pipeline orchestration + SSE
intake.py discovery.py eligibility.py documents.py verification.py
database.py PostgreSQL schema and connection helpers
data/schemes.json one-time import source for the initial scheme catalogue
eval/
cases.json 15 curated evaluation cases
metrics.py precision@k, recall@k, MRR, hit rate
retrieval_eval.py scores RetrievalService against expected results
eligibility_eval.py scores rules.evaluate() against expected verdicts
recommendation_eval.py full pipeline: structural + ranked semantic → eligibility filter
explanation_eval.py grounding checks on LLM summary output
run_evaluation.py orchestrates all evaluations, writes eval_report.json
tests/
test_metrics.py pure unit tests for evaluation metrics
test_evaluation.py CI-ready pass/fail thresholds for the full pipeline
scripts/
check_links.py link checker (keeps "verified <date>" honest)
translate_schemes.py one-time job: translates scheme content into hi/bn/ta/te via LLM
setup_pgvector_schema.py enables pgvector, adds embedding columns (one-off, not in init_db)
generate_scheme_embeddings.py embeds schemes, idempotent via content hash
verify_embeddings.py sanity-checks stored vectors
test_retrieval.py manual interactive retrieval test
test_rule_engine.py rule engine tests


## API

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| POST | `/api/navigate` | session | run the agent pipeline (SSE stream) |
| GET | `/api/schemes?lang=` | public | scheme catalogue (`lang`: en/hi/bn/ta/te, default en) |
| GET | `/api/schemes/{id}?lang=` | public | full scheme record + plain-language criteria, localized |
| POST | `/api/auth/register` | — | create account, sets JWT cookie |
| POST | `/api/auth/login` | — | sign in, sets JWT cookie |
| POST | `/api/auth/logout` | session | end session |
| GET | `/api/auth/me` | session | current user |
| GET | `/api/health` | public | liveness |

**Auth:** email/password with signed JWTs in an HttpOnly, SameSite cookie (7-day expiry). Users and revoked-token records live in PostgreSQL. PBKDF2-SHA256 is used with per-user salts; API clients can also use `Authorization: Bearer <token>`.

## Quick start

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
# open http://localhost:8000
```

Works fully offline with no API key. Optional extras:

```bash
# enable free-text extraction + AI summary + scheme translation (any OpenAI-compatible endpoint, e.g. Groq)
export LLM_API_KEY=...
export LLM_BASE_URL=https://api.groq.com/openai/v1
export LLM_MODEL=openai/gpt-oss-120b

# live-check official links during the Verification stage
export VERIFY_LINKS=1

# semantic discovery (see "Semantic Discovery (RAG)" above for full setup)
python scripts/setup_pgvector_schema.py
python scripts/generate_scheme_embeddings.py
```

Verify scheme links (run before demos; `--stamp` updates the verified dates):

```bash
python scripts/check_links.py --stamp
```

## JWT configuration

Authentication issues a signed JWT named `access_token` in an HttpOnly, SameSite cookie (seven-day expiry). API clients can instead send `Authorization: Bearer <token>`. Logout revokes the token ID until expiry.

For production, configure a stable, high-entropy secret and HTTPS cookies:

```bash
export JWT_SECRET="replace-with-a-long-random-secret"
export COOKIE_SECURE=true
```

## PostgreSQL setup

The application stores user accounts, revoked JWTs, scheme records (including translations), and scheme embeddings in PostgreSQL. `backend/data/schemes.json` is retained only as the one-time import source; the running application never reads it.

For local development, start PostgreSQL with Docker:

```bash
docker compose up -d postgres
```

Configure the connection and import the catalogue:

```bash
# PowerShell
$env:DATABASE_URL = "postgresql://navigator:navigator_dev_password@localhost:5432/navigator"
python scripts/seed_schemes.py
python scripts/setup_pgvector_schema.py
python scripts/generate_scheme_embeddings.py
uvicorn backend.main:app --reload
```

For a deployed database, set `DATABASE_URL` to its PostgreSQL URL and run `python scripts/seed_schemes.py` during deployment. The seed command is idempotent: it inserts new schemes and updates existing IDs.

A `.env` file in the repo root is the simplest way to set `DATABASE_URL`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and the RAG settings (`EMBEDDING_MODEL`, `RAG_TOP_K`, `RAG_MIN_SIMILARITY`, `ENABLE_HNSW_INDEX`) for local development — loaded automatically via `python-dotenv`. Keep `.env` out of version control (already covered by `.gitignore`).

## Multi-language support

The UI — navigation, the profile form, live agent panel, results cards, checklist, and sign-in flow — is available in **English, Hindi, Bengali, Tamil, and Telugu** via a lightweight `frontend/i18n.js` loader. No build step or framework: static text uses `data-i18n` attributes matched against JSON dictionaries in `frontend/locales/`, and the chosen language persists in the browser via `localStorage`. A dropdown in the nav bar on every page lets users switch instantly.

Scheme content (name, benefit, description, eligibility criteria, required documents) is **pre-translated once and stored** in the `schemes.translations` column (JSONB) rather than translated live on every request — this keeps scheme pages fast and avoids repeated LLM cost. Generate or refresh translations with:

```bash
python scripts/translate_schemes.py
```

This calls the configured LLM (`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`) once per scheme per language. It's resumable — re-running only fills in languages that are still missing rather than re-translating everything.

Machine translation of eligibility-critical text (income thresholds, age cutoffs, required documents) should be spot-checked by a native speaker before relying on it in production.

## Scheme database

16 central-government schemes across Education, Agriculture, Health, Housing, Pension, Insurance, Welfare, Livelihood, Savings, and Skill Development — including PM-KISAN, NSP scholarships (CSSS, Post-Matric SC/Minority, NMMSS), Ayushman Bharat PM-JAY, PMAY-Gramin, Ujjwala 2.0, Atal Pension Yojana, PM Vishwakarma, Sukanya Samriddhi, and NSAP pensions. Each record carries structured eligibility rules, required documents, apply route, and a live-verified official URL. The schema already supports state-level schemes (`"state": "Karnataka"`). See "Scaling beyond 16 schemes" above for what's needed to grow this responsibly.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI (Python) | async SSE streaming, pydantic validation |
| Agents | custom lightweight pipeline | deterministic orchestration, zero token cost for rules |
| LLM | any OpenAI-compatible endpoint | Groq / OpenAI / local — swappable via env vars |
| Embeddings | sentence-transformers (local) | zero API cost, keeps sensitive free-text input off third-party servers |
| Vector search | pgvector (PostgreSQL extension) | cosine similarity search co-located with existing data, no separate vector DB to run |
| Data | PostgreSQL | durable user, token-revocation, scheme, translation, and embedding storage |
| Frontend | vanilla HTML/CSS/JS | no build step, SSE via fetch streams, i18n via JSON dictionaries |
| Evaluation | pytest + custom harness | CI-ready, mixed exact/statistical thresholds per component |

## Roadmap

- [x] Vector search (pgvector) over scheme descriptions for fuzzy discovery
- [x] Automated evaluation system (retrieval, eligibility, recommendation, explanation grounding)
- [ ] Ingestion pipeline: schema validation, duplicate detection, and a review step for safely expanding the scheme catalogue (see "Scaling beyond 16 schemes")
- [ ] Expand catalogue to 200–500 schemes across Central + State governments, sourced from official portals only
- [ ] One-tap gap filling: answer a "possibly eligible" question and re-run instantly
- [ ] Voice intake via Whisper (speak your situation in any language) — model already available on Groq (`whisper-large-v3`)
- [ ] Deadline tracking + reminders (Postgres + cron)
- [ ] DigiLocker integration — auto-verify issued documents, catch income/certificate mismatches before applying
- [ ] Resolution agent — RTI templates, grievance-portal (CPGRAMS) guidance
- [ ] WhatsApp bot interface

## Disclaimer

Results are **indicative**, based on self-declared information. Final eligibility is decided by the concerned department against submitted documents. Always confirm on the official portal linked with each scheme.