# TESTING_STRATEGY.md — Test Architecture

## Executive Summary

This document outlines the testing philosophy and architecture for the Algo Trading Platform. Testing is layered:
- **Unit tests** verify individual components in isolation
- **Integration tests** verify interactions between layers
- **CLI contract tests** verify the Phase 1 standalone engine's input/output protocol
- **E2E tests** verify complete user journeys
- **CI/CD pipeline** ensures quality on every commit

**Philosophy:** Test the behavior that matters. Don't test implementation details. Focus P0 efforts on compute correctness (backtest metrics, optimization logic).

**Phase 1 is the testing foundation.** All Python engine unit and integration tests must pass with zero Node.js, Redis, or UI dependency. The CI job for Phase 1 is intentionally lightweight — no services, no Docker, just Python.

---

## 1. Testing Philosophy

### What to Test

| Layer | Phase | What | Why | Priority |
|-------|-------|------|-----|----------|
| **Python CLI contract** | 1 | stdout JSONL protocol, exit codes, CLI flags, resume behavior | First interface used by agents and developers; must be rock-solid before wrapping | P0 |
| **Python (Engine)** | 1 | Indicators (correct calculation), Metrics (known input → known output), Backtests (strategy logic), Optimization (param search) | Computational correctness is irreversible; garbage in = garbage out | P0 |
| **Node.js (API)** | 3 | Job orchestration (state machine), Repository CRUD (DB correctness), LLM validation (schema parsing), Error propagation | Data consistency & job reliability | P0 |
| **React (UI)** | 3 | Component rendering (Wizard, Dashboard), User interactions (form submission, filter apply), State management (Zustand stores) | UX correctness & user satisfaction | P1 |
| **Integration** | 3 | Wizard → Job submission → Results display, Export pipeline end-to-end | Full feature validation | P0 |
| **E2E (Playwright)** | 3 | User journey: describe strategy → backtest → validate → export | Real-world usage | P1 |

### What NOT to Test

- **Implementation details** (e.g., testing if a function calls another internal function)
- **Third-party libraries** (Redis, SQLite, React Router are tested by their maintainers)
- **UI styling** (CSS is not testable; use visual regression testing if needed later)
- **Network I/O to external APIs** (mock instead)

### Test Naming Convention

```
test_[what_is_tested]__[given_precondition]__[expected_outcome]

# Examples
test_calculate_sharpe_ratio__with_negative_returns__returns_negative_value
test_job_service__submit_job__enqueues_to_bullmq
test_wizard__invalid_definition__renders_error_message
```

---

## 2. Phase 1 CLI Contract Testing

These tests verify the standalone engine's public interface: CLI flags, stdout protocol, exit codes, and resume behavior. They require no Node.js, Redis, or running services — just Python and a temp SQLite file.

**File structure:** `engine/tests/cli/`

**Framework:** pytest + `subprocess`

```python
# engine/tests/cli/test_cli_contract.py

import json
import subprocess
import sqlite3
from pathlib import Path
import pytest

STRATEGY_FIXTURE = "engine/tests/fixtures/simple_sma_strategy.json"
PARAM_GRID_FIXTURE = "engine/tests/fixtures/simple_param_grid.json"
OHLCV_FIXTURE_DIR = "engine/tests/fixtures/data_cache"   # tiny synthetic Parquet


class TestCLIFlags:
    """Verify CLI accepts valid flags and rejects invalid ones."""

    def test_missing_strategy_flag__exits_with_code_1(self, tmp_path):
        result = subprocess.run(
            ["python", "engine/run.py", "--instruments", "EURUSD", "--timeframes", "H1",
             "--db", str(tmp_path / "test.db"), "--data-dir", OHLCV_FIXTURE_DIR],
            capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "strategy" in result.stderr.lower()

    def test_invalid_strategy_json__exits_with_code_1(self, tmp_path):
        bad_strategy = tmp_path / "bad.json"
        bad_strategy.write_text("{not valid json")
        result = subprocess.run(
            ["python", "engine/run.py", "--strategy", str(bad_strategy),
             "--instruments", "EURUSD", "--timeframes", "H1",
             "--db", str(tmp_path / "test.db"), "--data-dir", OHLCV_FIXTURE_DIR],
            capture_output=True, text=True
        )
        assert result.returncode == 1

    def test_strategy_failing_schema_validation__exits_with_code_1(self, tmp_path):
        bad_strategy = tmp_path / "schema_fail.json"
        bad_strategy.write_text('{"version": "1.0"}')  # missing required fields
        result = subprocess.run(
            ["python", "engine/run.py", "--strategy", str(bad_strategy),
             "--instruments", "EURUSD", "--timeframes", "H1",
             "--db", str(tmp_path / "test.db"), "--data-dir", OHLCV_FIXTURE_DIR],
            capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "validation" in result.stderr.lower()

    def test_missing_data_file__exits_with_code_1(self, tmp_path):
        result = subprocess.run(
            ["python", "engine/run.py", "--strategy", STRATEGY_FIXTURE,
             "--instruments", "NONEXISTENT", "--timeframes", "H1",
             "--db", str(tmp_path / "test.db"), "--data-dir", OHLCV_FIXTURE_DIR],
            capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "parquet" in result.stderr.lower() or "not found" in result.stderr.lower()


class TestStdoutProtocol:
    """Verify stdout is valid newline-delimited JSON with the correct message types."""

    @pytest.fixture
    def run_result(self, tmp_path):
        result = subprocess.run(
            ["python", "engine/run.py",
             "--strategy", STRATEGY_FIXTURE,
             "--instruments", "EURUSD",
             "--timeframes", "H1",
             "--param-grid", PARAM_GRID_FIXTURE,
             "--db", str(tmp_path / "test.db"),
             "--data-dir", OHLCV_FIXTURE_DIR],
            capture_output=True, text=True
        )
        return result

    def test_exit_code_zero_on_success(self, run_result):
        assert run_result.returncode == 0

    def test_stdout_is_valid_jsonl(self, run_result):
        lines = [l for l in run_result.stdout.strip().splitlines() if l]
        for line in lines:
            json.loads(line)  # raises if invalid

    def test_stdout_contains_progress_messages(self, run_result):
        messages = [json.loads(l) for l in run_result.stdout.strip().splitlines() if l]
        types = [m["type"] for m in messages]
        assert "progress" in types

    def test_stdout_contains_result_messages(self, run_result):
        messages = [json.loads(l) for l in run_result.stdout.strip().splitlines() if l]
        types = [m["type"] for m in messages]
        assert "result" in types

    def test_stdout_ends_with_completed_message(self, run_result):
        last_line = run_result.stdout.strip().splitlines()[-1]
        last = json.loads(last_line)
        assert last["type"] == "completed"
        assert "best_params" in last
        assert "best_metrics" in last
        assert "db_path" in last

    def test_progress_pct_is_monotonically_increasing(self, run_result):
        messages = [json.loads(l) for l in run_result.stdout.strip().splitlines() if l]
        progress = [m["pct"] for m in messages if m["type"] == "progress"]
        assert progress == sorted(progress)
        assert progress[-1] <= 100

    def test_result_messages_have_all_required_metrics(self, run_result):
        messages = [json.loads(l) for l in run_result.stdout.strip().splitlines() if l]
        results = [m for m in messages if m["type"] == "result"]
        required_metrics = {"sharpe_ratio", "max_drawdown", "win_rate", "net_pnl",
                            "num_trades", "profit_factor", "calmar_ratio"}
        for r in results:
            assert required_metrics.issubset(set(r["metrics"].keys()))

    def test_errors_go_to_stderr_not_stdout(self, tmp_path):
        """A failing run must not pollute stdout with non-JSON."""
        result = subprocess.run(
            ["python", "engine/run.py",
             "--strategy", STRATEGY_FIXTURE,
             "--instruments", "NONEXISTENT",
             "--timeframes", "H1",
             "--db", str(tmp_path / "test.db"),
             "--data-dir", OHLCV_FIXTURE_DIR],
            capture_output=True, text=True
        )
        # stdout must be empty or valid JSONL (no raw tracebacks)
        for line in result.stdout.strip().splitlines():
            if line:
                json.loads(line)  # raises if error text leaked to stdout


class TestSQLitePersistence:
    """Verify results are written to SQLite correctly after a CLI run."""

    def test_job_row_created_with_completed_status(self, tmp_path):
        db_path = tmp_path / "test.db"
        subprocess.run(
            ["python", "engine/run.py",
             "--strategy", STRATEGY_FIXTURE,
             "--instruments", "EURUSD",
             "--timeframes", "H1",
             "--db", str(db_path),
             "--data-dir", OHLCV_FIXTURE_DIR],
            capture_output=True
        )
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT status FROM jobs ORDER BY created_at DESC LIMIT 1").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "completed"

    def test_runs_written_per_param_combo(self, tmp_path):
        db_path = tmp_path / "test.db"
        subprocess.run(
            ["python", "engine/run.py",
             "--strategy", STRATEGY_FIXTURE,
             "--instruments", "EURUSD",
             "--timeframes", "H1",
             "--param-grid", PARAM_GRID_FIXTURE,  # 3 values × 2 values = 6 combos
             "--db", str(db_path),
             "--data-dir", OHLCV_FIXTURE_DIR],
            capture_output=True
        )
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        conn.close()
        assert count == 6


class TestResumeJob:
    """Verify an interrupted job can be resumed without re-running completed runs."""

    def test_resume_skips_already_completed_runs(self, tmp_path):
        db_path = tmp_path / "test.db"

        # First run (full)
        r1 = subprocess.run(
            ["python", "engine/run.py",
             "--strategy", STRATEGY_FIXTURE,
             "--instruments", "EURUSD",
             "--timeframes", "H1",
             "--param-grid", PARAM_GRID_FIXTURE,
             "--db", str(db_path),
             "--data-dir", OHLCV_FIXTURE_DIR],
            capture_output=True, text=True
        )
        completed = json.loads(r1.stdout.strip().splitlines()[-1])
        job_id = completed["job_id"]

        conn = sqlite3.connect(db_path)
        runs_before = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        conn.close()

        # Resume (nothing to do — should complete immediately with same count)
        r2 = subprocess.run(
            ["python", "engine/run.py",
             "--resume-job", job_id,
             "--db", str(db_path),
             "--data-dir", OHLCV_FIXTURE_DIR],
            capture_output=True, text=True
        )
        assert r2.returncode == 0

        conn = sqlite3.connect(db_path)
        runs_after = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        conn.close()

        assert runs_after == runs_before  # no duplicate runs inserted
```

**Fixtures needed** (`engine/tests/fixtures/`):

| File | Description |
|------|-------------|
| `simple_sma_strategy.json` | Minimal valid `StrategyDefinition` v1 using a single SMA |
| `simple_param_grid.json` | Small grid (e.g. `{"sma_period": [10, 20, 30], "sl_pips": [15, 20]}`) |
| `data_cache/EURUSD/H1.parquet` | Synthetic OHLCV data (500 bars), deterministic seed |

The synthetic Parquet is generated once by a script (`engine/tests/fixtures/generate_fixtures.py`) and committed to the repo. It must be small (< 100 KB) and produce deterministic backtest results.

---

## 3. Python Engine Testing

### Unit Tests

**File structure:** `engine/tests/unit/test_*.py`

**Framework:** pytest

**Example: Indicator Testing**

```python
# engine/tests/unit/test_indicators.py

import pytest
import numpy as np
import pandas as pd
from engine.backtest.indicators import calculate_sma, calculate_rsi

class TestSimpleMovingAverage:
    """Test SMA calculator."""
    
    def test_calculate_sma__basic_sequence__returns_correct_values(self):
        """SMA should return rolling mean of N bars."""
        prices = np.array([1, 2, 3, 4, 5], dtype=float)
        period = 3
        
        result = calculate_sma(prices, period)
        
        # First period-1 values should be NaN
        assert all(np.isnan(result[:period-1]))
        # SMA(3) = [-, -, 2, 3, 4] = [(1+2+3)/3, (2+3+4)/3, (3+4+5)/3]
        expected = [np.nan, np.nan, 2.0, 3.0, 4.0]
        np.testing.assert_array_almost_equal(result, expected, decimal=5)
    
    def test_calculate_sma__single_price__returns_same_price(self):
        """SMA with period=1 equals input."""
        prices = np.array([100, 101, 102])
        
        result = calculate_sma(prices, 1)
        
        np.testing.assert_array_equal(result, prices)
    
    def test_calculate_sma__with_nans__handles_gracefully(self):
        """SMA should skip NaN values."""
        prices = np.array([1, np.nan, 3, 4, 5])
        
        result = calculate_sma(prices, 2)
        
        # Implementation should handle this (backfill or skip)
        assert isinstance(result, np.ndarray)
    
    @pytest.mark.parametrize("period", [5, 10, 20, 50])
    def test_calculate_sma__various_periods__all_valid(self, period):
        """SMA should work for common periods."""
        prices = np.random.randn(200).cumsum()
        
        result = calculate_sma(prices, period)
        
        assert len(result) == len(prices)
        assert np.sum(~np.isnan(result)) > 50  # Most values valid


class TestRelativeStrengthIndex:
    """Test RSI calculator."""
    
    def test_calculate_rsi__uptrend__rsi_above_50(self):
        """RSI should be above 50 in uptrend."""
        # Monotonically increasing prices
        prices = np.arange(100, 150, dtype=float)
        
        result = calculate_rsi(prices, period=14)
        
        # Last values should approach 100 (max RSI)
        assert result[-1] > 70  # Strong uptrend
    
    def test_calculate_rsi__downtrend__rsi_below_50(self):
        """RSI should be below 50 in downtrend."""
        prices = np.arange(150, 100, -1, dtype=float)
        
        result = calculate_rsi(prices, period=14)
        
        assert result[-1] < 30  # Strong downtrend


class TestMetricsCalculation:
    """Test portfolio metrics."""
    
    def test_calculate_sharpe_ratio__constant_returns__returns_zero(self):
        """Sharpe ratio for constant returns should be zero (no volatility)."""
        equity_curve = np.ones(100) * 1000  # Flat equity
        
        from engine.metrics import calculate_sharpe_ratio
        sharpe = calculate_sharpe_ratio(equity_curve)
        
        assert sharpe == 0
    
    def test_calculate_max_drawdown__single_drop__correct_calculation(self):
        """Max drawdown should measure peak-to-trough decline."""
        equity_curve = np.array([1000, 1200, 800, 900])
        # Peak: 1200, Trough: 800
        # Max DD = (800 - 1200) / 1200 = -0.333
        
        from engine.metrics import calculate_max_drawdown
        dd = calculate_max_drawdown(equity_curve)
        
        expected = (800 - 1200) / 1200
        assert abs(dd - expected) < 0.001
```

### Integration Tests

**File structure:** `engine/tests/integration/test_*.py`

**Pattern: Known input → Known output**

```python
# engine/tests/integration/test_backtest_correctness.py

import pytest
from datetime import datetime
import numpy as np
import pandas as pd
from engine.backtest.runner import BacktestRunner
from engine.backtest.strategy import StrategyComposer
from shared.pydantic_models import StrategyDefinition
from engine.storage.db import get_db

class TestBacktestCorrectness:
    """Verify backtest produces correct results with known data."""
    
    @pytest.fixture
    def sample_ohlcv(self):
        """Load or generate known OHLCV data."""
        # Load from CSV fixture: engine/tests/fixtures/sample_ohlcv.csv
        df = pd.read_csv('engine/tests/fixtures/sample_ohlcv.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    @pytest.fixture
    def sample_strategy_definition(self):
        """Load known strategy definition."""
        return StrategyDefinition(
            version='1.0',
            name='Simple Trend',
            variant='basic',
            indicators=[
                {'name': 'sma_20', 'type': 'sma', 'params': {'period': 20}}
            ],
            entry_rules=[
                {'logic_type': 'indicator_above', 'indicator_ref': 'sma_20', 'threshold': None, 'side': 'long'}
            ],
            exit_rules=[
                {'logic_type': 'stop_loss'}
            ],
            position_management={
                'variant_type': 'basic',
                'stop_loss_pips': 20,
                'take_profit_pips': 40
            }
        )
    
    def test_backtest__known_data__produces_expected_metrics(self, sample_ohlcv, sample_strategy_definition):
        """Backtest with known data should produce known metrics."""
        runner = BacktestRunner(strategy=sample_strategy_definition)
        result = runner.run(sample_ohlcv)
        
        # These numbers are from a prior run (fixtures/expected_metrics.json)
        EXPECTED_TRADES = 23
        EXPECTED_WIN_RATE = 0.56
        EXPECTED_SHARPE_MIN, EXPECTED_SHARPE_MAX = 1.37, 1.47  # ±0.05 tolerance
        
        assert result.num_trades == EXPECTED_TRADES, \
            f"Expected {EXPECTED_TRADES} trades, got {result.num_trades}"
        assert abs(result.win_rate - EXPECTED_WIN_RATE) < 0.001, \
            f"Expected win rate {EXPECTED_WIN_RATE}, got {result.win_rate}"
        assert EXPECTED_SHARPE_MIN <= result.sharpe_ratio <= EXPECTED_SHARPE_MAX, \
            f"Expected Sharpe in [{EXPECTED_SHARPE_MIN}, {EXPECTED_SHARPE_MAX}], got {result.sharpe_ratio}"
    
    def test_optimization__grid_search__converges_to_best_params(self, sample_ohlcv, sample_strategy_definition):
        """Grid search should find parameter combination with highest Sharpe."""
        param_grid = {
            'sma_period': [10, 20, 30],
            'take_profit_pips': [20, 40, 60]
        }
        
        from engine.optimization.grid_search import GridSearchOptimizer
        optimizer = GridSearchOptimizer(strategy=sample_strategy_definition)
        results = optimizer.run(sample_ohlcv, param_grid)
        
        # Best result should have highest Sharpe
        best = results.best
        assert best.sharpe_ratio == max(r.sharpe_ratio for r in results.runs)
```

### Fixtures

```python
# engine/tests/conftest.py

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

@pytest.fixture
def sample_equity_curve():
    """Generate realistic equity curve for testing metrics."""
    np.random.seed(42)
    daily_returns = np.random.normal(0.0005, 0.01, 252)  # 1 year of daily returns
    equity = np.cumprod(1 + daily_returns) * 10000
    return equity

@pytest.fixture
def sample_trades():
    """Generate sample trades for testing."""
    return [
        {'entry_price': 1.1000, 'exit_price': 1.1050, 'profit_pips': 50, 'duration_bars': 10},
        {'entry_price': 1.1050, 'exit_price': 1.0995, 'profit_pips': -55, 'duration_bars': 5},
        {'entry_price': 1.0995, 'exit_price': 1.1100, 'profit_pips': 105, 'duration_bars': 20},
    ]

@pytest.fixture
def mock_redis():
    """Mock Redis for testing job queue."""
    from unittest.mock import AsyncMock
    return AsyncMock()

@pytest.fixture
def mock_sqlite(tmp_path):
    """Temporary SQLite for integration tests."""
    db_path = tmp_path / "test.db"
    from engine.storage.db import init_db
    init_db(str(db_path))
    return db_path
```

---

## 4. Node.js API Testing

### Unit Tests

**File structure:** `api/tests/unit/test_*.ts`

**Framework:** Jest

```typescript
// api/tests/unit/job.service.test.ts

import { JobService } from '../../src/services/job.service';
import { StrategyRepository } from '../../src/db/repositories/strategy.repo';
import { Queue } from 'bullmq';
import { Database } from 'better-sqlite3';

describe('JobService', () => {
  let jobService: JobService;
  let mockQueue: Jest.Mocked<Queue>;
  let mockStrategyRepo: Jest.Mocked<StrategyRepository>;
  let mockDb: Database;

  beforeEach(() => {
    // Mock BullMQ
    mockQueue = {
      add: jest.fn().mockResolvedValue({ id: 'job-123' }),
    } as any;

    // Create job service with mocks
    jobService = new JobService(mockQueue, mockStrategyRepo);
  });

  describe('submitBacktestJob', () => {
    it('should enqueue backtest job and return job ID', async () => {
      const jobPayload = {
        strategy_id: 'strategy-123',
        instruments: ['EURUSD'],
        timeframes: ['H1'],
        parameter_grid: { sma_period: [20, 50] },
      };

      const result = await jobService.submitBacktestJob(jobPayload);

      expect(mockQueue.add).toHaveBeenCalledWith(
        'backtest',
        expect.objectContaining({ strategy_id: 'strategy-123' }),
        expect.any(Object)
      );
      expect(result.job_id).toBe('job-123');
    });

    it('should throw if strategy_id is invalid', async () => {
      const jobPayload = {
        strategy_id: 'nonexistent',
        instruments: ['EURUSD'],
        timeframes: ['H1'],
        parameter_grid: {},
      };

      mockStrategyRepo.findById.mockResolvedValueOnce(null);

      await expect(jobService.submitBacktestJob(jobPayload)).rejects.toThrow(
        'Strategy not found'
      );
    });

    it('should set job retry policy', async () => {
      const jobPayload = {
        strategy_id: 'strategy-123',
        instruments: ['EURUSD'],
        timeframes: ['H1'],
        parameter_grid: {},
      };

      await jobService.submitBacktestJob(jobPayload);

      expect(mockQueue.add).toHaveBeenCalledWith(
        'backtest',
        expect.any(Object),
        expect.objectContaining({
          attempts: 3,
          backoff: expect.objectContaining({ type: 'exponential' }),
        })
      );
    });
  });

  describe('getJobStatus', () => {
    it('should return job status from database', async () => {
      const mockJob = {
        id: 'job-123',
        status: 'processing',
        progress_pct: 45,
        created_at: new Date(),
      };

      jest.spyOn(mockDb, 'prepare').mockReturnValueOnce({
        get: jest.fn().mockReturnValueOnce(mockJob),
      } as any);

      const result = await jobService.getJobStatus('job-123');

      expect(result.status).toBe('processing');
      expect(result.progress_pct).toBe(45);
    });
  });
});
```

### Integration Tests

**Pattern: Real API + Mock Python, Mock Redis**

```typescript
// api/tests/integration/e2e-wizard-to-results.test.ts

import request from 'supertest';
import { app } from '../../src/server';
import { Database } from 'better-sqlite3';
import { mockPythonWorker } from '../mocks/python-worker';

describe('E2E: Wizard → Job → Results', () => {
  let db: Database;

  beforeAll(() => {
    // Initialize test database
    db = new Database(':memory:');
    initTestSchema(db);
  });

  afterEach(() => {
    // Clean up test data
    db.exec('DELETE FROM strategies; DELETE FROM jobs; DELETE FROM runs;');
  });

  it('should complete full flow from wizard to backtest results', async () => {
    // Step 1: Chat with wizard
    const chatResponse = await request(app)
      .post('/api/wizard/chat')
      .send({
        message: 'I want a breakout strategy that goes long when price breaks above 20-day high',
      });

    expect(chatResponse.status).toBe(200);
    const { strategy_id } = chatResponse.body;
    expect(strategy_id).toBeDefined();

    // Step 2: Create strategy from definition
    const strategyResponse = await request(app)
      .post('/api/strategies')
      .send(chatResponse.body.strategy_definition);

    expect(strategyResponse.status).toBe(201);

    // Step 3: Submit backtest job
    const jobResponse = await request(app)
      .post('/api/jobs')
      .send({
        strategy_id,
        instruments: ['EURUSD'],
        timeframes: ['H1'],
        parameter_grid: { sma_period: [20, 50] },
      });

    expect(jobResponse.status).toBe(202);  // Accepted
    const { job_id } = jobResponse.body;

    // Step 4: Mock Python worker completing job
    await mockPythonWorker({ job_id, strategy_id });

    // Step 5: Poll job status
    let statusResponse = await request(app).get(`/api/jobs/${job_id}`);
    expect(statusResponse.body.status).toBe('completed');

    // Step 6: Fetch results
    const resultsResponse = await request(app).get(`/api/results/${job_id}`);
    expect(resultsResponse.status).toBe(200);
    expect(resultsResponse.body.runs).toHaveLength(4);  // 2 timeframes × 2 SMA periods
    expect(resultsResponse.body.runs[0]).toMatchObject({
      instrument: expect.any(String),
      timeframe: expect.any(String),
      sharpe_ratio: expect.any(Number),
      max_drawdown: expect.any(Number),
    });
  });
});
```

---

## 5. React UI Testing

### Component Tests

**File structure:** `ui/tests/components/ComponentName.test.tsx`

**Framework:** Vitest + React Testing Library

```typescript
// ui/tests/components/Wizard.test.tsx

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { StrategyWizard } from '../../src/components/Wizard/StrategyWizard';
import * as wizardApi from '../../src/api/wizard.api';

vi.mock('../../src/api/wizard.api');

describe('StrategyWizard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders chat interface', () => {
    render(<StrategyWizard />);

    expect(screen.getByPlaceholderText(/describe your strategy/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
  });

  it('sends message and displays response', async () => {
    const mockResponse = {
      strategy_definition: {
        version: '1.0',
        name: 'Breakout',
        variant: 'basic',
        indicators: [...],
      },
      variants: {
        basic: {...},
        advanced: {...},
      },
    };

    vi.mocked(wizardApi.chatWithWizard).mockResolvedValueOnce(mockResponse);

    const user = userEvent.setup();
    render(<StrategyWizard />);

    const input = screen.getByPlaceholderText(/describe your strategy/i);
    await user.type(input, 'Breakout strategy');
    await user.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText(/Breakout/i)).toBeInTheDocument();
    });
  });

  it('toggles between basic and advanced variants', async () => {
    const mockResponse = {
      strategy_definition: { variant: 'basic' },
      variants: {
        basic: { position_management: { variant_type: 'basic' } },
        advanced: { position_management: { partial_take_profits: [...] } },
      },
    };

    vi.mocked(wizardApi.chatWithWizard).mockResolvedValueOnce(mockResponse);

    const user = userEvent.setup();
    render(<StrategyWizard />);

    // ... send message and wait for response ...

    const advancedToggle = screen.getByRole('button', { name: /advanced/i });
    await user.click(advancedToggle);

    expect(screen.getByText(/Partial Take Profits/i)).toBeInTheDocument();
  });

  it('validates strategy before submission', async () => {
    render(<StrategyWizard />);

    const submitButton = screen.getByRole('button', { name: /create strategy/i });
    fireEvent.click(submitButton);

    expect(screen.getByText(/Please fill required fields/i)).toBeInTheDocument();
  });
});
```

### Hook Tests

```typescript
// ui/tests/hooks/useJobProgress.test.ts

import { renderHook, act, waitFor } from '@testing-library/react';
import { useJobProgress } from '../../src/hooks/useJobProgress';
import * as WebSocket from 'ws';

vi.mock('ws');

describe('useJobProgress', () => {
  it('subscribes to WebSocket and updates progress', async () => {
    const mockWs = {
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      close: vi.fn(),
    };

    vi.mocked(WebSocket).mockReturnValueOnce(mockWs as any);

    const { result } = renderHook(() => useJobProgress('job-123'));

    // Initially null
    expect(result.current.progress).toBeNull();

    // Simulate WebSocket message
    act(() => {
      const callback = mockWs.addEventListener.mock.calls[0][1];
      callback({
        data: JSON.stringify({
          progress_pct: 50,
          current_instrument: 'EURUSD',
        }),
      });
    });

    expect(result.current.progress).toEqual({
      progress_pct: 50,
      current_instrument: 'EURUSD',
    });
  });
});
```

---

## 6. E2E Testing (Playwright)

**File structure:** `ui/tests/e2e/*.spec.ts`

**Framework:** Playwright

```typescript
// ui/tests/e2e/wizard-to-backtest.spec.ts

import { test, expect, Page } from '@playwright/test';

test.describe('Full User Journey: Wizard → Backtest', () => {
  let page: Page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();
    await page.goto('http://localhost:5173');
  });

  test('user describes strategy, submits backtest, sees results', async () => {
    // Navigate to Wizard
    await page.click('button:has-text("New Strategy")');
    expect(page.url()).toContain('/wizard');

    // Submit strategy description
    await page.fill('textarea', 'Breakout strategy when price breaks 20-day high');
    await page.click('button:has-text("Send")');

    // Wait for LLM response
    await page.waitForSelector('text=Strategy Definition');

    // Select Advanced variant
    await page.click('button:has-text("Advanced")');

    // Verify partial take profits appear
    expect(page.locator('text=Partial Take Profits')).toBeTruthy();

    // Create strategy
    await page.click('button:has-text("Create Strategy")');

    // Redirect to vault
    expect(page.url()).toContain('/vault');
    await page.waitForSelector('text=Breakout');

    // Submit backtest job
    await page.click('button:has-text("Start Backtest")');
    await page.fill('[placeholder="Select instruments"]', 'EURUSD');
    await page.click('button:has-text("Optimize & Backtest")');

    // Wait for dashboard
    expect(page.url()).toContain('/dashboard');
    await page.waitForSelector('text=Processing');

    // Monitor progress (should show live %)
    const progressBar = page.locator('.progress-bar');
    const initialProgress = await progressBar.evaluate(el => el.textContent);

    // Wait for completion (timeout: 5 minutes for E2E)
    await page.waitForSelector('text=Backtesting Complete', { timeout: 300000 });

    // Verify dashboard shows results
    expect(page.locator('.equity-curve')).toBeTruthy();
    expect(page.locator('.heatmap')).toBeTruthy();
    expect(page.locator('text=Sharpe Ratio:')).toBeTruthy();
  });
});
```

---

## 7. CI/CD Pipeline

### GitHub Actions

**File: `.github/workflows/ci.yml`**

```yaml
name: CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  # ── Phase 1: CLI contract (no services required) ──────────────────────────
  test-cli:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install engine dependencies
        run: cd engine && pip install -r requirements.txt

      - name: Generate test fixtures (synthetic OHLCV)
        run: python engine/tests/fixtures/generate_fixtures.py

      - name: CLI contract tests (no Redis, no Node.js)
        run: cd engine && pytest tests/cli -v

  # ── Phase 1+: Python unit + integration ───────────────────────────────────
  test-engine:
    runs-on: ubuntu-latest
    needs: test-cli   # engine tests only run if CLI contract passes
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          cd engine
          pip install -r requirements.txt
          pip install pytest pytest-cov mypy black flake8

      - name: Lint (mypy)
        run: cd engine && mypy src --strict

      - name: Format check (black)
        run: cd engine && black --check src tests

      - name: Unit tests
        run: cd engine && pytest tests/unit -v --cov=src --cov-report=xml

      - name: Integration tests
        run: cd engine && pytest tests/integration -v

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./engine/coverage.xml

  # ── Phase 3+: Node.js API (requires Redis) ────────────────────────────────
  # Node.js tests
  test-api:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node
        uses: actions/setup-node@v3
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: 'api/package-lock.json'
      
      - name: Install dependencies
        run: cd api && npm ci
      
      - name: Lint (ESLint)
        run: cd api && npm run lint
      
      - name: Type check (tsc)
        run: cd api && npm run type-check
      
      - name: Unit tests
        run: cd api && npm run test:unit -- --coverage
      
      - name: Integration tests
        run: cd api && npm run test:integration
        env:
          REDIS_URL: redis://localhost:6379
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  # React tests
  test-ui:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node
        uses: actions/setup-node@v3
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: 'ui/package-lock.json'
      
      - name: Install dependencies
        run: cd ui && npm ci
      
      - name: Lint (ESLint)
        run: cd ui && npm run lint
      
      - name: Type check (tsc)
        run: cd ui && npm run type-check
      
      - name: Component tests
        run: cd ui && npm run test -- --run --coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  # E2E tests (nightly only, takes ~30 minutes)
  test-e2e:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    services:
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup all services
        run: |
          # Build and start containers
          docker-compose -f docker-compose.test.yml up -d
      
      - name: Wait for services ready
        run: |
          timeout 60 bash -c 'until curl -f http://localhost:3001/health; do sleep 1; done'
      
      - name: Run Playwright E2E tests
        run: cd ui && npm run test:e2e
      
      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: ui/playwright-report/

  # Build & deploy (on main branch only)
  deploy:
    runs-on: ubuntu-latest
    needs: [test-engine, test-api, test-ui]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker images
        run: docker-compose build
      
      - name: Push to registry
        run: |
          docker login -u ${{ secrets.DOCKER_USER }} -p ${{ secrets.DOCKER_PASS }}
          docker-compose push
      
      - name: Deploy to production
        run: |
          # Deploy script (e.g., SSH to server, pull images, restart)
          echo "Deploying to production..."
```

### Test Coverage Gates

| Component | Min Coverage | Threshold |
|-----------|--------------|-----------|
| Python engine | 80% | Fail CI if < 80% |
| Node.js API | 70% | Fail CI if < 70% |
| React UI | 50% | Warn (not fail) if < 50% |

### Test Execution Timing

| Suite | Time | Trigger | Services needed |
|-------|------|---------|----------------|
| **CLI contract tests** | 1–2 min | Every commit (PR) | Python only |
| **Engine unit tests** | 3–5 min | Every commit (PR) | Python only |
| **Engine integration tests** | 5–10 min | Every commit (PR) | Python + SQLite |
| **Node.js unit + integration** | 5–10 min | Every commit (PR) | Python + Redis |
| **React component tests** | 3–5 min | Every commit (PR) | None |
| **E2E tests (Playwright)** | 20–30 min | Nightly (main branch only) | Full stack |
| **Full suite** | < 35 min | Main branch pre-deploy | Full stack |

---

## 8. Testing Long-Running Jobs Without Actually Running Them

### Problem

Backtest jobs can take hours or days. We can't wait that long in CI/CD tests.

### Solution: Mock Python Worker

```python
# engine/tests/mocks/mock_worker.py

class MockPythonWorker:
    """Simulate Python worker completion for E2E tests."""
    
    def __init__(self, db, redis):
        self.db = db
        self.redis = redis
    
    async def simulate_backtest_completion(self, job_id: str, num_runs: int = 5):
        """Insert fake backtest results into DB."""
        import random
        
        runs = []
        for i in range(num_runs):
            run = {
                'id': str(uuid4()),
                'job_id': job_id,
                'instrument': random.choice(['EURUSD', 'GBPUSD']),
                'timeframe': random.choice(['H1', 'D1']),
                'sharpe_ratio': round(random.uniform(0.5, 2.5), 2),
                'max_drawdown': round(random.uniform(-0.30, -0.05), 2),
                'net_pnl': round(random.uniform(100, 5000), 2),
                'win_rate': round(random.uniform(0.45, 0.70), 2),
            }
            stmt = self.db.prepare(
                """INSERT INTO runs 
                   (id, job_id, instrument, timeframe, sharpe_ratio, max_drawdown, net_pnl, win_rate)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
            )
            stmt.execute(run.values())
            runs.append(run)
        
        # Mark job completed
        stmt = self.db.prepare(
            "UPDATE jobs SET status='completed', completed_at=? WHERE id=?"
        )
        stmt.execute([datetime.now(), job_id])
        
        return runs
```

---

## Next Steps

1. Set up pytest + coverage for Python engine
2. Set up Jest + Vitest for Node.js and React
3. Configure GitHub Actions workflow
4. Create fixture data (sample OHLCV, known-good metrics)
5. Implement first batch of unit tests (indicators, metrics)
