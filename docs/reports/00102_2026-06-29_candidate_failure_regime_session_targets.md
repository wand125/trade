# Candidate Failure Regime Session Targets

日時: 2026-06-29 06:04 JST
更新日時: 2026-06-29 06:04 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00101` の次作業として、normal-vol / time-sessionをruleで直接減点するのではなく、候補entry行に対する失敗targetとして教師化できるかを確認した。

既存の `oof-candidate-failure-model` は `large_adverse` のみだったため、session/regime別の選択失敗を表す分類targetを追加した。

## 実装

`oof-candidate-failure-model` の候補targetを拡張した。

- `large_adverse`: side別 `max_adverse_pnl <= -large_adverse_threshold`
- `large_loss`: side別 `best_adjusted_pnl <= -large_loss_threshold`
- `wrong_side`: opposite sideの `best_adjusted_pnl` が candidate sideを上回る
- `range_normal_vol_selected_failure`: `combined_regime=range_normal_vol` かつ side別 `best_adjusted_pnl <= 0`
- `normal_vol_selected_failure`: `combined_regime` が `*_normal_vol` かつ side別 `best_adjusted_pnl <= 0`
- `time_session_selected_failure`: `session_regime in {rollover, ny_late}` かつ side別 `best_adjusted_pnl <= 0`
- `any_failure`: 上記の合成

互換性のため、CLI defaultは従来通り `large_adverse` のままにした。新targetは `--failure-targets` で明示して使う。

## OOF 診断

validation months:

- `2024-07`
- `2024-09`
- `2024-11`
- `2025-01`

candidate条件:

- entry threshold: `12`
- long offset: `0`
- short offset: `6`
- side margin: `5`
- min entry rank: `0.5`

`large_loss_threshold=10` ではcandidate条件通過行の陽性がゼロだったため、`large_loss_threshold=0` も確認した。

| target | prevalence | predicted mean | bias | brier | AUC |
|---|---:|---:|---:|---:|---:|
| `large_loss` (`threshold=0`) | `0.0152` | `0.0155` | `0.0003` | `0.0152` | `0.4730` |
| `wrong_side` | `0.4088` | `0.4003` | `-0.0084` | `0.2668` | `0.4425` |
| `range_normal_vol_selected_failure` | `0.0033` | `0.0030` | `-0.0003` | `0.0033` | `0.7523` |
| `normal_vol_selected_failure` | `0.0067` | `0.0085` | `0.0018` | `0.0071` | `0.6418` |
| `time_session_selected_failure` | `0.0027` | `0.0020` | `-0.0008` | `0.0028` | `0.2607` |
| `any_failure` | `0.5409` | `0.5061` | `-0.0347` | `0.2916` | `0.3847` |

読み:

- `normal_vol_selected_failure` は薄いが、OOF AUCは `0.6418` で候補特徴としては試す価値がある。
- `range_normal_vol_selected_failure` はAUCだけ見ると高いが、prevalence `0.0033` で非常に疎。hard gateや大きなriskには向かない。
- `wrong_side`, `time_session_selected_failure`, `any_failure` は逆相関寄りで、現状の分類targetとしては使わない。
- `large_loss <= -10` は陽性ゼロ。candidateの `best_adjusted_pnl` を使う限り、強いloss thresholdは教師として成立しない。

## Validation Policy 接続

`normal_vol_selected_failure` をrisk columnとして `timed_ev` へ接続した。

固定条件:

- policy: `timed_ev`
- entry threshold: `12`
- long offset: `0`
- short offset: `6`
- side margin: `5`
- min entry rank: `0.5`
- holding: `pred_*_exit_event_time_bin_expected_minutes`
- max hold: `480`
- side EV penalty baseline: `short:down_low_vol:5`, `short:up_low_vol:10`, `short:range_low_vol:5`
- profit/loss: `1.0 / 1.20`

Base validation:

| risk | min pnl | sum pnl | min trades | max DD | min dir/session | min combined | min dir/combined |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0` | `145.5682` | `673.9120` | `66` | `92.0350` | `-23.8298` | `-40.6828` | `-40.6828` |
| `5` | `145.5682` | `677.2690` | `66` | `92.0350` | `-23.8298` | `-51.4238` | `-51.4238` |
| `10` | `147.5388` | `680.3234` | `65` | `92.0350` | `-23.4912` | `-55.1998` | `-55.1998` |
| `20` | `145.0404` | `677.7122` | `65` | `92.0350` | `-23.4912` | `-33.2110` | `-36.5880` |

High cost validation (`spread=0.2`, `slippage=0.1`, `delay=1`):

| risk | min pnl | sum pnl | min trades | max DD | min dir/session | min combined | min dir/combined |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0` | `120.5842` | `562.8784` | `66` | `97.1906` | `-26.7204` | `-53.0622` | `-53.0622` |
| `5` | `120.5842` | `567.1664` | `66` | `97.1906` | `-26.7204` | `-68.2646` | `-68.2646` |
| `10` | `121.5598` | `571.8670` | `65` | `97.1906` | `-26.7204` | `-68.4346` | `-68.4346` |
| `20` | `124.4280` | `567.4872` | `65` | `97.1906` | `-26.7204` | `-48.0382` | `-48.0382` |

Selectionでは `risk=20` がstress score topになった。ただし改善幅は小さく、fold別group損益も完全には安定しない。

## Holdout 反証

validationで選ばれた `normal_vol_selected_failure risk=20` を、2024-12 / 2025-02 / 2025-03 / 2025-04 holdoutへ固定適用した。

Base holdout:

| month | risk | adjusted pnl | trades | max DD | min dir/session | min combined | min dir/combined |
|---|---:|---:|---:|---:|---:|---:|---:|
| `2024-12` | `0` | `7.2314` | `73` | `117.9006` | `-38.8724` | `-28.1110` | `-28.1110` |
| `2024-12` | `20` | `-16.2116` | `73` | `117.9006` | `-36.8080` | `-28.9664` | `-28.9664` |
| `2025-02` | `0` | `101.3432` | `72` | `105.1896` | `-34.1916` | `-6.2814` | `-32.8306` |
| `2025-02` | `20` | `87.2912` | `70` | `124.5086` | `-21.7236` | `-19.0476` | `-26.3844` |
| `2025-03` | `0` | `10.1446` | `83` | `87.8826` | `-72.7322` | `-17.4046` | `-59.2926` |
| `2025-03` | `20` | `-24.8212` | `83` | `89.7304` | `-72.7322` | `-44.4036` | `-59.2926` |
| `2025-04` | `0` | `-223.7292` | `86` | `474.6194` | `-217.3936` | `-256.4940` | `-145.5636` |
| `2025-04` | `20` | `-230.0058` | `85` | `516.4888` | `-187.2460` | `-190.8788` | `-171.2464` |

Summary:

| risk | min pnl | sum pnl | min trades | max DD | min dir/session | min combined | min dir/combined |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0` | `-223.7292` | `-105.0100` | `72` | `474.6194` | `-217.3936` | `-256.4940` | `-145.5636` |
| `20` | `-230.0058` | `-183.7474` | `70` | `516.4888` | `-187.2460` | `-190.8788` | `-171.2464` |

## 判断

`normal_vol_selected_failure` riskは標準採用しない。

理由:

- validationでは小改善したが、holdout baseで `risk=20` が4ヶ月中4ヶ月すべてadjusted pnlを悪化させた。
- 2025-04の `combined_regime` lossは浅くなるが、direction-combined lossとmax drawdownが悪化する。壊れ方を別の場所へ移しただけ。
- `wrong_side` と `time_session_selected_failure` はOOF AUCが逆相関寄りで、現状の特徴量/target定義ではriskに使えない。
- sparse targetのAUCだけを根拠にentry scoreへ直結すると、validation過適合になりやすい。

次の方針:

- candidate failure target拡張は診断基盤として残す。
- `normal_vol_selected_failure` はhard/risk policyへ直結しない。
- 次は分類probabilityを直接penaltyにするのではなく、candidate rowの連続的な `realizable PnL / lower quantile / calibrated downside` を、月別prevalence shift込みで扱う。
- 2025-04のnormal-vol failureは、entry/side EVの過大評価とregime driftとして扱い、単独targetで救う方向へ寄せない。

## Artifacts

- OOF target diagnostics: `data/reports/modeling/20260628_205823_candidate_failure_regime_session_targets_loss0/`
- holdout apply: `data/reports/modeling/20260628_210330_candidate_failure_regime_session_targets_loss0_holdout_apply/`
- validation base sweeps: `data/reports/backtests/candidate_failure_normal_vol_risk_validation/`
- validation high cost sweeps: `data/reports/backtests/candidate_failure_normal_vol_risk_validation_highcost/`
- selection: `data/reports/backtests/candidate_failure_normal_vol_risk_selection/20260628_210153_model_candidate_selection/`
- holdout base sweeps: `data/reports/backtests/candidate_failure_normal_vol_risk_holdout_base/`
- summaries:
  - `data/reports/backtests/candidate_failure_normal_vol_risk_validation_base_summary.csv`
  - `data/reports/backtests/candidate_failure_normal_vol_risk_validation_highcost_summary.csv`
  - `data/reports/backtests/candidate_failure_normal_vol_risk_holdout_base_summary.csv`

## Verification

- `python3 -m py_compile src/trade_data/meta_model.py tests/test_meta_model.py`: OK
- `python3 -m unittest tests.test_meta_model.MetaModelTests.test_candidate_failure_model_adds_probability_and_risk_columns`: OK
- `python3 -m unittest tests.test_meta_model`: OK, 30 tests
- `python3 -m trade_data.meta_model oof-candidate-failure-model`: OK
- `python3 -m trade_data.backtest model-sweep`: OK for validation base/high cost and holdout base
- `python3 -m trade_data.backtest model-candidate-selection`: OK
