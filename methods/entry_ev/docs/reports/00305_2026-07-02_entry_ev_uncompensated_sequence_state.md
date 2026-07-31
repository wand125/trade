# Entry EV Uncompensated Sequence State

日時: 2026-07-02 15:56 JST
更新日時: 2026-07-02 15:56 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00304の次アクションとして、uncompensated loss targetをpointwise hard gateでさらに押すのではなく、選択済みtrade path上のsequence/stateを分解した。
- `scripts/experiments/entry_ev_uncompensated_sequence_state_diagnostics.py` を追加し、00304の予測CSVへ前後trade結果、月内trade数、前回exitからのgap、同方向/同context継続、target周辺のwinner availabilityを付与した。
- `next_*` 系列は診断専用であり、実行時featureとして使わない。実行時に使える候補は `prev_*`, 月内進行、prior context、entry/exit時点情報に限定する。
- `pnl/base/base` の選択pathは 232 trades / total `+329.4348` / uncompensated targets 22件。targetは孤立しておらず、`>10` trade月に18/22、次tradeが勝ちの位置に15/22、前回勝ち後に12/22が集中した。
- high-risk threshold除去は今回も全96本で悪化。positive block deltaは0本、最小悪化でも flagged PnL `+5.6900`。
- 判断: sequence-state diagnostics infrastructureはaccepted。uncompensated-risk probabilityのdirect gateは引き続きreject。次はcandidate-level selector / stateful replayで「この損失を消すと次の勝ちや代替候補をどう失うか」を扱う。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_uncompensated_sequence_state_diagnostics.py`
- New test:
  - `tests/test_entry_ev_uncompensated_sequence_state_diagnostics.py`
- Main run:
  - `data/reports/backtests/20260702_065509_20260702_entry_ev_uncompensated_sequence_state_s1/`

## Input

```text
data/reports/backtests/20260702_064017_20260702_entry_ev_uncompensated_loss_head_s1/selected_trade_uncompensated_loss_head_predictions.csv
```

Run setting:

```text
target modes:
  factor,pnl

large-loss feature sets:
  base,base_prior

uncompensated feature sets:
  base,base_prior,base_risk,base_prior_risk

diagnostic groups:
  prev_result_bucket
  next_result_bucket
  month_trade_count_bucket
  direction,session_regime
  direction,combined_regime
  prev_result_bucket,next_result_bucket
  prev_result_bucket,post_exit_gap_bucket
  month_trade_count_bucket,prev_result_bucket
```

Leakage note:

- `next_result_bucket`, `next_adjusted_pnl`, `decision_minutes_until_next_entry`, `next_is_target` はpath診断専用。
- 実行可能featureへ移す場合は、前回trade、月内trade数、prior-only context統計、entry/exit時点の観測値だけを使う。

## Sequence State Summary

`pnl/base/base` の集計:

| group | rows | total pnl | target count | target pnl | reading |
|---|---:|---:|---:|---:|---|
| all selected path | `232` | `+329.4348` | `22` | `-115.0848` | diagnostic branchは全体プラス |
| month trade count `>10` | `180` | `+234.1000` | `18` | `-105.3204` | targetは取引密度の高い月に集中 |
| next trade win | `122` | `+204.7122` | `15` | `-77.4000` | target直後にwinnerが多い |
| prev trade win | `126` | `+123.6028` | `12` | `-74.8680` | 前回勝ち後の損失も多い |
| prev win -> next win | `68` | `+72.5216` | `9` | `-58.3116` | 単純な局所blockは前後winnerを壊しやすい |
| short | `105` | `+105.6292` | `16` | `-93.8640` | targetはshort側に偏る |
| long | `127` | `+223.8056` | `6` | `-21.2208` | long側は損失targetが少ない |

Source / role:

| group | rows | target count | target pnl | total pnl |
|---|---:|---:|---:|---:|
| internal | `135` | `12` | `-65.0604` | `+291.3874` |
| hgb | `92` | `10` | `-50.0244` | `+26.7074` |
| hybrid | `5` | `0` | `0.0000` | `+11.3400` |
| refit2025_validation | `111` | `12` | `-65.0604` | `+273.0184` |
| hgb2024_0306_external | `81` | `10` | `-50.0244` | `+26.1720` |

Context concentration:

| context | rows | target count | target pnl | total pnl |
|---|---:|---:|---:|---:|
| short / down_normal_vol | `24` | `5` | `-41.5320` | `+42.7056` |
| short / up_normal_vol | `17` | `4` | `-19.8084` | `+16.0746` |
| long / range_normal_vol | `28` | `3` | `-14.0844` | `+12.9240` |
| short / range_low_vol | `16` | `2` | `-15.0120` | `-5.5598` |
| short / up_low_vol | `10` | `2` | `-7.2480` | `-5.0560` |

Reading:

- targetは「月初1件目だけ」「前回負け直後だけ」ではない。
- `next_win` 直前のtargetが多いため、現時点の除去診断は replacement / skip cost を入れないと実行PnLを誤読しやすい。
- short-side contextは引き続き濃いが、context totalがプラスのものも多く、static blacklist化は危険。

## Threshold Diagnostics

All threshold rows:

| metric | value |
|---|---:|
| threshold rows | `96` |
| positive block delta | `0` |
| best block delta if removed | `-5.6900` |
| best flagged target count | `0` |

`pnl/base/base`:

| threshold | flagged trades | flagged pnl | delta if removed | flagged target | target recall | flagged next wins | next win pnl |
|---|---:|---:|---:|---:|---:|---:|---:|
| `prob_ge_0.2` | `16` | `+60.9520` | `-60.9520` | `3` | `0.1364` | `11` | `+94.8570` |
| `prob_ge_0.4` | `4` | `+69.1000` | `-69.1000` | `0` | `0.0000` | `3` | `+66.0900` |
| `prob_ge_0.3` | `9` | `+76.1824` | `-76.1824` | `1` | `0.0455` | `7` | `+87.5970` |
| `top_q90` | `24` | `+80.1380` | `-80.1380` | `3` | `0.1364` | `16` | `+110.1370` |
| `prob_ge_0.1` | `41` | `+90.2314` | `-90.2314` | `8` | `0.3636` | `26` | `+149.1970` |
| `top_q95` | `12` | `+94.7224` | `-94.7224` | `1` | `0.0455` | `10` | `+92.1870` |

Reading:

- target recallを上げるほど、次のwinnerやpositive pathも強く巻き込む。
- `prob_ge_0.1` はtarget 8件を拾うが、flagged PnLは `+90.2314` なので除去すると大幅悪化。
- 00304と同じく、risk確率を直接hard gateに変換する方向は採用しない。

## Target Examples

`pnl/base/base` のtarget上位:

| source | role | month | idx / count | prev | next | direction | regime | session | pnl | pred uncomp | prev pnl | next pnl |
|---|---|---|---:|---|---|---|---|---|---:|---:|---:|---:|
| hgb | hgb2024_0306_external | `2024-05` | `1 / 21` | first | next_win | short | up_low_vol | asia | `-2.5716` | `0.3427` | n/a | `+11.7700` |
| internal | refit2025_validation | `2025-05` | `8 / 15` | prev_win | next_win | short | down_normal_vol | london | `-28.9920` | `0.2184` | `+2.2900` | `+2.6700` |
| hgb | hgb2024_0306_external | `2024-06` | `2 / 16` | prev_loss | next_loss | short | up_low_vol | ny_late | `-4.6764` | `0.2181` | `-1.4280` | `-1.6800` |
| internal | refit2025_validation | `2025-12` | `8 / 13` | prev_win | next_win | short | down_high_vol | ny_late | `-2.8200` | `0.1714` | `+10.5400` | `+4.0370` |

Reading:

- 大きいtargetもあるが、前後に勝ちtradeがあるものが多い。
- `2024-06` のようなprev_loss/next_lossは entry block候補に見えるが、全体では少数で、単純ruleはcoverageが薄い。

## Decision

Accepted:

- selected-trade sequence-state diagnostic infrastructure
- `uncompensated_loss_target` と前後pathのjoin
- threshold除去に `next_win` 巻き込みを併記する評価表

Rejected:

- uncompensated-loss probabilityのdirect hard gate
- high-risk quantile removal
- `prev_loss` / `month_warmup` など広い単純state ruleへの即時回帰
- `next_*` を実行時featureとして使うこと

Standard policy remains NoTrade.

## Next

1. Candidate-level selector / stateful replayで、risk rowを消したときのreplacement / skipped next winner / missed future candidateを明示的に評価する。
2. 実行時featureとして使える `prev_*`, 月内trade count、prior-only context residual、entry/exit timing featureを候補selectorへ接続する。
3. `next_*` は教師作成・error analysis専用にし、実行featureへ混ぜない。
4. short-side target集中はstatic blacklistではなく、candidate-level scoreやexit timing targetの補助featureとして扱う。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_uncompensated_sequence_state_diagnostics.py tests/test_entry_ev_uncompensated_sequence_state_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_uncompensated_sequence_state_diagnostics`: OK
- `uv run python -m unittest tests.test_entry_ev_uncompensated_sequence_state_diagnostics tests.test_entry_ev_selected_trade_uncompensated_loss_head tests.test_docs_reports`: OK
- `git diff --check`: OK
- uncompensated sequence-state diagnostics run: OK
