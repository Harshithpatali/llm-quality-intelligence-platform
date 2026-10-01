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
        db.get_client().table("llm_benchmark_runs").select("run_id").limit(1).execute()
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        logger.exception("Readiness check failed")
        raise HTTPException(status_code=503, detail="Database is not ready") from exc

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
