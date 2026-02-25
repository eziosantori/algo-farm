# API_SPEC.md — Node.js API Contract (Draft)

## Executive Summary

This document specifies **two distinct API surfaces** for the platform:

1. **Phase 1 — Python CLI contract** (no HTTP, no infra): The standalone engine is invoked as a subprocess. Input is CLI flags + JSON files. Output is newline-delimited JSON on stdout. Full schema in `SCHEMA.md §1`.
2. **Phase 2+ — Node.js REST API**: Express server that wraps the Python CLI, adds job orchestration, strategy vault CRUD, and export pipeline. Documented as an OpenAPI 3.1 spec below.

**REST API phase map:**

| Tag | Introduced |
|-----|-----------|
| Wizard | Phase 2 |
| Strategy CRUD | Phase 2 |
| Jobs, Results | Phase 3 |
| Robustness | Phase 4 |
| Vault (journal, param sets) | Phase 5 |
| Export | Phase 6 |

**Status markers:** `[stable]` = contract finalized for its phase. `[draft]` = subject to change.

---

## Phase 1 CLI Contract (quick reference)

> Full schema in `SCHEMA.md §1`. This section is a quick reference for the engine's command-line interface.

```bash
# Single backtest run (no optimization)
python engine/run.py \
  --strategy strategy.json \
  --instruments EURUSD,GBPUSD \
  --timeframes H1,D1 \
  --db ./algo_farm.db

# Grid search optimization
python engine/run.py \
  --strategy strategy.json \
  --instruments EURUSD \
  --timeframes H1 \
  --param-grid param_grid.json \
  --optimize grid \
  --metric sharpe_ratio \
  --db ./algo_farm.db

# Resume interrupted job
python engine/run.py --resume-job <job_id> --db ./algo_farm.db
```

**Output:** newline-delimited JSON on stdout (`progress`, `result`, `completed` messages — see `SCHEMA.md §1.2`). Errors on stderr.

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Completed successfully |
| `1` | Unrecoverable error (missing data file, invalid strategy JSON, etc.) |
| `2` | Interrupted (SIGINT/SIGTERM); job state saved, resumable with `--resume-job` |

---

## Phase 2+ — OpenAPI 3.1 Specification

```yaml
openapi: 3.1.0
info:
  title: Algo Farm API
  description: |
    REST API for the Algo Trading Strategy Development Platform.
    Introduced in Phase 2. Phase 1 uses the Python CLI directly (see CLI contract above).
  version: 1.0.0
  contact:
    name: Algo Farm Team

servers:
  - url: http://localhost:3001/api
    description: Local development
  - url: https://api.algo-farm.local
    description: Production

components:
  schemas:
    StrategyDefinition:
      # Reference shared schema from SCHEMA.md
      type: object
      required: [version, name, variant, indicators, entry_rules, exit_rules, position_management]
      properties:
        version:
          type: string
          const: "1.0"
        name:
          type: string
          minLength: 3
          maxLength: 100
        description:
          type: string
          maxLength: 1000
        variant:
          type: string
          enum: [basic, advanced]
        indicators:
          type: array
          items:
            type: object
            required: [name, type]
            properties:
              name:
                type: string
              type:
                type: string
                enum: [sma, ema, macd, rsi, stoch, atr, bollinger_bands, momentum, adx, cci, obv, williamsr]
              params:
                type: object
        entry_rules:
          type: array
          minItems: 1
        exit_rules:
          type: array
          minItems: 1
        position_management:
          type: object
          required: [variant_type, stop_loss_pips]
          properties:
            variant_type:
              type: string
              enum: [basic, advanced]
            stop_loss_pips:
              type: number
              minimum: 0.5
            take_profit_pips:
              type: number
            target_risk_reward_ratio:
              type: number
            partial_take_profits:
              type: array
            trailing_stop:
              type: object
            re_entry:
              type: object
        filters:
          type: object

    JobPayload:
      type: object
      required: [strategy_id, instruments, timeframes]
      properties:
        strategy_id:
          type: string
          format: uuid
          description: Reference to saved strategy
        instruments:
          type: array
          items:
            type: string
          minItems: 1
          example: [EURUSD, GBPUSD]
        timeframes:
          type: array
          items:
            type: string
          minItems: 1
          example: [H1, D1]
        data_start_date:
          type: string
          format: date
          example: "2023-01-01"
        data_end_date:
          type: string
          format: date
          example: "2026-02-18"
        parameter_grid:
          type: object
          description: |
            Parameter ranges for optimization.
            Each key is a parameter name, value is array of values to try.
          example:
            sma_period: [20, 50, 100]
            breakout_threshold: [1.0, 1.5, 2.0]
        optimization:
          type: object
          properties:
            method:
              type: string
              enum: [grid_only, grid_then_bayesian, bayesian_only]
              default: grid_then_bayesian
            grid_iterations:
              type: integer
              example: 27
            bayesian_iterations:
              type: integer
              example: 100
            metric_to_optimize:
              type: string
              enum: [sharpe_ratio, calmar_ratio, profit_factor, total_pnl]
              default: sharpe_ratio

    JobResponse:
      type: object
      properties:
        job_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [pending, processing, completed, failed, cancelled]
        created_at:
          type: string
          format: date-time
        started_at:
          type: string
          format: date-time
        completed_at:
          type: string
          format: date-time
        error_message:
          type: string

    JobProgress:
      type: object
      properties:
        job_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [pending, processing, completed, failed]
        progress_pct:
          type: integer
          minimum: 0
          maximum: 100
        current:
          type: object
          properties:
            instrument:
              type: string
            timeframe:
              type: string
            iteration:
              type: integer
            total_iterations:
              type: integer
        elapsed_seconds:
          type: integer
        estimated_remaining_seconds:
          type: integer

    BacktestRun:
      type: object
      properties:
        id:
          type: string
          format: uuid
        instrument:
          type: string
        timeframe:
          type: string
        parameters:
          type: object
          description: Actual parameters used for this run
        metrics:
          type: object
          properties:
            net_pnl:
              type: number
            cagr:
              type: number
            max_drawdown:
              type: number
            calmar_ratio:
              type: number
            sharpe_ratio:
              type: number
            sortino_ratio:
              type: number
            profit_factor:
              type: number
            win_rate:
              type: number
            num_trades:
              type: integer
            avg_trade_duration_bars:
              type: integer
            expectancy:
              type: number
        equity_curve:
          type: array
          items:
            type: object
            properties:
              timestamp:
                type: string
                format: date-time
              equity:
                type: number
              drawdown:
                type: number
        trades:
          type: array
          items:
            type: object
            properties:
              entry_time:
                type: string
                format: date-time
              entry_price:
                type: number
              exit_time:
                type: string
                format: date-time
              exit_price:
                type: number
              profit_pips:
                type: number
              profit_loss:
                type: number

    Strategy:
      type: object
      properties:
        id:
          type: string
          format: uuid
        definition:
          $ref: '#/components/schemas/StrategyDefinition'
        status:
          type: string
          enum: [draft, tested, validated, production, archived]
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    ErrorResponse:
      type: object
      required: [code, message]
      properties:
        code:
          type: string
          description: Machine-readable error code
        message:
          type: string
          description: Human-readable error message
        details:
          type: object
          description: Optional additional context

  responses:
    BadRequest:
      description: Invalid request body or parameters
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            code: SCHEMA_VALIDATION_ERROR
            message: 'Invalid strategy definition: missing required field "entry_rules"'
            details:
              field: entry_rules
              reason: required_field_missing

    Unauthorized:
      description: Missing or invalid authentication
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            code: UNAUTHORIZED
            message: Missing API key

    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            code: NOT_FOUND
            message: Strategy with ID strategy-123 not found

    Conflict:
      description: Resource state conflict (e.g., job already running)
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            code: JOB_ALREADY_RUNNING
            message: A backtest job is already running for this strategy

    InternalServerError:
      description: Server error (Python engine failed, DB error, etc.)
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            code: PYTHON_ENGINE_ERROR
            message: Strategy backtest failed
            details:
              error_type: DataMissingError
              job_id: job-123
              python_traceback: "Traceback (most recent call last)..."

paths:
  /health:
    get:
      tags: [System]
      summary: Health check
      operationId: getHealth
      responses:
        '200':
          description: Service is healthy
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    const: ok
                  timestamp:
                    type: string
                    format: date-time
                  uptime_seconds:
                    type: integer

  # Phase 2: Strategy Wizard
  /wizard/chat:
    post:
      tags: [Wizard]
      summary: Chat with LLM to generate strategy
      operationId: chatWithWizard
      status: "[stable]"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [message]
              properties:
                message:
                  type: string
                  description: User description of trading idea
                  example: "I want a breakout strategy that enters long when price breaks above 20-day high"
                chat_history:
                  type: array
                  items:
                    type: object
                    properties:
                      role:
                        type: string
                        enum: [user, assistant]
                      content:
                        type: string
      responses:
        '200':
          description: LLM generated strategy definition
          content:
            application/json:
              schema:
                type: object
                properties:
                  strategy_definition:
                    $ref: '#/components/schemas/StrategyDefinition'
                  variants:
                    type: object
                    properties:
                      basic:
                        $ref: '#/components/schemas/StrategyDefinition'
                      advanced:
                        $ref: '#/components/schemas/StrategyDefinition'
                  explanation:
                    type: string
                    description: Plain-English explanation of the generated strategy
        '400':
          $ref: '#/components/responses/BadRequest'
        '500':
          description: LLM API error or parsing failure
          $ref: '#/components/responses/InternalServerError'

  /wizard/suggest:
    get:
      tags: [Wizard]
      summary: Get suggested indicators for a strategy type
      operationId: getSuggestions
      status: "[stable]"
      parameters:
        - in: query
          name: style
          schema:
            type: string
            enum: [trend, mean-reversion, breakout, scalping, carry]
          description: Trading style
        - in: query
          name: timeframe_range
          schema:
            type: string
            enum: [scalp, swing, position]
          description: Timeframe range preference
      responses:
        '200':
          description: Suggested indicators and filter combinations
          content:
            application/json:
              schema:
                type: object
                properties:
                  indicators:
                    type: array
                    items:
                      type: object
                      properties:
                        name:
                          type: string
                        description:
                          type: string
                        suggested_params:
                          type: object
                  filters:
                    type: array
                    items:
                      type: object
                  sample_entry_rules:
                    type: array

  # Phase 2: Strategy CRUD
  # (Node.js persists the StrategyDefinition produced by the Wizard or submitted directly)
  /strategies:
    post:
      tags: [Strategy]
      summary: Create new strategy
      operationId: createStrategy
      status: "[stable]"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/StrategyDefinition'
      responses:
        '201':
          description: Strategy created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Strategy'
        '400':
          $ref: '#/components/responses/BadRequest'

    get:
      tags: [Strategy]
      summary: List all strategies (with filtering)
      operationId: listStrategies
      status: "[stable]"
      parameters:
        - in: query
          name: status
          schema:
            type: string
            enum: [draft, tested, validated, production, archived]
        - in: query
          name: tag
          schema:
            type: array
            items:
              type: string
          description: Filter by tags (OR logic)
        - in: query
          name: search
          schema:
            type: string
          description: Full-text search on name/description
      responses:
        '200':
          description: List of strategies
          content:
            application/json:
              schema:
                type: object
                properties:
                  strategies:
                    type: array
                    items:
                      $ref: '#/components/schemas/Strategy'
                  total:
                    type: integer

  /strategies/{strategy_id}:
    get:
      tags: [Strategy]
      summary: Get strategy details
      operationId: getStrategy
      status: "[stable]"
      parameters:
        - in: path
          name: strategy_id
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Strategy details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Strategy'
        '404':
          $ref: '#/components/responses/NotFound'

    put:
      tags: [Strategy]
      summary: Update strategy
      operationId: updateStrategy
      status: "[stable]"
      parameters:
        - in: path
          name: strategy_id
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                definition:
                  $ref: '#/components/schemas/StrategyDefinition'
                notes:
                  type: string
      responses:
        '200':
          description: Strategy updated
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Strategy'
        '404':
          $ref: '#/components/responses/NotFound'

    delete:
      tags: [Strategy]
      summary: Delete strategy
      operationId: deleteStrategy
      status: "[stable]"
      parameters:
        - in: path
          name: strategy_id
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '204':
          description: Strategy deleted

  /strategies/{strategy_id}/status:
    put:
      tags: [Strategy]
      summary: Update strategy status (lifecycle)
      operationId: updateStrategyStatus
      status: "[stable]"
      parameters:
        - in: path
          name: strategy_id
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [status]
              properties:
                status:
                  type: string
                  enum: [draft, tested, validated, production, archived]
      responses:
        '200':
          description: Status updated
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Strategy'
        '409':
          description: Invalid status transition
          $ref: '#/components/responses/Conflict'

  # Phase 3: Jobs (Backtest)
  # Node.js wraps the Phase 1 Python CLI via BullMQ child process
  /jobs:
    post:
      tags: [Jobs]
      summary: Submit backtest job
      operationId: submitBacktestJob
      status: "[stable]"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/JobPayload'
      responses:
        '202':
          description: Job queued
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobResponse'
        '400':
          $ref: '#/components/responses/BadRequest'
        '404':
          description: Strategy not found
          $ref: '#/components/responses/NotFound'
        '409':
          description: Job already running for this strategy
          $ref: '#/components/responses/Conflict'

  /jobs/{job_id}:
    get:
      tags: [Jobs]
      summary: Get job status
      operationId: getJobStatus
      status: "[stable]"
      parameters:
        - in: path
          name: job_id
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Job status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobResponse'
        '404':
          $ref: '#/components/responses/NotFound'

  /jobs/{job_id}/progress:
    get:
      tags: [Jobs]
      summary: Get job progress (polling)
      operationId: getJobProgress
      status: "[stable]"
      parameters:
        - in: path
          name: job_id
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Job progress
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobProgress'
        '404':
          $ref: '#/components/responses/NotFound'

  /jobs/{job_id}/cancel:
    post:
      tags: [Jobs]
      summary: Cancel running job
      operationId: cancelJob
      status: "[draft]"
      parameters:
        - in: path
          name: job_id
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Job cancelled
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobResponse'
        '409':
          description: Cannot cancel job (already completed)
          $ref: '#/components/responses/Conflict'

  # Phase 3: Results
  /results/{job_id}:
    get:
      tags: [Results]
      summary: Get backtest results
      operationId: getBacktestResults
      status: "[stable]"
      parameters:
        - in: path
          name: job_id
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Backtest results
          content:
            application/json:
              schema:
                type: object
                properties:
                  job_id:
                    type: string
                    format: uuid
                  runs:
                    type: array
                    items:
                      $ref: '#/components/schemas/BacktestRun'
                  summary:
                    type: object
                    properties:
                      total_runs:
                        type: integer
                      best_parameters:
                        type: object
                      best_metrics:
                        type: object
                      results_by_instrument:
                        type: object
        '404':
          $ref: '#/components/responses/NotFound'

  /results/{job_id}/heatmap:
    get:
      tags: [Results]
      summary: Get heatmap data (instrument × timeframe)
      operationId: getHeatmapData
      status: "[draft]"
      parameters:
        - in: path
          name: job_id
          required: true
          schema:
            type: string
            format: uuid
        - in: query
          name: metric
          schema:
            type: string
            enum: [sharpe_ratio, calmar_ratio, profit_factor, max_drawdown]
            default: sharpe_ratio
      responses:
        '200':
          description: Heatmap data
          content:
            application/json:
              schema:
                type: object
                properties:
                  instruments:
                    type: array
                    items:
                      type: string
                  timeframes:
                    type: array
                    items:
                      type: string
                  values:
                    type: array
                    items:
                      type: array
                      items:
                        type: number
                  min:
                    type: number
                  max:
                    type: number

  # Phase 6: Export
  /export/{strategy_id}/{format}:
    post:
      tags: [Export]
      summary: Export strategy to target format
      operationId: exportStrategy
      status: "[draft]"
      parameters:
        - in: path
          name: strategy_id
          required: true
          schema:
            type: string
            format: uuid
        - in: path
          name: format
          required: true
          schema:
            type: string
            enum: [ctrader, pine_script, metatrader5]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                parameter_set_id:
                  type: string
                  format: uuid
                  description: Optional; if not provided, use sample parameters
      responses:
        '200':
          description: Exported code
          content:
            application/json:
              schema:
                type: object
                properties:
                  format:
                    type: string
                  filename:
                    type: string
                  code:
                    type: string
                  language:
                    type: string
        '404':
          $ref: '#/components/responses/NotFound'
        '400':
          description: Format not supported for this strategy
          $ref: '#/components/responses/BadRequest'

  /export/formats:
    get:
      tags: [Export]
      summary: List supported export formats
      operationId: getExportFormats
      status: "[draft]"
      responses:
        '200':
          description: List of formats
          content:
            application/json:
              schema:
                type: object
                properties:
                  formats:
                    type: array
                    items:
                      type: object
                      properties:
                        id:
                          type: string
                        name:
                          type: string
                        description:
                          type: string
                        supported_features:
                          type: array
                          items:
                            type: string

  # WebSocket: Live job progress
  /ws/jobs/{job_id}/progress:
    get:
      tags: [WebSocket]
      summary: WebSocket endpoint for live job progress
      operationId: subscribeJobProgress
      status: "[draft]"
      description: |
        Upgrade to WebSocket to receive real-time job progress events.
        Connection string: `ws://localhost:3001/api/ws/jobs/{job_id}/progress`
        
        Events emitted:
        - `progress`: Job progress update (every 5-10 seconds)
        - `completed`: Job finished successfully
        - `failed`: Job failed with error
        - `cancelled`: Job was cancelled
        
        Message format:
        ```json
        {
          "type": "progress",
          "data": {
            "progress_pct": 45,
            "current_instrument": "EURUSD",
            "current_timeframe": "H1"
          }
        }
        ```
      parameters:
        - in: path
          name: job_id
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '101':
          description: Switching Protocols to WebSocket
        '404':
          $ref: '#/components/responses/NotFound'
```

---

## Error Codes

### Client Errors (4xx)

| Code | HTTP | Meaning |
|------|------|---------|
| `SCHEMA_VALIDATION_ERROR` | 400 | StrategyDefinition or JobPayload doesn't match schema |
| `INVALID_PARAMETER` | 400 | Query/path parameter invalid (e.g., invalid enum) |
| `MISSING_REQUIRED_FIELD` | 400 | Request missing required field |
| `UNAUTHORIZED` | 401 | Missing/invalid API key (future feature) |
| `NOT_FOUND` | 404 | Resource (strategy, job, run) doesn't exist |
| `JOB_ALREADY_RUNNING` | 409 | Can't submit another job for this strategy (one running) |
| `INVALID_STATUS_TRANSITION` | 409 | Strategy status change not allowed (e.g., archived → production) |
| `UNSUPPORTED_EXPORT_FORMAT` | 400 | Format not supported (or incompatible with strategy) |

### Server Errors (5xx)

| Code | HTTP | Meaning | Action |
|------|------|---------|--------|
| `INTERNAL_SERVER_ERROR` | 500 | Unexpected error (DB, Redis, etc.) | Retry after 30s |
| `PYTHON_ENGINE_ERROR` | 500 | Backtest/optimization failed | Check job error_log, retry (maybe with adjusted params) |
| `LLM_API_ERROR` | 500 | LLM provider timeout or error | Retry after 30s |
| `DATABASE_ERROR` | 500 | SQLite constraint or I/O error | Retry after 60s |

---

## Rate Limiting (Phase 4+)

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1613654400
```

- **Job submission:** 10 per minute per strategy
- **Other endpoints:** 100 per minute per IP
- **WebSocket:** No rate limit (connection-scoped)

---

## Status Codes Summary

| Code | Use Case |
|------|----------|
| `200 OK` | GET request successful, POST with no creation |
| `201 Created` | POST /strategies created new resource |
| `202 Accepted` | POST /jobs job queued (async) |
| `204 No Content` | DELETE successful |
| `400 Bad Request` | Schema/validation error, client's fault |
| `401 Unauthorized` | Missing/invalid auth |
| `404 Not Found` | Resource doesn't exist |
| `409 Conflict` | Job already running, invalid status transition |
| `500 Internal Server Error` | Server fault (DB, engine, LLM API) |

---

## Next Steps

1. Implement OpenAPI generator (swagger-ui or ReDoc)
2. Add authentication layer (optional API key or JWT)
3. Implement rate limiting (Phase 3+)
4. Set up API documentation site (swagger-ui at /api/docs)
