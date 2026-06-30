# Entry EV Residual 2024-03 Loss Diagnostics

日時: 2026-06-30 17:28 JST
更新日時: 2026-06-30 17:31 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00226で残った fresh `2024-03` の `q95_floor5 / 720m` 月次損失 `-9.1718` を、trade単位で「方向ミス」「exit capture不足」「prior risk coverage」に分解するscriptを追加した。
- `scripts/experiments/entry_ev_residual_month_loss_diagnostics.py` は enriched trade CSVを読み、role/candidate/monthで絞り込み、flag別・context別・loss trade別の集計を出す。
- 結論: この月は `no_edge_entry` では説明できない。18 tradesすべてに同方向oracle利益余地があり、same-side oracle totalは `+327.9840`、actual best totalは `+485.5670`。実現PnLが `-9.1718` になった主因は、7件の方向ミスと、13件の大きなexit regretである。
- `prior_context_risk>=0.50` はこの月の損失を拾えない。後付け感度として `>=0.20` なら4 trades / `-31.2560` を拾うが、全体検証なしにthresholdを下げて採用しない。
- 標準policyはNoTradeのまま。次はentry抑制の細密化ではなく、exit timing target / direction-side inversion target / EV過大評価校正を、chronological validationで分けて試す。

## Artifacts

- Script: `scripts/experiments/entry_ev_residual_month_loss_diagnostics.py`
- Test: `tests/test_entry_ev_residual_month_loss_diagnostics.py`
- Main diagnostic:
  - `data/reports/backtests/20260630_entry_ev_residual_month_loss_diagnostics/20260630_082721_entry_ev_residual_2024_03_q95_720/`
- Prior-risk threshold sensitivity:
  - `data/reports/backtests/20260630_entry_ev_residual_month_loss_diagnostics/20260630_082752_entry_ev_residual_2024_03_q95_720_prior020/`
- Input:
  - `data/reports/backtests/20260630_entry_ev_prior_context_risk_diagnostics/20260630_080641_entry_ev_prior_context_risk_fresh_q95_720_prior_validation/enriched_prior_context_risk_trades.csv`

## Main Result

対象は `fresh2024_validation`, `2024-03`, `q95_sg95_rank90_floor5_side_regime_session_month`, `max_predicted_hold=720m`, profit `1.0`, loss `1.20`。

| metric | value |
|---|---:|
| trades | `18` |
| adjusted PnL | `-9.1718` |
| loss trades | `7` |
| loss PnL | `-52.0548` |
| win rate | `0.6111` |
| same-side oracle total | `+327.9840` |
| actual best total | `+485.5670` |
| exit regret sum | `337.1558` |
| best-side regret sum | `494.7388` |
| direction error count | `7` |
| no-edge entry count | `0` |
| loss with same-side oracle edge | `7` |
| large exit regret count (`>=10`) | `13` |
| large best-side regret count (`>=10`) | `15` |
| EV overestimate vs realized positive | `17` |
| prior context available | `7` |
| prior context risk high (`>=0.50`) | `0` |

Interpretation:

- `no_edge_entry=0` なので、「entry候補そのものを消せばよい」という診断ではない。
- loss trades 7件すべてが同方向oracleでは正の利益余地を持つ。つまり、同じsideで入っていても手放し方が悪いtradeが多い。
- ただしdirection errorも7件あり、実際のbest sideへ反転した場合のregretも大きい。exitだけでなく、side/context inversionのtargetも必要。
- prediction EVはoracleに対しては平均で過大ではないが、realized PnLに対しては大きく過大。これは「oracleに近いexitを取れないなら、予測EVを割り引く」calibrationが必要ということ。

## Failure Flags

| flag | flagged trades | flagged PnL | removal delta | exit regret | best-side regret |
|---|---:|---:|---:|---:|---:|
| `is_loss` | `7` | `-52.0548` | `+52.0548` | `126.5758` | `262.6788` |
| `loss_with_same_side_oracle_edge` | `7` | `-52.0548` | `+52.0548` | `126.5758` | `262.6788` |
| `direction_error` | `7` | `-46.3626` | `+46.3626` | `81.0626` | `238.6456` |
| `prior_has_context` | `7` | `-35.9456` | `+35.9456` | `133.2456` | `239.1886` |
| `large_best_side_regret` | `15` | `-34.7518` | `+34.7518` | `316.5558` | `473.1688` |
| `large_exit_regret` | `13` | `-30.5188` | `+30.5188` | `308.1128` | `434.8458` |
| `ev_overestimate_positive` | `17` | `-27.5218` | `+27.5218` | `331.1858` | `488.7688` |
| `no_edge_entry` | `0` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| `prior_context_risk_high` (`>=0.50`) | `0` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |

`prior_has_context` 自体は負け側に寄るが、00226の標準threshold `0.50` では発火しない。これはsupport / risk scoreの強さが足りないというより、現risk scoreがこの残差月の主要損失構造を十分に表現していないことを示す。

## Worst Trades

| side | context | PnL | same-side oracle | actual best | direction error | exit regret | best-side regret | prior risk |
|---|---|---:|---:|---:|---|---:|---:|---:|
| short | `down_low_vol/asia` | `-21.1560` | `+0.4600` | `+38.7130` | true | `21.6160` | `59.8690` | `0.2312` |
| short | `up_normal_vol/london` | `-11.9196` | `+4.9500` | `+30.0100` | true | `16.8696` | `41.9296` | `0.0000` |
| short | `range_low_vol/london` | `-11.8200` | `+1.1800` | `+42.8400` | true | `13.0000` | `54.6600` | `0.2414` |
| short | `up_low_vol/asia` | `-5.4360` | `+2.7900` | `+12.1600` | true | `8.2260` | `17.5960` | `0.0000` |
| long | `range_normal_vol/ny_late` | `-0.7428` | `+21.3610` | `+21.3610` | false | `22.1038` | `22.1038` | `0.0000` |
| long | `range_normal_vol/london` | `-0.5040` | `+13.3800` | `+35.1400` | true | `13.8840` | `35.6440` | `0.0000` |
| long | `up_low_vol/ny_late` | `-0.4764` | `+30.4000` | `+30.4000` | false | `30.8764` | `30.8764` | `0.0000` |

Worst short 4件はdirection-side inversionに寄る。long側の小損はdirectionは合っているが、利益余地を手放し方で逃している。

## Threshold Sensitivity

`prior_context_risk>=0.20` を後付けで見ると:

| flag | flagged trades | flagged PnL | pointwise removal delta |
|---|---:|---:|---:|
| `prior_context_risk_high >=0.20` | `4` | `-31.2560` | `+31.2560` |

これは局所的には魅力的だが、採用しない。00225/00226で広いcontext blockは良いtradeも削ると分かっている。thresholdを下げるなら、fresh fixedだけでなく、validation role群と追加chronological windowで副作用を確認してからにする。

## Decision

Accepted:

- residual losing month diagnostic script。
- flag/context/loss trade単位で、direction error、same-side exit capture、prior risk coverageを分解する見方。
- `2024-03` の主因を「entry floor不足」ではなく「direction-side inversion + exit capture + realized EV calibration不足」と扱う判断。

Not accepted:

- `prior_context_risk` thresholdを `0.20` へ下げること。
- `no_edge_entry` だけを使ったentry suppression。
- fresh fixedの単月残差に合わせたhard block。

Standard policy remains NoTrade.

## Next

1. Exit timing targetを強化する。same-side oracle profitがあるlossを、hazard/survivalまたはhold extension/early-exit risk targetで拾う。
2. Direction-side inversion targetを分離する。worst short contextではactual best sideが逆側に大きく寄っているため、context-side priorだけでなくcurrent prediction side gap / dense label side bias / regime driftを使う。
3. Expected PnL calibrationをrealized-executable基準へ寄せる。oracleではなく「今のexit modelで実現可能なEV」を校正対象にする。
4. `prior_context_risk` はhard blockよりselector feature / rank featureとして試す。thresholdを下げる場合は追加chronological validationで副作用を見る。

## Verification

- `python3 -m unittest tests.test_entry_ev_residual_month_loss_diagnostics tests.test_entry_ev_prior_context_risk_diagnostics tests.test_entry_ev_quantile_hold_cap_sensitivity tests.test_docs_reports`: OK, `12` tests
- `python3 -m py_compile scripts/experiments/entry_ev_residual_month_loss_diagnostics.py tests/test_entry_ev_residual_month_loss_diagnostics.py`: OK
- main residual diagnostic run: OK
- prior risk threshold sensitivity run: OK
- `git diff --check`: OK
