"""RobustnessScorer: aggregate all robustness signals into a 0–100 composite score.

Combines five signals with fixed weights:

  Component              Weight  Signal
  ─────────────────────────────────────────────────────────────
  OOS retention           35%    oos_sharpe / is_sharpe ratio
  WF efficiency           25%    mean_oos / mean_is across windows
  MC P5 Sharpe            20%    5th-percentile Sharpe from Monte Carlo
  Parameter stability     10%    overall_stability from sensitivity analysis
  Permutation p-value     10%    statistical significance of the strategy edge

Grading:
  A  ≥ 80  — publication-quality robustness
  B  ≥ 65  — solid, fit for forward testing
  C  ≥ 50  — marginal, proceed with caution
  F  < 50  — insufficient evidence of edge

Decision: GO if composite_score ≥ 60, else NO-GO.

Any missing signal (module not run) is excluded and the remaining weights are
renormalised so the score is always comparable.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Scoring functions: each returns a value in [0.0, 100.0]
# ---------------------------------------------------------------------------

def _score_oos_retention(oos_sharpe: float, is_sharpe: float) -> float:
    """Score based on how well OOS Sharpe tracks IS Sharpe.

    Mapping:
      retention >= 1.0  → 100
      retention = 0.5   →  50
      retention = 0.0   →   0
      retention < 0.0   →   0
    """
    if is_sharpe <= 0.0:
        # IS itself has no edge; OOS positive = bonus, OOS negative = penalty
        return max(0.0, min(100.0, 50.0 + oos_sharpe * 50.0))
    retention = oos_sharpe / is_sharpe
    return max(0.0, min(100.0, retention * 100.0))


def _score_wf_efficiency(wf_efficiency: float | None) -> float | None:
    """Score WF efficiency.

    Mapping:
      >= 0.7  → 100
      0.5     →  75
      0.0     →   0
      < 0.0   →   0
    """
    if wf_efficiency is None:
        return None
    if wf_efficiency >= 0.7:
        return 100.0
    if wf_efficiency >= 0.5:
        # linear 0.5 → 75, 0.7 → 100
        return 75.0 + (wf_efficiency - 0.5) / 0.2 * 25.0
    return max(0.0, wf_efficiency / 0.5 * 75.0)


def _score_mc_p5_sharpe(p5_sharpe: float | None) -> float | None:
    """Score 5th-percentile Sharpe from Monte Carlo.

    Mapping:
      p5 >= 0.5  → 100
      p5 = 0     →  50
      p5 = -0.5  →   0
    """
    if p5_sharpe is None:
        return None
    score = (p5_sharpe + 0.5) / 1.0 * 100.0
    return max(0.0, min(100.0, score))


def _score_stability(overall_stability: float | None) -> float | None:
    if overall_stability is None:
        return None
    return max(0.0, min(100.0, overall_stability * 100.0))


def _score_permutation(p_value: float | None) -> float | None:
    """Score based on permutation test p-value.

    Mapping:
      p < 0.01  → 100
      p < 0.05  →  75
      p < 0.10  →  50
      p >= 0.10 →   0
    """
    if p_value is None:
        return None
    if p_value < 0.01:
        return 100.0
    if p_value < 0.05:
        return 75.0
    if p_value < 0.10:
        return 50.0
    return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "oos_retention": 0.35,
    "wf_efficiency": 0.25,
    "mc_p5_sharpe": 0.20,
    "sensitivity": 0.10,
    "permutation": 0.10,
}


class RobustnessScorer:
    """Compute a composite robustness score from individual module outputs."""

    def score(
        self,
        oos_sharpe: float | None = None,
        is_sharpe: float | None = None,
        wf_efficiency: float | None = None,
        mc_p5_sharpe: float | None = None,
        overall_stability: float | None = None,
        permutation_p_value: float | None = None,
    ) -> dict[str, Any]:
        """Compute composite score from available robustness signals.

        All arguments are optional; missing signals are excluded and remaining
        weights are renormalised so the score is always on a 0–100 scale.

        Args:
            oos_sharpe: OOS Sharpe ratio (from separate OOS backtest).
            is_sharpe: IS Sharpe ratio (baseline backtest on same period).
            wf_efficiency: Walk-forward efficiency (mean_oos_sharpe / mean_is_sharpe).
            mc_p5_sharpe: 5th-percentile Sharpe from Monte Carlo simulation.
            overall_stability: 0–1 stability score from parameter sensitivity.
            permutation_p_value: p-value from permutation significance test.

        Returns:
            Dict with ``composite_score`` (0–100), ``grade`` (A/B/C/F),
            ``go_nogo`` (GO/NO-GO), and ``components`` breakdown.
        """
        raw_scores: dict[str, float | None] = {
            "oos_retention": (
                _score_oos_retention(oos_sharpe, is_sharpe)  # type: ignore[arg-type]
                if oos_sharpe is not None and is_sharpe is not None
                else None
            ),
            "wf_efficiency": _score_wf_efficiency(wf_efficiency),
            "mc_p5_sharpe": _score_mc_p5_sharpe(mc_p5_sharpe),
            "sensitivity": _score_stability(overall_stability),
            "permutation": _score_permutation(permutation_p_value),
        }

        # Renormalise weights excluding missing signals
        available = {k: v for k, v in raw_scores.items() if v is not None}
        total_weight = sum(_WEIGHTS[k] for k in available)

        if not available or total_weight == 0.0:
            return {
                "composite_score": None,
                "grade": None,
                "go_nogo": None,
                "components": _build_components(raw_scores),
            }

        composite = sum(
            available[k] * _WEIGHTS[k] / total_weight for k in available
        )
        composite = round(composite, 1)
        grade = _grade(composite)

        components = _build_components(raw_scores, total_weight)

        return {
            "composite_score": composite,
            "grade": grade,
            "go_nogo": "GO" if composite >= 60.0 else "NO-GO",
            "components": components,
        }


def _grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    return "F"


def _build_components(
    raw_scores: dict[str, float | None],
    total_weight: float = 1.0,
) -> dict[str, Any]:
    components: dict[str, Any] = {}
    for key, raw in raw_scores.items():
        w = _WEIGHTS[key]
        components[key] = {
            "score": round(raw, 1) if raw is not None else None,
            "weight": w,
            "effective_weight": round(w / total_weight, 4) if raw is not None else 0.0,
        }
    return components
