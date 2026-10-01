import os
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="LLM Quality Intelligence", page_icon="🧪", layout="wide")

API = st.secrets.get("API_URL", os.getenv("API_URL", "http://localhost:8000")).rstrip("/")
API_KEY = st.secrets.get("API_ACCESS_TOKEN", os.getenv("API_ACCESS_TOKEN", ""))


def api_headers():
    return {"X-API-Key": API_KEY} if API_KEY else {}


def api_get(path):
    try:
        response = requests.get(API + path, headers=api_headers(), timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"API request failed: {exc}")
        return None


st.title("LLM Quality Intelligence Platform")
st.caption("Controlled model evaluation · traceable runs · human quality review")

with st.sidebar:
    st.header("Benchmark controls")
    providers = st.multiselect("Providers", ["groq", "openrouter"], default=["groq", "openrouter"])
    limit = st.slider("Benchmark cases", 1, 60, 20)
    st.caption("Provider keys and Supabase credentials remain on the backend.")
    page = st.radio("Workspace", ["Overview", "Run benchmark", "Human review", "Dataset"])

if page == "Overview":
    health = api_get("/health")
    if health:
        st.success("Backend is online")
    runs = api_get("/runs")
    if runs is not None:
        st.subheader("Recent benchmark runs")
        if runs:
            st.dataframe(pd.DataFrame(runs), use_container_width=True, hide_index=True)
            selected = st.selectbox("Inspect run", [r["run_id"] for r in runs])
            detail = api_get("/runs/" + selected)
            if detail:
                results = detail.get("results", [])
                df = pd.DataFrame(results)
                successful = df[df.status == "success"] if not df.empty else df
                c1, c2, c3 = st.columns(3)
                c1.metric("Successful responses", len(successful))
                scores = [x.get("heuristic_score") for x in successful.get("evaluation", []) if isinstance(x, dict) and x.get("heuristic_score") is not None] if not successful.empty else []
                c2.metric("Mean heuristic score", round(sum(scores)/len(scores), 1) if scores else "—")
                c3.metric("Failed responses", int((df.status == "error").sum()) if not df.empty else 0)
                if not df.empty:
                    df["heuristic_score"] = df.evaluation.apply(lambda x: x.get("heuristic_score") if isinstance(x, dict) else None)
                    st.bar_chart(df.groupby(["provider", "model"]).heuristic_score.mean())
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("Export run CSV", df.to_csv(index=False), "benchmark_run.csv", "text/csv")
        else:
            st.info("No runs yet. Start a benchmark to populate the workspace.")

elif page == "Run benchmark":
    st.subheader("Run a controlled evaluation")
    st.warning("Each selected model receives the same cases. Provider usage may incur charges.")
    if st.button("Start benchmark", type="primary", disabled=not providers):
        with st.spinner("Running benchmark…"):
            try:
                response = requests.post(
                    API + "/benchmark/run",
                    headers=api_headers(),
                    json={"providers": providers, "limit": limit},
                    timeout=1800,
                )
                response.raise_for_status()
                data = response.json()
                st.success(f"Completed run {data['run_id']} · {data['cases']} cases × {data['models']} models")
                df = pd.DataFrame(data["results"])
                if not df.empty:
                    df["heuristic_score"] = df.evaluation.apply(lambda x: x.get("heuristic_score") if isinstance(x, dict) else None)
                    st.dataframe(df[["case_id", "provider", "model", "status", "latency_ms", "heuristic_score"]], use_container_width=True)
                    st.download_button("Export results", df.to_csv(index=False), "benchmark_results.csv", "text/csv")
            except requests.RequestException as exc:
                st.error(f"Benchmark request failed: {exc}")

elif page == "Human review":
    st.subheader("Human annotation workspace")
    runs = api_get("/runs")
    if runs:
        run_id = st.selectbox("Benchmark run", [r["run_id"] for r in runs])
        detail = api_get("/runs/" + run_id)
        if detail:
            candidates = [r for r in detail.get("results", []) if r.get("status") == "success"]
            if candidates:
                selected = st.selectbox("Response under review", range(len(candidates)), format_func=lambda i: f"{candidates[i]['case_id']} · {candidates[i]['provider']} · {candidates[i]['model']}")
                item = candidates[selected]
                st.markdown("**Prompt**"); st.write(item["prompt"])
                st.markdown("**Reference answer**"); st.write(item["reference_answer"])
                st.markdown("**Model response**"); st.write(item["response"])
                with st.form("review_form"):
                    rating = st.slider("Quality rating", 1, 5, 3)
                    label = st.selectbox("Decision", ["excellent", "acceptable", "poor", "unsafe", "needs_review"])
                    reviewer = st.text_input("Reviewer", "Harshith")
                    notes = st.text_area("Evidence and review notes")
                    submit = st.form_submit_button("Save review")
                if submit:
                    payload = {"run_id": run_id, "case_id": item["case_id"], "provider": item["provider"], "model": item["model"], "rating": rating, "label": label, "notes": notes, "reviewer": reviewer}
                    try:
                        response = requests.post(API + "/annotations", headers=api_headers(), json=payload, timeout=20)
                        response.raise_for_status()
                        st.success("Review saved.")
                    except requests.RequestException as exc:
                        st.error(f"Could not save review: {exc}")
            else:
                st.info("This run has no successful model responses.")
    elif runs == []:
        st.info("No benchmark runs are available yet.")
    annotations = api_get("/annotations")
    if annotations:
        st.subheader("Review history")
        st.dataframe(pd.DataFrame(annotations), use_container_width=True, hide_index=True)

else:
    st.subheader("Benchmark dataset")
    data = api_get("/benchmark")
    if data:
        st.metric("Cases", data["count"])
        df = pd.DataFrame(data["cases"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Export benchmark CSV", df.to_csv(index=False), "benchmark_dataset.csv", "text/csv")
