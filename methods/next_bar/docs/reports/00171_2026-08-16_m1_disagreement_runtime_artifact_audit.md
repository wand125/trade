# 00171 M1 Five-model Disagreement runtime artifact audit

日時: 2026-08-16 19:31 JST

## 目的

M1 balanced coverage/probability-quality confidence候補のFive-model Disagreementについて、固定5 sourceを再学習せずlatest推論できるか監査する。

## 固定sourceと取得状況

configに固定されたsourceはbaseline HGB、Path Persistence HGB、Extra Trees、LightGBM、causal TCNの5本で、等重み、uncertainty penalty 0、baseline方向維持、confidence 0.515である。

| source | config参照artifact | 保存済みmodel |
|---|---|---:|
| baseline | `walk_forward_baseline_m1_current_001` | Windows canonical代替あり |
| Path Persistence | `walk_forward_path_persistence_m1_finite_001` | Windows canonical代替あり |
| Extra Trees | `walk_forward_extra_trees_m1_fixed_001` | 取得できず |
| LightGBM | `walk_forward_lightgbm_m1_fixed_001` | 取得できず |
| causal TCN | `walk_forward_tcn_m1_finite_001` | 取得できず |

`/srv/trade/experiments/next_bar`を監査した結果、baselineとPathには7fold modelを含むWindows canonical directoryがある。一方、Extra Trees、LightGBM、TCNはconfig参照directoryもWindows canonical生modelも存在しない。合成済みOOS predictionだけから最新行を外挿することはできない。

## 判断

Five-model Disagreementの研究上のbalanced confidence candidateは維持するが、**runtime parityは未達のまま保留**とする。3 sourceを欠いた2-model近似は別候補になり、履歴上の5-model根拠を再現しないため作らない。runtime parityだけを目的とした不要な再学習も行わない。

authoritative direction/confidence、fair odds、registry、paper/live policyは変更しない。固定3 model artifactが将来安全に復元された場合だけ、同じ等重み・0.515でparityを再開する。

## 検証

- configの5 source pathと`experiments/next_bar`のdirectory/model実在を照合
- runtime/account/credential変更なし
- shared high-load process停止なし
