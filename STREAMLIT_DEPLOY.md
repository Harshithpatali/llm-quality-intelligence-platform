# Streamlit Community Cloud deployment

Deploy \`frontend/app.py\` from the repository.

Required Streamlit secrets:

\`\`\`toml
API_URL = "https://llm-quality-intelligence-platform.onrender.com"
\`\`\`

If you set \`API_ACCESS_TOKEN\` in the Render backend, also add the same value to Streamlit secrets:

\`\`\`toml
API_ACCESS_TOKEN = "your-demo-token"
\`\`\`

Do not put Supabase keys, Groq keys, or OpenRouter keys in Streamlit secrets.

The frontend uses the backend API for catalog search, model execution, rubric generation, review queue operations, and annotations.
