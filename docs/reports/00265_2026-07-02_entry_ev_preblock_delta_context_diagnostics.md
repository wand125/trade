# Entry EV Pre-Block Delta Context Diagnostics

日時: 2026-07-02 03:14 JST
更新日時: 2026-07-02 03:14 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00264の次アクションとして、pre-block side-gap quantileで新たに入ったrefit2025 tradesを、month / direction / regime / sessionへ戻して診断した。
- `scripts/experiments/entry_ev_policy_delta_context_diagnostics.py` を追加し、`trade_delta_rows.csv` をprediction contextへjoinするようにした。
- 実データのdelta outputは共通 `entry_decision_timestamp` を持つため、候補/ベース別timestampがない場合はこの列へfallbackする。
- pre-block `sg95` はfresh supportを戻したが、refit2025ではonly-candidate追加が大きく負けた。q99/floor5は37 rows / `-90.9432`、q95/floor5は57 rows / `-149.6180`。
- 悪化の中心は `short/down_normal_vol`。候補行合計では17 rows / `-276.7060`。
- 2025-05の `short/down_normal_vol/london` は単発 `-77.0520` で、平均予測score `9.047970`、side gap `5.291377` と高いため、単純なscore/gap強化では防げない。
- 判断: delta-context診断インフラはaccepted。pre-block `sg95` policyは引き続きreject。標準policyはNoTrade。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_policy_delta_context_diagnostics.py`
- Added test:
  - `tests/test_entry_ev_policy_delta_context_diagnostics.py`
- Pre-block broad replay with trades:
  - `data/reports/backtests/20260701_180752_20260702_entry_ev_exit_regret_replguard_preblockgap_broad_trades_s1/`
- Post-block guard vs pre-block guard trade delta:
  - `data/reports/backtests/20260701_180937_20260702_entry_ev_replguard_preblockgap_vs_postblock_refit_delta_s1/`
- Delta context diagnostic:
  - `data/reports/backtests/20260701_181417_20260702_entry_ev_replguard_preblockgap_refit_delta_context_s1/`

## What Was Tested

00264では、post-block `side_gap_pct` がblocked side `-1e9` に汚染されてfresh2024を0 tradeにしていることを直した。

今回の問い:

```text
pre-block side-gap quantileで復活した候補は、どのcontextでrefit2025 tailを戻しているか
```

比較対象:

- base: post-block replacement guard broad replay
- candidate: pre-block side-gap quantile broad replay
- family: refit2025
- candidates:
  - `q99_sg95_rank90_floor5_side_regime_session_month`
  - `q95_sg95_rank90_floor5_side_regime_session_month`

## Trade Delta

refit2025のみ:

| candidate | base trades | base pnl | candidate trades | candidate pnl | delta |
|---|---:|---:|---:|---:|---:|
| q99/floor5 | `26` | `+24.7064` | `59` | `-50.0440` | `-74.7504` |
| q95/floor5 | `50` | `+65.2454` | `95` | `-45.6930` | `-110.9384` |

Delta status:

| candidate | status | rows | pnl delta | candidate pnl | base pnl |
|---|---|---:|---:|---:|---:|
| q99/floor5 | common | `22` | `0.0000` | `+40.8992` | `+40.8992` |
| q99/floor5 | only_base | `4` | `+16.1928` | `0.0000` | `-16.1928` |
| q99/floor5 | only_candidate | `37` | `-90.9432` | `-90.9432` | `0.0000` |
| q95/floor5 | common | `38` | `0.0000` | `+103.9250` | `+103.9250` |
| q95/floor5 | only_base | `12` | `+38.6796` | `0.0000` | `-38.6796` |
| q95/floor5 | only_candidate | `57` | `-149.6180` | `-149.6180` | `0.0000` |

Reading:

- pre-block化は悪いbase tradeも少し消している。
- しかしonly-candidate追加の負けが大きすぎる。
- 問題は「fresh supportを戻すこと」ではなく、「戻した後に何を入場許可するか」。

## Month Breakdown

Only-candidate added rows:

| month | candidate | rows | pnl | positive pnl | negative pnl |
|---|---|---:|---:|---:|---:|
| 2025-05 | q95/floor5 | `8` | `-114.2640` | `+63.9000` | `-178.1640` |
| 2025-05 | q99/floor5 | `5` | `-107.0804` | `+55.8400` | `-162.9204` |
| 2025-04 | q95/floor5 | `1` | `-70.1280` | `0.0000` | `-70.1280` |
| 2025-04 | q99/floor5 | `1` | `-70.1280` | `0.0000` | `-70.1280` |
| 2025-06 | q95/floor5 | `3` | `-52.7556` | `0.0000` | `-52.7556` |
| 2025-12 | q99/floor5 | `8` | `-17.6212` | `+53.3900` | `-71.0112` |

2025-11はonly-candidateが大きく勝つ月もあるが、4月/5月/6月/12月のtailで相殺される。

## Context Breakdown

Worst only-candidate contexts:

| context | candidate | rows | pnl | positive pnl | negative pnl |
|---|---|---:|---:|---:|---:|
| `short/down_normal_vol/ny_overlap` | q99/floor5 | `1` | `-70.1280` | `0.0000` | `-70.1280` |
| `short/down_normal_vol/ny_overlap` | q95/floor5 | `3` | `-68.0010` | `+4.4670` | `-72.4680` |
| `short/down_normal_vol/asia` | q99/floor5 | `3` | `-67.7380` | `+1.0100` | `-68.7480` |
| `short/down_normal_vol/asia` | q95/floor5 | `6` | `-62.4250` | `+6.3230` | `-68.7480` |
| `long/range_normal_vol/ny_overlap` | q99/floor5 | `3` | `-34.3452` | `+0.9300` | `-35.2752` |
| `short/down_high_vol/ny_late` | q99/floor5 | `1` | `-23.3556` | `0.0000` | `-23.3556` |
| `short/down_high_vol/ny_late` | q95/floor5 | `1` | `-23.3556` | `0.0000` | `-23.3556` |
| `short/down_normal_vol/london` | q99/floor5 | `2` | `-21.8520` | `+55.2000` | `-77.0520` |

Direction/regime aggregate over candidate rows:

| direction | regime | rows | pnl | positive pnl | negative pnl |
|---|---|---:|---:|---:|---:|
| short | down_normal_vol | `17` | `-276.7060` | `+157.4900` | `-434.1960` |
| long | range_normal_vol | `13` | `-63.8366` | `+28.1170` | `-91.9536` |
| short | down_high_vol | `3` | `-36.2012` | `+10.5100` | `-46.7112` |
| short | up_low_vol | `4` | `-30.8208` | `+3.4200` | `-34.2408` |
| short | down_low_vol | `5` | `-21.8376` | `0.0000` | `-21.8376` |

Important caveat:

- These are candidate-row aggregates, not unique market events. q95 and q99 overlap.
- Therefore this is a failure map, not a ready-made hard blacklist.

## Interpretation

pre-block side-gap quantile fixes one bug-like measurement problem:

```text
blocked score sentinelによってside-gap percentileが壊れる
```

But it exposes another policy problem:

```text
side-gap supportを戻すと、high-confidenceに見えるbad replacement / bad new admissionも戻る
```

The worst rows are not low-score rows. Some large losses have high predicted score and large side gap. So the next guard cannot be a simple `score > X` or `side_gap > X` rule.

The right split is:

1. pre-block side-gap quantile: support normalization layer
2. candidate-only downside / replacement-tail risk: admission layer

Same-window context blacklist such as `short/down_normal_vol` block is not accepted. It is useful as a target discovery clue only.

## Decision

Accepted:

- `entry_ev_policy_delta_context_diagnostics.py`
- timestamp fallback for real `trade_delta_rows.csv`
- pre-block side-gap failure-map evidence

Rejected:

- pre-block `sg95` as a standalone policy
- static context blacklist based on this refit2025 diagnosis
- score/gap-only tightening as the next main fix

Standard policy remains NoTrade.

## Next

1. Build a two-stage diagnostic candidate:
   - stage 1: pre-block side-gap quantile for support normalization
   - stage 2: block or margin newly admitted rows only when prior-only candidate-downside evidence exists
2. Convert this diagnosis into features/targets:
   - candidate-only downside
   - replacement-stateful-net
   - prior context short/downside pressure
   - high-score losing-tail flag
3. Keep q99/q95 selection frozen unless an external chronological window supports one.
4. Do not tune a `down_normal_vol short` hard block on this same refit window.

## Verification

- `python3 -m unittest tests.test_entry_ev_policy_delta_context_diagnostics`: OK
- delta context diagnostic run: OK
