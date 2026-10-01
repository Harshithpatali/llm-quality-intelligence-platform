import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import RunRequest, AnnotationRequest
from . import db
from .benchmark import load_dataset, run_benchmark

app=FastAPI(title="LLM Quality Intelligence API",version="1.0.0",
 description="Benchmark and human-review API for LLM response quality.")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

@app.on_event("startup")
def startup(): db.init_db()

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/benchmark")
def benchmark(): return {"count":len(load_dataset()),"cases":load_dataset()}

@app.post("/benchmark/run")
def run(req: RunRequest):
    try: return run_benchmark(req.providers,req.limit,req.categories)
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/runs")
def runs():
    rows=db.list_runs()
    for r in rows: r["config"]=json.loads(r.pop("config_json"))
    return rows

@app.get("/runs/{run_id}")
def run_detail(run_id:str):
    row=db.get_run(run_id)
    if not row: raise HTTPException(404,"Run not found")
    row["config"]=json.loads(row.pop("config_json")); row["results"]=json.loads(row.pop("results_json"))
    return row

@app.post("/annotations")
def annotate(req:AnnotationRequest):
    db.init_db()
    annotation_id=db.save_annotation(req,datetime.now(timezone.utc).isoformat())
    return {"id":annotation_id,"status":"saved"}

@app.get("/annotations")
def annotations():
    db.init_db()
    return db.list_annotations()
