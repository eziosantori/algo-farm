import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import {
  api,
  type LabSessionSummary,
  type LabSessionDetail,
  type BacktestResultDetail,
  type ResultStatus,
  type RobustnessScoreData,
} from "../../api/client.ts";

// ---------------------------------------------------------------------------
// Metric colour helpers
// ---------------------------------------------------------------------------

function sharpeClass(v: number) {
  if (v >= 1.0) return "text-emerald-600 dark:text-emerald-400";
  if (v >= 0.4) return "text-amber-600 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}
function ddClass(v: number) {
  if (v >= -10) return "text-emerald-600 dark:text-emerald-400";
  if (v >= -20) return "text-amber-600 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}
function winClass(v: number) {
  if (v >= 50) return "text-emerald-600 dark:text-emerald-400";
  if (v >= 40) return "text-amber-600 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}
function pfClass(v: number) {
  if (v >= 1.5) return "text-emerald-600 dark:text-emerald-400";
  if (v >= 1.2) return "text-amber-600 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}
function returnClass(v: number) {
  if (v > 0) return "text-emerald-600 dark:text-emerald-400";
  return "text-red-500 dark:text-red-400";
}

// ---------------------------------------------------------------------------
// Status badge styles
// ---------------------------------------------------------------------------

const SESSION_STATUS: Record<string, string> = {
  running:  "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  completed:"bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400",
};

const RESULT_STATUS: Record<string, string> = {
  pending:              "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  validated:            "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  rejected:             "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
  production_standard:  "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400",
  production_aggressive:"bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400",
  production_defensive: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400",
};

// ---------------------------------------------------------------------------
// SessionHistory
// ---------------------------------------------------------------------------

export function SessionHistory() {
  const [sessions, setSessions] = useState<LabSessionSummary[]>([]);
  const [expanded, setExpanded] = useState<Record<string, LabSessionDetail | null>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listLabSessions()
      .then(({ sessions }) => setSessions(sessions))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function toggleExpand(id: string) {
    if (expanded[id] !== undefined) {
      setExpanded((prev) => { const n = { ...prev }; delete n[id]; return n; });
      return;
    }
    try {
      const detail = await api.getLabSession(id);
      setExpanded((prev) => ({ ...prev, [id]: detail }));
    } catch (e: unknown) {
      console.error(e);
      setExpanded((prev) => ({ ...prev, [id]: null }));
    }
  }

  async function updateResultStatus(sessionId: string, resultId: string, status: ResultStatus) {
    try {
      const updated = await api.updateLabResultStatus(resultId, status);
      setExpanded((prev) => {
        const d = prev[sessionId];
        if (!d) return prev;
        return { ...prev, [sessionId]: { ...d, results: d.results.map((r) => r.id === resultId ? updated : r) } };
      });
    } catch (e: unknown) { console.error(e); }
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;

  if (sessions.length === 0) return <EmptyState />;

  return (
    <div className="space-y-3">
      {sessions.map((s) => (
        <div key={s.id} className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
          {/* Session card header */}
          <div className="flex flex-wrap items-center gap-3 p-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-gray-900 dark:text-white truncate">{s.strategy_name}</span>
                {s.strategy_id && (
                  <span className="text-xs text-gray-400 dark:text-gray-500">Linked</span>
                )}
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${SESSION_STATUS[s.status] ?? ""}`}>
                  {s.status}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                <span className="flex gap-1">
                  {s.instruments.map((i) => (
                    <span key={i} className="rounded bg-gray-100 px-1.5 py-0.5 font-mono dark:bg-gray-800">{i}</span>
                  ))}
                </span>
                <span>·</span>
                <span className="flex gap-1">
                  {s.timeframes.map((t) => (
                    <span key={t} className="rounded bg-gray-100 px-1.5 py-0.5 font-mono dark:bg-gray-800">{t}</span>
                  ))}
                </span>
                <span>·</span>
                <span>{new Date(s.created_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
              </div>
            </div>

            {/* Progress + action */}
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-xs text-gray-400 dark:text-gray-500">Results</p>
                <p className="font-mono text-sm font-semibold text-gray-900 dark:text-white">
                  {s.validated_results}
                  <span className="font-normal text-gray-400">/{s.total_results}</span>
                </p>
              </div>
              <div className="w-24">
                <div className="h-1.5 rounded-full bg-gray-200 dark:bg-gray-700">
                  <div
                    className="h-1.5 rounded-full bg-blue-500 transition-all"
                    style={{ width: s.total_results > 0 ? `${(s.validated_results / s.total_results) * 100}%` : "0%" }}
                  />
                </div>
                <p className="mt-0.5 text-right text-xs text-gray-400">{s.total_results > 0 ? Math.round((s.validated_results / s.total_results) * 100) : 0}% validated</p>
              </div>
              <button
                onClick={() => void toggleExpand(s.id)}
                className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700 transition-colors"
              >
                {expanded[s.id] !== undefined ? "Hide" : "Results"}
              </button>
            </div>
          </div>

          {/* Expanded detail */}
          {expanded[s.id] !== undefined && (
            <div className="border-t border-gray-100 dark:border-gray-800">
              {expanded[s.id] ? (
                <SessionDetail
                  session={expanded[s.id]!}
                  onStatusChange={(rId, status) => void updateResultStatus(s.id, rId, status)}
                />
              ) : (
                <p className="p-4 text-sm text-red-500">Failed to load session details.</p>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SessionDetail — strategy explainer + chart + results table
// ---------------------------------------------------------------------------

interface SessionDetailProps {
  session: LabSessionDetail;
  onStatusChange: (resultId: string, status: ResultStatus) => void;
}

function SessionDetail({ session, onStatusChange }: SessionDetailProps) {
  const { results, constraints } = session;

  const robustnessResults = results.filter((r) => r.split === "robustness_score");
  const backTestResults = results.filter((r) => r.split !== "robustness_score");

  const chartData = backTestResults.map((r) => ({
    name: `${r.instrument} ${r.timeframe}`,
    Sharpe: parseFloat(r.metrics.sharpe_ratio.toFixed(3)),
    "Profit Factor": parseFloat(r.metrics.profit_factor.toFixed(3)),
  }));

  return (
    <div className="p-4 space-y-5">
      {/* Strategy explainer */}
      <StrategyExplainer strategy={session.strategy} />

      {/* Constraints */}
      {constraints && (
        <p className="text-sm text-gray-600 dark:text-gray-400">
          <span className="font-semibold">Constraints:</span>{" "}
          {Object.entries(constraints).map(([k, v]) => `${k} >= ${v}`).join(" · ")}
        </p>
      )}

      {/* Robustness report */}
      {robustnessResults.length > 0 && (
        <RobustnessReport results={robustnessResults} />
      )}

      {backTestResults.length === 0 ? (
        <p className="text-sm text-gray-400">No results yet.</p>
      ) : (
        <>
          {/* Chart */}
          {chartData.length > 0 && (
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/50">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Performance overview</p>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData} margin={{ top: 0, right: 16, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(156,163,175,0.2)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "var(--surface-raised)", border: "1px solid var(--surface-border)", borderRadius: 8, fontSize: 12 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Sharpe" fill="#3b82f6" radius={[4, 4, 0, 0]} maxBarSize={48} />
                  <Bar dataKey="Profit Factor" fill="#8b5cf6" radius={[4, 4, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Results table */}
          <div className="overflow-x-auto rounded-lg border border-gray-100 dark:border-gray-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50 dark:border-gray-800 dark:bg-gray-900/60">
                  {["Instrument", "TF", "Params", "Sharpe", "Return %", "Max DD %", "Win %", "PF", "Trades", "Status", "Actions"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                {backTestResults.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
                    <td className="px-3 py-2.5 font-mono font-semibold text-gray-900 dark:text-white">{r.instrument}</td>
                    <td className="px-3 py-2.5 font-mono text-gray-500 dark:text-gray-400">{r.timeframe}</td>
                    <td className="px-3 py-2.5"><ParamsCell params={r.params} /></td>
                    <td className={`px-3 py-2.5 font-mono font-semibold ${sharpeClass(r.metrics.sharpe_ratio)}`}>{r.metrics.sharpe_ratio.toFixed(2)}</td>
                    <td className={`px-3 py-2.5 font-mono font-semibold ${returnClass(r.metrics.total_return_pct)}`}>{r.metrics.total_return_pct > 0 ? "+" : ""}{r.metrics.total_return_pct.toFixed(1)}%</td>
                    <td className={`px-3 py-2.5 font-mono font-semibold ${ddClass(r.metrics.max_drawdown_pct)}`}>{r.metrics.max_drawdown_pct.toFixed(1)}%</td>
                    <td className={`px-3 py-2.5 font-mono ${winClass(r.metrics.win_rate_pct)}`}>{r.metrics.win_rate_pct.toFixed(1)}%</td>
                    <td className={`px-3 py-2.5 font-mono ${pfClass(r.metrics.profit_factor)}`}>{r.metrics.profit_factor.toFixed(2)}</td>
                    <td className="px-3 py-2.5 font-mono text-gray-500 dark:text-gray-400">{r.metrics.total_trades}</td>
                    <td className="px-3 py-2.5">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${RESULT_STATUS[r.status] ?? ""}`}>
                        {r.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <ResultActions currentStatus={r.status} onAction={(s) => onStatusChange(r.id, s)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// RobustnessReport
// ---------------------------------------------------------------------------

const COMPONENT_LABELS: Record<string, string> = {
  oos_retention:  "OOS Retention",
  wf_efficiency:  "WF Efficiency",
  mc_p5_sharpe:   "MC P5 Sharpe",
  sensitivity:    "Param Stability",
  permutation:    "Permutation p",
};

function scoreColor(score: number) {
  if (score >= 80) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 65) return "text-blue-600 dark:text-blue-400";
  if (score >= 50) return "text-amber-600 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}

function scoreBg(score: number) {
  if (score >= 80) return "bg-emerald-50 border-emerald-200 dark:bg-emerald-950/30 dark:border-emerald-800";
  if (score >= 65) return "bg-blue-50 border-blue-200 dark:bg-blue-950/30 dark:border-blue-800";
  if (score >= 50) return "bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-800";
  return "bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-800";
}

function RobustnessReport({ results }: { results: BacktestResultDetail[] }) {
  return (
    <div className="space-y-3">
      <p className="text-xs font-bold uppercase tracking-wider text-gray-400">Robustness Report</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {results.map((r) => {
          const data = r.metrics as unknown as RobustnessScoreData;
          const score = data.composite_score;
          if (score === null || score === undefined) return null;
          return (
            <div key={r.id} className={`rounded-xl border p-4 ${scoreBg(score)}`}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-mono text-sm font-semibold text-gray-700 dark:text-gray-300">
                    {r.instrument} <span className="text-gray-400">{r.timeframe}</span>
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${
                    data.go_nogo === "GO"
                      ? "bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-900/40 dark:text-emerald-300 dark:border-emerald-700"
                      : "bg-red-100 text-red-700 border-red-300 dark:bg-red-900/40 dark:text-red-300 dark:border-red-700"
                  }`}>
                    {data.go_nogo}
                  </span>
                </div>
              </div>
              <div className="mt-3 flex items-end gap-2">
                <span className={`text-4xl font-bold tabular-nums leading-none ${scoreColor(score)}`}>
                  {score.toFixed(0)}
                </span>
                <span className={`mb-0.5 text-xl font-semibold ${scoreColor(score)}`}>
                  / 100
                </span>
                <span className={`mb-0.5 ml-1 text-lg font-bold ${scoreColor(score)}`}>
                  · {data.grade}
                </span>
              </div>
              <div className="mt-2 h-1.5 rounded-full bg-gray-200 dark:bg-gray-700">
                <div
                  className={`h-1.5 rounded-full transition-all ${
                    score >= 80 ? "bg-emerald-500" : score >= 65 ? "bg-blue-500" : score >= 50 ? "bg-amber-500" : "bg-red-500"
                  }`}
                  style={{ width: `${score}%` }}
                />
              </div>
              {data.components && (
                <div className="mt-3 space-y-1">
                  {Object.entries(data.components).map(([key, comp]) => (
                    comp.score !== null && (
                      <div key={key} className="flex items-center justify-between text-xs">
                        <span className="text-gray-500 dark:text-gray-400">
                          {COMPONENT_LABELS[key] ?? key}
                        </span>
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1 rounded-full bg-gray-200 dark:bg-gray-700">
                            <div
                              className={`h-1 rounded-full ${comp.score >= 65 ? "bg-emerald-400" : comp.score >= 40 ? "bg-amber-400" : "bg-red-400"}`}
                              style={{ width: `${comp.score}%` }}
                            />
                          </div>
                          <span className={`font-mono font-semibold w-8 text-right ${
                            comp.score >= 65 ? "text-emerald-600 dark:text-emerald-400"
                            : comp.score >= 40 ? "text-amber-600 dark:text-amber-400"
                            : "text-red-500 dark:text-red-400"
                          }`}>
                            {comp.score.toFixed(0)}
                          </span>
                        </div>
                      </div>
                    )
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StrategyExplainer
// ---------------------------------------------------------------------------

interface StrategyDef {
  name?: string;
  variant?: string;
  indicators?: { name: string; type: string; params?: Record<string, unknown> }[];
  entry_rules?: { indicator: string; condition: string; value?: number; compare_to?: string }[];
  exit_rules?: { indicator: string; condition: string; value?: number; compare_to?: string }[];
  position_management?: { size?: number; sl_pips?: number | null; tp_pips?: number | null; max_open_trades?: number };
}

function ruleToText(r: { indicator: string; condition: string; value?: number; compare_to?: string }) {
  return `${r.indicator} ${r.condition} ${r.compare_to ?? r.value ?? ""}`;
}

function StrategyExplainer({ strategy }: { strategy: unknown }) {
  const s = strategy as StrategyDef | null;
  if (!s?.indicators) return null;
  const pm = s.position_management;

  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50/60 p-4 dark:border-blue-900/50 dark:bg-blue-950/30">
      <p className="mb-3 text-sm font-semibold text-blue-800 dark:text-blue-300">
        {s.name ?? "Strategy"}{s.variant ? <span className="ml-2 font-normal text-blue-500">· {s.variant}</span> : null}
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <p className="mb-1 text-xs font-bold uppercase tracking-wider text-gray-400">Indicators</p>
          <ul className="space-y-0.5 text-xs text-gray-700 dark:text-gray-300">
            {s.indicators.map((ind) => {
              const p = ind.params && Object.keys(ind.params).length > 0
                ? `(${Object.entries(ind.params).map(([k, v]) => `${k}=${v}`).join(", ")})`
                : "";
              return <li key={ind.name}><code className="font-mono text-blue-700 dark:text-blue-300">{ind.name}</code> = {ind.type} {p}</li>;
            })}
          </ul>
        </div>
        <div>
          <p className="mb-1 text-xs font-bold uppercase tracking-wider text-gray-400">Entry (ALL)</p>
          <ul className="space-y-0.5 text-xs text-emerald-700 dark:text-emerald-400">
            {(s.entry_rules ?? []).map((r, i) => <li key={i} className="font-mono">{ruleToText(r)}</li>)}
          </ul>
          <p className="mb-1 mt-2 text-xs font-bold uppercase tracking-wider text-gray-400">Exit (ANY)</p>
          <ul className="space-y-0.5 text-xs text-red-600 dark:text-red-400">
            {(s.exit_rules ?? []).map((r, i) => <li key={i} className="font-mono">{ruleToText(r)}</li>)}
          </ul>
        </div>
        {pm && (
          <div>
            <p className="mb-1 text-xs font-bold uppercase tracking-wider text-gray-400">Position</p>
            <ul className="space-y-0.5 text-xs text-gray-600 dark:text-gray-400">
              <li>Size: <span className="font-mono font-semibold">{((pm.size ?? 0) * 100).toFixed(0)}%</span> of equity</li>
              {pm.sl_pips != null && <li>SL: <span className="font-mono">{pm.sl_pips} pips</span></li>}
              {pm.tp_pips != null && <li>TP: <span className="font-mono">{pm.tp_pips} pips</span></li>}
              <li>Max open: <span className="font-mono">{pm.max_open_trades ?? 1}</span></li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small sub-components
// ---------------------------------------------------------------------------

function ParamsCell({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params);
  if (entries.length === 0) return <span className="text-xs text-gray-400 italic">default</span>;
  return (
    <span className="font-mono text-xs text-gray-600 dark:text-gray-400">
      {entries.map(([k, v]) => `${k}=${v}`).join(", ")}
    </span>
  );
}

interface ResultActionsProps { currentStatus: ResultStatus; onAction: (s: ResultStatus) => void; }

function ResultActions({ currentStatus, onAction }: ResultActionsProps) {
  const actions: { label: string; status: ResultStatus; cls: string }[] = [];

  if (currentStatus === "pending" || currentStatus === "rejected") {
    actions.push({ label: "Validate", status: "validated", cls: "border-blue-300 text-blue-700 hover:bg-blue-50 dark:border-blue-700 dark:text-blue-400 dark:hover:bg-blue-900/30" });
    if (currentStatus === "pending") {
      actions.push({ label: "Reject", status: "rejected", cls: "border-red-300 text-red-600 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/30" });
    }
  }
  if (currentStatus === "validated" || currentStatus.startsWith("production")) {
    actions.push({ label: "Std", status: "production_standard", cls: "border-emerald-300 text-emerald-700 hover:bg-emerald-50 dark:border-emerald-700 dark:text-emerald-400 dark:hover:bg-emerald-900/30" });
    actions.push({ label: "Agg", status: "production_aggressive", cls: "border-orange-300 text-orange-700 hover:bg-orange-50 dark:border-orange-700 dark:text-orange-400 dark:hover:bg-orange-900/30" });
    actions.push({ label: "Def", status: "production_defensive", cls: "border-purple-300 text-purple-700 hover:bg-purple-50 dark:border-purple-700 dark:text-purple-400 dark:hover:bg-purple-900/30" });
    if (currentStatus !== "validated") {
      actions.push({ label: "Reject", status: "rejected", cls: "border-red-300 text-red-600 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/30" });
    }
  }

  return (
    <div className="flex flex-wrap gap-1">
      {actions.map((a) => (
        <button
          key={a.status}
          onClick={() => onAction(a.status)}
          className={`rounded border px-1.5 py-0.5 text-xs font-medium transition-colors ${a.cls}`}
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty / Loading / Error states
// ---------------------------------------------------------------------------

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-20 text-gray-400 dark:text-gray-600">
      <svg className="mr-2 h-5 w-5 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
      Loading sessions…
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-400">
      Error: {message}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 py-16 text-center dark:border-gray-800">
      <p className="text-sm font-medium text-gray-600 dark:text-gray-400">No sessions yet.</p>
      <p className="mt-1 text-xs text-gray-400 dark:text-gray-600">
        Launch an optimization from the Launch tab to get started.
      </p>
    </div>
  );
}
