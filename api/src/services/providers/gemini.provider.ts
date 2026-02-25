import { GoogleGenerativeAI, FunctionCallingMode, type FunctionDeclarationSchema } from "@google/generative-ai";
import { zodToJsonSchema } from "zod-to-json-schema";
import { StrategyDefinitionSchema } from "@algo-farm/shared/strategy";
import type { LLMProvider, ProviderId } from "./base.js";
import { SYSTEM_PROMPT, validateWithRetry } from "./base.js";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";

/**
 * Gemini's FunctionDeclarationSchema is a strict subset of JSON Schema.
 * Unsupported: $ref, $defs, $schema, additionalProperties, array type unions.
 * This function recursively strips them and normalizes nullable types.
 */
function sanitizeForGemini(schema: Record<string, unknown>): Record<string, unknown> {
  const SKIP_KEYS = new Set(["additionalProperties", "$schema", "$ref", "$defs"]);
  const result: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(schema)) {
    if (SKIP_KEYS.has(key)) continue;

    // type: ["string", "null"] → type: "string" + nullable: true
    if (key === "type" && Array.isArray(value)) {
      const nonNull = (value as string[]).filter((t) => t !== "null");
      result["type"] = nonNull[0] ?? "string";
      if ((value as string[]).includes("null")) result["nullable"] = true;
      continue;
    }

    if (value && typeof value === "object" && !Array.isArray(value)) {
      result[key] = sanitizeForGemini(value as Record<string, unknown>);
    } else if (Array.isArray(value)) {
      result[key] = value.map((item) =>
        item && typeof item === "object" ? sanitizeForGemini(item as Record<string, unknown>) : item
      );
    } else {
      result[key] = value;
    }
  }

  return result;
}

// Generate without $ref so all definitions are inlined — Gemini can't resolve $ref
const RAW_SCHEMA = zodToJsonSchema(StrategyDefinitionSchema, { $refStrategy: "none" }) as Record<string, unknown>;
const GEMINI_SCHEMA = sanitizeForGemini(RAW_SCHEMA);

export class GeminiProvider implements LLMProvider {
  readonly id: ProviderId = "gemini";
  private readonly genai: GoogleGenerativeAI;
  private readonly model: string;

  constructor(apiKey?: string) {
    this.genai = new GoogleGenerativeAI(apiKey ?? process.env.GEMINI_API_KEY ?? "");
    this.model = process.env.GEMINI_MODEL ?? "gemini-2.0-flash-lite";
  }

  async generateStrategy(message: string): Promise<{ strategy: StrategyDefinition; explanation: string }> {
    const rawArgs = await this.callGemini(message);

    const strategy = await validateWithRetry(rawArgs, async (errorMsg) => {
      return this.callGemini(
        message,
        `The previous strategy had validation errors: ${errorMsg}. Please fix them and call generate_strategy again.`
      );
    });

    return { strategy, explanation: "Strategy generated successfully." };
  }

  private async callGemini(userMessage: string, followUpMessage?: string): Promise<unknown> {
    const model = this.genai.getGenerativeModel({
      model: this.model,
      tools: [
        {
          functionDeclarations: [
            {
              name: "generate_strategy",
              description: "Generate a StrategyDefinition based on the user's description. Always call this tool.",
              parameters: GEMINI_SCHEMA as unknown as FunctionDeclarationSchema,
            },
          ],
        },
      ],
      toolConfig: { functionCallingConfig: { mode: FunctionCallingMode.ANY } },
    });

    const contents: Array<{ role: string; parts: Array<{ text: string }> }> = [
      { role: "user", parts: [{ text: userMessage }] },
    ];

    if (followUpMessage) {
      contents.push({ role: "model", parts: [{ text: "I'll fix the validation errors." }] });
      contents.push({ role: "user", parts: [{ text: followUpMessage }] });
    }

    const result = await model.generateContent({
      systemInstruction: SYSTEM_PROMPT,
      contents,
    });

    const call = result.response.functionCalls()?.[0];
    if (!call) {
      throw new Error("LLM_API_ERROR: Gemini did not return a function call");
    }

    return call.args;
  }
}
