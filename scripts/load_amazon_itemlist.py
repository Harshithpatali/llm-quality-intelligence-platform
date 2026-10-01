#!/usr/bin/env python3
"""Load final_clean_amazon.jsonl into the project Supabase catalog table."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


TABLE = "amazon_itemlist_metadata"


def env(name: str) -> str:
    return os.getenv(name, "").strip().strip('"').strip("'")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Path to final_clean_amazon.jsonl")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    load_dotenv()

    url = env("SUPABASE_URL")
    key = env("SUPABASE_SECRET_KEY") or env("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit(
            "Set SUPABASE_URL and SUPABASE_SECRET_KEY "
            "(or legacy SUPABASE_SERVICE_ROLE_KEY) in the environment."
        )

    rows = []
    seen = 0
    client = create_client(url.rstrip("/"), key)

    with args.path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            rows.append(
                {
                    "item_id": item.get("item_id"),
                    "domain_name": item.get("domain_name"),
                    "item_name": item.get("item_name"),
                    "brand": item.get("brand"),
                    "color": item.get("color"),
                    "product_type": item.get("product_type"),
                    "style": item.get("style"),
                    "material": item.get("material"),
                    "model_number": item.get("model_number"),
                    "bullet_points": item.get("bullet_points"),
                    "bullet_points_text": item.get("bullet_points_text"),
                    "country": item.get("country"),
                    "num_bullets": item.get("num_bullets"),
                }
            )

            if len(rows) >= args.batch_size:
                client.table(TABLE).upsert(
                    rows, on_conflict="item_id,domain_name"
                ).execute()
                seen += len(rows)
                rows.clear()

    if rows:
        client.table(TABLE).upsert(
            rows, on_conflict="item_id,domain_name"
        ).execute()
        seen += len(rows)

    print(f"Upserted {seen:,} source rows into {TABLE}.")


if __name__ == "__main__":
    main()
