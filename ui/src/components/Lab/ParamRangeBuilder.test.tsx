import { describe, it, expect } from "vitest";
import {
  extractTunableParams,
  buildParamGrid,
  calculateComboCount,
  type ParamRangeState,
} from "./ParamRangeBuilder.tsx";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";

const mockStrategy: StrategyDefinition = {
  version: "1",
  name: "Test Strategy",
  variant: "basic",
  indicators: [
    {
      name: "rsi",
      type: "rsi",
      params: { period: 14 },
    },
    {
      name: "ema",
      type: "ema",
      params: { period: 20, multiplier: 2.5 },
    },
  ],
  entry_rules: [],
  exit_rules: [],
  position_management: {
    size: 0.02,
    sl_pips: 50,
    tp_pips: 100,
    sl_atr_mult: 2.0,
    max_open_trades: 1,
  },
};

describe("ParamRangeBuilder", () => {
  describe("extractTunableParams", () => {
    it("extracts numeric params from indicators", () => {
      const params = extractTunableParams(mockStrategy);

      const keys = params.map(p => p.key);
      expect(keys).toContain("rsi.period");
      expect(keys).toContain("ema.period");
      expect(keys).toContain("ema.multiplier");
    });

    it("extracts numeric fields from position_management", () => {
      const params = extractTunableParams(mockStrategy);

      const keys = params.map(p => p.key);
      expect(keys).toContain("sl_pips");
      expect(keys).toContain("tp_pips");
      expect(keys).toContain("sl_atr_mult");
    });

    it("sets correct current values", () => {
      const params = extractTunableParams(mockStrategy);

      const rsiPeriod = params.find(p => p.key === "rsi.period");
      expect(rsiPeriod?.currentValue).toBe(14);

      const emaMult = params.find(p => p.key === "ema.multiplier");
      expect(emaMult?.currentValue).toBe(2.5);

      const slPips = params.find(p => p.key === "sl_pips");
      expect(slPips?.currentValue).toBe(50);
    });

    it("initializes all params in fixed mode", () => {
      const params = extractTunableParams(mockStrategy);

      params.forEach(p => {
        expect(p.mode).toBe("fixed");
        expect(p.value).toBe(p.currentValue);
      });
    });
  });

  describe("buildParamGrid", () => {
    it("converts fixed params to scalars", () => {
      const ranges: ParamRangeState = {
        "rsi.period": {
          key: "rsi.period",
          label: "rsi → period",
          currentValue: 14,
          mode: "fixed",
          value: 14,
        },
      };

      const grid = buildParamGrid(ranges);
      expect(grid["rsi.period"]).toBe(14);
    });

    it("converts range params to arrays", () => {
      const ranges: ParamRangeState = {
        "rsi.period": {
          key: "rsi.period",
          label: "rsi → period",
          currentValue: 14,
          mode: "range",
          min: 10,
          max: 20,
          step: 5,
        },
      };

      const grid = buildParamGrid(ranges);
      expect(Array.isArray(grid["rsi.period"])).toBe(true);
      expect(grid["rsi.period"]).toEqual([10, 15, 20]);
    });

    it("converts list params to arrays", () => {
      const ranges: ParamRangeState = {
        "rsi.period": {
          key: "rsi.period",
          label: "rsi → period",
          currentValue: 14,
          mode: "list",
          values: [7, 14, 21],
        },
      };

      const grid = buildParamGrid(ranges);
      expect(grid["rsi.period"]).toEqual([7, 14, 21]);
    });

    it("handles mixed modes", () => {
      const ranges: ParamRangeState = {
        "rsi.period": {
          key: "rsi.period",
          label: "rsi → period",
          currentValue: 14,
          mode: "fixed",
          value: 14,
        },
        "ema.period": {
          key: "ema.period",
          label: "ema → period",
          currentValue: 20,
          mode: "range",
          min: 10,
          max: 30,
          step: 5,
        },
        "sl_pips": {
          key: "sl_pips",
          label: "Position → sl_pips",
          currentValue: 50,
          mode: "list",
          values: [30, 50, 80],
        },
      };

      const grid = buildParamGrid(ranges);
      expect(grid["rsi.period"]).toBe(14);
      expect(grid["ema.period"]).toEqual([10, 15, 20, 25, 30]);
      expect(grid["sl_pips"]).toEqual([30, 50, 80]);
    });
  });

  describe("calculateComboCount", () => {
    it("multiplies all param value counts", () => {
      const ranges: ParamRangeState = {
        "rsi.period": {
          key: "rsi.period",
          label: "rsi → period",
          currentValue: 14,
          mode: "list",
          values: [7, 14, 21], // 3 values
        },
        "ema.period": {
          key: "ema.period",
          label: "ema → period",
          currentValue: 20,
          mode: "range",
          min: 10,
          max: 20,
          step: 5, // 3 values (10, 15, 20)
        },
      };

      const comboCount = calculateComboCount(ranges, 2, 3); // 2 instruments, 3 timeframes
      expect(comboCount).toBe(3 * 3 * 2 * 3); // 3 * 3 * 2 * 3 = 54
    });

    it("counts fixed params as 1 value each", () => {
      const ranges: ParamRangeState = {
        "rsi.period": {
          key: "rsi.period",
          label: "rsi → period",
          currentValue: 14,
          mode: "fixed",
          value: 14,
        },
        "ema.period": {
          key: "ema.period",
          label: "ema → period",
          currentValue: 20,
          mode: "list",
          values: [10, 20, 30], // 3 values
        },
      };

      const comboCount = calculateComboCount(ranges, 2, 2);
      expect(comboCount).toBe(1 * 3 * 2 * 2); // 12
    });

    it("multiplies by instrument count", () => {
      const ranges: ParamRangeState = {
        "rsi.period": {
          key: "rsi.period",
          label: "rsi → period",
          currentValue: 14,
          mode: "list",
          values: [14], // 1 value
        },
      };

      const comboCount = calculateComboCount(ranges, 5, 1);
      expect(comboCount).toBe(1 * 5 * 1); // 5
    });

    it("multiplies by timeframe count", () => {
      const ranges: ParamRangeState = {
        "rsi.period": {
          key: "rsi.period",
          label: "rsi → period",
          currentValue: 14,
          mode: "list",
          values: [14], // 1 value
        },
      };

      const comboCount = calculateComboCount(ranges, 1, 5);
      expect(comboCount).toBe(1 * 1 * 5); // 5
    });
  });
});
