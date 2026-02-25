import Anthropic from "@anthropic-ai/sdk";
import type { LLMProvider, ProviderId } from "./base.js";
import { SYSTEM_PROMPT, STRATEGY_TOOL_SCHEMA, validateWithRetry } from "./base.js";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";

export class ClaudeProvider implements LLMProvider {
  readonly id: ProviderId = "claude";
  private readonly client: Anthropic;

  constructor(apiKey?: string) {
    this.client = new Anthropic({ apiKey: apiKey ?? process.env.ANTHROPIC_API_KEY });
  }

  async generateStrategy(message: string): Promise<{ strategy: StrategyDefinition; explanation: string }> {
    const response = await this.callClaude(message);
    const toolUse = this.extractToolUse(response);

    const strategy = await validateWithRetry(toolUse.input, async (errorMsg) => {
      const retryResponse = await this.callClaude(
        message,
        `The previous strategy had validation errors: ${errorMsg}. Please fix them and call generate_strategy again.`
      );
      return this.extractToolUse(retryResponse).input;
    });

    const explanation = this.extractExplanation(response);
    return { strategy, explanation };
  }

  private async callClaude(userMessage: string, followUpMessage?: string): Promise<Anthropic.Message> {
    const messages: Anthropic.MessageParam[] = [{ role: "user", content: userMessage }];

    if (followUpMessage) {
      messages.push({ role: "assistant", content: "I'll fix the validation errors." });
      messages.push({ role: "user", content: followUpMessage });
    }

    return this.client.messages.create({
      model: "claude-sonnet-4-6",
      max_tokens: 2000,
      system: SYSTEM_PROMPT,
      messages,
      tools: [
        {
          name: "generate_strategy",
          description: "Generate a StrategyDefinition based on the user's description. Always call this tool.",
          input_schema: STRATEGY_TOOL_SCHEMA as Anthropic.Tool["input_schema"],
        },
      ],
      tool_choice: { type: "any" },
    });
  }

  private extractToolUse(response: Anthropic.Message): Anthropic.ToolUseBlock {
    const toolBlock = response.content.find(
      (block): block is Anthropic.ToolUseBlock => block.type === "tool_use"
    );
    if (!toolBlock) {
      throw new Error("LLM_API_ERROR: Claude did not return a tool_use block");
    }
    return toolBlock;
  }

  private extractExplanation(response: Anthropic.Message): string {
    const textBlock = response.content.find(
      (block): block is Anthropic.TextBlock => block.type === "text"
    );
    return textBlock?.text ?? "Strategy generated successfully.";
  }
}
