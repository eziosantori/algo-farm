using System;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    /// <summary>
    /// BOT 2: SUPERTREND + RSI MOMENTUM (v0.9.3 - Trade Mode Selection)
    /// Strategia: SuperTrend per direzione + RSI per timing
    /// TP Logic:
    ///   1. No Fixed TP — let the trend run
    ///   2. Scaling-Out — partial close at ScaleOutTrigger × Risk
    ///   3. SuperTrend Trailing SL — SL tracks the ST line
    ///   4. Time Filter — exit if flat/loss after N candles
    ///   5. Regime Filter — Avoid chop using BB Width + ADX > 25
    ///   6. Cooldown — Pause after consecutive losses
    /// Best for: Volatile markets (Crypto, BTC)
    /// Timeframe: 1H, 4H
    /// </summary>
    public enum TradeMode
    {
        Both,
        LongOnly,
        ShortOnly
    }

    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None, AddIndicators = true)]
    public class Bot2_SuperTrendRSI : Robot
    {
        const string version = "0.9.3";

        #region PARAMETRI

        [Parameter("Label", DefaultValue = "default")]
        public string Label { get; set; }

        [Parameter("SuperTrend Period", DefaultValue = 10, MinValue = 5, MaxValue = 20)]
        public int StPeriod { get; set; }

        [Parameter("SuperTrend Mult", DefaultValue = 3.0, MinValue = 1.0, MaxValue = 5.0)]
        public double StMultiplier { get; set; }

        [Parameter("RSI Period", DefaultValue = 14, MinValue = 10, MaxValue = 20)]
        public int RsiPeriod { get; set; }

        [Parameter("Risk %", DefaultValue = 1.0, MinValue = 0.05, MaxValue = 5.0)]
        public double RiskPercent { get; set; }

        [Parameter("Stop Loss (ATR)", DefaultValue = 2.0, MinValue = 1.0, MaxValue = 5.0)]
        public double SlAtr { get; set; }

        [Parameter("Min ADX (Strength)", DefaultValue = 25, MinValue = 0, MaxValue = 50)]
        public int MinAdx { get; set; }

        [Parameter("EMA Filter Period", DefaultValue = 200, MinValue = 50, MaxValue = 500)]
        public int EmaPeriod { get; set; }

        // ── Advanced TP Parameters ─────────────────────────────────────────────

        [Parameter("ScaleOut % Volume", DefaultValue = 40, MinValue = 10, MaxValue = 60,
            Group = "Advanced TP")]
        public int ScaleOutPercent { get; set; }

        [Parameter("ScaleOut Trigger (×Risk)", DefaultValue = 1.5, MinValue = 1.0, MaxValue = 4.0,
            Group = "Advanced TP")]
        public double ScaleOutTrigger { get; set; }

        [Parameter("Time Exit (Candles)", DefaultValue = 12, MinValue = 5, MaxValue = 50,
            Group = "Advanced TP")]
        public int TimeExitCandles { get; set; }

        // ── Regime & Chop Filter ───────────────────────────────────────────────

        [Parameter("BB Period", DefaultValue = 20, MinValue = 10, MaxValue = 100, Group = "Regime Filter")]
        public int BbPeriod { get; set; }

        [Parameter("BB StdDev", DefaultValue = 2.0, MinValue = 1.0, MaxValue = 4.0, Group = "Regime Filter")]
        public double BbStdDev { get; set; }

        [Parameter("Min BB Width %", DefaultValue = 1.5, MinValue = 0.5, MaxValue = 5.0, Group = "Regime Filter")]
        public double MinBbWidthPercent { get; set; }

        [Parameter("Max Consecutive Losses", DefaultValue = 3, MinValue = 1, MaxValue = 10, Group = "Regime Filter")]
        public int MaxConsecutiveLosses { get; set; }

        [Parameter("Cooldown Candles", DefaultValue = 8, MinValue = 1, MaxValue = 48, Group = "Regime Filter")]
        public int CooldownCandles { get; set; }

        [Parameter("Trade Mode", DefaultValue = TradeMode.Both, Group = "Regime Filter")]
        public TradeMode Mode { get; set; }

        // ── Trading Hours (Indices/Forex) ──────────────────────────────────────

        [Parameter("Enable Trading Hours", DefaultValue = false, Group = "Trading Hours")]
        public bool EnableTimeFilter { get; set; }

        [Parameter("Start Hour (Server Time)", DefaultValue = 8, MinValue = 0, MaxValue = 23, Group = "Trading Hours")]
        public int StartHour { get; set; }

        [Parameter("End Hour (Server Time)", DefaultValue = 20, MinValue = 0, MaxValue = 23, Group = "Trading Hours")]
        public int EndHour { get; set; }

        #endregion

        private Supertrend st;
        private RelativeStrengthIndex rsi;
        private AverageTrueRange atr;
        private DirectionalMovementSystem adx;
        private ExponentialMovingAverage ema;
        private BollingerBands bb;

        private Position position;
        private int totalTrades = 0;
        private int wins = 0;
        private bool wasInUpTrend = false;
        private bool wasInDownTrend = false;

        // ── Advanced TP State ──────────────────────────────────────────────────
        private int entryBarIndex = -1;         // Bar index when position was opened
        private bool scaledOut = false;          // Prevents multiple partial closes
        private double initialSlDistance = 0;   // SL distance in price at entry

        // ── Regime Filter State ────────────────────────────────────────────────
        private int consecutiveLosses = 0;
        private int cooldownExpirationBar = -1;

        protected override void OnStart()
        {
            Print("╔════════════════════════════════╗");
            Print("║  BOT 2: ST + RSI (Advanced TP) ║");
            Print("╚════════════════════════════════╝");
            Print($"Label: {Label} | Version: {version}");

            st  = Indicators.Supertrend(StPeriod, StMultiplier);
            rsi = Indicators.RelativeStrengthIndex(Bars.ClosePrices, RsiPeriod);
            atr = Indicators.AverageTrueRange(14, MovingAverageType.Simple);
            adx = Indicators.DirectionalMovementSystem(14);
            ema = Indicators.ExponentialMovingAverage(Bars.ClosePrices, EmaPeriod);
            bb  = Indicators.BollingerBands(Bars.ClosePrices, BbPeriod, BbStdDev, MovingAverageType.Simple);

            Positions.Closed += OnPosClosed;
        }

        protected override void OnBar()
        {
            position = Positions.Find("B2", SymbolName);

            bool isUpTrend   = st.UpTrend.Last(1) != double.NaN   && st.UpTrend.Last(1) > 0;
            bool isDownTrend = st.DownTrend.Last(1) != double.NaN && st.DownTrend.Last(1) > 0;

            double rsiVal   = rsi.Result.Last(1);
            double adxVal   = adx.ADX.Last(1);
            double emaVal   = ema.Result.Last(1);
            double closePrice = Bars.ClosePrices.Last(1);

            if (position == null)
            {
                // COOLDOWN: Wait if we had too many recent consecutive losses
                if (Bars.Count < cooldownExpirationBar)
                    return;

                // FILTER: Trend Strength (ADX)
                if (adxVal < MinAdx)
                    return;

                // FILTER: Regime Volatility (Bollinger Band Width)
                // In tight ranges, BB width contracts. Avoid trading then.
                double bbTop = bb.Top.Last(1);
                double bbBottom = bb.Bottom.Last(1);
                double bbMid = bb.Main.Last(1);
                double bbWidthPercent = ((bbTop - bbBottom) / bbMid) * 100.0;

                if (bbWidthPercent < MinBbWidthPercent)
                    return;

                // FILTER: Trading Hours (e.g., for Indices/Forex to avoid Asian session chop)
                if (EnableTimeFilter && !IsWithinTradingHours(Server.Time))
                    return;

                // LONG: New UpTrend + RSI > 50 + Price > EMA
                if (Mode != TradeMode.ShortOnly && isUpTrend && wasInDownTrend && rsiVal > 50 && closePrice > emaVal)
                    OpenTrade(TradeType.Buy);

                // SHORT: New DownTrend + RSI < 50 + Price < EMA
                if (Mode != TradeMode.LongOnly && isDownTrend && wasInUpTrend && rsiVal < 50 && closePrice < emaVal)
                    OpenTrade(TradeType.Sell);
            }
            else
            {
                ManagePosition();
            }

            wasInUpTrend   = isUpTrend;
            wasInDownTrend = isDownTrend;

            UpdateInfo();
        }

        // ──────────────────────────────────────────────────────────────────────
        //  MANAGE POSITION  (4-component Advanced TP)
        // ──────────────────────────────────────────────────────────────────────
        private void ManagePosition()
        {
            if (position == null) return;

            double currentPrice = position.TradeType == TradeType.Buy ? Symbol.Bid : Symbol.Ask;
            double profitDistance = position.TradeType == TradeType.Buy
                ? currentPrice - position.EntryPrice
                : position.EntryPrice - currentPrice;

            int barsElapsed = Bars.Count - 1 - entryBarIndex;

            // ── COMPONENT 4: Time Filter ──────────────────────────────────────
            // Exit if still flat or in loss after N candles
            if (barsElapsed >= TimeExitCandles && position.NetProfit <= 0)
            {
                ClosePosition(position);
                Print($"⏱️ Time filter exit | Bars: {barsElapsed} | P/L: {position.NetProfit:F2}");
                return;
            }

            // ── COMPONENT 2: Scaling-Out ──────────────────────────────────────
            // Partial close when profit >= ScaleOutTrigger × initial SL distance
            if (!scaledOut && initialSlDistance > 0 && profitDistance >= ScaleOutTrigger * initialSlDistance)
            {
                double scaleVolume = position.VolumeInUnits * (ScaleOutPercent / 100.0);
                scaleVolume = Symbol.NormalizeVolumeInUnits(scaleVolume, RoundingMode.Down);
                scaleVolume = Math.Max(scaleVolume, Symbol.VolumeInUnitsMin);

                if (scaleVolume < position.VolumeInUnits)
                {
                    ClosePosition(position, scaleVolume);
                    scaledOut = true;

                    // Refresh position reference after partial close
                    position = Positions.Find("B2", SymbolName);
                    if (position != null)
                    {
                        // Move SL to Breakeven on remaining position
                        ModifyPosition(position, position.EntryPrice, position.TakeProfit);
                        Print($"📊 ScaleOut {ScaleOutPercent}% @ {ScaleOutTrigger}×Risk | SL → Breakeven");
                    }
                }
                else
                {
                    // Volume too small to split — close entirely
                    ClosePosition(position);
                    Print("📊 ScaleOut: volume too small, full close");
                    return;
                }
            }

            // Re-fetch position (may have been partially closed above)
            position = Positions.Find("B2", SymbolName);
            if (position == null) return;

            // ── COMPONENT 3: SuperTrend Trailing SL ──────────────────────────
            // Trail the SL to follow the SuperTrend line
            TrailStopToSuperTrend();

            // ── COMPONENT 1 (Hard Exit): SuperTrend Reversal ─────────────────
            bool stInverted = false;
            if (position.TradeType == TradeType.Buy)
                stInverted = st.DownTrend.Last(1) != double.NaN && st.DownTrend.Last(1) > 0;
            else
                stInverted = st.UpTrend.Last(1) != double.NaN && st.UpTrend.Last(1) > 0;

            if (stInverted)
            {
                ClosePosition(position);
                Print("🔄 Exit: SuperTrend reversal");
            }
        }

        // ──────────────────────────────────────────────────────────────────────
        //  TRAIL SL TO SUPERTREND LINE
        // ──────────────────────────────────────────────────────────────────────
        private void TrailStopToSuperTrend()
        {
            if (position == null) return;

            double? newSl = null;

            if (position.TradeType == TradeType.Buy)
            {
                // For longs: use the UpTrend line (support) — it rises over time
                double stLine = st.UpTrend.Last(1);
                if (stLine != double.NaN && stLine > 0)
                {
                    // Only trail upward (never lower the SL)
                    double? currentSl = position.StopLoss;
                    if (currentSl == null || stLine > currentSl.Value)
                        newSl = stLine;
                }
            }
            else
            {
                // For shorts: use the DownTrend line (resistance) — it falls over time
                double stLine = st.DownTrend.Last(1);
                if (stLine != double.NaN && stLine > 0)
                {
                    double? currentSl = position.StopLoss;
                    if (currentSl == null || stLine < currentSl.Value)
                        newSl = stLine;
                }
            }

            if (newSl.HasValue)
            {
                ModifyPosition(position, newSl.Value, position.TakeProfit);
            }
        }

        // ──────────────────────────────────────────────────────────────────────
        //  OPEN TRADE  (no fixed TP)
        // ──────────────────────────────────────────────────────────────────────
        private void OpenTrade(TradeType type)
        {
            double atrValue = atr.Result.Last(1);
            double slPips   = (atrValue * SlAtr) / Symbol.PipSize;

            double volume = CalculateVolume(slPips);

            // Open without fixed TP (0 = no TP)
            var result = ExecuteMarketOrder(type, SymbolName, volume, "B2", slPips, null);

            if (result.IsSuccessful)
            {
                // Track entry state
                entryBarIndex    = Bars.Count - 1;
                scaledOut        = false;
                initialSlDistance = atrValue * SlAtr;   // SL distance in price units

                Print($"OPEN {type} | SL: {slPips:F1} pips | ADX: {adx.ADX.Last(1):F1} | RSI: {rsi.Result.Last(1):F1}");
                Print($"  → ScaleOut trigger: {ScaleOutTrigger}×{initialSlDistance:F4} = {ScaleOutTrigger * initialSlDistance:F4}");
                Print($"  → Time filter: exit if flat after {TimeExitCandles} candles");
            }
        }

        // ──────────────────────────────────────────────────────────────────────
        //  HELPERS
        // ──────────────────────────────────────────────────────────────────────
        
        private bool IsWithinTradingHours(DateTime currentTime)
        {
            // Simple check assuming StartHour < EndHour (e.g., 08:00 to 20:59)
            // If overnight trading is needed (e.g., 22 - 06), logic needs adjustment
            if (StartHour <= EndHour)
            {
                return (currentTime.Hour >= StartHour && currentTime.Hour <= EndHour);
            }
            else // Overnight case (e.g. Start 22, End 06)
            {
                return (currentTime.Hour >= StartHour || currentTime.Hour <= EndHour);
            }
        }

        private double CalculateVolume(double slPips)
        {
            double riskAmount = Account.Balance * (RiskPercent / 100.0);
            double volume     = riskAmount / (slPips * Symbol.PipValue);

            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
            volume = Math.Max(volume, Symbol.VolumeInUnitsMin);
            volume = Math.Min(volume, Symbol.VolumeInUnitsMax);

            return volume;
        }

        private void OnPosClosed(PositionClosedEventArgs args)
        {
            if (args.Position.Label != "B2") return;
            totalTrades++;
            
            if (args.Position.NetProfit > 0) 
            {
                wins++;
                consecutiveLosses = 0; // Reset streak
            }
            else 
            {
                consecutiveLosses++;
                if (consecutiveLosses >= MaxConsecutiveLosses)
                {
                    cooldownExpirationBar = Bars.Count + CooldownCandles;
                    Print($"⚠️ Max consecutive losses ({consecutiveLosses})! Cooling down for {CooldownCandles} candles.");
                    consecutiveLosses = 0; // Reset after triggering cooldown
                }
            }
            
            Print($"CLOSED | P/L: {args.Position.NetProfit:F2} | Reason: {args.Reason}");
        }

        private void UpdateInfo()
        {
            position = Positions.Find("B2", SymbolName);
            if (position == null) return;

            int barsElapsed = Bars.Count - 1 - entryBarIndex;
            string scaleTag = scaledOut ? " [ScaledOut]" : "";
            string info = $"B2 v{version} | {position.TradeType} | P/L: {position.NetProfit:F2} | Bars: {barsElapsed}/{TimeExitCandles}{scaleTag}";
            Chart.DrawStaticText("hud", info, VerticalAlignment.Top, HorizontalAlignment.Right, Color.Yellow);
        }

        protected override void OnStop()
        {
            double winRate = totalTrades > 0 ? (wins * 100.0 / totalTrades) : 0;
            Print($"STOPPED | Trades: {totalTrades} | Wins: {wins} | WinRate: {winRate:F1}%");
        }
    }
}
