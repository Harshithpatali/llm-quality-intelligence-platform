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
TABLE_PRODUCT_METADATA = "amazon_itemlist_metadata"

_REQUIRED_TABLES = {
    TABLE_RUNS: "run_id",
    TABLE_ANNOTATIONS: "id",
    TABLE_RUBRICS: "rubric_id",
    TABLE_PRODUCT_METADATA: "item_id",
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
    """Validate connectivity and return safe diagnostics without exposing credentials."""
    url = _clean_env("SUPABASE_URL")
    secret_key_present = bool(_clean_env("SUPABASE_SECRET_KEY"))
    legacy_key_present = bool(_clean_env("SUPABASE_SERVICE_ROLE_KEY"))

    if not url or not (secret_key_present or legacy_key_present):
        missing = []
        if not url:
            missing.append("SUPABASE_URL")
        if not (secret_key_present or legacy_key_present):
            missing.append("SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY")
        return {
            "configured": False,
            "host": urlparse(url).netloc if url else None,
            "credentials_present": False,
            "missing": missing,
            "tables": {},
        }

    try:
        client = get_client()
        configured_url, _ = _database_config()
    except Exception as exc:
        return {
            "configured": True,
            "host": urlparse(url).netloc,
            "credentials_present": True,
            "connection_ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc)[:300],
            "tables": {},
        }

    checked: dict[str, bool] = {}
    failed_table = None
    try:
        for table, probe_column in _REQUIRED_TABLES.items():
            try:
                client.table(table).select(probe_column).limit(1).execute()
                checked[table] = True
            except Exception as exc:
                failed_table = table
                checked[table] = False
                return {
                    "configured": True,
                    "host": urlparse(configured_url).netloc,
                    "credentials_present": True,
                    "connection_ok": True,
                    "schema_ok": False,
                    "failed_table": failed_table,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                    "tables": checked,
                }
    except Exception as exc:
        return {
            "configured": True,
            "host": urlparse(configured_url).netloc,
            "credentials_present": True,
            "connection_ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc)[:300],
            "tables": checked,
        }

    return {
        "configured": True,
        "host": urlparse(configured_url).netloc,
        "credentials_present": True,
        "connection_ok": True,
        "schema_ok": True,
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

def get_product_metadata(
    item_id: str,
    domain_name: str,
) -> dict[str, Any] | None:
    """Return one exact catalog record using the composite item_id + domain key."""
    response = (
        get_client()
        .table(TABLE_PRODUCT_METADATA)
        .select(
            "item_id,domain_name,item_name,brand,color,product_type,style,material,"
            "model_number,bullet_points,bullet_points_text,country,num_bullets"
        )
        .eq("item_id", item_id.strip())
        .eq("domain_name", domain_name.strip())
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def list_product_metadata(
    q: str | None = None,
    brand: str | None = None,
    product_type: str | None = None,
    domain_name: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search the project catalog grounding dataset without exposing backend credentials."""
    client = get_client()
    safe_limit = max(1, min(int(limit), 100))
    query = (
        client.table(TABLE_PRODUCT_METADATA)
        .select(
            "item_id,domain_name,item_name,brand,color,product_type,style,material,"
            "model_number,bullet_points,bullet_points_text,country,num_bullets"
        )
        .order("item_name")
        .limit(safe_limit)
    )
    if q and q.strip():
        term = q.strip().replace("%", "\\%").replace(",", "\\,")
        query = query.or_(
            "item_name.ilike.%{0}%,brand.ilike.%{0}%,product_type.ilike.%{0}%,bullet_points_text.ilike.%{0}%".format(
                term
            )
        )
    if brand and brand.strip():
        query = query.eq("brand", brand.strip())
    if product_type and product_type.strip():
        query = query.eq("product_type", product_type.strip())
    if domain_name and domain_name.strip():
        query = query.eq("domain_name", domain_name.strip())
    return query.execute().data or []


def list_active_policies() -> list[dict[str, Any]]:
    return (
        get_client()
        .table("quality_policies")
        .select("*")
        .eq("status", "active")
        .order("policy_name")
        .order("version", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )


def get_policy(policy_id: str) -> dict[str, Any] | None:
    response = (
        get_client()
        .table("quality_policies")
        .select("*")
        .eq("policy_id", policy_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def create_evaluation_job(
    job_id: str,
    job_type: str,
    request_json: dict[str, Any],
) -> dict[str, Any]:
    row = {
        "job_id": job_id,
        "job_type": job_type,
        "status": "queued",
        "request_json": request_json,
    }
    return get_client().table("evaluation_jobs").insert(row).execute().data[0]


def get_evaluation_job(job_id: str) -> dict[str, Any] | None:
    response = (
        get_client()
        .table("evaluation_jobs")
        .select("*")
        .eq("job_id", job_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def update_evaluation_job(
    job_id: str,
    *,
    status: str,
    result_json: dict[str, Any] | None = None,
    error_message: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {"status": status}
    if result_json is not None:
        payload["result_json"] = result_json
    if error_message is not None:
        payload["error_message"] = error_message
    if started_at is not None:
        payload["started_at"] = started_at
    if completed_at is not None:
        payload["completed_at"] = completed_at
    response = (
        get_client()
        .table("evaluation_jobs")
        .update(payload)
        .eq("job_id", job_id)
        .execute()
    )
    return response.data[0] if response.data else None


def save_evaluation_traces(run_id: str, traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not traces:
        return []
    rows = []
    for trace in traces:
        rows.append(
            {
                "trace_id": trace.get("trace_id") or str(uuid4()),
                "run_id": run_id,
                "run_type": trace.get("run_type", "catalog_response_evaluation"),
                "case_id": trace.get("case_id"),
                "item_id": trace.get("item_id"),
                "domain_name": trace.get("domain_name"),
                "user_query": trace.get("user_query", ""),
                "provider": trace.get("provider", ""),
                "model": trace.get("model", ""),
                "prompt": trace.get("prompt", ""),
                "response": trace.get("response", ""),
                "status": trace.get("status", "error"),
                "error_type": trace.get("error_type"),
                "error_message": trace.get("error"),
                "latency_ms": trace.get("latency_ms"),
                "prompt_tokens": trace.get("prompt_tokens"),
                "completion_tokens": trace.get("completion_tokens"),
                "estimated_cost_usd": trace.get("estimated_cost_usd"),
                "policy_id": trace.get("policy_id"),
                "rubric_id": trace.get("rubric_id"),
                "rubric_version": trace.get("rubric_version"),
                "automated_evaluation": trace.get("rubric_evaluation"),
                "review_status": trace.get("review_status", "unreviewed"),
            }
        )
    return get_client().table("evaluation_traces").insert(rows).execute().data or []


def get_evaluation_trace(trace_id: str) -> dict[str, Any] | None:
    response = (
        get_client()
        .table("evaluation_traces")
        .select("*")
        .eq("trace_id", trace_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def list_evaluation_traces(run_id: str | None = None) -> list[dict[str, Any]]:
    query = (
        get_client()
        .table("evaluation_traces")
        .select("*")
        .order("created_at", desc=True)
        .limit(1000)
    )
    if run_id:
        query = query.eq("run_id", run_id)
    return query.execute().data or []


def enqueue_review(trace_id: str, priority: int = 0) -> dict[str, Any]:
    client = get_client()
    existing = (
        client.table("quality_review_queue")
        .select("*")
        .eq("trace_id", trace_id)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return existing[0]

    trace = get_evaluation_trace(trace_id)
    if not trace:
        raise KeyError("Evaluation trace not found.")
    if trace.get("status") != "success":
        raise ValueError("Only successful evaluation traces can be queued for human review.")

    review = (
        client.table("quality_review_queue")
        .insert(
            {
                "review_id": str(uuid4()),
                "trace_id": trace_id,
                "status": "queued",
                "priority": int(priority),
                "blind_mode": True,
            }
        )
        .execute()
        .data[0]
    )
    client.table("evaluation_traces").update(
        {"review_status": "queued"}
    ).eq("trace_id", trace_id).execute()
    return review


def list_review_queue(
    status: str | None = None,
    assigned_to: str | None = None,
) -> list[dict[str, Any]]:
    query = (
        get_client()
        .table("quality_review_queue")
        .select("*")
        .order("priority", desc=True)
        .order("created_at")
        .limit(500)
    )
    if status:
        query = query.eq("status", status)
    if assigned_to:
        query = query.eq("assigned_to", assigned_to)

    queue_rows = query.execute().data or []
    trace_ids = [row["trace_id"] for row in queue_rows]
    if not trace_ids:
        return []

    traces = (
        get_client()
        .table("evaluation_traces")
        .select(
            "trace_id,item_id,domain_name,user_query,provider,model,status,"
            "latency_ms,review_status,created_at"
        )
        .in_("trace_id", trace_ids)
        .execute()
        .data
        or []
    )
    trace_by_id = {row["trace_id"]: row for row in traces}
    output = []
    for row in queue_rows:
        item = {**row, "trace": trace_by_id.get(row["trace_id"], {})}
        output.append(item)
    return output


def claim_review(review_id: str, reviewer: str) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc).isoformat()
    response = (
        get_client()
        .table("quality_review_queue")
        .update(
            {
                "status": "in_review",
                "assigned_to": reviewer,
                "claimed_at": now,
            }
        )
        .eq("review_id", review_id)
        .eq("status", "queued")
        .execute()
    )
    if not response.data:
        return None
    row = response.data[0]
    get_client().table("evaluation_traces").update(
        {"review_status": "in_review"}
    ).eq("trace_id", row["trace_id"]).execute()
    return row


def get_review_queue_item(
    review_id: str,
    include_automated: bool = False,
) -> dict[str, Any] | None:
    response = (
        get_client()
        .table("quality_review_queue")
        .select("*")
        .eq("review_id", review_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None

    queue = response.data[0]
    trace = get_evaluation_trace(queue["trace_id"])
    if not trace:
        return None

    result = {"review": queue, "trace": trace}
    if not include_automated:
        trace = dict(trace)
        trace.pop("automated_evaluation", None)
        result["trace"] = trace
    return result


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
    trace_id = payload.get("trace_id")

    if trace_id and not payload.get("automated_evaluation_snapshot"):
        trace = get_evaluation_trace(trace_id)
        if trace:
            payload = {
                **payload,
                "automated_evaluation_snapshot": trace.get("automated_evaluation"),
                "review_source": payload.get("review_source", "evaluation_trace"),
            }

    row = {
        **payload,
        "id": payload.get("id") or str(uuid4()),
        "task_id": payload.get("task_id"),
    }
    result = (
        client.table("annotation_submissions")
        .insert(row)
        .execute()
        .data[0]
    )

    details = {
        "task_id": payload.get("task_id"),
        "trace_id": trace_id,
        "sop_id": payload["sop_id"],
        "review_source": payload.get("review_source", "annotation_task"),
    }
    client.table("annotation_audit_events").insert(
        {
            "entity_type": "annotation",
            "entity_id": result["id"],
            "action": "submitted",
            "actor": payload["annotator_id"],
            "details_json": details,
        }
    ).execute()

    if trace_id:
        client.table("evaluation_traces").update(
            {"review_status": "reviewed"}
        ).eq("trace_id", trace_id).execute()
        (
            client.table("quality_review_queue")
            .update(
                {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("trace_id", trace_id)
            .neq("status", "skipped")
            .execute()
        )

    return result


def list_submissions(
    task_id: str | None = None,
    trace_id: str | None = None,
) -> list[dict[str, Any]]:
    query = (
        get_client()
        .table("annotation_submissions")
        .select("*")
        .order("created_at", desc=True)
        .limit(2000)
    )
    if task_id:
        query = query.eq("task_id", task_id)
    if trace_id:
        query = query.eq("trace_id", trace_id)
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
