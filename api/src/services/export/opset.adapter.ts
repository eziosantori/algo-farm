import type { ExportAdapter } from "./types.js";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";

// ---------------------------------------------------------------------------
// Helpers (must match ctrader.adapter naming conventions)
// ---------------------------------------------------------------------------

function toPascalCase(s: string): string {
  return s
    .split(/[_\s-]+/)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join("");
}

function toPropName(indicatorName: string, paramKey: string): string {
  return toPascalCase(indicatorName) + toPascalCase(paramKey);
}

// ---------------------------------------------------------------------------
// Timeframe mapping (AlgoFarm → cTrader Period format)
// ---------------------------------------------------------------------------

const TF_MAP: Record<string, string> = {
  M1: "m1", M5: "m5", M10: "m10", M15: "m15", M30: "m30",
  H1: "h1", H4: "h4", D1: "d1", W1: "w1",
};

function toCTraderPeriod(tf: string): string {
  return TF_MAP[tf] ?? tf.toLowerCase();
}

// ---------------------------------------------------------------------------
// Generate .cbotset JSON for a specific strategy (optionally per-pair)
// ---------------------------------------------------------------------------

export function generateOpsetJson(
  strategy: StrategyDefinition,
  instrument?: string,
  timeframe?: string,
): string {
  // Resolve per-pair overrides from strategy JSON
  const raw = strategy as Record<string, unknown>;
  const overridesAll = (raw["param_overrides"] ?? {}) as Record<
    string,
    Record<string, Record<string, unknown>>
  >;
  const pairOverrides: Record<string, unknown> =
    instrument && timeframe
      ? (overridesAll[instrument]?.[timeframe] ?? {})
      : {};

  const params: Record<string, string> = {};

  // Position management params
  const pm = strategy.position_management;
  params["RiskPct"] = String((pm.size ?? 0.02) * 100);
  if (pm.sl_pips != null) params["SlPips"] = String(pm.sl_pips);
  if (pm.tp_pips != null) params["TpPips"] = String(pm.tp_pips);
  if (pm.sl_atr_mult != null) params["SlAtrMult"] = String(pm.sl_atr_mult);
  if (pm.tp_atr_mult != null) params["TpAtrMult"] = String(pm.tp_atr_mult);

  // Per-indicator params — merge with pair overrides
  for (const ind of strategy.indicators) {
    const merged = { ...ind.params, ...pairOverrides };
    for (const [key, rawVal] of Object.entries(merged)) {
      if (key.startsWith("_")) continue;
      if (!(key in ind.params)) continue;
      if (typeof rawVal === "number" || typeof rawVal === "string" || typeof rawVal === "boolean") {
        params[toPropName(ind.name, key)] = String(rawVal);
      }
    }
  }

  // Entry/exit rule threshold values as parameters
  const allRules = [
    ...strategy.entry_rules,
    ...strategy.exit_rules,
    ...(strategy.entry_rules_short ?? []),
    ...(strategy.exit_rules_short ?? []),
  ];
  const thresholdSeen = new Set<string>();
  const thresholdCounts = new Map<string, number>();
  for (const rule of allRules) {
    if (rule.value != null && rule.compare_to == null) {
      const ruleKey = `${rule.indicator}|${rule.value}`;
      if (thresholdSeen.has(ruleKey)) continue;
      thresholdSeen.add(ruleKey);

      const indName = toPascalCase(rule.indicator);
      const count = thresholdCounts.get(rule.indicator) ?? 0;
      thresholdCounts.set(rule.indicator, count + 1);
      const suffix = count === 0 ? "" : String(count + 1);
      const propName = `${indName}Threshold${suffix}`;

      let effectiveValue: number = rule.value;
      const overrideKey = `_${rule.indicator.replace(/\d+$/, "")}_threshold`;
      if (overrideKey in pairOverrides) {
        effectiveValue = pairOverrides[overrideKey] as number;
      }

      params[propName] = String(effectiveValue);
    }
  }

  // Build cTrader JSON .cbotset format
  const cbotset: Record<string, unknown> = {
    Parameters: params,
  };

  // Include Chart section when instrument/timeframe are specified
  if (instrument && timeframe) {
    cbotset["Chart"] = {
      Symbol: instrument,
      Period: toCTraderPeriod(timeframe),
    };
  }

  return JSON.stringify(cbotset, null, 2);
}

// Keep the old name as alias for backward compat with routes
export const generateOpsetXml = generateOpsetJson;

// ---------------------------------------------------------------------------
// ExportAdapter implementation (global params, no per-pair)
// ---------------------------------------------------------------------------

export class OpsetAdapter implements ExportAdapter {
  readonly format = "opset" as const;
  readonly fileExtension = "cbotset";
  readonly mimeType = "application/json";

  generate(strategy: StrategyDefinition): string {
    return generateOpsetJson(strategy);
  }
}
