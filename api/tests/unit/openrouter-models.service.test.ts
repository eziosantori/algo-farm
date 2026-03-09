import { describe, it, expect, vi } from "vitest";
import { OpenRouterModelsService, __private__ } from "../../src/services/openrouter-models.service.js";

function asJsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("OpenRouterModelsService", () => {
  it("includes only truly free models with tools support", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      asJsonResponse({
        data: [
          {
            id: "openrouter/free",
            name: "OpenRouter Auto Free",
            context_length: 128000,
            supported_parameters: ["tools", "tool_choice"],
            pricing: { prompt: "0", completion: "0" },
          },
          {
            id: "paid/model",
            name: "Paid model",
            context_length: 128000,
            supported_parameters: ["tools"],
            pricing: { prompt: "0.0001", completion: "0.0002" },
          },
          {
            id: "free/no-tools",
            name: "Free but no tools",
            context_length: 64000,
            supported_parameters: ["temperature"],
            pricing: { prompt: "0", completion: "0" },
          },
        ],
      })
    );

    const service = new OpenRouterModelsService({
      fetchImpl: fetchMock as unknown as typeof fetch,
      ttlSeconds: 600,
    });

    const result = await service.listFreeModels();
    expect(result.models).toHaveLength(1);
    expect(result.models[0]?.id).toBe("openrouter/free");
    expect(result.models[0]?.supports_tools).toBe(true);
    expect(result.models[0]?.supports_tool_choice).toBe(true);
  });

  it("ranks models with priority first and caps list at 8", () => {
    const ranked = __private__.rankModels([
      {
        id: "model/high-context",
        name: "Model High Context",
        context_length: 200000,
        supports_tools: true,
        supports_tool_choice: false,
        source: "openrouter",
      },
      {
        id: "openrouter/free",
        name: "OpenRouter Free",
        context_length: 100000,
        supports_tools: true,
        supports_tool_choice: true,
        source: "openrouter",
      },
      {
        id: "arcee-ai/trinity-large-preview:free",
        name: "Trinity Large",
        context_length: 128000,
        supports_tools: true,
        supports_tool_choice: true,
        source: "openrouter",
      },
      {
        id: "arcee-ai/trinity-mini:free",
        name: "Trinity Mini",
        context_length: 64000,
        supports_tools: true,
        supports_tool_choice: false,
        source: "openrouter",
      },
      {
        id: "qwen/qwen3-coder:free",
        name: "Qwen Coder",
        context_length: 256000,
        supports_tools: true,
        supports_tool_choice: true,
        source: "openrouter",
      },
      {
        id: "stepfun/step-3.5-flash:free",
        name: "Step 3.5 Flash",
        context_length: 128000,
        supports_tools: true,
        supports_tool_choice: false,
        source: "openrouter",
      },
      {
        id: "model/a",
        name: "Model A",
        context_length: 1000,
        supports_tools: true,
        supports_tool_choice: false,
        source: "openrouter",
      },
      {
        id: "model/b",
        name: "Model B",
        context_length: 2000,
        supports_tools: true,
        supports_tool_choice: false,
        source: "openrouter",
      },
      {
        id: "model/c",
        name: "Model C",
        context_length: 3000,
        supports_tools: true,
        supports_tool_choice: false,
        source: "openrouter",
      },
    ]);

    expect(ranked).toHaveLength(8);
    expect(ranked[0]?.id).toBe("openrouter/free");
    expect(ranked[1]?.id).toBe("arcee-ai/trinity-large-preview:free");
  });

  it("uses cache until TTL expires and serves stale snapshot on fetch failure", async () => {
    let now = 1_000_000;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        asJsonResponse({
          data: [
            {
              id: "openrouter/free",
              name: "OpenRouter Free",
              context_length: 128000,
              supported_parameters: ["tools"],
              pricing: { prompt: "0", completion: "0" },
            },
          ],
        })
      )
      .mockRejectedValueOnce(new Error("network down"));

    const service = new OpenRouterModelsService({
      fetchImpl: fetchMock as unknown as typeof fetch,
      now: () => now,
      ttlSeconds: 60,
    });

    const first = await service.listFreeModels();
    const second = await service.listFreeModels();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(second.models[0]?.id).toBe(first.models[0]?.id);

    now += 61_000;
    const stale = await service.listFreeModels();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(stale.models[0]?.id).toBe("openrouter/free");
  });

  it("recognizes free models only when both prompt and completion are zero strings", () => {
    expect(__private__.isTrulyFree({ prompt: "0", completion: "0" })).toBe(true);
    expect(__private__.isTrulyFree({ prompt: "0", completion: "0.000001" })).toBe(false);
    expect(__private__.isTrulyFree({ prompt: "0.0", completion: "0" })).toBe(false);
  });
});
