# Deploy the Streamlit frontend

Deploy the frontend separately on Streamlit Community Cloud. The API runs as a Docker service on Render.

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

## Render backend (Docker)

1. In Render, choose **New → Blueprint** and connect this repository.
2. Render reads `render.yaml`, builds the backend using the root `Dockerfile`, and uses `/health` as the health check.
3. Add the requested secrets in the Render dashboard: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GROQ_API_KEY`, and `OPENROUTER_API_KEY`. The blueprint generates `API_ACCESS_TOKEN`.
4. After the service is live, copy its `onrender.com` URL into Streamlit's `API_URL` secret, and copy the Render `API_ACCESS_TOKEN` into Streamlit's `API_ACCESS_TOKEN` secret.

The Docker image runs only FastAPI. Streamlit is deployed independently by Streamlit Community Cloud. The container listens on Render's injected `PORT` and runs as a non-root user.

## Production note

The free Render instance may spin down when idle. The first request after inactivity can take time. For a public production service, use an always-on plan, add authentication per user, rate limits, background jobs for long benchmark runs, and monitoring.
