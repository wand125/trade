# Holding Error Target Diagnostics

日時: 2026-06-29 20:54 JST
更新日時: 2026-06-29 20:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00168` でcontext hard exclusionが標準採用に足りなかったため、次の教師候補として `holding_error_minutes`, `oracle_holding_gap_minutes`, `exit_regret` を分解した。

結論は、`hold_extension` は頻度が高いが損失signalではない。一方、`oracle_holding_gap_minutes < -30` かつ `exit_regret >= 5` の `exit_shortening_target` は強く損失に寄る。risk5では `should_exit_earlier` が141 tradesで `-1301.9486`、平均 `-9.2337`。`near_correct` は `+315.8636`、`should_hold_longer` は `+1340.9258`。次の教師は「もっと持つべきだった」ではなく、「早く手放すべきだった」をまず分類・校正する。

## Implementation

追加:

- `scripts/experiments/holding_error_target_diagnostics.py`
  - `trade_delta_rows.csv`, `enriched_trades.csv`, `selected_trades.csv` 系を読む。
  - `--pnl-source base|candidate|auto` でbase/candidate側の存在行だけに絞る。
  - `--case-label` でrisk0/risk5などの表示ラベルを明示できる。
  - `exit_shortening_target = oracle_holding_gap_minutes <= -30 and exit_regret >= 5`
  - `hold_extension_target = oracle_holding_gap_minutes >= 30 and exit_regret >= 5`
  - `pred_minus_oracle_holding_minutes = holding_error_minutes - oracle_holding_gap_minutes` を復元する。
  - 月、方向、regime、session、bucket別summaryとwalk-forward context profileを出す。
- `tests/test_holding_error_target_diagnostics.py`
  - exit-shortening / hold-extensionの符号分解。
  - base/candidate片側に存在しないdelta行の除外。
  - walk-forward profileがprior月だけを使うこと。

## Data

入力:

- `data/reports/backtests/20260629_075516_fixed_highcost_risk5_vs_risk0_wf_examples/trade_delta_rows.csv`

対象:

- base = `risk0`
- candidate = `risk5`
- months: `2024-11` .. `2025-05`
- thresholds: `min_abs_regret=5.0`, `min_abs_gap_minutes=30.0`

## Overall

| policy | rows | total pnl | avg pnl | exit-shortening rate | hold-extension rate | mismatch rate | exit regret mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| risk0 | `628` | `325.0954` | `0.5177` | `0.2102` | `0.6656` | `0.8758` | `22.8103` |
| risk5 | `607` | `354.8408` | `0.5846` | `0.2142` | `0.6590` | `0.8731` | `22.8779` |

`hold_extension` は6割以上で出るが、頻度が高すぎてそのままrisk targetにすると「良い利益機会も削る」可能性が高い。

## Risk5 Gap Split

`oracle_holding_gap_minutes` を3分類した。

| gap side | trades | total pnl | avg pnl | exit regret mean | pred-minus-oracle mean | large loss rate |
|---|---:|---:|---:|---:|---:|---:|
| should exit earlier | `141` | `-1301.9486` | `-9.2337` | `16.5986` | `544.6843` | `0.2270` |
| near correct | `50` | `315.8636` | `6.3173` | `6.2852` | `231.5543` | `0.0000` |
| should hold longer | `416` | `1340.9258` | `3.2234` | `27.0006` | `-326.4777` | `0.0288` |

`should_exit_earlier` はlong/short両方で悪い。

| direction | gap side | trades | total pnl | avg pnl |
|---|---|---:|---:|---:|
| long | should exit earlier | `71` | `-714.0862` | `-10.0576` |
| short | should exit earlier | `70` | `-587.8624` | `-8.3980` |
| long | near correct | `24` | `153.9568` | `6.4149` |
| short | near correct | `26` | `161.9068` | `6.2272` |
| long | should hold longer | `239` | `794.9088` | `3.3260` |
| short | should hold longer | `177` | `546.0170` | `3.0848` |

## Correlation

| feature | corr adjusted pnl | corr exit regret |
|---|---:|---:|
| exit_regret | `-0.1475` | n/a |
| holding_error_minutes | `-0.0971` | `0.1865` |
| oracle_holding_gap_minutes | `0.1734` | `0.4746` |
| pred_minus_oracle_holding_minutes | `-0.2120` | `-0.3929` |

`pred_minus_oracle_holding_minutes` が正に大きいほど、予測保有がoracleより長すぎる。これは損益と負相関で、exit-shortening targetの補助特徴として有望。

## Bad Contexts

risk5の悪いcontext上位:

| direction | combined regime | session | trades | total pnl | avg pnl | exit-shortening rate | hold-extension rate |
|---|---|---|---:|---:|---:|---:|---:|
| long | down_low_vol | london | `14` | `-189.1058` | `-13.5076` | `0.6429` | `0.1429` |
| short | up_normal_vol | asia | `28` | `-106.2852` | `-3.7959` | `0.2857` | `0.5714` |
| short | range_normal_vol | rollover | `6` | `-90.0972` | `-15.0162` | `0.5000` | `0.5000` |
| short | range_low_vol | asia | `18` | `-40.3564` | `-2.2420` | `0.2222` | `0.5000` |
| short | up_normal_vol | rollover | `12` | `-31.1226` | `-2.5936` | `0.3333` | `0.5833` |

ただし、walk-forward context profileではpriorで良かったcontextがholdoutで負に反転する例が多い。context hard ruleではなく、`exit_shortening_target` を分類・校正してsoft riskにする。

## Judgment

- `hold_extension_target` は利益機会も多く含むので、最初のrisk targetにはしない。
- `exit_shortening_target` は大きな損失bucketを明確に分離するため、本流の次ターゲットにする。
- 予測featureとしては `pred_minus_oracle_holding_minutes` が有望。ただしoracleそのものは未来情報なので、live predictionでは直接使わず、モデルが予測するtargetまたはOOF-derived riskとして使う。
- 次は selected trade failure / stateful risk 系へ `exit_shortening_high` targetを追加し、chronological OOFでAUCとpolicy接続を確認する。

## Artifacts

- risk0 diagnostics: `data/reports/backtests/20260629_115348_holding_error_target_fixed_highcost_risk0_final_2024_11_2025_05/`
- risk5 diagnostics: `data/reports/backtests/20260629_115348_holding_error_target_fixed_highcost_risk5_final_2024_11_2025_05/`

## Verification

- `python3 -m unittest tests.test_holding_error_target_diagnostics`: OK, 3 tests
- `python3 -m py_compile scripts/experiments/holding_error_target_diagnostics.py`: OK
