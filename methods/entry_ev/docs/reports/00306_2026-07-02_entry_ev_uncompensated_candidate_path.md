# Entry EV Uncompensated Candidate Path

日時: 2026-07-02 16:15 JST
更新日時: 2026-07-02 16:15 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00305の次アクションとして、uncompensated targetを単発row gateではなく、既存のrealized candidate path variantごとに比較する診断を追加した。
- `scripts/experiments/entry_ev_uncompensated_candidate_path_diagnostics.py` を追加し、path variantごとに context-month compensation、前後trade state、月次floor、candidate summary、target rowsを出せるようにした。
- 入力は00293 residual combo overlayの `entry_block_overlay_trades.csv`。`selector_variant` を実path variantとして扱い、`entry_blocked` はデフォルトで除外する。
- 正式runは `s4`。`s1` から `s3` は `entry_blocked` exclusionを入れる前、またはvariant解釈を調整中の中間出力なので採用しない。
- 00293 best branchは 232 trades / total `+329.4348` / role min `+0.5354` / month min `-0.7200` / uncompensated target 22件。targetは22件残るが、候補群内ではmonth floorが最も良い。
- target数を減らすだけでは良くならない。`uncompensated_target_count` と `total_pnl` の相関は `+0.0502` と弱く、`month_pnl_min` との相関は `+0.5674`。この候補集合では、activeで良いpathほどtargetも残る傾向がある。
- 判断: realized candidate-path diagnosticsはaccepted。target countの単純最小化やuncompensated rowのdirect blockはreject。次は完全な未選択entry candidate feedを使うstateful replacement replayへ進む。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_uncompensated_candidate_path_diagnostics.py`
- New test:
  - `tests/test_entry_ev_uncompensated_candidate_path_diagnostics.py`
- Main run:
  - `data/reports/backtests/20260702_071443_20260702_entry_ev_uncompensated_candidate_path_s4/`

## Input

```text
data/reports/backtests/20260702_043727_20260702_entry_ev_stateful_entry_block_overlay_residual_combo_s1/entry_block_overlay_trades.csv
```

Run setting:

```text
large_loss_threshold: -2.0
large_win_threshold: 5.0
context_columns:
  direction
  combined_regime
  session_regime
variant source:
  selector_variant when present
entry_blocked:
  excluded by default
```

Important caveat:

- この診断は既存overlay / hold-extensionのrealized path variant比較であり、未選択entry候補を全て再投入するfull replacement replayではない。
- `next_*` 系列は診断専用であり、実行時featureには使わない。

## Candidate Summary

Best candidate:

```text
variant:
  loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_short_rollover_or_london_midloss_or_holdext_range_ny

candidate:
  q95_sg95_rank90_floor5_side_regime_session_month
```

| metric | value |
|---|---:|
| total PnL | `+329.4348` |
| trades | `232` |
| role total PnL min | `+0.5354` |
| month PnL min | `-0.7200` |
| role trade count min | `3` |
| month trade count min | `1` |
| positive roles | `6 / 6` |
| large losses | `23` |
| compensated large losses | `1` |
| uncompensated targets | `22` |
| uncompensated target PnL | `-115.0848` |
| target followed by next win | `15` |
| next-win PnL after target | `+64.3560` |
| max drawdown | `30.8714` |
| overall side share | `0.5474` |

Top comparisons:

| variant sketch | total | trades | month min | targets | target PnL | next-win targets |
|---|---:|---:|---:|---:|---:|---:|
| best residual combo | `+329.4348` | `232` | `-0.7200` | `22` | `-115.0848` | `15` |
| short rollover block only group | `+323.5700` | `255` | `-2.4566` | `24` | `-119.5368` | `16` |
| no entry-block on same side horizon | `+318.8540` | `256` | `-4.1460` | `25` | `-124.2528` | `17` |
| `t-5_hpredicted` residual combo | `+351.2472` | `230` | `-23.5914` | `19` | `-162.3528` | `14` |
| `t-5_h720` no entry-block | `+170.5374` | `246` | `-112.1634` | `20` | `-328.7328` | `14` |

Reading:

- `t-5_hpredicted` はtotalだけなら `+351.2472` だが、month floor `-23.5914` が弱い。
- `t-5_h720` no entry-blockはtarget数が20件と少なく見えるが、month floor `-112.1634` とtarget PnL `-328.7328` が大きく悪い。
- 00293 best branchはtarget数の最小候補ではないが、role/month floorが最も安定している。

## Target Count Distribution

| target count | variants | total mean | total max | month min mean | best month min |
|---:|---:|---:|---:|---:|---:|
| `17` | `1` | `+218.8162` | `+218.8162` | `-112.1634` | `-112.1634` |
| `18` | `1` | `+214.1002` | `+214.1002` | `-112.1634` | `-112.1634` |
| `19` | `12` | `+213.3586` | `+351.2472` | `-97.4014` | `-23.5914` |
| `20` | `20` | `+307.7699` | `+346.5312` | `-32.3633` | `-23.4696` |
| `21` | `13` | `+237.5321` | `+307.5116` | `-84.8730` | `-23.4696` |
| `22` | `2` | `+263.7764` | `+329.4348` | `-56.4417` | `-0.7200` |
| `23` | `1` | `+324.7188` | `+324.7188` | `-4.1460` | `-4.1460` |
| `24` | `14` | `+299.9876` | `+323.5700` | `-13.6368` | `-2.4566` |
| `25` | `40` | `+237.3393` | `+318.8540` | `-36.2786` | `-4.1460` |
| `26` | `39` | `+272.8184` | `+290.3530` | `-13.5577` | `-6.8324` |
| `27` | `41` | `+268.7582` | `+286.5202` | `-6.8324` | `-6.8324` |
| `28` | `8` | `+262.7686` | `+267.0742` | `-6.8324` | `-6.8324` |

Correlation:

| pair | correlation |
|---|---:|
| target count vs total PnL | `+0.0502` |
| target count vs month PnL min | `+0.5674` |
| next-win target count vs total PnL | `+0.1434` |

Reading:

- target countは単独目的関数にしない。
- 低target数の候補は、活動量やblock位置の副作用で大きな月次tailを抱えることがある。
- target直後のwinnerも多く、target除去にはreplacement / skipped next winner / missed later candidateの評価が必要。

## Monthly Floor

Best branchのworst monthly rows:

| source | role | month | total | trades | targets | target PnL | next-win targets |
|---|---|---|---:|---:|---:|---:|---:|
| hybrid | hybrid2025_0912_external | `2025-11` | `-0.7200` | `1` | `0` | `0.0000` | `0` |
| internal | fresh2024_validation | `2024-11` | `-0.6120` | `1` | `0` | `0.0000` | `0` |
| internal | refit2025_validation | `2025-03` | `-0.4730` | `9` | `1` | `-2.3400` | `0` |
| internal | fresh2024_validation | `2024-03` | `-0.3636` | `1` | `0` | `0.0000` | `0` |
| hgb | hgb2025_08_external | `2025-08` | `+0.5354` | `11` | `0` | `0.0000` | `0` |
| hybrid | hybrid2025_0912_external | `2025-12` | `+0.5700` | `1` | `0` | `0.0000` | `0` |
| hgb | hgb2024_0306_external | `2024-05` | `+0.9578` | `21` | `4` | `-21.0036` | `3` |
| hgb | hgb2024_0306_external | `2024-06` | `+1.2246` | `16` | `2` | `-8.2404` | `1` |
| internal | refit2025_validation | `2025-05` | `+1.4766` | `15` | `3` | `-35.2164` | `2` |

Reading:

- 残るnegative monthsはthin support中心で、targetがない月もある。
- targetが複数ある `2024-05`, `2024-06`, `2025-05` でも月次totalはプラスで、targetだけを見てcontextを止めると勝ち側も削りやすい。

## Target Contexts

Best branchのuncompensated target 22件:

| context | count | target PnL | min PnL | next-win count | next-win PnL |
|---|---:|---:|---:|---:|---:|
| short / down_normal_vol / london | `2` | `-33.8160` | `-28.9920` | `2` | `+2.8700` |
| long / range_normal_vol / ny_overlap | `3` | `-14.0844` | `-7.5480` | `2` | `+1.0530` |
| short / range_low_vol / asia | `1` | `-11.4480` | `-11.4480` | `0` | `0.0000` |
| short / up_normal_vol / london | `2` | `-9.3924` | `-4.9800` | `2` | `+2.2100` |
| short / up_normal_vol / ny_late | `1` | `-6.5640` | `-6.5640` | `0` | `0.0000` |
| short / down_normal_vol / ny_overlap | `2` | `-5.0400` | `-2.7000` | `1` | `+1.0900` |
| short / up_low_vol / ny_late | `1` | `-4.6764` | `-4.6764` | `0` | `0.0000` |

Worst target rows:

| source | role | month | idx / count | direction | regime | session | PnL | context total | prev | next |
|---|---|---|---:|---|---|---|---:|---:|---|---|
| internal | refit2025_validation | `2025-05` | `8 / 15` | short | down_normal_vol | london | `-28.9920` | `-28.9920` | prev_win | next_win |
| hgb | hgb2024_0306_external | `2024-05` | `9 / 21` | short | range_low_vol | asia | `-11.4480` | `-11.4480` | prev_win | next_loss |
| internal | refit2025_validation | `2025-12` | `2 / 13` | long | range_normal_vol | ny_overlap | `-7.5480` | `-7.6200` | prev_loss | next_loss |
| hgb | hgb2024_0306_external | `2024-04` | `8 / 23` | short | up_normal_vol | ny_late | `-6.5640` | `-6.5640` | prev_loss | next_loss |
| hgb | hgb2024_0306_external | `2024-03` | `18 / 21` | short | up_normal_vol | london | `-4.9800` | `-4.1800` | prev_win | next_win |

Reading:

- 00305と同じく、targetは前後winnerや高密度pathに埋まっている。
- best branchでも大きいuncompensated targetは残るが、完全削除を優先すると月次floorやtotalを壊す候補が出る。

## Decision

Accepted:

- realized candidate-path diagnostics
- `selector_variant` をpath variantとして扱うnormalize
- `entry_blocked` default exclusion
- context-month compensationとcandidate summaryの横断比較

Rejected:

- target countの単純最小化
- uncompensated target probabilityのdirect hard gate
- `next_*` を実行featureとして使うこと
- realized path variant診断をfull replacement replay evidenceとして扱うこと

Standard policy remains NoTrade.

## Next

1. 未選択entry候補feedを使い、blocked / skipped / replacement candidateを含むstateful replayへ進む。
2. target countではなく、month floor、role floor、support、replacement cost、skipped next winnerを同時に評価する。
3. uncompensated targetは教師候補として残すが、direct gateではなくcandidate-level selector / exit timing target / uncertainty診断へ回す。
4. 00293 residual combo branchはdiagnostic benchmarkとして維持し、標準policyにはしない。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_uncompensated_candidate_path_diagnostics.py tests/test_entry_ev_uncompensated_candidate_path_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_uncompensated_candidate_path_diagnostics`: OK
- uncompensated candidate-path diagnostics run `s4`: OK
