"""Unit tests for atr_robust and atr_gaussian indicators."""
from __future__ import annotations

import numpy as np
import pytest

from src.backtest.indicators import IndicatorRegistry
from src.backtest.indicators.volatility import atr_robust, atr_gaussian
from src.models import IndicatorDef, StrategyDefinition, PositionManagement, RuleDef


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

RNG = np.random.default_rng(42)
N = 100
CLOSE = np.cumsum(RNG.normal(0, 1, N)) + 100.0
HIGH = CLOSE + RNG.uniform(0.1, 1.0, N)
LOW = CLOSE - RNG.uniform(0.1, 1.0, N)

PERIOD = 14


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["atr_robust", "atr_gaussian"])
def test_registered(name: str) -> None:
    fn = IndicatorRegistry.get(name)
    assert callable(fn)


# ---------------------------------------------------------------------------
# Output shape and NaN warm-up
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_robust_same_length_as_input(self) -> None:
        result = atr_robust(CLOSE, HIGH, LOW, period=PERIOD)
        assert len(result) == N

    def test_gaussian_same_length_as_input(self) -> None:
        result = atr_gaussian(CLOSE, HIGH, LOW, period=PERIOD)
        assert len(result) == N

    def test_robust_nan_warmup(self) -> None:
        result = atr_robust(CLOSE, HIGH, LOW, period=PERIOD)
        assert np.all(np.isnan(result[: PERIOD - 1]))
        assert not np.isnan(result[PERIOD - 1])

    def test_gaussian_nan_warmup(self) -> None:
        result = atr_gaussian(CLOSE, HIGH, LOW, period=PERIOD)
        assert np.all(np.isnan(result[: PERIOD - 1]))
        assert not np.isnan(result[PERIOD - 1])

    def test_robust_all_nan_when_period_exceeds_length(self) -> None:
        short = np.array([1.0, 2.0, 3.0])
        result = atr_robust(short, short, short, period=10)
        assert np.all(np.isnan(result))

    def test_gaussian_all_nan_when_period_exceeds_length(self) -> None:
        short = np.array([1.0, 2.0, 3.0])
        result = atr_gaussian(short, short, short, period=10)
        assert np.all(np.isnan(result))


# ---------------------------------------------------------------------------
# Values are positive (TR is always >= 0)
# ---------------------------------------------------------------------------

class TestPositiveValues:
    def test_robust_positive(self) -> None:
        result = atr_robust(CLOSE, HIGH, LOW, period=PERIOD)
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0)

    def test_gaussian_positive(self) -> None:
        result = atr_gaussian(CLOSE, HIGH, LOW, period=PERIOD)
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0)


# ---------------------------------------------------------------------------
# Outlier exclusion effect
# ---------------------------------------------------------------------------

class TestOutlierExclusion:
    def test_robust_lower_than_plain_atr_when_spike_present(self) -> None:
        """Inject a large spike and verify atr_robust is lower than plain atr."""
        from src.backtest.indicators.volatility import atr as plain_atr

        close = np.ones(50) * 100.0
        high = close + 1.0
        low = close - 1.0
        # Inject a spike at bar 20
        high[20] = 200.0
        low[20] = 50.0

        plain = plain_atr(close, high, low, period=14)
        robust = atr_robust(close, high, low, period=14, n_sigma=1.5)

        # The spike bar and the bars just after it should show robust < plain
        # (once the spike enters the rolling window)
        valid_both = ~np.isnan(plain) & ~np.isnan(robust)
        assert np.any(robust[valid_both] < plain[valid_both])

    def test_gaussian_lower_than_plain_atr_when_spike_present(self) -> None:
        from src.backtest.indicators.volatility import atr as plain_atr

        close = np.ones(50) * 100.0
        high = close + 1.0
        low = close - 1.0
        high[20] = 200.0
        low[20] = 50.0

        plain = plain_atr(close, high, low, period=14)
        gauss = atr_gaussian(close, high, low, period=14, n_sigma=1.5)

        valid_both = ~np.isnan(plain) & ~np.isnan(gauss)
        assert np.any(gauss[valid_both] < plain[valid_both])


# ---------------------------------------------------------------------------
# Gaussian weights: recent bars should drive value more than oldest bar
# ---------------------------------------------------------------------------

class TestGaussianWeighting:
    def test_recent_bar_influence_greater_than_oldest(self) -> None:
        """A bump on the most recent bar should shift atr_gaussian more than
        the same bump on the oldest bar of the window.

        Uses n_sigma=100 to disable outlier exclusion so only the kernel
        weighting is under test.
        """
        base_close = np.ones(30) * 100.0
        base_high = base_close + 1.0
        base_low = base_close - 1.0

        # Bump on last bar (most recent)
        high_recent = base_high.copy()
        high_recent[-1] += 10.0

        # Bump on bar at position -(period) (oldest in window)
        high_oldest = base_high.copy()
        high_oldest[-14] += 10.0

        kwargs = {"period": 14, "n_sigma": 100.0}
        gauss_recent = atr_gaussian(base_close, high_recent, base_low, **kwargs)
        gauss_oldest = atr_gaussian(base_close, high_oldest, base_low, **kwargs)
        baseline = atr_gaussian(base_close, base_high, base_low, **kwargs)

        delta_recent = float(gauss_recent[-1]) - float(baseline[-1])
        delta_oldest = float(gauss_oldest[-1]) - float(baseline[-1])

        assert delta_recent > delta_oldest


# ---------------------------------------------------------------------------
# Flat series: all variants should return the same value
# ---------------------------------------------------------------------------

class TestFlatSeries:
    def test_robust_flat_series(self) -> None:
        close = np.ones(30) * 100.0
        high = close + 2.0
        low = close - 2.0
        result = atr_robust(close, high, low, period=14)
        valid = result[~np.isnan(result)]
        np.testing.assert_allclose(valid, 4.0, rtol=1e-6)

    def test_gaussian_flat_series(self) -> None:
        close = np.ones(30) * 100.0
        high = close + 2.0
        low = close - 2.0
        result = atr_gaussian(close, high, low, period=14)
        valid = result[~np.isnan(result)]
        np.testing.assert_allclose(valid, 4.0, rtol=1e-6)


# ---------------------------------------------------------------------------
# High n_sigma → converges toward plain atr behaviour
# ---------------------------------------------------------------------------

class TestHighNSigmaConvergesToPlain:
    def test_robust_high_n_sigma_matches_rolling_mean(self) -> None:
        """With n_sigma=100 (no exclusion) atr_robust should equal a simple
        rolling mean of the True Range (not Wilder's EMA used by plain atr)."""
        from src.backtest.indicators.volatility import _compute_true_range

        close = CLOSE.copy()
        high = HIGH.copy()
        low = LOW.copy()

        robust = atr_robust(close, high, low, period=PERIOD, n_sigma=100.0)
        tr = _compute_true_range(close, high, low)

        # Manually compute rolling simple mean
        expected = np.full(N, np.nan, dtype=float)
        for i in range(PERIOD - 1, N):
            expected[i] = np.mean(tr[i - PERIOD + 1 : i + 1])

        valid = ~np.isnan(robust) & ~np.isnan(expected)
        np.testing.assert_allclose(robust[valid], expected[valid], rtol=1e-6)


# ---------------------------------------------------------------------------
# Pydantic schema validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ind_type,params", [
    ("atr_robust",   {"period": 14, "n_sigma": 2.0}),
    ("atr_gaussian", {"period": 14, "n_sigma": 2.0, "sigma_factor": 0.4}),
])
def test_pydantic_accepts_new_atr_types(ind_type: str, params: dict) -> None:
    sd = StrategyDefinition(
        version="1",
        name="test",
        variant="basic",
        indicators=[IndicatorDef(name="vol", type=ind_type, params=params)],  # type: ignore[arg-type]
        entry_rules=[RuleDef(indicator="vol", condition=">", value=0.001)],
        exit_rules=[RuleDef(indicator="vol", condition="<", value=0.0001)],
        position_management=PositionManagement(),
    )
    assert sd.indicators[0].type == ind_type
