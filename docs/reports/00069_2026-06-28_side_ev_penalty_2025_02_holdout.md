# Side EV Penalty 2025-02 Holdout

日時: 2026-06-28 22:03 JST
更新日時: 2026-06-28 22:03 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

2024-12で選んだ `long:session_regime=ny_late:15` side EV penalty候補を、同じtrain/valid splitのままtest月だけ `2025-02` に差し替えて固定評価した。

2025-02ではbaseline、PnL top、risk topの3候補すべてがNoTrade `0` を上回った。standard条件ではbaseline `+81.8334`, risk top `+79.4018`, PnL top `+59.1854`。高コスト + delay 1でもbaseline `+21.3628`, risk top `+19.5898` はプラスに残った。

ただし、2025-02ではbaselineがrisk topをわずかに上回る。したがって `long:ny_late:15` side EV penaltyは「2024-12の損失を大きく縮め、2025-02でも壊れない」候補だが、「標準採用すべき改善」とはまだ言えない。

## Scope

これはfresh blindではなく、既存研究で過去に扱ったことのある `2025-02` を、現在のHGB entry/side + MLP exit hybrid構成で再評価した追加固定testである。2024-12をtrainに足さず、既存hybridと同じtrain/valid splitを維持した。

## Data And Models

- dataset added: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/xauusd_m1_2025-02_h24_edge15.parquet`
- HGB run: `experiments/20260628_130038_policy_combined_side_exit_test_2025_02/`
- shared MLP run: `experiments/20260628_130102_shared_mlp_hgb_split_test_2025_02/`
- hybrid predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2025_02.parquet`
- metadata: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/metadata_test_2025_02.json`

Split:

- train: `2023-01` ... `2024-06`, `2024-08`, `2024-10`
- validation: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- test: `2025-02`
- purging: label overlap purge enabled, embargo `24h`
- evaluation multipliers: profit `1.0`, loss `1.20`

## Fixed Test Results

| candidate | side EV penalty | min rank | adjusted pnl | raw pnl | trades | long | short | profit factor | max DD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | none | `0.5` | `+81.8334` | `121.7120` | `118` | `12` | `106` | `1.3420` | `99.3504` |
| PnL top | `long:ny_late:15` | `0.0` | `+59.1854` | `101.3700` | `111` | `8` | `103` | `1.2338` | `123.5044` |
| risk top | `long:ny_late:15` | `0.5` | `+79.4018` | `116.5910` | `113` | `8` | `105` | `1.3558` | `113.6334` |

Diagnostics:

| candidate | direction error | EV over realized mean | worst direction/combined | worst group pnl |
|---|---:|---:|---|---:|
| baseline | `0.4407` | `23.1866` | `short:up_low_vol` | `-36.2828` |
| PnL top | `0.2793` | `22.4326` | `short:up_low_vol` | `-34.9144` |
| risk top | `0.4336` | `23.3695` | `short:up_low_vol` | `-36.2828` |

## Cost Stress

| scenario | baseline adj pnl | PnL top adj pnl | risk top adj pnl |
|---|---:|---:|---:|
| standard | `+81.8334` | `+59.1854` | `+79.4018` |
| delay 1, no cost | `+73.3642` | `+30.2796` | `+69.3512` |
| spread 0.1 / slippage 0.05 / delay 0 | `+55.8500` | `+34.7076` | `+54.5384` |
| spread 0.2 / slippage 0.1 / delay 0 | `+29.6348` | `+10.0576` | `+29.4652` |
| spread 0.2 / slippage 0.1 / delay 1 | `+21.3628` | `-18.7136` | `+19.5898` |

Worst stress row:

| candidate | adjusted pnl | profit factor | max DD |
|---|---:|---:|---:|
| baseline | `+21.3628` | `1.0792` | `102.2548` |
| PnL top | `-18.7136` | `0.9370` | `130.6348` |
| risk top | `+19.5898` | `1.0783` | `117.5448` |

## Findings

- 2025-02ではbaselineもrisk topもNoTradeと高コストstressを上回った。これはhybrid構成が全ての月で壊れる状態ではないことを示す。
- `long:ny_late:15` risk topは2024-12の損失を `-54.6032 -> -5.4938` へ縮め、2025-02でも `+79.4018` を維持した。
- 一方、2025-02ではbaselineがstandard/high-costのほぼ全条件でrisk topをわずかに上回る。side EV penaltyを標準採用すると、良い月の取り分を少し削る可能性がある。
- PnL topはdirection errorを大きく下げるが、drawdownが大きく、高コスト + delay 1で `-18.7136` まで落ちるため、risk topより弱い。
- 2025-02の弱点は引き続きshort偏重で、baselineはshort trade share `0.8983`, risk topは `0.9292`。worst groupは `short:up_low_vol`。

## Decision

- `long:ny_late:15` risk topは「棄却」ではなく「保留」。2024-12への防御効果と2025-02の非破綻は確認できた。
- ただしbaselineを上回る汎化改善ではないため、標準policyへは昇格しない。
- 次は `short:up_low_vol` / short偏重のriskを、hard blockではなくside/regime EV penaltyまたはsupport-aware risk targetで扱う。
- 次のvalidation設計では、2024-12と2025-02の片方に過適合しないよう、複数holdoutを同時に見るcandidate rankingへ進む。

## Artifacts

- fixed 2025-02 tests: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_2025_02/`
- cost stress 2025-02: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2025_02/`
- baseline cost stress: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2025_02/20260628_130233_model_cost_sensitivity_2025-02/`
- PnL top cost stress: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2025_02/20260628_130233_model_cost_sensitivity_2025-02_1/`
- risk top cost stress: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2025_02/20260628_130233_model_cost_sensitivity_2025-02_2/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`
- `git diff --check`
