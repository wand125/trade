# Entry EV Path Compensation Diagnostics

日時: 2026-07-02 15:27 JST
更新日時: 2026-07-02 15:27 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00302でlarge-loss probabilityのdirect hard gateが勝ちtradeを削ると分かったため、同じrisk scoreを「同じcontext-month内で大損が勝ちに補償されるか」というpath-aware軸で分解した。
- `scripts/experiments/entry_ev_selected_trade_path_compensation_diagnostics.py` を追加し、selected-trade large-loss head predictionsから context-month PnL、compensated large loss、risk threshold別のflagged context PnLを出せるようにした。
- 実大損23件のうち、同じ `direction|combined_regime|session_regime` / month内でnet positiveに補償されたものは1件だけだった。
- ただしrisk threshold除去は20本すべて悪化。最大でも `block_delta_if_removed = -15.0000` で、positive deltaは0本。
- 失敗理由は、大損が広く補償されているからではなく、large-loss risk scoreがwinnerやpositive context-monthも強くflagするから。
- 判断: path compensation diagnosticsはaccepted infrastructure。direct risk hard gateは引き続きreject。次は「uncompensated large loss」や「negative path context」を候補レベル / stateful replay用targetにする。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_selected_trade_path_compensation_diagnostics.py`
- New test:
  - `tests/test_entry_ev_selected_trade_path_compensation_diagnostics.py`
- Main run:
  - `data/reports/backtests/20260702_062720_20260702_entry_ev_path_compensation_large_loss_s1/`

## Input

```text
data/reports/backtests/20260702_061536_20260702_entry_ev_prior_pressure_large_loss_head_s1/selected_trade_large_loss_head_predictions.csv
```

Run setting:

```text
target modes:
  factor,pnl

feature sets:
  base,base_prior

context:
  direction,combined_regime,session_regime

large win threshold:
  5.0
```

## Large-Loss Compensation

| mode | feature set | trades | total PnL | large losses | large-loss PnL | compensated large losses | uncompensated large losses | large-loss context total |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| factor | base | `232` | `+329.4348` | `23` | `-123.0648` | `1` | `22` | `-58.0002` |
| factor | base_prior | `232` | `+329.4348` | `23` | `-123.0648` | `1` | `22` | `-58.0002` |
| pnl | base | `232` | `+329.4348` | `23` | `-123.0648` | `1` | `22` | `-58.0002` |
| pnl | base_prior | `232` | `+329.4348` | `23` | `-123.0648` | `1` | `22` | `-58.0002` |

Reading:

- compensated large loss shareは `1/23 = 0.0435`。
- 大損の多くは同context-month内でも補償されていない。
- したがって「大損はだいたい勝ちに補償される」という説明ではなく、「risk scoreがpositive pathも一緒に拾う」が主問題。

## Threshold Diagnostics

Top rows sorted by least-bad block delta:

| mode | feature set | threshold | flagged trades | flagged PnL | delta if removed | flagged large losses | compensated flagged large losses | flagged context months | positive flagged contexts | flagged context total |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| factor | base_prior | `prob_ge_0.4` | `2` | `+15.0000` | `-15.0000` | `0` | `0` | `2` | `2` | `+15.0000` |
| factor | base_prior | `prob_ge_0.3` | `7` | `+23.4124` | `-23.4124` | `1` | `0` | `7` | `5` | `+29.1024` |
| factor | base | `prob_ge_0.4` | `3` | `+25.8100` | `-25.8100` | `0` | `0` | `3` | `3` | `+27.4000` |
| factor | base_prior | `top_q95` | `13` | `+39.8504` | `-39.8504` | `1` | `0` | `9` | `6` | `+33.8824` |
| pnl | base | `prob_ge_0.2` | `17` | `+58.1320` | `-58.1320` | `5` | `1` | `14` | `8` | `+60.3820` |
| pnl | base_prior | `prob_ge_0.4` | `4` | `+59.9100` | `-59.9100` | `1` | `1` | `3` | `3` | `+70.8900` |

Reading:

- 20 threshold rowsのうち、positive block deltaは `0`。
- risk scoreは大損を一部拾うが、除去対象の合計PnLは常にプラス。
- context-monthで見ると、flagged contextの多くがnet positive。特に高risk上位はwinnerそのものを拾っている。

## High-Risk Path Example

| mode | feature set | month | context | trade PnL | large loss | predicted risk | context trades | context total | context win PnL | context loss PnL | compensated |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pnl | base | `2025-11` | `short|down_normal_vol|london` | `-7.9800` | true | `0.6541` | `2` | `+54.1000` | `+62.0800` | `-7.9800` | true |
| pnl | base | `2025-11` | `short|down_normal_vol|london` | `+62.0800` | false | `0.6359` | `2` | `+54.1000` | `+62.0800` | `-7.9800` | false |
| pnl | base_prior | `2025-11` | `long|range_normal_vol|ny_late` | `+0.1200` | false | `0.5306` | `3` | `+11.1000` | `+11.1000` | `0.0000` | false |
| pnl | base_prior | `2025-11` | `short|down_normal_vol|london` | `-7.9800` | true | `0.5004` | `2` | `+54.1000` | `+62.0800` | `-7.9800` | true |
| pnl | base_prior | `2025-11` | `short|down_normal_vol|london` | `+62.0800` | false | `0.5004` | `2` | `+54.1000` | `+62.0800` | `-7.9800` | false |

Reading:

- 00302で見えた `short|down_normal_vol|london` のpairは、path-awareに見るとcontext-month total `+54.1000`。
- large-loss headは「危険なcontext」を見ているが、そこで入らない判断にすると同じpathの大勝も消す。
- entry timing / exit timing / candidate replacementが必要で、pointwise risk blockでは情報の使い方が粗い。

## Decision

Accepted:

- path-aware context-month compensation diagnostics
- risk threshold別のflagged context PnL summary
- large-loss rowが補償済みかどうかのlabel生成インフラ

Rejected:

- large-loss probabilityのdirect hard gate
- high-risk quantile removal
- 「riskが高いcontextは全て避ける」という粗い解釈

Standard policy remains NoTrade.

## Next

1. large-loss targetを `is_large_loss` から `large_loss_uncompensated_by_context` / negative path contextへ分解する。
2. ただし同月の実現context PnLは未来情報なので、そのまま教師以外に使わない。実行時はprior-only context、candidate-level state、entry/exit featuresで代理する。
3. large-loss probabilityはhard gateではなく、candidate-level selector / stateful replay / exit timing targetの補助featureへ回す。
4. NoTrade-first selectorとsupport-aware diagnosticsを維持する。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_selected_trade_path_compensation_diagnostics.py tests/test_entry_ev_selected_trade_path_compensation_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_path_compensation_diagnostics`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_path_compensation_diagnostics tests.test_entry_ev_selected_trade_large_loss_head tests.test_docs_reports`: OK
- `git diff --check`: OK
- path compensation diagnostics run: OK
