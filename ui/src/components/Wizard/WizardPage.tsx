import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useWizardStore } from "../../store/wizard.ts";
import type { ProviderId } from "../../store/wizard.ts";
import { StrategyPreview } from "./StrategyPreview.tsx";

const PROVIDER_OPTIONS: { value: ProviderId; label: string }[] = [
  { value: "gemini", label: "Gemini (free)" },
  { value: "claude", label: "Claude" },
  { value: "openrouter", label: "Qwen / OpenRouter (free)" },
];

export function WizardPage() {
  const [input, setInput] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { messages, currentStrategy, isLoading, error, provider, setProvider, sendMessage, saveStrategy } =
    useWizardStore();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const msg = input.trim();
    if (!msg || isLoading) return;
    setInput("");
    await sendMessage(msg);
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

  return (
    <div>
      <h1 style={styles.heading}>Strategy Wizard</h1>
      <p style={styles.subtitle}>
        Describe your trading strategy in natural language and an LLM will generate it for you.
      </p>

      {/* Provider selector */}
      <div style={styles.providerRow}>
        <label style={styles.providerLabel} htmlFor="provider-select">Provider:</label>
        <select
          id="provider-select"
          value={provider}
          onChange={(e) => setProvider(e.target.value as ProviderId)}
          style={styles.providerSelect}
          disabled={isLoading}
        >
          {PROVIDER_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Chat messages */}
      <div style={styles.chatBox}>
        {messages.length === 0 && (
          <p style={styles.placeholder}>
            Try: &ldquo;RSI strategy: enter long when RSI &lt; 30, exit when RSI &gt; 70&rdquo;
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} style={m.role === "user" ? styles.userMsg : styles.assistantMsg}>
            <span style={styles.roleLabel}>{m.role === "user" ? "You" : PROVIDER_OPTIONS.find((o) => o.value === provider)?.label ?? provider}</span>
            <p style={styles.msgContent}>{m.content}</p>
          </div>
        ))}
        {isLoading && (
          <div style={styles.assistantMsg}>
            <span style={styles.roleLabel}>{PROVIDER_OPTIONS.find((o) => o.value === provider)?.label ?? provider}</span>
            <p style={styles.msgContent}>Generating strategy…</p>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {error && <p style={styles.error}>{error}</p>}

      {/* Strategy preview */}
      {currentStrategy && (
        <div>
          <StrategyPreview strategy={currentStrategy} />
          <button
            onClick={handleSave}
            disabled={saveStatus === "saving" || saveStatus === "saved"}
            style={styles.saveBtn}
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
      )}

      {/* Input form */}
      <form onSubmit={handleSubmit} style={styles.form}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handleSubmit(e as unknown as React.FormEvent);
            }
          }}
          placeholder="Describe your strategy…"
          rows={3}
          disabled={isLoading}
          style={styles.textarea}
        />
        <button type="submit" disabled={isLoading || !input.trim()} style={styles.submitBtn}>
          {isLoading ? "Generating…" : "Generate"}
        </button>
      </form>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  heading: { marginBottom: "0.25rem" },
  subtitle: { color: "#6b7280", marginBottom: "0.75rem", marginTop: 0 },
  providerRow: { display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" },
  providerLabel: { fontSize: "0.85rem", color: "#374151", fontWeight: 500 },
  providerSelect: {
    padding: "0.25rem 0.5rem",
    borderRadius: "6px",
    border: "1px solid #d1d5db",
    fontSize: "0.85rem",
    cursor: "pointer",
  },
  chatBox: {
    border: "1px solid #e5e7eb",
    borderRadius: "8px",
    padding: "1rem",
    minHeight: "120px",
    maxHeight: "320px",
    overflowY: "auto",
    backgroundColor: "#fff",
    marginBottom: "1rem",
  },
  placeholder: { color: "#9ca3af", fontStyle: "italic", margin: 0 },
  userMsg: {
    backgroundColor: "#eff6ff",
    borderRadius: "6px",
    padding: "0.5rem 0.75rem",
    marginBottom: "0.5rem",
  },
  assistantMsg: {
    backgroundColor: "#f0fdf4",
    borderRadius: "6px",
    padding: "0.5rem 0.75rem",
    marginBottom: "0.5rem",
  },
  roleLabel: { fontSize: "0.7rem", fontWeight: "bold", textTransform: "uppercase", color: "#6b7280" },
  msgContent: { margin: "0.25rem 0 0", fontSize: "0.9rem" },
  error: { color: "#dc2626", marginBottom: "0.5rem" },
  saveBtn: {
    marginTop: "0.75rem",
    padding: "0.5rem 1.25rem",
    backgroundColor: "#16a34a",
    color: "#fff",
    border: "none",
    borderRadius: "6px",
    cursor: "pointer",
    fontWeight: "bold",
  },
  form: { marginTop: "1.5rem", display: "flex", gap: "0.75rem", alignItems: "flex-start" },
  textarea: {
    flex: 1,
    padding: "0.5rem 0.75rem",
    borderRadius: "6px",
    border: "1px solid #d1d5db",
    fontSize: "0.9rem",
    resize: "vertical",
    fontFamily: "inherit",
  },
  submitBtn: {
    padding: "0.5rem 1.25rem",
    backgroundColor: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: "6px",
    cursor: "pointer",
    fontWeight: "bold",
    alignSelf: "flex-end",
  },
};
