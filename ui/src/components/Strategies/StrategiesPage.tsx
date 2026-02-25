import { useState, useEffect } from "react";
import { api, type StrategySummary, type StrategyRecord } from "../../api/client.ts";

export function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [expanded, setExpanded] = useState<Record<string, StrategyRecord | null>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listStrategies()
      .then(({ strategies }) => setStrategies(strategies))
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
      const record = await api.getStrategy(id);
      setExpanded((prev) => ({ ...prev, [id]: record }));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Error loading strategy";
      setExpanded((prev) => ({ ...prev, [id]: null }));
      console.error(msg);
    }
  }

  if (loading) return <p>Loading strategies…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Error: {error}</p>;

  return (
    <div>
      <h1 style={{ marginBottom: "1.5rem" }}>Saved Strategies</h1>

      {strategies.length === 0 ? (
        <p style={{ color: "#6b7280" }}>
          No strategies saved yet.{" "}
          <a href="/wizard" style={{ color: "#2563eb" }}>
            Create one in the Wizard.
          </a>
        </p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Name</th>
              <th style={styles.th}>Variant</th>
              <th style={styles.th}>Created</th>
              <th style={styles.th}></th>
            </tr>
          </thead>
          <tbody>
            {strategies.map((s) => (
              <>
                <tr key={s.id} style={styles.tr}>
                  <td style={styles.td}>{s.name}</td>
                  <td style={styles.td}>
                    <span style={styles.badge}>{s.variant}</span>
                  </td>
                  <td style={styles.td}>{new Date(s.created_at).toLocaleString()}</td>
                  <td style={styles.td}>
                    <button onClick={() => void toggleExpand(s.id)} style={styles.viewBtn}>
                      {expanded[s.id] !== undefined ? "Hide JSON" : "View JSON"}
                    </button>
                  </td>
                </tr>
                {expanded[s.id] !== undefined && (
                  <tr key={`${s.id}-detail`}>
                    <td colSpan={4} style={styles.detailCell}>
                      {expanded[s.id] ? (
                        <pre style={styles.json}>
                          {JSON.stringify(expanded[s.id]!.definition, null, 2)}
                        </pre>
                      ) : (
                        <p style={{ color: "#dc2626" }}>Failed to load JSON.</p>
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

const styles: Record<string, React.CSSProperties> = {
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "0.9rem",
  },
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
    backgroundColor: "#dbeafe",
    color: "#1d4ed8",
    textTransform: "uppercase",
  },
  viewBtn: {
    padding: "0.25rem 0.75rem",
    border: "1px solid #d1d5db",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "0.8rem",
    backgroundColor: "#fff",
  },
  detailCell: { padding: "0 0.75rem 1rem" },
  json: {
    backgroundColor: "#1f2937",
    color: "#f3f4f6",
    padding: "1rem",
    borderRadius: "6px",
    fontSize: "0.75rem",
    overflow: "auto",
    maxHeight: "300px",
    margin: 0,
  },
};
