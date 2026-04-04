import { useState } from "react";
import { useLocation } from "react-router-dom";
import { OptimizationLauncher } from "./OptimizationLauncher.tsx";
import { SessionHistory } from "./SessionHistory.tsx";

// ---------------------------------------------------------------------------
// Tab types
// ---------------------------------------------------------------------------

type Tab = "launch" | "sessions";

// ---------------------------------------------------------------------------
// LabPage — tab container
// ---------------------------------------------------------------------------

export function LabPage() {
  const location = useLocation();
  const navState = location.state as { strategyId?: string } | null;

  const [tab, setTab] = useState<Tab>(navState?.strategyId ? "launch" : "launch");
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  function handleLaunched(sessionId: string) {
    setActiveSessionId(sessionId);
    // Switch to sessions tab to see the running session
    setTab("sessions");
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Optimization Lab</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Launch optimizations and track results.
        </p>
      </div>

      {/* Tabs */}
      <div className="mb-6 flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden w-fit">
        <button
          onClick={() => setTab("launch")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            tab === "launch"
              ? "bg-blue-500 text-white"
              : "bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
          }`}
        >
          Launch
        </button>
        <button
          onClick={() => setTab("sessions")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            tab === "sessions"
              ? "bg-blue-500 text-white"
              : "bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
          }`}
        >
          Sessions
        </button>
      </div>

      {/* Tab content */}
      {tab === "launch" && (
        <div className="max-w-xl">
          <OptimizationLauncher
            initialStrategyId={navState?.strategyId}
            onLaunched={handleLaunched}
          />
        </div>
      )}

      {tab === "sessions" && <SessionHistory />}
    </div>
  );
}
