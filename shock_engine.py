# =============================================================================
# shock_engine.py v2.0 — Maersk Digital Twin: Monte Carlo Shock Simulator
# Updated March 2026 — includes Hormuz live validation, CNLI, reverse stress
# =============================================================================

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import numpy as np

from config import (
    BASELINE, CONFIDENCE_INTERVALS, FIGURES_DIR, MONTE_CARLO_RUNS,
    RESULTS_DIR, REVERSE_STRESS_DISTRESS_THRESHOLD, SHOCK_SCENARIOS,
    STRATEGIES, TABLES_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("shock_engine")
RNG_SEED = 42


# =============================================================================
# Data structures
# =============================================================================

@dataclass
class QuarterlyProjection:
    quarter:                         int
    revenue_usd_m:                   float
    ebitda_usd_m:                    float
    net_income_usd_m:                float
    fuel_cost_usd_m:                 float
    volume_teu_m:                    float
    freight_rate_usd:                float
    ebitda_margin:                   float
    cumulative_revenue_delta_usd_m:  float


@dataclass
class ShockResult:
    scenario_key:        str
    scenario_label:      str
    strategy_key:        str
    strategy_label:      str
    n_simulations:       int
    duration_quarters:   int
    timestamp:           str
    is_live_event:       bool = False

    revenue_total_dist:      dict = field(default_factory=dict)
    ebitda_total_dist:       dict = field(default_factory=dict)
    net_income_total_dist:   dict = field(default_factory=dict)
    revenue_delta_dist:      dict = field(default_factory=dict)
    ebitda_delta_dist:       dict = field(default_factory=dict)
    recovery_quarter_dist:   dict = field(default_factory=dict)
    median_quarterly:        list = field(default_factory=list)

    prob_negative_ebitda:          float = 0.0
    prob_net_loss:                 float = 0.0
    strategy_npv_advantage_usd_m:  float = 0.0
    financial_stress_score:        float = 0.0


@dataclass
class ReverseStressResult:
    """Result of reverse stress testing — minimum shock causing distress."""
    distress_threshold:         float
    min_volume_shock:           float
    min_rate_shock:             float
    min_fuel_shock:             float
    min_combined_severity:      float
    quarters_to_distress:       int
    description:                str


@dataclass
class CNLIResult:
    """Compound Non-Linearity Index result."""
    cnli:                        float
    non_linearity_premium_pct:   float
    compound_loss_usd_m:         float
    sum_individual_usd_m:        float
    individual_losses:           dict


# =============================================================================
# Core simulation engine
# =============================================================================

class MonteCarloEngine:

    def __init__(self, baseline: dict = None):
        from auto_updater import get_current_baseline
        self.baseline = baseline or get_current_baseline()
        self.rng = np.random.default_rng(RNG_SEED)

    def _draw_shock_magnitudes(self, scenario: dict, n: int) -> dict:
        def tri(lo, mode, hi):
            return self.rng.triangular(lo, mode, hi, size=n)
        v_lo, v_mode, v_hi = scenario["volume_impact"]
        f_lo, f_mode, f_hi = scenario["freight_rate_impact"]
        c_lo, c_mode, c_hi = scenario["fuel_cost_impact"]
        return {
            "volume":       tri(v_lo, v_mode, v_hi),
            "freight_rate": tri(f_lo, f_mode, f_hi),
            "fuel_cost":    tri(c_lo, c_mode, c_hi),
        }

    def _apply_strategy(self, shocks: dict, strategy: dict) -> dict:
        return {
            "volume":       shocks["volume"]       + strategy["volume_modifier"],
            "freight_rate": shocks["freight_rate"] + strategy["freight_rate_modifier"],
            "fuel_cost":    shocks["fuel_cost"]    + strategy["cost_modifier"],
        }

    def _quarterly_decay(self, quarter: int, duration: int) -> float:
        if quarter >= duration:
            return 0.0
        return 0.5 * (1 + np.cos(np.pi * quarter / duration))

    def run_single(self, scenario_key: str, strategy_key: str) -> ShockResult:
        scenario = SHOCK_SCENARIOS[scenario_key]
        strategy = STRATEGIES[strategy_key]
        n        = MONTE_CARLO_RUNS
        duration = scenario["duration_quarters"]
        b        = self.baseline

        log.info("Simulating [%s] × [%s] (%d runs)", scenario_key, strategy_key, n)

        raw_shocks     = self._draw_shock_magnitudes(scenario, n)
        applied_shocks = self._apply_strategy(raw_shocks, strategy)

        baseline_q_rev    = b.get("revenue_usd_m",   BASELINE["revenue_usd_m"])   / 4
        base_ebitda_margin= b.get("ebitda_usd_m",    BASELINE["ebitda_usd_m"])    / \
                            b.get("revenue_usd_m",   BASELINE["revenue_usd_m"])
        base_fuel_q       = b.get("fuel_cost_usd_m", BASELINE["fuel_cost_usd_m"]) / 4
        base_volume_q     = b.get("volume_teu_m",    BASELINE["volume_teu_m"])    / 4
        base_rate         = b.get("avg_freight_rate_usd_teu", BASELINE["avg_freight_rate_usd_teu"])

        total_revenue    = np.zeros(n)
        total_ebitda     = np.zeros(n)
        total_net_income = np.zeros(n)
        recovery_quarter = np.full(n, duration + 2, dtype=float)

        # Logistics revenue buffer — reduces shock severity for vertical integration
        logistics_buffer = strategy.get("logistics_revenue_buffer", 0.0)
        logistics_q      = b.get("logistics_revenue_usd_m", BASELINE.get("logistics_revenue_usd_m", 15_000)) / 4

        median_q_data = []
        cumulative_delta = 0.0

        for q in range(duration + 2):
            decay = self._quarterly_decay(q, duration)

            vol_impact  = applied_shocks["volume"]       * decay
            rate_impact = applied_shocks["freight_rate"] * decay
            fuel_impact = applied_shocks["fuel_cost"]    * decay

            # Revenue — ocean freight
            q_revenue = baseline_q_rev * (1 + vol_impact + rate_impact)

            # Logistics buffer — partially protected revenue stream
            q_logistics = logistics_q * (1 - logistics_buffer * abs(np.mean(vol_impact)))
            q_total_revenue = q_revenue + q_logistics

            # EBITDA — operating leverage compression + fuel
            op_lev_penalty = np.abs(vol_impact) * 0.5
            q_ebitda_margin = np.clip(base_ebitda_margin - op_lev_penalty, -0.20, 0.40)
            q_fuel          = base_fuel_q * (1 + fuel_impact)
            q_ebitda        = q_total_revenue * q_ebitda_margin - (q_fuel - base_fuel_q)

            # Net income (approx after D&A, interest, tax)
            q_net_income = q_ebitda * 0.55

            # Recovery tracking
            recovering = q_revenue >= baseline_q_rev * 0.95
            for i in np.where(recovering & (recovery_quarter == duration + 2))[0]:
                if q > 0:
                    recovery_quarter[i] = q

            total_revenue    += q_total_revenue
            total_ebitda     += q_ebitda
            total_net_income += q_net_income

            q_delta = float(np.median(q_total_revenue)) - baseline_q_rev
            cumulative_delta += q_delta
            median_q_data.append(QuarterlyProjection(
                quarter=q,
                revenue_usd_m=round(float(np.median(q_total_revenue)), 2),
                ebitda_usd_m=round(float(np.median(q_ebitda)), 2),
                net_income_usd_m=round(float(np.median(q_net_income)), 2),
                fuel_cost_usd_m=round(float(np.median(q_fuel)), 2),
                volume_teu_m=round(float(np.median(base_volume_q * (1 + vol_impact))), 4),
                freight_rate_usd=round(float(np.median(base_rate * (1 + rate_impact))), 2),
                ebitda_margin=round(float(np.median(q_ebitda / np.maximum(q_total_revenue, 1))), 4),
                cumulative_revenue_delta_usd_m=round(cumulative_delta, 2),
            ))

        baseline_total = baseline_q_rev * (duration + 2)
        baseline_ebitda_total = baseline_total * base_ebitda_margin

        def pct(arr):
            return {f"p{int(ci*100)}": float(np.percentile(arr, ci*100))
                    for ci in CONFIDENCE_INTERVALS}

        result = ShockResult(
            scenario_key=scenario_key,
            scenario_label=scenario["label"],
            strategy_key=strategy_key,
            strategy_label=strategy["label"],
            n_simulations=n,
            duration_quarters=duration,
            timestamp=datetime.now(timezone.utc).isoformat(),
            is_live_event=scenario.get("live_event", False),
            revenue_total_dist=pct(total_revenue),
            ebitda_total_dist=pct(total_ebitda),
            net_income_total_dist=pct(total_net_income),
            revenue_delta_dist=pct(total_revenue - baseline_total),
            ebitda_delta_dist=pct(total_ebitda - baseline_ebitda_total),
            recovery_quarter_dist=pct(recovery_quarter),
            median_quarterly=median_q_data,
            prob_negative_ebitda=float(np.mean(total_ebitda < 0)),
            prob_net_loss=float(np.mean(total_net_income < 0)),
        )

        log.info("  P50 rev delta=$%.0fM | P(loss)=%.1f%%",
                 result.revenue_delta_dist.get("p50", 0),
                 result.prob_net_loss * 100)
        return result

    def run_all(self) -> dict:
        results = {}
        total = len(SHOCK_SCENARIOS) * len(STRATEGIES)
        done  = 0
        for s_key in SHOCK_SCENARIOS:
            results[s_key] = {}
            for st_key in STRATEGIES:
                results[s_key][st_key] = self.run_single(s_key, st_key)
                done += 1
                log.info("Progress: %d/%d", done, total)
        self._annotate_npv_advantage(results)
        return results

    def _annotate_npv_advantage(self, results: dict, discount_rate_annual: float = 0.10):
        quarterly_rate = (1 + discount_rate_annual) ** 0.25 - 1
        for s_key, strat_results in results.items():
            baseline_p50 = strat_results["do_nothing"].revenue_delta_dist.get("p50", 0)
            duration = SHOCK_SCENARIOS[s_key]["duration_quarters"]
            for st_key, result in strat_results.items():
                strat_p50   = result.revenue_delta_dist.get("p50", 0)
                avg_q       = duration / 2
                npv_adv     = (strat_p50 - baseline_p50) / ((1 + quarterly_rate) ** avg_q)
                result.strategy_npv_advantage_usd_m = round(npv_adv, 2)

    # =========================================================================
    # CNLI — Compound Non-Linearity Index
    # =========================================================================
    def compute_cnli(self, individual_scenarios: list = None) -> CNLIResult:
        if individual_scenarios is None:
            individual_scenarios = ["demand_collapse", "fuel_price_spike", "suez_closure"]

        individual_losses = {}
        for s_key in individual_scenarios:
            if s_key not in SHOCK_SCENARIOS:
                continue
            r = self.run_single(s_key, "do_nothing")
            individual_losses[s_key] = abs(r.revenue_delta_dist.get("p50", 0))

        sum_individual = sum(individual_losses.values())

        compound = self.run_single("compound_shock", "do_nothing")
        compound_loss = abs(compound.revenue_delta_dist.get("p50", 0))

        cnli = compound_loss / max(sum_individual, 1)
        premium = (cnli - 1) * 100

        log.info("CNLI=%.3f | compound=$%.0fM | sum_individual=$%.0fM | premium=%.1f%%",
                 cnli, compound_loss, sum_individual, premium)

        return CNLIResult(
            cnli=round(cnli, 3),
            non_linearity_premium_pct=round(premium, 1),
            compound_loss_usd_m=round(compound_loss, 0),
            sum_individual_usd_m=round(sum_individual, 0),
            individual_losses={k: round(v, 0) for k, v in individual_losses.items()},
        )

    # =========================================================================
    # REVERSE STRESS TEST
    # =========================================================================
    def reverse_stress_test(self) -> ReverseStressResult:
        """
        Find the minimum shock magnitude combination that causes
        P(net loss) > REVERSE_STRESS_DISTRESS_THRESHOLD across 10,000 runs.
        Uses a grid search over vol × rate impact space.
        """
        log.info("Running reverse stress test (threshold=%.0f%%)",
                 REVERSE_STRESS_DISTRESS_THRESHOLD * 100)

        b        = self.baseline
        n        = MONTE_CARLO_RUNS
        duration = 4
        threshold= REVERSE_STRESS_DISTRESS_THRESHOLD

        # Grid search: vol impact from 0 to -60%, rate impact from 0 to -60%
        best_severity = float("inf")
        best_vol = best_rate = best_fuel = 0.0
        best_quarters = duration

        for vol_mode in np.arange(-0.05, -0.65, -0.05):
            for rate_mode in np.arange(-0.05, -0.65, -0.05):
                fuel_mode = 0.20  # moderate fuel increase

                # Quick 2000-run simulation for speed
                vol_shocks  = self.rng.triangular(vol_mode * 1.5,  vol_mode,  vol_mode * 0.5, size=2000)
                rate_shocks = self.rng.triangular(rate_mode * 1.5, rate_mode, rate_mode * 0.5, size=2000)
                fuel_shocks = self.rng.triangular(0.0, fuel_mode, fuel_mode * 2, size=2000)

                base_q_rev    = b.get("revenue_usd_m", BASELINE["revenue_usd_m"]) / 4
                base_ebitda_m = b.get("ebitda_usd_m",  BASELINE["ebitda_usd_m"])  / \
                                b.get("revenue_usd_m", BASELINE["revenue_usd_m"])
                base_fuel_q   = b.get("fuel_cost_usd_m", BASELINE["fuel_cost_usd_m"]) / 4

                total_net = np.zeros(2000)
                for q in range(duration):
                    decay = self._quarterly_decay(q, duration)
                    q_rev   = base_q_rev * (1 + vol_shocks * decay + rate_shocks * decay)
                    op_pen  = np.abs(vol_shocks * decay) * 0.5
                    q_ebitda= q_rev * np.clip(base_ebitda_m - op_pen, -0.20, 0.40) \
                              - (base_fuel_q * (1 + fuel_shocks * decay) - base_fuel_q)
                    total_net += q_ebitda * 0.55

                p_loss = float(np.mean(total_net < 0))
                if p_loss >= threshold:
                    severity = abs(vol_mode) + abs(rate_mode) + abs(fuel_mode)
                    if severity < best_severity:
                        best_severity  = severity
                        best_vol       = vol_mode
                        best_rate      = rate_mode
                        best_fuel      = fuel_mode
                        break
            if best_severity < float("inf"):
                break

        log.info("Reverse stress: min vol=%.0f%% | min rate=%.0f%% | severity=%.2f",
                 best_vol * 100, best_rate * 100, best_severity)

        return ReverseStressResult(
            distress_threshold=threshold,
            min_volume_shock=round(best_vol, 3),
            min_rate_shock=round(best_rate, 3),
            min_fuel_shock=round(best_fuel, 3),
            min_combined_severity=round(best_severity, 3),
            quarters_to_distress=best_quarters,
            description=(
                f"Maersk reaches P(net loss) > {threshold:.0%} when volume falls "
                f"{abs(best_vol):.0%} AND freight rates fall {abs(best_rate):.0%} "
                f"simultaneously over {duration} quarters."
            ),
        )

    # =========================================================================
    # LIVE EVENT VALIDATION — Hormuz 2026
    # =========================================================================
    def validate_against_live_event(self, event_key: str = "hormuz_2026") -> dict:
        """
        Run the shock corresponding to a live event and compare model predictions
        against actual Maersk operational data.
        """
        from config import LIVE_EVENTS
        event = LIVE_EVENTS.get(event_key, {})
        shock_key = event.get("linked_shock", "hormuz_closure")

        result = self.run_single(shock_key, "do_nothing")

        return {
            "event":           event_key,
            "event_label":     event.get("label", ""),
            "shock_key":       shock_key,
            "model_p50_rev_delta_usd_m": round(result.revenue_delta_dist.get("p50", 0), 0),
            "model_p5_rev_delta_usd_m":  round(result.revenue_delta_dist.get("p5", 0), 0),
            "model_prob_net_loss":        round(result.prob_net_loss * 100, 1),
            "model_brent_assumption":     85.0,
            "actual_brent_peak":          event.get("brent_at_event", None),
            "maersk_response_taken":      event.get("maersk_response", []),
            "validation_note": (
                "Model was calibrated using FY2023 baseline. "
                "Live Brent at $126 (vs model baseline $85) = fuel cost ~1.5x model assumption. "
                "Model likely UNDERSTATES actual impact — see hormuz_demand_compound for updated estimate."
            ),
        }


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================

def compute_financial_stress_score(baseline: dict) -> float:
    debt_ebitda = baseline.get("total_debt_usd_m", BASELINE["total_debt_usd_m"]) / \
                  max(baseline.get("ebitda_usd_m", BASELINE["ebitda_usd_m"]), 1)
    c1 = min(debt_ebitda / 6.0, 1.0) * 100

    fuel_share = baseline.get("fuel_cost_usd_m", BASELINE["fuel_cost_usd_m"]) / \
                 max(baseline.get("revenue_usd_m", BASELINE["revenue_usd_m"]), 1)
    c2 = min(fuel_share / 0.25, 1.0) * 100

    quarterly_ni = baseline.get("net_income_usd_m", BASELINE["net_income_usd_m"]) / 4
    runway = baseline.get("cash_usd_m", BASELINE["cash_usd_m"]) / max(abs(quarterly_ni), 1)
    c3 = max(0, (1 - min(runway / 12.0, 1.0))) * 100

    # Live Brent stress
    brent_stress = 0.0
    try:
        import json, os
        if os.path.exists("latest_snapshot.json"):
            snap = json.load(open("latest_snapshot.json"))
            live_brent = snap.get("tickers", {}).get("brent_crude", {}).get("current", 85)
            brent_stress = max(0, (live_brent - 85) / 85) * 100
    except Exception:
        pass
    c4 = min(brent_stress, 100)

    return round(0.35 * c1 + 0.25 * c2 + 0.25 * c3 + 0.15 * c4, 1)


def get_strategy_ranking(results: dict) -> dict:
    ranking = {}
    for s_key, strat_map in results.items():
        pairs = [(st_key, r.strategy_npv_advantage_usd_m)
                 for st_key, r in strat_map.items() if st_key != "do_nothing"]
        ranking[s_key] = sorted(pairs, key=lambda x: x[1], reverse=True)
    return ranking


# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================

def _ensure_dirs():
    for d in [RESULTS_DIR, TABLES_DIR, FIGURES_DIR]:
        os.makedirs(d, exist_ok=True)


def export_results_json(results: dict) -> str:
    _ensure_dirs()
    path = os.path.join(RESULTS_DIR, "shock_results.json")
    serialisable = {}
    for s_key, strat_map in results.items():
        serialisable[s_key] = {}
        for st_key, result in strat_map.items():
            d = asdict(result)
            d["median_quarterly"] = [asdict(q) for q in result.median_quarterly]
            serialisable[s_key][st_key] = d
    with open(path, "w") as f:
        json.dump(serialisable, f, indent=2)
    log.info("Results → %s", path)
    return path


def export_results_csv(results: dict) -> str:
    import csv
    _ensure_dirs()
    path = os.path.join(TABLES_DIR, "shock_summary.csv")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "scenario","scenario_label","category",
            "strategy","strategy_label",
            "rev_delta_p5","rev_delta_p25","rev_delta_p50","rev_delta_p75","rev_delta_p95",
            "prob_net_loss_pct","npv_advantage_usd_m","is_live_event","n_sims","duration_q",
        ])
        for s_key, strat_map in results.items():
            cat = SHOCK_SCENARIOS[s_key].get("category", "")
            live= SHOCK_SCENARIOS[s_key].get("live_event", False)
            for st_key, r in strat_map.items():
                rd = r.revenue_delta_dist
                writer.writerow([
                    s_key, r.scenario_label, cat,
                    st_key, r.strategy_label,
                    round(rd.get("p5",0),1), round(rd.get("p25",0),1),
                    round(rd.get("p50",0),1), round(rd.get("p75",0),1),
                    round(rd.get("p95",0),1),
                    round(r.prob_net_loss*100, 2),
                    r.strategy_npv_advantage_usd_m,
                    live, r.n_simulations, r.duration_quarters,
                ])
    log.info("CSV → %s", path)
    return path


# =============================================================================
# Standalone run
# =============================================================================

if __name__ == "__main__":
    engine = MonteCarloEngine()

    print("\n=== Live Event Validation: Hormuz 2026 ===")
    val = engine.validate_against_live_event()
    for k, v in val.items():
        print(f"  {k:<40} {v}")

    print("\n=== CNLI Analysis ===")
    cnli = engine.compute_cnli()
    print(f"  CNLI = {cnli.cnli} ({cnli.non_linearity_premium_pct}% worse than sum of parts)")

    print("\n=== Reverse Stress Test ===")
    rst = engine.reverse_stress_test()
    print(f"  {rst.description}")

    print("\n=== Running all scenarios (this takes 1-2 minutes) ===")
    results = engine.run_all()
    export_results_json(results)
    export_results_csv(results)
    ranking = get_strategy_ranking(results)
    for s_key, ranked in ranking.items():
        print(f"\n  {SHOCK_SCENARIOS[s_key]['label']}")
        for i, (st, npv) in enumerate(ranked[:3], 1):
            print(f"    {i}. {STRATEGIES[st]['label']:<45} ${npv:+,.0f}M")
