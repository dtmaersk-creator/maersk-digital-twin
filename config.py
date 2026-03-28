# =============================================================================
# config.py v2.0 — Maersk Digital Twin: Central Configuration
# Updated March 2026 — includes Hormuz crisis, 60 shocks, 11 strategies
# =============================================================================

# -----------------------------------------------------------------------------
# API KEY — paste your Finnhub key here
# -----------------------------------------------------------------------------
FINNHUB_API_KEY = "YOUR_KEY_HERE"

# -----------------------------------------------------------------------------
# DATA COLLECTION
# -----------------------------------------------------------------------------
FETCH_INTERVAL_SECONDS  = 60
DB_PATH                 = "maersk_twin.db"
SNAPSHOT_JSON           = "latest_snapshot.json"
HISTORY_DAYS            = 30

# -----------------------------------------------------------------------------
# MARKET DATA SYMBOLS (Yahoo Finance — free, no key needed)
# -----------------------------------------------------------------------------
MAERSK_YAHOO_SYMBOL = "MAERSK-B.CO"

YAHOO_TICKERS = {
    "brent_crude":  "BZ=F",
    "natural_gas":  "NG=F",
    "usd_dkk":      "DKK=X",
    "usd_eur":      "EURUSD=X",
    "usd_cny":      "CNY=X",
    "sp500":        "^GSPC",
}

# -----------------------------------------------------------------------------
# MAERSK BASELINE FINANCIALS — FY2023 Annual Report (USD millions)
# -----------------------------------------------------------------------------
BASELINE = {
    "year":                      2023,
    "revenue_usd_m":             51_000,
    "ebitda_usd_m":              9_600,
    "ebit_usd_m":                6_100,
    "net_income_usd_m":          3_800,
    "total_assets_usd_m":        65_000,
    "total_debt_usd_m":          14_200,
    "cash_usd_m":                9_100,
    "capex_usd_m":               3_500,
    "fleet_size_vessels":        703,
    "teu_capacity":              4_200_000,
    "volume_teu_m":              12.0,
    "avg_freight_rate_usd_teu":  1_800,
    "fuel_cost_usd_m":           4_200,
    "employees":                 100_000,
    "logistics_revenue_usd_m":   15_000,   # Logistics & Services segment FY2023
    "gulf_revenue_share":        0.08,     # ~8% of revenue from Gulf/Middle East routes
    "contract_revenue_share":    0.40,     # 40% long-term contracts, 60% spot
}

# -----------------------------------------------------------------------------
# MONTE CARLO SETTINGS
# -----------------------------------------------------------------------------
MONTE_CARLO_RUNS        = 10_000
SHOCK_DURATION_QUARTERS = 4
CONFIDENCE_INTERVALS    = [0.05, 0.25, 0.50, 0.75, 0.95]

# -----------------------------------------------------------------------------
# SHOCK SCENARIOS — 12 Categories, 18 Core Scenarios
# Format: (min, mode, max) = triangular distribution
# All impacts are fractional (−0.20 = −20%)
# -----------------------------------------------------------------------------
SHOCK_SCENARIOS = {

    # ── DEMAND SHOCKS ─────────────────────────────────────────────────────────
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
        "description":         "Chinese property/banking crisis, GDP −8%, global cascade",
        "empirical_basis":     "Evergrande 2021 partial, Japan 1991 analogue",
        "volume_impact":       (-0.40, -0.28, -0.15),
        "freight_rate_impact": (-0.45, -0.30, -0.15),
        "fuel_cost_impact":    (-0.20, -0.10,  0.00),
        "duration_quarters":   6,
    },
    "us_tariff_escalation": {
        "label":               "US Tariff Escalation (2025-style)",
        "category":            "demand",
        "description":         "Broad tariff increases driving import front-loading then collapse",
        "empirical_basis":     "2018-2019 US-China trade war, 2025 tariff escalation",
        "volume_impact":       (-0.20, -0.12, -0.05),
        "freight_rate_impact": (-0.20, -0.10,  0.00),
        "fuel_cost_impact":    (-0.05,  0.00,  0.05),
        "duration_quarters":   6,
    },

    # ── FUEL / ENERGY SHOCKS ──────────────────────────────────────────────────
    "fuel_price_spike": {
        "label":               "Fuel Price Spike",
        "category":            "fuel",
        "description":         "Brent crude surge from geopolitical supply disruption",
        "empirical_basis":     "Ukraine 2022: bunker +60%, Hormuz 2026: Brent hit $126",
        "volume_impact":       (-0.05, -0.02,  0.00),
        "freight_rate_impact": (-0.05,  0.05,  0.15),
        "fuel_cost_impact":    ( 0.25,  0.45,  0.80),
        "duration_quarters":   3,
    },
    "methanol_transition_shock": {
        "label":               "Green Fuel Transition Cost Shock",
        "category":            "fuel",
        "description":         "Methanol/ammonia supply chains fail to scale — stranded newbuilds",
        "empirical_basis":     "Maersk has 25 methanol dual-fuel vessels on order worth ~$4B",
        "volume_impact":       (-0.05, -0.02,  0.00),
        "freight_rate_impact": (-0.05,  0.03,  0.08),
        "fuel_cost_impact":    ( 0.30,  0.50,  0.90),
        "duration_quarters":   6,
    },

    # ── GEOPOLITICAL / ROUTE SHOCKS ───────────────────────────────────────────
    "suez_closure": {
        "label":               "Suez Canal / Red Sea Closure",
        "category":            "geopolitical",
        "description":         "Houthi attacks or canal blockage forcing Cape rerouting",
        "empirical_basis":     "Ever Given 2021, Houthi 2024: Suez traffic −66%",
        "volume_impact":       (-0.08, -0.04,  0.00),
        "freight_rate_impact": ( 0.10,  0.25,  0.45),
        "fuel_cost_impact":    ( 0.20,  0.35,  0.50),
        "duration_quarters":   2,
    },
    "hormuz_closure": {
        "label":               "Strait of Hormuz Closure (LIVE — March 2026)",
        "category":            "geopolitical",
        "description":         "Iran IRGC closes Hormuz — Gulf ports inaccessible, Brent >$100, insurance withdrawn",
        "empirical_basis":     "LIVE EVENT: Maersk suspended all Hormuz transits 28 Feb 2026. Brent hit $126/bbl 8 March 2026.",
        # Gulf revenue lockout: ~8% of Maersk revenue from Gulf routes, partially recoverable via landbridge
        "volume_impact":       (-0.12, -0.08, -0.03),
        # Rate spike on rerouted cargo + emergency freight surcharges (Maersk EFS effective 2 March 2026)
        "freight_rate_impact": ( 0.20,  0.35,  0.55),
        # Brent above $100 + war-zone refuelling premiums + Emergency Bunker Surcharge 25 March 2026
        "fuel_cost_impact":    ( 0.40,  0.65,  1.00),
        "duration_quarters":   3,
        "live_event":          True,
        "live_event_date":     "2026-03-02",
    },
    "hormuz_suez_simultaneous": {
        "label":               "Dual Chokepoint Closure (Hormuz + Red Sea)",
        "category":            "geopolitical",
        "description":         "Both Hormuz and Red Sea blocked simultaneously — live March 2026",
        "empirical_basis":     "LIVE: Houthis resumed Red Sea attacks 28 Feb 2026 same day as Hormuz closure",
        "volume_impact":       (-0.20, -0.14, -0.08),
        "freight_rate_impact": ( 0.35,  0.55,  0.80),
        "fuel_cost_impact":    ( 0.50,  0.75,  1.20),
        "duration_quarters":   4,
        "live_event":          True,
        "live_event_date":     "2026-02-28",
    },
    "sanctions_fleet_lockout": {
        "label":               "Sanctions-Driven Fleet / Insurance Lockout",
        "category":            "geopolitical",
        "description":         "P&I insurance withdrawn for major trade corridor — port bans follow",
        "empirical_basis":     "Russia 2022: P&I cancelled, port access blocked. Hormuz 2026: P&I cancelled 5 March",
        "volume_impact":       (-0.15, -0.10, -0.05),
        "freight_rate_impact": ( 0.05,  0.15,  0.30),
        "fuel_cost_impact":    ( 0.10,  0.25,  0.50),
        "duration_quarters":   4,
    },

    # ── PANDEMIC / OPERATIONAL SHOCKS ─────────────────────────────────────────
    "pandemic_redux": {
        "label":               "Pandemic-Level Disruption",
        "category":            "pandemic",
        "description":         "Port closures, demand whipsaw, supply chain seizure",
        "empirical_basis":     "COVID-19 2020: Maersk revenue −11.8% Q2 2020",
        "volume_impact":       (-0.15, -0.08,  0.05),
        "freight_rate_impact": (-0.10,  0.20,  0.80),
        "fuel_cost_impact":    (-0.20, -0.10,  0.10),
        "duration_quarters":   6,
    },
    "cyberattack": {
        "label":               "Major Cyberattack (NotPetya-scale)",
        "category":            "operational",
        "description":         "IT system takedown across fleet, ports, booking systems",
        "empirical_basis":     "NotPetya 2017: cost Maersk $300-450M, took down 4,000 servers, 45,000 PCs",
        "volume_impact":       (-0.20, -0.12, -0.05),
        "freight_rate_impact": (-0.10,  0.00,  0.05),
        "fuel_cost_impact":    ( 0.00,  0.05,  0.15),
        "duration_quarters":   2,
    },
    "carrier_bankruptcy_contagion": {
        "label":               "Competitor Carrier Bankruptcy Contagion",
        "category":            "operational",
        "description":         "Major competitor collapses — cargo windfall but systemic port congestion",
        "empirical_basis":     "Hanjin 2016: $14B cargo stranded, ports refused entry, MSC/Maersk gained volume",
        "volume_impact":       ( 0.05,  0.12,  0.20),  # POSITIVE — volume windfall
        "freight_rate_impact": ( 0.10,  0.20,  0.35),  # Rate spike from supply withdrawal
        "fuel_cost_impact":    ( 0.05,  0.10,  0.20),  # Port congestion adds cost
        "duration_quarters":   3,
    },

    # ── FINANCIAL SHOCKS ──────────────────────────────────────────────────────
    "credit_rating_downgrade": {
        "label":               "Credit Rating Downgrade (Investment Grade Loss)",
        "category":            "financial",
        "description":         "Moody's/S&P downgrade triggers debt covenant breaches, refinancing cost spike",
        "empirical_basis":     "Maersk $14.2B debt — IG loss adds 150-300bps, ~$200-400M annual interest increase",
        "volume_impact":       (-0.05, -0.02,  0.00),
        "freight_rate_impact": (-0.02,  0.00,  0.02),
        "fuel_cost_impact":    ( 0.00,  0.05,  0.10),
        "duration_quarters":   4,
    },

    # ── REGULATORY / COMPLIANCE SHOCKS ────────────────────────────────────────
    "carbon_price_shock": {
        "label":               "Carbon Price Shock (EU ETS + IMO CII)",
        "category":            "regulatory",
        "description":         "Disorderly green transition — carbon price spike overnight, CII vessel restrictions",
        "empirical_basis":     "EU ETS cost Maersk $44M Q1 2024 alone. Carbon price could 3-5x by 2030.",
        "volume_impact":       (-0.08, -0.04,  0.00),
        "freight_rate_impact": ( 0.05,  0.12,  0.20),  # Pass-through to customers
        "fuel_cost_impact":    ( 0.20,  0.40,  0.70),
        "duration_quarters":   8,
    },
    "antitrust_alliance_dissolution": {
        "label":               "Antitrust Action — Gemini Cooperation Dissolved",
        "category":            "regulatory",
        "description":         "Regulatory forced dissolution of Maersk-Hapag-Lloyd Gemini Cooperation",
        "empirical_basis":     "Gemini Cooperation launched Feb 2025 — under EU/US antitrust review",
        "volume_impact":       (-0.08, -0.05, -0.02),
        "freight_rate_impact": (-0.10, -0.06, -0.02),
        "fuel_cost_impact":    ( 0.05,  0.10,  0.18),
        "duration_quarters":   4,
    },

    # ── COMPOUND / STRESS SHOCKS ──────────────────────────────────────────────
    "compound_shock": {
        "label":               "Compound Shock (Demand + Fuel + Route Disruption)",
        "category":            "compound",
        "description":         "Simultaneous demand collapse, fuel spike, and route disruption",
        "empirical_basis":     "Hypothetical stress test — CNLI amplification factor ~1.34",
        "volume_impact":       (-0.40, -0.25, -0.12),
        "freight_rate_impact": (-0.30, -0.15,  0.00),
        "fuel_cost_impact":    ( 0.30,  0.50,  0.90),
        "duration_quarters":   6,
    },
    "hormuz_demand_compound": {
        "label":               "Hormuz Crisis + Global Recession (Live Compound)",
        "category":            "compound",
        "description":         "Current Hormuz crisis cascades into global recession via energy price shock",
        "empirical_basis":     "LIVE: Brent $126, LNG disruption, QatarEnergy force majeure 4 March 2026",
        "volume_impact":       (-0.35, -0.22, -0.10),
        "freight_rate_impact": ( 0.10,  0.25,  0.45),
        "fuel_cost_impact":    ( 0.50,  0.80,  1.30),
        "duration_quarters":   6,
        "live_event":          True,
        "live_event_date":     "2026-03-08",
    },
}

# -----------------------------------------------------------------------------
# STRATEGIES — 11 total (5 original + 6 new real-world strategies)
# -----------------------------------------------------------------------------
STRATEGIES = {
    # ── ORIGINAL 5 ────────────────────────────────────────────────────────────
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
        "label":                 "Route Optimisation (AI Voyage Planning)",
        "real_world_cadence":    "Daily — AI voyage optimisation systems",
        "freight_rate_modifier": 0.05,
        "cost_modifier":        -0.08,
        "volume_modifier":      -0.02,
    },
    "fuel_hedging": {
        "label":                 "Fuel Hedging (Forward Contracts)",
        "real_world_cadence":    "Quarterly — Maersk hedges 40-60% of consumption",
        "freight_rate_modifier": 0.00,
        "cost_modifier":        -0.20,
        "volume_modifier":       0.00,
    },
    "do_nothing": {
        "label":                 "No Response (Baseline)",
        "real_world_cadence":    "N/A — benchmark only",
        "freight_rate_modifier": 0.00,
        "cost_modifier":         0.00,
        "volume_modifier":       0.00,
    },

    # ── NEW STRATEGIES ────────────────────────────────────────────────────────
    "alliance_coordination": {
        "label":                 "Alliance Coordination (Gemini Cooperation)",
        "real_world_cadence":    "Ongoing — Maersk + Hapag-Lloyd since Feb 2025",
        "freight_rate_modifier": 0.06,   # Reliability premium + coordinated blank sailings
        "cost_modifier":        -0.12,   # Shared vessel costs, joint port calls
        "volume_modifier":      -0.03,   # Hub-spoke network serves fewer ports directly
    },
    "vertical_integration": {
        "label":                 "Vertical Integration Defence (Logistics Buffer)",
        "real_world_cadence":    "Multi-year — Maersk integrator strategy",
        "freight_rate_modifier": 0.00,
        "cost_modifier":         0.03,   # Investment in logistics infrastructure
        "volume_modifier":       0.05,   # Stickier integrated customers
    },
    "green_transition": {
        "label":                 "Green Transition (Dual-Fuel + EU ETS Compliance)",
        "real_world_cadence":    "Multi-year — Maersk $7.4B dual-fuel fleet orders",
        "freight_rate_modifier": 0.08,   # Green premium from ESG-mandated shippers
        "cost_modifier":         0.05,   # Green vessels + alt fuel premium, offset by ETS savings
        "volume_modifier":       0.03,   # ESG contract wins, regulatory compliance
    },
    "contract_lock_in": {
        "label":                 "Long-Term Contract Lock-in (Revenue Floor)",
        "real_world_cadence":    "Monthly — sales and commercial strategy",
        "freight_rate_modifier":-0.05,   # Contracts priced below spot — volume certainty premium
        "cost_modifier":        -0.03,   # Better fleet deployment planning
        "volume_modifier":       0.08,   # Guaranteed contracted volumes during demand collapse
    },
    "distressed_acquisition": {
        "label":                 "Distressed Asset Acquisition (Opportunistic M&A)",
        "real_world_cadence":    "During downturns — MSC 2020-2023 growth model",
        "freight_rate_modifier": 0.04,   # Market consolidation supports rates
        "cost_modifier":         0.08,   # Integration costs
        "volume_modifier":       0.15,   # Acquired routes and customers
    },
    "digital_platform": {
        "label":                 "Digital Freight Platform (Asset-Light)",
        "real_world_cadence":    "3-5 year build — Flexport/Maersk.com direction",
        "freight_rate_modifier": 0.03,
        "cost_modifier":        -0.10,   # Platform-brokered cargo = no vessel cost
        "volume_modifier":       0.07,   # SME customer acquisition
    },
}

# -----------------------------------------------------------------------------
# LIVE EVENTS — real-world events for dashboard alerts
# -----------------------------------------------------------------------------
LIVE_EVENTS = {
    "hormuz_2026": {
        "label":       "🔴 LIVE: Strait of Hormuz Crisis (March 2026)",
        "started":     "2026-02-28",
        "status":      "active",
        "description": "Iran IRGC closed Hormuz following US/Israeli strikes. Maersk suspended all transits. Brent hit $126/bbl. Both Red Sea and Hormuz blocked simultaneously for first time in modern history.",
        "linked_shock": "hormuz_closure",
        "brent_at_event": 126.0,
        "maersk_response": [
            "Emergency Freight Increase effective 2 March 2026",
            "Emergency Bunker Surcharge effective 25 March 2026",
            "Temporary suspension of empty container returns in Gulf",
            "Landbridge solutions deployed across Gulf region",
            "All Suez/Hormuz transits suspended until further notice",
        ],
    },
}

# -----------------------------------------------------------------------------
# MARKET INTELLIGENCE SIGNAL WEIGHTS
# -----------------------------------------------------------------------------
SIGNAL_WEIGHTS = {
    "brent_above_100":     {"scenario": "hormuz_closure",   "points": 40},
    "brent_above_126":     {"scenario": "hormuz_demand_compound", "points": 50},
    "brent_above_90":      {"scenario": "fuel_price_spike", "points": 15},
    "brent_daily_change":  {"scenario": "fuel_price_spike", "points": 20, "threshold": 0.02},
    "sp500_crash":         {"scenario": "demand_collapse",  "points": 30, "threshold": -0.02},
    "sp500_mild_drop":     {"scenario": "demand_collapse",  "points": 15, "threshold": -0.01},
    "usd_cny_move":        {"scenario": "us_tariff_escalation", "points": 25, "threshold": 0.005},
    "maersk_drop":         {"scenario": "demand_collapse",  "points": 20, "threshold": -0.03},
}

# -----------------------------------------------------------------------------
# REVERSE STRESS TEST — minimum shock combination causing financial distress
# Distress = P(net loss) > 50% over shock horizon
# -----------------------------------------------------------------------------
REVERSE_STRESS_DISTRESS_THRESHOLD = 0.50   # P(net loss) > 50% = distress

# -----------------------------------------------------------------------------
# DASHBOARD / DISPLAY SETTINGS
# -----------------------------------------------------------------------------
DASHBOARD_TITLE             = "Maersk Financial Digital Twin v2.0"
DASHBOARD_REFRESH_SECONDS   = 60
SPARKLINE_MINUTES           = 60
FEED_STALE_THRESHOLD_SECONDS= 180

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
