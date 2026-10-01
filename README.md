# LLM Quality Intelligence Platform

A practical, reproducible workbench for evaluating LLM response quality across Groq and OpenRouter models. Includes a curated synthetic benchmark, provider adapters, a FastAPI service, Streamlit dashboard, heuristic evaluation, optional LLM-as-judge, CSV/JSON exports, and tests.

> Dataset note: `data/benchmark.jsonl` is a purpose-built synthetic benchmark for engineering and demonstration. It is not real customer data and does not represent an externally validated gold standard.

## What it does
- Runs the same benchmark prompts against configured models for comparable results.
- Captures response text, latency, token usage when available, errors, and run metadata.
- Scores answer/reference alignment with transparent deterministic metrics: keyword coverage, answer completeness proxy, and length sanity.
- Supports optional judge scoring through a configured model (clearly marked as model-judged).
- Provides a human review queue and stores annotations locally in SQLite.
- Exports benchmark results and annotations to CSV/JSON.

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
- `GROQ_API_KEY`: optional; required to call Groq.
- `OPENROUTER_API_KEY`: optional; required to call OpenRouter.
- `GROQ_MODEL`: defaults to `llama-3.3-70b-versatile` (change if unavailable in your account).
- `OPENROUTER_MODELS`: comma-separated model slugs; defaults to two illustrative model IDs. Verify current model availability in the OpenRouter model catalog.
- `JUDGE_PROVIDER` and `JUDGE_MODEL`: optional model-as-judge configuration.
- `DATABASE_PATH`: defaults to `data/platform.db`.

Groq and OpenRouter both expose chat-completion style APIs; this project uses direct HTTP calls so provider-specific details remain visible and configurable. See [Groq API docs](https://console.groq.com/docs/api-reference) and [OpenRouter quickstart](https://openrouter.ai/docs/quickstart).

## Run without API keys
The app starts without keys. You can inspect the dataset and dashboard, but model calls return a clear configuration error. To validate the pipeline offline:
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
- **Length sanity**: penalizes extremely short responses relative to reference length.
- **Composite heuristic**: weighted combination of the above.
- **Judge score**: optional and model-generated; may be biased and must be reviewed by a human.

Do not use benchmark scores as a standalone production launch decision. Add task-specific expert rubrics, blinded human ratings, inter-annotator agreement, and confidence intervals before making high-stakes comparisons.

## Repository layout
```
backend/       FastAPI, providers, evaluator, persistence, benchmark runner
frontend/      Streamlit dashboard and human review
data/          synthetic benchmark JSONL
tests/         offline tests
```

## Roadmap
- Add stratified bootstrap confidence intervals and agreement statistics.
- Add rubric-specific evaluation and blind pairwise preference review.
- Add auth, managed database, queueing, and deployment secrets before multi-user production use.
