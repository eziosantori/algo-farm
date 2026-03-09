import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { WizardPage } from "./WizardPage.tsx";

const mockStore = {
  messages: [] as Array<{ role: "user" | "assistant"; content: string }>,
  currentStrategy: null,
  isLoading: false,
  error: null as string | null,
  model: "openrouter/free",
  availableModels: [
    {
      id: "openrouter/free",
      name: "OpenRouter Free",
      context_length: 128000,
      supports_tools: true,
      supports_tool_choice: true,
      source: "openrouter" as const,
    },
  ],
  isModelsLoading: false,
  modelsError: null as string | null,
  setModel: vi.fn(),
  loadModels: vi.fn().mockResolvedValue(undefined),
  sendMessage: vi.fn().mockResolvedValue(undefined),
  saveStrategy: vi.fn(),
};

vi.mock("../../store/wizard.ts", () => ({
  useWizardStore: () => mockStore,
}));

describe("WizardPage", () => {
  beforeAll(() => {
    HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  beforeEach(() => {
    mockStore.loadModels.mockClear();
    mockStore.setModel.mockClear();
  });

  it("shows only OpenRouter model selector and removes provider buttons", () => {
    render(
      <MemoryRouter>
        <WizardPage />
      </MemoryRouter>
    );

    expect(screen.getByText("OpenRouter model:")).toBeInTheDocument();
    expect(screen.queryByText("Provider:")).not.toBeInTheDocument();
    expect(screen.queryByText("Gemini")).not.toBeInTheDocument();
    expect(screen.queryByText("Claude")).not.toBeInTheDocument();
    expect(mockStore.loadModels).toHaveBeenCalledTimes(1);
  });
});
