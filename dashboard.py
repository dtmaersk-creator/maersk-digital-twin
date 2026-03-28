# =============================================================================
# dashboard.py v2.0 — Maersk Financial Digital Twin
# 5 tabs: Live Twin | Shock Engine | Stock Predictor | Manual Uncertainty | Live Validation
# =============================================================================

import json, os, time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auto_updater import get_current_baseline, start_updater
from config import (
    BASELINE, COLOR_BG, COLOR_CARD, COLOR_DANGER, COLOR_LIVE,
    COLOR_NEGATIVE, COLOR_NEUTRAL, COLOR_POSITIVE,
    DASHBOARD_REFRESH_SECONDS, DASHBOARD_TITLE, FEED_STALE_THRESHOLD_SECONDS,
    FINNHUB_API_KEY, LIVE_EVENTS, MONTE_CARLO_RUNS,
    SHOCK_SCENARIOS, SNAPSHOT_JSON, SPARKLINE_MINUTES, STRATEGIES,
)
from data_collection import get_feed_health, get_history, get_latest_snapshot, start_pipeline
from shock_engine import (
    MonteCarloEngine, compute_financial_stress_score,
    export_results_csv, export_results_json, get_strategy_ranking,
)

# =============================================================================
# Page config
# =============================================================================
st.set_page_config(
    page_title=DASHBOARD_TITLE, page_icon="🚢",
    layout="wide", initial_sidebar_state="expanded",
)

# =============================================================================
# CSS
# =============================================================================
st.markdown(f"""
<style>
.stApp {{background-color:{COLOR_BG};color:#E6EDF3}}
.block-container {{padding-top:1rem;padding-bottom:1rem}}
.ticker-strip {{
  background:{COLOR_CARD};border:1px solid #30363D;border-radius:8px;
  padding:12px 18px;margin-bottom:16px;display:flex;flex-wrap:wrap;gap:20px;align-items:center}}
.ticker-item {{display:flex;flex-direction:column;align-items:center;min-width:90px}}
.ticker-label {{font-size:10px;color:#8B949E;text-transform:uppercase;letter-spacing:.5px}}
.ticker-value {{font-size:16px;font-weight:700;font-family:'Courier New',monospace}}
.ticker-pct   {{font-size:11px;font-family:'Courier New',monospace}}
.positive {{color:{COLOR_POSITIVE}}} .negative {{color:{COLOR_NEGATIVE}}} .neutral {{color:{COLOR_NEUTRAL}}}
.live-badge {{
  display:inline-flex;align-items:center;gap:6px;
  background:rgba(0,229,255,.12);border:1px solid {COLOR_LIVE};
  border-radius:20px;padding:4px 12px;font-size:12px;font-weight:700;
  color:{COLOR_LIVE};letter-spacing:1px}}
.live-dot {{
  width:8px;height:8px;border-radius:50%;background:{COLOR_LIVE};
  animation:pulse 1.2s ease-in-out infinite}}
@keyframes pulse {{
  0%{{opacity:1;transform:scale(1);box-shadow:0 0 0 0 rgba(0,229,255,.6)}}
  50%{{opacity:.7;transform:scale(1.3);box-shadow:0 0 0 6px rgba(0,229,255,0)}}
  100%{{opacity:1;transform:scale(1);box-shadow:0 0 0 0 rgba(0,229,255,0)}}}}
.kpi-card {{background:{COLOR_CARD};border:1px solid #30363D;border-radius:8px;padding:14px 18px;text-align:center}}
.kpi-label {{font-size:11px;color:#8B949E;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}}
.kpi-value {{font-size:22px;font-weight:700;color:#E6EDF3}}
.kpi-unit  {{font-size:11px;color:#8B949E}}
.alert-live    {{background:rgba(255,107,53,.1);border:1px solid {COLOR_DANGER};border-radius:8px;padding:14px 18px;margin-bottom:12px}}
.alert-blue    {{background:rgba(0,229,255,.08);border:1px solid {COLOR_LIVE};border-radius:8px;padding:14px 18px;margin-bottom:12px}}
.alert-warning {{background:rgba(255,215,0,.08);border:1px solid {COLOR_NEUTRAL};border-radius:8px;padding:14px 18px;margin-bottom:12px}}
.alert-danger  {{background:rgba(255,23,68,.08);border:1px solid {COLOR_NEGATIVE};border-radius:8px;padding:14px 18px;margin-bottom:12px}}
.section-header {{
  font-size:13px;font-weight:700;color:#8B949E;text-transform:uppercase;
  letter-spacing:1px;border-bottom:1px solid #30363D;
  padding-bottom:6px;margin-bottom:12px}}
#MainMenu {{visibility:hidden}} footer {{visibility:hidden}} header {{visibility:hidden}}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# Session state — start services once
# =============================================================================
if "started" not in st.session_state:
    start_pipeline()
    start_updater()
    st.session_state.started = True

# =============================================================================
# Helpers
# =============================================================================
TICKER_LABELS = {
    "maersk_stock": "MAERSK-B", "brent_crude": "Brent",
    "natural_gas":  "Nat.Gas",  "sp500":       "S&P 500",
    "usd_dkk":      "USD/DKK",  "usd_eur":     "EUR/USD", "usd_cny": "USD/CNY",
}
TICKER_UNITS = {
    "maersk_stock": "DKK", "brent_crude": "$/bbl",
    "natural_gas":  "$/MMBtu", "sp500": "pts",
    "usd_dkk": "", "usd_eur": "", "usd_cny": "",
}

def fv(val, key):
    if val is None: return "—"
    if key == "maersk_stock": return f"{val:,.0f}"
    if key in ("usd_dkk","usd_eur","usd_cny"): return f"{val:.4f}"
    if key == "sp500": return f"{val:,.1f}"
    return f"{val:.2f}"

def fp(pct):
    if pct is None: return ""
    return f"{'+'if pct>=0 else''}{pct:.2f}%"

def pc(pct):
    if pct is None: return "neutral"
    return "positive" if pct >= 0 else "negative"

def secs_since(iso):
    try:
        ts = datetime.fromisoformat(iso)
        if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except: return 9999

def sparkline(history, field, key=""):
    rows = [r for r in history if r["field"] == field]
    fig  = go.Figure()
    if rows:
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
        c  = COLOR_POSITIVE if df["value"].iloc[-1] >= df["value"].iloc[0] else COLOR_NEGATIVE
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["value"], mode="lines",
                                 line=dict(color=c, width=1.5)))
    fig.update_layout(height=50, margin=dict(l=0,r=0,t=0,b=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False)
    return fig

# =============================================================================
# MARKET INTELLIGENCE
# =============================================================================

def market_intelligence(snapshot, baseline):
    if not snapshot: return {}
    tickers = snapshot.get("tickers", {})
    scores  = {k: 0 for k in SHOCK_SCENARIOS}
    signals = []

    brent     = tickers.get("brent_crude", {}).get("current", 0)
    brent_pct = tickers.get("brent_crude", {}).get("pct_change", 0) or 0
    sp500_pct = tickers.get("sp500",       {}).get("pct_change", 0) or 0
    cny_pct   = tickers.get("usd_cny",     {}).get("pct_change", 0) or 0
    maersk_pct= tickers.get("maersk_stock",{}).get("pct_change", 0) or 0

    # Hormuz / Fuel signals
    if brent > 126:
        scores["hormuz_demand_compound"] += 50
        scores["hormuz_closure"]         += 40
        signals.append({"level":"danger","icon":"🛢️",
            "text": f"Brent ${brent:.1f} — ABOVE HORMUZ CRISIS PEAK of $126! Extreme fuel stress."})
    elif brent > 100:
        scores["hormuz_closure"]   += 40
        scores["fuel_price_spike"] += 25
        signals.append({"level":"danger","icon":"🛢️",
            "text": f"Brent ${brent:.1f} — above $100. Hormuz/energy crisis conditions active."})
    elif brent > 90:
        scores["fuel_price_spike"] += 15
        signals.append({"level":"warning","icon":"🛢️",
            "text": f"Brent ${brent:.1f} — elevated fuel pressure."})

    if abs(brent_pct) > 2:
        scores["fuel_price_spike"] += 20
        signals.append({"level":"warning","icon":"📈",
            "text": f"Brent moved {brent_pct:+.1f}% today — high commodity volatility."})

    # Demand / macro signals
    if sp500_pct < -2:
        scores["demand_collapse"]    += 30
        scores["china_hard_landing"] += 20
        signals.append({"level":"danger","icon":"📉",
            "text": f"S&P 500 {sp500_pct:.1f}% — risk-off. Demand outlook deteriorating."})
    elif sp500_pct < -1:
        scores["demand_collapse"] += 15
        signals.append({"level":"warning","icon":"📉",
            "text": f"S&P 500 {sp500_pct:.1f}% — mild demand concern."})
    elif sp500_pct > 1:
        signals.append({"level":"info","icon":"📈",
            "text": f"S&P 500 +{sp500_pct:.1f}% — positive demand signal."})

    # Trade war / China signals
    if abs(cny_pct) > 0.5:
        scores["us_tariff_escalation"] += 25
        signals.append({"level":"warning","icon":"🇨🇳",
            "text": f"USD/CNY {cny_pct:+.2f}% — China FX volatility. Trade tension signal."})

    # Maersk-specific
    if maersk_pct < -3:
        scores["demand_collapse"] += 20
        signals.append({"level":"danger","icon":"🚢",
            "text": f"Maersk stock {maersk_pct:.1f}% — market pricing in negative outlook."})

    # Check for live events
    active_events = baseline.get("active_live_events", [])
    if "hormuz_2026" in active_events or brent > 100:
        signals.insert(0, {"level":"live","icon":"🔴",
            "text": "LIVE EVENT ACTIVE: Strait of Hormuz Crisis (March 2026). "
                    "Model shock G08 is currently happening in real time."})

    if max(scores.values()) == 0:
        most_likely = "demand_collapse"
        confidence  = 20
        signals.append({"level":"info","icon":"✅",
            "text": "No major stress signals detected — markets appear stable."})
    else:
        most_likely = max(scores, key=scores.get)
        confidence  = min(int(scores[most_likely] * 1.2), 95)

    try:
        engine = MonteCarloEngine(baseline)
        strat_results = {k: engine.run_single(most_likely, k) for k in STRATEGIES}
        best_strategy = max(
            [k for k in strat_results if k != "do_nothing"],
            key=lambda k: strat_results[k].strategy_npv_advantage_usd_m
        )
    except Exception:
        best_strategy = "dynamic_pricing"

    return {
        "most_likely_shock":    most_likely,
        "shock_confidence":     confidence,
        "recommended_strategy": best_strategy,
        "signals":              signals,
    }

# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar():
    with st.sidebar:
        st.markdown("### 🚢 Maersk Digital Twin v2.0")
        st.caption("March 2026 — Hormuz Crisis Edition")

        # Live event alert
        if os.path.exists(SNAPSHOT_JSON):
            try:
                snap = json.load(open(SNAPSHOT_JSON))
                brent = snap.get("tickers",{}).get("brent_crude",{}).get("current",0)
                if brent > 100:
                    st.error(f"🔴 LIVE: Hormuz Crisis\nBrent ${brent:.1f}/bbl")
            except Exception:
                pass

        st.markdown("---")
        st.markdown("### 📡 Data Sources")
        st.markdown("""
| Feed | Cadence |
|---|---|
| Stock, FX, Commodities | ~1 min |
| Maersk Stock | 15-min delay |
| Freight Rates (FBX) | Daily 14:00 UTC |
| Fundamentals | Quarterly |
""")
        st.markdown("---")
        st.markdown("### 📊 Model Stats")
        st.markdown(f"**Scenarios:** {len(SHOCK_SCENARIOS)} (incl. 3 live events)")
        st.markdown(f"**Strategies:** {len(STRATEGIES)}")
        st.markdown(f"**MC Runs:** {MONTE_CARLO_RUNS:,} per scenario")
        st.markdown("---")
        st.markdown("### 🔄 Refresh")
        st.caption("Data updates every 60s in background.")
        if st.button("🔄 Refresh Now", type="primary"):
            st.rerun()
        st.markdown("---")
        if FINNHUB_API_KEY == "YOUR_KEY_HERE":
            st.error("⚠️ Set FINNHUB_API_KEY in config.py")
        else:
            st.success("✅ API key configured")


# =============================================================================
# TAB 1: LIVE TWIN
# =============================================================================

def render_live_twin(snapshot, history, baseline, intel):
    # ── Header ────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([4, 1, 2])
    with c1:
        st.markdown(f"## 🚢 {DASHBOARD_TITLE}")
    with c2:
        if snapshot:
            age  = secs_since(snapshot.get("timestamp", ""))
            live = age < FEED_STALE_THRESHOLD_SECONDS
            badge = (
                '<div class="live-badge"><div class="live-dot"></div>LIVE</div>'
                if live else
                '<div class="live-badge" style="border-color:#FF1744;color:#FF1744">'
                '<div class="live-dot" style="background:#FF1744"></div>STALE</div>'
            )
        else:
            badge = '<div class="live-badge" style="opacity:.4">NO DATA</div>'
        st.markdown(badge, unsafe_allow_html=True)
    with c3:
        if snapshot:
            ts = snapshot.get("timestamp", "")
            q  = snapshot.get("quality", 0)
            qc = COLOR_POSITIVE if q >= 0.8 else COLOR_NEUTRAL if q >= 0.5 else COLOR_NEGATIVE
            st.markdown(
                f'<p style="font-size:11px;color:#8B949E;text-align:right">'
                f'Updated: {ts[:19].replace("T"," ")} UTC<br>'
                f'Quality: <span style="color:{qc};font-weight:700">{q:.0%}</span></p>',
                unsafe_allow_html=True,
            )

    # ── Live event banner ─────────────────────────────────────────────
    for evt_key, evt in LIVE_EVENTS.items():
        if evt.get("status") == "active":
            st.markdown(f"""
            <div class="alert-live">
                <b>{evt['label']}</b><br>
                {evt['description']}<br>
                <small>Started: {evt['started']} | Linked shock: <code>{evt['linked_shock']}</code></small>
            </div>""", unsafe_allow_html=True)

    # ── Ticker strip ──────────────────────────────────────────────────
    if snapshot:
        tickers = snapshot.get("tickers", {})
        html = ""
        for key in TICKER_LABELS:
            d = tickers.get(key)
            if not d:
                continue
            html += (
                f'<div class="ticker-item">'
                f'<span class="ticker-label">{TICKER_LABELS[key]}</span>'
                f'<span class="ticker-value {pc(d.get("pct_change"))}">{fv(d["current"], key)}</span>'
                f'<span class="ticker-pct {pc(d.get("pct_change"))}">'
                f'{fp(d.get("pct_change"))} {TICKER_UNITS.get(key,"")}</span>'
                f'</div>'
            )
        st.markdown(f'<div class="ticker-strip">{html}</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-header">60-MIN PRICE HISTORY</div>', unsafe_allow_html=True)
        cols = st.columns(len(TICKER_LABELS))
        for i, key in enumerate(TICKER_LABELS):
            with cols[i]:
                st.markdown(
                    f"<p style='font-size:10px;color:#8B949E;text-align:center'>"
                    f"{TICKER_LABELS[key]}</p>",
                    unsafe_allow_html=True,
                )
                st.plotly_chart(
                    sparkline(history, key),
                    use_container_width=True,
                    config={"displayModeBar": False},
                    key=f"sp_{key}",
                )
    else:
        st.warning("⏳ Waiting for first data fetch...")

    # ── Market intelligence ───────────────────────────────────────────
    if intel and intel.get("signals"):
        st.markdown("---")
        st.markdown('<div class="section-header">🤖 LIVE MARKET INTELLIGENCE</div>',
                    unsafe_allow_html=True)
        level_map = {
            "live": "alert-live", "danger": "alert-danger",
            "warning": "alert-warning", "info": "alert-blue",
        }
        for sig in intel["signals"]:
            cls = level_map.get(sig["level"], "alert-blue")
            st.markdown(f'<div class="{cls}">{sig["icon"]} {sig["text"]}</div>',
                        unsafe_allow_html=True)
        shock_lbl = SHOCK_SCENARIOS[intel["most_likely_shock"]]["label"]
        strat_lbl = STRATEGIES[intel["recommended_strategy"]]["label"]
        st.markdown(f"""
        <div class="alert-blue">
            🎯 <b>Assessment:</b> Most likely scenario: <b>{shock_lbl}</b>
            ({intel['shock_confidence']}% confidence)<br>
            ✅ <b>Recommended strategy:</b> <b>{strat_lbl}</b>
        </div>""", unsafe_allow_html=True)

    # ── Feed health ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-header">DATA FEED HEALTH</div>', unsafe_allow_html=True)
    health = get_feed_health()
    if health:
        cols = st.columns(min(len(health), 7))
        for i, feed in enumerate(health[:7]):
            with cols[i]:
                icon  = "🟢" if feed["status"] == "ok" else "🟡" if feed["status"] == "stale" else "🔴"
                lat   = f"{feed['latency_ms']:.0f}ms" if feed.get("latency_ms") else "—"
                age   = secs_since(feed.get("timestamp", ""))
                color = "#00C853" if feed["status"] == "ok" else "#FF1744"
                st.markdown(
                    f'<div class="kpi-card">'
                    f'<div class="kpi-label">{feed["source"]}</div>'
                    f'<div style="color:{color};font-weight:700">{icon} {feed["status"].upper()}</div>'
                    f'<div style="font-size:10px;color:#8B949E">{lat} · {age:.0f}s</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Financial Stress Score + KPIs ────────────────────────────────
    st.markdown("---")
    # Bug fix: baseline comes in as a parameter — no re-definition needed.
    # Bug fix: compute fss exactly ONCE.
    fss       = compute_financial_stress_score(baseline)
    fss_color = COLOR_POSITIVE if fss < 30 else COLOR_NEUTRAL if fss < 60 else COLOR_NEGATIVE

    st.markdown(
        '<div class="section-header">BASELINE FINANCIALS + FINANCIAL STRESS SCORE</div>',
        unsafe_allow_html=True,
    )
    kpis = [
        ("Revenue",      baseline.get("revenue_usd_m", 0),    "$", "B USD", 1000),
        ("EBITDA",       baseline.get("ebitda_usd_m", 0),     "$", "B USD", 1000),
        ("Net Income",   baseline.get("net_income_usd_m", 0), "$", "B USD", 1000),
        ("Fuel Cost",    baseline.get("fuel_cost_usd_m", 0),  "$", "B USD", 1000),
        ("Cash",         baseline.get("cash_usd_m", 0),       "$", "B USD", 1000),
        ("Stress Score", fss,                                  "",  "/ 100", 1),
    ]
    cols = st.columns(6)
    for i, (label, val, pre, suf, div) in enumerate(kpis):
        with cols[i]:
            color   = fss_color if label == "Stress Score" else "#E6EDF3"
            display = f"{pre}{val/div:.1f}" if div != 1 else f"{val:.1f}"
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value" style="color:{color}">{display}</div>'
                f'<div class="kpi-unit">{suf}</div></div>',
                unsafe_allow_html=True,
            )
# =============================================================================
# TAB 2: SHOCK ENGINE
# =============================================================================

def render_shock_engine(baseline):
    st.markdown("## ⚡ Shock Scenario Engine")

    # Group scenarios by category
    cats = {}
    for k, v in SHOCK_SCENARIOS.items():
        c = v.get("category","other")
        cats.setdefault(c, []).append(k)

    c1, c2, c3 = st.columns([2,2,1])
    with c1:
        cat = st.selectbox("Category", ["all"] + list(cats.keys()))
        filtered = list(SHOCK_SCENARIOS.keys()) if cat=="all" else cats.get(cat,[])
        scenario_key = st.selectbox("Shock Scenario", filtered,
                                    format_func=lambda k: SHOCK_SCENARIOS[k]["label"] +
                                    (" 🔴 LIVE" if SHOCK_SCENARIOS[k].get("live_event") else ""))
    with c2:
        strategy_key = st.selectbox("Strategic Response", list(STRATEGIES.keys()),
                                    format_func=lambda k: STRATEGIES[k]["label"])
    with c3:
        st.write("")
        run_btn = st.button("▶ Run", type="primary", key="run_shock")

    run_all = st.button("▶▶ Run All Scenarios + CNLI + Reverse Stress", type="secondary", key="run_all")

    if run_btn:
        with st.spinner("Running 10,000 simulations..."):
            engine = MonteCarloEngine(baseline)
            result = engine.run_single(scenario_key, strategy_key)

        if result.is_live_event:
            st.warning("🔴 This is a LIVE EVENT scenario — results reflect real conditions as of March 2026")

        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("Revenue Delta (P50)", f"${result.revenue_delta_dist.get('p50',0):,.0f}M")
        with c2: st.metric("EBITDA Delta (P50)",  f"${result.ebitda_delta_dist.get('p50',0):,.0f}M")
        with c3: st.metric("P(Net Loss)",         f"{result.prob_net_loss*100:.1f}%")
        with c4: st.metric("NPV Advantage",       f"${result.strategy_npv_advantage_usd_m:+,.0f}M")

        cum = [q.cumulative_revenue_delta_usd_m for q in result.median_quarterly]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(len(cum))), y=cum,
                                 line=dict(color=COLOR_LIVE, width=2), name="Cumulative Rev Delta"))
        fig.add_hline(y=0, line_dash="dot", line_color="#8B949E")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", height=300,
                          xaxis_title="Quarter", yaxis_title="Cumulative Revenue Delta (USD M)",
                          margin=dict(l=20,r=20,t=10,b=20))
        st.plotly_chart(fig, use_container_width=True, key="shock_chart")

        rows = [{"Q": q.quarter,
                 "Revenue ($M)": f"${q.revenue_usd_m:,.0f}",
                 "EBITDA ($M)":  f"${q.ebitda_usd_m:,.0f}",
                 "Margin":       f"{q.ebitda_margin:.1%}",
                 "Cum Delta":    f"${q.cumulative_revenue_delta_usd_m:,.0f}M"}
                for q in result.median_quarterly]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    if run_all:
        with st.spinner("Running all scenarios × strategies + CNLI + Reverse Stress (~2 min)..."):
            engine  = MonteCarloEngine(baseline)
            results = engine.run_all()
            ranking = get_strategy_ranking(results)
            cnli    = engine.compute_cnli()
            rst     = engine.reverse_stress_test()
            json_p  = export_results_json(results)
            csv_p   = export_results_csv(results)

        st.success("✅ Complete")

        # CNLI
        st.markdown("### 📊 Compound Non-Linearity Index (CNLI)")
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("CNLI", f"{cnli.cnli:.3f}")
        with c2: st.metric("Non-Linearity Premium", f"+{cnli.non_linearity_premium_pct:.1f}%")
        with c3: st.metric("Compound vs Sum of Parts",
                           f"${cnli.compound_loss_usd_m:,.0f}M vs ${cnli.sum_individual_usd_m:,.0f}M")

        # Reverse stress
        st.markdown("### 🔬 Reverse Stress Test")
        st.info(rst.description)

        # Rankings
        st.markdown("### 🏆 Strategy Rankings")
        for s_key, ranked in ranking.items():
            lbl = SHOCK_SCENARIOS[s_key]["label"]
            live= " 🔴" if SHOCK_SCENARIOS[s_key].get("live_event") else ""
            with st.expander(f"{lbl}{live}"):
                rdf = pd.DataFrame([{
                    "Rank": i+1,
                    "Strategy": STRATEGIES[st]["label"],
                    "NPV Advantage": f"${npv:+,.0f}M"
                } for i,(st,npv) in enumerate(ranked)])
                st.dataframe(rdf, use_container_width=True)

        c1,c2 = st.columns(2)
        with c1:
            with open(json_p) as f:
                st.download_button("⬇ JSON", f.read(), "shock_results.json", "application/json")
        with c2:
            with open(csv_p) as f:
                st.download_button("⬇ CSV", f.read(), "shock_summary.csv", "text/csv")


# =============================================================================
# TAB 3: STOCK PREDICTOR
# =============================================================================

def render_stock_predictor(snapshot, history):
    st.markdown("## 📈 Maersk Stock Predictor")
    current = snapshot.get("tickers",{}).get("maersk_stock",{}).get("current") if snapshot else None
    if not current:
        st.warning("⏳ Waiting for Maersk stock data...")
        return

    maersk_rows = [r for r in history if r["field"]=="maersk_stock"]
    if len(maersk_rows) > 2:
        prices = np.array([r["value"] for r in maersk_rows])
        returns= np.diff(prices)/prices[:-1]
        vol    = float(np.std(returns))
        drift  = float(np.mean(returns))
    else:
        vol, drift = 0.012, 0.0002

    rng = np.random.default_rng(42)
    n   = 500

    def simulate(n_days, long_term=False):
        v = vol*1.3 if long_term else vol
        d = drift*0.8 if long_term else drift
        paths = np.zeros((n, n_days+1))
        paths[:,0] = current
        for day in range(1, n_days+1):
            paths[:,day] = paths[:,day-1] * (1 + rng.normal(d, v, n))
        return paths

    short_p = simulate(7)
    long_p  = simulate(90, long_term=True)

    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">Current Price</div>'
                    f'<div class="kpi-value">{current:,.0f}</div><div class="kpi-unit">DKK</div></div>',
                    unsafe_allow_html=True)
    with c2:
        t7 = np.percentile(short_p, 50, axis=0)[-1]
        chg= (t7-current)/current*100
        col= COLOR_POSITIVE if chg>=0 else COLOR_NEGATIVE
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">7-Day Target (P50)</div>'
                    f'<div class="kpi-value" style="color:{col}">{t7:,.0f}</div>'
                    f'<div class="kpi-unit">{chg:+.1f}%</div></div>', unsafe_allow_html=True)
    with c3:
        t90= np.percentile(long_p, 50, axis=0)[-1]
        chg= (t90-current)/current*100
        col= COLOR_POSITIVE if chg>=0 else COLOR_NEGATIVE
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">3-Month Target (P50)</div>'
                    f'<div class="kpi-value" style="color:{col}">{t90:,.0f}</div>'
                    f'<div class="kpi-unit">{chg:+.1f}%</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">Daily Volatility</div>'
                    f'<div class="kpi-value">{vol*100:.2f}%</div>'
                    f'<div class="kpi-unit">std dev of returns</div></div>', unsafe_allow_html=True)

    st.write("")
    for label, paths, key in [("7-Day", short_p, "7d"), ("3-Month", long_p, "3m")]:
        st.markdown(f"#### {label} Price Forecast (Monte Carlo Fan)")
        days = list(range(paths.shape[1]))
        fig  = go.Figure()
        for pct, opacity in [(95,0.08),(75,0.15)]:
            fig.add_trace(go.Scatter(x=days, y=np.percentile(paths,100-pct,axis=0),
                                     line=dict(width=0), showlegend=False))
            fig.add_trace(go.Scatter(x=days, y=np.percentile(paths,pct,axis=0),
                                     line=dict(width=0), fill="tonexty",
                                     fillcolor=f"rgba(0,229,255,{opacity})",
                                     name=f"P{100-pct}–P{pct}"))
        fig.add_trace(go.Scatter(x=days, y=np.percentile(paths,50,axis=0),
                                 line=dict(color=COLOR_LIVE, width=2.5), name="Median"))
        fig.add_hline(y=current, line_dash="dot", line_color="#8B949E", annotation_text="Current")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", height=320,
                          xaxis_title="Days", yaxis_title="Price (DKK)",
                          margin=dict(l=20,r=20,t=10,b=20))
        st.plotly_chart(fig, use_container_width=True, key=f"stock_{key}")

    st.caption("⚠️ Monte Carlo GBM simulation (500 paths). Not financial advice.")


# =============================================================================
# TAB 4: MANUAL UNCERTAINTY
# =============================================================================

def render_manual_uncertainty(baseline, intel):
    st.markdown("## 🎛️ Manual Uncertainty Tester")

    if intel:
        s_lbl = SHOCK_SCENARIOS[intel.get("most_likely_shock","demand_collapse")]["label"]
        st_lbl= STRATEGIES[intel.get("recommended_strategy","dynamic_pricing")]["label"]
        st.markdown(f"""
        <div class="alert-blue">
            <b>🤖 AI Recommendation</b> — based on live market data<br>
            📌 Most likely: <b>{s_lbl}</b> ({intel.get('shock_confidence',0)}% confidence)<br>
            ✅ Optimal strategy: <b>{st_lbl}</b>
        </div>""", unsafe_allow_html=True)
        if st.button("🤖 Load AI Suggestion"):
            shock = SHOCK_SCENARIOS[intel["most_likely_shock"]]
            st.session_state.update({
                "m_vol_lo":  shock["volume_impact"][0]*100,
                "m_vol_hi":  shock["volume_impact"][2]*100,
                "m_rate_lo": shock["freight_rate_impact"][0]*100,
                "m_rate_hi": shock["freight_rate_impact"][2]*100,
                "m_fuel_lo": shock["fuel_cost_impact"][0]*100,
                "m_fuel_hi": shock["fuel_cost_impact"][2]*100,
                "m_dur":     shock["duration_quarters"],
                "m_strat":   intel["recommended_strategy"],
            })

    st.markdown("---")
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**📦 Volume Impact (%)**")
        vol_lo = st.slider("Volume worst case (%)", -60, 0, int(st.session_state.get("m_vol_lo",-20)))
        vol_hi = st.slider("Volume best case (%)",  -20,20, int(st.session_state.get("m_vol_hi",0)))
        st.markdown("**🛢️ Fuel Cost Impact (%)**")
        fuel_lo= st.slider("Fuel best case (%)", -20, 10, int(st.session_state.get("m_fuel_lo",-5)))
        fuel_hi= st.slider("Fuel worst case (%)", 0,150, int(st.session_state.get("m_fuel_hi",30)))
    with c2:
        st.markdown("**🚢 Freight Rate Impact (%)**")
        rate_lo= st.slider("Rate worst case (%)", -50, 0, int(st.session_state.get("m_rate_lo",-15)))
        rate_hi= st.slider("Rate best case (%)", -10,80, int(st.session_state.get("m_rate_hi",5)))
        st.markdown("**⏱️ Duration + Strategy**")
        dur    = st.slider("Duration (quarters)", 1, 10, int(st.session_state.get("m_dur",4)))
        strat  = st.selectbox("Strategy", list(STRATEGIES.keys()),
                              format_func=lambda k: STRATEGIES[k]["label"],
                              index=list(STRATEGIES.keys()).index(
                                  st.session_state.get("m_strat","dynamic_pricing")))

    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("Volume", f"{vol_lo}% to {vol_hi}%")
    with c2: st.metric("Rate",   f"{rate_lo}% to {rate_hi}%")
    with c3: st.metric("Fuel",   f"{fuel_lo}% to {fuel_hi}%")
    with c4: st.metric("Duration", f"{dur} quarters")

    if st.button("▶ Run Custom Simulation", type="primary"):
        vol_m  = (vol_lo+vol_hi)/2
        rate_m = (rate_lo+rate_hi)/2
        fuel_m = (fuel_lo+fuel_hi)/2
        custom = {
            "label":               "Custom Scenario",
            "category":            "custom",
            "description":         "User-defined",
            "empirical_basis":     "Manual input",
            "volume_impact":       (vol_lo/100, vol_m/100, vol_hi/100),
            "freight_rate_impact": (rate_lo/100, rate_m/100, rate_hi/100),
            "fuel_cost_impact":    (fuel_lo/100, fuel_m/100, fuel_hi/100),
            "duration_quarters":   dur,
        }
        with st.spinner(f"Running {MONTE_CARLO_RUNS:,} simulations..."):
            import config as cfg
            cfg.SHOCK_SCENARIOS["_custom"] = custom
            engine = MonteCarloEngine(baseline)
            result = engine.run_single("_custom", strat)
            dn     = engine.run_single("_custom", "do_nothing")
            # Rank all strategies
            all_r  = {k: engine.run_single("_custom", k) for k in STRATEGIES}
            del cfg.SHOCK_SCENARIOS["_custom"]

        st.success("✅ Done")
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("Revenue Delta P50", f"${result.revenue_delta_dist.get('p50',0):,.0f}M")
        with c2: st.metric("EBITDA Delta P50",  f"${result.ebitda_delta_dist.get('p50',0):,.0f}M")
        with c3: st.metric("P(Net Loss)",        f"{result.prob_net_loss*100:.1f}%")
        with c4: st.metric("NPV vs Do Nothing",  f"${result.strategy_npv_advantage_usd_m:+,.0f}M")

        pcts = ["p5","p25","p50","p75","p95"]
        fig = go.Figure()
        fig.add_trace(go.Bar(name=STRATEGIES[strat]["label"],
                             x=pcts, y=[result.revenue_delta_dist.get(p,0) for p in pcts],
                             marker_color=COLOR_LIVE))
        fig.add_trace(go.Bar(name="Do Nothing",
                             x=pcts, y=[dn.revenue_delta_dist.get(p,0) for p in pcts],
                             marker_color=COLOR_NEUTRAL, opacity=0.6))
        fig.add_hline(y=0, line_dash="dot", line_color="#8B949E")
        fig.update_layout(template="plotly_dark", barmode="group",
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          height=300, margin=dict(l=20,r=20,t=10,b=20))
        st.plotly_chart(fig, use_container_width=True, key="manual_chart")

        ranked = sorted([(k, all_r[k].strategy_npv_advantage_usd_m)
                         for k in all_r if k!="do_nothing"], key=lambda x:x[1], reverse=True)
        st.markdown("#### 🏆 All Strategies Ranked for This Scenario")
        rdf = pd.DataFrame([{"Rank":i+1,"Strategy":STRATEGIES[k]["label"],
                              "NPV Advantage":f"${npv:+,.0f}M",
                              "P(Net Loss)":f"{all_r[k].prob_net_loss*100:.1f}%"}
                            for i,(k,npv) in enumerate(ranked)])
        st.dataframe(rdf, use_container_width=True)


# =============================================================================
# TAB 5: LIVE VALIDATION
# =============================================================================

def render_live_validation(baseline):
    st.markdown("## 🔴 Live Event Validation — Hormuz Crisis 2026")
    st.markdown("""
    This tab validates our shock engine against a live real-world event.
    The Strait of Hormuz closure began **28 February 2026** — our model was calibrated in FY2023.
    This is a genuine out-of-sample test of the digital twin's predictive accuracy.
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### What Actually Happened")
        for item in LIVE_EVENTS["hormuz_2026"]["maersk_response"]:
            st.markdown(f"• {item}")
        st.markdown(f"""
        <div class="alert-live">
            <b>Key facts (from Maersk.com, verified March 2026):</b><br>
            • Closure effective: 28 February 2026<br>
            • Brent crude peak: $126/barrel (8 March 2026)<br>
            • Both Hormuz AND Red Sea simultaneously blocked<br>
            • Maersk Emergency Bunker Surcharge introduced 25 March 2026<br>
            • QatarEnergy declared force majeure on all LNG 4 March 2026<br>
            • ~20% of world daily oil supply affected
        </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown("#### Model Validation")
        if st.button("▶ Run Hormuz Shock Validation", type="primary"):
            with st.spinner("Running validation simulation..."):
                engine = MonteCarloEngine(baseline)
                val    = engine.validate_against_live_event("hormuz_2026")
                result_base = engine.run_single("hormuz_closure", "do_nothing")
                result_comp = engine.run_single("hormuz_demand_compound", "do_nothing")

            st.markdown(f"""
            <div class="alert-blue">
                <b>Model Prediction (G08 Hormuz Closure, do nothing):</b><br>
                P50 Revenue Delta: <b>${result_base.revenue_delta_dist.get('p50',0):,.0f}M</b><br>
                P5 Revenue Delta (worst case): <b>${result_base.revenue_delta_dist.get('p5',0):,.0f}M</b><br>
                P(Net Loss): <b>{result_base.prob_net_loss*100:.1f}%</b>
            </div>""", unsafe_allow_html=True)

            st.markdown(f"""
            <div class="alert-warning">
                <b>Compound Scenario (Hormuz + Recession cascade):</b><br>
                P50 Revenue Delta: <b>${result_comp.revenue_delta_dist.get('p50',0):,.0f}M</b><br>
                P(Net Loss): <b>{result_comp.prob_net_loss*100:.1f}%</b><br>
                <small>At actual Brent $126 (vs model baseline $85), fuel costs are ~1.5× model assumption.
                True impact likely exceeds base model prediction.</small>
            </div>""", unsafe_allow_html=True)

            st.info(val.get("validation_note",""))

            # Strategy comparison for this live shock
            st.markdown("#### Optimal Strategies for Live Hormuz Scenario")
            with st.spinner("Ranking all strategies..."):
                strat_results = {k: engine.run_single("hormuz_closure", k) for k in STRATEGIES}
            ranked = sorted(strat_results.items(),
                            key=lambda x: x[1].strategy_npv_advantage_usd_m, reverse=True)
            rdf = pd.DataFrame([{
                "Strategy": STRATEGIES[k]["label"],
                "NPV Advantage": f"${r.strategy_npv_advantage_usd_m:+,.0f}M",
                "P(Net Loss)": f"{r.prob_net_loss*100:.1f}%",
                "Real-World Cadence": STRATEGIES[k].get("real_world_cadence","")
            } for k,r in ranked if k!="do_nothing"])
            st.dataframe(rdf, use_container_width=True)


# =============================================================================
# MAIN
# =============================================================================

def main():
    render_sidebar()
    snapshot = get_latest_snapshot()
    history  = get_history(minutes=SPARKLINE_MINUTES)
    baseline = get_current_baseline()
    intel    = market_intelligence(snapshot, baseline)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🚢 Live Twin", "⚡ Shock Engine",
        "📈 Stock Predictor", "🎛️ Manual Uncertainty",
        "🔴 Live Validation"
    ])
    with tab1: render_live_twin(snapshot, history, baseline, intel)
    with tab2: render_shock_engine(baseline)
    with tab3: render_stock_predictor(snapshot, history)
    with tab4: render_manual_uncertainty(baseline, intel)
    with tab5: render_live_validation(baseline)


if __name__ == "__main__":
    main()
