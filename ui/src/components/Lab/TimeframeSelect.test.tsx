import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TimeframeSelect, ALL_TIMEFRAMES } from "./TimeframeSelect.tsx";

describe("TimeframeSelect", () => {
  it("renders all timeframe buttons", () => {
    const onChange = vi.fn();
    render(<TimeframeSelect selected={[]} onChange={onChange} />);

    for (const tf of ALL_TIMEFRAMES) {
      expect(screen.getByRole("button", { name: tf })).toBeInTheDocument();
    }
  });

  it("displays correct count of timeframes", () => {
    const onChange = vi.fn();
    render(<TimeframeSelect selected={[]} onChange={onChange} />);

    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(ALL_TIMEFRAMES.length);
  });

  it("toggles timeframe selection on click", () => {
    const onChange = vi.fn();
    render(<TimeframeSelect selected={[]} onChange={onChange} />);

    const h1Btn = screen.getByRole("button", { name: "H1" });
    fireEvent.click(h1Btn);

    expect(onChange).toHaveBeenCalledWith(["H1"]);
  });

  it("removes timeframe on second click", () => {
    const onChange = vi.fn();
    const { rerender } = render(<TimeframeSelect selected={["H1"]} onChange={onChange} />);

    const h1Btn = screen.getByRole("button", { name: "H1" });
    fireEvent.click(h1Btn);

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("selects multiple timeframes", () => {
    const onChange = vi.fn();
    const { rerender } = render(<TimeframeSelect selected={[]} onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "H1" }));
    expect(onChange).toHaveBeenLastCalledWith(["H1"]);

    rerender(<TimeframeSelect selected={["H1"]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "H4" }));

    expect(onChange).toHaveBeenLastCalledWith(["H1", "H4"]);
  });

  it("highlights selected buttons as active", () => {
    const onChange = vi.fn();
    render(<TimeframeSelect selected={["H1", "D1"]} onChange={onChange} />);

    const h1Btn = screen.getByRole("button", { name: "H1" });
    const d1Btn = screen.getByRole("button", { name: "D1" });
    const m5Btn = screen.getByRole("button", { name: "M5" });

    expect(h1Btn).toHaveClass("bg-blue-500");
    expect(d1Btn).toHaveClass("bg-blue-500");
    expect(m5Btn).not.toHaveClass("bg-blue-500");
  });
});
