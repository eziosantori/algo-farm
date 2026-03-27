import type { ExportAdapter } from "./types.js";
import type {
  StrategyDefinition,
  IndicatorDef,
  RuleDef,
  IndicatorType,
} from "@algo-farm/shared/strategy";
import { getCTraderSpec } from "./indicator-map.js";
import { generateStrategyPrinciples } from "./strategy-comment.js";

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
    const defaultLabel = strategy.name.toLowerCase().replace(/[^a-z0-9]+/g, "-");

    const paramLines: string[] = [];
    const fieldLines: string[] = [];
    const onStartLines: string[] = [];
    const prevFieldLines: string[] = [];
    const prevUpdateLines: string[] = [];

    // Label parameter (always first)
    paramLines.push(
      `        [Parameter("Label", DefaultValue = "${defaultLabel}")]`,
      `        public string Label { get; set; }`
    );

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

    // Extract entry/exit rule thresholds as C# parameters (for opset per-pair tuning)
    const thresholdProps = new Map<string, string>(); // "indicator|value" → C# property name
    const thresholdCounts = new Map<string, number>(); // indicator → count for disambiguation
    for (const rule of allRules) {
      if (rule.value != null && rule.compare_to == null) {
        const ruleKey = `${rule.indicator}|${rule.value}`;
        if (!thresholdProps.has(ruleKey)) {
          const indName = toPascalCase(rule.indicator);
          const count = thresholdCounts.get(rule.indicator) ?? 0;
          thresholdCounts.set(rule.indicator, count + 1);
          const suffix = count === 0 ? "" : String(count + 1);
          const propName = `${indName}Threshold${suffix}`;
          thresholdProps.set(ruleKey, propName);
          const csharpType = Number.isInteger(rule.value) ? "int" : "double";
          paramLines.push(
            `        [Parameter("${indName} Threshold${suffix ? " " + suffix : ""}", DefaultValue = ${rule.value})]`,
            `        public ${csharpType} ${propName} { get; set; }`
          );
        }
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
      const ruleKey = `${rule.indicator}|${rule.value}`;
      const rhs =
        rule.compare_to != null
          ? getAccessor(rule.compare_to)
          : thresholdProps.has(ruleKey)
            ? thresholdProps.get(ruleKey)!
            : String(rule.value ?? 0);

      switch (rule.condition) {
        case ">":  return `${lhs} > ${rhs}`;
        case "<":  return `${lhs} < ${rhs}`;
        case ">=": return `${lhs} >= ${rhs}`;
        case "<=": return `${lhs} <= ${rhs}`;
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
    const longExit  = joinConditions(strategy.exit_rules);
    const shortRules = strategy.entry_rules_short ?? [];
    const shortExitRules = strategy.exit_rules_short ?? [];
    const hasShort = shortRules.length > 0;

    // SL/TP pips expressions (precomputed before CalculateVolume call)
    const slPipsDecl =
      pm.sl_pips != null
        ? `double slPips = SlPips;`
        : pm.sl_atr_mult != null
          ? `double slPips = _atr != null ? _atr.Result.LastValue * SlAtrMult / Symbol.PipSize : 20.0;`
          : `double slPips = 20.0;`;

    const tpPipsDecl =
      pm.tp_pips != null
        ? `double? tpPips = TpPips;`
        : pm.tp_atr_mult != null
          ? `double? tpPips = _atr != null ? (double?)(_atr.Result.LastValue * TpAtrMult / Symbol.PipSize) : null;`
          : `double? tpPips = null;`;

    const onBarLines: string[] = [
      `            ${slPipsDecl}`,
      `            ${tpPipsDecl}`,
      ``,
      `            // Long entry`,
      `            if (Positions.Find(Label + "-long", SymbolName) == null)`,
      `            {`,
      `                if (${longEntry})`,
      `                {`,
      `                    ExecuteMarketOrder(TradeType.Buy, SymbolName, CalculateVolume(slPips), Label + "-long", slPips, tpPips);`,
      `                }`,
      `            }`,
      `            // Long exit`,
      `            else`,
      `            {`,
      `                if (${longExit})`,
      `                    ClosePosition(Positions.Find(Label + "-long", SymbolName));`,
      `            }`,
    ];

    if (hasShort) {
      const shortEntry = joinConditions(shortRules);
      const shortExit  = joinConditions(shortExitRules);
      onBarLines.push(
        `            // Short entry`,
        `            if (Positions.Find(Label + "-short", SymbolName) == null)`,
        `            {`,
        `                if (${shortEntry})`,
        `                {`,
        `                    ExecuteMarketOrder(TradeType.Sell, SymbolName, CalculateVolume(slPips), Label + "-short", slPips, tpPips);`,
        `                }`,
        `            }`,
        `            // Short exit`,
        `            else`,
        `            {`,
        `                if (${shortExit})`,
        `                    ClosePosition(Positions.Find(Label + "-short", SymbolName));`,
        `            }`
      );
    }

    if (prevUpdateLines.length > 0) {
      onBarLines.push(`            // Update previous values for cross detection`);
      onBarLines.push(...prevUpdateLines);
    }

    onBarLines.push(`            UpdateInfo();`);

    // Header: XML summary with strategy principles
    const xmlSummary = generateStrategyPrinciples(strategy, "cs");

    return [
      `using System;`,
      `using cAlgo.API;`,
      `using cAlgo.API.Indicators;`,
      ``,
      xmlSummary,
      `[Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None, AddIndicators = true)]`,
      `public class ${className} : Robot`,
      `{`,
      `    #region PARAMETRI`,
      ``,
      ...paramLines,
      ``,
      `    #endregion`,
      ``,
      `    // Indicator fields`,
      ...fieldLines,
      ...prevFieldLines,
      ``,
      `    // State`,
      `    private int _totalTrades = 0;`,
      `    private int _wins = 0;`,
      ``,
      `    protected override void OnStart()`,
      `    {`,
      `        Print($"=== ${className} | {Label} ===");`,
      `        Positions.Closed += OnPosClosed;`,
      ...onStartLines,
      `    }`,
      ``,
      `    protected override void OnBar()`,
      `    {`,
      ...onBarLines,
      `    }`,
      ``,
      `    private double CalculateVolume(double slPips)`,
      `    {`,
      `        double riskAmount = Account.Balance * (RiskPct / 100.0);`,
      `        double volume = riskAmount / (slPips * Symbol.PipValue);`,
      `        volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);`,
      `        volume = Math.Max(volume, Symbol.VolumeInUnitsMin);`,
      `        volume = Math.Min(volume, Symbol.VolumeInUnitsMax);`,
      `        return volume;`,
      `    }`,
      ``,
      `    private void OnPosClosed(PositionClosedEventArgs args)`,
      `    {`,
      `        if (!args.Position.Label.StartsWith(Label)) return;`,
      `        _totalTrades++;`,
      `        if (args.Position.NetProfit > 0) _wins++;`,
      `        Print($"CLOSED | P/L: {args.Position.NetProfit:F2} | Reason: {args.Reason}");`,
      `    }`,
      ``,
      `    private void UpdateInfo()`,
      `    {`,
      `        var pos = Positions.Find(Label + "-long", SymbolName)`,
      `            ?? Positions.Find(Label + "-short", SymbolName);`,
      `        if (pos == null) return;`,
      `        string info = $"${className} | {pos.TradeType} | P/L: {pos.NetProfit:F2}";`,
      `        Chart.DrawStaticText("hud", info, VerticalAlignment.Top, HorizontalAlignment.Right, Color.Yellow);`,
      `    }`,
      ``,
      `    protected override void OnStop()`,
      `    {`,
      `        double winRate = _totalTrades > 0 ? (_wins * 100.0 / _totalTrades) : 0;`,
      `        Print($"STOPPED | Trades: {_totalTrades} | Wins: {_wins} | WinRate: {winRate:F1}%");`,
      `    }`,
      `}`,
    ].join("\n");
  }
}
