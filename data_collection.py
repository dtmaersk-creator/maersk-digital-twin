# =============================================================================
# data_collection.py v2.0 — Maersk Digital Twin: Live Data Pipeline
# =============================================================================

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from config import (
    DB_PATH, FEED_STALE_THRESHOLD_SECONDS, FINNHUB_API_KEY,
    HISTORY_DAYS, MAERSK_YAHOO_SYMBOL, SNAPSHOT_JSON, YAHOO_TICKERS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("data_collection")
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}


# =============================================================================
# Database
# =============================================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL, source TEXT NOT NULL,
            field TEXT NOT NULL, value REAL, quality REAL DEFAULT 1.0)
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feed_health (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL, source TEXT NOT NULL,
            status TEXT NOT NULL, latency_ms REAL, detail TEXT)
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_snap_ts ON market_snapshots(timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_snap_field ON market_snapshots(field, timestamp DESC)")
    conn.commit()
    conn.close()
    log.info("DB ready: %s", DB_PATH)


def purge_old_records():
    cutoff = (datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM market_snapshots WHERE timestamp < ?", (cutoff,))
    conn.execute("DELETE FROM feed_health WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()


# =============================================================================
# Yahoo Finance fetcher
# =============================================================================

def fetch_yahoo(symbol: str, label: str) -> dict | None:
    try:
        t0  = time.time()
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
        resp = requests.get(url, headers=YAHOO_HEADERS, timeout=10)
        resp.raise_for_status()
        data      = resp.json()
        latency_ms= (time.time() - t0) * 1000
        result    = data.get("chart", {}).get("result", [])
        if not result:
            return None
        meta      = result[0].get("meta", {})
        current   = meta.get("regularMarketPrice")
        prev_close= meta.get("chartPreviousClose") or meta.get("previousClose")
        if not current:
            return None
        pct = ((current - prev_close) / prev_close * 100) if prev_close else 0
        return {
            "c":  current, "pc": prev_close or current,
            "h":  meta.get("regularMarketDayHigh", current),
            "l":  meta.get("regularMarketDayLow",  current),
            "dp": round(pct, 2),
            "_latency_ms": latency_ms, "_source": "yahoo",
        }
    except Exception as exc:
        log.error("Yahoo error [%s]: %s", label, exc)
        return None


def fetch_maersk_yahoo() -> dict | None:
    return fetch_yahoo(MAERSK_YAHOO_SYMBOL, "maersk_stock")


def fetch_all_tickers() -> dict:
    results = {}
    results["maersk_stock"] = fetch_yahoo(MAERSK_YAHOO_SYMBOL, "maersk_stock")
    time.sleep(0.3)
    for key, symbol in YAHOO_TICKERS.items():
        results[key] = fetch_yahoo(symbol, key)
        time.sleep(0.3)
    return results


# =============================================================================
# FBX freight rate (daily)
# =============================================================================

def get_latest_fbx_from_db() -> dict | None:
    try:
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.execute(
            "SELECT value, timestamp FROM market_snapshots "
            "WHERE field='fbx_composite' ORDER BY timestamp DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        return {"fbx_composite": row[0], "fbx_date": row[1]} if row else None
    except Exception:
        return None


# =============================================================================
# Data quality
# =============================================================================

def compute_quality(ticker_results: dict) -> float:
    core_keys = {"maersk_stock", "brent_crude", "usd_dkk"}
    aux_keys  = set(ticker_results.keys()) - core_keys
    core_hits = sum(1 for k in core_keys if ticker_results.get(k))
    aux_hits  = sum(1 for k in aux_keys  if ticker_results.get(k))
    return round((core_hits / len(core_keys)) * 0.70 +
                 (aux_hits  / max(len(aux_keys), 1)) * 0.30, 4)


# =============================================================================
# Persistence
# =============================================================================

def save_snapshot(timestamp: str, ticker_results: dict, fbx: dict | None, quality: float):
    conn = sqlite3.connect(DB_PATH)
    rows = []
    for key, q in ticker_results.items():
        if q:
            rows += [
                (timestamp, "yahoo", key,           q["c"],          quality),
                (timestamp, "yahoo", f"{key}_pct",  q.get("dp", 0),  quality),
                (timestamp, "yahoo", f"{key}_high",  q.get("h", q["c"]), quality),
                (timestamp, "yahoo", f"{key}_low",   q.get("l", q["c"]), quality),
            ]
    if fbx and fbx.get("fbx_composite"):
        rows.append((timestamp, "freightos", "fbx_composite", fbx["fbx_composite"], 1.0))
    conn.executemany(
        "INSERT INTO market_snapshots (timestamp,source,field,value,quality) VALUES(?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def save_feed_health(timestamp: str, ticker_results: dict):
    conn = sqlite3.connect(DB_PATH)
    rows = [(timestamp, key, "ok" if q else "error", q.get("_latency_ms", 0) if q else 0, None)
            for key, q in ticker_results.items()]
    conn.executemany(
        "INSERT INTO feed_health (timestamp,source,status,latency_ms,detail) VALUES(?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def write_snapshot_json(timestamp: str, ticker_results: dict, fbx: dict | None, quality: float):
    snap = {"timestamp": timestamp, "quality": quality, "tickers": {}, "fbx": fbx}
    for key, q in ticker_results.items():
        if q:
            snap["tickers"][key] = {
                "current":    q["c"],   "pct_change": q.get("dp", 0),
                "high":       q.get("h", q["c"]),  "low": q.get("l", q["c"]),
                "prev_close": q.get("pc", q["c"]),
            }
    with open(SNAPSHOT_JSON, "w") as f:
        json.dump(snap, f, indent=2)


# =============================================================================
# Master fetch
# =============================================================================

def fetch_all():
    timestamp = datetime.now(timezone.utc).isoformat()
    log.info("Fetch cycle — %s", timestamp)

    ticker_results = fetch_all_tickers()
    fbx = get_latest_fbx_from_db()
    quality = compute_quality(ticker_results)

    if quality < 0.5:
        log.warning("Degraded quality: %.2f", quality)

    save_snapshot(timestamp, ticker_results, fbx, quality)
    save_feed_health(timestamp, ticker_results)
    write_snapshot_json(timestamp, ticker_results, fbx, quality)

    ok = sum(1 for v in ticker_results.values() if v)
    log.info("Done — quality=%.2f | %d/%d feeds ok", quality, ok, len(ticker_results))

    fetch_all._count = getattr(fetch_all, "_count", 0) + 1
    if fetch_all._count % 100 == 0:
        purge_old_records()


# =============================================================================
# Public API
# =============================================================================

def get_latest_snapshot() -> dict | None:
    if os.path.exists(SNAPSHOT_JSON):
        with open(SNAPSHOT_JSON) as f:
            return json.load(f)
    return None


def get_history(minutes: int = 60) -> list:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.execute(
        "SELECT timestamp,field,value FROM market_snapshots WHERE timestamp>=? ORDER BY timestamp ASC",
        (cutoff,))
    rows = [{"timestamp": r[0], "field": r[1], "value": r[2]} for r in cur.fetchall()]
    conn.close()
    return rows


def get_feed_health() -> list:
    try:
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.execute(
            "SELECT source,status,latency_ms,timestamp FROM feed_health "
            "WHERE timestamp=(SELECT MAX(timestamp) FROM feed_health) ORDER BY source")
        rows = [{"source": r[0], "status": r[1], "latency_ms": r[2], "timestamp": r[3]}
                for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


# =============================================================================
# Scheduler
# =============================================================================

def start_pipeline():
    from config import FETCH_INTERVAL_SECONDS
    init_db()
    fetch_all()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(fetch_all, trigger="interval", seconds=FETCH_INTERVAL_SECONDS,
                      id="live_feed", max_instances=1, coalesce=True)
    scheduler.start()
    log.info("Pipeline started — %ds interval", FETCH_INTERVAL_SECONDS)
    return scheduler


if __name__ == "__main__":
    s = start_pipeline()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        s.shutdown()
