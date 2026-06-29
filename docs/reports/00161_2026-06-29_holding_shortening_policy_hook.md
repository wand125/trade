# Holding Shortening Policy Hook

日時: 2026-06-29 19:24 JST
更新日時: 2026-06-29 19:24 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00160` で作った dense holding-shortening target の分類確率を、`model-policy` / `model-sweep` の保有時間制御へ接続した。

追加した制御は、`pred_long_fixed_60m_beats_exit_event_prob_1` / `pred_short_fixed_60m_beats_exit_event_prob_1` が閾値以上のとき、side別の予測保有時間を指定cap分へ丸めるもの。これは「固定60分決済がexit-event決済より良い確率が高いなら、長く持ちすぎない」という補助policyであり、entry方向の直接変更ではない。

## Implementation

`src/trade_data/backtest.py`:

- `ModelPolicyConfig` に以下を追加。
  - `long_holding_shortening_column`
  - `short_holding_shortening_column`
  - `holding_shortening_threshold`
  - `holding_shortening_cap_minutes`
- `holding_shortening_threshold=inf` をデフォルトにし、既存挙動は完全に無効状態を維持。
- `timed_ev` / `fixed_horizon_ev` の holding が決まった後に、shortening probabilityが閾値以上なら `min(predicted_holding, cap_minutes)` を適用。
- `model-policy` CLI と `model-sweep` CLI に同じ設定を追加。
- `SWEEP_KEY_COLUMNS` と旧sweep CSV互換の正規化へ `holding_shortening_threshold` / `holding_shortening_cap_minutes` を追加。

`tests/test_backtest.py`:

- `timed_ev` の保有時間がshortening probabilityでcapされ、signalが早くflatへ戻ることを確認。
- `stateful_ev` / `stateless_ev` で finite threshold を指定した場合はエラーにすることを確認。
- 旧sweep metrics正規化で新カラムが default 無効値へ補完されることを確認。

## Smoke Setup

2025-02 holdoutの既存EV/holding predictionと、holding-shortening smoke OOFのbeat probabilityを `decision_timestamp` で結合した。

Input:

- base EV/holding: `data/reports/modeling/20260629_policy_combined_exit_holding_holdouts/predictions_test_2025_02_exit_holding_columns.parquet`
- shortening probability: `data/reports/modeling/20260629_100956_20260629_dense_holding_shortening_oof_smoke_2025_02_04/predictions_oof.parquet`

Output:

- `data/reports/modeling/20260629_holding_shortening_policy_hook_smoke/predictions_2025_02_merged.parquet`
- rows: `27,441`
- range: `2025-01-31 21:59 UTC` to `2025-02-28 21:58 UTC`

Probability distribution:

| column | mean | p25 | p50 | p75 | max |
|---|---:|---:|---:|---:|---:|
| `pred_long_fixed_60m_beats_exit_event_prob_1` | `0.4880` | `0.4372` | `0.4931` | `0.5403` | `0.6948` |
| `pred_short_fixed_60m_beats_exit_event_prob_1` | `0.5585` | `0.5005` | `0.5652` | `0.6251` | `0.7621` |

## Backtest Smoke

Evaluation:

- month: `2025-02`
- policy: `timed_ev`
- `entry_threshold=10`
- `side_margin=5`
- `profit_multiplier=1.0`
- `loss_multiplier=1.20`
- spread/slippage/delay: default `0`

単発比較:

| variant | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD |
|---|---:|---:|---:|---:|---:|---:|
| disabled | `-53.5244` | `-11.1590` | `34` | `0.5588` | `0.7894` | `142.0054` |
| threshold `0.70`, cap `60` | `-47.0418` | `-3.5890` | `36` | `0.5278` | `0.8196` | `142.0054` |

小sweep:

| threshold | cap minutes | adjusted pnl | raw pnl | trades | profit factor | avg holding min |
|---:|---:|---:|---:|---:|---:|---:|
| `0.65` | `30` | `-44.8382` | `-0.1260` | `43` | `0.8329` | `449.5349` |
| `0.70` | `60` | `-47.0418` | `-3.5890` | `36` | `0.8196` | `568.9444` |
| `0.70` | `30` | `-48.8944` | `-4.9290` | `38` | `0.8146` | `539.0526` |
| `inf` | `30` | `-53.5244` | `-11.1590` | `34` | `0.7894` | `600.0000` |
| `inf` | `60` | `-53.5244` | `-11.1590` | `34` | `0.7894` | `600.0000` |
| `0.65` | `60` | `-57.8288` | `-14.5820` | `40` | `0.7771` | `482.3250` |

Artifacts:

- base run: `data/reports/backtests/holding_shortening_policy_hook_smoke_base/20260629_102404_model_timed_ev_2025-02/`
- cap run: `data/reports/backtests/holding_shortening_policy_hook_smoke_cap60_t070/20260629_102404_model_timed_ev_2025-02/`
- sweep: `data/reports/backtests/holding_shortening_policy_hook_smoke_sweep/20260629_102426_model_sweep_2025-02/`

## Interpretation

接続は機能した。`threshold=0.70, cap=60` では disabled より adjusted pnl が `+6.4826` 改善し、小sweepでは `threshold=0.65, cap=30` が `+8.6862` 改善した。

ただし絶対成績はまだNoTrade未満で、単月・同日生成のsmoke predictionに過ぎない。`0.65 cap30` はtrade数を増やし、short側の挙動を変えているため、ここで採用せず、複数月walk-forward / cost stress / regime別診断で壊れ方を見る。

今回の価値は、深層学習targetを「entry方向」だけでなく「出口を待ちすぎない確率」としてpolicyに渡せるようになった点にある。次は `holding_shortening` target-setを単独smokeでなく、base EV/holding predictionと同時に生成するか、prediction mergeを正式パイプライン化して複数月で評価する。

## Verification

- `python3 -m py_compile src/trade_data/backtest.py`: OK
- `python3 -m unittest tests.test_backtest`: OK, 81 tests
- `model-policy` smoke disabled/cap: OK
- `model-sweep` threshold/cap smoke: OK

## Next

- 2025-02だけでなく、2025-03/04でも同じ接続で評価する。
- threshold/cap探索はvalidation内に限定し、fixed holdoutでは再探索しない。
- `holding_shortening` probabilityのcalibrationを確認し、probability thresholdの過大評価を抑える。
- `threshold=0.65 cap30` は候補ではなく、次のvalidation gridに入れる観測値として扱う。
