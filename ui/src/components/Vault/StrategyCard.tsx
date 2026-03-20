import { useState } from "react";
import { Link } from "react-router-dom";
import type { StrategySummary } from "../../api/client.ts";
import { downloadExport } from "../../api/client.ts";

// ---------------------------------------------------------------------------
// Badge helpers
// ---------------------------------------------------------------------------

const LIFECYCLE_BADGE: Record<string, string> = {
  validated:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400",
  production_standard:
    "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  production_aggressive:
    "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
  production_defensive:
    "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
};

const VARIANT_BADGE: Record<string, string> = {
  basic:
    "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  advanced:
    "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
};

function lifecycleLabel(status: string): string {
  return status.replace(/_/g, " ");
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  strategy: StrategySummary;
}

export function StrategyCard({ strategy }: Props) {
  const [downloading, setDownloading] = useState<"ctrader" | "pine" | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);

  async function handleDownload(format: "ctrader" | "pine") {
    setDownloading(format);
    setError(null);
    try {
      await downloadExport(strategy.id, format);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Download failed");
    } finally {
      setDownloading(null);
    }
  }

  const lifecycleBadge =
    LIFECYCLE_BADGE[strategy.lifecycle_status] ??
    "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400";

  const variantBadge =
    VARIANT_BADGE[strategy.variant] ??
    "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm flex flex-col gap-4 dark:border-gray-800 dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 dark:text-white truncate">
            <Link
              to={`/vault/${strategy.id}`}
              className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              {strategy.name}
            </Link>
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">
            {new Date(strategy.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span
            className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${lifecycleBadge}`}
          >
            {lifecycleLabel(strategy.lifecycle_status)}
          </span>
          <span
            className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${variantBadge}`}
          >
            {strategy.variant}
          </span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <p className="text-xs text-red-500 dark:text-red-400">{error}</p>
      )}

      {/* Export actions */}
      <div className="flex gap-2 mt-auto pt-2 border-t border-gray-100 dark:border-gray-800">
        <button
          onClick={() => handleDownload("ctrader")}
          disabled={downloading !== null}
          className="flex-1 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700 transition-colors"
        >
          {downloading === "ctrader" ? "..." : "↓ cTrader (.cs)"}
        </button>
        <button
          onClick={() => handleDownload("pine")}
          disabled={downloading !== null}
          className="flex-1 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700 transition-colors"
        >
          {downloading === "pine" ? "..." : "↓ Pine Script (.pine)"}
        </button>
      </div>
    </div>
  );
}
