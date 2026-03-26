import { z } from "zod";

export const IndicatorTypeSchema = z.enum([
  "sma",
  "ema",
  "macd",
  "rsi",
  "stoch",
  "atr",
  "atr_robust",
  "atr_gaussian",
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
  // Phase B — session indicators
  "session_active",
  "session_high",
  "session_low",
  "vwap",
  "vwap_upper",
  "vwap_lower",
  "anchored_vwap",
  "anchored_vwap_upper",
  "anchored_vwap_lower",
  // Phase B2 — fakeout indicators
  "range_fakeout_short",
  "range_fakeout_long",
  // Phase C / M8 — additional indicators
  "roc",
  "volume_sma",
  "htf_ema",
  "htf_sma",
  // Phase D — candlestick patterns
  "hammer",
  "shooting_star",
  "bullish_engulfing",
  "bearish_engulfing",
  "morning_star",
  "evening_star",
  "piercing_pattern",
  "dark_cloud_cover",
  "bullish_marubozu",
  "bearish_marubozu",
  "three_white_soldiers",
  "three_black_crows",
  "doji",
  "dragonfly_doji",
  "gravestone_doji",
  "spinning_top",
  "harami",
  "htf_pattern",
  // OHLCV primitives
  "close",
  "open",
  "high",
  "low",
  "volume",
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
  compare_to_multiplier: z.number().nullable().optional(),
  compare_to_offset: z.number().nullable().optional(),
});

export type RuleDef = z.infer<typeof RuleDefSchema>;

export const TradingHoursSchema = z.object({
  from_time: z.string().regex(/^\d{2}:\d{2}$/).default("00:00"),
  to_time: z.string().regex(/^\d{2}:\d{2}$/).default("23:59"),
  days: z.array(z.number().int().min(0).max(6)).nullable().optional(),
  force_close: z.boolean().default(false),
});

export type TradingHours = z.infer<typeof TradingHoursSchema>;

export const ScaleOutSchema = z.object({
  trigger_r: z.number().positive().default(1.5),
  volume_pct: z.number().int().min(1).max(99).default(50),
});

export type ScaleOut = z.infer<typeof ScaleOutSchema>;

export const EntryAnchoredVwapExitSchema = z.object({
  price_source: z.enum(["hlc3", "close"]).default("hlc3"),
});

export type EntryAnchoredVwapExit = z.infer<typeof EntryAnchoredVwapExitSchema>;

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
  trading_hours: TradingHoursSchema.nullable().optional(),
  entry_anchored_vwap_exit: EntryAnchoredVwapExitSchema.nullable().optional(),
  // Phase D — dynamic risk sizing
  risk_pct_min: z.number().positive().max(1).optional(),
  risk_pct_max: z.number().positive().max(1).optional(),
  risk_pct_group: z.string().optional(),
});

export type PositionManagement = z.infer<typeof PositionManagementSchema>;

// Phase D — advanced execution sub-schemas
export const SignalGateSchema = z.object({
  indicator: z.string(),
  active_for_bars: z.number().int().positive(),
});

export const SuppressionGateSchema = z.object({
  indicator: z.string(),
  suppress_for_bars: z.number().int().positive(),
  threshold: z.number().default(0.0),
});

export const TriggerHoldSchema = z.object({
  indicator: z.string(),
  hold_for_bars: z.number().int().positive(),
});

export const PatternGroupSchema = z.object({
  name: z.string(),
  patterns: z.array(z.string()),
  min_score: z.number().default(1.0),
});

export type SignalGate = z.infer<typeof SignalGateSchema>;
export type SuppressionGate = z.infer<typeof SuppressionGateSchema>;
export type TriggerHold = z.infer<typeof TriggerHoldSchema>;
export type PatternGroup = z.infer<typeof PatternGroupSchema>;

export const StrategyDefinitionSchema = z.object({
  version: z.string(),
  name: z.string(),
  variant: z.enum(["basic", "advanced"]),
  indicators: z.array(IndicatorDefSchema),
  entry_rules: z.array(RuleDefSchema),
  exit_rules: z.array(RuleDefSchema),
  position_management: PositionManagementSchema,
  // Phase C — short-side execution (optional; empty = long-only)
  entry_rules_short: z.array(RuleDefSchema).optional().default([]),
  exit_rules_short: z.array(RuleDefSchema).optional().default([]),
  // Phase D — advanced execution
  signal_gates: z.array(SignalGateSchema).optional().default([]),
  pattern_groups: z.array(PatternGroupSchema).optional().default([]),
  suppression_gates: z.array(SuppressionGateSchema).optional().default([]),
  trigger_holds: z.array(TriggerHoldSchema).optional().default([]),
  // Per-pair parameter overrides: { instrument: { timeframe: { key: value } } }
  param_overrides: z
    .record(z.record(z.record(z.unknown())))
    .optional()
    .default({}),
});

export type StrategyDefinition = z.infer<typeof StrategyDefinitionSchema>;
