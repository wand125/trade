# Shared MLP 4fold Pilot

日時: 2026-06-28 20:20 JST
更新日時: 2026-06-28 20:20 JST

## 目的

`oof-shared-mlp` のsmokeで配線は確認できた。今回は代表validation 4foldで、shared MLP regressionがHGB独立targetでは拾えなかった表現共有を作れているか、実行可能backtestまで含めて確認する。

Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime, file-update timestamp, or `更新日時`. Latest-report checks and renumbering must use the internal `日時`.

## Setup

- Dataset: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined`
- Loss multiplier: profit `1.0`, loss `1.20`
- Months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Fold: leave-one-month-out, `fold-month-count=1`
- Purge/embargo: `purge_label_overlap=true`, `embargo_hours=24`
- Model: shared `MLPRegressor`, hidden layers `32,16`
- Training: `sample_frac=0.15`, `max_iter=40`, `alpha=0.01`, `learning_rate_init=0.001`
- Policy target set: regression targets only. Classification probability targets are still not trained by this MLP path.

Artifact:

- `experiments/20260628_111106_shared_mlp_oof_4fold_pilot/`

## OOF Metrics

All folds reached `max_iter=40`, so the run is still convergence-limited.

| target | R2 | MAE | RMSE |
|---|---:|---:|---:|
| long best adjusted pnl | `-0.003462` | `10.321747` | `13.080293` |
| short best adjusted pnl | `-0.164505` | `11.505426` | `17.290482` |
| long fixed 240m adjusted pnl | `-0.106596` | `7.282006` | `10.469661` |
| short fixed 240m adjusted pnl | `-0.094095` | `7.300153` | `10.203828` |
| long exit event minutes | `0.338873` | `492.900681` | `699.467953` |
| short exit event minutes | `0.345407` | `490.890455` | `708.628137` |
| long wait regret | `0.029903` | `2.260426` | `3.578816` |
| short wait regret | `0.012852` | `2.143299` | `4.221730` |
| side score | `-0.151357` | `19.959515` | `26.742645` |

OOF oracle-exit selection at entry threshold `10`:

| selected trades | oracle-exit pnl | avg adjusted pnl | side accuracy | oracle upper bound |
|---:|---:|---:|---:|---:|
| `113069` | `2079901.7270` | `18.3950` | `0.590860` | `2966134.6440` |

このoracle値は実行可能policyではなく、モデルがside/exitに含む上限信号の診断である。EV系R2とside scoreは弱く、exit timingだけが相対的に学習できている。

## Fixed Policy Backtest

OOF予測を `timed_ev`, `entry_threshold=10`, `side_margin=1`, predicted holding `1..720m` でそのまま実行可能backtestへ接続した。

| holdout | adjusted pnl | raw pnl | trades | profit factor | max drawdown | forced exits | long / short / flat signals |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-07 | `-60.4136` | `92.7110` | `940` | `0.9342` | `172.4002` | `4` | `19969 / 10242 / 12416` |
| 2024-09 | `45.7428` | `167.5370` | `813` | `1.0626` | `71.8664` | `4` | `20300 / 6796 / 14149` |
| 2024-11 | `-171.2478` | `9.6740` | `777` | `0.8422` | `218.8300` | `3` | `18738 / 8383 / 13992` |
| 2025-01 | `184.0416` | `282.3770` | `767` | `1.3119` | `44.8230` | `4` | `20432 / 8099 / 11374` |
| total | `-1.8770` | `552.2990` | `3297` | - | - | `15` | - |

raw pnlはプラスだが、取引数が多く、コスト調整後はほぼゼロで、2024-11の崩れが大きい。

## Sweep And Selection

4ヶ月それぞれで `timed_ev` の閾値、short offset、side margin、rank、max holdingをsweepした。各月の単月topは以下。

| holdout | adjusted pnl | raw pnl | trades | PF | DD | entry | short offset | side margin | rank | max hold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-07 | `85.9052` | `118.8110` | `51` | `1.4351` | `42.9512` | `25` | `8` | `10` | `0.0` | `720` |
| 2024-09 | `241.5520` | `276.2010` | `128` | `2.1619` | `39.1116` | `15` | `0` | `10` | `0.0` | `480` |
| 2024-11 | `26.3904` | `35.7400` | `14` | `1.4704` | `43.2240` | `40` | `4` | `1` | `0.0` | `240` |
| 2025-01 | `271.7078` | `310.6380` | `174` | `2.1632` | `51.0446` | `20` | `4` | `3` | `0.5` | `720` |

Strict selection:

- `min_folds=4`
- `min_trades_per_fold=10`
- `max_forced_exit_rate=0.05`
- `max_drawdown=200`
- `min_adjusted_pnl_per_fold=0`
- `max_side_trade_share=0.85`

Result: `eligible=0`.

`eligible_base` / `eligible_cost` だけなら4候補が残ったが、いずれも `max_side_trade_share_max_all=1.0` で、少なくとも1foldが片側だけに寄る。strict基準では採用しない。

Relaxed side-balance diagnostic:

`max_side_trade_share=1.0` まで緩めると4候補がeligibleになる。topは `entry=40`, `short offset=0`, `side_margin=10`, `rank=0`, `max_hold=240` で、4fold合計 adjusted pnl `107.6652`, 最小月 adjusted pnl `8.1124`, 最小月 trades `16`, 最大DD `43.2240`。ただし片側100%を許容した結果なので、実運用候補ではない。

## 判断

shared MLPはexit timingには信号を持っているが、entry EVとside scoreはまだ弱い。固定policyでは高turnoverでコスト負けし、sweep後も厳格な横断候補は残らなかった。

片側偏りを許せばプラス候補は作れるが、それは「低頻度・片側寄りに逃げた候補」であり、未知regimeに壊れにくい意思決定システムとしては不十分。今回のshared MLP 4fold pilotは標準policyへ昇格しない。

## 次

- MLPを続けるなら、単純な長時間学習ではなく、EV/sideの校正とclassification hybridを追加する。
- `pred_*_exit_event_minutes` は有望なので、exit timing専用モデルとentry/sideモデルを分ける案を検証する。
- 片側100%候補は採用せず、side balance制約を維持したまま、entry thresholdの低頻度化が本当に汎化するかを別期間で見る。
- レポートの最新判断、再採番、既存レポート確認は、ファイル属性の更新時刻ではなく、本文冒頭の `日時` を参照する。

## Artifacts

- OOF model: `experiments/20260628_111106_shared_mlp_oof_4fold_pilot/`
- Fixed backtests: `data/reports/backtests/shared_mlp_oof_4fold_pilot/`
- Sweep backtests: `data/reports/backtests/shared_mlp_oof_4fold_pilot_sweep/`
- Strict selection: `data/reports/backtests/shared_mlp_oof_4fold_pilot_selection/20260628_111815_model_candidate_selection/`
- Relaxed side-balance diagnostic: `data/reports/backtests/shared_mlp_oof_4fold_pilot_selection_relaxed_side/20260628_111910_model_candidate_selection/`
