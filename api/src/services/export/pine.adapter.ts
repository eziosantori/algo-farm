import type { ExportAdapter } from "./types.js";
import type {
  StrategyDefinition,
  IndicatorDef,
  RuleDef,
  IndicatorType,
} from "@algo-farm/shared/strategy";
import { getPineSpec } from "./indicator-map.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toCamelCase(s: string): string {
  const parts = s.split(/[_\s-]+/);
  return (
    parts[0]! +
    parts
      .slice(1)
      .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
      .join("")
  );
}

function toPineInputName(indName: string, paramKey: string): string {
  return toCamelCase(`${indName}_${paramKey}`);
}

function priceVar(name: string): string | null {
  const map: Record<string, string> = {
    close: "close",
    open: "open",
    high: "high",
    low: "low",
  };
  return map[name.toLowerCase()] ?? null;
}

// ---------------------------------------------------------------------------
// Adapter
// ---------------------------------------------------------------------------

export class PineAdapter implements ExportAdapter {
  readonly format = "pine" as const;
  readonly fileExtension = "pine";
  readonly mimeType = "text/plain";

  generate(strategy: StrategyDefinition): string {
    const indMap = new Map<string, IndicatorDef>();
    for (const ind of strategy.indicators) indMap.set(ind.name, ind);

    const pm = strategy.position_management;
    const defaultQty = (pm.size ?? 0.02) * 100;

    const inputLines: string[] = [];
    const indicatorLines: string[] = [];

    for (const ind of strategy.indicators) {
      const varName = toCamelCase(ind.name);
      const spec = getPineSpec(ind.type as IndicatorType);

      if (!spec) {
        indicatorLines.push(
          `// TODO: implement custom indicator '${ind.type}' (${ind.name})`,
          `${varName} = float(na)`
        );
        continue;
      }

      const inputNames: Record<string, string> = {};
      for (const [key, val] of Object.entries(ind.params)) {
        if (typeof val === "number") {
          const inputName = toPineInputName(ind.name, key);
          const inputFn = Number.isInteger(val) ? "input.int" : "input.float";
          inputLines.push(
            `${inputName} = ${inputFn}(${val}, "${toCamelCase(ind.name)} ${key}")`
          );
          inputNames[key] = inputName;
        }
      }

      indicatorLines.push(spec.buildDecl(varName, inputNames));
    }

    // Condition builder
    const getAccessor = (name: string): string => {
      const price = priceVar(name);
      if (price) return price;
      const ind = indMap.get(name);
      if (!ind) return `/* unknown: ${name} */`;
      const spec = getPineSpec(ind.type as IndicatorType);
      if (!spec) return `/* TODO: ${name} */`;
      return spec.accessor(toCamelCase(ind.name));
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
        case "crosses_above":
          return `ta.crossover(${lhs}, ${rhs})`;
        case "crosses_below":
          return `ta.crossunder(${lhs}, ${rhs})`;
        default:
          return `/* unknown condition: ${rule.condition as string} */`;
      }
    };

    const joinConditions = (rules: RuleDef[]): string => {
      if (rules.length === 0) return "false";
      if (rules.length === 1) return buildCondition(rules[0]!);
      return rules.map(buildCondition).join(" and\n     ");
    };

    const longCond = joinConditions(strategy.entry_rules);
    const longExit = joinConditions(strategy.exit_rules);
    const shortRules = strategy.entry_rules_short ?? [];
    const shortExitRules = strategy.exit_rules_short ?? [];
    const hasShort = shortRules.length > 0;

    const lines: string[] = [
      `//@version=5`,
      `strategy("${strategy.name}", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=${defaultQty})`,
      ``,
      `// Inputs`,
      ...inputLines,
      ``,
      `// Indicators`,
      ...indicatorLines,
      ``,
      `// Entry conditions`,
      `longCondition = ${longCond}`,
    ];

    if (hasShort) {
      lines.push(`shortCondition = ${joinConditions(shortRules)}`);
    }

    lines.push(``, `// Exit conditions`, `longExit = ${longExit}`);

    if (hasShort) {
      lines.push(`shortExit = ${joinConditions(shortExitRules)}`);
    }

    lines.push(``, `// Orders`, `if longCondition`, `    strategy.entry("Long", strategy.long)`);

    if (hasShort) {
      lines.push(`if shortCondition`, `    strategy.entry("Short", strategy.short)`);
    }

    lines.push(`if longExit`, `    strategy.close("Long")`);

    if (hasShort) {
      lines.push(`if shortExit`, `    strategy.close("Short")`);
    }

    return lines.join("\n");
  }
}
