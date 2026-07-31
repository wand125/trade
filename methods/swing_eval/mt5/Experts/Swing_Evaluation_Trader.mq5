//+------------------------------------------------------------------+
//| Swing_Evaluation_Trader.mq5                                      |
//| Standalone MT5 swing/flow score trader. No bridge, no GPT.       |
//+------------------------------------------------------------------+
#property strict

#include <Trade/Trade.mqh>

input bool InpSignalOnly = true;
input bool InpEnableTrading = false;
input bool InpAllowLiveTrading = false;
input bool InpRequireStrategyTester = false;
input int InpEvaluateEverySeconds = 5;
input int InpMinSecondsBetweenTrades = 60;
input ulong InpMagicNumber = 26070802;
input int InpDeviationPoints = 50;

input double InpLot = 0.10;
input double InpMaxSingleLot = 0.10;
input double InpMaxTotalLot = 0.30;
input int InpMaxPositions = 3;
input bool InpCountAllSymbolPositions = true;
input int InpMaxSpreadPoints = 80;
input bool InpEnableBuy = true;
input bool InpEnableSell = true;

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

input int InpTesterMinClosedTrades = 30;
input double InpTesterMinProfitFactor = 1.20;

input bool InpUseDailyLossStop = true;
input double InpDailyLossLimit = 5000.0;
input bool InpUseConsecutiveLossStop = true;
input int InpConsecutiveLossLimit = 20;
input int InpConsecutiveLossCooldownMinutes = 120;

input bool InpWriteCsvLog = true;
input bool InpLogSignalRows = false;
input string InpCsvLogFile = "swing_evaluation_trades.csv";

input bool InpDrawSignalLines = true;
input bool InpClearLinesOnHold = false;
input bool InpShowChartEntryButton = false;
input bool InpManualButtonOnly = false;
input bool InpChartButtonDryRunOnly = true;
input bool InpAllowChartButtonTrading = false;
input int InpButtonX = 12;
input int InpButtonY = 80;
input int InpButtonWidth = 120;
input int InpButtonHeight = 24;

CTrade Trade;
datetime LastEvaluationTime = 0;
datetime LastTradeTime = 0;
datetime LastTradeBarTime = 0;
datetime LastSignalLogBarTime = 0;

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

int StatClosedTrades = 0;
int StatWins = 0;
int StatLosses = 0;
int StatConsecutiveLosses = 0;
int StatMaxConsecutiveLosses = 0;
double StatGrossProfit = 0.0;
double StatGrossLoss = 0.0;
double StatNetProfit = 0.0;
int StatDailyDateKey = 0;
int StatDailyClosedTrades = 0;
double StatDailyNetProfit = 0.0;
datetime StatConsecutiveLossCooldownUntil = 0;

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
   datetime opened_at;
   string m30_trend;
   string m15_trend;
   string m5_trend;
   string m30_slope;
   string m15_slope;
   string trend_alignment;
   double m1_close_position;
   double m1_body_atr;
   double m5_close_slow_atr;
   double m1_alternating_ratio;
   string reason;
};

struct ActiveSignal
{
   ulong position_id;
   string action;
   double score;
   double buy_score;
   double sell_score;
   double entry;
   double sl;
   double tp;
   double rr;
   double stop_points;
   datetime signal_time;
   datetime opened_at;
   string m30_trend;
   string m15_trend;
   string m5_trend;
   string m30_slope;
   string m15_slope;
   string trend_alignment;
   double m1_close_position;
   double m1_body_atr;
   double m5_close_slow_atr;
   double m1_alternating_ratio;
   string reason;
};

ActiveSignal ActiveSignals[];
EvaluationResult LastEvaluation;
bool HasLastEvaluation = false;

int OnInit()
{
   Trade.SetExpertMagicNumber(InpMagicNumber);
   Trade.SetDeviationInPoints(InpDeviationPoints);

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
      Print("Swing Evaluation Trader: failed to create indicator handles.");
      return INIT_FAILED;
   }

   EventSetTimer(1);
   ResetDailyStatsIfNeeded(TimeCurrent());
   PrintFormat("Swing Evaluation Trader initialized v20260717a. Standalone mode: no bridge, no GPT. env=%s tester_required=%s",
               ExecutionEnvironmentText(),
               InpRequireStrategyTester ? "true" : "false");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   ReleaseIndicators();
   DeleteEntryButton();
   PrintFormat("Swing Evaluation Trader stats closed=%d wins=%d losses=%d pf=%.2f net=%.2f max_losing_streak=%d",
               StatClosedTrades, StatWins, StatLosses, ProfitFactor(), StatNetProfit, StatMaxConsecutiveLosses);
   Comment("");
}

void OnTick()
{
   RunEvaluation();
}

void OnTimer()
{
   RunEvaluation();
}

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id != CHARTEVENT_OBJECT_CLICK)
      return;
   if(sparam != EntryButtonName())
      return;
   ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
   HandleEntryButtonClick();
}

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;
   if(trans.deal == 0 || !HistoryDealSelect(trans.deal))
      return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol)
      return;
   if((ulong)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagicNumber)
      return;

   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT && entry != DEAL_ENTRY_OUT_BY)
      return;

   double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
   double commission = HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   double swap = HistoryDealGetDouble(trans.deal, DEAL_SWAP);
   double net = profit + commission + swap;
   double dealPrice = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   datetime dealTime = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);

   ResetDailyStatsIfNeeded(dealTime);
   StatClosedTrades++;
   StatDailyClosedTrades++;
   StatNetProfit += net;
   StatDailyNetProfit += net;
   if(net > 0.0)
   {
      StatWins++;
      StatGrossProfit += net;
      StatConsecutiveLosses = 0;
      StatConsecutiveLossCooldownUntil = 0;
   }
   else if(net < 0.0)
   {
      StatLosses++;
      StatGrossLoss += MathAbs(net);
      StatConsecutiveLosses++;
      if(StatConsecutiveLosses > StatMaxConsecutiveLosses)
         StatMaxConsecutiveLosses = StatConsecutiveLosses;
      ArmConsecutiveLossCooldown(dealTime);
   }

   ulong positionId = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   int signalIndex = FindActiveSignal(positionId);
   EvaluationResult eval;
   ResetEvaluation(eval);
   if(signalIndex >= 0)
      EvaluationFromActiveSignal(signalIndex, eval);
   else
      eval.action = CloseDealActionName(HistoryDealGetInteger(trans.deal, DEAL_TYPE));

   AppendTradeCsv(
      "close",
      eval,
      0,
      trans.deal,
      positionId,
      HistoryDealGetDouble(trans.deal, DEAL_VOLUME),
      dealPrice,
      profit,
      commission,
      swap,
      net,
      "position closed"
   );
   if(signalIndex >= 0)
      RemoveActiveSignal(signalIndex);
}

double OnTester()
{
   double pf = ProfitFactor();
   if(StatClosedTrades < InpTesterMinClosedTrades)
      return -1000.0 + StatClosedTrades;
   if(pf < InpTesterMinProfitFactor)
      return -100.0 + pf * 10.0 + StatClosedTrades * 0.01;

   double expectancy = StatClosedTrades > 0 ? StatNetProfit / StatClosedTrades : 0.0;
   double score = pf * 100.0 + expectancy + StatClosedTrades * 0.05 - StatMaxConsecutiveLosses * 5.0;
   return score;
}

void RunEvaluation()
{
   datetime now = TimeCurrent();
   if(now - LastEvaluationTime < InpEvaluateEverySeconds)
      return;
   LastEvaluationTime = now;

   EvaluationResult eval;
   ResetEvaluation(eval);
   eval.signal_time = now;
   if(!EvaluateMarket(eval))
   {
      Comment("Swing Evaluation Trader\nwaiting for enough MT5 market data");
      return;
   }
   eval.signal_time = now;

   LastEvaluation = eval;
   HasLastEvaluation = true;
   RenderEvaluation(eval);
   LogSignalIfNeeded(eval);
   if(eval.action == "hold")
      return;
   if(InpManualButtonOnly)
      return;
   if(InpSignalOnly || !InpEnableTrading || !InpAllowLiveTrading)
      return;
   TryExecute(eval);
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

   MqlRates m5[];
   ArraySetAsSeries(m5, true);
   int m5Copied = CopyRates(_Symbol, PERIOD_M5, 0, 20, m5);
   double m5CloseSlowAtr = 0.0;
   if(m5Copied >= 3 && atrM5 > 0.0)
      m5CloseSlowAtr = (m5[1].close - emaSlowM5) / atrM5;
   double m1AlternatingRatio = M1AlternatingRatio(m1, copied, 14);
   eval.m30_trend = EmaTrendText(emaFastM30, emaSlowM30);
   eval.m15_trend = EmaTrendText(emaFastM15, emaSlowM15);
   eval.m5_trend = EmaTrendText(emaFastM5, emaSlowM5);
   eval.m30_slope = EmaSlopeText(emaFastM30, emaFastM30Prev);
   eval.m15_slope = EmaSlopeText(emaFastM15, emaFastM15Prev);
   eval.trend_alignment = TrendAlignmentText(eval.m30_trend, eval.m15_trend, eval.m5_trend);

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
   eval.m1_close_position = m1ClosePosition;
   eval.m1_body_atr = m1BodyAtr;
   eval.m5_close_slow_atr = m5CloseSlowAtr;
   eval.m1_alternating_ratio = m1AlternatingRatio;
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
   if(InpUseBuyM30M15UpGate && (eval.m30_trend != "up" || eval.m15_trend != "up"))
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
      if(eval.m30_trend == "down" && eval.m15_trend == "up")
      {
         sellTrendPass = false;
         AddReason(sellReasons, "sell trend fit rejected: M30 down M15 up");
      }
      else if(eval.trend_alignment == "m15_m5_up" || eval.trend_alignment == "m30_m15_up")
      {
         sellTrendPass = false;
         AddReason(sellReasons, StringFormat("sell trend fit rejected: %s", eval.trend_alignment));
      }
      if(!sellTrendPass)
         sellScore -= InpScoreRiskPenalty;
      else
         AddReason(sellReasons, "sell trend fit filter passed");
   }
   if(InpUseSellM30M15DownGate && (eval.m30_trend != "down" || eval.m15_trend != "down"))
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

   int spread = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints)
   {
      eval.action = "hold";
      eval.score = MathMax(buyScore, sellScore);
      eval.reason = StringFormat("spread too wide: %d > %d", spread, InpMaxSpreadPoints);
      return true;
   }
   if(IsRolloverBlocked())
   {
      eval.action = "hold";
      eval.score = MathMax(buyScore, sellScore);
      eval.reason = "rollover no-entry window";
      return true;
   }

   double buyDecisionScore = InpEnableBuy ? buyScore : -1000000.0;
   double sellDecisionScore = InpEnableSell ? sellScore : -1000000.0;

   if(InpEnableBuy && buyPlan.valid && buyScore >= InpMinScore && buyScore >= sellDecisionScore + InpMinDominance)
   {
      ApplyPlanToEvaluation("buy", buyScore, buyReasons, buyPlan, eval);
      return true;
   }
   if(InpEnableSell && sellPlan.valid && sellScore >= InpMinScore && sellScore >= buyDecisionScore + InpMinDominance)
   {
      ApplyPlanToEvaluation("sell", sellScore, sellReasons, sellPlan, eval);
      return true;
   }

   eval.action = "hold";
   if(!InpEnableBuy && !InpEnableSell)
   {
      eval.score = 0.0;
      eval.reason = "buy and sell disabled";
   }
   else if(!InpEnableBuy)
   {
      eval.score = sellDecisionScore;
      eval.reason = StringFormat("no dominant setup; buy disabled sell=%.1f", sellScore);
   }
   else if(!InpEnableSell)
   {
      eval.score = buyDecisionScore;
      eval.reason = StringFormat("no dominant setup; buy=%.1f sell disabled", buyScore);
   }
   else
   {
      eval.score = MathMax(buyDecisionScore, sellDecisionScore);
      eval.reason = StringFormat("no dominant setup; buy=%.1f sell=%.1f", buyScore, sellScore);
   }
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

void TryExecute(EvaluationResult &eval)
{
   datetime now = TimeCurrent();
   if(now - LastTradeTime < InpMinSecondsBetweenTrades)
      return;

   datetime barTime = iTime(_Symbol, PERIOD_M1, 0);
   if(barTime > 0 && LastTradeBarTime == barTime)
      return;

   string rejection = "";
   if(!ExecutionAllowed(eval, rejection))
   {
      AppendTradeCsv("reject", eval, 0, 0, 0, InpLot, 0.0, 0.0, 0.0, 0.0, 0.0, rejection);
      PrintFormat("Swing Evaluation Trader: execution rejected action=%s score=%.1f reason=%s",
                  eval.action, eval.score, rejection);
      return;
   }

   bool sent = false;
   if(eval.action == "buy")
      sent = Trade.Buy(InpLot, _Symbol, 0.0, eval.sl, eval.tp, "swing-eval buy");
   else if(eval.action == "sell")
      sent = Trade.Sell(InpLot, _Symbol, 0.0, eval.sl, eval.tp, "swing-eval sell");

   LastTradeTime = now;
   LastTradeBarTime = barTime;

   if(sent)
   {
      ulong order = Trade.ResultOrder();
      ulong deal = Trade.ResultDeal();
      ulong positionId = 0;
      double dealPrice = 0.0;
      if(deal > 0 && HistoryDealSelect(deal))
      {
         positionId = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
         dealPrice = HistoryDealGetDouble(deal, DEAL_PRICE);
      }
      RememberActiveSignal(positionId, eval);
      AppendTradeCsv("open", eval, order, deal, positionId, InpLot, dealPrice, 0.0, 0.0, 0.0, 0.0, "order sent");
      PrintFormat("Swing Evaluation Trader: %s sent lot=%.2f score=%.1f sl=%.2f tp=%.2f rr=%.1f",
                  eval.action, InpLot, eval.score, eval.sl, eval.tp, eval.rr);
   }
   else
   {
      AppendTradeCsv("reject", eval, Trade.ResultOrder(), Trade.ResultDeal(), 0, InpLot, 0.0, 0.0, 0.0, 0.0, 0.0, Trade.ResultComment());
      PrintFormat("Swing Evaluation Trader: order failed retcode=%d comment=%s",
                  Trade.ResultRetcode(), Trade.ResultComment());
   }
}

bool ExecutionAllowed(EvaluationResult &eval, string &reason)
{
   if(eval.action != "buy" && eval.action != "sell")
   {
      reason = "no tradable action";
      return false;
   }
   if(InpSignalOnly || !InpEnableTrading || !InpAllowLiveTrading)
   {
      reason = "live trading flags are not enabled";
      return false;
   }
   if(InpRequireStrategyTester && !IsStrategyTesterContext())
   {
      reason = "Strategy Tester required by preset";
      return false;
   }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
   {
      reason = "terminal or EA trading is disabled";
      return false;
   }
   ResetDailyStatsIfNeeded(TimeCurrent());
   if(DailyLossLimitReached())
   {
      reason = StringFormat("daily loss stop reached %.2f <= -%.2f", StatDailyNetProfit, InpDailyLossLimit);
      return false;
   }
   if(ConsecutiveLossLimitReached())
   {
      if(InpConsecutiveLossCooldownMinutes > 0)
         reason = StringFormat("consecutive loss cooldown active %d >= %d until %s",
                               StatConsecutiveLosses,
                               InpConsecutiveLossLimit,
                               TimeToString(StatConsecutiveLossCooldownUntil, TIME_DATE | TIME_SECONDS));
      else
         reason = StringFormat("consecutive loss stop reached %d >= %d", StatConsecutiveLosses, InpConsecutiveLossLimit);
      return false;
   }
   if((int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpreadPoints)
   {
      reason = "spread too wide";
      return false;
   }
   if(IsRolloverBlocked())
   {
      reason = "rollover no-entry window";
      return false;
   }
   if(InpLot <= 0.0 || InpLot > InpMaxSingleLot)
   {
      reason = "lot outside configured limits";
      return false;
   }
   if(!IsSymbolVolumeAllowed(_Symbol, InpLot))
   {
      reason = "lot outside broker symbol constraints";
      return false;
   }
   if(CountOpenPositionsForSymbol(_Symbol) >= InpMaxPositions)
   {
      reason = "max positions reached";
      return false;
   }
   if(OpenVolumeForSymbol(_Symbol) + InpLot > InpMaxTotalLot + 0.0000001)
   {
      reason = "max total lot reached";
      return false;
   }
   if(eval.sl <= 0.0 || eval.tp <= 0.0)
   {
      reason = "SL/TP missing";
      return false;
   }
   return true;
}

void RenderEvaluation(EvaluationResult &eval)
{
   string mode = "signal-only";
   if(!InpSignalOnly && InpEnableTrading && InpAllowLiveTrading)
      mode = "live-enabled";
   if(InpRequireStrategyTester && !IsStrategyTesterContext())
      mode = mode + "/tester-required";

   string text = "";
   text += "Swing Evaluation Trader\n";
   text += StringFormat("Mode: %s  Env: %s  Symbol: %s  Spread: %dpt\n",
                        mode,
                        ExecutionEnvironmentText(),
                        _Symbol,
                        (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD));
   text += StringFormat("Action: %s  Score: %.1f  Buy/Sell: %.1f / %.1f\n",
                        eval.action, eval.score, eval.buy_score, eval.sell_score);
   if(eval.action != "hold")
   {
      text += StringFormat("Entry: %.2f  SL: %.2f  TP: %.2f  RR: %.1f  SLpt: %.0f\n",
                           eval.entry, eval.sl, eval.tp, eval.rr, eval.stop_points);
   }
   text += "Reason: " + eval.reason;
   Comment(text);

   if(InpDrawSignalLines)
   {
      if(eval.action == "hold")
      {
         if(InpClearLinesOnHold)
            DeletePlanLines();
      }
      else
      {
         DrawPlanLines(eval);
      }
   }
   if(InpShowChartEntryButton)
      DrawEntryButton(eval);
   else
      DeleteEntryButton();
}

void DrawPlanLines(EvaluationResult &eval)
{
   string prefix = "SET_" + _Symbol + "_";
   DrawHLine(prefix + "ENTRY", eval.entry, clrDodgerBlue, STYLE_SOLID);
   DrawHLine(prefix + "SL", eval.sl, clrTomato, STYLE_DASH);
   DrawHLine(prefix + "TP", eval.tp, clrLimeGreen, STYLE_DASH);
}

void DrawHLine(const string name, const double price, const color lineColor, const ENUM_LINE_STYLE style)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   ObjectSetDouble(0, name, OBJPROP_PRICE, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, lineColor);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
}

void DeletePlanLines()
{
   string prefix = "SET_" + _Symbol + "_";
   ObjectDelete(0, prefix + "ENTRY");
   ObjectDelete(0, prefix + "SL");
   ObjectDelete(0, prefix + "TP");
}

void DrawEntryButton(EvaluationResult &eval)
{
   string name = EntryButtonName();
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, InpButtonX);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, InpButtonY);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, InpButtonWidth);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, InpButtonHeight);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, ButtonColor(eval.action));
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetString(0, name, OBJPROP_TEXT, EntryButtonLabel(eval));
}

void DeleteEntryButton()
{
   ObjectDelete(0, EntryButtonName());
}

string EntryButtonName()
{
   return "SET_" + _Symbol + "_ENTRY_BUTTON";
}

string EntryButtonLabel(EvaluationResult &eval)
{
   if(eval.action == "buy")
      return "ENTRY BUY";
   if(eval.action == "sell")
      return "ENTRY SELL";
   return "WAIT";
}

color ButtonColor(const string action)
{
   if(action == "buy")
      return clrSeaGreen;
   if(action == "sell")
      return clrFireBrick;
   return clrDimGray;
}

bool IsStrategyTesterContext()
{
   return MQLInfoInteger(MQL_TESTER) ||
          MQLInfoInteger(MQL_FORWARD) ||
          MQLInfoInteger(MQL_OPTIMIZATION);
}

string ExecutionEnvironmentText()
{
   if(MQLInfoInteger(MQL_FORWARD))
      return "tester-forward";
   if(MQLInfoInteger(MQL_OPTIMIZATION))
      return "tester-optimization";
   if(MQLInfoInteger(MQL_TESTER))
      return "tester-backtest";
   if(MQLInfoInteger(MQL_VISUAL_MODE))
      return "tester-visual";
   return "live-chart";
}

void HandleEntryButtonClick()
{
   if(!HasLastEvaluation)
   {
      Print("Swing Evaluation Trader: button ignored; no evaluation yet.");
      return;
   }
   EvaluationResult eval = LastEvaluation;
   if(eval.action != "buy" && eval.action != "sell")
   {
      AppendTradeCsv("button", eval, 0, 0, 0, InpLot, 0.0, 0.0, 0.0, 0.0, 0.0, "button ignored: no tradable action");
      Print("Swing Evaluation Trader: button ignored; no tradable action.");
      return;
   }
   if(InpChartButtonDryRunOnly || !InpAllowChartButtonTrading)
   {
      AppendTradeCsv("button", eval, 0, 0, 0, InpLot, 0.0, 0.0, 0.0, 0.0, 0.0, "button dry-run: no order sent");
      PrintFormat("Swing Evaluation Trader: button dry-run action=%s score=%.1f entry=%.2f sl=%.2f tp=%.2f",
                  eval.action, eval.score, eval.entry, eval.sl, eval.tp);
      return;
   }
   TryExecute(eval);
}

void LogSignalIfNeeded(EvaluationResult &eval)
{
   if(!InpWriteCsvLog || !InpLogSignalRows)
      return;
   datetime barTime = iTime(_Symbol, PERIOD_M1, 0);
   if(barTime > 0 && LastSignalLogBarTime == barTime)
      return;
   LastSignalLogBarTime = barTime;
   AppendTradeCsv("signal", eval, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "signal generated");
}

void AppendTradeCsv(const string event, EvaluationResult &eval, const ulong order,
                    const ulong deal, const ulong positionId, const double volume,
                    const double dealPrice, const double profit, const double commission,
                    const double swap, const double netProfit, const string message)
{
   if(!InpWriteCsvLog || InpCsvLogFile == "")
      return;

   int handle = FileOpen(
      InpCsvLogFile,
      FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE,
      ','
   );
   if(handle == INVALID_HANDLE)
   {
      PrintFormat("Swing Evaluation Trader: failed to open CSV log %s err=%d", InpCsvLogFile, GetLastError());
      return;
   }

   bool writeHeader = FileSize(handle) == 0;
   FileSeek(handle, 0, SEEK_END);
   if(writeHeader)
   {
      FileWrite(
         handle,
         "event",
         "server_time",
         "signal_time",
         "opened_at",
         "entry_server_hour",
         "symbol",
         "magic",
         "action",
         "volume",
         "score",
         "buy_score",
         "sell_score",
         "entry",
         "sl",
         "tp",
         "risk_reward",
         "stop_points",
         "spread_points",
         "latency_seconds",
         "hold_seconds",
         "order",
         "deal",
         "position_id",
         "deal_price",
         "profit",
         "commission",
         "swap",
         "net_profit",
         "closed_trades",
         "daily_closed_trades",
         "wins",
         "losses",
         "daily_net_profit",
         "profit_factor",
         "consecutive_losses",
         "max_losing_streak",
         "m30_trend",
         "m15_trend",
         "m5_trend",
         "m30_slope",
         "m15_slope",
         "trend_alignment",
         "m1_close_position",
         "m1_body_atr",
         "m5_close_slow_atr",
         "m1_alternating_ratio",
         "message",
         "reason"
      );
   }

   string cleanReason = CleanCsvText(eval.reason);
   string cleanMessage = CleanCsvText(message);
   FileWrite(
      handle,
      event,
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
      SignalTimeText(eval),
      OpenedAtText(event, eval),
      EntryServerHourText(event, eval),
      _Symbol,
      ULongText(InpMagicNumber),
      eval.action,
      DoubleToString(volume, 2),
      DoubleToString(eval.score, 2),
      DoubleToString(eval.buy_score, 2),
      DoubleToString(eval.sell_score, 2),
      DoubleToString(eval.entry, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)),
      DoubleToString(eval.sl, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)),
      DoubleToString(eval.tp, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)),
      DoubleToString(eval.rr, 2),
      DoubleToString(eval.stop_points, 1),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD),
      LatencySeconds(event, eval),
      HoldSeconds(event, eval),
      ULongText(order),
      ULongText(deal),
      ULongText(positionId),
      DoubleToString(dealPrice, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)),
      DoubleToString(profit, 2),
      DoubleToString(commission, 2),
      DoubleToString(swap, 2),
      DoubleToString(netProfit, 2),
      StatClosedTrades,
      StatDailyClosedTrades,
      StatWins,
      StatLosses,
      DoubleToString(StatDailyNetProfit, 2),
      DoubleToString(ProfitFactor(), 4),
      StatConsecutiveLosses,
      StatMaxConsecutiveLosses,
      eval.m30_trend,
      eval.m15_trend,
      eval.m5_trend,
      eval.m30_slope,
      eval.m15_slope,
      eval.trend_alignment,
      DoubleToString(eval.m1_close_position, 4),
      DoubleToString(eval.m1_body_atr, 4),
      DoubleToString(eval.m5_close_slow_atr, 4),
      DoubleToString(eval.m1_alternating_ratio, 4),
      cleanMessage,
      cleanReason
   );
   FileClose(handle);
}

string CleanCsvText(string value)
{
   StringReplace(value, "\r", " ");
   StringReplace(value, "\n", " ");
   return value;
}

string ULongText(const ulong value)
{
   return StringFormat("%I64u", value);
}

string SignalTimeText(EvaluationResult &eval)
{
   if(eval.signal_time <= 0)
      return "";
   return TimeToString(eval.signal_time, TIME_DATE | TIME_SECONDS);
}

datetime EntryTimeForCsv(const string event, EvaluationResult &eval)
{
   if(event == "open")
      return TimeCurrent();
   if(event == "close" && eval.opened_at > 0)
      return eval.opened_at;
   return 0;
}

string OpenedAtText(const string event, EvaluationResult &eval)
{
   datetime entryTime = EntryTimeForCsv(event, eval);
   if(entryTime <= 0)
      return "";
   return TimeToString(entryTime, TIME_DATE | TIME_SECONDS);
}

string EntryServerHourText(const string event, EvaluationResult &eval)
{
   datetime entryTime = EntryTimeForCsv(event, eval);
   if(entryTime <= 0)
      return "";
   MqlDateTime dt;
   TimeToStruct(entryTime, dt);
   return StringFormat("%02d:00-%02d:00", dt.hour, (dt.hour + 1) % 24);
}

int LatencySeconds(const string event, EvaluationResult &eval)
{
   if(eval.signal_time <= 0)
      return 0;
   if(event == "open" || event == "reject" || event == "signal")
      return (int)(TimeCurrent() - eval.signal_time);
   if(event == "close" && eval.opened_at > 0)
      return (int)(eval.opened_at - eval.signal_time);
   return 0;
}

int HoldSeconds(const string event, EvaluationResult &eval)
{
   if(event != "close" || eval.opened_at <= 0)
      return 0;
   return (int)(TimeCurrent() - eval.opened_at);
}

void ResetDailyStatsIfNeeded(const datetime now)
{
   int key = DateKey(now);
   if(StatDailyDateKey == key)
      return;
   StatDailyDateKey = key;
   StatDailyClosedTrades = 0;
   StatDailyNetProfit = 0.0;
}

int DateKey(const datetime value)
{
   MqlDateTime dt;
   TimeToStruct(value, dt);
   return dt.year * 10000 + dt.mon * 100 + dt.day;
}

bool DailyLossLimitReached()
{
   return InpUseDailyLossStop && InpDailyLossLimit > 0.0 && StatDailyNetProfit <= -InpDailyLossLimit;
}

bool ConsecutiveLossLimitReached()
{
   if(!InpUseConsecutiveLossStop || InpConsecutiveLossLimit <= 0)
      return false;
   if(StatConsecutiveLosses < InpConsecutiveLossLimit)
      return false;
   if(InpConsecutiveLossCooldownMinutes <= 0)
      return true;

   datetime now = TimeCurrent();
   if(StatConsecutiveLossCooldownUntil <= 0)
      StatConsecutiveLossCooldownUntil = now + InpConsecutiveLossCooldownMinutes * 60;
   if(now < StatConsecutiveLossCooldownUntil)
      return true;

   StatConsecutiveLosses = 0;
   StatConsecutiveLossCooldownUntil = 0;
   return false;
}

void ArmConsecutiveLossCooldown(const datetime now)
{
   if(!InpUseConsecutiveLossStop || InpConsecutiveLossLimit <= 0)
      return;
   if(InpConsecutiveLossCooldownMinutes <= 0)
      return;
   if(StatConsecutiveLosses < InpConsecutiveLossLimit)
      return;

   datetime until = now + InpConsecutiveLossCooldownMinutes * 60;
   if(until > StatConsecutiveLossCooldownUntil)
      StatConsecutiveLossCooldownUntil = until;
}

void RememberActiveSignal(const ulong positionId, EvaluationResult &eval)
{
   if(positionId == 0)
      return;
   int index = FindActiveSignal(positionId);
   if(index < 0)
   {
      index = ArraySize(ActiveSignals);
      ArrayResize(ActiveSignals, index + 1);
   }
   ActiveSignals[index].position_id = positionId;
   ActiveSignals[index].action = eval.action;
   ActiveSignals[index].score = eval.score;
   ActiveSignals[index].buy_score = eval.buy_score;
   ActiveSignals[index].sell_score = eval.sell_score;
   ActiveSignals[index].entry = eval.entry;
   ActiveSignals[index].sl = eval.sl;
   ActiveSignals[index].tp = eval.tp;
   ActiveSignals[index].rr = eval.rr;
   ActiveSignals[index].stop_points = eval.stop_points;
   ActiveSignals[index].signal_time = eval.signal_time;
   ActiveSignals[index].opened_at = TimeCurrent();
   ActiveSignals[index].m30_trend = eval.m30_trend;
   ActiveSignals[index].m15_trend = eval.m15_trend;
   ActiveSignals[index].m5_trend = eval.m5_trend;
   ActiveSignals[index].m30_slope = eval.m30_slope;
   ActiveSignals[index].m15_slope = eval.m15_slope;
   ActiveSignals[index].trend_alignment = eval.trend_alignment;
   ActiveSignals[index].m1_close_position = eval.m1_close_position;
   ActiveSignals[index].m1_body_atr = eval.m1_body_atr;
   ActiveSignals[index].m5_close_slow_atr = eval.m5_close_slow_atr;
   ActiveSignals[index].m1_alternating_ratio = eval.m1_alternating_ratio;
   ActiveSignals[index].reason = eval.reason;
}

int FindActiveSignal(const ulong positionId)
{
   if(positionId == 0)
      return -1;
   for(int i = 0; i < ArraySize(ActiveSignals); i++)
   {
      if(ActiveSignals[i].position_id == positionId)
         return i;
   }
   return -1;
}

void EvaluationFromActiveSignal(const int index, EvaluationResult &eval)
{
   if(index < 0 || index >= ArraySize(ActiveSignals))
      return;
   eval.action = ActiveSignals[index].action;
   eval.tradable = true;
   eval.score = ActiveSignals[index].score;
   eval.buy_score = ActiveSignals[index].buy_score;
   eval.sell_score = ActiveSignals[index].sell_score;
   eval.entry = ActiveSignals[index].entry;
   eval.sl = ActiveSignals[index].sl;
   eval.tp = ActiveSignals[index].tp;
   eval.rr = ActiveSignals[index].rr;
   eval.stop_points = ActiveSignals[index].stop_points;
   eval.signal_time = ActiveSignals[index].signal_time;
   eval.opened_at = ActiveSignals[index].opened_at;
   eval.m30_trend = ActiveSignals[index].m30_trend;
   eval.m15_trend = ActiveSignals[index].m15_trend;
   eval.m5_trend = ActiveSignals[index].m5_trend;
   eval.m30_slope = ActiveSignals[index].m30_slope;
   eval.m15_slope = ActiveSignals[index].m15_slope;
   eval.trend_alignment = ActiveSignals[index].trend_alignment;
   eval.m1_close_position = ActiveSignals[index].m1_close_position;
   eval.m1_body_atr = ActiveSignals[index].m1_body_atr;
   eval.m5_close_slow_atr = ActiveSignals[index].m5_close_slow_atr;
   eval.m1_alternating_ratio = ActiveSignals[index].m1_alternating_ratio;
   eval.reason = ActiveSignals[index].reason;
}

void RemoveActiveSignal(const int index)
{
   int size = ArraySize(ActiveSignals);
   if(index < 0 || index >= size)
      return;
   for(int i = index; i < size - 1; i++)
      ActiveSignals[i] = ActiveSignals[i + 1];
   ArrayResize(ActiveSignals, size - 1);
}

string CloseDealActionName(const long dealType)
{
   if(dealType == DEAL_TYPE_BUY)
      return "buy_deal";
   if(dealType == DEAL_TYPE_SELL)
      return "sell_deal";
   return "unknown_deal";
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
   eval.opened_at = 0;
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
   eval.opened_at = 0;
   eval.m30_trend = "unknown";
   eval.m15_trend = "unknown";
   eval.m5_trend = "unknown";
   eval.m30_slope = "unknown";
   eval.m15_slope = "unknown";
   eval.trend_alignment = "unknown";
   eval.m1_close_position = 0.0;
   eval.m1_body_atr = 0.0;
   eval.m5_close_slow_atr = 0.0;
   eval.m1_alternating_ratio = 0.0;
   eval.reason = "";
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

string EmaTrendText(const double fast, const double slow)
{
   if(fast > slow)
      return "up";
   if(fast < slow)
      return "down";
   return "flat";
}

string EmaSlopeText(const double current, const double previous)
{
   if(current > previous)
      return "rising";
   if(current < previous)
      return "falling";
   return "flat";
}

string TrendAlignmentText(const string m30, const string m15, const string m5)
{
   if(m30 == "up" && m15 == "up" && m5 == "up")
      return "all_up";
   if(m30 == "down" && m15 == "down" && m5 == "down")
      return "all_down";
   if(m30 == "up" && m15 == "up")
      return "m30_m15_up";
   if(m30 == "down" && m15 == "down")
      return "m30_m15_down";
   if(m15 == "up" && m5 == "up")
      return "m15_m5_up";
   if(m15 == "down" && m5 == "down")
      return "m15_m5_down";
   return "mixed";
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

int CountOpenPositionsForSymbol(const string symbol)
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(!PositionMatchesScope(symbol))
         continue;
      count++;
   }
   return count;
}

double OpenVolumeForSymbol(const string symbol)
{
   double volume = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(!PositionMatchesScope(symbol))
         continue;
      volume += PositionGetDouble(POSITION_VOLUME);
   }
   return volume;
}

bool PositionMatchesScope(const string symbol)
{
   if(PositionGetString(POSITION_SYMBOL) != symbol)
      return false;
   if(InpCountAllSymbolPositions)
      return true;
   return (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber;
}

bool IsSymbolVolumeAllowed(const string symbol, const double volume)
{
   double minVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(minVolume > 0.0 && volume + 0.0000001 < minVolume)
      return false;
   if(maxVolume > 0.0 && volume > maxVolume + 0.0000001)
      return false;
   if(step > 0.0)
   {
      double steps = volume / step;
      if(MathAbs(steps - MathRound(steps)) > 0.0000001)
         return false;
   }
   return true;
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

double ProfitFactor()
{
   if(StatGrossLoss <= 0.0)
   {
      if(StatGrossProfit > 0.0)
         return 99.0;
      return 0.0;
   }
   return StatGrossProfit / StatGrossLoss;
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
