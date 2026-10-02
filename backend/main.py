import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db
from .benchmark import load_dataset, run_benchmark
from .catalog_eval import (
    DEFAULT_CATALOG_RUBRIC,
    run_catalog_evaluation,
)
from .config import API_ACCESS_TOKEN, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS
from .ops_metrics import summarize_annotations, summarize_review_agreement
from .rubric_generator import generate_rubric
from .schemas import (
    AnnotationRequest,
    CatalogEvaluationRequest,
    OperationalAnnotationRequest,
    ReviewClaimRequest,
    ReviewQueueRequest,
    RubricDecisionRequest,
    RubricDraftRequest,
    RubricEditRequest,
    RubricGenerateRequest,
    RunRequest,
)

load_dotenv()
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

app = FastAPI(
    title="LLM Quality Intelligence API",
    version="1.4.0",
    description=(
        "Multi-model AI quality operations: catalog grounding, structured rubrics, "
        "blind human review, annotation governance, and audit metrics."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


def require_api_key(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    """Optional API protection.

    The portfolio stays easy to demo when API_ACCESS_TOKEN is unset.
    Setting it protects application data and model-spending routes.
    """
    if not API_ACCESS_TOKEN:
        return

    supplied = x_api_key or ""
    if not supplied and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization.split(" ", 1)[1].strip()

    if supplied != API_ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing API access token.")


def enforce_rate_limit(request: Request):
    """Single-instance rate limiter for expensive portfolio/demo endpoints."""
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _rate_buckets[client]

    while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
        )

    bucket.append(now)


def protected():
    return [
        Depends(enforce_rate_limit),
        Depends(require_api_key),
    ]


@app.get("/")
def root():
    return {
        "service": "LLM Quality Intelligence API",
        "version": "1.4.0",
        "docs": "/docs",
        "health": "/health",
        "catalog_evaluation": "/catalog/evaluate",
        "review_queue": "/ops/review-queue",
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "llm-quality-intelligence-api"}


@app.get("/ready")
def ready():
    database = db.database_status()
    if database.get("connection_ok") and database.get("schema_ok"):
        return {"status": "ready", "database": database}
    logger.error("Readiness check failed: %s", database)
    raise HTTPException(
        status_code=503,
        detail={"message": "Database is not ready.", "database": database},
    )


@app.get("/benchmark")
def benchmark():
    cases = load_dataset()
    return {"count": len(cases), "cases": cases}


@app.post("/benchmark/run", dependencies=protected())
def run(req: RunRequest):
    try:
        return run_benchmark(req.providers, req.limit, req.categories)
    except Exception as exc:
        logger.exception("Benchmark execution failed")
        raise HTTPException(
            status_code=502,
            detail="Benchmark execution failed. Check provider configuration and API logs.",
        ) from exc


@app.get("/runs", dependencies=[Depends(require_api_key)])
def runs():
    try:
        return db.list_runs()
    except Exception as exc:
        logger.exception("Could not retrieve benchmark runs")
        raise HTTPException(status_code=503, detail="Could not retrieve benchmark runs") from exc


@app.get("/runs/{run_id}", dependencies=[Depends(require_api_key)])
def run_detail(run_id: str):
    try:
        row = db.get_run(run_id)
    except Exception as exc:
        logger.exception("Could not retrieve benchmark run %s", run_id)
        raise HTTPException(status_code=503, detail="Could not retrieve benchmark run") from exc
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    row["config"] = row.pop("config_json", {})
    row["results"] = row.pop("results_json", [])
    return row


@app.post("/annotations", dependencies=protected())
def annotate(req: AnnotationRequest):
    try:
        return {
            "id": db.save_annotation(req, datetime.now(timezone.utc).isoformat()),
            "status": "saved",
        }
    except Exception as exc:
        logger.exception("Could not save annotation")
        raise HTTPException(status_code=503, detail="Could not save annotation") from exc


@app.get("/annotations", dependencies=[Depends(require_api_key)])
def annotations():
    try:
        return db.list_annotations()
    except Exception as exc:
        logger.exception("Could not retrieve annotations")
        raise HTTPException(status_code=503, detail="Could not retrieve annotations") from exc


# --------------------------- Rubric governance ---------------------------

@app.post("/rubrics", status_code=201, dependencies=protected())
def create_rubric(req: RubricDraftRequest):
    try:
        return db.create_rubric({"rubric_id": str(uuid4()), **req.model_dump()})
    except Exception as exc:
        logger.exception("Could not create rubric draft")
        raise HTTPException(
            status_code=503,
            detail="Could not create rubric draft; apply rubric schema and check database configuration.",
        ) from exc


@app.post("/rubrics/generate", status_code=201, dependencies=protected())
def generate_rubric_draft(req: RubricGenerateRequest):
    try:
        policy = db.get_policy(req.policy_id) if req.policy_id else None
        rubric = generate_rubric(
            rubric_name=req.rubric_name.strip(),
            objective=req.objective.strip(),
            policy_context=policy,
        )
        row = db.create_rubric(
            {
                "rubric_id": str(uuid4()),
                "rubric_name": rubric["rubric_name"].strip(),
                "rubric_json": rubric,
                "source_document": req.source_document,
                "generation_notes": (
                    f"Generated with {rubric.get('generator_provider')} / "
                    f"{rubric.get('generator_model')}. Human review is required "
                    "before approval or activation."
                ),
                "created_by": req.created_by,
            }
        )
        return row
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not generate rubric draft")
        raise HTTPException(
            status_code=502,
            detail="Could not generate rubric draft. Check rubric generator configuration.",
        ) from exc


@app.get("/rubrics", dependencies=[Depends(require_api_key)])
def rubrics(rubric_name: str | None = None):
    try:
        return db.list_rubrics(rubric_name)
    except Exception as exc:
        logger.exception("Could not list rubrics")
        raise HTTPException(status_code=503, detail="Could not list rubrics") from exc


@app.get("/rubrics/{rubric_id}", dependencies=[Depends(require_api_key)])
def rubric_detail(rubric_id: str):
    try:
        row = db.get_rubric(rubric_id)
    except Exception as exc:
        logger.exception("Could not retrieve rubric")
        raise HTTPException(status_code=503, detail="Could not retrieve rubric") from exc
    if not row:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return row


@app.patch("/rubrics/{rubric_id}", dependencies=protected())
def edit_rubric(rubric_id: str, req: RubricEditRequest):
    try:
        row = db.update_rubric(
            rubric_id,
            req.rubric_json,
            req.review_notes,
            req.reviewer,
        )
    except Exception as exc:
        logger.exception("Could not edit rubric")
        raise HTTPException(status_code=503, detail="Could not edit rubric") from exc
    if not row:
        raise HTTPException(status_code=409, detail="Only draft rubrics can be edited")
    return row


@app.post("/rubrics/{rubric_id}/approve", dependencies=protected())
def approve_rubric(rubric_id: str, req: RubricDecisionRequest):
    try:
        row = db.approve_rubric(rubric_id, req.reviewer, req.review_notes)
    except Exception as exc:
        logger.exception("Could not approve rubric")
        raise HTTPException(status_code=503, detail="Could not approve rubric") from exc
    if not row:
        raise HTTPException(status_code=409, detail="Only draft rubrics can be approved")
    return row


@app.post("/rubrics/{rubric_id}/activate", dependencies=protected())
def activate_rubric(rubric_id: str):
    try:
        row = db.activate_rubric(rubric_id)
    except Exception as exc:
        logger.exception("Could not activate rubric")
        raise HTTPException(status_code=503, detail="Could not activate rubric") from exc
    if not row:
        raise HTTPException(status_code=409, detail="Only approved rubrics can be activated")
    return row


# --------------------------- Catalog & policy ---------------------------

def _resolve_catalog_rubric(req: CatalogEvaluationRequest) -> tuple[dict, object]:
    if req.rubric_json is not None:
        return req.rubric_json, "request"

    if req.rubric_id:
        row = db.get_rubric(req.rubric_id)
        if not row:
            raise HTTPException(status_code=404, detail="Rubric not found")
        if row.get("status") not in {"approved", "active"}:
            raise HTTPException(
                status_code=409,
                detail="Only approved or active rubrics can evaluate responses.",
            )
        return row["rubric_json"], {
            "rubric_id": row["rubric_id"],
            "rubric_name": row["rubric_name"],
            "version": row["version"],
            "status": row["status"],
        }

    active = [
        row
        for row in db.list_rubrics("Catalog Response Quality")
        if row.get("status") == "active"
    ]
    if active:
        row = active[0]
        return row["rubric_json"], {
            "rubric_id": row["rubric_id"],
            "rubric_name": row["rubric_name"],
            "version": row["version"],
            "status": row["status"],
        }

    return DEFAULT_CATALOG_RUBRIC, "built_in_demo"


def _prepare_catalog_evaluation(req: CatalogEvaluationRequest) -> dict:
    product = db.get_product_metadata(req.item_id, req.domain_name)
    if not product:
        raise HTTPException(
            status_code=404,
            detail="Catalog product not found for item_id + domain_name.",
        )

    rubric, rubric_source = _resolve_catalog_rubric(req)

    policy = None
    if req.policy_id:
        policy = db.get_policy(req.policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found.")
    else:
        active_policies = db.list_active_policies()
        policy = active_policies[0] if active_policies else None

    return {
        "product": product,
        "rubric": rubric,
        "rubric_source": rubric_source,
        "policy": policy,
        "request": req.model_dump(),
    }


def _run_catalog_job(job_id: str, req: CatalogEvaluationRequest):
    started = datetime.now(timezone.utc).isoformat()
    try:
        db.update_evaluation_job(
            job_id,
            status="running",
            started_at=started,
        )

        context = _prepare_catalog_evaluation(req)
        product = context["product"]
        rubric = context["rubric"]
        rubric_source = context["rubric_source"]
        policy = context["policy"]

        evaluation = run_catalog_evaluation(
            product=product,
            user_query=req.user_query.strip(),
            providers=req.providers,
            rubric=rubric,
            policy=policy,
        )

        created = datetime.now(timezone.utc).isoformat()
        run_id = str(uuid4())
        results = evaluation["results"]

        rubric_id = (
            rubric_source.get("rubric_id")
            if isinstance(rubric_source, dict)
            else None
        )
        rubric_version = (
            rubric_source.get("version")
            if isinstance(rubric_source, dict)
            else rubric.get("version")
        )
        policy_id = policy.get("policy_id") if policy else None

        traces = []
        for row in results:
            trace_id = str(uuid4())
            row["trace_id"] = trace_id
            row["item_id"] = product["item_id"]
            row["domain_name"] = product["domain_name"]
            row["user_query"] = req.user_query.strip()
            row["policy_id"] = policy_id
            row["rubric_id"] = rubric_id
            row["rubric_version"] = rubric_version
            row["product_metadata"] = product
            row["policy_context"] = policy
            traces.append(row)

        config = {
            "run_type": "catalog_response_evaluation",
            "item_id": product["item_id"],
            "domain_name": product["domain_name"],
            "user_query": req.user_query.strip(),
            "providers": req.providers,
            "rubric_source": rubric_source,
            "policy_id": policy_id,
        }

        db.save_run(run_id, created, "completed", config, results)
        db.save_evaluation_traces(run_id, traces)

        evaluation.update(
            {
                "run_id": run_id,
                "created_at": created,
                "run_type": "catalog_response_evaluation",
                "product": product,
                "policy": policy,
                "rubric_source": rubric_source,
            }
        )

        db.update_evaluation_job(
            job_id,
            status="completed",
            result_json=evaluation,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        logger.exception("Catalog evaluation job %s failed", job_id)
        db.update_evaluation_job(
            job_id,
            status="failed",
            error_message=str(exc)[:2000],
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


@app.post(
    "/catalog/evaluate",
    status_code=202,
    dependencies=protected(),
)
def evaluate_catalog_response(
    req: CatalogEvaluationRequest,
    background_tasks: BackgroundTasks,
):
    # Validate data before creating a job so user errors are returned immediately.
    _prepare_catalog_evaluation(req)

    job_id = str(uuid4())
    try:
        db.create_evaluation_job(
            job_id,
            "catalog_response_evaluation",
            req.model_dump(),
        )
    except Exception as exc:
        logger.exception("Could not create evaluation job")
        raise HTTPException(
            status_code=503,
            detail="Could not create evaluation job. Apply the quality operations migration.",
        ) from exc

    background_tasks.add_task(_run_catalog_job, job_id, req)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Evaluation job created. Poll /evaluation-jobs/{job_id}.",
    }


@app.get("/evaluation-jobs/{job_id}", dependencies=[Depends(require_api_key)])
def evaluation_job(job_id: str):
    row = db.get_evaluation_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Evaluation job not found.")

    payload = {
        "job_id": row["job_id"],
        "job_type": row["job_type"],
        "status": row["status"],
        "created_at": row["created_at"],
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "error_message": row.get("error_message"),
    }
    if row.get("status") == "completed":
        payload["result"] = row.get("result_json")
    return payload


@app.get("/ops/products", dependencies=[Depends(require_api_key)])
def products(
    q: str | None = None,
    brand: str | None = None,
    product_type: str | None = None,
    domain_name: str | None = None,
    limit: int = 50,
):
    try:
        return db.list_product_metadata(q, brand, product_type, domain_name, limit)
    except Exception as exc:
        logger.exception("Could not list catalog product metadata")
        raise HTTPException(status_code=503, detail="Could not list catalog product metadata.") from exc


@app.get("/ops/policies/active", dependencies=[Depends(require_api_key)])
def active_policies():
    try:
        return db.list_active_policies()
    except Exception as exc:
        logger.exception("Could not list active policies")
        raise HTTPException(status_code=503, detail="Could not list active policies") from exc


# --------------------------- Annotation operations ---------------------------

@app.get("/ops/tasks", dependencies=[Depends(require_api_key)])
def operational_tasks(category: str | None = None):
    try:
        return db.list_annotation_tasks(category)
    except Exception as exc:
        logger.exception("Could not list annotation tasks")
        raise HTTPException(status_code=503, detail="Could not list annotation tasks") from exc


@app.get("/ops/sops/active", dependencies=[Depends(require_api_key)])
def active_sops():
    try:
        return db.list_active_sops()
    except Exception as exc:
        logger.exception("Could not list active SOPs")
        raise HTTPException(status_code=503, detail="Could not list active SOPs") from exc


@app.post("/ops/annotations", status_code=201, dependencies=protected())
def submit_operational_annotation(req: OperationalAnnotationRequest):
    try:
        if bool(req.task_id) == bool(req.trace_id):
            raise HTTPException(
                status_code=422,
                detail="Provide exactly one of task_id or trace_id.",
            )

        if req.task_id:
            task = next(
                (x for x in db.list_annotation_tasks() if x["task_id"] == req.task_id),
                None,
            )
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
        else:
            review = db.get_review_queue_item(req.review_id, include_automated=False) if req.review_id else None
            if not review:
                raise HTTPException(status_code=404, detail="Review queue item not found.")
            if review["review"]["trace_id"] != req.trace_id:
                raise HTTPException(status_code=409, detail="Review and trace IDs do not match.")
            if review["review"]["status"] not in {"in_review", "queued"}:
                raise HTTPException(status_code=409, detail="This review is no longer open.")
            if review["review"]["status"] == "queued":
                db.claim_review(req.review_id, req.annotator_id)

        sop = next(
            (x for x in db.list_active_sops() if x["sop_id"] == req.sop_id),
            None,
        )
        if not sop:
            raise HTTPException(status_code=409, detail="SOP is not active")

        payload = req.model_dump(exclude_none=True)
        payload.pop("review_id", None)
        payload["review_source"] = "evaluation_trace" if req.trace_id else "annotation_task"
        row = db.submit_annotation(payload)
        return {"status": "submitted", "annotation": row}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not submit operational annotation")
        raise HTTPException(status_code=503, detail="Could not submit annotation") from exc


@app.get("/ops/annotations", dependencies=[Depends(require_api_key)])
def operational_annotations(
    task_id: str | None = None,
    trace_id: str | None = None,
):
    try:
        return db.list_submissions(task_id=task_id, trace_id=trace_id)
    except Exception as exc:
        logger.exception("Could not list operational annotations")
        raise HTTPException(status_code=503, detail="Could not list annotations") from exc


@app.get("/ops/metrics", dependencies=[Depends(require_api_key)])
def operational_metrics():
    try:
        return summarize_annotations(db.list_submissions())
    except Exception as exc:
        logger.exception("Could not calculate operational metrics")
        raise HTTPException(status_code=503, detail="Could not calculate metrics") from exc


@app.get("/ops/review-agreement", dependencies=[Depends(require_api_key)])
def review_agreement():
    try:
        return summarize_review_agreement(db.list_submissions())
    except Exception as exc:
        logger.exception("Could not calculate review agreement")
        raise HTTPException(status_code=503, detail="Could not calculate review agreement") from exc


@app.get("/ops/audit", dependencies=[Depends(require_api_key)])
def audit_log():
    try:
        return (
            db.get_client()
            .table("annotation_audit_events")
            .select("*")
            .order("created_at", desc=True)
            .limit(500)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        logger.exception("Could not retrieve audit events")
        raise HTTPException(status_code=503, detail="Could not retrieve audit events") from exc


@app.post("/ops/review-queue", status_code=201, dependencies=protected())
def queue_review(req: ReviewQueueRequest):
    try:
        return db.enqueue_review(req.trace_id, req.priority)
    except KeyError:
        raise HTTPException(status_code=404, detail="Evaluation trace not found.")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not enqueue review")
        raise HTTPException(status_code=503, detail="Could not enqueue review") from exc


@app.get("/ops/review-queue", dependencies=[Depends(require_api_key)])
def review_queue(status: str | None = "queued"):
    try:
        return db.list_review_queue(status=status)
    except Exception as exc:
        logger.exception("Could not list review queue")
        raise HTTPException(status_code=503, detail="Could not list review queue") from exc


@app.get("/ops/review-queue/{review_id}", dependencies=[Depends(require_api_key)])
def review_queue_item(review_id: str):
    item = db.get_review_queue_item(review_id, include_automated=False)
    if not item:
        raise HTTPException(status_code=404, detail="Review not found.")

    if item["review"]["status"] in {"completed", "skipped"}:
        item = db.get_review_queue_item(review_id, include_automated=True)
    return item


@app.post("/ops/review-queue/{review_id}/claim", dependencies=protected())
def claim_review(review_id: str, req: ReviewClaimRequest):
    row = db.claim_review(review_id, req.reviewer)
    if not row:
        raise HTTPException(status_code=409, detail="Review is no longer queued.")
    return row


# --------------------------- SOP governance ---------------------------

class SOPDraftRequest(BaseModel):
    sop_name: str = Field(min_length=1, max_length=120)
    content_json: dict
    change_summary: str = Field(min_length=1, max_length=2000)
    created_by: str = Field(min_length=1, max_length=120)


class SOPReviewRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=120)


@app.get("/ops/sops", dependencies=[Depends(require_api_key)])
def list_sops():
    try:
        return db.list_sops()
    except Exception as exc:
        logger.exception("Could not list SOP versions")
        raise HTTPException(status_code=503, detail="Could not list SOP versions") from exc


@app.post("/ops/sops", status_code=201, dependencies=protected())
def create_sop(req: SOPDraftRequest):
    try:
        return db.create_sop_draft(
            req.sop_name,
            req.content_json,
            req.change_summary,
            req.created_by,
        )
    except Exception as exc:
        logger.exception("Could not create SOP draft")
        raise HTTPException(status_code=503, detail="Could not create SOP draft") from exc


@app.post("/ops/sops/{sop_id}/approve", dependencies=protected())
def approve_sop(sop_id: str, req: SOPReviewRequest):
    try:
        row = db.review_sop(sop_id, req.reviewer, True)
    except Exception as exc:
        logger.exception("Could not approve SOP")
        raise HTTPException(status_code=503, detail="Could not approve SOP") from exc
    if not row:
        raise HTTPException(status_code=409, detail="Only draft SOPs can be approved")
    db.record_audit_event(
        "sop",
        sop_id,
        "approved",
        req.reviewer,
        {"sop_name": row["sop_name"], "version": row["version"]},
    )
    return row


@app.post("/ops/sops/{sop_id}/activate", dependencies=protected())
def activate_sop(sop_id: str, req: SOPReviewRequest):
    try:
        row = db.activate_sop(sop_id, req.reviewer)
    except Exception as exc:
        logger.exception("Could not activate SOP")
        raise HTTPException(status_code=503, detail="Could not activate SOP") from exc
    if not row:
        raise HTTPException(status_code=409, detail="Only approved SOPs can be activated")
    return row
