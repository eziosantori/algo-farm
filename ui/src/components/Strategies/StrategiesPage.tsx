import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type StrategySummary, type StrategyRecord } from "../../api/client.ts";
import { StrategyPreview } from "../Wizard/StrategyPreview.tsx";

function lifecycleBadgeClass(status: string): string {
  if (status === "validated") return "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400";
  if (status.startsWith("production")) return "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300";
  if (status === "optimizing") return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300";
  return "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400";
}

export function StrategiesPage() {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [expanded, setExpanded] = useState<Record<string, StrategyRecord | null>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [labRow, setLabRow] = useState<string | null>(null);
  const [labInstruments, setLabInstruments] = useState("");
  const [labTimeframes, setLabTimeframes] = useState("");

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

  async function launchLab(s: StrategySummary) {
    let record = expanded[s.id];
    if (record === undefined) {
      try {
        record = await api.getStrategy(s.id);
        setExpanded((prev) => ({ ...prev, [s.id]: record }));
      } catch {
        return;
      }
    }
    if (!record) return;
    const instruments = labInstruments.split(",").map((x) => x.trim()).filter(Boolean);
    const timeframes = labTimeframes.split(",").map((x) => x.trim()).filter(Boolean);
    if (instruments.length === 0 || timeframes.length === 0) return;
    try {
      await api.createLabSession({
        strategy_id: s.id,
        strategy_name: s.name,
        strategy_json: JSON.stringify(record.definition),
        instruments,
        timeframes,
      });
      navigate("/lab");
    } catch (e: unknown) {
      console.error(e);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-400">
        <svg className="animate-spin w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
        </svg>
        Loading strategies…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-400">
        <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd"/>
        </svg>
        Error: {error}
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Saved Strategies
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {strategies.length > 0
              ? `${strategies.length} strateg${strategies.length === 1 ? "y" : "ies"} saved`
              : "No strategies yet"}
          </p>
        </div>
        <Link
          to="/wizard"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
          </svg>
          New Strategy
        </Link>
      </div>

      {strategies.length === 0 ? (
        <div className="text-center py-20 rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700">
          <div className="text-4xl mb-3">🌱</div>
          <p className="text-gray-600 dark:text-gray-400 font-medium">No strategies saved yet</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
            Use the{" "}
            <Link to="/wizard" className="text-blue-600 dark:text-blue-400 hover:underline">
              Wizard
            </Link>{" "}
            to create your first strategy.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-4 px-4 py-2.5 bg-gray-50 dark:bg-gray-800/60 border-b border-gray-200 dark:border-gray-700">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Name
            </span>
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Lifecycle
            </span>
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Variant
            </span>
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Created
            </span>
            <span />
            <span />
          </div>

          {/* Rows */}
          {strategies.map((s, idx) => (
            <div
              key={s.id}
              className={idx < strategies.length - 1 || expanded[s.id] !== undefined
                ? "border-b border-gray-200 dark:border-gray-700"
                : ""}
            >
              {/* Main row */}
              <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-4 items-center px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors">
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                  {s.name}
                </span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full uppercase tracking-wide whitespace-nowrap ${lifecycleBadgeClass(s.lifecycle_status)}`}>
                  {s.lifecycle_status}
                </span>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 uppercase tracking-wide whitespace-nowrap">
                  {s.variant}
                </span>
                <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
                  {new Date(s.created_at).toLocaleString()}
                </span>
                <button
                  onClick={() => {
                    if (labRow === s.id) { setLabRow(null); } else {
                      setLabInstruments(""); setLabTimeframes(""); setLabRow(s.id);
                      if (expanded[s.id] === undefined) { void api.getStrategy(s.id).then((r) => setExpanded((prev) => ({ ...prev, [s.id]: r }))).catch(() => {}); }
                    }
                  }}
                  className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-emerald-300 transition-colors whitespace-nowrap"
                >
                  ▶ Lab
                </button>
                <button
                  onClick={() => void toggleExpand(s.id)}
                  className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors whitespace-nowrap"
                >
                  {expanded[s.id] !== undefined ? (
                    <>
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7"/>
                      </svg>
                      Hide
                    </>
                  ) : (
                    <>
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
                      </svg>
                      Details
                    </>
                  )}
                </button>
              </div>

              {/* Inline Lab form */}
              {labRow === s.id && (
                <div className="px-4 py-3 bg-blue-50/50 dark:bg-blue-950/20 border-b border-blue-100 dark:border-blue-900/40">
                  <div className="flex items-center gap-3 flex-wrap">
                    <input
                      type="text"
                      placeholder="Instruments (e.g. EURUSD,XAUUSD)"
                      value={labInstruments}
                      onChange={(e) => setLabInstruments(e.target.value)}
                      className="text-sm border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500 w-56"
                    />
                    <input
                      type="text"
                      placeholder="Timeframes (e.g. H1,M15)"
                      value={labTimeframes}
                      onChange={(e) => setLabTimeframes(e.target.value)}
                      className="text-sm border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500 w-44"
                    />
                    <button
                      onClick={() => void launchLab(s)}
                      className="px-3 py-1 rounded bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 transition-colors"
                    >
                      Launch
                    </button>
                    <button
                      onClick={() => setLabRow(null)}
                      className="px-3 py-1 rounded border border-gray-300 dark:border-gray-600 text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Expanded detail */}
              {expanded[s.id] !== undefined && (
                <div className="px-4 pb-4 bg-gray-50/50 dark:bg-gray-800/20">
                  {expanded[s.id] ? (
                    <StrategyPreview strategy={expanded[s.id]!.definition} />
                  ) : (
                    <p className="text-sm text-red-500 dark:text-red-400 py-2">
                      Failed to load strategy details.
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
