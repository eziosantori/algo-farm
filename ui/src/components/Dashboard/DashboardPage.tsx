import { useState, useEffect, useCallback } from "react";
import { api } from "../../api/client.ts";
import type { LabSessionSummary } from "../../api/client.ts";
import { ProgressPanel } from "./ProgressPanel.tsx";

export function DashboardPage() {
  const [sessions, setSessions] = useState<LabSessionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fromDate, setFromDate] = useState("2024-01-01");
  const [toDate, setToDate] = useState(() => new Date(Date.now() - 86400000).toISOString().slice(0, 10));

  const refresh = useCallback(async () => {
    try {
      const data = await api.listLabSessions();
      setSessions(data.sessions);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = setInterval(() => void refresh(), 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  async function handleRun(sessionId: string) {
    setError(null);
    setRunningId(sessionId);
    // Select first so ProgressPanel mounts and subscribes via WS before the job starts
    setSelectedId(sessionId);
    try {
      await api.runLabSession(sessionId, { from_date: fromDate, to_date: toDate });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to run session");
    } finally {
      setRunningId(null);
    }
  }

  function statusBadge(status: string) {
    const colors: Record<string, string> = {
      running: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
      completed: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
      failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
    };
    return (
      <span
        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
          colors[status] ?? "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
        }`}
      >
        {status}
      </span>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
        <button
          onClick={() => void refresh()}
          className="rounded-md border border-gray-200 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Sessions list */}
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
            <h2 className="font-semibold text-gray-900 dark:text-white">Lab Sessions</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400">Auto-refreshes every 5s</p>
            {/* Date range for auto-download */}
            <div className="mt-2 flex items-center gap-2">
              <label className="text-xs text-gray-500 dark:text-gray-400">Data from</label>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="rounded border border-gray-200 px-1.5 py-0.5 text-xs dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
              />
              <label className="text-xs text-gray-500 dark:text-gray-400">to</label>
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="rounded border border-gray-200 px-1.5 py-0.5 text-xs dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
              />
            </div>
          </div>

          {loading ? (
            <div className="p-8 text-center text-sm text-gray-500 dark:text-gray-400">
              Loading...
            </div>
          ) : sessions.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-500 dark:text-gray-400">
              No sessions yet. Create one in the Lab.
            </div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className={`flex cursor-pointer items-start gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 ${
                    selectedId === s.id ? "bg-blue-50 dark:bg-blue-900/20" : ""
                  }`}
                  onClick={() => setSelectedId(s.id)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-gray-900 dark:text-white">
                        {s.strategy_name}
                      </span>
                      {statusBadge(s.status)}
                    </div>
                    <div className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                      {s.instruments.join(", ")} · {s.timeframes.join(", ")}
                    </div>
                    <div className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
                      {s.total_results} results · {new Date(s.created_at).toLocaleString()}
                    </div>
                  </div>
                  {s.status !== "running" && (
                    <button
                      disabled={runningId === s.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        void handleRun(s.id);
                      }}
                      className="shrink-0 rounded-md bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {runningId === s.id ? "Queuing..." : "Run"}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Progress panel */}
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          {selectedId ? (
            <ProgressPanel sessionId={selectedId} />
          ) : (
            <div className="flex h-64 items-center justify-center text-sm text-gray-500 dark:text-gray-400">
              Select a session to view live progress
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
