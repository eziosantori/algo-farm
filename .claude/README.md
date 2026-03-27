# Agent System Catalog

This folder contains the project-level agent orchestration for strategy ideation and lifecycle automation.

## Design Board (idea → draft strategy)

Command:
- `/design-strategy`

Agents used:
- `technical-analyst`
- `market-structure-analyst`
- `risk-position-analyst`
- `strategy-advocate`
- `strategy-critic`
- `strategy-composer`

Outputs:
- Strategy JSON: `engine/strategies/draft/<name>.json`
- Design report: `engine/strategies/designs/<name>_design.md`

## Development Pipeline (draft → validated)

Commands:
- `/backtest`
- `/iterate`
- `/optimize`
- `/strategy-lab`
- `/robustness`

Notes:
- `/iterate` now archives prior variants to `engine/strategies/archive/<name>/` to keep `draft/` clean.
- All optimization/iteration runs are IS-only; OOS validation happens in `/robustness`.

## Full Lifecycle

Agent:
- `@workflow-orchestrator`

Flow:
- baseline → iterate → optimize → robustness → promote

## Design Report Promotion

Command:
- `/promote-design <strategy_name>`

Behavior:
- Promotes from `engine/strategies/designs/` to `docs/ideas/strategies/`
- Includes fallback support for legacy `docs/ideas/tmp/<strategy_name>/`
