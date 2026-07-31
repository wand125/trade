# Model Trade Delta Drift Stability

日時: 2026-06-29 11:01 JST
更新日時: 2026-06-29 11:01 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00131` ではguard top候補のgroup driftを確認した。ただし1つの候補比較だけでは、その反転groupが偶然か、別候補でも繰り返す弱点かがわからない。

今回は複数のpreflight runを横断し、validation-positive / holdout-negativeの反転groupが繰り返すかを集計する。

## 実装

`model-trade-delta-drift-stability` を追加した。

入力:

- `--preflight-runs`

出力:

- `flip_stability_pnl.csv`
- `flip_stability_stateful.csv`
- `summary.json`

各groupについて以下を集計する。

- `flip_comparison_count`
- `flip_comparison_share`
- `validation_sum_total`
- `holdout_sum_total`
- `holdout_minus_validation_sum`
- `all_comparisons_flip`

## 実データ確認

対象preflight:

- guard top: `data/reports/backtests/20260629_015420_guard_fixed_entry_side_preflight_drift/`
- stack0: `data/reports/backtests/20260629_015839_stack0_validation_smoke_preflight_drift/`

```bash
python3 -m trade_data.backtest model-trade-delta-drift-stability \
  --preflight-runs data/reports/backtests/20260629_015420_guard_fixed_entry_side_preflight_drift,data/reports/backtests/20260629_015839_stack0_validation_smoke_preflight_drift \
  --label guard_stack0_drift_stability
```

summary:

- PnL common flip groups: `3`
- stateful common flip groups: `6`

通常PnLの共通flip:

| delta status | side | regime | validation total | holdout total | holdout - validation |
|---|---|---|---:|---:|---:|
| only_candidate | long | down_low_vol | `+223.8686` | `-159.6508` | `-383.5194` |
| only_candidate | short | down_normal_vol | `+52.0400` | `-101.0994` | `-153.1394` |
| only_candidate | short | up_normal_vol | `+49.9340` | `-36.5278` | `-86.4618` |

stateful netの共通flip:

| delta status | side | regime | validation total | holdout total | holdout - validation |
|---|---|---|---:|---:|---:|
| common | short | range_normal_vol | `+499.8912` | `-300.2620` | `-800.1532` |
| only_candidate | long | down_low_vol | `+165.7616` | `-190.0178` | `-355.7794` |
| only_candidate | short | down_normal_vol | `+52.0400` | `-239.2214` | `-291.2614` |
| only_candidate | long | up_low_vol | `+103.1506` | `-151.4118` | `-254.5624` |
| only_candidate | short | up_normal_vol | `+53.3594` | `-141.4038` | `-194.7632` |
| common | long | up_normal_vol | `+32.7230` | `-9.9444` | `-42.6674` |

## 判断

guard top候補だけでなく、stack0候補でも `only_candidate long down_low_vol` と `only_candidate short down_normal/up_normal_vol` が反転した。これは局所hard blockの根拠ではなく、候補が追加する取引のregime driftとして扱う。

次にやること:

- 共通flip groupの月別supportを確認する。
- 予測時点で見える特徴だけで `candidate added trade risk` を表現できるか確認する。
- hard blockではなく、OOF downside / stateful opportunity-cost targetの特徴量または診断列として戻す。

## Artifacts

- drift stability: `data/reports/backtests/20260629_020059_guard_stack0_drift_stability/`
- guard top preflight: `data/reports/backtests/20260629_015420_guard_fixed_entry_side_preflight_drift/`
- stack0 preflight: `data/reports/backtests/20260629_015839_stack0_validation_smoke_preflight_drift/`

## Verification

- targeted drift stability unit test: OK
- real drift stability run: OK
- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: OK, 77 tests
- `git diff --check`: OK
