# 00030 XGBoost and clear-body target

日時: 2026-08-08 12:19 JST

## 目的

既存HGBとは異なるboosting実装が、同じ加工済み定常特徴から方向またはconfidenceの追加edgeを抽出できるか検証する。通常方向教師と、既存最良候補であるclear-body教師を別々に評価する。

## 結果前に固定した方法

- dependency: `xgboost>=2.1,<4`。検証環境では3.4.0。
- model: `--model-type xgboost`
- 300 trees、depth 4、learning rate 0.03、min child weight 20、row/column subsample 0.80、L2 5、hist tree method。
- 入力はbaselineの38加工特徴だけで、raw OHLC価格水準は含めない。
- 早期停止やtestを見たparameter調整は行わない。
- 教師は全足の通常方向と、各foldのtrain内で次足body/ATR中央値以上だけを残す `body_atr_upper_half` の2条件。
- M15 2020〜2026途中の同一7fold、Platt calibration。通常25% blendとbaseline方向を維持する25% confidence blendを比較する。
- confidence閾値はdevelopment 2020〜2023の固定gridで選び、confirmation 2024〜2026途中へ固定する。

XGBoost artifactの保存、raw価格排除、最新推論をテストした。
Intel macOSではXGBoostとPyTorchのOpenMP runtimeが同一processで競合したため、両backendを遅延importし、CLI processが選択した学習器だけを読み込むようにした。統合テストもXGBoost経路を独立processで検証する。

## 通常方向教師

### 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| development | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| development | XGBoost single | 52.081% | 0.2493047 | 0.6917550 | 0.351% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | XGBoost single | 51.294% | 0.2495898 | 0.6923252 | 0.554% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | XGBoost single | 51.777% | 0.2494148 | 0.6919752 | 0.430% |

単体のdevelopment改善はconfirmationで反転した。通常25% blendもdevelopment accuracy 52.084%に対しconfirmation 51.458%で、全体は51.842%まで上がったが再現しない。誤り修正1,646件、新規誤り1,608件、McNemar exact p=0.517であり、方向edgeとして採用しない。

### 方向維持型confidence blend

developmentで選ばれた閾値は0.53だった。

| period | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | baseline | 29.868% | 54.309% | 0.02027 |
| development | XGBoost blend | 29.807% | 54.499% | 0.02129 |
| confirmation | baseline | 18.438% | 54.479% | 0.01511 |
| confirmation | XGBoost blend | 18.456% | 54.388% | 0.01472 |
| all | baseline | 25.453% | 54.357% | 0.01942 |
| all | XGBoost blend | 25.423% | 54.468% | 0.01996 |

confirmationでaccuracyとselection scoreが悪化した。Brier/log lossもconfirmationで僅かに悪化したため候補化しない。

## clear-body教師

### 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| development | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| development | clear XGBoost single | 52.091% | 0.2492829 | 0.6917104 | 0.235% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | clear XGBoost single | 51.357% | 0.2495659 | 0.6922772 | 0.468% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | clear XGBoost single | 51.807% | 0.2493922 | 0.6919293 | 0.324% |

通常25% blendは全体accuracy 51.825%だがconfirmationは51.460%へ低下した。誤り修正2,290件、新規誤り2,277件、p=0.859のため方向用途として棄却する。

### 方向維持型confidence blend

| period | metric | baseline | candidate |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2492876 |
| development | log loss | 0.6918398 | 0.6917207 |
| development | ECE | 0.377% | 0.307% |
| confirmation | Brier | 0.2495525 | 0.2495396 |
| confirmation | log loss | 0.6922506 | 0.6922247 |
| confirmation | ECE | 0.298% | 0.276% |
| all | Brier | 0.2494261 | 0.2493849 |
| all | log loss | 0.6919985 | 0.6919154 |
| all | ECE | 0.347% | 0.295% |

Brier/log lossは7/7 fold、ECEは5/7 fold改善した。developmentで選ばれた閾値は0.525だった。

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 33,770 | 37.908% | 53.858% | 0.02048 |
| development | clear XGBoost | 32,405 | 36.376% | 54.146% | 0.02173 |
| confirmation | baseline | 14,785 | 26.375% | 53.777% | 0.01527 |
| confirmation | clear XGBoost | 14,463 | 25.801% | 53.917% | 0.01576 |
| all | baseline | 48,555 | 33.454% | 53.834% | 0.01961 |
| all | clear XGBoost | 46,868 | 32.292% | 54.075% | 0.02059 |

accuracyとselection scoreは6/7 fold改善し、2026途中だけ僅かに悪化した。

## clear-body HGBとの比較

| period | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | clear HGB | 35.639% | 54.173% | 0.02164 |
| development | clear XGBoost | 36.376% | 54.146% | 0.02173 |
| confirmation | clear HGB | 24.714% | 54.201% | 0.01675 |
| confirmation | clear XGBoost | 25.801% | 53.917% | 0.01576 |
| all | clear HGB | 31.419% | 54.182% | 0.02088 |
| all | clear XGBoost | 32.292% | 54.075% | 0.02059 |

XGBoostはdevelopment scoreとcoverageだけ僅かに高いが、confirmationと全体のaccuracy・selection scoreはHGBが上回る。確率品質もclear HGBの全体Brier 0.2493800、log loss 0.6919054、ECE 0.254%がXGBoostより良い。

## 最新推論確認

clear-body XGBoostを全期間60%/20%/20%で別学習し、データ末尾まで `predict-latest` を実行した。2026-06-01 04:45 UTC判定はup、model confidence 0.57988だった。これはartifact経路の機能確認値で、有効なempirical oddsではない。

## 判断

- 通常教師XGBoost、clear-body XGBoostとも単体・通常方向blendは棄却する。
- clear-body XGBoostの方向維持型0.525は安定した改善だが、既存clear-body HGBをconfirmation、全体、確率品質で超えないためforward/shadow configは発行しない。
- XGBoost実装は学習器比較の再現用に残す。同じ履歴でtree数、深さ、正則化、subsample、blend weightを探索しない。
- authoritative confidence、odds、現行policy、paper policyは変更しない。損失倍率は標準1.0のみとする。
