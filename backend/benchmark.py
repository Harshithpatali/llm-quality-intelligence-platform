import json, uuid
from datetime import datetime, timezone
from pathlib import Path
from .config import DATASET_PATH
from .providers import call_provider, configured_models, ProviderError
from .evaluator import evaluate
from . import db

def load_dataset():
    path=Path(DATASET_PATH)
    if not path.exists(): return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def run_benchmark(providers, limit=20, categories=None):
    cases=load_dataset()
    if categories: cases=[x for x in cases if x["category"] in categories]
    cases=cases[:limit]
    run_id=str(uuid.uuid4())
    created=datetime.now(timezone.utc).isoformat()
    models=configured_models(providers)
    results=[]
    for case in cases:
        for item in models:
            row={"run_id":run_id,"case_id":case["case_id"],"category":case["category"],
                 "difficulty":case.get("difficulty","medium"),"provider":item["provider"],"model":item["model"],
                 "prompt":case["prompt"],"reference_answer":case["reference_answer"]}
            try:
                out=call_provider(item["provider"],item["model"],case["prompt"])
                row.update(out)
                row["evaluation"]=evaluate(out["response"],case["reference_answer"])
                row["status"]="success"
            except ProviderError as e:
                row.update({"response":"","latency_ms":None,"status":"error","error":str(e),"evaluation":None})
            results.append(row)
    db.save_run(run_id,created,"completed",{"providers":providers,"limit":limit,"categories":categories or []},results)
    return {"run_id":run_id,"created_at":created,"status":"completed","cases":len(cases),"models":len(models),"results":results}
