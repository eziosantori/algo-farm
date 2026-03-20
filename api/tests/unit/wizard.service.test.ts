import { describe, it, expect, vi, beforeEach } from "vitest";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";
import type { LLMProvider, ProviderId } from "../../src/services/providers/base.js";

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
};

function makeProvider(
  id: ProviderId,
  result: { strategy: StrategyDefinition; explanation: string }
): LLMProvider {
  return {
    id,
    generateStrategy: vi.fn().mockResolvedValue(result),
  };
}

describe("WizardService", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("delegates to GeminiProvider by default", async () => {
    const mockProvider = makeProvider("gemini", { strategy: validStrategy, explanation: "Gemini result." });

    vi.doMock("../../src/services/providers/gemini.provider.js", () => ({
      GeminiProvider: vi.fn().mockImplementation(() => mockProvider),
    }));

    const { WizardService } = await import("../../src/services/wizard.service.js");
    const service = new WizardService();
    const result = await service.chat("Create an RSI strategy");

    expect(result.strategy.name).toBe("RSI Reversal");
    expect(result.explanation).toBe("Gemini result.");
    expect(mockProvider.generateStrategy).toHaveBeenCalledTimes(1);
    expect((mockProvider.generateStrategy as ReturnType<typeof vi.fn>).mock.calls[0]?.[0]).toBe(
      "Create an RSI strategy"
    );
  });

  it("delegates to ClaudeProvider when provider=claude", async () => {
    const mockProvider = makeProvider("claude", { strategy: validStrategy, explanation: "Claude result." });

    vi.doMock("../../src/services/providers/claude.provider.js", () => ({
      ClaudeProvider: vi.fn().mockImplementation(() => mockProvider),
    }));

    const { WizardService } = await import("../../src/services/wizard.service.js");
    const service = new WizardService();
    const result = await service.chat("Create a strategy", "claude");

    expect(result.strategy.name).toBe("RSI Reversal");
    expect(result.explanation).toBe("Claude result.");
    expect(mockProvider.generateStrategy).toHaveBeenCalledTimes(1);
    expect((mockProvider.generateStrategy as ReturnType<typeof vi.fn>).mock.calls[0]?.[0]).toBe(
      "Create a strategy"
    );
  });

  it("delegates to OpenRouterProvider when provider=openrouter", async () => {
    const mockProvider = makeProvider("openrouter", { strategy: validStrategy, explanation: "OpenRouter result." });

    vi.doMock("../../src/services/providers/openrouter.provider.js", () => ({
      OpenRouterProvider: vi.fn().mockImplementation(() => mockProvider),
    }));

    const { WizardService } = await import("../../src/services/wizard.service.js");
    const service = new WizardService();
    const result = await service.chat("Create a strategy", "openrouter", {
      model: "openrouter/free",
    });

    expect(result.strategy.name).toBe("RSI Reversal");
    expect(mockProvider.generateStrategy).toHaveBeenCalledWith("Create a strategy", {
      model: "openrouter/free",
    });
  });
});

describe("validateWithRetry", () => {
  it("returns parsed strategy when rawArgs are valid", async () => {
    const { validateWithRetry } = await import("../../src/services/providers/base.js");
    const result = await validateWithRetry(validStrategy, vi.fn());
    expect(result.name).toBe("RSI Reversal");
  });

  it("calls retryFn and returns strategy on second attempt", async () => {
    const { validateWithRetry } = await import("../../src/services/providers/base.js");

    const retryFn = vi.fn().mockResolvedValue(validStrategy);
    const result = await validateWithRetry({ name: "Bad" }, retryFn);

    expect(retryFn).toHaveBeenCalledOnce();
    expect(result.name).toBe("RSI Reversal");
  });

  it("throws ZodError when retry also returns invalid data", async () => {
    const { validateWithRetry } = await import("../../src/services/providers/base.js");

    const retryFn = vi.fn().mockResolvedValue({ name: "Still bad" });
    await expect(validateWithRetry({ name: "Bad" }, retryFn)).rejects.toThrow();
  });
});
