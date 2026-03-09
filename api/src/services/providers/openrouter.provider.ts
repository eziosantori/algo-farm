import OpenAI from "openai";
import type { GenerateStrategyOptions, LLMProvider, ProviderId } from "./base.js";
import { SYSTEM_PROMPT, STRATEGY_TOOL_SCHEMA, validateWithRetry } from "./base.js";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";

const OPENROUTER_FALLBACK_MODEL = "openrouter/free";

export class OpenRouterProvider implements LLMProvider {
  readonly id: ProviderId = "openrouter";
  private readonly client: OpenAI;
  private readonly defaultModel: string;

  constructor(apiKey?: string) {
    this.client = new OpenAI({
      baseURL: "https://openrouter.ai/api/v1",
      apiKey: apiKey ?? process.env.OPENROUTER_API_KEY ?? "",
    });
    this.defaultModel = process.env.OPENROUTER_MODEL ?? OPENROUTER_FALLBACK_MODEL;
  }

  async generateStrategy(
    message: string,
    options?: GenerateStrategyOptions
  ): Promise<{ strategy: StrategyDefinition; explanation: string }> {
    const model = options?.model?.trim() || this.defaultModel;

    try {
      return await this.generateWithModel(message, model);
    } catch (primaryError) {
      if (model === OPENROUTER_FALLBACK_MODEL) {
        throw primaryError;
      }

      try {
        return await this.generateWithModel(message, OPENROUTER_FALLBACK_MODEL);
      } catch {
        throw primaryError;
      }
    }
  }

  private async generateWithModel(
    message: string,
    model: string
  ): Promise<{ strategy: StrategyDefinition; explanation: string }> {
    const rawArgs = await this.callOpenRouter(message, model);

    const strategy = await validateWithRetry(rawArgs, async (errorMsg) => {
      return this.callOpenRouter(
        message,
        model,
        `The previous strategy had validation errors: ${errorMsg}. Please fix them and call generate_strategy again.`
      );
    });

    return { strategy, explanation: "Strategy generated successfully." };
  }

  private async callOpenRouter(
    userMessage: string,
    model: string,
    followUpMessage?: string
  ): Promise<unknown> {
    const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: userMessage },
    ];

    if (followUpMessage) {
      messages.push({ role: "assistant", content: "I'll fix the validation errors." });
      messages.push({ role: "user", content: followUpMessage });
    }

    const response = await this.client.chat.completions.create({
      model,
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
