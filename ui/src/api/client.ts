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
  created_at: string;
}

export interface StrategyRecord {
  id: string;
  definition: StrategyDefinition;
  created_at: string;
  updated_at: string;
}

export type ProviderId = "claude" | "gemini" | "openrouter";

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
};
