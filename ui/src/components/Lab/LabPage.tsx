import { useState, useEffect } from "react";
import {
  api,
  type LabSessionSummary,
  type LabSessionDetail,
  type ResultStatus,
} from "../../api/client.ts";

export function LabPage() {
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
      setExpanded((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      return;
    }
    try {
      const detail = await api.getLabSession(id);
      setExpanded((prev) => ({ ...prev, [id]: detail }));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Error";
      console.error(msg);
      setExpanded((prev) => ({ ...prev, [id]: null }));
    }
  }

  async function updateResultStatus(
    sessionId: string,
    resultId: string,
    status: ResultStatus
  ) {
    try {
      const updated = await api.updateLabResultStatus(resultId, status);
      setExpanded((prev) => {
        const detail = prev[sessionId];
        if (!detail) return prev;
        return {
          ...prev,
          [sessionId]: {
            ...detail,
            results: detail.results.map((r) => (r.id === resultId ? updated : r)),
          },
        };
      });
    } catch (e: unknown) {
      console.error("Failed to update result status", e);
    }
  }

  if (loading) return <p>Loading lab sessions…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Error: {error}</p>;

  return (
    <div>
      <h1 style={{ marginBottom: "1.5rem" }}>Strategy Lab</h1>

      {sessions.length === 0 ? (
        <p style={{ color: "#6b7280" }}>No lab sessions yet. Run the /strategy-lab skill to create one.</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Strategy</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Instruments</th>
              <th style={styles.th}>Timeframes</th>
              <th style={styles.th}>Results</th>
              <th style={styles.th}>Created</th>
              <th style={styles.th}></th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <>
                <tr key={s.id} style={styles.tr}>
                  <td style={styles.td}>{s.strategy_name}</td>
                  <td style={styles.td}>
                    <span style={sessionStatusBadge(s.status)}>{s.status}</span>
                  </td>
                  <td style={styles.td}>
                    <span style={styles.chips}>{s.instruments.join(", ")}</span>
                  </td>
                  <td style={styles.td}>
                    <span style={styles.chips}>{s.timeframes.join(", ")}</span>
                  </td>
                  <td style={styles.td}>
                    {s.validated_results}/{s.total_results} validated
                  </td>
                  <td style={styles.td}>{new Date(s.created_at).toLocaleString()}</td>
                  <td style={styles.td}>
                    <button onClick={() => void toggleExpand(s.id)} style={styles.viewBtn}>
                      {expanded[s.id] !== undefined ? "Hide" : "View Results"}
                    </button>
                  </td>
                </tr>
                {expanded[s.id] !== undefined && (
                  <tr key={`${s.id}-detail`}>
                    <td colSpan={7} style={styles.detailCell}>
                      {expanded[s.id] ? (
                        <SessionResults
                          session={expanded[s.id]!}
                          onStatusChange={(resultId, status) =>
                            void updateResultStatus(s.id, resultId, status)
                          }
                        />
                      ) : (
                        <p style={{ color: "#dc2626" }}>Failed to load session details.</p>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SessionResults — inline detail table
// ---------------------------------------------------------------------------

interface SessionResultsProps {
  session: LabSessionDetail;
  onStatusChange: (resultId: string, status: ResultStatus) => void;
}

function SessionResults({ session, onStatusChange }: SessionResultsProps) {
  const { constraints, results } = session;

  return (
    <div style={styles.detailBox}>
      <StrategyExplainer strategy={session.strategy} />

      {constraints && (
        <p style={styles.constraintsLine}>
          <strong>Constraints:</strong>{" "}
          {Object.entries(constraints)
            .map(([k, v]) => `${k} ≥ ${v}`)
            .join(" · ")}
        </p>
      )}

      {results.length === 0 ? (
        <p style={{ color: "#6b7280", padding: "0.5rem 0" }}>No results yet.</p>
      ) : (
        <table style={styles.resultsTable}>
          <thead>
            <tr>
              <th style={styles.rth}>Instrument</th>
              <th style={styles.rth}>TF</th>
              <th style={styles.rth}>Params</th>
              <th style={styles.rth}>Sharpe</th>
              <th style={styles.rth}>Return %</th>
              <th style={styles.rth}>Max DD %</th>
              <th style={styles.rth}>Win %</th>
              <th style={styles.rth}>PF</th>
              <th style={styles.rth}>Trades</th>
              <th style={styles.rth}>Status</th>
              <th style={styles.rth}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.id} style={styles.rtr}>
                <td style={styles.rtd}>{r.instrument}</td>
                <td style={styles.rtd}>{r.timeframe}</td>
                <td style={styles.rtd}>
                  <ParamsCell params={r.params} />
                </td>
                <td style={styles.rtd}>{r.metrics.sharpe_ratio.toFixed(2)}</td>
                <td style={styles.rtd}>{r.metrics.total_return_pct.toFixed(2)}</td>
                <td style={styles.rtd}>{r.metrics.max_drawdown_pct.toFixed(2)}</td>
                <td style={styles.rtd}>{r.metrics.win_rate_pct.toFixed(1)}</td>
                <td style={styles.rtd}>{r.metrics.profit_factor.toFixed(2)}</td>
                <td style={styles.rtd}>{r.metrics.total_trades}</td>
                <td style={styles.rtd}>
                  <span style={resultStatusBadge(r.status)}>{r.status.replace(/_/g, " ")}</span>
                </td>
                <td style={styles.rtd}>
                  <ResultActions
                    currentStatus={r.status}
                    onAction={(status) => onStatusChange(r.id, status)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// StrategyExplainer — human-readable summary of the strategy logic
// ---------------------------------------------------------------------------

interface StrategyDef {
  name?: string;
  variant?: string;
  indicators?: { name: string; type: string; params?: Record<string, unknown> }[];
  entry_rules?: { indicator: string; condition: string; value?: number; compare_to?: string }[];
  exit_rules?: { indicator: string; condition: string; value?: number; compare_to?: string }[];
  position_management?: { size?: number; sl_pips?: number | null; tp_pips?: number | null; max_open_trades?: number };
}

function ruleToText(rule: { indicator: string; condition: string; value?: number; compare_to?: string }): string {
  const rhs = rule.compare_to !== undefined ? rule.compare_to : String(rule.value ?? "");
  return `${rule.indicator} ${rule.condition} ${rhs}`;
}

function StrategyExplainer({ strategy }: { strategy: unknown }) {
  const s = strategy as StrategyDef | null;
  if (!s || !s.indicators) return null;

  const pm = s.position_management;

  return (
    <div style={styles.explainerBox}>
      <p style={styles.explainerTitle}>
        {s.name ?? "Strategy"}{s.variant ? ` · ${s.variant}` : ""}
      </p>
      <div style={styles.explainerGrid}>
        <div>
          <span style={styles.explainerLabel}>Indicators</span>
          <ul style={styles.explainerList}>
            {s.indicators.map((ind) => {
              const paramStr = ind.params && Object.keys(ind.params).length > 0
                ? " (" + Object.entries(ind.params).map(([k, v]) => `${k}=${v}`).join(", ") + ")"
                : "";
              return <li key={ind.name}><code>{ind.name}</code> = {ind.type}{paramStr}</li>;
            })}
          </ul>
        </div>
        <div>
          <span style={styles.explainerLabel}>Entry (ALL must be true)</span>
          <ul style={styles.explainerList}>
            {(s.entry_rules ?? []).map((r, i) => (
              <li key={i}>{ruleToText(r)}</li>
            ))}
          </ul>
          <span style={styles.explainerLabel}>Exit (ANY triggers close)</span>
          <ul style={styles.explainerList}>
            {(s.exit_rules ?? []).map((r, i) => (
              <li key={i}>{ruleToText(r)}</li>
            ))}
          </ul>
        </div>
        {pm && (
          <div>
            <span style={styles.explainerLabel}>Position</span>
            <ul style={styles.explainerList}>
              <li>Size: {((pm.size ?? 0) * 100).toFixed(0)}% of equity</li>
              {pm.sl_pips != null && <li>SL: {pm.sl_pips} pips</li>}
              {pm.tp_pips != null && <li>TP: {pm.tp_pips} pips</li>}
              <li>Max open: {pm.max_open_trades ?? 1}</li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ParamsCell — compact display of optimised params (empty → "default")
// ---------------------------------------------------------------------------

function ParamsCell({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params);
  if (entries.length === 0) return <span style={{ color: "#9ca3af", fontSize: "0.72rem" }}>default</span>;
  return (
    <span style={{ fontSize: "0.72rem", color: "#374151" }}>
      {entries.map(([k, v]) => `${k}=${v}`).join(", ")}
    </span>
  );
}

// ---------------------------------------------------------------------------
// ResultActions — compact action buttons per result
// ---------------------------------------------------------------------------

interface ResultActionsProps {
  currentStatus: ResultStatus;
  onAction: (status: ResultStatus) => void;
}

function ResultActions({ currentStatus, onAction }: ResultActionsProps) {
  const actions: { label: string; status: ResultStatus; color: string }[] = [];

  if (currentStatus === "pending" || currentStatus === "rejected") {
    actions.push({ label: "Validate", status: "validated", color: "#2563eb" });
    if (currentStatus === "pending") {
      actions.push({ label: "Reject", status: "rejected", color: "#dc2626" });
    }
  }

  if (currentStatus === "validated" || currentStatus.startsWith("production")) {
    actions.push({ label: "→ Std", status: "production_standard", color: "#16a34a" });
    actions.push({ label: "→ Agg", status: "production_aggressive", color: "#ea580c" });
    actions.push({ label: "→ Def", status: "production_defensive", color: "#7c3aed" });
    if (currentStatus !== "validated") {
      actions.push({ label: "Reject", status: "rejected", color: "#dc2626" });
    }
  }

  return (
    <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap" }}>
      {actions.map((a) => (
        <button
          key={a.status}
          onClick={() => onAction(a.status)}
          style={{ ...styles.actionBtn, borderColor: a.color, color: a.color }}
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Style helpers
// ---------------------------------------------------------------------------

function sessionStatusBadge(status: string): React.CSSProperties {
  const color = status === "completed" ? "#16a34a" : "#d97706";
  const bg = status === "completed" ? "#dcfce7" : "#fef3c7";
  return { ...styles.badge, color, backgroundColor: bg };
}

function resultStatusBadge(status: ResultStatus): React.CSSProperties {
  const map: Record<ResultStatus, { color: string; bg: string }> = {
    pending: { color: "#6b7280", bg: "#f3f4f6" },
    validated: { color: "#2563eb", bg: "#dbeafe" },
    rejected: { color: "#dc2626", bg: "#fee2e2" },
    production_standard: { color: "#16a34a", bg: "#dcfce7" },
    production_aggressive: { color: "#ea580c", bg: "#ffedd5" },
    production_defensive: { color: "#7c3aed", bg: "#ede9fe" },
  };
  const { color, bg } = map[status] ?? { color: "#6b7280", bg: "#f3f4f6" };
  return { ...styles.badge, color, backgroundColor: bg };
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles: Record<string, React.CSSProperties> = {
  table: { width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" },
  th: {
    textAlign: "left",
    padding: "0.5rem 0.75rem",
    borderBottom: "2px solid #e5e7eb",
    color: "#6b7280",
    fontWeight: 600,
    fontSize: "0.8rem",
    textTransform: "uppercase",
  },
  tr: { borderBottom: "1px solid #f3f4f6" },
  td: { padding: "0.75rem", verticalAlign: "top" },
  badge: {
    fontSize: "0.7rem",
    padding: "2px 6px",
    borderRadius: "4px",
    textTransform: "uppercase",
    fontWeight: 600,
    whiteSpace: "nowrap",
  },
  chips: { fontSize: "0.8rem", color: "#374151" },
  viewBtn: {
    padding: "0.25rem 0.75rem",
    border: "1px solid #d1d5db",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "0.8rem",
    backgroundColor: "#fff",
  },
  detailCell: { padding: "0 0 0.5rem 0", backgroundColor: "#f9fafb" },
  detailBox: { padding: "1rem 1.5rem" },
  constraintsLine: { marginBottom: "0.75rem", fontSize: "0.85rem", color: "#374151" },
  explainerBox: {
    marginBottom: "1rem",
    padding: "0.75rem 1rem",
    backgroundColor: "#f0f9ff",
    borderRadius: "6px",
    border: "1px solid #bae6fd",
  },
  explainerTitle: { fontWeight: 600, fontSize: "0.85rem", margin: "0 0 0.5rem 0", color: "#0369a1" },
  explainerGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.75rem" },
  explainerLabel: { fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase" as const, color: "#6b7280", display: "block", marginBottom: "0.2rem" },
  explainerList: { margin: 0, paddingLeft: "1.2rem", fontSize: "0.78rem", color: "#374151", lineHeight: "1.6" },
  resultsTable: { width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" },
  rth: {
    textAlign: "left",
    padding: "0.4rem 0.6rem",
    borderBottom: "1px solid #e5e7eb",
    color: "#9ca3af",
    fontWeight: 600,
    fontSize: "0.72rem",
    textTransform: "uppercase",
  },
  rtr: { borderBottom: "1px solid #f3f4f6" },
  rtd: { padding: "0.5rem 0.6rem", verticalAlign: "middle" },
  actionBtn: {
    padding: "2px 6px",
    border: "1px solid",
    borderRadius: "3px",
    cursor: "pointer",
    fontSize: "0.7rem",
    backgroundColor: "#fff",
    whiteSpace: "nowrap",
  },
};
