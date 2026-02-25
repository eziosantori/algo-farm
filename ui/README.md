# algo-farm UI

React + Vite frontend for the Algo Farm platform.

## Requirements

The API must be running on `http://localhost:3001` before starting the UI.
See [`api/README.md`](../api/README.md) for setup instructions.

## Setup

```bash
# From repo root
pnpm install
```

## Running

```bash
# Development server (port 5173)
pnpm --filter ui dev

# Or from the ui/ directory
pnpm dev
```

Vite proxies all `/api/*` requests to `http://localhost:3001`, so no CORS configuration is needed in development.

## Pages

| Path | Description |
|---|---|
| `/wizard` | Strategy Wizard — describe a strategy in natural language, preview, and save |
| `/strategies` | Strategies list — all saved strategies with inline JSON viewer |
