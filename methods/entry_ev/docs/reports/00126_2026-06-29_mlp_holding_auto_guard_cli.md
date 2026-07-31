# MLP Holding Auto Guard CLI

日時: 2026-06-29 10:13 JST
更新日時: 2026-06-29 10:13 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00125` と ADR `0009` で、MLP holdingを使う `timed_ev` 実験では `min_valid_predicted_hold_minutes=30` の fail-close skipを標準安全制約にすると決めた。

ただし、CLI defaultが従来のclip-only挙動のままだと、今後のsweepや固定policyでフラグ指定漏れが起きる。今回はこの制約を `model-policy` / `model-sweep` の標準挙動に反映する。

## 実装

- `DEFAULT_MLP_MIN_VALID_HOLD_MINUTES = 30.0` を追加。
- holding columnが `pred_mlp_*` で始まる場合、auto defaultを `30.0` にする。
- holding columnが非MLPの場合は従来通り `-inf` にする。
- `model-policy` では `--min-valid-predicted-hold-minutes` 省略時にauto解決する。
- `model-sweep` では defaultを `auto` にし、同じ列名判定で1値へ解決する。
- 明示的な `-inf` や数値CSVはautoより優先する。
- `ModelPolicyConfig` dataclass defaultは `-inf` のまま維持した。直接API利用や非MLP holding実験の互換性を守るため。

## Smoke

2025-04のMLP holding policyで、`--min-valid-predicted-hold-minutes` を指定せずに `model-policy` を実行した。

主要条件:

- policy: `timed_ev`
- month: `2025-04`
- EV columns: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- entry threshold: `12`
- short entry threshold offset: `6`
- side margin: `5`
- min entry rank: `0.5`
- max predicted hold: `480`
- side EV penalty: `short:combined_regime=down_low_vol:5`, `short:combined_regime=up_low_vol:10`
- profit/loss: `1.0 / 1.20`

結果:

| item | value |
|---|---:|
| resolved min valid hold | `30.0` |
| adjusted PnL | `-18.7168` |
| trades | `77` |
| max drawdown | `249.9600` |
| forced exits | `1` |

config上も `min_valid_predicted_hold_minutes=30.0` を確認した。これは `00125` の `skip min_valid=30` と同じ結果で、CLI defaultのauto解決が標準guardとして効いている。

## 判断

MLP holdingを使う `timed_ev` 標準比較では、今後フラグを明示しなくてもfail-close guardが入る。

従来のclip-only挙動は、2025-04型の異常高回転を再発させるため標準比較から外す。再現実験として必要な場合だけ、明示的に `--min-valid-predicted-hold-minutes -inf` を指定する。

非MLP holding列ではauto defaultは `-inf` のままなので、HGB holdingや派生holding列の既存比較は勝手に変わらない。

## 次の作業

1. guard固定後の代表候補を再評価する。
2. entry/side EV calibrationとexit timing targetへ戻る。
3. 高回転破綻の再発確認として、trade count、median holding、forced rate、high-cost drawdownを必ず併記する。

## Artifacts

- smoke run: `data/reports/backtests/holding_guard_auto_cli_smoke/20260629_011241_model_timed_ev_2025-04/`
- config: `data/reports/backtests/holding_guard_auto_cli_smoke/20260629_011241_model_timed_ev_2025-04/config.json`

## Verification

- `python3 -m unittest tests.test_backtest`: OK, 72 tests
- `python3 -m unittest tests.test_docs_reports`: OK, 2 tests
- `python3 -m trade_data.backtest model-sweep --help | rg -n "min-valid|auto|pred_mlp"`: help text confirms `auto`
