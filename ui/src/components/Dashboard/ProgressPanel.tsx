import { useSessionProgress } from "../../hooks/useSessionProgress.ts";

interface Props {
  sessionId: string;
}

export function ProgressPanel({ sessionId }: Props) {
  const { latestProgress, events, isConnected, isComplete } = useSessionProgress(sessionId);
  const resultEvents = events.filter((e) => e.type === "result");

  return (
    <div className="flex h-full min-h-64 flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-800">
        <h2 className="font-semibold text-gray-900 dark:text-white">Live Progress</h2>
        <span
          className={`flex items-center gap-1.5 text-xs ${
            isConnected
              ? "text-green-600 dark:text-green-400"
              : "text-gray-400 dark:text-gray-500"
          }`}
        >
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${
              isConnected ? "animate-pulse bg-green-500" : "bg-gray-400"
            }`}
          />
          {isConnected ? "Connected" : "Disconnected"}
        </span>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {/* Progress bar */}
        {latestProgress && (
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
              <span>
                {latestProgress.current?.instrument} / {latestProgress.current?.timeframe}
              </span>
              <span>
                {latestProgress.current?.iteration} / {latestProgress.current?.total} (
                {latestProgress.pct}%)
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
              <div
                className="h-full rounded-full bg-blue-600 transition-all duration-300"
                style={{ width: `${latestProgress.pct ?? 0}%` }}
              />
            </div>
            <div className="text-xs text-gray-400 dark:text-gray-500">
              Elapsed: {latestProgress.elapsed_seconds}s
            </div>
          </div>
        )}

        {isComplete && (
          <div className="rounded-md bg-green-50 p-3 text-sm font-medium text-green-700 dark:bg-green-900/20 dark:text-green-400">
            Session completed — {resultEvents.length} result(s) saved
          </div>
        )}

        {/* Results table */}
        {resultEvents.length > 0 && (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Results ({resultEvents.length})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-500 dark:border-gray-700 dark:text-gray-400">
                    <th className="pb-1 pr-3">Instrument</th>
                    <th className="pb-1 pr-3">TF</th>
                    <th className="pb-1 pr-3 text-right">Sharpe</th>
                    <th className="pb-1 pr-3 text-right">Win%</th>
                    <th className="pb-1 text-right">Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {resultEvents.map((e, i) => (
                    <tr
                      key={i}
                      className="border-b border-gray-100 text-gray-700 dark:border-gray-800 dark:text-gray-300"
                    >
                      <td className="py-1 pr-3 font-mono">{e.instrument}</td>
                      <td className="py-1 pr-3 font-mono">{e.timeframe}</td>
                      <td className="py-1 pr-3 text-right font-mono">
                        {e.metrics?.["sharpe_ratio"] != null
                          ? Number(e.metrics["sharpe_ratio"]).toFixed(2)
                          : "—"}
                      </td>
                      <td className="py-1 pr-3 text-right font-mono">
                        {e.metrics?.["win_rate_pct"] != null
                          ? `${Number(e.metrics["win_rate_pct"]).toFixed(1)}%`
                          : "—"}
                      </td>
                      <td className="py-1 text-right font-mono">
                        {e.metrics?.["total_trades"] ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Downloading indicator */}
        {events.some((e) => e.type === "downloading") && !events.some((e) => e.type === "progress") && (
          <div className="rounded-md bg-blue-50 p-3 text-sm text-blue-700 animate-pulse dark:bg-blue-900/20 dark:text-blue-400">
            Downloading market data — this may take a minute...
          </div>
        )}

        {!latestProgress && !isComplete && !events.some((e) => e.type === "downloading" || e.type === "started") && (
          <div className="flex h-32 items-center justify-center text-sm text-gray-400 dark:text-gray-500">
            Waiting for job to start...
          </div>
        )}
      </div>
    </div>
  );
}
