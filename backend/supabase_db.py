import os
from datetime import datetime, timezone
from typing import Any
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE_RUNS = "llm_benchmark_runs"
TABLE_ANNOTATIONS = "llm_annotations"
TABLE_RUBRICS = "llm_rubrics"
_client: Client | None = None

def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("Supabase is not configured on the API service.")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

def init_db() -> None:
    if SUPABASE_URL and SUPABASE_KEY:
        get_client()

def save_run(run_id: str, created_at: str, status: str, config: dict[str, Any], results: list[dict[str, Any]]) -> None:
    get_client().table(TABLE_RUNS).upsert({"run_id": run_id, "created_at": created_at, "status": status, "config_json": config, "results_json": results}).execute()

def list_runs() -> list[dict[str, Any]]:
    response = get_client().table(TABLE_RUNS).select("run_id,created_at,status,config_json").order("created_at", desc=True).limit(100).execute()
    return response.data or []

def get_run(run_id: str) -> dict[str, Any] | None:
    response = get_client().table(TABLE_RUNS).select("*").eq("run_id", run_id).limit(1).execute()
    return response.data[0] if response.data else None

def save_annotation(annotation, created_at: str) -> int:
    response = get_client().table(TABLE_ANNOTATIONS).insert({"run_id": annotation.run_id, "case_id": annotation.case_id, "provider": annotation.provider, "model": annotation.model, "rating": annotation.rating, "label": annotation.label, "notes": annotation.notes, "reviewer": annotation.reviewer, "created_at": created_at}).execute()
    return int(response.data[0]["id"])

def list_annotations() -> list[dict[str, Any]]:
    response = get_client().table(TABLE_ANNOTATIONS).select("*").order("created_at", desc=True).limit(500).execute()
    return response.data or []

def create_rubric(payload: dict[str, Any]) -> dict[str, Any]:
    client = get_client()
    latest = client.table(TABLE_RUBRICS).select("version").eq("rubric_name", payload["rubric_name"]).order("version", desc=True).limit(1).execute()
    version = int(latest.data[0]["version"]) + 1 if latest.data else 1
    row = {"rubric_id": payload["rubric_id"], "rubric_name": payload["rubric_name"], "version": version, "status": "draft", "rubric_json": payload["rubric_json"], "source_document": payload.get("source_document"), "generation_notes": payload.get("generation_notes", ""), "created_by": payload.get("created_by", "system")}
    response = client.table(TABLE_RUBRICS).insert(row).execute()
    return response.data[0]

def list_rubrics(rubric_name: str | None = None) -> list[dict[str, Any]]:
    query = get_client().table(TABLE_RUBRICS).select("*").order("created_at", desc=True).limit(200)
    if rubric_name:
        query = query.eq("rubric_name", rubric_name)
    return query.execute().data or []

def get_rubric(rubric_id: str) -> dict[str, Any] | None:
    response = get_client().table(TABLE_RUBRICS).select("*").eq("rubric_id", rubric_id).limit(1).execute()
    return response.data[0] if response.data else None

def update_rubric(rubric_id: str, rubric_json: dict[str, Any], review_notes: str, reviewer: str) -> dict[str, Any] | None:
    response = get_client().table(TABLE_RUBRICS).update({"rubric_json": rubric_json, "review_notes": review_notes, "reviewed_by": reviewer, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("rubric_id", rubric_id).eq("status", "draft").execute()
    return response.data[0] if response.data else None

def approve_rubric(rubric_id: str, reviewer: str, review_notes: str) -> dict[str, Any] | None:
    response = get_client().table(TABLE_RUBRICS).update({"status": "approved", "reviewed_by": reviewer, "review_notes": review_notes}).eq("rubric_id", rubric_id).eq("status", "draft").execute()
    return response.data[0] if response.data else None

def activate_rubric(rubric_id: str) -> dict[str, Any] | None:
    client = get_client()
    current = get_rubric(rubric_id)
    if not current or current["status"] != "approved":
        return None
    client.table(TABLE_RUBRICS).update({"status": "retired"}).eq("rubric_name", current["rubric_name"]).eq("status", "active").execute()
    response = client.table(TABLE_RUBRICS).update({"status": "active"}).eq("rubric_id", rubric_id).eq("status", "approved").execute()
    return response.data[0] if response.data else None
