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

function xmlType(val: unknown): string {
  if (typeof val === "number") return Number.isInteger(val) ? "Int32" : "Double";
  if (typeof val === "boolean") return "Boolean";
  return "String";
}

function xmlEscape(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------------------
// Generate opset XML for a specific strategy (optionally with per-pair overrides)
// ---------------------------------------------------------------------------

export function generateOpsetXml(
  strategy: StrategyDefinition,
  instrument?: string,
  timeframe?: string,
): string {
  // Resolve per-pair overrides from strategy JSON (may exist even if not in Zod schema)
  const raw = strategy as Record<string, unknown>;
  const overridesAll = (raw["param_overrides"] ?? {}) as Record<
    string,
    Record<string, Record<string, unknown>>
  >;
  const pairOverrides: Record<string, unknown> =
    instrument && timeframe
      ? (overridesAll[instrument]?.[timeframe] ?? {})
      : {};

  const params: Array<{ name: string; type: string; value: string }> = [];

  // Position management params
  const pm = strategy.position_management;
  params.push({ name: "RiskPct", type: "Double", value: String((pm.size ?? 0.02) * 100) });
  if (pm.sl_pips != null) params.push({ name: "SlPips", type: "Double", value: String(pm.sl_pips) });
  if (pm.tp_pips != null) params.push({ name: "TpPips", type: "Double", value: String(pm.tp_pips) });
  if (pm.sl_atr_mult != null) params.push({ name: "SlAtrMult", type: "Double", value: String(pm.sl_atr_mult) });
  if (pm.tp_atr_mult != null) params.push({ name: "TpAtrMult", type: "Double", value: String(pm.tp_atr_mult) });

  // Per-indicator params — merge with pair overrides
  for (const ind of strategy.indicators) {
    const merged = { ...ind.params, ...pairOverrides };
    for (const [key, rawVal] of Object.entries(merged)) {
      // Skip private override keys (start with _)
      if (key.startsWith("_")) continue;
      // Only include params that exist in this indicator's original definition
      if (!(key in ind.params)) continue;
      const val = rawVal;
      if (typeof val === "number" || typeof val === "string" || typeof val === "boolean") {
        params.push({
          name: toPropName(ind.name, key),
          type: xmlType(val),
          value: String(val),
        });
      }
    }
  }

  // Entry/exit rule threshold values as parameters
  // Matches the cTrader adapter naming: unique (indicator, value) → ThresholdN
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
      // Apply pair-specific threshold override (e.g. _adx_threshold → adx threshold)
      const overrideKey = `_${rule.indicator.replace(/\d+$/, "")}_threshold`;
      if (overrideKey in pairOverrides) {
        effectiveValue = pairOverrides[overrideKey] as number;
      }

      params.push({
        name: propName,
        type: xmlType(effectiveValue),
        value: String(effectiveValue),
      });
    }
  }

  const pairLabel =
    instrument && timeframe ? ` (${instrument} ${timeframe})` : "";

  const lines = [
    `<?xml version="1.0" encoding="utf-8"?>`,
    `<!-- AlgoFarm Parameter Preset: ${xmlEscape(strategy.name)}${pairLabel} -->`,
    `<ParameterSet>`,
    `  <Parameters>`,
    ...params.map(
      (p) =>
        `    <Parameter Name="${xmlEscape(p.name)}" Type="${p.type}">${xmlEscape(p.value)}</Parameter>`
    ),
    `  </Parameters>`,
    `</ParameterSet>`,
  ];

  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// ExportAdapter implementation (global params, no per-pair)
// ---------------------------------------------------------------------------

export class OpsetAdapter implements ExportAdapter {
  readonly format = "opset" as const;
  readonly fileExtension = "cbotset";
  readonly mimeType = "application/xml";

  generate(strategy: StrategyDefinition): string {
    return generateOpsetXml(strategy);
  }
}
