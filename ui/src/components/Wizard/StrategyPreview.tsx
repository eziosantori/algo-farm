import { useState } from "react";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";

interface Props {
  strategy: StrategyDefinition;
}

const CONDITION_LABEL: Record<string, string> = {
  ">": ">",
  "<": "<",
  ">=": "≥",
  "<=": "≤",
  "==": "=",
  "!=": "≠",
};

const INDICATOR_COLOR: Record<string, string> = {
  rsi: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  ema: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  sma: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  macd: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  atr: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  adx: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
  supertrend: "bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300",
  supertrend_direction:
    "bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300",
  bbands: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300",
};

function indicatorColor(type: string) {
  return (
    INDICATOR_COLOR[type] ??
    "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
  );
}

interface RuleDef {
  indicator: string;
  condition: string;
  value?: number | null;
  compare_to?: string | null;
}

function RuleRow({
  rule,
  kind,
}: {
  rule: RuleDef;
  kind: "entry" | "exit";
}) {
  const cond = CONDITION_LABEL[rule.condition] ?? rule.condition;
  const rhs = rule.compare_to ?? String(rule.value ?? "");
  const dot =
    kind === "entry"
      ? "bg-green-500"
      : "bg-red-500";

  return (
    <div className="flex items-center gap-2 text-sm py-1">
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dot}`} />
      <code className="font-mono text-gray-800 dark:text-gray-200">
        {rule.indicator}
      </code>
      <span className="text-gray-400 font-medium">{cond}</span>
      <code className="font-mono text-gray-800 dark:text-gray-200">{rhs}</code>
    </div>
  );
}

function Section({
  title,
  color,
  children,
}: {
  title: string;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-lg border px-4 py-3 ${color}`}
    >
      <p className="text-xs font-semibold uppercase tracking-wide mb-2 text-current opacity-70">
        {title}
      </p>
      {children}
    </div>
  );
}

export function StrategyPreview({ strategy }: Props) {
  const [showJson, setShowJson] = useState(false);

  const pm = strategy.position_management;
  const stats = [
    { label: "Size", value: `${(pm.size * 100).toFixed(1)}%` },
    { label: "Max trades", value: String(pm.max_open_trades) },
    { label: "SL", value: pm.sl_pips != null ? `${pm.sl_pips} pips` : "—" },
    { label: "TP", value: pm.tp_pips != null ? `${pm.tp_pips} pips` : "—" },
  ];

  return (
    <div className="mt-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/60">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">
            {strategy.name}
          </h3>
          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 uppercase tracking-wide">
            {strategy.variant}
          </span>
        </div>
        <button
          onClick={() => setShowJson((v) => !v)}
          className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
        >
          {showJson ? "Hide JSON" : "View JSON"}
        </button>
      </div>

      {showJson ? (
        <pre className="m-0 p-4 text-xs font-mono bg-gray-900 dark:bg-gray-950 text-gray-100 overflow-auto max-h-72">
          {JSON.stringify(strategy, null, 2)}
        </pre>
      ) : (
        <div className="p-4 grid gap-3">
          {/* Indicators */}
          <Section
            title={`Indicators (${strategy.indicators.length})`}
            color="border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40"
          >
            <div className="flex flex-wrap gap-2">
              {strategy.indicators.map((ind) => {
                const params = Object.entries(ind.params ?? {})
                  .map(([k, v]) => `${k}=${v}`)
                  .join(", ");
                return (
                  <span
                    key={ind.name}
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${indicatorColor(ind.type)}`}
                  >
                    <span className="font-semibold">{ind.name}</span>
                    <span className="opacity-60">
                      {ind.type}
                      {params ? ` · ${params}` : ""}
                    </span>
                  </span>
                );
              })}
            </div>
          </Section>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Entry rules */}
            <Section
              title={`Entry rules (${strategy.entry_rules.length})`}
              color="border-green-200 dark:border-green-800/50 bg-green-50 dark:bg-green-950/20"
            >
              {strategy.entry_rules.length === 0 ? (
                <p className="text-xs text-gray-400 italic">No entry rules</p>
              ) : (
                strategy.entry_rules.map((r, i) => (
                  <RuleRow key={i} rule={r} kind="entry" />
                ))
              )}
            </Section>

            {/* Exit rules */}
            <Section
              title={`Exit rules (${strategy.exit_rules.length})`}
              color="border-red-200 dark:border-red-800/50 bg-red-50 dark:bg-red-950/20"
            >
              {strategy.exit_rules.length === 0 ? (
                <p className="text-xs text-gray-400 italic">No exit rules</p>
              ) : (
                strategy.exit_rules.map((r, i) => (
                  <RuleRow key={i} rule={r} kind="exit" />
                ))
              )}
            </Section>
          </div>

          {/* Position management */}
          <Section
            title="Position management"
            color="border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40"
          >
            <div className="grid grid-cols-4 gap-3">
              {stats.map(({ label, value }) => (
                <div key={label} className="text-center">
                  <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
                  <p className="font-mono text-sm font-semibold text-gray-900 dark:text-white mt-0.5">
                    {value}
                  </p>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}
    </div>
  );
}
