# Candidate Quality Component Targets

日時: 2026-06-29 02:43 JST
更新日時: 2026-06-29 02:43 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

前回の `joint_exit_adjusted_pnl` はOOF回帰指標を改善したが、timed barrier、fixed horizon、clipped bestを単一scalarへ混ぜるため、どの成分が使えていて、どの成分がpolicyを壊しているかが見えにくい。

今回はjointの各成分を個別targetとして学習できるようにし、過大評価risk penaltyとしてvalidation 4foldで比較した。

## 実装

`oof-candidate-quality-model --target-mode` に以下を追加した。

- `timed_barrier_component_adjusted_pnl`
- `fixed_horizon_component_adjusted_pnl`
- `clipped_best_adjusted_pnl`

既存の `joint_exit_adjusted_pnl` は、これらの成分を再利用して計算する形へ整理した。componentごとのtargetは、`joint_component_clip_multiple * min_adjusted_edge` でclipする。

単体テストでは、同じcandidate frameに対して以下のtargetが分離されることを確認した。

| target mode | expected target |
|---|---:|
| `timed_barrier_component_adjusted_pnl` | `[11.25, -11.25, -6.0]` |
| `fixed_horizon_component_adjusted_pnl` | `[5.0, 7.0, 8.0]` |
| `clipped_best_adjusted_pnl` | `[10.0, 15.0, 15.0]` |

## 条件

- prediction source: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_forced_targets/`
- validation months: `2024-07,2024-09,2024-11,2025-01`
- apply month generated: `2024-12`
- policy validation: profit multiplier `1.0`, loss multiplier `1.20`
- source EV columns: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- entry threshold grid: `10,12,15`
- short offset: `6`
- side margin: `5`
- risk penalty grid: `0,0.05,0.1,0.25,0.5,1,2`
- min entry rank grid: `0,0.5`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- max predicted hold minutes: `480`
- minimum trades per fold: `10`
- max forced exit rate: `0.10`

## OOF

| target | target mean | mean bias | mean MAE | mean RMSE | mean R2 | lower coverage |
|---|---:|---:|---:|---:|---:|---:|
| timed barrier component | `1.4816` | `0.7989` | `12.7850` | `13.5326` | `-0.1667` | `0.6754` |
| fixed horizon component | `1.2754` | `0.2982` | `7.9169` | `9.4811` | `-0.0895` | `0.7055` |
| clipped best component | `11.0714` | `0.0182` | `4.9377` | `5.6107` | `-0.1309` | `0.7078` |

fixed horizon componentは3成分の中ではR2が最もましだが、それでも負で、単独で汎化可能なcandidate qualityを説明しているとは言えない。clipped bestはtargetが簡単なためMAEは小さいが、実行policyのriskとして有効とは限らない。

## Validation

全componentで、validation 4foldの最良は `risk_penalty=0` だった。これはcomponent modelをpolicyに使わないbaselineであり、component riskを入れるとfold最低PnLが下がった。

| target | best no-risk min pnl | best no-risk sum pnl | best positive-risk setting | best positive-risk min pnl | best positive-risk sum pnl |
|---|---:|---:|---|---:|---:|
| timed barrier component | `82.7176` | `406.6546` | entry `12`, risk `0.05`, rank `0.5` | `62.5366` | `345.4122` |
| fixed horizon component | `82.7176` | `406.6546` | entry `15`, risk `0.05`, rank `0.5` | `43.6626` | `195.1810` |
| clipped best component | `82.7176` | `406.6546` | entry `12`, risk `0.05`, rank `0.0` | `41.7588` | `314.2650` |
| joint exit previous | `82.7176` | `406.6546` | entry `12`, risk `0.05`, rank `0.0` | `47.4988` | `296.5646` |
| forced barrier previous | `82.7176` | `406.6546` | entry `12`, risk `0.05`, rank `0.5` | `62.5366` | `359.6626` |

同じ代表spine `entry=12`, `min_entry_rank=0.5` でも、riskを上げるほどtrade数とfold最低PnLが落ちた。EV過大評価も改善せず、むしろ悪化する傾向がある。

| target | risk | min pnl | sum pnl | min trades | EV overestimate vs realized mean |
|---|---:|---:|---:|---:|---:|
| timed barrier component | `0.00` | `82.7176` | `406.6546` | `24` | `15.5226` |
| timed barrier component | `0.05` | `62.5366` | `345.4122` | `22` | `16.2400` |
| fixed horizon component | `0.00` | `82.7176` | `406.6546` | `24` | `15.5226` |
| fixed horizon component | `0.05` | `34.9142` | `280.7764` | `22` | `16.8210` |
| clipped best component | `0.00` | `82.7176` | `406.6546` | `24` | `15.5226` |
| clipped best component | `0.05` | `32.2546` | `317.3208` | `22` | `16.5413` |

## 判断

component分解は診断として有益だが、現時点では単一の `raw EV - component quality` risk penaltyとして標準採用しない。

理由:

- validation topが全て `risk_penalty=0` へ戻る。
- positive-risk候補はfold最低PnL、合計PnL、trade数のいずれかを大きく削る。
- EV過大評価を下げる目的にも効いていない。
- OOF回帰指標が改善しても、1玉制約とentry/exit policyの中で有効な意思決定信号になっていない。

次はcomponentをscalar penaltyへ潰さず、exit class、time-to-event、fixed horizon成分、side/regime residualを別々の特徴またはmulti-output診断として扱う。entry可否を直接下げる前に、どの失敗型を避けたいのかを分ける。

## Artifacts

- timed component OOF/apply: `data/reports/modeling/20260628_173832_candidate_quality_timed_barrier_component_2024_12/`
- fixed component OOF/apply: `data/reports/modeling/20260628_173832_candidate_quality_fixed_horizon_component_2024_12/`
- clipped component OOF/apply: `data/reports/modeling/20260628_173831_candidate_quality_clipped_best_component_2024_12/`
- timed component validation: `data/reports/backtests/candidate_quality_timed_barrier_component_overestimate_risk_validation/`
- fixed component validation: `data/reports/backtests/candidate_quality_fixed_horizon_component_overestimate_risk_validation/`
- clipped component validation: `data/reports/backtests/candidate_quality_clipped_best_component_overestimate_risk_validation/`
- timed component summary: `data/reports/backtests/candidate_quality_timed_barrier_component_overestimate_risk_summary/20260628_174249_model_sweep_summary/`
- fixed component summary: `data/reports/backtests/candidate_quality_fixed_horizon_component_overestimate_risk_summary/20260628_174249_model_sweep_summary/`
- clipped component summary: `data/reports/backtests/candidate_quality_clipped_best_component_overestimate_risk_summary/20260628_174249_model_sweep_summary/`

## Verification

- `PYTHONPATH=src python3 -m unittest discover -s tests`: OK, 136 tests
- `git diff --check`: OK
