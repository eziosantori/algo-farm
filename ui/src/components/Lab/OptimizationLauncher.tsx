import { useState, useEffect } from "react";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";
import { api, type StrategySummary, type StrategyRecord } from "../../api/client.ts";
import { InstrumentMultiSelect } from "./InstrumentMultiSelect.tsx";
import { TimeframeSelect } from "./TimeframeSelect.tsx";
import { OptimizerConfig, type OptimizerSettings } from "./OptimizerConfig.tsx";

// ---------------------------------------------------------------------------
// Vault status filter (same as VaultPage)
// ---------------------------------------------------------------------------

const VAULT_STATUSES = new Set([
  "validated",
  "production_standard",
  "production_aggressive",
  "production_defensive",
]);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Props {
  /** Pre-selected strategy ID (e.g. from Vault "Optimize" button) */
  initialStrategyId?: string;
  /** Called after a session is launched with its ID */
  onLaunched: (sessionId: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function OptimizationLauncher({ initialStrategyId, onLaunched }: Props) {
  // Strategy picker
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [strategyId, setStrategyId] = useState<string>(initialStrategyId ?? "");
  const [strategyDef, setStrategyDef] = useState<StrategyDefinition | null>(null);
  const [loadingStrategies, setLoadingStrategies] = useState(true);

  // Selections
  const [instruments, setInstruments] = useState<string[]>([]);
  const [timeframes, setTimeframes] = useState<string[]>([]);
  const [optimizerSettings, setOptimizerSettings] = useState<OptimizerSettings>({
    optimizer: "bayesian",
    metric: "sharpe_ratio",
    nTrials: 50,
    populationSize: 20,
    fromDate: "",
    toDate: "",
  });

  // Launch state
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load vault strategies
  useEffect(() => {
    setLoadingStrategies(true);
    api.listStrategies()
      .then(({ strategies: all }) => {
        const vault = all.filter((s) => VAULT_STATUSES.has(s.lifecycle_status));
        setStrategies(vault);
        if (initialStrategyId && vault.some((s) => s.id === initialStrategyId)) {
          setStrategyId(initialStrategyId);
        }
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingStrategies(false));
  }, [initialStrategyId]);

  // Load strategy definition when selected
  useEffect(() => {
    if (!strategyId) {
      setStrategyDef(null);
      return;
    }
    api.getStrategy(strategyId)
      .then((rec: StrategyRecord) => setStrategyDef(rec.definition))
      .catch((e) => setError(String(e)));
  }, [strategyId]);

  // Validation
  const canLaunch =
    strategyId &&
    strategyDef &&
    instruments.length > 0 &&
    timeframes.length > 0 &&
    !launching;

  async function handleLaunch() {
    if (!canLaunch || !strategyDef) return;
    setLaunching(true);
    setError(null);

    try {
      // 1. Create session
      const { id: sessionId } = await api.createLabSession({
        strategy_name: strategyDef.name,
        strategy_json: JSON.stringify(strategyDef),
        instruments,
        timeframes,
        strategy_id: strategyId,
      });

      // 2. Run (enqueue BullMQ job)
      await api.runLabSession(sessionId, {
        optimizer: optimizerSettings.optimizer,
        optimize_metric: optimizerSettings.metric,
        ...(optimizerSettings.optimizer !== "grid" && {
          n_trials: optimizerSettings.nTrials,
        }),
        ...(optimizerSettings.optimizer === "genetic" && {
          population_size: optimizerSettings.populationSize,
        }),
        ...(optimizerSettings.fromDate && { from_date: optimizerSettings.fromDate }),
        ...(optimizerSettings.toDate && { to_date: optimizerSettings.toDate }),
      });

      onLaunched(sessionId);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLaunching(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* Strategy picker */}
      <div>
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
          Strategy
        </label>
        {loadingStrategies ? (
          <div className="text-xs text-gray-400">Loading strategies…</div>
        ) : strategies.length === 0 ? (
          <div className="text-xs text-gray-400">
            No validated/production strategies in the Vault.
          </div>
        ) : (
          <select
            value={strategyId}
            onChange={(e) => setStrategyId(e.target.value)}
            className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2.5 py-1.5 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Select a strategy…</option>
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} {s.variant !== "basic" ? `(${s.variant})` : ""} — {s.lifecycle_status.replace("_", " ")}
              </option>
            ))}
          </select>
        )}

        {/* Strategy summary */}
        {strategyDef && (
          <div className="mt-2 rounded-md border border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50 px-3 py-2 text-[11px] text-gray-500 dark:text-gray-400">
            <span className="font-medium text-gray-700 dark:text-gray-300">{strategyDef.name}</span>
            {" — "}
            {strategyDef.indicators.length} indicators,{" "}
            {strategyDef.entry_rules.length} entry rules,{" "}
            {strategyDef.exit_rules.length} exit rules
            {strategyDef.entry_rules_short && strategyDef.entry_rules_short.length > 0 && " (long+short)"}
          </div>
        )}
      </div>

      {/* Instruments */}
      <InstrumentMultiSelect selected={instruments} onChange={setInstruments} />

      {/* Timeframes */}
      <TimeframeSelect selected={timeframes} onChange={setTimeframes} />

      {/* Optimizer config */}
      <OptimizerConfig value={optimizerSettings} onChange={setOptimizerSettings} />

      {/* Error */}
      {error && (
        <div className="rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-xs text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Launch button */}
      <button
        type="button"
        disabled={!canLaunch}
        onClick={handleLaunch}
        className={`w-full rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
          canLaunch
            ? "bg-blue-600 hover:bg-blue-700 text-white"
            : "bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-600 cursor-not-allowed"
        }`}
      >
        {launching ? "Launching…" : "Launch Optimization"}
      </button>
    </div>
  );
}
