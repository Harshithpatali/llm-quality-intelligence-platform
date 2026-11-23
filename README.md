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

By default the demo API can run without an API token, but `API_ACCESS_TOKEN` can now protect application and paid-provider routes. A lightweight single-instance rate limit also protects expensive POST routes. Provider keys and the Supabase secret/service-role key must remain in Render environment variables and must never be placed in Streamlit secrets or committed to Git.

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

The deterministic evaluator reports token-level precision, recall, F1, coverage, missing/extra terms, and response-length diagnostics. Its composite remains explicitly labelled a lexical heuristic: it is not semantic correctness, factuality, relevance, or safety. A fluent or keyword-rich response can still be wrong. Use the independent rubric judge for triage and human review for final labels.

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

`API_ACCESS_TOKEN` is optional. When set, use the same token in Streamlit secrets. The backend listens on Render's injected `PORT`.

### Streamlit Community Cloud frontend

Deploy `frontend/app.py` from this repository. Set the Streamlit secret:

```toml
API_URL = "https://YOUR-RENDER-SERVICE.onrender.com"
```

The frontend calls FastAPI; it does not connect directly to Supabase. When API protection is enabled, the frontend sends `X-API-Key` from Streamlit secrets.

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
- Provider requests retry transient failures and honor bounded Retry-After delays; durable queueing is still needed for multi-worker production use.
- The heuristic evaluator is a lexical diagnostic, not a validated quality metric. Judge calibration requires a human-labelled dataset.
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

The current default generation configuration produces three distinct model identities when both providers are selected: Groq GPT-OSS 120B, Groq GPT-OSS 20B, and OpenRouter DeepSeek V4 Flash 0731. The independent rubric judge is configured separately.


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

The rubric is stored as structured JSON when a saved active rubric is selected; otherwise the workflow uses a built-in demonstration rubric. The rubric judge is configured with JUDGE_PROVIDER and JUDGE_MODEL. With the current default generation configuration, selecting both providers produces two Groq generations plus one OpenRouter generation, while the judge runs separately so generator traces remain comparable.

This design is intentionally different from a generic LLM leaderboard. The product search creates a realistic grounding problem, the three generation traces create comparable model behavior, and the rubric layer turns each trace into auditable quality evidence before a human reviewer makes the final judgment.

## Quality Operations v2

The project now connects catalog grounding, multi-model generation, rubric evaluation, blind human review, and calibration into one quality-operations workflow.

### Flagship workflow

Product keyword → ranked catalog search → product + policy context → three distinct generation models → structured rubric judge → persisted evaluation traces → blind human review queue → human annotation → human/LLM agreement and defect analytics.

### Default model roles

| Role | Provider | Model |
| --- | --- | --- |
| Generator 1 | Groq | openai/gpt-oss-120b |
| Generator 2 | Groq | openai/gpt-oss-20b |
| Generator 3 | OpenRouter | deepseek/deepseek-v4-flash-0731 |
| Rubric judge | Groq | qwen/qwen3.8-27b |
| Rubric generator | Groq | qwen/qwen3.8-27b |

The configuration is environment-driven. The generator set is intentionally three distinct model identities rather than three calls to the same model through different providers.

### New quality layers

**Policy context:** versioned project policy records are supplied separately from catalog facts so the evaluator can distinguish product grounding from policy/instruction compliance. The seeded policy is explicitly a portfolio demonstration policy, not an Amazon policy.

**Rubric Studio:** evaluation rubrics can be generated as drafts from an objective and supplied policy context. Drafts require human review before approval and activation. Decision thresholds and critical dimensions are stored in the rubric JSON rather than only in code.

**Async evaluation jobs:** catalog evaluations return a job ID and execute generation/judging in the background. The frontend polls job state and displays each model response and provider failure independently.

**Blind human review:** successful traces can be queued for review. Human reviewers receive product context, policy context, the user question, and model response while automated rubric scores remain hidden. After submission, the automated evaluation is revealed for comparison.

**Calibration:** the platform calculates human-human agreement, Cohen's kappa for two-annotator traces, per-dimension agreement, and automated-judge vs human agreement.

**Audit sampling:** the QA sampler prioritizes escalations, rejected responses, and major issues before filling the sample deterministically. It is a QA heuristic, not a statistically representative sample.

**Reliability:** provider requests classify failures, retry transient errors and timeouts, preserve token/latency metadata, and can estimate cost from configured pricing snapshots.

**Security:** an optional API_ACCESS_TOKEN can protect application routes, while expensive POST routes have a lightweight rate limit. Provider and Supabase credentials remain server-side.

### Database migration

After the existing schemas, apply:

1. supabase/quality_operations_v2.sql
2. supabase/quality_operations_v2_patch.sql

The v2 schema adds policy records, evaluation jobs, evaluation traces, a blind review queue, trace-linked annotations, and indexed catalog search. The patch permits repeated reviews of the same trace for inter-annotator calibration.

### Important boundaries

The supplied catalog file is portfolio product metadata, not Amazon internal customer/support data. Automated rubric results are model-generated evaluation signals, not expert-validated ground truth. Human annotation is the final review layer. The API and Render Free deployment remain demo-oriented rather than production-grade multi-tenant infrastructure.

## Judge validation against human review

An offline validation utility compares rubric-judge decisions with independently collected human labels. It reports a three-class confusion matrix, accuracy, balanced accuracy, per-class precision/recall/F1, macro-F1 over observed classes, Cohen's kappa, category breakdowns, and a deterministic percentile-bootstrap 95% interval for accuracy.

Prepare a JSONL file with one independently reviewed response per line:

```json
{"judge_decision":"pass","human_decision":"accept","category":"catalog_grounding"}
{"judge_decision":"review","human_decision":"revise","category":"policy"}
{"judge_decision":"fail","human_decision":"reject","category":"safety"}
```

Run the analysis locally:

```bash
python -m backend.judge_validation path/to/human_review_pairs.jsonl --output judge_validation_report.json
```

Human labels `accept`, `revise`, `reject`, and `escalate` map to `pass`, `review`, `fail`, and `fail` respectively. This is a declared evaluation policy, not a discovered truth. Do not use synthetic or self-generated labels and describe the result as human validation. Report sample size and label distribution alongside metrics, and inspect disagreements before changing thresholds.


## Evaluator Calibration and Reliability

The offline calibration module evaluates reviewer consistency and calibrates a numeric rubric-judge score without using holdout labels to select thresholds.

### Input contract

Create a JSONL file with one row per response. `trace_id` must be unique. Keep related variants of the same prompt in one split by supplying a shared `group_id`.

```json
{"trace_id":"r-001","group_id":"prompt-001","split":"validation","reviewer_a_decision":"pass","reviewer_b_decision":"review","adjudicated_decision":"review","judge_decision":"pass","judge_score":0.74,"dimensions":{"correctness":{"reviewer_a":"pass","reviewer_b":"review","judge":"pass","adjudicated":"review"},"grounding":{"reviewer_a":"fail","reviewer_b":"fail","judge":"fail","adjudicated":"fail"}}}
{"trace_id":"r-002","group_id":"prompt-002","split":"holdout","reviewer_a_decision":"fail","reviewer_b_decision":"fail","adjudicated_decision":"fail","judge_decision":"review","judge_score":0.31,"dimensions":{"correctness":{"reviewer_a":"fail","reviewer_b":"fail","judge":"review","adjudicated":"fail"}}}
```

Required top-level fields: `trace_id`, `split`, `reviewer_a_decision`, `reviewer_b_decision`, `adjudicated_decision`, `judge_decision`, and `judge_score`. Decisions are `pass`, `review`, or `fail` (human aliases `accept`, `revise`, `reject`, and `escalate` are accepted). Scores must be consistently normalized to [0, 1]. The adjudicated decision is the operational reference for threshold fitting and judge comparison; preserve original reviewer labels for inter-rater agreement. Dimension-level fields are optional.

### Run

```bash
python -m backend.calibration path/to/calibration_records.jsonl --output calibration_reliability_report.json
```

The report includes:
- Reviewer A vs Reviewer B exact agreement, Cohen's kappa, balanced accuracy, macro-F1, and confusion matrix, separately for validation and holdout.
- Judge vs adjudicated-reference agreement, including per-class performance and confusion matrices.
- Human-human and judge-vs-adjudicated disagreement rates by rubric dimension.
- Two score cutoffs selected on validation data to maximize macro-F1 for fail/review/pass.
- A frozen-threshold evaluation on the untouched holdout set, with raw judge labels compared against calibrated score decisions.

Threshold search is exhaustive over observed validation scores. Holdout labels are not used in selection. If a threshold is changed after inspecting holdout performance, that holdout is no longer untouched and a new holdout is required. If multiple generations share a prompt or source case, use the same `group_id` so it cannot cross splits.

**Data requirements and interpretation:** use genuinely independent reviewer annotations and a documented adjudication process; do not fabricate or auto-generate human labels. A practical initial target is 200+ labelled responses, with both reviewers independently rating the same subset and all three decision classes represented in each split. More data may be required for stable subgroup/dimension estimates. Cohen's kappa is prevalence-sensitive. Adjudication is an operational reference, not infallible ground truth. The judge score must be the rubric judge's documented numeric score—not the lexical-overlap heuristic. Small samples and class imbalance can make thresholds unstable; always publish split sizes, class support, and uncertainty alongside headline metrics.
