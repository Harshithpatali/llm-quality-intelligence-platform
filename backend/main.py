import hmac
import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import RunRequest, AnnotationRequest
from . import db
from .benchmark import load_dataset, run_benchmark

load_dotenv()

API_ACCESS_TOKEN = os.getenv("API_ACCESS_TOKEN", "")
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "*").split(",") if x.strip()]

app = FastAPI(
    title="LLM Quality Intelligence API",
    version="1.1.0",
    description="Controlled multi-model benchmarking and human quality review.",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    # Local development may omit the token. Production should always set it.
    if API_ACCESS_TOKEN and not hmac.compare_digest(x_api_key or "", API_ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


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
    except Exception:
        raise HTTPException(status_code=503, detail="Database is not ready")


@app.get("/benchmark", dependencies=[Depends(require_api_key)])
def benchmark():
    cases = load_dataset()
    return {"count": len(cases), "cases": cases}


@app.post("/benchmark/run", dependencies=[Depends(require_api_key)])
def run(req: RunRequest):
    try:
        return run_benchmark(req.providers, req.limit, req.categories)
    except Exception:
        raise HTTPException(status_code=502, detail="Benchmark execution failed. Check API logs and provider configuration.")


@app.get("/runs", dependencies=[Depends(require_api_key)])
def runs():
    try:
        return db.list_runs()
    except Exception:
        raise HTTPException(status_code=503, detail="Could not retrieve benchmark runs")


@app.get("/runs/{run_id}", dependencies=[Depends(require_api_key)])
def run_detail(run_id: str):
    try:
        row = db.get_run(run_id)
    except Exception:
        raise HTTPException(status_code=503, detail="Could not retrieve benchmark run")
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    # Supabase JSONB values are already decoded Python objects.
    row["config"] = row.pop("config_json", {})
    row["results"] = row.pop("results_json", [])
    return row


@app.post("/annotations", dependencies=[Depends(require_api_key)])
def annotate(req: AnnotationRequest):
    try:
        annotation_id = db.save_annotation(req, datetime.now(timezone.utc).isoformat())
        return {"id": annotation_id, "status": "saved"}
    except Exception:
        raise HTTPException(status_code=503, detail="Could not save annotation")


@app.get("/annotations", dependencies=[Depends(require_api_key)])
def annotations():
    try:
        return db.list_annotations()
    except Exception:
        raise HTTPException(status_code=503, detail="Could not retrieve annotations")
