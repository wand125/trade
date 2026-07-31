from pathlib import Path
from decimal import Decimal, InvalidOperation
import re
import unittest


EA_PATH = Path("methods/swing_eval/mt5/Experts/Swing_Evaluation_Trader.mq5")
BRIDGE_EA_PATH = Path("methods/swing_eval/mt5/Experts/AI_Bridge_Advisor.mq5")
INDICATOR_PATH = Path("methods/swing_eval/mt5/Indicators/Swing_Evaluation_Predictor.mq5")
FORWARD_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_forward_test.set")
BACKTEST_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_backtest.set")
SAMPLE_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sample_collection.set")
OPTIMIZATION_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_optimization.set")
NEXT_OPTIMIZATION_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set")
STABLE_CANDIDATE_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_stable_candidate_next.set")
BUY_REFIT_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_refit.set")
BUY_ENTRY_REFIT_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_entry_refit.set")
BUY_HOUR03_VALIDATION_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_validation.set")
BUY_STRONG_HOURS_VALIDATION_SET_PATH = Path(
    "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_strong_hours_validation.set"
)
BUY_STRONG_HOURS_M30M15_VALIDATION_SET_PATH = Path(
    "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set"
)
BUY_WIDE_STOP_VALIDATION_SET_PATH = Path(
    "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_wide_stop_validation.set"
)
BUY_HOUR03_WIDE_STOP_VALIDATION_SET_PATH = Path(
    "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set"
)
BUY_HOUR03_WIDE_STOP_CALENDAR_VALIDATION_SET_PATH = Path(
    "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set"
)
SELL_ENTRY_REFIT_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_entry_refit.set")
SELL_REGIME_ENTRY_REFIT_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_regime_entry_refit.set")
SELL_HOUR12_VALIDATION_SET_PATH = Path("methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_hour12_validation.set")
SELL_HOUR12_M30M15_VALIDATION_SET_PATH = Path(
    "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set"
)
SELL_HOUR12_M30M15_CALENDAR_VALIDATION_SET_PATH = Path(
    "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set"
)
STRATEGY_TEST_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_strategy_test.ini")
BACKTEST_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_backtest.ini")
FORWARD_TEST_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_forward_test.ini")
SAMPLE_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sample_collection.ini")
OPTIMIZATION_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_optimization.ini")
NEXT_OPTIMIZATION_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini")
STABLE_CANDIDATE_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_stable_candidate.ini")
BUY_REFIT_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_refit.ini")
BUY_ENTRY_REFIT_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_entry_refit.ini")
BUY_HOUR03_VALIDATION_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_validation.ini")
BUY_STRONG_HOURS_VALIDATION_CONFIG_PATH = Path(
    "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_validation.ini"
)
BUY_STRONG_HOURS_M30M15_VALIDATION_CONFIG_PATH = Path(
    "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.ini"
)
BUY_WIDE_STOP_VALIDATION_CONFIG_PATH = Path(
    "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_wide_stop_validation.ini"
)
BUY_HOUR03_WIDE_STOP_VALIDATION_CONFIG_PATH = Path(
    "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.ini"
)
BUY_HOUR03_WIDE_STOP_CALENDAR_VALIDATION_CONFIG_PATH = Path(
    "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.ini"
)
SELL_ENTRY_REFIT_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_entry_refit.ini")
SELL_REGIME_ENTRY_REFIT_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_regime_entry_refit.ini")
SELL_HOUR12_VALIDATION_CONFIG_PATH = Path("methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_validation.ini")
SELL_HOUR12_M30M15_VALIDATION_CONFIG_PATH = Path(
    "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini"
)
SELL_HOUR12_M30M15_CALENDAR_VALIDATION_CONFIG_PATH = Path(
    "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.ini"
)


def read_ea() -> str:
    return EA_PATH.read_text(encoding="utf-8")


def read_bridge_ea() -> str:
    return BRIDGE_EA_PATH.read_text(encoding="utf-8")


def read_indicator() -> str:
    return INDICATOR_PATH.read_text(encoding="utf-8")


def ea_input_names() -> list[str]:
    return re.findall(r"^input\s+\w+\s+(Inp\w+)\s*=", read_ea(), re.M)


def set_input_names(path: Path) -> list[str]:
    return re.findall(r"^(Inp\w+)=", path.read_text(encoding="utf-8"), re.M)


def optimization_value_count(start: str, step: str, stop: str) -> int:
    normalized_start = start.strip().lower()
    normalized_stop = stop.strip().lower()
    if normalized_start in ("false", "true") or normalized_stop in ("false", "true"):
        return 1 if normalized_start == normalized_stop else 2
    try:
        start_value = Decimal(start.strip())
        step_value = Decimal(step.strip())
        stop_value = Decimal(stop.strip())
    except InvalidOperation:
        return 1
    if step_value == 0:
        return 1 if start_value == stop_value else 0
    if (stop_value - start_value) * step_value < 0:
        return 0
    return int((stop_value - start_value) / step_value) + 1


def optimization_search_space(path: Path) -> int:
    total = 1
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith(";") or "||" not in line:
            continue
        _, raw_value = line.split("=", 1)
        parts = raw_value.split("||")
        if len(parts) < 5 or parts[4].strip().upper() != "Y":
            continue
        total *= optimization_value_count(parts[1], parts[2], parts[3])
    return total


class StandaloneMt5EaTests(unittest.TestCase):
    def test_standalone_ea_exists_and_does_not_use_bridge_requests(self):
        source = read_ea()
        self.assertIn("Swing_Evaluation_Trader.mq5", source)
        self.assertNotIn("WebRequest(", source)
        self.assertNotIn("http://127.0.0.1", source)
        self.assertNotIn("InpBridge", source)

    def test_standalone_ea_has_safe_default_trading_flags(self):
        source = read_ea()
        self.assertIn("input bool InpSignalOnly = true;", source)
        self.assertIn("input bool InpEnableTrading = false;", source)
        self.assertIn("input bool InpAllowLiveTrading = false;", source)
        self.assertIn("input double InpLot = 0.10;", source)
        self.assertIn("input double InpMaxTotalLot = 0.30;", source)
        self.assertIn("input bool InpEnableBuy = true;", source)
        self.assertIn("input bool InpEnableSell = true;", source)

    def test_bridge_ea_has_safe_default_trading_flags(self):
        source = read_bridge_ea()
        self.assertIn("AI_Bridge_Advisor.mq5", source)
        self.assertIn("input bool InpSaveOnlyMode = true;", source)
        self.assertIn("input bool InpPollCodexTradeCommands = false;", source)
        self.assertIn("input bool InpEnableTrading = false;", source)
        self.assertIn("input bool InpAllowCodexTrading = false;", source)
        self.assertIn("if(InpSaveOnlyMode || !InpEnableTrading)", source)
        self.assertIn("if(!dryRun && !InpAllowCodexTrading)", source)

    def test_standalone_ea_uses_latest_optimization_defaults(self):
        source = read_ea()
        self.assertIn("input double InpMinScore = 50.0;", source)
        self.assertIn("input bool InpUseSideRiskReward = true;", source)
        self.assertIn("input double InpBuyRiskReward = 4.0;", source)
        self.assertIn("input double InpSellRiskReward = 5.0;", source)
        self.assertIn("input bool InpUseFittedSellFilter = true;", source)
        self.assertIn("input double InpSellMinM5CloseSlowAtr = -3.2145;", source)
        self.assertIn("input double InpSellMinM1AlternatingRatio = 0.33333;", source)
        self.assertIn("input bool InpUseFittedSellTrendFilter = false;", source)
        self.assertIn("input bool InpUseSellM30M15DownGate = false;", source)
        self.assertIn("input bool InpUseFittedSellTimeFilter = false;", source)
        self.assertIn("input string InpSellBlockedServerHours = \"1,9,10,13,14,16,20\";", source)
        self.assertIn("input bool InpUseFittedSellCalendarFilter = false;", source)
        self.assertIn("input string InpSellBlockedMonths = \"3,6,12\";", source)
        self.assertIn("input string InpSellBlockedWeekdays = \"3\";", source)
        self.assertIn("input bool InpUseSellAllowedServerHours = false;", source)
        self.assertIn("input string InpSellAllowedServerHours = \"\";", source)
        self.assertIn("input bool InpUseFittedSellEntryFilter = false;", source)
        self.assertIn("input bool InpSellRequireBreakConfirm = true;", source)
        self.assertIn("input double InpSellMaxM1ClosePosition = 0.35;", source)
        self.assertIn("input double InpSellMinM1BodyAtr = 0.10;", source)
        self.assertIn("input double InpSellMaxM5CloseSlowAtr = 0.0;", source)
        self.assertIn("input bool InpUseFittedBuyBreakFilter = false;", source)
        self.assertIn("input bool InpUseBuyM30M15UpGate = false;", source)
        self.assertIn("input bool InpUseFittedBuyEntryFilter = false;", source)
        self.assertIn("input bool InpBuyRequireBreakConfirm = true;", source)
        self.assertIn("input double InpBuyMinM1ClosePosition = 0.65;", source)
        self.assertIn("input double InpBuyMinM1BodyAtr = 0.10;", source)
        self.assertIn("input double InpBuyMinM5CloseSlowAtr = 0.0;", source)
        self.assertIn("input bool InpUseFittedBuyTimeFilter = false;", source)
        self.assertIn("input string InpBuyBlockedServerHours = \"2,7,15,18,19,20,23\";", source)
        self.assertIn("input bool InpUseFittedBuyCalendarFilter = false;", source)
        self.assertIn("input string InpBuyBlockedMonths = \"6,8,10\";", source)
        self.assertIn("input string InpBuyBlockedWeekdays = \"3,5\";", source)
        self.assertIn("input bool InpUseBuyAllowedServerHours = false;", source)
        self.assertIn("input string InpBuyAllowedServerHours = \"\";", source)

    def test_standalone_ea_has_forward_test_hooks(self):
        source = read_ea()
        self.assertIn("double OnTester()", source)
        self.assertIn("void OnTradeTransaction(", source)
        self.assertIn("InpTesterMinClosedTrades", source)
        self.assertIn("InpTesterMinProfitFactor", source)

    def test_standalone_ea_exports_mt5_forward_csv_log(self):
        source = read_ea()
        self.assertIn("input bool InpWriteCsvLog = true;", source)
        self.assertIn("input string InpCsvLogFile = \"swing_evaluation_trades.csv\";", source)
        self.assertIn("void AppendTradeCsv(", source)
        self.assertLess(source.index("LogSignalIfNeeded(eval);"), source.index('if(eval.action == "hold")'))
        self.assertIn("event", source)
        self.assertIn("net_profit", source)
        self.assertIn("deal_price", source)
        self.assertIn("spread_points", source)
        self.assertIn("signal_time", source)
        self.assertIn("opened_at", source)
        self.assertIn("entry_server_hour", source)
        self.assertIn("EntryServerHourText", source)
        self.assertIn("latency_seconds", source)
        self.assertIn("hold_seconds", source)
        self.assertIn("m30_trend", source)
        self.assertIn("m15_trend", source)
        self.assertIn("m5_trend", source)
        self.assertIn("m30_slope", source)
        self.assertIn("m15_slope", source)
        self.assertIn("trend_alignment", source)
        self.assertIn("m1_close_position", source)
        self.assertIn("m1_body_atr", source)
        self.assertIn("m5_close_slow_atr", source)
        self.assertIn("m1_alternating_ratio", source)
        self.assertIn("TrendAlignmentText", source)
        self.assertIn("ActiveSignals[index].trend_alignment = eval.trend_alignment;", source)
        self.assertIn("ActiveSignals[index].m1_close_position = eval.m1_close_position;", source)

    def test_strategy_tester_set_files_cover_all_ea_inputs(self):
        expected = ea_input_names()
        for path in (
            BACKTEST_SET_PATH,
            FORWARD_SET_PATH,
            SAMPLE_SET_PATH,
            OPTIMIZATION_SET_PATH,
            NEXT_OPTIMIZATION_SET_PATH,
            STABLE_CANDIDATE_SET_PATH,
            BUY_REFIT_SET_PATH,
            BUY_ENTRY_REFIT_SET_PATH,
            BUY_HOUR03_VALIDATION_SET_PATH,
            BUY_STRONG_HOURS_VALIDATION_SET_PATH,
            BUY_STRONG_HOURS_M30M15_VALIDATION_SET_PATH,
            BUY_WIDE_STOP_VALIDATION_SET_PATH,
            BUY_HOUR03_WIDE_STOP_VALIDATION_SET_PATH,
            BUY_HOUR03_WIDE_STOP_CALENDAR_VALIDATION_SET_PATH,
            SELL_ENTRY_REFIT_SET_PATH,
            SELL_REGIME_ENTRY_REFIT_SET_PATH,
            SELL_HOUR12_VALIDATION_SET_PATH,
            SELL_HOUR12_M30M15_VALIDATION_SET_PATH,
            SELL_HOUR12_M30M15_CALENDAR_VALIDATION_SET_PATH,
        ):
            with self.subTest(path=path):
                self.assertTrue(path.exists())
                actual = set_input_names(path)
                self.assertEqual([name for name in expected if name not in actual], [])
                self.assertEqual([name for name in actual if name not in expected], [])

    def test_strategy_tester_optimization_search_spaces_match_set_comments(self):
        expected_counts = {
            BUY_REFIT_SET_PATH: 288,
            BUY_ENTRY_REFIT_SET_PATH: 864,
            BUY_HOUR03_VALIDATION_SET_PATH: 864,
            BUY_STRONG_HOURS_VALIDATION_SET_PATH: 864,
            BUY_STRONG_HOURS_M30M15_VALIDATION_SET_PATH: 864,
            BUY_WIDE_STOP_VALIDATION_SET_PATH: 864,
            BUY_HOUR03_WIDE_STOP_VALIDATION_SET_PATH: 864,
            BUY_HOUR03_WIDE_STOP_CALENDAR_VALIDATION_SET_PATH: 432,
            SELL_ENTRY_REFIT_SET_PATH: 864,
            SELL_REGIME_ENTRY_REFIT_SET_PATH: 2592,
            SELL_HOUR12_VALIDATION_SET_PATH: 1296,
            SELL_HOUR12_M30M15_VALIDATION_SET_PATH: 648,
            SELL_HOUR12_M30M15_CALENDAR_VALIDATION_SET_PATH: 1296,
            STABLE_CANDIDATE_SET_PATH: 5184,
        }
        for path, expected_count in expected_counts.items():
            with self.subTest(path=path):
                source = path.read_text(encoding="utf-8")
                self.assertEqual(optimization_search_space(path), expected_count)
                self.assertTrue(
                    f"{expected_count} combinations" in source
                    or f"full-factorial passes: {expected_count}" in source
                )

    def test_forward_test_set_enables_tester_trades_but_keeps_chart_button_safe(self):
        source = FORWARD_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("InpSignalOnly=false", source)
        self.assertIn("InpEnableTrading=true", source)
        self.assertIn("InpAllowLiveTrading=true", source)
        self.assertIn("InpLot=0.10", source)
        self.assertIn("InpMaxTotalLot=0.30", source)
        self.assertIn("InpEnableBuy=true", source)
        self.assertIn("InpEnableSell=true", source)
        self.assertIn("InpWriteCsvLog=true", source)
        self.assertIn("InpLogSignalRows=true", source)
        self.assertIn("InpUseConsecutiveLossStop=true", source)
        self.assertIn("InpConsecutiveLossLimit=20", source)
        self.assertIn("InpConsecutiveLossCooldownMinutes=120", source)
        self.assertIn("InpChartButtonDryRunOnly=true", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_backtest_set_enables_tester_trades_but_is_named_for_no_forward_split(self):
        source = BACKTEST_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("backtest preset", source)
        self.assertIn("Forward=No", source)
        self.assertIn("InpSignalOnly=false", source)
        self.assertIn("InpEnableTrading=true", source)
        self.assertIn("InpAllowLiveTrading=true", source)
        self.assertIn("InpLot=0.10", source)
        self.assertIn("InpMaxTotalLot=0.30", source)
        self.assertIn("InpEnableBuy=true", source)
        self.assertIn("InpEnableSell=true", source)
        self.assertIn("InpWriteCsvLog=true", source)
        self.assertIn("InpLogSignalRows=true", source)
        self.assertIn("InpUseConsecutiveLossStop=true", source)
        self.assertIn("InpConsecutiveLossLimit=20", source)
        self.assertIn("InpConsecutiveLossCooldownMinutes=120", source)
        self.assertIn("InpChartButtonDryRunOnly=true", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_sample_collection_set_disables_tester_safety_stops_for_trade_count(self):
        source = SAMPLE_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("sample collection preset", source)
        self.assertIn("InpSignalOnly=false", source)
        self.assertIn("InpEnableTrading=true", source)
        self.assertIn("InpAllowLiveTrading=true", source)
        self.assertIn("InpLot=0.10", source)
        self.assertIn("InpMaxTotalLot=0.30", source)
        self.assertIn("InpEnableBuy=true", source)
        self.assertIn("InpEnableSell=true", source)
        self.assertIn("InpUseDailyLossStop=false", source)
        self.assertIn("InpUseConsecutiveLossStop=false", source)
        self.assertIn("InpConsecutiveLossLimit=20", source)
        self.assertIn("InpConsecutiveLossCooldownMinutes=120", source)
        self.assertIn("InpWriteCsvLog=true", source)
        self.assertIn("InpLogSignalRows=true", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_optimization_set_keeps_search_space_small_and_forward_ready(self):
        source = OPTIMIZATION_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("InpSignalOnly=false", source)
        self.assertIn("InpEnableTrading=true", source)
        self.assertIn("InpAllowLiveTrading=true", source)
        self.assertIn("InpEnableBuy=true||false||0||true||N", source)
        self.assertIn("InpEnableSell=true||false||0||true||N", source)
        self.assertIn("InpMinScore=50.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpBuyRiskReward=4.0||2.0||1.0||5.0||Y", source)
        self.assertIn("InpSellRiskReward=5.0||2.0||1.0||5.0||Y", source)
        self.assertIn("InpMinRiskReward=2.0||2.0||1.0||5.0||N", source)
        self.assertIn("InpUseFittedSellFilter=true||false||0||true||Y", source)
        self.assertIn("InpUseFittedSellTrendFilter=false||false||0||true||Y", source)
        self.assertIn("InpUseFittedSellTimeFilter=false||false||0||true||Y", source)
        self.assertIn("InpSellBlockedServerHours=1,9,10,13,14,16,20", source)
        self.assertIn("InpUseFittedSellEntryFilter=false||false||0||true||N", source)
        self.assertIn("InpSellRequireBreakConfirm=true||false||0||true||N", source)
        self.assertIn("InpSellMaxM1ClosePosition=0.35||0.35||0.05||0.35||N", source)
        self.assertIn("InpSellMinM1BodyAtr=0.10||0.10||0.05||0.10||N", source)
        self.assertIn("InpSellMaxM5CloseSlowAtr=0.0||0.0||0.25||0.0||N", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_next_optimization_set_is_sell_focused_from_recommendation(self):
        source = NEXT_OPTIMIZATION_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("Focus side: sell", source)
        self.assertIn("InpSignalOnly=false", source)
        self.assertIn("InpEnableTrading=true", source)
        self.assertIn("InpAllowLiveTrading=true", source)
        self.assertIn("InpEnableBuy=false||false||0||true||N", source)
        self.assertIn("InpEnableSell=true||false||0||true||N", source)
        self.assertIn("RR values: 3.0", source)
        self.assertIn("InpMinScore=50.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpSwingDepth=3||3||1||6||Y", source)
        self.assertIn("InpSwingAtrBand=0.80||0.60||0.20||1.00||Y", source)
        self.assertIn("InpBuyRiskReward=3||3||1||3||N", source)
        self.assertIn("InpSellRiskReward=3||3||1||3||N", source)
        self.assertIn("InpMinRiskReward=3||3||1||3||N", source)
        self.assertIn("InpMaxRiskReward=3||3||1||3||N", source)
        self.assertIn("InpStopBufferPoints=30||20||10||40||Y", source)
        self.assertIn("InpSellMinM5CloseSlowAtr=-3.2145||-4.0||0.75||-2.5||Y", source)
        self.assertIn("InpSellMinM1AlternatingRatio=0.33333||0.25||0.10||0.45||Y", source)
        self.assertIn("InpUseFittedSellTrendFilter=false||false||0||true||Y", source)
        self.assertIn("InpUseFittedSellTimeFilter=false||false||0||true||Y", source)
        self.assertIn("InpSellBlockedServerHours=1,9,10,13,14,16,20", source)
        self.assertIn("InpUseFittedSellEntryFilter=false||false||0||true||N", source)
        self.assertIn("InpSellRequireBreakConfirm=true||false||0||true||N", source)
        self.assertIn("InpSellMaxM1ClosePosition=0.35||0.35||0.05||0.35||N", source)
        self.assertIn("InpSellMinM1BodyAtr=0.10||0.10||0.05||0.10||N", source)
        self.assertIn("InpSellMaxM5CloseSlowAtr=0.0||0.0||0.25||0.0||N", source)
        self.assertIn("InpMinStopPoints=250||250||25||250||N", source)
        self.assertIn("InpMaxStopPoints=350||350||25||350||N", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_stable_candidate_set_is_separate_sell_focused_search(self):
        source = STABLE_CANDIDATE_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("Stable hint inputs:", source)
        self.assertIn("Focus side: sell", source)
        self.assertIn("full-factorial passes: 5184", source)
        self.assertIn("InpSignalOnly=false", source)
        self.assertIn("InpEnableTrading=true", source)
        self.assertIn("InpAllowLiveTrading=true", source)
        self.assertIn("InpEnableBuy=false||false||0||true||N", source)
        self.assertIn("InpEnableSell=true||false||0||true||N", source)
        self.assertIn("InpUseFittedSellFilter=true||false||0||true||Y", source)
        self.assertIn("InpUseFittedSellTrendFilter=true||false||0||true||Y", source)
        self.assertIn("InpUseFittedSellTimeFilter=true||false||0||true||Y", source)
        self.assertIn("InpMinStopPoints=250||250||25||250||N", source)
        self.assertIn("InpMaxStopPoints=400||400||25||400||N", source)
        self.assertIn("InpUseConsecutiveLossStop=true", source)
        self.assertIn("InpConsecutiveLossLimit=20", source)
        self.assertIn("InpChartButtonDryRunOnly=true", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_buy_refit_set_is_buy_only_and_bounded_for_tester_optimization(self):
        source = BUY_REFIT_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("BUY refit optimization preset", source)
        self.assertIn("288 combinations", source)
        self.assertIn("InpSignalOnly=false", source)
        self.assertIn("InpEnableTrading=true", source)
        self.assertIn("InpAllowLiveTrading=true", source)
        self.assertIn("InpEnableBuy=true||false||0||true||N", source)
        self.assertIn("InpEnableSell=false||false||0||true||N", source)
        self.assertIn("InpSwingDepth=4||3||1||5||Y", source)
        self.assertIn("InpSwingAtrBand=0.80||0.60||0.20||1.00||Y", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpBuyRiskReward=3||2||1||5||Y", source)
        self.assertIn("InpSellRiskReward=4||4||1||4||N", source)
        self.assertIn("InpBuyRsiMin=38.0||38.0||2.0||38.0||N", source)
        self.assertIn("InpBuyRsiMax=66.0||66.0||2.0||66.0||N", source)
        self.assertIn("InpUseFittedSellTrendFilter=false||false||0||true||N", source)
        self.assertIn("InpUseFittedSellTimeFilter=false||false||0||true||N", source)
        self.assertIn("InpSellBlockedServerHours=1,9,10,13,14,16,20", source)
        self.assertIn("InpUseFittedSellEntryFilter=false||false||0||true||N", source)
        self.assertIn("InpSellRequireBreakConfirm=true||false||0||true||N", source)
        self.assertIn("InpSellMaxM1ClosePosition=0.35||0.35||0.05||0.35||N", source)
        self.assertIn("InpSellMinM1BodyAtr=0.10||0.10||0.05||0.10||N", source)
        self.assertIn("InpSellMaxM5CloseSlowAtr=0.0||0.0||0.25||0.0||N", source)
        self.assertIn("InpUseFittedBuyBreakFilter=false||false||0||true||Y", source)
        self.assertIn("InpUseFittedBuyEntryFilter=false||false||0||true||N", source)
        self.assertIn("InpBuyRequireBreakConfirm=true||false||0||true||N", source)
        self.assertIn("InpBuyMinM1ClosePosition=0.65||0.65||0.05||0.65||N", source)
        self.assertIn("InpBuyMinM1BodyAtr=0.10||0.10||0.05||0.10||N", source)
        self.assertIn("InpBuyMinM5CloseSlowAtr=0.0||0.0||0.25||0.0||N", source)
        self.assertIn("InpUseBuyM30M15UpGate=false||false||0||true||N", source)
        self.assertIn("InpUseFittedBuyTimeFilter=false||false||0||true||N", source)
        self.assertIn("InpBuyBlockedServerHours=2,7,15,18,19,20,23", source)
        self.assertIn("InpUseBuyAllowedServerHours=false||false||0||true||N", source)
        self.assertIn("InpBuyAllowedServerHours=", source)
        self.assertIn("InpMaxStopPoints=300||300||50||300||N", source)
        self.assertIn("InpStopBufferPoints=30||30||10||30||N", source)
        self.assertIn("InpUseConsecutiveLossStop=true", source)
        self.assertIn("InpConsecutiveLossLimit=20", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_buy_entry_refit_set_is_buy_only_and_searches_entry_quality(self):
        source = BUY_ENTRY_REFIT_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("BUY entry refit optimization preset", source)
        self.assertIn("864 combinations", source)
        self.assertIn("InpSignalOnly=false", source)
        self.assertIn("InpEnableTrading=true", source)
        self.assertIn("InpAllowLiveTrading=true", source)
        self.assertIn("InpEnableBuy=true||false||0||true||N", source)
        self.assertIn("InpEnableSell=false||false||0||true||N", source)
        self.assertIn("InpSwingDepth=4||4||1||4||N", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpBuyRiskReward=3||2||1||5||Y", source)
        self.assertIn("InpSellRiskReward=4||4||1||4||N", source)
        self.assertIn("InpUseFittedSellEntryFilter=false||false||0||true||N", source)
        self.assertIn("InpUseFittedBuyBreakFilter=false||false||0||true||N", source)
        self.assertIn("InpUseFittedBuyEntryFilter=true||false||0||true||N", source)
        self.assertIn("InpUseBuyM30M15UpGate=false||false||0||true||N", source)
        self.assertIn("InpBuyRequireBreakConfirm=true||false||0||true||Y", source)
        self.assertIn("InpBuyMinM1ClosePosition=0.65||0.55||0.10||0.75||Y", source)
        self.assertIn("InpBuyMinM1BodyAtr=0.10||0.05||0.05||0.15||Y", source)
        self.assertIn("InpBuyMinM5CloseSlowAtr=0.0||-0.25||0.25||0.25||Y", source)
        self.assertIn("InpUseFittedBuyTimeFilter=false||false||0||true||N", source)
        self.assertIn("InpBuyBlockedServerHours=2,7,15,18,19,20,23", source)
        self.assertIn("InpUseBuyAllowedServerHours=false||false||0||true||N", source)
        self.assertIn("InpBuyAllowedServerHours=", source)
        self.assertIn("InpMaxStopPoints=300||300||50||300||N", source)
        self.assertIn("InpStopBufferPoints=30||30||10||30||N", source)
        self.assertIn("InpUseConsecutiveLossStop=true", source)
        self.assertIn("InpConsecutiveLossLimit=20", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_buy_hour03_validation_set_restricts_buy_to_strong_entry_hour(self):
        source = BUY_HOUR03_VALIDATION_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("BUY hour-03 validation optimization preset", source)
        self.assertIn("864 combinations", source)
        self.assertIn("InpEnableBuy=true||false||0||true||N", source)
        self.assertIn("InpEnableSell=false||false||0||true||N", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpBuyRiskReward=3||2||1||5||Y", source)
        self.assertIn("InpUseFittedBuyEntryFilter=true||false||0||true||N", source)
        self.assertIn("InpBuyRequireBreakConfirm=true||false||0||true||Y", source)
        self.assertIn("InpBuyMinM1ClosePosition=0.65||0.55||0.10||0.75||Y", source)
        self.assertIn("InpBuyMinM1BodyAtr=0.10||0.05||0.05||0.15||Y", source)
        self.assertIn("InpBuyMinM5CloseSlowAtr=0.0||-0.25||0.25||0.25||Y", source)
        self.assertIn("InpUseFittedBuyTimeFilter=false||false||0||true||N", source)
        self.assertIn("InpUseBuyAllowedServerHours=true||false||0||true||N", source)
        self.assertIn("InpBuyAllowedServerHours=3", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_buy_strong_hours_validation_set_broadens_buy_time_regime(self):
        source = BUY_STRONG_HOURS_VALIDATION_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("BUY strong-hours validation optimization preset", source)
        self.assertIn("864 combinations", source)
        self.assertIn("InpEnableBuy=true||false||0||true||N", source)
        self.assertIn("InpEnableSell=false||false||0||true||N", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpBuyRiskReward=3||2||1||5||Y", source)
        self.assertIn("InpUseFittedBuyEntryFilter=true||false||0||true||N", source)
        self.assertIn("InpBuyRequireBreakConfirm=true||false||0||true||Y", source)
        self.assertIn("InpBuyMinM1ClosePosition=0.65||0.55||0.10||0.75||Y", source)
        self.assertIn("InpBuyMinM1BodyAtr=0.10||0.05||0.05||0.15||Y", source)
        self.assertIn("InpBuyMinM5CloseSlowAtr=0.0||-0.25||0.25||0.25||Y", source)
        self.assertIn("InpUseBuyAllowedServerHours=true||false||0||true||N", source)
        self.assertIn("InpBuyAllowedServerHours=3,5,6,10", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_buy_strong_hours_m30m15_validation_set_combines_time_and_trend_gates(self):
        source = BUY_STRONG_HOURS_M30M15_VALIDATION_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("BUY strong-hours M30/M15-up validation optimization preset", source)
        self.assertIn("864 combinations", source)
        self.assertIn("InpEnableBuy=true||false||0||true||N", source)
        self.assertIn("InpEnableSell=false||false||0||true||N", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpBuyRiskReward=3||2||1||5||Y", source)
        self.assertIn("InpUseBuyM30M15UpGate=true||false||0||true||N", source)
        self.assertIn("InpUseFittedBuyEntryFilter=true||false||0||true||N", source)
        self.assertIn("InpBuyRequireBreakConfirm=true||false||0||true||Y", source)
        self.assertIn("InpBuyMinM1ClosePosition=0.65||0.55||0.10||0.75||Y", source)
        self.assertIn("InpBuyMinM1BodyAtr=0.10||0.05||0.05||0.15||Y", source)
        self.assertIn("InpBuyMinM5CloseSlowAtr=0.0||-0.25||0.25||0.25||Y", source)
        self.assertIn("InpUseBuyAllowedServerHours=true||false||0||true||N", source)
        self.assertIn("InpBuyAllowedServerHours=3,5,6,10", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_buy_wide_stop_validation_set_forces_broader_buy_risk_box(self):
        source = BUY_WIDE_STOP_VALIDATION_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("BUY wide-stop validation optimization preset", source)
        self.assertIn("864 combinations", source)
        self.assertIn("InpEnableBuy=true||false||0||true||N", source)
        self.assertIn("InpEnableSell=false||false||0||true||N", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpBuyRiskReward=5||2||1||5||Y", source)
        self.assertIn("InpMinStopPoints=300||300||25||300||N", source)
        self.assertIn("InpMaxStopPoints=350||350||25||350||N", source)
        self.assertIn("InpUseBuyM30M15UpGate=true||false||0||true||N", source)
        self.assertIn("InpUseFittedBuyEntryFilter=true||false||0||true||N", source)
        self.assertIn("InpBuyRequireBreakConfirm=true||false||0||true||Y", source)
        self.assertIn("InpBuyMinM1ClosePosition=0.65||0.55||0.10||0.75||Y", source)
        self.assertIn("InpBuyMinM1BodyAtr=0.10||0.05||0.05||0.15||Y", source)
        self.assertIn("InpBuyMinM5CloseSlowAtr=0.0||-0.25||0.25||0.25||Y", source)
        self.assertIn("InpUseBuyAllowedServerHours=true||false||0||true||N", source)
        self.assertIn("InpBuyAllowedServerHours=3,5,6,10", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_buy_hour03_wide_stop_validation_set_splits_entry_hour_and_wide_stop(self):
        source = BUY_HOUR03_WIDE_STOP_VALIDATION_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("BUY hour-03 wide-stop validation optimization preset", source)
        self.assertIn("864 combinations", source)
        self.assertIn("InpEnableBuy=true||false||0||true||N", source)
        self.assertIn("InpEnableSell=false||false||0||true||N", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpBuyRiskReward=5||2||1||5||Y", source)
        self.assertIn("InpMinStopPoints=300||300||25||300||N", source)
        self.assertIn("InpMaxStopPoints=350||350||25||350||N", source)
        self.assertIn("InpUseBuyM30M15UpGate=true||false||0||true||N", source)
        self.assertIn("InpUseFittedBuyEntryFilter=true||false||0||true||N", source)
        self.assertIn("InpBuyRequireBreakConfirm=true||false||0||true||Y", source)
        self.assertIn("InpBuyMinM1ClosePosition=0.65||0.55||0.10||0.75||Y", source)
        self.assertIn("InpBuyMinM1BodyAtr=0.10||0.05||0.05||0.15||Y", source)
        self.assertIn("InpBuyMinM5CloseSlowAtr=0.0||-0.25||0.25||0.25||Y", source)
        self.assertIn("InpUseBuyAllowedServerHours=true||false||0||true||N", source)
        self.assertIn("InpBuyAllowedServerHours=3", source)
        self.assertNotIn("InpBuyAllowedServerHours=3,5,6,10", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_buy_hour03_wide_stop_calendar_validation_set_tests_buy_calendar_filter(self):
        source = BUY_HOUR03_WIDE_STOP_CALENDAR_VALIDATION_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("BUY hour-03 wide-stop calendar validation optimization preset", source)
        self.assertIn("432 combinations", source)
        self.assertIn("InpEnableBuy=true||false||0||true||N", source)
        self.assertIn("InpEnableSell=false||false||0||true||N", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpBuyRiskReward=3||3||1||3||N", source)
        self.assertIn("InpMinRiskReward=3||3||1||3||N", source)
        self.assertIn("InpMaxRiskReward=3||3||1||3||N", source)
        self.assertIn("InpMinStopPoints=300||300||25||300||N", source)
        self.assertIn("InpMaxStopPoints=400||400||25||400||N", source)
        self.assertIn("InpUseBuyM30M15UpGate=true||false||0||true||N", source)
        self.assertIn("InpUseFittedBuyCalendarFilter=false||false||0||true||Y", source)
        self.assertIn("InpBuyBlockedMonths=6,8,10", source)
        self.assertIn("InpBuyBlockedWeekdays=3,5", source)
        self.assertIn("InpUseBuyAllowedServerHours=true||false||0||true||N", source)
        self.assertIn("InpBuyAllowedServerHours=3", source)
        self.assertNotIn("InpBuyAllowedServerHours=3,5,6,10", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_sell_entry_refit_set_is_sell_only_and_bounded_for_tester_optimization(self):
        source = SELL_ENTRY_REFIT_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("SELL entry refit optimization preset", source)
        self.assertIn("864 combinations", source)
        self.assertIn("InpSignalOnly=false", source)
        self.assertIn("InpEnableTrading=true", source)
        self.assertIn("InpAllowLiveTrading=true", source)
        self.assertIn("InpEnableBuy=false||false||0||true||N", source)
        self.assertIn("InpEnableSell=true||false||0||true||N", source)
        self.assertIn("InpSwingDepth=4||4||1||4||N", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpSellRiskReward=3||2||1||5||Y", source)
        self.assertIn("InpMinStopPoints=250||250||25||250||N", source)
        self.assertIn("InpMaxStopPoints=350||350||25||350||N", source)
        self.assertIn("InpUseFittedSellFilter=true||false||0||true||N", source)
        self.assertIn("InpUseFittedSellTrendFilter=false||false||0||true||N", source)
        self.assertIn("InpUseFittedSellTimeFilter=false||false||0||true||N", source)
        self.assertIn("InpUseFittedSellEntryFilter=true||false||0||true||N", source)
        self.assertIn("InpSellRequireBreakConfirm=true||false||0||true||Y", source)
        self.assertIn("InpSellMaxM1ClosePosition=0.35||0.25||0.10||0.45||Y", source)
        self.assertIn("InpSellMinM1BodyAtr=0.10||0.05||0.05||0.15||Y", source)
        self.assertIn("InpSellMaxM5CloseSlowAtr=0.0||-0.50||0.25||0.0||Y", source)
        self.assertIn("InpUseFittedBuyBreakFilter=false||false||0||true||N", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_sell_regime_entry_refit_set_combines_entry_trend_and_time_filters(self):
        source = SELL_REGIME_ENTRY_REFIT_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("SELL regime-entry refit optimization preset", source)
        self.assertIn("2592 combinations", source)
        self.assertIn("InpSignalOnly=false", source)
        self.assertIn("InpEnableTrading=true", source)
        self.assertIn("InpAllowLiveTrading=true", source)
        self.assertIn("InpEnableBuy=false||false||0||true||N", source)
        self.assertIn("InpEnableSell=true||false||0||true||N", source)
        self.assertIn("InpSwingDepth=4||4||1||4||N", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpSellRiskReward=3||3||1||5||Y", source)
        self.assertIn("InpMinRiskReward=3||3||1||3||N", source)
        self.assertIn("InpMaxRiskReward=5||5||1||5||N", source)
        self.assertIn("InpMinStopPoints=250||250||25||250||N", source)
        self.assertIn("InpMaxStopPoints=300||300||25||300||N", source)
        self.assertIn("InpUseFittedSellFilter=true||false||0||true||N", source)
        self.assertIn("InpUseFittedSellTrendFilter=false||false||0||true||Y", source)
        self.assertIn("InpUseFittedSellTimeFilter=false||false||0||true||Y", source)
        self.assertIn("InpSellBlockedServerHours=1,7,9,10,12,13,14,16,19,20", source)
        self.assertIn("InpUseFittedSellEntryFilter=true||false||0||true||N", source)
        self.assertIn("InpSellRequireBreakConfirm=true||false||0||true||Y", source)
        self.assertIn("InpSellMaxM1ClosePosition=0.35||0.25||0.10||0.45||Y", source)
        self.assertIn("InpSellMinM1BodyAtr=0.10||0.05||0.05||0.15||Y", source)
        self.assertIn("InpSellMaxM5CloseSlowAtr=0.0||-0.50||0.25||0.0||Y", source)
        self.assertIn("InpUseFittedBuyBreakFilter=false||false||0||true||N", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_sell_hour12_validation_set_restricts_sell_to_annual_strong_hour(self):
        source = SELL_HOUR12_VALIDATION_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("SELL hour-12 validation optimization preset", source)
        self.assertIn("1296 combinations", source)
        self.assertIn("InpEnableBuy=false||false||0||true||N", source)
        self.assertIn("InpEnableSell=true||false||0||true||N", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpSellRiskReward=3||3||1||5||Y", source)
        self.assertIn("InpUseFittedSellTrendFilter=false||false||0||true||Y", source)
        self.assertIn("InpUseSellM30M15DownGate=false||false||0||true||N", source)
        self.assertIn("InpUseFittedSellTimeFilter=false||false||0||true||N", source)
        self.assertIn("InpUseSellAllowedServerHours=true||false||0||true||N", source)
        self.assertIn("InpSellAllowedServerHours=12", source)
        self.assertIn("InpUseFittedSellEntryFilter=true||false||0||true||N", source)
        self.assertIn("InpSellRequireBreakConfirm=true||false||0||true||Y", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_sell_hour12_m30m15_validation_set_restricts_sell_to_hour_and_downtrend(self):
        source = SELL_HOUR12_M30M15_VALIDATION_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("SELL hour-12 M30/M15-down validation optimization preset", source)
        self.assertIn("648 combinations", source)
        self.assertIn("InpEnableBuy=false||false||0||true||N", source)
        self.assertIn("InpEnableSell=true||false||0||true||N", source)
        self.assertIn("InpMinScore=55.0||45.0||5.0||60.0||Y", source)
        self.assertIn("InpSellRiskReward=3||3||1||5||Y", source)
        self.assertIn("InpUseFittedSellTrendFilter=false||false||0||true||N", source)
        self.assertIn("InpUseSellM30M15DownGate=true||false||0||true||N", source)
        self.assertIn("InpUseFittedSellTimeFilter=false||false||0||true||N", source)
        self.assertIn("InpUseSellAllowedServerHours=true||false||0||true||N", source)
        self.assertIn("InpSellAllowedServerHours=12", source)
        self.assertIn("InpUseFittedSellEntryFilter=true||false||0||true||N", source)
        self.assertIn("InpSellRequireBreakConfirm=true||false||0||true||Y", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_sell_hour12_m30m15_calendar_validation_set_tests_weak_calendar_filter(self):
        source = SELL_HOUR12_M30M15_CALENDAR_VALIDATION_SET_PATH.read_text(encoding="utf-8")
        self.assertIn("SELL hour-12 M30/M15-down calendar validation optimization preset", source)
        self.assertIn("1296 combinations", source)
        self.assertIn("InpEnableBuy=false||false||0||true||N", source)
        self.assertIn("InpEnableSell=true||false||0||true||N", source)
        self.assertIn("InpUseSellM30M15DownGate=true||false||0||true||N", source)
        self.assertIn("InpUseFittedSellCalendarFilter=false||false||0||true||Y", source)
        self.assertIn("InpSellBlockedMonths=3,6,12", source)
        self.assertIn("InpSellBlockedWeekdays=3", source)
        self.assertIn("InpUseSellAllowedServerHours=true||false||0||true||N", source)
        self.assertIn("InpSellAllowedServerHours=12", source)
        self.assertIn("InpAllowChartButtonTrading=false", source)

    def test_strategy_tester_launcher_configs_are_forward_ready(self):
        strategy = STRATEGY_TEST_CONFIG_PATH.read_text(encoding="utf-8")
        backtest = BACKTEST_CONFIG_PATH.read_text(encoding="utf-8")
        forward_test = FORWARD_TEST_CONFIG_PATH.read_text(encoding="utf-8")
        sample = SAMPLE_CONFIG_PATH.read_text(encoding="utf-8")
        optimization = OPTIMIZATION_CONFIG_PATH.read_text(encoding="utf-8")
        next_optimization = NEXT_OPTIMIZATION_CONFIG_PATH.read_text(encoding="utf-8")
        stable_candidate = STABLE_CANDIDATE_CONFIG_PATH.read_text(encoding="utf-8")
        buy_refit = BUY_REFIT_CONFIG_PATH.read_text(encoding="utf-8")
        buy_entry_refit = BUY_ENTRY_REFIT_CONFIG_PATH.read_text(encoding="utf-8")
        buy_hour03_validation = BUY_HOUR03_VALIDATION_CONFIG_PATH.read_text(encoding="utf-8")
        buy_strong_hours_validation = BUY_STRONG_HOURS_VALIDATION_CONFIG_PATH.read_text(encoding="utf-8")
        buy_strong_hours_m30m15_validation = BUY_STRONG_HOURS_M30M15_VALIDATION_CONFIG_PATH.read_text(
            encoding="utf-8"
        )
        buy_wide_stop_validation = BUY_WIDE_STOP_VALIDATION_CONFIG_PATH.read_text(encoding="utf-8")
        buy_hour03_wide_stop_validation = BUY_HOUR03_WIDE_STOP_VALIDATION_CONFIG_PATH.read_text(
            encoding="utf-8"
        )
        buy_hour03_wide_stop_calendar_validation = (
            BUY_HOUR03_WIDE_STOP_CALENDAR_VALIDATION_CONFIG_PATH.read_text(encoding="utf-8")
        )
        sell_entry_refit = SELL_ENTRY_REFIT_CONFIG_PATH.read_text(encoding="utf-8")
        sell_regime_entry_refit = SELL_REGIME_ENTRY_REFIT_CONFIG_PATH.read_text(encoding="utf-8")
        sell_hour12_validation = SELL_HOUR12_VALIDATION_CONFIG_PATH.read_text(encoding="utf-8")
        sell_hour12_m30m15_validation = SELL_HOUR12_M30M15_VALIDATION_CONFIG_PATH.read_text(encoding="utf-8")
        sell_hour12_m30m15_calendar_validation = SELL_HOUR12_M30M15_CALENDAR_VALIDATION_CONFIG_PATH.read_text(
            encoding="utf-8"
        )

        for source in (
            strategy,
            backtest,
            forward_test,
            sample,
            optimization,
            next_optimization,
            stable_candidate,
            buy_refit,
            buy_entry_refit,
            buy_hour03_validation,
            buy_strong_hours_validation,
            buy_strong_hours_m30m15_validation,
            buy_wide_stop_validation,
            buy_hour03_wide_stop_validation,
            buy_hour03_wide_stop_calendar_validation,
            sell_entry_refit,
            sell_regime_entry_refit,
            sell_hour12_validation,
            sell_hour12_m30m15_validation,
            sell_hour12_m30m15_calendar_validation,
        ):
            with self.subTest(source=source.splitlines()[0]):
                self.assertIn("[Experts]", source)
                self.assertIn("Enabled=1", source)
                self.assertIn("AllowLiveTrading=1", source)
                self.assertIn("[Tester]", source)
                self.assertIn("Expert=Swing_Evaluation_Trader.ex5", source)
                self.assertIn("Symbol=XAUUSD-m", source)
                self.assertIn("Period=M1", source)
                self.assertIn("Model=4", source)
                self.assertIn("ExecutionMode=0", source)
                self.assertIn("OptimizationCriterion=6", source)
                self.assertIn("FromDate=2026.06.30", source)
                self.assertIn("ToDate=2026.07.08", source)
                self.assertIn("UseRemote=0", source)
                self.assertIn("UseCloud=0", source)
                if source in (backtest, forward_test):
                    self.assertIn("ShutdownTerminal=1", source)
                else:
                    self.assertIn("ShutdownTerminal=0", source)

        self.assertIn("ForwardMode=0", backtest)
        for source in (
            strategy,
            forward_test,
            sample,
            optimization,
            next_optimization,
            stable_candidate,
            buy_refit,
            buy_entry_refit,
            buy_hour03_validation,
            buy_strong_hours_validation,
            buy_strong_hours_m30m15_validation,
            buy_wide_stop_validation,
            buy_hour03_wide_stop_validation,
            buy_hour03_wide_stop_calendar_validation,
            sell_entry_refit,
            sell_regime_entry_refit,
            sell_hour12_validation,
            sell_hour12_m30m15_validation,
            sell_hour12_m30m15_calendar_validation,
        ):
            with self.subTest(forward_source=source.splitlines()[0]):
                self.assertIn("ForwardMode=3", source)

        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_forward_test.set", strategy)
        self.assertIn("Optimization=0", strategy)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_strategy_test", strategy)
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_backtest.set", backtest)
        self.assertIn("Optimization=0", backtest)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_backtest", backtest)
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_forward_test.set", forward_test)
        self.assertIn("Optimization=0", forward_test)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_forward_test", forward_test)
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_sample_collection.set", sample)
        self.assertIn("Optimization=0", sample)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_sample_collection", sample)
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_optimization.set", optimization)
        self.assertIn("Optimization=2", optimization)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_optimization", optimization)
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_next_optimization.set", next_optimization)
        self.assertIn("Optimization=2", next_optimization)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_next_optimization", next_optimization)
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_stable_candidate_next.set", stable_candidate)
        self.assertIn("Optimization=2", stable_candidate)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_stable_candidate", stable_candidate)
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_buy_refit.set", buy_refit)
        self.assertIn("Optimization=2", buy_refit)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_buy_refit", buy_refit)
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_buy_entry_refit.set", buy_entry_refit)
        self.assertIn("Optimization=2", buy_entry_refit)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_buy_entry_refit", buy_entry_refit)
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_buy_hour03_validation.set", buy_hour03_validation)
        self.assertIn("Optimization=2", buy_hour03_validation)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_buy_hour03_validation", buy_hour03_validation)
        self.assertIn(
            "ExpertParameters=Swing_Evaluation_Trader_buy_strong_hours_validation.set",
            buy_strong_hours_validation,
        )
        self.assertIn("Optimization=2", buy_strong_hours_validation)
        self.assertIn(
            "Report=Tester\\Swing_Evaluation_Trader_buy_strong_hours_validation",
            buy_strong_hours_validation,
        )
        self.assertIn(
            "ExpertParameters=Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set",
            buy_strong_hours_m30m15_validation,
        )
        self.assertIn("Optimization=2", buy_strong_hours_m30m15_validation)
        self.assertIn(
            "Report=Tester\\Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation",
            buy_strong_hours_m30m15_validation,
        )
        self.assertIn(
            "ExpertParameters=Swing_Evaluation_Trader_buy_wide_stop_validation.set",
            buy_wide_stop_validation,
        )
        self.assertIn("Optimization=2", buy_wide_stop_validation)
        self.assertIn(
            "Report=Tester\\Swing_Evaluation_Trader_buy_wide_stop_validation",
            buy_wide_stop_validation,
        )
        self.assertIn(
            "ExpertParameters=Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set",
            buy_hour03_wide_stop_validation,
        )
        self.assertIn("Optimization=2", buy_hour03_wide_stop_validation)
        self.assertIn(
            "Report=Tester\\Swing_Evaluation_Trader_buy_hour03_wide_stop_validation",
            buy_hour03_wide_stop_validation,
        )
        self.assertIn(
            "ExpertParameters=Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set",
            buy_hour03_wide_stop_calendar_validation,
        )
        self.assertIn("Optimization=2", buy_hour03_wide_stop_calendar_validation)
        self.assertIn(
            "Report=Tester\\Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation",
            buy_hour03_wide_stop_calendar_validation,
        )
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_sell_entry_refit.set", sell_entry_refit)
        self.assertIn("Optimization=2", sell_entry_refit)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_sell_entry_refit", sell_entry_refit)
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_sell_regime_entry_refit.set", sell_regime_entry_refit)
        self.assertIn("Optimization=2", sell_regime_entry_refit)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_sell_regime_entry_refit", sell_regime_entry_refit)
        self.assertIn("ExpertParameters=Swing_Evaluation_Trader_sell_hour12_validation.set", sell_hour12_validation)
        self.assertIn("Optimization=2", sell_hour12_validation)
        self.assertIn("Report=Tester\\Swing_Evaluation_Trader_sell_hour12_validation", sell_hour12_validation)
        self.assertIn(
            "ExpertParameters=Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set",
            sell_hour12_m30m15_validation,
        )
        self.assertIn("Optimization=2", sell_hour12_m30m15_validation)
        self.assertIn(
            "Report=Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_validation",
            sell_hour12_m30m15_validation,
        )
        self.assertIn(
            "ExpertParameters=Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set",
            sell_hour12_m30m15_calendar_validation,
        )
        self.assertIn("Optimization=2", sell_hour12_m30m15_calendar_validation)
        self.assertIn(
            "Report=Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation",
            sell_hour12_m30m15_calendar_validation,
        )

    def test_standalone_ea_has_live_safety_stops(self):
        source = read_ea()
        self.assertIn("input bool InpUseDailyLossStop = true;", source)
        self.assertIn("input double InpDailyLossLimit = 5000.0;", source)
        self.assertIn("input bool InpUseConsecutiveLossStop = true;", source)
        self.assertIn("input int InpConsecutiveLossLimit = 20;", source)
        self.assertIn("input int InpConsecutiveLossCooldownMinutes = 120;", source)
        self.assertIn("DailyLossLimitReached()", source)
        self.assertIn("ConsecutiveLossLimitReached()", source)
        self.assertIn("ArmConsecutiveLossCooldown(dealTime);", source)
        self.assertIn("StatConsecutiveLossCooldownUntil", source)
        self.assertIn("daily_net_profit", source)
        self.assertIn("consecutive_losses", source)

    def test_standalone_ea_has_guarded_chart_entry_button(self):
        source = read_ea()
        self.assertIn("input bool InpShowChartEntryButton = false;", source)
        self.assertIn("input bool InpManualButtonOnly = false;", source)
        self.assertIn("input bool InpChartButtonDryRunOnly = true;", source)
        self.assertIn("input bool InpAllowChartButtonTrading = false;", source)
        self.assertIn("void OnChartEvent(", source)
        self.assertIn("OBJ_BUTTON", source)
        self.assertIn("ENTRY BUY", source)
        self.assertIn("ENTRY SELL", source)
        self.assertIn("button dry-run: no order sent", source)
        self.assertIn("button ignored: no tradable action", source)
        self.assertIn("if(InpManualButtonOnly)", source)
        self.assertIn("TryExecute(eval)", source)

    def test_prediction_indicator_exists_and_is_chart_only(self):
        source = read_indicator()
        self.assertIn("Swing_Evaluation_Predictor.mq5", source)
        self.assertIn("#property indicator_chart_window", source)
        self.assertIn("#property indicator_plots 0", source)
        self.assertNotIn("WebRequest(", source)
        self.assertNotIn("http://127.0.0.1", source)
        self.assertNotIn("#include <Trade/Trade.mqh>", source)
        self.assertNotIn("CTrade", source)
        self.assertNotIn("Trade.Buy", source)
        self.assertNotIn("Trade.Sell", source)
        self.assertNotIn("OrderSend", source)

    def test_prediction_indicator_draws_dry_run_order_lines_and_panel(self):
        source = read_indicator()
        self.assertIn("input bool InpDrawDryRunOrderLines = true;", source)
        self.assertIn("DrawPredictionPanel", source)
        self.assertIn("DrawDryRunOrderLines", source)
        self.assertIn("input bool InpClearLinesOnHold = true;", source)
        self.assertIn("DeleteDryRunOrderLines();", source)
        self.assertLess(source.index('if(eval.action == "hold")'), source.index("DrawDryRunOrderLines(eval);"))
        self.assertIn("DRY-RUN ENTRY", source)
        self.assertIn("DRY-RUN SL", source)
        self.assertIn("DRY-RUN TP", source)
        self.assertNotIn("No order is sent by this indicator.", source)
        self.assertIn("OBJ_HLINE", source)
        self.assertIn("OBJ_LABEL", source)
        self.assertIn("input bool InpPanelUsePercentPosition = true;", source)
        self.assertIn("input double InpPanelLeftPercent = 0.0;", source)
        self.assertIn("input double InpPanelTopPercent = 80.0;", source)
        self.assertIn("input ENUM_BASE_CORNER InpPanelCorner = CORNER_LEFT_UPPER;", source)
        self.assertIn("input int InpPanelWidth = 540;", source)
        self.assertIn("input int InpPanelHeight = 168;", source)
        self.assertIn("DrawPanelBox", source)
        self.assertIn("PANEL_BOX", source)
        self.assertIn("OBJ_RECTANGLE_LABEL", source)
        self.assertIn("OBJPROP_BGCOLOR", source)
        self.assertIn("input color InpPanelBackgroundColor = C'18,24,30';", source)
        self.assertIn("input color InpPanelPrimaryColor = clrGold;", source)
        self.assertIn("input int InpPanelDetailFontSize = 7;", source)
        self.assertIn("input int InpPanelScoreFontSize = 10;", source)
        self.assertIn("PanelXDistance()", source)
        self.assertIn("PanelYDistance()", source)
        self.assertIn("CHART_WIDTH_IN_PIXELS", source)
        self.assertIn("CHART_HEIGHT_IN_PIXELS", source)
        self.assertIn("int ClampInt(", source)
        self.assertIn("color actionColor = PanelColor(eval.action);", source)
        self.assertIn("DrawPanelBox(actionColor);", source)
        self.assertIn('StringFormat("%s: %.1f", actionText, eval.score)', source)
        self.assertIn("DrawPanelLineStyled(0, line0, actionColor, InpPanelScoreFontSize);", source)
        self.assertIn("B %.1f/S %.1f", source)
        self.assertIn("M30 %s M15 %s", source)
        self.assertIn("SL %.2f TP %.2f", source)
        self.assertIn('StringFormat("E %.2f   RR %.1f"', source)
        self.assertIn('StringFormat("SL %.2f TP %.2f"', source)
        self.assertNotIn("E -   RR -   SL -   TP -", source)
        self.assertIn("HoldReasonText(eval)", source)
        self.assertIn("WAIT: SCORE LOW", source)
        self.assertIn("WAIT: SPREAD", source)
        self.assertIn("WAIT: NO DOMINANCE", source)
        self.assertIn("OBJPROP_ANCHOR", source)
        self.assertIn("ENUM_ANCHOR_POINT PanelAnchor()", source)
        self.assertIn("string TrendText(", source)
        self.assertNotIn("Buy detail:", source)
        self.assertNotIn("Sell detail:", source)
        self.assertNotIn("Settings:", source)
        self.assertNotIn("Reason:", source)
        self.assertIn("Updated %s", source)
        self.assertIn("Updated %s Spr %dpt Valid %s", source)
        self.assertIn("Spr %dpt", source)
        self.assertIn("Valid %s", source)
        self.assertIn("string ClockText(const datetime value)", source)
        self.assertIn("string ValidClockText(EvaluationResult &eval)", source)
        self.assertIn("string ValidUntilText(EvaluationResult &eval)", source)
        self.assertIn("return 5;", source)

    def test_prediction_indicator_uses_latest_optimization_defaults(self):
        source = read_indicator()
        self.assertIn("input double InpMinScore = 50.0;", source)
        self.assertIn("input bool InpUseSideRiskReward = true;", source)
        self.assertIn("input double InpBuyRiskReward = 4.0;", source)
        self.assertIn("input double InpSellRiskReward = 5.0;", source)
        self.assertIn("input bool InpUseFittedSellFilter = true;", source)
        self.assertIn("input double InpSellMinM5CloseSlowAtr = -3.2145;", source)
        self.assertIn("input double InpSellMinM1AlternatingRatio = 0.33333;", source)
        self.assertIn("input bool InpUseFittedSellTrendFilter = false;", source)
        self.assertIn("input bool InpUseSellM30M15DownGate = false;", source)
        self.assertIn("input bool InpUseFittedSellTimeFilter = false;", source)
        self.assertIn("input string InpSellBlockedServerHours = \"1,9,10,13,14,16,20\";", source)
        self.assertIn("input bool InpUseFittedSellCalendarFilter = false;", source)
        self.assertIn("input string InpSellBlockedMonths = \"3,6,12\";", source)
        self.assertIn("input string InpSellBlockedWeekdays = \"3\";", source)
        self.assertIn("input bool InpUseSellAllowedServerHours = false;", source)
        self.assertIn("input string InpSellAllowedServerHours = \"\";", source)
        self.assertIn("input bool InpUseFittedSellEntryFilter = false;", source)
        self.assertIn("input bool InpSellRequireBreakConfirm = true;", source)
        self.assertIn("input double InpSellMaxM1ClosePosition = 0.35;", source)
        self.assertIn("input double InpSellMinM1BodyAtr = 0.10;", source)
        self.assertIn("input double InpSellMaxM5CloseSlowAtr = 0.0;", source)
        self.assertIn("input bool InpUseFittedBuyBreakFilter = false;", source)
        self.assertIn("input bool InpUseBuyM30M15UpGate = false;", source)
        self.assertIn("input bool InpUseFittedBuyEntryFilter = false;", source)
        self.assertIn("input bool InpBuyRequireBreakConfirm = true;", source)
        self.assertIn("input double InpBuyMinM1ClosePosition = 0.65;", source)
        self.assertIn("input double InpBuyMinM1BodyAtr = 0.10;", source)
        self.assertIn("input double InpBuyMinM5CloseSlowAtr = 0.0;", source)
        self.assertIn("input bool InpUseFittedBuyTimeFilter = false;", source)
        self.assertIn("input string InpBuyBlockedServerHours = \"2,7,15,18,19,20,23\";", source)
        self.assertIn("input bool InpUseFittedBuyCalendarFilter = false;", source)
        self.assertIn("input string InpBuyBlockedMonths = \"6,8,10\";", source)
        self.assertIn("input string InpBuyBlockedWeekdays = \"3,5\";", source)
        self.assertIn("input bool InpUseBuyAllowedServerHours = false;", source)
        self.assertIn("input string InpBuyAllowedServerHours = \"\";", source)


if __name__ == "__main__":
    unittest.main()
