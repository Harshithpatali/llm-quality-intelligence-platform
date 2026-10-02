import os
import time
import requests
import pandas as pd
import json
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="LLM Quality Intelligence", page_icon="◈", layout="wide")

API = st.secrets.get("API_URL", os.getenv("API_URL", "http://localhost:8000")).rstrip("/")

# ─────────────────────────────────────────────────────────────────────────────
#  Enhanced visual system: gradients, animations, glass cards, hover effects
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root {
  --ink:#172033; --muted:#6b7280; --line:#e5e9f0; --blue:#3978e8;
  --purple:#8b5cf6; --pink:#ec4899; --teal:#14b8a6; --amber:#f59e0b;
  --green:#10b981; --red:#ef4444; --slate:#64748b;
}

/* ---------- Keyframes ---------- */
@keyframes fadeIn { from{opacity:0} to{opacity:1} }
@keyframes fadeInUp { from{opacity:0; transform:translateY(18px)} to{opacity:1; transform:translateY(0)} }
@keyframes slideInLeft { from{opacity:0; transform:translateX(-18px)} to{opacity:1; transform:translateX(0)} }
@keyframes gradientShift { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
@keyframes pulseDot { 0%,100%{opacity:1; transform:scale(1)} 50%{opacity:.55; transform:scale(1.35)} }
@keyframes shimmer { 0%{background-position:-800px 0} 100%{background-position:800px 0} }
@keyframes floaty { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
@keyframes barFill { from{width:0%} to{width:var(--w)} }

/* ---------- Layout ---------- */
.block-container { padding-top:1.5rem; padding-bottom:3rem; max-width:1500px;
  animation: fadeIn .6s ease-out; }

h1,h2,h3 { letter-spacing:-.035em; color:#172033; animation: fadeInUp .5s ease-out both; }

h1 {
  font-weight: 800 !important;
  background: linear-gradient(120deg,#172033 0%, #3978e8 45%, #8b5cf6 75%, #ec4899 100%);
  background-size: 220% 220%;
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: gradientShift 9s ease infinite, fadeInUp .5s ease-out both;
}
h2, h3 { font-weight: 700 !important; }

/* ---------- Metric cards (Streamlit native, restyled) ---------- */
[data-testid="stMetric"] {
  background: linear-gradient(160deg,#ffffff 0%, #f8faff 100%);
  border:1px solid #e5e9f0;
  border-radius:14px;
  padding:16px 18px;
  box-shadow: 0 1px 2px rgba(23,32,51,.03), 0 8px 24px -18px rgba(57,120,232,.35);
  position: relative; overflow: hidden;
  transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
  animation: fadeInUp .5s ease-out both;
}
[data-testid="stMetric"]::before {
  content:""; position:absolute; inset:0 0 auto 0; height:3px;
  background: linear-gradient(90deg, var(--blue), var(--purple), var(--pink));
  opacity:.9;
}
[data-testid="stMetric"]:hover {
  transform: translateY(-3px);
  border-color:#cdd9ee;
  box-shadow: 0 12px 32px -18px rgba(57,120,232,.55);
}
[data-testid="stMetricLabel"] { color:#697386; font-size:.82rem; font-weight:600; letter-spacing:.02em; }
[data-testid="stMetricValue"] { color:#172033; font-weight:800; }
[data-testid="stMetricDelta"] { font-size:.78rem; }

/* ---------- Tabs ---------- */
div[data-testid="stTabs"] button { font-weight:600; transition: color .2s ease; }
div[data-testid="stTabs"] button:hover { color: var(--blue); }
div[data-testid="stTabs"] button[aria-selected="true"] {
  color: var(--blue) !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
  background: linear-gradient(90deg, var(--blue), var(--purple)) !important;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg,#f7f8fb 0%, #eef2fb 100%);
  border-right:1px solid #e8ebf1;
  animation: slideInLeft .45s ease-out both;
}
section[data-testid="stSidebar"] h2 {
  background: linear-gradient(120deg, #172033, #3978e8);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* ---------- Panels & pills ---------- */
.panel {
  background: linear-gradient(160deg,#ffffff, #fafbff);
  border:1px solid #e5e9f0;
  border-radius:14px; padding:18px 20px; margin-bottom:12px;
  box-shadow: 0 1px 2px rgba(23,32,51,.03), 0 10px 24px -22px rgba(23,32,51,.25);
  transition: transform .25s ease, box-shadow .25s ease;
  animation: fadeInUp .5s ease-out both;
}
.panel:hover { transform: translateY(-2px); box-shadow: 0 14px 32px -22px rgba(23,32,51,.4); }

.eyebrow {
  font-size:.76rem; text-transform:uppercase; letter-spacing:.14em;
  background: linear-gradient(90deg, var(--blue), var(--purple));
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight:800;
  animation: fadeIn .6s ease-out both;
}
.subtle { color:#788294; font-size:.9rem; }

.model-pill {
  display:inline-block;border:1px solid #e5e9f0;border-radius:999px;
  padding:7px 12px;margin:3px 5px 3px 0;font-size:.83rem;
  background: linear-gradient(160deg,#ffffff,#f6f9ff);
  box-shadow: 0 1px 2px rgba(23,32,51,.03);
  transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
  animation: fadeInUp .45s ease-out both;
}
.model-pill:hover {
  transform: translateY(-2px) scale(1.02);
  border-color:#cdd9ee;
  box-shadow: 0 6px 18px -12px rgba(57,120,232,.6);
}
.dot {
  display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;
  animation: pulseDot 2.4s ease-in-out infinite;
  box-shadow: 0 0 0 3px rgba(57,120,232,.08);
}

/* ---------- Step cards ---------- */
.step {
  border:1px solid #dfe5ee;border-radius:12px;padding:15px;background:#fff;
  min-height:116px; position:relative; overflow:hidden;
  transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
  animation: fadeInUp .5s ease-out both;
}
.step:hover { transform: translateY(-3px); box-shadow: 0 14px 28px -20px rgba(23,32,51,.4); }
.step.active {
  border:2px solid transparent;
  background: linear-gradient(#f5f8ff,#eef4ff) padding-box,
              linear-gradient(120deg, var(--blue), var(--purple), var(--pink)) border-box;
  animation: fadeInUp .5s ease-out both, floaty 4s ease-in-out infinite;
}
.step.active::after {
  content:""; position:absolute; right:-30px; top:-30px; width:110px; height:110px; border-radius:50%;
  background: radial-gradient(circle at 30% 30%, rgba(57,120,232,.18), transparent 70%);
  pointer-events:none;
}

/* ---------- Buttons ---------- */
div.stButton>button[kind="primary"] {
  border-radius:10px;
  background: linear-gradient(120deg, var(--blue), var(--purple));
  border: 0;
  box-shadow: 0 8px 20px -12px rgba(57,120,232,.9);
  transition: transform .2s ease, box-shadow .2s ease, filter .2s ease;
  font-weight: 700;
}
div.stButton>button[kind="primary"]:hover {
  transform: translateY(-1px);
  filter: brightness(1.05);
  box-shadow: 0 12px 26px -12px rgba(57,120,232,1);
}
div.stButton>button { transition: transform .15s ease, box-shadow .15s ease; }
div.stButton>button:hover { transform: translateY(-1px); }

/* ---------- Dataframe / expander polish ---------- */
[data-testid="stDataFrame"], [data-testid="stTable"] {
  border-radius:12px; overflow:hidden; border:1px solid #e5e9f0;
  animation: fadeInUp .45s ease-out both;
}
details[data-testid="stExpander"] {
  border-radius:12px; border:1px solid #e5e9f0; overflow:hidden;
  transition: box-shadow .25s ease, border-color .25s ease;
  animation: fadeInUp .45s ease-out both;
}
details[data-testid="stExpander"]:hover {
  border-color:#cdd9ee;
  box-shadow: 0 12px 30px -24px rgba(57,120,232,.7);
}

/* ---------- Custom score widgets ---------- */
.score-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; margin:6px 0 14px; }
.score-tile {
  position:relative; border:1px solid #e5e9f0; border-radius:14px; padding:14px 16px;
  background: linear-gradient(160deg,#fff,#f8faff);
  overflow:hidden; animation: fadeInUp .5s ease-out both;
  transition: transform .2s ease, box-shadow .2s ease;
}
.score-tile:hover { transform: translateY(-2px); box-shadow: 0 14px 30px -22px rgba(23,32,51,.5); }
.score-tile .lbl { font-size:.72rem; text-transform:uppercase; letter-spacing:.09em; color:#778196; font-weight:800; }
.score-tile .val { font-size:1.55rem; font-weight:800; color:#172033; margin-top:4px; }
.score-tile .bar { height:6px; border-radius:999px; background:#eef2f8; margin-top:10px; overflow:hidden; }
.score-tile .fill { height:100%; border-radius:999px; animation: barFill 1s cubic-bezier(.2,.7,.2,1) both; }
.score-tile .hint { font-size:.78rem; color:#788294; margin-top:6px; }

.badge {
  display:inline-block; padding:3px 9px; border-radius:999px; font-size:.72rem;
  font-weight:800; letter-spacing:.04em;
}
.badge.ok   { background:#e8f7ef; color:#0f7a4f; }
.badge.warn { background:#fff4e0; color:#a56200; }
.badge.bad  { background:#fdecec; color:#b42318; }
.badge.neutral { background:#eef2fb; color:#31406a; }

.hero-strip {
  height:4px; border-radius:999px; margin:6px 0 18px;
  background: linear-gradient(90deg, var(--blue), var(--purple), var(--pink), var(--amber), var(--teal));
  background-size: 300% 100%;
  animation: gradientShift 12s linear infinite;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────
def headers():
    token = st.secrets.get("API_ACCESS_TOKEN", os.getenv("API_ACCESS_TOKEN", "")).strip()
    return {"X-API-Key": token} if token else {}

def api_get(path, params=None):
    try:
        r = requests.get(API+path, headers=headers(), params=params, timeout=25)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        st.error(f"API request failed: {e}")
        return None

def api_post(path, payload, timeout=1800):
    try:
        r = requests.post(API+path, headers=headers(), json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        detail = r.text[:2000] if r is not None else str(e)
        raise requests.HTTPError(f"{e} | Response: {detail}", response=r) from e

def _display_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    if value is None:
        return "—"
    return str(value)

def clean_display_df(frame):
    df = frame.copy()
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].map(_display_value)
    return df

def frame_results(results):
    df = pd.DataFrame(results or [])
    if df.empty:
        return df

    evaluations = df.get(
        "evaluation",
        pd.Series([None] * len(df), index=df.index, dtype="object"),
    )
    rubric_evaluations = df.get(
        "rubric_evaluation",
        pd.Series([None] * len(df), index=df.index, dtype="object"),
    )

    df["heuristic_score"] = evaluations.apply(
        lambda x: x.get("heuristic_score") if isinstance(x, dict) else None
    )
    df["keyword_coverage"] = evaluations.apply(
        lambda x: 100 * x.get("keyword_coverage", 0) if isinstance(x, dict) else None
    )
    df["rubric_score"] = rubric_evaluations.apply(
        lambda x: x.get("overall_score") if isinstance(x, dict) else None
    )
    df["rubric_decision"] = rubric_evaluations.apply(
        lambda x: x.get("decision") if isinstance(x, dict) else None
    )
    return df

def model_name(row):
    return f'{row.get("provider","")} / {row.get("model","")}'


# ── Visual helpers ───────────────────────────────────────────────────────────
PALETTE = ["#3978e8", "#8b5cf6", "#ec4899", "#f59e0b", "#14b8a6",
           "#10b981", "#ef4444", "#0ea5e9", "#6366f1", "#84cc16"]

def _hex_to_rgba(hex_color, alpha=1.0):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def style_plotly(fig, height=340, showlegend=True):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color="#172033", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)") if showlegend else dict(),
        showlegend=showlegend,
        hoverlabel=dict(bgcolor="white", bordercolor="#e5e9f0",
                        font=dict(color="#172033", size=12)),
    )
    fig.update_xaxes(gridcolor="#eef2f7", linecolor="#e5e9f0", zerolinecolor="#e5e9f0", automargin=True)
    fig.update_yaxes(gridcolor="#eef2f7", linecolor="#e5e9f0", zerolinecolor="#e5e9f0", automargin=True)
    return fig

def gauge_score(value, title="Overall", height=260, color=None):
    v = float(value) if value is not None else 0.0
    if color is None:
        color = "#10b981" if v >= 80 else "#f59e0b" if v >= 60 else "#ef4444"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=v,
        number=dict(suffix="/100", font=dict(size=26, color="#172033")),
        title=dict(text=title, font=dict(size=12, color="#697386")),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=1, tickcolor="#cbd5e1",
                      tickfont=dict(size=10, color="#94a3b8")),
            bar=dict(color=color, thickness=0.72),
            bgcolor="#f3f6fb",
            borderwidth=0,
            steps=[
                dict(range=[0, 60], color="#fdecec"),
                dict(range=[60, 80], color="#fff4e0"),
                dict(range=[80, 100], color="#e8f7ef"),
            ],
            threshold=dict(line=dict(color="#172033", width=2), thickness=0.85, value=80),
        ),
    ))
    fig.update_layout(height=height, margin=dict(l=14, r=14, t=30, b=6),
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif"))
    return fig

def radar_dimensions(dims, title="Dimension profile", height=340):
    if not dims:
        return None
    names = list(dims.keys())
    vals = []
    for n in names:
        e = dims.get(n)
        s = e.get("score") if isinstance(e, dict) else None
        vals.append(float(s) if s is not None else 0.0)
    names_c = names + [names[0]]
    vals_c = vals + [vals[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_c, theta=names_c, fill="toself", name=title,
        line=dict(color="#3978e8", width=2),
        fillcolor=_hex_to_rgba("#3978e8", 0.22),
    ))
    max_v = max(vals) if vals else 10
    top = 100 if max_v > 10 else (10 if max_v > 5 else 5)
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, top], gridcolor="#e9eef6",
                            tickfont=dict(size=10, color="#94a3b8")),
            angularaxis=dict(gridcolor="#e9eef6", tickfont=dict(size=11, color="#41506b")),
        ),
        showlegend=False, height=height,
        margin=dict(l=30, r=30, t=30, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig

def gradient_bar(df, x, y, color_by=None, title=None, height=340, horizontal=False, value_fmt=".1f"):
    if df.empty:
        return None
    if color_by is None:
        color_by = y
    fig = px.bar(df, x=y if not horizontal else x,
                 y=x if not horizontal else y,
                 color=color_by,
                 color_discrete_sequence=PALETTE,
                 orientation="h" if horizontal else "v",
                 text=df[y].round(1) if value_fmt else None)
    if horizontal:
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_xaxes(showgrid=True)
    else:
        fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_traces(marker_line_width=0)
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=13, color="#41506b"), x=0.01))
    return style_plotly(fig, height=height, showlegend=bool(color_by and color_by != y))

def dimension_bars(dims, height=None):
    if not dims:
        return None
    rows = []
    for name, entry in dims.items():
        if not isinstance(entry, dict):
            continue
        rows.append({"dimension": name, "score": entry.get("score") or 0})
    if not rows:
        return None
    d = pd.DataFrame(rows)
    h = height or max(200, 40 + 32*len(d))
    fig = px.bar(d, x="score", y="dimension", orientation="h",
                 color="score", color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
                 text=d["score"].round(1))
    fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
    fig.update_layout(coloraxis_showscale=False)
    fig.update_xaxes(range=[0, max(10, d["score"].max()*1.15 if len(d) else 10)])
    return style_plotly(fig, height=h, showlegend=False)

def score_tile(label, value, maxv=100, accent="#3978e8", hint=None):
    try:
        v = float(value)
        pct = max(0, min(100, (v / maxv) * 100))
        shown = f"{v:g}"
    except Exception:
        pct = 0
        shown = "—"
    hint_html = f"<div class='hint'>{hint}</div>" if hint else ""
    # Return a single-line HTML string without indentation to prevent Streamlit markdown code-block rendering
    return "".join([
        f"<div class='score-tile'>",
        f"<div class='lbl'>{label}</div>",
        f"<div class='val'>{shown}</div>",
        f"<div class='bar'><div class='fill' style='--w:{pct}%; width:{pct}%; background:linear-gradient(90deg,{accent},{_hex_to_rgba(accent,0.55)})'></div></div>",
        hint_html,
        f"</div>"
    ])

def badge(text, kind="neutral"):
    return f"<span class='badge {kind}'>{text}</span>"


# ─────────────────────────────────────────────────────────────────────────────
#  Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='eyebrow'>MODEL QUALITY OPERATIONS</div>", unsafe_allow_html=True)
st.title("Evaluation workspace")
st.markdown("<div class='hero-strip'></div>", unsafe_allow_html=True)
st.markdown("<div class='subtle'>Compare model behavior, inspect response traces, and turn human feedback into repeatable evaluation data.</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ◈ Quality Lab")
    st.caption("LLM evaluation · review · analytics")
    page = st.radio(
        "WORKSPACE",
        ["Annotation operations", "Review queue", "Rubric studio", "Calibration", "Catalog response lab",
         "Catalog grounding", "Overview", "Compare evaluations", "Run evaluation", "Human review", "Test cases"],
        label_visibility="visible",
    )
    st.divider()
    st.markdown("**Run configuration**")
    providers = st.multiselect("Providers", ["groq", "openrouter"], default=["groq", "openrouter"])
    limit = st.slider("Cases per run", 1, 60, 20)
    st.caption("Provider and database credentials stay on the API service.")
    st.divider()
    health = api_get("/health")
    if health:
        st.success("API connected")
    else:
        st.warning("API unavailable")


runs = api_get("/runs")
runs = runs or []
run_options = [x.get("run_id") for x in runs if x.get("run_id")]


# ─────────────────────────────────────────────────────────────────────────────
#  Catalog response lab
# ─────────────────────────────────────────────────────────────────────────────
if page == "Catalog response lab":
    st.subheader("Catalog-grounded response evaluation")
    st.caption(
        "Search the supplied item-list metadata, ask a product question, run the same grounded prompt across the configured models, "
        "then score each response with the selected rubric. The catalog file is project-supplied metadata, not Amazon internal support data."
    )

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        q = st.text_input("Search product", placeholder="e.g. wireless, drawer slides, phone case…", key="catalog_eval_q")
    with c2:
        product_type = st.text_input("Product type", placeholder="optional", key="catalog_eval_type")
    with c3:
        domain_name = st.text_input("Marketplace", placeholder="optional", key="catalog_eval_domain")

    catalog = api_get("/ops/products", params={
        "q": q.strip() or None,
        "product_type": product_type.strip() or None,
        "domain_name": domain_name.strip() or None,
        "limit": 50,
    }) or []

    if not catalog:
        st.info("No catalog records matched the search.")
    else:
        selected = st.selectbox(
            "Select product",
            range(len(catalog)),
            format_func=lambda i: f'{catalog[i]["item_id"]} · {catalog[i].get("item_name") or "Unnamed item"} · {catalog[i].get("domain_name")}',
            key="catalog_eval_product",
        )
        item = catalog[selected]

        left, right = st.columns([1, 1])
        with left:
            st.markdown("#### Product grounding context")
            metadata = [
                {"Field": k.replace("_", " ").title(), "Value": item.get(k)}
                for k in [
                    "item_id", "domain_name", "item_name", "brand", "color",
                    "product_type", "style", "material", "model_number", "country"
                ]
                if item.get(k) not in (None, "")
            ]
            st.dataframe(
                clean_display_df(pd.DataFrame(metadata)),
                use_container_width=True,
                hide_index=True,
            )
        with right:
            st.markdown("#### Catalog bullet points")
            bullets = item.get("bullet_points") or []
            if bullets:
                for bullet in bullets:
                    st.write(f"• {bullet}")
            else:
                st.caption("No bullet points supplied.")

        st.markdown("#### User question")
        user_query = st.text_area(
            "Ask a product question that a seller/customer-support assistant should answer",
            placeholder="Example: Does this product specify a material and color?",
            height=100,
            key="catalog_eval_query",
        )

        rubric_rows = api_get("/rubrics", params={"rubric_name": "Catalog Response Quality"}) or []
        active_rubrics = [r for r in rubric_rows if r.get("status") == "active"]
        rubric_options = ["built_in_demo"] + [r["rubric_id"] for r in active_rubrics]
        selected_rubric = st.selectbox(
            "Rubric",
            rubric_options,
            format_func=lambda rid: (
                "Built-in Catalog Response Quality v1"
                if rid == "built_in_demo"
                else next(
                    (f'{r.get("rubric_name")} · v{r.get("version")} · active' for r in active_rubrics if r.get("rubric_id") == rid),
                    rid,
                )
            ),
            key="catalog_eval_rubric",
        )

        st.markdown(
            "<div class='panel'><b>Evaluation flow</b><br>"
            "1. Retrieve product metadata → 2. Generate the same grounded answer with each configured model → "
            "3. Judge every response against safety, relevance, correctness/grounding, completeness, policy/instruction following, and clarity → "
            "4. Persist the trace and rubric result as an evaluation run.</div>",
            unsafe_allow_html=True,
        )

        run_button = st.button(
            "▶ Generate and score responses",
            type="primary",
            disabled=(not user_query.strip()),
            key="catalog_eval_run",
        )
        if run_button:
            payload = {
                "item_id": item["item_id"],
                "domain_name": item["domain_name"],
                "user_query": user_query.strip(),
                "providers": providers,
            }
            if selected_rubric != "built_in_demo":
                payload["rubric_id"] = selected_rubric

            with st.spinner("Running the configured generation models and rubric judge…"):
                try:
                    data = api_post("/catalog/evaluate", payload, timeout=1800)
                    st.success(
                        f'Catalog evaluation completed · {data.get("successful_responses",0)} successful model responses '
                        f'of {data.get("models_requested",0)} configured model calls.'
                    )

                    results = data.get("results", [])
                    good = [r for r in results if r.get("status") == "success" and isinstance(r.get("rubric_evaluation"), dict)]

                    # ── Scoreboard: tiles + gauges ───────────────────────────
                    if good:
                        st.markdown("### Rubric scorecard")
                        # Overview tiles
                        tiles = []
                        overalls = [g["rubric_evaluation"].get("overall_score") for g in good]
                        critical = sum(1 for g in good if g["rubric_evaluation"].get("critical_failure"))
                        decisions = [str(g["rubric_evaluation"].get("decision", "—")).upper() for g in good]
                        avg = sum(o for o in overalls if isinstance(o, (int, float))) / max(1, sum(1 for o in overalls if isinstance(o, (int, float))))
                        tiles.append(score_tile("Mean overall", f"{avg:.1f}", maxv=100,
                                                accent="#3978e8", hint=f"{len(good)} responses judged"))
                        tiles.append(score_tile("Critical failures", critical, maxv=max(1, len(good)),
                                                accent="#ef4444" if critical else "#10b981",
                                                hint="Safety / policy blockers"))
                        accept = sum(1 for d in decisions if d in ("ACCEPT", "PASS", "APPROVE"))
                        tiles.append(score_tile("Accepted decisions", accept, maxv=max(1, len(good)),
                                                accent="#10b981", hint=f"{accept}/{len(good)} models"))
                        
                        # Fix: join tiles and ensure no newlines exist to prevent markdown code-block rendering
                        grid_html = "".join(tiles).replace("\n", "")
                        st.markdown(f"<div class='score-grid'>{grid_html}</div>", unsafe_allow_html=True)

                        # Per-model gauges
                        gauge_cols = st.columns(min(len(good), 4))
                        for i, r in enumerate(good[:4]):
                            ev = r["rubric_evaluation"]
                            with gauge_cols[i]:
                                st.plotly_chart(
                                    gauge_score(ev.get("overall_score"),
                                                title=f'{r.get("provider")} · {r.get("model")}'),
                                    use_container_width=True,
                                    config={"displayModeBar": False},
                                )

                        # Dataframe view (kept as before)
                        rows = []
                        for r in good:
                            ev = r["rubric_evaluation"]
                            row = {
                                "provider": r.get("provider"),
                                "model": r.get("model"),
                                "decision": ev.get("decision"),
                                "overall_score": ev.get("overall_score"),
                                "critical_failure": ev.get("critical_failure"),
                            }
                            for name, entry in (ev.get("dimensions") or {}).items():
                                row[name] = entry.get("score") if isinstance(entry, dict) else None
                            rows.append(row)
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                    st.markdown("### Model responses and evidence")
                    for idx, r in enumerate(results):
                        label = f'{r.get("provider")} · {r.get("model")}'
                        with st.expander(label, expanded=(idx == 0)):
                            if r.get("status") != "success":
                                st.error(r.get("error", "Model call failed."))
                                continue

                            st.markdown("**Model response**")
                            st.markdown(f"<div class='panel'>{r.get('response','')}</div>", unsafe_allow_html=True)

                            ev = r.get("rubric_evaluation")
                            if not isinstance(ev, dict):
                                st.warning("Rubric scoring failed for this response.")
                                continue
                            m1, m2, m3, m4 = st.columns(4)
                            m1.metric("Overall", f'{ev.get("overall_score","—")}/100')
                            m2.metric("Decision", str(ev.get("decision", "—")).upper())
                            m3.metric("Critical failure", "Yes" if ev.get("critical_failure") else "No")
                            m4.metric("Judge", f'{ev.get("judge_provider","")} / {ev.get("judge_model","")}')

                            st.markdown("**Dimension scores**")
                            dims = ev.get("dimensions") or {}

                            # Bar chart + radar side by side
                            viz_l, viz_r = st.columns([1.15, 1])
                            with viz_l:
                                dbar = dimension_bars(dims)
                                if dbar is not None:
                                    st.plotly_chart(dbar, use_container_width=True, config={"displayModeBar": False})
                            with viz_r:
                                rdr = radar_dimensions(dims)
                                if rdr is not None:
                                    st.plotly_chart(rdr, use_container_width=True, config={"displayModeBar": False})

                            dim_df = pd.DataFrame([
                                {
                                    "dimension": name,
                                    "score": entry.get("score"),
                                    "rationale": entry.get("rationale", ""),
                                }
                                for name, entry in dims.items()
                                if isinstance(entry, dict)
                            ])
                            if not dim_df.empty:
                                st.dataframe(dim_df, use_container_width=True, hide_index=True)

                            evidence = ev.get("evidence") or []
                            unsupported = ev.get("unsupported_claims") or []
                            if evidence:
                                st.markdown("**Evidence**")
                                for x in evidence:
                                    st.write(f"• {x}")
                            if unsupported:
                                st.markdown("**Unsupported claims detected**")
                                for x in unsupported:
                                    st.write(f"• {x}")
                            if ev.get("recommended_action"):
                                st.info(ev["recommended_action"])

                    st.caption(
                        "Rubric judgments are model-generated evaluation signals. They are not expert-validated ground truth; "
                        "human annotation remains the final review layer."
                    )
                except requests.RequestException as e:
                    st.error(f"Catalog evaluation failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Catalog grounding
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Catalog grounding":
    st.subheader("Catalog grounding")
    st.caption("Browse the uploaded Amazon item-list metadata used as product/catalog grounding data for this portfolio project. This is catalog metadata, not Amazon internal customer or support data.")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        q = st.text_input("Product name search", placeholder="Search product names…")
    with c2:
        product_type = st.text_input("Product type", placeholder="e.g. CELLULAR_PHONE_CASE")
    with c3:
        domain_name = st.text_input("Marketplace", placeholder="e.g. amazon.in")
    catalog = api_get("/ops/products", params={
        "q": q.strip() or None,
        "product_type": product_type.strip() or None,
        "domain_name": domain_name.strip() or None,
        "limit": 100,
    }) or []
    st.metric("Rows returned", len(catalog))
    if catalog:
        df = pd.DataFrame(catalog)
        display_cols = [c for c in ["item_id", "domain_name", "item_name", "brand", "product_type", "color", "material", "model_number", "country", "num_bullets"] if c in df.columns]

        # Small visual: bullet count distribution
        if "num_bullets" in df.columns and df["num_bullets"].notna().any():
            bc = df["num_bullets"].dropna().astype(int).value_counts().sort_index().reset_index()
            bc.columns = ["num_bullets", "count"]
            fig = px.bar(bc, x="num_bullets", y="count", color="count",
                         color_continuous_scale=["#cdd9ee", "#3978e8", "#8b5cf6"],
                         text="count")
            fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
            fig.update_layout(coloraxis_showscale=False,
                              title=dict(text="Bullet-point coverage across returned rows",
                                         font=dict(size=13, color="#41506b"), x=0.01))
            style_plotly(fig, height=260, showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
        selected_id = st.selectbox("Inspect item", range(len(catalog)), format_func=lambda i: f'{catalog[i]["item_id"]} · {catalog[i].get("brand") or "—"}')
        item = catalog[selected_id]
        left, right = st.columns([1, 1])
        with left:
            st.markdown("#### Product metadata")
            metadata = [
                {"Field": k.replace("_", " ").title(), "Value": item.get(k)}
                for k in ["item_id", "domain_name", "item_name", "brand", "color",
                          "product_type", "style", "material", "model_number", "country", "num_bullets"]
                if item.get(k) not in (None, "")
            ]
            st.dataframe(
                clean_display_df(pd.DataFrame(metadata)),
                use_container_width=True,
                hide_index=True,
            )
        with right:
            st.markdown("#### Bullet points")
            bullets = item.get("bullet_points") or []
            if bullets:
                for b in bullets:
                    st.write(f"• {b}")
            else:
                st.caption("No bullet points supplied.")
    else:
        st.info("No catalog records matched the current filters.")


# ─────────────────────────────────────────────────────────────────────────────
#  Overview
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Overview":
    st.subheader("Quality overview")
    if not runs:
        st.info("No evaluation runs yet. Start an evaluation to populate the workspace.")
    else:
        chosen = st.selectbox("Evaluation run", run_options, format_func=lambda x: next((f'{r.get("created_at","")[:19]} · {r.get("run_id","")[:8]}' for r in runs if r.get("run_id") == x), x))
        detail = api_get("/runs/" + chosen)
        df = frame_results(detail.get("results", []) if detail else [])
        if not df.empty:
            ok = df[df["status"] == "success"]
            scores = ok["heuristic_score"].dropna()
            models = ok.groupby(["provider", "model"], dropna=False)
            a, b, c, d = st.columns(4)
            a.metric("Responses evaluated", len(df))
            b.metric("Successful", len(ok))
            c.metric("Mean diagnostic score", f"{scores.mean():.1f}/100" if len(scores) else "—")
            d.metric("Errors", int((df.status == "error").sum()))

            st.markdown("### Model comparison")
            cols = st.columns([1.5, 1, 1])
            with cols[0]:
                st.markdown("<div class='panel'><div class='eyebrow'>Models in this run</div>", unsafe_allow_html=True)
                for i, ((provider, model), g) in enumerate(models):
                    st.markdown(f"<span class='model-pill'><span class='dot' style='background:{PALETTE[i%len(PALETTE)]}'></span>{provider} · {model}</span>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                st.caption("Diagnostic score is reference-term overlap plus a response-length heuristic; it is not a correctness or safety verdict.")

            with cols[1]:
                st.markdown("**Average diagnostic score**")
                if not ok.empty:
                    agg = ok.groupby("model")["heuristic_score"].mean().reset_index()
                    fig = px.bar(agg, x="model", y="heuristic_score",
                                 color="heuristic_score",
                                 color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
                                 text=agg["heuristic_score"].round(1))
                    fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
                    fig.update_layout(coloraxis_showscale=False)
                    style_plotly(fig, height=300, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            with cols[2]:
                st.markdown("**Average latency (ms)**")
                if not ok.empty and "latency_ms" in ok:
                    agg = ok.groupby("model")["latency_ms"].mean().reset_index()
                    fig = px.bar(agg, x="model", y="latency_ms",
                                 color="latency_ms",
                                 color_continuous_scale=["#cdd9ee", "#3978e8", "#8b5cf6"],
                                 text=agg["latency_ms"].round(0))
                    fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
                    fig.update_layout(coloraxis_showscale=False)
                    style_plotly(fig, height=300, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            st.markdown("### Scorecard")
            summary = ok.groupby(["provider", "model"], dropna=False).agg(
                Responses=("case_id", "count"),
                Mean_score=("heuristic_score", "mean"),
                Keyword_coverage=("keyword_coverage", "mean"),
                Mean_latency_ms=("latency_ms", "mean")
            ).reset_index()
            if not summary.empty:
                summary["Mean_score"] = summary["Mean_score"].round(1)
                summary["Keyword_coverage"] = summary["Keyword_coverage"].round(1)
                summary["Mean_latency_ms"] = summary["Mean_latency_ms"].round(0)
                st.dataframe(summary, use_container_width=True, hide_index=True)
            with st.expander("Inspect evaluation responses"):
                st.dataframe(df[["case_id", "category", "provider", "model", "status", "latency_ms", "heuristic_score", "keyword_coverage"]], use_container_width=True, hide_index=True)
                st.download_button("Export evaluation CSV", df.to_csv(index=False), "evaluation_results.csv", "text/csv")
        else:
            st.info("This run has no response records.")


# ─────────────────────────────────────────────────────────────────────────────
#  Compare evaluations
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Compare evaluations":
    st.subheader("Compare evaluations")
    if len(run_options) < 1:
        st.info("Run an evaluation first.")
    else:
        selected = st.multiselect(
            "Choose evaluations to compare",
            run_options,
            default=run_options[:min(2, len(run_options))],
            format_func=lambda x: next((f'{r.get("created_at","")[:16]} · {x[:8]}' for r in runs if r.get("run_id") == x), x),
        )
        records = []
        for rid in selected:
            detail = api_get("/runs/" + rid)
            if detail:
                z = frame_results(detail.get("results", []))
                z["evaluation_id"] = rid[:8]
                records.append(z)
        if records:
            all_df = pd.concat(records, ignore_index=True)
            good = all_df[all_df.status == "success"]
            st.markdown("### Summary metrics")
            m1, m2, m3 = st.columns(3)
            m1.metric("Evaluations selected", len(selected))
            m2.metric("Successful responses", len(good))
            m3.metric("Mean diagnostic score", f'{good.heuristic_score.mean():.1f}/100' if not good.empty else "—")

            st.markdown("### Model score comparison")
            if not good.empty:
                pivot = good.groupby(["evaluation_id", "model"])["heuristic_score"].mean().unstack(0).reset_index()
                melted = pivot.melt(id_vars="model", var_name="evaluation_id", value_name="score")
                fig = px.bar(melted, x="model", y="score", color="evaluation_id",
                             barmode="group", color_discrete_sequence=PALETTE,
                             text=melted["score"].round(1))
                fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
                style_plotly(fig, height=360)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                st.markdown("### Latency comparison")
                pivot_l = good.groupby(["evaluation_id", "model"])["latency_ms"].mean().unstack(0).reset_index()
                melted_l = pivot_l.melt(id_vars="model", var_name="evaluation_id", value_name="latency_ms")
                fig2 = px.bar(melted_l, x="model", y="latency_ms", color="evaluation_id",
                              barmode="group", color_discrete_sequence=PALETTE,
                              text=melted_l["latency_ms"].round(0))
                fig2.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
                style_plotly(fig2, height=360)
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

                st.markdown("### Scorecard")
                st.dataframe(
                    good.groupby(["evaluation_id", "provider", "model"]).agg(
                        Responses=("case_id", "count"),
                        Mean_score=("heuristic_score", "mean"),
                        Keyword_coverage=("keyword_coverage", "mean"),
                        Mean_latency_ms=("latency_ms", "mean"),
                    ).reset_index().round(2),
                    use_container_width=True, hide_index=True,
                )
            st.caption("Comparisons are descriptive. Runs may differ in selected cases, provider availability, or model versions.")
        else:
            st.info("Select one or more runs to compare.")


# ─────────────────────────────────────────────────────────────────────────────
#  Run evaluation
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Run evaluation":
    st.subheader("Run a controlled evaluation")
    st.markdown("<div class='panel'>The same selected test cases are sent to each configured model. Provider usage may incur charges.</div>", unsafe_allow_html=True)
    if st.button("▶ Start evaluation", type="primary", disabled=not providers):
        with st.spinner("Evaluating selected models…"):
            try:
                data = api_post("/benchmark/run", {"providers": providers, "limit": limit})
                st.success(f'Run completed · {data["cases"]} cases × {data["models"]} models')
                df = frame_results(data.get("results", []))
                st.dataframe(df[["case_id", "provider", "model", "status", "latency_ms", "heuristic_score"]], use_container_width=True, hide_index=True)
                st.download_button("Download results", df.to_csv(index=False), "evaluation.csv", "text/csv")
            except requests.RequestException as e:
                st.error(f"Evaluation failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Calibration
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Calibration":
    st.subheader("Calibration reference")
    st.caption("Use this view only for reviewer calibration. Do not use the reference behavior as a shortcut during live annotation.")
    tasks = api_get("/ops/tasks") or []
    if not tasks:
        st.warning("No annotation tasks available.")
    else:
        task_ids = [t["task_id"] for t in tasks]
        task_id = st.selectbox(
            "Calibration task",
            task_ids,
            format_func=lambda x: next(
                (f'{t["task_id"]} · {t["category"]} · {t["difficulty"]}'
                 for t in tasks if t["task_id"] == x),
                x,
            ),
        )
        task = next(t for t in tasks if t["task_id"] == task_id)
        left, right = st.columns([1, 1])
        with left:
            st.markdown("#### Customer query")
            st.info(task["query"])
            st.markdown("#### Supplied context / policy")
            st.write(task["context"])
            st.markdown("#### AI response")
            st.write(task["model_response"])
        with right:
            st.markdown("#### Project calibration reference")
            st.success(task["expected_behavior"])
            st.caption("Synthetic project-created reference behavior; it is not externally validated ground truth or an Amazon policy.")


# ─────────────────────────────────────────────────────────────────────────────
#  Human review
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Human review":
    st.subheader("Human-in-the-loop review")
    st.markdown("<div class='subtle'>Inspect the full prompt and response, record a structured judgment, and preserve the reviewed example.</div>", unsafe_allow_html=True)
    st.markdown("#### Review workflow")
    x1, x2, x3 = st.columns(3)
    for col, title, desc, active in [
        (x1, "1 · Select trace", "Choose a production-like model response", False),
        (x2, "2 · Human review", "Inspect evidence and apply the rubric", True),
        (x3, "3 · Structured feedback", "Save labels and notes for analysis", False),
    ]:
        with col:
            st.markdown(f"<div class='step {'active' if active else ''}'><b>{title}</b><br><span class='subtle'>{desc}</span></div>", unsafe_allow_html=True)
    if runs:
        rid = st.selectbox("Evaluation run", run_options, key="review_run")
        detail = api_get("/runs/" + rid)
        candidates = [x for x in (detail or {}).get("results", []) if x.get("status") == "success"]
        if candidates:
            idx = st.selectbox("Response trace", range(len(candidates)), format_func=lambda i: f'{candidates[i]["case_id"]} · {candidates[i]["provider"]} · {candidates[i]["model"]}')
            item = candidates[idx]
            left, right = st.columns([1.1, 1])
            with left:
                st.markdown("**Prompt / user input**")
                st.markdown(f"<div class='panel'>{item.get('prompt','')}</div>", unsafe_allow_html=True)
                st.markdown("**Reference answer**")
                st.info(item.get("reference_answer", ""))
                st.markdown("**Model output**")
                st.markdown(f"<div class='panel'>{item.get('response','')}</div>", unsafe_allow_html=True)
            with right:
                st.markdown("**Trace metadata**")
                trace_meta = pd.DataFrame([
                    {"Field": k.replace("_", " ").title(), "Value": _display_value(item.get(k))}
                    for k in ["case_id", "category", "provider", "model", "latency_ms", "usage", "evaluation"]
                    if k in item
                ])
                st.dataframe(trace_meta, use_container_width=True, hide_index=True)
                with st.form("review_form"):
                    rating = st.slider("Overall quality", 1, 5, 3)
                    label = st.selectbox("Review label", ["excellent", "acceptable", "poor", "unsafe", "needs_review"])
                    reviewer = st.text_input("Reviewer", "Harshith")
                    notes = st.text_area("Evidence, failure mode, and suggested correction")
                    submit = st.form_submit_button("Save structured review", type="primary")
                if submit:
                    payload = {"run_id": rid, "case_id": item["case_id"], "provider": item["provider"], "model": item["model"], "rating": rating, "label": label, "notes": notes, "reviewer": reviewer}
                    try:
                        api_post("/annotations", payload, timeout=30)
                        st.success("Review saved.")
                    except requests.RequestException as e:
                        st.error(f"Could not save review: {e}")
        else:
            st.info("No successful responses in this run.")
    else:
        st.info("No runs are available to review.")
    annotations = api_get("/annotations")
    if annotations:
        st.markdown("### Review history")
        st.dataframe(clean_display_df(pd.DataFrame(annotations)), use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Annotation operations
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Annotation operations":
    st.subheader("Seller response annotation operations")
    st.caption("Project-created synthetic cases · human labels are separate from model-generated diagnostics.")
    metrics = api_get("/ops/metrics")
    if metrics:
        a, b, c, d = st.columns(4)
        a.metric("Annotations", metrics.get("annotation_count", 0))
        b.metric("Tasks reviewed", metrics.get("tasks_reviewed", 0))
        c.metric("Annotators", metrics.get("unique_annotators", 0))
        seconds = metrics.get("mean_handling_seconds")
        d.metric("Mean handling time", f"{seconds:.0f}s" if seconds is not None else "—")

        st.markdown("### Dimension pass rates")
        rates = metrics.get("dimension_pass_rate", {})
        if any(v is not None for v in rates.values()):
            clean = {k: v*100 for k, v in rates.items() if v is not None}
            rdf = pd.DataFrame({"dimension": list(clean.keys()), "pass_rate": list(clean.values())})
            fig = px.bar(rdf, x="pass_rate", y="dimension", orientation="h",
                         color="pass_rate",
                         color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
                         text=rdf["pass_rate"].round(1))
            fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
            fig.update_layout(coloraxis_showscale=False,
                              title=dict(text="Pass rate by dimension (%)",
                                         font=dict(size=13, color="#41506b"), x=0.01))
            fig.update_xaxes(range=[0, 105])
            style_plotly(fig, height=max(240, 60 + 46*len(rdf)), showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        m1, m2 = st.columns(2)
        m1.metric("Major issue rate", f'{metrics.get("major_issue_rate",0)*100:.1f}%' if metrics.get("major_issue_rate") is not None else "—")
        m2.metric("Escalation rate", f'{metrics.get("escalation_rate",0)*100:.1f}%' if metrics.get("escalation_rate") is not None else "—")

    sops = api_get("/ops/sops/active") or []
    tasks = api_get("/ops/tasks") or []
    if not sops:
        st.warning("No active SOP found. Apply supabase/operations_workflow.sql.")
    elif not tasks:
        st.warning("No annotation tasks found. Apply supabase/operations_workflow.sql.")
    else:
        sop = sops[0]
        st.markdown(f"**Active SOP:** {sop.get('sop_name')} · v{sop.get('version')}  ")
        st.caption("This is a demonstration SOP, not an Amazon SOP. Review and adapt it before using it as an operational standard.")
        task_ids = [t["task_id"] for t in tasks]
        task_id = st.selectbox("Select task", task_ids, format_func=lambda x: next((f'{t["task_id"]} · {t["category"]} · {t["difficulty"]}' for t in tasks if t["task_id"] == x), x))
        task = next(t for t in tasks if t["task_id"] == task_id)
        left, right = st.columns([1, 1])
        with left:
            st.markdown("#### Customer query")
            st.info(task["query"])
            st.markdown("#### Supplied context / policy")
            st.write(task["context"])
            st.markdown("#### AI response to annotate")
            st.write(task["model_response"])
            st.caption("Reference behavior is withheld during live annotation to reduce label leakage and preserve the integrity of reviewer judgments.")
        with right:
            st.markdown("#### Apply the SOP")
            st.caption("Pass = no material issue · Minor = limited issue · Major = material defect · N/A = not assessable")
            with st.form("ops_annotation_form", clear_on_submit=True):
                annotator = st.text_input("Annotator ID", value="reviewer-01")
                relevance = st.selectbox("Relevance", ["pass", "minor_issue", "major_issue", "not_applicable"])
                correctness = st.selectbox("Correctness", ["pass", "minor_issue", "major_issue", "not_applicable"])
                completeness = st.selectbox("Completeness", ["pass", "minor_issue", "major_issue", "not_applicable"])
                overall = st.selectbox("Overall decision", ["accept", "revise", "reject", "escalate"])
                defect = st.selectbox("Primary defect category", ["none", "irrelevant", "unsupported_claim", "incorrect_policy", "missing_next_step", "privacy_or_safety", "unclear_or_confusing", "other"])
                evidence = st.text_area("Evidence for decision (required)", placeholder="Quote the response and connect it to the supplied context…")
                confidence = st.slider("Confidence", 1, 5, 3)
                handling = st.number_input("Handling time (seconds)", min_value=0, max_value=86400, value=60, step=5)
                escalated = st.checkbox("Escalated for specialist/policy review")
                audit = st.checkbox("This is an audit/re-review")
                submit = st.form_submit_button("Submit annotation", type="primary")
            if submit:
                evidence_clean = evidence.strip()
                if len(annotator.strip()) < 1:
                    st.error("Annotator ID is required.")
                elif len(evidence_clean) < 8:
                    st.error("Evidence must contain at least 8 characters and should explain the decision.")
                elif len(evidence_clean) > 4000:
                    st.error("Evidence must be 4,000 characters or fewer.")
                else:
                    payload = {
                        "task_id": task_id, "annotator_id": annotator.strip(), "sop_id": sop["sop_id"],
                        "relevance": relevance, "correctness": correctness, "completeness": completeness,
                        "overall_label": overall, "evidence": evidence_clean, "defect_category": defect,
                        "confidence": confidence, "handling_seconds": int(handling),
                        "escalated": escalated, "is_audit": audit,
                    }
                    try:
                        result = api_post("/ops/annotations", payload, timeout=30)
                        st.success("Annotation saved with SOP version reference.")
                        st.rerun()
                    except requests.RequestException as e:
                        st.error(f"Could not submit annotation: {e}")

    st.markdown("### Annotation ledger")
    ledger = api_get("/ops/annotations") or []
    if ledger:
        ledger_df = pd.DataFrame(ledger)
        st.dataframe(clean_display_df(ledger_df), use_container_width=True, hide_index=True)
        st.download_button("Export auditable annotation ledger", ledger_df.to_csv(index=False), "annotation_ledger.csv", "text/csv")
    else:
        st.info("No annotations submitted yet.")

    st.markdown("### Audit trail")
    audit_rows = api_get("/ops/audit") or []
    if audit_rows:
        st.dataframe(clean_display_df(pd.DataFrame(audit_rows)), use_container_width=True, hide_index=True)
    else:
        st.caption("Submission events will appear here after the first annotation.")


# ─────────────────────────────────────────────────────────────────────────────
#  Test cases (default)
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Test cases":
    st.subheader("Evaluation dataset")
    st.markdown("<div class='subtle'>Curated benchmark cases used for repeatable model evaluation.</div>", unsafe_allow_html=True)
    data = api_get("/benchmark")
    if data:
        df = pd.DataFrame(data.get("cases", []))
        a, b = st.columns([1, 3])
        a.metric("Total test cases", data.get("count", len(df)))
        if not df.empty:
            categories = sorted(df.category.dropna().unique())
            chosen = st.multiselect("Filter categories", categories, default=categories)
            view = df[df.category.isin(chosen)]

            if "category" in view.columns and view["category"].notna().any():
                cat_counts = view["category"].value_counts().reset_index()
                cat_counts.columns = ["category", "count"]
                fig = px.bar(cat_counts, x="count", y="category", orientation="h",
                             color="count",
                             color_continuous_scale=["#cdd9ee", "#3978e8", "#8b5cf6"],
                             text="count")
                fig.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
                fig.update_layout(coloraxis_showscale=False,
                                  title=dict(text="Cases by category",
                                             font=dict(size=13, color="#41506b"), x=0.01))
                style_plotly(fig, height=max(240, 60 + 40*len(cat_counts)), showlegend=False)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            st.dataframe(view, use_container_width=True, hide_index=True)
            st.download_button("Export test cases", view.to_csv(index=False), "benchmark_cases.csv", "text/csv")
