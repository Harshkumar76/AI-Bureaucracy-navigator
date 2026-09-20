# AI Bureaucracy Navigator

AI Bureaucracy Navigator is a FastAPI-based government-scheme discovery application that combines:

- Structured user profiles
- Scheme discovery via semantic retrieval
- Deterministic eligibility checks
- Document matching
- Optional LLM-based extraction and summaries
- PostgreSQL-backed persistence

The guiding rule is simple:

> **RAG helps find likely schemes; the rule engine decides eligibility.**

---

## What the App Does

The application lets a user enter a structured profile and optionally provide a free-text note. It then evaluates relevant schemes from a curated government-scheme catalogue.

The application returns:

- Likely relevant schemes
- Eligibility status: `eligible` / `possible` / `ineligible`
- Reasons for each eligibility decision
- Required and missing documents
- Official scheme links
- A final summary of the findings

---

## Architecture

The application is built around a multi-agent workflow:

### 1. Intake Agent

- Builds a structured profile from the form
- Optionally extracts additional facts from the free-text note using the LLM

### 2. Discovery Agent

- Applies structural/applicability checks to narrow the scheme catalogue
- Ranks the remaining candidates using semantic similarity search over pgvector embeddings

### 3. Eligibility Agent

- Evaluates scheme rules against the structured profile
- Returns `eligible`, `possible`, or `ineligible`
- Records reasons and unknown fields

### 4. Documents Agent

- Compares required scheme documents with documents already available to the user
- Identifies missing documents

### 5. Verification Agent

- Attaches official scheme links
- Provides verification metadata

The pipeline streams progress to the frontend using **Server-Sent Events (SSE)**.

---

## Core Principles

- The LLM is optional and is used for fact extraction and summarization only.
- Eligibility is decided by the deterministic rule engine in [`backend/rules.py`](backend/rules.py).
- Retrieval is used for relevance ranking, not final eligibility.
- The system separates probabilistic language-model behavior from deterministic eligibility logic.
- The application is designed to be explainable and reproducible.

---

## Tech Stack

- Python
- FastAPI
- PostgreSQL
- pgvector
- Pydantic
- JWT Authentication
- SentenceTransformers
- Optional OpenAI-compatible LLM integration
- HTML
- CSS
- JavaScript
- Server-Sent Events (SSE)

---

## Repository Structure

```text
AI-Bureaucracy-navigator/

├── backend/
│   ├── agents/
│   │   ├── base.py
│   │   ├── coordinator.py
│   │   ├── discovery.py
│   │   ├── documents.py
│   │   ├── eligibility.py
│   │   ├── intake.py
│   │   └── verification.py
│   ├── data/
│   │   └── schemes.json
│   ├── auth.py
│   ├── database.py
│   ├── embeddings.py
│   ├── llm.py
│   ├── main.py
│   ├── models.py
│   ├── rag_config.py
│   ├── retrieval_service.py
│   ├── rules.py
│   └── scheme_document.py
│
├── eval/
│   ├── cases.json
│   ├── classifier/
│   ├── eligibility_eval.py
│   ├── explanation_eval.py
│   ├── metrics.py
│   ├── recommendation_eval.py
│   ├── retrieval_eval.py
│   └── run_evaluation.py
│
├── frontend/
│   ├── app.html
│   ├── app.js
│   ├── i18n.js
│   ├── index.html
│   ├── scheme.html
│   ├── signin.html
│   ├── style.css
│   └── locales/
│
├── scripts/
│   ├── check_links.py
│   ├── generate_scheme_embeddings.py
│   ├── seed_schemes.py
│   ├── setup_pgvector_schema.py
│   ├── translate_schemes.py
│   └── verify_embeddings.py
│
├── tests/
│   ├── __init__.py
│   ├── test_evaluation.py
│   ├── test_full_pipeline.py
│   ├── test_metrics.py
│   ├── test_rag_rules.py
│   ├── test_retrieval.py
│   └── test_rule_engine.py
│
├── .env.example
├── docker-compose.yml
├── README.md
├── requirements.txt
└── ...
```

---

## Prerequisites

- Python 3.10+
- PostgreSQL with pgvector enabled
- A local or cloud LLM provider only if you want automatic profile extraction or LLM-generated summaries

---

## Setup

### 1. Clone the Project

```bash
git clone https://github.com/Harshkumar76/AI-Bureaucracy-navigator.git
cd AI-Bureaucracy-navigator
```

### 2. Create and Activate a Virtual Environment

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### macOS/Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If you plan to run the test suite, also install `pytest` and any additional evaluation dependencies required by the project.

---

## Environment Variables

Create a `.env` file in the project root.

At minimum, configure PostgreSQL and JWT settings:

```env
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/navigator
JWT_SECRET=change-this-to-a-long-random-secret

RAG_TOP_K=10
RAG_MIN_SIMILARITY=0.0
ENABLE_HNSW_INDEX=true

LLM_API_KEY=your-api-key-if-using-llm
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

### Environment Variable Notes

- The application reads environment variables using `python-dotenv`.
- LLM variables are optional.
- The application can perform its core scheme retrieval and eligibility workflow without an LLM.
- `DATABASE_URL` must point to a valid PostgreSQL instance.
- Never commit the real `.env` file or API keys to GitHub.
- Replace the example `JWT_SECRET` with a long random secret in actual deployments.

---

## PostgreSQL + pgvector Setup

Create the database and enable the pgvector extension:

```sql
CREATE DATABASE navigator;
```

Then connect to the database:

```sql
\c navigator
```

Enable pgvector:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Initialize the application schema:

```bash
python scripts/setup_pgvector_schema.py
```

Seed the scheme catalogue:

```bash
python scripts/seed_schemes.py
```

Generate embeddings:

```bash
python scripts/generate_scheme_embeddings.py
```

Verify the generated embeddings:

```bash
python scripts/verify_embeddings.py
```

---

## Retrieval-Augmented Generation (RAG)

The application uses semantic retrieval to identify schemes that are relevant to a user's profile.

### Embedding Model

The project uses:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The embeddings have:

```text
384 dimensions
```

Embeddings are generated locally and stored in PostgreSQL using pgvector.

### Retrieval Configuration

The current retrieval configuration uses:

```text
RAG_TOP_K=10
RAG_MIN_SIMILARITY=0.0
ENABLE_HNSW_INDEX=true
```

The retrieval stage produces a ranked shortlist of relevant schemes.

Importantly:

> **Semantic similarity does not determine eligibility.**

The retrieved schemes are subsequently evaluated by the deterministic rule engine.

### RAG Flow

```text
User Profile
     │
     ▼
Profile / Query Representation
     │
     ▼
SentenceTransformer Embedding
     │
     ▼
pgvector Similarity Search
     │
     ▼
Ranked Scheme Candidates
     │
     ▼
Deterministic Rule Engine
     │
     ▼
Eligibility Result
```

---

## Eligibility Rule Engine

Eligibility is handled by a deterministic rule engine in:

```text
backend/rules.py
```

The rule engine evaluates structured profile fields against scheme-specific rules.

Supported rule categories include:

- Minimum age
- Maximum age
- Maximum income
- Gender
- Category
- Occupation
- Residence
- Education level
- Religion
- Disability percentage
- Marital status
- Bank-account requirements
- LPG connection requirements
- Income-tax status
- Government-employee status
- BPL-card requirements
- Cultivable-land requirements
- Pucca-house requirements
- Girl-child requirements
- Breadwinner-related conditions
- External verification requirements

### Tri-State Eligibility

The engine uses three possible eligibility states:

```text
eligible
possible
ineligible
```

The logic is:

```text
Any failed condition
        │
        ▼
    ineligible

No failed condition
but some information is unknown
        │
        ▼
     possible

All required conditions pass
        │
        ▼
     eligible
```

This prevents incomplete information from being incorrectly treated as eligibility.

---

## Eligibility and RAG Separation

The project intentionally separates **retrieval** from **eligibility**.

For example:

```text
RAG:
"Which schemes appear relevant to this user?"

        ↓

Rule Engine:
"Does this user's profile satisfy the scheme's eligibility conditions?"

        ↓

Result:
eligible / possible / ineligible
```

This separation makes the final eligibility decision deterministic and easier to inspect and test.

---

## Optional LLM Features

The LLM layer is implemented in [`backend/llm.py`](backend/llm.py).

The LLM is used for:

- Extracting structured facts from the free-text profile note
- Generating short summaries or explanations

The LLM does **not** act as the final eligibility authority.

The eligibility decision is still produced by the deterministic rule engine.

If no LLM API key is configured, the LLM-dependent features can be disabled while the rest of the application continues to operate.

---

## Authentication

The backend includes JWT-based authentication with:

- Registration
- Login
- Logout
- Token revocation
- Protected routes
- Dependency-based authentication checks

Authentication is kept separate from the scheme retrieval and eligibility logic.

---

## Documents

The Documents Agent compares:

```text
Required scheme documents
        +
Documents already available to the user
        ↓
Missing documents
```

This allows the application to show users which documents may still be required for a scheme.

---

## Verification

The Verification Agent attaches scheme metadata including:

- Official scheme URL
- Application mode
- Last verification information
- Link status where available

The application is intended to help users discover schemes, but users should still verify current requirements and application information through the relevant official government source.

---

## Classifier Experiment

The project also contains an experimental multi-label classifier used to investigate whether structured profile eligibility labels can be approximated using a lightweight machine-learning model.

The experiment uses:

- TF-IDF features
- Unigram and bigram features
- One-vs-Rest Logistic Regression
- Deterministic rule-engine labels as ground truth
- A fixed train/test split
- Micro, macro, and weighted precision/recall/F1
- Exact label-set match
- Hamming loss

### Synthetic Dataset

The classifier experiment uses a synthetic dataset containing:

```text
520 profiles
26 targetable schemes
```

Four schemes are excluded from the synthetic classifier experiment because their remaining eligibility logic depends only on external verification and therefore cannot be reliably inferred from a generated user profile.

The labels are generated from the deterministic rule engine rather than from LLM judgments.

The LLM may be used to rewrite structured synthetic profiles into natural-language descriptions, but it does not determine the ground-truth labels.

### Classifier Role

The classifier is an experimental approximation/shortlisting mechanism.

It does **not** replace the production rule engine.

The production architecture remains:

```text
Profile
   │
   ├── Semantic Retrieval
   │
   └── Deterministic Eligibility Rules
                    │
                    ▼
          Final Eligibility Result
```

---

## Evaluation

The project contains evaluation scripts covering multiple parts of the system.

Evaluation areas include:

- Retrieval quality
- Eligibility accuracy
- Recommendation quality
- Explanation quality
- End-to-end behavior
- Classifier performance

The evaluation framework uses deterministic rule-engine outputs where appropriate so that eligibility evaluation does not depend on an LLM making the final decision.

---

## Testing

The project contains pytest-based tests for retrieval, rule evaluation, metrics, and end-to-end behavior.

Run the complete test suite:

```bash
pytest
```

Run individual test files:

```bash
pytest tests/test_retrieval.py
```

```bash
pytest tests/test_rule_engine.py
```

```bash
pytest tests/test_full_pipeline.py
```

---

## Run the Backend

Start the FastAPI development server:

```bash
uvicorn backend.main:app --reload
```

The backend is available at:

```text
http://localhost:8000
```

Swagger API documentation:

```text
http://localhost:8000/docs
```

---

## Frontend

The frontend is implemented as a static HTML/CSS/JavaScript application and is served through the FastAPI backend.

The project includes:

- Sign-in page
- Scheme discovery flow
- Scheme detail page
- Multilingual locale support
- Eligibility result presentation
- Document status information

---

## SSE Progress Streaming

The application uses **Server-Sent Events (SSE)** to stream progress from the backend while the multi-stage pipeline executes.

A simplified workflow is:

```text
Client
  │
  ▼
POST /api/navigate
  │
  ▼
FastAPI Pipeline
  │
  ├── Intake
  ├── Discovery
  ├── Eligibility
  ├── Documents
  └── Verification
          │
          ▼
     SSE Events
          │
          ▼
       Frontend
```

This allows the frontend to display progress while the pipeline is running instead of waiting for the entire process to finish.

---

## Important Design Decisions

### Retrieval Is Not Eligibility

Vector similarity is useful for discovering semantically relevant schemes, but similarity alone cannot establish legal or policy eligibility.

Therefore:

```text
Retrieval → relevance
Rules → eligibility
```

### Deterministic Eligibility

The eligibility engine uses explicit rules rather than allowing an LLM to directly decide whether a user qualifies.

This makes the decision process:

- Deterministic
- Testable
- Explainable
- Reproducible

### Unknown Information

If a required condition cannot be determined from the available profile, the system can return:

```text
possible
```

rather than incorrectly returning:

```text
eligible
```

### Optional LLM

The LLM is treated as an optional layer for:

- Free-text extraction
- Explanation
- Summarization

The core eligibility workflow does not depend on an LLM making the final decision.

---

## Important Caveats

- The application requires PostgreSQL and pgvector for the database-backed retrieval workflow.
- Retrieval uses embedding similarity to rank potentially relevant schemes.
- Final eligibility comes from the deterministic rule engine.
- Scheme-specific rules are stored in the scheme dataset and evaluated by [`backend/rules.py`](backend/rules.py).
- Some eligibility conditions require additional external verification.
- An incomplete profile may therefore result in a `possible` status.
- Government schemes and eligibility requirements can change over time.
- Users should verify current requirements and application instructions through the relevant official government source before applying.

---

## Security

Do not commit sensitive credentials to the repository.

The following should remain local or be provided through secure deployment configuration:

```text
.env
LLM_API_KEY
DATABASE_URL credentials
JWT_SECRET
```

The repository should contain only safe placeholders such as:

```env
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/navigator
JWT_SECRET=change-this-to-a-long-random-secret
```

---

## Future Improvements

Potential future improvements include:

- Better retrieval evaluation with larger query sets
- Improved multilingual retrieval
- More comprehensive scheme coverage
- Better handling of incomplete profiles
- More robust external verification workflows
- Improved classifier calibration
- Confidence-aware classifier/LLM routing
- Additional automated link verification
- Expanded integration and end-to-end tests
- More detailed evaluation of explanation grounding

---

## License and Contribution

This project is intended for educational and practical use in government-scheme discovery workflows.

It is not a substitute for official government verification or legal advice.

If you are working on the project locally, keep the scheme dataset and rule engine consistent so that retrieval and eligibility logic remain aligned.

---

## Key Takeaway

The central design of AI Bureaucracy Navigator is:

```text
Structured Profile
        │
        ▼
Applicability Checks
        │
        ▼
Semantic Retrieval
        │
        ▼
Ranked Scheme Candidates
        │
        ▼
Deterministic Rule Engine
        │
        ▼
Eligible / Possible / Ineligible
        │
        ▼
Documents + Verification
        │
        ▼
Final User Summary
```

The project deliberately combines **AI-based semantic retrieval** with **deterministic rule-based decision making**, keeping the final eligibility logic transparent and reproducible.

---

## Author

**Harsh Kumar**

B.Tech CSE (AI)

GitHub:  
https://github.com/Harshkumar76/AI-Bureaucracy-navigator