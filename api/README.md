# algo-farm API

Express + TypeScript REST API for the Algo Farm platform.

## Setup

```bash
# From repo root
pnpm install

# Copy env file and add your provider API key(s)
cp api/.env.example api/.env
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Anthropic API key (only if using Claude provider) |
| `GEMINI_API_KEY` | — | Google API key (only if using Gemini provider) |
| `GEMINI_MODEL` | `gemini-2.0-flash-lite` | Gemini model override |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `OPENROUTER_MODEL` | `openrouter/free` | Default OpenRouter model when request does not include `model` |
| `PORT` | `3001` | Port to listen on |
| `DB_PATH` | `./algo_farm.db` | SQLite database file path |

## Running

```bash
# Development (hot reload)
pnpm --filter api dev

# Or from the api/ directory
pnpm dev
```

## Testing

```bash
pnpm --filter api test
# or
cd api && pnpm test
```

## Endpoints

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Returns `{"status":"ok"}` |

### Wizard
| Method | Path | Description |
|---|---|---|
| POST | `/wizard/chat` | Generate a strategy from a natural language description |

**POST /wizard/chat**
```json
// Request
{
  "message": "RSI strategy: enter long when RSI < 30, exit when RSI > 70",
  "provider": "openrouter",
  "model": "openrouter/free"
}

// Response
{
  "strategy": { /* StrategyDefinition */ },
  "explanation": "Here is an RSI reversal strategy..."
}

// Errors
{ "error": "SCHEMA_VALIDATION_ERROR", "message": "..." }
{ "error": "LLM_API_ERROR", "message": "..." }
```

### OpenRouter models
| Method | Path | Description |
|---|---|---|
| GET | `/wizard/openrouter/models` | Returns top free tool-compatible OpenRouter models |

### Strategies CRUD
| Method | Path | Description |
|---|---|---|
| POST | `/strategies` | Save a strategy |
| GET | `/strategies` | List all strategies (summary) |
| GET | `/strategies/:id` | Get a strategy with full definition |
| PUT | `/strategies/:id` | Update a strategy |
| DELETE | `/strategies/:id` | Delete a strategy |

**POST /strategies** — body: `StrategyDefinition` → `{ id, created_at }`

**GET /strategies** → `{ strategies: [{ id, name, variant, created_at }] }`

**GET /strategies/:id** → `{ id, definition: StrategyDefinition, created_at, updated_at }`
