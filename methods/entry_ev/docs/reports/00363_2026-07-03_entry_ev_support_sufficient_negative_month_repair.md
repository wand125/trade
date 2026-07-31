# Entry EV Support-Sufficient Negative Month Repair

日時: 2026-07-03 15:24 JST
更新日時: 2026-07-03 15:24 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00362で `refit2025 2025-03` はraw prediction不足ではなく、`extra_*_needed=0` のsupport-sufficient negative monthだと分かったため、既存trade起点のrepair診断を追加した。
- `entry_ev_support_sufficient_negative_month_repair_diagnostics.py` を追加し、既存tradeのskip / fixed-horizon exit extension / predicted fixed-horizon choice / replacement candidateを分けて出力した。
- `refit2025 2025-03` は9 trades、5L / 4S、month PnL `-0.4730`、loss trades 4本 / loss PnL `-3.4800`。
- 事後oracleでは、loss全skipで月PnL `+3.0070`、single worst skipで `+1.8670`、single fixed-best exit repairで `+4.1230`、top-score replacementで `+4.2170` まで改善余地がある。
- ただし現predicted fixed-horizon argmaxは、single bestでも月PnL `-8.8574` へ悪化する。exit extensionは「実績上は直せる箇所がある」が、現予測のhorizon選択が壊れている。
- 判断: support-sufficient negative month laneはaccepted diagnostic infrastructure。次はloss trade識別headとhorizon abstention / replacement selectorを作る。標準policyはNoTrade。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_support_sufficient_negative_month_repair_diagnostics.py`

Added tests:

- `tests/test_entry_ev_support_sufficient_negative_month_repair_diagnostics.py`

Run:

- `data/reports/backtests/20260703_062432_20260703_entry_ev_00363_support_sufficient_negative_month_repair_s2/`

Outputs:

- `support_sufficient_month_summary.csv`
- `support_sufficient_current_trade_diagnostics.csv`
- `support_sufficient_loss_replacement_summary.csv`
- `support_sufficient_replacement_candidate_examples.csv`
- `support_sufficient_repair_meta.json`

## Method

Target:

```text
refit2025_validation:2025-03:short
```

Input config:

```text
data/reports/backtests/20260702_111114_20260702_entry_ev_00318_thin_month_opposite_candidates_00314_w5_s2/config.json
```

Diagnostics:

- Current trade repair:
  - `skip_trade_delta = -adjusted_pnl`
  - actual fixed 60/240/720m best as oracle diagnostic
  - predicted fixed 60/240/720m argmax and realized PnL at that horizon
  - predicted-vs-actual overestimate per fixed horizon
- Replacement:
  - remove one losing current trade interval
  - exclude already selected current entries
  - keep statefully available strict / relaxed / one-fail candidates
  - report top-score replacement using predicted fixed-horizon argmax
  - report oracle best replacement only as diagnostic upper bound

Important:

- Actual fixed-best and oracle replacement are diagnostics only.
- Choosing which loss to skip or replace after it loses is hindsight. This report identifies target labels and failure modes, not a deployable policy.

## Month Result

| metric | value |
|---|---:|
| baseline month PnL | `-0.4730` |
| trades | `9` |
| side mix | `5L / 4S` |
| loss trades | `4` |
| loss PnL sum | `-3.4800` |
| winner PnL sum | `+3.0070` |
| skip all losses oracle | `+3.0070` |
| best single skip oracle | `+1.8670` |
| best single fixed-best exit oracle | `+4.1230` |
| best single predicted fixed-exit | `-8.8574` |
| best top-score replacement at predicted horizon | `+4.2170` |
| best oracle replacement | `+40.3570` |

## Current Trade Findings

Key loss trades:

| trade | current | actual fixed-best | pred fixed argmax -> actual | reading |
|---|---:|---:|---:|---|
| `2025-03-20 00:38 long` | `-0.6360` | `240m +3.9600` | `720m -> -13.7040` | exit extension possible in oracle, prediction chooses bad horizon |
| `2025-03-20 09:53 long` | `-0.1716` | `720m +2.7470` | `240m -> -8.5560` | extension possible in oracle, prediction chooses bad horizon |
| `2025-03-21 14:00 short` | `-2.3400` | `240m -11.2440` | `240m -> -11.2440` | no exit extension repair; skip/replacement needed |
| `2025-03-21 14:29 short` | `-0.3324` | `60m -7.1964` | `240m -> -13.0800` | no exit extension repair; skip/replacement needed |

Winner risk:

- Some winner trades also have large bad predicted horizon choices. Example: `2025-03-31 03:40 short` current `+1.3800`, predicted fixed argmax 720m actual `-15.5400`.
- Therefore fixed-horizon extension must be abstention-first. It cannot simply follow current predicted fixed-horizon argmax.

## Replacement Findings

For each loss trade, the top-score statefully available replacement was the same one-fail long cluster around `2025-03-26 14:34 UTC`:

| replaced loss | candidate | stage | side score | pred horizon | actual at pred horizon | month PnL |
|---|---|---|---:|---:|---:|---:|
| `2025-03-20 00:38 long -0.6360` | `2025-03-26 14:34 long` | one-fail | `7.1392` | `240m` | `+2.3500` | `+2.5130` |
| `2025-03-20 09:53 long -0.1716` | `2025-03-26 14:34 long` | one-fail | `7.1392` | `240m` | `+2.3500` | `+2.0486` |
| `2025-03-21 14:00 short -2.3400` | `2025-03-26 14:34 long` | one-fail | `7.1392` | `240m` | `+2.3500` | `+4.2170` |
| `2025-03-21 14:29 short -0.3324` | `2025-03-26 14:34 long` | one-fail | `7.1392` | `240m` | `+2.3500` | `+2.2094` |

Replacement read:

- The replacement candidate is not a standard-policy signal yet. It is one-fail, and choosing which loss to replace requires a loss-risk selector.
- This supports a narrow replacement lane for support-sufficient negative months, not global one-fail widening.
- The main target is the `2025-03-21 14:00 short` loss: skip alone moves month PnL to `+1.8670`; top-score replacement moves it to `+4.2170`.

## Decision

- Keep 00318 thin-support lane unchanged.
- Add support-sufficient negative-month repair as a separate lane:
  - loss-risk classifier for existing selected trades
  - horizon abstention / horizon confidence for extension candidates
  - target-aware replacement selector that does not globally widen one-fail rows
- Current predicted fixed-horizon argmax is rejected as an exit selector for this lane.
- Standard policy remains NoTrade.

## Next

1. Build a loss-risk target for support-sufficient negative months using current selected trade features only.
2. Build a replacement candidate selector that starts from predicted loss-risk, then searches statefully available one-fail / relaxed candidates with horizon guard.
3. For fixed-horizon exit extension, add abstention: require predicted horizon confidence and reject cases where broad prior / tail / EV disagreement is high.
4. Keep oracle fixed-best and oracle replacement columns diagnostic-only.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_sufficient_negative_month_repair_diagnostics.py tests/test_entry_ev_support_sufficient_negative_month_repair_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_sufficient_negative_month_repair_diagnostics`: OK
- 00363 support-sufficient negative month repair diagnostic run: OK
