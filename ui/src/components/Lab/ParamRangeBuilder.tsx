import type { StrategyDefinition } from "@algo-farm/shared/strategy";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ParamMode = "range" | "list" | "fixed";

export interface ParamRange {
  key: string;
  label: string;
  currentValue: number;
  mode: ParamMode;
  min?: number;
  max?: number;
  step?: number;
  values?: number[];
  value?: number;
}

export interface ParamRangeState {
  [key: string]: ParamRange;
}

// ---------------------------------------------------------------------------
// Extract tunable params from strategy
// ---------------------------------------------------------------------------

export function extractTunableParams(def: StrategyDefinition): ParamRange[] {
  const params: ParamRange[] = [];

  // From indicators
  for (const ind of def.indicators) {
    for (const [key, value] of Object.entries(ind.params)) {
      if (typeof value === "number") {
        params.push({
          key: `${ind.name}.${key}`,
          label: `${ind.name} → ${key}`,
          currentValue: value,
          mode: "fixed",
          value,
        });
      }
    }
  }

  // From position_management (selected numeric fields)
  const pmFields = [
    "sl_pips", "tp_pips", "sl_atr_mult", "tp_atr_mult",
    "trailing_sl_atr_mult", "risk_pct", "time_exit_bars"
  ];
  for (const field of pmFields) {
    const val = def.position_management[field as keyof typeof def.position_management];
    if (typeof val === "number") {
      params.push({
        key: field,
        label: `Position → ${field}`,
        currentValue: val,
        mode: "fixed",
        value: val,
      });
    }
  }

  return params;
}

// ---------------------------------------------------------------------------
// Build param_grid for engine
// ---------------------------------------------------------------------------

export function buildParamGrid(ranges: ParamRangeState): Record<string, unknown> {
  const grid: Record<string, unknown> = {};

  for (const [_, range] of Object.entries(ranges)) {
    if (range.mode === "fixed") {
      grid[range.key] = range.value;
    } else if (range.mode === "range") {
      if (range.min !== undefined && range.max !== undefined && range.step !== undefined) {
        const values: number[] = [];
        for (let v = range.min; v <= range.max + 1e-9; v += range.step) {
          values.push(Math.round(v * 1e6) / 1e6);
        }
        grid[range.key] = values;
      }
    } else if (range.mode === "list") {
      if (range.values) {
        grid[range.key] = range.values;
      }
    }
  }

  return grid;
}

// ---------------------------------------------------------------------------
// Calculate combo count
// ---------------------------------------------------------------------------

export function calculateComboCount(
  ranges: ParamRangeState,
  instrumentCount: number,
  timeframeCount: number
): number {
  let product = 1;

  for (const range of Object.values(ranges)) {
    if (range.mode === "fixed") {
      // Fixed = 1 value
      product *= 1;
    } else if (range.mode === "range") {
      if (range.min !== undefined && range.max !== undefined && range.step !== undefined) {
        const count = Math.ceil((range.max - range.min) / range.step) + 1;
        product *= count;
      }
    } else if (range.mode === "list") {
      product *= range.values?.length ?? 0;
    }
  }

  return product * instrumentCount * timeframeCount;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  params: ParamRange[];
  ranges: ParamRangeState;
  onChange: (ranges: ParamRangeState) => void;
  instrumentCount: number;
  timeframeCount: number;
}

export function ParamRangeBuilder({
  params, ranges, onChange, instrumentCount, timeframeCount
}: Props) {
  function updateRange(key: string, updates: Partial<ParamRange>) {
    onChange({
      ...ranges,
      [key]: { ...ranges[key], ...updates }
    });
  }

  function setMode(key: string, mode: ParamMode) {
    const range = ranges[key];
    const updated: ParamRange = { ...range, mode };

    // Set sensible defaults for mode
    if (mode === "range") {
      updated.min = updated.currentValue;
      updated.max = updated.currentValue * 1.5;
      updated.step = 1;
    } else if (mode === "list") {
      updated.values = [updated.currentValue];
    } else if (mode === "fixed") {
      updated.value = updated.currentValue;
    }

    updateRange(key, updated);
  }

  const comboCount = calculateComboCount(ranges, instrumentCount, timeframeCount);
  const tooMany = comboCount > 10000;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400">
          Parameter ranges
        </label>
        {params.length === 0 && (
          <span className="text-[10px] text-amber-600 dark:text-amber-400">
            No tunable params found
          </span>
        )}
      </div>

      {params.length > 0 && (
        <div className="space-y-3 rounded-lg border border-gray-100 dark:border-gray-800 p-3 bg-gray-50/50 dark:bg-gray-900/30">
          {params.map((param) => {
            const range = ranges[param.key];
            if (!range) return null;

            return (
              <div key={param.key} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-gray-700 dark:text-gray-300">
                    {param.label}
                    <span className="ml-1 font-normal text-gray-400">
                      (current: {param.currentValue})
                    </span>
                  </label>
                  <div className="flex gap-0.5">
                    {(["fixed", "range", "list"] as const).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setMode(param.key, m)}
                        className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                          range.mode === m
                            ? "bg-blue-500 text-white"
                            : "bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-300 dark:hover:bg-gray-600"
                        }`}
                      >
                        {m === "fixed" ? "Fixed" : m === "range" ? "Range" : "List"}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Mode-specific inputs */}
                {range.mode === "fixed" && (
                  <div className="pl-2 text-[10px] text-gray-600 dark:text-gray-400">
                    Value: <span className="font-mono">{range.value}</span>
                  </div>
                )}

                {range.mode === "range" && (
                  <div className="pl-2 flex gap-2">
                    <div className="flex-1">
                      <label className="text-[10px] text-gray-500 dark:text-gray-400">min</label>
                      <input
                        type="number"
                        value={range.min ?? ""}
                        onChange={(e) => updateRange(param.key, { min: Number(e.target.value) })}
                        className="w-full rounded px-1.5 py-0.5 text-xs border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="text-[10px] text-gray-500 dark:text-gray-400">max</label>
                      <input
                        type="number"
                        value={range.max ?? ""}
                        onChange={(e) => updateRange(param.key, { max: Number(e.target.value) })}
                        className="w-full rounded px-1.5 py-0.5 text-xs border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="text-[10px] text-gray-500 dark:text-gray-400">step</label>
                      <input
                        type="number"
                        value={range.step ?? ""}
                        onChange={(e) => updateRange(param.key, { step: Number(e.target.value) })}
                        className="w-full rounded px-1.5 py-0.5 text-xs border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900"
                      />
                    </div>
                  </div>
                )}

                {range.mode === "list" && (
                  <div className="pl-2">
                    <input
                      type="text"
                      placeholder="comma-separated values (e.g. 7,10,14,21,28)"
                      value={range.values?.join(",") ?? ""}
                      onChange={(e) => {
                        const vals = e.target.value
                          .split(",")
                          .map(s => parseFloat(s.trim()))
                          .filter(v => !isNaN(v));
                        updateRange(param.key, { values: vals });
                      }}
                      className="w-full rounded px-1.5 py-1 text-xs border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 placeholder:text-gray-400"
                    />
                  </div>
                )}

                {/* Preview */}
                {range.mode !== "fixed" && (
                  <div className="pl-2 text-[10px] text-gray-500 dark:text-gray-400">
                    {range.mode === "range" && range.min !== undefined && range.max !== undefined && range.step !== undefined
                      ? `→ ${Math.ceil((range.max - range.min) / range.step) + 1} values`
                      : range.mode === "list"
                        ? `→ ${range.values?.length ?? 0} values`
                        : ""}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Combo counter */}
      {params.length > 0 && (
        <div className={`rounded-lg border p-2.5 text-xs ${
          tooMany
            ? "border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400"
            : "border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/30 text-gray-600 dark:text-gray-400"
        }`}>
          <div className="font-mono font-semibold">
            {comboCount.toLocaleString()} combinations
          </div>
          <div className="text-[10px] mt-0.5">
            = {params.filter(p => ranges[p.key]?.mode !== "fixed").length} params
            × {instrumentCount} instruments
            × {timeframeCount} timeframes
          </div>
          {tooMany && (
            <div className="mt-1 font-medium">
              ⚠ Grid will be slow. Consider Bayesian or Genetic.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
