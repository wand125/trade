//+------------------------------------------------------------------+
//| Swing_Evaluation_Predictor.mq5                                   |
//| Chart-only prediction overlay. No bridge, no GPT, no trading.    |
//+------------------------------------------------------------------+
#property strict
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots 0

input int InpEvaluateEverySeconds = 5;
input int InpLookbackBars = 180;
input int InpSwingDepth = 3;
input int InpFastEmaPeriod = 9;
input int InpSlowEmaPeriod = 21;
input int InpRsiPeriod = 14;
input int InpAtrPeriod = 14;
input double InpSwingAtrBand = 0.80;

input double InpMinScore = 50.0;
input double InpMinDominance = 0.0;
input int InpScoreTrendM30 = 18;
input int InpScoreTrendM15 = 22;
input int InpScoreTrendSlope = 8;
input int InpScoreTrendM5 = 8;
input int InpScoreRsiTurn = 12;
input int InpScoreRsiM5 = 5;
input int InpScoreSwingReversal = 15;
input int InpScoreBreakConfirm = 6;
input int InpScoreRiskPlan = 15;
input int InpScoreRiskPenalty = 20;

input double InpBuyRsiMin = 38.0;
input double InpBuyRsiMax = 66.0;
input double InpSellRsiMin = 34.0;
input double InpSellRsiMax = 62.0;

input bool InpUseVariableRiskReward = true;
input bool InpUseSideRiskReward = true;
input double InpRiskReward = 4.0;
input double InpBuyRiskReward = 4.0;
input double InpSellRiskReward = 5.0;
input double InpMinRiskReward = 3.0;
input double InpMaxRiskReward = 5.0;
input double InpScoreForRR4 = 78.0;
input double InpScoreForRR5 = 88.0;
input int InpMinStopPoints = 25;
input int InpMaxStopPoints = 300;
input int InpStopBufferPoints = 30;
input int InpMaxSpreadPoints = 80;

input bool InpUseRolloverFilter = true;
input int InpRolloverStartHour = 23;
input int InpRolloverStartMinute = 55;
input int InpRolloverEndHour = 0;
input int InpRolloverEndMinute = 10;

input bool InpUseFittedSellFilter = true;
input double InpSellMinM5CloseSlowAtr = -3.2145;
input double InpSellMinM1AlternatingRatio = 0.33333;
input bool InpUseFittedSellTrendFilter = false;
input bool InpUseSellM30M15DownGate = false;
input bool InpUseFittedSellTimeFilter = false;
input string InpSellBlockedServerHours = "1,9,10,13,14,16,20";
input bool InpUseFittedSellCalendarFilter = false;
input string InpSellBlockedMonths = "3,6,12";
input string InpSellBlockedWeekdays = "3";
input bool InpUseSellAllowedServerHours = false;
input string InpSellAllowedServerHours = "";
input bool InpUseFittedSellEntryFilter = false;
input bool InpSellRequireBreakConfirm = true;
input double InpSellMaxM1ClosePosition = 0.35;
input double InpSellMinM1BodyAtr = 0.10;
input double InpSellMaxM5CloseSlowAtr = 0.0;
input bool InpUseFittedBuyBreakFilter = false;
input bool InpUseBuyM30M15UpGate = false;
input bool InpUseFittedBuyEntryFilter = false;
input bool InpBuyRequireBreakConfirm = true;
input double InpBuyMinM1ClosePosition = 0.65;
input double InpBuyMinM1BodyAtr = 0.10;
input double InpBuyMinM5CloseSlowAtr = 0.0;
input bool InpUseFittedBuyTimeFilter = false;
input string InpBuyBlockedServerHours = "2,7,15,18,19,20,23";
input bool InpUseFittedBuyCalendarFilter = false;
input string InpBuyBlockedMonths = "6,8,10";
input string InpBuyBlockedWeekdays = "3,5";
input bool InpUseBuyAllowedServerHours = false;
input string InpBuyAllowedServerHours = "";

input bool InpDrawDryRunOrderLines = true;
input bool InpClearLinesOnHold = true;
input int InpLineValidSeconds = 120;
input string InpObjectPrefix = "SEP_";
input bool InpPanelUsePercentPosition = true;
input double InpPanelLeftPercent = 0.0;
input double InpPanelTopPercent = 80.0;
input ENUM_BASE_CORNER InpPanelCorner = CORNER_LEFT_UPPER;
input int InpPanelX = 0;
input int InpPanelY = 0;
input int InpPanelWidth = 540;
input int InpPanelHeight = 168;
input int InpPanelPadding = 6;
input int InpPanelLineHeight = 18;
input int InpPanelFontSize = 8;
input int InpPanelDetailFontSize = 7;
input int InpPanelScoreFontSize = 10;
input color InpPanelBackgroundColor = C'18,24,30';
input color InpPanelPrimaryColor = clrGold;

datetime LastEvaluationTime = 0;

int EmaFastM5Handle = INVALID_HANDLE;
int EmaSlowM5Handle = INVALID_HANDLE;
int EmaFastM15Handle = INVALID_HANDLE;
int EmaSlowM15Handle = INVALID_HANDLE;
int EmaFastM30Handle = INVALID_HANDLE;
int EmaSlowM30Handle = INVALID_HANDLE;
int RsiM1Handle = INVALID_HANDLE;
int RsiM5Handle = INVALID_HANDLE;
int AtrM1Handle = INVALID_HANDLE;
int AtrM5Handle = INVALID_HANDLE;

struct TradePlan
{
   bool valid;
   string action;
   double entry;
   double sl;
   double tp;
   double rr;
   double stop_points;
   string reason;
};

struct EvaluationResult
{
   string action;
   bool tradable;
   double score;
   double buy_score;
   double sell_score;
   double entry;
   double sl;
   double tp;
   double rr;
   double stop_points;
   datetime signal_time;
   string reason;
   string buy_reason;
   string sell_reason;
   string m30_trend;
   string m15_trend;
};

int OnInit()
{
   IndicatorSetString(INDICATOR_SHORTNAME, "Swing Evaluation Predictor");

   EmaFastM5Handle = iMA(_Symbol, PERIOD_M5, InpFastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   EmaSlowM5Handle = iMA(_Symbol, PERIOD_M5, InpSlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   EmaFastM15Handle = iMA(_Symbol, PERIOD_M15, InpFastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   EmaSlowM15Handle = iMA(_Symbol, PERIOD_M15, InpSlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   EmaFastM30Handle = iMA(_Symbol, PERIOD_M30, InpFastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   EmaSlowM30Handle = iMA(_Symbol, PERIOD_M30, InpSlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   RsiM1Handle = iRSI(_Symbol, PERIOD_M1, InpRsiPeriod, PRICE_CLOSE);
   RsiM5Handle = iRSI(_Symbol, PERIOD_M5, InpRsiPeriod, PRICE_CLOSE);
   AtrM1Handle = iATR(_Symbol, PERIOD_M1, InpAtrPeriod);
   AtrM5Handle = iATR(_Symbol, PERIOD_M5, InpAtrPeriod);

   if(EmaFastM5Handle == INVALID_HANDLE || EmaSlowM5Handle == INVALID_HANDLE ||
      EmaFastM15Handle == INVALID_HANDLE || EmaSlowM15Handle == INVALID_HANDLE ||
      EmaFastM30Handle == INVALID_HANDLE || EmaSlowM30Handle == INVALID_HANDLE ||
      RsiM1Handle == INVALID_HANDLE || RsiM5Handle == INVALID_HANDLE ||
      AtrM1Handle == INVALID_HANDLE || AtrM5Handle == INVALID_HANDLE)
   {
      Print("Swing Evaluation Predictor: failed to create indicator handles.");
      return INIT_FAILED;
   }

   EventSetTimer(1);
   Print("Swing Evaluation Predictor initialized. Chart-only dry-run overlay.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   ReleaseIndicators();
   DeleteAllObjects();
}

void OnTimer()
{
   EvaluateAndRender(false);
}

int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   EvaluateAndRender(false);
   return rates_total;
}

void EvaluateAndRender(const bool force)
{
   datetime now = TimeCurrent();
   if(!force && now - LastEvaluationTime < InpEvaluateEverySeconds)
      return;
   LastEvaluationTime = now;

   EvaluationResult eval;
   ResetEvaluation(eval);
   eval.signal_time = now;
   if(!EvaluateMarket(eval))
   {
      eval.action = "hold";
      eval.score = 0.0;
      if(eval.reason == "")
         eval.reason = "waiting for enough MT5 market data";
   }
   eval.signal_time = now;
   RenderPrediction(eval);
}

bool EvaluateMarket(EvaluationResult &eval)
{
   ResetEvaluation(eval);

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
   {
      eval.reason = "SymbolInfoTick failed";
      return false;
   }

   int lookback = InpLookbackBars;
   if(lookback < 80)
      lookback = 80;

   MqlRates m1[];
   ArraySetAsSeries(m1, true);
   int copied = CopyRates(_Symbol, PERIOD_M1, 0, lookback, m1);
   if(copied < 60)
   {
      eval.reason = "not enough M1 bars";
      return false;
   }

   double emaFastM30 = IndicatorValue(EmaFastM30Handle, 1);
   double emaFastM30Prev = IndicatorValue(EmaFastM30Handle, 2);
   double emaSlowM30 = IndicatorValue(EmaSlowM30Handle, 1);
   double emaFastM15 = IndicatorValue(EmaFastM15Handle, 1);
   double emaFastM15Prev = IndicatorValue(EmaFastM15Handle, 2);
   double emaSlowM15 = IndicatorValue(EmaSlowM15Handle, 1);
   double emaFastM5 = IndicatorValue(EmaFastM5Handle, 1);
   double emaSlowM5 = IndicatorValue(EmaSlowM5Handle, 1);
   double rsiM1 = IndicatorValue(RsiM1Handle, 1);
   double rsiM1Prev = IndicatorValue(RsiM1Handle, 2);
   double rsiM5 = IndicatorValue(RsiM5Handle, 1);
   double atrM1 = IndicatorValue(AtrM1Handle, 1);
   double atrM5 = IndicatorValue(AtrM5Handle, 1);

   if(emaFastM30 <= 0.0 || emaSlowM30 <= 0.0 || emaFastM15 <= 0.0 ||
      emaSlowM15 <= 0.0 || emaFastM5 <= 0.0 || emaSlowM5 <= 0.0 ||
      rsiM1 <= 0.0 || rsiM5 <= 0.0 || atrM1 <= 0.0 || atrM5 <= 0.0)
   {
      eval.reason = "indicators are not ready";
      return false;
   }
   eval.m30_trend = TrendText(emaFastM30, emaSlowM30, emaFastM30Prev);
   eval.m15_trend = TrendText(emaFastM15, emaSlowM15, emaFastM15Prev);

   MqlRates m5[];
   ArraySetAsSeries(m5, true);
   int m5Copied = CopyRates(_Symbol, PERIOD_M5, 0, 20, m5);
   double m5CloseSlowAtr = 0.0;
   if(m5Copied >= 3 && atrM5 > 0.0)
      m5CloseSlowAtr = (m5[1].close - emaSlowM5) / atrM5;
   double m1AlternatingRatio = M1AlternatingRatio(m1, copied, 14);

   double buyScore = 0.0;
   double sellScore = 0.0;
   string buyReasons = "";
   string sellReasons = "";

   if(emaFastM30 > emaSlowM30)
   {
      buyScore += InpScoreTrendM30;
      AddReason(buyReasons, "M30 uptrend");
   }
   else if(emaFastM30 < emaSlowM30)
   {
      sellScore += InpScoreTrendM30;
      AddReason(sellReasons, "M30 downtrend");
   }

   if(emaFastM15 > emaSlowM15)
   {
      buyScore += InpScoreTrendM15;
      AddReason(buyReasons, "M15 uptrend");
   }
   else if(emaFastM15 < emaSlowM15)
   {
      sellScore += InpScoreTrendM15;
      AddReason(sellReasons, "M15 downtrend");
   }

   if(emaFastM30 > emaFastM30Prev)
   {
      buyScore += InpScoreTrendSlope;
      AddReason(buyReasons, "M30 EMA rising");
   }
   else if(emaFastM30 < emaFastM30Prev)
   {
      sellScore += InpScoreTrendSlope;
      AddReason(sellReasons, "M30 EMA falling");
   }

   if(emaFastM15 > emaFastM15Prev)
   {
      buyScore += InpScoreTrendSlope;
      AddReason(buyReasons, "M15 EMA rising");
   }
   else if(emaFastM15 < emaFastM15Prev)
   {
      sellScore += InpScoreTrendSlope;
      AddReason(sellReasons, "M15 EMA falling");
   }

   if(emaFastM5 > emaSlowM5)
   {
      buyScore += InpScoreTrendM5;
      AddReason(buyReasons, "M5 upflow");
   }
   else if(emaFastM5 < emaSlowM5)
   {
      sellScore += InpScoreTrendM5;
      AddReason(sellReasons, "M5 downflow");
   }

   if(rsiM1 > rsiM1Prev && rsiM1 >= InpBuyRsiMin && rsiM1 <= InpBuyRsiMax)
   {
      buyScore += InpScoreRsiTurn;
      AddReason(buyReasons, "M1 RSI rebound");
   }
   if(rsiM1 < rsiM1Prev && rsiM1 >= InpSellRsiMin && rsiM1 <= InpSellRsiMax)
   {
      sellScore += InpScoreRsiTurn;
      AddReason(sellReasons, "M1 RSI rollover");
   }

   if(rsiM5 > 50.0)
   {
      buyScore += InpScoreRsiM5;
      AddReason(buyReasons, "M5 RSI above 50");
   }
   else if(rsiM5 < 50.0)
   {
      sellScore += InpScoreRsiM5;
      AddReason(sellReasons, "M5 RSI below 50");
   }

   int swingLowIndex = -1;
   int swingHighIndex = -1;
   double swingLow = FindRecentSwingLow(m1, copied, InpSwingDepth, lookback - 5, swingLowIndex);
   double swingHigh = FindRecentSwingHigh(m1, copied, InpSwingDepth, lookback - 5, swingHighIndex);
   if(swingLow <= 0.0)
      swingLow = RecentLowestLow(m1, copied, 2, 40);
   if(swingHigh <= 0.0)
      swingHigh = RecentHighestHigh(m1, copied, 2, 40);

   MqlRates last = m1[1];
   MqlRates prev = m1[2];
   double m1ClosePosition = CandleClosePosition(last);
   double m1BodyAtr = BearishBodyAtr(last, atrM1);
   double m1BullishBodyAtr = BullishBodyAtr(last, atrM1);
   double buyBand = swingLow + atrM1 * InpSwingAtrBand;
   double sellBand = swingHigh - atrM1 * InpSwingAtrBand;

   if(last.low <= buyBand && last.close > last.open)
   {
      buyScore += InpScoreSwingReversal;
      AddReason(buyReasons, "bullish rebound near swing low");
   }
   if(last.high >= sellBand && last.close < last.open)
   {
      sellScore += InpScoreSwingReversal;
      AddReason(sellReasons, "bearish rejection near swing high");
   }

   bool buyBreakConfirm = last.close > prev.high;
   bool sellBreakConfirm = last.close < prev.low;
   if(buyBreakConfirm)
   {
      buyScore += InpScoreBreakConfirm;
      AddReason(buyReasons, "previous high reclaimed");
   }
   if(sellBreakConfirm)
   {
      sellScore += InpScoreBreakConfirm;
      AddReason(sellReasons, "previous low lost");
   }

   if(InpUseFittedBuyBreakFilter && !buyBreakConfirm)
   {
      buyScore -= InpScoreRiskPenalty;
      AddReason(buyReasons, "buy fit filter rejected: no break trigger");
   }
   if(InpUseFittedBuyEntryFilter)
   {
      bool buyEntryPass = true;
      if(InpBuyRequireBreakConfirm && !buyBreakConfirm)
      {
         buyEntryPass = false;
         AddReason(buyReasons, "buy entry fit rejected: no high break");
      }
      if(m1ClosePosition < InpBuyMinM1ClosePosition)
      {
         buyEntryPass = false;
         AddReason(buyReasons, StringFormat("buy entry fit rejected: M1 close position %.2f", m1ClosePosition));
      }
      if(m1BullishBodyAtr < InpBuyMinM1BodyAtr)
      {
         buyEntryPass = false;
         AddReason(buyReasons, StringFormat("buy entry fit rejected: M1 body %.2f ATR", m1BullishBodyAtr));
      }
      if(m5CloseSlowAtr < InpBuyMinM5CloseSlowAtr)
      {
         buyEntryPass = false;
         AddReason(buyReasons, StringFormat("buy entry fit rejected: M5 close/EMA %.2f ATR", m5CloseSlowAtr));
      }
      if(!buyEntryPass)
         buyScore -= InpScoreRiskPenalty;
      else
         AddReason(buyReasons, "buy entry fit filter passed");
   }
   if(InpUseFittedBuyTimeFilter && IsServerHourInList(TimeCurrent(), InpBuyBlockedServerHours))
   {
      buyScore -= InpScoreRiskPenalty;
      AddReason(buyReasons, "buy time fit rejected: weak server hour");
   }
   if(InpUseFittedBuyCalendarFilter && IsServerCalendarInList(TimeCurrent(), InpBuyBlockedMonths, InpBuyBlockedWeekdays))
   {
      buyScore -= InpScoreRiskPenalty;
      AddReason(buyReasons, "buy calendar fit rejected: weak month/weekday");
   }
   if(InpUseBuyAllowedServerHours && !IsServerHourInList(TimeCurrent(), InpBuyAllowedServerHours))
   {
      buyScore = 0.0;
      AddReason(buyReasons, "buy allowed-hour filter rejected");
   }
   if(InpUseBuyM30M15UpGate && !(emaFastM30 > emaSlowM30 && emaFastM15 > emaSlowM15))
   {
      buyScore = 0.0;
      AddReason(buyReasons, "buy M30/M15 up gate rejected");
   }
   if(InpUseFittedSellFilter)
   {
      bool sellFitPass = true;
      if(m5CloseSlowAtr < InpSellMinM5CloseSlowAtr)
      {
         sellFitPass = false;
         AddReason(sellReasons, StringFormat("sell fit rejected: M5 close/EMA %.2f ATR", m5CloseSlowAtr));
      }
      if(m1AlternatingRatio < InpSellMinM1AlternatingRatio)
      {
         sellFitPass = false;
         AddReason(sellReasons, StringFormat("sell fit rejected: M1 alternating %.2f", m1AlternatingRatio));
      }
      if(!sellFitPass)
         sellScore -= InpScoreRiskPenalty;
      else
         AddReason(sellReasons, "sell fit filters passed");
   }
   if(InpUseFittedSellTrendFilter)
   {
      bool sellTrendPass = true;
      if(emaFastM30 < emaSlowM30 && emaFastM15 > emaSlowM15)
      {
         sellTrendPass = false;
         AddReason(sellReasons, "sell trend fit rejected: M30 down M15 up");
      }
      else if(SellPartialUpTrendRejected(emaFastM30, emaSlowM30, emaFastM15, emaSlowM15, emaFastM5, emaSlowM5))
      {
         sellTrendPass = false;
         AddReason(sellReasons, "sell trend fit rejected: partial upper trend");
      }
      if(!sellTrendPass)
         sellScore -= InpScoreRiskPenalty;
      else
         AddReason(sellReasons, "sell trend fit filter passed");
   }
   if(InpUseSellM30M15DownGate && !(emaFastM30 < emaSlowM30 && emaFastM15 < emaSlowM15))
   {
      sellScore = 0.0;
      AddReason(sellReasons, "sell M30/M15 down gate rejected");
   }
   if(InpUseFittedSellTimeFilter && IsServerHourInList(TimeCurrent(), InpSellBlockedServerHours))
   {
      sellScore -= InpScoreRiskPenalty;
      AddReason(sellReasons, "sell time fit rejected: weak server hour");
   }
   if(InpUseFittedSellCalendarFilter && IsServerCalendarInList(TimeCurrent(), InpSellBlockedMonths, InpSellBlockedWeekdays))
   {
      sellScore -= InpScoreRiskPenalty;
      AddReason(sellReasons, "sell calendar fit rejected: weak month/weekday");
   }
   if(InpUseSellAllowedServerHours && !IsServerHourInList(TimeCurrent(), InpSellAllowedServerHours))
   {
      sellScore = 0.0;
      AddReason(sellReasons, "sell allowed-hour filter rejected");
   }
   if(InpUseFittedSellEntryFilter)
   {
      bool sellEntryPass = true;
      if(InpSellRequireBreakConfirm && !sellBreakConfirm)
      {
         sellEntryPass = false;
         AddReason(sellReasons, "sell entry fit rejected: no low break");
      }
      if(m1ClosePosition > InpSellMaxM1ClosePosition)
      {
         sellEntryPass = false;
         AddReason(sellReasons, StringFormat("sell entry fit rejected: M1 close position %.2f", m1ClosePosition));
      }
      if(m1BodyAtr < InpSellMinM1BodyAtr)
      {
         sellEntryPass = false;
         AddReason(sellReasons, StringFormat("sell entry fit rejected: M1 body %.2f ATR", m1BodyAtr));
      }
      if(m5CloseSlowAtr > InpSellMaxM5CloseSlowAtr)
      {
         sellEntryPass = false;
         AddReason(sellReasons, StringFormat("sell entry fit rejected: M5 close/EMA %.2f ATR", m5CloseSlowAtr));
      }
      if(!sellEntryPass)
         sellScore -= InpScoreRiskPenalty;
      else
         AddReason(sellReasons, "sell entry fit filter passed");
   }

   TradePlan buyPlan;
   TradePlan sellPlan;
   BuildPlan("buy", tick.ask, swingLow, swingHigh, buyScore, buyPlan);
   BuildPlan("sell", tick.bid, swingLow, swingHigh, sellScore, sellPlan);

   if(buyPlan.valid)
   {
      buyScore += InpScoreRiskPlan;
      AddReason(buyReasons, buyPlan.reason);
   }
   else
   {
      buyScore -= InpScoreRiskPenalty;
      AddReason(buyReasons, buyPlan.reason);
   }

   if(sellPlan.valid)
   {
      sellScore += InpScoreRiskPlan;
      AddReason(sellReasons, sellPlan.reason);
   }
   else
   {
      sellScore -= InpScoreRiskPenalty;
      AddReason(sellReasons, sellPlan.reason);
   }

   eval.buy_score = buyScore;
   eval.sell_score = sellScore;
   eval.buy_reason = buyReasons;
   eval.sell_reason = sellReasons;

   int currentSpread = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(currentSpread > InpMaxSpreadPoints)
   {
      eval.action = "hold";
      eval.score = MathMax(buyScore, sellScore);
      eval.reason = StringFormat("spread too wide: %d > %d", currentSpread, InpMaxSpreadPoints);
      return true;
   }
   if(IsRolloverBlocked())
   {
      eval.action = "hold";
      eval.score = MathMax(buyScore, sellScore);
      eval.reason = "rollover no-entry window";
      return true;
   }

   if(buyPlan.valid && buyScore >= InpMinScore && buyScore >= sellScore + InpMinDominance)
   {
      ApplyPlanToEvaluation("buy", buyScore, buyReasons, buyPlan, eval);
      return true;
   }
   if(sellPlan.valid && sellScore >= InpMinScore && sellScore >= buyScore + InpMinDominance)
   {
      ApplyPlanToEvaluation("sell", sellScore, sellReasons, sellPlan, eval);
      return true;
   }

   eval.action = "hold";
   eval.score = MathMax(buyScore, sellScore);
   eval.reason = StringFormat("no dominant setup; buy=%.1f sell=%.1f", buyScore, sellScore);
   return true;
}

void BuildPlan(const string action, const double entry, const double swingLow,
               const double swingHigh, const double preliminaryScore, TradePlan &plan)
{
   ResetPlan(action, plan);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0.0)
   {
      plan.reason = "invalid symbol point";
      return;
   }

   double rr = SelectedRiskReward(action, preliminaryScore);
   double buffer = InpStopBufferPoints * point;
   plan.entry = NormalizePrice(entry);
   plan.rr = rr;

   if(action == "buy")
   {
      plan.sl = NormalizePrice(swingLow - buffer);
      if(plan.sl <= 0.0 || plan.sl >= plan.entry)
      {
         plan.reason = "buy risk invalid";
         return;
      }
      double stopDistance = plan.entry - plan.sl;
      plan.tp = NormalizePrice(plan.entry + rr * stopDistance);
      plan.stop_points = stopDistance / point;
   }
   else if(action == "sell")
   {
      plan.sl = NormalizePrice(swingHigh + buffer);
      if(plan.sl <= plan.entry)
      {
         plan.reason = "sell risk invalid";
         return;
      }
      double stopDistance = plan.sl - plan.entry;
      plan.tp = NormalizePrice(plan.entry - rr * stopDistance);
      plan.stop_points = stopDistance / point;
   }
   else
   {
      plan.reason = "unsupported plan action";
      return;
   }

   int stopLevel = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(plan.stop_points < InpMinStopPoints)
   {
      plan.reason = StringFormat("SL too close %.0fpt", plan.stop_points);
      return;
   }
   if(plan.stop_points > InpMaxStopPoints)
   {
      plan.reason = StringFormat("SL too far %.0fpt", plan.stop_points);
      return;
   }
   if(stopLevel > 0 && plan.stop_points <= stopLevel)
   {
      plan.reason = StringFormat("SL inside broker stop level %.0fpt <= %dpt", plan.stop_points, stopLevel);
      return;
   }
   if(action == "buy" && plan.tp <= plan.entry)
   {
      plan.reason = "buy TP invalid";
      return;
   }
   if(action == "sell" && plan.tp >= plan.entry)
   {
      plan.reason = "sell TP invalid";
      return;
   }

   plan.valid = true;
   plan.reason = StringFormat("risk plan RR %.1f SL %.0fpt", plan.rr, plan.stop_points);
}

double SelectedRiskReward(const string action, const double preliminaryScore)
{
   double minRR = InpMinRiskReward;
   double maxRR = InpMaxRiskReward;
   if(minRR < 1.0)
      minRR = 1.0;
   if(maxRR < minRR)
      maxRR = minRR;

   if(InpUseSideRiskReward)
   {
      if(action == "buy")
         return ClampDouble(InpBuyRiskReward, minRR, maxRR);
      if(action == "sell")
         return ClampDouble(InpSellRiskReward, minRR, maxRR);
   }
   if(!InpUseVariableRiskReward)
      return ClampDouble(InpRiskReward, minRR, maxRR);
   if(preliminaryScore >= InpScoreForRR5)
      return ClampDouble(5.0, minRR, maxRR);
   if(preliminaryScore >= InpScoreForRR4)
      return ClampDouble(4.0, minRR, maxRR);
   return ClampDouble(3.0, minRR, maxRR);
}

void RenderPrediction(EvaluationResult &eval)
{
   DrawPredictionPanel(eval);
   if(!InpDrawDryRunOrderLines)
   {
      ChartRedraw(0);
      return;
   }

   if(eval.action == "hold")
   {
      if(InpClearLinesOnHold)
         DeleteDryRunOrderLines();
      ChartRedraw(0);
      return;
   }
   DrawDryRunOrderLines(eval);
   ChartRedraw(0);
}

void DrawPredictionPanel(EvaluationResult &eval)
{
   color actionColor = PanelColor(eval.action);
   DrawPanelBox(actionColor);
   string actionText = StringUpperCopy(eval.action);
   string line0 = StringFormat("%s: %.1f", actionText, eval.score);
   string line1 = StringFormat("B %.1f/S %.1f M30 %s M15 %s",
                               eval.buy_score, eval.sell_score, eval.m30_trend, eval.m15_trend);
   string line2 = StringFormat("Updated %s Spr %dpt Valid %s",
                               ClockText(eval.signal_time),
                               (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD),
                               ValidClockText(eval));
   string line3 = HoldReasonText(eval);
   string line4 = "";
   if(eval.action != "hold")
   {
      line3 = StringFormat("E %.2f   RR %.1f", eval.entry, eval.rr);
      line4 = StringFormat("SL %.2f TP %.2f", eval.sl, eval.tp);
   }

   DrawPanelLineStyled(0, line0, actionColor, InpPanelScoreFontSize);
   DrawPanelLineStyled(1, line1, clrSilver, InpPanelDetailFontSize);
   DrawPanelLineStyled(2, line2, clrWhite, InpPanelDetailFontSize);
   DrawPanelLine(3, line3, actionColor);
   DrawPanelLineStyled(4, line4, clrWhite, InpPanelDetailFontSize);
}

void DrawPanelBox(const color borderColor)
{
   string name = ObjectPrefix() + "PANEL_BOX";
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, PanelCorner());
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, PanelXDistance());
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, PanelYDistance());
   ObjectSetInteger(0, name, OBJPROP_XSIZE, InpPanelWidth);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, InpPanelHeight);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, InpPanelBackgroundColor);
   ObjectSetInteger(0, name, OBJPROP_COLOR, borderColor);
   ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}

void DrawPanelLine(const int index, const string text, const color textColor)
{
   DrawPanelLineStyled(index, text, textColor, InpPanelFontSize);
}

void DrawPanelLineStyled(const int index, const string text, const color textColor,
                         const int fontSize)
{
   string name = ObjectPrefix() + "PANEL_" + IntegerToString(index);
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, PanelCorner());
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, PanelXDistance() + InpPanelPadding);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, PanelLineY(index));
   ObjectSetInteger(0, name, OBJPROP_COLOR, textColor);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, PanelAnchor());
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
   ObjectSetString(0, name, OBJPROP_TEXT, text);
}

int PanelLineY(const int index)
{
   int safeIndex = index;
   if(safeIndex < 0)
      safeIndex = 0;
   if(safeIndex >= PanelLineCount())
      safeIndex = PanelLineCount() - 1;

   int baseY = PanelYDistance();
   ENUM_BASE_CORNER corner = PanelCorner();
   if(corner == CORNER_LEFT_LOWER || corner == CORNER_RIGHT_LOWER)
      return baseY + InpPanelPadding + PanelLineTopOffset(PanelLineCount() - 1) - PanelLineTopOffset(safeIndex);
   return baseY + InpPanelPadding + PanelLineTopOffset(safeIndex);
}

int PanelLineCount()
{
   return 5;
}

int PanelLineTopOffset(const int index)
{
   if(index <= 0)
      return 0;
   if(index == 1)
      return InpPanelLineHeight + 22;
   if(index == 2)
      return InpPanelLineHeight * 2 + 26;
   if(index == 3)
      return InpPanelLineHeight * 3 + 30;
   return InpPanelLineHeight * index + 34;
}

ENUM_ANCHOR_POINT PanelAnchor()
{
   ENUM_BASE_CORNER corner = PanelCorner();
   if(corner == CORNER_LEFT_LOWER)
      return ANCHOR_LEFT_LOWER;
   if(corner == CORNER_RIGHT_LOWER)
      return ANCHOR_RIGHT_LOWER;
   if(corner == CORNER_RIGHT_UPPER)
      return ANCHOR_RIGHT_UPPER;
   return ANCHOR_LEFT_UPPER;
}

ENUM_BASE_CORNER PanelCorner()
{
   if(InpPanelUsePercentPosition)
      return CORNER_LEFT_UPPER;
   return InpPanelCorner;
}

int PanelXDistance()
{
   if(!InpPanelUsePercentPosition)
      return InpPanelX;
   long width = ChartGetInteger(0, CHART_WIDTH_IN_PIXELS, 0);
   if(width <= 0)
      return InpPanelX;
   int maxX = (int)width - InpPanelWidth;
   if(maxX < 0)
      maxX = 0;
   int x = (int)MathRound((double)width * InpPanelLeftPercent / 100.0);
   return ClampInt(x, 0, maxX);
}

int PanelYDistance()
{
   if(!InpPanelUsePercentPosition)
      return InpPanelY;
   long height = ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, 0);
   if(height <= 0)
      return InpPanelY;
   int maxY = (int)height - InpPanelHeight;
   if(maxY < 0)
      maxY = 0;
   int y = (int)MathRound((double)height * InpPanelTopPercent / 100.0);
   return ClampInt(y, 0, maxY);
}

int ClampInt(const int value, const int minimum, const int maximum)
{
   if(value < minimum)
      return minimum;
   if(value > maximum)
      return maximum;
   return value;
}

string TimeText(const datetime value)
{
   if(value <= 0)
      return "-";
   return TimeToString(value, TIME_DATE | TIME_SECONDS);
}

string ValidUntilText(EvaluationResult &eval)
{
   if(eval.action == "hold" || eval.signal_time <= 0 || InpLineValidSeconds <= 0)
      return "-";
   return TimeToString(eval.signal_time + InpLineValidSeconds, TIME_DATE | TIME_SECONDS);
}

string ClockText(const datetime value)
{
   if(value <= 0)
      return "-";
   return TimeToString(value, TIME_SECONDS);
}

string ValidClockText(EvaluationResult &eval)
{
   if(eval.action == "hold" || eval.signal_time <= 0 || InpLineValidSeconds <= 0)
      return "-";
   return TimeToString(eval.signal_time + InpLineValidSeconds, TIME_SECONDS);
}

string HoldReasonText(EvaluationResult &eval)
{
   if(eval.action != "hold")
      return "";
   string reason = eval.reason;
   StringToLower(reason);
   if(eval.score < InpMinScore)
      return "WAIT: SCORE LOW";
   if(StringFind(reason, "spread") >= 0)
      return "WAIT: SPREAD";
   if(StringFind(reason, "rollover") >= 0)
      return "WAIT: ROLLOVER";
   if(StringFind(reason, "not enough") >= 0 || StringFind(reason, "not ready") >= 0 || StringFind(reason, "waiting") >= 0)
      return "WAIT: DATA";
   if(StringFind(reason, "no dominant") >= 0)
      return "WAIT: NO DOMINANCE";
   return "WAIT: OTHER";
}

bool SellPartialUpTrendRejected(const double fastM30, const double slowM30,
                                const double fastM15, const double slowM15,
                                const double fastM5, const double slowM5)
{
   bool m30Up = fastM30 > slowM30;
   bool m15Up = fastM15 > slowM15;
   bool m5Up = fastM5 > slowM5;
   return (m30Up && m15Up && !m5Up) || (!m30Up && m15Up && m5Up);
}

string TrendText(const double fast, const double slow, const double previousFast)
{
   if(fast > slow)
   {
      if(fast > previousFast)
         return "UP+";
      return "UP";
   }
   if(fast < slow)
   {
      if(fast < previousFast)
         return "DOWN+";
      return "DOWN";
   }
   return "FLAT";
}

void DrawDryRunOrderLines(EvaluationResult &eval)
{
   string prefix = ObjectPrefix();
   DrawHLine(prefix + "ENTRY", eval.entry, clrDodgerBlue, STYLE_SOLID, 2, "DRY-RUN ENTRY");
   DrawHLine(prefix + "SL", eval.sl, clrTomato, STYLE_DASH, 1, "DRY-RUN SL");
   DrawHLine(prefix + "TP", eval.tp, clrLimeGreen, STYLE_DASH, 1, "DRY-RUN TP");
}

void DrawHLine(const string name, const double price, const color lineColor,
               const ENUM_LINE_STYLE style, const int width, const string label)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   ObjectSetDouble(0, name, OBJPROP_PRICE, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, lineColor);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetString(0, name, OBJPROP_TEXT, label);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, label + " " + DoubleToString(price, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)));
}

void DeleteDryRunOrderLines()
{
   string prefix = ObjectPrefix();
   ObjectDelete(0, prefix + "ENTRY");
   ObjectDelete(0, prefix + "SL");
   ObjectDelete(0, prefix + "TP");
}

void DeleteAllObjects()
{
   DeleteDryRunOrderLines();
   string prefix = ObjectPrefix();
   ObjectDelete(0, prefix + "PANEL_BOX");
   for(int i = 0; i < 20; i++)
      ObjectDelete(0, prefix + "PANEL_" + IntegerToString(i));
}

color PanelColor(const string action)
{
   if(action == "buy")
      return clrLimeGreen;
   if(action == "sell")
      return clrTomato;
   return InpPanelPrimaryColor;
}

string ObjectPrefix()
{
   return InpObjectPrefix + _Symbol + "_";
}

string ShortText(const string text, const int maxLength)
{
   if(StringLen(text) <= maxLength)
      return text;
   if(maxLength <= 3)
      return StringSubstr(text, 0, maxLength);
   return StringSubstr(text, 0, maxLength - 3) + "...";
}

string PanelDetailText(const string text)
{
   if(text == "")
      return "-";
   return text;
}

string StringUpperCopy(const string text)
{
   string copy = text;
   StringToUpper(copy);
   return copy;
}

void ApplyPlanToEvaluation(const string action, const double score, const string reasons,
                           TradePlan &plan, EvaluationResult &eval)
{
   eval.action = action;
   eval.tradable = true;
   eval.score = score;
   eval.entry = plan.entry;
   eval.sl = plan.sl;
   eval.tp = plan.tp;
   eval.rr = plan.rr;
   eval.stop_points = plan.stop_points;
   eval.reason = reasons;
}

void ResetEvaluation(EvaluationResult &eval)
{
   eval.action = "hold";
   eval.tradable = false;
   eval.score = 0.0;
   eval.buy_score = 0.0;
   eval.sell_score = 0.0;
   eval.entry = 0.0;
   eval.sl = 0.0;
   eval.tp = 0.0;
   eval.rr = 0.0;
   eval.stop_points = 0.0;
   eval.signal_time = 0;
   eval.reason = "";
   eval.buy_reason = "";
   eval.sell_reason = "";
   eval.m30_trend = "-";
   eval.m15_trend = "-";
}

void ResetPlan(const string action, TradePlan &plan)
{
   plan.valid = false;
   plan.action = action;
   plan.entry = 0.0;
   plan.sl = 0.0;
   plan.tp = 0.0;
   plan.rr = 0.0;
   plan.stop_points = 0.0;
   plan.reason = "";
}

double IndicatorValue(const int handle, const int shift)
{
   double buffer[];
   ArraySetAsSeries(buffer, true);
   if(CopyBuffer(handle, 0, shift, 1, buffer) != 1)
      return 0.0;
   return buffer[0];
}

double FindRecentSwingLow(MqlRates &rates[], const int total, const int depth,
                          const int maxBars, int &foundIndex)
{
   foundIndex = -1;
   int safeDepth = depth;
   if(safeDepth < 1)
      safeDepth = 1;
   int limit = total - safeDepth - 1;
   if(limit > maxBars)
      limit = maxBars;
   for(int i = safeDepth + 1; i <= limit; i++)
   {
      bool isSwing = true;
      for(int j = 1; j <= safeDepth; j++)
      {
         if(rates[i].low >= rates[i - j].low || rates[i].low > rates[i + j].low)
         {
            isSwing = false;
            break;
         }
      }
      if(isSwing)
      {
         foundIndex = i;
         return rates[i].low;
      }
   }
   return 0.0;
}

double FindRecentSwingHigh(MqlRates &rates[], const int total, const int depth,
                           const int maxBars, int &foundIndex)
{
   foundIndex = -1;
   int safeDepth = depth;
   if(safeDepth < 1)
      safeDepth = 1;
   int limit = total - safeDepth - 1;
   if(limit > maxBars)
      limit = maxBars;
   for(int i = safeDepth + 1; i <= limit; i++)
   {
      bool isSwing = true;
      for(int j = 1; j <= safeDepth; j++)
      {
         if(rates[i].high <= rates[i - j].high || rates[i].high < rates[i + j].high)
         {
            isSwing = false;
            break;
         }
      }
      if(isSwing)
      {
         foundIndex = i;
         return rates[i].high;
      }
   }
   return 0.0;
}

double RecentLowestLow(MqlRates &rates[], const int total, const int start, const int count)
{
   int begin = start;
   if(begin < 1)
      begin = 1;
   int end = begin + count;
   if(end > total)
      end = total;
   double value = rates[begin].low;
   for(int i = begin + 1; i < end; i++)
   {
      if(rates[i].low < value)
         value = rates[i].low;
   }
   return value;
}

double RecentHighestHigh(MqlRates &rates[], const int total, const int start, const int count)
{
   int begin = start;
   if(begin < 1)
      begin = 1;
   int end = begin + count;
   if(end > total)
      end = total;
   double value = rates[begin].high;
   for(int i = begin + 1; i < end; i++)
   {
      if(rates[i].high > value)
         value = rates[i].high;
   }
   return value;
}

double CandleClosePosition(const MqlRates &candle)
{
   double range = candle.high - candle.low;
   if(range <= 0.0)
      return 0.5;
   double position = (candle.close - candle.low) / range;
   if(position < 0.0)
      return 0.0;
   if(position > 1.0)
      return 1.0;
   return position;
}

double BearishBodyAtr(const MqlRates &candle, const double atr)
{
   if(atr <= 0.0)
      return 0.0;
   double body = candle.open - candle.close;
   if(body <= 0.0)
      return 0.0;
   return body / atr;
}

double BullishBodyAtr(const MqlRates &candle, const double atr)
{
   if(atr <= 0.0)
      return 0.0;
   double body = candle.close - candle.open;
   if(body <= 0.0)
      return 0.0;
   return body / atr;
}

double M1AlternatingRatio(MqlRates &rates[], const int total, const int bars)
{
   int usable = bars;
   if(usable < 3)
      usable = 3;
   if(usable > total - 2)
      usable = total - 2;

   int transitions = 0;
   int comparisons = 0;
   int previousDirection = 0;
   for(int i = usable; i >= 1; i--)
   {
      double body = rates[i].close - rates[i].open;
      int direction = 0;
      if(body > 0.0)
         direction = 1;
      else if(body < 0.0)
         direction = -1;
      if(direction == 0)
         continue;
      if(previousDirection != 0)
      {
         comparisons++;
         if(direction != previousDirection)
            transitions++;
      }
      previousDirection = direction;
   }
   if(comparisons <= 0)
      return 0.0;
   return (double)transitions / (double)comparisons;
}

bool IsRolloverBlocked()
{
   if(!InpUseRolloverFilter)
      return false;
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);

   int nowMinutes = dt.hour * 60 + dt.min;
   int startMinutes = InpRolloverStartHour * 60 + InpRolloverStartMinute;
   int endMinutes = InpRolloverEndHour * 60 + InpRolloverEndMinute;

   if(startMinutes <= endMinutes)
      return nowMinutes >= startMinutes && nowMinutes <= endMinutes;
   return nowMinutes >= startMinutes || nowMinutes <= endMinutes;
}

bool IsServerHourInList(const datetime value, const string csvHours)
{
   MqlDateTime dt;
   TimeToStruct(value, dt);
   string normalized = csvHours;
   StringReplace(normalized, " ", "");
   normalized = "," + normalized + ",";
   string needle = "," + IntegerToString(dt.hour) + ",";
   return StringFind(normalized, needle) >= 0;
}

bool IsIntInCsv(const int value, const string csvValues)
{
   string normalized = csvValues;
   StringReplace(normalized, " ", "");
   if(normalized == "")
      return false;
   normalized = "," + normalized + ",";
   string needle = "," + IntegerToString(value) + ",";
   return StringFind(normalized, needle) >= 0;
}

bool IsServerCalendarInList(const datetime value, const string csvMonths, const string csvWeekdays)
{
   MqlDateTime dt;
   TimeToStruct(value, dt);
   return IsIntInCsv(dt.mon, csvMonths) || IsIntInCsv(dt.day_of_week, csvWeekdays);
}

void AddReason(string &reasons, const string reason)
{
   if(reason == "")
      return;
   if(reasons != "")
      reasons += "; ";
   reasons += reason;
}

double NormalizePrice(const double price)
{
   return NormalizeDouble(price, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS));
}

double ClampDouble(const double value, const double minValue, const double maxValue)
{
   if(value < minValue)
      return minValue;
   if(value > maxValue)
      return maxValue;
   return value;
}

void ReleaseIndicators()
{
   if(EmaFastM5Handle != INVALID_HANDLE) IndicatorRelease(EmaFastM5Handle);
   if(EmaSlowM5Handle != INVALID_HANDLE) IndicatorRelease(EmaSlowM5Handle);
   if(EmaFastM15Handle != INVALID_HANDLE) IndicatorRelease(EmaFastM15Handle);
   if(EmaSlowM15Handle != INVALID_HANDLE) IndicatorRelease(EmaSlowM15Handle);
   if(EmaFastM30Handle != INVALID_HANDLE) IndicatorRelease(EmaFastM30Handle);
   if(EmaSlowM30Handle != INVALID_HANDLE) IndicatorRelease(EmaSlowM30Handle);
   if(RsiM1Handle != INVALID_HANDLE) IndicatorRelease(RsiM1Handle);
   if(RsiM5Handle != INVALID_HANDLE) IndicatorRelease(RsiM5Handle);
   if(AtrM1Handle != INVALID_HANDLE) IndicatorRelease(AtrM1Handle);
   if(AtrM5Handle != INVALID_HANDLE) IndicatorRelease(AtrM5Handle);
}
