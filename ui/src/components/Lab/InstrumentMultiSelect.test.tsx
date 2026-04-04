import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { InstrumentMultiSelect } from "./InstrumentMultiSelect.tsx";

describe("InstrumentMultiSelect", () => {
  it("renders with placeholder when empty", () => {
    const onChange = vi.fn();
    render(
      <InstrumentMultiSelect selected={[]} onChange={onChange} />
    );
    expect(screen.getByPlaceholderText("Search instruments…")).toBeInTheDocument();
  });

  it("displays selected chips", () => {
    const onChange = vi.fn();
    render(
      <InstrumentMultiSelect selected={["EURUSD", "XAUUSD"]} onChange={onChange} />
    );
    expect(screen.getByText("EURUSD")).toBeInTheDocument();
    expect(screen.getByText("XAUUSD")).toBeInTheDocument();
  });

  it("shows placeholder text based on selection count", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <InstrumentMultiSelect selected={[]} onChange={onChange} />
    );

    const input = screen.getByPlaceholderText("Search instruments…") as HTMLInputElement;
    expect(input.placeholder).toBe("Search instruments…");

    rerender(
      <InstrumentMultiSelect selected={["EURUSD", "XAUUSD"]} onChange={onChange} />
    );

    const input2 = screen.getByPlaceholderText(/2 selected/i) as HTMLInputElement;
    expect(input2).toBeInTheDocument();
  });

  it("removes selected chip on X click", () => {
    const onChange = vi.fn();
    render(
      <InstrumentMultiSelect selected={["EURUSD"]} onChange={onChange} />
    );

    const removeButton = screen.getByText("×");
    fireEvent.click(removeButton);

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("toggles dropdown on input focus", () => {
    const onChange = vi.fn();
    render(
      <InstrumentMultiSelect selected={[]} onChange={onChange} />
    );

    const input = screen.getByPlaceholderText("Search instruments…");

    // Focus to show dropdown
    fireEvent.focus(input);
    expect(screen.getByText("Forex")).toBeInTheDocument();
  });

  it("filters instruments by search text", async () => {
    const onChange = vi.fn();
    render(
      <InstrumentMultiSelect selected={[]} onChange={onChange} />
    );

    const input = screen.getByPlaceholderText("Search instruments…") as HTMLInputElement;
    fireEvent.focus(input);

    // Type in the input
    fireEvent.change(input, { target: { value: "AU" } });

    // Searching for AU should show AUDUSD
    await waitFor(() => {
      expect(screen.getByText("AUDUSD")).toBeInTheDocument();
    });
    // Should not show instruments that don't match
    expect(screen.queryByText("EURUSD")).not.toBeInTheDocument();
  });
});
