# Entry EV Component Target Calibration

日時: 2026-07-01 00:27 JST
更新日時: 2026-07-01 00:27 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00239で分解したcomponent targetを、まず深いモデルへ進めず、低容量なbucket calibrationで診断した。
- 追加した `scripts/experiments/entry_ev_component_target_calibration.py` は `component_trade_targets.csv` を読み、target別に chronological month と role holdout の校正指標を出す。
- groupは `support_bucket + pressure_bucket`。対象targetは `direction_side_inversion_target`, `exit_capture_failure_target`, `executable_ev_overestimate_target`, `realized_loss_target`。
- chronological / role holdout の両方で相対的に残ったsignalは `executable_ev_overestimate_target` だけ。chronological mean AUC `0.6741`、role holdout mean AUC `0.6401`。
- `direction_side_inversion_target` と `exit_capture_failure_target` は同じbucketでは逆相関に近く、hard gateや単純低容量headにはしない。
- 判断: component target calibration infrastructureはaccepted。`support_bucket + pressure_bucket` だけを十分なtarget modelとは扱わない。次はEV overestimateを校正targetとして残し、direction/exitはside/context/holding/capture特徴を足して別headへ進める。

## Artifacts

- Script: `scripts/experiments/entry_ev_component_target_calibration.py`
- Test: `tests/test_entry_ev_component_target_calibration.py`
- Input:
  - `data/reports/backtests/20260630_145606_20260630_entry_ev_composite_target_decomposition_s1/component_trade_targets.csv`
- Diagnostic artifact:
  - `data/reports/backtests/20260630_153252_20260701_entry_ev_component_target_calibration_s2/`

Outputs:

```text
target_overall_summary.csv
target_group_summary.csv
target_chronological_month_metrics.csv
target_role_holdout_metrics.csv
target_calibration_metric_summary.csv
target_chronological_month_predictions.csv
target_role_holdout_predictions.csv
config.json
```

## Method

低容量診断として、各targetをbucket内target率で予測する。

```text
prediction = blended bucket target rate
fallback = train global target rate
no_prior = chronological first monthなど、train rowsがない場合
```

設定:

```text
group_columns = support_bucket, pressure_bucket
prior_strength = 5
min_group_support = 3
chronological_month = fold monthより前のtradeだけでfit
role_holdout = holdout role以外のroleだけでfit
```

これはpolicyではない。component targetが「その時点で見える粗いsupport/pressureだけでどれだけ説明できるか」を測るpreflightである。

## Overall Target Distribution

| target | rows | target rate | total pnl | target true pnl | target false pnl |
|---|---:|---:|---:|---:|---:|
| exit capture failure | `115` | `0.7130` | `+21.1508` | `-142.4728` | `+163.6236` |
| direction side inversion | `115` | `0.5739` | `+21.1508` | `-247.9762` | `+269.1270` |
| realized loss | `115` | `0.5391` | `+21.1508` | `-355.2012` | `+376.3520` |
| executable EV overestimate | `115` | `0.4870` | `+21.1508` | `-325.3432` | `+346.4940` |

target自体は損失説明に効く。特に `executable_ev_overestimate_target` と `realized_loss_target` は target true PnL が大きく負。ただし、このtargetを事前に安定予測できるかは別問題。

## Calibration Summary

| fold type | target | predicted | target rate | pred mean | brier | mean AUC | bucket share |
|---|---|---:|---:|---:|---:|---:|---:|
| chronological | direction side inversion | `58/115` | `0.5739` | `0.6259` | `0.2960` | `0.2644` | `0.3478` |
| chronological | exit capture failure | `58/115` | `0.7130` | `0.6547` | `0.2171` | `0.4457` | `0.3478` |
| chronological | executable EV overestimate | `58/115` | `0.4870` | `0.5236` | `0.2862` | `0.6741` | `0.3478` |
| chronological | realized loss | `58/115` | `0.5391` | `0.5629` | `0.2693` | `0.4819` | `0.3478` |
| role holdout | direction side inversion | `115/115` | `0.5739` | `0.6179` | `0.2940` | `0.2587` | `0.9304` |
| role holdout | exit capture failure | `115/115` | `0.7130` | `0.7295` | `0.2383` | `0.2716` | `0.9304` |
| role holdout | executable EV overestimate | `115/115` | `0.4870` | `0.3969` | `0.2676` | `0.6401` | `0.9304` |
| role holdout | realized loss | `115/115` | `0.5391` | `0.5131` | `0.2724` | `0.5009` | `0.9304` |

Important reading:

- `executable_ev_overestimate_target` は chronological と role holdout の両方でAUCが `0.64..0.67`。低容量bucketでもrank signalがある。
- `direction_side_inversion_target` はAUC `0.26` 前後で逆向き。support/pressure bucketだけでは方向反転を説明できない。
- `exit_capture_failure_target` も role holdout AUC `0.2716`。exit失敗はholding/capture/side/context特徴を足さないと分離できない。
- `realized_loss_target` はほぼrandom。lossを直接単純target化するより、EV overestimate、direction、exitへ分ける方針を維持する。

## Chronological Month Details

2024-01はpriorがないため予測不可。以降は対象月より前だけでfitした。

| target | month note | reading |
|---|---|---|
| direction side inversion | 2024-03 AUC `0.0625`, 2025-02 AUC `0.2308` | 低容量bucketは方向反転を逆に読んでいる |
| exit capture failure | 2025-02 target rate `0.8387`, pred mean `0.6589`, AUC `0.2538` | 高頻度だがrank付けできていない |
| executable EV overestimate | 2024-03 AUC `0.6875`, 2024-04 AUC `1.0000`, 2025-02 AUC `0.5091` | early foldsは小さいが、他targetより一貫して良い |
| realized loss | 2024-03 AUC `0.5417`, 2025-02 AUC `0.4042` | realized loss直接予測は弱い |

Chronological summaryの `predicted_count` は `58/115`。early monthにpriorがないためcoverageは低い。このため、今回の結果は採用判定ではなく、target別に次へ進める優先順位として扱う。

## Role Holdout Details

| target | cal2024 AUC | fresh2024 AUC | refit2025 AUC | reading |
|---|---:|---:|---:|---|
| direction side inversion | `0.4286` | `0.1250` | `0.2227` | role横断で逆向き。別特徴が必要 |
| exit capture failure | `0.4167` | `0.1500` | `0.2481` | support/pressureではexit失敗を分けられない |
| executable EV overestimate | `0.5714` | `0.8250` | `0.5238` | target別head候補として残す |
| realized loss | `0.4375` | `0.6750` | `0.3902` | freshでは見えるがrole横断では安定しない |

## Group Findings

`medium/high` groupは3 rowsしかないが、EV overestimate / exit failure / realized loss が全て `1.0000` で total `-43.1964`。ただしsupportが小さいためhard blockerにしない。

`missing/low` は81 rowsで、target rateは高いが totalは `-1.6042` とほぼflat。target false PnLは強く正で、missing supportを自動拒否すると利益も消す。

`high/extreme` は16 rowsで total `+53.4144`。exit failure rate `0.8125` でも利益が出ているため、exit targetは「改善余地」であり、単純な負例ではない。

## Decision

Accepted:

- Component target calibration script.
- Chronological month / role holdoutの低容量target診断。
- `executable_ev_overestimate_target` を優先target head / calibration feature候補として残す。
- `support_bucket + pressure_bucket` は説明特徴として残す。

Not accepted:

- `support_bucket + pressure_bucket` だけでdirection/exit/lossを判断するtarget model。
- direction/exit targetのhard gate化。
- missing supportの自動拒否。
- realized loss単独targetを主labelにすること。

Standard policy remains NoTrade.

## Next

1. `executable_ev_overestimate_target` を低容量calibration featureとして、entry ranking / selector featureへ戻す。
2. `direction_side_inversion_target` は selected side、actual best side、prior side PnL、prediction side drift、side margin/rank を足した別headで診断する。
3. `exit_capture_failure_target` は holding cap、raw/predicted exit event、oracle best holding、capture shortfallを足したexit-specific headへ進める。
4. chronological predicted coverageが低いため、component targetsをより多いwalk-forward monthsで生成する。
5. 予測headの指標はAUC/Brierだけでなく、stateful one-position backtestのNoTrade-first selectorで確認する。

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_component_target_calibration.py tests/test_entry_ev_component_target_calibration.py`: OK
- `python3 -m unittest tests.test_entry_ev_component_target_calibration`: OK
- Component target calibration diagnostic run: OK
