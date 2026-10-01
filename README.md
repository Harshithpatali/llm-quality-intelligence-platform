# LLM Quality Intelligence Platform

A portfolio-grade LLM evaluation workbench for reproducible model comparisons, response-level diagnostics, trace inspection, and human review. Groq and OpenRouter are called by the FastAPI backend; Supabase stores runs and annotations.

## Capabilities

- Execute a shared benchmark dataset against configured models.
- Capture model/provider identity, response text, latency, token counts, and provider errors.
- Compare evaluation runs and inspect individual response traces.
- Record structured human labels and reviewer notes.
- Persist runs, annotations, and catalog grounding metadata in Supabase PostgreSQL.
- Search 7,908 uploaded Amazon item-list metadata records across 29 marketplace domains.
- Deploy the API as a Docker service on Render and the UI independently on Streamlit Community Cloud.
- Run automated tests in GitHub Actions.

## Architecture

```text
Streamlit Community Cloud
       | HTTPS (public API)
       v
Render: Dockerized FastAPI ----> Groq API
       |                        OpenRouter API
       v
Supabase PostgreSQL
       ^
Amazon item-list metadata (catalog grounding)
```

The API is intentionally public and does not require a shared API token. This is appropriate for a demo, not a safe configuration for an unrestricted production service: public users can trigger paid provider calls. Add rate limits, quotas, and user authentication before exposing it broadly. Provider keys and the Supabase service-role key must remain in Render environment variables and must never be placed in Streamlit secrets or committed to Git.

## Repository layout

```text
backend/                 FastAPI routes, providers, evaluation, persistence
frontend/                Streamlit application
data/                    Versioned benchmark dataset
supabase/                Database schema
tests/                   Unit and API tests
.github/workflows/       Continuous integration
Dockerfile               Render backend image
render.yaml              Optional Render Blueprint (manual Docker setup does not need it)
requirements.txt         Python dependencies
```

## Dataset and scoring caveat

`data/benchmark.jsonl` contains 60 synthetic benchmark cases. It is a starter portfolio dataset, not real customer data or an externally validated gold standard.

The current deterministic evaluator reports reference-term overlap and response-length diagnostics. These metrics are not semantic correctness, factuality, relevance, or safety judgments. A fluent or keyword-rich response can still be wrong. Human review is included so benchmark owners can inspect evidence and label failures.

## Local development

Python 3.11 is recommended.

```bash
git clone https://github.com/Harshithpatali/llm-quality-intelligence-platform.git
cd llm-quality-intelligence-platform
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set provider and Supabase credentials in `.env`, then run in separate terminals:

```bash
uvicorn backend.main:app --reload --port 8000
streamlit run frontend/app.py
```

API docs: http://localhost:8000/docs

## Tests and CI

```bash
pytest -q
python -m compileall -q backend frontend
```

GitHub Actions runs the test suite on pushes and pull requests. The tests are designed not to call paid model APIs or require Supabase credentials.

## Deployment

### Render backend — manual Docker setup

1. Create **New → Web Service** and connect this repository.
2. Choose **Docker** runtime.
3. Set Dockerfile path to `./Dockerfile` and Docker context to `.`.
4. Set health check path to `/health`.
5. Configure `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (or the legacy `SUPABASE_SERVICE_ROLE_KEY`), `GROQ_API_KEY`, and `OPENROUTER_API_KEY`.
6. Deploy the service.

No `API_ACCESS_TOKEN` is needed. The backend listens on Render's injected `PORT`.

### Streamlit Community Cloud frontend

Deploy `frontend/app.py` from this repository. Set the Streamlit secret:

```toml
API_URL = "https://YOUR-RENDER-SERVICE.onrender.com"
```

The frontend calls the public API; it does not connect directly to Supabase.

### Database

The reproducible schema is in `supabase/schema.sql`. RLS is enabled; the backend uses the service-role key, which bypasses RLS and must remain server-side.

## API

- `GET /`, `GET /health`: service metadata and liveness.
- `GET /ready`: Supabase connectivity check.
- `GET /benchmark`: benchmark cases.
- `POST /benchmark/run`: execute a benchmark.
- `GET /runs`, `GET /runs/{run_id}`: run history and details.
- `POST /annotations`, `GET /annotations`: human review records.

All endpoints are public in this demo deployment.

## Known limitations and next hardening steps

- Benchmark execution is synchronous; long runs can exceed request timeouts.
- No public-API rate limit or spend quota is implemented yet.
- No user identity, reviewer roles, or per-user audit trail.
- No provider retry/backoff or asynchronous job queue.
- The heuristic evaluator is not validated against expert labels.
- Render free services may sleep when idle.

Before treating this as a production service, implement rate limiting and provider budgets, background jobs, robust retry handling, identity/authorization, observability, retention controls, and evaluation calibration against human judgments.


## Seller Response Annotation Operations

The flagship workflow is a human-in-the-loop annotation operations demo, not an automated ground-truth generator. It includes 16 **synthetic project-created** seller-support cases, a demonstration SOP, structured human labels for relevance/correctness/completeness, evidence capture, handling time, confidence, escalation, SOP-version linkage, an annotation ledger, audit events, and transparent operational metrics.

### Enable the workflow

1. Run `supabase/operations_workflow.sql` in the Supabase SQL Editor. This creates the workflow tables, seeds the synthetic tasks, and installs a project demonstration SOP v1.
2. Keep `SUPABASE_SERVICE_ROLE_KEY` only in the backend environment. Never put it in Streamlit secrets or commit it.
3. Deploy/restart the API and frontend.
4. Open **Annotation operations**, review the demonstration SOP, and annotate tasks. Use distinct annotator IDs only when distinct people actually perform the reviews.

The annotation task set is synthetic and is not Amazon data or an Amazon SOP. Separately, the project stores 7,908 records from the user-supplied `final_clean_amazon.jsonl` item-list metadata file as catalog grounding data. This is product/catalog metadata, not Amazon internal customer or support data. Reference behavior is separated into an explicit calibration view so live annotation is not pre-labeled. The reference behavior must not be represented as independently validated ground truth. The dashboard reports descriptive metrics; it does not infer quality improvements or claim statistical significance. Annotations preserve the SOP ID used at submission. The audit log records submission events; it is not a tamper-proof compliance ledger.
