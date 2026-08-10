# 00020 Intrabar structure features

日時: 2026-08-08 02:25 JST

## 目的

レポート00018の足内M1集約値に加え、M15内部で極値がいつ出たか、経路がどれだけ反転・蛇行したかを加工する。raw価格水準を使わず、次のM15方向そのものと高信頼度選別が改善するかを同一7foldで確認した。

## 事前固定した特徴

既存のintrabar 7特徴に次の8特徴を追加した。

- M15内で最初に高値を付けた相対位置
- M15内で最初に安値を付けた相対位置
- 高値位置 - 安値位置
- M1実体方向の転換率
- M1 close経路の方向効率
- M1実現分散 / M15 log range²
- M1 close経路の最大drawdown / 過去20本M15 ATR
- M1 close経路の最大runup / 過去20本M15 ATR

すべて完成済みM1だけから計算する。将来M1のOHLCを変えても過去完成M15特徴が変わらないテスト、生価格水準を特徴へ含めないguard、保存artifactからの最新1行推論を通した。実装名は `--feature-set intrabar_structure`。

HGB parameter、Platt校正、2020〜2026途中の7fold、blend weight 25%はbaselineと既存実験に固定した。結果後に特徴の追加・削除、weight変更はしていない。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| 2020–2023 | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| 2020–2023 | structure single | 52.123% | 0.2492495 | 0.6916438 | 0.383% |
| 2024–2026途中 | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| 2024–2026途中 | structure single | 51.339% | 0.2495939 | 0.6923338 | 0.486% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | structure single | 51.820% | 0.2493825 | 0.6919103 | 0.421% |

単体はdevelopmentで改善したがconfirmationのaccuracyと全proper scoreが悪化したため方向モデルとして採用しない。

通常25% blendは全体accuracy 51.815%でbaselineをわずかに下回り、confirmationも51.430%へ低下した。誤り修正2,185件、新規誤り2,187件、McNemar exact p=0.988で方向改善はない。

## 方向維持型confidence blend

baseline方向を固定し、structure HGB 25%をconfidence edgeの強さだけへ使った。accuracyとbalanced accuracyはbaselineと完全に同一。

| period | metric | baseline | candidate |
|---|---|---:|---:|
| 2020–2023 | Brier | 0.2493466 | 0.2492878 |
| 2020–2023 | log loss | 0.6918398 | 0.6917211 |
| 2020–2023 | ECE | 0.377% | 0.360% |
| 2024–2026途中 | Brier | 0.2495525 | 0.2495475 |
| 2024–2026途中 | log loss | 0.6922506 | 0.6922407 |
| 2024–2026途中 | ECE | 0.298% | 0.277% |
| all | Brier | 0.2494261 | 0.2493881 |
| all | log loss | 0.6919985 | 0.6919218 |
| all | ECE | 0.347% | 0.328% |

Brier、log loss、ECEはdevelopmentとconfirmationの両方で改善した。fold別でも各指標6/7 fold改善。

## confidence 0.55高精度lane

| period | model | rows | coverage | accuracy | Wilson lower | selection score |
|---|---|---:|---:|---:|---:|---:|
| 2020–2023 | baseline | 9,821 | 11.025% | 55.453% | 54.468% | 0.01483 |
| 2020–2023 | candidate | 9,699 | 10.888% | 55.934% | 54.943% | 0.01631 |
| 2024–2026途中 | baseline | 1,887 | 3.366% | 55.750% | 53.499% | 0.00642 |
| 2024–2026途中 | candidate | 1,740 | 3.104% | 56.437% | 54.095% | 0.00722 |
| all | baseline | 11,708 | 8.067% | 55.501% | 54.599% | 0.01306 |
| all | candidate | 11,439 | 7.881% | 56.010% | 55.099% | 0.01431 |

coverageを0.185pt減らす代わりにaccuracyを0.510pt上げ、selection scoreを9.59%改善した。年別accuracyは7/7 fold改善。selection scoreは5/7改善、1fold同値、1fold悪化だった。

0.53は全体scoreを0.01942から0.01994へ改善するがconfirmationでは0.01511から0.01471へ悪化する。0.54もconfirmationで悪化し、0.60はconfirmation 3件しかない。したがって固定候補は0.55だけとする。

## 判断

- structure単体と通常blendは方向用途として棄却する。
- 方向維持型25% blend + confidence 0.55を `m15_intrabar_structure_confidence_candidate_v1.json` のforward candidateへ固定する。
- 00018のintrabar候補と同じ履歴から作った派生候補なので、履歴数値で両者の勝者を決めたりstackしたりしない。次の完全未使用期間へ両方を固定適用して比較する。
- authoritative confidence、odds、採用policy、paper policyは変更しない。
- 損益は目的関数へ含めず、後続診断でも損失倍率は標準1.0のみとする。
