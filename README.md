# LLM Quality Intelligence Platform

A controlled LLM response-quality workbench built around reproducible evaluation, provider comparisons, traceable runs, and human review. Groq and OpenRouter are accessed only by the FastAPI backend. Supabase PostgreSQL stores benchmark runs and annotations.

## What it does
- Runs the same curated benchmark cases across selected models.
- Captures response text, latency, token usage when available, and provider errors.
- Computes transparent reference-overlap diagnostics (not a semantic truth score).
- Stores runs and human annotations in Supabase.
- Provides a Streamlit review and analytics workspace.
- Uses an API access token between Streamlit and FastAPI; provider and database credentials remain server-side.

## Architecture
```
Streamlit Community Cloud
       | HTTPS + API token
       v
Render FastAPI service ----> Groq API
       |                    OpenRouter API
       v
Supabase PostgreSQL
```

## Dataset
`data/benchmark.jsonl` contains 60 purpose-built synthetic cases across multiple task categories. It is not real customer data and is not an externally validated gold standard.

## Local development
Python 3.11 recommended.

```bash
git clone https://github.com/Harshithpatali/llm-quality-intelligence-platform.git
cd llm-quality-intelligence-platform
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, fill in credentials, and run:

```bash
uvicorn backend.main:app --reload --port 8000
streamlit run frontend/app.py
```

API docs: http://localhost:8000/docs

## Deploy
- **Backend:** Render blueprint in `render.yaml`.
- **Frontend:** Streamlit Community Cloud; main file path `frontend/app.py`.
- Follow [STREAMLIT_DEPLOY.md](STREAMLIT_DEPLOY.md) for the exact environment variables and secrets.

Required Render secrets:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (backend only; never expose in Streamlit)
- `API_ACCESS_TOKEN` (generate a long random value)
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`

Streamlit secrets:
- `API_URL` = Render service URL
- `API_ACCESS_TOKEN` = same token configured on Render

The Supabase schema is in `supabase/schema.sql`. The project tables were provisioned in the connected Supabase project; the SQL file documents the schema for reproducibility. RLS is enabled. The backend uses the service-role key, which must be stored only as a Render secret.

## API
- `GET /`, `GET /health`: public service metadata and liveness.
- `GET /ready`: checks Supabase connectivity.
- `GET /benchmark`: dataset (requires API token).
- `POST /benchmark/run`: run selected providers and cases (requires token).
- `GET /runs`, `GET /runs/{run_id}`: run history (requires token).
- `POST /annotations`, `GET /annotations`: human reviews (requires token).

## Evaluation limitations
The current score combines reference-term coverage and a response-length sanity heuristic. It is useful for diagnostics, not semantic correctness, relevance, or safety certification. Fluent or keyword-rich responses can still be wrong. Production model decisions should include task-specific expert rubrics, blinded human ratings, inter-annotator agreement, confidence intervals, and safety review.

## Tests
```bash
pytest -q
```

## Production hardening roadmap
For a multi-user production launch, add user identity/roles, per-user audit trails, request rate limits, asynchronous benchmark jobs, retry/backoff and provider budgets, retention policies, observability, and load tests. The included Render free plan can sleep when idle.
