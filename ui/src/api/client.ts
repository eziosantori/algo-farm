import type { StrategyDefinition } from "@algo-farm/shared/strategy";

const BASE_URL = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.message ?? `HTTP ${res.status}`);
  }

  return res.json() as Promise<T>;
}

export interface WizardChatResponse {
  strategy: StrategyDefinition;
  explanation: string;
}

export interface StrategySummary {
  id: string;
  name: string;
  variant: string;
  lifecycle_status: string;
  created_at: string;
}

export interface StrategyRecord {
  id: string;
  definition: StrategyDefinition;
  created_at: string;
  updated_at: string;
}

export type ProviderId = "claude" | "gemini" | "openrouter";

// ---------------------------------------------------------------------------
// Lab types
// ---------------------------------------------------------------------------

export type SessionStatus = "running" | "completed";
export type ResultStatus =
  | "pending"
  | "validated"
  | "rejected"
  | "production_standard"
  | "production_aggressive"
  | "production_defensive";

export interface LabSessionSummary {
  id: string;
  strategy_name: string;
  strategy_id?: string;
  instruments: string[];
  timeframes: string[];
  status: SessionStatus;
  total_results: number;
  validated_results: number;
  created_at: string;
  updated_at: string;
}

export interface BacktestMetrics {
  total_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  profit_factor: number;
  total_trades: number;
  avg_trade_duration_bars: number;
  cagr_pct: number;
  expectancy: number;
}

export interface BacktestResultDetail {
  id: string;
  session_id: string;
  instrument: string;
  timeframe: string;
  params: Record<string, unknown>;
  metrics: BacktestMetrics;
  status: ResultStatus;
  created_at: string;
}

export interface LabSessionDetail {
  id: string;
  strategy_name: string;
  strategy_id?: string;
  strategy: unknown;
  instruments: string[];
  timeframes: string[];
  constraints: Record<string, number> | null;
  status: SessionStatus;
  results: BacktestResultDetail[];
  created_at: string;
  updated_at: string;
}

export const api = {
  wizardChat(message: string, provider: ProviderId = "gemini"): Promise<WizardChatResponse> {
    return request("/wizard/chat", {
      method: "POST",
      body: JSON.stringify({ message, provider }),
    });
  },

  createStrategy(definition: StrategyDefinition): Promise<{ id: string; created_at: string }> {
    return request("/strategies", {
      method: "POST",
      body: JSON.stringify(definition),
    });
  },

  listStrategies(): Promise<{ strategies: StrategySummary[] }> {
    return request("/strategies");
  },

  getStrategy(id: string): Promise<StrategyRecord> {
    return request(`/strategies/${id}`);
  },

  listLabSessions(): Promise<{ sessions: LabSessionSummary[] }> {
    return request("/lab/sessions");
  },

  getLabSession(id: string): Promise<LabSessionDetail> {
    return request(`/lab/sessions/${id}`);
  },

  updateLabResultStatus(id: string, status: ResultStatus): Promise<BacktestResultDetail> {
    return request(`/lab/results/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },

  createLabSession(payload: {
    strategy_name: string;
    strategy_json: string;
    instruments: string[];
    timeframes: string[];
    strategy_id?: string;
  }): Promise<{ id: string; created_at: string }> {
    return request("/lab/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
