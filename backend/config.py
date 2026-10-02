import json
import os
from dotenv import load_dotenv

load_dotenv()

def csv_env(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]

def json_env(name: str, default: str = "{}") -> dict:
    raw = os.getenv(name, default).strip()
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Three genuinely distinct default generation models:
# 1) GPT-OSS 120B on Groq
# 2) GPT-OSS 20B on Groq
# 3) DeepSeek V4 Flash 0731 on OpenRouter
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_MODELS = csv_env(
    "GROQ_MODELS",
    os.getenv("GROQ_MODEL", "openai/gpt-oss-120b") + ",openai/gpt-oss-20b",
)
OPENROUTER_MODELS = csv_env(
    "OPENROUTER_MODELS",
    "deepseek/deepseek-v4-flash-0731",
)

# The judge should be a distinct model by default. Qwen 3.8 27B is a
# separately served Groq model and can be changed without touching generators.
JUDGE_PROVIDER = os.getenv("JUDGE_PROVIDER", "groq").strip()
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen/qwen3.8-27b").strip()

# Rubric generation can use a separate model; defaults to the same judge.
RUBRIC_PROVIDER = os.getenv("RUBRIC_PROVIDER", JUDGE_PROVIDER).strip()
RUBRIC_MODEL = os.getenv("RUBRIC_MODEL", JUDGE_MODEL).strip()

# Optional per-model pricing snapshot for portfolio cost estimates.
# Prices are estimates, not billing truth.
MODEL_PRICING_USD_PER_MILLION = json_env(
    "MODEL_PRICING_USD_PER_MILLION",
    '{"groq/openai/gpt-oss-120b":{"input":0.15,"output":0.60},"groq/openai/gpt-oss-20b":{"input":0.075,"output":0.30},"openrouter/deepseek/deepseek-v4-flash-0731":{"input":0.018,"output":0.32},"groq/qwen/qwen3.8-27b":{"input":0.80,"output":4.00}}',
)

API_ACCESS_TOKEN = os.getenv("API_ACCESS_TOKEN", "").strip()
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "300"))

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/platform.db")
DATASET_PATH = os.getenv("DATASET_PATH", "data/benchmark.jsonl")
