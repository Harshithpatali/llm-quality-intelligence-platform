# LLM Quality Intelligence Platform

A reproducible workbench for evaluating LLM response quality across Groq and OpenRouter models. Includes a curated synthetic benchmark, provider adapters, FastAPI service, Streamlit dashboard, transparent heuristic evaluation, human review, CSV exports, and Supabase PostgreSQL persistence.

> Dataset note: `data/benchmark.jsonl` contains 60 purpose-built synthetic examples for engineering and demonstration. It is not real customer data or an externally validated gold standard.

## Capabilities
- Runs identical benchmark prompts against configured models.
- Captures responses, latency, token usage when available, errors, and run metadata.
- Computes transparent reference-overlap and length-sanity diagnostics.
- Provides a human review queue with ratings, labels, and notes stored in SQLite.
- Exports benchmark results and the dataset from the dashboard.

## Architecture
```
Streamlit UI -> FastAPI -> Provider adapters (Groq / OpenRouter)
                     |-> benchmark runner -> JSONL benchmark
                     |-> evaluator -> SQLite run history / annotations
```

## Quick start
Python 3.10+ recommended.

```bash
git clone https://github.com/Harshithpatali/llm-quality-intelligence-platform.git
cd llm-quality-intelligence-platform
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add API keys to `.env`. Never commit real keys.

Start the API:
```bash
uvicorn backend.main:app --reload --port 8000
```
In another terminal:
```bash
streamlit run frontend/app.py
```
Open Streamlit at http://localhost:8501 and API docs at http://localhost:8000/docs.

## Configuration
- `GROQ_API_KEY`: required to call Groq.
- `OPENROUTER_API_KEY`: required to call OpenRouter.
- `GROQ_MODEL`: defaults to `llama-3.3-70b-versatile`; change if unavailable.
- `OPENROUTER_MODELS`: comma-separated model slugs; defaults are examples. Verify availability in the OpenRouter catalog.
- `SUPABASE_URL`: Supabase project URL.- `SUPABASE_KEY`: Supabase publishable/anon key for the configured access model. Do not use a service-role key in client-facing code.

Groq and OpenRouter expose chat-completion APIs. This project uses direct HTTP calls. See [Groq API docs](https://console.groq.com/docs/api-reference) and [OpenRouter quickstart](https://openrouter.ai/docs/quickstart).

## Run without API keys
The app starts without keys. Dataset inspection and offline tests work; live model calls return a clear configuration error.
```bash
pytest -q
```

## API
- `GET /health`
- `GET /benchmark`
- `POST /benchmark/run` — body: `{"providers":["groq","openrouter"],"limit":10}`
- `GET /runs`
- `GET /runs/{run_id}`
- `POST /annotations`
- `GET /annotations`

## Evaluation methodology
Scores are diagnostics, not truth labels:
- **Reference keyword coverage**: fraction of meaningful reference terms present in the response.
- **Length sanity**: proxy that penalizes extremely short responses relative to the reference.
- **Composite heuristic**: weighted combination of the two.

The heuristic is not semantic evaluation and can reward keyword overlap while missing nuance. Human review is included. Do not use benchmark scores as a standalone production launch decision. For stronger evidence, add task-specific expert rubrics, blinded ratings, inter-annotator agreement, and confidence intervals.

## Repository layout
```
backend/       FastAPI, providers, evaluator, Supabase persistence, benchmark runner
frontend/      Streamlit dashboard and human review
data/          synthetic benchmark JSONL
tests/         offline tests
```

## Roadmap
- Add rubric-specific evaluation, optional model-as-judge with calibration, and blind pairwise preference review.
- Add bootstrap confidence intervals and inter-annotator agreement.
- Add authentication, managed database, queueing, and deployment secrets before multi-user production use.
