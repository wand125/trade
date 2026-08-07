//+------------------------------------------------------------------+
//| AI_Bridge_Advisor.mq5                                           |
//| Sends MT5 snapshots to a local AI bridge and optionally trades.  |
//+------------------------------------------------------------------+
#property strict

#include <Trade/Trade.mqh>

input string InpBridgeUrl = "http://127.0.0.1:8765/snapshot";
input string InpBridgeToken = "";
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M1;
input int InpBarsToSend = 60;
input bool InpSendMultiTimeframes = true;
input int InpHigherTimeframeBars = 40;
input int InpSwingTimeframeBars = 120;   // H1/H4/D1 用。120本で H1=5日 / H4=20日 / D1=半年
input int InpMaxHistoryHours = 168;
input bool InpSendAccountInfo = true;
input bool InpSendDealHistory = true;
input int InpDealsHistoryHours = 24;
input int InpMaxDealsToSend = 10;
input int InpRequestEverySeconds = 30;
input bool InpEnableTimerFallback = true;
input bool InpSaveOnlyMode = true;
input bool InpRequestOnlyFromMatchingChart = true;
input bool InpPollCodexTradeCommands = false;
input int InpWebRequestRetries = 1;
input int InpWebRequestRetryDelayMs = 250;
input bool InpLogSuccessfulSnapshots = false;
input bool InpEnableTrading = false;
input double InpFixedLot = 0.01;
input int InpMaxSpreadPoints = 80;
input double InpMinConfidence = 0.70;
input int InpMaxPositions = 1;
input ulong InpMagicNumber = 26070201;
input int InpDeviationPoints = 50;
input bool InpAllowCodexTrading = false;
input double InpCodexMaxLot = 0.01;
input int InpCodexMaxSpreadPoints = 80;
input int InpCodexMaxPositions = 1;
input bool InpCodexRequireSlTp = true;
input bool InpCodexEnableOco = true;
input int InpCodexMaxPendingOrders = 4;
input string InpCodexAllowedSymbol = "";

CTrade Trade;
datetime LastRequestTime = 0;
datetime LastTimerRequestTime = 0;
string CurrentHistoryRequestId = "";
int CurrentHistoryChunkSize = 240;
string CurrentDealHistoryRequestId = "";
int CurrentDealHistoryDays = 0;
int CurrentDealHistoryMaxDeals = 0;
int CurrentDealHistoryChunkSize = 500;
int CurrentDealHistoryNextChunk = 0;
string EmbeddedDealHistoryRequestId = "";
int EmbeddedDealHistoryNextChunk = 0;
int EmbeddedDealHistoryChunkCount = 0;
int EmbeddedDealHistoryDealsToSend = 0;
int EmbeddedDealHistoryTotalDeals = 0;
string PendingEmbeddedDealHistoryRequestId = "";
int PendingEmbeddedDealHistoryChunkIndex = -1;
string PendingEmbeddedDealHistoryChunkJson = "";
int RsiHandle = INVALID_HANDLE;
int EmaFastHandle = INVALID_HANDLE;
int EmaSlowHandle = INVALID_HANDLE;
int AtrHandle = INVALID_HANDLE;
string PendingTradeResultJson = "";

int OnInit()
{
   Trade.SetExpertMagicNumber(InpMagicNumber);
   Trade.SetDeviationInPoints(InpDeviationPoints);

   RsiHandle = iRSI(_Symbol, InpTimeframe, 14, PRICE_CLOSE);
   EmaFastHandle = iMA(_Symbol, InpTimeframe, 9, 0, MODE_EMA, PRICE_CLOSE);
   EmaSlowHandle = iMA(_Symbol, InpTimeframe, 21, 0, MODE_EMA, PRICE_CLOSE);
   AtrHandle = iATR(_Symbol, InpTimeframe, 14);

   if(RsiHandle == INVALID_HANDLE || EmaFastHandle == INVALID_HANDLE ||
      EmaSlowHandle == INVALID_HANDLE || AtrHandle == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles.");
      return INIT_FAILED;
   }

   if(InpEnableTimerFallback)
      EventSetTimer(1);

   Print("AI Bridge Advisor initialized v20260805a. Add allowed WebRequest URL: http://127.0.0.1:8765");
   if(!IsBridgeSender())
      PrintFormat("AI Bridge Advisor passive on chart timeframe=%s; active sender timeframe=%s",
                  EnumToString(_Period), EnumToString(InpTimeframe));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(InpEnableTimerFallback)
      EventKillTimer();
   if(RsiHandle != INVALID_HANDLE) IndicatorRelease(RsiHandle);
   if(EmaFastHandle != INVALID_HANDLE) IndicatorRelease(EmaFastHandle);
   if(EmaSlowHandle != INVALID_HANDLE) IndicatorRelease(EmaSlowHandle);
   if(AtrHandle != INVALID_HANDLE) IndicatorRelease(AtrHandle);
}

void OnTimer()
{
   if(!InpEnableTimerFallback)
      return;
   if(!IsBridgeSender())
      return;

   datetime now = TimeLocal();
   if(now - LastTimerRequestTime < InpRequestEverySeconds)
      return;
   LastTimerRequestTime = now;

   int requestedHistoryHours = GetRequestedHistoryHours();
   string historyRequestId = CurrentHistoryRequestId;
   int historyChunkSize = CurrentHistoryChunkSize;
   string dealHistoryRequestId = CurrentDealHistoryRequestId;
   int dealHistoryDays = CurrentDealHistoryDays;
   int dealHistoryMaxDeals = CurrentDealHistoryMaxDeals;
   int dealHistoryChunkSize = CurrentDealHistoryChunkSize;

   if(requestedHistoryHours > 0 && historyRequestId != "")
      SendHistoryChunks(historyRequestId, requestedHistoryHours, historyChunkSize);
   if(dealHistoryRequestId == "")
      ResetEmbeddedDealHistoryState();
}

void OnTick()
{
   if(!IsBridgeSender())
      return;

   datetime now = TimeCurrent();
   if(now - LastRequestTime < InpRequestEverySeconds)
      return;
   LastRequestTime = now;

   int requestedHistoryHours = GetRequestedHistoryHours();
   string historyRequestId = CurrentHistoryRequestId;
   int historyChunkSize = CurrentHistoryChunkSize;
   string dealHistoryRequestId = CurrentDealHistoryRequestId;
   int dealHistoryDays = CurrentDealHistoryDays;
   int dealHistoryMaxDeals = CurrentDealHistoryMaxDeals;
   int dealHistoryChunkSize = CurrentDealHistoryChunkSize;

   if(InpPollCodexTradeCommands)
      CheckTradeCommand();
   if(InpCodexEnableOco)
      EnforceOcoPairs();

   string payload = BuildSnapshotJson();
   if(payload == "")
      return;

   string response = PostJson(InpBridgeUrl, payload);
   if(response == "")
      return;

   bool ok = JsonGetBool(response, "ok", false);
   if(!ok)
   {
      Print("Bridge error: ", response);
      return;
   }
   if(PendingTradeResultJson != "")
      PendingTradeResultJson = "";
   CommitEmbeddedDealHistoryChunk();

   string action = "hold";
   double confidence = 0.0;
   double stopLoss = 0.0;
   double takeProfit = 0.0;
   if(InpSaveOnlyMode)
   {
      if(InpLogSuccessfulSnapshots)
         PrintFormat("Snapshot saved server_time=%s", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS));
   }
   else
   {
      action = JsonGetString(response, "action", "hold");
      confidence = JsonGetDouble(response, "confidence", 0.0);
      stopLoss = JsonGetDouble(response, "stop_loss", 0.0);
      takeProfit = JsonGetDouble(response, "take_profit", 0.0);
      string reason = JsonGetString(response, "reason", "");

      PrintFormat("AI signal action=%s confidence=%.2f sl=%.2f tp=%.2f reason=%s",
                  action, confidence, stopLoss, takeProfit, reason);
   }

   if(requestedHistoryHours > 0 && historyRequestId != "")
      SendHistoryChunks(historyRequestId, requestedHistoryHours, historyChunkSize);
   if(dealHistoryRequestId == "")
      ResetEmbeddedDealHistoryState();

   if(InpSaveOnlyMode || !InpEnableTrading)
      return;

   TryTrade(action, confidence, stopLoss, takeProfit);
}

bool IsBridgeSender()
{
   if(!InpRequestOnlyFromMatchingChart)
      return true;
   return _Period == InpTimeframe;
}

string BuildSnapshotJson()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
   {
      Print("SymbolInfoTick failed.");
      return "";
   }

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, InpTimeframe, 0, InpBarsToSend, rates);
   if(copied <= 0)
   {
      Print("CopyRates failed.");
      return "";
   }

   double rsi = IndicatorValue(RsiHandle);
   double emaFast = IndicatorValue(EmaFastHandle);
   double emaSlow = IndicatorValue(EmaSlowHandle);
   double atr = IndicatorValue(AtrHandle);
   int spreadPoints = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   string json = "{";
   json += StringFormat("\"symbol\":\"%s\",", JsonEscape(_Symbol));
   json += StringFormat("\"timeframe\":\"%s\",", EnumToString(InpTimeframe));
   json += StringFormat("\"server_time\":\"%s\",", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS));
   json += "\"history_hours\":0,";
   json += StringFormat("\"bid\":%s,", DoubleToJson(tick.bid, digits));
   json += StringFormat("\"ask\":%s,", DoubleToJson(tick.ask, digits));
   json += StringFormat("\"spread_points\":%d,", spreadPoints);
   json += StringFormat("\"digits\":%d,", digits);
   json += StringFormat("\"point\":%s,", DoubleToJson(point, digits + 2));
   json += "\"indicators\":{";
   json += StringFormat("\"rsi14\":%s,", DoubleToJson(rsi, 4));
   json += StringFormat("\"ema_fast\":%s,", DoubleToJson(emaFast, digits));
   json += StringFormat("\"ema_slow\":%s,", DoubleToJson(emaSlow, digits));
   json += StringFormat("\"atr14\":%s", DoubleToJson(atr, digits));
   json += "},\"bars\":[";

   for(int i = copied - 1; i >= 0; i--)
   {
      if(i != copied - 1)
         json += ",";
      json += "{";
      json += StringFormat("\"time\":\"%s\",", TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES));
      json += StringFormat("\"open\":%s,", DoubleToJson(rates[i].open, digits));
      json += StringFormat("\"high\":%s,", DoubleToJson(rates[i].high, digits));
      json += StringFormat("\"low\":%s,", DoubleToJson(rates[i].low, digits));
      json += StringFormat("\"close\":%s,", DoubleToJson(rates[i].close, digits));
      json += StringFormat("\"tick_volume\":%I64d", rates[i].tick_volume);
      json += "}";
   }

   json += "]";
   if(InpSendMultiTimeframes)
   {
      json += ",\"timeframes\":{";
      json += "\"M1\":" + BuildTimeframeJson(PERIOD_M1, InpBarsToSend, digits);
      json += ",\"M5\":" + BuildTimeframeJson(PERIOD_M5, InpHigherTimeframeBars, digits);
      json += ",\"M15\":" + BuildTimeframeJson(PERIOD_M15, InpHigherTimeframeBars, digits);
      json += ",\"M30\":" + BuildTimeframeJson(PERIOD_M30, InpHigherTimeframeBars, digits);
      // スイング判断には日単位の地図が要る。M30までだと20時間しか見えない。
      json += ",\"H1\":" + BuildTimeframeJson(PERIOD_H1, InpSwingTimeframeBars, digits);
      json += ",\"H4\":" + BuildTimeframeJson(PERIOD_H4, InpSwingTimeframeBars, digits);
      json += ",\"D1\":" + BuildTimeframeJson(PERIOD_D1, InpSwingTimeframeBars, digits);
      json += "}";
   }
   if(InpSendAccountInfo)
      json += ",\"account\":" + BuildAccountJson(digits);
   if(PendingTradeResultJson != "")
      json += ",\"trade_result\":" + PendingTradeResultJson;
   string embeddedDealHistoryChunk = BuildNextEmbeddedDealHistoryChunkJson(digits);
   if(embeddedDealHistoryChunk != "")
      json += ",\"embedded_deal_history_chunk\":" + embeddedDealHistoryChunk;
   json += "}";
   return json;
}

string BuildAccountJson(const int digits)
{
   string json = "{";
   json += StringFormat("\"login\":%I64d,", AccountInfoInteger(ACCOUNT_LOGIN));
   json += StringFormat("\"trade_mode\":%d,", (int)AccountInfoInteger(ACCOUNT_TRADE_MODE));
   json += StringFormat("\"leverage\":%d,", (int)AccountInfoInteger(ACCOUNT_LEVERAGE));
   json += StringFormat("\"currency\":\"%s\",", JsonEscape(AccountInfoString(ACCOUNT_CURRENCY)));
   json += StringFormat("\"balance\":%s,", DoubleToJson(AccountInfoDouble(ACCOUNT_BALANCE), 2));
   json += StringFormat("\"equity\":%s,", DoubleToJson(AccountInfoDouble(ACCOUNT_EQUITY), 2));
   json += StringFormat("\"margin\":%s,", DoubleToJson(AccountInfoDouble(ACCOUNT_MARGIN), 2));
   json += StringFormat("\"free_margin\":%s,", DoubleToJson(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2));
   json += StringFormat("\"margin_level\":%s,", DoubleToJson(AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), 2));
   json += "\"positions\":" + BuildPositionsJson(digits) + ",";
   json += "\"deals\":" + (InpSendDealHistory ? BuildDealsJson(digits) : "[]");
   json += "}";
   return json;
}

string BuildPositionsJson(const int digits)
{
   string json = "[";
   bool first = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(!first)
         json += ",";
      first = false;

      string symbol = PositionGetString(POSITION_SYMBOL);
      long type = PositionGetInteger(POSITION_TYPE);
      double volume = PositionGetDouble(POSITION_VOLUME);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      double profit = PositionGetDouble(POSITION_PROFIT);
      long magic = PositionGetInteger(POSITION_MAGIC);
      datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);

      json += "{";
      json += StringFormat("\"ticket\":%I64u,", ticket);
      json += StringFormat("\"symbol\":\"%s\",", JsonEscape(symbol));
      json += StringFormat("\"type\":\"%s\",", type == POSITION_TYPE_BUY ? "buy" : "sell");
      json += StringFormat("\"volume\":%s,", DoubleToJson(volume, 2));
      json += StringFormat("\"open_price\":%s,", DoubleToJson(openPrice, digits));
      json += StringFormat("\"current_price\":%s,", DoubleToJson(currentPrice, digits));
      json += StringFormat("\"sl\":%s,", DoubleToJson(sl, digits));
      json += StringFormat("\"tp\":%s,", DoubleToJson(tp, digits));
      json += StringFormat("\"profit\":%s,", DoubleToJson(profit, 2));
      json += StringFormat("\"magic\":%d,", (int)magic);
      json += StringFormat("\"open_time\":\"%s\"", TimeToString(openTime, TIME_DATE|TIME_SECONDS));
      json += "}";
   }
   json += "]";
   return json;
}

string BuildDealsJson(const int digits)
{
   datetime toTime = TimeCurrent();
   int hours = InpDealsHistoryHours;
   if(hours < 1)
      hours = 1;
   if(hours > 24 * 30)
      hours = 24 * 30;
   datetime fromTime = toTime - hours * 3600;

   string json = "[";
   if(!HistorySelect(fromTime, toTime))
      return json + "]";

   int total = HistoryDealsTotal();
   int sent = 0;
   bool first = true;
   for(int i = total - 1; i >= 0 && sent < InpMaxDealsToSend; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0)
         continue;

      if(!first)
         json += ",";
      first = false;
      sent++;
      json += BuildDealJson(ticket, digits);
   }
   json += "]";
   return json;
}

string BuildDealJson(const ulong ticket, const int digits)
{
   string symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
   long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
   long type = HistoryDealGetInteger(ticket, DEAL_TYPE);
   double volume = HistoryDealGetDouble(ticket, DEAL_VOLUME);
   double price = HistoryDealGetDouble(ticket, DEAL_PRICE);
   double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
   double commission = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   double swap = HistoryDealGetDouble(ticket, DEAL_SWAP);
   datetime dealTime = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
   long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);

   string json = "{";
   json += StringFormat("\"ticket\":%I64u,", ticket);
   json += StringFormat("\"symbol\":\"%s\",", JsonEscape(symbol));
   json += StringFormat("\"type\":\"%s\",", DealTypeName(type));
   json += StringFormat("\"entry\":\"%s\",", DealEntryName(entry));
   json += StringFormat("\"volume\":%s,", DoubleToJson(volume, 2));
   json += StringFormat("\"price\":%s,", DoubleToJson(price, digits));
   json += StringFormat("\"profit\":%s,", DoubleToJson(profit, 2));
   json += StringFormat("\"commission\":%s,", DoubleToJson(commission, 2));
   json += StringFormat("\"swap\":%s,", DoubleToJson(swap, 2));
   json += StringFormat("\"magic\":%d,", (int)magic);
   json += StringFormat("\"time\":\"%s\"", TimeToString(dealTime, TIME_DATE|TIME_SECONDS));
   json += "}";
   return json;
}

void SendHistoryChunks(const string requestId, const int requestedHours, const int configuredChunkSize)
{
   int hours = requestedHours;
   if(hours < 1)
      return;
   if(hours > InpMaxHistoryHours)
      hours = InpMaxHistoryHours;

   int chunkSize = configuredChunkSize;
   if(chunkSize < 30)
      chunkSize = 240;

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   bool ok = true;
   ok = ok && SendHistoryTimeframe(requestId, hours, PERIOD_M1, hours * 60, chunkSize, digits);
   ok = ok && SendHistoryTimeframe(requestId, hours, PERIOD_M5, hours * 12, chunkSize, digits);
   ok = ok && SendHistoryTimeframe(requestId, hours, PERIOD_M15, hours * 4, chunkSize, digits);
   ok = ok && SendHistoryTimeframe(requestId, hours, PERIOD_M30, hours * 2, chunkSize, digits);
   if(ok)
      PrintFormat("History chunks sent request=%s hours=%d", requestId, hours);
}

void SendDealHistoryChunks(const string requestId, const int requestedDays,
                           const int requestedMaxDeals, const int configuredChunkSize)
{
   datetime toTime = TimeCurrent();
   datetime fromTime = 0;
   int days = requestedDays;
   if(days < 0)
      days = 0;
   if(days > 3650)
      days = 3650;
   if(days > 0)
      fromTime = toTime - days * 86400;

   if(!HistorySelect(fromTime, toTime))
   {
      PrintFormat("Deal history select failed request=%s", requestId);
      return;
   }

   int total = HistoryDealsTotal();
   int maxDeals = requestedMaxDeals;
   if(maxDeals < 0)
      maxDeals = 0;
   int dealsToSend = total;
   if(maxDeals > 0 && dealsToSend > maxDeals)
      dealsToSend = maxDeals;

   int chunkSize = configuredChunkSize;
   if(chunkSize < 1)
      chunkSize = 500;
   if(chunkSize > 2000)
      chunkSize = 2000;

   int chunkCount = (dealsToSend + chunkSize - 1) / chunkSize;
   if(chunkCount < 1)
      chunkCount = 1;

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   bool ok = true;
   for(int chunkIndex = 0; chunkIndex < chunkCount; chunkIndex++)
   {
      int start = chunkIndex * chunkSize;
      int end = start + chunkSize;
      if(end > dealsToSend)
         end = dealsToSend;
      string payload = BuildDealHistoryChunkJson(requestId, days, maxDeals, total, start, end,
                                                 chunkIndex, chunkCount, digits);
      string response = PostJson(BridgeDealHistoryChunkUrl(), payload);
      if(response == "")
      {
         ok = false;
         break;
      }
      if(!JsonGetBool(response, "ok", false))
      {
         Print("Deal history chunk rejected: ", response);
         ok = false;
         break;
      }
   }
   if(ok)
      PrintFormat("Deal history chunks sent request=%s deals=%d total=%d", requestId, dealsToSend, total);
}

string BuildDealHistoryChunkJson(const string requestId, const int days, const int maxDeals,
                                 const int totalDeals, const int start, const int end,
                                 const int chunkIndex, const int chunkCount, const int digits)
{
   string json = "{";
   json += StringFormat("\"deal_history_request_id\":\"%s\",", JsonEscape(requestId));
   json += StringFormat("\"days\":%d,", days);
   json += StringFormat("\"max_deals\":%d,", maxDeals);
   json += StringFormat("\"symbol\":\"%s\",", JsonEscape(_Symbol));
   json += StringFormat("\"account_login\":%I64d,", AccountInfoInteger(ACCOUNT_LOGIN));
   json += StringFormat("\"currency\":\"%s\",", JsonEscape(AccountInfoString(ACCOUNT_CURRENCY)));
   json += StringFormat("\"server_time\":\"%s\",", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS));
   json += StringFormat("\"chunk_index\":%d,", chunkIndex);
   json += StringFormat("\"chunk_count\":%d,", chunkCount);
   json += StringFormat("\"total_deals\":%d,", totalDeals);
   json += "\"deals\":[";

   bool first = true;
   for(int offset = start; offset < end; offset++)
   {
      int historyIndex = totalDeals - 1 - offset;
      ulong ticket = HistoryDealGetTicket(historyIndex);
      if(ticket == 0)
         continue;
      if(!first)
         json += ",";
      first = false;
      json += BuildDealJson(ticket, digits);
   }

   json += "]}";
   return json;
}

void ResetEmbeddedDealHistoryState()
{
   EmbeddedDealHistoryRequestId = "";
   EmbeddedDealHistoryNextChunk = 0;
   EmbeddedDealHistoryChunkCount = 0;
   EmbeddedDealHistoryDealsToSend = 0;
   EmbeddedDealHistoryTotalDeals = 0;
   PendingEmbeddedDealHistoryRequestId = "";
   PendingEmbeddedDealHistoryChunkIndex = -1;
   PendingEmbeddedDealHistoryChunkJson = "";
}

string BuildNextEmbeddedDealHistoryChunkJson(const int digits)
{
   if(CurrentDealHistoryRequestId == "")
      return "";

   if(EmbeddedDealHistoryRequestId != CurrentDealHistoryRequestId)
   {
      ResetEmbeddedDealHistoryState();
      EmbeddedDealHistoryRequestId = CurrentDealHistoryRequestId;
   }

   datetime toTime = TimeCurrent();
   datetime fromTime = 0;
   int days = CurrentDealHistoryDays;
   if(days < 0)
      days = 0;
   if(days > 3650)
      days = 3650;
   if(days > 0)
      fromTime = toTime - days * 86400;

   if(!HistorySelect(fromTime, toTime))
   {
      PrintFormat("Embedded deal history select failed request=%s", CurrentDealHistoryRequestId);
      return "";
   }

   int maxDeals = CurrentDealHistoryMaxDeals;
   if(maxDeals < 0)
      maxDeals = 0;

   int chunkSize = CurrentDealHistoryChunkSize;
   if(chunkSize < 1)
      chunkSize = 50;
   if(chunkSize > 100)
      chunkSize = 100;

   EmbeddedDealHistoryTotalDeals = HistoryDealsTotal();
   EmbeddedDealHistoryDealsToSend = EmbeddedDealHistoryTotalDeals;
   if(maxDeals > 0 && EmbeddedDealHistoryDealsToSend > maxDeals)
      EmbeddedDealHistoryDealsToSend = maxDeals;
   EmbeddedDealHistoryChunkCount = (EmbeddedDealHistoryDealsToSend + chunkSize - 1) / chunkSize;
   if(EmbeddedDealHistoryChunkCount < 1)
      EmbeddedDealHistoryChunkCount = 1;

   int chunkIndex = CurrentDealHistoryNextChunk;
   if(chunkIndex >= EmbeddedDealHistoryChunkCount)
      return "";

   int start = chunkIndex * chunkSize;
   int end = start + chunkSize;
   if(end > EmbeddedDealHistoryDealsToSend)
      end = EmbeddedDealHistoryDealsToSend;

   PendingEmbeddedDealHistoryRequestId = EmbeddedDealHistoryRequestId;
   PendingEmbeddedDealHistoryChunkIndex = chunkIndex;
   PendingEmbeddedDealHistoryChunkJson = BuildDealHistoryChunkJson(
      EmbeddedDealHistoryRequestId,
      CurrentDealHistoryDays,
      CurrentDealHistoryMaxDeals,
      EmbeddedDealHistoryTotalDeals,
      start,
      end,
      chunkIndex,
      EmbeddedDealHistoryChunkCount,
      digits
   );

   return PendingEmbeddedDealHistoryChunkJson;
}

void CommitEmbeddedDealHistoryChunk()
{
   if(PendingEmbeddedDealHistoryChunkJson == "")
      return;
   if(PendingEmbeddedDealHistoryRequestId == EmbeddedDealHistoryRequestId &&
      PendingEmbeddedDealHistoryChunkIndex >= 0)
   {
      EmbeddedDealHistoryNextChunk = PendingEmbeddedDealHistoryChunkIndex + 1;
      if(EmbeddedDealHistoryNextChunk >= EmbeddedDealHistoryChunkCount &&
         EmbeddedDealHistoryChunkCount > 0)
      {
         PrintFormat("Embedded deal history chunks sent request=%s deals=%d total=%d",
                     EmbeddedDealHistoryRequestId,
                     EmbeddedDealHistoryDealsToSend,
                     EmbeddedDealHistoryTotalDeals);
      }
   }

   PendingEmbeddedDealHistoryRequestId = "";
   PendingEmbeddedDealHistoryChunkIndex = -1;
   PendingEmbeddedDealHistoryChunkJson = "";
}

bool SendHistoryTimeframe(const string requestId, const int hours, const ENUM_TIMEFRAMES timeframe,
                          const int barsToSend, const int chunkSize, const int digits)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, timeframe, 0, barsToSend, rates);
   if(copied <= 0)
   {
      PrintFormat("History CopyRates failed timeframe=%s", EnumToString(timeframe));
      return false;
   }

   int chunkCount = (copied + chunkSize - 1) / chunkSize;
   for(int chunkIndex = 0; chunkIndex < chunkCount; chunkIndex++)
   {
      int start = chunkIndex * chunkSize;
      int end = start + chunkSize;
      if(end > copied)
         end = copied;
      string payload = BuildHistoryChunkJson(requestId, hours, timeframe, rates, copied, start, end,
                                            chunkIndex, chunkCount, digits);
      string response = PostJson(BridgeHistoryChunkUrl(), payload);
      if(response == "")
         return false;
      if(!JsonGetBool(response, "ok", false))
      {
         Print("History chunk rejected: ", response);
         return false;
      }
   }
   return true;
}

string BuildHistoryChunkJson(const string requestId, const int hours, const ENUM_TIMEFRAMES timeframe,
                             MqlRates &rates[], const int copied, const int start, const int end,
                             const int chunkIndex, const int chunkCount, const int digits)
{
   MqlTick tick;
   SymbolInfoTick(_Symbol, tick);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int spreadPoints = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   string key = TimeframeKey(timeframe);

   string json = "{";
   json += StringFormat("\"history_request_id\":\"%s\",", JsonEscape(requestId));
   json += StringFormat("\"history_hours\":%d,", hours);
   json += StringFormat("\"symbol\":\"%s\",", JsonEscape(_Symbol));
   json += StringFormat("\"server_time\":\"%s\",", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS));
   json += StringFormat("\"timeframe_key\":\"%s\",", key);
   json += StringFormat("\"timeframe\":\"%s\",", EnumToString(timeframe));
   json += StringFormat("\"chunk_index\":%d,", chunkIndex);
   json += StringFormat("\"chunk_count\":%d,", chunkCount);
   json += StringFormat("\"total_bars\":%d,", copied);
   json += StringFormat("\"bid\":%s,", DoubleToJson(tick.bid, digits));
   json += StringFormat("\"ask\":%s,", DoubleToJson(tick.ask, digits));
   json += StringFormat("\"spread_points\":%d,", spreadPoints);
   json += StringFormat("\"digits\":%d,", digits);
   json += StringFormat("\"point\":%s,", DoubleToJson(point, digits + 2));
   json += "\"indicators\":{";
   json += StringFormat("\"rsi14\":%s,", DoubleToJson(IndicatorSingleValue(iRSI(_Symbol, timeframe, 14, PRICE_CLOSE)), 4));
   json += StringFormat("\"ema_fast\":%s,", DoubleToJson(IndicatorSingleValue(iMA(_Symbol, timeframe, 9, 0, MODE_EMA, PRICE_CLOSE)), digits));
   json += StringFormat("\"ema_slow\":%s,", DoubleToJson(IndicatorSingleValue(iMA(_Symbol, timeframe, 21, 0, MODE_EMA, PRICE_CLOSE)), digits));
   json += StringFormat("\"atr14\":%s", DoubleToJson(IndicatorSingleValue(iATR(_Symbol, timeframe, 14)), digits));
   json += "},\"bars\":[";

   for(int chronoIndex = start; chronoIndex < end; chronoIndex++)
   {
      int seriesIndex = copied - 1 - chronoIndex;
      if(chronoIndex != start)
         json += ",";
      json += "{";
      json += StringFormat("\"time\":\"%s\",", TimeToString(rates[seriesIndex].time, TIME_DATE|TIME_MINUTES));
      json += StringFormat("\"open\":%s,", DoubleToJson(rates[seriesIndex].open, digits));
      json += StringFormat("\"high\":%s,", DoubleToJson(rates[seriesIndex].high, digits));
      json += StringFormat("\"low\":%s,", DoubleToJson(rates[seriesIndex].low, digits));
      json += StringFormat("\"close\":%s,", DoubleToJson(rates[seriesIndex].close, digits));
      json += StringFormat("\"tick_volume\":%I64d", rates[seriesIndex].tick_volume);
      json += "}";
   }

   json += "]}";
   return json;
}

string BuildTimeframeJson(const ENUM_TIMEFRAMES timeframe, const int barsToSend, const int digits)
{
   string json = "{";
   json += StringFormat("\"label\":\"%s\",", TimeframeKey(timeframe));
   json += StringFormat("\"timeframe\":\"%s\",", EnumToString(timeframe));
   json += "\"indicators\":{";
   json += StringFormat("\"rsi14\":%s,", DoubleToJson(IndicatorSingleValue(iRSI(_Symbol, timeframe, 14, PRICE_CLOSE)), 4));
   json += StringFormat("\"ema_fast\":%s,", DoubleToJson(IndicatorSingleValue(iMA(_Symbol, timeframe, 9, 0, MODE_EMA, PRICE_CLOSE)), digits));
   json += StringFormat("\"ema_slow\":%s,", DoubleToJson(IndicatorSingleValue(iMA(_Symbol, timeframe, 21, 0, MODE_EMA, PRICE_CLOSE)), digits));
   json += StringFormat("\"atr14\":%s", DoubleToJson(IndicatorSingleValue(iATR(_Symbol, timeframe, 14)), digits));
   json += "},";
   json += "\"bars\":" + BuildBarsArrayJson(timeframe, barsToSend, digits);
   json += "}";
   return json;
}

string BuildBarsArrayJson(const ENUM_TIMEFRAMES timeframe, const int barsToSend, const int digits)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, timeframe, 0, barsToSend, rates);
   if(copied <= 0)
      return "[]";

   string json = "[";
   for(int i = copied - 1; i >= 0; i--)
   {
      if(i != copied - 1)
         json += ",";
      json += "{";
      json += StringFormat("\"time\":\"%s\",", TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES));
      json += StringFormat("\"open\":%s,", DoubleToJson(rates[i].open, digits));
      json += StringFormat("\"high\":%s,", DoubleToJson(rates[i].high, digits));
      json += StringFormat("\"low\":%s,", DoubleToJson(rates[i].low, digits));
      json += StringFormat("\"close\":%s,", DoubleToJson(rates[i].close, digits));
      json += StringFormat("\"tick_volume\":%I64d", rates[i].tick_volume);
      json += "}";
   }
   json += "]";
   return json;
}

double IndicatorValue(const int handle)
{
   double buffer[];
   ArraySetAsSeries(buffer, true);
   if(CopyBuffer(handle, 0, 0, 1, buffer) != 1)
      return 0.0;
   return buffer[0];
}

double IndicatorSingleValue(const int handle)
{
   if(handle == INVALID_HANDLE)
      return 0.0;
   double value = IndicatorValue(handle);
   IndicatorRelease(handle);
   return value;
}

string TimeframeKey(const ENUM_TIMEFRAMES timeframe)
{
   if(timeframe == PERIOD_M1) return "M1";
   if(timeframe == PERIOD_M5) return "M5";
   if(timeframe == PERIOD_M15) return "M15";
   if(timeframe == PERIOD_M30) return "M30";
   if(timeframe == PERIOD_H1) return "H1";
   if(timeframe == PERIOD_H4) return "H4";
   if(timeframe == PERIOD_D1) return "D1";
   return EnumToString(timeframe);
}

string DealTypeName(const long type)
{
   if(type == DEAL_TYPE_BUY) return "buy";
   if(type == DEAL_TYPE_SELL) return "sell";
   if(type == DEAL_TYPE_BALANCE) return "balance";
   if(type == DEAL_TYPE_CREDIT) return "credit";
   if(type == DEAL_TYPE_CHARGE) return "charge";
   if(type == DEAL_TYPE_CORRECTION) return "correction";
   if(type == DEAL_TYPE_BONUS) return "bonus";
   if(type == DEAL_TYPE_COMMISSION) return "commission";
   return IntegerToString((int)type);
}

string DealEntryName(const long entry)
{
   if(entry == DEAL_ENTRY_IN) return "in";
   if(entry == DEAL_ENTRY_OUT) return "out";
   if(entry == DEAL_ENTRY_INOUT) return "inout";
   if(entry == DEAL_ENTRY_OUT_BY) return "out_by";
   return IntegerToString((int)entry);
}

int SafeWebRequestAttempts()
{
   int retries = InpWebRequestRetries;
   if(retries < 0)
      retries = 0;
   if(retries > 3)
      retries = 3;
   return retries + 1;
}

int SafeWebRequestRetryDelayMs()
{
   int delay = InpWebRequestRetryDelayMs;
   if(delay < 0)
      delay = 0;
   if(delay > 2000)
      delay = 2000;
   return delay;
}

bool IsRetryableWebRequestStatus(const int status)
{
   return status == -1 || status == 1003 || status == 1004 || status == 1005;
}

string BridgeLockName()
{
   string symbol = _Symbol;
   StringReplace(symbol, ".", "_");
   StringReplace(symbol, "-", "_");
   return "AI_BRIDGE_HTTP_LOCK_" + IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN)) + "_" + symbol;
}

bool AcquireBridgeHttpLock()
{
   string name = BridgeLockName();
   double now = (double)TimeLocal();
   double expiresAt = now + 12.0;
   if(!GlobalVariableCheck(name))
      GlobalVariableSet(name, 0.0);

   for(int attempt = 0; attempt < 5; attempt++)
   {
      double current = GlobalVariableGet(name);
      if(current > 0.0 && current < now)
      {
         GlobalVariableSetOnCondition(name, 0.0, current);
         current = GlobalVariableGet(name);
      }
      if(current == 0.0 && GlobalVariableSetOnCondition(name, expiresAt, 0.0))
         return true;

      Sleep(50);
      now = (double)TimeLocal();
      expiresAt = now + 12.0;
   }
   return false;
}

void ReleaseBridgeHttpLock()
{
   string name = BridgeLockName();
   if(GlobalVariableCheck(name))
      GlobalVariableSet(name, 0.0);
}

string PostJson(const string url, const string payload)
{
   char data[];
   StringToCharArray(payload, data, 0, WHOLE_ARRAY, CP_UTF8);
   if(ArraySize(data) > 0)
      ArrayResize(data, ArraySize(data) - 1);

   char result[];
   string resultHeaders = "";
   string headers = "Content-Type: application/json\r\n";
   if(InpBridgeToken != "")
      headers += "X-Bridge-Token: " + InpBridgeToken + "\r\n";

   int attempts = SafeWebRequestAttempts();
   int retryDelayMs = SafeWebRequestRetryDelayMs();
   for(int attempt = 0; attempt < attempts; attempt++)
   {
      if(!AcquireBridgeHttpLock())
      {
         if(attempt + 1 < attempts)
         {
            Sleep(retryDelayMs);
            continue;
         }
         Print("Bridge HTTP lock busy; skipped POST.");
         return "";
      }

      ArrayResize(result, 0);
      resultHeaders = "";
      ResetLastError();
      int status = WebRequest("POST", url, headers, 10000, data, result, resultHeaders);
      int err = GetLastError();
      ReleaseBridgeHttpLock();

      if(status >= 200 && status < 300)
         return CharArrayToString(result, 0, -1, CP_UTF8);

      if(attempt + 1 < attempts && IsRetryableWebRequestStatus(status))
      {
         Sleep(retryDelayMs);
         continue;
      }

      if(status == -1)
         PrintFormat("WebRequest failed err=%d. Check MT5 allowed URLs for http://127.0.0.1:8765", err);
      else
         PrintFormat("Bridge HTTP status=%d url=%s body=%s", status, url, CharArrayToString(result, 0, -1, CP_UTF8));
      return "";
   }
   return "";
}

string GetJson(const string url)
{
   char data[];
   char result[];
   string resultHeaders = "";
   string headers = "";
   if(InpBridgeToken != "")
      headers += "X-Bridge-Token: " + InpBridgeToken + "\r\n";

   int attempts = SafeWebRequestAttempts();
   int retryDelayMs = SafeWebRequestRetryDelayMs();
   for(int attempt = 0; attempt < attempts; attempt++)
   {
      if(!AcquireBridgeHttpLock())
      {
         if(attempt + 1 < attempts)
         {
            Sleep(retryDelayMs);
            continue;
         }
         Print("Bridge HTTP lock busy; skipped GET.");
         return "";
      }

      ArrayResize(result, 0);
      resultHeaders = "";
      ResetLastError();
      int status = WebRequest("GET", url, headers, 5000, data, result, resultHeaders);
      int err = GetLastError();
      ReleaseBridgeHttpLock();

      if(status >= 200 && status < 300)
         return CharArrayToString(result, 0, -1, CP_UTF8);

      if(attempt + 1 < attempts && IsRetryableWebRequestStatus(status))
      {
         Sleep(retryDelayMs);
         continue;
      }

      if(status == -1)
         PrintFormat("WebRequest GET failed err=%d url=%s", err, url);
      else
         PrintFormat("Bridge GET HTTP status=%d url=%s body=%s", status, url, CharArrayToString(result, 0, -1, CP_UTF8));
      return "";
   }
   return "";
}

int GetRequestedHistoryHours()
{
   CurrentHistoryRequestId = "";
   CurrentHistoryChunkSize = 240;
   CurrentDealHistoryRequestId = "";
   CurrentDealHistoryDays = 0;
   CurrentDealHistoryMaxDeals = 0;
   CurrentDealHistoryChunkSize = 500;
   CurrentDealHistoryNextChunk = 0;

   string body = GetJson(BridgeConfigUrl());
   if(body == "")
      return 0;

   CurrentHistoryRequestId = JsonGetString(body, "history_request_id", "");
   CurrentHistoryChunkSize = (int)JsonGetDouble(body, "history_chunk_size", 240.0);
   if(CurrentHistoryChunkSize < 30)
      CurrentHistoryChunkSize = 240;
   CurrentDealHistoryRequestId = JsonGetString(body, "deal_history_request_id", "");
   CurrentDealHistoryDays = (int)JsonGetDouble(body, "deal_history_days", 0.0);
   if(CurrentDealHistoryDays < 0)
      CurrentDealHistoryDays = 0;
   if(CurrentDealHistoryDays > 3650)
      CurrentDealHistoryDays = 3650;
   CurrentDealHistoryMaxDeals = (int)JsonGetDouble(body, "deal_history_max_deals", 0.0);
   if(CurrentDealHistoryMaxDeals < 0)
      CurrentDealHistoryMaxDeals = 0;
   CurrentDealHistoryChunkSize = (int)JsonGetDouble(body, "deal_history_chunk_size", 500.0);
   if(CurrentDealHistoryChunkSize < 1 || CurrentDealHistoryChunkSize > 2000)
      CurrentDealHistoryChunkSize = 500;
   CurrentDealHistoryNextChunk = (int)JsonGetDouble(body, "deal_history_next_chunk", 0.0);
   if(CurrentDealHistoryNextChunk < 0)
      CurrentDealHistoryNextChunk = 0;
   int hours = (int)JsonGetDouble(body, "history_hours", 0.0);
   if(hours < 0)
      return 0;
   if(hours > InpMaxHistoryHours)
      return InpMaxHistoryHours;
   return hours;
}

string BridgeHistoryChunkUrl()
{
   return InpBridgeUrl;
}

string BridgeDealHistoryChunkUrl()
{
   return InpBridgeUrl;
}

string BridgeConfigUrl()
{
   return BridgeBaseUrl() + "/config";
}

string BridgeTradeCommandUrl()
{
   return BridgeBaseUrl() + "/trade_command?symbol=" + _Symbol;
}

string BridgeTradeResultUrl()
{
   return BridgeBaseUrl() + "/trade_result";
}

string BridgeBaseUrl()
{
   int pos = StringFind(InpBridgeUrl, "/analyze");
   if(pos >= 0)
      return StringSubstr(InpBridgeUrl, 0, pos);
   pos = StringFind(InpBridgeUrl, "/snapshot");
   if(pos >= 0)
      return StringSubstr(InpBridgeUrl, 0, pos);
   pos = StringFind(InpBridgeUrl, "/ingest");
   if(pos >= 0)
      return StringSubstr(InpBridgeUrl, 0, pos);
   return "http://127.0.0.1:8765";
}

void CheckTradeCommand()
{
   string response = GetJson(BridgeTradeCommandUrl());
   if(response == "")
      return;

   string id = JsonGetString(response, "id", "");
   if(id == "")
      return;

   string action = JsonGetString(response, "action", "");
   string symbol = JsonGetString(response, "symbol", _Symbol);
   double volume = JsonGetDouble(response, "volume", 0.0);
   double sl = JsonGetDouble(response, "sl", 0.0);
   double tp = JsonGetDouble(response, "tp", 0.0);
   ulong ticket = (ulong)JsonGetDouble(response, "ticket", 0.0);
   bool dryRun = JsonGetBool(response, "dry_run", true);
   int maxSpread = (int)JsonGetDouble(response, "max_spread_points", InpCodexMaxSpreadPoints);
   datetime expiresAt = (datetime)JsonGetDouble(response, "expires_at", 0.0);
   string comment = JsonGetString(response, "comment", "codex command");

   string allowedSymbol = InpCodexAllowedSymbol;
   if(allowedSymbol == "")
      allowedSymbol = _Symbol;

   if(symbol != allowedSymbol || symbol != _Symbol)
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, 0.0, sl, tp, ticket,
                      "symbol not allowed", 0, 0, 0);
      return;
   }
   if(expiresAt > 0 && TimeGMT() > expiresAt)
   {
      SendTradeResult(id, "expired", dryRun, action, symbol, volume, 0.0, sl, tp, ticket,
                      "command expired", 0, 0, 0);
      return;
   }
   if(!dryRun && !InpAllowCodexTrading)
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, 0.0, sl, tp, ticket,
                      "InpAllowCodexTrading is false", 0, 0, 0);
      return;
   }
   double pendingPrice = JsonGetDouble(response, "price", 0.0);
   bool isEntry = (action == "buy" || action == "sell" ||
                   action == "buy_limit" || action == "sell_limit" ||
                   action == "buy_stop" || action == "sell_stop");
   if(isEntry &&
      ((int)SymbolInfoInteger(symbol, SYMBOL_SPREAD) > maxSpread ||
       (int)SymbolInfoInteger(symbol, SYMBOL_SPREAD) > InpCodexMaxSpreadPoints))
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, 0.0, sl, tp, ticket,
                      "spread too wide", 0, 0, 0);
      return;
   }

   if(action == "buy" || action == "sell")
      ExecuteCodexMarketCommand(id, action, symbol, volume, sl, tp, dryRun, comment);
   else if(action == "buy_limit" || action == "sell_limit" ||
           action == "buy_stop" || action == "sell_stop")
      ExecuteCodexPendingCommand(id, action, symbol, volume, pendingPrice, sl, tp, dryRun, comment);
   else if(action == "modify")
      ExecuteCodexModifyCommand(id, symbol, ticket, sl, tp, dryRun);
   else if(action == "cancel")
      ExecuteCodexCancelCommand(id, symbol, ticket, dryRun);
   else if(action == "close")
      ExecuteCodexCloseCommand(id, action, symbol, ticket, dryRun, comment);
   else if(action == "close_all")
      ExecuteCodexCloseAllCommand(id, action, symbol, dryRun, comment);
   else
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, 0.0, sl, tp, ticket,
                      "unsupported action", 0, 0, 0);
}

void ExecuteCodexMarketCommand(const string id, const string action, const string symbol,
                               const double volume, const double sl, const double tp,
                               const bool dryRun, const string comment)
{
   if(volume <= 0.0 || volume > InpCodexMaxLot)
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, 0.0, sl, tp, 0,
                      "volume outside allowed range", 0, 0, 0);
      return;
   }
   if(CountOpenPositionsForSymbol(symbol) >= InpCodexMaxPositions)
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, 0.0, sl, tp, 0,
                      "max positions reached", 0, 0, 0);
      return;
   }
   if(InpCodexRequireSlTp && (sl <= 0.0 || tp <= 0.0))
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, 0.0, sl, tp, 0,
                      "SL/TP required", 0, 0, 0);
      return;
   }

   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double price = (action == "buy" ? ask : bid);
   if(action == "buy" && (sl >= bid || tp <= ask))
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, price, sl, tp, 0,
                      "invalid buy SL/TP", 0, 0, 0);
      return;
   }
   if(action == "sell" && (sl <= ask || tp >= bid))
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, price, sl, tp, 0,
                      "invalid sell SL/TP", 0, 0, 0);
      return;
   }

   if(dryRun)
   {
      SendTradeResult(id, "dry_run_passed", true, action, symbol, volume, price, sl, tp, 0,
                      "validation passed; no order sent", 0, 0, 0);
      return;
   }

   bool sent = false;
   if(action == "buy")
      sent = Trade.Buy(volume, symbol, ask, sl, tp, comment);
   else
      sent = Trade.Sell(volume, symbol, bid, sl, tp, comment);

   SendTradeResult(id, sent ? "executed" : "rejected", false, action, symbol, volume, price, sl, tp, 0,
                   sent ? "order sent" : Trade.ResultComment(),
                   (int)Trade.ResultRetcode(), (ulong)Trade.ResultOrder(), (ulong)Trade.ResultDeal());
}

void ExecuteCodexCloseCommand(const string id, const string action, const string symbol,
                              const ulong ticket, const bool dryRun, const string comment)
{
   if(ticket == 0 || !PositionSelectByTicket(ticket))
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, 0.0, 0.0, 0.0, 0.0, ticket,
                      "position ticket not found", 0, 0, 0);
      return;
   }
   string positionSymbol = PositionGetString(POSITION_SYMBOL);
   double volume = PositionGetDouble(POSITION_VOLUME);
   double price = PositionGetDouble(POSITION_PRICE_CURRENT);
   if(positionSymbol != symbol)
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, price, 0.0, 0.0, ticket,
                      "position symbol mismatch", 0, 0, 0);
      return;
   }
   if(dryRun)
   {
      SendTradeResult(id, "dry_run_passed", true, action, symbol, volume, price, 0.0, 0.0, ticket,
                      "close validation passed; no order sent", 0, 0, 0);
      return;
   }
   bool sent = Trade.PositionClose(ticket);
   SendTradeResult(id, sent ? "executed" : "rejected", false, action, symbol, volume, price, 0.0, 0.0, ticket,
                   sent ? "close sent" : Trade.ResultComment(),
                   (int)Trade.ResultRetcode(), (ulong)Trade.ResultOrder(), (ulong)Trade.ResultDeal());
}

void ExecuteCodexCloseAllCommand(const string id, const string action, const string symbol,
                                 const bool dryRun, const string comment)
{
   int count = CountOpenPositionsForSymbol(symbol);
   if(count <= 0)
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, 0.0, 0.0, 0.0, 0.0, 0,
                      "no matching positions", 0, 0, 0);
      return;
   }
   if(dryRun)
   {
      SendTradeResult(id, "dry_run_passed", true, action, symbol, (double)count, 0.0, 0.0, 0.0, 0,
                      "close_all validation passed; no orders sent", 0, 0, 0);
      return;
   }

   bool allSent = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != symbol)
         continue;
      if(!Trade.PositionClose(ticket))
         allSent = false;
   }
   SendTradeResult(id, allSent ? "executed" : "partial_or_rejected", false, action, symbol,
                   (double)count, 0.0, 0.0, 0.0, 0,
                   allSent ? "close_all sent" : Trade.ResultComment(),
                   (int)Trade.ResultRetcode(), (ulong)Trade.ResultOrder(), (ulong)Trade.ResultDeal());
}

int CountPendingOrdersForSymbol(const string symbol)
{
   int count = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) == symbol)
         count++;
   }
   return count;
}

// OCOタグは注文コメントの "oco:<group>" で表す。同じgroupの注文は、
// 片方が約定してポジションになった時点で残りをキャンセルする。
string ExtractOcoGroup(const string text)
{
   int pos = StringFind(text, "oco:");
   if(pos < 0)
      return "";
   string tail = StringSubstr(text, pos + 4);
   int space = StringFind(tail, " ");
   if(space >= 0)
      tail = StringSubstr(tail, 0, space);
   return tail;
}

void EnforceOcoPairs()
{
   for(int p = PositionsTotal() - 1; p >= 0; p--)
   {
      ulong posTicket = PositionGetTicket(p);
      if(posTicket == 0)
         continue;
      string group = ExtractOcoGroup(PositionGetString(POSITION_COMMENT));
      if(group == "")
         continue;
      for(int o = OrdersTotal() - 1; o >= 0; o--)
      {
         ulong orderTicket = OrderGetTicket(o);
         if(orderTicket == 0)
            continue;
         if(ExtractOcoGroup(OrderGetString(ORDER_COMMENT)) != group)
            continue;
         if(Trade.OrderDelete(orderTicket))
            PrintFormat("OCO: cancelled order %I64u (group %s) after position %I64u filled",
                        orderTicket, group, posTicket);
      }
   }
}

void ExecuteCodexPendingCommand(const string id, const string action, const string symbol,
                                const double volume, const double price, const double sl,
                                const double tp, const bool dryRun, const string comment)
{
   if(volume <= 0.0 || volume > InpCodexMaxLot)
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, price, sl, tp, 0,
                      "volume outside allowed range", 0, 0, 0);
      return;
   }
   if(price <= 0.0)
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, price, sl, tp, 0,
                      "price required for pending order", 0, 0, 0);
      return;
   }
   if(InpCodexRequireSlTp && (sl <= 0.0 || tp <= 0.0))
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, price, sl, tp, 0,
                      "SL/TP required", 0, 0, 0);
      return;
   }
   if(CountPendingOrdersForSymbol(symbol) >= InpCodexMaxPendingOrders)
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, price, sl, tp, 0,
                      "max pending orders reached", 0, 0, 0);
      return;
   }
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   if(action == "buy_limit" && (price >= ask || sl >= price || (tp > 0.0 && tp <= price)))
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, price, sl, tp, 0,
                      "invalid buy_limit price/SL/TP", 0, 0, 0);
      return;
   }
   if(action == "sell_limit" && (price <= bid || (sl > 0.0 && sl <= price) || tp >= price))
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, price, sl, tp, 0,
                      "invalid sell_limit price/SL/TP", 0, 0, 0);
      return;
   }
   if(action == "buy_stop" && (price <= ask || sl >= price || (tp > 0.0 && tp <= price)))
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, price, sl, tp, 0,
                      "invalid buy_stop price/SL/TP", 0, 0, 0);
      return;
   }
   if(action == "sell_stop" && (price >= bid || (sl > 0.0 && sl <= price) || tp >= price))
   {
      SendTradeResult(id, "rejected", dryRun, action, symbol, volume, price, sl, tp, 0,
                      "invalid sell_stop price/SL/TP", 0, 0, 0);
      return;
   }
   if(dryRun)
   {
      SendTradeResult(id, "dry_run_passed", true, action, symbol, volume, price, sl, tp, 0,
                      "pending validation passed; no order sent", 0, 0, 0);
      return;
   }
   bool sent = false;
   if(action == "buy_limit")
      sent = Trade.BuyLimit(volume, price, symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
   else if(action == "sell_limit")
      sent = Trade.SellLimit(volume, price, symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
   else if(action == "buy_stop")
      sent = Trade.BuyStop(volume, price, symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
   else
      sent = Trade.SellStop(volume, price, symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
   SendTradeResult(id, sent ? "executed" : "rejected", false, action, symbol, volume, price, sl, tp, 0,
                   sent ? "pending order placed" : Trade.ResultComment(),
                   (int)Trade.ResultRetcode(), (ulong)Trade.ResultOrder(), (ulong)Trade.ResultDeal());
}

void ExecuteCodexModifyCommand(const string id, const string symbol, const ulong ticket,
                               const double sl, const double tp, const bool dryRun)
{
   if(ticket == 0)
   {
      SendTradeResult(id, "rejected", dryRun, "modify", symbol, 0.0, 0.0, sl, tp, ticket,
                      "ticket required", 0, 0, 0);
      return;
   }
   if(sl <= 0.0 && tp <= 0.0)
   {
      SendTradeResult(id, "rejected", dryRun, "modify", symbol, 0.0, 0.0, sl, tp, ticket,
                      "sl or tp required", 0, 0, 0);
      return;
   }
   if(PositionSelectByTicket(ticket))
   {
      if(PositionGetString(POSITION_SYMBOL) != symbol)
      {
         SendTradeResult(id, "rejected", dryRun, "modify", symbol, 0.0, 0.0, sl, tp, ticket,
                         "position symbol mismatch", 0, 0, 0);
         return;
      }
      double volume = PositionGetDouble(POSITION_VOLUME);
      double current = PositionGetDouble(POSITION_PRICE_CURRENT);
      double newSl = (sl > 0.0 ? sl : PositionGetDouble(POSITION_SL));
      double newTp = (tp > 0.0 ? tp : PositionGetDouble(POSITION_TP));
      if(dryRun)
      {
         SendTradeResult(id, "dry_run_passed", true, "modify", symbol, volume, current,
                         newSl, newTp, ticket, "position modify validation passed; no order sent", 0, 0, 0);
         return;
      }
      bool sent = Trade.PositionModify(ticket, newSl, newTp);
      SendTradeResult(id, sent ? "executed" : "rejected", false, "modify", symbol, volume, current,
                      newSl, newTp, ticket,
                      sent ? "position modified" : Trade.ResultComment(),
                      (int)Trade.ResultRetcode(), (ulong)Trade.ResultOrder(), (ulong)Trade.ResultDeal());
      return;
   }
   if(OrderSelect(ticket))
   {
      if(OrderGetString(ORDER_SYMBOL) != symbol)
      {
         SendTradeResult(id, "rejected", dryRun, "modify", symbol, 0.0, 0.0, sl, tp, ticket,
                         "order symbol mismatch", 0, 0, 0);
         return;
      }
      double volume = OrderGetDouble(ORDER_VOLUME_CURRENT);
      double orderPrice = OrderGetDouble(ORDER_PRICE_OPEN);
      double newSl = (sl > 0.0 ? sl : OrderGetDouble(ORDER_SL));
      double newTp = (tp > 0.0 ? tp : OrderGetDouble(ORDER_TP));
      if(dryRun)
      {
         SendTradeResult(id, "dry_run_passed", true, "modify", symbol, volume, orderPrice,
                         newSl, newTp, ticket, "order modify validation passed; no order sent", 0, 0, 0);
         return;
      }
      bool sent = Trade.OrderModify(ticket, orderPrice, newSl, newTp, ORDER_TIME_GTC, 0);
      SendTradeResult(id, sent ? "executed" : "rejected", false, "modify", symbol, volume, orderPrice,
                      newSl, newTp, ticket,
                      sent ? "pending order modified" : Trade.ResultComment(),
                      (int)Trade.ResultRetcode(), (ulong)Trade.ResultOrder(), (ulong)Trade.ResultDeal());
      return;
   }
   SendTradeResult(id, "rejected", dryRun, "modify", symbol, 0.0, 0.0, sl, tp, ticket,
                   "ticket not found", 0, 0, 0);
}

void ExecuteCodexCancelCommand(const string id, const string symbol, const ulong ticket, const bool dryRun)
{
   if(ticket == 0 || !OrderSelect(ticket))
   {
      SendTradeResult(id, "rejected", dryRun, "cancel", symbol, 0.0, 0.0, 0.0, 0.0, ticket,
                      "pending order ticket not found", 0, 0, 0);
      return;
   }
   if(OrderGetString(ORDER_SYMBOL) != symbol)
   {
      SendTradeResult(id, "rejected", dryRun, "cancel", symbol, 0.0, 0.0, 0.0, 0.0, ticket,
                      "order symbol mismatch", 0, 0, 0);
      return;
   }
   double price = OrderGetDouble(ORDER_PRICE_OPEN);
   double volume = OrderGetDouble(ORDER_VOLUME_CURRENT);
   if(dryRun)
   {
      SendTradeResult(id, "dry_run_passed", true, "cancel", symbol, volume, price, 0.0, 0.0, ticket,
                      "cancel validation passed; no order sent", 0, 0, 0);
      return;
   }
   bool sent = Trade.OrderDelete(ticket);
   SendTradeResult(id, sent ? "executed" : "rejected", false, "cancel", symbol, volume, price, 0.0, 0.0, ticket,
                   sent ? "pending order deleted" : Trade.ResultComment(),
                   (int)Trade.ResultRetcode(), (ulong)Trade.ResultOrder(), (ulong)Trade.ResultDeal());
}

int CountOpenPositionsForSymbol(const string symbol)
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) == symbol)
         count++;
   }
   return count;
}

void SendTradeResult(const string id, const string status, const bool dryRun, const string action,
                     const string symbol, const double volume, const double price, const double sl,
                     const double tp, const ulong ticket, const string message, const int retcode,
                     const ulong order, const ulong deal)
{
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   string json = "{";
   json += StringFormat("\"id\":\"%s\",", JsonEscape(id));
   json += StringFormat("\"status\":\"%s\",", JsonEscape(status));
   json += StringFormat("\"dry_run\":%s,", dryRun ? "true" : "false");
   json += StringFormat("\"action\":\"%s\",", JsonEscape(action));
   json += StringFormat("\"symbol\":\"%s\",", JsonEscape(symbol));
   json += StringFormat("\"volume\":%s,", DoubleToJson(volume, 2));
   json += StringFormat("\"price\":%s,", DoubleToJson(price, digits));
   json += StringFormat("\"sl\":%s,", DoubleToJson(sl, digits));
   json += StringFormat("\"tp\":%s,", DoubleToJson(tp, digits));
   json += StringFormat("\"ticket\":%I64u,", ticket);
   json += StringFormat("\"order\":%I64u,", order);
   json += StringFormat("\"deal\":%I64u,", deal);
   json += StringFormat("\"retcode\":%d,", retcode);
   json += StringFormat("\"message\":\"%s\",", JsonEscape(message));
   json += StringFormat("\"server_time\":\"%s\"", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS));
   json += "}";
   string response = PostJson(BridgeTradeResultUrl(), json);
   if(response == "")
      PendingTradeResultJson = json;
   else
      PendingTradeResultJson = "";
}

void TryTrade(const string action, const double confidence, const double stopLoss, const double takeProfit)
{
   if(action != "buy" && action != "sell")
      return;
   if(confidence < InpMinConfidence)
   {
      Print("Trade skipped: confidence below threshold.");
      return;
   }
   if((int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpreadPoints)
   {
      Print("Trade skipped: spread too wide.");
      return;
   }
   if(stopLoss <= 0.0 || takeProfit <= 0.0)
   {
      Print("Trade skipped: missing stop loss or take profit.");
      return;
   }
   if(CountOpenPositions() >= InpMaxPositions)
   {
      Print("Trade skipped: max positions reached.");
      return;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   bool sent = false;

   if(action == "buy")
   {
      if(stopLoss >= bid || takeProfit <= ask)
      {
         Print("Trade skipped: invalid buy SL/TP.");
         return;
      }
      sent = Trade.Buy(InpFixedLot, _Symbol, ask, stopLoss, takeProfit, "AI bridge buy");
   }
   else if(action == "sell")
   {
      if(stopLoss <= ask || takeProfit >= bid)
      {
         Print("Trade skipped: invalid sell SL/TP.");
         return;
      }
      sent = Trade.Sell(InpFixedLot, _Symbol, bid, stopLoss, takeProfit, "AI bridge sell");
   }

   if(!sent)
      PrintFormat("Order failed retcode=%d comment=%s", Trade.ResultRetcode(), Trade.ResultComment());
}

int CountOpenPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         count++;
      }
   }
   return count;
}

string DoubleToJson(const double value, const int digits)
{
   if(!MathIsValidNumber(value))
      return "0";
   return DoubleToString(value, digits);
}

string JsonEscape(string value)
{
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   return value;
}

string JsonGetString(const string json, const string key, const string fallback)
{
   string needle = "\"" + key + "\":";
   int pos = StringFind(json, needle);
   if(pos < 0)
      return fallback;
   pos += StringLen(needle);
   while(pos < StringLen(json) && StringGetCharacter(json, pos) == ' ')
      pos++;
   if(pos >= StringLen(json) || StringGetCharacter(json, pos) != '"')
      return fallback;
   pos++;
   string out = "";
   bool escaped = false;
   for(int i = pos; i < StringLen(json); i++)
   {
      ushort ch = StringGetCharacter(json, i);
      if(escaped)
      {
         out += ShortToString(ch);
         escaped = false;
         continue;
      }
      if(ch == '\\')
      {
         escaped = true;
         continue;
      }
      if(ch == '"')
         return out;
      out += ShortToString(ch);
   }
   return fallback;
}

double JsonGetDouble(const string json, const string key, const double fallback)
{
   string raw = JsonGetRaw(json, key);
   if(raw == "" || raw == "null")
      return fallback;
   return StringToDouble(raw);
}

bool JsonGetBool(const string json, const string key, const bool fallback)
{
   string raw = JsonGetRaw(json, key);
   if(raw == "true")
      return true;
   if(raw == "false")
      return false;
   return fallback;
}

string JsonGetRaw(const string json, const string key)
{
   string needle = "\"" + key + "\":";
   int pos = StringFind(json, needle);
   if(pos < 0)
      return "";
   pos += StringLen(needle);
   while(pos < StringLen(json) && StringGetCharacter(json, pos) == ' ')
      pos++;

   int start = pos;
   for(int i = pos; i < StringLen(json); i++)
   {
      ushort ch = StringGetCharacter(json, i);
      if(ch == ',' || ch == '}' || ch == ']')
         return StringSubstr(json, start, i - start);
   }
   return StringSubstr(json, start);
}
