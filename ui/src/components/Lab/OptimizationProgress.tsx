import { useEffect, useState } from "react";
import { useSessionProgress, type ProgressEvent } from "../../hooks/useSessionProgress.ts";
import { api, type BacktestMetrics } from "../../api/client.ts";

// ---------------------------------------------------------------------------
// Color helpers
// ---------------------------------------------------------------------------

function sharpeClass(v: number): string {
  if (v >= 1.0) return "text-emerald-600 dark:text-emerald-400";
  if (v >= 0.4) return "text-amber-600 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}

function ddClass(v: number): string {
  if (v >= -10) return "text-emerald-600 dark:text-emerald-400";
  if (v >= -20) return "text-amber-600 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}

function returnClass(v: number): string {
  if (v > 0) return "text-emerald-600 dark:text-emerald-400";
  return "text-red-500 dark:text-red-400";
}

// ---------------------------------------------------------------------------
// Result row type
// ---------------------------------------------------------------------------

interface ResultRow {
  instrument: string;
  timeframe: string;
  sharpe: number;
  return_pct: number;
  max_dd_pct: number;
  params_str: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  sessionId: string;
  onCompleted?: () => void;
}

export function OptimizationProgress({ sessionId, onCompleted }: Props) {
  const { events, isConnected, latestProgress, isComplete } = useSessionProgress(sessionId);
  const [results, setResults] = useState<ResultRow[]>([]);
  const [sortKey, setSortKey] = useState<"sharpe" | "return_pct">("sharpe");
  const [completedData, setCompletedData] = useState<{
    best_params?: Record<string, unknown>;
    best_metrics?: BacktestMetrics;
  } | null>(null);

  // Parse result events
  useEffect(() => {
    const resultEvents = events.filter(e => e.type === "result");
    const rows: ResultRow[] = resultEvents.map(e => ({
      instrument: e.instrument || "—",
      timeframe: e.timeframe || "—",
      sharpe: e.metrics?.sharpe_ratio ?? 0,
      return_pct: e.metrics?.total_return_pct ?? 0,
      max_dd_pct: e.metrics?.max_drawdown_pct ?? 0,
      params_str: e.params ? Object.entries(e.params).map(([k, v]) => `${k}=${v}`).join(", ") : "default",
    }));

    // Sort
    rows.sort((a, b) => {
      const aVal = sortKey === "sharpe" ? a.sharpe : a.return_pct;
      const bVal = sortKey === "sharpe" ? b.sharpe : b.return_pct;
      return bVal - aVal;
    });

    setResults(rows);
  }, [events, sortKey]);

  // Extract completed data from last event
  useEffect(() => {
    if (isComplete) {
      const lastEvent = events[events.length - 1];
      if (lastEvent?.type === "completed") {
        const completedEvent = lastEvent as any;
        setCompletedData({
          best_params: completedEvent.best_params,
          best_metrics: completedEvent.best_metrics,
        });
      }
      onCompleted?.();
    }
  }, [isComplete, events, onCompleted]);

  const progress = latestProgress?.pct ?? 0;
  const elapsedSec = latestProgress?.elapsed_seconds ?? 0;
  const current = latestProgress?.current;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          Optimization running…
        </h2>
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${
            isConnected
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-red-500 dark:text-red-400"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-emerald-500" : "bg-red-500"}`} />
            {isConnected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-900 dark:text-white">
            {progress}%
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {Math.floor(elapsedSec / 60)}m {Math.floor(elapsedSec % 60)}s elapsed
          </span>
        </div>
        <div className="h-3 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div
            className="h-3 rounded-full bg-blue-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Current task */}
      {current && (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 p-3">
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
            Current
          </p>
          <div className="flex items-center gap-2 text-sm">
            <span className="font-mono font-semibold text-gray-900 dark:text-white">
              {current.instrument} {current.timeframe}
            </span>
            <span className="text-gray-500 dark:text-gray-400">
              {current.iteration} / {current.total}
            </span>
          </div>
        </div>
      )}

      {/* Results table */}
      {results.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
              Results ({results.length})
            </p>
            <div className="flex gap-1">
              <button
                onClick={() => setSortKey("sharpe")}
                className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                  sortKey === "sharpe"
                    ? "bg-blue-500 text-white"
                    : "text-gray-500 dark:text-gray-400 hover:text-gray-700"
                }`}
              >
                Sharpe
              </button>
              <button
                onClick={() => setSortKey("return_pct")}
                className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                  sortKey === "return_pct"
                    ? "bg-blue-500 text-white"
                    : "text-gray-500 dark:text-gray-400 hover:text-gray-700"
                }`}
              >
                Return %
              </button>
            </div>
          </div>

          <div className="overflow-x-auto rounded-lg border border-gray-100 dark:border-gray-800">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50 dark:border-gray-800 dark:bg-gray-900/60">
                  <th className="px-2 py-1.5 text-left font-semibold uppercase tracking-wider text-gray-400">Instrument</th>
                  <th className="px-2 py-1.5 text-left font-semibold uppercase tracking-wider text-gray-400">TF</th>
                  <th className="px-2 py-1.5 text-left font-semibold uppercase tracking-wider text-gray-400">Sharpe</th>
                  <th className="px-2 py-1.5 text-left font-semibold uppercase tracking-wider text-gray-400">Return %</th>
                  <th className="px-2 py-1.5 text-left font-semibold uppercase tracking-wider text-gray-400">Max DD %</th>
                  <th className="px-2 py-1.5 text-left font-semibold uppercase tracking-wider text-gray-400">Params</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                {results.slice(0, 20).map((r, i) => (
                  <tr key={i} className="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
                    <td className="px-2 py-1.5 font-mono text-gray-900 dark:text-white">{r.instrument}</td>
                    <td className="px-2 py-1.5 font-mono text-gray-500 dark:text-gray-400">{r.timeframe}</td>
                    <td className={`px-2 py-1.5 font-mono font-semibold ${sharpeClass(r.sharpe)}`}>
                      {r.sharpe.toFixed(2)}
                    </td>
                    <td className={`px-2 py-1.5 font-mono font-semibold ${returnClass(r.return_pct)}`}>
                      {r.return_pct > 0 ? "+" : ""}{r.return_pct.toFixed(1)}%
                    </td>
                    <td className={`px-2 py-1.5 font-mono font-semibold ${ddClass(r.max_dd_pct)}`}>
                      {r.max_dd_pct.toFixed(1)}%
                    </td>
                    <td className="px-2 py-1.5 font-mono text-[9px] text-gray-600 dark:text-gray-400 truncate max-w-32">
                      {r.params_str}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {results.length > 20 && (
            <p className="text-xs text-gray-400 text-center">
              … and {results.length - 20} more (showing top 20)
            </p>
          )}
        </div>
      )}

      {/* Completed state */}
      {isComplete && completedData?.best_params && (
        <div className="rounded-lg border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50 dark:bg-emerald-950/20 p-4">
          <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-400 mb-2">
            ✓ Optimization complete
          </p>
          <div className="space-y-2 text-xs text-emerald-700 dark:text-emerald-400">
            <p><span className="font-medium">Best params:</span></p>
            <code className="block font-mono bg-emerald-100/50 dark:bg-emerald-900/30 rounded px-2 py-1 text-[10px] break-all">
              {JSON.stringify(completedData.best_params, null, 2)}
            </code>
          </div>
        </div>
      )}
    </div>
  );
}
