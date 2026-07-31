# Short Up Low Vol EV Penalty

日時: 2026-06-28 22:12 JST
更新日時: 2026-06-28 22:12 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。

## Summary

2025-02でworst groupに出ていた `short:up_low_vol` を、hard blockではなく `side_ev_penalty_rules` で直接減点する実験を行った。

結論は、`short:combined_regime=up_low_vol` の直接減点は標準policyへ採用しない。short偏重は下がるが、validationの最悪月PnLが大きく落ちる。2024-12/2025-02固定testでも、2025-02ではプラスを残す一方で2024-12を悪化させ、複数holdoutに強い改善ではなかった。

## Setup

- predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_oof.parquet`
- fixed tests:
  - `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2024_12.parquet`
  - `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2025_02.parquet`
- validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- policy: `timed_ev`
- entry threshold: `15`
- short threshold offset: `4`
- side margin: `5`
- max predicted hold: `480`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- evaluation multipliers: profit `1.0`, loss `1.20`

Rule sets:

- none
- `short:combined_regime=up_low_vol:5/10/15/20`
- `long:session_regime=ny_late:15`
- `long:session_regime=ny_late:15` + `short:combined_regime=up_low_vol:5/10/15/20`

## Validation

Base validation:

| candidate | min rank | min pnl | sum pnl | min trades | max DD | max short share | max dir/combined loss |
|---|---:|---:|---:|---:|---:|---:|---:|
| `long:ny_late:15` | `0.0` | `93.8904` | `424.0446` | `17` | `58.9488` | `0.7857` | `-59.7000` |
| `long:ny_late:15` | `0.5` | `85.7834` | `440.0672` | `16` | `51.8988` | `0.7857` | `-59.7000` |
| none | `0.5` | `81.5352` | `396.9782` | `23` | `60.0744` | `0.7097` | `-73.8224` |
| `long:ny_late:15,short:up_low_vol:10` | `0.0` | `69.8078` | `478.9268` | `25` | `74.5450` | `0.5745` | `-59.7000` |
| `long:ny_late:15,short:up_low_vol:10` | `0.5` | `63.6080` | `501.3944` | `24` | `68.6542` | `0.5745` | `-59.7000` |
| `short:up_low_vol:10` | `0.5` | `50.2796` | `443.0866` | `31` | `80.1652` | `0.5192` | `-73.8224` |

Cost-mid validation (`spread=0.1`, `slippage=0.05`, `delay=0`):

| candidate | min rank | min pnl | sum pnl | min trades | max DD | max short share |
|---|---:|---:|---:|---:|---:|---:|
| `long:ny_late:15` | `0.0` | `88.8904` | `404.6046` | `17` | `60.1488` | `0.7857` |
| `long:ny_late:15` | `0.5` | `80.9834` | `421.1472` | `16` | `53.0988` | `0.7857` |
| none | `0.5` | `76.4152` | `374.1782` | `23` | `61.6344` | `0.7097` |
| `long:ny_late:15,short:up_low_vol:10` | `0.0` | `60.8478` | `447.2868` | `25` | `77.0250` | `0.5745` |
| `long:ny_late:15,short:up_low_vol:10` | `0.5` | `55.2480` | `470.9144` | `24` | `70.7342` | `0.5745` |
| `short:up_low_vol:10` | `0.5` | `41.2216` | `408.5886` | `31` | `82.8452` | `0.5192` |

Validation上の読みは明確。`short:up_low_vol` 減点はshort shareを下げるが、最悪月PnLとdrawdownを悪化させる。sum pnlだけを見るとcomboが良く見えるが、これはshort側の取引増と月依存が強く、汎化候補としては弱い。

## Fixed Tests

| candidate | side EV penalty | min rank | month | adjusted pnl | raw pnl | trades | long | short | short share | PF | max DD |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| combo | `long:ny_late:15,short:up_low_vol:10` | `0.0` | `2024-12` | `-77.3720` | `-36.7910` | `43` | `23` | `20` | `0.4651` | `0.6822` | `123.2378` |
| combo | `long:ny_late:15,short:up_low_vol:10` | `0.0` | `2025-02` | `+28.5478` | `85.1930` | `133` | `27` | `106` | `0.7970` | `1.0840` | `101.9898` |
| combo | `long:ny_late:15,short:up_low_vol:10` | `0.5` | `2024-12` | `-79.1486` | `-40.5740` | `57` | `22` | `35` | `0.6140` | `0.6580` | `126.1048` |
| combo | `long:ny_late:15,short:up_low_vol:10` | `0.5` | `2025-02` | `+64.0924` | `117.0590` | `138` | `29` | `109` | `0.7899` | `1.2017` | `73.5174` |
| short only | `short:up_low_vol:10` | `0.5` | `2024-12` | `-134.4310` | `-84.9650` | `61` | `26` | `35` | `0.5738` | `0.5471` | `183.2702` |
| short only | `short:up_low_vol:10` | `0.5` | `2025-02` | `+66.8030` | `118.6450` | `140` | `31` | `109` | `0.7786` | `1.2148` | `76.7474` |

比較基準:

- 2024-12 baseline: `-54.6032`
- 2024-12 `long:ny_late:15` risk top: `-5.4938`
- 2025-02 baseline: `+81.8334`
- 2025-02 `long:ny_late:15` risk top: `+79.4018`

今回のcombo/short-onlyは、2025-02ではプラスを維持するが、既存baselineや `long:ny_late` risk topを上回らない。2024-12では既存候補より明確に悪い。

## Cost Stress

Representative `min_rank=0.5` candidates:

| candidate | month | scenario | adjusted pnl | PF | max DD | trades |
|---|---|---|---:|---:|---:|---:|
| combo | `2024-12` | standard | `-79.1486` | `0.6580` | `126.1048` | `57` |
| combo | `2024-12` | spread `0.1` / slippage `0.05` / delay `0` | `-92.0286` | `0.6171` | `136.5848` | `57` |
| combo | `2024-12` | spread `0.2` / slippage `0.1` / delay `0` | `-104.9364` | `0.5792` | `147.0926` | `57` |
| combo | `2025-02` | standard | `+64.0924` | `1.2017` | `73.5174` | `138` |
| combo | `2025-02` | spread `0.2` / slippage `0.1` / delay `0` | `+3.1332` | `1.0089` | `85.9938` | `138` |
| short only | `2024-12` | standard | `-134.4310` | `0.5471` | `183.2702` | `61` |
| short only | `2024-12` | spread `0.2` / slippage `0.1` / delay `0` | `-161.8988` | `0.4864` | `205.5380` | `61` |
| short only | `2025-02` | standard | `+66.8030` | `1.2148` | `76.7474` | `140` |
| short only | `2025-02` | spread `0.2` / slippage `0.1` / delay `0` | `+4.8038` | `1.0138` | `89.2238` | `140` |

Cost stressは採用判断を変えない。2025-02のプラスは高コストでほぼ消え、2024-12はさらに悪化する。

## Decision

- `short:combined_regime=up_low_vol` の直接side EV penaltyは採用しない。
- short concentrationを下げること自体は正しい診断軸だが、直接減点ではvalidation最悪月と2024-12 holdoutを壊す。
- `short:up_low_vol` は今後も失敗分析の重要groupとして残す。ただし次はpost-hocなgroup減点ではなく、support-aware target、side/regime別のcalibrated EV、または複数holdout同時rankingで扱う。
- 直近の標準候補は引き続き「採用なし」。`long:ny_late:15` risk topは保留診断候補だが、2025-02でbaselineを上回らないため標準policyではない。

## Artifacts

- base validation sweeps: `data/reports/backtests/hgb_entry_mlp_exit_short_up_low_vol_penalty_validation_base/`
- cost-mid validation sweeps: `data/reports/backtests/hgb_entry_mlp_exit_short_up_low_vol_penalty_validation_cost_mid/`
- fixed tests: `data/reports/backtests/hgb_entry_mlp_exit_short_up_low_vol_penalty_fixed_tests/`
- fixed cost stress: `data/reports/backtests/hgb_entry_mlp_exit_short_up_low_vol_penalty_fixed_cost_stress/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`
- `git diff --check`
