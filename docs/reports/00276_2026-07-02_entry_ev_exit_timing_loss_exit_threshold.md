# Entry EV Exit Timing Loss Exit Threshold

日時: 2026-07-02 08:53 JST
更新日時: 2026-07-02 08:53 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00275でtail-risk headをdiagnosticへ降格したため、exit timing / exit regret reductionへ戻した。
- `scripts/experiments/entry_ev_quantile_exit_timing_sensitivity.py` を追加し、既存quantile replayへ `time_exit_holding_shrink`, `loss_first_holding_shrink`, `time_exit_exit_threshold`, `loss_first_exit_threshold` を固定variantとして差し込めるようにした。
- 高めのdynamic exit threshold `0.75/0.90` はhybrid/HGBともほぼ発火せず、baselineと同一だった。
- holding shrinkは損失を少し縮めるが、HGB 2024-03の大損を止められず標準候補にはならない。
- 低めの `loss_first_exit_threshold` は明確に効いた。HGB単体では q95/floor5/rank90 + `loss_exit20` が total `+54.0206`, month min `+2.6780`, 233 tradesでNoTrade-first gateを通過した。
- ただしhybrid 2025-09..12では最良帯が `loss_exit35` 付近へずれ、HGBの `loss_exit20/25` はhybrid roleをわずかに負にした。
- HGB + hybrid統合では q95 + `loss_exit30` が total `+44.5308`, role min `+2.6780`, positive roles `3/3`, 141 tradesまで改善したが、month min `-4.1460` が残る。
- 判断: low loss-first dynamic exitは有力なexit timing診断候補。ただし同じ外部window上でthreshold sweepしており、標準採用しない。次は `loss_exit30` などをpre-registerして追加chronologyへ再探索なし適用する。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_quantile_exit_timing_sensitivity.py`
- Added test:
  - `tests/test_entry_ev_quantile_exit_timing_sensitivity.py`
- Holding-shrink / high-threshold runs:
  - `data/reports/backtests/20260701_234630_20260702_entry_ev_external_hybrid_exit_timing_sensitivity_s1/`
  - `data/reports/backtests/20260701_234729_20260702_entry_ev_external_hgb_exit_timing_sensitivity_s1/`
- Low-threshold runs:
  - `data/reports/backtests/20260701_234912_20260702_entry_ev_external_hybrid_exit_threshold_low_s1/`
  - `data/reports/backtests/20260701_235003_20260702_entry_ev_external_hgb_exit_threshold_low_s1/`
- Loss-exit threshold sweeps:
  - `data/reports/backtests/20260701_235108_20260702_entry_ev_external_hgb_loss_exit_threshold_sweep_s1/`
  - `data/reports/backtests/20260701_235146_20260702_entry_ev_external_hybrid_loss_exit_threshold_sweep_s1/`

## Method

対象branch:

- HGB external: 00269 pre-block exit-regret selector score
- Hybrid 2025-09..12: 00273 base executable pre-block selector score

Common settings:

- candidates: q99/q95 `sg95/rank90/floor5/side_regime_session_month`
- holding: `pred_mlp_*_exit_event_minutes`
- `max_predicted_hold_minutes=720`
- `profit_multiplier=1.0`
- `loss_multiplier=1.2`
- admission diagnostic: `min_role_trades=4`, `min_month_trades=1`, `max_side_trade_share=0.95`

Tested exit timing controls:

- holding shrink by `pred_*_exit_event_prob_0` / `pred_*_exit_event_prob_2`
- dynamic exit threshold by time-exit probability
- dynamic exit threshold by loss-first probability

## Holding Shrink

Hybrid base executable selector:

| candidate | variant | total pnl | worst month | trades |
|---|---|---:|---:|---:|
| q95 | base | `-12.1040` | `-26.7600` | `4` |
| q95 | time_shrink25 | `-8.8880` | `-24.4680` | `4` |
| q95 | loss_shrink75 | `-9.5150` | `-15.4560` | `4` |
| q99 | base | `-27.4800` | `-26.7600` | `2` |
| q99 | loss_shrink75 | `-16.1760` | `-15.4560` | `2` |

HGB external selector:

| candidate | variant | total pnl | worst month | trades |
|---|---|---:|---:|---:|
| q99 | base | `-9.5756` | `-56.1766` | `35` |
| q99 | both_shrink25 | `-8.6036` | `-56.1766` | `35` |
| q95 | base | `-48.2026` | `-55.4548` | `75` |
| q95 | both_shrink25 | `-47.2306` | `-55.4548` | `75` |

Reading:

- shrinkはhybrid 2025-12の大きなshort lossを早めに切り、損失幅を縮める。
- HGBでは最大負け月をほぼ変えないため、単独では不十分。
- high threshold dynamic exit `0.75/0.90` は実行経路を変えなかった。

## Low Loss-First Exit Threshold

HGB loss-first exit threshold sweep:

| candidate | variant | selector pass | total pnl | role min | month min | trades |
|---|---|---|---:|---:|---:|---:|
| q95 | loss_exit20 | true | `+54.0206` | `+2.6780` | `+2.6780` | `233` |
| q95 | loss_exit25 | true | `+37.9012` | `+2.6780` | `+2.6780` | `170` |
| q95 | loss_exit30 | false | `+35.2568` | `+2.6780` | `-0.0622` | `133` |
| q99 | loss_exit20 | false | `+28.4722` | `-0.2736` | `-4.2762` | `73` |
| q99 | base | false | `-9.5756` | `-36.1556` | `-56.1766` | `35` |

Hybrid loss-first exit threshold sweep:

| candidate | variant | selector pass | total pnl | role min | month min | trades |
|---|---|---|---:|---:|---:|---:|
| q95 | loss_exit35 | false | `+19.9900` | `+19.9900` | `-0.7200` | `6` |
| q95 | loss_exit45 | false | `+11.5000` | `+11.5000` | `-3.1560` | `5` |
| q95 | loss_exit30 | false | `+9.2740` | `+9.2740` | `-4.1460` | `8` |
| q95 | loss_exit20 | false | `-0.3140` | `-0.3140` | `-4.1460` | `10` |
| q95 | base | false | `-12.1040` | `-12.1040` | `-26.7600` | `4` |

Reading:

- HGBでは `0.20..0.25` が強く、hybridでは `0.35` 近辺が良い。
- これは低閾値dynamic exitに実効性がある一方で、absolute probability thresholdのscale driftが残ることを示す。

## Combined View

HGB + hybridのmonthly metricsを同じvariant/candidateで統合した。

| candidate | variant | total pnl | role min | positive roles | month min | trades | max DD |
|---|---|---:|---:|---:|---:|---:|---:|
| q95 | loss_exit30 | `+44.5308` | `+2.6780` | `3/3` | `-4.1460` | `141` | `16.4086` |
| q95 | loss_exit35 | `+23.8116` | `+1.1436` | `3/3` | `-5.5142` | `122` | `25.1408` |
| q95 | loss_exit20 | `+53.7066` | `-0.3140` | `2/3` | `-4.1460` | `243` | `7.0560` |
| q95 | loss_exit25 | `+37.5872` | `-0.3140` | `2/3` | `-4.1460` | `180` | `7.8036` |
| q95 | base | `-60.3066` | `-72.0826` | `1/3` | `-55.4548` | `79` | `74.7678` |

For q95 + `loss_exit30`, month detail:

| role | month | pnl | trades |
|---|---|---:|---:|
| hgb2024_0306 | 2024-03 | `+7.0122` | `30` |
| hgb2024_0306 | 2024-04 | `+23.0122` | `30` |
| hgb2024_0306 | 2024-05 | `-0.0622` | `23` |
| hgb2024_0306 | 2024-06 | `+2.6166` | `20` |
| hgb2025_08 | 2025-08 | `+2.6780` | `30` |
| hybrid2025_0912 | 2025-09 | `0.0000` | `0` |
| hybrid2025_0912 | 2025-10 | `+14.1400` | `5` |
| hybrid2025_0912 | 2025-11 | `-0.7200` | `1` |
| hybrid2025_0912 | 2025-12 | `-4.1460` | `2` |

Reading:

- `loss_exit30` は全role positiveで、baseの大きなtailを大幅に圧縮する。
- まだactive losing monthが残るため、標準policy gateは通さない。
- q95側がq99より良い。entry rowsを増やしても、低loss-first exitで尾を短くできるなら、q95の方がrisk-adjustedには有望。

## Decision

Accepted:

- exit timing sensitivity replay infrastructure
- `loss_first_exit_threshold` を低めに置くdynamic exitを有力診断候補として保持
- q95 + `loss_exit30` を追加chronology用のpre-registered candidate候補にする

Rejected:

- HGB単体で通った `loss_exit20/25` を標準採用すること
- 同じ外部window上のthreshold sweep結果をそのままpolicy化すること
- high threshold `0.75/0.90` dynamic exitを有効候補として扱うこと
- holding shrink単独でexit-capture failureが解けたと判断すること

Standard policy remains NoTrade.

## Next

1. q95 + `loss_exit30` を追加chronologyへ再探索なしで固定適用する。
2. absolute probability thresholdではなく、対象月以前のvalidation分布に基づくloss-first quantile / calibrated thresholdへ置き換える。
3. `loss_exit30` の改善が「早期決済」なのか「早期決済後の追加entry機会」なのか、trade deltaで分解する。
4. hybridの2025-11/12小損失を静的blacklistにせず、exit-risk calibrationまたはmonth-independent supportで扱う。

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_quantile_exit_timing_sensitivity.py tests/test_entry_ev_quantile_exit_timing_sensitivity.py`: OK
- `python3 -m unittest tests.test_entry_ev_quantile_exit_timing_sensitivity`: OK
- hybrid holding-shrink/high-threshold replay: OK
- HGB holding-shrink/high-threshold replay: OK
- hybrid low-threshold replay: OK
- HGB low-threshold replay: OK
- HGB loss-exit threshold sweep: OK
- hybrid loss-exit threshold sweep: OK
