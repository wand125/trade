# 00085 M1 Volatility Regime Candidate Router

日時: 2026-08-11 JST

## 目的

M1の固定方向候補を常に一つ使う代わりに、判定時点で既知のvolatility regimeごとに候補を切り替えると、既存候補への増分edgeが得られるか検証した。候補はPath Persistence 25%、Volatility State 25%、Session Relative 25%、Extra Trees 25%、standalone LightGBMの5つに事前限定した。

## 方法と品質

baseline OOSに保存されたfold別train分位点由来の `volatility_regime = low / normal / high` だけをrouting contextに使った。生価格水準、未来足、confirmationの正解は固定ruleの選択に使っていない。

二つの選択方式を実装した。

- fixed development: test2020〜test2023の各regime方向accuracyが最大の候補を一度選び、test2024〜2026途中へ固定する。
- chronological prior-OOS: 最初のfoldをPath fallbackとして評価から除き、以後は各foldより前の累積OOSだけでregime別winnerを更新する。

入力のfold/timestamp/target/regime完全整列、確率の有限 `[0, 1]`、全regimeの完全被覆、future fold変更が固定選択へ影響しないこと、chronological選択がprior foldだけを見ることをテストした。routing後はdirection、confidence、correctを確率から再生成し、元候補固有のensemble列を除去した。

## Fixed development router

開発期間の固定選択は次になった。

| regime | 選択候補 | development accuracy | 同regimeの次点 |
|---|---|---:|---:|
| low | LightGBM | 50.4549% | Extra Trees 50.4282% |
| normal | Path | 51.0520% | Volatility 51.0218% |
| high | Extra Trees | 51.4744% | Volatility 51.4591% |

| period | baseline | fixed router | Path | LightGBM |
|---|---:|---:|---:|---:|
| development accuracy | 50.9374% | 51.0011% | 50.9789% | 50.9579% |
| confirmation accuracy | 50.6000% | 50.6352% | 50.6457% | 50.6785% |
| all accuracy | 50.8069% | 50.8596% | 50.8501% | 50.8499% |

baseline比はdevelopment +853件、confirmation +297件、all +1,150件で、accuracy 6/7foldを改善した。UTC日paired bootstrap 20,000回ではrouter−baselineのaccuracy差95%区間がdevelopment +0.0216〜+0.1060pt、confirmation -0.0122〜+0.0829pt、all +0.0213〜+0.0842ptだった。all Brier/log lossも改善側であり、既存候補をregimeで組み合わせてもbaseline edgeを失わないことは確認できた。

しかし増分評価では、Pathにdevelopment +297件でもconfirmation -89件、all +208件に留まり、all accuracy差95%区間は-0.0184〜+0.0376ptだった。LightGBMにはdevelopment +578件でもconfirmation -366件、all +212件で、confirmation差区間は-0.0968〜+0.0106pt、allは-0.0211〜+0.0410ptといずれも0を跨いだ。routerのall proper scoreはPathより良いが、Session/Volatilityの既存確率品質役割を超えず、LightGBMとの差も未確定である。

## Chronological prior-OOS router

最初のtest2020を除くnested 1,838,693行では、router accuracy 50.6947%、Path 50.7118%、LightGBM 50.7227%だった。confirmationではrouter 50.6241%、Path 50.6457%、LightGBM 50.6785%である。

過去winner追随は低volatilityでSessionとLightGBM、高volatilityでExtra TreesからVolatilityへ切り替わったが、次foldの変化を安定して先取りしなかった。固定routerより厳しい時系列選択でも既存単体候補への増分edgeは再現しない。

## Confidence 0.515

fixed routerは全期間coverage 21.731%、accuracy 52.0897%、selection score 0.009079だった。TCNはcoverage 18.897%、accuracy 52.3027%、score 0.009348で、TCNがaccuracy・scoreとも7/7fold勝った。

router−TCNのaccuracy差95%区間はdevelopment -0.2583〜-0.0825pt、confirmation -0.7088〜-0.2774pt、all -0.2957〜-0.1329ptだった。routerはcoverageを全期間+2.834pt広げるが、その代償となる精度低下が明確で、Brier/log lossもTCNより悪い。confidence・fair oddsには使わない。

## 判断

不採用。volatility regime別routingはbaselineに対する既存候補のedgeを維持するが、開発期間で選んだセルwinnerが確認期間のPath/LightGBMを上積みせず、prior-OOS更新も平均回帰に負けた。候補pool自体が同じ履歴で研究された後に確定しているため、全期間の高い点推定を新しい独立edgeとは解釈しない。

実装、固定予測、chronological予測、直接比較、bootstrapは再現・安定性監査用に残す。regime境界、候補subset、selection metric、時間帯とのcross cell、weight、confidence閾値をこの履歴へ合わせて再探索しない。forward config、candidate registry、latest runtime、odds calibration、売買policyは変更しない。

## 成果物

- implementation: `src/trade_data/next_bar_regime_router.py`
- CLI: `methods/next_bar/scripts/regime_candidate_router.py`
- predictions/report: `experiments/next_bar/regime_candidate_router_m1_001`
- baseline comparison/bootstrap: `experiments/next_bar/regime_router_vs_baseline_m1_direction_analysis.json`, `experiments/next_bar/regime_router_vs_baseline_m1_direction_bootstrap.json`
- Path comparison/bootstrap: `experiments/next_bar/regime_router_vs_path_m1_direction_analysis.json`, `experiments/next_bar/regime_router_vs_path_m1_direction_bootstrap.json`
- LightGBM comparison/bootstrap: `experiments/next_bar/regime_router_vs_lightgbm_m1_direction_analysis.json`, `experiments/next_bar/regime_router_vs_lightgbm_m1_direction_bootstrap.json`
- TCN comparison/bootstrap: `experiments/next_bar/regime_router_vs_tcn_m1_confidence_0515_analysis.json`, `experiments/next_bar/regime_router_vs_tcn_m1_confidence_0515_bootstrap.json`
