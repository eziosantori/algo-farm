import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { OptimizationLauncher } from "./OptimizationLauncher.tsx";
import * as apiClient from "../../api/client.ts";

vi.mock("../../api/client.ts", () => ({
  api: {
    listStrategies: vi.fn(),
    getStrategy: vi.fn(),
    createLabSession: vi.fn(),
    runLabSession: vi.fn(),
  },
}));

const mockStrategy = {
  id: "strat-1",
  name: "Test RSI",
  variant: "basic",
  indicators: [
    { name: "rsi", type: "rsi", params: { period: 14 } },
  ],
  entry_rules: [{ indicator: "rsi", condition: "<", value: 30 }],
  exit_rules: [{ indicator: "rsi", condition: ">", value: 70 }],
  position_management: { size: 0.02, sl_pips: 50, tp_pips: 100 },
};

describe("OptimizationLauncher", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.api.listStrategies as any).mockResolvedValue({
      strategies: [
        { id: "strat-1", name: "Test RSI", variant: "basic", lifecycle_status: "validated" },
      ],
    });
    (apiClient.api.getStrategy as any).mockResolvedValue({
      id: "strat-1",
      definition: mockStrategy,
      created_at: "2026-01-01",
      updated_at: "2026-01-01",
    });
  });

  it("renders form with strategy selector", async () => {
    const onLaunched = vi.fn();
    render(<OptimizationLauncher onLaunched={onLaunched} />);

    expect(screen.getByText("Strategy")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search instruments…")).toBeInTheDocument();
  });

  it("disables launch button initially", () => {
    const onLaunched = vi.fn();
    render(<OptimizationLauncher onLaunched={onLaunched} />);

    const launchBtn = screen.getByRole("button", { name: /Launch Optimization/ });
    expect(launchBtn).toBeDisabled();
  });

  it("shows loading state for strategies", () => {
    const onLaunched = vi.fn();
    render(<OptimizationLauncher onLaunched={onLaunched} />);

    expect(screen.getByText("Loading strategies…")).toBeInTheDocument();
  });

  it("calls api.listStrategies on mount", async () => {
    const onLaunched = vi.fn();
    render(<OptimizationLauncher onLaunched={onLaunched} />);

    await waitFor(() => {
      expect(apiClient.api.listStrategies).toHaveBeenCalled();
    });
  });
});
