import type { ExportAdapter } from "./types.js";
import type {
  StrategyDefinition,
  IndicatorDef,
  RuleDef,
  IndicatorType,
} from "@algo-farm/shared/strategy";
import { getCTraderSpec } from "./indicator-map.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toPascalCase(s: string): string {
  return s
    .split(/[_\s-]+/)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join("");
}

function toFieldName(name: string): string {
  const p = toPascalCase(name);
  return `_${p.charAt(0).toLowerCase()}${p.slice(1)}`;
}

function toPropName(indicatorName: string, paramKey: string): string {
  return toPascalCase(indicatorName) + toPascalCase(paramKey);
}

function priceAccessor(name: string): string | null {
  const map: Record<string, string> = {
    close: "Bars.ClosePrices.LastValue",
    open: "Bars.OpenPrices.LastValue",
    high: "Bars.HighPrices.LastValue",
    low: "Bars.LowPrices.LastValue",
  };
  return map[name.toLowerCase()] ?? null;
}

// ---------------------------------------------------------------------------
// Adapter
// ---------------------------------------------------------------------------

export class CTraderAdapter implements ExportAdapter {
  readonly format = "ctrader" as const;
  readonly fileExtension = "cs";
  readonly mimeType = "text/plain";

  generate(strategy: StrategyDefinition): string {
    const indMap = new Map<string, IndicatorDef>();
    for (const ind of strategy.indicators) indMap.set(ind.name, ind);

    const allRules: RuleDef[] = [
      ...strategy.entry_rules,
      ...strategy.exit_rules,
      ...(strategy.entry_rules_short ?? []),
      ...(strategy.exit_rules_short ?? []),
    ];

    // Indicators used in cross conditions need a _prev field
    const crossInds = new Set<string>(
      allRules
        .filter(
          (r) =>
            r.condition === "crosses_above" || r.condition === "crosses_below"
        )
        .map((r) => r.indicator)
    );

    const pm = strategy.position_management;
    const className = toPascalCase(strategy.name);

    const paramLines: string[] = [];
    const fieldLines: string[] = [];
    const onStartLines: string[] = [];
    const prevFieldLines: string[] = [];
    const prevUpdateLines: string[] = [];

    // Risk/sizing params
    paramLines.push(
      `        [Parameter("Risk Percent", DefaultValue = ${(pm.size ?? 0.02) * 100}, MinValue = 0.1, MaxValue = 10.0)]`,
      `        public double RiskPct { get; set; }`
    );
    if (pm.sl_pips != null) {
      paramLines.push(
        `        [Parameter("Stop Loss Pips", DefaultValue = ${pm.sl_pips})]`,
        `        public double SlPips { get; set; }`
      );
    }
    if (pm.tp_pips != null) {
      paramLines.push(
        `        [Parameter("Take Profit Pips", DefaultValue = ${pm.tp_pips})]`,
        `        public double TpPips { get; set; }`
      );
    }
    if (pm.sl_atr_mult != null) {
      paramLines.push(
        `        [Parameter("SL ATR Multiplier", DefaultValue = ${pm.sl_atr_mult})]`,
        `        public double SlAtrMult { get; set; }`
      );
    }
    if (pm.tp_atr_mult != null) {
      paramLines.push(
        `        [Parameter("TP ATR Multiplier", DefaultValue = ${pm.tp_atr_mult})]`,
        `        public double TpAtrMult { get; set; }`
      );
    }

    // Per-indicator params, fields, and OnStart init
    for (const ind of strategy.indicators) {
      const spec = getCTraderSpec(ind.type as IndicatorType);
      const fieldName = toFieldName(ind.name);

      if (!spec) {
        fieldLines.push(
          `        // TODO: implement custom indicator '${ind.type}' (${ind.name})`
        );
        onStartLines.push(`            // TODO: initialize ${ind.name}`);
        if (crossInds.has(ind.name)) {
          const prevName = `_prev${toPascalCase(ind.name)}`;
          prevFieldLines.push(`        private double ${prevName};`);
          prevUpdateLines.push(
            `            // TODO: update ${prevName} for cross detection`
          );
        }
        continue;
      }

      fieldLines.push(`        private ${spec.fieldType} ${fieldName};`);

      const paramProps: Record<string, string> = {};
      for (const [key, val] of Object.entries(ind.params)) {
        if (
          typeof val === "number" ||
          typeof val === "string" ||
          typeof val === "boolean"
        ) {
          const propName = toPropName(ind.name, key);
          const csharpType =
            typeof val === "number"
              ? Number.isInteger(val)
                ? "int"
                : "double"
              : typeof val === "boolean"
                ? "bool"
                : "string";
          paramLines.push(
            `        [Parameter("${toPascalCase(ind.name)} ${toPascalCase(key)}", DefaultValue = ${String(val)})]`,
            `        public ${csharpType} ${propName} { get; set; }`
          );
          paramProps[key] = propName;
        }
      }

      onStartLines.push(
        `            ${fieldName} = ${spec.buildInit(fieldName, paramProps)};`
      );

      if (crossInds.has(ind.name)) {
        const prevName = `_prev${toPascalCase(ind.name)}`;
        prevFieldLines.push(`        private double ${prevName};`);
        prevUpdateLines.push(
          `            ${prevName} = ${fieldName}${spec.accessor};`
        );
      }
    }

    // Condition builder
    const getAccessor = (name: string): string => {
      const price = priceAccessor(name);
      if (price) return price;
      const ind = indMap.get(name);
      if (!ind) return `/* unknown indicator: ${name} */`;
      const spec = getCTraderSpec(ind.type as IndicatorType);
      if (!spec) return `/* TODO: ${name} */`;
      return `${toFieldName(name)}${spec.accessor}`;
    };

    const buildCondition = (rule: RuleDef): string => {
      const lhs = getAccessor(rule.indicator);
      const rhs =
        rule.compare_to != null
          ? getAccessor(rule.compare_to)
          : String(rule.value ?? 0);

      switch (rule.condition) {
        case ">":
          return `${lhs} > ${rhs}`;
        case "<":
          return `${lhs} < ${rhs}`;
        case ">=":
          return `${lhs} >= ${rhs}`;
        case "<=":
          return `${lhs} <= ${rhs}`;
        case "crosses_above": {
          const prev = `_prev${toPascalCase(rule.indicator)}`;
          return `${prev} < ${rhs} && ${lhs} >= ${rhs}`;
        }
        case "crosses_below": {
          const prev = `_prev${toPascalCase(rule.indicator)}`;
          return `${prev} > ${rhs} && ${lhs} <= ${rhs}`;
        }
        default:
          return `/* unknown condition: ${rule.condition as string} */`;
      }
    };

    const joinConditions = (rules: RuleDef[]): string => {
      if (rules.length === 0) return "false";
      if (rules.length === 1) return buildCondition(rules[0]!);
      return rules.map(buildCondition).join(" &&\n                ");
    };

    const longEntry = joinConditions(strategy.entry_rules);
    const longExit = joinConditions(strategy.exit_rules);
    const shortRules = strategy.entry_rules_short ?? [];
    const shortExitRules = strategy.exit_rules_short ?? [];
    const hasShort = shortRules.length > 0;

    const slExpr =
      pm.sl_pips != null
        ? "SlPips"
        : pm.sl_atr_mult != null
          ? `(double?)(_atr?.Result.LastValue * SlAtrMult / Symbol.PipSize)`
          : "null";
    const tpExpr =
      pm.tp_pips != null
        ? "TpPips"
        : pm.tp_atr_mult != null
          ? `(double?)(_atr?.Result.LastValue * TpAtrMult / Symbol.PipSize)`
          : "null";

    const onBarLines: string[] = [
      `            // Long entry`,
      `            if (Positions.Find("Long", SymbolName) == null)`,
      `            {`,
      `                if (${longEntry})`,
      `                {`,
      `                    var volume = Symbol.NormalizeVolumeInUnits(`,
      `                        Account.Balance * RiskPct / 100.0 / (${slExpr} ?? 20.0) / Symbol.PipValue);`,
      `                    ExecuteMarketOrder(TradeType.Buy, SymbolName, volume, "Long", ${slExpr}, ${tpExpr});`,
      `                }`,
      `            }`,
      `            // Long exit`,
      `            else`,
      `            {`,
      `                if (${longExit})`,
      `                    ClosePosition(Positions.Find("Long", SymbolName));`,
      `            }`,
    ];

    if (hasShort) {
      const shortEntry = joinConditions(shortRules);
      const shortExit = joinConditions(shortExitRules);
      onBarLines.push(
        `            // Short entry`,
        `            if (Positions.Find("Short", SymbolName) == null)`,
        `            {`,
        `                if (${shortEntry})`,
        `                {`,
        `                    var volume = Symbol.NormalizeVolumeInUnits(`,
        `                        Account.Balance * RiskPct / 100.0 / (${slExpr} ?? 20.0) / Symbol.PipValue);`,
        `                    ExecuteMarketOrder(TradeType.Sell, SymbolName, volume, "Short", ${slExpr}, ${tpExpr});`,
        `                }`,
        `            }`,
        `            // Short exit`,
        `            else`,
        `            {`,
        `                if (${shortExit})`,
        `                    ClosePosition(Positions.Find("Short", SymbolName));`,
        `            }`
      );
    }

    if (prevUpdateLines.length > 0) {
      onBarLines.push(`            // Update previous values for cross detection`);
      onBarLines.push(...prevUpdateLines);
    }

    return [
      `using System;`,
      `using cAlgo.API;`,
      `using cAlgo.API.Indicators;`,
      ``,
      `// Generated by AlgoFarm Export Engine`,
      `// Strategy: ${strategy.name} (${strategy.variant})`,
      `// WARNING: Review and test thoroughly before live trading`,
      ``,
      `namespace cAlgo.Robots`,
      `{`,
      `    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]`,
      `    public class ${className} : Robot`,
      `    {`,
      `        // Parameters`,
      ...paramLines,
      ``,
      `        // Indicator fields`,
      ...fieldLines,
      ...prevFieldLines,
      ``,
      `        protected override void OnStart()`,
      `        {`,
      ...onStartLines,
      `        }`,
      ``,
      `        protected override void OnBar()`,
      `        {`,
      ...onBarLines,
      `        }`,
      `    }`,
      `}`,
    ].join("\n");
  }
}
