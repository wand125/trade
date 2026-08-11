# 00130 State Correctness M5/M15/M30 Windows Transfer

日時: 2026-08-11 22:30 JST

## 目的

M1で作ったState CorrectnessをM5、M15、M30へ固定移植した。baselineの次足方向は変更せず、加工済みDistribution Shift市場状態54列とreference confidence・aligned edge・predicted-upの3列から「baseline方向が正しい確率」を学習する。

新規学習のcanonical環境はWindows/WSL2 x86 Linuxとし、低優先度worker、標準8 threadで3時間足を順番に実行した。HGB 100 iteration、learning rate 0.05、15 leaves、min leaf 50、L2 2、最大750,000行、過去OOSの古い80% fit・直近20% Platt、seed 42、標準損失1.0をM1から変更していない。

最初のtest2020は過去OOSがなくreference confidence fallbackなので、閾値選択、比較、bootstrapから除外した。developmentはtest2021〜2023、confirmationはtest2024〜2026途中である。

## Development選択閾値

固定grid `0.50, 0.505, 0.51, 0.515, 0.52, 0.525, 0.53, 0.54, 0.55, 0.575, 0.60` からdevelopment selection score最大を一度だけ選んだ。目的関数は `sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)` である。

| TF | 選択閾値 | 比較対象 | development score | confirmation score | all score | all Brier差 State−比較対象 |
|---|---:|---|---:|---:|---:|---:|
| M5 | 0.515 | Profile 0.515 | 0.013410 / 0.014995 | 0.008831 / 0.012313 | 0.012135 / 0.014475 | +0.00006987 |
| M15 | 0.51 | baseline 0.51 | 0.013739 / 0.015703 | 0.010007 / 0.012855 | 0.013231 / 0.015578 | +0.00013769 |
| M30 | 0.505 | baseline 0.505 | 0.013198 / 0.012608 | 0.009126 / 0.009429 | 0.012976 / 0.012816 | +0.00010260 |

M5はconfirmationでaccuracy差-0.3424ptの95%区間が-0.6791〜-0.0012pt、selection score差は-0.005376〜-0.001550で、Profile劣位が明確だった。all Brier/log loss差も悪化側で0を跨がない。

M15はbaselineにselection score 0/6fold、accuracy 2/6foldだった。all selection score差は-0.004250〜-0.000430、Brier/log lossも悪化側で0を跨がない。

M30はcoverage増加によりdevelopment/allの点scoreだけ僅かに上がったが、confirmationで反転した。all accuracy差-0.0874pt、score差+0.000160はいずれも95%区間が0を跨ぎ、Brier/log lossは悪化方向、accuracyは2/6foldだった。広coverage候補として採用しない。

## 固定0.55 tail

| TF | State rows / accuracy / score | 既存precision候補 rows / accuracy / score | 判断 |
|---|---:|---:|---|
| M5 | 8,930 / 54.9496% / 0.006085 | Follow-through 16,271 / 55.7618% / 0.010482 | 劣位 |
| M15 | 5,791 / 55.3100% / 0.008774 | Structure 9,523 / 55.0982% / 0.011450 | coverage不足でscore劣位 |
| M30 | 598 / 54.0134% / 0.000006 | Pressure + AR 4,088 / 55.5773% / 0.010585 | support・score不足 |

M5はFollow-throughにaccuracy 1/6、score 2/6foldで、all score差の95%区間は-0.006068〜-0.002732だった。M15は点accuracyだけStructureを+0.2118pt上回ったが区間は-0.8817〜+1.3103pt、score差区間は-0.005302〜-0.000078である。M30はdevelopment 163件・Wilson下限44.52%でedge自体を確認できない。

全分布のState確率は3時間足とも比較対象よりBrier/log lossが悪い。0.55をauthoritative probabilityやfair oddsへ使わない。

## M1固定guardの外部移植

M1で固定済みの `confidence >= 0.55 AND predicted up AND volatility normal/high` を、M5/M15/M30の結果を見ずにそのまま適用した。down全行とup-lowだけをabstentionにし、方向、閾値、volatility境界を再探索していない。

| TF | period | rows | coverage | accuracy | Wilson下限 | score | mean confidence |
|---|---|---:|---:|---:|---:|---:|---:|
| M5 | development | 3,480 | 1.7367% | 55.4023% | 53.7457% | 0.004936 | 56.2538% |
| M5 | confirmation | 1,469 | 0.8670% | 55.3438% | 52.7908% | 0.002599 | 56.1874% |
| M5 | all | 4,949 | 1.3382% | 55.3849% | 53.9963% | 0.004623 | 56.2341% |
| M15 | development | 2,521 | 3.8259% | 56.0889% | 54.1437% | 0.008105 | 56.7297% |
| M15 | confirmation | 538 | 0.9597% | 56.5056% | 52.2849% | 0.002238 | 55.9149% |
| M15 | all | 3,059 | 2.5084% | 56.1621% | 54.3971% | 0.006964 | 56.5864% |
| M30 | development | 85 | 0.2642% | 55.2941% | 44.7239% | -0.002712 | 55.2427% |
| M30 | confirmation | 329 | 1.1894% | 56.5350% | 51.1334% | 0.001236 | 56.5277% |
| M30 | all | 414 | 0.6919% | 56.2802% | 51.4658% | 0.001219 | 56.2638% |

M5 guardは未guardよりall accuracyを+0.4353pt上げたが、accuracy区間は0を跨ぎ、coverage減でscore差-0.001462が確定した。Follow-throughにもall scoreで明確に劣る。

M15 guardは未guardよりall accuracy+0.8522pt、Structureより+1.0640ptで、accuracyは5/6foldだった。しかしaccuracy差の95%区間はStructure比-0.4853〜+2.6477pt、all score差は-0.007300〜-0.001659で明確に劣る。test2023は11件、confirmation各foldも201/141/196件と疎く、confirmation合計538件はM1 precision laneのfresh 1,000件条件にも届かない。新しいultra-sparse役割を後付けせず棄却する。

M30 guardはcalibration点値が実績と近いが、development 85件・Wilson下限44.72%、all 414件に過ぎない。Pressure + ARよりall score差-0.009365が確定しており、shadowにも追加しない。

## 判断

M5/M15/M30 State Correctnessのdevelopment選択lane、未guard 0.55、M1固定guard 0.55をすべて再現専用として棄却する。新config、candidate registry、authoritative direction/confidence、fair odds、paper/live policyを変更しない。

M15固定guardは点accuracyと局所calibrationが最も有望だったが、ユーザー指定のaccuracy×coverage目的ではprecision championを明確に下回る。完全未使用期間を既存M1 shadowと同条件で受動監査することはできるが、今回の履歴から閾値、方向、volatility、別roleを再設計しない。

platform差を混ぜないため、今回のWindows canonical artifactと以前のMac再学習artifactは比較・平均・stackしない。今後の新規実験はWindowsで学習する。

## 品質改善

固定比較CLIの `--first-dir` と `--second-dir` を反復可能にした。M15のようにOOSが複数directoryへ非重複保存されていても、中間parquetを再生成せず厳密結合できる。parser testを追加した。

## 成果物

- canonical OOS/model: `experiments/next_bar/state_correctness_m{5,15,30}_windows_canonical_001`
- fixed M1 guard: `experiments/next_bar/state_correctness_up_nonlow_m{5,15,30}_windows_canonical_001`
- main comparisons: `experiments/next_bar/state_correctness_m{5,15,30}_windows_*_analysis.json`
- main daily bootstrap: `experiments/next_bar/state_correctness_m{5,15,30}_windows_*_bootstrap.json`
- guard comparisons: `experiments/next_bar/state_correctness_up_nonlow_m{5,15,30}_windows_*_analysis.json`
- guard daily bootstrap: `experiments/next_bar/state_correctness_up_nonlow_m{5,15,30}_windows_*_bootstrap.json`
- CLI: `methods/next_bar/scripts/compare_fixed_candidates.py`
- tests: `tests/test_next_bar_registry.py`
