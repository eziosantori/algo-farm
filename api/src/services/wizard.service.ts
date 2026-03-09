import type { StrategyDefinition } from "@algo-farm/shared/strategy";
import type { LLMProvider, ProviderId } from "./providers/base.js";
import { ClaudeProvider } from "./providers/claude.provider.js";
import { GeminiProvider } from "./providers/gemini.provider.js";
import { OpenRouterProvider } from "./providers/openrouter.provider.js";

export interface WizardChatOptions {
  model?: string;
}

export class WizardService {
  async chat(
    message: string,
    providerId: ProviderId = "gemini",
    options?: WizardChatOptions
  ): Promise<{ strategy: StrategyDefinition; explanation: string }> {
    return this.getProvider(providerId).generateStrategy(message, options);
  }

  private getProvider(id: ProviderId): LLMProvider {
    switch (id) {
      case "claude":
        return new ClaudeProvider();
      case "gemini":
        return new GeminiProvider();
      case "openrouter":
        return new OpenRouterProvider();
    }
  }
}
