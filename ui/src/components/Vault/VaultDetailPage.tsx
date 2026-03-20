import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../../api/client.ts";
import type { StrategyLabSummary, TopPerformerRow } from "../../api/client.ts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sharpeBadge(v: number): string {
  if (v >= 1) return "text-emerald-600 dark:text-emerald-400 font-semibold";
  if (v >= 0.5) return "text-amber-600 dark:text-amber-400 font-semibold";
  return "text-red-500 dark:text-red-400 font-semibold";
}

function fmt(v: number, decimals = 2): string {
  return v.toFixed(decimals);
}

// ---------------------------------------------------------------------------
// Sub-panels
// ---------------------------------------------------------------------------

function TopPerformersTable({ rows }: { rows: TopPerformerRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-gray-400">No full-split results yet.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table className="min-w-full text-xs">
        <thead className="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          <tr>
            {["Instrument", "TF", "Sharpe", "Return %", "Max DD %", "Win %", "PF", "Trades"].map((h) => (
              <th key={h} className="px-3 py-2 text-left font-medium whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {rows.map((r, i) => (
            <tr
              key={`${r.instrument}-${r.timeframe}-${i}`}
              className={
                i === 0
                  ? "ring-1 ring-inset ring-blue-300 dark:ring-blue-700 bg-blue-50/40 dark:bg-blue-900/10"
                  : "bg-white dark:bg-gray-900"
              }
            >
              <td className="px-3 py-2 font-medium text-gray-900 dark:text-white">{r.instrument}</td>
              <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{r.timeframe}</td>
              <td className={`px-3 py-2 ${sharpeBadge(r.sharpe_ratio)}`}>{fmt(r.sharpe_ratio)}</td>
              <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{fmt(r.total_return_pct)}%</td>
              <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{fmt(r.max_drawdown_pct)}%</td>
              <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{fmt(r.win_rate_pct)}%</td>
              <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{fmt(r.profit_factor)}</td>
              <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{r.total_trades}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResearchNotesPanel({
  notes,
}: {
  notes: Array<{ id: string; created_at: string; research_notes: string }>;
}) {
  if (notes.length === 0) {
    return (
      <p className="text-sm text-gray-400">
        No research notes saved yet. Use <code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 rounded">PHASE 5.5</code> in workflow-orchestrator to save a summary.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {notes.map((n) => (
        <div key={n.id}>
          <p className="text-xs text-gray-400 mb-1">
            {new Date(n.created_at).toLocaleString()}
          </p>
          <pre className="whitespace-pre-wrap font-mono text-xs overflow-x-auto bg-gray-50 dark:bg-gray-800 rounded-md p-3 text-gray-800 dark:text-gray-200 leading-relaxed">
            {n.research_notes}
          </pre>
        </div>
      ))}
    </div>
  );
}

function BestParamsPanel({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params);
  if (entries.length === 0) {
    return <p className="text-sm text-gray-400">No params recorded.</p>;
  }
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
      {entries.map(([k, v]) => (
        <>
          <dt key={`k-${k}`} className="text-gray-500 dark:text-gray-400 truncate">{k}</dt>
          <dd key={`v-${k}`} className="text-gray-900 dark:text-white font-medium">{String(v)}</dd>
        </>
      ))}
    </dl>
  );
}

function CoveragePanel({
  coverage,
}: {
  coverage: { instruments: string[]; timeframes: string[]; total_runs: number };
}) {
  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wide">Instruments</p>
        <div className="flex flex-wrap gap-1">
          {coverage.instruments.map((i) => (
            <span key={i} className="rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 text-xs px-2 py-0.5 font-medium">
              {i}
            </span>
          ))}
        </div>
      </div>
      <div>
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wide">Timeframes</p>
        <div className="flex flex-wrap gap-1">
          {coverage.timeframes.map((tf) => (
            <span key={tf} className="rounded-full bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 text-xs px-2 py-0.5 font-medium">
              {tf}
            </span>
          ))}
        </div>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Total runs (full split): <span className="font-semibold text-gray-900 dark:text-white">{coverage.total_runs}</span>
      </p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 flex flex-col gap-3">
      <h2 className="font-semibold text-gray-900 dark:text-white text-sm">{title}</h2>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function VaultDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [summary, setSummary] = useState<StrategyLabSummary | null | "loading" | "not_found">("loading");

  useEffect(() => {
    if (!id) return;
    api
      .getStrategyLabSummary(id)
      .then(setSummary)
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "";
        setSummary(msg.includes("404") || msg.includes("NOT_FOUND") ? "not_found" : null);
      });
  }, [id]);

  return (
    <div className="flex flex-col gap-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
        <Link to="/vault" className="hover:text-gray-900 dark:hover:text-white transition-colors">
          ← Vault
        </Link>
        <span>/</span>
        <span className="text-gray-900 dark:text-white font-medium">Lab Summary</span>
      </div>

      {summary === "loading" && (
        <p className="text-sm text-gray-400 animate-pulse">Loading lab data…</p>
      )}

      {summary === "not_found" && (
        <div className="rounded-xl border border-dashed border-gray-300 dark:border-gray-700 p-10 text-center">
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            No lab data yet. Run{" "}
            <code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 rounded">
              /workflow-orchestrator
            </code>{" "}
            to generate results.
          </p>
        </div>
      )}

      {summary !== "loading" && summary !== "not_found" && summary !== null && (
        <>
          {/* Row 1: Top performers + Research notes */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Panel title="Top Performers (full split, best Sharpe)">
              <TopPerformersTable rows={summary.top_performers} />
            </Panel>
            <Panel title="Research Notes">
              <ResearchNotesPanel notes={summary.sessions_with_notes} />
            </Panel>
          </div>

          {/* Row 2: Best params + Coverage */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <Panel title="Best Parameters">
              <BestParamsPanel params={summary.best_params} />
            </Panel>
            <Panel title="Coverage">
              <CoveragePanel coverage={summary.coverage} />
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
