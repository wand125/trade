# Drift Stability Monthly Support

日時: 2026-06-29 11:07 JST
更新日時: 2026-06-29 11:07 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00132` で共通flip groupは見つかったが、月別supportが薄いなら過解釈になる。

今回はdrift stabilityの共通flip groupを、preflight configに残っている元delta runへ戻し、月別group CSVからsupportを確認できるようにする。

## 実装

`model-trade-delta-drift-stability` に以下を追加した。

- `flip_stability_pnl_monthly_support.csv`
- `flip_stability_pnl_monthly_support_summary.csv`
- `flip_stability_stateful_monthly_support.csv`
- `flip_stability_stateful_monthly_support_summary.csv`

preflight runの `config.json` にある `expanded_validation_deltas` / `expanded_holdout_deltas` を読み、元の `group_by_month_status_direction_combined_regime.csv` と `group_by_blocking_candidate_month_status_direction_combined_regime.csv` を月別に再集計する。

## 実データ確認

対象は `00132` と同じ2つのpreflight。

```bash
python3 -m trade_data.backtest model-trade-delta-drift-stability \
  --preflight-runs data/reports/backtests/20260629_015420_guard_fixed_entry_side_preflight_drift,data/reports/backtests/20260629_015839_stack0_validation_smoke_preflight_drift \
  --label guard_stack0_drift_support
```

summary:

- PnL common flip groups: `3`
- stateful common flip groups: `6`
- PnL monthly support rows: `49`
- stateful monthly support rows: `99`

主な通常PnL support:

| comparison | split | group | months | rows | sum | min month | negative months | positive months |
|---|---|---|---:|---:|---:|---:|---:|---:|
| guard top | validation | only_candidate long down_low_vol | 4 | 46 | `+84.3218` | `-7.3532` | 2 | 6 |
| guard top | holdout | only_candidate long down_low_vol | 3 | 24 | `-93.4838` | `-55.5182` | 2 | 4 |
| stack0 | validation | only_candidate long down_low_vol | 3 | 29 | `+139.5468` | `+29.4136` | 0 | 3 |
| stack0 | holdout | only_candidate long down_low_vol | 2 | 23 | `-66.1670` | `-65.4130` | 2 | 0 |
| guard top | validation | only_candidate short down_normal_vol | 1 | 2 | `+25.4090` | `+12.0390` | 0 | 2 |
| guard top | holdout | only_candidate short down_normal_vol | 2 | 8 | `-91.0014` | `-32.0280` | 4 | 0 |
| stack0 | validation | only_candidate short down_normal_vol | 1 | 2 | `+26.6310` | `+26.6310` | 0 | 1 |
| stack0 | holdout | only_candidate short down_normal_vol | 2 | 2 | `-10.0980` | `-6.9480` | 2 | 0 |

主なstateful support:

| comparison | split | group | months | rows | sum | min month | negative months | positive months |
|---|---|---|---:|---:|---:|---:|---:|---:|
| guard top | validation | only_candidate long down_low_vol | 4 | 8 | `+107.4676` | `-14.4392` | 2 | 6 |
| guard top | holdout | only_candidate long down_low_vol | 3 | 6 | `-136.4816` | `-67.6918` | 4 | 2 |
| stack0 | validation | only_candidate long down_low_vol | 3 | 3 | `+58.2940` | `-19.7396` | 1 | 2 |
| stack0 | holdout | only_candidate long down_low_vol | 2 | 2 | `-53.5362` | `-40.0522` | 2 | 0 |
| guard top | validation | only_candidate long up_low_vol | 4 | 8 | `+35.6784` | `-32.4914` | 2 | 6 |
| guard top | holdout | only_candidate long up_low_vol | 4 | 8 | `-125.5044` | `-144.5750` | 2 | 6 |
| stack0 | validation | only_candidate long up_low_vol | 4 | 4 | `+67.4722` | `+0.9360` | 0 | 4 |
| stack0 | holdout | only_candidate long up_low_vol | 2 | 2 | `-25.9074` | `-56.4254` | 1 | 1 |

## 判断

共通flip groupは単月だけの偶然ではない。一方で、validation側にも負の月が混じるため、これをそのままhard blockにすると別期間の良い取引も削る可能性が高い。

扱い:

- hard blockにはしない。
- `direction + combined_regime` を単純ruleではなく、candidate-added contextとしてOOF examplesへ結合する。
- targetは通常PnLではなく、downside / stateful opportunity-cost / replacement regret側を優先する。
- 次は予測時点で利用可能な特徴だけで、このcandidate-added文脈を表現できるか確認する。

## Artifacts

- drift support: `data/reports/backtests/20260629_020655_guard_stack0_drift_support/`
- PnL support: `data/reports/backtests/20260629_020655_guard_stack0_drift_support/flip_stability_pnl_monthly_support_summary.csv`
- stateful support: `data/reports/backtests/20260629_020655_guard_stack0_drift_support/flip_stability_stateful_monthly_support_summary.csv`

## Verification

- targeted drift stability/support unit test: OK
- real drift support run: OK
