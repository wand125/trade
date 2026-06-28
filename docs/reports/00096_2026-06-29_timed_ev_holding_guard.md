# Timed EV Holding Guard

日時: 2026-06-29 04:57 JST
更新日時: 2026-06-29 04:57 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00095` で確認した 2025-04 failure では、MLP exit minutes が負値を大量に出し、`timed_ev` が `min_predicted_hold_minutes=1` にclipして高回転化した。

この対策として、`timed_ev` に raw holding prediction の妥当性チェックを追加した。目的は勝つ候補を作ることではなく、異常な exit minutes をそのまま約定/決済policyへ流さない fail-close/fallback 基盤を作ること。

## 実装

`ModelPolicyConfig` と `model-sweep` に以下を追加した。

- `min_valid_predicted_hold_minutes`
- `long_holding_fallback_column`
- `short_holding_fallback_column`

挙動:

- default は `min_valid_predicted_hold_minutes=-inf` で、既存のclip-only挙動を維持する。
- `min_valid_predicted_hold_minutes` を有限値にすると、raw holding prediction が非finiteまたは閾値未満のsideはentry不可にする。
- fallback columnを指定した場合、primary holdingが無効なときだけfallback holdingを使う。
- fallbackも非finiteまたは閾値未満なら、そのsideはentry不可。

これにより、exit timing回帰が月外で負値を大量に出しても、明示的に `NoTrade` 寄りへ倒すか、より安定したHGB holdingへfallbackできる。

## 2025-04診断

評価倍率は現行ルール通り `profit=1.0`, `loss=1.20`。candidateは `00095` の strict top と同じ `entry=12`, short offset `6`, side margin `5`, short low-vol penalty `down5,up10,range5`。

| mode | scenario | min valid hold | adjusted pnl | raw pnl | trades | win rate | max DD | avg hold min | forced exit rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fallback to HGB event minutes | base | `120` | `-170.7302` | `-18.2460` | `86` | `0.4535` | `439.0468` | `348.34` | `0.0116` |
| fallback to HGB event minutes | high cost | `120` | `-182.3386` | `-29.0300` | `86` | `0.4535` | `470.2968` | `348.33` | `0.0116` |
| fail-close skip | base | `60` | `-111.2648` | `-37.5830` | `65` | `0.5385` | `290.2292` | `236.40` | `0.0154` |
| fail-close skip | high cost | `60` | `-129.9124` | `-55.9010` | `65` | `0.5077` | `285.9210` | `236.40` | `0.0154` |

比較:

- `00095` のMLP holding本線 strict topは base `-477.6848`, high `-1503.3702`。
- HGB fallbackは高回転を止めるが、base/highともNoTradeには届かない。
- fail-close skipはさらに損失とdrawdownを縮めるが、やはりNoTradeには届かない。

## 判断

holding guardは採用する。ただし標準candidateの改善ではなく、安全装置として扱う。

今回の結果は次を示す。

- MLP exit minutesを非負制約なし回帰としてpolicy holdingへ直結するのは危険。
- fallbackよりも、異常なraw holdingではentryしない fail-close のほうが2025-04では損失を抑えた。
- それでも 2025-04 は負なので、exit timing guardだけでは entry/side EV の月外崩れは解決しない。

次に進めること:

- exit minutes targetを `log1p(minutes)`、bin分類、hazard/event probabilityへ変える。
- `min_valid_predicted_hold_minutes` はstress診断軸として残し、validationで選んだ候補を未使用月へ固定適用する。
- 2025-04に直接合わせたthreshold最適化はしない。改善案はwalk-forward validationへ戻してから再評価する。

## Artifacts

- fallback base sweep: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_2025_04_hold_guard_fallback_base_sweep/20260628_195306_model_sweep_2025-04/`
- fallback high-cost sweep: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_2025_04_hold_guard_fallback_highcost_sweep/20260628_195306_model_sweep_2025-04/`
- fail-close base sweep: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_2025_04_hold_guard_skip_base_sweep/20260628_195658_model_sweep_2025-04/`
- fail-close high-cost sweep: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_2025_04_hold_guard_skip_highcost_sweep/20260628_195658_model_sweep_2025-04/`

## Verification

- `python3 -m py_compile src/trade_data/backtest.py tests/test_backtest.py`: OK
- `python3 -m unittest tests.test_backtest`: OK, 62 tests
- `python3 -m unittest tests.test_docs_reports`: OK, 2 tests
- `python3 -m unittest discover tests`: OK, 144 tests
- `python3 -m trade_data.backtest model-sweep`: OK for fallback and fail-close 2025-04 diagnostics
- `git diff --check`: OK
