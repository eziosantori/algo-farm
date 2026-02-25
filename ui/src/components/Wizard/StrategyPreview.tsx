import type { StrategyDefinition } from "@algo-farm/shared/strategy";

interface Props {
  strategy: StrategyDefinition;
}

export function StrategyPreview({ strategy }: Props) {
  return (
    <div style={styles.wrapper}>
      <h3 style={styles.title}>
        {strategy.name}
        <span style={styles.badge}>{strategy.variant}</span>
      </h3>

      <div style={styles.summary}>
        <p>
          <strong>Indicators:</strong>{" "}
          {strategy.indicators.map((i) => `${i.name} (${i.type})`).join(", ")}
        </p>
        <p>
          <strong>Entry rules:</strong> {strategy.entry_rules.length} rule
          {strategy.entry_rules.length !== 1 ? "s" : ""}
        </p>
        <p>
          <strong>Exit rules:</strong> {strategy.exit_rules.length} rule
          {strategy.exit_rules.length !== 1 ? "s" : ""}
        </p>
        <p>
          <strong>Position size:</strong> {(strategy.position_management.size * 100).toFixed(1)}%
          &nbsp;&nbsp;
          <strong>Max open trades:</strong> {strategy.position_management.max_open_trades}
        </p>
      </div>

      <pre style={styles.json}>{JSON.stringify(strategy, null, 2)}</pre>
    </div>
  );
}

const styles = {
  wrapper: {
    border: "1px solid #e5e7eb",
    borderRadius: "8px",
    padding: "1rem",
    backgroundColor: "#f9fafb",
    marginTop: "1rem",
  },
  title: {
    margin: "0 0 0.5rem",
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    fontSize: "1rem",
  },
  badge: {
    fontSize: "0.7rem",
    padding: "2px 6px",
    borderRadius: "4px",
    backgroundColor: "#dbeafe",
    color: "#1d4ed8",
    fontWeight: "normal",
    textTransform: "uppercase" as const,
  },
  summary: {
    fontSize: "0.875rem",
    color: "#374151",
    marginBottom: "0.75rem",
  },
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
