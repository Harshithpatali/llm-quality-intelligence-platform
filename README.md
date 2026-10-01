# LLM Quality Intelligence Platform

A portfolio-grade LLM evaluation workbench for reproducible model comparisons, response-level diagnostics, trace inspection, and human review. Groq and OpenRouter are called by the FastAPI backend; Supabase stores runs and annotations.

## Capabilities

- Execute a shared benchmark dataset against configured models.
- Capture model/provider identity, response text, latency, token counts, and provider errors.
- Compare evaluation runs and inspect individual response traces.
- Record structured human labels and reviewer notes.
- Persist runs, annotations, and catalog grounding metadata in Supabase PostgreSQL.
- Search 7,908 uploaded Amazon item-list metadata records across 29 marketplace domains.
- Run catalog-grounded response evaluations: keyword-search a product, send the same product-grounded question to three configured models, then score each response with a rubric across safety/privacy, relevance, correctness/grounding, completeness, policy/instruction following, and clarity.
- Deploy the API as a Docker service on Render and the UI independently on Streamlit Community Cloud.
- Run automated tests in GitHub Actions.

## Architecture

```text
Streamlit Community Cloud
       | HTTPS (public API)
       v
Render: Dockerized FastAPI ----> Groq API
       |                        OpenRouter API
       |
       v
Supabase PostgreSQL <---- Amazon item-list metadata
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

The reproducible schema is in `supabase/schema.sql`, with the annotation workflow in `supabase/operations_workflow.sql` and the catalog grounding table in `supabase/amazon_itemlist_metadata.sql`.

The catalog metadata was loaded into `public.amazon_itemlist_metadata` as 7,908 rows using a composite key of `item_id + domain_name`, preserving duplicate item IDs that occur across marketplaces. The raw 10 MB JSONL upload is intentionally not committed to GitHub; `scripts/load_amazon_itemlist.py` provides a repeatable local ingestion path when the source file is available.

RLS is enabled on the catalog table. It has no anonymous read policy, so the Streamlit client accesses it only through the FastAPI backend. Backend database credentials remain server-side.

## API

- `GET /`, `GET /health`: service metadata and liveness.
- `GET /ready`: Supabase connectivity check, including the catalog grounding table.
- `GET /ops/products`: catalog metadata search for product grounding and inspection.
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


### Multi-model evaluation

The default evaluation configuration runs three model calls when both providers are selected: the configured Groq model plus two OpenRouter models (`openai/gpt-oss-120b` and `deepseek/deepseek-v4-flash-0731`). OpenRouter model slugs should be kept in a comma-separated `OPENROUTER_MODELS` environment variable.


## Catalog-grounded response evaluation

The Catalog response lab is the end-to-end product-quality workflow added on top of the benchmark and annotation layers:

\`\`\`text
User keyword
    ↓
Supplied product catalog metadata
    ↓
Select product + ask a product-support question
    ↓
Same grounded prompt → Model 1 / Model 2 / Model 3
    ↓
Per-response rubric judge
    ↓
Safety & privacy
Relevance
Correctness / catalog grounding
Completeness
Policy / instruction following
Clarity
    ↓
Weighted score + evidence + unsupported claims
    ↓
Persisted evaluation run → human review / annotation
\`\`\`

The evaluator treats the uploaded item-list metadata as product grounding context. It does not represent the dataset as Amazon internal customer, support, policy, or proprietary operational data. When a requested attribute is absent from the catalog record, the generation prompt explicitly instructs the model to say that the supplied metadata does not specify it rather than inventing a value.

The rubric is stored as structured JSON when a saved active rubric is selected; otherwise the workflow uses a built-in demonstration rubric. The rubric judge is configured with JUDGE_PROVIDER and JUDGE_MODEL. With the current default generation configuration, selecting both providers produces the configured Groq model plus the two OpenRouter models, while the judge is run separately so the model-generation traces remain comparable.

This design is intentionally different from a generic LLM leaderboard. The product search creates a realistic grounding problem, the three generation traces create comparable model behavior, and the rubric layer turns each trace into auditable quality evidence before a human reviewer makes the final judgment.
