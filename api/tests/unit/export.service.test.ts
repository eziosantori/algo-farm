import { describe, it, expect } from "vitest";
import { CTraderAdapter } from "../../src/services/export/ctrader.adapter.js";
import { PineAdapter } from "../../src/services/export/pine.adapter.js";
import { getExportAdapter } from "../../src/services/export/index.js";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";

// ---------------------------------------------------------------------------
// Fixture: simple SMA + RSI long-only strategy
// ---------------------------------------------------------------------------

const smaRsiStrategy: StrategyDefinition = {
  version: "1",
  name: "sma_rsi_basic",
  variant: "basic",
  indicators: [
    { name: "trend_sma", type: "sma", params: { period: 20 } },
    { name: "rsi14", type: "rsi", params: { period: 14 } },
  ],
  entry_rules: [
    { indicator: "close", condition: ">", compare_to: "trend_sma" },
    { indicator: "rsi14", condition: ">", value: 50 },
  ],
  exit_rules: [{ indicator: "rsi14", condition: "<", value: 40 }],
  position_management: {
    size: 0.02,
    sl_pips: 20,
    tp_pips: 40,
    max_open_trades: 1,
    trailing_sl_atr_mult: 2.0,
  },
  entry_rules_short: [],
  exit_rules_short: [],
  signal_gates: [],
  pattern_groups: [],
  suppression_gates: [],
  trigger_holds: [],
  param_overrides: {},
};

// Fixture: bidirectional strategy with ATR-based SL/TP
const biDirStrategy: StrategyDefinition = {
  version: "1",
  name: "ema_atr_bidi",
  variant: "advanced",
  indicators: [
    { name: "fast_ema", type: "ema", params: { period: 10 } },
    { name: "slow_ema", type: "ema", params: { period: 30 } },
    { name: "atr14", type: "atr", params: { period: 14 } },
  ],
  entry_rules: [
    { indicator: "fast_ema", condition: "crosses_above", compare_to: "slow_ema" },
  ],
  exit_rules: [
    { indicator: "fast_ema", condition: "crosses_below", compare_to: "slow_ema" },
  ],
  entry_rules_short: [
    { indicator: "fast_ema", condition: "crosses_below", compare_to: "slow_ema" },
  ],
  exit_rules_short: [
    { indicator: "fast_ema", condition: "crosses_above", compare_to: "slow_ema" },
  ],
  position_management: {
    size: 0.01,
    sl_atr_mult: 1.5,
    tp_atr_mult: 3.0,
    max_open_trades: 1,
    trailing_sl_atr_mult: 2.0,
  },
  signal_gates: [],
  pattern_groups: [],
  suppression_gates: [],
  trigger_holds: [],
  param_overrides: {},
};

// ---------------------------------------------------------------------------
// cTrader adapter tests
// ---------------------------------------------------------------------------

describe("CTraderAdapter", () => {
  const adapter = new CTraderAdapter();

  it("generates a valid C# file header", () => {
    const code = adapter.generate(smaRsiStrategy);
    expect(code).toContain("using cAlgo.API;");
    expect(code).toContain("[Robot(TimeZone = TimeZones.UTC");
    expect(code).toContain("public class SmaRsiBasic : Robot");
  });

  it("declares parameters for each indicator param", () => {
    const code = adapter.generate(smaRsiStrategy);
    expect(code).toContain("TrendSmaPeriod");
    expect(code).toContain("Rsi14Period");
    expect(code).toContain("SlPips");
    expect(code).toContain("TpPips");
  });

  it("declares private indicator fields", () => {
    const code = adapter.generate(smaRsiStrategy);
    expect(code).toContain("private SimpleMovingAverage _trendSma;");
    expect(code).toContain("private RelativeStrengthIndex _rsi14;");
  });

  it("generates OnStart with indicator initialization", () => {
    const code = adapter.generate(smaRsiStrategy);
    expect(code).toContain("protected override void OnStart()");
    expect(code).toContain(
      "_trendSma = Indicators.SimpleMovingAverage(Bars.ClosePrices, TrendSmaPeriod);"
    );
  });

  it("generates OnBar with entry and exit conditions", () => {
    const code = adapter.generate(smaRsiStrategy);
    expect(code).toContain("protected override void OnBar()");
    expect(code).toContain("Bars.ClosePrices.LastValue > _trendSma.Result.LastValue");
    // Threshold values are now exposed as C# parameters for per-pair opset tuning
    expect(code).toContain("_rsi14.Result.LastValue > Rsi14Threshold");
    expect(code).toContain("_rsi14.Result.LastValue < Rsi14Threshold2");
  });

  it("generates ATR-based SL/TP expressions", () => {
    const code = adapter.generate(biDirStrategy);
    expect(code).toContain("SlAtrMult");
    expect(code).toContain("TpAtrMult");
  });

  it("generates cross_above as prev-compare pattern", () => {
    const code = adapter.generate(biDirStrategy);
    expect(code).toContain("_prevFastEma");
    expect(code).toContain("_prevFastEma < _slowEma.Result.LastValue");
    expect(code).toContain("_fastEma.Result.LastValue >= _slowEma.Result.LastValue");
  });

  it("generates short-side entry/exit when entry_rules_short is non-empty", () => {
    const code = adapter.generate(biDirStrategy);
    expect(code).toContain(`"Short"`);
    expect(code).toContain("TradeType.Sell");
  });

  it("does NOT generate short-side code for long-only strategies", () => {
    const code = adapter.generate(smaRsiStrategy);
    expect(code).not.toContain("TradeType.Sell");
  });

  it("adds TODO comment for unsupported indicator types", () => {
    const stratWithSession: StrategyDefinition = {
      ...smaRsiStrategy,
      indicators: [
        ...smaRsiStrategy.indicators,
        { name: "london", type: "session_active", params: { session: "london" } },
      ],
    };
    const code = adapter.generate(stratWithSession);
    expect(code).toContain("TODO: implement custom indicator 'session_active'");
  });
});

// ---------------------------------------------------------------------------
// Pine adapter tests
// ---------------------------------------------------------------------------

describe("PineAdapter", () => {
  const adapter = new PineAdapter();

  it("generates Pine Script v5 header", () => {
    const code = adapter.generate(smaRsiStrategy);
    expect(code).toContain("//@version=5");
    expect(code).toContain('strategy("sma_rsi_basic"');
  });

  it("generates input declarations for indicator params", () => {
    const code = adapter.generate(smaRsiStrategy);
    expect(code).toContain("trendSmaPeriod = input.int(20");
    expect(code).toContain("rsi14Period = input.int(14");
  });

  it("generates indicator declarations", () => {
    const code = adapter.generate(smaRsiStrategy);
    expect(code).toContain("trendSma = ta.sma(close, trendSmaPeriod)");
    expect(code).toContain("rsi14 = ta.rsi(close, rsi14Period)");
  });

  it("generates longCondition and longExit", () => {
    const code = adapter.generate(smaRsiStrategy);
    expect(code).toContain("longCondition =");
    expect(code).toContain("close > trendSma");
    expect(code).toContain("rsi14 > 50");
    expect(code).toContain("longExit =");
    expect(code).toContain("rsi14 < 40");
  });

  it("generates strategy.entry and strategy.close calls", () => {
    const code = adapter.generate(smaRsiStrategy);
    expect(code).toContain('strategy.entry("Long", strategy.long)');
    expect(code).toContain('strategy.close("Long")');
  });

  it("generates crossover using ta.crossover", () => {
    const code = adapter.generate(biDirStrategy);
    expect(code).toContain("ta.crossover(fastEma, slowEma)");
    expect(code).toContain("ta.crossunder(fastEma, slowEma)");
  });

  it("generates short-side orders for bidirectional strategies", () => {
    const code = adapter.generate(biDirStrategy);
    expect(code).toContain('strategy.entry("Short", strategy.short)');
    expect(code).toContain('strategy.close("Short")');
  });
});

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

describe("getExportAdapter", () => {
  it("returns CTraderAdapter for 'ctrader'", () => {
    expect(getExportAdapter("ctrader")).toBeInstanceOf(CTraderAdapter);
  });

  it("returns PineAdapter for 'pine'", () => {
    expect(getExportAdapter("pine")).toBeInstanceOf(PineAdapter);
  });

  it("returns undefined for unknown format", () => {
    expect(getExportAdapter("metatrader")).toBeUndefined();
  });
});
