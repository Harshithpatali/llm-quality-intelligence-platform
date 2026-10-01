import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .benchmark import load_dataset, run_benchmark
from .schemas import AnnotationRequest, RunRequest

load_dotenv()
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in __import__("os").getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

app = FastAPI(
    title="LLM Quality Intelligence API",
    version="1.2.0",
    description="Controlled multi-model benchmarking and human quality review.",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def root():
    return {
        "service": "LLM Quality Intelligence API",
        "docs": "/docs",
        "health": "/health",
    }


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
        raise HTTPException(
            status_code=502,
            detail="Benchmark execution failed. Check API logs and provider configuration.",
        ) from exc


@app.get("/runs")
def runs():
    try:
        return db.list_runs()
    except Exception as exc:
        logger.exception("Could not retrieve benchmark runs")
        raise HTTPException(status_code=503, detail="Could not retrieve benchmark runs") from exc


@app.get("/runs/{run_id}")
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


@app.post("/annotations")
def annotate(req: AnnotationRequest):
    try:
        annotation_id = db.save_annotation(req, datetime.now(timezone.utc).isoformat())
        return {"id": annotation_id, "status": "saved"}
    except Exception as exc:
        logger.exception("Could not save annotation")
        raise HTTPException(status_code=503, detail="Could not save annotation") from exc


@app.get("/annotations")
def annotations():
    try:
        return db.list_annotations()
    except Exception as exc:
        logger.exception("Could not retrieve annotations")
        raise HTTPException(status_code=503, detail="Could not retrieve annotations") from exc
