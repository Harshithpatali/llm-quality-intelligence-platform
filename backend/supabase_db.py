import json
import os
from typing import Any

from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

TABLE_RUNS = "llm_benchmark_runs"
TABLE_ANNOTATIONS = "llm_annotations"

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be configured.")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def init_db() -> None:
    # Schema is managed in Supabase. This function intentionally does not run DDL.
    if SUPABASE_URL and SUPABASE_KEY:
        get_client()


def save_run(run_id: str, created_at: str, status: str, config: dict[str, Any], results: list[dict[str, Any]]) -> None:
    get_client().table(TABLE_RUNS).upsert({
        "run_id": run_id,
        "created_at": created_at,
        "status": status,
        "config_json": config,
        "results_json": results,
    }).execute()


def list_runs() -> list[dict[str, Any]]:
    response = (
        get_client()
        .table(TABLE_RUNS)
        .select("run_id,created_at,status,config_json")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def get_run(run_id: str) -> dict[str, Any] | None:
    response = (
        get_client()
        .table(TABLE_RUNS)
        .select("*")
        .eq("run_id", run_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def save_annotation(annotation, created_at: str) -> int:
    response = (
        get_client()
        .table(TABLE_ANNOTATIONS)
        .insert({
            "run_id": annotation.run_id,
            "case_id": annotation.case_id,
            "provider": annotation.provider,
            "model": annotation.model,
            "rating": annotation.rating,
            "label": annotation.label,
            "notes": annotation.notes,
            "reviewer": annotation.reviewer,
            "created_at": created_at,
        })
        .execute()
    )
    return int(response.data[0]["id"])


def list_annotations() -> list[dict[str, Any]]:
    response = (
        get_client()
        .table(TABLE_ANNOTATIONS)
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []
