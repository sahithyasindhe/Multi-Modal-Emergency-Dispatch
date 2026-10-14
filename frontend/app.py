"""
SENTINEL-911 Dispatcher Dashboard
Research / educational decision-support prototype — NOT for real emergency dispatch.
AI recommends, human decides.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Ensure repo root on path when launched via streamlit
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_BASE = os.getenv("SENTINEL_API_URL", "http://127.0.0.1:8000")
DISCLAIMER = (
    "⚠ RESEARCH/DEMO PROTOTYPE — Not for real emergency dispatch. "
    "AI recommends, human decides. No real units are contacted."
)

TIER_COLORS = {
    "RED": "#ff3b3b",
    "YELLOW": "#f5c542",
    "GREEN": "#2ecc71",
    "BLACK": "#9aa0a6",
}


def api_get(path: str, timeout: float = 30.0):
    try:
        r = httpx.get(f"{API_BASE}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


def api_post(path: str, payload: dict | None = None, timeout: float = 120.0):
    try:
        r = httpx.post(f"{API_BASE}{path}", json=payload or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] {
            font-family: 'IBM Plex Sans', sans-serif;
        }
        .stApp {
            background:
                radial-gradient(1200px 600px at 10% -10%, #1a2a3a 0%, transparent 55%),
                radial-gradient(900px 500px at 100% 0%, #2a1a12 0%, transparent 50%),
                linear-gradient(180deg, #0b1118 0%, #0e1620 40%, #0a1016 100%);
            color: #e8eef6;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0d1520 0%, #0a1018 100%);
            border-right: 1px solid #1e2c3c;
        }
        .sentinel-hero {
            padding: 0.4rem 0 1rem 0;
            border-bottom: 1px solid #243447;
            margin-bottom: 1rem;
        }
        .sentinel-brand {
            font-size: 2.1rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            color: #f2f6fb;
            margin: 0;
        }
        .sentinel-sub {
            color: #8fa3b8;
            font-size: 0.95rem;
            margin-top: 0.25rem;
        }
        .disclaimer-banner {
            background: linear-gradient(90deg, #3a2210, #2a180c);
            border: 1px solid #8a5a28;
            color: #f0d2a0;
            padding: 0.65rem 0.9rem;
            border-radius: 6px;
            font-size: 0.85rem;
            margin-bottom: 1rem;
        }
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 0.75rem;
            margin-bottom: 1rem;
        }
        .kpi {
            background: rgba(18, 28, 40, 0.9);
            border: 1px solid #243447;
            border-radius: 8px;
            padding: 0.85rem 1rem;
        }
        .kpi .label { color: #8fa3b8; font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; }
        .kpi .value { font-size: 1.7rem; font-weight: 700; font-family: 'IBM Plex Mono', monospace; margin-top: 0.2rem; }
        .kpi.red { border-color: #6a2020; box-shadow: inset 0 0 0 1px rgba(255,59,59,0.15); }
        .kpi.red .value { color: #ff5c5c; }
        .kpi.yellow { border-color: #6a5520; }
        .kpi.yellow .value { color: #f5c542; }
        .kpi.green { border-color: #1f5a38; }
        .kpi.green .value { color: #2ecc71; }
        .kpi.dup { border-color: #3a2a5a; }
        .kpi.dup .value { color: #c4a8ff; }
        .tier-badge {
            display: inline-block;
            padding: 0.15rem 0.55rem;
            border-radius: 4px;
            font-weight: 700;
            font-size: 0.75rem;
            letter-spacing: 0.06em;
            font-family: 'IBM Plex Mono', monospace;
        }
        .tier-RED { background: #5a1515; color: #ff8a8a; border: 1px solid #ff3b3b; }
        .tier-YELLOW { background: #4a3a10; color: #ffe08a; border: 1px solid #f5c542; }
        .tier-GREEN { background: #123a24; color: #8dffb8; border: 1px solid #2ecc71; }
        .tier-BLACK { background: #222; color: #ccc; border: 1px solid #666; }
        .conflict-box {
            background: #3a2208;
            border-left: 4px solid #f5a623;
            padding: 0.8rem 1rem;
            border-radius: 4px;
            margin: 0.5rem 0 1rem 0;
        }
        .evidence-chip {
            display: inline-block;
            background: #1a2736;
            border: 1px solid #334859;
            color: #b8c9da;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            margin: 0.15rem;
            font-family: 'IBM Plex Mono', monospace;
        }
        .bar-row { margin: 0.35rem 0; }
        .bar-label { display: flex; justify-content: space-between; font-size: 0.82rem; color: #a8b8c8; }
        .bar-track {
            height: 10px; background: #1a2430; border-radius: 3px; overflow: hidden; margin-top: 0.2rem;
        }
        .bar-fill { height: 100%; border-radius: 3px; }
        div[data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def tier_badge(tier: str) -> str:
    t = tier or "GREEN"
    return f'<span class="tier-badge tier-{t}">{t}</span>'


def feature_bar(label: str, value: float, color: str) -> str:
    w = max(0, min(100, value))
    return f"""
    <div class="bar-row">
      <div class="bar-label"><span>{label}</span><span>{value:.0f}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{w}%;background:{color};"></div></div>
    </div>
    """


def render_sidebar():
    st.sidebar.markdown("## SYSTEM STATUS")
    health = api_get("/health")
    if "error" in health:
        st.sidebar.error(f"API offline: {health['error']}")
        st.sidebar.info(f"Start backend: `uvicorn backend.main:app --reload`\n\nExpected: `{API_BASE}`")
        return health

    comps = health.get("components", {})
    st.sidebar.success("API online")
    st.sidebar.markdown(f"**Mode:** `{health.get('model_mode', '?')}`")
    st.sidebar.markdown(f"**Demo mode:** `{health.get('demo_mode')}`")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Model / RAG")
    for k, v in comps.items():
        st.sidebar.markdown(f"- **{k}:** `{v}`")
    st.sidebar.markdown("---")
    st.sidebar.caption(DISCLAIMER)
    return health


def kpi_row(metrics: dict):
    tiers = metrics.get("tiers", {})
    html = f"""
    <div class="kpi-grid">
      <div class="kpi"><div class="label">Active</div><div class="value">{metrics.get('active_incidents', 0)}</div></div>
      <div class="kpi red"><div class="label">RED</div><div class="value">{tiers.get('RED', 0)}</div></div>
      <div class="kpi yellow"><div class="label">YELLOW</div><div class="value">{tiers.get('YELLOW', 0)}</div></div>
      <div class="kpi green"><div class="label">GREEN</div><div class="value">{tiers.get('GREEN', 0)}</div></div>
      <div class="kpi dup"><div class="label">Dup Clusters</div><div class="value">{metrics.get('duplicate_clusters', 0)}</div></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def incident_map(incidents: list):
    if not incidents:
        st.info("No incidents to map yet. Run a simulation.")
        return
    rows = []
    for i in incidents:
        loc = i.get("location") or {}
        urg = i.get("urgency") or {}
        rows.append(
            {
                "lat": loc.get("lat"),
                "lon": loc.get("lon"),
                "tier": (urg.get("tier") or "GREEN"),
                "score": urg.get("value") or 0,
                "id": i.get("incident_id"),
                "type": i.get("incident_type"),
                "callers": i.get("caller_count", 1),
            }
        )
    import pandas as pd

    df = pd.DataFrame(rows).dropna(subset=["lat", "lon"])
    if df.empty:
        return
    fig = px.scatter_mapbox(
        df,
        lat="lat",
        lon="lon",
        color="tier",
        size="score",
        hover_name="id",
        hover_data=["type", "callers", "score"],
        color_discrete_map=TIER_COLORS,
        zoom=11,
        height=360,
    )
    fig.update_layout(
        mapbox_style="carto-darkmatter",
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(bgcolor="rgba(10,16,24,0.8)"),
    )
    st.plotly_chart(fig, use_container_width=True)


def score_gauge(value: float, tier: str):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": f"  {tier}", "font": {"size": 28}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": TIER_COLORS.get(tier, "#888")},
                "steps": [
                    {"range": [0, 25], "color": "#123a24"},
                    {"range": [25, 50], "color": "#1a3a28"},
                    {"range": [50, 75], "color": "#4a3a10"},
                    {"range": [75, 100], "color": "#5a1515"},
                ],
                "threshold": {"line": {"color": "white", "width": 2}, "value": value},
            },
        )
    )
    fig.update_layout(
        height=220,
        margin=dict(l=20, r=20, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e8eef6"},
    )
    st.plotly_chart(fig, use_container_width=True)


def render_incident_detail(inc: dict):
    left, center, right = st.columns([1.1, 1.2, 1.1])
    audio = inc.get("audio_evidence") or {}
    vision = inc.get("visual_evidence") or {}
    loc = inc.get("location") or {}
    urg = inc.get("urgency") or {}
    fb = urg.get("feature_breakdown") or {}
    plan = inc.get("resource_plan") or {}
    safety = inc.get("safety") or {}
    expl = inc.get("explanation") or {}
    pe = inc.get("protocol_evidence") or {}

    with left:
        st.markdown("### Incident")
        st.markdown(f"{tier_badge(urg.get('tier', ''))} `{inc.get('incident_id')}`", unsafe_allow_html=True)
        st.write(f"**Type:** {inc.get('incident_type')}")
        st.write(f"**Status:** {inc.get('status')}")
        st.write(f"**Location:** {loc.get('address')}")
        st.write(f"**Coords:** {loc.get('lat')}, {loc.get('lon')}")
        st.write(f"**H3-like cell:** `{loc.get('h3_cell')}`")
        st.write(f"**Confidence:** {inc.get('extraction_confidence')}")
        st.write(f"**Callers in cluster:** {inc.get('caller_count', 1)}")

        st.markdown("#### Audio")
        st.write(audio.get("transcript") or "—")
        st.caption(f"Lang: {audio.get('language')} | Panic: {audio.get('panic_index')} | Provider: {audio.get('provider')}")
        events = audio.get("audio_events") or []
        if events:
            st.markdown(
                " ".join(f'<span class="evidence-chip">{e}</span>' for e in events),
                unsafe_allow_html=True,
            )

        st.markdown("#### Vision")
        st.write(f"Scene: **{vision.get('scene_type')}** | Persons: {vision.get('persons_visible')} | Down: {vision.get('persons_down')}")
        chips = []
        if vision.get("fire_visible"):
            chips.append("fire")
        if vision.get("smoke_present"):
            chips.append("smoke")
        if vision.get("hazmat_placard"):
            chips.append("hazmat")
        if vision.get("structural_damage"):
            chips.append("structural")
        if vision.get("water_rising"):
            chips.append("water")
        if vision.get("fuel_leak_visible"):
            chips.append("fuel_leak")
        if chips:
            st.markdown(
                " ".join(f'<span class="evidence-chip">{c}</span>' for c in chips),
                unsafe_allow_html=True,
            )
        st.caption(vision.get("notes") or "")

        hazards = inc.get("hazards") or {}
        st.markdown("#### Hazard provenance")
        prov = inc.get("hazard_provenance") or {}
        for k, v in hazards.items():
            if v:
                src = prov.get(k, {})
                sources = src.get("sources") if isinstance(src, dict) else []
                st.write(f"- **{k}:** true ← {sources or 'inferred'}")

    with center:
        st.markdown("### Urgency (deterministic)")
        if urg:
            score_gauge(float(urg.get("value") or 0), urg.get("tier") or "GREEN")
            bars = (
                feature_bar("Life Threat", float(fb.get("life_threat") or 0), "#ff5c5c")
                + feature_bar("Casualty Load", float(fb.get("casualty_load") or 0), "#f5c542")
                + feature_bar("Hazard Risk", float(fb.get("hazard_risk") or 0), "#ff8a4c")
                + feature_bar("Access", float(fb.get("access") or 0), "#5dade2")
                + feature_bar("Caller State", float(fb.get("caller_state") or 0), "#a78bfa")
            )
            st.markdown(bars, unsafe_allow_html=True)
            st.markdown(
                f"**Final:** `{urg.get('value')} — {urg.get('tier')}`",
            )
            st.markdown("**Triggered rules**")
            for r in (urg.get("rules_triggered") or [])[:12]:
                st.caption(f"• {r}")
            for o in urg.get("overrides_applied") or []:
                st.warning(o)
        else:
            st.write("No score")

        conflicts = inc.get("conflicts") or []
        if conflicts:
            for c in conflicts:
                st.markdown(
                    f"""
                    <div class="conflict-box">
                      <strong>⚠ MODALITY CONFLICT — {c.get('field')}</strong><br/>
                      <b>Audio says:</b> {c.get('audio_says')}<br/>
                      <b>Vision indicates:</b> {c.get('vision_says')}<br/>
                      <b>Resolution:</b> {c.get('resolution')}<br/>
                      <b>Retained:</b> {c.get('retained')} | Confidence: {c.get('confidence')}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("### Protocol evidence (DEMO citations)")
        if pe.get("insufficient_evidence"):
            st.error(pe.get("summary") or "Insufficient protocol evidence — human review required.")
        for cite in pe.get("citations") or []:
            with st.expander(f"{cite.get('citation_id')} — {cite.get('title')} (score {cite.get('score')})"):
                st.write(cite.get("snippet"))
                st.caption("DEMO/synthetic educational excerpt — not an official protocol.")

        st.markdown("### Why this tier?")
        for w in expl.get("why_tier") or []:
            st.write(f"- {w}")
        if expl.get("decision_line"):
            st.success(expl["decision_line"])
        st.caption(expl.get("narrative") or "")

    with right:
        st.markdown("### Recommended resources")
        st.caption("Conceptual recommendations only — no real dispatch.")
        for u in plan.get("recommended_units") or []:
            st.write(f"- **{u.get('unit_id')}** `{u.get('unit_type')}` ETA ~{u.get('eta_minutes')} min")
        st.write(f"**Nearest facility:** {plan.get('nearest_facility')}")
        st.write(f"**Facility ETA:** {plan.get('nearest_facility_eta_min')} min")
        if plan.get("hazmat_warning"):
            st.error("HAZMAT WARNING (DEMO) — isolate / upwind staging concepts")
        for n in plan.get("notes") or []:
            st.caption(n)

        st.markdown("### Safety validation")
        if safety.get("valid"):
            st.success("Safety checks passed (still requires human approval)")
        else:
            st.error("Safety validation FAILED")
        for v in safety.get("violations") or []:
            st.write(f"❌ {v}")
        for w in safety.get("warnings") or []:
            st.write(f"⚠ {w}")
        st.info(f"Required human action: **{safety.get('required_human_action')}**")

        if inc.get("abstain"):
            st.error(f"ABSTAIN / ESCALATE: {inc.get('abstain_reason')}")

        st.markdown("### Human decision")
        st.caption("AI recommends, human decides.")
        reason = st.text_input("Reason / notes", key=f"reason_{inc['incident_id']}")
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        iid = inc["incident_id"]
        if c1.button("APPROVE", key=f"ap_{iid}", use_container_width=True):
            res = api_post(f"/incidents/{iid}/approve", {"reason": reason or "Approved for demo record"})
            st.write(res.get("note") or res)
            st.rerun()
        if c2.button("AMEND", key=f"am_{iid}", use_container_width=True):
            res = api_post(
                f"/incidents/{iid}/amend",
                {"reason": reason or "Amended", "changes": {"notes": reason or "Dispatcher amendment"}},
            )
            st.write(res.get("note") or res)
            st.rerun()
        if c3.button("REJECT", key=f"rj_{iid}", use_container_width=True):
            res = api_post(f"/incidents/{iid}/reject", {"reason": reason or "Rejected"})
            st.write(res.get("note") or res)
            st.rerun()
        if c4.button("ESCALATE", key=f"es_{iid}", use_container_width=True):
            res = api_post(f"/incidents/{iid}/escalate", {"reason": reason or "Escalated to supervisor"})
            st.write(res.get("note") or res)
            st.rerun()

        actions = inc.get("dispatcher_actions") or []
        if actions:
            st.markdown("#### Audit trail")
            for a in actions:
                st.caption(f"{a.get('timestamp')} — **{a.get('action')}** — {a.get('reason')}")


def main():
    st.set_page_config(
        page_title="SENTINEL-911",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    health = render_sidebar()

    st.markdown(
        """
        <div class="sentinel-hero">
          <p class="sentinel-brand">SENTINEL-911</p>
          <p class="sentinel-sub">Multimodal Emergency Decision Support — Research Prototype</p>
        </div>
        <div class="disclaimer-banner">"""
        + DISCLAIMER
        + "</div>",
        unsafe_allow_html=True,
    )

    # Simulation controls
    st.markdown("### Live simulation")
    scenarios = api_get("/scenarios")
    opts = ["vehicle_crash", "apartment_fire", "kitchen_vs_structural_fire", "flood", "hazmat_leak", "cardiac", "mci"]
    if isinstance(scenarios, dict) and scenarios.get("scenarios"):
        opts = [s["id"] for s in scenarios["scenarios"]]
        labels = {s["id"]: s["title"] for s in scenarios["scenarios"]}
    else:
        labels = {o: o for o in opts}

    sc1, sc2, sc3, sc4 = st.columns([2, 1, 1, 1])
    choice = sc1.selectbox("Scenario", opts, format_func=lambda x: labels.get(x, x))
    if sc2.button("▶ RUN EMERGENCY SIMULATION", use_container_width=True, type="primary"):
        with st.spinner("Running full multimodal pipeline..."):
            result = api_post("/simulation/run", {"scenario_id": choice, "generate_duplicates": False})
        if "error" in result:
            st.error(result["error"])
        else:
            st.success(f"Simulation complete: {result.get('title')}")
            st.caption(" → ".join(result.get("pipeline") or []))
            st.rerun()
    if sc3.button("Generate 10 Duplicate Calls", use_container_width=True):
        with st.spinner("Generating MCI duplicate callers..."):
            result = api_post("/simulation/mci", {"duplicate_count": 10})
        if "error" in result:
            st.error(result["error"])
        else:
            st.success(f"MCI demo: {result.get('caller_count')} callers clustered")
            st.rerun()
    if sc4.button("Refresh", use_container_width=True):
        st.rerun()

    if "error" in (health or {}):
        st.stop()

    metrics = api_get("/metrics")
    if "error" not in metrics:
        kpi_row(metrics)

    data = api_get("/incidents")
    incidents = data.get("incidents") or [] if isinstance(data, dict) else []
    clusters = api_get("/clusters").get("clusters") or []

    tab_q, tab_map, tab_audit, tab_rag = st.tabs(["Incident Queue", "Map", "Audit", "Protocol Search"])

    with tab_q:
        if clusters:
            st.markdown("#### 🚨 Possible duplicate clusters")
            for c in clusters:
                st.warning(
                    f"**POSSIBLE DUPLICATE** `{c.get('cluster_id')}` — {c.get('caller_count')} callers | "
                    f"type={c.get('incident_type')} | similarity={float(c.get('similarity') or 0)*100:.0f}% | "
                    f"primary={c.get('primary_incident_id')}"
                )

        if not incidents:
            st.info("Queue empty. Click **RUN EMERGENCY SIMULATION** to generate a demo incident.")
        else:
            labels_inc = []
            for i in incidents:
                urg = i.get("urgency") or {}
                labels_inc.append(
                    f"[{urg.get('tier', '?')}] {urg.get('value', '?')} | {i.get('incident_type')} | "
                    f"{i.get('incident_id')} | callers={i.get('caller_count', 1)}"
                )
            idx = st.selectbox(
                "Select incident (sorted by urgency)",
                range(len(incidents)),
                format_func=lambda j: labels_inc[j],
            )
            selected = incidents[idx]
            # Mini card strip
            cas = selected.get("casualties") or {}
            haz = selected.get("hazards") or {}
            urg = selected.get("urgency") or {}
            st.markdown(
                f"{tier_badge(urg.get('tier', ''))} "
                f"**Score {urg.get('value')}** · casualties≈{cas.get('count_est')} · "
                f"fire={haz.get('fire')} hazmat={haz.get('hazmat')} · conf={selected.get('extraction_confidence')}",
                unsafe_allow_html=True,
            )
            render_incident_detail(selected)

    with tab_map:
        st.markdown("#### Incident map (demo coordinates)")
        incident_map(incidents)

    with tab_audit:
        audit = api_get("/audit?limit=40")
        for e in audit.get("events") or []:
            st.caption(
                f"{e.get('created_at')} | **{e.get('event_type')}** | {e.get('incident_id')} | {e.get('message')}"
            )

    with tab_rag:
        q = st.text_input("Search DEMO protocols", value="structural fire trapped HAZMAT")
        if st.button("Search protocols"):
            res = api_get(f"/protocols/search?q={q}")
            ev = (res or {}).get("evidence") or {}
            st.write(ev.get("summary"))
            for c in ev.get("citations") or []:
                st.markdown(f"**{c.get('citation_id')}** — {c.get('title')}")
                st.caption(c.get("snippet"))


if __name__ == "__main__":
    main()
