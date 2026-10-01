import os, requests, pandas as pd, streamlit as st
API=os.getenv("API_URL","http://localhost:8000")
st.set_page_config(page_title="LLM Quality Intelligence",page_icon="🧪",layout="wide")
st.title("🧪 LLM Quality Intelligence Platform")
st.caption("Reproducible multi-model benchmarking • transparent diagnostics • human review")
with st.sidebar:
    st.header("Benchmark controls")
    providers=st.multiselect("Providers",["groq","openrouter"],default=["groq","openrouter"])
    limit=st.slider("Benchmark cases",1,300,20)
    st.caption("Keys are configured on the API server in .env.")
    page=st.radio("Workspace",["Overview","Run benchmark","Human review","Dataset"])
def get(path):
    try:
        r=requests.get(API+path,timeout=15); r.raise_for_status(); return r.json()
    except Exception as e: st.error(f"API unavailable: {e}"); return None
if page=="Overview":
    health=get("/health")
    if health: st.success("API connected")
    runs=get("/runs")
    if runs:
        st.subheader("Recent benchmark runs")
        st.dataframe(pd.DataFrame(runs),use_container_width=True,hide_index=True)
        rid=st.selectbox("Inspect run", [x["run_id"] for x in runs])
        if rid:
            detail=get("/runs/"+rid)
            if detail:
                df=pd.DataFrame(detail["results"])
                ok=df[df.status=="success"] if not df.empty else df
                a,b,c=st.columns(3)
                a.metric("Responses",len(ok)); b.metric("Mean heuristic score",round(ok.evaluation.apply(lambda x:x["heuristic_score"]).mean(),1) if len(ok) else "—")
                c.metric("Errors",int((df.status=="error").sum()) if not df.empty else 0)
                if len(ok):
                    df["heuristic_score"]=df.evaluation.apply(lambda x:x["heuristic_score"] if x else None)
                    st.bar_chart(df.groupby(["provider","model"]).heuristic_score.mean())
                    st.dataframe(df[["case_id","category","provider","model","status","latency_ms","heuristic_score","response"]],use_container_width=True)
                    st.download_button("Download run CSV",df.to_csv(index=False),"benchmark_results.csv","text/csv")
elif page=="Run benchmark":
    st.subheader("Run a controlled evaluation")
    st.info("Every selected model receives the same prompt set. API usage may incur provider charges.")
    if st.button("Start benchmark",type="primary",disabled=not providers):
        with st.spinner("Calling configured models…"):
            try:
                r=requests.post(API+"/benchmark/run",json={"providers":providers,"limit":limit},timeout=900)
                r.raise_for_status(); data=r.json()
                st.success(f"Run complete: {data['run_id']} — {data['cases']} cases × {data['models']} models")
                df=pd.DataFrame(data["results"])
                if not df.empty:
                    df["heuristic_score"]=df.evaluation.apply(lambda x:x["heuristic_score"] if x else None)
                    st.dataframe(df[["case_id","provider","model","status","latency_ms","heuristic_score","error"]],use_container_width=True)
                    st.download_button("Download results",df.to_csv(index=False),"results.csv","text/csv")
            except Exception as e: st.error(str(e))
elif page=="Human review":
    st.subheader("Human annotation queue")
    runs=get("/runs") or []
    if runs:
        rid=st.selectbox("Run", [r["run_id"] for r in runs])
        detail=get("/runs/"+rid)
        if detail:
            rows=[x for x in detail["results"] if x["status"]=="success"]
            if rows:
                keys=[f"{x['case_id']} | {x['provider']} | {x['model']}" for x in rows]
                chosen=st.selectbox("Response",range(len(rows)),format_func=lambda i:keys[i])
                item=rows[chosen]
                st.markdown("**Prompt**"); st.write(item["prompt"])
                st.markdown("**Reference**"); st.write(item["reference_answer"])
                st.markdown("**Model response**"); st.write(item["response"])
                with st.form("annotation"):
                    rating=st.slider("Quality rating",1,5,3)
                    label=st.selectbox("Label",["excellent","acceptable","poor","unsafe","needs_review"])
                    reviewer=st.text_input("Reviewer","Harshith")
                    notes=st.text_area("Notes")
                    submitted=st.form_submit_button("Save annotation")
                if submitted:
                    payload={"run_id":rid,"case_id":item["case_id"],"provider":item["provider"],"model":item["model"],"rating":rating,"label":label,"notes":notes,"reviewer":reviewer}
                    try:
                        res=requests.post(API+"/annotations",json=payload,timeout=15); res.raise_for_status(); st.success("Annotation saved")
                    except Exception as e: st.error(str(e))
            else: st.info("No successful responses in this run.")
    else: st.info("Run a benchmark first.")
    anns=get("/annotations")
    if anns: st.dataframe(pd.DataFrame(anns),use_container_width=True,hide_index=True)
else:
    data=get("/benchmark")
    if data:
        st.metric("Benchmark examples",data["count"])
        df=pd.DataFrame(data["cases"])
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.download_button("Download dataset CSV",df.to_csv(index=False),"benchmark_dataset.csv","text/csv")
