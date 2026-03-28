# =============================================================================
# auto_updater.py v2.0 — Maersk Digital Twin: Baseline Updater
# =============================================================================

import json
import logging
import os
import time
from datetime import datetime, timezone

import finnhub
import requests
from apscheduler.schedulers.background import BackgroundScheduler

from config import BASELINE, FINNHUB_API_KEY, SNAPSHOT_JSON

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("auto_updater")

BASELINE_STATE_FILE = "baseline_state.json"
finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)


def load_baseline_state() -> dict:
    if os.path.exists(BASELINE_STATE_FILE):
        with open(BASELINE_STATE_FILE) as f:
            return json.load(f)
    return dict(BASELINE)


def save_baseline_state(state: dict):
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(BASELINE_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_maersk_fundamentals() -> dict | None:
    try:
        data = finnhub_client.company_basic_financials("CPH:MAERSK-B", "all")
        if not data or "metric" not in data:
            return None
        m = data["metric"]
        return {
            "revenue_ttm":          m.get("revenueTTM"),
            "ebitda_ttm":           m.get("ebitdaTTM"),
            "net_income_ttm":       m.get("netIncomeTTM"),
            "total_debt":           m.get("totalDebt"),
            "cash_and_equivalents": m.get("cashAndEquivalentsTotal"),
            "total_assets":         m.get("totalAssets"),
            "ebitda_margin":        m.get("ebitdaMarginAnnual"),
            "net_margin":           m.get("netProfitMarginAnnual"),
            "roe":                  m.get("roeRfy"),
            "current_ratio":        m.get("currentRatioAnnual"),
            "debt_to_equity":       m.get("totalDebt/totalEquityAnnual"),
        }
    except Exception as exc:
        log.error("Fundamentals error: %s", exc)
        return None


def compute_fuel_cost_adjustment(state: dict) -> float:
    """
    Adjust fuel cost using live Brent price via VLSFO-Brent correlation (r=0.85).
    At Brent $126 (Hormuz 2026 peak): fuel cost ≈ +50% above FY2023 baseline.
    """
    BASELINE_BRENT = 85.0
    BASELINE_FUEL  = state.get("fuel_cost_usd_m", BASELINE["fuel_cost_usd_m"])
    CORRELATION    = 0.85
    try:
        if os.path.exists(SNAPSHOT_JSON):
            snap = json.load(open(SNAPSHOT_JSON))
            live_brent = snap.get("tickers", {}).get("brent_crude", {}).get("current")
            if live_brent and live_brent > 0:
                ratio       = live_brent / BASELINE_BRENT
                adjustment  = 1 + (ratio - 1) * CORRELATION
                adjusted    = round(BASELINE_FUEL * adjustment, 1)
                log.info("Fuel adjusted: $%.0fM (Brent $%.1f vs baseline $%.1f)",
                         adjusted, live_brent, BASELINE_BRENT)
                return adjusted
    except Exception as exc:
        log.warning("Fuel adjustment failed: %s", exc)
    return BASELINE_FUEL


def compute_fx_adjustment(state: dict) -> dict:
    BASELINE_USD_DKK = 6.90
    DKK_COST_SHARE   = 0.15
    try:
        if os.path.exists(SNAPSHOT_JSON):
            snap = json.load(open(SNAPSHOT_JSON))
            live_fx = snap.get("tickers", {}).get("usd_dkk", {}).get("current")
            if live_fx and live_fx > 0:
                opex       = state.get("revenue_usd_m", BASELINE["revenue_usd_m"]) * 0.70
                fx_ratio   = BASELINE_USD_DKK / live_fx
                fx_impact  = opex * DKK_COST_SHARE * (fx_ratio - 1)
                return {"fx_opex_adjustment_usd_m": round(fx_impact, 1),
                        "live_usd_dkk": live_fx}
    except Exception as exc:
        log.warning("FX adjustment failed: %s", exc)
    return {}


def detect_live_events(state: dict) -> list:
    """
    Check live market data against known live event thresholds.
    Returns list of active event keys.
    """
    from config import LIVE_EVENTS
    active = []
    try:
        if os.path.exists(SNAPSHOT_JSON):
            snap = json.load(open(SNAPSHOT_JSON))
            brent = snap.get("tickers", {}).get("brent_crude", {}).get("current", 0)
            if brent > 100:
                active.append("hormuz_2026")
                log.warning("LIVE EVENT DETECTED: Brent $%.1f > $100 — Hormuz crisis conditions", brent)
    except Exception:
        pass
    return active


def update_baseline() -> dict:
    log.info("=== Baseline update starting ===")
    state = load_baseline_state()

    fundamentals = fetch_maersk_fundamentals()
    if fundamentals:
        if fundamentals.get("revenue_ttm"):
            state["revenue_usd_m"]      = round(fundamentals["revenue_ttm"] / 1e6, 1)
        if fundamentals.get("ebitda_ttm"):
            state["ebitda_usd_m"]       = round(fundamentals["ebitda_ttm"] / 1e6, 1)
        if fundamentals.get("net_income_ttm"):
            state["net_income_usd_m"]   = round(fundamentals["net_income_ttm"] / 1e6, 1)
        if fundamentals.get("total_debt"):
            state["total_debt_usd_m"]   = round(fundamentals["total_debt"] / 1e6, 1)
        if fundamentals.get("cash_and_equivalents"):
            state["cash_usd_m"]         = round(fundamentals["cash_and_equivalents"] / 1e6, 1)
        if fundamentals.get("total_assets"):
            state["total_assets_usd_m"] = round(fundamentals["total_assets"] / 1e6, 1)
        for k in ["ebitda_margin","net_margin","roe","current_ratio","debt_to_equity"]:
            if fundamentals.get(k):
                state[k] = fundamentals[k]
        log.info("Fundamentals updated from Finnhub")

    state["fuel_cost_usd_m"] = compute_fuel_cost_adjustment(state)
    state.update(compute_fx_adjustment(state))
    state["active_live_events"] = detect_live_events(state)

    save_baseline_state(state)
    log.info("=== Baseline update complete ===")
    return state


def get_current_baseline() -> dict:
    return load_baseline_state()


def start_updater():
    update_baseline()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(update_baseline, trigger="interval", hours=24,
                      id="baseline_updater", max_instances=1, coalesce=True)
    scheduler.start()
    log.info("Baseline updater started — 24h refresh")
    return scheduler


if __name__ == "__main__":
    state = update_baseline()
    print("\n=== Current Baseline ===")
    for k, v in state.items():
        print(f"  {k:<35} {v}")
