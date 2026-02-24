# SCHEMA.md — Contracts & Data Models

## Executive Summary

This document defines all data contracts and persistence schemas for the Algo Trading Platform. It includes:
- **StrategyDefinition v1**: JSON Schema, Pydantic model, Zod schema (source of truth)
- **Phase 1 CLI schemas**: `param_grid.json` input and stdout JSONL progress/result protocol
- **SQLite schema**: All tables with types, indexes, foreign keys
- **Job payload**: Schema for BullMQ job submission and progress events (Phase 3+)
- **Versioning policy**: How schema evolves across phases without breaking changes

**Key principle:** Single source of truth (JSON Schema) generates code for both Python and TypeScript to ensure consistency.

### Phase applicability at a glance

| Schema | Phase introduced | Who consumes it |
|--------|-----------------|-----------------|
| `StrategyDefinition` JSON Schema | Phase 1 | Python (validation on CLI load) |
| `StrategyDefinition` Pydantic model | Phase 1 | Python engine |
| `param_grid.json` | Phase 1 | Python engine CLI |
| stdout JSONL protocol | Phase 1 | Any consumer (agent, shell, Node.js) |
| SQLite schema (`strategies`, `runs`, `jobs`) | Phase 1 | Python engine (read/write) |
| `StrategyDefinition` Zod schema | Phase 2 | Node.js API, React UI |
| BullMQ job payload | Phase 3 | Node.js → Python via Redis |
| Robustness report schema | Phase 4 | Python engine, Node.js, React |

---

## 1. StrategyDefinition v1 — Core Strategy Contract

### Overview

A `StrategyDefinition` is a structured representation of a trading strategy:
- **Indicators**: Which technical indicators to calculate (SMA, RSI, Bollinger Bands, etc.)
- **Entry rules**: Conditions for opening a position
- **Exit rules**: Conditions for closing a position
- **Position management**: Stop-loss, take-profit levels
- **Filters**: Time-of-day, day-of-week, volatility regime restrictions
- **Variants**: Basic (simple SL/TP) vs. Advanced (scaled entries, partial TPs, trailing stop)

### JSON Schema (v1.0)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://algo-farm.local/schemas/strategy-definition/v1.0.json",
  "title": "StrategyDefinition",
  "description": "A complete trading strategy definition, version 1",
  "type": "object",
  "required": [
    "version",
    "name",
    "variant",
    "indicators",
    "entry_rules",
    "exit_rules",
    "position_management"
  ],
  "properties": {
    "version": {
      "type": "string",
      "const": "1.0",
      "description": "Schema version for backward compatibility"
    },
    "name": {
      "type": "string",
      "minLength": 3,
      "maxLength": 100,
      "description": "Human-readable strategy name"
    },
    "description": {
      "type": "string",
      "maxLength": 1000,
      "description": "Optional detailed description"
    },
    "variant": {
      "type": "string",
      "enum": ["basic", "advanced"],
      "description": "Basic: simple SL/TP; Advanced: scaled entries, partial TPs, trailing stop"
    },
    "indicators": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["name", "type"],
        "properties": {
          "name": {
            "type": "string",
            "description": "Indicator identifier (e.g., 'sma_20', 'rsi_14')"
          },
          "type": {
            "type": "string",
            "enum": [
              "sma", "ema", "macd", "rsi", "stoch", "atr", "bollinger_bands",
              "momentum", "adx", "cci", "obv", "williamsr"
            ],
            "description": "Built-in indicator type"
          },
          "params": {
            "type": "object",
            "description": "Indicator-specific parameters; structure varies by type"
          }
        }
      },
      "description": "List of indicators to calculate on each bar"
    },
    "entry_rules": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["logic_type"],
        "properties": {
          "logic_type": {
            "type": "string",
            "enum": ["price_above", "price_below", "indicator_cross", "indicator_above", "indicator_below"],
            "description": "Type of condition"
          },
          "indicator_ref": {
            "type": "string",
            "description": "Reference to indicator (e.g., 'sma_20', 'rsi_14'); required unless logic_type is price_*"
          },
          "threshold": {
            "type": "number",
            "description": "Threshold value for comparison"
          },
          "side": {
            "type": "string",
            "enum": ["long", "short"],
            "description": "Trade direction"
          },
          "all_must_match": {
            "type": "boolean",
            "default": true,
            "description": "If true, ALL entry rules must match to enter; if false, ANY rule triggers entry"
          }
        }
      },
      "description": "Conditions for opening a position"
    },
    "exit_rules": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["logic_type"],
        "properties": {
          "logic_type": {
            "type": "string",
            "enum": [
              "stop_loss", "take_profit", "time_based", "indicator_cross",
              "indicator_above", "indicator_below", "price_level"
            ]
          },
          "indicator_ref": {
            "type": "string",
            "description": "Reference to indicator; required for indicator_* types"
          },
          "threshold": {
            "type": "number",
            "description": "Threshold for comparison"
          },
          "time_bars": {
            "type": "integer",
            "description": "Number of bars for time_based exit"
          }
        }
      },
      "description": "Conditions for closing a position"
    },
    "position_management": {
      "type": "object",
      "required": ["variant_type"],
      "properties": {
        "variant_type": {
          "type": "string",
          "enum": ["basic", "advanced"],
          "description": "Match strategy variant: basic or advanced"
        },
        "stop_loss_pips": {
          "type": "number",
          "minimum": 0.5,
          "description": "Fixed stop-loss distance in pips"
        },
        "take_profit_pips": {
          "type": "number",
          "minimum": 1,
          "description": "Fixed take-profit distance in pips (basic variant)"
        },
        "target_risk_reward_ratio": {
          "type": "number",
          "minimum": 0.5,
          "description": "Risk-reward ratio (e.g., 1:2 = TP is 2x SL); alternative to fixed TP"
        },
        "partial_take_profits": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["level_pct", "close_pct"],
            "properties": {
              "level_pct": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "Distance as % of total TP (e.g., 50 = half TP level)"
              },
              "close_pct": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "Percentage of position to close at that level"
              }
            }
          },
          "description": "Partial take-profit levels; only for advanced variant"
        },
        "trailing_stop": {
          "type": "object",
          "properties": {
            "enabled": {
              "type": "boolean"
            },
            "trigger_pips": {
              "type": "number",
              "description": "Activate trailing stop after profit reaches this level"
            },
            "trail_pips": {
              "type": "number",
              "description": "Trail stop-loss by this many pips below peak profit"
            }
          },
          "description": "Trailing stop configuration; only for advanced variant"
        },
        "re_entry": {
          "type": "object",
          "properties": {
            "enabled": {
              "type": "boolean"
            },
            "max_re_entries": {
              "type": "integer",
              "minimum": 1,
              "description": "Max times position can be re-opened"
            },
            "delay_bars": {
              "type": "integer",
              "minimum": 1,
              "description": "Bars to wait after exit before re-entry allowed"
            }
          },
          "description": "Re-entry logic; only for advanced variant"
        }
      }
    },
    "filters": {
      "type": "object",
      "description": "Restrictions on when trades can be opened",
      "properties": {
        "time_of_day": {
          "type": "object",
          "properties": {
            "enabled": {
              "type": "boolean"
            },
            "start_hour": {
              "type": "integer",
              "minimum": 0,
              "maximum": 23,
              "description": "Start of trading window (UTC)"
            },
            "end_hour": {
              "type": "integer",
              "minimum": 0,
              "maximum": 23,
              "description": "End of trading window (UTC)"
            }
          }
        },
        "day_of_week": {
          "type": "object",
          "properties": {
            "enabled": {
              "type": "boolean"
            },
            "allowed_days": {
              "type": "array",
              "items": {
                "type": "integer",
                "enum": [0, 1, 2, 3, 4, 5, 6],
                "description": "0=Monday, 6=Sunday"
              }
            }
          }
        },
        "volatility_regime": {
          "type": "object",
          "properties": {
            "enabled": {
              "type": "boolean"
            },
            "min_atr": {
              "type": "number",
              "description": "Minimum ATR to trade (pips)"
            },
            "max_atr": {
              "type": "number",
              "description": "Maximum ATR to trade (pips)"
            }
          }
        }
      }
    }
  }
}
```

### Pydantic Model (Python)

```python
# shared/pydantic-models/strategy_definition.py

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, validator

class Indicator(BaseModel):
    name: str = Field(..., description="Indicator ID (e.g., 'sma_20')")
    type: Literal[
        'sma', 'ema', 'macd', 'rsi', 'stoch', 'atr', 'bollinger_bands',
        'momentum', 'adx', 'cci', 'obv', 'williamsr'
    ]
    params: dict = Field(default_factory=dict, description="Indicator-specific parameters")

class EntryRule(BaseModel):
    logic_type: Literal['price_above', 'price_below', 'indicator_cross', 'indicator_above', 'indicator_below']
    indicator_ref: Optional[str] = None
    threshold: Optional[float] = None
    side: Literal['long', 'short']
    all_must_match: bool = True

class ExitRule(BaseModel):
    logic_type: Literal[
        'stop_loss', 'take_profit', 'time_based', 'indicator_cross',
        'indicator_above', 'indicator_below', 'price_level'
    ]
    indicator_ref: Optional[str] = None
    threshold: Optional[float] = None
    time_bars: Optional[int] = None

class PartialTakeProfit(BaseModel):
    level_pct: float = Field(..., ge=0, le=100)
    close_pct: float = Field(..., ge=0, le=100)

class TrailingStop(BaseModel):
    enabled: bool
    trigger_pips: float
    trail_pips: float

class ReEntry(BaseModel):
    enabled: bool
    max_re_entries: int = 1
    delay_bars: int = 1

class PositionManagement(BaseModel):
    variant_type: Literal['basic', 'advanced']
    stop_loss_pips: float = Field(..., gt=0.5)
    take_profit_pips: Optional[float] = None  # Required for basic
    target_risk_reward_ratio: Optional[float] = None
    partial_take_profits: Optional[List[PartialTakeProfit]] = None
    trailing_stop: Optional[TrailingStop] = None
    re_entry: Optional[ReEntry] = None

    @validator('partial_take_profits', pre=True, always=True)
    def validate_partial_tps(cls, v, values):
        if values.get('variant_type') == 'basic' and v:
            raise ValueError('partial_take_profits only allowed in advanced variant')
        return v

class TimeOfDay(BaseModel):
    enabled: bool
    start_hour: int = Field(..., ge=0, le=23)
    end_hour: int = Field(..., ge=0, le=23)

class DayOfWeek(BaseModel):
    enabled: bool
    allowed_days: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])

class VolatilityRegime(BaseModel):
    enabled: bool
    min_atr: Optional[float] = None
    max_atr: Optional[float] = None

class Filters(BaseModel):
    time_of_day: Optional[TimeOfDay] = None
    day_of_week: Optional[DayOfWeek] = None
    volatility_regime: Optional[VolatilityRegime] = None

class StrategyDefinition(BaseModel):
    version: Literal['1.0'] = '1.0'
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    variant: Literal['basic', 'advanced']
    indicators: List[Indicator] = Field(..., min_items=1)
    entry_rules: List[EntryRule] = Field(..., min_items=1)
    exit_rules: List[ExitRule] = Field(..., min_items=1)
    position_management: PositionManagement
    filters: Optional[Filters] = None

    class Config:
        schema_extra = {
            "example": {
                "version": "1.0",
                "name": "Breakout Trend",
                "variant": "advanced",
                "indicators": [
                    {"name": "breakout", "type": "sma", "params": {"period": 20}},
                    {"name": "trend", "type": "ema", "params": {"period": 50}}
                ],
                "entry_rules": [
                    {
                        "logic_type": "price_above",
                        "threshold": None,
                        "side": "long",
                        "all_must_match": True
                    }
                ],
                "exit_rules": [
                    {"logic_type": "stop_loss"}
                ],
                "position_management": {
                    "variant_type": "advanced",
                    "stop_loss_pips": 25,
                    "target_risk_reward_ratio": 2.5,
                    "partial_take_profits": [
                        {"level_pct": 50, "close_pct": 50},
                        {"level_pct": 100, "close_pct": 50}
                    ],
                    "trailing_stop": {
                        "enabled": True,
                        "trigger_pips": 50,
                        "trail_pips": 10
                    }
                }
            }
        }
```

### Zod Schema (TypeScript)

```typescript
// shared/zod-schemas/strategy-definition.ts

import { z } from 'zod';

const Indicator = z.object({
  name: z.string().describe('Indicator ID'),
  type: z.enum([
    'sma', 'ema', 'macd', 'rsi', 'stoch', 'atr', 'bollinger_bands',
    'momentum', 'adx', 'cci', 'obv', 'williamsr'
  ]),
  params: z.record(z.any()).default({})
});

const EntryRule = z.object({
  logic_type: z.enum([
    'price_above', 'price_below', 'indicator_cross',
    'indicator_above', 'indicator_below'
  ]),
  indicator_ref: z.string().optional(),
  threshold: z.number().optional(),
  side: z.enum(['long', 'short']),
  all_must_match: z.boolean().default(true)
});

const ExitRule = z.object({
  logic_type: z.enum([
    'stop_loss', 'take_profit', 'time_based',
    'indicator_cross', 'indicator_above', 'indicator_below', 'price_level'
  ]),
  indicator_ref: z.string().optional(),
  threshold: z.number().optional(),
  time_bars: z.number().int().optional()
});

const PartialTakeProfit = z.object({
  level_pct: z.number().min(0).max(100),
  close_pct: z.number().min(0).max(100)
});

const TrailingStop = z.object({
  enabled: z.boolean(),
  trigger_pips: z.number().positive(),
  trail_pips: z.number().positive()
});

const ReEntry = z.object({
  enabled: z.boolean(),
  max_re_entries: z.number().int().min(1).default(1),
  delay_bars: z.number().int().min(1).default(1)
});

const PositionManagement = z.object({
  variant_type: z.enum(['basic', 'advanced']),
  stop_loss_pips: z.number().gt(0.5),
  take_profit_pips: z.number().optional(),
  target_risk_reward_ratio: z.number().optional(),
  partial_take_profits: z.array(PartialTakeProfit).optional(),
  trailing_stop: TrailingStop.optional(),
  re_entry: ReEntry.optional()
});

const TimeOfDay = z.object({
  enabled: z.boolean(),
  start_hour: z.number().int().min(0).max(23),
  end_hour: z.number().int().min(0).max(23)
});

const DayOfWeek = z.object({
  enabled: z.boolean(),
  allowed_days: z.array(z.number().int().min(0).max(6)).default([0, 1, 2, 3, 4])
});

const VolatilityRegime = z.object({
  enabled: z.boolean(),
  min_atr: z.number().optional(),
  max_atr: z.number().optional()
});

const Filters = z.object({
  time_of_day: TimeOfDay.optional(),
  day_of_week: DayOfWeek.optional(),
  volatility_regime: VolatilityRegime.optional()
});

export const StrategyDefinitionSchema = z.object({
  version: z.literal('1.0'),
  name: z.string().min(3).max(100),
  description: z.string().max(1000).optional(),
  variant: z.enum(['basic', 'advanced']),
  indicators: z.array(Indicator).min(1),
  entry_rules: z.array(EntryRule).min(1),
  exit_rules: z.array(ExitRule).min(1),
  position_management: PositionManagement,
  filters: Filters.optional()
});

export type StrategyDefinition = z.infer<typeof StrategyDefinitionSchema>;
```

---

## 2. SQLite Schema

### Entity Relationship Diagram

```
strategies
    ├─ id (PK UUID)
    ├─ definition (JSON blob)
    ├─ status (enum: draft, tested, validated, production, archived)
    ├─ created_at, updated_at

strategies ←── runs (1:N)
    ├─ id (PK UUID)
    ├─ strategy_id (FK strategies.id)
    ├─ job_id (FK jobs.id)
    ├─ instrument, timeframe, params_json
    ├─ equity_curve (JSON), trades_json
    ├─ metrics (PnL, Sharpe, Calmar, etc.)
    ├─ completed_at

strategies ←── parameter_sets (1:N)
    ├─ id (PK UUID)
    ├─ strategy_id (FK strategies.id)
    ├─ regime (enum: bull, bear, sideways, default)
    ├─ parameters (JSON)
    ├─ created_at

strategies ←── journal_entries (1:N)
    ├─ id (PK UUID)
    ├─ strategy_id (FK strategies.id)
    ├─ note (text)
    ├─ created_at

jobs (1:N)← runs
    ├─ id (PK UUID)
    ├─ status (enum: pending, processing, completed, failed)
    ├─ job_type (enum: backtest, robustness_validation)
    ├─ params_json
    ├─ resume_from_instrument (for interrupted jobs)
    ├─ created_at, started_at, completed_at
    ├─ error_message (if failed)

robustness_reports
    ├─ id (PK UUID)
    ├─ job_id (FK jobs.id)
    ├─ strategy_id (FK strategies.id)
    ├─ tests (JSON: walk_forward, monte_carlo, oos, param_sensitivity, trade_shuffle)
    ├─ composite_score (0-10)
    ├─ justification (text)
    ├─ created_at

tags
    ├─ id (PK UUID)
    ├─ name (unique, e.g., 'trend', 'mean-reversion', 'EURUSD', 'D1')
    ├─ category (enum: style, instrument, timeframe, regime)

strategy_tags (association)
    ├─ strategy_id (FK strategies.id)
    ├─ tag_id (FK tags.id)

audit_log
    ├─ id (PK UUID)
    ├─ entity_type (strategies, parameter_sets, journal_entries)
    ├─ entity_id (UUID)
    ├─ action (created, updated, deleted, status_changed)
    ├─ changed_fields (JSON)
    ├─ created_at
    ├─ performed_by (optional user/agent ID)
```

### SQL DDL

```sql
-- strategies table
CREATE TABLE IF NOT EXISTS strategies (
    id TEXT PRIMARY KEY,
    definition TEXT NOT NULL,  -- JSON blob (StrategyDefinition v1)
    status TEXT NOT NULL CHECK(status IN ('draft', 'tested', 'validated', 'production', 'archived')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_strategies_status ON strategies(status);

-- runs table (backtest results)
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    instrument TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    params_json TEXT,           -- JSON: actual params used for this run
    equity_curve TEXT NOT NULL,  -- JSON: [{timestamp, equity, drawdown}, ...]
    trades_json TEXT NOT NULL,   -- JSON: [{entry_time, exit_time, profit_pips, ...}, ...]
    
    -- Key metrics (denormalized for quick queries)
    net_pnl REAL,
    cagr REAL,
    max_drawdown REAL,
    calmar_ratio REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    profit_factor REAL,
    win_rate REAL,
    avg_win_loss REAL,
    expectancy REAL,
    num_trades INTEGER,
    avg_trade_duration_bars INTEGER,
    
    completed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(job_id) REFERENCES jobs(id),
    FOREIGN KEY(strategy_id) REFERENCES strategies(id)
);

CREATE INDEX idx_runs_job_id ON runs(job_id);
CREATE INDEX idx_runs_strategy_id ON runs(strategy_id);
CREATE INDEX idx_runs_instrument_timeframe ON runs(instrument, timeframe);
CREATE INDEX idx_runs_sharpe_ratio ON runs(sharpe_ratio DESC);

-- jobs table (backtest/robustness jobs)
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK(status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    job_type TEXT NOT NULL CHECK(job_type IN ('backtest', 'robustness_validation')),
    strategy_id TEXT NOT NULL,
    params_json TEXT NOT NULL,  -- Input: instruments, timeframes, param_grid, etc.
    
    -- Resume state (for interrupted optimization)
    resume_from_instrument TEXT,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    
    FOREIGN KEY(strategy_id) REFERENCES strategies(id)
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_strategy_id ON jobs(strategy_id);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);

-- robustness_reports table
CREATE TABLE IF NOT EXISTS robustness_reports (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    
    -- Test results as JSON
    tests_json TEXT NOT NULL,  -- {walk_forward: {...}, monte_carlo: {...}, ...}
    
    composite_score REAL NOT NULL CHECK(composite_score >= 0 AND composite_score <= 10),
    justification TEXT NOT NULL,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(job_id) REFERENCES jobs(id),
    FOREIGN KEY(strategy_id) REFERENCES strategies(id)
);

CREATE INDEX idx_robustness_reports_strategy_id ON robustness_reports(strategy_id);
CREATE INDEX idx_robustness_reports_composite_score ON robustness_reports(composite_score DESC);

-- parameter_sets table (strategies saved by regime)
CREATE TABLE IF NOT EXISTS parameter_sets (
    id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    regime TEXT NOT NULL CHECK(regime IN ('bull', 'bear', 'sideways', 'default')),
    parameters TEXT NOT NULL,   -- JSON: { sma_period: 20, breakout_threshold: 1.5, ... }
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(strategy_id) REFERENCES strategies(id),
    UNIQUE(strategy_id, regime)
);

CREATE INDEX idx_parameter_sets_strategy_id ON parameter_sets(strategy_id);

-- journal_entries table (timestamped notes on strategies)
CREATE TABLE IF NOT EXISTS journal_entries (
    id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(strategy_id) REFERENCES strategies(id)
);

CREATE INDEX idx_journal_entries_strategy_id ON journal_entries(strategy_id);
CREATE INDEX idx_journal_entries_created_at ON journal_entries(created_at DESC);

-- tags table
CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK(category IN ('style', 'instrument', 'timeframe', 'regime', 'custom')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tags_category ON tags(category);

-- strategy_tags association table (many-to-many)
CREATE TABLE IF NOT EXISTS strategy_tags (
    strategy_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    PRIMARY KEY (strategy_id, tag_id),
    FOREIGN KEY(strategy_id) REFERENCES strategies(id),
    FOREIGN KEY(tag_id) REFERENCES tags(id)
);

CREATE INDEX idx_strategy_tags_tag_id ON strategy_tags(tag_id);

-- audit_log table (immutable audit trail)
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('strategies', 'parameter_sets', 'journal_entries', 'runs', 'jobs')),
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('created', 'updated', 'deleted', 'status_changed')),
    changed_fields TEXT,            -- JSON: {field_name: {old_value, new_value}, ...}
    performed_by TEXT,              -- (optional) user/agent ID
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);

-- error_log table (detailed error tracking for debugging)
CREATE TABLE IF NOT EXISTS error_log (
    id TEXT PRIMARY KEY,
    job_id TEXT,
    error_type TEXT NOT NULL,       -- e.g., 'DataMissingError', 'CalculationError'
    message TEXT NOT NULL,
    traceback TEXT,
    context_json TEXT,              -- JSON: {instrument, timeframe, param_combo, ...}
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE INDEX idx_error_log_job_id ON error_log(job_id);
CREATE INDEX idx_error_log_error_type ON error_log(error_type);
```

---

## 3. Job Payload Schema

### Backtest Job Submission

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "backtest",
  "strategy_id": "strategy-uuid",
  "created_at": "2026-02-18T10:00:00Z",
  "params": {
    "instruments": ["EURUSD", "GBPUSD", "AUDUSD"],
    "timeframes": ["H1", "D1"],
    "data_start_date": "2023-01-01",
    "data_end_date": "2026-02-18",
    "parameter_grid": {
      "sma_period": [20, 50, 100],
      "breakout_threshold": [1.0, 1.5, 2.0],
      "slippage_pips": 2
    },
    "optimization": {
      "method": "grid_then_bayesian",
      "grid_iterations": 27,
      "bayesian_iterations": 100,
      "metric_to_optimize": "sharpe_ratio"
    }
  }
}
```

### Job Progress Event

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": {
    "pct_complete": 45,
    "current_phase": "grid_search",
    "current_instrument": "EURUSD",
    "current_timeframe": "H1",
    "current_iteration": 15,
    "total_iterations": 36,
    "elapsed_seconds": 3600,
    "estimated_remaining_seconds": 4400
  }
}
```

### Job Completion Result

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "completed_at": "2026-02-18T12:00:00Z",
  "summary": {
    "total_runs": 36,
    "optimization_method": "grid_then_bayesian",
    "best_parameters": {
      "sma_period": 50,
      "breakout_threshold": 1.5,
      "slippage_pips": 2
    },
    "best_metrics": {
      "sharpe_ratio": 1.85,
      "calmar_ratio": 0.92,
      "win_rate": 0.62,
      "max_drawdown": -0.15,
      "total_pnl": 4500
    },
    "results_by_instrument": {
      "EURUSD": {
        "H1": {...metrics...},
        "D1": {...metrics...}
      },
      "GBPUSD": {...}
    }
  }
}
```

---

## 4. Versioning Policy

### Schema Evolution Rules

**Phase 1–2:** StrategyDefinition v1.0 stable

**Phase 3+:** If new fields required (e.g., regime-based logic):
1. Create v1.1 schema (backward compatible)
2. Add new fields as optional with defaults
3. Keep v1.0 deserializer for legacy strategies
4. Mark status in API response: `schema_version: "1.0"` or `"1.1"`

**New major version (v2.0) only if:**
- Removing required fields
- Fundamentally changing entry/exit logic structure
- Cannot express via unions/enums in v1

### Migration Strategy

#### Python (alembic)

```bash
# Create migration
alembic revision --autogenerate -m "add_regime_logic_to_strategies"

# Run migration
alembic upgrade head
```

#### Node.js (manual SQL)

Store migrations in `/api/src/db/migrations/` as numbered SQL files:
```
001-initial-schema.sql
002-add-error-log-table.sql
003-add-robustness-reports-table.sql
```

On startup, Node.js execution checks schema version and applies missing migrations.

### Backward Compatibility

- **Reads:** Always deserialize using union of all active schema versions
- **Writes:** Always serialize to current version (v1.0 initially)
- **Queries:** Layer abstraction (Repository pattern) handles schema differences

Example (Python):
```python
def load_strategy(strategy_json: str) -> StrategyDefinition:
    """Load strategy from any version, return v1.0"""
    data = json.loads(strategy_json)
    version = data.get('version', '1.0')
    
    if version == '1.0':
        return StrategyDefinition.parse_obj(data)
    elif version == '1.1':
        # Convert v1.1 → v1.0 (strip new fields or apply defaults)
        return _migrate_v11_to_v10(data)
    else:
        raise ValueError(f"Unknown version: {version}")
```

---

## 5. Key Constraints & Validation

### StrategyDefinition Validation

1. **Entry rules must reference valid indicators or price_*:**
   ```python
   for rule in strategy.entry_rules:
       if rule.logic_type not in ('price_above', 'price_below'):
           assert rule.indicator_ref in [ind.name for ind in strategy.indicators]
   ```

2. **Advanced features only in advanced variant:**
   ```python
   if strategy.variant == 'basic':
       assert strategy.position_management.partial_take_profits is None
       assert strategy.position_management.trailing_stop is None
   ```

3. **SL must be < TP (for risk-reward >= 1):**
   ```python
   if strategy.position_management.target_risk_reward_ratio:
       min_tp = strategy.position_management.stop_loss_pips * \
                strategy.position_management.target_risk_reward_ratio
       assert strategy.position_management.take_profit_pips >= min_tp
   ```

### SQLite Constraints

- Runs foreign keys: cascade delete jobs → runs are deleted
- Audit log never updated (immutable): only INSERT
- Strategy status transitions: validate state machine (draft → tested or tested → validated)

---

## Next Steps

1. Generate Pydantic models in Python from StrategyDefinition schema
2. Generate Zod schemas in TypeScript for validation
3. Implement SQLite schema creation script
4. Create first alembic migration
5. Implement repository pattern CRUD operations
