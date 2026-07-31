# Entry EV Post-Exit Path Diagnostics

日時: 2026-07-02 12:18 JST
更新日時: 2026-07-02 12:18 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00286の次アクションとして、raw `loss_exit30_cd15` benchmarkの実行tradeから post-exit re-entry path を診断した。
- `scripts/experiments/entry_ev_post_exit_path_diagnostics.py` を追加し、複数trade rootのCSVを統合して、前回trade結果、前回exitからの経過分、同方向再入、月別PnL、cooldown no-replacement estimateを出力する。
- raw cd15 baselineの合計は00286と一致し、266 trades / total `+118.6900`。
- 全体集計では `prev_loss` 後のtradeは `+122.9292` と強く、広いpost-loss blockは勝ちを削る。`first` tradeは `-10.3524`、`prev_non_loss` 後は `+6.1132`。
- 最良のno-replacement診断は `prev_adjusted_pnl <= -2` かつ60分以内の再入除去で、11 trades / flagged PnL `-8.4774`、kept total `+127.1674`。ただし月floorは `-6.7236` のまま負で、policy採用には足りない。
- 判断: post-exit path diagnostic infrastructureはaccepted。単純なpost-loss cooldown拡張はreject。次はentry削除ではなく、初回/孤立大損と前回勝ち後の大損に対するexit-capture改善へ戻る。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_post_exit_path_diagnostics.py`
- Test:
  - `tests/test_entry_ev_post_exit_path_diagnostics.py`
- Run:
  - `data/reports/backtests/20260702_031623_20260702_entry_ev_raw_cd15_post_exit_path_diagnostics_s1/`

## Method

Input trade roots:

```text
data/reports/backtests/20260702_023738_20260702_entry_ev_downside_meta_raw_cd15_internal_hgb_baseline_s1/trades
data/reports/backtests/20260702_023808_20260702_entry_ev_downside_meta_raw_cd15_hybrid_baseline_s1/trades
```

For each monthly stateful trade sequence:

```text
prev_adjusted_pnl
prev_direction
minutes_since_prev_exit
decision_minutes_since_prev_exit
same_side_as_prev
prev_result_bucket = first / prev_loss / prev_non_loss
post_exit_gap_bucket = <=15 / 15-30 / 30-60 / ...
```

Cooldown grid is a diagnostic no-replacement estimate:

```text
flagged = prev_adjusted_pnl <= threshold
          and 0 <= decision_minutes_since_prev_exit <= cooldown_minutes

kept_pnl_if_removed_no_replacement = total_pnl - flagged_pnl
delta_if_removed_no_replacement = -flagged_pnl
```

This is not a full stateful replay. If a trade is removed, replacement entries are not simulated.

## Overall Path Result

| bucket | trades | total PnL | loss trades | large losses |
|---|---:|---:|---:|---:|
| first | `23` | `-10.3524` | `14` | `6` |
| prev_non_loss | `135` | `+6.1132` | `67` | `16` |
| prev_loss | `108` | `+122.9292` | `41` | `13` |

Reading:

- `prev_loss` 後のtradeを広く止めると、現benchmarkの大きな利益源を消す。
- `first` tradeと、前回勝ち後または長時間後の孤立大損がmonth floorを強く押し下げている。
- `post-exit re-entry` は問題の一部だが、主因全体ではない。

## Cooldown Grid

Top no-replacement rows:

| prev loss threshold | cooldown | flagged trades | flagged PnL | kept total | delta |
|---:|---:|---:|---:|---:|---:|
| `-2.0` | `60m` | `11` | `-8.4774` | `+127.1674` | `+8.4774` |
| `-2.0` | `30m` | `7` | `-5.1204` | `+123.8104` | `+5.1204` |
| `-1.0` | `60m` | `15` | `-2.6158` | `+121.3058` | `+2.6158` |
| `-2.0` | `15m` | `3` | `-1.8760` | `+120.5660` | `+1.8760` |
| `0.0` | `60m` | `33` | `+5.1412` | `+113.5488` | `-5.1412` |
| `-2.0` | `120m` | `15` | `+53.1166` | `+65.5734` | `-53.1166` |

Reading:

- 条件を `prev <= -2` の短時間同方向再入に絞ると、損失clusterを少し削れる。
- ただし `120m` 以上へ広げると flagged PnL が大きくプラスになり、勝ちtradeを消す。
- `prev <= 0` のような広いpost-loss/post-flat条件も勝ちtradeを削る。

## Losing Months

Raw worst months:

| family | month | trades | total PnL | losses | large losses | min trade |
|---|---|---:|---:|---:|---:|---:|
| refit2025 | 2025-09 | `8` | `-6.8324` | `4` | `3` | `-3.4680` |
| refit2025 | 2025-06 | `6` | `-6.5136` | `4` | `2` | `-2.6760` |
| refit2025 | 2025-02 | `11` | `-6.0104` | `8` | `1` | `-4.5564` |
| hybrid2025_0912 | 2025-12 | `2` | `-4.1460` | `1` | `1` | `-4.7160` |
| refit2025 | 2025-08 | `3` | `-3.0500` | `2` | `1` | `-2.5152` |

For the best no-replacement diagnostic `prev <= -2, cooldown 60m`:

| family | month | raw PnL | flagged trades | flagged PnL | kept PnL |
|---|---|---:|---:|---:|---:|
| refit2025 | 2025-06 | `-6.5136` | `1` | `+0.2100` | `-6.7236` |
| refit2025 | 2025-02 | `-6.0104` | `0` | `0.0000` | `-6.0104` |
| refit2025 | 2025-09 | `-6.8324` | `1` | `-2.0040` | `-4.8284` |
| hybrid2025_0912 | 2025-12 | `-4.1460` | `0` | `0.0000` | `-4.1460` |
| refit2025 | 2025-08 | `-3.0500` | `1` | `+0.7300` | `-3.7800` |

Reading:

- 2025-09は少し改善するが、2025-06/2025-08では勝ちtradeも消える。
- 最悪month floorは `-6.8324` から `-6.7236` へ小改善するだけで、非負には遠い。
- hybrid 2025-12の大損は月初回tradeであり、post-loss cooldownでは拾えない。

## Decision

Accepted:

- post-exit sequence enrichment
- cooldown no-replacement diagnostic
- month-level post-exit path breakdown

Rejected as policy:

- broad post-loss cooldown
- `prev <= -2, cooldown 60m` を標準policyとして採用すること
- no-replacement estimateをstateful replay evidenceとして扱うこと

Standard policy remains NoTrade.

Raw `loss_exit30_cd15` remains the fixed diagnostic benchmark.

## Next

1. 初回tradeと前回勝ち後/長時間後の孤立大損を対象に、entry削除ではなくexit-capture targetを作る。
2. `first` / `prev_non_loss` / `>1440` / large loss を文脈特徴として、早期exitまたはcapture shrinkの教師を作る。
3. `prev <= -2, cooldown 30/60m` はpolicyではなく、狭いdownside context featureとして残す。
4. 次にpath-changing interventionを作ったら、00286のstateful floor selectorで role/month floor を再評価する。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_post_exit_path_diagnostics.py tests/test_entry_ev_post_exit_path_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_post_exit_path_diagnostics`: OK
- post-exit path diagnostics run: OK
