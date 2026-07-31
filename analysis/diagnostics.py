from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import sqrt
from statistics import mean
from typing import Callable, Iterable

from analysis.models import BacktestResult, Candidate


DEFAULT_THRESHOLDS = tuple(float(value) for value in range(40, 86, 5))


@dataclass(frozen=True)
class ComponentWeights:
    trend: float = 1.0
    structure: float = 1.0
    entry: float = 1.0
    risk: float = 1.0
    cost: float = 1.0
    chop: float = 1.0

    def label(self) -> str:
        return (
            f"tr{self.trend:g}_st{self.structure:g}_en{self.entry:g}_"
            f"rr{self.risk:g}_co{self.cost:g}_ch{self.chop:g}"
        )


def feature_diagnostics(candidates: list[Candidate], results: list[BacktestResult]) -> list[dict[str, object]]:
    result_by_id = {result.candidate_id: result for result in results}
    names = sorted(_numeric_feature_names(candidates))
    rows: list[dict[str, object]] = []
    for name in names:
        pairs: list[tuple[float, BacktestResult]] = []
        missing = 0
        for candidate in candidates:
            result = result_by_id.get(candidate.candidate_id)
            if result is None:
                continue
            value = _feature_value(candidate, name)
            if value is None:
                missing += 1
                continue
            pairs.append((value, result))
        if not pairs:
            continue
        values = [value for value, _ in pairs]
        wins = [value for value, result in pairs if result.result == "win"]
        losses = [value for value, result in pairs if result.result == "loss"]
        net_values = [result.net_r_multiple for _, result in pairs]
        corr = _correlation(values, net_values)
        rows.append(
            {
                "feature": name,
                "count": len(pairs),
                "missing": missing,
                "mean_all": round(mean(values), 5),
                "mean_win": round(mean(wins), 5) if wins else "",
                "mean_loss": round(mean(losses), 5) if losses else "",
                "win_minus_loss": round(mean(wins) - mean(losses), 5) if wins and losses else "",
                "corr_net_r": round(corr, 5) if corr is not None else "",
                "higher_is_better": "yes" if corr is not None and corr > 0 else "no" if corr is not None and corr < 0 else "",
            }
        )
    return sorted(rows, key=lambda row: abs(float(row["corr_net_r"] or 0.0)), reverse=True)


def threshold_diagnostics(
    candidates: list[Candidate],
    results: list[BacktestResult],
    *,
    thresholds: Iterable[float] = DEFAULT_THRESHOLDS,
    score_getter: Callable[[Candidate], float] | None = None,
) -> list[dict[str, object]]:
    result_by_id = {result.candidate_id: result for result in results}
    score = score_getter or (lambda candidate: candidate.score)
    rows: list[dict[str, object]] = []
    for threshold in thresholds:
        selected = [
            (candidate, result_by_id[candidate.candidate_id])
            for candidate in candidates
            if candidate.candidate_id in result_by_id and score(candidate) >= threshold
        ]
        rows.append({"threshold": threshold, **metrics_for_pairs(selected)})
    return rows


def component_weight_search(
    candidates: list[Candidate],
    results: list[BacktestResult],
    *,
    side: str = "both",
    thresholds: Iterable[float] = DEFAULT_THRESHOLDS,
    min_count: int = 30,
    positive_multipliers: Iterable[float] = (0.75, 1.0, 1.25, 1.5),
    penalty_multipliers: Iterable[float] = (0.75, 1.0, 1.25),
) -> list[dict[str, object]]:
    filtered_candidates = [candidate for candidate in candidates if side == "both" or candidate.side == side]
    result_by_id = {result.candidate_id: result for result in results}
    positive_values = tuple(positive_multipliers)
    penalty_values = tuple(penalty_multipliers)
    threshold_values = tuple(thresholds)
    rows: list[dict[str, object]] = []

    for trend, structure, entry, risk in product(positive_values, repeat=4):
        for cost, chop in product(penalty_values, repeat=2):
            weights = ComponentWeights(trend, structure, entry, risk, cost, chop)
            rescored = [
                (candidate, result_by_id[candidate.candidate_id], weighted_score(candidate, weights))
                for candidate in filtered_candidates
                if candidate.candidate_id in result_by_id
            ]
            for threshold in threshold_values:
                selected = [(candidate, result) for candidate, result, score in rescored if score >= threshold]
                if len(selected) < min_count:
                    continue
                metrics = metrics_for_pairs(selected)
                rows.append(
                    {
                        "side": side,
                        "threshold": threshold,
                        "weights": weights.label(),
                        "trend_w": trend,
                        "structure_w": structure,
                        "entry_w": entry,
                        "risk_w": risk,
                        "cost_w": cost,
                        "chop_w": chop,
                        **metrics,
                    }
                )
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("avg_r", 0.0) or 0.0),
            float(row.get("pf", 0.0) or 0.0),
            float(row.get("total_r", 0.0) or 0.0),
        ),
        reverse=True,
    )


def weighted_score(candidate: Candidate, weights: ComponentWeights) -> float:
    parts = candidate.score_parts
    score = (
        _number(parts.get("trend_score")) * weights.trend
        + _number(parts.get("structure_score")) * weights.structure
        + _number(parts.get("entry_trigger_score")) * weights.entry
        + _number(parts.get("risk_reward_score")) * weights.risk
        + _number(parts.get("cost_penalty")) * weights.cost
        + _number(parts.get("chop_penalty")) * weights.chop
    )
    return max(0.0, min(100.0, score))


def metrics_for_pairs(pairs: list[tuple[Candidate, BacktestResult]]) -> dict[str, object]:
    if not pairs:
        return {
            "count": 0,
            "wins": 0,
            "losses": 0,
            "timeouts": 0,
            "win_rate": 0.0,
            "avg_r": 0.0,
            "pf": 0.0,
            "total_r": 0.0,
            "max_losing_streak": 0,
            "max_drawdown_r": 0.0,
            "avg_bars_held": 0.0,
        }
    results = [result for _, result in pairs]
    net_values = [result.net_r_multiple for result in results]
    gross_profit = sum(value for value in net_values if value > 0)
    gross_loss = -sum(value for value in net_values if value < 0)
    wins = sum(1 for result in results if result.result == "win")
    losses = sum(1 for result in results if result.result == "loss")
    timeouts = sum(1 for result in results if result.result == "timeout")
    return {
        "count": len(results),
        "wins": wins,
        "losses": losses,
        "timeouts": timeouts,
        "win_rate": round(wins / len(results), 4),
        "avg_r": round(sum(net_values) / len(results), 4),
        "pf": round(gross_profit / gross_loss, 4) if gross_loss > 0 else 0.0,
        "total_r": round(sum(net_values), 4),
        "max_losing_streak": max_losing_streak(results),
        "max_drawdown_r": round(max_drawdown(net_values), 4),
        "avg_bars_held": round(sum(result.bars_held for result in results) / len(results), 2),
    }


def max_losing_streak(results: list[BacktestResult]) -> int:
    longest = 0
    current = 0
    for result in results:
        if result.net_r_multiple < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def max_drawdown(net_values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in net_values:
        equity += value
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def _numeric_feature_names(candidates: list[Candidate]) -> set[str]:
    names = {
        "score",
        "trend_score",
        "structure_score",
        "entry_trigger_score",
        "risk_reward_score",
        "cost_penalty",
        "chop_penalty",
    }
    for candidate in candidates:
        for name, value in candidate.features.items():
            if _value_to_float(value) is not None:
                names.add(name)
    return names


def _feature_value(candidate: Candidate, name: str) -> float | None:
    if name == "score":
        return candidate.score
    if name in candidate.score_parts:
        return _value_to_float(candidate.score_parts.get(name))
    return _value_to_float(candidate.features.get(name))


def _value_to_float(value: object) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _number(value: object) -> float:
    parsed = _value_to_float(value)
    return parsed if parsed is not None else 0.0


def _correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mean_x = mean(xs)
    mean_y = mean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom_x = sqrt(sum((x - mean_x) ** 2 for x in xs))
    denom_y = sqrt(sum((y - mean_y) ** 2 for y in ys))
    if denom_x == 0 or denom_y == 0:
        return None
    return numerator / (denom_x * denom_y)
