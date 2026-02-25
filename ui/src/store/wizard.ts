import { create } from "zustand";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";
import { api } from "../api/client.ts";

export type ProviderId = "claude" | "gemini" | "openrouter";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface WizardStore {
  messages: Message[];
  currentStrategy: StrategyDefinition | null;
  isLoading: boolean;
  error: string | null;
  provider: ProviderId;
  setProvider: (p: ProviderId) => void;
  sendMessage: (msg: string) => Promise<void>;
  saveStrategy: () => Promise<{ id: string }>;
  reset: () => void;
}

export const useWizardStore = create<WizardStore>((set, get) => ({
  messages: [],
  currentStrategy: null,
  isLoading: false,
  error: null,
  provider: "gemini",

  setProvider(p: ProviderId) {
    set({ provider: p });
  },

  async sendMessage(msg: string) {
    const { provider } = get();
    set((s) => ({
      messages: [...s.messages, { role: "user", content: msg }],
      isLoading: true,
      error: null,
    }));

    try {
      const { strategy, explanation } = await api.wizardChat(msg, provider);
      set((s) => ({
        messages: [...s.messages, { role: "assistant", content: explanation }],
        currentStrategy: strategy,
        isLoading: false,
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      set({ isLoading: false, error: message });
    }
  },

  async saveStrategy() {
    const { currentStrategy } = get();
    if (!currentStrategy) throw new Error("No strategy to save");
    return api.createStrategy(currentStrategy);
  },

  reset() {
    set({ messages: [], currentStrategy: null, isLoading: false, error: null });
  },
}));
