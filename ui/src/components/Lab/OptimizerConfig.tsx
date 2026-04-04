export type OptimizerType = "grid" | "bayesian" | "genetic";

export const METRICS = [
  { value: "sharpe_ratio", label: "Sharpe Ratio" },
  { value: "profit_factor", label: "Profit Factor" },
  { value: "total_return_pct", label: "Total Return %" },
  { value: "max_drawdown_pct", label: "Max Drawdown %" },
  { value: "win_rate_pct", label: "Win Rate %" },
  { value: "sortino_ratio", label: "Sortino Ratio" },
  { value: "calmar_ratio", label: "Calmar Ratio" },
] as const;

export interface OptimizerSettings {
  optimizer: OptimizerType;
  metric: string;
  nTrials: number;
  populationSize: number;
  fromDate: string;
  toDate: string;
}

interface Props {
  value: OptimizerSettings;
  onChange: (v: OptimizerSettings) => void;
}

const OPTIMIZER_TABS: { key: OptimizerType; label: string; desc: string }[] = [
  { key: "grid", label: "Grid", desc: "Exhaustive sweep of all combinations" },
  { key: "bayesian", label: "Bayesian", desc: "Optuna TPE — smart sampling" },
  { key: "genetic", label: "Genetic", desc: "NSGA-II multi-objective with Pareto front" },
];

export function OptimizerConfig({ value, onChange }: Props) {
  function set<K extends keyof OptimizerSettings>(key: K, val: OptimizerSettings[K]) {
    onChange({ ...value, [key]: val });
  }

  return (
    <div className="space-y-3">
      {/* Optimizer type tabs */}
      <div>
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
          Optimizer
        </label>
        <div className="flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          {OPTIMIZER_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => set("optimizer", tab.key)}
              className={`flex-1 px-3 py-1.5 text-xs font-medium transition-colors ${
                value.optimizer === tab.key
                  ? "bg-blue-500 text-white"
                  : "bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
              title={tab.desc}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <p className="mt-1 text-[10px] text-gray-400 dark:text-gray-500">
          {OPTIMIZER_TABS.find((t) => t.key === value.optimizer)?.desc}
        </p>
      </div>

      {/* Optimizer-specific options */}
      {(value.optimizer === "bayesian" || value.optimizer === "genetic") && (
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-400 mb-0.5">
              Trials
            </label>
            <input
              type="number"
              min={10}
              max={10000}
              value={value.nTrials}
              onChange={(e) => set("nTrials", Number(e.target.value))}
              className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          {value.optimizer === "genetic" && (
            <div className="flex-1">
              <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-400 mb-0.5">
                Population size
              </label>
              <input
                type="number"
                min={4}
                max={200}
                value={value.populationSize}
                onChange={(e) => set("populationSize", Number(e.target.value))}
                className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          )}
        </div>
      )}

      {/* Metric selector */}
      <div>
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
          Optimize for
        </label>
        <select
          value={value.metric}
          onChange={(e) => set("metric", e.target.value)}
          className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2.5 py-1.5 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          {METRICS.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </div>

      {/* Date range */}
      <div className="flex gap-3">
        <div className="flex-1">
          <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-400 mb-0.5">
            From date <span className="text-gray-400">(optional)</span>
          </label>
          <input
            type="date"
            value={value.fromDate}
            onChange={(e) => set("fromDate", e.target.value)}
            className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div className="flex-1">
          <label className="block text-[10px] font-medium text-gray-500 dark:text-gray-400 mb-0.5">
            To date <span className="text-gray-400">(optional)</span>
          </label>
          <input
            type="date"
            value={value.toDate}
            onChange={(e) => set("toDate", e.target.value)}
            className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>
    </div>
  );
}
