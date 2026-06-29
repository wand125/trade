# Side Drift Guard Delta Diagnostics

日時: 2026-06-29 22:55 JST
更新日時: 2026-06-29 22:55 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `00176` の no guard vs side drift guard を `model-trade-delta` で分解した。
- broad p5 は total PnLを `-419.0574 -> -394.7214`、delta `+24.3360`。
- strict short-only p10 は total PnLを `-419.0574 -> -317.4998`、delta `+101.5576`。
- ただし、改善の大部分は「悪いbase tradeを消す」効果で、空いた時間に入る replacement trade が大きな損失を作っている。
- 結論: side drift guardは悪いshort文脈を検出できるが、単独採用はしない。次は「guardで抑制した後に代替tradeへ入るか、stay flat/cooldownするか」を別の判断問題として扱う。

## Artifacts

- broad p5 delta: `data/reports/backtests/20260629_135405_side_drift_guard_broad_p5_delta_2025_01_12/`
- strict p10 delta: `data/reports/backtests/20260629_135405_side_drift_guard_strict_p10_delta_2025_01_12/`
- source broad run: `data/reports/backtests/20260629_134533_side_drift_guard_wf_2025_01_12_coststress_260/`
- source strict run: `data/reports/backtests/20260629_134638_side_drift_guard_wf_short_strict_2025_01_12_coststress_260/`

## Aggregate Delta

| case | base PnL | candidate PnL | delta | base trades | candidate trades |
|---|---:|---:|---:|---:|---:|
| broad p5 | `-419.0574` | `-394.7214` | `+24.3360` | `1153` | `1187` |
| strict p10 | `-419.0574` | `-317.4998` | `+101.5576` | `1153` | `1146` |

## Status Breakdown

`only_base` はguard候補で消えたbase取引、`only_candidate` はguard候補で新しく入った取引、`common` は同じentry/directionで残った取引。

| case | status | rows | base PnL | candidate PnL | delta |
|---|---|---:|---:|---:|---:|
| broad p5 | common | `975` | `-177.3478` | `-100.9376` | `+76.4102` |
| broad p5 | only_base | `178` | `-241.7096` | `0.0000` | `+241.7096` |
| broad p5 | only_candidate | `212` | `0.0000` | `-293.7838` | `-293.7838` |
| strict p10 | common | `1028` | `112.5658` | `184.8674` | `+72.3016` |
| strict p10 | only_base | `125` | `-531.6232` | `0.0000` | `+531.6232` |
| strict p10 | only_candidate | `118` | `0.0000` | `-502.3672` | `-502.3672` |

Interpretation:

- broad p5 は `only_base +241.7096` と `common +76.4102` を作ったが、`only_candidate -293.7838` でほぼ相殺された。
- strict p10 は悪いbase trade除外が強く、`only_base +531.6232`。しかし replacement の `only_candidate -502.3672` が同程度に大きい。
- したがって弱点はside guardそのものより、guard後に入る代替tradeの入場判定にある。

## Direction Breakdown

| case | status | direction | rows | delta |
|---|---|---|---:|---:|
| broad p5 | only_base | short | `103` | `+207.2548` |
| broad p5 | only_candidate | short | `80` | `-267.0140` |
| broad p5 | only_base | long | `75` | `+34.4548` |
| broad p5 | only_candidate | long | `132` | `-26.7698` |
| strict p10 | only_base | short | `111` | `+431.5526` |
| strict p10 | only_candidate | short | `62` | `-435.4884` |
| strict p10 | only_base | long | `14` | `+100.0706` |
| strict p10 | only_candidate | long | `56` | `-66.8788` |

strict p10はshort除外の目的には合っている。問題は、shortを抑制しても新しいshortが別時点で入り、fresh tailの損失を消し切れないこと。

## Worst Replacement Contexts

strict p10の `only_candidate` worst contexts:

| month | direction | combined regime | rows | candidate PnL |
|---|---|---|---:|---:|
| 2025-09 | short | range_low_vol | `4` | `-119.5560` |
| 2025-12 | short | range_low_vol | `10` | `-74.2140` |
| 2025-05 | short | range_low_vol | `2` | `-50.7720` |
| 2025-12 | short | up_low_vol | `2` | `-36.4470` |
| 2025-11 | short | range_normal_vol | `1` | `-34.4760` |
| 2025-05 | short | range_normal_vol | `4` | `-34.3960` |
| 2025-09 | short | range_normal_vol | `1` | `-33.9000` |
| 2025-12 | long | up_low_vol | `10` | `-30.9020` |

broad p5でも同じ構造が出ている。最大は2025-09 `only_candidate short/range_low_vol` の `-110.5740`。

## Best Removed Base Losses

strict p10の `only_base` best removals:

| month | direction | combined regime | rows | removed base PnL | delta |
|---|---|---|---:|---:|---:|
| 2025-09 | short | range_low_vol | `14` | `-128.0052` | `+128.0052` |
| 2025-12 | short | range_low_vol | `11` | `-106.4744` | `+106.4744` |
| 2025-12 | long | up_low_vol | `1` | `-61.1040` | `+61.1040` |
| 2025-09 | short | up_normal_vol | `7` | `-41.1680` | `+41.1680` |
| 2025-11 | short | range_normal_vol | `2` | `-40.4084` | `+40.4084` |
| 2025-12 | short | up_normal_vol | `2` | `-35.3148` | `+35.3148` |
| 2025-05 | short | up_normal_vol | `21` | `-31.7820` | `+31.7820` |

この表はguardが見ている悪いshort文脈が完全な偶然ではないことを示す。一方で、同じ `range_low_vol` 周辺がreplacement側でも大きく負ける。

## Stateful Replacement Cost

`candidate_stateful_positive_cost_adjusted_pnl` は、候補PnLから候補がブロックしたbase側のプラスPnLだけを差し引く保守的な値。

| case | status | direction | candidate PnL | blocked positive PnL | positive-cost value |
|---|---|---|---:|---:|---:|
| broad p5 | only_candidate | short | `-267.0140` | `43.9630` | `-310.9770` |
| broad p5 | only_candidate | long | `-26.7698` | `239.0380` | `-265.8078` |
| strict p10 | only_candidate | short | `-435.4884` | `39.8860` | `-475.3744` |
| strict p10 | only_candidate | long | `-66.8788` | `69.2110` | `-136.0898` |

replacementは単体PnLでも悪く、さらに一部では良いbase機会も潰している。したがって次の教師設計は、entry方向そのものよりも `replacement_regret` / `positive_replacement_regret` / `stateful_positive_cost_value` を重視する。

## Decision

- side drift guardは標準policyへ採用しない。
- ただし、prior-only drift guardは診断・候補生成として残す。
- 次は以下を試す:
  - guard発火後に代替sideへ即入らず、EV marginまたはquality marginが不足するなら stay flat にする。
  - guardで抑制された時点の replacement 候補を `stateful_positive_cost_value` / `positive_replacement_regret` で再評価する。
  - `range_low_vol` のshort replacementをhard blockするのではなく、対象月より前だけで `replacement_risk` を作る。
  - 月別walk-forwardで、removed-loss効果とreplacement-loss効果を別々にscore化する。

採番監査: 既存 `docs/reports/*.md` は本文内 `日時` 順で問題0件。最新判定は `00177` の本文 `日時: 2026-06-29 22:55 JST`。
