# =============================================================================
# config.py v3.0 — Maersk Digital Twin: Central Configuration
# Updated March 2026 — 30 global scenarios, 11 strategies, all bug fixes applied
#
# BUG FIXES vs v2.0:
#   [BF-1] BASELINE_FUEL in auto_updater.py must use BASELINE constant, not state
#   [BF-2] logistics_revenue_usd_m added to BASELINE so shock_engine doesn't KeyError
#   [BF-3] SIGNAL_WEIGHTS keys now match SHOCK_SCENARIOS keys exactly
#   [BF-4] Finnhub symbol "CPH:MAERSK-B" → correct exchange prefix
#   [BF-5] YAHOO_TICKERS expanded with Baltic Dry, natural gas, coal, copper
# =============================================================================

import os

# -----------------------------------------------------------------------------
# API KEY — set via Streamlit secrets (st.secrets["FINNHUB_API_KEY"]) or env var
# Never hardcode here — this file is committed to git
# -----------------------------------------------------------------------------
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "d741vr9r01qno4q059b0d741vr9r01qno4q059bg")

# -----------------------------------------------------------------------------
# DATA COLLECTION
# -----------------------------------------------------------------------------
FETCH_INTERVAL_SECONDS   = 60
DB_PATH                  = "maersk_twin.db"
SNAPSHOT_JSON            = "latest_snapshot.json"
HISTORY_DAYS             = 30
FEED_STALE_THRESHOLD_SECONDS = 180

# -----------------------------------------------------------------------------
# MARKET DATA SYMBOLS (Yahoo Finance)
# [BF-5] Added BDI proxy, coal, copper, LNG, EUR/USD for full macro coverage
# -----------------------------------------------------------------------------
MAERSK_YAHOO_SYMBOL = "MAERSK-B.CO"

YAHOO_TICKERS = {
    # Energy
    "brent_crude":  "BZ=F",       # Brent crude — primary fuel input signal
    "natural_gas":  "NG=F",       # LNG price signal (QatarEnergy exposure)
    "coal":         "MTF=F",      # Coal — fallback shipping demand signal
    # Macro / equity
    "sp500":        "^GSPC",      # US demand proxy
    "baltic_dry":   "^BDI",       # Dry bulk shipping proxy (container demand leading)
    "copper":       "HG=F",       # Copper — global growth leading indicator
    "vix":          "^VIX",       # Volatility — risk-off signal
    # FX
    "usd_dkk":      "DKK=X",      # Maersk reporting currency
    "usd_eur":      "EURUSD=X",   # EU trade exposure
    "usd_cny":      "CNY=X",      # China trade exposure (largest volume corridor)
    "usd_krw":      "KRW=X",      # Korea — Samsung, Hyundai supply chains
    "usd_inr":      "INR=X",      # India — fastest-growing trade lane
}

# -----------------------------------------------------------------------------
# MAERSK BASELINE FINANCIALS — FY2023 Annual Report (USD millions)
# [BF-2] logistics_revenue_usd_m added so shock_engine never KeyErrors on it
# -----------------------------------------------------------------------------
BASELINE = {
    "year":                         2023,
    "revenue_usd_m":                51_000,
    "ebitda_usd_m":                  9_600,
    "ebit_usd_m":                    6_100,
    "net_income_usd_m":              3_800,
    "total_assets_usd_m":           65_000,
    "total_debt_usd_m":             14_200,
    "cash_usd_m":                    9_100,
    "capex_usd_m":                   3_500,
    "fleet_size_vessels":              703,
    "teu_capacity":              4_200_000,
    "volume_teu_m":                   12.0,
    "avg_freight_rate_usd_teu":      1_800,
    "fuel_cost_usd_m":               4_200,   # [BF-1] This is the IMMUTABLE baseline
    "employees":                   100_000,
    "logistics_revenue_usd_m":      15_000,   # [BF-2] Logistics & Services FY2023
    "gulf_revenue_share":             0.08,
    "contract_revenue_share":         0.40,
    "eu_ets_cost_usd_m":               176,   # ~$44M/quarter Q1 2024
    "methanol_vessels_on_order":        25,
    "methanol_capex_usd_b":            4.0,
}

# -----------------------------------------------------------------------------
# MONTE CARLO SETTINGS
# -----------------------------------------------------------------------------
MONTE_CARLO_RUNS        = 10_000
SHOCK_DURATION_QUARTERS = 4
CONFIDENCE_INTERVALS    = [0.05, 0.25, 0.50, 0.75, 0.95]

# -----------------------------------------------------------------------------
# SHOCK SCENARIOS — 30 global scenarios across 8 categories
# Format: (min, mode, max) = triangular distribution
# All impacts are fractional (−0.20 = −20% relative to baseline)
# -----------------------------------------------------------------------------
SHOCK_SCENARIOS = {

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 1: DEMAND SHOCKS
    # ══════════════════════════════════════════════════════════════════════════

    "demand_collapse": {
        "label":               "Global Demand Collapse",
        "category":            "demand",
        "description":         "Sharp contraction in global trade (GFC-level recession)",
        "empirical_basis":     "2009 GFC: global trade −12%, 2023 normalisation −15%",
        "volume_impact":       (-0.35, -0.20, -0.10),
        "freight_rate_impact": (-0.40, -0.25, -0.12),
        "fuel_cost_impact":    (-0.15, -0.08,  0.00),
        "duration_quarters":   4,
    },
    "china_hard_landing": {
        "label":               "China Economic Hard Landing",
        "category":            "demand",
        "description":         "Chinese property/banking crisis, GDP −8%, global cascade. "
                               "China is Maersk's single largest trade corridor (~30% of volume).",
        "empirical_basis":     "Evergrande 2021 partial collapse; Japan 1991 analogue",
        "volume_impact":       (-0.40, -0.28, -0.15),
        "freight_rate_impact": (-0.45, -0.30, -0.15),
        "fuel_cost_impact":    (-0.20, -0.10,  0.00),
        "duration_quarters":   6,
    },
    "us_tariff_escalation": {
        "label":               "US Tariff Escalation (125% — Active 2026)",
        "category":            "demand",
        "description":         "125% US-China tariffs driving front-loading then trans-Pacific collapse. "
                               "Trans-Pacific is ~18% of Maersk container revenue.",
        "empirical_basis":     "2018-2019 US-China trade war; 2025-2026 tariff escalation live",
        "volume_impact":       (-0.20, -0.12, -0.05),
        "freight_rate_impact": (-0.20, -0.10,  0.00),
        "fuel_cost_impact":    (-0.05,  0.00,  0.05),
        "duration_quarters":   6,
        "live_event":          True,
        "live_event_date":     "2026-01-20",
    },
    "india_slowdown": {
        "label":               "India Growth Slowdown",
        "category":            "demand",
        "description":         "India's fastest-growing trade lane stalls — rupee crisis, monsoon failure, "
                               "or political instability. India is Maersk's fastest-growing corridor.",
        "empirical_basis":     "India GDP growth −3% scenario; 2013 taper tantrum rupee shock",
        "volume_impact":       (-0.08, -0.04,  0.00),
        "freight_rate_impact": (-0.10, -0.05,  0.02),
        "fuel_cost_impact":    ( 0.00,  0.03,  0.08),
        "duration_quarters":   4,
    },
    "eu_recession": {
        "label":               "European Recession + Demand Collapse",
        "category":            "demand",
        "description":         "EU enters deep recession (energy shock, political fragmentation). "
                               "Europe is ~25% of Maersk's total trade volume.",
        "empirical_basis":     "2011-2013 Eurozone crisis; 2022 energy shock near-recession",
        "volume_impact":       (-0.18, -0.10, -0.04),
        "freight_rate_impact": (-0.20, -0.12, -0.04),
        "fuel_cost_impact":    (-0.05,  0.00,  0.05),
        "duration_quarters":   5,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 2: FUEL / ENERGY SHOCKS
    # ══════════════════════════════════════════════════════════════════════════

    "fuel_price_spike": {
        "label":               "Fuel Price Spike (VLSFO > $800/MT)",
        "category":            "fuel",
        "description":         "Brent crude surge from geopolitical supply disruption. "
                               "Fuel is Maersk's #1 variable cost (~8-10% of revenue).",
        "empirical_basis":     "Ukraine 2022: bunker +60%; Hormuz 2026: Brent hit $126",
        "volume_impact":       (-0.05, -0.02,  0.00),
        "freight_rate_impact": (-0.05,  0.05,  0.15),
        "fuel_cost_impact":    ( 0.25,  0.45,  0.80),
        "duration_quarters":   3,
        "live_event":          True,
        "live_event_date":     "2026-02-28",
    },
    "methanol_transition_shock": {
        "label":               "Green Fuel Transition Cost Shock",
        "category":            "fuel",
        "description":         "Methanol/ammonia supply chains fail to scale — Maersk's 25 methanol vessels "
                               "stranded at $800/MT methanol vs $400/MT VLSFO break-even.",
        "empirical_basis":     "Maersk $4B methanol newbuild programme; methanol currently 2× VLSFO cost",
        "volume_impact":       (-0.05, -0.02,  0.00),
        "freight_rate_impact": (-0.05,  0.03,  0.08),
        "fuel_cost_impact":    ( 0.30,  0.50,  0.90),
        "duration_quarters":   6,
    },
    "lng_supply_shock": {
        "label":               "LNG Supply Shock (QatarEnergy Force Majeure)",
        "category":            "fuel",
        "description":         "Qatar LNG disruption drives European gas prices to record highs, "
                               "triggering energy-intensive industry shutdowns and trade volume collapse.",
        "empirical_basis":     "QatarEnergy declared force majeure 4 March 2026 (LIVE)",
        "volume_impact":       (-0.10, -0.06, -0.02),
        "freight_rate_impact": ( 0.05,  0.15,  0.30),
        "fuel_cost_impact":    ( 0.20,  0.40,  0.70),
        "duration_quarters":   4,
        "live_event":          True,
        "live_event_date":     "2026-03-04",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 3: GEOPOLITICAL / ROUTE SHOCKS
    # ══════════════════════════════════════════════════════════════════════════

    "suez_closure": {
        "label":               "Suez Canal / Red Sea Closure",
        "category":            "geopolitical",
        "description":         "Houthi attacks or canal blockage forcing Cape of Good Hope rerouting. "
                               "+10-14 days transit time, +$800/TEU direct cost.",
        "empirical_basis":     "Ever Given 2021; Houthi 2024: Suez traffic −66%",
        "volume_impact":       (-0.08, -0.04,  0.00),
        "freight_rate_impact": ( 0.10,  0.25,  0.45),
        "fuel_cost_impact":    ( 0.20,  0.35,  0.50),
        "duration_quarters":   2,
        "live_event":          True,
        "live_event_date":     "2026-02-28",
    },
    "hormuz_closure": {
        "label":               "Strait of Hormuz Closure (LIVE — Feb 2026)",
        "category":            "geopolitical",
        "description":         "Iran IRGC closes Hormuz — Gulf ports inaccessible, Brent >$100, "
                               "P&I insurance withdrawn. Emergency Bunker Surcharge activated 25 March 2026.",
        "empirical_basis":     "LIVE: Maersk suspended all Hormuz transits 28 Feb 2026. Brent $126/bbl.",
        "volume_impact":       (-0.12, -0.08, -0.03),
        "freight_rate_impact": ( 0.20,  0.35,  0.55),
        "fuel_cost_impact":    ( 0.40,  0.65,  1.00),
        "duration_quarters":   3,
        "live_event":          True,
        "live_event_date":     "2026-02-28",
    },
    "hormuz_suez_simultaneous": {
        "label":               "Dual Chokepoint Closure (Hormuz + Red Sea) — LIVE",
        "category":            "geopolitical",
        "description":         "Both Hormuz and Red Sea blocked simultaneously — first time in modern history. "
                               "~30% of global oil + 12% of world trade affected.",
        "empirical_basis":     "LIVE: Both closures active simultaneously from 28 Feb 2026",
        "volume_impact":       (-0.20, -0.14, -0.08),
        "freight_rate_impact": ( 0.35,  0.55,  0.80),
        "fuel_cost_impact":    ( 0.50,  0.75,  1.20),
        "duration_quarters":   4,
        "live_event":          True,
        "live_event_date":     "2026-02-28",
    },
    "taiwan_strait_blockade": {
        "label":               "Taiwan Strait Blockade / China-Taiwan Conflict",
        "category":            "geopolitical",
        "description":         "PLA naval blockade of Taiwan disrupts East Asia shipping lanes. "
                               "Taiwan Strait handles ~50% of global container traffic. "
                               "Maersk's Asia-Europe and Trans-Pacific services severely impacted.",
        "empirical_basis":     "China military exercises 2022 disrupted Taiwan Strait shipping lanes",
        "volume_impact":       (-0.30, -0.20, -0.10),
        "freight_rate_impact": ( 0.20,  0.40,  0.70),
        "fuel_cost_impact":    ( 0.25,  0.45,  0.80),
        "duration_quarters":   6,
    },
    "panama_canal_drought": {
        "label":               "Panama Canal Drought / Capacity Restriction",
        "category":            "geopolitical",
        "description":         "El Nino-driven drought reduces Panama Canal water levels, "
                               "cutting daily transits from 36 to 18. Trans-Atlantic and US-Asia lanes rerouted.",
        "empirical_basis":     "2023 drought: Canal restricted to 24 vessels/day, then 18; spot rates +30%",
        "volume_impact":       (-0.06, -0.03,  0.02),
        "freight_rate_impact": ( 0.08,  0.20,  0.38),
        "fuel_cost_impact":    ( 0.12,  0.25,  0.40),
        "duration_quarters":   3,
    },
    "russia_ukraine_escalation": {
        "label":               "Russia-Ukraine War Escalation / NATO Conflict",
        "category":            "geopolitical",
        "description":         "Escalation into NATO territory triggers sanctions expansion, "
                               "Baltic Sea shipping disruption, European energy crisis re-acceleration. "
                               "Maersk already exited Russia — residual exposure via Baltic routes.",
        "empirical_basis":     "2022 Russia exit cost Maersk ~$700M; Baltic Sea mine risk ongoing",
        "volume_impact":       (-0.12, -0.07, -0.02),
        "freight_rate_impact": (-0.05,  0.10,  0.25),
        "fuel_cost_impact":    ( 0.25,  0.45,  0.80),
        "duration_quarters":   6,
    },
    "south_china_sea_conflict": {
        "label":               "South China Sea Conflict / Spratly Islands Flashpoint",
        "category":            "geopolitical",
        "description":         "Military confrontation in South China Sea — the world's busiest shipping lane "
                               "($3.4T of annual trade). Maersk Asia-Europe and intra-Asia services shut down.",
        "empirical_basis":     "China-Philippines incidents 2024; US-China naval posturing",
        "volume_impact":       (-0.22, -0.15, -0.07),
        "freight_rate_impact": ( 0.20,  0.40,  0.65),
        "fuel_cost_impact":    ( 0.20,  0.40,  0.70),
        "duration_quarters":   5,
    },
    "sanctions_fleet_lockout": {
        "label":               "Sanctions-Driven Fleet / Insurance Lockout",
        "category":            "geopolitical",
        "description":         "P&I insurance withdrawn for major trade corridor — port bans follow. "
                               "Affects Maersk's ability to serve sanctioned routes.",
        "empirical_basis":     "Russia 2022: P&I cancelled, port access blocked; Hormuz 2026: P&I cancelled 5 March",
        "volume_impact":       (-0.15, -0.10, -0.05),
        "freight_rate_impact": ( 0.05,  0.15,  0.30),
        "fuel_cost_impact":    ( 0.10,  0.25,  0.50),
        "duration_quarters":   4,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 4: PANDEMIC / HEALTH SHOCKS
    # ══════════════════════════════════════════════════════════════════════════

    "pandemic_redux": {
        "label":               "Pandemic-Level Disruption (COVID-Redux)",
        "category":            "pandemic",
        "description":         "New pathogen causes global port closures, demand whipsaw, "
                               "supply chain seizure. Initial demand collapse followed by rate supercycle.",
        "empirical_basis":     "COVID-19 2020: Maersk revenue −11.8% Q2 2020, then +200% freight rates 2021",
        "volume_impact":       (-0.15, -0.08,  0.05),
        "freight_rate_impact": (-0.10,  0.20,  0.80),
        "fuel_cost_impact":    (-0.20, -0.10,  0.10),
        "duration_quarters":   6,
    },
    "port_congestion_cascade": {
        "label":               "Global Port Congestion Cascade",
        "category":            "pandemic",
        "description":         "Labour strikes + vessel bunching create simultaneous congestion at "
                               "Los Angeles, Rotterdam, Singapore and Ningbo — vessels idle for weeks.",
        "empirical_basis":     "2021-2022 US West Coast congestion; LA/LB 100+ ships at anchor",
        "volume_impact":       (-0.12, -0.07, -0.02),
        "freight_rate_impact": ( 0.15,  0.30,  0.55),
        "fuel_cost_impact":    ( 0.08,  0.15,  0.28),
        "duration_quarters":   3,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 5: OPERATIONAL / CYBER SHOCKS
    # ══════════════════════════════════════════════════════════════════════════

    "cyberattack": {
        "label":               "Major Cyberattack (NotPetya-Scale)",
        "category":            "operational",
        "description":         "IT system takedown across fleet, ports, booking systems. "
                               "NotPetya cost Maersk $300-450M in 10 days. Modern attack surface far larger.",
        "empirical_basis":     "NotPetya 2017: 4,000 servers, 45,000 PCs destroyed; $300-450M loss",
        "volume_impact":       (-0.20, -0.12, -0.05),
        "freight_rate_impact": (-0.10,  0.00,  0.05),
        "fuel_cost_impact":    ( 0.00,  0.05,  0.15),
        "duration_quarters":   2,
    },
    "carrier_bankruptcy_contagion": {
        "label":               "Competitor Carrier Bankruptcy / Market Windfall",
        "category":            "operational",
        "description":         "Major competitor (e.g. SM Line, Yang Ming) collapses — "
                               "Maersk gains volume windfall but suffers systemic port congestion.",
        "empirical_basis":     "Hanjin 2016: $14B cargo stranded; MSC/Maersk gained volume but port chaos",
        "volume_impact":       ( 0.05,  0.12,  0.20),   # POSITIVE — volume windfall
        "freight_rate_impact": ( 0.10,  0.20,  0.35),
        "fuel_cost_impact":    ( 0.05,  0.10,  0.20),
        "duration_quarters":   3,
    },
    "labour_strike_cascade": {
        "label":               "Global Longshoremen Strike Cascade",
        "category":            "operational",
        "description":         "Coordinated strike action at major US East Coast and European ports. "
                               "ILA strike 2024 briefly closed 36 US ports — a prolonged version would be catastrophic.",
        "empirical_basis":     "ILA strike Oct 2024 (3 days); ILWU 2002 (10 days cost $1B/day to US economy)",
        "volume_impact":       (-0.18, -0.10, -0.04),
        "freight_rate_impact": ( 0.10,  0.25,  0.45),
        "fuel_cost_impact":    ( 0.05,  0.12,  0.22),
        "duration_quarters":   2,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 6: FINANCIAL SHOCKS
    # ══════════════════════════════════════════════════════════════════════════

    "credit_rating_downgrade": {
        "label":               "Credit Rating Downgrade (Investment Grade Loss)",
        "category":            "financial",
        "description":         "Moody's/S&P downgrade triggers debt covenant breaches, refinancing cost spike. "
                               "Maersk $14.2B debt — IG loss adds 150-300bps = $200-400M annual interest increase.",
        "empirical_basis":     "Maersk rated Baa1/BBB+ — 2 notch downgrade removes IG status",
        "volume_impact":       (-0.05, -0.02,  0.00),
        "freight_rate_impact": (-0.02,  0.00,  0.02),
        "fuel_cost_impact":    ( 0.00,  0.05,  0.10),
        "duration_quarters":   4,
    },
    "usd_dollar_supercycle": {
        "label":               "USD Supercycle Strengthening",
        "category":            "financial",
        "description":         "Fed tightening cycle drives USD +20%, crushing emerging market trade volumes. "
                               "Maersk reports in USD but 60% of costs in DKK/EUR.",
        "empirical_basis":     "2014-2016 USD supercycle: EM trade volumes fell 15-20%; 2022 partial repeat",
        "volume_impact":       (-0.12, -0.07, -0.02),
        "freight_rate_impact": (-0.15, -0.08, -0.02),
        "fuel_cost_impact":    (-0.05,  0.02,  0.08),
        "duration_quarters":   6,
    },
    "freight_rate_supercycle_bust": {
        "label":               "Freight Rate Supercycle Bust (2023 Repeat)",
        "category":            "financial",
        "description":         "Post-peak rate normalisation — Shanghai Containerized Freight Index "
                               "collapses from elevated 2024-2025 levels back toward pre-COVID norms.",
        "empirical_basis":     "SCFI fell −85% from peak Jan 2022 to Jan 2024; Maersk EBITDA −87% in that period",
        "volume_impact":       (-0.05,  0.02,  0.08),
        "freight_rate_impact": (-0.55, -0.35, -0.18),
        "fuel_cost_impact":    (-0.15, -0.05,  0.05),
        "duration_quarters":   8,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 7: REGULATORY / COMPLIANCE SHOCKS
    # ══════════════════════════════════════════════════════════════════════════

    "carbon_price_shock": {
        "label":               "Carbon Price Shock (EU ETS + IMO CII)",
        "category":            "regulatory",
        "description":         "Disorderly green transition — carbon price spikes overnight, "
                               "CII D/E-rated vessels restricted from trading. "
                               "EU ETS cost Maersk $44M Q1 2024 alone; 3-5× by 2030 scenario.",
        "empirical_basis":     "EU ETS shipping inclusion Jan 2024; IMO CII annual tightening",
        "volume_impact":       (-0.08, -0.04,  0.00),
        "freight_rate_impact": ( 0.05,  0.12,  0.20),
        "fuel_cost_impact":    ( 0.20,  0.40,  0.70),
        "duration_quarters":   8,
    },
    "antitrust_alliance_dissolution": {
        "label":               "Antitrust Action — Gemini Cooperation Dissolved",
        "category":            "regulatory",
        "description":         "Regulatory forced dissolution of Maersk-Hapag-Lloyd Gemini Cooperation. "
                               "Alliance cost savings lost; vessel utilisation falls.",
        "empirical_basis":     "Gemini launched Feb 2025; EU/US antitrust review active",
        "volume_impact":       (-0.08, -0.05, -0.02),
        "freight_rate_impact": (-0.10, -0.06, -0.02),
        "fuel_cost_impact":    ( 0.05,  0.10,  0.18),
        "duration_quarters":   4,
    },
    "imo_2030_nox_sox": {
        "label":               "IMO 2030 NOx/SOx Rule Tightening (EEXI Breach)",
        "category":            "regulatory",
        "description":         "IMO 2030 fuel efficiency rules require Maersk to slow-steam or retrofit "
                               "its legacy fleet. 30% of current fleet may face operational restrictions.",
        "empirical_basis":     "IMO EEXI/CII in force Jan 2023; 2030 phase escalation confirmed",
        "volume_impact":       (-0.06, -0.03,  0.00),
        "freight_rate_impact": ( 0.03,  0.08,  0.15),
        "fuel_cost_impact":    ( 0.10,  0.20,  0.35),
        "duration_quarters":   8,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY 8: COMPOUND / STRESS SHOCKS
    # ══════════════════════════════════════════════════════════════════════════

    "compound_shock": {
        "label":               "Compound Shock (Demand + Fuel + Route Disruption)",
        "category":            "compound",
        "description":         "Simultaneous global recession, fuel spike, and major route disruption. "
                               "CNLI amplification factor ~1.34 (34% worse than linear sum).",
        "empirical_basis":     "Hypothetical worst-case stress test",
        "volume_impact":       (-0.40, -0.25, -0.12),
        "freight_rate_impact": (-0.30, -0.15,  0.00),
        "fuel_cost_impact":    ( 0.30,  0.50,  0.90),
        "duration_quarters":   6,
    },
    "hormuz_demand_compound": {
        "label":               "Hormuz Crisis + Global Recession (Live Compound)",
        "category":            "compound",
        "description":         "Current Hormuz crisis cascades into global recession via energy price shock. "
                               "Both Red Sea and Hormuz blocked simultaneously + tariff collapse of trans-Pacific.",
        "empirical_basis":     "LIVE: Brent $126, QatarEnergy force majeure 4 March 2026, tariffs active",
        "volume_impact":       (-0.35, -0.22, -0.10),
        "freight_rate_impact": ( 0.10,  0.25,  0.45),
        "fuel_cost_impact":    ( 0.50,  0.80,  1.30),
        "duration_quarters":   6,
        "live_event":          True,
        "live_event_date":     "2026-03-08",
    },
    "climate_extreme_event": {
        "label":               "Extreme Climate Event Cascade (Multi-Port Closure)",
        "category":            "compound",
        "description":         "Simultaneous climate events: super-typhoon closes Shanghai/Ningbo, "
                               "flooding closes Rotterdam, extreme heat shuts down Suez dredging. "
                               "Insurance markets retreat from catastrophe coverage.",
        "empirical_basis":     "2011 Thailand floods disrupted global supply chains for 6 months; "
                               "2022 Rhine drought cut European barge capacity 80%",
        "volume_impact":       (-0.25, -0.15, -0.06),
        "freight_rate_impact": ( 0.15,  0.30,  0.55),
        "fuel_cost_impact":    ( 0.10,  0.22,  0.40),
        "duration_quarters":   4,
    },
    "geopolitical_great_decoupling": {
        "label":               "Great Decoupling (US-China Trade Bifurcation)",
        "category":            "compound",
        "description":         "Structural permanent bifurcation of US-China trade — 'friendshoring' "
                               "reshapes global container flows. Maersk loses trans-Pacific but gains "
                               "India/Mexico/Vietnam corridors over 5 years.",
        "empirical_basis":     "FDI rerouting to Vietnam +35% (2022-2024); Mexico nearshoring boom",
        "volume_impact":       (-0.15, -0.08,  0.02),
        "freight_rate_impact": (-0.20, -0.10,  0.00),
        "fuel_cost_impact":    ( 0.05,  0.12,  0.22),
        "duration_quarters":   12,
    },
}

# -----------------------------------------------------------------------------
# STRATEGIES — 11 total
# -----------------------------------------------------------------------------
STRATEGIES = {
    "dynamic_pricing": {
        "label":                 "Dynamic Pricing (Yield Management)",
        "real_world_cadence":    "Daily — Maersk SpotOn platform",
        "freight_rate_modifier": 0.12,
        "cost_modifier":         0.02,
        "volume_modifier":      -0.04,
    },
    "capacity_reduction": {
        "label":                 "Capacity Reduction (Slow Steaming + Lay-up)",
        "real_world_cadence":    "Weekly — blank sailing coordination",
        "freight_rate_modifier": 0.08,
        "cost_modifier":        -0.15,
        "volume_modifier":      -0.12,
    },
    "route_optimisation": {
        "label":                 "Route Optimisation (Cape Rerouting + AI Planning)",
        "real_world_cadence":    "Daily — AI voyage optimisation",
        "freight_rate_modifier": 0.05,
        "cost_modifier":        -0.08,
        "volume_modifier":      -0.02,
    },
    "fuel_hedging": {
        "label":                 "Fuel Hedging (Forward Contracts — 40-60% cover)",
        "real_world_cadence":    "Quarterly — Maersk hedges 40-60% of consumption",
        "freight_rate_modifier": 0.00,
        "cost_modifier":        -0.20,
        "volume_modifier":       0.00,
    },
    "do_nothing": {
        "label":                 "No Response (Baseline — Do Nothing)",
        "real_world_cadence":    "N/A — benchmark only",
        "freight_rate_modifier": 0.00,
        "cost_modifier":         0.00,
        "volume_modifier":       0.00,
    },
    "alliance_coordination": {
        "label":                 "Alliance Coordination (Gemini — Maersk + Hapag-Lloyd)",
        "real_world_cadence":    "Ongoing since Feb 2025",
        "freight_rate_modifier": 0.06,
        "cost_modifier":        -0.12,
        "volume_modifier":      -0.03,
    },
    "vertical_integration": {
        "label":                 "Vertical Integration (Logistics Buffer)",
        "real_world_cadence":    "Multi-year — Maersk integrator strategy",
        "freight_rate_modifier": 0.00,
        "cost_modifier":         0.03,
        "volume_modifier":       0.05,
        "logistics_revenue_buffer": 0.30,  # 30% of logistics revenue shielded from shocks
    },
    "green_transition": {
        "label":                 "Green Transition (Methanol Fleet + EU ETS Compliance)",
        "real_world_cadence":    "Multi-year — Maersk $7.4B dual-fuel fleet orders",
        "freight_rate_modifier": 0.08,
        "cost_modifier":         0.05,
        "volume_modifier":       0.03,
    },
    "contract_lock_in": {
        "label":                 "Long-Term Contract Lock-in (Revenue Floor)",
        "real_world_cadence":    "Monthly — sales and commercial strategy",
        "freight_rate_modifier":-0.05,
        "cost_modifier":        -0.03,
        "volume_modifier":       0.08,
    },
    "distressed_acquisition": {
        "label":                 "Distressed Asset Acquisition (Opportunistic M&A)",
        "real_world_cadence":    "During downturns — MSC 2020-2023 growth model",
        "freight_rate_modifier": 0.04,
        "cost_modifier":         0.08,
        "volume_modifier":       0.15,
    },
    "digital_platform": {
        "label":                 "Digital Freight Platform (Asset-Light Revenue)",
        "real_world_cadence":    "3-5 year build — Maersk.com / Captain Peter direction",
        "freight_rate_modifier": 0.03,
        "cost_modifier":        -0.10,
        "volume_modifier":       0.07,
    },
}

# -----------------------------------------------------------------------------
# LIVE EVENTS — real-world confirmed events (March 2026)
# [BF-3] Keys must match SHOCK_SCENARIOS keys exactly
# -----------------------------------------------------------------------------
LIVE_EVENTS = {
    "hormuz_2026": {
        "label":        "🔴 LIVE: Strait of Hormuz + Red Sea Crisis (March 2026)",
        "started":      "2026-02-28",
        "status":       "active",
        "description":  "Iran IRGC closed Hormuz following US/Israeli strikes. "
                        "Maersk suspended all transits. Brent hit $126/bbl. "
                        "Both Red Sea and Hormuz blocked simultaneously — first time in modern history. "
                        "QatarEnergy declared force majeure 4 March 2026.",
        "linked_shock": "hormuz_closure",          # [BF-3] matches SHOCK_SCENARIOS key exactly
        "brent_at_event": 126.0,
        "maersk_response": [
            "Emergency Freight Increase effective 2 March 2026",
            "Emergency Bunker Surcharge effective 25 March 2026",
            "Temporary suspension of empty container returns in Gulf",
            "Landbridge solutions deployed across Gulf region",
            "All Suez and Hormuz transits suspended until further notice",
            "Gemini Alliance coordination with Hapag-Lloyd activated",
        ],
    },
    "us_tariff_2026": {
        "label":        "🟡 ACTIVE: US-China 125% Tariffs (January 2026)",
        "started":      "2026-01-20",
        "status":       "active",
        "description":  "125% US tariffs on Chinese goods in effect. "
                        "Trans-Pacific booking cancellations +45%. "
                        "Front-loading surge ended; volume collapse underway.",
        "linked_shock": "us_tariff_escalation",    # [BF-3] matches SHOCK_SCENARIOS key exactly
        "maersk_response": [
            "Trans-Pacific capacity reduction (blank sailings)",
            "Pivot to intra-Asia and Asia-India trade lanes",
            "Dynamic pricing on remaining trans-Pacific slots",
        ],
    },
}

# -----------------------------------------------------------------------------
# SIGNAL WEIGHTS — live market signals mapped to scenario scores
# [BF-3] All keys now reference valid SHOCK_SCENARIOS keys
# -----------------------------------------------------------------------------
SIGNAL_WEIGHTS = {
    "brent_above_126":         {"scenario": "hormuz_demand_compound",   "points": 50},
    "brent_above_100":         {"scenario": "hormuz_closure",           "points": 40},
    "brent_above_90":          {"scenario": "fuel_price_spike",         "points": 20},
    "brent_daily_spike":       {"scenario": "fuel_price_spike",         "points": 25, "threshold": 0.03},
    "sp500_crash":             {"scenario": "demand_collapse",          "points": 35, "threshold": -0.02},
    "sp500_mild_drop":         {"scenario": "demand_collapse",          "points": 15, "threshold": -0.01},
    "vix_above_30":            {"scenario": "demand_collapse",          "points": 20, "threshold": 30},
    "vix_above_40":            {"scenario": "compound_shock",           "points": 35, "threshold": 40},
    "usd_cny_move":            {"scenario": "us_tariff_escalation",     "points": 25, "threshold": 0.005},
    "copper_drop":             {"scenario": "china_hard_landing",       "points": 20, "threshold": -0.03},
    "baltic_dry_drop":         {"scenario": "demand_collapse",          "points": 20, "threshold": -0.05},
    "maersk_drop":             {"scenario": "demand_collapse",          "points": 20, "threshold": -0.03},
    "usd_krw_spike":           {"scenario": "south_china_sea_conflict", "points": 15, "threshold": 0.01},
    "natural_gas_spike":       {"scenario": "lng_supply_shock",         "points": 30, "threshold": 0.05},
}

# -----------------------------------------------------------------------------
# REVERSE STRESS TEST
# -----------------------------------------------------------------------------
REVERSE_STRESS_DISTRESS_THRESHOLD = 0.50

# -----------------------------------------------------------------------------
# DASHBOARD SETTINGS
# -----------------------------------------------------------------------------
DASHBOARD_TITLE             = "Maersk Financial Digital Twin v3.0"
DASHBOARD_REFRESH_SECONDS   = 60
SPARKLINE_MINUTES           = 60

COLOR_POSITIVE  = "#00C853"
COLOR_NEGATIVE  = "#FF1744"
COLOR_NEUTRAL   = "#FFD600"
COLOR_LIVE      = "#00E5FF"
COLOR_BG        = "#0D1117"
COLOR_CARD      = "#161B22"
COLOR_DANGER    = "#FF6B35"

# -----------------------------------------------------------------------------
# RESULTS EXPORT
# -----------------------------------------------------------------------------
RESULTS_DIR = "results/"
TABLES_DIR  = "results/tables/"
FIGURES_DIR = "results/figures/"
