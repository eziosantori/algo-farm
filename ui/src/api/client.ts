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

export type ProviderId = "openrouter";
export interface OpenRouterModelOption {
  id: string;
  name: string;
  context_length: number;
  supports_tools: boolean;
  supports_tool_choice: boolean;
  source: "openrouter";
}

export interface OpenRouterModelsResponse {
  models: OpenRouterModelOption[];
  fetched_at: string;
  cache_ttl_seconds: number;
}

// ---------------------------------------------------------------------------
// Lab types
// ---------------------------------------------------------------------------

export type SessionStatus = "running" | "completed" | "failed";
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

export type ResultSplit =
  | "is" | "oos" | "full"
  | "robustness_score" | "wf" | "mc" | "sensitivity" | "permutation";

export interface RobustnessComponentScore {
  score: number | null;
  weight: number;
  effective_weight: number;
}

export interface RobustnessScoreData {
  composite_score: number | null;
  grade: "A" | "B" | "C" | "F" | null;
  go_nogo: "GO" | "NO-GO" | null;
  components: Record<string, RobustnessComponentScore>;
}

export interface BacktestResultDetail {
  id: string;
  session_id: string;
  instrument: string;
  timeframe: string;
  params: Record<string, unknown>;
  metrics: BacktestMetrics;
  status: ResultStatus;
  split: ResultSplit;
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

// ---------------------------------------------------------------------------
// Vault / Lab summary types
// ---------------------------------------------------------------------------

export interface TopPerformerRow {
  instrument: string;
  timeframe: string;
  sharpe_ratio: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  profit_factor: number;
  total_trades: number;
  params: Record<string, unknown>;
  status: string;
}

export interface StrategyLabSummary {
  top_performers: TopPerformerRow[];
  best_params: Record<string, unknown>;
  coverage: { instruments: string[]; timeframes: string[]; total_runs: number };
  sessions_with_notes: Array<{ id: string; created_at: string; research_notes: string }>;
}

// ---------------------------------------------------------------------------
// Deployment types
// ---------------------------------------------------------------------------

export interface DeploymentPairRow {
  instrument: string;
  timeframe: string;
  /** Global params + per-pair overrides merged — the params to apply on platform */
  effective_params: Record<string, unknown>;
  /** Keys whose value differs from global default */
  overridden_keys: string[];
  is_sharpe: number | null;
  oos_sharpe: number | null;
  oos_is_ratio: number | null;
  passed_robustness: boolean;
}

export interface DeploymentSummary {
  strategy_id: string;
  global_params: Record<string, unknown>;
  pairs: DeploymentPairRow[];
}

// ---------------------------------------------------------------------------
// Export helpers
// ---------------------------------------------------------------------------

export type ExportFormat = "ctrader" | "pine" | "opset";

export async function downloadExport(
  id: string,
  format: ExportFormat,
  options?: { instrument?: string; timeframe?: string },
): Promise<void> {
  const qs = new URLSearchParams();
  if (options?.instrument) qs.set("instrument", options.instrument);
  if (options?.timeframe) qs.set("timeframe", options.timeframe);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const res = await fetch(`${BASE_URL}/strategies/${id}/export/${format}${suffix}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { message?: string }).message ?? `HTTP ${res.status}`
    );
  }
  const blob = await res.blob();
  const extMap: Record<ExportFormat, string> = { ctrader: "cs", pine: "pine", opset: "cbotset" };
  const ext = extMap[format];
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? `strategy.${ext}`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function previewExport(
  id: string,
  format: ExportFormat,
  options?: { instrument?: string; timeframe?: string },
): Promise<{ code: string; filename: string }> {
  const qs = new URLSearchParams();
  if (options?.instrument) qs.set("instrument", options.instrument);
  if (options?.timeframe) qs.set("timeframe", options.timeframe);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const res = await fetch(
    `${BASE_URL}/strategies/${id}/export/${format}/preview${suffix}`
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { message?: string }).message ?? `HTTP ${res.status}`
    );
  }
  return res.json() as Promise<{ code: string; filename: string }>;
}

export const api = {
  wizardChat(
    message: string,
    provider: ProviderId = "openrouter",
    model?: string
  ): Promise<WizardChatResponse> {
    return request("/wizard/chat", {
      method: "POST",
      body: JSON.stringify({ message, provider, model }),
    });
  },

  listOpenRouterFreeModels(): Promise<OpenRouterModelsResponse> {
    return request("/wizard/openrouter/models");
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

  getStrategyLabSummary(id: string): Promise<StrategyLabSummary> {
    return request(`/strategies/${id}/lab-summary`);
  },

  runLabSession(
    sessionId: string,
    options?: {
      data_dir?: string;
      engine_db_path?: string;
      param_grid?: Record<string, unknown>;
      optimize_metric?: string;
      optimizer?: "grid" | "bayesian";
      n_trials?: number;
      from_date?: string;
      to_date?: string;
    }
  ): Promise<{ job_id: string; session_id: string }> {
    return request(`/lab/sessions/${sessionId}/run`, {
      method: "POST",
      body: JSON.stringify(options ?? {}),
    });
  },

  getDeploymentSummary(id: string): Promise<DeploymentSummary> {
    return request(`/strategies/${id}/deployment`);
  },
};
