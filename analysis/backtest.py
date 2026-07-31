from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.candidate_generator import generate_candidates
from analysis.deal_context import deal_context_rows, load_deal_history, write_deal_context_report
from analysis.economic_calendar import load_economic_calendar, parse_currencies
from analysis.market_data import Bar, load_history
from analysis.models import BacktestResult, Candidate
from analysis.reports import print_summary, summarize, write_report


def run_backtest(
    candidates: list[Candidate],
    bars: list[Bar],
    *,
    max_hold_minutes: int = 60,
    spread_price: float = 0.0,
) -> list[BacktestResult]:
    results: list[BacktestResult] = []
    for candidate in candidates:
        results.append(_evaluate_candidate(candidate, bars, max_hold_minutes=max_hold_minutes, spread_price=spread_price))
    return results


def _evaluate_candidate(
    candidate: Candidate,
    bars: list[Bar],
    *,
    max_hold_minutes: int,
    spread_price: float,
) -> BacktestResult:
    max_index = min(len(bars) - 1, candidate.index + max_hold_minutes)
    if candidate.index >= len(bars) - 1:
        return BacktestResult(candidate.candidate_id, "timeout", 0.0, 0.0, candidate.time_text, candidate.entry, "no_future_bars", 0)

    for index in range(candidate.index + 1, max_index + 1):
        bar = bars[index]
        if candidate.side == "buy":
            hit_sl = bar.low <= candidate.sl
            hit_tp = bar.high >= candidate.tp
        else:
            hit_sl = bar.high >= candidate.sl
            hit_tp = bar.low <= candidate.tp

        if hit_sl and hit_tp:
            return _result(candidate, "loss", -1.0, bar.time_text, candidate.sl, "ambiguous_sl_first", index, spread_price)
        if hit_sl:
            return _result(candidate, "loss", -1.0, bar.time_text, candidate.sl, "sl", index, spread_price)
        if hit_tp:
            return _result(candidate, "win", candidate.risk_reward, bar.time_text, candidate.tp, "tp", index, spread_price)

    exit_bar = bars[max_index]
    if candidate.side == "buy":
        r_multiple = (exit_bar.close - candidate.entry) / candidate.risk
    else:
        r_multiple = (candidate.entry - exit_bar.close) / candidate.risk
    return _result(candidate, "timeout", r_multiple, exit_bar.time_text, exit_bar.close, "max_hold", max_index, spread_price)


def _result(
    candidate: Candidate,
    result: str,
    r_multiple: float,
    exit_time: str,
    exit_price: float,
    exit_reason: str,
    exit_index: int,
    spread_price: float,
) -> BacktestResult:
    cost_r = spread_price / candidate.risk if candidate.risk > 0 else 0.0
    return BacktestResult(
        candidate_id=candidate.candidate_id,
        result=result,
        r_multiple=r_multiple,
        net_r_multiple=r_multiple - cost_r,
        exit_time=exit_time,
        exit_price=exit_price,
        exit_reason=exit_reason,
        bars_held=max(0, exit_index - candidate.index),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest swing score candidates from MT5 bridge history.")
    parser.add_argument("--history", default="runtime/latest_history_24h.json", help="Path to latest_history_24h.json or latest_history_168h.json")
    parser.add_argument("--deals", default="", help="Optional latest_deal_history.json. When set, also writes a deal/M1 context report.")
    parser.add_argument("--output", default="reports/signal_score_backtest.xlsx", help="Output .xlsx, .csv, or .md report path")
    parser.add_argument("--deal-context-output", default="", help="Optional output path for the deal/M1 context report.")
    parser.add_argument("--rr", type=float, default=5.0, help="Risk/reward target")
    parser.add_argument("--min-score", type=float, default=None, help="Optional minimum score filter")
    parser.add_argument("--max-hold-minutes", type=int, default=60)
    parser.add_argument("--swing-left", type=int, default=3)
    parser.add_argument("--swing-right", type=int, default=3)
    parser.add_argument("--min-atr-distance", type=float, default=0.5)
    parser.add_argument("--max-risk-atr", type=float, default=3.0)
    parser.add_argument("--side", choices=("buy", "sell", "both"), default="both", help="Optional side filter")
    parser.add_argument("--score-profile", choices=("side", "balanced", "buy", "sell"), default="side", help="Scoring profile; side uses buy scoring for buy candidates and sell scoring for sell candidates")
    parser.add_argument("--include-blackout-times", action="store_true", help="Include rollover/news-proxy no-entry windows in candidate generation.")
    parser.add_argument("--calendar", default="runtime/economic_calendar.json", help="Optional economic calendar JSON/CSV in MT5 server time.")
    parser.add_argument("--calendar-input-utc-offset", type=float, default=None, help="UTC offset of naive calendar times, e.g. 9 for JST. Omit when calendar is already MT5 server time.")
    parser.add_argument("--calendar-server-utc-offset", type=float, default=None, help="MT5 server UTC offset used when converting calendar times.")
    parser.add_argument("--news-before-minutes", type=int, default=10)
    parser.add_argument("--news-after-minutes", type=int, default=10)
    parser.add_argument("--news-min-impact", default="high", choices=("low", "medium", "high"))
    parser.add_argument("--news-currencies", default="USD,XAU,ALL")
    parser.add_argument("--limit", type=int, default=0, help="Limit candidates after generation; 0 means no limit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    history = load_history(args.history)
    calendar_events = load_economic_calendar(
        args.calendar,
        input_utc_offset_hours=args.calendar_input_utc_offset,
        server_utc_offset_hours=args.calendar_server_utc_offset,
    )
    candidates = generate_candidates(
        history,
        risk_reward=args.rr,
        swing_left=args.swing_left,
        swing_right=args.swing_right,
        min_atr_distance=args.min_atr_distance,
        max_risk_atr=args.max_risk_atr,
        min_score=args.min_score,
        score_profile=args.score_profile,
        exclude_blackout_times=not args.include_blackout_times,
        blackout_events=calendar_events,
        news_before_minutes=args.news_before_minutes,
        news_after_minutes=args.news_after_minutes,
        news_min_impact=args.news_min_impact,
        news_currencies=parse_currencies(args.news_currencies),
    )
    if args.side != "both":
        candidates = [candidate for candidate in candidates if candidate.side == args.side]
    if args.limit > 0:
        candidates = candidates[: args.limit]
    spread_price = history.spread_points * history.point
    results = run_backtest(candidates, history.bars("M1"), max_hold_minutes=args.max_hold_minutes, spread_price=spread_price)
    write_report(args.output, candidates, results)
    if args.deals:
        deal_history = load_deal_history(args.deals)
        summaries, contexts = deal_context_rows(
            history,
            deal_history,
            symbol=history.symbol or None,
            entry_filter="out",
            before_minutes=10,
            after_minutes=10,
        )
        deal_context_output = args.deal_context_output or default_deal_context_output(args.output)
        write_deal_context_report(deal_context_output, summaries, contexts)
        print(f"deal context deals: {len(summaries)}")
        print(f"deal context rows: {len(contexts)}")
        print(f"wrote {deal_context_output}")
    summary = summarize(candidates, results)
    print_summary(summary)
    print(f"wrote {args.output}")
    return 0


def default_deal_context_output(backtest_output: str | Path) -> str:
    output = Path(backtest_output)
    suffix = output.suffix if output.suffix.lower() in (".xlsx", ".csv") else ".xlsx"
    return str(output.with_name(f"{output.stem}_deal_context{suffix}"))


if __name__ == "__main__":
    raise SystemExit(main())
