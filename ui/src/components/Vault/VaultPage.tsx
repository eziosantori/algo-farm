import { useState, useEffect } from "react";
import { api, type StrategySummary } from "../../api/client.ts";
import { StrategyCard } from "./StrategyCard.tsx";

const VAULT_STATUSES = new Set([
  "validated",
  "production_standard",
  "production_aggressive",
  "production_defensive",
]);

export function VaultPage() {
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listStrategies()
      .then(({ strategies: all }) => {
        setStrategies(
          all
            .filter((s) => VAULT_STATUSES.has(s.lifecycle_status))
            .sort(
              (a, b) =>
                new Date(b.created_at).getTime() -
                new Date(a.created_at).getTime()
            )
        );
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Strategy Vault
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Validated and production-ready strategies. Download as cTrader C# or
          Pine Script v5.
        </p>
      </div>

      {/* Loading */}
      {loading && (
        <div className="py-16 text-center text-sm text-gray-400">
          Loading strategies…
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && strategies.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-200 py-20 dark:border-gray-800">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            No production-ready strategies yet.
          </p>
          <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
            Run <code className="font-mono">/workflow-orchestrator</code> to
            develop and validate one.
          </p>
        </div>
      )}

      {/* Strategy grid */}
      {!loading && strategies.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {strategies.map((s) => (
            <StrategyCard key={s.id} strategy={s} />
          ))}
        </div>
      )}
    </div>
  );
}
