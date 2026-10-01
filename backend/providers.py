import os, time, requests
from . import config

class ProviderError(RuntimeError): pass

def _post(url, key, model, prompt, timeout=60):
    if not key:
        raise ProviderError("API key is not configured. Add it to .env and restart the API.")
    start = time.perf_counter()
    try:
        r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type":"application/json"},
            json={"model":model,"messages":[{"role":"user","content":prompt}],"temperature":0.0},
            timeout=timeout)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return {"response": text or "", "latency_ms": round((time.perf_counter()-start)*1000,2),
                "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens")}
    except requests.RequestException as e:
        raise ProviderError(f"Provider request failed: {e}") from e
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError(f"Unexpected provider response: {e}") from e

def call_provider(provider, model, prompt):
    if provider == "groq":
        return _post("https://api.groq.com/openai/v1/chat/completions", config.GROQ_API_KEY, model, prompt)
    if provider == "openrouter":
        return _post("https://openrouter.ai/api/v1/chat/completions", config.OPENROUTER_API_KEY, model, prompt)
    raise ProviderError(f"Unsupported provider: {provider}")

def configured_models(providers):
    models=[]
    if "groq" in providers:
        models.append({"provider":"groq","model":config.GROQ_MODEL})
    if "openrouter" in providers:
        models.extend({"provider":"openrouter","model":m} for m in config.OPENROUTER_MODELS)
    return models
