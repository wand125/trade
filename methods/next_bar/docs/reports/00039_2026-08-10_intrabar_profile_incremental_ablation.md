# 00039 Intrabar profile incremental ablation

日時: 2026-08-10 14:12 JST

## 目的

00038のbroad confidence改善が新しい12 trajectory特徴によるものか、親のintrabar structure 15特徴だけでも同じ結果になるかを切り分ける。ProfileとStructureの方向維持25% blendを同じconfidence 0.515で直接比較する。

## 比較方法

- baseline feature、HGB parameter、7fold、Platt calibration、blend weight 25%は共通。
- Structureはbaseline + intrabar 15特徴、Profileはこれに正規化trajectory 12特徴を加えたもの。
- 閾値はProfileのdevelopment選択値0.515へ固定し、Structure側を再最適化しない。
- 2020〜2023 development、2024〜2026途中confirmation、全期間、各foldを同じ145,140行で比較する。
- 直接比較器 `compare_fixed_candidates.py` を追加し、確率品質、lane、選択集合の重なり、fold勝敗を保存する。

## 親Structureの現行grid再解析

Structureを0.515〜0.60の現行gridへ通すとdevelopment目的関数首位は0.53だった。ただし0.53はconfirmationでbaseline score 0.01511から0.01471へ悪化する。Profileで選ばれた0.515では、Structureはdevelopment scoreをbaseline 0.02048から0.02030へ下げた。

したがって「Structureを広coverageへ移しただけ」でProfile 0.515の改善を説明できない。

## 同一0.515の直接比較

| period | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | Structure | 58.479% | 53.084% | 0.02030 |
| development | Profile | 58.402% | 53.221% | 0.02134 |
| confirmation | Structure | 49.214% | 52.628% | 0.01430 |
| confirmation | Profile | 49.327% | 52.743% | 0.01513 |
| all | Structure | 54.901% | 52.926% | 0.01911 |
| all | Profile | 54.897% | 53.055% | 0.02007 |

Profileはcoverageをほぼ維持しながら、accuracyをdevelopment +0.138pt、confirmation +0.115pt、全体 +0.129pt改善した。selection scoreは3期間すべてで改善した。

## Fold安定性と選択集合

- ProfileはStructureに対しselection scoreを7/7 foldで改善した。
- accuracyは6/7 foldでProfile、1/7 foldでStructureが高かった。
- 選択集合Jaccardはdevelopment 92.01%、confirmation 92.24%、全体92.09%。
- 全体では両方選択76,397行、Profileだけ3,280行、Structureだけ3,286行だった。

選択件数を大きく変えた結果ではなく、約8%の境界行をtrajectory形状で入れ替えたことがaccuracy差につながっている。

## 確率品質

| period | metric | Structure | Profile |
|---|---|---:|---:|
| development | Brier | 0.2492878 | 0.2492852 |
| development | log loss | 0.6917211 | 0.6917161 |
| development | ECE | 0.360% | 0.347% |
| confirmation | Brier | 0.2495475 | 0.2495356 |
| confirmation | log loss | 0.6922407 | 0.6922169 |
| confirmation | ECE | 0.277% | 0.281% |
| all | Brier | 0.2493881 | 0.2493819 |
| all | log loss | 0.6919218 | 0.6919095 |
| all | ECE | 0.328% | 0.321% |

Profileはconfirmation ECEだけ僅かに劣るが、Brier/log lossは全3期間、全体ECEも改善した。

## 成果物と判断

- Structure再解析: `experiments/next_bar/intrabar_structure_candidate_analysis.json`
- 固定0.515直接比較: `experiments/next_bar/intrabar_profile_vs_structure_0515_analysis.json`
- 比較器: `methods/next_bar/scripts/compare_fixed_candidates.py`

新しいtrajectory特徴には親Structureを超えるincremental edgeがあると判断する。00038のbroad forward candidate採用とregistry championを維持する。ただしProfileはStructureから派生し同じ履歴で検証した候補なので、authoritative昇格には完全未使用期間が必要である。Profile地点・特徴subset・weight・閾値は再探索しない。損失倍率は標準1.0のみとする。
