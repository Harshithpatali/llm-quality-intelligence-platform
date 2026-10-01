import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

TABLE_RUNS = "llm_benchmark_runs"
TABLE_ANNOTATIONS = "llm_annotations"
TABLE_RUBRICS = "llm_rubrics"

_REQUIRED_TABLES = {
    TABLE_RUNS: "run_id",
    TABLE_ANNOTATIONS: "id",
    TABLE_RUBRICS: "rubric_id",
    "annotation_tasks": "task_id",
    "annotation_sops": "sop_id",
    "annotation_submissions": "id",
    "annotation_audit_events": "id",
}

_client: Client | None = None
_client_config: tuple[str, str] | None = None


def _clean_env(name: str) -> str:
    """Read a Render/local environment variable defensively."""
    value = os.getenv(name, "")
    return value.strip().strip('"').strip("'")


def _database_config() -> tuple[str, str]:
    url = _clean_env("SUPABASE_URL")
    key = _clean_env("SUPABASE_SECRET_KEY") or _clean_env("SUPABASE_SERVICE_ROLE_KEY")

    missing = []
    if not url:
        missing.append("SUPABASE_URL")
    if not key:
        missing.append("SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY")
    if missing:
        raise RuntimeError(
            "Supabase configuration is missing: " + ", ".join(missing)
        )

    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(
            "SUPABASE_URL must be a valid HTTPS URL such as "
            "https://<project-ref>.supabase.co"
        )

    return url.rstrip("/"), key


def get_client() -> Client:
    """Create/cache the client from the current environment configuration."""
    global _client, _client_config

    config = _database_config()
    if _client is None or _client_config != config:
        _client = create_client(*config)
        _client_config = config
    return _client


def init_db() -> None:
    if _clean_env("SUPABASE_URL") and (
        _clean_env("SUPABASE_SECRET_KEY")
        or _clean_env("SUPABASE_SERVICE_ROLE_KEY")
    ):
        get_client()


def database_status() -> dict[str, Any]:
    """Validate connectivity and the schema required by the API."""
    client = get_client()
    url, _ = _database_config()
    checked: dict[str, bool] = {}
    for table, probe_column in _REQUIRED_TABLES.items():
        client.table(table).select(probe_column).limit(1).execute()
        checked[table] = True

    return {
        "host": urlparse(url).netloc,
        "tables": checked,
    }


def save_run(run_id: str, created_at: str, status: str, config: dict[str, Any], results: list[dict[str, Any]]) -> None:
    get_client().table(TABLE_RUNS).upsert(
        {
            "run_id": run_id,
            "created_at": created_at,
            "status": status,
            "config_json": config,
            "results_json": results,
        }
    ).execute()


def list_runs() -> list[dict[str, Any]]:
    response = (
        get_client()
        .table(TABLE_RUNS)
        .select("run_id,created_at,status,config_json")
        .order("created_at", desc=True)
        .limit(100)
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
        .insert(
            {
                "run_id": annotation.run_id,
                "case_id": annotation.case_id,
                "provider": annotation.provider,
                "model": annotation.model,
                "rating": annotation.rating,
                "label": annotation.label,
                "notes": annotation.notes,
                "reviewer": annotation.reviewer,
                "created_at": created_at,
            }
        )
        .execute()
    )
    return int(response.data[0]["id"])


def list_annotations() -> list[dict[str, Any]]:
    response = (
        get_client()
        .table(TABLE_ANNOTATIONS)
        .select("*")
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )
    return response.data or []


def create_rubric(payload: dict[str, Any]) -> dict[str, Any]:
    client = get_client()
    latest = (
        client.table(TABLE_RUBRICS)
        .select("version")
        .eq("rubric_name", payload["rubric_name"])
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    version = int(latest.data[0]["version"]) + 1 if latest.data else 1
    row = {
        "rubric_id": payload["rubric_id"],
        "rubric_name": payload["rubric_name"],
        "version": version,
        "status": "draft",
        "rubric_json": payload["rubric_json"],
        "source_document": payload.get("source_document"),
        "generation_notes": payload.get("generation_notes", ""),
        "created_by": payload.get("created_by", "system"),
    }
    response = client.table(TABLE_RUBRICS).insert(row).execute()
    return response.data[0]


def list_rubrics(rubric_name: str | None = None) -> list[dict[str, Any]]:
    query = (
        get_client()
        .table(TABLE_RUBRICS)
        .select("*")
        .order("created_at", desc=True)
        .limit(200)
    )
    if rubric_name:
        query = query.eq("rubric_name", rubric_name)
    return query.execute().data or []


def get_rubric(rubric_id: str) -> dict[str, Any] | None:
    response = (
        get_client()
        .table(TABLE_RUBRICS)
        .select("*")
        .eq("rubric_id", rubric_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def update_rubric(
    rubric_id: str,
    rubric_json: dict[str, Any],
    review_notes: str,
    reviewer: str,
) -> dict[str, Any] | None:
    response = (
        get_client()
        .table(TABLE_RUBRICS)
        .update(
            {
                "rubric_json": rubric_json,
                "review_notes": review_notes,
                "reviewed_by": reviewer,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("rubric_id", rubric_id)
        .eq("status", "draft")
        .execute()
    )
    return response.data[0] if response.data else None


def approve_rubric(
    rubric_id: str,
    reviewer: str,
    review_notes: str,
) -> dict[str, Any] | None:
    response = (
        get_client()
        .table(TABLE_RUBRICS)
        .update(
            {
                "status": "approved",
                "reviewed_by": reviewer,
                "review_notes": review_notes,
                "approved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("rubric_id", rubric_id)
        .eq("status", "draft")
        .execute()
    )
    return response.data[0] if response.data else None


def activate_rubric(rubric_id: str) -> dict[str, Any] | None:
    client = get_client()
    current = get_rubric(rubric_id)
    if not current or current["status"] != "approved":
        return None

    (
        client.table(TABLE_RUBRICS)
        .update({"status": "retired"})
        .eq("rubric_name", current["rubric_name"])
        .eq("status", "active")
        .execute()
    )
    response = (
        client.table(TABLE_RUBRICS)
        .update(
            {
                "status": "active",
                "activated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("rubric_id", rubric_id)
        .eq("status", "approved")
        .execute()
    )
    return response.data[0] if response.data else None


# Auditable annotation operations
def list_annotation_tasks(category: str | None = None) -> list[dict[str, Any]]:
    query = (
        get_client()
        .table("annotation_tasks")
        .select("*")
        .order("task_id")
        .limit(500)
    )
    if category:
        query = query.eq("category", category)
    return query.execute().data or []


def list_active_sops() -> list[dict[str, Any]]:
    return (
        get_client()
        .table("annotation_sops")
        .select("*")
        .eq("status", "active")
        .order("sop_name")
        .order("version", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )


def submit_annotation(payload: dict[str, Any]) -> dict[str, Any]:
    client = get_client()
    row = {
        **payload,
        "id": payload.get("id") or str(uuid4()),
    }
    result = (
        client.table("annotation_submissions")
        .insert(row)
        .execute()
        .data[0]
    )
    client.table("annotation_audit_events").insert(
        {
            "entity_type": "annotation",
            "entity_id": result["id"],
            "action": "submitted",
            "actor": payload["annotator_id"],
            "details_json": {
                "task_id": payload["task_id"],
                "sop_id": payload["sop_id"],
            },
        }
    ).execute()
    return result


def list_submissions(task_id: str | None = None) -> list[dict[str, Any]]:
    query = (
        get_client()
        .table("annotation_submissions")
        .select("*")
        .order("created_at", desc=True)
        .limit(2000)
    )
    if task_id:
        query = query.eq("task_id", task_id)
    return query.execute().data or []


def record_audit_event(
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str,
    details: dict[str, Any],
) -> None:
    (
        get_client()
        .table("annotation_audit_events")
        .insert(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "actor": actor,
                "details_json": details,
            }
        )
        .execute()
    )


def create_sop_draft(
    name: str,
    content_json: dict,
    change_summary: str,
    created_by: str,
) -> dict[str, Any]:
    client = get_client()
    latest = (
        client.table("annotation_sops")
        .select("version")
        .eq("sop_name", name)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    version = int(latest.data[0]["version"]) + 1 if latest.data else 1
    row = {
        "sop_id": str(uuid4()),
        "sop_name": name,
        "version": version,
        "status": "draft",
        "content_json": content_json,
        "change_summary": change_summary,
        "created_by": created_by,
    }
    return client.table("annotation_sops").insert(row).execute().data[0]


def list_sops() -> list[dict[str, Any]]:
    return (
        get_client()
        .table("annotation_sops")
        .select("*")
        .order("sop_name")
        .order("version", desc=True)
        .limit(200)
        .execute()
        .data
        or []
    )


def review_sop(
    sop_id: str,
    reviewer: str,
    approve: bool,
) -> dict[str, Any] | None:
    status = "approved" if approve else "retired"
    result = (
        get_client()
        .table("annotation_sops")
        .update(
            {
                "status": status,
                "reviewed_by": reviewer,
                "approved_at": (
                    datetime.now(timezone.utc).isoformat() if approve else None
                ),
            }
        )
        .eq("sop_id", sop_id)
        .eq("status", "draft")
        .execute()
    )
    return result.data[0] if result.data else None


def activate_sop(sop_id: str, actor: str) -> dict[str, Any] | None:
    client = get_client()
    found = (
        client.table("annotation_sops")
        .select("*")
        .eq("sop_id", sop_id)
        .limit(1)
        .execute()
        .data
    )
    if not found or found[0]["status"] != "approved":
        return None

    row = found[0]
    (
        client.table("annotation_sops")
        .update({"status": "retired"})
        .eq("sop_name", row["sop_name"])
        .eq("status", "active")
        .execute()
    )
    result = (
        client.table("annotation_sops")
        .update(
            {
                "status": "active",
                "activated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("sop_id", sop_id)
        .eq("status", "approved")
        .execute()
    )
    if result.data:
        record_audit_event(
            "sop",
            sop_id,
            "activated",
            actor,
            {"version": row["version"], "sop_name": row["sop_name"]},
        )
        return result.data[0]
    return None
