import { zodToJsonSchema } from "zod-to-json-schema";
import {
  StrategyDefinitionSchema,
  type StrategyDefinition,
} from "@algo-farm/shared/strategy";

export type ProviderId = "claude" | "gemini" | "openrouter";
export interface GenerateStrategyOptions {
  model?: string;
}

export interface LLMProvider {
  readonly id: ProviderId;
  generateStrategy(
    message: string,
    options?: GenerateStrategyOptions
  ): Promise<{ strategy: StrategyDefinition; explanation: string }>;
}

export const SYSTEM_PROMPT = `You are an algorithmic trading strategy generator for the Algo Farm platform.

When the user describes a trading strategy, you MUST call the generate_strategy tool with a valid StrategyDefinition.

Supported indicator types: sma, ema, macd, rsi, stoch, atr, bollinger_bands, momentum, adx, cci, obv, williamsr, roc, volume_sma, supertrend, supertrend_direction, session_active, session_high, session_low, vwap, vwap_upper, vwap_lower, anchored_vwap, anchored_vwap_upper, anchored_vwap_lower, ichimoku_tenkan, ichimoku_kijun, ichimoku_senkou_a, ichimoku_senkou_b, ichimoku_chikou, close, open, high, low, volume

Supported rule conditions: >, <, >=, <=, crosses_above, crosses_below

Rules reference indicators by their "name" field. Each rule must have either a numeric "value" or a "compare_to" referencing another indicator name.

Example StrategyDefinition:
{
  "version": "1.0",
  "name": "RSI Reversal",
  "variant": "basic",
  "indicators": [
    { "name": "rsi14", "type": "rsi", "params": { "period": 14 } }
  ],
  "entry_rules": [
    { "indicator": "rsi14", "condition": "<", "value": 30 }
  ],
  "exit_rules": [
    { "indicator": "rsi14", "condition": ">", "value": 70 }
  ],
  "position_management": {
    "size": 0.02,
    "sl_pips": 20,
    "tp_pips": 40,
    "max_open_trades": 1
  }
}

Always set version to "1.0". Use "basic" variant unless the strategy uses multiple complex indicators.`;

export const STRATEGY_TOOL_SCHEMA = zodToJsonSchema(StrategyDefinitionSchema) as Record<string, unknown>;

/**
 * Validates raw tool-call arguments against StrategyDefinitionSchema.
 * On failure, calls retryFn with the error message and validates again (throws on second failure).
 */
export async function validateWithRetry(
  rawArgs: unknown,
  retryFn: (errorMsg: string) => Promise<unknown>
): Promise<StrategyDefinition> {
  const parsed = StrategyDefinitionSchema.safeParse(rawArgs);

  if (parsed.success) {
    return parsed.data;
  }

  const errorMsg = parsed.error.errors
    .map((e) => `${e.path.join(".")}: ${e.message}`)
    .join("; ");

  const retryArgs = await retryFn(errorMsg);
  return StrategyDefinitionSchema.parse(retryArgs);
}
