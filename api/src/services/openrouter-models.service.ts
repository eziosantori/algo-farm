import { z } from "zod";

const OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models";
const DEFAULT_TTL_SECONDS = 600;
const MAX_SHORTLIST_SIZE = 8;
const PRIORITY_MODEL_IDS = [
  "openrouter/free",
  "arcee-ai/trinity-large-preview:free",
  "arcee-ai/trinity-mini:free",
  "qwen/qwen3-coder:free",
  "stepfun/step-3.5-flash:free",
] as const;

const OpenRouterModelsResponseSchema = z.object({
  data: z.array(
    z.object({
      id: z.string(),
      name: z.string().optional(),
      context_length: z.number().optional(),
      supported_parameters: z.array(z.string()).optional(),
      pricing: z
        .object({
          prompt: z.string().optional(),
          completion: z.string().optional(),
        })
        .optional(),
    })
  ),
});

export interface OpenRouterModelSummary {
  id: string;
  name: string;
  context_length: number;
  supports_tools: boolean;
  supports_tool_choice: boolean;
  source: "openrouter";
}

export interface OpenRouterModelsListResponse {
  models: OpenRouterModelSummary[];
  fetched_at: string;
  cache_ttl_seconds: number;
}

interface CachedOpenRouterModels {
  models: OpenRouterModelSummary[];
  fetchedAt: string;
  expiresAtMs: number;
}

function supportsTools(supportedParameters: string[] | undefined): boolean {
  return (supportedParameters ?? []).includes("tools");
}

function supportsToolChoice(supportedParameters: string[] | undefined): boolean {
  return (supportedParameters ?? []).includes("tool_choice");
}

function isTrulyFree(pricing: { prompt?: string; completion?: string } | undefined): boolean {
  return pricing?.prompt === "0" && pricing?.completion === "0";
}

function rankModels(models: OpenRouterModelSummary[]): OpenRouterModelSummary[] {
  const byId = new Map<string, OpenRouterModelSummary>();
  for (const model of models) {
    const existing = byId.get(model.id);
    if (!existing || model.context_length > existing.context_length) {
      byId.set(model.id, model);
    }
  }

  const ordered: OpenRouterModelSummary[] = [];
  for (const priorityId of PRIORITY_MODEL_IDS) {
    const model = byId.get(priorityId);
    if (model) {
      ordered.push(model);
      byId.delete(priorityId);
    }
  }

  const rest = [...byId.values()].sort(
    (a, b) => b.context_length - a.context_length || a.id.localeCompare(b.id)
  );
  ordered.push(...rest);

  return ordered.slice(0, MAX_SHORTLIST_SIZE);
}

export class OpenRouterModelsService {
  private readonly fetchImpl: typeof fetch;
  private readonly now: () => number;
  private readonly ttlMs: number;
  private cache: CachedOpenRouterModels | null = null;
  private lastGoodSnapshot: CachedOpenRouterModels | null = null;

  constructor(opts?: { fetchImpl?: typeof fetch; now?: () => number; ttlSeconds?: number }) {
    this.fetchImpl = opts?.fetchImpl ?? fetch;
    this.now = opts?.now ?? (() => Date.now());
    this.ttlMs = (opts?.ttlSeconds ?? DEFAULT_TTL_SECONDS) * 1000;
  }

  async listFreeModels(): Promise<OpenRouterModelsListResponse> {
    const currentTime = this.now();
    if (this.cache && this.cache.expiresAtMs > currentTime) {
      return this.toResponse(this.cache);
    }

    try {
      const models = await this.fetchAndBuildShortlist();
      const snapshot: CachedOpenRouterModels = {
        models,
        fetchedAt: new Date(currentTime).toISOString(),
        expiresAtMs: currentTime + this.ttlMs,
      };

      this.cache = snapshot;
      this.lastGoodSnapshot = snapshot;
      return this.toResponse(snapshot);
    } catch (err) {
      if (this.lastGoodSnapshot) {
        return this.toResponse(this.lastGoodSnapshot);
      }

      const message = err instanceof Error ? err.message : "Unknown error";
      throw new Error(`LLM_API_ERROR: Failed to load OpenRouter models: ${message}`);
    }
  }

  private toResponse(snapshot: CachedOpenRouterModels): OpenRouterModelsListResponse {
    return {
      models: snapshot.models,
      fetched_at: snapshot.fetchedAt,
      cache_ttl_seconds: Math.floor(this.ttlMs / 1000),
    };
  }

  private async fetchAndBuildShortlist(): Promise<OpenRouterModelSummary[]> {
    const headers: Record<string, string> = {};
    const apiKey = process.env.OPENROUTER_API_KEY;
    if (apiKey) {
      headers["Authorization"] = `Bearer ${apiKey}`;
    }

    const response = await this.fetchImpl(OPENROUTER_MODELS_URL, { headers });
    if (!response.ok) {
      throw new Error(`OpenRouter HTTP ${response.status}`);
    }

    const payload = await response.json();
    const parsed = OpenRouterModelsResponseSchema.parse(payload);

    const compatibleFreeModels = parsed.data
      .filter((m) => isTrulyFree(m.pricing))
      .filter((m) => supportsTools(m.supported_parameters))
      .map<OpenRouterModelSummary>((m) => ({
        id: m.id,
        name: m.name ?? m.id,
        context_length: m.context_length ?? 0,
        supports_tools: true,
        supports_tool_choice: supportsToolChoice(m.supported_parameters),
        source: "openrouter",
      }));

    return rankModels(compatibleFreeModels);
  }
}

export const openRouterModelsService = new OpenRouterModelsService();
export const __private__ = { isTrulyFree, rankModels };
