import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useWizardStore } from "../../store/wizard.ts";
import { StrategyPreview } from "./StrategyPreview.tsx";

const EXAMPLES = [
  "RSI strategy: enter long when RSI < 30, exit when RSI > 70",
  "SuperTrend + RSI: enter when SuperTrend is bullish and RSI > 50",
  "EMA crossover: buy when EMA 20 crosses above EMA 50",
];

export function WizardPage() {
  const [input, setInput] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">(
    "idle"
  );
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    currentStrategy,
    isLoading,
    error,
    model,
    availableModels,
    isModelsLoading,
    modelsError,
    setModel,
    loadModels,
    sendMessage,
    saveStrategy,
  } = useWizardStore();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    void loadModels();
  }, [loadModels]);

  async function generate() {
    const msg = input.trim();
    if (!msg || isLoading) return;
    setInput("");
    await sendMessage(msg);
  }

  function handleSubmit(e: React.SyntheticEvent) {
    e.preventDefault();
    void generate();
  }

  async function handleSave() {
    setSaveStatus("saving");
    try {
      await saveStrategy();
      setSaveStatus("saved");
      setTimeout(() => navigate("/strategies"), 1000);
    } catch {
      setSaveStatus("error");
    }
  }

  const modelLabel =
    availableModels.find((option) => option.id === model)?.name ?? model;

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Strategy Wizard
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Describe your trading strategy in natural language — the LLM will generate it for you.
        </p>
      </div>

      {/* OpenRouter model selector */}
      <div className="grid grid-cols-1 md:grid-cols-[auto_1fr] items-center gap-2 mb-4">
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          OpenRouter model:
        </span>
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={isLoading || isModelsLoading}
              className="min-w-[320px] max-w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 disabled:opacity-60"
            >
              {availableModels.length === 0 && (
                <option value="openrouter/free">openrouter/free</option>
              )}
              {availableModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.id})
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => void loadModels()}
              disabled={isLoading || isModelsLoading}
              className="px-3 py-2 rounded-lg text-xs font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700 disabled:opacity-50"
            >
              {isModelsLoading ? "Refreshing…" : "Refresh"}
            </button>
          </div>
          {modelsError && (
            <p className="text-xs text-amber-700 dark:text-amber-400">
              Model list unavailable, using fallback `openrouter/free`: {modelsError}
            </p>
          )}
        </div>
      </div>

      {/* Chat messages */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 min-h-[160px] max-h-[340px] overflow-y-auto p-4 mb-4">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center gap-3 py-4">
            <p className="text-sm text-gray-400 dark:text-gray-500 italic text-center">
              Describe your strategy below, or try one of these examples:
            </p>
            <div className="flex flex-col gap-1.5 w-full max-w-md">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => setInput(ex)}
                  className="text-left text-xs px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-blue-50 hover:text-blue-700 dark:hover:bg-blue-900/30 dark:hover:text-blue-300 transition-colors border border-gray-200 dark:border-gray-700"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`mb-3 ${m.role === "user" ? "flex justify-end" : "flex justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-xl px-4 py-2.5 ${
                m.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200"
              }`}
            >
              <p className={`text-[10px] font-semibold uppercase tracking-wide mb-1 ${
                m.role === "user" ? "text-blue-200" : "text-gray-400"
              }`}>
                {m.role === "user" ? "You" : `OpenRouter (${modelLabel})`}
              </p>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{m.content}</p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start mb-3">
            <div className="bg-gray-100 dark:bg-gray-800 rounded-xl px-4 py-2.5">
              <p className="text-[10px] font-semibold uppercase tracking-wide mb-1 text-gray-400">
                {`OpenRouter (${modelLabel})`}
              </p>
              <div className="flex items-center gap-1.5">
                {[0, 1, 2].map((n) => (
                  <span
                    key={n}
                    className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce"
                    style={{ animationDelay: `${n * 150}ms` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 px-4 py-2.5 text-sm text-red-700 dark:text-red-400">
          <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd"/>
          </svg>
          {error}
        </div>
      )}

      {/* Input form */}
      <form onSubmit={handleSubmit} className="flex gap-2 items-end">
        <div className="flex-1">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void generate();
              }
            }}
            placeholder="Describe your strategy… (Enter to send, Shift+Enter for newline)"
            rows={3}
            disabled={isLoading}
            className="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-4 py-3 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-60 resize-none"
          />
        </div>
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="flex-shrink-0 px-5 py-3 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? "Generating…" : "Generate"}
        </button>
      </form>

      {/* Strategy preview */}
      {currentStrategy && (
        <div className="mt-4">
          <StrategyPreview strategy={currentStrategy} />
          <div className="mt-3 flex justify-end">
            <button
              onClick={handleSave}
              disabled={saveStatus === "saving" || saveStatus === "saved"}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors disabled:cursor-not-allowed ${
                saveStatus === "saved"
                  ? "bg-green-600 text-white"
                  : saveStatus === "error"
                    ? "bg-red-600 text-white hover:bg-red-700"
                    : "bg-green-600 text-white hover:bg-green-700 disabled:opacity-60"
              }`}
            >
              {saveStatus === "saving"
                ? "Saving…"
                : saveStatus === "saved"
                  ? "Saved! Redirecting…"
                  : saveStatus === "error"
                    ? "Error — retry"
                    : "Save Strategy"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
