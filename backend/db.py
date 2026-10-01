import json, os, sqlite3
from pathlib import Path
from .config import DATABASE_PATH

def connect():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL,
            config_json TEXT NOT NULL, results_json TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, case_id TEXT NOT NULL,
            provider TEXT NOT NULL, model TEXT NOT NULL, rating INTEGER NOT NULL,
            label TEXT NOT NULL, notes TEXT, reviewer TEXT, created_at TEXT NOT NULL)""")

def save_run(run_id, created_at, status, config, results):
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?)",
                  (run_id, created_at, status, json.dumps(config), json.dumps(results)))

def list_runs():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT run_id,created_at,status,config_json FROM runs ORDER BY created_at DESC")]

def get_run(run_id):
    with connect() as c:
        row = c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None

def save_annotation(a, created_at):
    with connect() as c:
        cur = c.execute("""INSERT INTO annotations
            (run_id,case_id,provider,model,rating,label,notes,reviewer,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (a.run_id,a.case_id,a.provider,a.model,a.rating,a.label,a.notes,a.reviewer,created_at))
        return cur.lastrowid

def list_annotations():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM annotations ORDER BY created_at DESC")]
