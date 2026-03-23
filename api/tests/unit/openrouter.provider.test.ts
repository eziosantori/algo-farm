import { describe, it, expect, vi } from "vitest";
import { OpenRouterProvider } from "../../src/services/providers/openrouter.provider.js";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";

const validStrategy: StrategyDefinition = {
  version: "1.0",
  name: "RSI Reversal",
  variant: "basic",
  indicators: [{ name: "rsi14", type: "rsi", params: { period: 14 } }],
  entry_rules: [{ indicator: "rsi14", condition: "<", value: 30 }],
  exit_rules: [{ indicator: "rsi14", condition: ">", value: 70 }],
  position_management: { size: 0.02, max_open_trades: 1, trailing_sl_atr_mult: 2.0 },
  entry_rules_short: [],
  exit_rules_short: [],
  signal_gates: [],
  pattern_groups: [],
  suppression_gates: [],
  trigger_holds: [],
};

describe("OpenRouterProvider", () => {
  it("uses the requested model override", async () => {
    const provider = new OpenRouterProvider("test-key");
    const callSpy = vi
      .fn()
      .mockResolvedValue(validStrategy);

    (provider as unknown as { callOpenRouter: typeof callSpy }).callOpenRouter = callSpy;

    const result = await provider.generateStrategy("create strategy", {
      model: "qwen/qwen3-coder:free",
    });

    expect(result.strategy.name).toBe("RSI Reversal");
    expect(callSpy).toHaveBeenCalledWith("create strategy", "qwen/qwen3-coder:free");
  });

  it("falls back to openrouter/free when requested model fails", async () => {
    const provider = new OpenRouterProvider("test-key");
    const callSpy = vi.fn().mockImplementation((_message: string, model: string) => {
      if (model === "openrouter/free") {
        return Promise.resolve(validStrategy);
      }
      return Promise.reject(new Error("LLM_API_ERROR: requested model failed"));
    });

    (provider as unknown as { callOpenRouter: typeof callSpy }).callOpenRouter = callSpy;

    const result = await provider.generateStrategy("create strategy", {
      model: "broken/model:free",
    });

    expect(result.strategy.name).toBe("RSI Reversal");
    expect(callSpy.mock.calls.map((c) => c[1])).toEqual([
      "broken/model:free",
      "openrouter/free",
    ]);
  });
});
