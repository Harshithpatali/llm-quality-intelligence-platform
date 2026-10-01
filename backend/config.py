import os
from dotenv import load_dotenv

load_dotenv()

def csv_env(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENROUTER_MODELS = csv_env("OPENROUTER_MODELS", "meta-llama/llama-3.3-70b-instruct,google/gemini-2.0-flash-001")
JUDGE_PROVIDER = os.getenv("JUDGE_PROVIDER", "")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/platform.db")
DATASET_PATH = os.getenv("DATASET_PATH", "data/benchmark.jsonl")
