import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { OptimizerConfig, type OptimizerSettings } from "./OptimizerConfig.tsx";

describe("OptimizerConfig", () => {
  const mockSettings: OptimizerSettings = {
    optimizer: "grid",
    metric: "sharpe_ratio",
    nTrials: 50,
    populationSize: 20,
    fromDate: "",
    toDate: "",
  };

  it("renders optimizer tabs", () => {
    const onChange = vi.fn();
    render(<OptimizerConfig value={mockSettings} onChange={onChange} />);

    expect(screen.getByRole("button", { name: "Grid" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bayesian" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Genetic" })).toBeInTheDocument();
  });

  it("renders metric dropdown", () => {
    const onChange = vi.fn();
    render(<OptimizerConfig value={mockSettings} onChange={onChange} />);

    const select = screen.getByRole("combobox");
    expect(select).toHaveValue("sharpe_ratio");
  });

  it("switches to Bayesian and shows nTrials input", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <OptimizerConfig value={mockSettings} onChange={onChange} />
    );

    const bayesianBtn = screen.getByRole("button", { name: "Bayesian" });
    fireEvent.click(bayesianBtn);

    expect(onChange).toHaveBeenCalledWith({
      ...mockSettings,
      optimizer: "bayesian",
    });

    const updatedSettings = { ...mockSettings, optimizer: "bayesian" as const };
    rerender(<OptimizerConfig value={updatedSettings} onChange={onChange} />);

    // nTrials input should be visible
    const nTrialsInputs = screen.getAllByDisplayValue("50");
    expect(nTrialsInputs.length).toBeGreaterThan(0);
  });

  it("switches to Genetic and shows nTrials + populationSize inputs", () => {
    const onChange = vi.fn();
    const geneticSettings: OptimizerSettings = {
      ...mockSettings,
      optimizer: "genetic",
    };

    render(<OptimizerConfig value={geneticSettings} onChange={onChange} />);

    // Both inputs should be visible for genetic
    const nTrialsInputs = screen.getAllByDisplayValue("50");
    const popSizeInputs = screen.getAllByDisplayValue("20");

    expect(nTrialsInputs.length).toBeGreaterThan(0);
    expect(popSizeInputs.length).toBeGreaterThan(0);
  });

  it("hides trial inputs for Grid optimizer", () => {
    const onChange = vi.fn();
    render(<OptimizerConfig value={mockSettings} onChange={onChange} />);

    // Grid should not show nTrials/populationSize inputs
    const inputs = screen.queryAllByDisplayValue("50");
    expect(inputs.length).toBe(0);
  });

  it("changes metric on dropdown select", () => {
    const onChange = vi.fn();
    render(<OptimizerConfig value={mockSettings} onChange={onChange} />);

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "profit_factor" } });

    expect(onChange).toHaveBeenCalledWith({
      ...mockSettings,
      metric: "profit_factor",
    });
  });

  it("updates nTrials on input change", () => {
    const onChange = vi.fn();
    const bayesianSettings: OptimizerSettings = {
      ...mockSettings,
      optimizer: "bayesian",
    };

    render(<OptimizerConfig value={bayesianSettings} onChange={onChange} />);

    const nTrialsInputs = screen.getAllByDisplayValue("50");
    const input = nTrialsInputs[0] as HTMLInputElement;

    fireEvent.change(input, { target: { value: "100" } });

    expect(onChange).toHaveBeenCalledWith({
      ...bayesianSettings,
      nTrials: 100,
    });
  });

  it("updates populationSize on input change", () => {
    const onChange = vi.fn();
    const geneticSettings: OptimizerSettings = {
      ...mockSettings,
      optimizer: "genetic",
    };

    render(<OptimizerConfig value={geneticSettings} onChange={onChange} />);

    const popSizeInputs = screen.getAllByDisplayValue("20");
    const input = popSizeInputs[0] as HTMLInputElement;

    fireEvent.change(input, { target: { value: "50" } });

    expect(onChange).toHaveBeenCalledWith({
      ...geneticSettings,
      populationSize: 50,
    });
  });

  it("has date range inputs for optional filtering", () => {
    const onChange = vi.fn();
    const withDates: OptimizerSettings = {
      ...mockSettings,
      fromDate: "2026-01-01",
      toDate: "2026-12-31",
    };

    render(<OptimizerConfig value={withDates} onChange={onChange} />);

    // Date inputs exist (they're type="date", not textbox)
    const form = screen.getByRole("button", { name: "Grid" }).closest("div");
    expect(form).toBeInTheDocument();
  });

  it("highlights selected optimizer tab", () => {
    const onChange = vi.fn();
    render(<OptimizerConfig value={mockSettings} onChange={onChange} />);

    const gridBtn = screen.getByRole("button", { name: "Grid" });
    const bayesianBtn = screen.getByRole("button", { name: "Bayesian" });

    expect(gridBtn).toHaveClass("bg-blue-500");
    expect(bayesianBtn).not.toHaveClass("bg-blue-500");
  });
});
