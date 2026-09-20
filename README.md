# AI Bureaucracy Navigator

AI Bureaucracy Navigator is a FastAPI-based government-scheme discovery application that combines:

- Structured user profiles
- Semantic scheme retrieval using RAG
- Deterministic eligibility evaluation
- Document matching
- Optional LLM-based profile extraction and explanations
- PostgreSQL + pgvector persistence
- JWT authentication
- Server-Sent Events (SSE) for real-time pipeline progress
- Evaluation tooling for retrieval, eligibility, explanations, recommendations, and classification

The guiding principle is:

> **RAG helps find relevant schemes; the deterministic rule engine decides eligibility.**

---

## What the App Does

The application allows a user to enter a structured profile and optionally provide additional information as free text.

The system then processes the profile through a multi-stage pipeline to identify potentially relevant government schemes and evaluate their eligibility conditions.

The application returns:

- Relevant scheme recommendations
- Eligibility status:
  - `eligible`
  - `possible`
  - `ineligible`
- Reasons for eligibility decisions
- Unknown or missing eligibility information
- Required documents
- Missing documents
- Official scheme links
- Application information
- A final summary of the findings

The current catalogue contains **30 government schemes**.

---

## Architecture

The application is built around a multi-agent workflow.

### 1. Intake Agent

The Intake Agent:

- Builds a structured profile from the submitted form
- Accepts optional free-text information
- Uses the LLM only when additional fact extraction is required
- Converts extracted information into the canonical `UserProfile`

The structured form values take precedence over extracted free-text information.

---

### 2. Discovery Agent

The Discovery Agent is responsible for finding potentially relevant schemes.

It performs:

1. Structural/applicability checks
2. Semantic retrieval using vector embeddings
3. Ranking of candidate schemes

The semantic retrieval layer uses:

- SentenceTransformers
- `all-MiniLM-L6-v2`
- PostgreSQL
- pgvector
- Vector similarity search

The Discovery Agent produces a ranked candidate list.

Importantly, retrieval does **not** determine eligibility.

---

### 3. Eligibility Agent

The Eligibility Agent evaluates each candidate scheme against its deterministic rules.

It returns one of:

```text
eligible
possible
ineligible

It also records:

Failed conditions
Unknown conditions
Missing information

The final eligibility decision is produced by backend/rules.py.

The LLM does not make the final eligibility decision.

4. Documents Agent

The Documents Agent compares:

Required scheme documents
        +
Documents already available
        ↓
Missing documents

This allows the application to identify documents that may still be required before applying.

5. Verification Agent

The Verification Agent attaches scheme metadata including:

Official scheme URL
Application mode
Last verification date
Link verification status

The project also contains an automated link checker with manual verification support for official portals that do not respond reliably to automated HTTP requests.

Pipeline

The complete workflow can be summarized as:

User Profile
     │
     ▼
Intake Agent
     │
     ▼
Discovery Agent
     │
     ├── Applicability Checks
     │
     └── Semantic Retrieval
             │
             ▼
       Ranked Candidates
             │
             ▼
     Eligibility Agent
             │
             ▼
     Documents Agent
             │
             ▼
    Verification Agent
             │
             ▼
       Final Summary

The pipeline streams progress to the frontend using Server-Sent Events (SSE).

Core Principles

The project follows several important design principles:

The LLM is optional.
The LLM is used for extraction, explanation, and summarization.
Eligibility is decided by deterministic rules.
Semantic retrieval is used for relevance ranking.
Retrieval and eligibility are intentionally separated.
Unknown information is not silently treated as a successful condition.
The system is designed to be deterministic, explainable, and reproducible where possible.

The most important separation is:

RAG
↓
Find relevant schemes

Rule Engine
↓
Determine eligibility
Tech Stack
Backend
Python
FastAPI
Pydantic
PostgreSQL
pgvector
SentenceTransformers
JWT Authentication
Server-Sent Events (SSE)
AI / ML
SentenceTransformers
sentence-transformers/all-MiniLM-L6-v2
Optional OpenAI-compatible LLM
TF-IDF
One-vs-Rest Logistic Regression
Frontend
HTML
CSS
JavaScript
Multilingual locale support
Evaluation
pytest
Retrieval evaluation
Eligibility evaluation
Recommendation evaluation
Explanation evaluation
Multi-label classifier evaluation
Repository Structure
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
│   │
│   ├── data/
│   │   └── schemes.json
│   │
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
Prerequisites
Python 3.10+
PostgreSQL
pgvector PostgreSQL extension
Git
An LLM provider only if LLM-based extraction or explanations are required

The core retrieval and deterministic eligibility workflow does not require an LLM.

Setup
1. Clone the Project
git clone https://github.com/Harshkumar76/AI-Bureaucracy-navigator.git
cd AI-Bureaucracy-navigator
2. Create a Virtual Environment
Windows
python -m venv .venv
.venv\Scripts\activate
macOS/Linux
python -m venv .venv
source .venv/bin/activate
3. Install Dependencies
pip install -r requirements.txt

For testing:

pip install pytest
Environment Variables

Create a .env file in the project root.

Example:

DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/navigator

JWT_SECRET=change-this-to-a-long-random-secret

RAG_TOP_K=10
RAG_MIN_SIMILARITY=0.0
ENABLE_HNSW_INDEX=true

LLM_API_KEY=your-api-key-if-using-llm
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
Environment Variable Notes
Environment variables are loaded using python-dotenv.
LLM variables are optional.
DATABASE_URL must point to a valid PostgreSQL instance.
JWT_SECRET should be a long random secret in production.
Never commit .env.
Never commit real API keys or database credentials.
PostgreSQL + pgvector Setup

Create the database:

CREATE DATABASE navigator;

Connect to it:

\c navigator

Enable pgvector:

CREATE EXTENSION IF NOT EXISTS vector;

Initialize the application schema:

python scripts/setup_pgvector_schema.py

Seed the scheme catalogue:

python scripts/seed_schemes.py

Generate embeddings:

python scripts/generate_scheme_embeddings.py

Verify embeddings:

python scripts/verify_embeddings.py
Retrieval-Augmented Generation (RAG)

The application uses RAG-style semantic retrieval to identify schemes that are relevant to the user's profile.

The retrieval layer is responsible for ranking relevant candidates, not deciding eligibility.

Embedding Model

The project uses:

sentence-transformers/all-MiniLM-L6-v2

Embedding dimension:

384

Embeddings are generated locally and stored in PostgreSQL using pgvector.

This keeps the embedding step local instead of sending profile information to an external embedding API.

Retrieval Configuration

The current configuration is:

RAG_TOP_K=10
RAG_MIN_SIMILARITY=0.0
ENABLE_HNSW_INDEX=true

The retrieval stage produces a ranked shortlist of candidate schemes.

The project intentionally uses retrieval as a ranked candidate generator rather than as an eligibility filter.

RAG Flow
User Profile
     │
     ▼
Profile / Query Representation
     │
     ▼
SentenceTransformer
     │
     ▼
384-Dimensional Embedding
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
Retrieval vs Eligibility

A central architectural decision is:

RAG
↓
Which schemes appear relevant?

Rule Engine
↓
Does the profile satisfy the scheme's rules?

For example, a user may semantically resemble several agricultural schemes.

That does not mean the user is eligible for all of them.

The retrieved schemes are therefore passed to the deterministic rule engine for eligibility evaluation.

Eligibility Rule Engine

Eligibility is implemented in:

backend/rules.py

The rule engine evaluates structured profile fields against scheme-specific rules.

Supported Rule Categories

The current rule engine supports conditions including:

Minimum age
Maximum age
Maximum income
Gender
Category
Occupation
Residence
Education level
Religion
Disability percentage
Marital status
Bank-account requirements
LPG connection requirements
Income-tax status
Government-employee status
BPL-card requirements
Cultivable-land requirements
Pucca-house requirements
Girl-child requirements
Breadwinner conditions
External verification requirements
Tri-State Eligibility

The rule engine returns:

eligible
possible
ineligible

The logic is:

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

This prevents incomplete profile information from automatically being treated as eligibility.

Unknown Conditions

An unknown condition does not silently pass.

For example:

User profile
    │
    ├── Age = known
    ├── Income = known
    └── External verification = unknown
                     │
                     ▼
                 possible

This allows the application to distinguish between:

Definitely eligible
Potentially eligible but requiring additional information
Definitely ineligible
Optional LLM Features

The LLM layer is implemented in:

backend/llm.py

The LLM can be used for:

Extracting structured facts from free-text profile notes
Generating explanations
Generating summaries

The LLM does not act as the final eligibility authority.

The final eligibility decision is always produced by the deterministic rule engine.

If an LLM API key is not configured, the core retrieval and deterministic eligibility workflow can continue without LLM-based features.

Authentication

The backend includes JWT-based authentication.

Features include:

Registration
Login
Logout
Token revocation
Protected routes
Dependency-based authentication checks

Authentication is kept separate from the retrieval and eligibility logic.

Documents

The Documents Agent compares:

Required Scheme Documents
          +
Documents Available to User
          │
          ▼
    Missing Documents

This allows the application to tell the user which documents may still be required.

Verification

The Verification Agent attaches scheme metadata including:

Official scheme URL
Application mode
Last verification information
Link status

The project contains an automated link-checking script:

python scripts/check_links.py --stamp

The current catalogue contains:

30 schemes
30/30 links passing verification checks

Some official government portals may not respond reliably to automated HTTP requests. These are handled through explicit manual verification rather than changing a valid government URL simply to satisfy an automated checker.

Users should still verify current scheme requirements and application instructions through the relevant official government source before applying.

Classifier Experiment

The project contains an experimental multi-label classifier.

The purpose of the experiment is to investigate whether structured eligibility labels can be approximated from natural-language user profiles using a lightweight machine-learning model.

The classifier is not the production eligibility authority.

Classifier Pipeline
Synthetic Structured Profiles
            │
            ▼
Deterministic Rule Engine
            │
            ▼
Ground-Truth Eligibility Labels
            │
            ▼
Natural-Language Profile Text
            │
            ▼
TF-IDF
            │
            ▼
One-vs-Rest Logistic Regression
            │
            ▼
Predicted Scheme Labels
Model

The classifier uses:

TF-IDF
Unigram features
Bigram features
One-vs-Rest Logistic Regression
Class balancing
A fixed random seed
A fixed train/test split

The classifier uses deterministic rule-engine outputs as ground truth.

The LLM is not used to generate the labels.

It may only be used to convert structured synthetic profiles into natural-language descriptions.

Synthetic Dataset

The experiment contains:

520 synthetic profiles
26 targetable schemes

Four schemes are excluded from the classifier experiment because their remaining eligibility logic depends only on external verification and therefore cannot be reliably inferred from a generated profile.

The dataset contains targeted synthetic profiles designed around scheme eligibility conditions.

Baseline Classifier Results

Using the fixed held-out test set:

Test profiles: 130
Targetable schemes: 26

Baseline classifier results:

Metric	Score
Micro Precision	0.741
Micro Recall	0.895
Micro F1	0.811
Macro Precision	0.660
Macro Recall	0.843
Macro F1	0.718
Weighted F1	0.830
Exact Label-Set Match	0.223
Hamming Loss	0.057

These results are a baseline for the experimental classifier and should not be interpreted as production eligibility accuracy.

The deterministic rule engine remains the production source of truth.

Classifier Role

The classifier is intended as an experimental approximation or possible shortlisting mechanism.

It does not replace the production rule engine.

The production architecture remains:

User Profile
     │
     ├── Semantic Retrieval
     │
     └── Deterministic Eligibility Rules
                    │
                    ▼
          Final Eligibility Result

A future architecture could investigate:

Profile
   │
   ▼
Lightweight Classifier
   │
   ├── High Confidence
   │       │
   │       ▼
   │   Candidate Shortlist
   │
   └── Low Confidence
           │
           ▼
       LLM Extraction
           │
           ▼
   Deterministic Rule Engine

This remains an experimental direction rather than the current production pipeline.

LLM vs Classifier Evaluation

The project also includes an evaluation script for comparing:

LLM extraction → deterministic rules

against:

TF-IDF classifier

The important fairness principle is that both approaches are evaluated against the same deterministic ground-truth labels.

The LLM does not generate the ground truth.

The experiment measures:

Precision
Recall
F1
Exact label-set match
Hamming loss
Latency
API usage

A cached LLM result is treated separately from a fresh API call when interpreting latency measurements.

Evaluation

The project contains evaluation tooling for multiple parts of the system.

Evaluation areas include:

Retrieval quality
Eligibility evaluation
Recommendation quality
Explanation quality
End-to-end behavior
Classifier performance
Latency measurements

The evaluation framework uses deterministic rule-engine outputs where appropriate so that eligibility evaluation does not depend on an LLM making the final decision.

Testing

The project contains pytest-based tests for:

Retrieval
Rule evaluation
Metrics
RAG/rule interaction
Evaluation
End-to-end pipeline behavior

Run the complete test suite:

pytest

Run individual test files:

pytest tests/test_retrieval.py
pytest tests/test_rule_engine.py
pytest tests/test_full_pipeline.py
Run the Backend

Start the FastAPI development server:

uvicorn backend.main:app --reload

Backend:

http://localhost:8000

Swagger API documentation:

http://localhost:8000/docs
Frontend

The frontend is implemented using:

HTML
CSS
JavaScript

It is served through the FastAPI backend.

The application includes:

Landing page
Sign-in page
Scheme discovery flow
Scheme detail page
Eligibility result presentation
Document status information
Multilingual locale support
SSE Progress Streaming

The application uses Server-Sent Events (SSE) to stream progress from the backend while the pipeline executes.

Simplified flow:

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

This allows the frontend to display pipeline progress without waiting for the entire workflow to complete.

Important Design Decisions
1. Retrieval Is Not Eligibility

Vector similarity is useful for discovering semantically relevant schemes.

It cannot by itself establish eligibility.

Therefore:

Retrieval → relevance
Rules → eligibility
2. Deterministic Eligibility

The eligibility engine uses explicit rules instead of allowing an LLM to directly determine whether a user qualifies.

This makes the decision process:

Deterministic
Testable
Explainable
Reproducible
3. Unknown Information

If a required condition cannot be determined from the available profile, the system can return:

possible

rather than incorrectly returning:

eligible
4. Optional LLM

The LLM is treated as an optional layer for:

Free-text extraction
Explanation
Summarization

The core eligibility workflow does not depend on an LLM making the final decision.

5. Ranked Retrieval

The RAG layer is designed to produce a ranked shortlist rather than act as a hard eligibility filter.

Conceptually:

All Schemes
     │
     ▼
Applicability / Structural Checks
     │
     ▼
Semantic Retrieval
     │
     ▼
Top-K Ranked Candidates
     │
     ▼
Deterministic Eligibility

This allows semantic similarity to assist discovery without overriding explicit eligibility rules.

Important Caveats
The application requires PostgreSQL and pgvector for the database-backed retrieval workflow.
Retrieval uses embedding similarity to rank potentially relevant schemes.
Semantic similarity does not establish eligibility.
Final eligibility comes from the deterministic rule engine.
Scheme-specific rules are stored in the scheme dataset and evaluated by backend/rules.py.
Some eligibility conditions require additional external verification.
An incomplete profile may result in a possible status.
Government schemes and eligibility requirements can change over time.
Official URLs can change or become temporarily unavailable.
Users should verify current requirements and application instructions through the relevant official government source before applying.
Security

Do not commit sensitive credentials to the repository.

The following should remain local or be supplied through secure deployment configuration:

.env
LLM_API_KEY
DATABASE_URL credentials
JWT_SECRET

The repository should contain only safe placeholders:

DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/navigator

JWT_SECRET=change-this-to-a-long-random-secret

Never commit:

API keys
Database passwords
Production JWT secrets
Personal credentials
Future Improvements

Potential future improvements include:

Larger retrieval evaluation datasets
Improved multilingual retrieval
More comprehensive scheme coverage
Better handling of incomplete profiles
More robust external verification workflows
Improved classifier calibration
Confidence-aware classifier/LLM routing
More robust automated link verification
Expanded integration tests
More detailed explanation-grounding evaluation
Improved production observability
Better latency and cost benchmarking
License and Contribution

This project is intended for educational and practical use in government-scheme discovery workflows.

It is not a substitute for official government verification or legal advice.

When modifying the project, keep the scheme dataset, embeddings, and deterministic rule engine consistent so that retrieval and eligibility logic remain aligned.

Key Takeaway

The central architecture of AI Bureaucracy Navigator is:

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

The project deliberately combines:

AI-based semantic retrieval
          +
Deterministic rule-based decision making

The result is a system where AI assists with understanding and discovery, while the final eligibility logic remains transparent, deterministic, and reproducible.

Author

Harsh Kumar

B.Tech CSE (AI)

GitHub:

https://github.com/Harshkumar76/AI-Bureaucracy-navigator


