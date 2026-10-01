# Deploy the Streamlit frontend

Deploy the frontend separately on Streamlit Community Cloud. The API runs as a Docker service on Render.

1. Create an app from this GitHub repository.
2. Set **Main file path** to `frontend/app.py`.
3. In app settings, add this secret:

```toml
API_URL = "https://YOUR-RENDER-SERVICE.onrender.com"
```

The Streamlit app calls the public Render API over HTTPS. It does not connect directly to Supabase and needs no provider keys or API access token.

## Render backend (manual Docker deployment)

1. In Render, choose **New → Web Service** and connect this repository.
2. Select **Docker** as the runtime.
3. Set Dockerfile path to `./Dockerfile` and Docker context directory to `.`.
4. Set health check path to `/health`.
5. Configure `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GROQ_API_KEY`, and `OPENROUTER_API_KEY` as Render environment variables.
6. Deploy. Render supplies the `PORT` variable used by the container.

Do not configure `API_ACCESS_TOKEN`; the API is intentionally open for this demo. The public benchmark endpoint can trigger provider usage and incur costs. Do not share the URL widely until rate limits and spend controls are implemented.

The Docker image runs only FastAPI as a non-root user. Streamlit is deployed independently by Streamlit Community Cloud.
