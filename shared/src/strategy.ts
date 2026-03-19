import { z } from "zod";

export const IndicatorTypeSchema = z.enum([
  "sma",
  "ema",
  "macd",
  "rsi",
  "stoch",
  "atr",
  "bollinger_bands",
  "bollinger_upper",
  "bollinger_lower",
  "bollinger_basis",
  "momentum",
  "adx",
  "cci",
  "obv",
  "williamsr",
  "supertrend",
  "supertrend_direction",
]);

export type IndicatorType = z.infer<typeof IndicatorTypeSchema>;

export const RuleConditionSchema = z.enum([
  ">",
  "<",
  ">=",
  "<=",
  "crosses_above",
  "crosses_below",
]);

export type RuleCondition = z.infer<typeof RuleConditionSchema>;

export const IndicatorDefSchema = z.object({
  name: z.string(),
  type: IndicatorTypeSchema,
  params: z.record(z.unknown()),
});

export type IndicatorDef = z.infer<typeof IndicatorDefSchema>;

export const RuleDefSchema = z.object({
  indicator: z.string(),
  condition: RuleConditionSchema,
  value: z.number().nullable().optional(),
  compare_to: z.string().nullable().optional(),
});

export type RuleDef = z.infer<typeof RuleDefSchema>;

export const ScaleOutSchema = z.object({
  trigger_r: z.number().positive().default(1.5),
  volume_pct: z.number().int().min(1).max(99).default(50),
});

export type ScaleOut = z.infer<typeof ScaleOutSchema>;

export const PositionManagementSchema = z.object({
  size: z.number().default(0.02),
  sl_pips: z.number().nullable().optional(),
  tp_pips: z.number().nullable().optional(),
  max_open_trades: z.number().int().default(1),
  // M9 — Advanced Position Management
  risk_pct: z.number().positive().max(1).nullable().optional(),
  sl_atr_mult: z.number().positive().nullable().optional(),
  tp_atr_mult: z.number().positive().nullable().optional(),
  trailing_sl: z.enum(["atr", "supertrend"]).nullable().optional(),
  trailing_sl_atr_mult: z.number().positive().default(2.0),
  scale_out: ScaleOutSchema.nullable().optional(),
  time_exit_bars: z.number().int().positive().nullable().optional(),
});

export type PositionManagement = z.infer<typeof PositionManagementSchema>;

export const StrategyDefinitionSchema = z.object({
  version: z.string(),
  name: z.string(),
  variant: z.enum(["basic", "advanced"]),
  indicators: z.array(IndicatorDefSchema),
  entry_rules: z.array(RuleDefSchema),
  exit_rules: z.array(RuleDefSchema),
  position_management: PositionManagementSchema,
});

export type StrategyDefinition = z.infer<typeof StrategyDefinitionSchema>;
