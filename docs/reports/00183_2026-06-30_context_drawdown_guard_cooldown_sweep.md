# Context Drawdown Guard Cooldown Sweep

日時: 2026-06-30 07:32 JST
更新日時: 2026-06-30 07:32 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- online context drawdown guard に `context_drawdown_guard_cooldown_minutes` を追加した。
- 既定値 `0` は従来通り、breach後の同一side/contextを月内hard blockする。
- 正の値を指定した場合は、breachした同一side/contextを `close_timestamp + cooldown_minutes` までだけブロックする。
- 仮説は「hard blockで消していた利益機会を、一定時間後に再評価すれば戻せるか」。
- 結果は不採用。cooldownは前半月の利益機会を戻す一方、2025-08以降のshort損失を再入場させ、prior-onlyでは既存のhard block / high margin案より悪化した。

## Artifacts

- Cooldown sweep: `data/reports/backtests/20260629_221524_context_drawdown_guard_side_month_cooldown_sweep/`
- Prior-only selection min4: `data/reports/backtests/context_drawdown_guard_side_month_cooldown_selection_min4/`
- Prior-only selection min8: `data/reports/backtests/context_drawdown_guard_side_month_cooldown_selection_min8/`

Inputは `00182` と同じ `p10 + margin10` 月次run。`context_columns=dataset_month`, profit `1.0`, loss `1.20`, coststress spread/slippage/delay。

## Implementation

- `ModelPolicyConfig.context_drawdown_guard_cooldown_minutes` を追加。
- `run_backtest(...)` は、cooldown `0` なら既存通り永久block、正の有限値なら期限付きblockとして扱う。
- `model-policy` CLI: `--context-drawdown-guard-cooldown-minutes`
- `model-sweep` CLI: `--context-drawdown-guard-cooldown-minutes-values`
- `context_drawdown_guard_apply.py` CLI: `--cooldown-minutes-values`

## All-Window Sweep

これは全2025月を見た後知恵のshape check。

| threshold | margin | cooldown min | trades | total PnL | worst month | max DD | short PnL | long PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `60` | `20` | `0` | `842` | `142.9750` | `-153.6646` | `153.6646` | `-146.5528` | `289.5278` |
| `60` | `inf` | `0` | `841` | `135.6350` | `-153.6646` | `153.6646` | `-153.8928` | `289.5278` |
| `40` | `inf` | `720` | `886` | `110.2922` | `-152.2210` | `179.7390` | `-236.5366` | `346.8288` |
| `40` | `20` | `720` | `886` | `110.2922` | `-152.2210` | `179.7390` | `-236.5366` | `346.8288` |
| `40` | `20` | `0` | `693` | `107.9040` | `-138.4960` | `138.4960` | `-64.3548` | `172.2588` |
| `40` | `inf` | `0` | `692` | `100.5640` | `-138.4960` | `138.4960` | `-71.6948` | `172.2588` |

all-windowでも最高値は cooldown `0`。`40/720min` はlong利益を増やすがshort損失も大きく戻し、max DDが悪化する。

## Prior-Only Selection

`threshold + margin + cooldown` を候補として、対象月より前だけで選択した。

| min train months | selection | target months | trades | total PnL | worst month | max DD | selected pattern |
|---:|---|---:|---:|---:|---:|---:|---|
| `4` | `worst` | `8` | `492` | `38.8288` | `-126.1230` | `178.8940` | `20/20/60`, `20/inf/720`, `20/20/0` |
| `4` | `total` | `8` | `528` | `-358.0610` | `-283.2780` | `283.2780` | `40/20/720`, `60/20/1440`, `60/20/60` |
| `8` | `worst` | `4` | `99` | `-209.1152` | `-126.1230` | `178.8940` | `20/inf/720`, `20/20/0` |
| `8` | `total` | `4` | `161` | `-548.3290` | `-283.2780` | `283.2780` | `40/20/720`, `60/20/60` |

`00182` の cooldownなし margin-aware prior-only `worst` は、min4 total `69.9374`, worst `-116.4516`; min8 total `-199.4438`, worst `-116.4516`。今回の cooldown候補込みは、どちらも悪化した。

## Failure Pattern

`20/20` の月別比較では cooldown `60` が2025-05..07を改善したが、2025-08以降でshort損失を戻した。

| month | cooldown 0 PnL | cooldown 60 PnL | cooldown 720 PnL |
|---|---:|---:|---:|
| 2025-05 | `-45.3640` | `54.8332` | `54.6078` |
| 2025-06 | `90.2534` | `225.3196` | `187.6570` |
| 2025-07 | `-36.7236` | `78.6708` | `33.4710` |
| 2025-08 | `-54.2112` | `-110.8796` | `-40.5738` |
| 2025-09 | `-116.4516` | `-289.3546` | `-126.1230` |
| 2025-11 | `-3.0350` | `-97.1596` | `-53.8020` |
| 2025-12 | `-31.4700` | `-137.1030` | `-147.5630` |

これは「短い冷却で利益機会も戻るが、同じ仕組みで壊れたshortも戻る」挙動。side drift が強い後半では cooldown がリスク制御として不十分。

## Decision

- cooldown infrastructureは残す。
- 標準policyやrisk mandateには採用しない。
- `00182` の結論を維持する。defensible familyは、prior-only `worst` objective の hard block / high re-entry margin 側。
- 次は cooldown ではなく、breach後に「再入場するか」をentry marginだけでなく、recent side drift / realized context loss / prediction-side biasを特徴量化して学習またはselectionに戻す。

## Verification

- `python3 -m py_compile src/trade_data/backtest.py scripts/experiments/context_drawdown_guard_apply.py scripts/experiments/context_drawdown_guard_selection.py`: OK
- `python3 -m unittest tests.test_backtest tests.test_context_drawdown_guard_selection`: OK, 99 tests
