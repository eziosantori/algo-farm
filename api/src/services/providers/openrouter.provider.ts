import OpenAI from "openai";
import type { LLMProvider, ProviderId } from "./base.js";
import { SYSTEM_PROMPT, STRATEGY_TOOL_SCHEMA, validateWithRetry } from "./base.js";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";

export class OpenRouterProvider implements LLMProvider {
  readonly id: ProviderId = "openrouter";
  private readonly client: OpenAI;
  private readonly model: string;

  constructor(apiKey?: string) {
    this.client = new OpenAI({
      baseURL: "https://openrouter.ai/api/v1",
      apiKey: apiKey ?? process.env.OPENROUTER_API_KEY ?? "",
    });
    this.model = process.env.OPENROUTER_MODEL ?? "upstage/solar-pro-3:free";
  }

  async generateStrategy(message: string): Promise<{ strategy: StrategyDefinition; explanation: string }> {
    const rawArgs = await this.callOpenRouter(message);

    const strategy = await validateWithRetry(rawArgs, async (errorMsg) => {
      return this.callOpenRouter(
        message,
        `The previous strategy had validation errors: ${errorMsg}. Please fix them and call generate_strategy again.`
      );
    });

    return { strategy, explanation: "Strategy generated successfully." };
  }

  private async callOpenRouter(userMessage: string, followUpMessage?: string): Promise<unknown> {
    const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: userMessage },
    ];

    if (followUpMessage) {
      messages.push({ role: "assistant", content: "I'll fix the validation errors." });
      messages.push({ role: "user", content: followUpMessage });
    }

    const response = await this.client.chat.completions.create({
      model: this.model,
      messages,
      tools: [
        {
          type: "function",
          function: {
            name: "generate_strategy",
            description: "Generate a StrategyDefinition based on the user's description. Always call this tool.",
            parameters: STRATEGY_TOOL_SCHEMA,
          },
        },
      ],
      tool_choice: { type: "function", function: { name: "generate_strategy" } },
    });

    const toolCall = response.choices[0]?.message.tool_calls?.[0];
    if (!toolCall) {
      throw new Error("LLM_API_ERROR: OpenRouter did not return a tool call");
    }

    return JSON.parse(toolCall.function.arguments) as unknown;
  }
}
