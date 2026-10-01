# Deploy the Streamlit frontend

Deploy the frontend separately on Streamlit Community Cloud. The API runs on Render.

1. In Streamlit Community Cloud, create an app from this repository.
2. Set **Main file path** to `frontend/app.py`.
3. Add these secrets in the app's Settings → Secrets:

```toml
API_URL = "https://YOUR-RENDER-SERVICE.onrender.com"
API_ACCESS_TOKEN = "COPY_THE_RENDER_API_ACCESS_TOKEN"
```

4. Keep the API token and Supabase service-role key out of GitHub. The frontend receives only the API access token; Supabase credentials stay on Render.
5. Redeploy after changing secrets.

The Streamlit app makes server-side HTTP requests to the Render API. It does not connect directly to Supabase.

## Render backend

Use the repository's `render.yaml` blueprint, or create a Python web service with:
- Build: `pip install -r requirements.txt`
- Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`

Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GROQ_API_KEY`, and `OPENROUTER_API_KEY` in Render environment settings. Render can generate `API_ACCESS_TOKEN` from the blueprint. Copy that value into Streamlit secrets.

## Production note

The free Render instance may spin down when idle. The first request after inactivity can take time. For a public production service, use an always-on plan, add authentication per user, rate limits, background jobs for long benchmark runs, and monitoring.
