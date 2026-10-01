import os
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="LLM Quality Intelligence", page_icon="◈", layout="wide")

API = st.secrets.get("API_URL", os.getenv("API_URL", "http://localhost:8000")).rstrip("/")
API_KEY = st.secrets.get("API_ACCESS_TOKEN", os.getenv("API_ACCESS_TOKEN", ""))

st.markdown("""
<style>
:root { --ink:#172033; --muted:#6b7280; --line:#e5e9f0; --blue:#3978e8; }
.block-container {padding-top:1.5rem; padding-bottom:3rem; max-width:1500px;}
h1,h2,h3 {letter-spacing:-.035em;color:#172033;}
[data-testid="stMetric"] {background:#fff;border:1px solid #e5e9f0;border-radius:13px;padding:16px 18px;}
[data-testid="stMetricLabel"] {color:#697386;font-size:.82rem;}
[data-testid="stMetricValue"] {color:#172033;font-weight:700;}
div[data-testid="stTabs"] button {font-weight:600;}
section[data-testid="stSidebar"] {background:#f7f8fb;border-right:1px solid #e8ebf1;}
.panel {background:white;border:1px solid #e5e9f0;border-radius:14px;padding:18px 20px;margin-bottom:12px;}
.eyebrow {font-size:.76rem;text-transform:uppercase;letter-spacing:.09em;color:#778196;font-weight:700;}
.subtle {color:#788294;font-size:.9rem;}
.model-pill {display:inline-block;border:1px solid #e5e9f0;border-radius:8px;padding:7px 11px;margin:3px 5px 3px 0;font-size:.83rem;background:white;}
.dot {display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;}
.step {border:1px solid #dfe5ee;border-radius:12px;padding:15px;background:#fff;min-height:116px;}
.step.active {border:2px solid #3978e8;background:#f5f8ff;}
div.stButton>button[kind="primary"] {border-radius:9px;}
</style>
""", unsafe_allow_html=True)

def headers():
    return {"X-API-Key": API_KEY} if API_KEY else {}

def api_get(path):
    try:
        r=requests.get(API+path,headers=headers(),timeout=25); r.raise_for_status(); return r.json()
    except requests.RequestException as e:
        st.error(f"API request failed: {e}"); return None

def api_post(path,payload,timeout=1800):
    r=requests.post(API+path,headers=headers(),json=payload,timeout=timeout); r.raise_for_status(); return r.json()

def frame_results(results):
    df=pd.DataFrame(results or [])
    if not df.empty:
        df["heuristic_score"]=df["evaluation"].apply(lambda x:x.get("heuristic_score") if isinstance(x,dict) else None)
        df["keyword_coverage"]=df["evaluation"].apply(lambda x:100*x.get("keyword_coverage",0) if isinstance(x,dict) else None)
    return df

def model_name(row):
    return f'{row.get("provider","")} / {row.get("model","")}'

st.markdown("<div class='eyebrow'>MODEL QUALITY OPERATIONS</div>",unsafe_allow_html=True)
st.title("Evaluation workspace")
st.markdown("<div class='subtle'>Compare model behavior, inspect response traces, and turn human feedback into repeatable evaluation data.</div>",unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ◈ Quality Lab")
    st.caption("LLM evaluation · review · analytics")
    page=st.radio("WORKSPACE",["Annotation operations","Overview","Compare evaluations","Run evaluation","Human review","Test cases"],label_visibility="visible")
    st.divider()
    st.markdown("**Run configuration**")
    providers=st.multiselect("Providers",["groq","openrouter"],default=["groq","openrouter"])
    limit=st.slider("Cases per run",1,60,20)
    st.caption("Provider and database credentials stay on the API service.")
    st.divider()
    health=api_get("/health")
    if health: st.success("API connected")
    else: st.warning("API unavailable")

runs=api_get("/runs")
runs=runs or []
run_options=[x.get("run_id") for x in runs if x.get("run_id")]
if page=="Overview":
    st.subheader("Quality overview")
    if not runs:
        st.info("No evaluation runs yet. Start an evaluation to populate the workspace.")
    else:
        chosen=st.selectbox("Evaluation run",run_options,format_func=lambda x: next((f'{r.get("created_at","")[:19]} · {r.get("run_id","")[:8]}' for r in runs if r.get("run_id")==x),x))
        detail=api_get("/runs/"+chosen)
        df=frame_results(detail.get("results",[]) if detail else [])
        if not df.empty:
            ok=df[df["status"]=="success"]
            scores=ok["heuristic_score"].dropna()
            models=ok.groupby(["provider","model"],dropna=False)
            a,b,c,d=st.columns(4)
            a.metric("Responses evaluated",len(df))
            b.metric("Successful",len(ok))
            c.metric("Mean diagnostic score",f"{scores.mean():.1f}/100" if len(scores) else "—")
            d.metric("Errors",int((df.status=="error").sum()))
            st.markdown("### Model comparison")
            cols=st.columns([1.5,1,1])
            with cols[0]:
                st.markdown("<div class='panel'><div class='eyebrow'>Models in this run</div>",unsafe_allow_html=True)
                for i,((provider,model),g) in enumerate(models):
                    st.markdown(f"<span class='model-pill'><span class='dot' style='background:{['#4f83df','#d95d62','#d875a3','#83b84b'][i%4]}'></span>{provider} · {model}</span>",unsafe_allow_html=True)
                st.markdown("</div>",unsafe_allow_html=True)
                st.caption("Diagnostic score is reference-term overlap plus a response-length heuristic; it is not a correctness or safety verdict.")
            with cols[1]:
                st.markdown("**Average diagnostic score**")
                if not ok.empty: st.bar_chart(ok.groupby("model")["heuristic_score"].mean())
            with cols[2]:
                st.markdown("**Average latency (ms)**")
                if not ok.empty and "latency_ms" in ok: st.bar_chart(ok.groupby("model")["latency_ms"].mean())
            st.markdown("### Scorecard")
            summary=ok.groupby(["provider","model"],dropna=False).agg(Responses=("case_id","count"),Mean_score=("heuristic_score","mean"),Keyword_coverage=("keyword_coverage","mean"),Mean_latency_ms=("latency_ms","mean")).reset_index()
            if not summary.empty:
                summary["Mean_score"]=summary["Mean_score"].round(1)
                summary["Keyword_coverage"]=summary["Keyword_coverage"].round(1)
                summary["Mean_latency_ms"]=summary["Mean_latency_ms"].round(0)
                st.dataframe(summary,use_container_width=True,hide_index=True)
            with st.expander("Inspect evaluation responses"):
                st.dataframe(df[["case_id","category","provider","model","status","latency_ms","heuristic_score","keyword_coverage"]],use_container_width=True,hide_index=True)
                st.download_button("Export evaluation CSV",df.to_csv(index=False),"evaluation_results.csv","text/csv")
        else: st.info("This run has no response records.")

elif page=="Compare evaluations":
    st.subheader("Compare evaluations")
    if len(run_options)<1: st.info("Run an evaluation first.")
    else:
        selected=st.multiselect("Choose evaluations to compare",run_options,default=run_options[:min(2,len(run_options))],format_func=lambda x:next((f'{r.get("created_at","")[:16]} · {x[:8]}' for r in runs if r.get("run_id")==x),x))
        records=[]
        for rid in selected:
            detail=api_get("/runs/"+rid)
            if detail:
                z=frame_results(detail.get("results",[])); z["evaluation_id"]=rid[:8]; records.append(z)
        if records:
            all_df=pd.concat(records,ignore_index=True)
            good=all_df[all_df.status=="success"]
            st.markdown("### Summary metrics")
            m1,m2,m3=st.columns(3)
            m1.metric("Evaluations selected",len(selected))
            m2.metric("Successful responses",len(good))
            m3.metric("Mean diagnostic score",f'{good.heuristic_score.mean():.1f}/100' if not good.empty else "—")
            st.markdown("### Model score comparison")
            if not good.empty:
                chart=good.groupby(["evaluation_id","model"])["heuristic_score"].mean().unstack(0)
                st.bar_chart(chart)
                latency=good.groupby(["evaluation_id","model"])["latency_ms"].mean().unstack(0)
                st.markdown("### Latency comparison")
                st.bar_chart(latency)
                st.markdown("### Scorecard")
                st.dataframe(good.groupby(["evaluation_id","provider","model"]).agg(Responses=("case_id","count"),Mean_score=("heuristic_score","mean"),Keyword_coverage=("keyword_coverage","mean"),Mean_latency_ms=("latency_ms","mean")).reset_index().round(2),use_container_width=True,hide_index=True)
            st.caption("Comparisons are descriptive. Runs may differ in selected cases, provider availability, or model versions.")
        else: st.info("Select one or more runs to compare.")

elif page=="Run evaluation":
    st.subheader("Run a controlled evaluation")
    st.markdown("<div class='panel'>The same selected test cases are sent to each configured model. Provider usage may incur charges.</div>",unsafe_allow_html=True)
    if st.button("▶ Start evaluation",type="primary",disabled=not providers):
        with st.spinner("Evaluating selected models…"):
            try:
                data=api_post("/benchmark/run",{"providers":providers,"limit":limit})
                st.success(f'Run completed · {data["cases"]} cases × {data["models"]} models')
                df=frame_results(data.get("results",[]))
                st.dataframe(df[["case_id","provider","model","status","latency_ms","heuristic_score"]],use_container_width=True,hide_index=True)
                st.download_button("Download results",df.to_csv(index=False),"evaluation.csv","text/csv")
            except requests.RequestException as e: st.error(f"Evaluation failed: {e}")

elif page=="Human review":
    st.subheader("Human-in-the-loop review")
    st.markdown("<div class='subtle'>Inspect the full prompt and response, record a structured judgment, and preserve the reviewed example.</div>",unsafe_allow_html=True)
    st.markdown("#### Review workflow")
    x1,x2,x3=st.columns(3)
    for col,title,desc,active in [(x1,"1 · Select trace","Choose a production-like model response",False),(x2,"2 · Human review","Inspect evidence and apply the rubric",True),(x3,"3 · Structured feedback","Save labels and notes for analysis",False)]:
        with col: st.markdown(f"<div class='step {'active' if active else ''}'><b>{title}</b><br><span class='subtle'>{desc}</span></div>",unsafe_allow_html=True)
    if runs:
        rid=st.selectbox("Evaluation run",run_options,key="review_run")
        detail=api_get("/runs/"+rid)
        candidates=[x for x in (detail or {}).get("results",[]) if x.get("status")=="success"]
        if candidates:
            idx=st.selectbox("Response trace",range(len(candidates)),format_func=lambda i:f'{candidates[i]["case_id"]} · {candidates[i]["provider"]} · {candidates[i]["model"]}')
            item=candidates[idx]
            left,right=st.columns([1.1,1])
            with left:
                st.markdown("**Prompt / user input**")
                st.markdown(f"<div class='panel'>{item.get('prompt','')}</div>",unsafe_allow_html=True)
                st.markdown("**Reference answer**")
                st.info(item.get("reference_answer",""))
                st.markdown("**Model output**")
                st.markdown(f"<div class='panel'>{item.get('response','')}</div>",unsafe_allow_html=True)
            with right:
                st.markdown("**Trace metadata**")
                st.json({k:item.get(k) for k in ["case_id","category","provider","model","latency_ms","usage","evaluation"] if k in item})
                with st.form("review_form"):
                    rating=st.slider("Overall quality",1,5,3)
                    label=st.selectbox("Review label",["excellent","acceptable","poor","unsafe","needs_review"])
                    reviewer=st.text_input("Reviewer","Harshith")
                    notes=st.text_area("Evidence, failure mode, and suggested correction")
                    submit=st.form_submit_button("Save structured review",type="primary")
                if submit:
                    payload={"run_id":rid,"case_id":item["case_id"],"provider":item["provider"],"model":item["model"],"rating":rating,"label":label,"notes":notes,"reviewer":reviewer}
                    try: api_post("/annotations",payload,timeout=30); st.success("Review saved.")
                    except requests.RequestException as e: st.error(f"Could not save review: {e}")
        else: st.info("No successful responses in this run.")
    else: st.info("No runs are available to review.")
    annotations=api_get("/annotations")
    if annotations:
        st.markdown("### Review history")
        st.dataframe(pd.DataFrame(annotations),use_container_width=True,hide_index=True)


elif page=="Annotation operations":
    st.subheader("Seller response annotation operations")
    st.caption("Project-created synthetic cases · human labels are separate from model-generated diagnostics.")
    metrics=api_get("/ops/metrics")
    if metrics:
        a,b,c,d=st.columns(4)
        a.metric("Annotations",metrics.get("annotation_count",0))
        b.metric("Tasks reviewed",metrics.get("tasks_reviewed",0))
        c.metric("Annotators",metrics.get("unique_annotators",0))
        seconds=metrics.get("mean_handling_seconds")
        d.metric("Mean handling time",f"{seconds:.0f}s" if seconds is not None else "—")
        st.markdown("### Dimension pass rates")
        rates=metrics.get("dimension_pass_rate",{})
        if any(v is not None for v in rates.values()):
            st.bar_chart(pd.Series({k:v*100 for k,v in rates.items() if v is not None},name="Pass rate (%)"))
        m1,m2=st.columns(2)
        m1.metric("Major issue rate",f'{metrics.get("major_issue_rate",0)*100:.1f}%' if metrics.get("major_issue_rate") is not None else "—")
        m2.metric("Escalation rate",f'{metrics.get("escalation_rate",0)*100:.1f}%' if metrics.get("escalation_rate") is not None else "—")
    sops=api_get("/ops/sops/active") or []
    tasks=api_get("/ops/tasks") or []
    if not sops:
        st.warning("No active SOP found. Apply supabase/operations_workflow.sql.")
    elif not tasks:
        st.warning("No annotation tasks found. Apply supabase/operations_workflow.sql.")
    else:
        sop=sops[0]
        st.markdown(f"**Active SOP:** {sop.get('sop_name')} · v{sop.get('version')}  ")
        st.caption("This is a demonstration SOP, not an Amazon SOP. Review and adapt it before using it as an operational standard.")
        task_ids=[t["task_id"] for t in tasks]
        task_id=st.selectbox("Select task",task_ids,format_func=lambda x:next((f'{t["task_id"]} · {t["category"]} · {t["difficulty"]}' for t in tasks if t["task_id"]==x),x))
        task=next(t for t in tasks if t["task_id"]==task_id)
        left,right=st.columns([1,1])
        with left:
            st.markdown("#### Customer query")
            st.info(task["query"])
            st.markdown("#### Supplied context / policy")
            st.write(task["context"])
            st.markdown("#### AI response to annotate")
            st.write(task["model_response"])
            with st.expander("Reference behavior (for calibration; avoid using as a shortcut)"):
                st.write(task["expected_behavior"])
        with right:
            st.markdown("#### Apply the SOP")
            st.caption("Pass = no material issue · Minor = limited issue · Major = material defect · N/A = not assessable")
            with st.form("ops_annotation_form",clear_on_submit=True):
                annotator=st.text_input("Annotator ID",value="reviewer-01")
                relevance=st.selectbox("Relevance",["pass","minor_issue","major_issue","not_applicable"])
                correctness=st.selectbox("Correctness",["pass","minor_issue","major_issue","not_applicable"])
                completeness=st.selectbox("Completeness",["pass","minor_issue","major_issue","not_applicable"])
                overall=st.selectbox("Overall decision",["accept","revise","reject","escalate"])
                defect=st.selectbox("Primary defect category",["none","irrelevant","unsupported_claim","incorrect_policy","missing_next_step","privacy_or_safety","unclear_or_confusing","other"])
                evidence=st.text_area("Evidence for decision (required)",placeholder="Quote the response and connect it to the supplied context…")
                confidence=st.slider("Confidence",1,5,3)
                handling=st.number_input("Handling time (seconds)",min_value=0,max_value=86400,value=60,step=5)
                escalated=st.checkbox("Escalated for specialist/policy review")
                audit=st.checkbox("This is an audit/re-review")
                submit=st.form_submit_button("Submit annotation",type="primary")
            if submit:
                payload={"task_id":task_id,"annotator_id":annotator,"sop_id":sop["sop_id"],"relevance":relevance,"correctness":correctness,"completeness":completeness,"overall_label":overall,"evidence":evidence,"defect_category":defect,"confidence":confidence,"handling_seconds":int(handling),"escalated":escalated,"is_audit":audit}
                try:
                    result=api_post("/ops/annotations",payload,timeout=30)
                    st.success("Annotation saved with SOP version reference.")
                    st.rerun()
                except requests.RequestException as e: st.error(f"Could not submit annotation: {e}")
    st.markdown("### Annotation ledger")
    ledger=api_get("/ops/annotations") or []
    if ledger:
        ledger_df=pd.DataFrame(ledger)
        st.dataframe(ledger_df,use_container_width=True,hide_index=True)
        st.download_button("Export auditable annotation ledger",ledger_df.to_csv(index=False),"annotation_ledger.csv","text/csv")
    else: st.info("No annotations submitted yet.")
    st.markdown("### Audit trail")
    audit_rows=api_get("/ops/audit") or []
    if audit_rows: st.dataframe(pd.DataFrame(audit_rows),use_container_width=True,hide_index=True)
    else: st.caption("Submission events will appear here after the first annotation.")

else:
    st.subheader("Evaluation dataset")
    st.markdown("<div class='subtle'>Curated benchmark cases used for repeatable model evaluation.</div>",unsafe_allow_html=True)
    data=api_get("/benchmark")
    if data:
        df=pd.DataFrame(data.get("cases",[]))
        a,b=st.columns([1,3]); a.metric("Total test cases",data.get("count",len(df)))
        if not df.empty:
            categories=sorted(df.category.dropna().unique())
            chosen=st.multiselect("Filter categories",categories,default=categories)
            view=df[df.category.isin(chosen)]
            st.dataframe(view,use_container_width=True,hide_index=True)
            st.download_button("Export test cases",view.to_csv(index=False),"benchmark_cases.csv","text/csv")
