# CONVENTIONS.md — Coding Standards & Extension Patterns

## Executive Summary

This document establishes coding standards, naming conventions, and extension patterns for the Algo Trading Platform across Python, Node.js, React, and TypeScript. It ensures consistency, readability, and maintainability as developers add new indicators, robustness tests, and export formats.

---

## 1. Naming Conventions

### Python

| Category | Convention | Example |
|----------|-----------|---------|
| **Modules** | `snake_case.py` | `backtest_runner.py`, `monte_carlo.py` |
| **Classes** | `PascalCase` | `StrategyDefinition`, `BacktestRunner`, `OptimizationEngine` |
| **Functions** | `snake_case()` | `calculate_sma()`, `optimize_parameters()` |
| **Variables** | `snake_case` | `instrument_list`, `max_drawdown`, `equity_curve` |
| **Constants** | `UPPER_SNAKE_CASE` | `DEFAULT_SLIPPAGE_PIPS`, `MAX_ITERATIONS` |
| **Private** | `_snake_case()` | `_internal_backtest()`, `_validate_params()` |
| **Type hints** | Required (mypy strict) | `def run(job_id: str) -> RunResult:` |
| **Docstrings** | Google-style | See example below |

**Type hints mandatory:**
```python
from typing import List, Optional, Dict
from datetime import datetime

def calculate_metrics(
    equity_curve: List[float],
    trades: List[Dict[str, float]],
    risk_free_rate: float = 0.02
) -> Dict[str, float]:
    """Calculate backtest metrics from equity curve and trades.
    
    Args:
        equity_curve: List of account equity values over time.
        trades: List of trade dicts with 'entry_time', 'exit_time', 'profit'.
        risk_free_rate: Annual risk-free rate for Sharpe calculation.
    
    Returns:
        Dict with keys: 'sharpe_ratio', 'calmar_ratio', 'max_drawdown', etc.
    
    Raises:
        ValueError: If equity_curve is empty or has NaN values.
    """
    if not equity_curve or any(pd.isna(v) for v in equity_curve):
        raise ValueError("Invalid equity_curve")
    ...
```

### Node.js / TypeScript

| Category | Convention | Example |
|----------|-----------|---------|
| **Files** | `camelCase.ts` | `strategyService.ts`, `jobQueue.ts` |
| **Classes** | `PascalCase` | `JobService`, `StrategyRepository`, `ExportAdapter` |
| **Functions** | `camelCase()` | `submitJob()`, `getStrategyById()` |
| **Variables** | `camelCase` | `jobId`, `isProcessing`, `instrumentList` |
| **Constants** | `UPPER_SNAKE_CASE` or `camelCase` | `MAX_RETRIES`, `defaultTimeout` |
| **Interfaces** | `PascalCase`, prefix `I` optional | `JobPayload`, `IExportAdapter` (or just `ExportAdapter`) |
| **Type generics** | `PascalCase` | `<T>`, `<K extends string>` |
| **React components** | `PascalCase.tsx` | `StrategyWizard.tsx`, `EquityCurve.tsx` |
| **Hooks** | `use`Prefix | `useWizard()`, `useJobProgress()` |
| **Props interfaces** | `ComponentNameProps` | `EquityCurveProps`, `DashboardProps` |

**No `any` types (apply to entire codebase):**
```typescript
// ❌ Bad
function processData(data: any): any {
  return data.map(d => d.value);
}

// ✅ Good
interface DataRow {
  value: number;
  timestamp: Date;
}

function processData(data: DataRow[]): number[] {
  return data.map(d => d.value);
}
```

### React / TSX

```tsx
// ✅ Component file: EquityCurve.tsx
interface EquityCurveProps {
  jobId: string;
  equityData: EquityPoint[];
  isLoading: boolean;
  onExport?: (data: EquityPoint[]) => void;
}

export const EquityCurve: React.FC<EquityCurveProps> = ({
  jobId,
  equityData,
  isLoading,
  onExport
}) => {
  const [hoveredBar, setHoveredBar] = useState<Date | null>(null);
  
  const handleExport = () => {
    onExport?.(equityData);
  };
  
  return (
    <div className="equity-curve">
      {/* JSX content */}
    </div>
  );
};
```

---

## 2. Extension Patterns

### How to Add a New Indicator

**Goal:** Add a new technical indicator (e.g., Stochastic RSI) to the engine.

**Steps:**

1. **Define the indicator in Python** (`engine/src/backtest/indicators/momentum.py`):

```python
# engine/src/backtest/indicators/momentum.py

import numpy as np

def calculate_stochrsi(
    closes: np.ndarray,
    rsi_period: int = 14,
    stoch_period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3
) -> np.ndarray:
    """Calculate Stochastic RSI.
    
    Args:
        closes: Array of close prices.
        rsi_period: Period for RSI calculation.
        stoch_period: Period for stochastic smoothing.
        smooth_k: K line smoothing period.
        smooth_d: D line smoothing period.
    
    Returns:
        Array of StochRSI values (0-100).
    """
    # Calculate RSI first
    rsi = calculate_rsi(closes, rsi_period)
    
    # Apply stochastic formula
    rsi_min = pd.Series(rsi).rolling(window=stoch_period).min()
    rsi_max = pd.Series(rsi).rolling(window=stoch_period).max()
    
    stochrsi = ((rsi - rsi_min) / (rsi_max - rsi_min)) * 100
    
    # Smooth K and D lines
    k_line = pd.Series(stochrsi).rolling(window=smooth_k).mean()
    d_line = k_line.rolling(window=smooth_d).mean()
    
    return np.array(stochrsi)
```

2. **Register with IndicatorRegistry:**

```python
# engine/src/backtest/indicators/__init__.py

from .momentum import calculate_stochrsi

IndicatorRegistry.register('stochrsi', calculate_stochrsi)
```

3. **Add to JSON Schema** (SCHEMA.md):
   Add `'stochrsi'` to the enum in `StrategyDefinition.indicators[].type`

4. **Write unit tests** (`engine/tests/unit/test_indicators.py`):

```python
# engine/tests/unit/test_indicators.py

def test_calculate_stochrsi():
    """Test Stochastic RSI with known data."""
    closes = np.array([102, 103, 101, 104, 102, 105, 103, 106, 104, 107])
    
    result = calculate_stochrsi(closes, rsi_period=5, stoch_period=3)
    
    assert len(result) == len(closes)
    assert np.all((result >= 0) & (result <= 100)) or np.all(np.isnan(result[:8]))
    assert result[-1] > 0  # Last value should be valid
```

5. **Update Zod/Pydantic schemas** (`shared/zod-schemas/strategy-definition.ts`):

```typescript
// Add to Indicator type enum
type: z.enum([
  'sma', 'ema', 'macd', 'rsi', 'stoch', 'atr', 'bollinger_bands',
  'momentum', 'adx', 'cci', 'obv', 'williamsr',
  'stochrsi'  // ← NEW
])
```

6. **Document in UI hints** (`ui/src/api/wizard.api.ts`):

```typescript
const INDICATOR_SUGGESTIONS = {
  stochrsi: {
    label: 'Stochastic RSI',
    description: 'Momentum indicator combining RSI and Stochastic oscillator',
    category: 'momentum',
    defaultParams: { rsi_period: 14, stoch_period: 14, smooth_k: 3, smooth_d: 3 }
  }
};
```

**Checklist:**
- [ ] Indicator function implemented with proper type hints
- [ ] Registered in IndicatorRegistry
- [ ] Added to JSON schema & Zod/Pydantic
- [ ] Unit tests pass (known input → known output)
- [ ] Integration test: strategy using indicator backtests successfully
- [ ] Documentation added (docstring + README)
- [ ] Pushed to repo with commit: `engine: add stochrsi indicator`

---

### How to Add a New Robustness Test

**Goal:** Add a new robustness validation test (e.g., Correlation to Random Returns).

**Steps:**

1. **Define the test in Python** (`engine/src/robustness/correlation_random.py`):

```python
# engine/src/robustness/correlation_random.py

from typing import Dict
import numpy as np
from scipy.stats import pearsonr

def test_correlation_with_random_returns(
    equity_curve: np.ndarray,
    num_random_trials: int = 1000,
    confidence_level: float = 0.95
) -> Dict[str, float]:
    """Test correlation between strategy returns and random returns.
    
    Hypothesis: If strategy is just luck, correlation with random returns
    should be near zero and not statistically significant.
    
    Args:
        equity_curve: Account equity over time.
        num_random_trials: Number of random return sequences to test.
        confidence_level: Statistical significance threshold.
    
    Returns:
        {
            'mean_correlation': float,
            'max_correlation': float,
            'p_value': float,
            'is_significant': bool,
            'pass': bool (True if strategy uncorrelated with random)
        }
    """
    strategy_returns = np.diff(equity_curve) / equity_curve[:-1]
    
    correlations = []
    for _ in range(num_random_trials):
        random_returns = np.random.normal(np.mean(strategy_returns), 
                                          np.std(strategy_returns), 
                                          len(strategy_returns))
        corr, _ = pearsonr(strategy_returns, random_returns)
        correlations.append(corr)
    
    mean_corr = np.mean(correlations)
    max_corr = np.max(np.abs(correlations))
    
    # Simple p-value: fraction of random trials with |corr| > 0.5
    p_value = np.sum(np.abs(correlations) > 0.5) / num_random_trials
    
    return {
        'mean_correlation': float(mean_corr),
        'max_correlation': float(max_corr),
        'p_value': float(p_value),
        'is_significant': p_value < (1 - confidence_level),
        'pass': p_value > (1 - confidence_level)  # Pass if NOT significant
    }
```

2. **Register in RobustnessRegistry:**

```python
# engine/src/robustness/__init__.py

from .correlation_random import test_correlation_with_random_returns

class RobustnessRegistry:
    _tests: Dict[str, Callable] = {}
    
    @classmethod
    def register(cls, name: str, fn: Callable):
        cls._tests[name] = fn
    
    @classmethod
    def get_all(cls) -> Dict[str, Callable]:
        return cls._tests.copy()

RobustnessRegistry.register('correlation_random', test_correlation_with_random_returns)
```

3. **Add to job payload schema** (SCHEMA.md):
   Add to robustness report structure

4. **Write integration test** (`engine/tests/integration/test_robustness.py`):

```python
def test_robustness_correlation_random():
    """Test that robustness test catches random strategies."""
    # Load sample equity curve with no real edge
    random_equity = np.cumprod(1 + np.random.normal(0, 0.01, 500))
    
    result = test_correlation_with_random_returns(random_equity)
    
    # Random series should NOT pass (correlation is significant)
    assert not result['pass']
```

5. **Update API to expose test** (`api/src/services/job.service.ts`):

```typescript
const AVAILABLE_TESTS = {
  walk_forward: { name: 'Walk-Forward Analysis', duration: 'medium' },
  monte_carlo: { name: 'Monte Carlo Simulation', duration: 'long' },
  oos_test: { name: 'Out-of-Sample Test', duration: 'fast' },
  parameter_sensitivity: { name: 'Parameter Sensitivity', duration: 'medium' },
  trade_shuffle: { name: 'Trade Shuffle', duration: 'fast' },
  correlation_random: { name: 'Correlation w/ Random Returns', duration: 'medium' }  // ← NEW
};
```

6. **Update React UI** (`ui/src/components/Dashboard/RobustnessTestSelector.tsx`):

```tsx
export const RobustnessTestSelector: React.FC = () => {
  const [selectedTests, setSelectedTests] = useState<string[]>([]);
  
  const TESTS = [
    { id: 'walk_forward', label: 'Walk-Forward Analysis' },
    { id: 'monte_carlo', label: 'Monte Carlo Simulation' },
    { id: 'correlation_random', label: 'Correlation w/ Random Returns', isNew: true }  // ← NEW
  ];
  
  return (
    <div className="robustness-selector">
      {TESTS.map(test => (
        <label key={test.id}>
          <input 
            type="checkbox" 
            value={test.id}
            onChange={(e) => toggleTest(e.target.value)}
          />
          {test.label} {test.isNew && <Badge>NEW</Badge>}
        </label>
      ))}
    </div>
  );
};
```

**Checklist:**
- [ ] Robustness test function implemented with docstring
- [ ] Registered in RobustnessRegistry
- [ ] Integration test validates known behavior
- [ ] Job payload schema updated
- [ ] API endpoint includes new test in available options
- [ ] React component updated with test selector
- [ ] Commit: `engine: add correlation_with_random_returns robustness test`

---

### How to Add a New Export Format

**Goal:** Export strategies to a new platform (e.g., MetaTrader 5).

**Steps:**

1. **Implement ExportAdapter** (`api/src/services/export/adapters/mt5.adapter.ts`):

```typescript
// api/src/services/export/adapters/mt5.adapter.ts

import { ExportAdapter } from '../types';
import { StrategyDefinition } from '@shared/schemas';

export class MT5Adapter implements ExportAdapter {
  name = 'metatrader5';
  
  canExport(strategy: StrategyDefinition): boolean {
    // Check if all indicators/rules are supported by MT5
    return !strategy.indicators.some(ind => ['obv'].includes(ind.type));
  }
  
  async export(
    strategy: StrategyDefinition,
    params: Record<string, any>
  ): Promise<string> {
    const code = this.generateMQL5Code(strategy, params);
    
    // Validate MQL5 syntax (optional)
    const isValid = this.validateMQL5(code);
    if (!isValid) {
      throw new Error('Generated MQL5 code has syntax errors');
    }
    
    return code;
  }
  
  private generateMQL5Code(strategy: StrategyDefinition, params: any): string {
    let code = `
// Auto-generated MQL5 strategy from Algo Farm
// Strategy: ${strategy.name}
// Generated: ${new Date().toISOString()}

#property copyright "Algo Farm"
#property link "https://algo-farm.local"
#property version "1.00"
#property strict

// Input parameters
input double StopLossPips = ${params.stop_loss_pips};
input double TakeProfitPips = ${params.take_profit_pips};

// OnInit
void OnInit() {
  Print("Strategy initialized: ${strategy.name}");
}

// OnTick
void OnTick() {
  // Entry logic
  if (checkEntryCondition()) {
    openPosition(ORDER_TYPE_BUY, StopLossPips, TakeProfitPips);
  }
  
  // Exit logic
  if (checkExitCondition()) {
    closeAllPositions();
  }
}

// Helper functions
bool checkEntryCondition() {
  // Entry rules from strategy definition
  return true; // Placeholder
}

bool checkExitCondition() {
  return false; // Placeholder
}
    `;
    
    return code;
  }
  
  private validateMQL5(code: string): boolean {
    // Basic validation: check for required functions
    return code.includes('OnInit') && code.includes('OnTick');
  }
}
```

2. **Register with ExportService** (`api/src/services/export/service.ts`):

```typescript
// api/src/services/export/service.ts

import { CTraderAdapter } from './adapters/ctrader.adapter';
import { PineScriptAdapter } from './adapters/pine-script.adapter';
import { MT5Adapter } from './adapters/mt5.adapter';  // ← NEW

export class ExportService {
  private adapters: Map<string, ExportAdapter> = new Map([
    ['ctrader', new CTraderAdapter()],
    ['pine_script', new PineScriptAdapter()],
    ['metatrader5', new MT5Adapter()]  // ← NEW
  ]);
  
  async export(
    strategy: StrategyDefinition,
    format: string,
    params: Record<string, any>
  ): Promise<string> {
    const adapter = this.adapters.get(format);
    if (!adapter) {
      throw new Error(`Unknown format: ${format}`);
    }
    
    if (!adapter.canExport(strategy)) {
      throw new Error(`Strategy cannot be exported to ${format}`);
    }
    
    return adapter.export(strategy, params);
  }
  
  supportedFormats(): string[] {
    return Array.from(this.adapters.keys());
  }
}
```

3. **Add route** (`api/src/routes/export.ts`):
   Route already handles all registered adapters automatically.

4. **Write tests** (`api/tests/unit/export.adapter.test.ts`):

```typescript
describe('MT5Adapter', () => {
  const adapter = new MT5Adapter();
  
  it('generates valid MQL5 code', async () => {
    const strategy = buildMockStrategy('advanced');
    const code = await adapter.export(strategy, { stop_loss_pips: 25 });
    
    expect(code).toContain('#include <Trade\\Trade.mqh>');
    expect(code).toContain('OnTick');
    expect(code).toContain('StopLossPips');
  });
  
  it('rejects unsupported indicators', () => {
    const strategy = buildMockStrategy('advanced');
    strategy.indicators.push({ name: 'obv', type: 'obv', params: {} });
    
    expect(adapter.canExport(strategy)).toBe(false);
  });
});
```

**Checklist:**
- [ ] ExportAdapter interface implemented
- [ ] Registered in ExportService
- [ ] Generated code is valid (syntax check)
- [ ] Unit tests cover happy path + edge cases
- [ ] Integration test: export → validate format
- [ ] Route automatically serves new format
- [ ] Commit: `api: add MT5 export adapter`

---

## 3. Commit Message Format

**Format: `{scope}: {brief description}`**

| Scope | Examples |
|-------|----------|
| `engine` | `engine: add stochrsi indicator`, `engine: fix backtest equity curve rounding` |
| `api` | `api: add robustness job handler`, `api: fix job status polling` |
| `ui` | `ui: improve equity curve rendering performance`, `ui: add wizard step validation` |
| `docs` | `docs: update SCHEMA.md with v1.1 migration guide` |
| `build` | `build: upgrade python dependencies to vectorbt 0.25` |

**Detailed commits:**
- Use present tense ("add" not "added")
- Keep first line < 50 characters
- Optionally add body with rationale (separated by blank line)

```
engine: add stochrsi indicator

This adds Stochastic RSI, a composite momentum indicator combining
RSI and Stochastic oscillator. Useful for overbought/oversold signals
in mean-reversion strategies.

Includes unit tests and integration with IndicatorRegistry.
Resolves #123.
```

---

## 4. Branch Naming

**Format: `{type}/{scope}-{brief}`**

| Type | Usage | Example |
|------|-------|---------|
| `feat` | New feature | `feat/wizard-llm-integration` |
| `fix` | Bug fix | `fix/backtest-equity-rounding` |
| `test` | Test improvements | `test/robustness-monte-carlo` |
| `docs` | Documentation | `docs/schema-versioning-guide` |
| `refactor` | Code cleanup | `refactor/indicator-registry` |

**Naming rules:**
- Lowercase
- Hyphens (not underscores)
- Correlate with PR description

---

## 5. Environment Setup

### Prerequisites

- **Python 3.11+** (check: `python --version`)
- **Node.js 20+** (check: `node --version`)
- **Redis** (local via Docker or Docker Compose)
- **make** (for Makefile tasks)
- **Git**

### Bootstrap Monorepo

```bash
# Clone repo
git clone <repo-url>
cd algo-farm

# Run setup (creates venv, installs deps, initializes DB)
make init

# Verify all layers running
make run-api &
make run-engine-worker &
make run-ui &

# Access UI at http://localhost:5173
```

### .env Configuration

Create `/.env.local` (not committed):

```bash
# Python Engine
REDIS_URL=redis://localhost:6379
DATABASE_URL=sqlite:///./algo_farm.db
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1

# Node.js API
NODE_ENV=development
PORT=3001
REDIS_URL=redis://localhost:6379
DATABASE_URL=sqlite:///./algo_farm.db
LLM_PROVIDER=openai        # or 'claude'
LLM_API_KEY=sk-xxx...
SESSION_SECRET=dev-secret-change-in-prod

# React UI
VITE_API_BASE_URL=http://localhost:3001
VITE_WS_URL=ws://localhost:3001
```

### Makefile Targets

```bash
make init               # Full bootstrap
make install            # Install dependencies only
make test               # Run all tests
make test-engine        # Python unit tests
make test-api           # Node.js unit tests
make test-ui            # React component tests
make e2e                # Playwright E2E tests
make lint               # ESLint + mypy + black
make run-api            # Start Node.js server
make run-engine-worker  # Start Python worker
make run-ui             # React dev server (Vite)
make run-redis          # Redis (Docker)
make clean              # Remove build artifacts
```

---

## 6. Testing Requirements

### What Must Be Tested

| Component | Level | Priority |
|-----------|-------|----------|
| **Indicators** | Unit | P0 (every new indicator) |
| **Backtest runner** | Integration | P0 (known input → known output) |
| **Optimization logic** | Unit | P1 (correctness of param search) |
| **Robustness tests** | Unit + Integration | P0 |
| **API endpoints** | Integration | P0 (mock DB + Python) |
| **React components** | Unit (Vitest) + Component (RTL) | P1 |
| **Repositories** | Unit (mock SQLite) | P0 |
| **Export adapters** | Unit | P1 |

### Minimum Coverage

- **Python engine:** ≥ 80% line coverage (critical paths higher)
- **Node.js API:** ≥ 70% line coverage
- **React UI:** ≥ 50% component coverage (not strict, focus on critical flows)

### Test Organization

```
engine/tests/
├── unit/
│   ├── test_indicators.py            # Each indicator has test
│   ├── test_strategy.py              # Strategy composition
│   └── test_metrics.py               # Metrics calculation
├── integration/
│   ├── test_backtest_correctness.py  # Known input → known output
│   ├── test_optimization.py          # Parameter search correctness
│   └── test_robustness_suite.py      # All robustness tests
└── fixtures/
    ├── sample_equity.csv             # Known good equity curve
    └── sample_trades.json            # Known good trades

api/tests/
├── unit/
│   ├── wizard.service.test.ts        # LLM validation
│   ├── job.service.test.ts           # Job lifecycle (mock Redis)
│   └── repositories.test.ts          # CRUD (mock SQLite)
└── integration/
    ├── e2e-wizard-to-results.test.ts # Full flow (real API, mock Python)
    └── export.test.ts                # Export service + adapters

ui/tests/
├── unit/
│   ├── hooks.test.tsx                # useWizard, useJobProgress
│   └── store.test.ts                 # Zustand store logic
├── components/
│   ├── Wizard.test.tsx               # Wizard form flow
│   └── Dashboard.test.tsx            # Results rendering
└── e2e/
    └── full-flow.spec.ts             # Playwright: user journey
```

---

## 7. Code Review Checklist

Before PR merge:

- [ ] Commits follow format (scope: description)
- [ ] Tests added/updated (unit + integration)
- [ ] Type hints present (Python + TypeScript)
- [ ] Docstrings complete (Google style)
- [ ] No `any` types or `# type: ignore`
- [ ] Code follows naming conventions
- [ ] New extension? Follow pattern (Conventions.md)
- [ ] Documentation updated (if user-facing)
- [ ] No secrets in code (check .env)

---

## Next Steps

1. Implement Makefile with all targets
2. Set up Python linting (mypy, black, flake8)
3. Set up Node.js linting (ESLint, Prettier)
4. Create PR template with checklist
5. Configure CI pipeline (GitHub Actions)
