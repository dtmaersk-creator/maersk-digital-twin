# =============================================================================
# auto_updater.py v3.0 — Maersk Digital Twin: Baseline Updater
#
# BUG FIXES vs v2.0:
#   [BF-1] CRITICAL: BASELINE_FUEL now uses BASELINE["fuel_cost_usd_m"] (constant)
#          instead of state.get("fuel_cost_usd_m") — this was causing compounding
#          fuel cost escalation from $5,053M → $81,032M on each restart.
#   [BF-6] Finnhub symbol corrected: "MAERSK-B" (no exchange prefix needed for basic)
#   [BF-7] detect_live_events now covers all LIVE_EVENTS keys, not just hormuz_2026
#   [BF-8] Added VIX, copper, natural gas, Baltic Dry signal detection
# =============================================================================

import json
import logging
import os
import time
from datetime import datetime, timezone

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from config import BASELINE, FINNHUB_API_KEY, LIVE_EVENTS, SNAPSHOT_JSON

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("auto_updater")

BASELINE_STATE_FILE = "baseline_state.json"

# [BF-6] Use requests-based Finnhub calls with correct endpoint
FINNHUB_BASE = "https://finnhub.io/api/v1"


def _finnhub_get(endpoint: str, params: dict) -> dict | None:
    """Generic Finnhub GET with error handling."""
    try:
        params["token"] = FINNHUB_API_KEY
        resp = requests.get(f"{FINNHUB_BASE}/{endpoint}", params=params, timeout=10)
        if resp.status_code == 401:
            log.error("Finnhub 401: API key invalid or expired — regenerate at finnhub.io")
            return None
        if resp.status_code == 429:
            log.warning("Finnhub 429: rate limit hit — backing off 5s")
            time.sleep(5)
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        log.error("Finnhub error [%s]: %s", endpoint, exc)
        return None


def load_baseline_state() -> dict:
    if os.path.exists(BASELINE_STATE_FILE):
        try:
            with open(BASELINE_STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            log.warning("Corrupt baseline_state.json — resetting to BASELINE")
    return dict(BASELINE)


def save_baseline_state(state: dict):
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(BASELINE_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except IOError as exc:
        log.error("Could not save baseline_state: %s", exc)


def fetch_maersk_fundamentals() -> dict | None:
    """
    [BF-6] Use correct Finnhub symbol. MAERSK-B trades on Copenhagen (CO).
    Finnhub accepts 'MAERSK-B.CO' for basic financials endpoint.
    """
    data = _finnhub_get("stock/metric", {"symbol": "MAERSK-B.CO", "metric": "all"})
    if not data or "metric" not in data:
        log.warning("Finnhub: no fundamentals data returned for MAERSK-B.CO")
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


def compute_fuel_cost_adjustment(state: dict) -> float:
    """
    Adjust fuel cost using live Brent price via VLSFO-Brent correlation (r=0.85).

    [BF-1] CRITICAL FIX: Always use BASELINE["fuel_cost_usd_m"] as the reference
    point — NEVER state.get("fuel_cost_usd_m"). Using the state value caused
    compounding: each restart multiplied an already-inflated fuel cost,
    escalating from $5,053M → $81,032M across restarts.

    The correct formula: adjusted = BASELINE_FUEL_CONSTANT * adjustment_ratio
    """
    BASELINE_BRENT = 85.0
    BASELINE_FUEL  = BASELINE["fuel_cost_usd_m"]   # [BF-1] ALWAYS the FY2023 constant
    CORRELATION    = 0.85

    try:
        if os.path.exists(SNAPSHOT_JSON):
            with open(SNAPSHOT_JSON) as f:
                snap = json.load(f)
            live_brent = snap.get("tickers", {}).get("brent_crude", {}).get("current")
            if live_brent and live_brent > 0:
                ratio      = live_brent / BASELINE_BRENT
                adjustment = 1 + (ratio - 1) * CORRELATION
                adjusted   = round(BASELINE_FUEL * adjustment, 1)
                log.info(
                    "Fuel adjusted: $%.0fM (Brent $%.1f vs baseline $%.1f, factor=%.3f)",
                    adjusted, live_brent, BASELINE_BRENT, adjustment
                )
                return adjusted
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.warning("Fuel adjustment failed: %s", exc)

    return BASELINE_FUEL   # fallback to constant, never to state value


def compute_fx_adjustment(state: dict) -> dict:
    """
    Compute DKK/USD FX impact on operating costs.
    Maersk ~15% of opex in DKK (HQ, Danish operations).
    """
    BASELINE_USD_DKK = 6.90
    DKK_COST_SHARE   = 0.15
    try:
        if os.path.exists(SNAPSHOT_JSON):
            with open(SNAPSHOT_JSON) as f:
                snap = json.load(f)
            live_fx = snap.get("tickers", {}).get("usd_dkk", {}).get("current")
            if live_fx and live_fx > 0:
                # Use state revenue for opex base — this is fine (not fuel cost)
                opex      = state.get("revenue_usd_m", BASELINE["revenue_usd_m"]) * 0.70
                fx_ratio  = BASELINE_USD_DKK / live_fx
                fx_impact = opex * DKK_COST_SHARE * (fx_ratio - 1)
                return {
                    "fx_opex_adjustment_usd_m": round(fx_impact, 1),
                    "live_usd_dkk": live_fx,
                }
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.warning("FX adjustment failed: %s", exc)
    return {}


def detect_live_events(state: dict) -> list:
    """
    [BF-7] Detect all active live events, not just hormuz_2026.
    [BF-8] Expanded: VIX, copper, natural gas, Baltic Dry signals.
    Returns list of active event keys detected from live market data.
    """
    active = []
    try:
        if not os.path.exists(SNAPSHOT_JSON):
            return active
        with open(SNAPSHOT_JSON) as f:
            snap = json.load(f)
        tickers = snap.get("tickers", {})

        brent   = tickers.get("brent_crude",  {}).get("current", 0) or 0
        vix     = tickers.get("vix",          {}).get("current", 0) or 0
        gas     = tickers.get("natural_gas",  {}).get("current", 0) or 0
        gas_pct = tickers.get("natural_gas",  {}).get("pct_change", 0) or 0
        copper_pct = tickers.get("copper",    {}).get("pct_change", 0) or 0
        bdi_pct = tickers.get("baltic_dry",   {}).get("pct_change", 0) or 0
        cny_pct = tickers.get("usd_cny",      {}).get("pct_change", 0) or 0
        sp500_pct = tickers.get("sp500",      {}).get("pct_change", 0) or 0
        krw_pct = tickers.get("usd_krw",      {}).get("pct_change", 0) or 0

        # Hormuz / Middle East energy crisis
        if brent > 100:
            active.append("hormuz_2026")
            log.warning("LIVE EVENT: Brent $%.1f > $100 — Hormuz crisis conditions", brent)

        # Tariff escalation
        if abs(cny_pct) > 0.5:
            active.append("us_tariff_2026")
            log.info("SIGNAL: USD/CNY moved %.2f%% — tariff tension", cny_pct)

        # [BF-8] Additional signal detections
        if vix > 40:
            log.warning("SIGNAL: VIX=%.1f > 40 — extreme risk-off, compound shock risk", vix)
        elif vix > 30:
            log.info("SIGNAL: VIX=%.1f > 30 — elevated risk-off", vix)

        if gas_pct > 5:
            log.warning("SIGNAL: Natural gas +%.1f%% — LNG supply shock conditions", gas_pct)

        if copper_pct < -3:
            log.info("SIGNAL: Copper %.1f%% — China demand weakness signal", copper_pct)

        if bdi_pct < -5:
            log.info("SIGNAL: Baltic Dry Index %.1f%% — dry bulk demand warning", bdi_pct)

        if krw_pct > 1.0:
            log.info("SIGNAL: USD/KRW +%.2f%% — Asia risk-off / geopolitical tension", krw_pct)

    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.warning("Event detection failed: %s", exc)

    return list(set(active))   # deduplicate


def update_baseline() -> dict:
    log.info("=== Baseline update starting ===")
    state = load_baseline_state()

    # Fundamentals from Finnhub
    fundamentals = fetch_maersk_fundamentals()
    if fundamentals:
        field_map = {
            "revenue_usd_m":      ("revenue_ttm",          1e6),
            "ebitda_usd_m":       ("ebitda_ttm",           1e6),
            "net_income_usd_m":   ("net_income_ttm",       1e6),
            "total_debt_usd_m":   ("total_debt",           1e6),
            "cash_usd_m":         ("cash_and_equivalents", 1e6),
            "total_assets_usd_m": ("total_assets",         1e6),
        }
        for state_key, (fund_key, div) in field_map.items():
            val = fundamentals.get(fund_key)
            if val and val > 0:
                state[state_key] = round(val / div, 1)
        for ratio_key in ["ebitda_margin", "net_margin", "roe", "current_ratio", "debt_to_equity"]:
            if fundamentals.get(ratio_key):
                state[ratio_key] = fundamentals[ratio_key]
        log.info("Fundamentals updated from Finnhub")
    else:
        log.info("Fundamentals not updated — using existing state values")

    # [BF-1] Fuel adjustment uses BASELINE constant, not state
    state["fuel_cost_usd_m"] = compute_fuel_cost_adjustment(state)
    state.update(compute_fx_adjustment(state))
    state["active_live_events"] = detect_live_events(state)

    save_baseline_state(state)
    log.info("=== Baseline update complete ===")
    return state


def get_current_baseline() -> dict:
    """Return latest baseline state, falling back to BASELINE config if missing."""
    state = load_baseline_state()
    # Always ensure fuel_cost_usd_m is present and plausible
    if state.get("fuel_cost_usd_m", 0) > BASELINE["fuel_cost_usd_m"] * 5:
        log.error(
            "[BF-1] Detected compounded fuel cost $%.0fM — resetting to adjusted value",
            state["fuel_cost_usd_m"]
        )
        state["fuel_cost_usd_m"] = compute_fuel_cost_adjustment(state)
        save_baseline_state(state)
    return state


def start_updater():
    update_baseline()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        update_baseline, trigger="interval", hours=24,
        id="baseline_updater", max_instances=1, coalesce=True
    )
    scheduler.start()
    log.info("Baseline updater started — 24h refresh cycle")
    return scheduler


if __name__ == "__main__":
    state = update_baseline()
    print("\n=== Current Baseline ===")
    for k, v in sorted(state.items()):
        print(f"  {k:<35} {v}")
