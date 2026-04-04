import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { OptimizationProgress } from "./OptimizationProgress.tsx";
import type { ProgressEvent } from "../../hooks/useSessionProgress.ts";

// Mock useSessionProgress hook
vi.mock("../../hooks/useSessionProgress.ts", () => ({
  useSessionProgress: vi.fn(),
}));

import { useSessionProgress } from "../../hooks/useSessionProgress.ts";

describe("OptimizationProgress", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders header and connection indicator", () => {
    (useSessionProgress as any).mockReturnValue({
      events: [],
      isConnected: true,
      latestProgress: null,
      isComplete: false,
    });

    render(<OptimizationProgress sessionId="session-123" />);

    expect(screen.getByText("Optimization running…")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("shows progress bar with percentage", () => {
    const mockProgress: ProgressEvent = {
      type: "progress",
      pct: 45,
      elapsed_seconds: 120,
      current: {
        instrument: "EURUSD",
        timeframe: "H1",
        iteration: 450,
        total: 1000,
      },
    };

    (useSessionProgress as any).mockReturnValue({
      events: [mockProgress],
      isConnected: true,
      latestProgress: mockProgress,
      isComplete: false,
    });

    render(<OptimizationProgress sessionId="session-123" />);

    expect(screen.getByText("45%")).toBeInTheDocument();
  });

  it("formats elapsed time correctly", () => {
    const mockProgress: ProgressEvent = {
      type: "progress",
      pct: 50,
      elapsed_seconds: 125, // 2m 5s
      current: {
        instrument: "EURUSD",
        timeframe: "H1",
        iteration: 500,
        total: 1000,
      },
    };

    (useSessionProgress as any).mockReturnValue({
      events: [mockProgress],
      isConnected: true,
      latestProgress: mockProgress,
      isComplete: false,
    });

    render(<OptimizationProgress sessionId="session-123" />);

    expect(screen.getByText("2m 5s elapsed")).toBeInTheDocument();
  });

  it("displays current task info", () => {
    const mockProgress: ProgressEvent = {
      type: "progress",
      pct: 50,
      elapsed_seconds: 60,
      current: {
        instrument: "EURUSD",
        timeframe: "H1",
        iteration: 450,
        total: 1000,
      },
    };

    (useSessionProgress as any).mockReturnValue({
      events: [mockProgress],
      isConnected: true,
      latestProgress: mockProgress,
      isComplete: false,
    });

    render(<OptimizationProgress sessionId="session-123" />);

    expect(screen.getByText("EURUSD H1")).toBeInTheDocument();
    expect(screen.getByText("450 / 1000")).toBeInTheDocument();
  });

  it("displays live results from stream", () => {
    const resultEvent1: ProgressEvent = {
      type: "result",
      instrument: "EURUSD",
      timeframe: "H1",
      metrics: {
        sharpe_ratio: 1.45,
        total_return_pct: 25.5,
        max_drawdown_pct: -8.2,
        profit_factor: 1.8,
      },
      params: { period: 14 },
    };

    const resultEvent2: ProgressEvent = {
      type: "result",
      instrument: "XAUUSD",
      timeframe: "H4",
      metrics: {
        sharpe_ratio: 0.85,
        total_return_pct: 12.3,
        max_drawdown_pct: -15.0,
        profit_factor: 1.3,
      },
      params: { period: 14 },
    };

    (useSessionProgress as any).mockReturnValue({
      events: [resultEvent1, resultEvent2],
      isConnected: true,
      latestProgress: null,
      isComplete: false,
    });

    render(<OptimizationProgress sessionId="session-123" />);

    expect(screen.getByText("Results (2)")).toBeInTheDocument();
    expect(screen.getByText("EURUSD")).toBeInTheDocument();
    expect(screen.getByText("XAUUSD")).toBeInTheDocument();
  });

  it("sorts results by Sharpe descending by default", () => {
    const event1: ProgressEvent = {
      type: "result",
      instrument: "A",
      timeframe: "H1",
      metrics: { sharpe_ratio: 0.5 } as any,
    };

    const event2: ProgressEvent = {
      type: "result",
      instrument: "B",
      timeframe: "H1",
      metrics: { sharpe_ratio: 1.5 } as any,
    };

    (useSessionProgress as any).mockReturnValue({
      events: [event1, event2],
      isConnected: true,
      latestProgress: null,
      isComplete: false,
    });

    render(<OptimizationProgress sessionId="session-123" />);

    // B (1.5 sharpe) should come before A (0.5 sharpe)
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("B"); // First data row
    expect(rows[2]).toHaveTextContent("A"); // Second data row
  });

  it("shows completion message when done", async () => {
    const completedEvent: ProgressEvent = {
      type: "completed",
      best_params: { period: 14, multiplier: 2.5 },
      best_metrics: {
        sharpe_ratio: 1.5,
      } as any,
    };

    (useSessionProgress as any).mockReturnValue({
      events: [completedEvent],
      isConnected: true,
      latestProgress: null,
      isComplete: true,
    });

    render(<OptimizationProgress sessionId="session-123" />);

    await waitFor(() => {
      expect(screen.getByText("✓ Optimization complete")).toBeInTheDocument();
    });
  });

  it("shows disconnected indicator when WebSocket is down", () => {
    (useSessionProgress as any).mockReturnValue({
      events: [],
      isConnected: false,
      latestProgress: null,
      isComplete: false,
    });

    render(<OptimizationProgress sessionId="session-123" />);

    expect(screen.getByText("Disconnected")).toBeInTheDocument();
  });

  it("calls onCompleted callback when optimization finishes", async () => {
    const onCompleted = vi.fn();

    const completedEvent: ProgressEvent = {
      type: "completed",
      best_params: { period: 14 },
    };

    (useSessionProgress as any).mockReturnValue({
      events: [completedEvent],
      isConnected: true,
      latestProgress: null,
      isComplete: true,
    });

    render(
      <OptimizationProgress sessionId="session-123" onCompleted={onCompleted} />
    );

    await waitFor(() => {
      expect(onCompleted).toHaveBeenCalled();
    });
  });

  it("limits results table to top 20", () => {
    const events: ProgressEvent[] = Array.from({ length: 30 }, (_, i) => ({
      type: "result",
      instrument: `INST${i}`,
      timeframe: "H1",
      metrics: {
        sharpe_ratio: Math.random(),
        total_return_pct: 10,
        max_drawdown_pct: -5,
      } as any,
    }));

    (useSessionProgress as any).mockReturnValue({
      events,
      isConnected: true,
      latestProgress: null,
      isComplete: false,
    });

    render(<OptimizationProgress sessionId="session-123" />);

    expect(screen.getByText("Results (30)")).toBeInTheDocument();
    expect(screen.getByText("… and 10 more (showing top 20)")).toBeInTheDocument();
  });
});
