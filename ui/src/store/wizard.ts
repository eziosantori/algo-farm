import { create } from "zustand";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";
import { api, type OpenRouterModelOption } from "../api/client.ts";

export type ProviderId = "openrouter";
const DEFAULT_OPENROUTER_MODEL = "openrouter/free";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface WizardStore {
  messages: Message[];
  currentStrategy: StrategyDefinition | null;
  isLoading: boolean;
  error: string | null;
  model: string;
  availableModels: OpenRouterModelOption[];
  isModelsLoading: boolean;
  modelsError: string | null;
  setModel: (model: string) => void;
  loadModels: () => Promise<void>;
  sendMessage: (msg: string) => Promise<void>;
  saveStrategy: () => Promise<{ id: string }>;
  reset: () => void;
}

export const useWizardStore = create<WizardStore>((set, get) => ({
  messages: [],
  currentStrategy: null,
  isLoading: false,
  error: null,
  model: DEFAULT_OPENROUTER_MODEL,
  availableModels: [],
  isModelsLoading: false,
  modelsError: null,

  setModel(model: string) {
    set({ model });
  },

  async loadModels() {
    set({ isModelsLoading: true, modelsError: null });
    try {
      const response = await api.listOpenRouterFreeModels();
      const currentModel = get().model;
      const hasCurrentModel = response.models.some((m) => m.id === currentModel);
      const nextModel = hasCurrentModel
        ? currentModel
        : (response.models[0]?.id ?? DEFAULT_OPENROUTER_MODEL);

      set({
        availableModels: response.models,
        model: nextModel,
        isModelsLoading: false,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to load OpenRouter models";
      set({
        availableModels: [],
        model: DEFAULT_OPENROUTER_MODEL,
        isModelsLoading: false,
        modelsError: message,
      });
    }
  },

  async sendMessage(msg: string) {
    const { model } = get();
    set((s) => ({
      messages: [...s.messages, { role: "user", content: msg }],
      isLoading: true,
      error: null,
    }));

    try {
      const { strategy, explanation } = await api.wizardChat(msg, "openrouter", model);
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
