import type { IndicatorType } from "@algo-farm/shared/strategy";

// ---------------------------------------------------------------------------
// cTrader specs
// ---------------------------------------------------------------------------

export interface CTraderIndSpec {
  fieldType: string;
  /** Returns Indicators.XYZ(...) call; pp maps param key → C# property name */
  buildInit(fieldName: string, pp: Record<string, string>): string;
  /** Relative accessor, e.g. ".Result.LastValue" */
  accessor: string;
}

const CTRADER_SPECS: Partial<Record<IndicatorType, CTraderIndSpec>> = {
  sma: {
    fieldType: "SimpleMovingAverage",
    buildInit: (_fn, pp) =>
      `Indicators.SimpleMovingAverage(Bars.ClosePrices, ${pp["period"] ?? "20"})`,
    accessor: ".Result.LastValue",
  },
  ema: {
    fieldType: "ExponentialMovingAverage",
    buildInit: (_fn, pp) =>
      `Indicators.ExponentialMovingAverage(Bars.ClosePrices, ${pp["period"] ?? "20"})`,
    accessor: ".Result.LastValue",
  },
  rsi: {
    fieldType: "RelativeStrengthIndex",
    buildInit: (_fn, pp) =>
      `Indicators.RelativeStrengthIndex(Bars.ClosePrices, ${pp["period"] ?? "14"})`,
    accessor: ".Result.LastValue",
  },
  macd: {
    fieldType: "MacdCrossOver",
    buildInit: (_fn, pp) =>
      `Indicators.MacdCrossOver(Bars.ClosePrices, ${pp["slow_period"] ?? pp["long_period"] ?? "26"}, ${pp["fast_period"] ?? pp["short_period"] ?? "12"}, ${pp["signal_period"] ?? "9"})`,
    accessor: ".Histogram.LastValue",
  },
  atr: {
    fieldType: "AverageTrueRange",
    buildInit: (_fn, pp) =>
      `Indicators.AverageTrueRange(Bars, ${pp["period"] ?? "14"}, MovingAverageType.Exponential)`,
    accessor: ".Result.LastValue",
  },
  adx: {
    fieldType: "DirectionalMovementSystem",
    buildInit: (_fn, pp) =>
      `Indicators.DirectionalMovementSystem(Bars, ${pp["period"] ?? "14"})`,
    accessor: ".ADX.LastValue",
  },
  cci: {
    fieldType: "CommodityChannelIndex",
    buildInit: (_fn, pp) =>
      `Indicators.CommodityChannelIndex(Bars, ${pp["period"] ?? "20"}, MovingAverageType.Simple)`,
    accessor: ".Result.LastValue",
  },
  bollinger_bands: {
    fieldType: "BollingerBands",
    buildInit: (_fn, pp) =>
      `Indicators.BollingerBands(Bars.ClosePrices, ${pp["period"] ?? "20"}, ${pp["std_dev"] ?? "2"}, MovingAverageType.Simple)`,
    accessor: ".Main.LastValue",
  },
  bollinger_upper: {
    fieldType: "BollingerBands",
    buildInit: (_fn, pp) =>
      `Indicators.BollingerBands(Bars.ClosePrices, ${pp["period"] ?? "20"}, ${pp["std_dev"] ?? "2"}, MovingAverageType.Simple)`,
    accessor: ".Top.LastValue",
  },
  bollinger_lower: {
    fieldType: "BollingerBands",
    buildInit: (_fn, pp) =>
      `Indicators.BollingerBands(Bars.ClosePrices, ${pp["period"] ?? "20"}, ${pp["std_dev"] ?? "2"}, MovingAverageType.Simple)`,
    accessor: ".Bottom.LastValue",
  },
  bollinger_basis: {
    fieldType: "BollingerBands",
    buildInit: (_fn, pp) =>
      `Indicators.BollingerBands(Bars.ClosePrices, ${pp["period"] ?? "20"}, ${pp["std_dev"] ?? "2"}, MovingAverageType.Simple)`,
    accessor: ".Main.LastValue",
  },
  stoch: {
    fieldType: "StochasticOscillator",
    buildInit: (_fn, pp) =>
      `Indicators.StochasticOscillator(Bars, ${pp["k_period"] ?? pp["period"] ?? "14"}, ${pp["k_slowing"] ?? "3"}, ${pp["d_period"] ?? "3"}, MovingAverageType.Simple)`,
    accessor: ".PercentK.LastValue",
  },
};

// ---------------------------------------------------------------------------
// Pine Script specs
// ---------------------------------------------------------------------------

export interface PineIndSpec {
  /** Returns the indicator declaration line(s); inputs maps param key → Pine input var name */
  buildDecl(varName: string, inputs: Record<string, string>): string;
  accessor(varName: string): string;
}

const PINE_SPECS: Partial<Record<IndicatorType, PineIndSpec>> = {
  sma: {
    buildDecl: (v, i) => `${v} = ta.sma(close, ${i["period"] ?? "20"})`,
    accessor: (v) => v,
  },
  ema: {
    buildDecl: (v, i) => `${v} = ta.ema(close, ${i["period"] ?? "20"})`,
    accessor: (v) => v,
  },
  rsi: {
    buildDecl: (v, i) => `${v} = ta.rsi(close, ${i["period"] ?? "14"})`,
    accessor: (v) => v,
  },
  macd: {
    buildDecl: (v, i) =>
      `[${v}, ${v}Signal, ${v}Hist] = ta.macd(close, ${i["fast_period"] ?? i["short_period"] ?? "12"}, ${i["slow_period"] ?? i["long_period"] ?? "26"}, ${i["signal_period"] ?? "9"})`,
    accessor: (v) => `${v}Hist`,
  },
  atr: {
    buildDecl: (v, i) => `${v} = ta.atr(${i["period"] ?? "14"})`,
    accessor: (v) => v,
  },
  adx: {
    buildDecl: (v, i) =>
      `[${v}Plus, ${v}Minus, ${v}] = ta.dmi(${i["period"] ?? "14"}, ${i["period"] ?? "14"})`,
    accessor: (v) => v,
  },
  cci: {
    buildDecl: (v, i) => `${v} = ta.cci(hlc3, ${i["period"] ?? "20"})`,
    accessor: (v) => v,
  },
  bollinger_bands: {
    buildDecl: (v, i) =>
      `[${v}Upper, ${v}, ${v}Lower] = ta.bb(close, ${i["period"] ?? "20"}, ${i["std_dev"] ?? "2"})`,
    accessor: (v) => v,
  },
  bollinger_upper: {
    buildDecl: (v, i) =>
      `[${v}, _${v}Basis, _${v}Lower] = ta.bb(close, ${i["period"] ?? "20"}, ${i["std_dev"] ?? "2"})`,
    accessor: (v) => v,
  },
  bollinger_lower: {
    buildDecl: (v, i) =>
      `[_${v}Upper, _${v}Basis, ${v}] = ta.bb(close, ${i["period"] ?? "20"}, ${i["std_dev"] ?? "2"})`,
    accessor: (v) => v,
  },
  bollinger_basis: {
    buildDecl: (v, i) =>
      `[_${v}Upper, ${v}, _${v}Lower] = ta.bb(close, ${i["period"] ?? "20"}, ${i["std_dev"] ?? "2"})`,
    accessor: (v) => v,
  },
  stoch: {
    buildDecl: (v, i) =>
      `${v} = ta.stoch(close, high, low, ${i["k_period"] ?? i["period"] ?? "14"})`,
    accessor: (v) => v,
  },
};

export function getCTraderSpec(type: IndicatorType): CTraderIndSpec | undefined {
  return CTRADER_SPECS[type];
}

export function getPineSpec(type: IndicatorType): PineIndSpec | undefined {
  return PINE_SPECS[type];
}
