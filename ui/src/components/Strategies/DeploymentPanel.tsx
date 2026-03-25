import { useState, useEffect } from "react";
import { api, type DeploymentSummary, type DeploymentPairRow } from "../../api/client.ts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function oosRatioClass(ratio: number): string {
  if (ratio >= 0.75) return "text-emerald-600 dark:text-emerald-400 font-semibold";
  if (ratio >= 0.5)  return "text-amber-600 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}

function ParamsCell({ row }: { row: DeploymentPairRow }) {
  return (
    <span className="flex flex-wrap gap-1">
      {Object.entries(row.effective_params).map(([k, v]) => (
        <span
          key={k}
          title={row.overridden_keys.includes(k) ? `overrides global default` : "global default"}
          className={`text-xs font-mono px-1.5 py-0.5 rounded ${
            row.overridden_keys.includes(k)
              ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 font-semibold ring-1 ring-amber-300 dark:ring-amber-700"
              : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
          }`}
        >
          {k}={String(v)}
        </span>
      ))}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Sub-table (reused for passed + failed sections)
// ---------------------------------------------------------------------------

function PairTable({
  rows,
  globalParams,
  onCopy,
  copied,
  dimmed,
}: {
  rows: DeploymentPairRow[];
  globalParams: Record<string, unknown>;
  onCopy: (row: DeploymentPairRow) => void;
  copied: string | null;
  dimmed?: boolean;
}) {
  return (
    <div className={`overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700 ${dimmed ? "opacity-50" : ""}`}>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 dark:bg-gray-800/60 border-b border-gray-200 dark:border-gray-700">
            {["Pair", "TF", "Parameters", "IS Sharpe", "OOS Sharpe", "OOS/IS", ""].map((h) => (
              <th
                key={h}
                className={`text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 px-3 py-2 ${
                  h === "" || h === "Pair" || h === "TF" || h === "Parameters"
                    ? "text-left"
                    : "text-right"
                }`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const key = `${row.instrument}|${row.timeframe}`;
            return (
              <tr
                key={key}
                className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50/50 dark:hover:bg-gray-800/20"
              >
                <td className="px-3 py-2 font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">
                  {row.instrument}
                </td>
                <td className="px-3 py-2 font-mono text-gray-500 dark:text-gray-400">
                  {row.timeframe}
                </td>
                <td className="px-3 py-2">
                  <ParamsCell row={row} />
                </td>
                <td className="px-3 py-2 text-right font-mono text-gray-700 dark:text-gray-300">
                  {row.is_sharpe !== null ? row.is_sharpe.toFixed(2) : "—"}
                </td>
                <td className="px-3 py-2 text-right font-mono text-gray-700 dark:text-gray-300">
                  {row.oos_sharpe !== null ? row.oos_sharpe.toFixed(2) : "—"}
                </td>
                <td className="px-3 py-2 text-right font-mono">
                  {row.oos_is_ratio !== null ? (
                    <span className={oosRatioClass(row.oos_is_ratio)}>
                      {Math.round(row.oos_is_ratio * 100)}%
                    </span>
                  ) : "—"}
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => onCopy(row)}
                    className="text-xs text-blue-600 dark:text-blue-400 hover:underline whitespace-nowrap"
                    title={`Copy: ${Object.entries(row.effective_params).map(([k, v]) => `${k}=${v}`).join(", ")}`}
                  >
                    {copied === key ? "✓" : "Copy"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function DeploymentPanel({ strategyId }: { strategyId: string }) {
  const [data, setData] = useState<DeploymentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFailed, setShowFailed] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    api
      .getDeploymentSummary(strategyId)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [strategyId]);

  if (loading) {
    return (
      <div className="py-4 flex items-center gap-2 text-sm text-gray-400">
        <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
        </svg>
        Loading deployment parameters…
      </div>
    );
  }

  if (error) {
    return <p className="py-3 text-sm text-red-500 dark:text-red-400">{error}</p>;
  }

  if (!data) return null;

  const passed = data.pairs.filter((p) => p.passed_robustness);
  const failed = data.pairs.filter((p) => !p.passed_robustness);
  const hasOverrides = data.pairs.some((p) => p.overridden_keys.length > 0);

  function handleCopy(row: DeploymentPairRow) {
    const text = Object.entries(row.effective_params)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    void navigator.clipboard.writeText(text);
    const key = `${row.instrument}|${row.timeframe}`;
    setCopied(key);
    setTimeout(() => setCopied(null), 1500);
  }

  function handleExportJson() {
    // Export only the param_overrides delta (not full effective_params)
    const overrides: Record<string, Record<string, Record<string, unknown>>> = {};
    for (const row of data!.pairs) {
      if (row.overridden_keys.length === 0) continue;
      if (!overrides[row.instrument]) overrides[row.instrument] = {};
      overrides[row.instrument][row.timeframe] = Object.fromEntries(
        row.overridden_keys.map((k) => [k, row.effective_params[k]]),
      );
    }
    const json = JSON.stringify({ param_overrides: overrides }, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "param_overrides.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4 pt-1">
      {/* Global params + legend + export */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            Global params
          </span>
          {Object.entries(data.global_params).map(([k, v]) => (
            <span
              key={k}
              className="text-xs font-mono px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
            >
              {k}={String(v)}
            </span>
          ))}
          {Object.keys(data.global_params).length === 0 && (
            <span className="text-xs text-gray-400 italic">none</span>
          )}
          {hasOverrides && (
            <span className="text-xs text-amber-700 dark:text-amber-400 bg-amber-100 dark:bg-amber-900/30 px-1.5 py-0.5 rounded font-mono ring-1 ring-amber-300 dark:ring-amber-700">
              highlighted
            </span>
          )}
          {hasOverrides && (
            <span className="text-xs text-gray-400">= pair-specific override</span>
          )}
        </div>
        <button
          onClick={handleExportJson}
          disabled={!hasOverrides}
          className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
          title="Download param_overrides JSON — paste into strategy file"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
          </svg>
          Export JSON
        </button>
      </div>

      {/* Passed pairs */}
      {passed.length > 0 ? (
        <PairTable
          rows={passed}
          globalParams={data.global_params}
          onCopy={handleCopy}
          copied={copied}
        />
      ) : (
        <p className="text-sm text-gray-400 dark:text-gray-500 italic py-1">
          No pairs have passed the robustness gate yet.
          {data.pairs.length > 0 && " See failed pairs below."}
        </p>
      )}

      {/* Failed / not validated pairs (collapsible) */}
      {failed.length > 0 && (
        <div>
          <button
            onClick={() => setShowFailed((v) => !v)}
            className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
          >
            <svg
              className={`w-3 h-3 transition-transform ${showFailed ? "rotate-90" : ""}`}
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M7.293 4.707a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L10.586 9 7.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
            Failed / not validated ({failed.length} pair{failed.length !== 1 ? "s" : ""})
          </button>
          {showFailed && (
            <div className="mt-2">
              <PairTable
                rows={failed}
                globalParams={data.global_params}
                onCopy={handleCopy}
                copied={copied}
                dimmed
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
