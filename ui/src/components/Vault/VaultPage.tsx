import { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { api, type StrategySummary, type StrategyLabSummary } from "../../api/client.ts";
import { StrategyCard } from "./StrategyCard.tsx";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EnrichedStrategy extends StrategySummary {
  lab: StrategyLabSummary | null;
  bestSharpe: number | null;
  bestReturn: number | null;
  bestDD: number | null;
  totalTrades: number | null;
  instruments: string[];
  timeframes: string[];
}

type SortKey = "name" | "sharpe" | "return" | "dd" | "trades" | "date";
type ViewMode = "cards" | "table";

const VAULT_STATUSES = new Set([
  "validated",
  "production_standard",
  "production_aggressive",
  "production_defensive",
]);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const LIFECYCLE_BADGE: Record<string, string> = {
  validated: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400",
  production_standard: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  production_aggressive: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
  production_defensive: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
};

function sharpeBadge(v: number): string {
  if (v >= 1) return "text-emerald-600 dark:text-emerald-400 font-semibold";
  if (v >= 0.5) return "text-amber-600 dark:text-amber-400 font-semibold";
  if (v > 0) return "text-gray-700 dark:text-gray-300";
  return "text-red-500 dark:text-red-400";
}

function fmt(v: number | null, decimals = 2): string {
  if (v === null) return "—";
  return v.toFixed(decimals);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ViewToggle({ mode, onChange }: { mode: ViewMode; onChange: (m: ViewMode) => void }) {
  return (
    <div className="flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <button
        onClick={() => onChange("cards")}
        className={`px-3 py-1.5 text-xs font-medium transition-colors ${
          mode === "cards"
            ? "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white"
            : "text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50"
        }`}
      >
        Cards
      </button>
      <button
        onClick={() => onChange("table")}
        className={`px-3 py-1.5 text-xs font-medium transition-colors border-l border-gray-200 dark:border-gray-700 ${
          mode === "table"
            ? "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white"
            : "text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50"
        }`}
      >
        Table
      </button>
    </div>
  );
}

function SortHeader({
  label,
  sortKey,
  currentSort,
  currentDir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  currentSort: SortKey;
  currentDir: "asc" | "desc";
  onSort: (k: SortKey) => void;
}) {
  const active = currentSort === sortKey;
  return (
    <th
      className="px-3 py-2 text-left font-medium whitespace-nowrap cursor-pointer select-none hover:text-gray-900 dark:hover:text-white transition-colors"
      onClick={() => onSort(sortKey)}
    >
      {label}
      {active && (
        <span className="ml-1 text-blue-500">{currentDir === "asc" ? "▲" : "▼"}</span>
      )}
    </th>
  );
}

function VaultTable({
  strategies,
  sortKey,
  sortDir,
  onSort,
}: {
  strategies: EnrichedStrategy[];
  sortKey: SortKey;
  sortDir: "asc" | "desc";
  onSort: (k: SortKey) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
      <table className="min-w-full text-xs">
        <thead className="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 uppercase tracking-wide text-[11px]">
          <tr>
            <SortHeader label="Strategy" sortKey="name" currentSort={sortKey} currentDir={sortDir} onSort={onSort} />
            <th className="px-3 py-2 text-left font-medium whitespace-nowrap">Status</th>
            <th className="px-3 py-2 text-left font-medium whitespace-nowrap">Instruments</th>
            <th className="px-3 py-2 text-left font-medium whitespace-nowrap">Timeframes</th>
            <SortHeader label="Best Sharpe" sortKey="sharpe" currentSort={sortKey} currentDir={sortDir} onSort={onSort} />
            <SortHeader label="Best Return %" sortKey="return" currentSort={sortKey} currentDir={sortDir} onSort={onSort} />
            <SortHeader label="Max DD %" sortKey="dd" currentSort={sortKey} currentDir={sortDir} onSort={onSort} />
            <SortHeader label="Trades" sortKey="trades" currentSort={sortKey} currentDir={sortDir} onSort={onSort} />
            <SortHeader label="Created" sortKey="date" currentSort={sortKey} currentDir={sortDir} onSort={onSort} />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {strategies.map((s) => (
            <tr
              key={s.id}
              className="bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            >
              <td className="px-3 py-2.5">
                <Link
                  to={`/vault/${s.id}`}
                  className="font-medium text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                >
                  {s.name}
                </Link>
              </td>
              <td className="px-3 py-2.5">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium capitalize ${
                    LIFECYCLE_BADGE[s.lifecycle_status] ?? "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                  }`}
                >
                  {s.lifecycle_status.replace(/_/g, " ")}
                </span>
              </td>
              <td className="px-3 py-2.5">
                <div className="flex flex-wrap gap-1">
                  {s.instruments.length > 0
                    ? s.instruments.map((i) => (
                        <span key={i} className="rounded bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 text-[10px] font-medium">
                          {i}
                        </span>
                      ))
                    : <span className="text-gray-400">—</span>}
                </div>
              </td>
              <td className="px-3 py-2.5">
                <div className="flex flex-wrap gap-1">
                  {s.timeframes.length > 0
                    ? s.timeframes.map((tf) => (
                        <span key={tf} className="rounded bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 px-1.5 py-0.5 text-[10px] font-medium">
                          {tf}
                        </span>
                      ))
                    : <span className="text-gray-400">—</span>}
                </div>
              </td>
              <td className={`px-3 py-2.5 tabular-nums ${s.bestSharpe !== null ? sharpeBadge(s.bestSharpe) : "text-gray-400"}`}>
                {fmt(s.bestSharpe)}
              </td>
              <td className="px-3 py-2.5 tabular-nums text-gray-700 dark:text-gray-300">
                {s.bestReturn !== null ? `${fmt(s.bestReturn)}%` : "—"}
              </td>
              <td className="px-3 py-2.5 tabular-nums text-gray-700 dark:text-gray-300">
                {s.bestDD !== null ? `${fmt(s.bestDD)}%` : "—"}
              </td>
              <td className="px-3 py-2.5 tabular-nums text-gray-700 dark:text-gray-300">
                {s.totalTrades !== null ? s.totalTrades : "—"}
              </td>
              <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                {new Date(s.created_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function VaultPage() {
  const [strategies, setStrategies] = useState<EnrichedStrategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [sortKey, setSortKey] = useState<SortKey>("sharpe");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filterInstrument, setFilterInstrument] = useState<string>("");
  const [filterStatus, setFilterStatus] = useState<string>("");

  useEffect(() => {
    api
      .listStrategies()
      .then(async ({ strategies: all }) => {
        const vaultStrategies = all.filter((s) => VAULT_STATUSES.has(s.lifecycle_status));

        // Fetch lab summaries in parallel
        const enriched: EnrichedStrategy[] = await Promise.all(
          vaultStrategies.map(async (s) => {
            let lab: StrategyLabSummary | null = null;
            try {
              lab = await api.getStrategyLabSummary(s.id);
            } catch {
              // No lab data
            }

            const top = lab?.top_performers ?? [];
            const bestRow = top.length > 0 ? top[0] : null;

            return {
              ...s,
              lab,
              bestSharpe: bestRow?.sharpe_ratio ?? null,
              bestReturn: bestRow?.total_return_pct ?? null,
              bestDD: bestRow?.max_drawdown_pct ?? null,
              totalTrades: top.reduce((sum, r) => sum + r.total_trades, 0) || null,
              instruments: lab?.coverage.instruments ?? [],
              timeframes: lab?.coverage.timeframes ?? [],
            };
          })
        );

        setStrategies(enriched);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Unique values for filters
  const allInstruments = useMemo(
    () => [...new Set(strategies.flatMap((s) => s.instruments))].sort(),
    [strategies]
  );
  const allStatuses = useMemo(
    () => [...new Set(strategies.map((s) => s.lifecycle_status))].sort(),
    [strategies]
  );

  // Filter + sort
  const displayed = useMemo(() => {
    let result = [...strategies];

    if (filterInstrument) {
      result = result.filter((s) => s.instruments.includes(filterInstrument));
    }
    if (filterStatus) {
      result = result.filter((s) => s.lifecycle_status === filterStatus);
    }

    const dir = sortDir === "asc" ? 1 : -1;
    result.sort((a, b) => {
      switch (sortKey) {
        case "name":
          return dir * a.name.localeCompare(b.name);
        case "sharpe":
          return dir * ((a.bestSharpe ?? -Infinity) - (b.bestSharpe ?? -Infinity));
        case "return":
          return dir * ((a.bestReturn ?? -Infinity) - (b.bestReturn ?? -Infinity));
        case "dd":
          return dir * ((a.bestDD ?? -Infinity) - (b.bestDD ?? -Infinity));
        case "trades":
          return dir * ((a.totalTrades ?? 0) - (b.totalTrades ?? 0));
        case "date":
          return dir * (new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
        default:
          return 0;
      }
    });

    return result;
  }, [strategies, filterInstrument, filterStatus, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Strategy Vault
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Validated and production-ready strategies.
          </p>
        </div>
        <ViewToggle mode={viewMode} onChange={setViewMode} />
      </div>

      {/* Filters (table mode) */}
      {viewMode === "table" && strategies.length > 0 && (
        <div className="flex flex-wrap gap-3 items-center">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            Filters
          </span>
          <select
            value={filterInstrument}
            onChange={(e) => setFilterInstrument(e.target.value)}
            className="rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2.5 py-1.5 text-xs text-gray-700 dark:text-gray-300"
          >
            <option value="">All instruments</option>
            {allInstruments.map((i) => (
              <option key={i} value={i}>{i}</option>
            ))}
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2.5 py-1.5 text-xs text-gray-700 dark:text-gray-300"
          >
            <option value="">All statuses</option>
            {allStatuses.map((s) => (
              <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
            ))}
          </select>
          <span className="text-xs text-gray-400 ml-auto">
            {displayed.length} of {strategies.length} strategies
          </span>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="py-16 text-center text-sm text-gray-400 animate-pulse">
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

      {/* Table view */}
      {!loading && viewMode === "table" && displayed.length > 0 && (
        <VaultTable
          strategies={displayed}
          sortKey={sortKey}
          sortDir={sortDir}
          onSort={handleSort}
        />
      )}

      {/* Card view */}
      {!loading && viewMode === "cards" && displayed.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {displayed.map((s) => (
            <StrategyCard key={s.id} strategy={s} />
          ))}
        </div>
      )}
    </div>
  );
}
