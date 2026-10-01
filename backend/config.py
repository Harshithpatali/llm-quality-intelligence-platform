import os
from dotenv import load_dotenv

load_dotenv()

def csv_env(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# Groq retired llama-3.3-70b-versatile on 2026-08-16.
# GPT-OSS 120B is the current replacement model used by this project.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
OPENROUTER_MODELS = csv_env("OPENROUTER_MODELS", "openai/gpt-oss-120b,deepseek/deepseek-v4-flash-0731")
JUDGE_PROVIDER = os.getenv("JUDGE_PROVIDER", "")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/platform.db")
DATASET_PATH = os.getenv("DATASET_PATH", "data/benchmark.jsonl")
