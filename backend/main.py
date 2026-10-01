import logging
import os
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from . import db
from .benchmark import load_dataset, run_benchmark
from .schemas import AnnotationRequest, RunRequest, RubricDraftRequest, RubricEditRequest, RubricDecisionRequest

load_dotenv()
logger = logging.getLogger(__name__)
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",") if origin.strip()]
app = FastAPI(title="LLM Quality Intelligence API", version="1.3.0", description="Controlled multi-model benchmarking and human quality review.", docs_url="/docs", redoc_url="/redoc")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS or ["*"], allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["Content-Type"])

@app.get("/")
def root():
    return {"service": "LLM Quality Intelligence API", "docs": "/docs", "health": "/health"}

@app.get("/health")
def health():
    return {"status": "ok", "service": "llm-quality-intelligence-api"}

@app.get("/ready")
def ready():
    try:
        return {"status": "ready", "database": db.database_status()}
    except Exception as exc:
        logger.exception(
            "Readiness check failed; verify SUPABASE_URL and "
            "SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY in the API environment"
        )
        raise HTTPException(
            status_code=503,
            detail="Database is not ready. Verify the API Supabase configuration and schema.",
        ) from exc

@app.get("/benchmark")
def benchmark():
    cases = load_dataset()
    return {"count": len(cases), "cases": cases}

@app.post("/benchmark/run")
def run(req: RunRequest):
    try:
        return run_benchmark(req.providers, req.limit, req.categories)
    except Exception as exc:
        logger.exception("Benchmark execution failed")
        raise HTTPException(status_code=502, detail="Benchmark execution failed. Check API logs and provider configuration.") from exc

@app.get("/runs")
def runs():
    try: return db.list_runs()
    except Exception as exc:
        logger.exception("Could not retrieve benchmark runs")
        raise HTTPException(status_code=503, detail="Could not retrieve benchmark runs") from exc

@app.get("/runs/{run_id}")
def run_detail(run_id: str):
    try: row = db.get_run(run_id)
    except Exception as exc:
        logger.exception("Could not retrieve benchmark run %s", run_id)
        raise HTTPException(status_code=503, detail="Could not retrieve benchmark run") from exc
    if not row: raise HTTPException(status_code=404, detail="Run not found")
    row["config"] = row.pop("config_json", {})
    row["results"] = row.pop("results_json", [])
    return row

@app.post("/annotations")
def annotate(req: AnnotationRequest):
    try: return {"id": db.save_annotation(req, datetime.now(timezone.utc).isoformat()), "status": "saved"}
    except Exception as exc:
        logger.exception("Could not save annotation")
        raise HTTPException(status_code=503, detail="Could not save annotation") from exc

@app.get("/annotations")
def annotations():
    try: return db.list_annotations()
    except Exception as exc:
        logger.exception("Could not retrieve annotations")
        raise HTTPException(status_code=503, detail="Could not retrieve annotations") from exc

# Rubric generation output is persisted as a draft. This API deliberately does not
# generate a rubric or treat model output as truth; a reviewer must edit/approve it.
@app.post("/rubrics", status_code=201)
def create_rubric(req: RubricDraftRequest):
    try:
        return db.create_rubric({"rubric_id": str(uuid4()), **req.model_dump()})
    except Exception as exc:
        logger.exception("Could not create rubric draft")
        raise HTTPException(status_code=503, detail="Could not create rubric draft; apply the rubric migration and check database configuration.") from exc

@app.get("/rubrics")
def rubrics(rubric_name: str | None = None):
    try: return db.list_rubrics(rubric_name)
    except Exception as exc:
        logger.exception("Could not list rubrics")
        raise HTTPException(status_code=503, detail="Could not list rubrics") from exc

@app.get("/rubrics/{rubric_id}")
def rubric_detail(rubric_id: str):
    try: row = db.get_rubric(rubric_id)
    except Exception as exc:
        logger.exception("Could not retrieve rubric")
        raise HTTPException(status_code=503, detail="Could not retrieve rubric") from exc
    if not row: raise HTTPException(status_code=404, detail="Rubric not found")
    return row

@app.patch("/rubrics/{rubric_id}")
def edit_rubric(rubric_id: str, req: RubricEditRequest):
    try: row = db.update_rubric(rubric_id, req.rubric_json, req.review_notes, req.reviewer)
    except Exception as exc:
        logger.exception("Could not edit rubric")
        raise HTTPException(status_code=503, detail="Could not edit rubric") from exc
    if not row: raise HTTPException(status_code=409, detail="Only draft rubrics can be edited")
    return row

@app.post("/rubrics/{rubric_id}/approve")
def approve_rubric(rubric_id: str, req: RubricDecisionRequest):
    try: row = db.approve_rubric(rubric_id, req.reviewer, req.review_notes)
    except Exception as exc:
        logger.exception("Could not approve rubric")
        raise HTTPException(status_code=503, detail="Could not approve rubric") from exc
    if not row: raise HTTPException(status_code=409, detail="Only draft rubrics can be approved")
    return row

@app.post("/rubrics/{rubric_id}/activate")
def activate_rubric(rubric_id: str):
    try: row = db.activate_rubric(rubric_id)
    except Exception as exc:
        logger.exception("Could not activate rubric")
        raise HTTPException(status_code=503, detail="Could not activate rubric") from exc
    if not row: raise HTTPException(status_code=409, detail="Only approved rubrics can be activated")
    return row


from .ops_metrics import summarize_annotations
from pydantic import BaseModel, Field
from typing import Literal

class OperationalAnnotationRequest(BaseModel):
    task_id: str
    annotator_id: str = Field(min_length=1, max_length=120)
    sop_id: str
    relevance: Literal["pass", "minor_issue", "major_issue", "not_applicable"]
    correctness: Literal["pass", "minor_issue", "major_issue", "not_applicable"]
    completeness: Literal["pass", "minor_issue", "major_issue", "not_applicable"]
    overall_label: Literal["accept", "revise", "reject", "escalate"]
    evidence: str = Field(min_length=8, max_length=4000)
    defect_category: str = "none"
    confidence: int = Field(ge=1, le=5)
    handling_seconds: int = Field(ge=0, le=86400)
    escalated: bool = False
    is_audit: bool = False

@app.get("/ops/products")
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
        raise HTTPException(
            status_code=503,
            detail="Could not list catalog product metadata. Verify the API Supabase project, key, and catalog schema.",
        ) from exc


@app.get("/ops/tasks")
def operational_tasks(category: str | None = None):
    try:
        return db.list_annotation_tasks(category)
    except Exception as exc:
        logger.exception("Could not list annotation tasks")
        raise HTTPException(
            status_code=503,
            detail="Could not list annotation tasks. Verify the API Supabase project, key, and workflow schema.",
        ) from exc

@app.get("/ops/sops/active")
def active_sops():
    try: return db.list_active_sops()
    except Exception as exc:
        logger.exception("Could not list active SOPs")
        raise HTTPException(status_code=503, detail="Could not list active SOPs") from exc

@app.post("/ops/annotations", status_code=201)
def submit_operational_annotation(req: OperationalAnnotationRequest):
    try:
        task = next((x for x in db.list_annotation_tasks() if x["task_id"] == req.task_id), None)
        if not task: raise HTTPException(status_code=404, detail="Task not found")
        sop = next((x for x in db.list_active_sops() if x["sop_id"] == req.sop_id), None)
        if not sop: raise HTTPException(status_code=409, detail="SOP is not active")
        row = db.submit_annotation(req.model_dump())
        return {"status": "submitted", "annotation": row}
    except HTTPException: raise
    except Exception as exc:
        logger.exception("Could not submit operational annotation")
        raise HTTPException(status_code=503, detail="Could not submit annotation; apply workflow migration and seed tasks") from exc

@app.get("/ops/annotations")
def operational_annotations(task_id: str | None = None):
    try: return db.list_submissions(task_id)
    except Exception as exc:
        logger.exception("Could not list operational annotations")
        raise HTTPException(status_code=503, detail="Could not list annotations") from exc

@app.get("/ops/metrics")
def operational_metrics():
    try:
        rows = db.list_submissions()
        return summarize_annotations(rows)
    except Exception as exc:
        logger.exception("Could not calculate operational metrics")
        raise HTTPException(status_code=503, detail="Could not calculate metrics") from exc

@app.get("/ops/audit")
def audit_log():
    try:
        return db.get_client().table("annotation_audit_events").select("*").order("created_at", desc=True).limit(500).execute().data or []
    except Exception as exc:
        logger.exception("Could not retrieve audit events")
        raise HTTPException(status_code=503, detail="Could not retrieve audit events") from exc


class SOPDraftRequest(BaseModel):
    sop_name: str = Field(min_length=1, max_length=120)
    content_json: dict
    change_summary: str = Field(min_length=1, max_length=2000)
    created_by: str = Field(min_length=1, max_length=120)

class SOPReviewRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=120)

@app.get("/ops/sops")
def list_sops():
    try: return db.list_sops()
    except Exception as exc:
        logger.exception("Could not list SOP versions")
        raise HTTPException(status_code=503, detail="Could not list SOP versions") from exc

@app.post("/ops/sops", status_code=201)
def create_sop(req: SOPDraftRequest):
    try: return db.create_sop_draft(req.sop_name, req.content_json, req.change_summary, req.created_by)
    except Exception as exc:
        logger.exception("Could not create SOP draft")
        raise HTTPException(status_code=503, detail="Could not create SOP draft") from exc

@app.post("/ops/sops/{sop_id}/approve")
def approve_sop(sop_id: str, req: SOPReviewRequest):
    try: row = db.review_sop(sop_id, req.reviewer, True)
    except Exception as exc:
        logger.exception("Could not approve SOP")
        raise HTTPException(status_code=503, detail="Could not approve SOP") from exc
    if not row: raise HTTPException(status_code=409, detail="Only draft SOPs can be approved")
    db.record_audit_event("sop",sop_id,"approved",req.reviewer,{"sop_name":row["sop_name"],"version":row["version"]})
    return row

@app.post("/ops/sops/{sop_id}/activate")
def activate_sop(sop_id: str, req: SOPReviewRequest):
    try: row = db.activate_sop(sop_id, req.reviewer)
    except Exception as exc:
        logger.exception("Could not activate SOP")
        raise HTTPException(status_code=503, detail="Could not activate SOP") from exc
    if not row: raise HTTPException(status_code=409, detail="Only approved SOPs can be activated")
    return row
