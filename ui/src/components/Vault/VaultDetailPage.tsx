import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, downloadExport, previewExport } from "../../api/client.ts";
import type { StrategyLabSummary, TopPerformerRow, StrategyRecord, ExportFormat } from "../../api/client.ts";
import { StrategyPreview } from "../Wizard/StrategyPreview.tsx";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sharpeBadge(v: number): string {
  if (v >= 1) return "text-emerald-600 dark:text-emerald-400 font-semibold";
  if (v >= 0.5) return "text-amber-600 dark:text-amber-400 font-semibold";
  return "text-red-500 dark:text-red-400 font-semibold";
}

function fmt(v: number | null | undefined, decimals = 2): string {
  if (v == null || isNaN(v)) return "—";
  return v.toFixed(decimals);
}

// ---------------------------------------------------------------------------
// Sub-panels
// ---------------------------------------------------------------------------

function TopPerformersTable({ rows }: { rows: TopPerformerRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-gray-400">No full-split results yet.</p>;
  }

  // Compute which param keys differ across rows (pair-specific overrides)
  const allParamKeys = [...new Set(rows.flatMap((r) => Object.keys(r.params)))];
  const overriddenKeys = new Set<string>();
  for (const key of allParamKeys) {
    const values = rows.map((r) => r.params[key]);
    if (values.some((v, _, arr) => String(v) !== String(arr[0]))) {
      overriddenKeys.add(key);
    }
  }

  const hasParams = rows.some((r) => Object.keys(r.params).length > 0);

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table className="min-w-full text-xs">
        <thead className="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          <tr>
            {["Instrument", "TF", "Sharpe", "Return %", "Max DD %", "Win %", "PF", "Trades", ...(hasParams ? ["Effective Params"] : [])].map((h) => (
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
              {hasParams && (
                <td className="px-3 py-2">
                  <span className="flex flex-wrap gap-1">
                    {Object.entries(r.params).map(([k, v]) => (
                      <span
                        key={k}
                        title={overriddenKeys.has(k) ? "differs across pairs" : "same for all pairs"}
                        className={`font-mono px-1.5 py-0.5 rounded ${
                          overriddenKeys.has(k)
                            ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 font-semibold ring-1 ring-amber-300 dark:ring-amber-700"
                            : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                        }`}
                      >
                        {k}={String(v)}
                      </span>
                    ))}
                  </span>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CopyMarkdownButton({ markdown }: { markdown: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <button
      onClick={handleCopy}
      title="Copy as Markdown"
      className="flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-2.5 py-1 text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-white transition-colors"
    >
      {copied ? (
        <>
          <svg className="w-3.5 h-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          <span className="text-emerald-600 dark:text-emerald-400">Copied!</span>
        </>
      ) : (
        <>
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
          </svg>
          Copy MD
        </>
      )}
    </button>
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
    <div className="flex flex-col gap-6">
      {notes.map((n) => (
        <div key={n.id}>
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs text-gray-400">
              {new Date(n.created_at).toLocaleString()}
            </p>
            <CopyMarkdownButton markdown={n.research_notes} />
          </div>
          <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:text-sm prose-headings:font-semibold prose-h2:text-base prose-h2:border-b prose-h2:border-gray-200 prose-h2:dark:border-gray-700 prose-h2:pb-1 prose-h2:mb-3 prose-h3:mt-4 prose-h3:mb-2 prose-table:text-xs prose-td:px-2 prose-td:py-1 prose-th:px-2 prose-th:py-1.5 prose-th:bg-gray-50 prose-th:dark:bg-gray-800 prose-table:border prose-table:border-gray-200 prose-table:dark:border-gray-700 prose-tr:border-b prose-tr:border-gray-100 prose-tr:dark:border-gray-800 prose-p:text-gray-700 prose-p:dark:text-gray-300 prose-li:text-gray-700 prose-li:dark:text-gray-300 prose-strong:text-gray-900 prose-strong:dark:text-white prose-code:text-xs prose-code:bg-gray-100 prose-code:dark:bg-gray-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none">
            <Markdown remarkPlugins={[remarkGfm]}>{n.research_notes}</Markdown>
          </div>
        </div>
      ))}
    </div>
  );
}

function StrategyDefinitionPanel({ strategyId }: { strategyId: string }) {
  const [record, setRecord] = useState<StrategyRecord | null | "loading">("loading");

  useEffect(() => {
    api
      .getStrategy(strategyId)
      .then(setRecord)
      .catch(() => setRecord(null));
  }, [strategyId]);

  if (record === "loading") {
    return <p className="text-sm text-gray-400 animate-pulse">Loading strategy…</p>;
  }
  if (!record) {
    return <p className="text-sm text-gray-400">Strategy definition not available.</p>;
  }
  return <StrategyPreview strategy={record.definition} />;
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

function ExportPanel({
  strategyId,
  pairs,
}: {
  strategyId: string;
  pairs: Array<{ instrument: string; timeframe: string }>;
}) {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ code: string; filename: string; format: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload(
    format: ExportFormat,
    opts?: { instrument?: string; timeframe?: string },
  ) {
    const key = `${format}-${opts?.instrument ?? "global"}-${opts?.timeframe ?? ""}`;
    setDownloading(key);
    setError(null);
    try {
      await downloadExport(strategyId, format, opts);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Download failed");
    } finally {
      setDownloading(null);
    }
  }

  async function handlePreview(
    format: ExportFormat,
    opts?: { instrument?: string; timeframe?: string },
  ) {
    setError(null);
    try {
      const result = await previewExport(strategyId, format, opts);
      setPreview({ ...result, format });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Preview failed");
    }
  }

  const btnClass =
    "rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors whitespace-nowrap";

  return (
    <div className="flex flex-col gap-4">
      {/* Global exports row */}
      <div>
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">
          Strategy code
        </p>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => handleDownload("ctrader")} disabled={downloading !== null} className={btnClass}>
            {downloading === "ctrader-global-" ? "..." : "cTrader (.cs)"}
          </button>
          <button onClick={() => handlePreview("ctrader")} className={btnClass}>
            Preview .cs
          </button>
          <button onClick={() => handleDownload("pine")} disabled={downloading !== null} className={btnClass}>
            {downloading === "pine-global-" ? "..." : "Pine Script (.pine)"}
          </button>
          <button onClick={() => handlePreview("pine")} className={btnClass}>
            Preview .pine
          </button>
        </div>
      </div>

      {/* Per-pair opset exports */}
      <div>
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">
          cTrader Parameter Presets (.cbotset)
        </p>
        {pairs.length === 0 ? (
          <p className="text-xs text-gray-400">No pair data available for opset generation.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {pairs.map(({ instrument, timeframe }) => {
              const key = `opset-${instrument}-${timeframe}`;
              return (
                <div key={key} className="flex items-center gap-1">
                  <button
                    onClick={() => handleDownload("opset", { instrument, timeframe })}
                    disabled={downloading !== null}
                    className={btnClass}
                  >
                    {downloading === key ? "..." : `${instrument} ${timeframe}`}
                  </button>
                  <button
                    onClick={() => handlePreview("opset", { instrument, timeframe })}
                    className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                    title={`Preview opset for ${instrument} ${timeframe}`}
                  >
                    preview
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Error */}
      {error && <p className="text-xs text-red-500 dark:text-red-400">{error}</p>}

      {/* Preview panel */}
      {preview && (
        <div className="relative">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-gray-600 dark:text-gray-400">
              {preview.filename}
            </p>
            <button
              onClick={() => setPreview(null)}
              className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              Close
            </button>
          </div>
          <pre className="rounded-lg bg-gray-900 dark:bg-gray-950 text-gray-100 text-xs font-mono p-4 overflow-auto max-h-80">
            {preview.code}
          </pre>
        </div>
      )}
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

      {summary === null && (
        <div className="rounded-xl border border-dashed border-red-300 dark:border-red-800 p-10 text-center">
          <p className="text-red-500 dark:text-red-400 text-sm">
            Failed to load lab data. Check the browser console for details.
          </p>
        </div>
      )}

      {summary !== "loading" && summary !== "not_found" && summary !== null && (
        <>
          {/* Row 1: Top performers + Coverage */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <Panel title="Top Performers (full split, best Sharpe)">
                <TopPerformersTable rows={summary.top_performers} />
              </Panel>
            </div>
            <Panel title="Coverage">
              <CoveragePanel coverage={summary.coverage} />
            </Panel>
          </div>

          {/* Row 2: Strategy definition + Export */}
          {id && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <Panel title="Strategy Definition">
                  <StrategyDefinitionPanel strategyId={id} />
                </Panel>
              </div>
              <Panel title="Export">
                <ExportPanel
                  strategyId={id}
                  pairs={summary.top_performers.map((r) => ({
                    instrument: r.instrument,
                    timeframe: r.timeframe,
                  }))}
                />
              </Panel>
            </div>
          )}

          {/* Row 3: Research notes (full width for readable markdown) */}
          <Panel title="Research Notes">
            <ResearchNotesPanel notes={summary.sessions_with_notes} />
          </Panel>
        </>
      )}
    </div>
  );
}
