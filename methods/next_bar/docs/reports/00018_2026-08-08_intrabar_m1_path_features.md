# 00018 Intrabar M1 path features

日時: 2026-08-08 02:05 JST

## 目的

M15 OHLCへ集約すると失われる足内M1経路を加工し、次のM15方向と高信頼度精度を改善できるか確認する。

## 固定特徴

現在の完成M15を構成する完成済みM1から次の7指標を計算した。足内最初のclose returnだけは直前に完成したM1 closeを分母に使うが、いずれもM15判定時点より前の観測値である。

- M1 log returnの足内標準偏差
- 上昇M1実体の比率
- M1実体合計 / M1実体絶対値合計
- 最大M1実体 / M1実体絶対値合計
- 足の最初の1/3における正規化実体合計
- 足の最後の1/3における正規化実体合計
- 終盤実体合計 - 序盤実体合計

raw M1/M15価格水準はモデル特徴にしない。未来のM1を変更しても過去完成M15のintrabar特徴が変わらない因果性テストを追加した。

現行38特徴へ7特徴を追加し、HGB parameter、Platt校正、2020〜2026途中の7foldは固定。結果後に特徴を追加・削除していない。単体は `walk_forward_intrabar_manual_001`、通常25% blendは `ensemble_intrabar_manual_25_001`、方向維持型は `intrabar_manual_confidence_blend_001`。

## 単体と方向blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| 2020–2023 | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| 2020–2023 | intrabar single | 52.131% | 0.2492755 | 0.6916961 | 0.298% |
| 2024–2026途中 | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| 2024–2026途中 | intrabar single | 51.380% | 0.2495538 | 0.6922532 | 0.434% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | intrabar single | 51.841% | 0.2493830 | 0.6919113 | 0.349% |

単体はdevelopmentで改善したがconfirmationでaccuracy・Brier・log loss・ECEが悪化したため置換しない。

固定25%通常blendは全体accuracy 51.848%、development 52.050%、confirmation 51.526%で、両期間ともbaselineを上回った。Brier、log loss、ECEも両期間で改善した。ただし誤り修正2,003件、新規誤り1,957件、純改善46件、McNemar exact p=0.475で、fold accuracy改善は3/7。方向モデル置換には弱いためshadow候補に留める。

## 方向維持型confidence blend

方向をbaseline HGBへ固定し、intrabar HGB 25%をconfidence edgeへだけ使用した。全体accuracyはbaselineと完全同一。

| period | metric | baseline | candidate |
|---|---|---:|---:|
| 2020–2023 | Brier | 0.2493466 | 0.2492997 |
| 2020–2023 | log loss | 0.6918398 | 0.6917452 |
| 2020–2023 | ECE | 0.377% | 0.348% |
| 2024–2026途中 | Brier | 0.2495525 | 0.2495402 |
| 2024–2026途中 | log loss | 0.6922506 | 0.6922261 |
| 2024–2026途中 | ECE | 0.298% | 0.277% |
| all | Brier | 0.2494261 | 0.2493926 |
| all | log loss | 0.6919985 | 0.6919309 |
| all | ECE | 0.347% | 0.320% |

## confidence 0.55高精度lane

| period | model | rows | coverage | accuracy | Wilson lower | selection score |
|---|---|---:|---:|---:|---:|---:|
| 2020–2023 | baseline | 9,821 | 11.025% | 55.453% | 54.468% | 0.01483 |
| 2020–2023 | candidate | 9,534 | 10.702% | 55.832% | 54.833% | 0.01581 |
| 2024–2026途中 | baseline | 1,887 | 3.366% | 55.750% | 53.499% | 0.00642 |
| 2024–2026途中 | candidate | 1,734 | 3.093% | 56.459% | 54.114% | 0.00723 |
| all | baseline | 11,708 | 8.067% | 55.501% | 54.599% | 0.01306 |
| all | candidate | 11,268 | 7.764% | 55.928% | 55.010% | 0.01396 |

coverageを0.303pt減らす代わりにaccuracyを0.428pt上げ、selection scoreを6.87%改善した。年別accuracyとselection scoreはいずれも6/7 foldで改善した。

confidence 0.53はselection scoreが `0.01942 -> 0.01907` と悪化するため採用しない。0.60はconfirmation supportが2件しかなく採用根拠にしない。

## 判断

- intrabar単体は方向モデルとして不採用。
- 通常25%方向blendは両期間で改善したが差が小さくfold安定性も弱いためshadowに留める。
- 方向維持型blend + confidence 0.55を `m15_intrabar_confidence_candidate_v1.json` の高精度forward candidateへ固定する。
- Extra Trees 0.53をcoverage重視、body/ATR weighted 0.54を精度重視、intrabar 0.55を高精度重視の別laneとして扱う。履歴結果を見た後に3候補をstackしない。
- 次の完全未使用期間で0.55 accuracy、selection score、Brierがすべてbaseline以上なら昇格を検討する。
- 損益は目的関数に含めていない。後続診断を行う場合も損失倍率は標準1.0のみとする。
