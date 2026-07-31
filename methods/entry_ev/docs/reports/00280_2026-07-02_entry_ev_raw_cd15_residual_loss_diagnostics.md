# Entry EV Raw Cd15 Residual Loss Diagnostics

日時: 2026-07-02 10:07 JST
更新日時: 2026-07-02 10:07 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00279の次アクションとして、q95 + raw `loss_exit30_cd15` を固定したまま、残る負け月をprediction文脈へjoinして分解した。
- `entry_ev_multifamily_policy_trade_enrichment.py` を exit-timing成果物にも使えるようにし、`monthly_exit_timing_metrics.csv`、`variant`付きtrade path、`--variants` などのフィルタに対応した。
- internal / external HGB / external hybrid の raw `loss_exit30_cd15` trades は全て prediction match `1.0`。統合結果は00278と同じ total `+118.6900`, 266 trades。
- loss tradeは122件、損失合計 `-229.4220`。このうち no-edge entry は3件 `-34.6800` だけで、119件 `-194.7420` は同方向oracle利益があった。
- つまり主問題は「入る向きが無価値」ではなく、同方向で取れた利益を実行exitで取り逃がす exit-capture failure と、予測EVの過大評価。
- 残存負け月の大半は `loss_with_same_side_oracle_edge` で、`large_exit_regret` も強い。方向ミスだけを強く削ると、勝ちtradeも落とす可能性が高い。
- 判断: raw `loss_exit30_cd15` は固定診断候補として維持。ただし標準policyはNoTrade。次は side/family/regime-conditioned な exit-capture calibration と、loss-first/holding targetのsupervised calibrationへ進む。

## Artifacts

- Updated:
  - `scripts/experiments/entry_ev_direction_residual_loss_diagnostics.py`
  - `scripts/experiments/entry_ev_multifamily_policy_trade_enrichment.py`
  - `tests/test_entry_ev_multifamily_policy_trade_enrichment.py`
- Enrichment artifacts:
  - `data/reports/backtests/20260702_010625_20260702_entry_ev_raw_cd15_internal_enrichment_s1/`
  - `data/reports/backtests/20260702_010637_20260702_entry_ev_raw_cd15_hgb_enrichment_s1/`
  - `data/reports/backtests/20260702_010647_20260702_entry_ev_raw_cd15_hybrid_enrichment_s1/`
- Residual diagnostics:
  - `data/reports/backtests/20260702_010655_20260702_entry_ev_raw_cd15_residual_loss_diagnostics_s1/`

## Method

Fixed candidate:

```text
candidate: q95_sg95_rank90_floor5_side_regime_session_month
variant: loss_exit30_cd15
profit_multiplier: 1.0
loss_multiplier: 1.2
dynamic exit: loss_first_exit_threshold = 0.30
cooldown: 15 minutes after dynamic exit
```

Prediction joins:

| scope | prediction score columns |
|---|---|
| internal | `pred_exit_regret_selector_replguard_preblockgap_confidenceexit_bucket_t0p4_*_best_adjusted_pnl` |
| HGB external | same as internal |
| hybrid external | `pred_base_executable_exit_regret_selector_replguard_preblockgap_confidenceexit_bucket_t0p4_*_best_adjusted_pnl` |

Diagnostics:

- join each executed trade by `entry_decision_timestamp`
- compute selected-side actual oracle PnL, opposite-side oracle PnL, exit regret, best-side regret, EV overestimate
- summarize by role/month and by direction/regime/session
- flag no-edge entry, direction error, same-side oracle edge, large exit regret, large best-side regret, EV overestimate

## Combined Residual Summary

Raw `loss_exit30_cd15` combined:

| metric | value |
|---|---:|
| trades | `266` |
| total adjusted pnl | `+118.6900` |
| loss trades | `122` |
| loss adjusted pnl | `-229.4220` |
| win rate | `0.5338` |
| same-side oracle total | `+7007.4260` |
| actual best total | `+9945.9390` |
| exit regret sum | `+6888.7360` |
| best-side regret sum | `+9827.2490` |
| EV overestimate vs realized sum | `+2567.0266` |
| direction error rate | `0.4549` |
| no-edge entry rate | `0.0113` |
| same-side oracle profitable rate | `0.9887` |
| large exit regret rate | `0.6880` |
| EV overestimate positive rate | `0.9624` |

Reading:

- totalは大きくプラスだが、内部には大きな取り逃がしが残る。
- `same_side_oracle_total` と `actual_best_total` が大きく、entry opportunityそのものは多い。
- `ev_overestimate_vs_realized` はほぼ全tradeで正方向に偏っており、予測EVをそのままthresholdへ使うには過大評価が強い。

## Loss-Only Breakdown

Loss trades only:

| flag | count | pnl | exit regret | same-side oracle |
|---|---:|---:|---:|---:|
| `no_edge_entry` | `3` | `-34.6800` | `+27.9720` | `-6.7080` |
| `direction_error` | `61` | `-127.8564` | `+712.1704` | `+584.3140` |
| `loss_with_same_side_oracle_edge` | `119` | `-194.7420` | `+2937.1700` | `+2742.4280` |
| `large_exit_regret` | `85` | `-174.9012` | `+2777.6792` | `+2602.7780` |
| `large_best_side_regret` | `118` | `-227.9220` | `+2952.4910` | `+2724.5690` |
| `ev_overestimate_positive` | `122` | `-229.4220` | `+2965.1420` | `+2735.7200` |
| `is_forced_exit` | `2` | `-4.3236` | `+9.3336` | `+5.0100` |

Reading:

- loss tradeの大半は、同じ方向を持ち続けるか別の出口なら利益余地があった。
- forced exitは主因ではない。24時間強制決済より前のsignal close / dynamic exit周辺のcaptureが中心。
- no-edgeは少数だが、3件で `-34.6800` と重い。これはentry-side guardの対象として別枠で扱う。

No-edge trades:

| role | month | direction | pnl | same-side oracle | opposite oracle | regime | session |
|---|---|---|---:|---:|---:|---|---|
| refit2025 | 2025-04 | short | `-2.7000` | `-2.7000` | `+58.4400` | down_normal_vol | ny_overlap |
| refit2025 | 2025-05 | short | `-28.9920` | `-2.0640` | `+64.2100` | down_normal_vol | london |
| refit2025 | 2025-10 | long | `-2.9880` | `-1.9440` | `+77.9200` | range_normal_vol | ny_overlap |

## Losing Months

Remaining negative months:

| role | month | trades | pnl | loss pnl | exit regret | direction error rate | no-edge rate |
|---|---|---:|---:|---:|---:|---:|---:|
| refit2025_validation | 2025-09 | `8` | `-6.8324` | `-8.7324` | `+174.2124` | `0.5000` | `0.0000` |
| refit2025_validation | 2025-06 | `6` | `-6.5136` | `-7.0236` | `+53.5096` | `0.8333` | `0.0000` |
| refit2025_validation | 2025-02 | `11` | `-6.0104` | `-8.1804` | `+336.0774` | `0.2727` | `0.0000` |
| hybrid2025_0912_external | 2025-12 | `2` | `-4.1460` | `-4.7160` | `+50.5660` | `0.5000` | `0.0000` |
| refit2025_validation | 2025-08 | `3` | `-3.0500` | `-3.7800` | `+43.8960` | `0.3333` | `0.0000` |
| refit2025_validation | 2025-03 | `11` | `-2.4566` | `-5.4636` | `+158.9276` | `0.6364` | `0.0000` |
| hybrid2025_0912_external | 2025-11 | `1` | `-0.7200` | `-0.7200` | `+48.9000` | `0.0000` | `0.0000` |
| fresh2024_validation | 2024-11 | `1` | `-0.6120` | `-0.6120` | `+60.4720` | `0.0000` | `0.0000` |
| fresh2024_validation | 2024-03 | `1` | `-0.3636` | `-0.3636` | `+37.5636` | `0.0000` | `0.0000` |
| refit2025_validation | 2025-04 | `28` | `-0.3000` | `-30.7800` | `+1547.3000` | `0.3571` | `0.0357` |
| refit2025_validation | 2025-10 | `8` | `-0.0046` | `-10.9716` | `+381.7076` | `0.2500` | `0.1250` |

Reading:

- 2025-09/06/02は小trade数ながらloss pnlよりexit regretが大きく、exit capture改善の余地がある。
- 2025-04/10は月PnLほぼflatだが、内部では大きなloss/winが相殺されている。ここはmonth totalだけでは見落とす。
- hybrid 2025-11/12とfresh 2024-03/11はsupportが薄すぎるため、単月blacklistではなく共通failure targetへ還元する。

## Worst Contexts

Top negative contexts:

| role | month | side | regime | session | trades | pnl | loss pnl | direction error | exit regret |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| refit2025 | 2025-05 | short | down_normal_vol | london | `1` | `-28.9920` | `-28.9920` | `1.0000` | `+26.9280` |
| refit2025 | 2025-04 | long | range_normal_vol | rollover | `1` | `-11.7960` | `-11.7960` | `0.0000` | `+37.0160` |
| HGB 2024-03..06 | 2024-05 | short | range_low_vol | asia | `1` | `-11.4480` | `-11.4480` | `1.0000` | `+24.7850` |
| refit2025 | 2025-12 | long | range_normal_vol | ny_overlap | `2` | `-7.6200` | `-7.6200` | `1.0000` | `+18.0400` |
| HGB 2024-03..06 | 2024-04 | short | up_normal_vol | ny_late | `1` | `-6.5640` | `-6.5640` | `1.0000` | `+9.6410` |
| HGB 2024-03..06 | 2024-06 | short | up_low_vol | ny_late | `3` | `-5.5964` | `-6.3564` | `0.0000` | `+97.3534` |
| hybrid 2025-09..12 | 2025-12 | short | down_high_vol | rollover | `1` | `-4.7160` | `-4.7160` | `1.0000` | `+21.9560` |

Reading:

- worst contextは単一tradeが多く、静的blacklistにすると過学習しやすい。
- HGB側にも同じ「shortで同方向oracle edgeがあるのにcaptureできない」型が出ており、internal固有の過学習だけではない。
- direction errorがある行でも同方向oracleが正のケースが多く、方向分類だけでなくexit timing / capture ratioを別targetにする必要がある。

## Decision

Accepted:

- exit-timing monthly metrics / variant path support in multifamily trade enrichment
- raw `loss_exit30_cd15` residual loss diagnostics
- raw `loss_exit30_cd15` as fixed diagnostic candidate

Rejected:

- treating the remaining losses as a simple entry-direction problem
- static blacklist by single month/context
- standardizing raw `loss_exit30_cd15` while month floor remains negative

Standard policy remains NoTrade.

## Next

1. Build side/family/regime-conditioned exit-capture calibration:
   - target: low capture with same-side oracle edge
   - features: selected side, family, combined regime, session, loss-first probability, predicted holding, side confidence gap, fixed-horizon predicted/actual proxies
2. Add a supervised expected-PnL shrinkage layer:
   - calibrate `pred_taken_ev` to realized / captured PnL
   - evaluate by chronological walk-forward, not random split
3. Keep no-edge as a separate rare-event guard:
   - do not overfit to the three observed no-edge trades
   - require broad support before blocking contexts
4. Preserve raw `loss_exit30_cd15` as frozen benchmark while testing calibration overlays.

## Verification

- `python3 -m unittest tests.test_entry_ev_multifamily_policy_trade_enrichment tests.test_entry_ev_direction_residual_loss_diagnostics`: OK
- raw cd15 internal enrichment: OK
- raw cd15 external HGB enrichment: OK
- raw cd15 external hybrid enrichment: OK
- raw cd15 combined residual diagnostics: OK
