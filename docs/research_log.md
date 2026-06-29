# Research Log

時系列の作業記録。判断、実験、失敗、次の行動を追記する。

## 2026-06-29 JST

### 19:12 Dense holding OOF smoke

- `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined_dense_holding/` に2023-01..2025-08の32ヶ月datasetを新schemaで生成した。
- 全32ヶ月でrows `899,408`、新target列の欠損は0。60分beat rateはlong `0.4786`, short `0.5536`。
- 全 `policy` target-setで2024-11..2025-04のHGB OOFを試したが、fold 0だけで多数targetを順にfitし7分超になったため中断。新target診断には重すぎる。
- `target-set holding_shortening` を追加し、exit-event adjusted PnL、fixed-vs-event delta、fixed-vs-event beat labelだけを学習できるようにした。
- 2025-02..2025-04、`sample-frac=0.2`, `max_iter=40` のOOF smokeでは、delta回帰R2は概ね `-0.026..0.015`、beat分類balanced accuracyは `0.5214..0.5430`。
- 判断: 連続deltaを直接policyへ使うには弱い。beat probability、bucket化、regime別calibration、candidate/ranking特徴として試す。
- report updated: `docs/reports/00160_2026-06-29_dense_holding_shortening_targets.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 18:45 Dense holding shortening targets

- `00159` の直接cap診断を、全decision rowで学べるdense targetへ拡張した。
- `src/trade_data/dataset.py` に `long/short_exit_event_raw_pnl`, `long/short_exit_event_adjusted_pnl`, `long/short_fixed_60m/240m/720m_minus_exit_event_adjusted_pnl`, `long/short_fixed_60m/240m/720m_beats_exit_event` を追加した。
- `src/trade_data/modeling.py` の `policy` / `full` target-setへ、exit-event adjusted PnLとfixed-vs-event deltaを回帰target、beat labelを分類targetとして追加した。`prediction_frame` にも実測列を残す。
- 2025-08 smoke datasetを `data/processed/datasets/xauusd_m1_dense_holding_target_smoke/` へ生成し、rows `28,971`、新targetは全行非欠損。60分beat rateはlong `0.5032`, short `0.5530`。
- `python3 -m unittest tests.test_dataset tests.test_modeling` と `python3 -m py_compile src/trade_data/dataset.py src/trade_data/modeling.py` はOK。
- 判断: これはpolicy改善確認ではなくschema/teacher target実装。次は主dataset再生成、chronological OOF、holding policyへの接続で検証する。
- report: `docs/reports/00160_2026-06-29_dense_holding_shortening_targets.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 18:06 Holding risk overlay

- `scripts/experiments/holding_risk_overlay.py` を追加し、`pred_hit_actual_miss_prob * q75 high-overestimate prob` をentry riskではなくMLP予測保有時間capとして使えるようにした。
- thresholdはchronological q75 OOFの2025-02..2025-04から固定し、2025-05/06/07へは再探索なしで適用する形にした。
- both-side capでは `q0.75 cap60 risk0` がmax DDを `259.0392 -> 145.4232` に縮めたが、long側まで壊してtotalは `222.1276 -> 200.8008` に落ちた。
- short-onlyに限定すると、2025-02..2025-06で `short-only q0.75 cap60 risk0` が total `314.7458`, min month `-47.5324`, max DD `145.4232` となり、risk0 `222.1276 / -61.3708 / 259.0392` とbaseline risk5 `203.3466 / -48.2052 / 224.7524` を上回った。
- 2025-07固定適用でも小幅に改善し、risk0は `-9.4002 -> -0.8914`、risk5は `8.2858 -> 16.7946`。ただしshort active率は `6.75%` と低く、改善幅は小さい。
- delta診断では2025-04 `common short/range_normal_vol` が `-77.8268 -> +30.0540` へ改善した一方、2025-02/03では追加short損失が出た。2025-07でも `common short/up_low_vol` は悪化している。
- 判断: `short-only q0.75 cap60` は固定候補に昇格するが、標準採用はまだしない。次は2025-08固定、またはshort context filterで `range_low_vol/range_normal_vol` に絞る。
- report: `docs/reports/00157_2026-06-29_holding_risk_overlay.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 17:43 Predhit overestimate fixed 2025-06

- `00155` の固定候補 `predhit_q75_w4` / `w6` を再探索なしで未使用月2025-06へ適用した。
- 既存2025-06 blind artifactは旧schemaで現行policyの補助列が揃わなかったため、2025-05固定確認と同じ設定で2025-06 dataset、HGB、MLP、hybrid、stateful risk、failure probability、trade quality、q75 high-overestimateを作り直した。
- 2025-06 highcost評価では risk0 `120.5302`, baseline risk5 `111.4464`, `predhit_q75_w4` `105.8618`, `predhit_q75_w6` `102.0418`。q75 interactionはbaseline risk5を下回った。
- `predhit_evhigh` interactionはw4/w6ともbaselineと同一で、risk scaleが小さすぎる。
- delta診断では、q75 w4/w6とも baseline側の良い `only_base short/range_normal_vol +25.6700` を落とし、追加分で完全には取り返せなかった。`only_candidate long/up_low_vol -3.9156` も悪化に寄与した。
- 判断: `predhit_q75_w4` / `w6` は固定候補から降格し、標準policyへ採用しない。q75 high-overestimateは直接risk penaltyではなく、exit timing calibration / EV過大評価校正 / selected trade診断特徴として残す。
- report: `docs/reports/00156_2026-06-29_predhit_overestimate_fixed_2025_06.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 17:28 Predhit overestimate interaction

- `scripts/experiments/predhit_overestimate_interaction.py` を追加し、chronological q75 high-overestimate予測と2025-05 apply予測を結合して、`pred_hit_actual_miss_prob` とのinteraction riskを作れるようにした。
- 初回は評価月の `dataset_month` だけへpredictionを絞ってしまい、post期間のシグナルが標準 `model-policy` CLIと不一致になった。修正後は統合prediction frame全体を各月評価へ渡し、CLI単発結果と一致することを確認した。
- 2025-02..2025-05 highcost固定評価では、`predhit_evhigh` interactionはほぼbaseline同等。`predhit_q75` は効くがweight感度が大きい。
- fine gridでは `predhit_q75_w4` が total PnL `107.2486`, min month `-22.9762`, max monthly DD `233.5124`, trades `386`。risk0は `101.5974 / -61.3708 / 259.0392 / 408`、baseline risk5は `91.9002 / -48.2052 / 224.7524 / 386`。
- ただし `w3=80.5836`, `w5=97.4686`, `w8=62.9580` と周辺が安定せず、安定した台地ではない。標準採用せず、`w4` / `w6` を固定候補として未使用月・別walk-forwardへ再探索なしで適用する。
- 2025-05改善はcommon `long/down_low_vol` の損失が `-117.9480 -> -94.0680` へ縮んだことが主因。2025-04悪化は `only_base long/down_high_vol +8.7600` と `only_base short/range_normal_vol +7.0000` を落としたことが主因。
- report: `docs/reports/00155_2026-06-29_predhit_overestimate_interaction.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 16:19 Trade overestimate scale diagnostics

- `trade-overestimate-scale-diagnostics` を追加し、chronological overestimate modelのfit側target分布、holdout selected trade予測、全prediction行のthreshold発火率を診断できるようにした。
- q90診断では、selected targetがfit q90を超えるtradeは36件あるが、selected prediction > fit q90は0件、全side prediction行でも0件。median selected pred max / fit q90 は `0.4428`、median prediction max / fit q90 は `0.5491`。
- q75診断では、selected target >= fit q75が79件、selected prediction > fit q75が12件、全side prediction行では13093件発火。q75なら発火するが捕捉は弱く、short側は全foldでselected prediction > fit q75が0件。
- fold-local q75 threshold + lambda `2.0` をpolicy接続したが、2025-02..2025-04 totalは baseline `154.6374` に対して `135.9620`、delta `-18.6754`。2025-02で良いlongを落とし、悪いshortを追加した。
- 判断: q90は発火せず、q75は発火するが悪化。thresholdを下げるだけでは解決しない。次はhigh-overestimate分類、side別calibration、stateful/context downside targetとの統合へ進む。
- report: `docs/reports/00151_2026-06-29_trade_overestimate_scale_diagnostics.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 16:05 Trade overestimate chronological q90 check

- `oof-trade-overestimate-model` に `--oof-scheme expanding` と `--min-train-months` を追加し、対象月より前だけでfitするchronological OOFを実行した。
- `min_train_months=3` により2025-02..2025-04を評価。chronological OOFは target mean `5.3943`, predicted mean `4.3290`, R2 `0.0145`, high-overestimate AUC `0.6328`。leave-one-monthの R2 `0.1273` から大きく落ちた。
- `00148` の固定threshold long `18.8171`, short `21.1886`, lambda `2.0` を再調整せず適用したところ、chronological prediction maxは long `7.1065`, short `7.8064` で、active rowsは `0 / 85361`。
- 2025-02..2025-04のbacktestはbaselineと完全同一。total PnLは baseline `154.6374`, leave-one-month q90 `165.9728`, chronological q90 `154.6374`。`model-trade-delta` でもonly_base/only_candidateは0。
- fit側selected-trade target q90も long `10.9981..12.8793`, short `13.3550..13.5405` でprediction maxより高く、q90方式では発火しない。問題はthreshold参照元だけでなく、chronological fit時のamount prediction scaleが低く潰れる点。
- report: `docs/reports/00150_2026-06-29_trade_overestimate_chronological_q90_check.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 15:49 Trade overestimate q90 delta diagnostics

- `q90 w2.0` とbaseline stateful risk5を `model-trade-delta` で比較した。
- validation 2024-11..2025-04では base `407.8172`, candidate `460.6640`, delta `+52.8468`。2025-03だけ `-0.9926` と小幅悪化し、他5ヶ月は改善。
- 2025-05では base `-52.9764`, candidate `25.5248`, delta `+78.5012`。ただし改善の主因は only_base の悪いtrade除外 `+158.6046` で、only_candidateは `-92.9324` と大きく悪化。
- group driftでは、validationで良かった `only_candidate short/up_normal_vol` が `+109.0090 -> -93.7270` に反転。statefulでも `common long/down_low_vol` が `+33.7666 -> -106.9060` に反転した。
- `model-trade-delta-preflight` はPnL条件ではpassしたが、group drift validation-positive/holdout-negativeが3件、stateful group driftが2件。q90 w2.0は固定候補に残すが、標準policyへ即採用しない。
- report: `docs/reports/00149_2026-06-29_trade_overestimate_q90_delta_diagnostics.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 15:39 Trade overestimate amount model

- `pred_taken_ev - adjusted_pnl` の正の部分を `trade_overestimate_target_amount` とする `oof-trade-overestimate-model` を追加した。
- highcost risk5 2024-11..2025-04 selected trades 502件のOOFでは、target mean `18.2772`, predicted mean `17.7814`, MAE `8.3937`, RMSE `11.6532`, R2 `0.1273`, high-overestimate AUC `0.6814`。selected-trade quality回帰よりrank signalが強い。
- amount全体を直接penaltyする方式はbaseline `407.8172` を下回った。lambda `0.005` でも `385.1526`、`0.05` は `314.3812`。平均水準を引いて良いtradeも落とすため不採用。
- validation OOF prediction分布のq90超過分だけをpenaltyする方式は改善した。`q90 w2.0` はvalidation合計 `460.6640`, trades `529`, min month `-2.3046`, max DD `204.8324` でbaseline `407.8172 / 502 / -16.9006 / 224.7524` を上回った。
- 2025-05固定適用では、baseline stateful risk5 `-52.9764` に対して `q90 w2.0` が `+25.5248`, 106 trades, profit factor `1.0531`。max DDは `151.0632` でbaselineより悪化するため、即標準化ではなく固定候補として次月・delta診断へ進める。
- report: `docs/reports/00148_2026-06-29_trade_overestimate_amount_model.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 15:17 Quality secondary tiebreak validation

- failure-prob quality scoreを `secondary_score_tie_margin` でnear-tie side選択だけに使った。raw EV、entry threshold、stateful risk5、MLP holding guardは固定。
- highcost risk5 OOF validation 2024-11..2025-04では、baseline total PnL `407.8172`、margin 5は完全同一、margin 10は `154.2024`、margin 20は `-84.8690`。
- margin 10は2025-04を `14.3072 -> 105.1364` に改善したが、2025-03を `27.1660 -> -156.0008` へ壊した。margin 20は2024-11を `129.9968 -> -212.8968` へ壊した。
- 判断: quality secondary tiebreakは採用しない。2025-05固定適用も行わない。次はside反転ではなく、同一side内ranking、EV overestimate residual、連続/分位targetへ進む。
- report: `docs/reports/00147_2026-06-29_quality_secondary_tiebreak_validation.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 15:09 Failure probability quality feature

- `pred_trade_failure_*_{long,short}_prob` をtrade quality modelのoptional side featureとして使えるようにした。selected side視点で `pred_taken_*`, `pred_opposite_*`, `*_gap` を作る。
- `enrich_trades_for_trade_quality` がfailure probability列をselected tradesへ保持できるように、analysis prediction columnsにも追加した。
- highcost risk5の2024-11..2025-04 OOF qualityでは、failure-prob feature入りが calibrated bias `0.2061`, overestimate mean `4.4255`, MAE `8.6450`。baseline qualityは `0.2806`, `4.4680`, `8.6555`。微改善だが、RMSE/R2は改善しない。
- 2025-05 policyでは `min_trade_quality=0.5` がbaseline quality `-92.2498`, failure-prob quality `-101.9736` と悪化。failure-prob quality `1.0` は `-124.0614` でさらに悪い。
- 判断: failure probabilityをEV校正featureとして使う配線は残すが、quality hard filterには採用しない。次はnear-tie ranking、EV overestimate residual、連続/分位targetへ進む。
- report: `docs/reports/00146_2026-06-29_failure_probability_quality_feature.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 14:58 Pred-hit actual-miss failure target

- `oof-trade-failure-model` に `pred_hit_actual_miss` と `ev_overestimate_high` targetを追加し、side confidence系の特徴量 `pred_taken_side_confidence`, `pred_opposite_side_confidence`, `pred_side_confidence_gap` をselected trade failure modelへ入れた。
- 2024-11..2025-04のselected trades 502件で、`pred_hit_actual_miss` は prevalence `0.0717`, predicted mean `0.0687`, AUC `0.9626`。ただしtarget定義がprofit-barrier予測列を条件にするため、AUCは過大評価しない。
- 2025-05 highcostでは `failure only risk10` が adjusted PnL `-52.9764 -> -7.1330` へ改善したが、max DDは `137.4392 -> 147.1096` へ悪化した。
- OOF validation 2024-11..2025-04へ戻すと、baseline stateful risk5 は PnL `407.8172`、`failure only risk10` は `325.8466`、`stateful + predhit w1` は `240.9596`。単月改善は採用条件を満たさない。
- 判断: `pred_hit_actual_miss` 実装は残すが、今回のrisk penaltyを標準policyへ採用しない。次はrisk hard penaltyではなく、exit timing / EV calibration / ranking featureとして使う。
- report: `docs/reports/00145_2026-06-29_pred_hit_actual_miss_failure_target.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 14:38 Selected trade exit/EV/confidence diagnostics

- `model-trade-exposure-diagnostics` を追加した。selected tradesを、side gap、side confidence、予測保有時間、profit barrier predicted/actual、EV過大評価、exit regretのbucketで集計できる。
- 2025-05 highcost risk5では、`long/down_low_vol/london` が3 tradesで `-87.6396`、`short/up_normal_vol/asia` が13 tradesで `-56.7420`、`short/up_normal_vol/london` が8 tradesで `-54.5500`。
- `short/up_normal_vol/london` はside gap mean `14.6367`、side confidence mean `0.6674`、predicted profit-barrier hit rate `1.0000` だが actual hit rate `0.3750`。低confidenceではなく、profit-barrier / EV overestimate / exit timingの過大評価が主因。
- side confidence hard screenでは `min_side_confidence=0.75` が7ヶ月highcost minを `-12.2140` に縮めるが、22 tradesしか残らない。`0.60` は2025-04を壊すため採用しない。
- 判断: side confidenceはhard gateではなくinteraction featureに留める。次は `pred_hit_actual_miss`, `ev_overestimate_vs_realized`, `exit_regret`, `holding_ratio_actual_vs_pred` をchronological OOFのtarget/featureへ戻す。
- report: `docs/reports/00144_2026-06-29_selected_trade_exit_ev_confidence_diagnostics.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 14:23 Prior context floor risk target

- `oof-stateful-risk-model` に `walkforward_prior_floor_nonpositive` と `walkforward_prior_floor_lowered` を追加し、`target_walkforward_prior_context_mean_floor` を分類targetとして使えるようにした。
- prior floor列入りのstateful examplesを再生成した。session contextでは1544例中322件がall-prior loss flagで、`target_walkforward_prior_context_mean_floor` meanは `-2.1393`。
- `00140` と同じHGB/expanding/mean_match設定では、`walkforward_floor_lowered` AUC `0.6371`、`walkforward_prior_floor_lowered` AUC `0.6063`、`walkforward_prior_floor_nonpositive` AUC `0.6240`。prior targetはbiasが小さいが、rankでは既存floorを上回らない。
- 2025-05 quick screenでは、base/highcostとも既存 `floor_lowered risk=5` が最良。`prior_nonpositive risk=5` はbase `-109.5876`、highcost `-171.5662` と悪化した。
- 2024-11..2025-05の7ヶ月でも、`prior_lowered risk=5` はbase total `491.7438`、highcost total `278.3902` で、既存 `floor_lowered risk=5` のbase `567.7900`、highcost `354.8408` に負けた。
- 判断: prior floorは単独risk penaltyには採用しない。`prior_floor_nonpositive` はEV calibration / ranking feature候補として残し、残存損失はexit timing / EV overestimate / side-confidence interactionへ戻す。
- report: `docs/reports/00143_2026-06-29_prior_context_floor_risk_target.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 13:16 Selected trade walk-forward context

- `model-trade-context-walkforward-stress` を追加した。model-policyのselected tradesを対象に、対象月より前の月だけでcontext stressとall-prior context floorを作る。
- 追加列は `walkforward_prior_context_target_mean`, `walkforward_prior_context_loss_flag`, `target_walkforward_prior_context_mean_floor`。validation-positive / holdout-negative反転だけでなく、過去から一貫して弱い文脈をfuture-safeに拾う。
- `risk=5` 固定runを2024-11..2025-05で再生成した。2025-05 highcostの未解決損失は `long:down_low_vol` `-117.9480` と `short:up_normal_vol` `-100.9936` が中心。
- 広い文脈では `long:down_low_vol` と `short:up_normal_vol` は過去月だけのstressで捕捉できる。session分解では `long:down_low_vol:london` がprior support 11, mean `-9.2242`、`short:up_normal_vol:asia` がprior support 15, mean `-3.3029` でall-prior loss flagに入る。
- ただし `short:up_normal_vol:london` は2025-05で大きく負けたが過去平均は正。contextだけでは捕捉しにくいため、exit timing / EV calibration / higher-order feature側へ戻す。
- docs運用として、OSのmtimeが逆でもレポート本文の `日時` を採番・最新判断に使うテストを追加した。`更新日時` も採番には使わない。
- 判断: hard blockにはしない。`target_walkforward_context_stress_adjusted` と `target_walkforward_prior_context_mean_floor` をdownside分類・EV校正・ranking featureへ戻す。
- report: `docs/reports/00142_2026-06-29_selected_trade_walkforward_context.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 12:36 Stateful downside mean-match 2025-05 fixed

- `00140` で事前登録candidateにした `mean_match + session_floor_lowered risk=5` を、同じ6ヶ月内で追加調整せず、2025-05へ固定適用した。
- 2025-05の同一形式dataset / HGB entry-side / MLP exit / forced predictionを生成した。HGB best-side balanced accuracyは `0.4571`、selected side accuracyは `0.4924`。MLP exit minutes R2はlong `0.1177`, short `0.1361` だが、holding中央値はlong `-82.44`, short `-76.93` で、`min_valid_predicted_hold_minutes=30` のfail-close guard頼みが続く。
- 固定policyでは、baseが `risk0=13.9990 -> risk5=25.3104`、highcostが `risk0=-66.1420 -> risk5=-52.9764`。防御方向には働いたが、highcostはNoTrade未満で、`00140` のcost min基準 `>= -20` を満たさない。
- trade deltaでは改善が少数の入れ替えに依存し、common tradeには `long:down_low_vol` と `short:up_normal_vol` の大きな損失が残った。risk=5後のstateful target meanもhighcostでは `-0.6984` と負。
- 判断: `risk=5` は標準policyへ採用しない。candidate ranking / diagnostic featureへ降格寄りに扱い、同じ2025-05上でrisk閾値を追加最適化しない。
- report: `docs/reports/00141_2026-06-29_stateful_downside_mean_match_2025_05_fixed.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 12:23 Stateful downside mean-match risk budget

- `oof-stateful-risk-model` に `--probability-calibration none|mean_match` を追加した。`mean_match` はlogit interceptだけをずらして、scored foldの平均probabilityをfit側target prevalenceへ合わせる。fold内順位は保つがfold間スケールは変わるため、OOF全体AUCは動き得る。
- `session_floor_lowered` のexpanding OOFでは predicted mean が `0.1051 -> 0.1214`、biasが `-0.1703 -> -0.1540`、Brierが `0.2181 -> 0.2129` に改善した。一方、AUCは `0.6473 -> 0.6371` に低下した。
- 6ヶ月policy接続では `risk=5` がbase合計をほぼ維持しつつ最悪月を `-18.7168 -> +8.0868` に改善し、high costも合計 `391.2374 -> 407.8172`、最悪月 `-34.3748 -> -16.9006`、max DD `259.0392 -> 224.7524` に改善した。
- candidate selectionでは `risk=5` だけがbase/high cost条件を通過した。ただし同じ6ヶ月診断セット上で選んだため標準採用はせず、次の未使用月で固定確認する事前登録candidateにする。
- report: `docs/reports/00140_2026-06-29_stateful_downside_mean_match_risk_budget.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 12:11 Stateful downside risk policy

- `oof-stateful-risk-model` に `--oof-scheme` / `--min-train-months` を追加し、walk-forward stress/floor由来の分類targetを追加した。
- expanding OOFでは、available `walkforward_stress_flag` AUC `0.6512`、session `walkforward_floor_lowered` AUC `0.6473`。stateful value回帰よりrank signalはあるが、predicted meanがprevalenceを大きく下回りcalibrationは弱い。
- 6ヶ月policy接続では、`session_floor_lowered risk=10` がbase最悪月を `-18.7168 -> +8.0320`、high cost最悪月を `-34.3748 -> -20.8080` へ改善した。一方でbase合計PnLは `543.9972 -> 422.1416`、high cost合計は `391.2374 -> 311.0372` へ低下した。
- 判断: `session_floor_lowered` は防御signalとして残すが、標準policyには採用しない。risk budget / drawdown-aware ranking / candidate selectionの補助特徴として扱い、calibrationと追加月再現性を確認する。
- report: `docs/reports/00139_2026-06-29_stateful_downside_risk_policy.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 11:56 Stateful value walk-forward target comparison

- `oof-stateful-value-model` に `--oof-scheme leave_one_month|expanding` と `--min-train-months` を追加した。expandingでは対象月より前の月だけでfitし、学習月不足のfoldは `fold_plan` に `skipped` として残す。
- `00137` のwalk-forward stress targetをstateful value modelの教師候補として比較した。leave-one-monthではbase targetだけR2 `+0.0052` だったが、chronologicalなexpandingではbase targetもR2 `-0.0113`、bias `+1.5287` へ悪化した。
- available/session floor targetはMAE/RMSEを下げるが、targetを保守的に落とした効果が大きく、expandingではavailable floor R2 `-0.0945`, bias `+4.1365`、session floor R2 `-0.0498`, bias `+3.1195`。EV replacementには使えない。
- 判断: walk-forward stress/floor targetは現時点でpolicyへ直接gate/EV置換しない。下方リスク分類、support-aware calibration、追加月でのchronological OOF診断に回す。
- report: `docs/reports/00138_2026-06-29_stateful_value_walkforward_target_comparison.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 11:42 Stateful walk-forward stress target

- `stateful-examples-walkforward-stress` を追加した。対象月より前の月だけを使い、直前月をpseudo holdout、それ以前をpseudo validationとしてcontext stress profileを作る。
- 出力列は `walkforward_context_stress_flag`, `walkforward_context_stress_penalty`, `target_walkforward_context_stress_adjusted`, `target_walkforward_context_holdout_mean_floor`。事後holdout監査列と区別するため `walkforward_` prefixにした。
- available contextはsupport `20/10` で1544例中397例がstress flag、penalty mean `1.8977`、target mean `+0.6154`、stress-adjusted mean `-1.2823`。
- session contextはsupport `10/5` で1544例中208例がstress flag、penalty mean `1.3989`、stress-adjusted mean `-0.7835`。
- 2025-03/04でpenaltyが強く出た。availableでは2025-03の `short/up_normal_vol`, `long/up_low_vol`, `short/range_normal_vol`, `short/down_normal_vol` が大きく、sessionでは2025-03の `long/up_low_vol/london`, `short/down_normal_vol/london`, `short/range_normal_vol/london` が目立つ。
- 判断: これは対象月より未来を見ないので、次のstateful value modelのtarget候補にできる。ただし月数はまだ8ヶ月で少ないため、まずtarget比較・OOF診断に使い、policyへの直接gate化はしない。
- report: `docs/reports/00137_2026-06-29_stateful_walkforward_stress_target.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 11:30 Stateful context stress target

- `stateful-examples-drift` の `combined_stateful_examples.csv` にstress-aware target監査列を追加した。
- 追加列は `context_stress_flag`, `context_stress_penalty`, `target_context_stress_adjusted`, `target_context_holdout_mean_floor`。flagはvalidation meanが正でholdout meanが負に反転したcontext、penaltyは `validation_target_mean - holdout_target_mean` の正の部分。
- available contextでは1544例中1083例がstress flag、penalty mean `3.6772`、target mean `+0.6154`、stress-adjusted mean `-3.0618`。
- session contextでは1544例中387例がstress flag、penalty mean `2.7589`、stress-adjusted mean `-2.1435`。
- 判断: これはholdoutを見た事後監査列なので、そのままlive学習targetにはしない。次はwalk-forwardで過去foldだけからstress penaltyを作り、OOF stateful modelへ使えるtargetに落とす。
- report: `docs/reports/00136_2026-06-29_stateful_context_stress_target.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 11:23 Stateful examples drift

- `stateful-examples-drift` を追加した。複数の `stateful_candidate_examples.csv` をvalidation/holdoutに分け、context別のtarget sum/mean、downside率、raw EV過大評価、validation-positive/holdout-negative反転を出す。
- guard validation/highcost + stack0 validation と guard apply/highcost + stack0 smoke をまとめ、1544例で診断した。
- `candidate_side + combined_regime` では15group中6groupがmean/sumとも反転。主な反転は `short/range_normal_vol` `+501.7660 -> -298.2216`, `long/down_low_vol` `+358.3530 -> -234.8292`, `short/down_normal_vol` `+303.8836 -> -19.4788`。
- `session_regime` も加えると52group中10groupが反転し、`long/up_low_vol:london` `+254.3226 -> -284.4936`, `short/range_normal_vol:rollover` `+125.9528 -> -227.1028` が目立つ。
- 判断: これはhard ruleにしない。validation内でよく見える文脈がholdout/stressで反転することを、stress-aware target / 追加walk-forward / candidate採用前監査に使う。
- report: `docs/reports/00135_2026-06-29_stateful_examples_drift.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 11:17 Available-context drift

- `model-trade-delta-preflight` に `direction + combined_regime` だけのavailable-context drift出力を追加した。`delta_status=only_candidate` は比較後に分かる情報なので、live特徴へ直接入れない。
- `model-trade-delta-drift-stability` もavailable-context版を集計し、`flip_stability_available_pnl*.csv` / `flip_stability_available_stateful*.csv` と月別supportを出すようにした。
- guard top / stack0の再実行では、通常PnLの共通available flipは `short/down_normal_vol` 1件、statefulの共通available flipは `long/down_low_vol`, `long/up_normal_vol` 2件。
- stateful OOF context reportでは、`short/down_normal_vol` はsupport 15, target mean `+4.7383`、`long/down_low_vol` はsupport 66, target mean `+2.1228`。既存validation OOFだけでは、これらを悪い文脈として学べていない。
- 判断: available contextは診断として有効だが、単純な教師特徴追加やhard gateでは不足。次は追加walk-forwardでexamplesを増やし、stress-aware targetやregime driftを学習・評価設計へ戻す。
- report: `docs/reports/00134_2026-06-29_available_context_drift.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 11:07 Drift stability monthly support

- `model-trade-delta-drift-stability` に、共通flip groupを元deltaの月別group CSVへ戻すsupport出力を追加した。
- 出力は `flip_stability_pnl_monthly_support.csv`, `flip_stability_pnl_monthly_support_summary.csv`, `flip_stability_stateful_monthly_support.csv`, `flip_stability_stateful_monthly_support_summary.csv`。
- guard top / stack0 の共通flipに対し、通常PnL supportは49行、stateful supportは99行。`only_candidate long down_low_vol` はguard topでvalidation 4ヶ月/holdout 3ヶ月、stack0でvalidation 3ヶ月/holdout 2ヶ月に出ており、単月だけの偶然ではない。
- 一方、validation側にも負の月が混じる。たとえばguard topの `only_candidate long down_low_vol` はvalidation合計 `+84.3218` だが負月2、holdout合計 `-93.4838` で負月2。hard blockではなくsupport-aware downside / stateful risk特徴として扱う。
- 判断: 共通flip groupは「候補が追加する取引の危険な文脈」として教師/特徴へ戻す。次は、予測時点で見える `direction + combined_regime + candidate_added_context` をOOF examplesへ結合し、hard ruleではなくdownside targetで評価する。
- report: `docs/reports/00133_2026-06-29_drift_stability_monthly_support.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 11:01 Model trade delta drift stability

- `model-trade-delta-drift-stability` を追加した。複数のpreflight runから、validation-positive / holdout-negativeになったgroupが何回繰り返したかを集計する。
- guard top比較とstack0比較の2つを対象にした。通常PnLのcommon flip groupは3件、stateful netのcommon flip groupは6件。
- 通常PnLで共通反転したのは `only_candidate long down_low_vol`, `only_candidate short down_normal_vol`, `only_candidate short up_normal_vol`。合計ではそれぞれ validation `+223.8686`, `+52.0400`, `+49.9340` に対し、holdout `-159.6508`, `-101.0994`, `-36.5278`。
- statefulでは `only_candidate long down_low_vol`, `only_candidate long up_low_vol`, `only_candidate short down_normal_vol`, `only_candidate short up_normal_vol` など6件が共通反転した。
- 判断: これらはhard block候補ではなく、regime drift / downside / stateful opportunity-cost特徴として扱う。次は共通flip groupを教師特徴へ戻す前に、月単位supportと予測時点で利用可能な情報だけで表現できるかを確認する。
- report: `docs/reports/00132_2026-06-29_model_trade_delta_drift_stability.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 10:54 Model trade delta preflight group drift

- `model-trade-delta-preflight` にstatus/direction/combined_regime別のdrift出力を追加した。
- 通常PnL用に `group_drift_status_direction_combined_regime.csv`、stateful blocking用に `stateful_group_drift_status_direction_combined_regime.csv` を出力する。validationでプラス、holdoutでマイナスになったgroupをflag化する。
- 標準候補 vs validation top候補では、通常PnLのvalidation-positive/holdout-negative groupが10件、stateful groupも10件。`only_candidate long down_low_vol` は通常PnL `+84.3218 -> -93.4838`、stateful `+107.4676 -> -136.4816` に反転した。
- `only_candidate short down_normal_vol` は通常PnL `+25.4090 -> -91.0014`、stateful `+25.4090 -> -228.1214` に反転し、2025-02/04側の機会損失を強く示す。
- 判断: 次はこれらの反転groupを直接hard blockしない。先に追加walk-forwardで同じ反転groupが再現するかを確認し、OOF/downside/stateful target側に特徴として戻す。
- report: `docs/reports/00131_2026-06-29_model_trade_delta_preflight_group_drift.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 10:48 Model trade delta preflight audit

- `model-trade-delta-preflight` を追加した。複数の `model-trade-delta` runをvalidation/holdoutに分けて読み、case別に `pnl_delta_sum`, worst-month `pnl_delta`, worst-month `stateful_target` を集計する。
- デフォルトではvalidationは合計PnL delta非負を要求し、holdoutは合計PnL delta、月別最悪PnL delta、月別最悪stateful targetがすべて非負であることを要求する。stateful例がない場合は、有限閾値ではfailする。
- `00128` / `00129` の標準候補 vs validation top候補に適用したところ、validation 2件はpass、holdout/apply 2件はfail。preflight全体は `False` で、validation top候補を採用前に棄却できる。
- 出力先: `data/reports/backtests/20260629_014830_guard_fixed_entry_side_preflight/`
- 判断: 今後の候補採用前には、validation summaryだけでなく `model-trade-delta-preflight` のholdout passを確認する。これはpolicy変更ではなく、過適合候補を殺す検証フローの追加。
- report: `docs/reports/00130_2026-06-29_model_trade_delta_preflight.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 10:40 Model trade delta parent pairing

- `model-trade-delta` を候補採用前の標準診断にしやすくするため、複数月の `model-policy` runが入った親ディレクトリを直接比較できるようにした。
- 実装は親ディレクトリを展開し、各runの `config.json` 内 `backtest_config.evaluation_start` の月でbase/candidateをペアリングする。月の重複や不一致はfail-fastする。
- READMEにも、親ディレクトリ比較ではディレクトリ名やmtimeではなくrun内部の評価月で対応付けることを追記した。
- `00128` と同じ標準候補 vs validation top候補を親ディレクトリ指定だけで再実行し、validation base/high cost delta `+62.8970 / +86.4218`, apply base/high cost delta `-289.3090 / -290.4310` を再現した。
- 判断: `model-trade-delta` の親ディレクトリ比較を、候補採用前のstateful delta診断フローに使う。今回の変更は診断基盤の改善であり、trade policy自体は変更しない。
- report: `docs/reports/00129_2026-06-29_model_trade_delta_parent_pairing.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 10:33 Guard-fixed entry/side drift diagnostics

- `00127` のvalidation top候補と現行標準候補を、validation/apply x base/high costで固定 `model-policy` 実行し、`model-trade-exposure` と `model-trade-delta` でtrade-level差分を確認した。
- validationではtopが取引数を `275 -> 228` に減らし、base/high cost PnLを `+62.8970`, `+86.4218` 改善した。一方applyでは `377 -> 306` / `380 -> 308` に減らして、base/high cost PnLを `-289.3090`, `-290.4310` 悪化させた。
- base deltaでは、validation topは `only_candidate +359.4784` で `only_base +328.6498` の喪失を上回ったが、applyでは `only_base +261.9228` を捨て、`only_candidate` は `+19.6058` に留まった。high cost applyでは `only_candidate -26.6700` まで悪化した。
- top候補側のstateful target meanはvalidation baseで全月プラス (`1.8330`, `1.7054`, `2.8303`, `1.9971`) だが、apply baseでは `2025-02=-1.7983`, `2025-03=-0.1697`, `2025-04=-2.1726` と3/4ヶ月でマイナス化した。
- 2025-02のtop専用 `long:up_low_vol` は自身 `-42.9714` に加え、標準側 `+101.6036` をブロックし、stateful net `-144.5750`。一玉制約下の機会損失が主因。
- 判断: validation topは採用しない。entry threshold / short offset / side penaltyの追加grid探索は本流にしない。次はOOF calibration、stateful blocking / replacement regret target、より広いwalk-forwardへ戻る。
- report: `docs/reports/00128_2026-06-29_guard_fixed_entry_side_drift_diagnostics.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 10:23 Guard-fixed entry/side grid

- MLP holding auto guardを固定した状態で、entry threshold `10/12/14/16`, short offset `4/6/8`, side margin `3/5/7`, short low-vol penalty rule set `none/down5up10/down5up10range5/down10up10` の小gridをvalidation 4ヶ月で再評価した。
- `model-candidate-selection` はbase/high costとも4fold全通過、月10trades以上、forced rate `<=0.05`, DD `<=300`, 月次PnL `>0`, max side share `<=0.9` を要求した。144候補中82候補がeligible。
- validation topは `entry=14`, short offset `4`, side margin `5`, `short:down_low_vol:5,up_low_vol:10,range_low_vol:5`。validation base/high costは sum/min `685.5456 / 154.4590`, `586.9640 / 138.6648`。
- 現行標準 `entry=12`, short offset `6`, side margin `5`, `short:down_low_vol:5,up_low_vol:10` は validation base/high cost sum/min `622.6486 / 138.0338`, `500.5422 / 96.8776`。
- しかしvalidation topをapply 4ヶ月へ固定すると base sum/min `-42.4328 / -50.1562`, high cost sum/min `-157.7340 / -69.2394`。現行標準guard候補の apply base/high cost `246.8762 / -18.7168`, `132.6970 / -34.3748` を大きく下回った。
- 判断: guardは高回転破綻を止めるが、entry threshold / short offset / side penaltyのvalidation最適化はまだ外挿しない。validation top候補は標準採用しない。次はパラメータ探索を増やさず、OOF校正・downside feature・regime drift診断へ戻る。
- report: `docs/reports/00127_2026-06-29_guard_fixed_entry_side_grid.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 10:13 MLP holding auto guard CLI

- `00125` / ADR `0009` の標準安全制約をCLI defaultへ反映した。
- `model-policy` では `--min-valid-predicted-hold-minutes` 省略時、holding columnが `pred_mlp_*` なら `30`、それ以外なら従来通り `-inf` に解決する。
- `model-sweep` のdefaultは `auto` とし、同じ列名判定で1値に解決する。明示的な `-inf` や数値CSVはautoより優先する。
- `ModelPolicyConfig` のdataclass defaultは従来通り `-inf` のままにし、CLI標準だけを変えた。直接API利用や非MLP holding実験の互換性を保つため。
- 2025-04 smokeでは config に `min_valid_predicted_hold_minutes=30.0` が入り、前回の `skip min_valid=30` と同じ adjusted PnL `-18.7168`, trades `77`, max DD `249.9600`, forced `1` を再現した。
- 判断: MLP holdingを使う標準比較では、今後フラグを明示しなくてもfail-close guardが入る。従来clip-onlyを再現する場合だけ `--min-valid-predicted-hold-minutes -inf` を明示する。
- report: `docs/reports/00126_2026-06-29_mlp_holding_auto_guard_cli.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 10:05 Holding guard validation/apply

- `00124` の結論に沿って、stateful riskではなくMLP holding guard/fallbackを再評価した。
- validation 4ヶ月 (`2024-07`, `2024-09`, `2024-11`, `2025-01`) では、skip/fallback とも `min_valid=-inf/30/60/120` が完全に同じ。validation上はholding guardの優劣をPnLで選べない。
- apply 4ヶ月 (`2024-12`, `2025-02`, `2025-03`, `2025-04`) では、従来挙動が2025-04で異常高回転化し、base/high costとも大きく崩れた。`skip min_valid=30` はbase sum PnL `-261.3216 -> 246.8762`, high cost sum PnL `-1435.1746 -> 132.6970` に改善し、trade数を約2910件から約380件へ抑えた。
- `fallback` は損失を縮めるがskipより弱い。HGB holdingへ逃がすことで、壊れたMLP holding候補を取引として残してしまう。
- 判断: `min_valid_predicted_hold_minutes=30` の fail-close skip を、MLP holdingを使う `timed_ev` 実験の標準安全制約にする。ただしvalidation PnLで選ばれたedgeではなく、外挿破綻値を売買ルールへ渡さないための固定制約として扱う。
- report: `docs/reports/00125_2026-06-29_holding_guard_validation_apply.md`
- decision: `docs/decisions/0009_mlp_holding_fail_close_guard.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 09:53 Stateful blocking risk 2025-04 fixed check

- `00123` の事前登録候補 `positive_blocking risk=5` を、追加walk-forward月として 2025-04 に固定適用した。
- `oof-stateful-risk-model` を同じvalidation examples / 同じ設定で再実行し、`predictions_hgb_entry_mlp_exit_2025_04_forced.parquet` にstateful risk列を付与した。
- 2025-04結果は baseline `-503.8224`, risk `5` `-509.6742`, risk `10` `-494.0544`, risk `20` `-486.2782`。risk `5` は改善せず、risk `20` でもNoTradeには遠い。
- apply 4ヶ月合計では baseline sum/min/DD `-261.3216 / -503.8224 / 718.7252` に対し、risk `5` は `-310.6882 / -509.6742 / 729.0912`。
- 判断: `positive_blocking risk=5` は標準policyにも事前登録候補にも昇格しない。2025-04の主因はstateful entry riskではなく、MLP holding外挿による異常高回転なので、先にholding guard/fallbackを標準候補として再評価する。
- report: `docs/reports/00124_2026-06-29_stateful_blocking_risk_2025_04_fixed_check.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 09:48 Stateful blocking risk model

- `trade_data.meta_model oof-stateful-risk-model` を追加した。`stateful_candidate_examples.csv` から `positive_blocking`, `positive_replacement_regret_high`, `stateful_nonpositive` を月抜きOOF分類し、prediction parquetへ `pred_stateful_risk_<prefix>_<target>_<side>_prob/risk` を出力する。
- OOF metricsは `positive_blocking` AUC `0.4878`, `positive_replacement_regret_high` AUC `0.4869`, `stateful_nonpositive` AUC `0.4520`。probability平均のbiasは小さいが、rank能力は弱い。
- validation policy sweepでは `positive_blocking risk=5` がbaseline sum/min/DD `622.6486 / 138.0338 / 85.0166` を `675.7414 / 157.0628 / 74.7688` に改善した。
- `positive_replacement_regret_high risk=5` はsum `683.7320` だがmin month `91.4356` へ悪化し、`stateful_nonpositive` は取引を削りすぎた。
- apply 3ヶ月では `positive_blocking risk=5` が2024-12を `-20.8252 -> -3.5260` に改善した一方、2025-02/2025-03を削り、sum `242.5008 -> 198.9860`, maxDD `122.9852 -> 128.1944` に悪化した。
- 判断: stateful risk modelの実装は採用するが、標準policyのrisk penaltyにはまだ採用しない。`positive_blocking risk=5` は追加walk-forwardで固定評価する事前登録候補にする。
- report: `docs/reports/00123_2026-06-29_stateful_blocking_risk_model.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 09:30 Stateful near-tie local diagnostics

- `trade_data.meta_model stateful-near-tie-report` を追加した。`stateful_candidate_examples.csv` とside別secondary score入りprediction parquetをjoinし、primary EV near-tie内でsecondary scoreがtargetを順位付けできるかを診断する。
- validation examples 254件で `stateful_positive_cost_value` をtargetに診断。`min_primary_score=12` でもusable examplesは254件で変わらなかった。
- margin `20` では raw bias `14.7685` に対しsecondary bias `0.0853`、raw overestimate `15.6463` に対しsecondary overestimate `4.2896` まで縮む。一方、secondary target Spearmanは `-0.1327`。
- secondary top25 liftはmargin `20` で `+0.4830` だが、top-bottom25 spreadは `-1.2899`。margin `5/10/15/20` 全てでtop-bottom25 spreadは負。
- margin `20` のsecondary score bucketでは最高score bucket `q05` のtarget meanが `-0.1244` と最悪で、最低score bucket `q01` が `2.6477`。
- 判断: `stateful_positive_cost_value` meanは校正値として有用だが、ranking scoreとしては使わない。`00121` のtie-break悪化はscoreのrank能力不足と整合する。
- 次は追加月examplesでsupportを増やし、`blocking_cost` / `replacement_regret` を分類・下方リスクtargetとして扱う。
- report: `docs/reports/00122_2026-06-29_stateful_near_tie_local_diagnostics.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 09:22 Stateful secondary tie-break

- `model-policy` / `model-sweep` に `long_secondary_score_column`, `short_secondary_score_column`, `secondary_score_tie_margin(s)` を追加した。
- secondary scoreはprimary EV side gapが指定margin以下のときだけside選択に使う。entry thresholdとside marginはprimary EVのまま維持する。
- `stateful_positive_cost_value` meanをsecondaryにしたvalidation 4ヶ月では、baseline `sum=622.6486`, min `138.0338`, trades `275`。margin `5` は完全一致、`10` はsum `563.7984`, min `115.1392`、`15` はsum `582.0794`, min `120.2830`、`20` はsum `582.2844`, min `120.2830`。
- 判断: secondary tie-break機構は探索軸として採用するが、今回のstateful positive-cost tie-break設定は標準policyに採用しない。validationで棄却されたためapply holdoutは実行しない。
- 次はside反転ではなく、entry優先順位、risk budget、near-tie局所OOF診断、追加月examplesへ進む。
- report: `docs/reports/00121_2026-06-29_stateful_secondary_tiebreak.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 09:10 Stateful positive cost value

- `oof-stateful-value-model --target-column stateful_positive_cost_value --prediction-prefix stateful_positive_cost` を実行した。
- OOFでは target mean `1.6588`, raw bias `14.7685`, mean bias `0.0853`, raw overestimate mean `15.6463`, mean overestimate mean `4.2896`, mean R2 `-0.0085`。
- direct replacement validationはbestでも threshold `2.0`, side margin `0.0`, sum `270.3750`, min `-64.5430`, trades `1349` でbaselineを下回る。閾値を上げると一部月が0 tradeになる。
- positive-cost overestimate risk validationはbaseline `sum=622.6486`, `min=138.0338` に対し、`risk=0.10` がsum `606.7320`, min `73.5066`。applyでもbaseline `sum=242.5008`, min `-20.8252` に対し、`risk=0.10` がsum `14.1920`, min `-38.4826`。
- 判断: `stateful_positive_cost_value` は校正信号として残すが、direct replacement / scalar penaltyは標準policyに採用しない。現行policyでは補正後EVがentry集合まで変えてしまうため、次はnear-tie専用secondary scoreを実装する。
- report: `docs/reports/00120_2026-06-29_stateful_positive_cost_value.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 09:05 Stateful EV blend risk

- `stateful_entry_value` meanをentry EVへ直接置換せず、`raw_ev - alpha * max(raw_ev - stateful_mean, 0)` の形でraw EVの過大評価penaltyとして検証した。
- validation 4ヶ月では `risk_penalty=0` がsum `622.6486`, min month `138.0338`, trades `275` で最良。`0.10` はsum `571.1410`, min `70.0596`、`0.25` はsum `416.3896`, min `73.3056` に悪化した。
- apply 3ヶ月でも `0.10` は2024-12を `-20.8252 -> -10.1916` に改善するが、2025-02を `179.2484 -> 132.4320`、2025-03を `84.0776 -> -25.6206` に壊した。
- 判断: stateful overestimate riskの単純な線形penaltyは標準policyに採用しない。stateful meanは校正信号として有用だが、順位付け能力が弱いため良い取引まで削る。
- 次は `stateful_positive_cost_value` target、near-tie ranking/tie-break、追加月examples、month/regime別drift診断へ進む。
- report: `docs/reports/00119_2026-06-29_stateful_ev_blend_risk.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 08:59 Stateful value model

- `trade_data.meta_model oof-stateful-value-model` を追加した。`stateful_candidate_examples.csv` を直接読み、`stateful_entry_value` など任意target列を月抜きOOFで学習する。
- 出力は `validation_oof_stateful_value_examples.csv`, `predictions_validation_oof_stateful_value_model.parquet`, `predictions_apply_stateful_value_model.parquet`, `stateful_value_model.joblib`。
- validation OOFでは raw bias `14.0151` が mean bias `0.0753`、raw overestimate mean `15.0311` が `4.2816` まで縮んだ。一方で mean R2 は `-0.0141`。
- stateful mean direct replacementのvalidation sweepは threshold `3.5` がsum `148.5810`, min `-0.4126` だが2024-09が0 trade。apply 3ヶ月では同じthresholdが全月0 trade。
- 判断: model列は校正・診断として採用するが、direct EV replacementは標準policyに採用しない。次は raw EVとの混合、near-tie ranking、または `stateful_positive_cost_value` targetを試す。
- report: `docs/reports/00118_2026-06-29_stateful_value_model.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 08:49 Validation stateful candidate examples

- 代表validation 4ヶ月 (`2024-07`, `2024-09`, `2024-11`, `2025-01`) で、raw policy と `min_trade_quality=0` stack0 policy の `model-policy` runを生成した。
- 固定条件は `timed_ev`, entry threshold `12`, short offset `6`, side margin `5`, min entry rank `0.5`, max predicted hold `480`, loss multiplier `1.2`, short low-vol系side EV penalty。
- `model-trade-delta` で `stateful_candidate_examples.csv` を作成。254例、target mean `2.4123`, target median `1.3995`, `target<=0` rate `0.3976`。
- raw EVとのcalibrationは raw predicted mean `16.4274`, raw bias `14.0151`, raw overestimate mean `15.0311`, mean MAE `16.0471`。validationでもraw EVはstateful targetを大きく過大評価。
- 判断: validation例を次の教師候補として採用。次は月抜きOOFで `stateful_entry_value` modelを作り、hard gateではなくEV補正/ranking tie-breakとして検証する。
- report: `docs/reports/00117_2026-06-29_validation_stateful_candidate_examples.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 08:42 Stateful candidate examples

- `model-trade-delta` に `stateful_candidate_examples.csv` 出力を追加した。candidate policyで実際に取った取引を、candidate-quality-styleの学習入力として保存する。
- 追加列: `target`, `stateful_entry_value`, `stateful_positive_cost_value`, `blocking_cost`, `positive_blocking_cost`, `replacement_regret`, `positive_replacement_regret`, `side`, `candidate_side`, `decision_timestamp`, `pred_side_gap`, `decision_hour_sin/cos`。
- `--stateful-example-target` を追加。defaultは `stateful_net = candidate_adjusted_pnl - blocked_base_adjusted_pnl`。`stateful_positive_cost` と `candidate_pnl` も選べる。
- 2024-12/2025-03 smokeでは `stateful_candidate_examples.csv` は220行。target meanは2024-12 `0.5921`, 2025-03 `-0.4640`。positive-cost target meanは2024-12 `-0.5883`, 2025-03 `-0.7904`。
- `candidate-quality-report` でraw EVとstateful targetのずれを測ると、support `220`, target mean `-0.0655`, raw predicted mean `18.4353`, raw bias `18.5008`, raw overestimate mean `18.7974`。raw EVはstateful targetにも大きく過大評価。
- 判断: `stateful_candidate_examples.csv` を次の学習入力として採用。次は代表validation月で同じ形式を作り、月抜きOOFでstateful value modelを学習する。
- report: `docs/reports/00116_2026-06-29_stateful_candidate_examples.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 08:35 Stateful blocking diagnostics

- `model-trade-delta` にstateful blocking診断を追加した。candidate取引の保有中に消えたbase-only取引を `blocking_pairs.csv` と `group_by_blocking_candidate_*` に出力する。
- `candidate_stateful_net_adjusted_pnl = candidate_adjusted_pnl - blocked_base_adjusted_pnl`、`candidate_stateful_positive_cost_adjusted_pnl = candidate_adjusted_pnl - blocked_base_positive_pnl` を追加した。
- 2025-03では `only_candidate long` がcandidate pnl `-18.8318`、blocked base pnl `+51.0776`、stateful net `-69.9094`。`only_candidate short` もcandidate pnl `-45.9878`、blocked base pnl `+7.1968`、stateful net `-53.1846`。
- 2025-03 `only_candidate long/up_low_vol` はcandidate pnl `-18.0778`、blocked base pnl `+38.3476`、blocked positive `+65.5600`、stateful net `-56.4254`。gate quality meanは `0.7288` で正なので、pointwise qualityは機会費用を見ていない。
- 判断: 次は `stateful_entry_value` / `stateful_positive_cost_value` をOOFで作る。base policyを固定し、hard gateではなくranking/tie-breakまたはEV補正として検証する。
- report: `docs/reports/00115_2026-06-29_stateful_blocking_diagnostics.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 08:27 Side outcome stack trade delta

- `model-trade-delta` を追加した。base/candidateの `model-policy` runを `entry_decision_timestamp + direction` で比較し、`common` / `only_base` / `only_candidate` に分解する。candidate側のquality列もprediction parquetから結合する。
- 2024-12はraw `-20.8252`、stack gate `-18.7302` で差分 `+2.0950`。`only_base` の除外が `+67.2954`、`only_candidate` の追加が `-65.2004` でほぼ相殺。
- 2025-03はraw `84.0776`、stack gate `-5.2898` で差分 `-89.3674`。`only_base` が `+24.5478` の利益を持ち、`only_candidate` が `-64.8196` の損失を追加した。
- 2025-03の最大悪化は `only_base long` の利益 `+73.4000` を失ったこと。`only_base` のquality `0-5` bucketにも `+51.0784` があり、`min_trade_quality >= 0` を満たす可能性のある良い後続取引が一玉制約の経路変化で消えている。
- 判断: `side_outcome_stack_fixed >= 0` hard gateは標準policyへ採用しない。品質予測はhard gateではなく、近接候補の優先順位、risk budget、candidate ranking tie-breakへ回す。次は `blocking_cost` / `replacement_regret` / `stateful_entry_value` 系のstateful教師を検討する。
- report: `docs/reports/00114_2026-06-29_side_outcome_stack_trade_delta.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 08:09 Side outcome stacking features

- `trade_quality_features_from_predictions` にside別補助特徴を追加した。side-outcome EV分布列と `component_fixed_weighted` quality列を、taken/opposite/gap の3系統でcandidate-quality modelへ渡せるようにした。列が存在しないartifactでは0になり、既存互換を維持する。
- `oof-candidate-quality-model` のdefaultは `source_mode=fixed_horizon` なので、固定候補と同じEV sourceにするため `--source-mode columns --long-column pred_long_best_adjusted_pnl --short-column pred_short_best_adjusted_pnl` を明示した。
- `side_outcome_stack_fixed` modelは validation OOF candidate `9091` 件で fixed component targetを学習。mean R2 `0.0168`, mean bias `0.0298`, mean overestimate `3.7140`。raw EVのbias `20.7301` より大きく改善した。
- validationでは `pred_candidate_quality_side_outcome_stack_fixed_*_adjusted_pnl >= 0` gateがsum `673.0854`, min `148.8660`, trades `254`, maxDD `81.8534` でraw `622.6486` / `138.0338` / `275` / `85.0166` を上回った。lower gateはvalidation時点でraw未満。
- holdoutでは `mean>=0` が2024-12を `-20.8252 -> -18.7302`、maxDDを `122.9852 -> 109.2604` に少し改善したが、2025-03を `84.0776 -> -5.2898` に壊し、sumは `242.5008 -> 155.4990` に落ちた。
- 判断: side-outcome/component特徴を二段目modelへ入れる実装は採用。ただし `side_outcome_stack_fixed` gateは標準policyには採用しない。risk budgetを明示したranking/tie-breakや診断特徴として残す。
- report: `docs/reports/00113_2026-06-29_side_outcome_stacking_features.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 07:58 Side outcome EV distribution calibration

- `trade_data.meta_model side-outcome-calibration` を追加した。side別EV bucket、side confidence bucket、`combined_regime`, `session_regime` で、target mean/lower、no-edge確率、large-loss確率、wrong-side確率、EV過大評価riskをsupport-awareに出力する。
- 代表4ヶ月validationでは `dataset_month` を抜くOOF校正で、scored monthの情報をfit側に混ぜないようにした。OOF predictionsは `115252` 行。
- raw baselineは side-outcome列付きparquetでも `sum=622.6486`, `min=138.0338`, `trades=275` を再現した。
- EV列への直接差し替えはvalidationで棄却。bestでも calibrated meanが `sum=176.2470`, `min=-116.8952` とrawを大きく下回った。
- gateとしてはvalidationで `wrong_side_risk >= -0.45` が `sum=663.4534`, `min=148.1228`、`conservative_ev_score >= 10` が `sum=678.4180`, `min=143.8022` と改善した。
- しかし既存holdout `2024-12`, `2025-02`, `2025-03` ではraw `sum=242.5008`, `min=-20.8252` に対し、`wrong_side_risk >= -0.45` は `sum=145.5712`, `min=-57.7274`、`conservative_ev_score >= 10` は `sum=192.3162`, `min=-28.4754` に悪化した。
- 判断: side-outcome校正列は実装として採用し、診断・stacking特徴量として残す。ただし標準policyのEV差し替えやhard gateには採用しない。単一risk列の閾値化はvalidation改善がholdoutへ外挿しない。
- report: `docs/reports/00112_2026-06-29_side_outcome_evdist_calibration.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 07:16 Jackknife holdout gap

- `00108` のjackknife選定候補を、既存の2024-12 / 2025-02 / 2025-03 base/mid/high cost holdout sweepへ固定監査した。
- `model-holdout-audit` がjackknife summaryの重複candidate keyで出力重複し、空のholding fallback keyがCSV読み込み時にNaN/float化してmergeに失敗したため修正した。`normalize_sweep_key_columns` でholding fallback keyを文字列正規化し、validation summaryはmerge前にcandidate keyで重複排除する。
- `down5,up10` はholdout 9case中6通過、min pnl `-57.7402`, sum `473.2982`, positive rate `0.6667`。2024-12はbase/mid/high全て負けた。
- `down5,range5` はholdout coverageが6caseのみで、2case通過、min pnl `-125.8666`, sum `-271.6002`, positive rate `0.3333`。2024-12と2025-02で負けた。
- 判断: jackknifeはvalidation内の単月依存を殺す診断として有用だが、既存holdout stressの崩れを解消しない。候補は標準policyへ昇格しない。次は候補rankingの微調整ではなく、追加walk-forward foldまたはregime/session failureを明示的に扱う設計へ戻る。
- report: `docs/reports/00109_2026-06-29_jackknife_holdout_gap.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 07:10 Candidate selection jackknife

- `model-candidate-selection-jackknife` を追加した。保存済み `model-candidate-selection` の `config.json` を入力にし、同じbase/cost sweepと選定条件で各validation foldを1つずつ抜いて再選定する。
- 抜いたfoldは選定に使わず、選ばれた候補をその抜いたfoldのbase/cost sweepで評価する。`min_base_folds` / `min_cost_folds` は残りfold数に合わせて下げるため、4fold selectionなら3foldで再選定する。
- `00107` の `near_top_pnl_stability_weight=0` と `1.0` のconfigで実行した。両者のjackknife結果は同じ。
- 4fold全てで `holdout_pass=True`。3foldはfull top `down5,up10` と一致し、2024-11を抜いた場合だけ `down5,range5` が選ばれた。
- 抜いたfoldでのworst minは `86.0172`、4foldの抜きfoldmin合計は `456.5626`。2024-11抜きで候補が変わっても、抜いた2024-11のbase/costは `94.6622 / 86.0172` で通過した。
- 判断: この診断は候補選定の単月依存を調べる基盤として採用する。今回の4fold内では強いfold依存は見えないが、これは未使用holdoutの代替ではない。次は追加walk-forward foldまたは未使用月で同じ事前条件を確認する。
- report: `docs/reports/00108_2026-06-29_candidate_selection_jackknife.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 07:03 PnL stability candidate ranking

- `model-sweep-summary` にfold別 `total_adjusted_pnl` の標準偏差 `total_adjusted_pnl_std` を追加した。
- `model-candidate-selection` に `--near-top-pnl-stability-weight` を追加し、`near_top_risk` / `stress_score` のnear-top候補rankingへbase/costのfold-to-fold adjusted PnL標準偏差をpenaltyとして入れられるようにした。defaultは `0` で既存ranking互換。
- 既存のbase 4fold + moderate/high cost 8fold validationで、`near_top_pnl_stability_weight=0/0.5/1.0` を比較した。topはいずれも `short:combined_regime=down_low_vol:5,short:combined_regime=up_low_vol:10` のまま。
- top候補の `pnl_stability_risk_all` は `28.4510` でnear-top内では低い。一方 `down10,up10,range10` は `45.3052`、`down5,up10,range10` は `50.1692` と不安定性が高く、weight追加で順位が下がる。
- 判断: PnL安定性rankingは採用するが、今回のvalidationでは標準候補を変える根拠にはしない。既存holdoutに合わせてweightを調整するとpost-hocになるため、診断・事前登録tie-breakとして扱う。
- report: `docs/reports/00107_2026-06-29_pnl_stability_candidate_ranking.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 06:56 Entry timing calibration

- `00105` の続きとして、`wait_regret` hard gateではなくside / `combined_regime` / predicted wait-regret bucket別にactual wait regretをOOF校正する `trade_data.meta_model entry-timing-calibration` を追加した。
- `bad_wait_threshold=4` で `pred_entry_timing_wait4_<side>_bad_wait_prob_risk`, `wait_excess_risk`, `wait_underestimate_risk` を出力し、既存backtestの `--risk-penalties` にそのまま接続できるようにした。
- 代表4ヶ月OOFでは全体bad wait probabilityがlong `0.2404`, short `0.2201`。group sourceはlong `115203/115252`, short `115080/115252` で概ね十分。
- validation 4foldでは `bad_wait_prob_risk` も `wait_excess_risk` もrisk `0` が最上位。baseline sum `673.9120`, min month `145.5682` に対し、bad prob risk `5` はsum `538.1352`, min `39.2836`、wait excess risk `0.5` はsum `589.5164`, min `98.7648`。
- 判断: calibration列の実装は採用するが、soft risk penaltyとして標準policyへは採用しない。validationで棄却されたためholdout固定確認には進めない。
- report: `docs/reports/00106_2026-06-29_entry_timing_calibration.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 06:44 Entry timing wait regret gate

- `00104` の次作業として、risk penaltyではなく既存entry timing教師の `pred_*_wait_regret` / `pred_*_entry_local_rank` gateを代表4ヶ月validationで再評価した。
- 固定条件は `timed_ev`, entry `12`, short offset `6`, side margin `5`, rank `0.5`, max hold `480`, short low-vol penalty `down5/up10/range5`, profit/loss `1.0/1.20`。
- `min_entry_rank=0.7` は全月0 trade。予測分布上の最大はlong `0.6818`, short `0.6905` で、現行スケールでは探索値として無効。
- validation baseでは `max_wait_regret=4` がmax DDを `92.0350 -> 74.9336` に下げたが、sum pnlは `673.9120 -> 654.3170`, min monthは `145.5682 -> 142.5510` に悪化。`2` は2024-11で `-9.1754`。
- high costでも同様で、`4` はmax DD `97.1906 -> 79.4966` だがsum/min monthは悪化。`2` は2024-11 `-17.4532`。
- holdoutでは `max_wait_regret=2` がsum `180.4620` と良く見えるが、validationで棄却済みかつ2025-04を5 tradesまで落とす後付け効果に近い。採用しない。
- 判断: 標準policyにwait_regret hard gateは追加しない。`wait_regret` はhard閾値ではなく、side/regime別の「待つべき確率」または「今入る価値のlower bound」として再校正する次候補にする。
- report: `docs/reports/00105_2026-06-29_entry_timing_wait_regret_gate.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 06:36 Candidate quality downside calibration

- `00103` のdownside driftを受け、`trade_data.meta_model candidate-quality-downside-calibration` を追加した。candidate side + `combined_regime` + quality bucketごとに target mean/lower, downside probability, large downside probability, overestimate risk, support/sourceを出力する。
- OOF validationでは `--oof-column dataset_month` によりscored monthをfit examplesから外す。holdout applyではOOF全体fitを固定predictionへ適用する。
- fixed component OOF globalは support `9091`, target mean `1.2754`, downside prob `0.4114`, large downside prob `0.0806`, mean overestimate `4.1076`, lower coverage `0.7055`。short側のdownside probは `0.4545` と高い。
- validation 4ヶ月では `overestimate_risk` penalty `0.25` がsum pnl `673.9120 -> 690.8404` を改善したが、min month pnlは `145.5682 -> 128.2770` に悪化。high costでもsumは `562.8784 -> 587.6084` だがmin monthは `120.5842 -> 88.7012`。
- `downside_risk` penalty `2.0` はvalidation sum `684.8380` だがworst regime lossが悪化し、強いpenaltyは取引数を削りすぎる。
- holdout 4ヶ月では `overestimate_risk` penalty `0.25` がsum `-116.0564 -> -88.1660`, max DD `474.6194 -> 406.1932` と改善した一方、2025-03/2025-04を悪化させた。`downside_risk` penalty `2.0` はsum `-160.0460`, min month `-326.0556` に悪化。
- 判断: downside calibration列は診断・ranking特徴量として採用するが、標準policyのrisk penaltyには採用しない。次は2025-04へ後付けで合わせず、validation内で事前登録したregime/session exposure riskとentry timing target再設計を扱う。
- report: `docs/reports/00104_2026-06-29_candidate_quality_downside_calibration.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 06:17 Candidate quality downside drift report

- `00102` の次作業として、分類failure probability直結ではなく、candidate rowの連続targetを月別・regime別・bucket別に診断する `trade_data.meta_model candidate-quality-report` を追加した。
- 既存のtimed / fixed / clipped candidate quality component OOF examplesを診断し、`overall_metrics.csv`, `group_metrics.csv`, `bucket_metrics.csv`, `summary.json` を出力するようにした。
- fixed componentはoverallで target mean `1.2754`, mean bias `0.2982`, mean MAE `7.9169`, lower coverage `0.7055`, `target<=0` `0.4114`, `target<=-15` `0.0806`。timedより現実的で、clipped bestよりdownside情報を保持している。
- ただしfixed componentは2024-11で mean overestimate `5.4115`, lower coverage `0.6125`, `target<=-15` `0.1151` と下振れが大きい。2025-01も `target<=0` `0.4885` まで悪化する。
- prediction bucket別では、fixed componentの上位 `q09/q10` がmean prediction高めにもかかわらずmean overestimate `6.5076` / `6.3060`、lower coverage `0.5844` / `0.6139` と悪い。quality scoreは単調なrankとして使えない。
- 判断: `candidate-quality-report` は採用。fixed componentを中心に次はmonth/regime/bucket別のsupport-aware calibrated downside featureへ進む。global quality hard gateやscalar risk直結は継続して採用しない。
- report: `docs/reports/00103_2026-06-29_candidate_quality_downside_drift_report.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 06:04 Candidate failure regime/session targets

- `00101` の次作業として、normal-vol / time-sessionをruleで直接減点せず、candidate-entry failure targetとして教師化した。
- `oof-candidate-failure-model` に `large_loss`, `wrong_side`, `range_normal_vol_selected_failure`, `normal_vol_selected_failure`, `time_session_selected_failure`, `any_failure` を追加した。CLI defaultは互換性維持のため従来通り `large_adverse` のまま。
- validation OOFでは `normal_vol_selected_failure` がprevalence `0.0067`, AUC `0.6418`、`range_normal_vol_selected_failure` がprevalence `0.0033`, AUC `0.7523`。一方 `wrong_side`, `time_session_selected_failure`, `any_failure` は逆相関寄り。
- `large_loss_threshold=10` はcandidate条件通過行で陽性ゼロだったため、`large_loss_threshold=0` を診断したがAUC `0.4730` で弱い。
- `normal_vol_selected_failure` riskをpolicyへ接続すると、base validationはrisk `10` で min pnl `145.5682 -> 147.5388`、high cost validationはrisk `20` で min pnl `120.5842 -> 124.4280` へ小改善した。
- しかしrisk `20` を2024-12 / 2025-02 / 2025-03 / 2025-04 holdout baseへ固定適用すると、sum pnlは `-105.0100 -> -183.7474`、max DDは `474.6194 -> 516.4888` に悪化した。
- 判断: `normal_vol_selected_failure` riskは標準採用しない。target拡張は診断基盤として残し、次は分類probability直結ではなく、candidate rowの連続的なrealizable PnL / lower quantile / calibrated downsideへ進む。
- report: `docs/reports/00102_2026-06-29_candidate_failure_regime_session_targets.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 05:48 Normal vol / time risk validation

- `00100` の2025-04 failureで見えた `short:range_normal_vol`, `short:up_normal_vol`, `long:range_normal_vol`, `rollover`, `ny_late` を、2025-04へ直接合わせず代表4ヶ月validationだけで確認した。
- 既存low-vol short penaltyをbaselineにし、normal-vol方向別EV減点と `rollover/ny_late` 両side EV減点を10候補の小gridで評価した。
- `model-candidate-selection --plateau-column side_ev_penalty_rules` が文字列rule setで落ちたため、`plateau_support_counts` をカテゴリplateau列にも対応させた。数値列は従来通り、カテゴリ列は同一カテゴリのeligible件数をsupportとして数える。
- validation結果では、`short_norm5` / `short_norm10` はhigh cost最低月がマイナスへ落ち、normal-vol short直接減点は台地にならなかった。
- `time5` はhigh cost min pnlを `120.5842 -> 125.4900` に小改善したが、base sum `673.9120 -> 644.3098`、cost sum `562.8784 -> 552.7068` と全体を削るため標準昇格しない。
- `long_range5` もcost min `120.8868` とbaselineをわずかに上回るが、base/cost sumを削るため診断候補止まり。
- 判断: normal-vol side EV penaltyを標準候補にしない。`time5` / `long_range5` はrisk診断・ranking特徴として残し、次はrule追加ではなくsession/regime別の選択失敗を教師化する。
- report: `docs/reports/00101_2026-06-29_normal_time_risk_validation.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 05:38 Exit holding holdout stress

- `00099` でvalidation最上位だった `bin_expected cap=480` を、2024-12 / 2025-02 / 2025-03 / 2025-04の固定holdoutへ適用した。
- 比較のため `raw_event cap=480` も同じ固定entry条件で評価した。固定条件は `entry=12`, short offset `6`, side margin `5`, rank `0.5`, short low-vol penalty `down5/up10/range5`, profit/loss `1.0/1.20`。
- base groupでは `bin_expected` が min pnl `-223.7292`, sum pnl `-116.0564`。`raw_event` は min pnl `-157.1394`, sum pnl `-52.2202`。
- high cost groupでは `bin_expected` が min pnl `-200.9822`, sum pnl `-186.3262`。`raw_event` は min pnl `-167.4006`, sum pnl `-163.4272`。
- 2025-04 baseの `bin_expected` は `-223.7292` まで崩れた。損失は `short:range_normal_vol` `-145.5636`, `short:up_normal_vol` `-144.7394`, `long:range_normal_vol` `-110.9304`、sessionでは `rollover` `-206.7266`, `ny_late` `-127.7102` に集中した。
- 判断: `bin_expected cap=480` はvalidationでは有望だが、fixed holdout stressでは標準昇格しない。exit holding表現だけではなくentry/side selectionがnormal-volと時間帯で壊れている。
- 次は2025-04へ直接合わせず、validation fold内でnormal-vol / rollover / ny_late riskを事前登録したcost-aware診断・rankingを試す。log-derived holding比較はlog列入りartifact再生成後に別枠で行う。
- report: `docs/reports/00100_2026-06-29_exit_holding_holdout_stress.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 05:28 Exit holding multifold comparison

- 既存の4ヶ月validation prediction `experiments/20260628_101740_policy_combined_side_exit_p1_l1p2/predictions_valid.parquet` を使い、exit holding sourceを同じgridで比較した。
- 既存predictionへ派生列を後付けする `trade_data.modeling derive-exit-holding-columns` を追加した。
- 対象foldは `2024-07`, `2024-09`, `2024-11`, `2025-01`。固定entry条件は `entry=12`, short offset `6`, side margin `5`, rank `0.5`, short low-vol penalty `down5/up10/range5`。
- baseでは `bin_expected cap=480` が最上位。4fold min pnl `145.5682`, sum pnl `673.9120`。
- high cost (`spread=0.2`, `slippage=0.1`, `delay=1`) でも `bin_expected cap=480` が最上位。4fold min pnl `120.5842`, sum pnl `562.8784`。
- `raw_event cap=480` との差は小さいため、bin expectedを新edgeとして採用するのではなく、raw event minutesと同等以上に機能するholding表現として扱う。
- `bin_expected_hazard` はtrade数とforced exitを抑えるが、fold最低PnLと合計PnLを削るため、この固定条件では標準採用しない。
- 既存artifactには `pred_*_exit_event_log_minutes` がないため、log-derived holdingの4fold比較は未実施。logを含めるにはdataset/train artifactを揃え直す。
- report: `docs/reports/00099_2026-06-29_exit_holding_multifold_comparison.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 05:18 Exit time bin holding columns

- 既存の `long_exit_event_time_bin` / `short_exit_event_time_bin` classifier出力から、`timed_ev` に渡せるholding派生列を追加した。
- `pred_*_exit_event_time_bin_minutes` は予測classをbin上限 `[15,60,240,720,1440,1440]` 分へ変換する。
- `pred_*_exit_event_time_bin_expected_minutes` はclass probabilityと代表値 `[7.5,37.5,150,480,1080,1440]` の期待値で作る。
- 2025-01 train、2025-02 validation、2025-04 testの小型HGB smokeでは、time-bin分類指標は弱い。2025-04 testのbalanced accuracyはlong `0.2765`, short `0.2439`。
- ただし派生列は保存でき、time-bin expected holdingでbacktestへ接続できた。2025-04 smokeは base `32.6798`, high cost `13.4170`。
- 同じHGB smoke内のlog-derived holdingも同じtrade集合になったため、今回の数字を採用根拠にしない。holding cap `480` で差が消えている可能性がある。
- 判断: bin分類由来holding列は採用するが、モデル候補ではなく表現・接続基盤として扱う。次は複数foldでlog/bin/hazardを同じgrid比較する。
- report: `docs/reports/00098_2026-06-29_exit_time_bin_holding_columns.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 05:09 Log exit event minutes target

- `long_exit_event_log_minutes` / `short_exit_event_log_minutes` をdataset targetへ追加し、`policy` / `full` regression target setにも入れた。
- prediction artifactには `pred_long_exit_event_minutes_from_log` / `pred_short_exit_event_minutes_from_log` を保存する。`expm1(clip(log_pred, 0, log1p(1440)))` で `0..1440` 分に閉じる。
- 2025-01 train、2025-02 validation、2025-04 testの小型MLP smokeでは、log target自体のR2はvalid/testとも負で、モデル候補としては使わない。
- ただし raw minutes回帰が `-54145.92` や `351152.22` を出す一方で、log派生holdingは `0..1440` に収まり、policyへ渡す出力制約としては機能した。
- 2025-04 backtest smokeは base `-28.4370`, high cost `-57.1444`。NoTradeには届かないため採用候補ではないが、`00095` の負値holdingによる高回転破綻は止まった。
- 判断: log exit minutes targetとbounded派生列は安全なexit timing表現として採用する。次はbin分類/hazard targetと複数fold validationへ戻す。
- report: `docs/reports/00097_2026-06-29_log_exit_event_minutes_target.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 04:57 Timed EV holding guard

- `timed_ev` に raw holding predictionのfail-close/fallback guardを追加した。
- `model-sweep` grid keyに `min_valid_predicted_hold_minutes`, `long_holding_fallback_column`, `short_holding_fallback_column` を追加した。
- defaultは `min_valid_predicted_hold_minutes=-inf` で既存のclip-only挙動を維持する。
- primary holdingが非finiteまたは `min_valid_predicted_hold_minutes` 未満の場合、fallback columnがあればfallbackへ差し替え、fallbackも無効ならそのsideのentryを不可にする。
- 2025-04 strict top診断では、HGB fallbackが base `-170.7302`, high `-182.3386`、fail-close skipが base `-111.2648`, high `-129.9124` まで損失を縮めた。
- 判断: holding guardは採用するが、標準candidateではなく安全装置として扱う。NoTradeには届かないため、次は exit minutes targetを `log1p(minutes)`, bin分類, hazard/event probability型へ作り直し、walk-forward validationで評価する。
- report: `docs/reports/00096_2026-06-29_timed_ev_holding_guard.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 04:44 2025-04 stress score holdout

- `00094` の方針通り、未使用月 `2025-04` へ同一形式の `xauusd_m1_p1_l1p2_policy_combined` dataset、HGB entry/side、MLP exit、forced target、`component_fixed_weighted` applyを生成した。
- HGB testは long EV R2 `-0.5656`, short EV R2 `-0.2691`, side score R2 `-0.0257`。MLP testは long EV R2 `-0.5518`, short EV R2 `-0.1337`, side score R2 `-0.2685`。
- MLP exit minutesは2025-04で外挿破綻し、中央値が long `-163.75`, short `-145.39`、1分未満率が long `0.6458`, short `0.6549`。これにより `timed_ev` が数分保有の高回転strategyになった。
- MLP holding本線では、best availableでも base `-475.6374` / mid `-933.4812` / high `-1442.3792`。stress top `down5,up10` は base `-503.8224`, high `-1503.3702` で標準採用不可。
- HGB holding fallbackでは高回転は止まり、best/strict `down5,up10,range5` が base `-157.1394`, high `-167.4006`、80-81 trades。ただしNoTradeには届かず、entry/side EVも2025-04で崩れている。
- 判断: 2025-04は未使用holdout failureとして保存する。次は exit minutes の unconstrained regression をやめ、log/bin/hazard targetと fail-close guardを入れる。2025-04へ直接weight最適化はしない。
- report: `docs/reports/00095_2026-06-29_2025_04_stress_score_holdout.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 04:26 Stress score ranking audit

- `model-candidate-selection --candidate-rank-mode stress_score` を追加した。既存 `near_top_risk_score` に対して、validation cost/base scenario合計PnLをrewardするranking。
- `model-holdout-audit` を `model-sweep` の `metrics.csv` gridにも対応させ、複数候補holdout sweepをvalidation summaryへmergeできるようにした。
- base 4fold + moderate/high cost 8foldで stress score selectionを実行。topは `down5,up10`、cost min pnl `96.8776`, cost sum `1060.7086`, max DD `88.9514`。
- 既存holdout stress監査では、全候補に負けcaseが残った。stress top `down5,up10` は holdout min pnl `-57.7402`, sum `473.2982`。`down10,up10,range10` は holdout min `-41.0256`, sum `569.9690`, max DD `127.9822` で相対的に良いが、validation stress scoreでは3位。
- 判断: stress score実装は有用だが、この設定だけでは標準採用候補を作れない。既存holdoutに合わせてweight調整するとpost-hocになるため、次は2025-04以降へ同一形式predictionを生成して未使用holdoutで確認する。
- report: `docs/reports/00094_2026-06-29_stress_score_ranking_audit.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 04:14 High-stress cost selection failure

- validation側にもhigh cost (`spread=0.2`, `slippage=0.1`, `delay=1`) を追加し、base + moderate + high costを同時に満たすcandidate selectionを実行した。
- `model-candidate-selection` に `--min-base-folds` / `--min-cost-folds` を追加。base/no-cost fold数とcost scenario fold数が違う場合でも、本文内の実験設計どおりに `base=4`, `cost=8` のように明示できる。
- explicit fold selectionでは `down5,up10,range5` がtop。validation base min pnl `138.3706`, cost min pnl `107.1572`, cost sum `1182.7684`, max drawdown `86.9156`。
- ただし固定holdout stressでは同候補の全scenario min pnlが `-32.4176`、high cost合計が `-31.6628`、max drawdownが `181.6922` まで悪化した。
- `down10,up10,range10` はvalidation topではないが、holdout全scenario合計 `569.9690` とmax drawdown `127.9822` は相対的に良い。現行rankingはこの外挿を拾えていない。
- 判断: high-stress validation selectionを入れても標準採用候補はまだない。次はvalidation fold内でstress-aware rankingを定義し、未使用holdout月で確認する。
- report: `docs/reports/00093_2026-06-29_highstress_cost_selection_failure.md`
- 採番、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

### 04:06 Cost-aware low-vol selection holdout

- short low-vol rule set gridをmoderate cost (`spread=0.1`, `slippage=0.05`, `delay=1`) でも4fold validation評価した。
- strict candidate selectionでは `down5,up10,range5` がtop。validation base min pnl `138.3706`, cost min pnl `121.9972`, max drawdown `86.9156`。
- ただし固定holdout cost stressでは2024-12 no-cost `-0.0572`, moderate cost `-11.7670`, high cost `-32.4176`。2025-03もhigh cost `-15.6634`、stress worst `-34.6572`。
- 判断: cost-aware validation selectionは前進だが標準採用には未達。rule set探索を広げず、stress-aware drawdown、月別下振れ、局所direction/session損失、EV overestimateをrankingへ入れる。
- report: `docs/reports/00092_2026-06-29_cost_aware_lowvol_selection_holdout.md`
- 採番と最新判断は、ファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 03:59 Short low-vol side EV penalty cost stress

- 2025-03 baselineのselected tradesを診断。longは `+47.6936`、shortは `-96.3762` で、最悪groupは `short:asia -67.7956` と `short:rollover -37.6094`。
- `min_side_confidence` hard gateはvalidationを壊した。baseline min pnl `82.7176` に対し、`0.55` は `7.0802`、`0.60` は `-12.1826`。global `side_confidence_penalty` も最良 `5` で min pnl `49.0358` に落ちるため採用しない。
- short combined-regime side EV penaltyを試し、`down5,up15,range10` はvalidation min pnl `118.7610`, sum `638.9718`、zero-cost holdout 2024-12/2025-02/2025-03で `10.0758 / 83.0220 / 82.7884` と全てプラス。
- ただしcost stressでは2024-12がmoderate cost `-22.8348`、high cost `-53.7684` へ落ち、3ヶ月合算もhigh costでマイナス。取引回数増加によるzero-cost改善の可能性が残る。
- `entry=16`, `rank=0.5` で取引回数を減らす案は、holdoutで2024-12 `-18.6930`、2025-02 `-43.3716` とzero-cost時点で悪化したため採用しない。
- 判断: short low-vol side EV comboは重要候補として残すが標準policyへ昇格しない。次はzero-costだけでなくmoderate costのvalidation min pnlも同時に見るcandidate selectionへ進む。
- report: `docs/reports/00091_2026-06-29_short_lowvol_side_ev_penalty_cost_stress.md`
- 採番と最新判断は、ファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 2026-06-28 JST

### 23:19 Selected-trade quality hybrid gate

- 直近hybrid top policy (`timed_ev`, entry `15`, short offset `4`, side margin `5`, rank `0.5`, MLP holding, max hold `480`) のvalidation 4ヶ月実行trade 106件を生成し、既存 `oof-trade-quality-calibration` でselected-trade qualityをOOF校正した。
- OOFでは raw bias `15.8005` が calibrated bias `-0.4206`、raw overestimate mean `17.3736` が `5.8545` へ改善。ただし calibrated R2 は `-0.0684`。
- `min_trade_quality` gateはvalidationで改善せず、topはgateなし `-inf` のまま。`min_trade_quality=4` は4fold eligibleだが min pnl `21.0614`, sum `214.5450` まで落ちる。
- fixed holdoutでは `min_trade_quality=4` が2024-12を `-54.6032 -> -4.6296` へ縮める一方、2025-02を `+81.8334 -> +8.5648` へ壊す。
- 判断: selected-trade qualityは過大評価診断として有効だが、下限gateとしては標準採用しない。次は校正EVへの置換またはsoft overestimate penalty、もしくは実行trade failure classifierへ進む。
- report: `docs/reports/00075_2026-06-28_selected_trade_quality_hybrid_gate.md`
- 採番と最新判断は、ファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 23:11 Candidate-entry residual penalty

- `ResidualPenaltyConfig` に `candidate_entry_only`, side別entry offset, `side_margin`, `min_entry_rank` を追加し、`candidate_entry_side_masks` でentry候補行だけをfit対象にできるようにした。
- `session_regime`, candidate-only, weight `10`, rank `0.5` は2024-12/2025-02 applyのrow-level selected avgを改善したが、validation OOF selected avg `19.0855 -> 17.7061`、side accuracy `0.5449 -> 0.5016` と壊れたため棄却。
- `session_regime`, candidate-only, weight `1`, rank `0.5` はvalidation 4foldで min adjusted pnl `50.5324`, sum `412.1412`。fixed holdoutは2024-12 `-17.1780`, 2025-02 `+78.0748`。
- 判断: 2024-12は raw hybrid baseline `-54.6032` より改善したが、validation minは既存baseline `81.5352` や `long:ny_late:15` risk top `85.7834` より弱い。標準採用せず、次はselected trade realized residual / side failureへ進む。
- report: `docs/reports/00074_2026-06-28_candidate_entry_residual_penalty.md`
- 採番と最新判断は、ファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

### 23:01 Regime residual penalty

- `ResidualPenaltyCalibrator` と `oof-residual-penalty` CLIを追加。side平均より過大評価が大きいregimeだけ `penalty_weight * excess_overestimate` をEVから差し引く列を生成する。
- `volatility_regime,session_regime`, weight `1` はrow-level OOFで selected avg adjusted pnl `19.0855 -> 19.2500`、side accuracy `0.5449 -> 0.5492` と小幅改善。ただしpenalty平均は `0.1-0.2` 程度。
- `session_regime`, weight `10` はvalidation 4foldでeligible、min adjusted pnl `85.7296` / `81.0356`。しかしfixed holdoutでは2024-12が `-156.1742` / `-159.1944` と大幅悪化し、2025-02は `+102.3132` / `+137.5952`。
- `volatility_regime,session_regime`, weight `10` も2024-12 `-166.4110` / `-159.6254`、2025-02 `+16.6456` / `+61.8658` で弱い。
- 判断: row-level residual penaltyは診断インフラとして残すが標準採用しない。次は全rowではなく、entry条件通過候補または実行tradeに限定した selected-trade / candidate-entry residual targetへ進む。

### 22:47 Support-aware lower EV calibration

- `GroupEVCalibrationConfig.lower_z` と support-aware lower EV columnsを追加。`prior_strength > 0` では `target_std * sqrt(prior/(support+prior))` をmarginに使い、`pred_regime_calibrated_*_best_adjusted_pnl_lower` を出力する。
- validation OOF上は lower EVで selected rowsが `107001` から `73694` に減り、selected avg adjusted pnlは `18.9940` から `19.5499`、side accuracyは `0.6066` から `0.6163` へ改善。
- しかし executable validationでは `lower_z=0.5` が2024-11で崩れ、4fold min adjusted pnlは `-127.7796` / `-134.5254`。eligible fold countは2/4のみ。
- fixed holdoutでは2025-02は `+135.2708` / `+106.2222` と強いが、2024-12は `-101.7542` / `-133.4082` で既存baselineより悪化。
- 判断: support-aware lower EV columnsは残すが、std-margin lower EVは標準policyへ採用しない。次は一律lower boundではなく、side/regime別のcalibration residual targetやregime-conditioned side confidenceへ進む。

### 22:28 Multi-holdout audit

- `model-holdout-audit` を追加。`model-policy` / `model-cost-sensitivity` artifactから候補keyを復元し、validation summaryとmergeして複数holdout月・cost caseを同時監査できるようにした。
- `short:up_low_vol` sweepのvalidation eligible候補を、2024-12/2025-02標準holdoutで監査。全候補 `audit_eligible=false`。相対最良は `long:ny_late:15`, `min_rank=0.5` だが holdout min pnl `-5.4938`。
- cost stress監査でも全候補 `audit_eligible=false`。相対最良の `long:ny_late:15`, `min_rank=0.5` は min pnl `-26.0816`、36 cases中19 pass。
- 判断: 現在のside EV penalty候補は標準policyへ昇格しない。次はside EV penalty探索を広げず、support-aware realized-PnL targetやside/regime別EV calibrationへ戻る。

### 22:12 Short up_low_vol EV penalty

- `short:combined_regime=up_low_vol` を直接side EV penaltyで減点する実験を実施。
- validationではshort shareは下がったが、最悪月PnLが `long:ny_late:15` 単独 `93.8904` からcombo `69.8078` / `63.6080`、short-only `50.2796` へ悪化。
- 2024-12/2025-02固定testでも、comboは2024-12で `-77.3720` / `-79.1486`、2025-02で `+28.5478` / `+64.0924`。既存baselineや `long:ny_late` risk topを上回らない。
- 判断: `short:up_low_vol` 直接減点は採用しない。short偏重riskはsupport-aware target、side/regime別calibrated EV、複数holdout同時rankingで扱う。
- 運用メモ: report ordering/latest/renumberingはファイルシステム更新時刻や本文の `更新日時` ではなく、各レポート本文の作成時刻 `日時` を参照する。

### 作業

- XAUUSD の HistData 取得パイプラインを作成。
- M1 の長期データを取得。
- M1 から M5 を生成。
- Tick の 2025 年 1 月サンプルを取得・変換。
- データ検証を実行。
- 研究目的とドキュメント運用を `GOAL.md` と `docs/` に整理。
- 体系的な作業まとめ、時系列ログ、実験レポートテンプレート、意思決定ログを追加。

### データ状態

- M1: 6,025,170 rows
- M5: 1,214,607 rows
- Tick sample: 5,798,226 rows

### 検証結果

- M1/M5 は timestamp 重複なし。
- M1/M5 は NULL なし。
- M1/M5 は OHLC 不整合なし。
- Tick sample は Bid/Ask 逆転なし。
- 大きな gap は週末・祝日由来が中心。

### 判断

- まず M1 ベースでバックテストとモデル評価の土台を作る。
- Tick は全期間取得せず、最初は約定・スプレッド検証用に限定利用する。
- 任意の 1 か月間の利益最大化を目的にするが、単月過学習を避けるため複数月検証を必須にする。

### 次の行動

- バックテスト環境を作る。
- `flat / long / short / close / hold` の状態遷移を実装する。
- ルールベースのベースラインを作り、月次スコアを出す。

### 追加作業

- M1 の次足 open 約定バックテストを実装。
- 1 玉制約、ロング/ショート、24 時間強制決済、月次評価を実装。
- `no_trade`, `random`, `ma_cross`, `rsi_reversal`, `breakout` のベースライン戦略を実装。
- trade log、equity curve、metrics、config の成果物保存を実装。
- 単体テストで、次足約定、強制決済、反転時に即時ドテンしない挙動を確認。

### ベンチマーク

対象月: 2025-01

| strategy | adjusted pnl | raw pnl | trades | win rate | max drawdown |
|---|---:|---:|---:|---:|---:|
| no_trade | 0.0000 | 0.000 | 0 | 0.0000 | 0.0000 |
| rsi_reversal | -56.5288 | 181.776 | 1069 | 0.6492 | 123.4142 |
| random | -107.9284 | -65.748 | 49 | 0.4082 | 112.7517 |
| ma_cross | -279.2953 | -39.229 | 485 | 0.3402 | 309.5242 |
| breakout | -311.2774 | -141.790 | 156 | 0.3077 | 320.3002 |

成果物:

- `data/reports/backtests/20260627_165623_benchmark_2025-01/`

### 判断

- ベースラインは 2025-01 では全て adjusted pnl がマイナス。
- raw pnl がプラスでも、利益 0.9 倍・損失 1.3 倍の補正で期待値が悪化する例が出ている。
- 次は、未来 24 時間の最良 exit に基づく教師ラベルと、リークのない特徴量を作る。

### 特徴量・ラベル作成

- `src/trade_data/dataset.py` を追加。
- M1 の月次 dataset 生成CLIを追加。
- 特徴量は現在barと過去rollingだけから作る。
- ラベルは次足open entry、未来24時間内のbest exitから作る。
- FFT特徴量として 64/256 window の low/high power と spectral centroid を追加。
- 2025-01 の edge1 と edge15 dataset を生成。

生成物:

- `data/processed/datasets/xauusd_m1/xauusd_m1_2025-01_h24_edge1.parquet`
- `data/processed/datasets/xauusd_m1/xauusd_m1_2025-01_h24_edge15.parquet`

edge15 summary:

- rows: 30,197
- feature_count: 47
- labels: short 5,175 / stay_flat 8,390 / long 16,632
- best adjusted pnl mean: 19.4884
- best adjusted pnl median: 19.2177

### 判断

- edge1 は stay_flat が 100 件しかなく、分類問題として偏りが強い。
- edge15 は stay_flat が増え、初期学習に使いやすい。
- ただし edge は test 月に合わせず、validation で調整する。
- 次は複数月 dataset を生成し、train/valid/test split を固定する。

### Target 方針の見直し

- 3クラスラベルだけでは情報を落としすぎるため、主ターゲットにしない方針に変更。
- `docs/decisions/0002_multitask_targets.md` を追加。
- dataset に連続ターゲットと量子化補助ターゲットを追加。
- edge1/edge15 dataset を新フォーマットで再生成。

追加ターゲット:

- long/short best adjusted pnl
- long/short forced adjusted pnl
- long/short max adverse pnl
- long/short best holding minutes
- side score
- best adjusted pnl quantile
- side score quantile
- holding time bins

再生成結果:

- edge1: rows 30,197 / columns 80 / nulls 0
- edge15: rows 30,197 / columns 80 / nulls 0
- edge15 labels: short 5,175 / stay_flat 8,390 / long 16,632
- edge15 best adjusted pnl quantile: 6,040 / 6,039 / 6,039 / 6,039 / 6,040
- edge15 side score quantile: 6,040 / 6,039 / 6,039 / 6,039 / 6,040

### 複数月 Dataset

2024-01 から 2024-07 まで、edge15 の dataset を同一仕様で生成した。

split:

- train: 2024-01 から 2024-06
- valid: 2024-07
- test: 2025-01

月次 rows:

| month | rows | short | stay_flat | long |
|---|---:|---:|---:|---:|
| 2024-01 | 30,028 | 6,941 | 17,253 | 5,834 |
| 2024-02 | 28,808 | 3,269 | 22,609 | 2,930 |
| 2024-03 | 27,589 | 4,204 | 9,955 | 13,430 |
| 2024-04 | 30,299 | 11,303 | 3,862 | 15,134 |
| 2024-05 | 31,523 | 10,681 | 10,511 | 10,331 |
| 2024-06 | 27,507 | 7,833 | 9,598 | 10,076 |
| 2024-07 | 31,587 | 8,951 | 8,728 | 13,908 |

### 初回 Multi-task 学習

`src/trade_data/modeling.py` を追加し、軽量な HistGradientBoosting で初回モデルを学習した。

学習ターゲット:

- regression: `long_best_adjusted_pnl`, `short_best_adjusted_pnl`, `side_score`
- classification: `best_adjusted_pnl_quantile`, `side_score_quantile`, `label`

実験:

- command: `python3 -m trade_data.modeling train --train-start 2024-01 --train-end 2024-06 --valid-start 2024-07 --valid-end 2024-07 --test-start 2025-01 --test-end 2025-01 --min-adjusted-edge 15 --max-iter 80 --learning-rate 0.05 --entry-threshold 15`
- artifacts: `experiments/20260627_171852_hgb_multitask_edge15/`
- report: `docs/reports/00003_2026-06-28_hgb_multitask_initial.md`

主要結果:

| split | rows | selected trades | oracle-exit adjusted pnl | avg pnl | side acc | label macro F1 |
|---|---:|---:|---:|---:|---:|---:|
| train | 175,754 | 67,942 | 1,786,652.8970 | 26.2967 | 0.8215 | 0.7885 |
| valid | 31,587 | 14,741 | 217,820.3601 | 14.7765 | 0.5207 | 0.4351 |
| test | 30,197 | 22,589 | 319,595.3148 | 14.1483 | 0.5636 | 0.4200 |

判断:

- train と valid/test の差が大きく、過学習または期間依存が見える。
- test の side accuracy は 0.5636 で完全なランダムよりは良いが、regression R2 は不安定。
- selection metric は oracle exit を使っているため、まだ実行可能な取引成績ではない。
- 次は予測値だけで entry/exit する backtest policy を実装し、同じ取引制約で評価する。

### 実行可能 Model Policy

`src/trade_data/backtest.py` に、保存済みモデル予測を使う backtest policy を追加した。

追加CLI:

- `python3 -m trade_data.backtest model-policy ...`
- `python3 -m trade_data.backtest model-sweep ...`

policy:

- `stateless_ev`: 各 decision bar で predicted long/short EV が entry threshold を超えた時だけ desired position を出す。
- `stateful_ev`: flat 時は entry threshold を超えた時だけ入る。保有中は、保有側EVが exit threshold 未満、または反対側EVが十分強い場合に閉じる。

validation sweep:

- month: 2024-07
- predictions: `experiments/20260627_171852_hgb_multitask_edge15/predictions_valid.parquet`
- artifacts: `data/reports/backtests/20260627_172832_model_sweep_2024-07/`
- best valid setting: `stateful_ev`, entry threshold 30, exit threshold 10, side margin 5
- best valid adjusted pnl: -5.4446

test:

- month: 2025-01
- predictions: `experiments/20260627_171852_hgb_multitask_edge15/predictions_test.parquet`
- artifacts: `data/reports/backtests/20260627_172849_model_stateful_ev_2025-01/`
- adjusted pnl: -35.8255
- raw pnl: 4.5610
- trades: 21
- win rate: 0.5714
- profit factor: 0.7239
- max drawdown: 71.5889
- forced exits: 1

判断:

- oracle exit を使った selection metric と実行可能 backtest の差が大きい。
- raw pnl はわずかにプラスでも、利益 0.9 倍・損失 1.3 倍の補正後はマイナスになる。
- valid 最良設定でも valid adjusted pnl がマイナスなので、このモデルは no_trade をまだ超えていない。
- 2025-01 の trading baseline では `rsi_reversal` が -56.5288 だったため、model policy の -35.8255 は既存 trading baseline より損失が小さい。

### 過学習対策の方針整理

会話上の判断:

- 少ないデータでも過学習しにくい設計が理想。
- ただし XAUUSD の M1 データは年単位で増やせるため、まず期間依存を測れるだけの月数を用意する。
- データ増加の目的は「複雑なモデルを正当化すること」ではなく、「どの月・局面で壊れるかを見える化すること」。
- 単月最適化を避けるため、validation で閾値・calibration を決め、test では一度だけ評価する。
- 現モデルの主な弱点は、方向よりも exit timing と predicted EV の過大評価。

次に試すこと:

1. 追加月の dataset を生成する。
2. `long/short_best_holding_minutes` を予測対象に加え、exit timing に使う。
3. validation で expected pnl calibration を行い、calibrated EV で backtest policy を動かす。
4. walk-forward split で複数月に対する安定性を確認する。
5. 正則化を強めた HGB と比較し、モデル容量より汎化を優先する。

### 旧倍率train / 新倍率validation のpolicy選択

会話上の判断:

- 学習 dataset と教師 target は旧倍率 0.9 / 1.3 のまま維持する。
- validation と final test の executable backtest は新倍率 1.0 / 1.25 で評価する。
- validation を旧倍率のままにすると、no_trade に近い低参入設定へ寄りすぎるため、新倍率でpolicyを選ぶ。
- test 月で閾値を選ばない。複数 validation fold の集計でpolicyを選ぶ。

実装:

- `src/trade_data/backtest.py` に `model-sweep-summary` を追加。
- 複数の `model-sweep` CSVを、`policy`, `entry_threshold`, `exit_threshold`, `side_margin`, `risk_penalty` ごとに集計する。
- 集計時に、fold数、最低取引数、強制決済率、drawdown、各foldの最低 adjusted pnl を制約として使えるようにした。
- `tests/test_backtest.py` に、sweep CSV正規化と複数fold集計のテストを追加。

実験:

- fold A validation: 2024-07
  - model: `experiments/20260627_174250_hgb_multitask_edge15/`
  - sweep: `data/reports/backtests/20260627_180433_model_sweep_2024-07/`
- fold B validation: 2025-01
  - model: `experiments/20260627_174030_hgb_multitask_edge15/`
  - sweep: `data/reports/backtests/20260627_180029_model_sweep_2025-01/`
- summary: `data/reports/backtests/20260627_180908_model_sweep_summary/`

summary条件:

- min folds: 2
- min trades per fold: 30
- max forced exit rate: 0.0
- max drawdown: 100
- min adjusted pnl per fold: 0
- sort: mean adjusted pnl

暫定候補:

- policy: `timed_ev`
- entry threshold: 15
- exit threshold: 0
- side margin: 5
- risk penalty: 0
- validation mean adjusted pnl: 133.9964
- validation min adjusted pnl: 120.5680
- validation mean trades: 46.0
- validation max drawdown: 66.4905
- validation forced exits: 0

2025-02 test 診断:

- artifacts: `data/reports/backtests/20260627_180701_model_timed_ev_2025-02/`
- adjusted pnl: +23.7253
- raw pnl: +78.7070
- trades: 42
- win rate: 0.5000
- profit factor: 1.0863
- max drawdown: 112.5325
- forced exits: 0

比較:

- 2025-02 no_trade: 0.0000
- 2025-02 random: -14.0078
- 2025-02 breakout: -103.0195
- 2025-02 ma_cross: -203.7905
- 2025-02 rsi_reversal: -296.2607

判断:

- no_trade を超える実行可能policyが出た。
- ただし 2025-02 test の drawdown は validation制約の 100 を少し超えたため、まだ安定とは言えない。
- validation単月最高の stateful/risk付き設定は test で +6.6193 まで落ちた。単月最適化は危険。
- forced exit rate 0 を制約に入れると、exit timing が壊れている候補を避けやすい。
- 次は fold を増やし、`timed_ev` の保持時間予測だけでなく exit probability / trailing logic を比較する。

### 追加 Walk-forward Fold

目的:

- 2foldだけではpolicy selectionが偶然安定して見えている可能性がある。
- 2024-07 と 2025-01 の間に 2024-09 validation fold を追加し、同じ候補が残るか確認する。

split:

- train: 2023-01 から 2024-08
- valid: 2024-09
- test: 2024-10

model:

- artifacts: `experiments/20260627_183038_hgb_multitask_edge15/`
- model type: HistGradientBoosting multi-task
- train target: 旧倍率 0.9 / 1.3
- validation/test backtest: 新倍率 1.0 / 1.25

2024-09 valid sweep:

- artifacts: `data/reports/backtests/20260627_183050_model_sweep_2024-09/`
- 単月上位は risk付き `stateful_ev` だったが、強制決済を含む。
- forced exit rate 0 の候補では `timed_ev` が有力。

3fold summary:

- artifacts: `data/reports/backtests/20260627_183241_model_sweep_summary/`
- folds: 2024-07, 2024-09, 2025-01
- constraints: min trades 30, max forced exit rate 0, max drawdown 100, min adjusted pnl per fold 0
- selected candidate: `timed_ev`, entry threshold 15, exit threshold 0, side margin 5, risk penalty 0
- validation mean adjusted pnl: 126.3996
- validation min adjusted pnl: 111.2060
- mean trades: 43.3333
- max drawdown: 66.4905
- forced exits: 0

2024-10 test:

- artifacts: `data/reports/backtests/20260627_183253_model_timed_ev_2024-10/`
- adjusted pnl: +48.9555
- raw pnl: +99.6620
- trades: 43
- win rate: 0.6047
- profit factor: 1.1931
- max drawdown: 77.1468
- forced exits: 0

2024-10 baseline:

- random: +43.9895
- no_trade: 0.0000
- breakout: -206.6695
- rsi_reversal: -242.5953
- ma_cross: -397.3735

判断:

- 3foldでも標準候補は変わらなかった。
- 2024-10 test では no_trade と random を上回った。
- ただし signal は long 側に偏っており、上昇局面依存の疑いが残る。
- 次は short 優勢またはレンジ相場を含むfoldを追加し、direction bias を評価する。

### Short/Down-Regime 確認

目的:

- 2024-10 test で標準候補の signal が long 側に偏っていた。
- short 優勢または下落局面で、標準候補が維持できるか確認する。

split:

- train: 2023-01 から 2024-10
- valid: 2024-11
- test: 2024-12

月次価格変化:

- 2024-11: -3.517%
- 2024-12: -1.090%

model:

- artifacts: `experiments/20260627_183919_hgb_multitask_edge15/`

2024-11 valid sweep:

- artifacts: `data/reports/backtests/20260627_183932_model_sweep_2024-11/`
- 単月上位は short を多く取る stateful 系だった。
- 従来候補 `timed_ev entry=15 side_margin=5 risk=0` は adjusted pnl -21.0065、max drawdown 199.0998、forced exit rate 0.0208 で、このfoldでは崩れた。

4fold strict summary:

- artifacts: `data/reports/backtests/20260627_184136_model_sweep_summary/`
- folds: 2024-07, 2024-09, 2024-11, 2025-01
- constraints: min trades 30, forced exit rate 0, max drawdown 100, min adjusted pnl per fold 0
- result: eligible candidate なし

4fold relaxed summary:

- artifacts: `data/reports/backtests/20260627_184150_model_sweep_summary/`
- constraints: min trades 30, forced exit rate 0.5, max drawdown 150, min adjusted pnl per fold 0
- top eligible: `stateful_ev`, entry 5, exit 10, side margin 5, risk penalty 0.1
- validation mean adjusted pnl: 113.5546
- validation min adjusted pnl: 100.7555
- forced exit rate max: 0.5000

2024-12 test:

- standard candidate artifact: `data/reports/backtests/20260627_184333_model_timed_ev_2024-12/`
- standard candidate adjusted pnl: -175.6668
- raw pnl: -107.4190
- trades: 44
- win rate: 0.3636
- profit factor: 0.4852
- max drawdown: 206.9538
- forced exits: 0
- long adjusted pnl: -110.5037
- short adjusted pnl: -65.1630
- long trades: 12
- short trades: 32

2024-12 baseline:

- rsi_reversal: +41.0018
- random: +0.8950
- no_trade: 0.0000
- ma_cross: -34.3620
- breakout: -158.6600

判断:

- 下落/short寄りfoldを入れると、従来の標準候補は棄却される。
- 2024-12では short signal が多いにもかかわらず short trades も損失なので、単純な long bias ではない。
- 失敗は、下落/レンジ局面での entry timing、exit timing、EV calibration の崩れと見る。
- 次は `model-sweep-summary` に方向別P/L、long/short exposure、regime別評価を入れる。
- モデル側では regime feature、volatility/trend classifier、side-specific calibration を検討する。

### Mixed-Regime Weighted Training

問題意識:

- testで過学習が判明しているため、現時点の学習品質は高くない。
- 一部の連続した数か月だけでtrain/validを作ると、相場局面に依存したモデルになりやすい。
- 学習データ自体に、上昇・下落・レンジを混ぜる必要がある。

実装:

- `src/trade_data/modeling.py` に `--train-months`, `--valid-months`, `--test-months` を追加。
- 非連続の月リストでsplitを作れるようにした。
- `--sample-weighting none|month|label|month_label` を追加。
- `month_label` は各 `dataset_month × label` セルの総重みを揃える。

実験:

- report: `docs/reports/00006_2026-06-28_mixed_regime_weighted_training.md`
- model: `experiments/20260627_185200_hgb_multitask_edge15/`
- train: 2023-01..2023-12, 2024-01..2024-06, 2024-08, 2024-10
- valid: 2024-07, 2024-09, 2024-11, 2025-01
- test: 2024-12, 2025-02
- sample weighting: `month_label`
- target clip quantile: 0.99
- max leaf nodes: 15
- min samples leaf: 100
- l2: 0.2

validation:

- strict summary artifact: `data/reports/backtests/20260627_185959_model_sweep_summary/`
- relaxed summary artifact: `data/reports/backtests/20260627_190009_model_sweep_summary/`
- strict constraints では eligible candidate なし。
- relaxed constraints では `timed_ev`, entry 10, side margin 5, risk penalty 0.4 が選ばれた。
- validation mean adjusted pnl: +146.0508
- validation min adjusted pnl: +73.0053
- max drawdown: 124.0158
- max forced exit rate: 0.0213

test:

- 2024-12 artifact: `data/reports/backtests/20260627_190023_model_timed_ev_2024-12/`
- 2024-12 adjusted pnl: -183.5370
- 2024-12 long adjusted pnl: -128.3435
- 2024-12 short adjusted pnl: -55.1935
- 2025-02 artifact: `data/reports/backtests/20260627_190023_model_timed_ev_2025-02/`
- 2025-02 adjusted pnl: +54.9137

判断:

- 学習データ混合と `month_label` weighting は、validation上の下落月では改善した。
- しかし 2024-12 test には汎化せず、過学習問題は解決していない。
- 2025-02 は改善したため、方向性に一部効果はある。
- 次は閾値調整ではなく、教師targetと特徴量の改善が必要。
- 特に oracle best exit target だけでは、実行可能なentry/exit timingを学習しきれていない可能性が高い。

### 評価倍率の緩和

会話上の判断:

- no_trade に負け続けると比較が難しいため、評価倍率を緩和する。
- 旧ルール: profit multiplier 0.9 / loss multiplier 1.3
- 新ルール: profit multiplier 1.0 / loss multiplier 1.25

作業方針:

- 既存モデルは旧倍率 target で学習しており、今後も学習 dataset は旧倍率を維持する。
- validation の policy 選択は新倍率 backtest で行う。
- test も validation で選んだ設定を固定した上で、新倍率 backtest で評価する。
- validation を旧倍率で行うと、no_trade に近い方向、つまり参入回数を下げる方向へ最適化されすぎるため、新倍率 validation で十分な参入を維持する。
- 旧 dataset を上書きしない。

補足:

- 新倍率 dataset は `data/processed/datasets/xauusd_m1_p100_l125/` に生成済みだが、主経路の学習には使わない。
- 以後は旧倍率 target での学習効率向上、calibration、exit timing、walk-forward 安定性を優先する。

標準フロー:

```text
train target: old multipliers 0.9 / 1.3
validation policy selection: new multipliers 1.0 / 1.25
final test: new multipliers 1.0 / 1.25
```

### Dense Entry Quality Target

会話上の問題提起:

- entry timing を直接学習させると、正例が少なくなり学習量が足りない。
- `long / short / stay_flat` まで圧縮すると、deep learning に渡す情報として粗すぎる。
- 1つのdatasetを、entry方向だけでなく、entryに向いている度合い、待つべきか、exit timing、EV calibration など多方面から学習に使いたい。

判断:

- entry timing は単一分類ではなく、密な品質targetに分解する。
- 量子化は情報を落とす主手段ではなく、連続targetのノイズを安定化する補助タスクとして使う。
- 学習datasetは旧倍率 0.9 / 1.3 を維持する。
- validation/test の policy 評価は新倍率 1.0 / 1.25 を維持する。

実装:

- `src/trade_data/dataset.py`
  - `long_profit_barrier_hit`, `short_profit_barrier_hit`
  - `long_wait_regret`, `short_wait_regret`
  - `long_entry_local_rank`, `short_entry_local_rank`
  - `long_entry_urgency`, `short_entry_urgency`
  - wait regret quantile と local rank bin
  - `--entry-timing-lookahead-minutes`, default 60
- `src/trade_data/modeling.py`
  - 上記targetを regression/classification のmulti-task学習対象に追加。
  - predictions parquet に真値と予測値を残す。
- `tests/test_dataset.py`
  - barrier hit と新target列の生成を確認。

次の行動:

1. 新schemaで旧倍率datasetを再生成する。
2. mixed-regime split で新target込みのHGBを学習する。
3. validation foldで calibrated EV と timed policy を再選択する。
4. 2024-12 test の失敗が entry quality target で緩和されるか確認する。

検証:

- `python3 -m unittest discover tests`: 23 tests OK
- 2025-01 の1か月datasetを `/tmp` に新schemaで生成し、rows 30,197、旧label分布は従来edge15と一致。
- 2024-07 から 2024-09 の3か月datasetを `/tmp` に新schemaで生成。
- `max_iter=2`, `sample_frac=0.2` のスモーク学習で、追加した全targetの train/evaluate/prediction 保存まで完了。

### Dense Entry Quality 実験

作業:

- 主datasetを 2023-01 から 2025-12 まで新schemaで再生成。
- dense entry quality target込みで mixed-regime HGB を再学習。
- HGBはtargetごとの独立モデルなので、追加targetがEVモデルの表現改善には直接効かない点を確認。
- `model-policy` / `model-sweep` に quality filter を追加。
  - `--max-wait-regret`
  - `--min-entry-rank`
  - `--require-profit-barrier`

実験:

- report: `docs/reports/00007_2026-06-28_dense_entry_quality_targets.md`
- model: `experiments/20260627_192112_hgb_multitask_edge15/`
- validation quality summary: `data/reports/backtests/20260627_192904_model_sweep_summary/`

validation選択:

- `timed_ev`, entry 5, exit 0, side margin 5, risk penalty 0.1, min entry rank 0.5
- validation mean adjusted pnl: +38.6307
- validation min adjusted pnl: +2.3763
- min trades per fold: 17
- max drawdown: 85.5988
- max forced exit rate: 0.0476

test:

- 2024-12: adjusted pnl -135.9573
- 2025-02: adjusted pnl -101.0583

追加診断:

- 強く絞る候補では 2024-12 が -9.5233 まで改善したが、5 trades しかなく、2025-02 は -43.2768。

判断:

- entry quality filter は露出削減と損失抑制には効く。
- しかし no_trade を超えるedgeはまだ出ていない。
- 次は、予測済みtargetを入力にした二段階meta model、またはshared representationの小型深層学習へ進む。

### 二段階 Meta EV Model

作業:

- `src/trade_data/meta_model.py` を追加。
- validation predictions を long/short の side-aware examples に展開し、base modelの予測済みtargetから side別 adjusted pnl を再推定するHGBを実装。
- `trade-meta` CLIを追加。

実験:

- meta artifact: `experiments/20260627_193559_meta_ev_dense_entry_quality/`
- train predictions: `experiments/20260627_192112_hgb_multitask_edge15/predictions_valid.parquet`
- apply predictions: `experiments/20260627_192112_hgb_multitask_edge15/predictions_test.parquet`

結果:

- validation-fit R2: long 0.1837 / short 0.1980
- test-apply R2: long -0.0652 / short -0.1921
- meta EV + standard quality candidate:
  - 2024-12: -240.5445
  - 2025-02: +23.7068
- meta EV + stronger filter:
  - 2024-12: -114.5178
  - 2025-02: -71.8913

判断:

- validationにfitしたmeta modelは、testでは再過学習している。
- 2025-02は一部改善するが、2024-12で崩れるため採用しない。
- 次は meta fit 月と policy selection 月を分ける。validation内walk-forwardでmeta modelを評価する。

### Validation-internal OOF Meta

作業:

- `meta_model fit` に `--train-months` / `--apply-months` を追加し、同じprediction fileから月を分けてfit/applyできるようにした。
- validation 4ヶ月で leave-one-month-out meta を実施。
- 各holdout月のmeta予測でpolicy sweepし、4fold summaryで候補を選択した。

OOF artifacts:

- `experiments/20260627_194501_meta_oof_2024-07/`
- `experiments/20260627_194501_meta_oof_2024-09/`
- `experiments/20260627_194501_meta_oof_2024-11/`
- `experiments/20260627_194501_meta_oof_2025-01/`
- summary: `data/reports/backtests/20260627_194724_model_sweep_summary_1/`

選択:

- policy: `timed_ev`
- entry threshold: 10
- side margin: 5
- risk penalty: 0.2
- max wait regret: 2
- min entry rank: 0.5
- require profit barrier: false
- validation OOF mean adjusted pnl: +72.4758
- validation OOF min adjusted pnl: +3.0118
- min trades per fold: 28
- max drawdown: 83.2353
- forced exit max: 0

test:

- final meta artifact: `experiments/20260627_194740_meta_all_valid_to_test_oof_selected/`
- 2024-12: adjusted pnl -97.3488, 31 trades, profit factor 0.5403, max drawdown 143.0608
- 2025-02: adjusted pnl -0.4358, 21 trades, profit factor 0.9971, max drawdown 72.8378

比較:

- 同じpolicyのmetaなしbase予測は 2024-12 -130.3193 / 2025-02 -47.2025。
- OOF選択metaはbaseよりtest合計を改善したが、no_trade 0.0 にはまだ負ける。
- final metaのtest R2は long -0.0652 / short -0.1921 で、EV calibration自体の汎化はまだできていない。

判断:

- 過学習は悪化していない。fit月と選択月を分けたことで、同月fit/同月選択の漏れは抑えられた。
- ただしtestでNoTradeに勝てていないため、過学習は解消していない。
- 次はvalidationだけでmetaを学習するのをやめ、train期間にもOOF predictionsを作ってmeta学習量を増やす。
- 2024-12の失敗tradeをentry方向、exit遅れ、EV過大評価に分けて診断する。

### 学習時間と過学習対策

作業:

- HGBに過学習抑制パラメータを追加。
  - `max_depth`
  - `max_features`
  - `early_stopping`
  - `validation_fraction`
  - `n_iter_no_change`
  - `tol`
- defaultを保守的に変更。
  - `learning_rate=0.03`
  - `max_leaf_nodes=15`
  - `max_depth=4`
  - `min_samples_leaf=100`
  - `l2_regularization=0.2`
  - `max_features=0.8`
  - `target_clip_quantile=0.99`
  - `sample_weighting=month_label`
- `model_diagnostics` を追加し、targetごとの `n_iter` とmax_iter到達有無を保存。
- `target-set policy` を追加し、executable policyに必要なtargetだけで長時間学習比較できるようにした。
- meta modelにも `month_side` weighting、regime feature input、prediction shrinkage、強めの正則化defaultを追加。
- 2019-01 から 2022-12 のdatasetを生成し、データ増量の準備も行った。

実験:

- report: `docs/reports/00009_2026-06-28_training_time_and_generalization.md`
- iter80: `experiments/20260627_201301_policy_iter80_base_train/`
- iter320: `experiments/20260627_201455_policy_iter320_base_train/`
- train rows: 546,537
- target set: `policy`
- valid: 2024-07, 2024-09, 2024-11, 2025-01
- test: 2024-12, 2025-02

結果:

- iter80もiter320も、14 targetすべてがmax_iterに到達した。
- iter320はvalidation selection pnlを増やしたが、test side accuracyは改善しなかった。
- iter80はvalidation sweepで10 trades/fold条件でもeligibleなし。
- iter320は10 trades/fold条件でeligibleが出たが、30 trades/fold条件ではeligibleなし。
- min fold pnl優先候補:
  - `timed_ev entry=15 side_margin=0 risk=0 max_wait_regret=4 min_entry_rank=0 require_profit_barrier=true`
  - validation mean adjusted pnl: +41.8295
  - validation min adjusted pnl: +26.2700
  - min trades per fold: 15
  - max drawdown: 51.2338
- test:
  - 2024-12: -99.9843
  - 2025-02: -38.9125

判断:

- 学習時間を伸ばす余地はある。少なくとも `max_iter=320` でも内部early stoppingは発火していない。
- ただし、学習時間を80から320へ伸ばしてもtestでNoTradeを超えない。
- validationでは改善するため、長く回すほどvalidationに適合する可能性がある。
- 今後さらに長く回す場合は、低learning rate、OOF validation、追加test月をセットにして、validation過適合かどうかを確認する。
- データ増量は面白いが、本流は「反復数を伸ばしても汎化するか」を厳密に見ること。

### 1280 Iter 追試

作業:

- iter320と同じ条件で `max_iter=1280` を試した。
- artifact: `experiments/20260627_202929_policy_iter1280_base_train/`

結果:

- 14 targetすべてが `max_iter=1280` に到達した。
- valid selection pnlは 1,025,559.2831 まで増えた。
- ただし valid R2 は long 0.0014 / short -0.0107 で、iter320より悪化。
- test R2 は long -0.0213 / short -0.0591。
- test side accuracyは 0.4744 でiter320より少し上がったが、実行可能backtestでは改善しなかった。
- validation sweepでは、30 trades/foldでも10 trades/foldでもeligible候補なし。
- 参考候補 `timed_ev entry=15 side_margin=0 risk=0.2 max_wait_regret=4 require_profit_barrier=true` のtest:
  - 2024-12: -97.7620
  - 2025-02: -97.0460

判断:

- 1280は採用しない。
- 長く回すほど内部lossとselection量は増えるが、月別validationとtest backtestは安定しない。
- 次に長時間学習を試すなら、`learning_rate` を下げ、OOFまたは月別backtestをearly stopping指標にする必要がある。

### 1.0/1.2 Target/Evaluation Alignment

方針:

- 教師生成とvalidation/test評価の倍率差が予測EVのずれを作っている可能性を検証する。
- 新dataset `data/processed/datasets/xauusd_m1_p1_l1p2/` を作成し、profit 1.0 / loss 1.2 で教師を再生成した。
- validation/test/backtestも profit 1.0 / loss 1.2 に揃えた。
- 80iterへ戻す方針を維持しつつ、ユーザー指定により320iterも比較検証した。

実験:

- iter80: `experiments/20260627_203932_policy_iter80_p1_l1p2/`
- iter320: `experiments/20260627_204140_policy_iter320_p1_l1p2/`
- report: `docs/reports/00009_2026-06-28_training_time_and_generalization.md`

結果:

- iter80は10 trades/fold条件でもvalidation eligibleなし。
- iter320は10 trades/fold条件でvalidation eligible 31件。
- min fold pnl優先候補:
  - `timed_ev entry=5 side_margin=0 risk=0.1 max_wait_regret=inf min_entry_rank=0.5 require_profit_barrier=true`
  - validation mean adjusted pnl: `+31.5473`
  - validation min adjusted pnl: `+16.5412`
  - min trades/fold: `38`
  - max drawdown: `73.3766`
- `16.5412` は4つのvalidation月のうち最悪月の月間 `total_adjusted_pnl`。1オンス前提なので概ねUSDだが、profit 1.0 / loss 1.2 を適用したadjusted値で、raw値や%ではない。
- fixed test:
  - 2024-12: adjusted pnl `-131.6996`, raw pnl `-102.5750`, 35 trades
  - 2025-02: adjusted pnl `-71.2528`, raw pnl `-42.0540`, 39 trades
- test診断sweepでは、10 trades/fold以上かつ各fold PnL 0以上のeligible候補なし。

判断:

- 倍率をtrain/valid/testで揃えてもtest汎化は改善しなかった。
- 320iterはvalidationでは成立するがholdoutで崩れるため採用しない。
- 10 trades/月条件は今後の探索で許容するが、少数tradeだけのtestプラスはedgeとして扱わない。
- 次は倍率差ではなく、validation選択の過適合、regime差、exit timing target、expected PnL calibrationを優先する。

### 長時間学習と方向性レビュー

作業:

- 1.0/1.2 aligned datasetで長時間学習を追加診断した。
- same LR: `max_iter=1280`, `learning_rate=0.03`
- low LR: `max_iter=1280`, `learning_rate=0.01`
- 実験中にdocsを再読し、方向性レビューを作成した。
- report: `docs/reports/00008_2026-06-28_research_direction_review.md`

Artifacts:

- same LR: `experiments/20260627_205602_policy_iter1280_p1_l1p2/`
- low LR: `experiments/20260627_210612_policy_iter1280_lr001_p1_l1p2/`
- training report: `docs/reports/00009_2026-06-28_training_time_and_generalization.md`

結果:

- same LR 1280:
  - validation 30 trades/fold eligibleなし。
  - validation 10 trades/fold候補は `mean pnl=15.6527`, `min pnl=1.1964` と薄い。
  - fixed test: 2024-12 `-69.7450`, 2025-02 `-137.1102`。
- low LR 1280:
  - validation 30 trades/foldでeligible 2件。
  - min fold pnl優先候補:
    - `timed_ev entry=15 side_margin=0 risk=0 max_wait_regret=inf min_entry_rank=0 require_profit_barrier=true`
    - validation mean adjusted pnl `+48.2348`
    - validation min adjusted pnl `+40.8376`
    - min trades/fold `46`
  - fixed test: 2024-12 `-134.5306`, 2025-02 `-110.0922`。
- test sweepを後付けで見るとプラス候補はあるが、最上位test候補はvalidationでは `min pnl=-28.2506` でeligibleではない。

判断:

- 低LR長時間学習はvalidationでは明確に良くなる。
- しかしtest固定適用で崩れるため、主因は学習時間不足ではなく、validation selection過適合、regime shift、EV calibration崩れ、exit timing未解決と見る。
- HGBの反復数探索はここでいったん打ち切る。
- 次は以下を優先する。
  - 2024-12/2025-02のtrade failure analyzer。
  - train期間OOF predictions。
  - side/regime別EV calibration。
  - exit timing target強化。
  - shared representationを持つ小型MLP/TCN。

### 汎化原則レビューと失敗trade分析

作業:

- トレードMLの汎化原則を `docs/trading_ml_generalization_principles.md` に整理した。
- 現状がその原則を守れているかを `docs/reports/00011_2026-06-28_generalization_principles_review.md` にレビューした。
- 低LR1280モデルの固定test負けを分解する `trade-backtest analyze-trades` を追加した。
- 失敗trade分析レポートを `docs/reports/00010_2026-06-28_trade_failure_analysis.md` に作成した。

判断:

- NoTrade比較、月別validation/test、次足open約定、executable backtest、失敗trade分析は守れている。
- purging / embargo、regime別標準評価、spread/slippage/delay感度、validationを見すぎない運用は未整備。
- 2024-12/2025-02は何度も見たため、今後の最終holdoutとしては弱い。
- 低LR1280のtest失敗では、予測EVが実現PnLに対して平均約22ドル過大だった。
- actual barrier miss、direction error、exit regretが損失の中心。
- predicted barrierは今回の全tradeを通しており、filterとして弱い。
- `min_entry_rank=0.5` focused sweepは損失を抑えたが、NoTradeには届かなかった。

次の行動:

1. analyzerを今後の候補診断に必須化する。
2. regime labelをdataset/backtest reportへ追加する。
3. spread/slippage/delay sensitivityをbacktestへ追加する。
4. purged/embargo walk-forward splitを実装する。
5. OOF predictionsとside/regime別EV calibrationへ進む。

### Regime / Cost / Purge Controls

作業:

- `src/trade_data/regime.py` を追加し、regime scoreとregime categoryを標準化した。
- datasetに `trend_score_240`, `volatility_score_60` をfeatureとして追加し、`trend_regime`, `volatility_regime`, `session_regime`, `gap_regime`, `combined_regime` を診断列として保存するようにした。
- `analyze-trades` がregime別group outputを出せるようにした。
- backtestに `spread_points`, `slippage_points`, `execution_delay_bars` を追加した。
- 固定policyのコスト感度を見る `model-cost-sensitivity` を追加した。
- `trade_data.modeling train` に `--purge-label-overlap` と `--embargo-hours` を追加した。デフォルトでラベル期間が後続valid/testに重なるtrain/valid行をpurgeする。
- report: `docs/reports/00012_2026-06-28_regime_cost_purge_controls.md`

検証:

- `python3 -m unittest discover tests`: 40 tests OK。
- `git diff --check`: OK。
- `model-cost-sensitivity --help` と `modeling train --help`: OK。

判断:

- 検証設計上の不足だったregime分析、執行stress、label overlap purgeの土台は入った。
- この時点では既存datasetにregime列がなかったため、次はdataset再生成が必要と判断した。
- 次の実験は、regime列込みdataset、purge有効学習、固定policyのcost sensitivity、regime別failure analysisの順に進める。

### Regime/Purge HGB 80iter Follow-up

作業:

- 1.0/1.2 aligned datasetをregime列込みで 2023-01 から 2025-02 まで再生成した。
- `feature_count` は 49。追加featureは `trend_score_240` と `volatility_score_60`。
- purge実装にバグを発見した。複数test月を1つの連続windowとして扱い、2025-01 validが丸ごと落ちていた。
- `dataset_month` ごとにblocked windowを分割するよう修正し、非連続test月の間にあるvalid月を保持するテストを追加した。
- purge有効、embargo 24hで HGB 80iter policy modelを再学習した。

Artifact:

- model: `experiments/20260627_215123_policy_iter80_p1_l1p2_regime_purge_e24_v2/`
- validation sweep summary: `data/reports/backtests/20260627_215228_model_sweep_summary/`
- fixed test: `data/reports/backtests/20260627_215245_model_timed_ev_2024-12/`, `data/reports/backtests/20260627_215245_model_timed_ev_2025-02/`
- regime analysis: `data/reports/backtests/20260627_215257_analyze_regime_purge_v2_2024-12/`, `data/reports/backtests/20260627_215257_analyze_regime_purge_v2_2025-02/`

結果:

- 修正後purge: train 546,537 -> 535,493、valid 119,241 -> 112,494、test 56,204。
- 30 trades/fold条件ではeligibleなし。
- 10 trades/fold条件では `timed_ev entry=15 risk=0 max_wait=2 min_rank=0.5` が validation全foldプラス。
- fixed test:
  - 2024-12: adjusted pnl `-35.7010`, 15 trades, max DD `58.5892`
  - 2025-02: adjusted pnl `-47.6716`, 17 trades, max DD `54.6236`
- 多めに取引するeligible候補は 2024-12 `-154.9860`、2025-02 `-125.5468` と悪化。
- regime分析では、両testともtradeが `low_vol` に集中した。
- 2025-02は `asia` が `-46.9276`、`rollover` が `-24.8160`、`ny_late` が `+24.0720`。

判断:

- regime/cost/purgeの基盤は有効だが、HGB 80iterの汎化成績はまだ改善していない。
- NoTradeに負けているため採用不可。
- 次は低ボラ・asia・rolloverでentryを抑えるregime gate、direction/regime別calibration、profit barrier確率化を試す。

### Regime Gate Experiment

作業:

- `model-policy` / `model-sweep` に hard regime gate を追加した。
- `--block-trend-regimes`, `--block-volatility-regimes`, `--block-session-regimes`, `--block-gap-regimes`, `--block-combined-regimes` を追加。
- gate条件は `quality_ok` に合成し、新規entryだけを抑制する。保有中のexitや強制決済は変えない。
- `model-sweep-summary` では block条件もpolicy keyに含め、gateあり/なしを別候補として集計する。
- report: `docs/reports/00013_2026-06-28_regime_gate_experiment.md`

検証:

- `python3 -m unittest discover tests`: 41 tests OK。
- `git diff --check`: OK。

Validation:

- 対象モデル: `experiments/20260627_215123_policy_iter80_p1_l1p2_regime_purge_e24_v2/`
- validation: 2024-07, 2024-09, 2024-11, 2025-01。
- `asia,rollover` gate top: mean pnl `31.3258`, min pnl `21.4868`, min trades `16`。
- `asia` gate top: mean pnl `40.0143`, min pnl `16.6970`, min trades `17`。
- `rollover` gate top: mean pnl `62.6525`, min pnl `38.4034`, min trades `15`。

Fixed test:

- `asia,rollover` validation top: 2024-12 `-121.9240`, 2025-02 `+58.5242`。
- `asia` validation top: 2024-12 `-127.9708`, 2025-02 `+63.3104`。
- `rollover` validation top: 2024-12 `-37.5214`, 2025-02 `-38.0992`。
- 前回候補に `asia,rollover` を足した場合: 2024-12 `+5.8384`、2025-02 `+24.0720`。ただし 7 trades / 3 trades と薄い。

判断:

- hard gateは損失回避のablationとして有用。
- ただし、採用policyとしては月間regime差に弱い。
- `asia` / `asia,rollover` は 2025-02を改善するが2024-12を悪化させる。
- `rollover` はvalidationでは強いがtestではNoTradeに負ける。
- 本流は hard block ではなく、side/regime別EV calibration、予測EV shrinkage、regime別threshold offsetへ進める。

### Side/Regime EV Calibration

作業:

- `trade_data.meta_model` に side/regime EV calibration を追加した。
- `fit-group-calibration` と `oof-group-calibration` を追加した。
- 出力列は `pred_regime_calibrated_long_best_adjusted_pnl` / `pred_regime_calibrated_short_best_adjusted_pnl`。
- validation内OOFでは、各validation月をholdoutし、残りvalidation月でcalibratorをfitする。
- testにはvalidation全体でfitしたcalibratorを固定適用する。
- report: `docs/reports/00014_2026-06-28_side_regime_ev_calibration.md`

検証:

- `python3 -m unittest tests.test_meta_model`: 11 tests OK。
- `python3 -m trade_data.meta_model oof-group-calibration --help`: OK。
- `git diff --check`: OK。

実験:

- 対象モデル: `experiments/20260627_215123_policy_iter80_p1_l1p2_regime_purge_e24_v2/`
- group columns: `volatility_regime,session_regime`
- validation: 2024-07, 2024-09, 2024-11, 2025-01。
- test: 2024-12, 2025-02。

Shrink to group mean:

- artifact: `experiments/20260627_221255_regime_ev_calib_vol_session/`
- summary: `data/reports/backtests/20260627_221441_model_sweep_summary/`
- OOF validation top: mean pnl `63.4787`, min pnl `13.9340`, min trades `28`。
- fixed test: 2024-12 `-260.2992`, 2025-02 `-6.6830`。

Residual offset:

- artifact: `experiments/20260627_221536_regime_ev_calib_vol_session_offset/`
- summary: `data/reports/backtests/20260627_221737_model_sweep_summary/`
- OOF validation top: mean pnl `102.5949`, min pnl `73.6080`, min trades `54`。
- fixed test top: 2024-12 `-185.8364`, 2025-02 `-65.1476`。
- fixed test conservative candidate: 2024-12 `-149.2616`, 2025-02 `-10.7646`。

判断:

- OOF validationでは強く改善するが、fixed testではraw EV候補より悪い。
- validation 4ヶ月だけのside/regime補正は未知test月へ汎化していない。
- calibrated EVはtestでentry数を増やしすぎる。
- 現時点では採用不可。
- 次は train期間OOF predictions を作ってcalibration fit月数を増やすか、exit timing target改善を優先する。

### Train-Period OOF Prediction Infrastructure

作業:

- `trade_data.modeling` に `oof` サブコマンドを追加した。
- 指定したOOF対象月を `--fold-month-count` ごとのholdout foldに分ける。
- 各foldでholdout月を学習から外し、必要なら `--purge-label-overlap` と `--embargo-hours` でlabel overlapを削除する。
- 予測は `predictions_oof.parquet` に保存する。
- report: `docs/reports/00015_2026-06-28_train_oof_predictions_infra.md`

検証:

- `python3 -m unittest tests.test_modeling`: 17 tests OK。
- `python3 -m trade_data.modeling oof --help`: OK。
- 軽量smoke run: `experiments/20260627_222746_oof_smoke_policy/`
- `python3 -m unittest discover tests`: 47 tests OK。
- `git diff --check`: OK。

判断:

- train期間OOF predictionsを作るための基盤は整った。
- smoke runは機能確認用であり、スコアは研究判断に使わない。
- 次は HGB 80iter regime/purge v2 と同じtrain monthsで本番OOFを実行し、validation OOFと結合してside/regime calibrationを再評価する。

### Train OOF Calibration and Loss 1.20 Standard

作業:

- `oof-group-calibration` に `--base-fit-predictions` / `--base-fit-months` を追加した。
- 各validation holdoutのcalibration fitを `train OOF + 他validation月` に変更できるようにした。
- `trade_data.dataset` と `trade_data.backtest` のデフォルト倍率を profit 1.0 / loss 1.20 に変更した。
- ADR `docs/decisions/0006_loss_multiplier_120_standard.md` を追加した。
- report: `docs/reports/00017_2026-06-28_train_oof_calibration_loss120.md`

実験:

- train OOF: `experiments/20260627_223559_policy_train_oof_4m_p1_l1p2_regime_purge_e24/`
- offset calibration: `experiments/20260627_223950_regime_ev_calib_train_oof4m_vol_session_offset/`
- shrink065 calibration: `experiments/20260627_224357_regime_ev_calib_train_oof4m_vol_session_shrink065/`
- shrink065 loss1.20 summary: `data/reports/backtests/20260627_224840_model_sweep_summary/`
- offset loss1.20 summary: `data/reports/backtests/20260627_225028_model_sweep_summary/`

結果:

- shrink065 top-min validation: mean pnl `49.9715`, min pnl `41.1354`, min trades `10`, max DD `35.1396`。
- shrink065 top-min fixed test: 2024-12 `+18.8306`, 2025-02 `-44.5990`。
- offset top-min validation: mean pnl `72.3580`, min pnl `46.8804`, min trades `15`, max DD `47.0160`。
- offset top-min fixed test: 2024-12 `-63.2266`, 2025-02 `-44.3740`。

判断:

- loss 1.20統一で損益は改善したが、NoTradeを安定して超える状態ではない。
- train OOFをcalibration fitに足す方向は、entry過多の抑制には効いた。
- shrink065は2024-12をプラス化したが、2025-02では少数のshort失敗が損失を支配する。
- 次は2025-02 short失敗tradeのregime/session分解と、exit timing targetの改善を優先する。

### 2026-06-28 08:07 JST Calibrated Trade Failure And Exit Targets

作業:

- `analyze-trades` に `--long-column` / `--short-column` を追加し、calibrated EV列を指定してtrade failure分析できるようにした。
- 既存レポートに日付だけでなく時刻を入れる運用へ変更した。
- 既存 `docs/reports/*.md` の冒頭メタデータを時刻付きへ整えた。通し番号や並びは本文の `日時` を基準にし、ファイル更新時刻や `更新日時` は採番に使わない。
- `future_best_labels` に固定保有 60/240/720 分のlong/short adjusted pnl targetを追加した。
- `modeling` は古いdatasetにも対応できるよう、存在しない研究用targetを自動的に落とし、missing targetsをmetricsへ記録するようにした。
- report: `docs/reports/00016_2026-06-28_calibrated_trade_failure_exit_targets.md`

結果:

- calibrated列で再分析した shrink065 top-min は、2024-12 `+18.8306`、2025-02 `-44.5990`。
- 2025-02は 12 trades、direction error rate `0.7500`、predicted side error rate `0.7500`、EV overestimate vs realized mean `20.0388`。
- 2025-02の実績best sideがshortだった8 tradesは全てlongで入り、adjusted pnl `-30.7830`。
- 唯一のshortは `2025-02-10 04:32 UTC` の `asia/up/low_vol` で、adjusted pnl `-39.0000`。

判断:

- 問題は単純な「shortが多すぎる」ではなく、calibrated EVの方向選択が未知月で壊れていること。
- 全tradeでexit regretが正で、勝ちtradeも含めて手放し方に改善余地がある。
- 固定horizon targetはまずfull target setの研究用targetとして追加し、policy target setにはまだ入れない。

### 2026-06-28 08:26 JST Fixed Horizon Exit Policy

作業:

- `data/processed/datasets/xauusd_m1_p1_l1p2/` を 2023-01 から 2025-02 まで再生成し、固定保有 60/240/720 分targetを実データに反映した。
- `trade_data.backtest` に `fixed_horizon_ev` policyを追加した。
- `--extra-side-margin-rules` を追加し、`session_regime=asia:5,session_regime=rollover:5` のようなregime別追加side marginを指定できるようにした。
- `target-set full` のHGB 80iterモデルを学習した。
- report: `docs/reports/00018_2026-06-28_fixed_horizon_exit_policy.md`

Artifacts:

- model: `experiments/20260627_231921_full_fixed_horizon_targets_p1_l1p2/`
- no extra margin validation summary: `data/reports/backtests/20260627_232147_model_sweep_summary/`
- asia/rollover +5 validation summary: `data/reports/backtests/20260627_232445_model_sweep_summary/`
- fixed test: `data/reports/backtests/20260627_232459_model_fixed_horizon_ev_2024-12/`, `data/reports/backtests/20260627_232459_model_fixed_horizon_ev_2025-02/`

結果:

- validation top-min候補: `fixed_horizon_ev`, entry `2`, side margin `2`, max wait regret `4`, min entry rank `0.5`, barrierなし, `asia/rollover +5`。
- validation: mean pnl `27.2219`, min pnl `19.1398`, min trades `45`, max DD `50.3740`。
- fixed test 2024-12: adjusted pnl `+30.2662`, 58 trades, max DD `25.2926`。
- fixed test 2025-02: adjusted pnl `+4.6898`, 71 trades, max DD `99.4746`。

判断:

- validationで選んだ同一候補が 2024-12 / 2025-02 の両test月でNoTradeを上回った。
- ただし2025-02のedgeは薄く、slippageやspreadで消える。
- 2025-02はlong pnl `+17.6144`、short pnl `-12.9246` で、short側の弱さは残る。
- 次は short専用entry threshold / side margin、barrier hit probability calibration、コスト込みvalidation選択を優先する。

### 2026-06-28 08:38 JST Side-Specific Entry Offsets

作業:

- `model-policy` / `model-sweep` に `long_entry_threshold_offset` と `short_entry_threshold_offset` を追加した。
- `SWEEP_KEY_COLUMNS` と `model-sweep-summary` 正規化にoffset列を追加した。
- `stateless_ev`, `stateful_ev`, `timed_ev`, `fixed_horizon_ev` のentry判定とflip判定にside別thresholdを適用した。
- レポート時刻を `YYYY-MM-DD HH:MM JST` で記録する方針を再確認し、既存fixed horizonレポートにも更新時刻を追記した。
- report: `docs/reports/00019_2026-06-28_side_specific_entry_offsets.md`

実験:

- model: `experiments/20260627_231921_full_fixed_horizon_targets_p1_l1p2/`
- validation months: 2024-07, 2024-09, 2024-11, 2025-01
- grid: entry `0,2,4`, long offset `0`, short offset `0,2,4,6,8`, side margin `1,2,3`
- no-cost summary: `data/reports/backtests/20260627_233509_model_sweep_summary/`
- cost-aware summary: `data/reports/backtests/20260627_233552_model_sweep_summary/`

結果:

- no-cost / cost-aware validation top-minはともに `entry=0`, `short offset=4`, `side margin=2`。
- top-min候補のfixed testは 2024-12 `+22.7102`、2025-02 `+0.3502`。前回候補より2025-02が薄くなった。
- validation rank-3の `entry=0`, `short offset=8`, `side margin=2` は診断比較で 2024-12 `+27.4184`、2025-02 `+26.8074`。
- `short offset=8` のcost sensitivityは 2024-12で spread `0.2` / slippage `0.10` / delay `1` が `-7.0904`、2025-02で同条件が `+16.8146`。
- trade failure分析では、2024-12 direction error rate `0.6034`、2025-02 `0.4754`。2025-02のexit regret sumは `1189.8406` で依然大きい。

判断:

- short専用entry threshold offsetは有効な調整軸。
- validation top-minだけでは未知月の安定性を選び切れていない。
- `short offset=8` はfixed test上では良いが、testを見てからの採用になるため本採用しない。
- 次は事前登録した選択基準として、cost-aware validation、周辺offsetの台地、side/regime別PnL、max drawdown、execution delay感度を組み込む。
- 新しいblind holdout月を追加し、2024-12/2025-02を見すぎない。

### 2026-06-28 08:53 JST Blind Holdout Candidate Selection

作業:

- `model-candidate-selection` を追加し、no-cost/cost-aware validation、cost drop、side loss、short offset plateauを同時に評価できるようにした。
- 2025-03 の p1/l1.2 fixed horizon datasetを追加生成した。
- 前回fixed horizon modelと同じtrain/validationで、testだけ2025-03にしたHGB 80iter full modelを学習した。
- report: `docs/reports/00020_2026-06-28_blind_holdout_candidate_selection.md`

Artifacts:

- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-03_h24_edge15.parquet`
- model: `experiments/20260627_235034_full_fixed_horizon_blind_2025_03_p1_l1p2/`
- candidate selection: `data/reports/backtests/20260627_235220_model_candidate_selection/`
- blind test: `data/reports/backtests/20260627_235231_model_fixed_horizon_ev_2025-03/`
- cost sensitivity: `data/reports/backtests/20260627_235330_model_cost_sensitivity_2025-03/`

結果:

- candidate selection条件は `max_forced_exit_rate=0.04`, `max_side_loss_per_fold=45`, cost drop max `20`, short offset plateau radius `4`。
- validation選択候補は `fixed_horizon_ev`, entry `0`, short offset `8`, side margin `1`。
- 2025-03 blind holdoutは adjusted pnl `-49.7004`, raw pnl `-24.2030`, 63 trades, profit factor `0.6751`, max DD `73.8334`。
- long pnl `-0.3766`、short pnl `-49.3238`。short 5 tradesのうち、2025-03-31 01:28 UTC の1 tradeが `-49.3248`。
- 最大損失tradeは `range / low_vol / asia`、actual best sideはlong、predicted short fixed EVは `9.5934`、predicted short profit barrier hitは `0`。
- cost sensitivityは全条件でマイナス。spread `0.2` / slippage `0.10` / delay `1` では adjusted pnl `-75.9388`。

判断:

- short offsetとcost-aware validationだけでは汎化不足。
- 2024-12/2025-02で良く見えたshort offset候補は、2025-03でNoTradeに負けたため採用しない。
- 最大損失は predicted profit barrier hitが0のshortを許したこと、かつ721分まで保有したことが中心。
- 次は profit barrier probability calibration、`asia / range / low_vol` shortの抑制、hazard-like close probability / stop-loss timing targetを優先する。

### 2026-06-28 09:08 JST Profit Barrier Probability Gate

作業:

- binary classifierのclass `1` probabilityを `pred_<target>_prob` として保存するようにした。
- `model-policy` に `--profit-barrier-threshold`、`model-sweep` に `--profit-barrier-thresholds` を追加した。
- `SWEEP_KEY_COLUMNS` とsummary正規化へ `profit_barrier_threshold` を追加し、閾値違いの候補が混ざらないようにした。
- 既存 `docs/reports/*.md` の冒頭メタデータを時刻付きへ整えた。通し番号や並びは本文の `日時` を基準にし、ファイル更新時刻や `更新日時` は採番に使わない。
- report: `docs/reports/00021_2026-06-28_profit_barrier_probability_gate.md`

Artifacts:

- model: `experiments/20260628_000509_full_fixed_horizon_blind_2025_03_barrier_prob_p1_l1p2/`
- no-cost validation sweeps: `data/reports/backtests/20260628_000602_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware validation sweeps: `data/reports/backtests/20260628_000643_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection: `data/reports/backtests/20260628_000706_model_candidate_selection/`
- blind test: `data/reports/backtests/20260628_000729_model_fixed_horizon_ev_2025-03/`
- cost sensitivity: `data/reports/backtests/20260628_000839_model_cost_sensitivity_2025-03/`
- failure analysis: `data/reports/backtests/20260628_000901_barrier_prob_gate_2025-03/`

結果:

- validation選択候補は `fixed_horizon_ev`, entry `0`, short offset `8`, side margin `1`, profit barrier threshold `0.40`。
- validation base min pnl `22.4864`, base mean pnl `49.7168`, cost min pnl `17.4064`, cost mean pnl `43.1869`, min trades `24`。
- 2025-03 blindは adjusted pnl `-29.5462`, raw pnl `-14.4330`, 29 trades, profit factor `0.6742`, max DD `54.1392`。
- long pnl `+18.0844`、short pnl `-47.6306`。
- 前回blind `-49.7004` より損失は縮小したが、NoTrade `0.0` には届かない。
- cost sensitivityは全条件でマイナス。spread `0.2` / slippage `0.10` / delay `1` は adjusted pnl `-55.7310`。
- 最大損失は引き続き 2025-03-31 01:28 UTC の `asia / range / low_vol` shortで、adjusted pnl `-49.3248`。
- このtradeの predicted short barrier probabilityは `0.4859`。閾値 `0.50` なら落ちるが、validationでは月10tradesを満たしにくく、blind後の診断でも `6` trades / adjusted pnl `-39.5282` と悪化した。

判断:

- profit barrier probability gateは有効なfilter軸だが、単独では採用不可。
- 最大損失は barrier確率だけでなく、fixed horizon 720m short EVの過大評価とexit timingの遅さが重なっている。
- 次は `asia / range / low_vol` のshortだけを抑制する side-specific regime suppression、exit timing target、candidate selectionへのprofit barrier miss率追加を優先する。

### 2026-06-28 09:26 JST Side-Specific Regime Suppression

作業:

- `model-policy` / `model-sweep` に `--side-block-rules` と `--side-extra-margin-rules` を追加した。
- rule形式は `short:session_regime=asia`、`short:trend_regime=range+volatility_regime=low_vol+session_regime=asia`、`short:session_regime=asia:5`。
- `model-candidate-selection` の集計keyへ `side_extra_margin_rules` / `side_block_rules` を追加した。
- 既存レポート `docs/reports/00021_2026-06-28_profit_barrier_probability_gate.md` は更新時刻 `2026-06-28 09:26 JST` で追記した。
- report: `docs/reports/00022_2026-06-28_side_specific_regime_suppression.md`

Artifacts:

- narrow candidate selection: `data/reports/backtests/20260628_001732_model_candidate_selection/`
- medium candidate selection: `data/reports/backtests/20260628_002001_model_candidate_selection/`
- asia short candidate selection: `data/reports/backtests/20260628_002217_model_candidate_selection/`
- validation-selected blind: `data/reports/backtests/20260628_002235_model_fixed_horizon_ev_2025-03/`
- reference blind: `data/reports/backtests/20260628_002236_model_fixed_horizon_ev_2025-03/`
- cost sensitivity: `data/reports/backtests/20260628_002255_model_cost_sensitivity_2025-03/`
- failure analysis: `data/reports/backtests/20260628_002507_side_specific_asia_short_block_2025-03/`

結果:

- `short:trend_regime=range+volatility_regime=low_vol+session_regime=asia` は、2025-03 blindを `-27.4534` までしか改善しなかった。`trend_regime` が変わった直後の再entryを許した。
- `short:volatility_regime=low_vol+session_regime=asia` は、2025-03 blind `-26.8930`。`asia / normal_vol` shortへの再entryを許した。
- `short:session_regime=asia` はvalidation-selected `entry=0`, `short offset=6`, `side_margin=1`, `barrier threshold=0.40` で、2025-03 blind adjusted pnl `+18.0748`, raw pnl `+29.2330`, 35 trades, profit factor `1.2700`, max DD `44.6526`。
- 同candidateのshort pnlは `-0.0096` で、2025-03の最大short損失はほぼ消えた。
- ただし spread `0.2` / slippage `0.10` / delay `1` では adjusted pnl `-6.1046` まで落ちる。
- `short offset=8` referenceは2025-03 blind `+27.1356`、最悪コスト条件でも `+5.4936` だが、validation選択では2番手なので採用しない。

判断:

- `short:session_regime=asia` は、今回のlineで初めて2025-03 blindのNoTradeを上回った。
- ただし2025-03の最大損失を見た後に作ったruleなので、2025-03でのプラスは最終採用根拠にしない。
- 次は2025-04以降のblindで事前登録候補として検証する。
- failure analysisでは direction error rate `0.4286`、predicted side error rate `0.4571`、exit regret sum `702.5012` が残る。改善は方向予測ではなく、危険時間帯のshortをno-trade化した効果が中心。
- 次の本流は、side/regime別損失集中をcandidate selectionに入れることと、exit timing target改善。

### 2026-06-28 09:39 JST 2025-04/05 Blind Check For Asia Short Block

作業:

- 2025-04 / 2025-05 の p1/l1.2 fixed horizon datasetを生成した。
- 同じtrain/validation条件で、testだけ2025-04 / 2025-05にしたHGB 80iter full modelを学習した。
- 2025-03後に事前登録した `short:session_regime=asia` 候補を固定適用した。
- 既存レポート `docs/reports/00022_2026-06-28_side_specific_regime_suppression.md` は更新時刻 `2026-06-28 09:39 JST` で追記した。

Artifacts:

- dataset 2025-04: `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-04_h24_edge15.parquet`
- dataset 2025-05: `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-05_h24_edge15.parquet`
- model 2025-04: `experiments/20260628_003331_full_fixed_horizon_blind_2025_04_barrier_prob_p1_l1p2/`
- model 2025-05: `experiments/20260628_003756_full_fixed_horizon_blind_2025_05_barrier_prob_p1_l1p2/`
- 2025-04 selected: `data/reports/backtests/20260628_003401_model_fixed_horizon_ev_2025-04/`
- 2025-04 cost sensitivity: `data/reports/backtests/20260628_003424_model_cost_sensitivity_2025-04/`
- 2025-04 failure analysis: `data/reports/backtests/20260628_003423_side_specific_asia_short_block_2025-04/`
- 2025-05 selected: `data/reports/backtests/20260628_003824_model_fixed_horizon_ev_2025-05/`
- 2025-05 cost sensitivity: `data/reports/backtests/20260628_003846_model_cost_sensitivity_2025-05/`
- 2025-05 failure analysis: `data/reports/backtests/20260628_003846_side_specific_asia_short_block_2025-05/`

結果:

- 固定候補は `fixed_horizon_ev`, entry `0`, short offset `6`, side margin `1`, max wait regret `4`, min entry rank `0.5`, barrier threshold `0.40`, `short:session_regime=asia`。
- 2025-04 selectedは adjusted pnl `+56.3148`, raw pnl `+81.4040`, 31 trades, profit factor `1.3741`, max DD `56.7380`。
- 2025-04 blockなし同条件は adjusted pnl `-24.5976`、short pnl `-79.7916`。blockなしでは `asia` shortが 14 trades / `-106.2104`。
- 2025-04 cost worst spread `0.2` / slippage `0.10` / delay `1` は adjusted pnl `+51.5630`。
- 2025-05 selectedは adjusted pnl `+83.0630`, raw pnl `+109.8070`, 28 trades, profit factor `1.5176`, max DD `53.2900`。
- 2025-05 blockなし同条件は adjusted pnl `-57.6474`、short pnl `-77.4874`。blockなしでは `asia` shortが 15 trades / `-100.5254`。
- 2025-05 cost worst spread `0.2` / slippage `0.10` / delay `1` は adjusted pnl `+68.2500`。
- offset8 referenceは2025-04 `+10.4808`、2025-05 `+7.1750` で、validation-selected offset6より明確に弱い。

判断:

- `short:session_regime=asia` は2025-04/05でも機能し、2025-03専用の後付けruleではない可能性が高まった。
- 暫定採用候補へ昇格する。
- ただし2025-04 failure analysisでは direction error rate `0.5161`、predicted side error rate `0.5484`、exit regret sum `1183.4512`。方向予測そのものは依然弱い。
- 次はcandidate selectionへside/session別損失集中を追加し、このruleを手作業ではなくvalidation内で検出できるようにする。

### 2026-06-28 09:51 JST Direction Session Candidate Gate

作業:

- `model-sweep` metricsへ `direction_session_adjusted_pnl_min`, `worst_direction_session`, `worst_direction_session_trade_count` を追加した。
- `model-candidate-selection` に `--max-direction-session-loss-per-fold` を追加した。
- 古いsweep CSVは新列なしでも読めるよう、normalize時は `direction_session_adjusted_pnl_min=inf` として扱う。
- report: `docs/reports/00023_2026-06-28_direction_session_candidate_gate.md`

Artifacts:

- no-cost no block: `data/reports/backtests/20260628_005016_model_sweep_2025-05/`
- no-cost asia short block: `data/reports/backtests/20260628_005016_model_sweep_2025-05_1/`
- cost no block: `data/reports/backtests/20260628_005015_model_sweep_2025-05_1/`
- cost asia short block: `data/reports/backtests/20260628_005015_model_sweep_2025-05/`
- candidate selection: `data/reports/backtests/20260628_005032_model_candidate_selection/`

結果:

- 2025-05 no blockは `direction_session_adjusted_pnl_min=-100.5254`, `worst_direction_session=short:asia`, costでは `-103.8054`。
- 2025-05 asia short blockは `direction_session_adjusted_pnl_min=+19.8400`, costでは `+17.4840`。
- `--max-direction-session-loss-per-fold 45` により、no blockは `direction_session_loss_ok=False`, `eligible=False`、blockありは `eligible=True`。

検証:

- `python3 -m py_compile src/trade_data/backtest.py`: OK。
- `python3 -m unittest tests.test_backtest`: 26 tests OK。
- `python3 -m unittest discover tests`: 62 tests OK。
- `model-candidate-selection --help`, `model-sweep --help`: OK。
- `git diff --check`: OK。

判断:

- side/session別損失集中を候補選択へ組み込めるようになった。
- 次は predicted/actual profit barrier miss率もcandidate selectionへ追加する。

### 2026-06-28 09:54 JST Report Timestamp Normalization

作業:

- 既存 `docs/reports/*.md` の旧形式レポートに、冒頭の `日時` / `更新日時` を追加した。
- 旧Summary内の `- Datetime` / `- Updated` は、重複しないよう冒頭メタデータへ移した。
- `docs/README.md`, `docs/experiment_protocol.md`, `docs/templates/experiment_report.md` を、冒頭に `日時` と `更新日時` を置く運用へ更新した。

判断:

- レポート作成時刻と更新時刻は、以後 `YYYY-MM-DD HH:MM JST` で明示する。
- 既存レポートの補正では、既存の `Datetime` / `Updated` 記録を優先し、不足分だけ確認可能な時刻情報で補った。通し番号や並びは本文の `日時` を基準にし、ファイル更新時刻や `更新日時` は採番に使わない。

### 2026-06-28 10:06 JST Profit Barrier Miss Candidate Gate

作業:

- `model-policy` / `model-sweep` metricsへ predicted/actual profit barrier miss率を追加した。
- `model-candidate-selection` に `--max-predicted-profit-barrier-miss-rate` と `--max-actual-profit-barrier-miss-rate` を追加した。
- `require_profit_barrier=false` でも、prediction parquetにbarrier列が存在すれば predicted miss を測れるよう、barrier列を任意読み込みにした。
- report: `docs/reports/00024_2026-06-28_profit_barrier_miss_candidate_gate.md`

Artifacts:

- model-policy block: `data/reports/backtests/20260628_010449_model_fixed_horizon_ev_2025-05/`
- model-policy no block: `data/reports/backtests/20260628_010449_model_fixed_horizon_ev_2025-05_1/`
- no-cost no block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05_1/`
- no-cost asia short block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05_3/`
- cost no block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05_2/`
- cost asia short block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05/`
- candidate selection: `data/reports/backtests/20260628_010550_model_candidate_selection/`

結果:

- 2025-05 no blockは `actual_profit_barrier_miss_rate=0.5000`, `actual_profit_barrier_miss_count=17`, `actual_profit_barrier_miss_adjusted_pnl=-221.5828`。
- 2025-05 asia short blockは `actual_profit_barrier_miss_rate=0.464286`, `actual_profit_barrier_miss_count=13`, `actual_profit_barrier_miss_adjusted_pnl=-126.3004`。
- `--max-actual-profit-barrier-miss-rate 0.48` により、direction/session gateを緩めても no blockは `actual_profit_barrier_miss_ok=False`, blockありは `eligible=True`。
- `predicted_profit_barrier_miss_rate` は両候補とも `0.0`。barrier thresholdを通過した候補の過大評価はmiss率だけでは検出できない。

検証:

- `python3 -m py_compile src/trade_data/backtest.py`: OK。
- `python3 -m unittest tests.test_backtest`: 28 tests OK。
- `python3 -m unittest discover tests`: 64 tests OK。
- `model-candidate-selection --help`, `model-sweep --help`: OK。

判断:

- actual barrier miss率は候補選択の追加gateとして機能する。
- 閾値 `0.48` はsmoke用であり、採用するにはvalidation fold全体で台地を見る。
- 次は predicted probability bucket別のactual hit rateを標準診断に入れ、calibrationの過大評価を直接見る。

### 2026-06-28 10:19 JST Report Sequence Numbers

作業:

- `docs/reports` の既存24本を `00001_YYYY-MM-DD_slug.md` 形式へリネームした。
- 通し番号はファイルシステムの更新時刻ではなく、各レポート本文冒頭の `日時: YYYY-MM-DD HH:MM JST` の昇順で決めた。
- docs内の既存レポート参照を通し番号付きパスへ更新した。
- `GOAL.md`, `docs/README.md`, `docs/experiment_protocol.md`, `docs/templates/experiment_report.md` に命名ルールを追加した。

判断:

- 新規 `docs/reports` レポートは、既存最大番号の次を使う。
- 採番順を判断するときは、必ずレポート本文の `日時` を見る。`更新日時` やファイル更新時刻は採番基準にしない。

### 2026-06-28 10:21 JST Profit Barrier Calibration Candidate Gate

作業:

- predicted profit barrier probability bucket別のactual hit rateを `model-policy` / `model-sweep` metricsへ追加した。
- bucketは `0.0-0.2`, `0.2-0.4`, `0.4-0.6`, `0.6-0.8`, `0.8-1.0`。
- `model-candidate-selection` に `--max-profit-barrier-calibration-overestimate` を追加した。
- candidate selectionのsummaryは横に広くなりすぎないよう、bucket詳細は `model-sweep` metricsに残し、candidate selectionではsummary列だけを集計する。
- report: `docs/reports/00025_2026-06-28_profit_barrier_calibration_candidate_gate.md`

Artifacts:

- no-cost no block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05_2/`
- no-cost asia short block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05_1/`
- cost no block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05_3/`
- cost asia short block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05/`
- candidate selection: `data/reports/backtests/20260628_011509_model_candidate_selection/`

結果:

- 2025-05 no blockは calibration overestimate max `0.054305`。worst bucketは `0.6-0.8`, count `5`, predicted mean `0.654305`, actual hit rate `0.600000`。
- 2025-05 asia short blockは calibration overestimate max `0.248089`。worst bucketは `0.6-0.8`, count `7`, predicted mean `0.676661`, actual hit rate `0.428571`。
- `--max-profit-barrier-calibration-overestimate 0.2` では、no blockは `profit_barrier_calibration_ok=True`、blockありは `False`。

検証:

- `python3 -m py_compile src/trade_data/backtest.py`: OK。
- `python3 -m unittest tests.test_backtest`: 30 tests OK。
- `python3 -m unittest discover tests`: 66 tests OK。
- `model-candidate-selection --help`, `model-sweep --help`: OK。

判断:

- calibration overestimateは、barrier threshold通過後の過大評価を検出する診断軸として有効。
- ただし今回のsmokeでは、PnLが良いblockあり候補のほうがcalibration overestimateは悪い。
- したがって `--max-profit-barrier-calibration-overestimate 0.2` は採用閾値にしない。validation fold全体で台地を見るまでhard gateではなく診断値として扱う。

### 2026-06-28 10:37 JST 2025-06 Blind Holdout Failure

作業:

- 2025-06 の p1/l1.2 fixed horizon datasetを追加生成した。
- 同じtrain/validation設定で、2025-06 blind modelを学習した。
- report: `docs/reports/00026_2026-06-28_blind_2025_06_asia_short_block_failure.md`

Artifacts:

- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-06_h24_edge15.parquet`
- model: `experiments/20260628_013141_full_fixed_horizon_blind_2025_06_barrier_prob_p1_l1p2/`
- selected asia short block: `data/reports/backtests/20260628_013232_model_fixed_horizon_ev_2025-06_1/`
- no block: `data/reports/backtests/20260628_013232_model_fixed_horizon_ev_2025-06/`
- offset8 reference: `data/reports/backtests/20260628_013232_model_fixed_horizon_ev_2025-06_2/`
- cost sensitivity: `data/reports/backtests/20260628_013232_model_cost_sensitivity_2025-06/`
- failure analysis: `data/reports/backtests/20260628_013257_side_specific_asia_short_block_2025-06/`
- validation back-check candidate selection: `data/reports/backtests/20260628_013608_model_candidate_selection/`

結果:

- 2025-06 dataset rows: `28,889`
- label counts: short `14,763`, flat `953`, long `13,173`
- selected `short:session_regime=asia` block: adjusted pnl `-100.4662`, raw pnl `-74.9250`, 15 trades, profit factor `0.3444`, max DD `133.5832`
- no block: adjusted pnl `-109.9862`, 18 trades
- offset8 reference: adjusted pnl `-80.9672`, 11 trades
- selectedの short pnlは `-101.0232`
- worst direction/sessionは `short:london`, adjusted pnl `-101.2102`
- actual profit barrier miss rateは `0.4667`
- calibration overestimate maxは `0.4667`
- direction error rateは `0.6000`
- profit barrier missは 7 trades / adjusted pnl `-152.0642`

Post-hoc diagnostics:

- `short:london` block only: adjusted pnl `-36.2062`, 12 trades
- `short:asia,london` block: adjusted pnl `+0.7440`, 2 trades
- all short sessions blocked in this candidate: adjusted pnl `+0.5570`, 1 trade

Validation back-check:

- no block、`short:asia`、`short:london`、`short:asia,london` を4 validation monthsへ戻して確認した。
- どの条件もeligibleではなかった。
- `short:london` はvalidation base mean pnl `+3.9695` だが min pnl `-19.9560`、min trades `2` で採用根拠にならない。
- `short:asia,london` はvalidation mean pnl `-6.3636` で、London blockを事前選択する根拠はない。

判断:

- `short:session_regime=asia` は暫定採用候補から降格する。
- 2025-04 / 2025-05の改善は、asia shortの局所損失を避けた効果であって、方向予測そのものの改善ではなかった。
- 2025-06では同じshort過大評価が London shortへ移動した。
- session hard blockを増やすとNoTradeへ近づくだけなので、本流にはしない。
- 次は short exposure concentration、support-aware actual miss / calibration、exit timing targetを優先する。

### 2026-06-28 10:47 JST Short Exposure And Support-Aware Gates

作業:

- `model-policy` / `model-sweep` metricsへ side exposure concentration列を追加した。
- `long_trade_share`, `short_trade_share`, `max_side_trade_share` を保存する。
- profit barrier miss rateへ Laplace-smoothed rateを追加した。
- profit barrier calibrationへ smoothed actual hit rate / overestimateを追加した。
- `model-candidate-selection` に以下を追加した。
  - `--max-short-trade-share`
  - `--max-side-trade-share`
  - `--max-smoothed-actual-profit-barrier-miss-rate`
  - `--max-smoothed-profit-barrier-calibration-overestimate`
- report: `docs/reports/00027_2026-06-28_short_exposure_support_aware_gates.md`

Artifacts:

- no-cost selected: `data/reports/backtests/20260628_014713_model_sweep_2025-06_1/`
- no-cost no-short diagnostic: `data/reports/backtests/20260628_014713_model_sweep_2025-06/`
- cost selected: `data/reports/backtests/20260628_014713_model_sweep_2025-06_2/`
- cost no-short diagnostic: `data/reports/backtests/20260628_014713_model_sweep_2025-06_3/`
- candidate selection: `data/reports/backtests/20260628_014727_model_candidate_selection/`

結果:

- 2025-06 selected `short:session_regime=asia`:
  - no-cost adjusted pnl `-100.4662`
  - cost adjusted pnl `-103.7488`
  - trades `15`
  - `short_trade_share=0.933333`
  - `max_side_trade_share=0.933333`
  - `actual_profit_barrier_miss_rate_smoothed=0.470588`
  - `profit_barrier_calibration_overestimate_smoothed_max=0.470588`
  - `short_trade_share_ok=false`
  - `eligible=false`
- all short sessions blocked diagnostic:
  - no-cost adjusted pnl `0.5570`
  - cost adjusted pnl `0.3570`
  - trades `1`
  - `max_side_trade_share=1.000000`
  - smoothed actual miss / calibration `0.333333`
  - `eligible_base=false`, `eligible_cost=false`

検証:

- `python3 -m py_compile src/trade_data/backtest.py`: OK。
- `python3 -m unittest tests.test_backtest`: 33 tests OK。
- `model-candidate-selection --help`: OK。
- `git diff --check`: OK。

判断:

- `--max-short-trade-share` は 2025-06の失敗候補を直接落とせる。
- `--max-side-trade-share` は少数tradeのNoTrade類似候補も検出するが、主に診断として使う。
- smoothed actual miss / calibrationは raw 0/1の過反応を弱める。1 trade候補を raw 0.0 として楽観せず `0.333333` に補正できた。
- 次は validation 4fold以上で short share閾値と smoothed gateの台地を見る。

### 2026-06-28 10:52 JST Report Numbering Rule Clarification

作業:

- `docs/reports` の通し番号は、ファイルシステムの更新時刻や本文の `更新日時` ではなく、本文冒頭の `日時: YYYY-MM-DD HH:MM JST` だけを基準にする運用を再確認した。
- `GOAL.md`, `docs/README.md`, `docs/experiment_protocol.md`, `docs/status.md` に `更新日時` を採番基準にしないことを明記した。

判断:

- `更新日時` は追記・修正履歴の管理に使う。
- 通し番号の並び替えや新規番号判断には `日時` のみを使う。

### 2026-06-28 11:14 JST High Turnover Gate Validation

作業:

- validation 4foldで short share / smoothed miss / smoothed calibration gateを比較した。
- 前回候補周辺gridを追加列込みで再生成した。
- 月10trades条件を満たせなかったため、high-turnover gridを追加した。
- high-turnover gridでは `min_entry_rank=0/0.5`, `max_wait_regret=4/inf`, `profit_barrier_threshold=0.0/0.2` を含めた。
- 2025-06は既知の失敗月として、暫定候補A/Bの回帰チェックだけを実施した。
- report: `docs/reports/00028_2026-06-28_high_turnover_gate_validation.md`

Artifacts:

- fixed-neighborhood comparison: `data/reports/backtests/20260628_020416_model_sweep_candidate_gate_comparison.csv`
- high-turnover comparison: `data/reports/backtests/20260628_021001_high_turnover_candidate_gate_comparison.csv`
- forced/direction gate comparison: `data/reports/backtests/20260628_021102_high_turnover_forced_direction_gate_comparison.csv`
- selected validation comparison: `data/reports/backtests/20260628_021208_model_candidate_selection/`
- 2025-06 known-month regression: `data/reports/backtests/20260628_021217_known_2025_06_regression_candidates.csv`
- decision: `docs/decisions/0007_high_turnover_gate_selection.md`

結果:

- 前回候補周辺gridは `min-trades-per-fold=10` を満たせず、最大でも `trade_count_min_base=5`。
- high-turnover gridでは、PnL条件を緩めると48候補が残った。
- `max-forced-exit-rate=0` では全滅。`0.05` なら候補が残る。
- `max-direction-session-loss-per-fold=45` では全滅。`60` なら5候補が残る。
- `max-short-trade-share=0.65` でも上位候補は残る。
- smoothed actual missは `0.55` なら5候補、`0.50` なら1候補。
- smoothed calibrationを `0.60` まで締めると、asia block候補だけが残る。

2025-06既知月回帰:

- A no block candidate: cost adjusted pnl `+37.0572`, 52 trades, short pnl `-14.2222`, max drawdown `77.7572`。
- B asia block calibration candidate: cost adjusted pnl `-29.4530`, 50 trades, short pnl `-84.9312`, max drawdown `123.6128`。

判断:

- 暫定hard gateは `max-short-trade-share=0.65` と `max-smoothed-actual-profit-barrier-miss-rate=0.55`。
- smoothed calibrationはhard gateにしない。診断またはtie-breakに留める。
- 暫定候補Aを、次の未見月 2025-07 で見る前に `docs/decisions/` へ固定する。
- 固定記録は `docs/decisions/0007_high_turnover_gate_selection.md` に作成済み。

### 2026-06-28 12:27 JST Blind 2025-07 Candidate A Evaluation

作業:

- 2025-07の1.0/1.20 datasetを追加生成した。
- 2025-07をtest monthにしたblind modelを、候補A固定時と同じtrain/validation設定で学習した。
- `docs/decisions/0007_high_turnover_gate_selection.md` で固定した候補Aを、no-costとstandard cost-aware caseで評価した。
- `analyze-trades` と `model-cost-sensitivity` で失敗要因を分解した。
- report: `docs/reports/00029_2026-06-28_blind_2025_07_candidate_a.md`

Artifacts:

- dataset summary: `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-07_h24_edge15.summary.json`
- model: `experiments/20260628_032236_full_fixed_horizon_blind_2025_07_barrier_prob_p1_l1p2/`
- comparison: `data/reports/backtests/20260628_032236_candidate_a_2025_07_blind_comparison.csv`
- no-cost backtest: `data/reports/backtests/20260628_032312_model_fixed_horizon_ev_2025-07/`
- cost-aware backtest: `data/reports/backtests/20260628_032314_model_fixed_horizon_ev_2025-07/`
- cost analysis: `data/reports/backtests/20260628_032410_candidate_a_2025_07_cost_analysis/`
- cost sensitivity: `data/reports/backtests/20260628_032641_model_cost_sensitivity_2025-07/`

結果:

- no-cost adjusted pnl `+1.5838`, raw pnl `+22.8040`, 66 trades, profit factor `1.0124`。
- standard cost-aware adjusted pnl `-12.7764`, raw pnl `+9.6040`, 66 trades, profit factor `0.9049`。
- short trade shareは `0.0758` で、short concentrationは回避した。
- cost-awareの損失中心は long `-11.7354`, `ny_overlap` `-20.0054`, `low_vol` `-30.8756`, `down_low_vol` `-27.1054`。
- direction error rate `0.5303`、actual profit barrier miss rate `0.6515`、EV overestimate vs realized mean `15.6821`。
- spread/slippage感度では、no-cost `+1.5838` から slippage `0.05` だけで `-5.5862`、slippage `0.10` で `-12.7764`。

判断:

- 候補Aは2025-07 blindで失敗。採用候補から外す。
- 2025-06のshort集中崩れは回避できたが、edgeがlong/low-vol側で消えた。
- 次はcost-aware評価を主目的へ寄せ、profit barrier classifierとexit timing targetを作り直す。
- `ny_overlap` や `low_vol` のpost-hoc blockは直接採用しない。validation foldで支持されるかを確認する。
- レポート通し番号は、今後もファイル更新時刻や `更新日時` ではなく、本文冒頭の `日時` を基準にする。

### 2026-06-28 12:37 JST Trade Analysis Diagnostic Gates

作業:

- `model-sweep` metricsへ trade-analysis diagnostic列を追加した。
- 追加列は `direction_error_rate`, `no_edge_rate`, `predicted_side_error_rate`, `exit_regret_mean`, `ev_overestimate_vs_realized_mean` など。
- `model-candidate-selection` に以下のgateを追加した。
  - `--max-direction-error-rate`
  - `--max-predicted-side-error-rate`
  - `--max-no-edge-rate`
  - `--max-exit-regret-mean`
  - `--max-ev-overestimate-vs-realized-mean`
- report: `docs/reports/00030_2026-06-28_trade_analysis_diagnostic_gates.md`

Artifacts:

- no-cost one-point sweep: `data/reports/backtests/20260628_033639_model_sweep_2025-07/`
- cost-aware one-point sweep: `data/reports/backtests/20260628_033650_model_sweep_2025-07/`
- candidate-selection smoke: `data/reports/backtests/20260628_033702_model_candidate_selection/`

結果:

- 2025-07候補Aのpost-hoc smokeで、新diagnosticが `analyze-trades` と一致することを確認した。
- no-cost: direction error rate `0.5303`, exit regret mean `17.2330`, EV overestimate vs realized mean `15.4645`。
- cost-aware: direction error rate `0.5303`, exit regret mean `17.4505`, EV overestimate vs realized mean `15.6821`。
- `max-direction-error-rate=0.5`, `max-exit-regret-mean=15`, `max-ev-overestimate-vs-realized-mean=10` で候補Aは `eligible=false`。

検証:

- `python3 -m unittest tests.test_backtest`: 34 tests OK。
- `python3 -m unittest discover tests`: 70 tests OK。
- `python3 -m trade_data.backtest model-candidate-selection --help`: OK。
- `git diff --check`: OK。

判断:

- 2025-07の失敗要因を、post-hoc分析だけでなくvalidation候補選定へ戻せるようになった。
- ただし、この閾値は2025-07を見た後のsmoke値なので採用基準ではない。次はvalidation 4foldで閾値台地を確認する。
- `ny_overlap` / `low_vol` の直接blockではなく、direction error、exit regret、EV overestimateのような構造的な失敗指標を使う。

### 2026-06-28 12:48 JST Diagnostic Gate Validation

validation 4foldのhigh-turnover gridを、新しいtrade-analysis diagnostic列入りで再生成した。

確認したdiagnostic gate:

- direction error rate
- predicted side error rate
- no-edge rate
- exit regret mean
- EV overestimate vs realized mean

結果:

- no diagnostic / lenient / balanced gate: eligible `5`
- focused gate: eligible `2`
- strict gate: eligible `1`
- 2025-07 smoke-like gate (`exit_regret_mean<=15`, `EV overestimate<=10`): eligible `0`

判断:

- 2025-07の失敗をpost-hocで落とせた厳しいgateは、validationでは候補を全滅させるため採用しない。
- 現時点ではdiagnosticを主hard gateにせず、tie-breakと失敗分析に使う。
- 既存 `docs/reports/*.md` 30本について、ファイル更新時刻ではなく本文内 `日時` 順で採番が一致することを確認した。

成果物:

- `docs/reports/00031_2026-06-28_diagnostic_gate_validation.md`
- `docs/decisions/0008_trade_analysis_diagnostic_gate_policy.md`
- `data/reports/backtests/20260628_034513_model_candidate_selection/`
- `data/reports/backtests/20260628_124813_diagnostic_gate_threshold_comparison.csv`

次は exit timing target、risk target、expected pnl calibration を改善する。

### 2026-06-28 12:58 JST Time-Limited Profit Barrier Targets

作業:

- `long_profit_barrier_hit_60m/240m/720m` と `short_profit_barrier_hit_60m/240m/720m` をdataset targetに追加した。
- `target-set policy` / `full` のclassification targetへ追加した。
- 既存の `--long-profit-barrier-column` / `--short-profit-barrier-column` に `pred_long_profit_barrier_hit_240m_prob` のような列を差し替えられるようにした。
- report: `docs/reports/00032_2026-06-28_time_limited_profit_barrier_targets.md`

Smoke:

- `/tmp` に 2025-01 から 2025-03 のdatasetを生成。
- 2025-01では、60m targetはlong `0.0023` / short `0.0063` と希少。
- 240m targetはlong `0.0665` / short `0.0420`、720m targetはlong `0.3255` / short `0.1196`。
- 軽量HGB smoke `experiments/20260628_035801_exit_target_smoke/` で新targetの学習と確率列保存を確認。

判断:

- 60m targetはhard gateには早い。class weightingやpositive supportを検討するまでは診断扱い。
- 240m/720m targetは、24h targetより短いexit依存を落とすfilterとしてvalidationで比較する価値がある。
- 主datasetはまだ再生成していない。次は本番dataset再生成、policy再学習、cost-aware validation sweep。

検証:

- `python3 -m unittest tests.test_dataset tests.test_modeling`: 25 tests OK。
- `python3 -m unittest discover tests`: 71 tests OK。
- `git diff --check`: OK。

### 2026-06-28 13:53 JST Timebarrier Validation Sweep

作業:

- 主dataset `data/processed/datasets/xauusd_m1_p1_l1p2/` を、時間別profit barrier target込みで 2023-01 から 2025-07 まで再生成した。
- `target-set policy` に固定horizon回帰targetが不足していたため、`EXIT_FIXED_HORIZON_TARGETS` を追加した。
- policy HGBを再学習し、`fixed_horizon_ev` と 24h/240m/720m profit barrier probabilityを同時に使える prediction frameを作成した。
- 24h, 240m, 720m probabilityのvalidation 4fold sweepを比較した。
- 240m / 720m はfine thresholdも追加で検証した。
- report: `docs/reports/00033_2026-06-28_timebarrier_validation_sweep.md`

Artifacts:

- model: `experiments/20260628_040828_policy_timebarrier_p1_l1p2/`
- broad summary: `data/reports/backtests/20260628_timebarrier_candidate_selection_summary.csv`
- fine summary: `data/reports/backtests/20260628_timebarrier_fine_candidate_selection_summary.csv`
- 240m fine candidate selection: `data/reports/backtests/20260628_045220_barrier240_fine_candidate_selection/`
- 720m fine candidate selection: `data/reports/backtests/20260628_045221_barrier720_fine_candidate_selection/`

結果:

| variant | eligible | top threshold | cost min pnl | min trades | forced exit max | worst dir/session | smoothed miss max |
|---|---:|---:|---:|---:|---:|---:|---:|
| 24h broad | 12 | `0.2` | `27.2158` | 47 | `0.0000` | `-39.1342` | `0.454545` |
| 240m broad | 5 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` |
| 720m broad | 5 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` |
| 240m fine | 8 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` |
| 720m fine | 8 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` |

classifier診断:

- time-limited barrier classifierのvalidation balanced accuracyはほぼ `0.5`。
- 60m targetは希少で、現HGBではhard gateに向かない。
- 240m / 720m probabilityは候補を絞れるが、現在のtop候補ではthreshold `0.0` が勝っており、filterとして強く機能していない。

判断:

- 240m / 720m probabilityはhard gateへ昇格しない。
- 24h profit barrier probability threshold `0.2` は、現validation上ではまだ上位候補。
- 次はtime-limited binary probabilityよりも、exit regret / EV overestimateを直接下げるtarget、またはhazard / survival形式のexit timing targetを優先する。
- レポート採番は、引き続きファイル更新時刻や `更新日時` ではなく、ファイル本文の `日時` を基準にする。

### 2026-06-28 14:10 JST Fixed Horizon Score Mode Validation

作業:

- `fixed_horizon_ev` に `fixed_horizon_score_mode` を追加した。
- `model-policy --fixed-horizon-score-mode` と `model-sweep --fixed-horizon-score-modes` を追加した。
- modeは `max`, `mean`, `median`, `min`。
- `SWEEP_KEY_COLUMNS` に `fixed_horizon_score_mode` を追加し、古いsweep metricsには `max` を補完する。
- validation 4foldで `max/mean/median/min` を比較した。
- report: `docs/reports/00034_2026-06-28_fixed_horizon_score_mode_validation.md`

Artifacts:

- base sweeps: `data/reports/backtests/20260628_050708_model_sweep_2024-07/`, `20260628_050721_model_sweep_2024-09/`, `20260628_050733_model_sweep_2024-11/`, `20260628_050745_model_sweep_2025-01/`
- cost sweeps: `data/reports/backtests/20260628_050757_model_sweep_2024-07/`, `20260628_050809_model_sweep_2024-09/`, `20260628_050822_model_sweep_2024-11/`, `20260628_050834_model_sweep_2025-01/`
- candidate selection: `data/reports/backtests/20260628_050919_horizon_score_mode_candidate_selection/`
- summary: `data/reports/backtests/20260628_horizon_score_mode_candidate_selection_summary.csv`

結果:

| mode | eligible | top cost min pnl | top cost min trades | short share max | EV overestimate max | exit regret max |
|---|---:|---:|---:|---:|---:|---:|
| `max` | 7 | `27.2158` | 47 | `0.170213` | `15.692745` | `25.465302` |
| `mean` | 0 | `-57.7550` | 92 | `0.065217` | `16.620512` | `22.515032` |
| `median` | 0 | `-53.7286` | 77 | `0.064935` | `16.457595` | `22.309429` |
| `min` | 0 | `-46.6480` | 57 | `0.000000` | `16.510913` | `21.548846` |

判断:

- 単純な保守的horizon集約は採用しない。
- `mean/median/min` はshort exposureを強く落とすが、EV overestimateは大きく改善せず、long-only寄りでfold最低PnLを壊す。
- `fixed_horizon_score_mode=max` を維持する。
- EV過大評価対策は、horizon集約ではなくOOFで実現PnLに対するcalibration/penaltyを学習する方向へ進める。

### 2026-06-28 14:26 JST Fixed Horizon OOF Calibration

作業:

- fixed horizon EV target用の汎用group calibrationを追加した。
- `oof-fixed-horizon-calibration` CLIを追加し、validation月をleave-one-month-outで校正できるようにした。
- `docs/reports` の採番が本文 `日時` の昇順であることを確認する `tests/test_docs_reports.py` を追加した。
- regime calibration (`volatility_regime,session_regime`, shrink `0.65`) と global bias calibration (groupなし, shrink `1.0`) を比較した。
- report: `docs/reports/00035_2026-06-28_fixed_horizon_oof_calibration.md`

Artifacts:

- regime calibration: `experiments/20260628_052021_fixed_horizon_oof_group_calib_p1_l1p2/`
- regime candidate selection: `data/reports/backtests/20260628_052218_model_candidate_selection/`
- global bias calibration: `experiments/20260628_052305_fixed_horizon_oof_global_bias_p1_l1p2/`
- global strict selection: `data/reports/backtests/20260628_052436_model_candidate_selection/`
- global relaxed diagnostic selection: `data/reports/backtests/20260628_052503_model_candidate_selection/`

結果:

| variant | strict eligible | top cost min pnl | min trades | forced exit max | smoothed miss max | EV overestimate max |
|---|---:|---:|---:|---:|---:|---:|
| raw fixed horizon | 7 | `27.2158` | 47 | `0.000000` | `0.454545` | `15.692745` |
| regime calibration | 0 | `9.3470` | 3 | `0.000000` | `0.666667` | `20.238968` |
| global bias calibration | 0 | `38.0184` | 76 | `0.057471` | `0.617978` | `15.713636` |

判断:

- regime別fixed horizon calibrationは採用しない。
- global bias calibrationはtarget biasを下げるが、trade selection後のEV overestimateを下げないため採用保留。
- strict gateを緩めるとglobal bias候補は3件残るが、profit-barrier missとforced exitを悪化させているため、採用ではなく診断扱い。
- 次はtrade selection後の実現PnL penalty、profit-barrier missを直接下げるexit target、hazard/survival型exit timing targetへ進む。

### 2026-06-28 14:39 JST Profit Barrier Miss Penalty Sweep

作業:

- `fixed_horizon_ev` のentry scoreに `profit_barrier_miss_penalty * (1 - side_profit_barrier_hit_probability)` を引くsoft penaltyを追加した。
- `model-policy --profit-barrier-miss-penalty` と `model-sweep --profit-barrier-miss-penalties` を追加した。
- 古いsweep metricsには `profit_barrier_miss_penalty=0.0` を補完する。
- report: `docs/reports/00036_2026-06-28_profit_barrier_miss_penalty_sweep.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_053518_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost delay0 sweeps: `data/reports/backtests/20260628_053731_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection delay0: `data/reports/backtests/20260628_053757_model_candidate_selection/`
- cost delay1 sweeps: `data/reports/backtests/20260628_053602_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection delay1: `data/reports/backtests/20260628_053630_model_candidate_selection/`

結果:

| cost case | eligible penalty | best cost min pnl | min trades | smoothed miss max | EV overestimate max |
|---|---:|---:|---:|---:|---:|
| delay0 | `0.0` | `27.2158` | 47 | `0.454545` | `15.692745` |
| delay1 | `0.0` | `23.4720` | 48 | `0.492308` | `14.766051` |

判断:

- penalty `2/4/6/8` は、delay0 / delay1 のどちらでもstrict candidate selectionに残らなかった。
- 線形miss penaltyはtrade集合の実現品質を改善せず、smoothed missやEV overestimateを悪化させた。
- 実装は探索軸として残すが、標準設定は `profit_barrier_miss_penalty=0.0` を維持する。
- 次はselected tradesの実現PnL、actual barrier miss、exit regretを直接targetにする二段階モデル、またはhazard/survival型exit timing targetへ進む。

### 2026-06-28 15:00 JST Selected Trade Quality Calibration

作業:

- policyが実際に選んだtradeだけを使う `TradeQualityCalibrator` を追加した。
- `trade_data.meta_model oof-trade-quality-calibration` を追加し、validation月leave-one-month-outで `pred_trade_quality_long/short_adjusted_pnl` を生成できるようにした。
- `model-policy --min-trade-quality` と `model-sweep --min-trade-qualities` を追加した。
- 現行基準候補のcost-aware trades 4ヶ月分を生成し、OOF quality列を作った。
- report: `docs/reports/00037_2026-06-28_selected_trade_quality_calibration.md`

Artifacts:

- selected-trade fit trades: `data/reports/backtests/20260628_055630_model_fixed_horizon_ev_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- OOF quality predictions: `experiments/20260628_055648_trade_quality_oof_fixed_horizon/`
- no-cost quality sweeps: `data/reports/backtests/20260628_055803_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost quality sweeps: `data/reports/backtests/20260628_055853_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection: `data/reports/backtests/20260628_055927_model_candidate_selection/`

結果:

| min trade quality | eligible | best cost min pnl | best base min pnl | min trades | best smoothed miss | best EV overestimate |
|---:|---:|---:|---:|---:|---:|---:|
| `-inf` | 7 | `27.2158` | `39.7538` | 47 | `0.454545` | `14.377795` |
| `-1.0` | 6 | `22.7466` | `34.8046` | 47 | `0.454545` | `14.377795` |
| `0.0` | 3 | `9.2116` | `20.8296` | 47 | `0.464286` | `14.549737` |
| `0.5` | 3 | `4.7194` | `15.3554` | 27 | `0.488889` | `14.763182` |
| `1.0` | 0 | `-9.1060` | `-4.2660` | 17 | `0.625000` | `16.130152` |

判断:

- OOF selected-trade calibrationはraw biasを `0.628560` から `-0.078209` へ下げたが、R2は `-0.017978` で個別trade識別力は弱い。
- `min_trade_quality` gateはtop候補を改善しない。`0` 以上ではcost min pnlが大きく悪化する。
- 実装は残すが、標準候補には採用しない。標準は `min_trade_quality=-inf`。
- 次はgroup平均ではなく小型モデルでselected-trade targetを学習するか、hazard/survival型exit timing targetへ進む。

### 2026-06-28 15:11 JST Selected Trade Quality Model

作業:

- selected tradesの実現PnLを小型HGBで学習する `TradeQualityModelConfig` / `TradeQualityModelBundle` を追加した。
- `trade_data.meta_model oof-trade-quality-model` を追加し、validation月leave-one-month-outでHGB版 `pred_trade_quality_long/short_adjusted_pnl` を生成できるようにした。
- report: `docs/reports/00038_2026-06-28_selected_trade_quality_model.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- HGB OOF quality predictions: `experiments/20260628_060718_trade_quality_model_oof_fixed_horizon/`
- no-cost quality sweeps: `data/reports/backtests/20260628_060955_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost quality sweeps: `data/reports/backtests/20260628_061047_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection: `data/reports/backtests/20260628_061118_model_candidate_selection/`

結果:

| min trade quality | eligible | best cost min pnl | best base min pnl | min trades | best smoothed miss | best EV overestimate |
|---:|---:|---:|---:|---:|---:|---:|
| `-inf` | 7 | `27.2158` | `39.7538` | 47 | `0.454545` | `14.377795` |
| `-1.0` | 7 | `27.2158` | `39.7538` | 47 | `0.454545` | `14.377795` |
| `0.0` | 7 | `27.2158` | `39.7538` | 47 | `0.459016` | `14.411078` |
| `0.5` | 0 | `-15.5310` | `-10.3410` | 23 | `0.450000` | `17.109478` |
| `1.0` | 4 | `1.7620` | `4.1220` | 10 | `0.477612` | `18.353985` |

判断:

- HGB版selected-trade qualityはgroup補正よりMAEを少し下げたが、bias/R2は悪く、安定した個別trade識別器にはなっていない。
- `min_trade_quality=0.0` はtop候補を壊さないが、改善もしない。
- `1.0` 以上はtrade数とfold最低PnLを大きく削る。
- selected-trade quality modelは診断・探索基盤として残すが、標準候補には採用しない。標準は引き続き `min_trade_quality=-inf`。
- 次はtrade後品質の単発gateより、exit timing targetを直接増やす。特に利確/損切り/時間切れの時刻をhazard/survival型またはtime-bucket classificationで扱う。

### 2026-06-28 15:21 JST Exit Event Timing Targets

作業:

- side別に `time_exit/profit_first/loss_first` を表す `long_exit_event` / `short_exit_event` をdatasetに追加した。
- side別に最初のexit eventまでの `long_exit_event_minutes` / `short_exit_event_minutes` を追加した。
- `long_exit_event_time_bin` / `short_exit_event_time_bin` を追加した。
- `trade_data.modeling` の `policy` / `full` target setへexit event targetを追加した。
- report: `docs/reports/00039_2026-06-28_exit_event_timing_targets.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- smoke datasets: `data/processed/datasets/xauusd_m1_exit_event_smoke/`
- smoke model: `experiments/20260628_062101_exit_event_target_smoke/`
- smoke backtest: `data/reports/backtests/20260628_062138_model_timed_ev_2024-09/`

結果:

| split | target | MAE | RMSE | R2 |
|---|---|---:|---:|---:|
| valid | `long_exit_event_minutes` | `537.5728` | `676.4928` | `0.1628` |
| valid | `short_exit_event_minutes` | `524.9559` | `656.6593` | `0.1565` |
| test | `long_exit_event_minutes` | `600.3732` | `854.8331` | `0.1306` |
| test | `short_exit_event_minutes` | `611.3872` | `876.4042` | `0.1450` |

接続確認:

- `pred_long_exit_event_minutes` / `pred_short_exit_event_minutes` は保存された。
- 既存 `timed_ev` policyの `--long-holding-column` / `--short-holding-column` に渡してbacktestが実行できた。
- smoke backtestは `2024-09` で adjusted pnl `-118.8852`, 47 trades。これは軽量1ヶ月trainの接続確認であり、採用判断には使わない。

判断:

- exit event timing targetは本流の次実験軸へ昇格する。
- 次はvalidation 4fold用に新target入りdatasetを再生成し、従来 `pred_*_best_holding_minutes` と `pred_*_exit_event_minutes` をholding columnとして比較する。
- 多クラス `exit_event` のprobability出力を追加し、profit/loss/time確率をgateやpenaltyに使えるようにする。

### 2026-06-28 15:50 JST Exit Event Holding Validation

作業:

- 新target入りdataset `data/processed/datasets/xauusd_m1_p1_l1p2_exit_event/` を 2023-01 から 2025-01 まで生成した。
- `policy` target setでHGB 80iterを再学習し、validation 4foldで従来holding columnとexit-event holding columnを比較した。
- 多クラスclassifierについて `pred_<target>_prob_<class>` を出力するようにし、`pred_long_exit_event_prob_1` / `pred_short_exit_event_prob_1` をprofit-first gateとして使えるようにした。
- `short_entry_threshold_offset=8,12,16,20` の拡張gridも試した。
- report: `docs/reports/00040_2026-06-28_exit_event_holding_validation.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- model with exit-event class probabilities: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/`
- best-holding comparison: `data/reports/backtests/20260628_063841_model_candidate_selection/`
- exit-event holding comparison: `data/reports/backtests/20260628_063856_model_candidate_selection/`
- exit-event profit probability gate: `data/reports/backtests/20260628_064600_model_candidate_selection/`
- short offset expansion strict: `data/reports/backtests/20260628_064844_model_candidate_selection/`
- short offset expansion forced-exit 10% diagnostic: `data/reports/backtests/20260628_065005_model_candidate_selection/`

結果:

| variant | strict eligible | best cost min pnl | main failure |
|---|---:|---:|---|
| best holding + old barrier prob | 0 | `30.2476` | smoothed barrier miss `0.551020` |
| exit-event holding + old barrier prob | 0 | `59.5464` | forced exit `0.097561` |
| exit-event holding + exit-event profit prob | 0 | `75.8344` | forced exit `0.125000` |
| exit-event holding + profit prob + short offset expansion | 0 | `75.8344` | forced exit `0.125000` |

10% forced-exit diagnostic:

| entry | short offset | min entry rank | profit-first threshold | cost min pnl | min trades | forced exit max | short share max | smoothed miss max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `5` | `12` | `0.5` | `0.4` | `56.6182` | `29` | `0.081081` | `0.540541` | `0.538462` |
| `0` | `16` | `0.5` | `0.4` | `53.2866` | `32` | `0.055556` | `0.550000` | `0.534884` |

判断:

- exit-event minutesはbest holding minutesより学習しやすく、validation PnL台地も押し上げる。
- ただし、strict `max_forced_exit_rate=0.05` では採用不可。5% gateを緩めて採用するのは、まだtime-expiry riskの取り扱いが粗い。
- `pred_*_exit_event_prob_1` はbarrier missを抑える方向に効いたため、研究信号として残す。
- 次はholding minuteをそのまま使うのではなく、time-exit probability penalty、holding cap、hazard/survival型exit policyで強制決済率を直接下げる。

### 2026-06-28 16:05 JST Holding Cap Sweep

作業:

- `model-sweep` の `--min-predicted-hold-minutes` / `--max-predicted-hold-minutes` をCSV grid対応にした。
- `min_predicted_hold_minutes` / `max_predicted_hold_minutes` をcandidate keyへ追加し、cap違いの候補がfold集計で混ざらないようにした。
- exit-event holding + profit-first probability gateのvalidation 4foldで、`max_predicted_hold_minutes=240,480,720,960,1200,1440` を比較した。
- report: `docs/reports/00041_2026-06-28_holding_cap_sweep.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_065828_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware sweeps: `data/reports/backtests/20260628_065950_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- strict candidate selection: `data/reports/backtests/20260628_070227_model_candidate_selection/`
- 10% forced-exit diagnostic: `data/reports/backtests/20260628_070240_model_candidate_selection/`
- delay `1` fixed top diagnostic: `data/reports/backtests/20260628_070518_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`

結果:

| forced-exit gate | eligible | best cost min pnl | best base min pnl | min trades | forced exit max | best cap |
|---:|---:|---:|---:|---:|---:|---:|
| `0.05` | `20` | `84.7072` | `92.2774` | `32` | `0.028571` | `720` |
| `0.10` | `29` | `84.7072` | `92.2774` | `32` | `0.028571` | `720` |

Best strict candidate:

- `policy=timed_ev`
- `entry_threshold=10`
- `short_entry_threshold_offset=8`
- `profit_barrier_threshold=0.4`
- `max_predicted_hold_minutes=720`
- cost-aware fold pnl: `151.2868`, `98.1128`, `87.6574`, `84.7072`
- cost-aware min trades `32`, max drawdown `80.4432`, max forced exit rate `0.028571`

判断:

- holding capはforced-exit問題に直接効き、strict gateを緩めずに候補を復活させた。
- cap `720` は `480` よりPnLが高く、`960` 以上よりforced exitが少ないため、現時点の中心候補。
- delay `1` 固定診断では4fold全てプラスだが、smoothed miss max `0.552632` が現行gate `0.55` を少し超えた。delay `1` はfull-grid選定前に標準採用しない。
- 次は閾値を固定して未使用blind月へ適用する。test結果を見てcapやthresholdを再選択しない。

### 2026-06-28 16:31 JST Delay 1 Combined Regime Holdout

作業:

- `model-sweep` metricsへ `combined_regime` / `direction:combined_regime` の最悪損益診断を追加した。
- `model-candidate-selection` に `--max-combined-regime-loss-per-fold` と `--max-direction-combined-regime-loss-per-fold` を追加した。
- delay `1` のvalidation 4fold full-gridを、新しい診断列入りで再生成した。
- combined regime gateの閾値感度を確認し、`60/65` gateのtop候補を2024-12 holdoutへ固定適用した。
- report: `docs/reports/00042_2026-06-28_delay1_combined_regime_holdout.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_072504_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware sweeps: `data/reports/backtests/20260628_072645_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- baseline support-aware selection: `data/reports/backtests/20260628_072821_model_candidate_selection/`
- combined gate `60/60`: `data/reports/backtests/20260628_072839_model_candidate_selection/`
- combined gate `60/65`: `data/reports/backtests/20260628_073009_model_candidate_selection/`
- 2024-12 holdout: `data/reports/backtests/20260628_073040_model_timed_ev_2024-12/`
- 2024-12 analysis: `data/reports/backtests/20260628_073055_holdout_2024_12_combined_gate_top/`

結果:

| selection | eligible | pre-plateau | top | cost min pnl |
|---|---:|---:|---|---:|
| baseline support-aware | `13` | `21` | `entry=5, short offset=12, cap=720` | `58.2310` |
| combined `60/60` | `0` | `13` | n/a | n/a |
| combined `60/65` | `3` | `16` | `entry=5, short offset=20, cap=480` | `45.4484` |

2024-12 holdout:

- adjusted pnl `-149.7354`
- raw pnl `-109.3520`
- trades `33`
- win rate `0.4545`
- profit factor `0.3820`
- max drawdown `176.6504`
- forced exits `2`

失敗診断:

- long adjusted pnl `-116.2186`
- short adjusted pnl `-33.5168`
- direction error rate `0.575758`
- exit regret mean `16.019952`
- EV overestimate vs realized mean `21.857830`
- profit barrier miss trades `25`, adjusted pnl `-184.2444`

判断:

- combined regime gateはvalidation候補を絞るが、hard gateとして採用候補を改善しなかった。
- 2024-12の主因はforced exitではなく、direction error、profit barrier miss、EV過大評価。
- combined regimeはcandidate tie-break / failure analysisには使うが、標準hard gateにはしない。
- 次はside/entry calibrationを直接扱う。特に `actual_best_side`, profit barrier miss, EV overestimateを教師信号またはcalibration targetにする。

### 2026-06-28 16:48 JST Best Side Confidence Smoke

作業:

- `label` とは別に、long/shortの相対的に良い方向を保持する `best_side` targetを追加した。
- `target-set policy` / `full` で `best_side` をclassification targetに含め、`pred_best_side_prob_1` / `pred_best_side_prob_-1` を保存するようにした。
- `model-policy` / `model-sweep` に `--side-confidence-penalty` と `--min-side-confidence` を追加した。
- 2024-09..2024-12のsmoke datasetとHGB modelを作成し、2024-12 testでside-confidence sweepを行った。
- report: `docs/reports/00043_2026-06-28_best_side_confidence_smoke.md`
- 採番はファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- dataset: `data/processed/datasets/xauusd_m1_best_side_smoke/`
- model: `experiments/20260628_074412_best_side_confidence_smoke/`
- sweep: `data/reports/backtests/20260628_074450_model_sweep_2024-12/`

結果:

| split | best_side balanced accuracy | macro f1 |
|---|---:|---:|
| train | `0.6710` | `0.6624` |
| validation | `0.5464` | `0.5393` |
| test | `0.4797` | `0.4766` |

2024-12 executable smoke:

| side penalty | min side confidence | adjusted pnl | trades | profit factor | max drawdown |
|---:|---:|---:|---:|---:|---:|
| `10` | `0.55` | `-109.8978` | `331` | `0.7276` | `119.9102` |
| `0` | `0.00` | `-220.5348` | `506` | `0.6484` | `241.2352` |

判断:

- side-confidence gateは損失と取引数を減らすが、NoTradeには負けるため採用しない。
- `best_side` は方向選択の診断 target としては有用。ただし2024-12ではbelow-randomなので、hard gateにするにはwalk-forward OOFの確認が必須。
- 次は広い期間のdatasetに反映し、side confidenceをcalibration/diagnosticとして使う。

### 2026-06-28 16:55 JST Side Confidence Calibration Report

作業:

- `trade_data.modeling side-confidence-report` を追加した。
- 予測済みparquetから `best_side` 確率のaccuracy、balanced accuracy、confidence、overconfidence、predicted/actual long shareを集計する。
- `prediction_split`, `dataset_month`, `session_regime`, `volatility_regime`, `trend_regime`, `combined_regime` 別とconfidence bucket別の診断CSVを出す。
- 直近の `best_side` smoke valid/testに適用した。
- report: `docs/reports/00044_2026-06-28_side_confidence_calibration_report.md`
- 採番はファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- diagnostic: `data/reports/modeling/20260628_075447_side_confidence_smoke/`
- inputs:
  - `experiments/20260628_074412_best_side_confidence_smoke/predictions_valid.parquet`
  - `experiments/20260628_074412_best_side_confidence_smoke/predictions_test.parquet`

結果:

| scope | rows | accuracy | confidence mean | overconfidence |
|---|---:|---:|---:|---:|
| valid+test | `54725` | `0.5089` | `0.5861` | `0.0772` |
| valid | `25962` | `0.5443` | `0.5880` | `0.0437` |
| test | `28763` | `0.4770` | `0.5844` | `0.1074` |

worst groups:

| group | rows | accuracy | confidence | overconfidence |
|---|---:|---:|---:|---:|
| test `range_normal_vol` | `2075` | `0.3817` | `0.5771` | `0.1954` |
| test `london` | `7559` | `0.4046` | `0.5806` | `0.1760` |
| valid `down_low_vol` | `3204` | `0.4498` | `0.6192` | `0.1694` |

判断:

- `best_side` probabilityはglobal thresholdで使うには危険。2024-12 testでは高confidence bucketほど悪くなる箇所がある。
- side confidenceは、hard gateではなくOOF regime-aware calibrationの対象にする。
- 次は広い期間のdataset/predictionsへこの診断を適用し、過大確信が月固有か構造的かを確認する。

### 2026-06-28 17:12 JST Side Confidence Representative OOF

作業:

- `best_side` 対応datasetを `2024-07..2025-01` で生成した。
- `side_confidence` target setを追加した。targetは `long_best_adjusted_pnl`, `short_best_adjusted_pnl`, `best_side` のみ。
- full 7ヶ月 `policy` OOFと7ヶ月 `side_confidence` OOFは診断用途には重すぎたため中断した。
- 代表4ヶ月 `2024-07,2024-09,2024-11,2025-01` で、`sample_frac=0.25`, `max_iter=20` のblocked OOFを完走した。
- `side-confidence-report` をOOF予測へ適用した。
- report: `docs/reports/00045_2026-06-28_side_confidence_oof_representative.md`
- 採番はファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- dataset: `data/processed/datasets/xauusd_m1_best_side_oof_smoke/`
- OOF model: `experiments/20260628_081124_best_side_oof_representative_smoke/`
- diagnostic: `data/reports/modeling/20260628_081219_side_confidence_oof_representative_smoke/`

結果:

| metric | value |
|---|---:|
| rows | `119241` |
| best_side accuracy | `0.5666` |
| best_side balanced accuracy | `0.5519` |
| confidence mean | `0.5685` |
| overconfidence | `0.0020` |

worst groups:

| group | rows | accuracy | confidence | overconfidence |
|---|---:|---:|---:|---:|
| `high_vol` | `503` | `0.4553` | `0.5949` | `0.1396` |
| `down_normal_vol` | `7830` | `0.4764` | `0.5865` | `0.1101` |
| `up_normal_vol` | `7210` | `0.4656` | `0.5485` | `0.0829` |
| `2024-09` | `28885` | `0.5071` | `0.5810` | `0.0739` |

判断:

- global calibrationはかなり改善し、全体ではconfidenceとaccuracyがほぼ一致した。
- ただし高confidence bucket `0.70-0.80` はaccuracy `0.3309` で強く壊れている。
- side confidenceは採用gateではなく、regime-aware calibration/penaltyの材料として扱う。
- 次はこの結果をexecutable backtestに接続する前に、より広いOOFまたは別holdoutで再現性を確認する。

### 2026-06-28 17:20 JST Regime Side Confidence Penalty Smoke

作業:

- `--side-confidence-penalty-rules` を追加した。
- `--side-confidence-overfit-penalty-rules` を追加した。
- 2024-12 smokeで、前回worstだった `combined_regime=range_normal_vol` と `session_regime=london` にpenaltyをかけた。
- report: `docs/reports/00046_2026-06-28_regime_side_confidence_penalty_smoke.md`
- 採番はファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- low-confidence rule: `data/reports/backtests/20260628_081824_model_sweep_2024-12/`
- high-confidence overfit rule: `data/reports/backtests/20260628_081949_model_sweep_2024-12/`

結果:

| variant | adjusted pnl | trades | profit factor | max drawdown | worst direction/session |
|---|---:|---:|---:|---:|---|
| prior best global confidence gate | `-109.8978` | `331` | `0.7276` | `119.9102` | `long:london` |
| regime low-confidence penalty | `-222.3816` | `473` | `0.6309` | `233.7378` | `long:london` |
| regime high-confidence overfit penalty | `-249.2666` | `503` | `0.6269` | `263.4316` | `long:london` |

判断:

- regime-aware penaltyは探索軸として実装したが、このsmokeでは採用しない。
- 悪化の中心は引き続き `long:london` で、confidence penaltyだけではentry集合の質を改善できなかった。
- side confidenceは、NoTradeに大きく負ける候補を救う道具ではなく、既にviableな候補のtie-break/penaltyとして検証すべき。

### 2026-06-28 17:24 JST Report Time Reference Clarification

作業:

- レポートの通し番号、再採番、直近レポート参照では、ファイルシステムの更新時刻ではなく、各ファイル本文冒頭の `日時` を参照する運用を再確認した。
- `docs/README.md` と `docs/experiment_protocol.md` の「最新レポート」参照を、本文 `日時` と通し番号基準だと明記した。
- `docs/status.md` のレポート運用記述も同じ表現へ更新した。

判断:

- `更新日時` は追記・修正履歴を見るための補助情報であり、採番・直近判定・再採番の基準には使わない。
- `tests/test_docs_reports.py` は本文 `日時` を抽出して番号順を検証しているため、mtime依存の検証にはなっていない。

### 2026-06-28 17:30 JST Group Loss Penalty Ranking

作業:

- `model-candidate-selection` に `--group-loss-penalty-weight` を追加した。
- `group_loss_penalty`, `robust_total_adjusted_pnl_min_cost`, `robust_total_adjusted_pnl_min_base` をcandidate summaryへ追加した。
- delay `1` 4fold sweepで、weight `0.0` と `1.0` を比較した。
- weight `1.0` topを2024-12 holdoutへ固定適用した。
- report: `docs/reports/00047_2026-06-28_group_loss_penalty_ranking.md`
- 採番はファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- weight `0.0`: `data/reports/backtests/20260628_082937_model_candidate_selection/`
- weight `1.0`: `data/reports/backtests/20260628_082923_model_candidate_selection/`
- 2024-12 holdout: `data/reports/backtests/20260628_083021_model_timed_ev_2024-12/`

結果:

| candidate | adjusted pnl | trades | profit factor | max drawdown |
|---|---:|---:|---:|---:|
| previous combined-gate top | `-149.7354` | `33` | `0.3820` | `176.6504` |
| group-loss penalty top | `-126.0770` | `33` | `0.4731` | `165.9662` |

判断:

- group-loss soft rankingは、validation内で深いgroup損失を持つ候補の順位を下げられる。
- 2024-12 holdout損失は縮んだが、NoTradeには大きく負けるため採用しない。
- 引き続き、中心課題はentry/side calibrationとprofit-barrier hit calibration。group-loss penaltyは候補比較の補助軸に留める。

### 2026-06-28 17:36 JST Profit Barrier Prediction Calibration

作業:

- `trade_data.modeling profit-barrier-report` を追加した。
- prediction parquet全体をlong/short縦持ちにして、actual hit rate / predicted mean / overestimate / Brier scoreをsplit・月・regime・bucket別に集計できるようにした。
- `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/` のvalid/test predictionsでsmoke診断した。
- report: `docs/reports/00048_2026-06-28_profit_barrier_prediction_calibration.md`
- 採番はファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifact:

- `data/reports/modeling/20260628_083635_profit_barrier_valid_test_exit_event_prob/`

結果:

| scope | rows | actual hit | predicted mean | overestimate |
|---|---:|---:|---:|---:|
| overall | `288030` | `0.3661` | `0.3299` | `0.0000` |
| test `0.4-0.6` bucket | `9481` | `0.1807` | `0.4447` | `0.2640` |
| test `0.6-0.8` bucket | `63` | `0.1905` | `0.6216` | `0.4311` |
| valid `0.60-0.80` bucket | `419` | `0.2267` | `0.6231` | `0.3964` |

判断:

- 全体平均ではprofit-barrier確率は過小評価に見えるが、threshold `0.4` 以上のtest bucketは強く過大評価している。
- 2024-12 holdoutでactual profit barrier missが高かった理由と整合する。
- 次はOOF予測へこの診断を適用し、bucket崩れが単月固有か構造的かを確認する。

### 2026-06-28 17:44 JST Profit Barrier OOF Representative

作業:

- `profit_barrier` target setを追加し、`long_profit_barrier_hit` / `short_profit_barrier_hit` だけを学習するblocked OOFを可能にした。
- EV予測列がないtarget setでもOOF評価とreport出力が落ちないよう、selection metricsは必要列がある場合だけ計算するようにした。
- 2024-07 / 2024-09 / 2024-11 / 2025-01 の代表4ヶ月で1ヶ月blocked OOFを実行した。
- `profit-barrier-report` をOOF predictionへ適用した。
- report: `docs/reports/00049_2026-06-28_profit_barrier_oof_representative.md`
- 採番はファイル更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- OOF predictions: `experiments/20260628_084318_profit_barrier_oof_representative_smoke/predictions_oof.parquet`
- OOF metrics: `experiments/20260628_084318_profit_barrier_oof_representative_smoke/metrics.json`
- calibration report: `data/reports/modeling/20260628_084402_profit_barrier_oof_representative_smoke/`

結果:

| scope | rows | actual hit | predicted mean | error |
|---|---:|---:|---:|---:|
| overall stacked | `238482` | `0.3734` | `0.3295` | `-0.0439` |
| `0.4-0.6` bucket | `49088` | `0.4759` | `0.4341` | `-0.0417` |
| `>=0.4` long | `37938` | `0.5164` | `0.4282` | `-0.0882` |
| `>=0.4` short | `11165` | `0.3376` | `0.4545` | `0.1169` |
| `>=0.5` long | `2149` | `0.3685` | `0.5556` | `0.1870` |
| `>=0.5` short | `1638` | `0.3107` | `0.5196` | `0.2089` |

判断:

- 前回testで見た `0.4-0.6` bucketの大きな過大評価は、代表OOF全体では再現しなかった。
- ただし short側と `>=0.5` 高信頼bucketは過大評価しており、profit-barrier確率を単純なhard gateとして採用するのは危険。
- global calibration補正も危険。全体平均は過小評価だが、side/bucketごとに符号が違う。
- 次は side別・bucket別・support-aware なOOF calibrationを作り、raw probabilityではなくsmoothed actual hit rate / uncertainty / supportを候補選定へ入れる。

### 2026-06-28 17:56 JST Profit Barrier Bucket Calibration

作業:

- `trade_data.modeling profit-barrier-calibrate` を追加した。
- side別・probability bucket別の実測profit-barrier hit rateをLaplace smoothingし、calibrated probability列をprediction parquetへ追加できるようにした。
- `min_bucket_rows` 未満のbucketはside全体へfallbackする。
- `calibrated_prob_lower`, support, source, bucket列も保存する。
- `--oof-column dataset_month` を追加し、月別holdoutでfitから抜いた月へ校正を当てる診断を可能にした。
- report: `docs/reports/00050_2026-06-28_profit_barrier_bucket_calibration.md`
- 採番はファイル更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- `data/reports/modeling/20260628_085552_profit_barrier_oof_month_bucket_calibration_smoke_v2/`
- calibrated predictions: `data/reports/modeling/20260628_085552_profit_barrier_oof_month_bucket_calibration_smoke_v2/predictions_profit_barrier_calibrated.parquet`
- OOF calibration table: `data/reports/modeling/20260628_085552_profit_barrier_oof_month_bucket_calibration_smoke_v2/oof_calibration_table.csv`

結果:

| probability | actual hit | predicted mean | calibration error | Brier | threshold accuracy |
|---|---:|---:|---:|---:|---:|
| raw | `0.3734` | `0.3295` | `-0.0439` | `0.2272` | `0.6166` |
| calibrated | `0.3734` | `0.3707` | `-0.0027` | `0.2250` | `0.6129` |
| conservative lower | `0.3734` | `0.3684` | `-0.0050` | `0.2251` | `0.6129` |

threshold subset:

| signal | side | rows | actual hit | predicted mean | error |
|---|---|---:|---:|---:|---:|
| raw `>=0.4` | short | `11165` | `0.3376` | `0.4545` | `0.1169` |
| calibrated `>=0.4` | long | `115742` | `0.4859` | `0.4808` | `-0.0051` |
| calibrated `>=0.5` | long | `43362` | `0.4106` | `0.5234` | `0.1128` |
| lower `>=0.5` | long | `43362` | `0.4106` | `0.5208` | `0.1102` |

判断:

- 月別OOFでもglobalにはBrierとbiasが改善した。
- ただし校正後 `>=0.5` はlong偏重になり、強い過大評価が残る。
- 月×sideでは 2024-11 long `+0.1378`、2024-11 short `-0.1228`、2025-01 long `-0.0974` と不安定。
- 校正列は採用するが、policy hard gateへ直結しない。次は raw / calibrated / lower を同一validation条件で `model-policy` に渡して比較する。

### 2026-06-28 18:06 JST Profit Barrier Policy Column Validation

作業:

- policy exit-event probabilityモデルのvalid/test予測に対し、profit-barrier raw / calibrated / conservative lower列を同一条件で比較した。
- policy valid 4ヶ月では `--oof-column dataset_month` による月別OOF calibrationを使い、test 2024-12ではvalid全体fitのcalibrationを適用した。
- `model-sweep` は `timed_ev`, exit-event holding minutes, `entry=5,10`, short offset `8,12`, barrier threshold `0.35,0.40,0.45,0.50`, max hold `480,720` で比較した。
- report: `docs/reports/00051_2026-06-28_profit_barrier_policy_column_validation.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- valid month-OOF calibration: `data/reports/modeling/20260628_090051_policy_valid_month_oof_profit_barrier_calibration/`
- test-applied calibration: `data/reports/modeling/20260628_090105_policy_valid_fit_test_profit_barrier_calibration/`
- validation summary: `data/reports/backtests/20260628_profit_barrier_column_validation_summary.csv`
- 2024-12 raw diagnostic: `data/reports/backtests/20260628_090555_model_timed_ev_2024-12/`
- 2024-12 calibrated diagnostic: `data/reports/backtests/20260628_090556_model_timed_ev_2024-12/`
- 2024-12 lower diagnostic: `data/reports/backtests/20260628_090558_model_timed_ev_2024-12/`

結果:

| variant | validation basic eligible | validation min pnl | test 2024-12 adjusted pnl | trades | profit factor |
|---|---|---:|---:|---:|---:|
| raw | `true` | `25.5832` | `-184.9344` | `54` | `0.4738` |
| calibrated | `false` | `-48.8580` | `-215.7914` | `54` | `0.4226` |
| lower | `false` | `-48.8580` | `-215.7914` | `54` | `0.4226` |

判断:

- policy valid内OOFではcalibrationのBrierが raw `0.2270` から calibrated `0.2191` に改善した。
- ただしvalid全体fitを2024-12へ外挿すると、Brierは raw `0.2310` に対して calibrated `0.2488`, lower `0.2484` と悪化した。
- calibrated/lower列はvalidation内でlong-only化し、2024-11の adjusted pnl `-48.8580` によりbasic gateを満たさない。
- raw列はvalidation上はbasic eligibleだが、2024-12で adjusted pnl `-184.9344` と大きく崩れた。
- profit-barrier probabilityはhard gateへ昇格しない。次は `penalty * (1 - calibrated_probability_lower)` のようなEV score penalty / tie-break / uncertainty penaltyとして試す。

### 2026-06-28 18:17 JST Profit Barrier EV Penalty Validation

作業:

- profit-barrier hard gateを外し、既存の `profit_barrier_miss_penalty * (1 - probability)` を raw / calibrated / lower probability列で比較した。
- validation 4foldは `timed_ev`, exit-event holding minutes, `entry=5,10`, short offset `8,12`, max hold `480,720`, penalty `0,0.5,1,2,4,6,8`。
- no-penalty最良、raw strict最良、calibrated/lower strict最良を2024-12反証月へ固定適用した。
- report: `docs/reports/00052_2026-06-28_profit_barrier_ev_penalty_validation.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- raw sweeps: `data/reports/backtests/profit_barrier_penalty_raw/`
- calibrated sweeps: `data/reports/backtests/profit_barrier_penalty_calibrated/`
- lower sweeps: `data/reports/backtests/profit_barrier_penalty_lower/`
- summary CSV: `data/reports/backtests/20260628_profit_barrier_penalty_validation_summary.csv`
- 2024-12 raw penalty diagnostic: `data/reports/backtests/20260628_091701_model_timed_ev_2024-12/`
- 2024-12 no-penalty reference: `data/reports/backtests/20260628_091701_model_timed_ev_2024-12_1/`
- 2024-12 lower diagnostic: `data/reports/backtests/20260628_091701_model_timed_ev_2024-12_2/`
- 2024-12 calibrated diagnostic: `data/reports/backtests/20260628_091701_model_timed_ev_2024-12_3/`

結果:

| variant | validation strict | min pnl | total pnl | 2024-12 adjusted pnl | trades | profit factor |
|---|---|---:|---:|---:|---:|---:|
| lower penalty `6`, max hold `480` | `true` | `52.3018` | `462.2030` | `-214.3986` | `72` | `0.4837` |
| calibrated penalty `6`, max hold `480` | `true` | `52.3018` | `461.7346` | `-212.1886` | `72` | `0.4890` |
| raw penalty `8`, max hold `720` | `true` | `33.5668` | `317.7776` | `-141.9282` | `56` | `0.6029` |
| no penalty reference | `false` | `12.5636` | `287.8596` | `-227.4118` | `63` | `0.4507` |

判断:

- 線形profit-barrier penaltyはvalidationでは明確に改善したが、calibrated/lower topは2024-12でNoTradeに大きく負けた。
- raw penaltyは2024-12損失を縮めたが、`-141.9282` で採用水準ではない。
- calibrated/lowerの2024-12 selected tradesでは `0.4-0.6` bucketが actual hit `0.24` / predicted mean 約 `0.52` と強く過大評価した。
- profit-barrier probability単独のhard gate/global linear penalty探索はいったん打ち切る。次は exit timing、time-exit probability penalty、hazard-like exit policyへ進む。

### 2026-06-28 18:28 JST Exit Event Probability Penalties

作業:

- `time_exit_penalty` と `loss_first_penalty` を `ModelPolicyConfig`, `model-policy`, `model-sweep` に追加した。
- default列は `pred_long_exit_event_prob_0`, `pred_short_exit_event_prob_0`, `pred_long_exit_event_prob_2`, `pred_short_exit_event_prob_2`。
- score adjustmentは `EV -= penalty * probability`。
- validation 4foldで `time_exit_penalty=0,2,4,6`, `loss_first_penalty=0,2,4,6` を比較した。
- validation topとno-penalty/time-only/loss-onlyを2024-12反証月へ固定適用した。
- report: `docs/reports/00053_2026-06-28_exit_event_probability_penalties.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- validation sweeps: `data/reports/backtests/exit_event_penalty_soft/`
- validation summary: `data/reports/backtests/20260628_exit_event_penalty_soft_validation_summary.csv`
- 2024-12 validation top: `data/reports/backtests/20260628_092737_model_timed_ev_2024-12/`
- 2024-12 no-penalty reference: `data/reports/backtests/20260628_092737_model_timed_ev_2024-12_1/`
- 2024-12 time-only: `data/reports/backtests/20260628_092737_model_timed_ev_2024-12_2/`
- 2024-12 loss-only: `data/reports/backtests/20260628_092737_model_timed_ev_2024-12_3/`

結果:

| policy | validation strict | min pnl | total pnl | 2024-12 adjusted pnl | trades | profit factor |
|---|---|---:|---:|---:|---:|---:|
| time `6` + loss `6`, max hold `720` | `true` | `75.1682` | `531.6246` | `-172.7944` | `46` | `0.4960` |
| no penalty reference | `false` | `12.5636` | `287.8596` | `-227.4118` | `63` | `0.4507` |
| time-only `6` | - | - | - | `-178.2488` | `57` | `0.5235` |
| loss-only `6` | - | - | - | `-175.3652` | `50` | `0.5222` |

判断:

- time/loss soft penaltyはvalidation上ではprofit-barrier penaltyより強い候補を作った。
- 2024-12では損失とdrawdownを縮めたが、NoTradeには大きく負ける。
- direction errorとactual barrier missは依然高く、entry score penaltyだけでは方向選択やtail lossを直せない。
- 実装は探索軸として残すが標準policyへ昇格しない。次はevent probabilityで予定保有時間を短縮するhazard-like policyへ進む。

### 2026-06-28 18:40 JST Holding Shrink Validation

作業:

- `time_exit_holding_shrink` と `loss_first_holding_shrink` を `ModelPolicyConfig`, `model-policy`, `model-sweep` に追加した。
- `timed_ev` / `fixed_horizon_ev` の予定保有時間に `1 - shrink * event_probability` をかける。entry scoreは落とさず、entry後の予定決済だけを早める。
- validation 4foldで `time_exit_holding_shrink=0,0.25,0.5,0.75,1`, `loss_first_holding_shrink=0,0.25,0.5,0.75,1` を比較した。
- validation top、top2、no-shrink reference、前回のentry penalty topを2024-12反証月へ固定適用した。
- report: `docs/reports/00054_2026-06-28_holding_shrink_validation.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- validation sweeps: `data/reports/backtests/holding_shrink_soft/`
- validation summary: `data/reports/backtests/20260628_holding_shrink_validation_summary.csv`
- 2024-12 holding shrink top: `data/reports/backtests/20260628_094021_model_timed_ev_2024-12/`
- 2024-12 holding shrink top2: `data/reports/backtests/20260628_094021_model_timed_ev_2024-12_1/`
- 2024-12 entry penalty top: `data/reports/backtests/20260628_094021_model_timed_ev_2024-12_2/`
- 2024-12 no-shrink reference: `data/reports/backtests/20260628_094021_model_timed_ev_2024-12_3/`

結果:

| policy | validation strict | min pnl | total pnl | 2024-12 adjusted pnl | trades | profit factor |
|---|---|---:|---:|---:|---:|---:|
| holding shrink `time=0.25`, `loss=0.75`, max hold `720` | `true` | `55.5528` | `450.7384` | `-209.0802` | `68` | `0.4728` |
| holding shrink `time=0.75`, `loss=0.75`, max hold `480` | `true` | `53.2266` | `443.0060` | `-236.7336` | `76` | `0.4361` |
| entry penalty `time=6`, `loss=6`, max hold `720` | `true` | `75.1682` | `531.6246` | `-172.7944` | `46` | `0.4960` |
| no-shrink reference | `false` | `12.5636` | `287.8596` | `-227.4118` | `63` | `0.4507` |

判断:

- holding shrink単独でもvalidationではno-shrinkを大きく上回り、strict候補を作った。
- 2024-12ではno-shrinkより損失を縮める候補はあるが、entry penalty topには届かずNoTradeにも大きく負ける。
- 予定保有時間をentry時点で短縮するだけでは、悪いentryの抑制やactual barrier miss改善が弱い。
- 実装は探索軸として残すが標準policyへ昇格しない。次はentry penaltyとの組み合わせ、または保有中にprobabilityを再評価するdynamic / hazard-like exitへ進む。

### 2026-06-28 18:48 JST Entry Penalty Holding Shrink Combo

作業:

- entry EV penaltyとholding shrinkを同時に使う小gridをvalidation 4foldで比較した。
- gridは `time_exit_penalty=0,3,6`, `loss_first_penalty=0,3,6`, `time_exit_holding_shrink=0,0.25,0.5`, `loss_first_holding_shrink=0,0.5,0.75`, max hold `480,720`。
- validation top2本、entry penalty単独、no-shrink referenceを2024-12反証月へ固定適用した。
- report: `docs/reports/00055_2026-06-28_entry_penalty_holding_shrink_combo.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- validation sweeps: `data/reports/backtests/entry_penalty_holding_shrink_combo/`
- validation summary: `data/reports/backtests/20260628_entry_penalty_holding_shrink_combo_summary.csv`
- 2024-12 combo top min-pnl: `data/reports/backtests/20260628_094754_model_timed_ev_2024-12/`
- 2024-12 combo top2 holdout: `data/reports/backtests/20260628_094754_model_timed_ev_2024-12_1/`
- 2024-12 entry penalty reference: `data/reports/backtests/20260628_094754_model_timed_ev_2024-12_2/`
- 2024-12 no-shrink reference: `data/reports/backtests/20260628_094754_model_timed_ev_2024-12_3/`

結果:

| policy | validation strict | min pnl | total pnl | 2024-12 adjusted pnl | trades | profit factor |
|---|---|---:|---:|---:|---:|---:|
| penalty `6/6` + time shrink `0.50`, max hold `720` | `true` | `85.1886` | `493.4848` | `-173.6648` | `47` | `0.4733` |
| penalty `6/6` + time shrink `0.25`, max hold `720` | `true` | `80.0648` | `513.3876` | `-159.0158` | `46` | `0.5211` |
| entry penalty `6/6`, max hold `720` | `true` | `75.1682` | `531.6246` | `-172.7944` | `46` | `0.4960` |
| no-shrink reference | `false` | `12.5636` | `287.8596` | `-227.4118` | `63` | `0.4507` |

判断:

- combinationはvalidation min pnlを改善したが、total pnlはentry penalty単独が上。
- 2024-12ではcombo top2がentry penalty単独より `13.7786` 改善したが、NoTradeには大きく負ける。
- validation topの `time shrink=0.50` は2024-12でdirection error `0.6383` と壊れた。
- 標準policyには昇格しない。次は保有中にprobabilityを再評価するdynamic / hazard-like exit policyを実装する。

### 2026-06-28 19:01 JST Dynamic Exit Probability Thresholds

作業:

- `time_exit_exit_threshold` と `loss_first_exit_threshold` を `ModelPolicyConfig`, `model-policy`, `model-sweep` に追加した。
- 保有中に現在sideの `pred_*_exit_event_prob_0` / `pred_*_exit_event_prob_2` を再評価し、finite閾値以上ならflat signalを出して予定exit時刻を消すdynamic / hazard-like exitを実装した。
- validation 4foldで `time_exit_penalty=0,6`, `loss_first_penalty=0,6`, `time_exit_holding_shrink=0,0.25`, `time_exit_exit_threshold=inf,0.75,0.90`, `loss_first_exit_threshold=inf,0.50,0.75`, max hold `480,720` を比較した。
- validation上位、entry penalty + holding shrink reference、entry penalty reference、no-penalty referenceを2024-12反証月へ固定適用した。
- report: `docs/reports/00056_2026-06-28_dynamic_exit_probability.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- validation sweeps: `data/reports/backtests/dynamic_exit_probability/`
- validation summary: `data/reports/backtests/20260628_dynamic_exit_probability_summary.csv`
- 2024-12 fixed diagnostics: `data/reports/backtests/dynamic_exit_probability/fixed_2024_12/`
- 2024-12 fixed summary: `data/reports/backtests/20260628_dynamic_exit_probability_2024_12_fixed.csv`

結果:

| policy | validation strict | min pnl | total pnl | 2024-12 adjusted pnl | trades | profit factor |
|---|---|---:|---:|---:|---:|---:|
| penalty `6/6` + time shrink `0.25` + dynamic `time=0.90`, `loss=0.75` | `false` | `81.1178` | `528.8282` | `-162.9304` | `46` | `0.5146` |
| penalty `6/6` + dynamic `time=0.90`, `loss=0.75` | `false` | `76.2212` | `543.3552` | `-176.3334` | `46` | `0.4905` |
| penalty `6/6` + time shrink `0.25`, no dynamic | `false` | `80.0648` | `513.3876` | `-159.0158` | `46` | `0.5211` |
| entry penalty `6/6`, no dynamic | `false` | `75.1682` | `531.6246` | `-172.7944` | `46` | `0.4960` |
| no-penalty dynamic high-turnover | `false` | `72.1134` | `377.7014` | `-104.0014` | `171` | `0.7174` |
| no-penalty no-dynamic reference | `false` | `12.5636` | `287.8596` | `-227.4118` | `63` | `0.4507` |

判断:

- dynamic exit thresholdはvalidation basic条件ではわずかに改善した。`actual_profit_barrier_miss_rate_smoothed` 基準ならstrict候補は残るが、`predicted_profit_barrier_miss_rate_smoothed` を追加警告gateにすると0件になる。
- 2024-12ではpenalty込みdynamic topがno-dynamic comboよりわずかに悪化し、NoTradeにも大きく負けた。
- no-penalty dynamic high-turnoverは2024-12損失を `-104.0014` まで縮めたが、direction error `0.6316`、smoothed miss `0.9075` で汎化候補としては弱い。
- dynamic exitは探索軸として残すが、標準policyには昇格しない。次はexit制御単独ではなく、side/entry calibrationとprofit-barrier missの同時制御へ戻る。

### 2026-06-28 19:25 JST Combined Side Confidence And Miss Control

作業:

- 現行dataset生成コードで `best_side` とexit-event/profit-barrier targetsを同居させた `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/` を生成した。
- `target-set policy` で `experiments/20260628_101740_policy_combined_side_exit_p1_l1p2/` を学習した。
- side-confidence reportを実行し、overall accuracy `0.4750`, balanced accuracy `0.4856`, confidence mean `0.5404`, overconfidence `0.0654` を確認した。
- validation 4foldで profit-barrier miss penalty、exit-event penalty、time-exit holding shrink、side-confidence penalty、min side confidenceをjoint sweepした。
- validation代表候補を2024-12反証月へ固定適用した。
- report: `docs/reports/00057_2026-06-28_combined_side_miss_joint.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/`
- model: `experiments/20260628_101740_policy_combined_side_exit_p1_l1p2/`
- side-confidence report: `data/reports/modeling/20260628_101811_combined_side_exit_side_confidence_report/`
- validation sweeps: `data/reports/backtests/combined_side_miss_joint/`
- validation summary: `data/reports/backtests/20260628_combined_side_miss_joint_summary.csv`
- 2024-12 fixed summary: `data/reports/backtests/20260628_combined_side_miss_joint_2024_12_fixed.csv`

結果:

| policy | validation strict | min pnl | total pnl | 2024-12 adjusted pnl | trades | profit factor |
|---|---|---:|---:|---:|---:|---:|
| prior combo `penalty=6/6`, time shrink `0.25` | `true` | `80.0648` | `513.3876` | `-159.0158` | `46` | `0.5211` |
| min side confidence `0.55`, `penalty=6/6` | `true` | `65.0410` | `375.9450` | `-91.9786` | `33` | `0.5963` |
| loss penalty `6` + side penalty `4` | `true` | `55.0364` | `520.2350` | `-126.5046` | `43` | `0.5788` |
| profit miss penalty `4` + min side confidence `0.60` | `true` | `41.5250` | `331.6830` | `-92.1928` | `22` | `0.4199` |
| no-penalty reference | `false` | `12.5636` | `287.8596` | `-227.4118` | `63` | `0.4507` |

判断:

- combined policy modelのbest_side probabilityは弱く、標準のhard gateやglobal penaltyに昇格しない。
- `min_side_confidence=0.55` は2024-12損失を縮めたが、validation min/total pnlを削り、NoTradeにも届かない。単月反証月を見た後の採用はしない。
- profit-barrier miss penaltyもtrade throttleとしては効くが、miss問題自体は残る。
- 次はbest_sideをpolicy multi-taskに混ぜるより、別建て `target-set side_confidence` やblocked OOF calibrationで信頼度そのものを改善する。

### 2026-06-28 19:39 JST Side Confidence Target Weighting

作業:

- `trade_data.modeling` に `--sample-weighting target` / `month_target` を追加した。
- classification targetでは各target自身のclass labelでsample weightを作る。`month_target` は `dataset_month x target class` を均す。
- `target-set side_confidence` を同一splitで `month_label` と `month_target` の2条件で学習した。
- policy combined予測のentry/exit列は維持し、`pred_best_side_prob_*` だけを `month_target` side modelに差し替えたparquetを作った。
- validation 4foldと2024-12 fixedで、side confidenceだけ差し替えた影響を確認した。
- report: `docs/reports/00058_2026-06-28_side_confidence_target_weighting.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- dedicated side model, `month_label`: `experiments/20260628_103304_side_confidence_dedicated_p1_l1p2/`
- target-weighted side model, `month_target`: `experiments/20260628_103541_side_confidence_month_target_p1_l1p2/`
- side-confidence report: `data/reports/modeling/20260628_103557_side_confidence_month_target_report/`
- merged predictions: `data/reports/modeling/20260628_103557_side_confidence_month_target_report/policy_predictions_valid_month_target_side.parquet`
- validation rows: `data/reports/backtests/20260628_side_confidence_month_target_validation_rows.csv`
- validation summary: `data/reports/backtests/20260628_side_confidence_month_target_summary.csv`
- 2024-12 fixed run: `data/reports/backtests/side_confidence_month_target_fixed_2024_12/20260628_103731_model_timed_ev_2024-12/`

結果:

| model | accuracy | balanced accuracy | confidence mean | overconfidence |
|---|---:|---:|---:|---:|
| policy combined reference | `0.4750` | `0.4856` | `0.5404` | `0.0654` |
| dedicated side, `month_label` | `0.4750` | `0.4856` | `0.5404` | `0.0654` |
| dedicated side, `month_target` | `0.4748` | `0.4896` | `0.5353` | `0.0605` |

| policy side confidence | min side conf | validation min pnl | validation total pnl | validation total trades | 2024-12 adjusted pnl | 2024-12 trades |
|---|---:|---:|---:|---:|---:|---:|
| disabled reference | `0.00` | `75.1682` | `531.6246` | `157` | n/a | n/a |
| prior policy side | `0.55` | `65.0410` | `375.9450` | n/a | `-91.9786` | `33` |
| month-target side | `0.55` | `-15.2120` | `178.8212` | `95` | `-88.1826` | `32` |

判断:

- `target-set side_confidence` の `month_label` 結果はpolicy combined内の `best_side` と完全一致した。現行HGBはtargetごと独立fitであり、multi-task crowdingは主因ではない。
- `month_target` はbalanced accuracyとoverconfidenceを少し改善したが、validation 4foldのtrade selectionを壊した。
- 2024-12だけの小改善は採用理由にしない。side-confidence hard/min gateは標準採用しない。
- target-aware weightingは実装として残すが、次はside confidenceのhard gateではなくOOF calibration/diagnosticまたはshared representation modelへ進む。

### 2026-06-28 19:52 JST Diagnostic Soft Penalty Ranking

作業:

- `model-candidate-selection` に複合diagnostic soft penaltyを追加した。
- direction error、actual profit barrier miss、EV overestimateが閾値を超えた分をpenalty化し、eligible候補のrobust scoreを下げる。
- `combined_side_miss_joint` の4fold sweepを再利用し、base/cost同一入力でdiagnostic rankingの影響だけを切り分けた。
- diagnostic ranking topを2024-12反証月へ固定適用した。
- report: `docs/reports/00059_2026-06-28_diagnostic_soft_penalty_ranking.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- baseline selection: `data/reports/backtests/diagnostic_soft_penalty_baseline/20260628_104916_model_candidate_selection/`
- diagnostic selection: `data/reports/backtests/diagnostic_soft_penalty_validation/20260628_104938_model_candidate_selection/`
- diagnostic top fixed 2024-12: `data/reports/backtests/diagnostic_soft_penalty_validation/fixed_2024_12/20260628_105024_model_timed_ev_2024-12/`

結果:

| candidate | validation min pnl | validation total pnl | diagnostic penalty | robust min pnl | 2024-12 adjusted pnl | profit factor |
|---|---:|---:|---:|---:|---:|---:|
| diagnostic top, no shrink | `75.1682` | `531.6246` | `5.8683` | `69.2999` | `-172.7944` | `0.4960` |
| prior holding shrink combo | `80.0648` | `513.3876` | `11.3607` | `68.7041` | `-159.0158` | `0.5211` |
| min side confidence diagnostic | `65.0410` | `375.9450` | `2.9922` | `62.0488` | `-91.9786` | `0.5963` |

判断:

- soft penaltyによりvalidation順位は変わったが、2024-12反証月では悪化した。
- diagnostic soft penaltyはtie-break/診断基盤として残す。
- 今回のrankingは標準policyへ昇格しない。post-hoc診断値の改善だけで候補を採用しない。

### 2026-06-28 20:01 JST Shared MLP Regression Smoke

作業:

- `trade_data.modeling train-shared-mlp` を追加した。
- scikit-learn `MLPRegressor` を `StandardScaler` と `TransformedTargetRegressor` で包み、複数回帰targetを1つのshared modelで同時出力する。
- 既存HGBと同じprediction parquet / metrics / report artifactを出す。
- `xauusd_m1_p1_l1p2_policy_combined` の2024-07 train、2024-09 valid、2024-12 testで極小smokeを実行した。
- smoke predictionを `timed_ev` backtestへ接続した。
- report: `docs/reports/00060_2026-06-28_shared_mlp_regression_smoke.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- MLP smoke model: `experiments/20260628_110048_shared_mlp_policy_smoke/`
- executable smoke: `data/reports/backtests/shared_mlp_policy_smoke/20260628_110101_model_timed_ev_2024-12/`

結果:

| item | value |
|---|---:|
| train rows | `632` |
| valid rows | `28885` |
| test rows | `28763` |
| targets | `19` regression targets |
| MLP n_iter | `3/3` |
| executable 2024-12 adjusted pnl | `-88.1778` |
| executable 2024-12 raw pnl | `19.2880` |
| trades | `689` |
| profit factor | `0.8632` |
| max drawdown | `155.4504` |

判断:

- shared MLP regressionの接続基盤は動いた。
- 極小smokeは性能判断ではない。`max_iter=3` で未収束、sampleも2%のみ。
- executable smokeでは取引過多、long偏り、コスト負けが明確。代表4fold本実験ではturnover制御とside balanceを必ず見る。
- classification probabilityは未対応なので、exit-event/profit-barrier確率が必要なpolicyはHGB classifierとのhybridまたはshared classifier追加を別に検討する。

### 2026-06-28 20:06 JST Shared MLP Blocked OOF

作業:

- `trade_data.modeling oof-shared-mlp` を追加した。
- holdout月ごとにfit月を分け、purge/embargoを適用した上でshared MLP regressionをfitする。
- 2024-07/2024-09の2ヶ月で極小OOF smokeを実行した。
- 生成した `predictions_oof.parquet` を各holdout月の `timed_ev` backtestへ接続した。
- report: `docs/reports/00061_2026-06-28_shared_mlp_blocked_oof.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- OOF smoke model: `experiments/20260628_110628_shared_mlp_oof_smoke/`
- executable smoke 2024-07: `data/reports/backtests/shared_mlp_oof_smoke/20260628_110643_model_timed_ev_2024-07/`
- executable smoke 2024-09: `data/reports/backtests/shared_mlp_oof_smoke/20260628_110643_model_timed_ev_2024-09/`

結果:

| item | value |
|---|---:|
| input / OOF rows | `60472 / 60472` |
| fold fit rows after sample | `578`, `632` |
| fold n_iter | `2/2`, `2/2` |
| OOF selected trades | `47557` |
| OOF oracle-exit pnl | `846517.1014` |
| OOF side accuracy | `0.5784` |
| 2024-07 executable adjusted pnl | `47.3170` |
| 2024-09 executable adjusted pnl | `32.6390` |
| 2024-07 / 2024-09 trades | `562 / 985` |

判断:

- shared MLP blocked OOFの配線は動いた。
- 2% sample、max_iter 2のsmokeなので性能採用には使わない。
- 両月のexecutable pnlはプラスだが、取引数が多く、2024-07はshort signalが少ない。代表4fold本実験ではturnoverとside balanceを主要診断にする。

### 2026-06-28 20:20 JST Shared MLP 4fold Pilot

作業:

- `oof-shared-mlp` を代表validation 4ヶ月 `2024-07,2024-09,2024-11,2025-01` で実行した。
- `sample_frac=0.15`, `max_iter=40`, hidden layers `32,16`, `alpha=0.01`, `learning_rate_init=0.001`。
- purge/embargoは `purge_label_overlap=true`, `embargo_hours=24`。
- OOF予測を `timed_ev` fixed policyと4fold sweepへ接続した。
- strict candidate selectionと、片側偏りだけを緩めたdiagnostic selectionを比較した。
- report: `docs/reports/00062_2026-06-28_shared_mlp_4fold_pilot.md`
- 採番と最新判断は、ファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- OOF model: `experiments/20260628_111106_shared_mlp_oof_4fold_pilot/`
- fixed backtests: `data/reports/backtests/shared_mlp_oof_4fold_pilot/`
- sweeps: `data/reports/backtests/shared_mlp_oof_4fold_pilot_sweep/`
- strict selection: `data/reports/backtests/shared_mlp_oof_4fold_pilot_selection/20260628_111815_model_candidate_selection/`
- relaxed side diagnostic: `data/reports/backtests/shared_mlp_oof_4fold_pilot_selection_relaxed_side/20260628_111910_model_candidate_selection/`

結果:

| item | value |
|---|---:|
| OOF rows | `119241` |
| folds | `4` |
| fold n_iter | `40/40` all hit max_iter |
| long best adjusted pnl R2 | `-0.003462` |
| short best adjusted pnl R2 | `-0.164505` |
| long exit event minutes R2 | `0.338873` |
| short exit event minutes R2 | `0.345407` |
| side score R2 | `-0.151357` |
| OOF oracle side accuracy | `0.590860` |
| fixed policy total adjusted pnl | `-1.8770` |
| fixed policy worst month | `2024-11 -171.2478` |
| strict selection eligible | `0` |
| relaxed side selection eligible | `4` |

判断:

- shared MLPはexit timingには信号を持つが、entry EVとside scoreはまだ弱い。
- fixed policyは高turnoverでコスト負けし、2024-11の崩れが大きい。
- strict selectionでは採用候補なし。片側偏りを100%許容すれば候補は残るが、未知regimeへの頑健性としては採用不可。
- shared MLPを標準policyへ昇格しない。次はexit timing専用化、entry/side calibration、HGB classifierとのhybrid、またはshared classifier追加を検証する。

### 2026-06-28 20:38 JST HGB Entry With MLP Exit Hybrid

作業:

- HGB combined validation predictionsに、shared MLP OOFの `pred_*_exit_event_minutes` をmergeした。
- HGB holding baseとHGB entry/side + MLP holding hybridを、同一4fold gridで比較した。
- 同じHGB splitでfinal shared MLPをtrainし、2024-12 test用のMLP holdingを生成した。
- validation top候補を2024-12へ固定適用し、HGB holding / MLP holdingを比較した。
- report: `docs/reports/00063_2026-06-28_hgb_mlp_exit_hybrid.md`
- 採番と最新判断は、ファイルシステムの更新時刻(mtime)や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- hybrid validation predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_oof.parquet`
- hybrid test predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2024_12.parquet`
- MLP final model: `experiments/20260628_113707_shared_mlp_hgb_split_test_2024_12/`
- base sweeps: `data/reports/backtests/hgb_exit_holding_base_sweep/`
- hybrid sweeps: `data/reports/backtests/hgb_entry_mlp_exit_hybrid_sweep/`
- fixed 2024-12 tests: `data/reports/backtests/hgb_vs_mlp_exit_holding_2024_12/`

結果:

| item | base | hybrid |
|---|---:|---:|
| validation eligible candidates | `51` | `58` |
| validation top min pnl | `78.4344` | `81.5352` |
| validation top sum pnl | `369.5736` | `396.9782` |
| validation top max DD | `68.0340` | `60.0744` |
| 2024-12 fixed adjusted pnl | `-91.5596` base top HGB holding | `-54.6032` hybrid top MLP holding |
| 2024-12 direction error | `0.6250` | `0.6327` |
| 2024-12 EV over realized | `22.3310` | `23.0714` |

判断:

- MLP holdingはvalidationでは小幅に改善する。
- 2024-12でも損失を縮めるが、NoTradeには届かない。
- 主因はexit timingではなく、direction errorとEV過大評価。MLP exit timingだけでは壊れたentry/sideを救えない。
- hybridは標準policyへ昇格しない。MLP exit timingは補助信号として残し、本流はentry/side risk controlとEV calibrationへ戻す。

### 2026-06-28 20:45 JST Group Loss Gate And Posthoc Failure Analysis

作業:

- HGB entry/side + MLP exit timing hybridのvalidation sweepsに対して、group-loss / diagnostic penaltyで候補を再選定した。
- `group_loss_penalty_weight=1.0`、group gate60、group gate50、diagnostic soft penaltyを比較した。
- group gate60 topを2024-12へ固定適用し、HGB holding / MLP holdingを比較した。
- 2024-12の失敗箇所を仮説化するため、posthoc限定で `long:ny_late` と `range_low_vol` blockを診断した。
- report: `docs/reports/00064_2026-06-28_group_loss_gate_posthoc_failure.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- group soft selection: `data/reports/backtests/hgb_entry_mlp_exit_hybrid_selection_group_soft/20260628_114255_model_candidate_selection/`
- group gate60 selection: `data/reports/backtests/hgb_entry_mlp_exit_hybrid_selection_group_gate60/20260628_114255_model_candidate_selection/`
- group gate50 selection: `data/reports/backtests/hgb_entry_mlp_exit_hybrid_selection_group_gate50/20260628_114255_model_candidate_selection/`
- diagnostic soft selection: `data/reports/backtests/hgb_entry_mlp_exit_hybrid_selection_diag_soft/20260628_114255_model_candidate_selection/`
- group gate60 fixed test: `data/reports/backtests/hgb_entry_mlp_exit_group_gate_2024_12/`
- posthoc block diagnostics: `data/reports/backtests/hgb_entry_mlp_exit_posthoc_blocks_2024_12/`

結果:

| item | value |
|---|---:|
| baseline eligible | `58` |
| group soft eligible | `58` |
| group gate60 eligible | `11` |
| group gate50 eligible | `0` |
| diagnostic soft eligible | `58` |
| baseline / group soft top min pnl | `81.5352` |
| group gate60 top min pnl | `23.1484` |
| previous hybrid top 2024-12 MLP holding | `-54.6032` |
| group gate60 top 2024-12 HGB holding | `-69.0240` |
| group gate60 top 2024-12 MLP holding | `-97.6568` |
| posthoc `long:ny_late` block 2024-12 | `-5.4938` |

判断:

- soft group-loss / diagnostic penaltyはtop候補を変えなかった。
- group gate60はvalidation group lossを抑えたが、edgeを削り、2024-12固定testを悪化させた。
- 2024-12の主な崩れは引き続き `long:ny_late`。ただしposthoc blockは後付けなので採用しない。
- 次は `long:session_regime=ny_late` と `long:combined_regime=range_low_vol` をvalidation gridの候補軸として事前に入れ、2024-12を見ずに候補選定する。

### 2026-06-28 21:14 JST Long Rule Validation Grid

作業:

- `model-sweep` に `--side-block-rule-sets` / `--side-extra-margin-rule-sets` を追加した。
- 単一policyの `model-sweep` ではprediction parquetを1回だけ読み、各grid候補で使い回すようにした。
- preload時は欠損行を広いread configで落とさず、候補ごとの必須列で評価直前にdropするようにした。
- `long:session_regime=ny_late` と `long:combined_regime=range_low_vol` をhard block / extra marginのvalidation local gridに入れた。
- validation top近傍の非空rule候補を2024-12へ固定適用した。
- report: `docs/reports/00065_2026-06-28_long_rule_validation_grid.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- hard block local sweeps: `data/reports/backtests/hgb_entry_mlp_exit_long_block_rule_local_sweep/`
- hard block selection: `data/reports/backtests/hgb_entry_mlp_exit_long_block_rule_local_selection/20260628_121018_model_candidate_selection/`
- extra margin local sweeps: `data/reports/backtests/hgb_entry_mlp_exit_long_margin_rule_local_sweep/`
- extra margin selection: `data/reports/backtests/hgb_entry_mlp_exit_long_margin_rule_local_selection/20260628_121238_model_candidate_selection/`
- fixed 2024-12 tests: `data/reports/backtests/hgb_entry_mlp_exit_long_rule_validation_candidates_2024_12/`

結果:

| item | value |
|---|---:|
| validation top rule | none |
| validation top min pnl | `81.5352` |
| validation top sum pnl | `396.9782` |
| best `long:ny_late` block min pnl | `79.7192` |
| best `long:ny_late` block sum pnl | `370.9706` |
| `long:ny_late` block rank0.5 validation min pnl | `78.0572` |
| best `long:range_low_vol` block min pnl | `75.7566` |
| best `long:range_low_vol:+10` margin min pnl | `76.9566` |
| 2024-12 prior hybrid top | `-54.6032` |
| 2024-12 `long:ny_late` block rank0 | `-15.0538` |
| 2024-12 `long:ny_late` block rank0.5 | `-5.4938` |
| 2024-12 `long:range_low_vol` block | `-141.5698` |
| 2024-12 `long:range_low_vol:+10` margin | `-144.2494` |

判断:

- `long:ny_late` blockはposthocだけでなくvalidationでもtop近傍に残る。
- ただしvalidation全体topはruleなしで、`long:ny_late` はsum pnlとEV overestimateが劣る。
- 2024-12では大きく改善するがNoTradeには届かないため、標準policyへ昇格しない。
- `long:range_low_vol` hard block / extra marginは2024-12で悪化したため棄却する。
- 次は単体rule採用ではなく、top min pnlからの許容劣化幅とrisk reductionをselection基準に入れるか検討する。

### 2026-06-28 21:28 JST Near Top Risk Selection

作業:

- `model-candidate-selection` に `--candidate-rank-mode near_top_risk` を追加した。
- best eligible cost min PnLからの許容劣化幅 `--near-top-cost-pnl-tolerance` と、group loss / drawdown / EV overestimate / exit regret / actual miss / side shareのrisk scoreを追加した。
- 直近のhard block / extra margin long rule gridへ、composite riskとdrawdown-only感度を適用した。
- drawdown-onlyで上位になるextra-margin `long:ny_late:+5/+10` を2024-12へ固定適用した。
- report: `docs/reports/00066_2026-06-28_near_top_risk_selection.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- composite hard selection: `data/reports/backtests/hgb_entry_mlp_exit_long_block_rule_near_top_risk_selection/20260628_122635_model_candidate_selection/`
- composite extra-margin selection: `data/reports/backtests/hgb_entry_mlp_exit_long_margin_rule_near_top_risk_selection/20260628_122635_model_candidate_selection/`
- drawdown-only hard selection: `data/reports/backtests/hgb_entry_mlp_exit_long_block_rule_near_top_drawdown_only_selection/20260628_122750_model_candidate_selection/`
- drawdown-only extra-margin selection: `data/reports/backtests/hgb_entry_mlp_exit_long_margin_rule_near_top_drawdown_only_selection/20260628_122750_model_candidate_selection/`
- extra-margin fixed 2024-12: `data/reports/backtests/hgb_entry_mlp_exit_long_near_top_extra_margin_2024_12/`

結果:

| item | value |
|---|---:|
| composite hard top | none |
| composite hard top risk score | `448.1983` |
| composite hard `long:ny_late` rank0.5 risk score | `484.1204` |
| composite hard `long:ny_late` rank0 risk score | `485.7224` |
| composite extra-margin top | none |
| drawdown-only hard top | `long:ny_late`, rank0 |
| drawdown-only extra-margin top | `long:ny_late:+5/+10`, rank0 |
| drawdown-only max DD improvement vs none | `1.1256` |
| 2024-12 extra-margin `long:ny_late:+5` | `-15.0538` |
| 2024-12 extra-margin `long:ny_late:+10` | `-15.0538` |

判断:

- near-top risk rankingは選定インフラとして採用するが、今回の複合riskではruleなしが引き続きtop。
- `long:ny_late` はnear-topには残るが、group loss、EV overestimate、exit regret、side concentrationが悪化するため保守候補として選ばれない。
- drawdown-onlyなら `long:ny_late` を選べるが、max DD改善が小さく、他のrisk proxyを悪化させるため標準基準にしない。
- 次は `long:ny_late` をhard ruleで塞ぐのではなく、side/regime別EV calibrationまたはregime-conditioned risk targetとして扱う。

### 2026-06-28 21:43 JST Side Regime EV Penalty

作業:

- `model-policy` / `model-sweep` に `--side-ev-penalty-rules` を追加した。
- `model-sweep` に `--side-ev-penalty-rule-sets` を追加し、side/regime別EV減点幅をvalidation gridへ入れられるようにした。
- docs reportの検証コードは、ファイル更新時刻ではなく本文内の `日時` を読む意図が分かるよう `read_internal_report_time` へ整理した。
- HGB entry/side + MLP exit hybridで `long:session_regime=ny_late:2/5/10/15` をvalidation 4fold評価した。
- report: `docs/reports/00067_2026-06-28_side_regime_ev_penalty.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- validation sweeps: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_sweep/`
- PnL selection: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_selection/20260628_124130_model_candidate_selection/`
- near-top risk selection: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_selection_risk/20260628_124241_model_candidate_selection/`
- 2024-12 fixed tests: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_2024_12/`

結果:

| item | value |
|---|---:|
| ruleなし validation min pnl | `81.5352` |
| `long:ny_late:15` PnL top validation min pnl | `93.8904` |
| `long:ny_late:15` PnL top validation sum pnl | `424.0446` |
| `long:ny_late:15` risk top validation min pnl | `85.7834` |
| `long:ny_late:15` risk top validation sum pnl | `440.0672` |
| ruleなし 2024-12 | `-54.6032` |
| `long:ny_late:15` PnL top 2024-12 | `-15.0538` |
| `long:ny_late:15` risk top 2024-12 | `-5.4938` |

判断:

- side/regime EV penaltyはhard blockよりも滑らかなrisk controlとして有効な探索軸。
- 今回はvalidationと2024-12の両方でruleなしより改善したが、NoTrade `0` を超えないため標準policyへは昇格しない。
- 次は別holdout月、コスト/遅延ストレス、penalty幅の周辺台地を確認する。

### 2026-06-28 21:52 JST Side EV Penalty Cost Stress

作業:

- 2024-12のHGB entry/side + MLP exit hybrid predictionで、ruleなしbaseline、`long:session_regime=ny_late:15` PnL top、同risk topをcost/delay stressした。
- stress gridは spread `0,0.1,0.2`, slippage `0,0.05,0.1`, execution delay bars `0,1`。
- report: `docs/reports/00068_2026-06-28_side_ev_penalty_cost_stress.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- cost stress runs: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2024_12/`
- risk top: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2024_12/20260628_124906_model_cost_sensitivity_2024-12/`
- PnL top: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2024_12/20260628_124906_model_cost_sensitivity_2024-12_1/`
- baseline: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2024_12/20260628_124906_model_cost_sensitivity_2024-12_2/`

結果:

| item | baseline | PnL top | risk top |
|---|---:|---:|---:|
| standard adjusted pnl | `-54.6032` | `-15.0538` | `-5.4938` |
| delay1 no-cost adjusted pnl | `-45.9842` | `-10.6880` | `+3.6670` |
| high cost delay0 adjusted pnl | `-76.3910` | `-28.6638` | `-26.0816` |
| standard trades | `49` | `31` | `46` |
| standard profit factor | `0.7504` | `0.9154` | `0.9658` |
| standard max DD | `97.3520` | `69.6900` | `61.1556` |

判断:

- risk topはbaselineより大きく壊れにくいが、NoTrade `0` を安定して超えないため標準policyへ昇格しない。
- delay1のプラスは約定遅延に依存した偶然改善として扱い、edgeとはみなさない。
- 現在のhybrid prediction artifactは2024-12までなので、次は別holdout月のdataset追加、HGB/MLP再学習、hybrid prediction生成を行う。

### 2026-06-28 22:03 JST Side EV Penalty 2025-02 Holdout

作業:

- `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined` に2025-02を追加生成した。
- 既存hybridと同じtrain/valid splitで、testだけ2025-02にしたHGB entry/sideモデルとshared MLP exitモデルを再学習した。
- HGB予測にMLPの `pred_*_exit_event_minutes` を `pred_mlp_*_exit_event_minutes` として結合し、hybrid predictionを作成した。
- baseline、`long:session_regime=ny_late:15` PnL top、同risk topを2025-02へ固定適用し、同じcost stress gridを実行した。
- report: `docs/reports/00069_2026-06-28_side_ev_penalty_2025_02_holdout.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の `日時` を基準にする。

Artifacts:

- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/xauusd_m1_2025-02_h24_edge15.parquet`
- HGB: `experiments/20260628_130038_policy_combined_side_exit_test_2025_02/`
- shared MLP: `experiments/20260628_130102_shared_mlp_hgb_split_test_2025_02/`
- hybrid predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2025_02.parquet`
- fixed tests: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_2025_02/`
- cost stress: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2025_02/`

結果:

| item | baseline | PnL top | risk top |
|---|---:|---:|---:|
| standard adjusted pnl | `+81.8334` | `+59.1854` | `+79.4018` |
| high cost delay1 adjusted pnl | `+21.3628` | `-18.7136` | `+19.5898` |
| standard trades | `118` | `111` | `113` |
| standard profit factor | `1.3420` | `1.2338` | `1.3558` |
| standard max DD | `99.3504` | `123.5044` | `113.6334` |
| worst direction/combined | `short:up_low_vol` | `short:up_low_vol` | `short:up_low_vol` |

判断:

- 2025-02ではbaselineとrisk topの両方がNoTradeと高コストstressを上回った。
- risk topは2024-12防御として有効だが、2025-02ではbaselineをわずかに下回るため、標準policyへ昇格しない。
- PnL topは高コスト + delay 1でマイナス化するため、risk topより弱い。
- 次は `short:up_low_vol` / short偏重riskを、複数holdoutを同時に見るselectionで扱う。

### 2026-06-28 23:27 JST Selected Trade Quality EV Replacement

作業:

- 前回の selected-trade quality calibration を、`min_trade_quality` hard gate ではなく entry EV column replacement として検証した。
- `pred_trade_quality_long_adjusted_pnl` / `pred_trade_quality_short_adjusted_pnl` を `timed_ev` の long/short EV として使い、entry threshold `-2,0,1,2,3,4,5` を代表4ヶ月でsweepした。
- report: `docs/reports/00076_2026-06-28_selected_trade_quality_ev_replacement.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

Artifacts:

- validation sweeps: `data/reports/backtests/selected_trade_quality_ev_replacement_validation/`
- validation summary: `data/reports/backtests/selected_trade_quality_ev_replacement_summary/20260628_142622_model_sweep_summary/`
- fixed tests: `data/reports/backtests/selected_trade_quality_ev_replacement_fixed_tests/`

結果:

| item | value |
|---|---:|
| strict eligible candidates | `0` |
| best near-miss validation min pnl | `-4.1156` |
| best near-miss validation sum pnl | `36.1418` |
| best near-miss min trades | `5` |
| fixed 2024-12 adjusted pnl | `-24.2766` |
| fixed 2025-02 adjusted pnl | `-41.1456` |

判断:

- 校正済みqualityをEVへ全面置換すると、平均biasは下がるがentry rankingとtrade数を壊す。
- 直前hybrid基準 min `81.5352` / sum `396.9782` から大きく劣るため、標準採用しない。
- 次は全面置換ではなく、過大評価soft penalty、または `large_loss`, `wrong_side`, `profit_barrier_miss`, `exit_regret` のtrade failure分類targetへ進む。

### 2026-06-28 23:39 JST Selected Trade Quality Overestimate Soft Penalty

作業:

- `add_trade_quality_columns` に `pred_trade_quality_*_overestimate` と `pred_trade_quality_*_overestimate_risk` を追加した。
- `overestimate = max(raw_ev - calibrated_quality, 0)`、`overestimate_risk = -overestimate` とし、既存 `risk_penalty` で部分的にEVから引けるようにした。
- validation 4foldで risk penalty `0,0.1,0.25,0.5,0.75,1` をsweepした。
- validation topとrisk別代表を2024-12 / 2025-02 fixed holdoutへ適用した。
- report: `docs/reports/00077_2026-06-28_selected_trade_quality_overestimate_soft_penalty.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

Artifacts:

- calibration 2024-12 apply: `data/reports/modeling/20260628_143330_selected_trade_quality_hybrid_session_p20_overestimate_risk_2024_12/`
- calibration 2025-02 apply: `data/reports/modeling/20260628_143330_selected_trade_quality_hybrid_session_p20_overestimate_risk_2025_02/`
- validation sweeps: `data/reports/backtests/selected_trade_quality_overestimate_soft_penalty_validation/`
- validation summary: `data/reports/backtests/selected_trade_quality_overestimate_soft_penalty_summary/20260628_143730_model_sweep_summary/`
- fixed tests: `data/reports/backtests/selected_trade_quality_overestimate_soft_penalty_fixed_tests/`

結果:

| item | value |
|---|---:|
| validation top risk penalty | `0.25` |
| validation top min pnl | `86.9174` |
| validation top sum pnl | `442.9766` |
| validation top min trades | `36` |
| fixed 2024-12, risk 0.25 | `-128.2556` |
| fixed 2025-02, risk 0.25 | `43.2518` |
| fixed 2024-12, risk 0.10 | `-222.7318` |
| fixed 2024-12, risk 0.50 | `-77.5040` |

判断:

- soft penaltyはvalidation上の見た目を改善したが、fixed 2024-12で既存baseline `-54.6032` より悪化した。
- EV overestimate平均もvalidation topで `15.6220` とほぼ下がらず、失敗原因の直接制御になっていない。
- selected-trade quality由来の回帰的penaltyはいったん止め、次は `large_loss`, `wrong_side`, `profit_barrier_miss`, `exit_regret_high` の実行trade failure分類targetへ進む。

### 2026-06-28 23:55 JST Trade Failure Classifier Risk

作業:

- `trade_data.meta_model` に `oof-trade-failure-model` を追加した。
- targetは `large_loss`, `wrong_side`, `profit_barrier_miss`, `exit_regret_high`, `any_failure`。
- side別に `pred_trade_failure_<target>_<side>_prob` と `pred_trade_failure_<target>_<side>_risk=-prob` を出力する。
- `large_loss_threshold=10`, `exit_regret_threshold=10` で、hybrid top validation selected trades 106件からOOF分類した。
- `large_loss` はfull validation sweep、他targetは同一policy骨格のrisk smoke sweepを実施した。
- report: `docs/reports/00078_2026-06-28_trade_failure_classifier_risk.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

Artifacts:

- failure model 2024-12 apply: `data/reports/modeling/20260628_144901_trade_failure_hybrid_v1_2024_12/`
- failure model 2025-02 apply: `data/reports/modeling/20260628_144901_trade_failure_hybrid_v1_2025_02/`
- large_loss validation sweeps: `data/reports/backtests/trade_failure_large_loss_risk_validation/`
- large_loss summary: `data/reports/backtests/trade_failure_large_loss_risk_summary/20260628_145258_model_sweep_summary/`
- large_loss fixed tests: `data/reports/backtests/trade_failure_large_loss_risk_fixed_tests/`
- other target smoke sweeps: `data/reports/backtests/trade_failure_*_risk_smoke_validation/`

結果:

| item | value |
|---|---:|
| large_loss OOF AUC | `0.5736` |
| wrong_side OOF AUC | `0.4845` |
| profit_barrier_miss OOF AUC | `0.4595` |
| exit_regret_high OOF AUC | `0.4566` |
| any_failure OOF AUC | `0.5284` |
| large_loss validation top min pnl | `92.8530` |
| large_loss validation top sum pnl | `402.2514` |
| large_loss risk0 same skeleton min pnl | `82.7176` |
| fixed 2024-12 large_loss risk | `-37.2928` |
| fixed 2025-02 large_loss risk | `76.9254` |

判断:

- `large_loss` だけが薄く有効。validation fold最低損益と2024-12固定testを改善した。
- ただし2024-12はまだNoTrade未満で、2025-02はbaselineより少し弱い。標準採用は保留。
- `wrong_side`, `profit_barrier_miss`, `exit_regret_high`, `any_failure` は単独riskでは最良がrisk `0`。
- 次は `large_loss` targetに絞り、threshold `5/10/15`、side/regime別校正、candidate-entry集合への拡張を試す。

### 2026-06-29 00:22 JST Large Loss Threshold Comparison

作業:

- `large_loss_threshold=5` と `15` のOOF trade failure modelを追加生成した。
- 既存 `threshold=10` と同じgridで、validation 4foldのrisk sweepとsummaryを作成した。
- 各thresholdのvalidation top候補を、fixed holdout `2024-12` / `2025-02` に適用した。
- report: `docs/reports/00079_2026-06-29_large_loss_threshold_comparison.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。

Artifacts:

- t5 model apply: `data/reports/modeling/20260628_150052_trade_failure_large_loss_t5_2024_12/`, `data/reports/modeling/20260628_150052_trade_failure_large_loss_t5_2025_02/`
- t15 model apply: `data/reports/modeling/20260628_150053_trade_failure_large_loss_t15_2024_12/`, `data/reports/modeling/20260628_150053_trade_failure_large_loss_t15_2025_02/`
- t5 validation summary: `data/reports/backtests/trade_failure_large_loss_t5_risk_summary/20260628_151951_model_sweep_summary/`
- t10 validation summary: `data/reports/backtests/trade_failure_large_loss_risk_summary/20260628_145258_model_sweep_summary/`
- t15 validation summary: `data/reports/backtests/trade_failure_large_loss_t15_risk_summary/20260628_151951_model_sweep_summary/`
- fixed tests: `data/reports/backtests/trade_failure_large_loss_t5_risk_fixed_tests/`, `data/reports/backtests/trade_failure_large_loss_risk_fixed_tests/`, `data/reports/backtests/trade_failure_large_loss_t15_risk_fixed_tests/`

結果:

| item | t5 | t10 | t15 |
|---|---:|---:|---:|
| OOF AUC | `0.4042` | `0.5736` | `0.5665` |
| validation top min pnl | `88.8168` | `92.8530` | `87.4970` |
| validation top sum pnl | `386.5722` | `402.2514` | `399.4064` |
| fixed 2024-12 adjusted pnl | `22.3498` | `-37.2928` | `-55.4970` |
| fixed 2025-02 adjusted pnl | `-19.6600` | `76.9254` | `21.5216` |

判断:

- `threshold=5` はOOF AUCが0.5未満で、2024-12を救っても2025-02をNoTrade未満にする。採用しない。
- `threshold=15` は分類性能は `10` に近いが、2024-12を悪化させる。優先度を下げる。
- `threshold=10` はOOF/validation/2ヶ月合計で最も筋がよいが、2024-12がまだNoTrade未満。標準採用は保留する。
- 次はthreshold探索ではなく、`threshold=10` のside/regime別校正、またはcandidate-entry集合へのfailure target拡張へ進む。

### 2026-06-29 00:45 JST Trade Failure Probability Calibration

作業:

- `trade_data.meta_model` に `oof-trade-failure-calibration` を追加した。
- 既存 `oof-trade-failure-model` のOOF predictions/tradesを読み、side/regime別にfailure probabilityを校正する。
- 出力列は `pred_trade_failure_<target>_<side>_calibrated_prob/risk` と support-aware `upper_prob/risk`。
- `large_loss threshold=10` で `side only`, `session`, `combined`, `volatility_regime+session_regime` を比較した。
- `combined` はfull grid、`volatility_regime+session_regime` はraw top骨格の軽量smokeを実施した。
- `combined_upper` 以降のfull gridは実行時間が長く、`combined_calibrated` がrawを下回った時点で中断した。未完了variantは採用判断に使っていない。
- report: `docs/reports/00080_2026-06-29_trade_failure_probability_calibration.md`

Artifacts:

- calibration models: `data/reports/modeling/20260628_153210_trade_failure_large_loss_calibration_side_only_2024_12/`, `data/reports/modeling/20260628_153221_trade_failure_large_loss_calibration_session_2024_12/`, `data/reports/modeling/20260628_153237_trade_failure_large_loss_calibration_combined_2024_12/`, `data/reports/modeling/20260628_153253_trade_failure_large_loss_calibration_vol_session_2024_12/`
- combined full validation: `data/reports/backtests/trade_failure_large_loss_calibration_validation/combined_calibrated/`
- combined summary: `data/reports/backtests/trade_failure_large_loss_calibration_summary/combined_calibrated/20260628_154339_model_sweep_summary/`
- vol+session smoke: `data/reports/backtests/trade_failure_large_loss_calibration_smoke/`
- vol+session smoke summary: `data/reports/backtests/trade_failure_large_loss_calibration_smoke_summary/`
- fixed smoke: `data/reports/backtests/trade_failure_large_loss_calibration_fixed_smoke/vol_session_calibrated_risk30/`

結果:

| item | value |
|---|---:|
| raw OOF AUC | `0.5736` |
| combined calibrated OOF AUC | `0.5799` |
| vol+session calibrated OOF AUC | `0.5837` |
| raw t10 validation min pnl | `92.8530` |
| combined full-grid top min pnl | `82.7176` |
| combined full-grid top risk | `0` |
| vol+session calibrated risk30 validation min pnl | `62.7122` |
| vol+session calibrated risk30 validation sum pnl | `523.2990` |
| vol+session calibrated risk30 fixed 2024-12 | `-159.2242` |
| vol+session calibrated risk30 fixed 2025-02 | `-0.4302` |

判断:

- side/regime校正はOOF分類AUCを少し上げたが、実行policyのfold最低PnLを改善しない。
- `combined` full gridではrisk `0` がtopに戻ったため、校正riskは選ばれていない。
- `vol+session risk30` はsum pnlと一部diagnosticを改善するが、最悪月とfixed 2024-12を壊す。
- 今回の校正riskは標準採用しない。基盤は残し、次はcandidate-entry集合へfailure targetを広げる。

### 2026-06-29 01:02 JST Candidate-entry failure model

作業:

- `trade_data.meta_model` に `oof-candidate-failure-model` を追加した。
- selected tradesだけでなく、entry条件を通ったcandidate rowをside別に展開し、`large_adverse = max_adverse_pnl <= -10` を学習する。
- 出力列は `pred_candidate_failure_<target>_<side>_prob/risk`。
- candidate条件は直近raw top骨格に合わせて entry `12`, short offset `6`, side margin `5`, min rank `0.5`。
- 通常risk `-prob` と、診断用の反転risk `-(1 - prob)` をvalidation 4foldで比較した。
- fixed holdout `2024-12` / `2025-02` でも通常riskをsmokeした。
- report: `docs/reports/00081_2026-06-29_candidate_entry_failure_model.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- candidate model 2024-12 apply: `data/reports/modeling/20260628_155801_candidate_failure_large_adverse_t10_2024_12/`
- candidate model 2025-02 apply: `data/reports/modeling/20260628_155821_candidate_failure_large_adverse_t10_2025_02/`
- normal validation summary: `data/reports/backtests/candidate_failure_large_adverse_t10_smoke_summary/20260628_160008_model_sweep_summary/`
- inverse validation summary: `data/reports/backtests/candidate_failure_large_adverse_t10_inverse_smoke_summary/20260628_160203_model_sweep_summary/`
- fixed smoke: `data/reports/backtests/candidate_failure_large_adverse_t10_fixed_smoke/`

結果:

| item | value |
|---|---:|
| candidate count | `9091` |
| long candidates | `2530` |
| short candidates | `6561` |
| `large_adverse` prevalence | `0.5322` |
| OOF AUC | `0.3738` |
| normal risk0 validation min pnl | `82.7176` |
| normal risk10 validation min pnl | `5.9462` |
| inverse risk5 validation min pnl | `39.9032` |
| raw large_loss t10 validation min pnl reference | `92.8530` |
| fixed 2024-12 normal risk10 | `19.2252` |
| fixed 2025-02 normal risk10 | `-18.6000` |

判断:

- candidate rowへ広げることで件数不足は緩和したが、`large_adverse` 二値targetは意思決定riskとしては弱い。
- `large_adverse` は保有中の逆行を捉えるが、24h以内のexit込み最終損益最大化とはズレる。
- fixed holdout改善は片月依存で、validationでもriskなしに勝てない。標準採用しない。
- 次はcandidate rowを使う場合でも、二値adverse分類ではなく、連続EV、下方分位、exit timing込みの実現可能PnL targetを優先する。

### 2026-06-29 01:21 JST Candidate-entry quality quantile

作業:

- `trade_data.meta_model` に `oof-candidate-quality-model` を追加した。
- entry条件を通ったcandidate rowをside別に展開し、side別 `*_best_adjusted_pnl` を連続targetとして学習する。
- 平均回帰と下方分位回帰を同時にfitし、`pred_candidate_quality_*_adjusted_pnl` / `*_lower_adjusted_pnl` / `*_overestimate_risk` を出力する。
- candidate条件は直近raw top骨格に合わせて entry `12`, short offset `6`, side margin `5`, min rank `0.5`。
- mean/lowerの直接EV置換と、lower overestimate riskのsoft penaltyをvalidation 4foldで比較した。
- fixed holdout `2024-12` / `2025-02` でもlower overestimate riskをsmokeした。
- report: `docs/reports/00082_2026-06-29_candidate_entry_quality_quantile.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- candidate quality 2024-12 apply: `data/reports/modeling/20260628_161319_candidate_quality_q25_2024_12/`
- candidate quality 2025-02 apply: `data/reports/modeling/20260628_161344_candidate_quality_q25_2025_02/`
- mean direct summary: `data/reports/backtests/candidate_quality_mean_direct_summary/20260628_161542_model_sweep_summary/`
- lower direct summary: `data/reports/backtests/candidate_quality_lower_direct_summary/20260628_161659_model_sweep_summary/`
- lower overestimate risk summary: `data/reports/backtests/candidate_quality_lower_overestimate_risk_summary/20260628_161822_model_sweep_summary/`
- fixed holdout: `data/reports/backtests/candidate_quality_lower_overestimate_risk_fixed/`

結果:

| item | value |
|---|---:|
| candidate count | `9091` |
| target mean | `23.1947` |
| raw overestimate mean | `7.7361` |
| mean overestimate mean | `6.6840` |
| lower overestimate mean | `1.5366` |
| mean MAE | `16.2496` |
| mean R2 | `-0.0509` |
| lower coverage | `0.6845` |
| mean direct validation min pnl | `-190.2562` |
| lower direct validation min pnl | `-152.8084` |
| lower risk0 validation min pnl | `82.7176` |
| lower risk0.1 validation min pnl | `5.6070` |
| lower risk0.5 validation min pnl | `1.1300` |
| fixed 2024-12 risk0.5 | `-4.8092` |
| fixed 2025-02 risk0.5 | `-45.8502` |

判断:

- 連続PnL targetは二値failureより情報量は多いが、今回の平均回帰はcandidate順位付けとして弱い。
- 下方分位はEV過大評価を抑えるが、entry decisionに使うと保守化しすぎる。
- risk penaltyは2024-12だけを救い、2025-02とvalidation robustnessを壊す。
- 標準採用しない。candidate quality列は診断・calibration補助として残し、次はexit timing、barrier到達順、forced exit、EV calibration誤差を含むtarget設計へ進む。

### 2026-06-29 01:56 JST Candidate quality barrier target

作業:

- `oof-candidate-quality-model` に `--target-mode barrier_event_adjusted_pnl` を追加した。
- targetはprofit firstを `+min_adjusted_edge`、loss firstを `-min_adjusted_edge`、time exitをforced adjusted PnLで扱う。
- 現在のhybrid prediction parquetには `*_forced_adjusted_pnl` が無いため、time exitは `*_fixed_720m_adjusted_pnl` へfallbackした。
- candidate examplesに `candidate_actual_exit_event`, `candidate_actual_exit_event_minutes`, `candidate_actual_time_exit_adjusted_pnl`, `candidate_actual_time_exit_source` を残すようにした。
- mean/lower direct EV、barrier overestimate risk、fixed 2024-12 / 2025-02 smokeを確認した。
- report: `docs/reports/00083_2026-06-29_candidate_quality_barrier_target.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- candidate barrier quality 2024-12 apply: `data/reports/modeling/20260628_164936_candidate_quality_barrier_q25_720m_2024_12/`
- candidate barrier quality 2025-02 apply: `data/reports/modeling/20260628_165001_candidate_quality_barrier_q25_720m_2025_02/`
- barrier risk validation summary: `data/reports/backtests/candidate_quality_barrier_overestimate_risk_summary/20260628_165132_model_sweep_summary/`
- barrier mean direct summary: `data/reports/backtests/candidate_quality_barrier_mean_direct_summary/20260628_165417_model_sweep_summary/`
- barrier lower direct summary: `data/reports/backtests/candidate_quality_barrier_lower_direct_summary/20260628_165559_model_sweep_summary/`
- fixed smoke: `data/reports/backtests/candidate_quality_barrier_overestimate_risk_fixed/`

結果:

| item | value |
|---|---:|
| candidate count | `9091` |
| target mean | `1.5739` |
| raw bias | `20.4316` |
| mean bias | `0.9855` |
| lower bias | `-16.4275` |
| raw overestimate mean | `20.4382` |
| mean overestimate mean | `7.7639` |
| lower overestimate mean | `0.1186` |
| mean MAE | `14.5424` |
| mean R2 | `-0.1730` |
| lower coverage | `0.9925` |
| risk0 validation min pnl | `82.7176` |
| risk0.10 validation min pnl | `27.1240` |
| risk0.25 validation min pnl | `1.2864` |
| mean direct best min pnl | `-8.7380` |
| lower direct best min pnl | `-50.9794` |
| fixed 2024-12 risk0.10 | `-2.2914` |
| fixed 2025-02 risk0.10 | `-17.9024` |

判断:

- barrier targetはraw EV過大評価を強く可視化するが、現モデルの順位付け性能は足りない。
- mean direct EVは方向ミスとDDが大きく、lower direct EVは保守的すぎる。
- overestimate riskは2024-12の損失を縮める局面があるが、validation最良はrisk `0`、2025-02も削る。
- 標準採用しない。次はprediction artifactにforced PnLを残すか、exit event class、time-to-event、fixed horizon PnL、EV calibration誤差をjoint targetとして扱う。

### 2026-06-29 02:11 JST Forced prediction targets

作業:

- `prediction_frame` がforced exit target列を保存するようにした。
- 保存対象は `long_forced_raw_pnl`, `short_forced_raw_pnl`, `long_forced_adjusted_pnl`, `short_forced_adjusted_pnl`, `forced_side_score`。
- 既存prediction artifact向けに `trade_data.modeling enrich-predictions` を追加した。
- join keyは `dataset_month` + `decision_timestamp`。target値ではなく明示markerで結合成否を判定し、targetがNaNでも行一致があれば成功する。
- 既存hybrid OOF / 2024-12 / 2025-02 predictionをdataset target contextで補完した。
- enriched predictionで `oof-candidate-quality-model --target-mode barrier_event_adjusted_pnl` を再実行した。
- forced barrier overestimate riskをvalidation 4foldとfixed 2024-12 / 2025-02でsmokeした。
- report: `docs/reports/00084_2026-06-29_forced_prediction_targets.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- enriched hybrid predictions: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_forced_targets/`
- forced barrier quality 2024-12 apply: `data/reports/modeling/20260628_170650_candidate_quality_barrier_forced_q25_2024_12/`
- forced barrier quality 2025-02 apply: `data/reports/modeling/20260628_170650_candidate_quality_barrier_forced_q25_2025_02/`
- forced barrier risk validation summary: `data/reports/backtests/candidate_quality_barrier_forced_overestimate_risk_summary/20260628_170819_model_sweep_summary/`
- fixed smoke: `data/reports/backtests/candidate_quality_barrier_forced_overestimate_risk_fixed/`

結果:

| item | value |
|---|---:|
| OOF enriched rows | `115252` |
| 2024-12 enriched rows | `28763` |
| 2025-02 enriched rows | `27441` |
| forced column missing matches | `0` |
| forced target candidate count | `9091` |
| forced target mean | `1.6521` |
| forced raw bias | `20.3534` |
| forced mean bias | `0.8738` |
| forced mean R2 | `-0.1692` |
| validation risk0 min pnl | `82.7176` |
| validation risk0.10 min pnl | `27.0340` |
| validation risk0.25 min pnl | `-19.1186` |
| fixed 2024-12 risk0.10 | `0.1206` |
| fixed 2025-02 risk0.10 | `-17.3004` |

判断:

- forced PnL列のartifact gapは解消した。time exit sourceは `long_forced_adjusted_pnl` / `short_forced_adjusted_pnl` だけになり、`fixed_720m` fallbackは使われなくなった。
- target semanticsは正しくなり、OOF biasとR2はわずかに改善したが、MAEは少し悪化した。
- 実行policyではvalidation topがrisk `0` のままで、forced targetのrisk列は標準採用できない。
- 次はforced target単独ではなく、exit event class、time-to-event、fixed horizon PnL、EV calibration誤差をjointに扱うtargetへ進む。

### 2026-06-29 02:28 JST Joint exit candidate quality target

作業:

- `oof-candidate-quality-model --target-mode joint_exit_adjusted_pnl` を追加した。
- targetはtimed barrier成分、fixed horizon実現PnL、clipped best PnLを `0.7/0.2/0.1` で混合する。
- event time decay `0.25`、fixed horizon minutes `60,240,720`、component clip `min_adjusted_edge * 1.0` でsmokeした。
- mean/lower overestimate riskをvalidation 4foldで比較し、fixed 2024-12 / 2025-02でも確認した。
- report: `docs/reports/00085_2026-06-29_joint_exit_candidate_quality_target.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- joint quality 2024-12 apply: `data/reports/modeling/20260628_172218_candidate_quality_joint_exit_w721_2024_12/`
- joint quality 2025-02 apply: `data/reports/modeling/20260628_172218_candidate_quality_joint_exit_w721_2025_02/`
- mean-risk validation summary: `data/reports/backtests/candidate_quality_joint_exit_overestimate_risk_summary/20260628_172335_model_sweep_summary/`
- lower-risk validation summary: `data/reports/backtests/candidate_quality_joint_exit_lower_overestimate_risk_summary/20260628_172653_model_sweep_summary/`
- mean-risk fixed smoke: `data/reports/backtests/candidate_quality_joint_exit_overestimate_risk_fixed/`
- lower-risk fixed smoke: `data/reports/backtests/candidate_quality_joint_exit_lower_overestimate_risk_fixed/`

結果:

| item | value |
|---|---:|
| candidate count | `9091` |
| target mean | `2.3994` |
| raw bias | `19.6061` |
| mean bias | `0.6522` |
| lower bias | `-9.5179` |
| mean MAE | `10.7047` |
| mean RMSE | `11.4542` |
| mean R2 | `-0.1613` |
| lower coverage | `0.6800` |
| mean-risk validation risk0 min pnl | `82.7176` |
| mean-risk validation risk0.05 min pnl | `35.4626` |
| lower-risk validation risk0.05 min pnl | `10.8048` |
| fixed 2024-12 lower risk0.05 | `-1.6336` |
| fixed 2025-02 lower risk0.05 | `23.7418` |

判断:

- OOF回帰指標はforced barrier targetより明確に改善した。
- ただし実行policyではrisk `0` がvalidation最良のままで、risk penalty化するとfold最低PnLが下がる。
- fixed smokeでは2024-12改善と2025-02悪化が両立せず、月依存の挙動。
- 標準採用しない。joint targetはtarget familyとして残し、次はscalar penaltyではなくexit class、time-to-event、fixed horizon成分、side/regime別residualへ分解して扱う。

### 2026-06-29 02:43 JST Candidate quality component target split

作業:

- `oof-candidate-quality-model --target-mode` に `timed_barrier_component_adjusted_pnl`, `fixed_horizon_component_adjusted_pnl`, `clipped_best_adjusted_pnl` を追加した。
- 既存 `joint_exit_adjusted_pnl` はcomponent helperを再利用する形へ整理した。
- component targetの分離を `tests/test_meta_model.py` へ追加した。
- validation 4foldでcomponent別のoverestimate risk penaltyを比較した。
- report: `docs/reports/00086_2026-06-29_candidate_quality_component_targets.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- timed component OOF/apply: `data/reports/modeling/20260628_173832_candidate_quality_timed_barrier_component_2024_12/`
- fixed component OOF/apply: `data/reports/modeling/20260628_173832_candidate_quality_fixed_horizon_component_2024_12/`
- clipped component OOF/apply: `data/reports/modeling/20260628_173831_candidate_quality_clipped_best_component_2024_12/`
- timed summary: `data/reports/backtests/candidate_quality_timed_barrier_component_overestimate_risk_summary/20260628_174249_model_sweep_summary/`
- fixed summary: `data/reports/backtests/candidate_quality_fixed_horizon_component_overestimate_risk_summary/20260628_174249_model_sweep_summary/`
- clipped summary: `data/reports/backtests/candidate_quality_clipped_best_component_overestimate_risk_summary/20260628_174249_model_sweep_summary/`

結果:

| item | timed component | fixed component | clipped best |
|---|---:|---:|---:|
| candidate count | `9091` | `9091` | `9091` |
| target mean | `1.4816` | `1.2754` | `11.0714` |
| mean bias | `0.7989` | `0.2982` | `0.0182` |
| mean MAE | `12.7850` | `7.9169` | `4.9377` |
| mean RMSE | `13.5326` | `9.4811` | `5.6107` |
| mean R2 | `-0.1667` | `-0.0895` | `-0.1309` |
| no-risk validation min pnl | `82.7176` | `82.7176` | `82.7176` |
| best positive-risk validation min pnl | `62.5366` | `43.6626` | `41.7588` |

判断:

- component分解は診断として有益だが、単一のoverestimate risk penaltyへ変換するとbaselineに負ける。
- fixed horizon componentはOOF R2が相対的にましだが、実行policyではentry `15`, risk `0.05` でもmin pnl `43.6626` に落ちる。
- clipped bestはOOF MAEが小さいが、実行policyではEV過大評価を下げない。
- 標準採用しない。次はcomponentをscalar penaltyにせず、別特徴/別target/multi-output診断として扱う。

### 2026-06-29 02:57 JST Candidate quality prefixed component gates

作業:

- `oof-candidate-quality-model` に `--prediction-prefix` を追加した。
- prefixなしでは既存の `pred_candidate_quality_long_adjusted_pnl` などを維持する。
- prefixありでは `pred_candidate_quality_<prefix>_<side>_*` 列を出し、複数componentの予測を同じparquetへ共存できる。
- timed / fixed / clipped best componentを順番にOOF scoringし、final combined parquetを作った。
- component mean列を `min_trade_quality` gateとしてvalidation 4foldで比較した。
- report: `docs/reports/00087_2026-06-29_candidate_quality_prefixed_component_gates.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- timed prefixed OOF: `data/reports/modeling/20260628_175235_candidate_quality_prefixed_timed_component_oof/`
- fixed prefixed OOF: `data/reports/modeling/20260628_175302_candidate_quality_prefixed_fixed_component_oof/`
- final combined prefixed OOF: `data/reports/modeling/20260628_175327_candidate_quality_prefixed_clipped_best_oof/`
- timed gate summary: `data/reports/backtests/candidate_quality_timed_component_quality_gate_summary/20260628_175700_model_sweep_summary/`
- fixed gate summary: `data/reports/backtests/candidate_quality_fixed_component_quality_gate_summary/20260628_175700_model_sweep_summary/`
- clipped gate summary: `data/reports/backtests/candidate_quality_clipped_best_quality_gate_summary/20260628_175700_model_sweep_summary/`

結果:

| gate family | best positive gate | min pnl | sum pnl | min trades | forced exit max | EV overestimate mean |
|---|---|---:|---:|---:|---:|---:|
| baseline | no gate | `82.7176` | `406.6546` | `24` | `0.0370` | `15.5226` |
| timed component | entry `10`, rank `0.5`, quality `0` | `39.5520` | `287.2454` | `24` | `0.0357` | `16.5066` |
| fixed component | entry `12`, rank `0.5`, quality `0` | `71.1944` | `367.3486` | `21` | `0.0000` | `15.9284` |
| clipped best | entry `12`, rank `0.5`, quality `0/2/5` | `82.7176` | `406.6546` | `24` | `0.0370` | `15.5226` |
| clipped best | entry `12`, rank `0.5`, quality `8` | `82.7176` | `402.3006` | `24` | `0.0370` | `15.5758` |

判断:

- prefix付きcomponent列は採用する。componentを潰さず同じparquetへ持てるため、診断とstacking基盤として必要。
- component meanの単独quality gateは標準採用しない。
- fixed component gateはforced exitを減らすが、PnL改善へ変換できていない。
- 次はcomponent列をhard gateではなく、diagnostic/tie-break/multi-feature stackingの説明変数として使う。

### 2026-06-29 03:10 JST Candidate quality component composite

作業:

- `combine-candidate-quality-components` を追加した。
- prefixed candidate quality component列を `mean`, `min`, `max`, `weighted_mean` で合成できる。
- 出力は `pred_candidate_quality_<output_prefix>_<side>_*` なので、既存 `model-sweep` のquality columnとして使える。
- timed / fixed / clipped best componentを `mean`, `min`, `weighted_mean(0.25,0.5,0.25)` で合成し、validation 4foldで比較した。
- report: `docs/reports/00088_2026-06-29_candidate_quality_component_composite.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- composite predictions: `data/reports/modeling/20260629_candidate_quality_component_composites/`
- mean summary: `data/reports/backtests/candidate_quality_component_mean_stack_summary/20260628_180940_model_sweep_summary/`
- min summary: `data/reports/backtests/candidate_quality_component_min_stack_summary/20260628_180940_model_sweep_summary/`
- fixed weighted summary: `data/reports/backtests/candidate_quality_component_fixed_weighted_stack_summary/20260628_180940_model_sweep_summary/`

結果:

| variant | best finite gate | min pnl | sum pnl | min trades | forced exit max | EV overestimate mean |
|---|---|---:|---:|---:|---:|---:|
| baseline | no gate | `82.7176` | `406.6546` | `24` | `0.0370` | `15.5226` |
| component_mean | quality `0` | `82.7176` | `406.1976` | `24` | `0.0370` | `15.5271` |
| component_min | quality `0` | `34.5604` | `315.1544` | `18` | `0.0000` | `16.4648` |
| component_fixed_weighted | quality `0` | `82.7176` | `410.7146` | `24` | `0.0370` | `15.4567` |

判断:

- `component_fixed_weighted quality>=0` はbaselineと同じfold最低PnLを保ち、sumとEV過大評価を小さく改善した。
- 改善幅は小さく、fixed holdout未確認なので標準採用しない。
- `component_min` は絞りすぎてtrade数とPnLを壊すため採用しない。
- 次はprefixed applyを生成し、2024-12 / 2025-02と追加holdoutへ固定適用する。

### 2026-06-29 03:24 JST Candidate quality component holdout apply

作業:

- `component_fixed_weighted` のprefixed applyを2024-12 / 2025-02へ生成した。
- timed / fixed / clipped best componentを順にapply parquetへ積み増し、`combine-candidate-quality-components` で `weighted_mean(0.25,0.5,0.25)` を作った。
- validationで事前選択した `quality>=0` と、診断用の閾値 `-inf,0,2,5,8,10,12` を固定policyで比較した。
- report: `docs/reports/00089_2026-06-29_candidate_quality_component_holdout_apply.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- composite apply predictions: `data/reports/modeling/20260629_candidate_quality_component_fixed_weighted_apply/`
- no-gate fixed backtests: `data/reports/backtests/candidate_quality_component_fixed_weighted_apply_baseline/`
- quality `0` fixed backtests: `data/reports/backtests/candidate_quality_component_fixed_weighted_apply_quality0/`
- quality threshold diagnostic sweeps: `data/reports/backtests/candidate_quality_component_fixed_weighted_apply_quality_sweep/`

結果:

| scope | min quality | adjusted/min pnl | trades/min trades | note |
|---|---:|---:|---:|---|
| validation | `-inf` | `82.7176` | `24` | baseline |
| validation | `0` | `82.7176` | `24` | sumだけ小改善 |
| validation | `2` | `71.1944` | `21` | validationを悪化 |
| 2024-12 | `-inf` | `-31.7576` | `52` | baseline |
| 2024-12 | `0` | `-31.7576` | `52` | baseline同一 |
| 2024-12 | `2` | `-16.4354` | `43` | 診断上は改善 |
| 2024-12 | `5` | `29.9552` | `14` | 2024-12だけ良い |
| 2025-02 | `-inf` | `47.1824` | `126` | baseline |
| 2025-02 | `0` | `47.1824` | `126` | baseline同一 |
| 2025-02 | `2` | `62.7588` | `125` | 診断上は改善 |
| 2025-02 | `5` | `-27.1872` | `41` | 壊れる |

判断:

- `quality>=0` はholdoutで取引を落とさずbaseline同一。標準採用しない。
- `quality>=2` は2024-12/2025-02を改善したが、validationでfold最低PnLとsumを落とす。採用ではなく、次のblind holdoutでの事前登録候補にする。
- `quality>=5` はpost-hoc overfitの形なので採用しない。
- 追加holdout 2025-03は、同一HGB entry + MLP exit hybrid prediction frameが現時点で存在しない。別モデルの2025-03 predictionを流用すると比較条件が変わるため、まず同一形式のprediction生成から行う。

### 2026-06-29 03:38 JST Candidate quality component 2025-03 apply

作業:

- `xauusd_m1_p1_l1p2_policy_combined` に2025-03 datasetを生成した。
- 同一split/settingsで HGB entry/side と shared MLP exit timing を2025-03 testとして学習/推論した。
- HGB predictionへMLP exit timingをmergeし、forced PnL列を付与した。
- timed / fixed / clipped best componentをapplyへ生成し、`component_fixed_weighted = weighted_mean(0.25,0.5,0.25)` を作った。
- 2024-12 / 2025-02で診断上改善していた `quality>=2` を、事前登録候補として2025-03追加holdoutへ固定適用した。
- report: `docs/reports/00090_2026-06-29_candidate_quality_component_2025_03_apply.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- 2025-03 dataset: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/xauusd_m1_2025-03_h24_edge15.parquet`
- HGB 2025-03: `experiments/20260628_183132_policy_combined_side_exit_test_2025_03/`
- MLP 2025-03: `experiments/20260628_182929_shared_mlp_hgb_split_test_2025_03/`
- hybrid predictions: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_2025_03/`
- component apply predictions: `data/reports/modeling/20260629_candidate_quality_component_fixed_weighted_apply/predictions_component_fixed_weighted_2025_03.parquet`
- fixed holdout sweep: `data/reports/backtests/candidate_quality_component_fixed_weighted_apply_quality_sweep/20260628_183650_model_sweep_2025-03/`

結果:

| min quality | adjusted pnl | trades | forced exit rate | profit factor | direction error | note |
|---:|---:|---:|---:|---:|---:|---|
| `-inf` | `-48.6826` | `112` | `0.0089` | `0.8285` | `0.7679` | baseline |
| `0` | `-48.6826` | `112` | `0.0089` | `0.8285` | `0.7679` | baseline同一 |
| `2` | `-55.7516` | `104` | `0.0096` | `0.8107` | `0.7788` | 事前登録候補だが悪化 |
| `5` | `-45.2572` | `42` | `0.0238` | `0.6815` | `0.6667` | 2025-03単月post-hocでは小改善 |
| `8` | `0.0000` | `0` | `0.0000` | - | `0.0000` | NoTrade化 |

判断:

- `component_fixed_weighted quality>=2` は標準採用しない。2024-12/2025-02での改善が2025-03で再現しなかった。
- 2025-03はHGB side/entryが崩れており、direction error `0.7679`、short偏重、`short:asia` 損失集中が主因。
- `quality>=5` は単月post-hocで、validation/2025-02を壊すため採用しない。
- `quality>=8` 以上は月10trades条件を満たさず、実質NoTradeなので採用しない。
- 次はquality hard gateではなく、side/entry calibration、short exposure concentration、direction/session別risk検知、component列のmulti-feature stackingへ戻る。

### 2026-06-29 07:29 JST Trade exposure failure profile

作業:

- `model-trade-exposure` を追加し、複数の `model-policy` runから `config.json` の予測parquetと `trades.csv` を結合できるようにした。
- `down5,up10` のbase runを、validation 4か月と既存holdout 3か月で同じ露出軸に集計した。
- 2024-12で悪化した `long:london` / `short:asia` をblockまたはEV penaltyにする後付け診断も実施した。
- report: `docs/reports/00110_2026-06-29_trade_exposure_failure_profile.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

Artifacts:

- base exposure: `data/reports/backtests/20260628_222618_down5_up10_trade_exposure/`
- block exposure: `data/reports/backtests/20260628_222813_down5_up10_block_long_london_short_asia_exposure/`
- penalty exposure: `data/reports/backtests/20260628_222923_down5_up10_penalty_long_london_short_asia5_exposure/`
- variant split summary: `data/reports/backtests/20260629_down5_up10_local_exposure_variant_split_summary.csv`

結果:

| variant | validation sum | validation min | holdout sum | holdout min | note |
|---|---:|---:|---:|---:|---|
| base | `622.6486` | `138.0338` | `242.5008` | `-20.8252` | 現行基準 |
| block `long:london`, `short:asia` | `499.9724` | `110.9922` | `261.6722` | `-39.0314` | 2024-12を悪化 |
| penalty5 `long:london`, `short:asia` | `401.9836` | `40.1824` | `243.5110` | `13.2610` | 2024-12は救うがvalidationを壊す |

判断:

- `model-trade-exposure` は固定候補の失敗局所化に使える。
- 2024-12失敗は月全体のregime mixではなく、選択tradeのside / session / low-vol露出とEV過大評価に出る。
- 単純なsession/regime blockは、ポジション空きで別entryが入り実backtestを悪化させうる。採用しない。
- 次はhard ruleではなく、side confidence / EV calibration / exit timing targetの教師・特徴側へ戻す。

### 2026-06-29 07:37 JST Side confidence / calibrated EV recheck

作業:

- `down5,up10` 固定候補で `side_confidence_penalty=0,2,5,8,12,16` をvalidation 4か月と既存holdout 3か月で評価した。
- `min_side_confidence=0,0.55,0.6,0.65,0.7,0.75` をvalidationで評価した。
- `pred_calibrated_long_best_adjusted_pnl` / `pred_calibrated_short_best_adjusted_pnl` へ差し替えた固定候補をvalidationで評価した。
- report: `docs/reports/00111_2026-06-29_side_confidence_ev_calibration_recheck.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

結果:

| variant | validation sum | validation min | holdout sum | holdout min | 判断 |
|---|---:|---:|---:|---:|---|
| base | `622.6486` | `138.0338` | `242.5008` | `-20.8252` | 現行基準 |
| side confidence penalty `2` | `691.1634` | `151.6892` | `192.9620` | `-34.8578` | validationは良いがholdout悪化 |
| side confidence penalty `16` | `184.0738` | `-9.4830` | `68.8822` | `-17.8110` | 低頻度化。validation不適格 |
| min side confidence `0.55` | `314.7878` | `42.4602` | - | - | validationで棄却 |
| calibrated EV columns | `211.9996` | `-90.7698` | - | - | validationで棄却 |

判断:

- `side_confidence_penalty=2` はvalidationだけなら選ばれるが、holdoutでbaseより悪い。採用しない。
- global `min_side_confidence` は取引数とPnLを落としすぎる。採用しない。
- calibrated EV列の単純差し替えは2024-11を大きく壊す。採用しない。
- 次は後段のglobal補正ではなく、教師・特徴側でside不確実性と実現EV分布を直接扱う。

### 2026-06-29 16:37 JST Trade overestimate high classifier

作業:

- `oof-trade-overestimate-high-model` を追加し、selected tradeの `trade_overestimate_target_amount` がside別fit分布のq75/q90を超えるかをchronological OOFで分類した。
- q75 high probabilityを既存stateful risk5へ追加するcombined riskを作り、2025-02..2025-04で `w=0.5/1.0/2.0` を固定policy検証した。
- bestのw1.0について `model-trade-delta` を実行し、何を落として何を追加したかを確認した。
- report: `docs/reports/00152_2026-06-29_trade_overestimate_high_classifier.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

結果:

| target | AUC | target rate | predicted mean | top quartile target rate |
|---|---:|---:|---:|---:|
| q75 | `0.5509` | `0.2811` | `0.2488` | `0.3662` |
| q90 | `0.4574` | `0.1281` | `0.1070` | `0.1268` |

| label | total PnL | min month PnL | trades |
|---|---:|---:|---:|
| baseline | `154.6374` | `14.3072` | `281` |
| q75 high prob w0.5 | `94.7914` | `-12.8388` | `280` |
| q75 high prob w1.0 | `109.3234` | `-12.7308` | `279` |
| q75 high prob w2.0 | `86.1926` | `4.9996` | `273` |

判断:

- q75分類には薄いrank signalがあるが、単独risk化するとbaselineを下回る。
- q90分類は尾部検知として弱く、AUCが逆方向気味。
- deltaではw1.0が2025-02/04の良いbase tradeを落とし、一部悪いcandidate tradeを追加した。fold-local q75 thresholdと同じ失敗形。
- high-overestimate probabilityは標準riskに採用しない。使う場合はstacking feature、blocking/replacement regret、exit/holding失敗targetの補助特徴に限定する。

### 2026-06-29 16:47 JST Augmented stateful blocking examples

作業:

- `oof-stateful-value-model` / `oof-stateful-risk-model` の `--examples` を、複数CSV/ディレクトリ入力に対応した。
- 読み込んだexamplesへ `example_source` を付与し、metricsへ `example_source_rows` を保存するようにした。
- 3つのdelta sourceから1093例を作り、`positive_blocking`, `blocking_cost_high`, `replacement_regret_high`, `positive_replacement_regret_high`, `stateful_nonpositive` をchronological OOFで再評価した。
- report: `docs/reports/00153_2026-06-29_augmented_stateful_blocking_examples.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

結果:

| target | prevalence | AUC |
|---|---:|---:|
| positive_blocking | `0.0281` | `0.4751` |
| blocking_cost_high | `0.0211` | `0.5439` |
| replacement_regret_high | `0.2485` | `0.4795` |
| positive_replacement_regret_high | `0.2591` | `0.4445` |
| stateful_nonpositive | `0.4783` | `0.5070` |

| label | total PnL | min month PnL | trades |
|---|---:|---:|---:|
| baseline | `154.6374` | `14.3072` | `281` |
| aug blockcost w5 | `123.7672` | `2.6652` | `280` |
| aug blockcost w10 | `92.1764` | `2.7732` | `280` |

判断:

- 複数examples入力の実装は、追加support検証の基盤として採用。
- supportを1093例に増やしてもrank能力は大きく改善しない。
- `blocking_cost_high` はAUC `0.5439` だが、policy接続ではbaseline未満。標準riskには採用しない。
- source別target率が大きく異なるため、次は同一固定policyのwalk-forward examplesを増やし、source driftを抑えて再評価する。

### 2026-06-29 16:59 JST Fixed policy stateful examples

作業:

- `fixed_highcost_risk5` vs `fixed_highcost_risk0` の2024-11..2025-05を `model-trade-delta` で比較し、同一固定policy pair由来のstateful examplesを607件作った。
- 2024-11..2025-04のOOF predictionと2025-05 apply predictionを結合し、2025-02..2025-05をchronological OOFで再評価した。
- `oof-stateful-value-model` 側にも `read_stateful_examples()` を適用し、risk modelと同じ複数CSV/ディレクトリ入力に揃えた。
- report: `docs/reports/00154_2026-06-29_fixed_policy_stateful_examples.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

結果:

| target | prevalence | AUC |
|---|---:|---:|
| positive_blocking | `0.0881` | `0.4393` |
| blocking_cost_high | `0.0570` | `0.3563` |
| replacement_regret_high | `0.2746` | `0.4895` |
| positive_replacement_regret_high | `0.2876` | `0.4623` |
| stateful_nonpositive | `0.4819` | `0.5216` |

| label | total PnL | min month PnL | trades |
|---|---:|---:|---:|
| risk0 | `111.3582` | `-66.1420` | `408` |
| baseline risk5 | `101.6610` | `-52.9764` | `386` |
| blockcost w5 | `78.5882` | `-61.3746` | `385` |
| blockcost w10 | `35.7162` | `-56.3702` | `382` |
| nonpositive w5 | `-88.3904` | `-140.8344` | `295` |
| nonpositive w10 | `-96.3226` | `-74.7448` | `196` |

判断:

- 同一固定policyに絞っても、`blocking_cost_high` / `stateful_nonpositive` の追加riskは標準採用しない。
- `blocking_cost_high` はOOF AUCが逆方向。`stateful_nonpositive` は薄いsignalがあるが、policyでは取引を削りすぎる。
- 高コスト2025-02..2025-05ではrisk0がrisk5のtotalを上回る。risk5はmin month / max DD改善用の防御diagnosticとして扱い、利益最大化signalとは分ける。
- 次はcandidate差分targetではなく、selected trade全体のEV overestimate residual、exit timing target、context prior floorの校正へ戻る。

### 2026-06-29 18:26 JST Holding overlay 2025-08 fixed check

作業:

- 2025-08の現行schema dataset/HGB/MLP/hybrid/stateful/failure/quality/q75 apply predictionを生成した。
- `short-only q0.75 cap60` を2025-08へ再探索なしで固定適用した。
- `model-trade-delta` で悪化要因を確認し、`short/range_low_vol` の勝ちtradeを早く切りすぎる問題を特定した。
- `holding_risk_overlay.py` に `--include-combined-regimes` / `--exclude-combined-regimes` を追加し、`range_low_vol` 除外版を検証した。
- 複数月評価では各runのpredictionを `dataset_month == month` に絞るようにし、月次独立評価へ揃えた。
- report: `docs/reports/00158_2026-06-29_holding_overlay_2025_08_fixed.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

結果:

| scope | variant | total/adjusted pnl | min month | max DD | trades |
|---|---|---:|---:|---:|---:|
| 2025-08 | risk0 | `71.7412` | - | `78.6346` | `99` |
| 2025-08 | short-only q0.75 cap60 risk0 | `65.7002` | - | `78.6346` | `100` |
| 2025-08 | exclude range_low_vol risk0 | `72.4252` | - | `78.6346` | `99` |
| 2025-02..08 | no-context cap risk0 | `378.8870` | `-52.3036` | `145.4232` | `825` |
| 2025-02..08 | exclude range_low_vol risk0 | `398.2740` | `-51.3760` | `181.8916` | `801` |
| 2025-02..08 | no-context cap risk5 | `351.2370` | `-48.5396` | `146.3352` | `790` |
| 2025-02..08 | exclude range_low_vol risk5 | `364.8860` | `-43.2404` | `166.9948` | `765` |

判断:

- 単純な `short-only q0.75 cap60` は2025-08単月で悪化したため標準採用しない。
- `range_low_vol` 除外版は2025-08とtotal/min月PnLを改善するが、2025-04のDD悪化が大きい。regime hard ruleとしてはまだ不安定。
- holding capは有望な補正軸だが、次は `range_low_vol` 内でcapすべきshortと保持すべきshortを分ける教師targetを作る。

### 2026-06-29 18:36 JST Holding cap target diagnostics

作業:

- `holding_cap_target_diagnostics.py` を追加し、`model-trade-delta` のcommon tradeから `cap_value = candidate_adjusted_pnl - base_adjusted_pnl` を作るようにした。
- no-context capのrisk0/risk5全月deltaを使い、`short/range_low_vol` のdirect cap targetを抽出した。
- `holding_risk_overlay.py` に `--include-combined-session-pairs` / `--exclude-combined-session-pairs` を追加した。
- `range_low_vol:london,range_low_vol:rollover` だけcap対象から外す候補を2025-02..2025-08月次独立評価で検証した。
- report: `docs/reports/00159_2026-06-29_holding_cap_target_diagnostics.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

結果:

| scope | examples | cap value sum | beneficial rate |
|---|---:|---:|---:|
| no-context `short/range_low_vol` | `51` | `14.8088` | `0.4706` |
| after excluding london/rollover | `20` | `74.4080` | `0.6500` |

| variant | total pnl | min month pnl | max DD | trades |
|---|---:|---:|---:|---:|
| no-context cap risk0 | `378.8870` | `-52.3036` | `145.4232` | `825` |
| exclude all range_low_vol risk0 | `398.2740` | `-51.3760` | `181.8916` | `801` |
| exclude range_low_vol:london/rollover risk0 | `404.9366` | `-51.3760` | `145.4232` | `810` |
| no-context cap risk5 | `351.2370` | `-48.5396` | `146.3352` | `790` |
| exclude all range_low_vol risk5 | `364.8860` | `-43.2404` | `166.9948` | `765` |
| exclude range_low_vol:london/rollover risk5 | `360.9802` | `-43.2404` | `146.3352` | `774` |

判断:

- `range_low_vol:london/rollover` 除外は現診断セットでは最もバランスが良いが、post-hoc候補なので標準採用しない。
- direct cap targetはsupportが少ない。深層学習の直接教師にするには、prediction全行に対するdenseなholding短縮targetを作る必要がある。
- 次は未使用月への固定確認、またはdataset生成側に `cap60_vs_event_holding_delta` のようなdense targetを追加する。

### 2026-06-29 19:24 JST Holding shortening policy hook

作業:

- `holding_shortening` target-setのbeat probabilityを `model-policy` / `model-sweep` へ接続した。
- `holding_shortening_threshold` が有限のとき、`timed_ev` / `fixed_horizon_ev` のside別予測保有時間を `holding_shortening_cap_minutes` で上限化する。
- デフォルトは `holding_shortening_threshold=inf` として既存挙動を維持した。
- 2025-02の既存EV/holding predictionとshortening OOF probabilityを `decision_timestamp` で結合し、接続smokeを実施した。
- report: `docs/reports/00161_2026-06-29_holding_shortening_policy_hook.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

結果:

| variant | adjusted pnl | raw pnl | trades | profit factor | avg holding min |
|---|---:|---:|---:|---:|---:|
| disabled | `-53.5244` | `-11.1590` | `34` | `0.7894` | `600.0000` |
| threshold `0.70`, cap `60` | `-47.0418` | `-3.5890` | `36` | `0.8196` | `568.9444` |
| threshold `0.65`, cap `30` | `-44.8382` | `-0.1260` | `43` | `0.8329` | `449.5349` |

判断:

- policy hookは機能し、2025-02単月では保有短縮が損失を縮めた。
- ただしNoTrade未満であり、単月smokeなので採用しない。
- 次は複数月walk-forwardで、threshold/capをvalidation内探索、fixed holdoutでは再探索なしで確認する。

### 2026-06-29 19:32 JST Holding shortening multimonth validation

作業:

- 2025-02..2025-04のbase EV/holding predictionに、holding-shortening OOF probabilityを `decision_timestamp` で結合した。
- `holding_shortening_thresholds=inf,0.60,0.65,0.70,0.75`、`holding_shortening_cap_minutes=30,60,120` を月別sweepした。
- `model-sweep-summary` 実行時に `sweep_source` が重複追加される不具合を修正し、既存sourceを保持する回帰テストを追加した。
- report: `docs/reports/00162_2026-06-29_holding_shortening_multimonth_validation.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

結果:

| variant | 3m sum pnl | mean pnl | min month | max DD | mean trades |
|---|---:|---:|---:|---:|---:|
| disabled | `-172.4522` | `-57.4841` | `-125.9826` | `533.9704` | `43.0000` |
| threshold `0.60`, cap `60` | `-53.9566` | `-17.9855` | `-43.7620` | `461.3556` | `69.6667` |
| threshold `0.65`, cap `120` | `-119.4782` | `-39.8261` | `-96.9486` | `488.8364` | `52.0000` |

判断:

- `0.60 / 60` は3ヶ月すべてでdisabledを上回り、特に2025-04の損失を大きく縮めた。
- ただしこの3ヶ月内で探索した値なので標準採用しない。
- 次は `0.60 / 60` を固定候補として、未使用月または新規apply predictionへ再探索なしで適用する。

### 2026-06-29 19:44 JST Holding shortening fixed 2025-05

作業:

- `trade_data.modeling train --target-set holding_shortening` がEV selection列を前提に落ちる問題を修正した。
- 2023-01..2025-03でholding-shortening HGBをfitし、2025-04 valid、2025-05 test predictionを生成した。
- 2025-05 base EV/holding predictionへholding-shortening probabilityを結合した。
- `0.60 / 60` を2025-05へ再探索なしで固定適用した。
- 2025-04 validでthresholdを再校正し、valid最良 `0.50 / 60` を2025-05へ固定適用した。
- `model-trade-delta` でdisabled vs `0.50 / 60` の差分を診断した。
- report: `docs/reports/00163_2026-06-29_holding_shortening_fixed_2025_05.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

結果:

| variant | adjusted pnl | trades | profit factor | max DD | avg holding min |
|---|---:|---:|---:|---:|---:|
| disabled | `-179.2516` | `56` | `0.7793` | `269.5060` | `539.1071` |
| fixed `0.60 / 60` | `-179.2516` | `56` | `0.7793` | `269.5060` | `539.1071` |
| valid-calibrated `0.50 / 60` | `-79.7894` | `119` | `0.8952` | `212.4794` | `231.5630` |

判断:

- `0.60 / 60` は2025-05の選択tradeで発火0。raw probability thresholdはfit方式が変わると移植できない。
- `0.50 / 60` はvalid校正後に2025-05損失を大きく縮めたが、まだNoTrade未満でtrade数が増えすぎる。
- 次はcalibrated probability / validation quantile化と、`short/up_normal_vol`, `long/range_normal_vol`, `short/range_low_vol` の悪い追加tradeを抑えるentry quality gateを組み合わせる。

### 2026-06-29 19:58 JST Holding shortening quantile calibration

作業:

- `src/trade_data/quantile_calibration.py` を追加し、fit分布の経験CDFでapply predictionへquantile列を付与できるようにした。
- `scripts/experiments/holding_shortening_quantile_calibration.py` を追加し、holding-shortening probabilityをvalidation分布上の相対順位へ変換した。
- 2025-04 validでquantile thresholdを選び、2025-05へ再探索なしで固定適用した。
- q0.25のdelta診断と、validで見えるbad group blockの小診断を実施した。
- report: `docs/reports/00164_2026-06-29_holding_shortening_quantile_calibration.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

結果:

| variant | valid adjusted pnl | test adjusted pnl | test trades | test max DD |
|---|---:|---:|---:|---:|
| disabled | `-156.1574` | `-179.2516` | `56` | `269.5060` |
| raw valid-calibrated `0.50 / 60` | `-43.7680` | `-79.7894` | `119` | `212.4794` |
| quantile `0.25 / 60` | `-43.7680` | `-89.7428` | `127` | `222.6048` |
| quantile `0.25 / 60` + block `short/up_normal_vol` | `-60.0166` | `-77.1744` | `119` | `200.0362` |
| quantile `0.25 / 60` + visible-bad block | `45.2330` | `-115.9068` | `118` | `217.7606` |

判断:

- quantile化はraw probability scale差を扱う実装として残すが、今回の単月valid/testではraw校正を超えない。
- `short/up_normal_vol` blockはtestだけ見ると改善するが、valid PnL最大化では選ばれない。
- visible-bad blockはvalidだけ大幅に良く、testで悪化した。少数月deltaからregime blockを増やすのは過学習しやすい。
- 次は単月block rule追加ではなく、複数月walk-forwardでquantile thresholdを選ぶか、holding-shortening probabilityをentry quality/risk modelのfeatureへ戻す。

### 2026-06-29 20:06 JST Holding shortening multimonth quantile check

作業:

- 2025-02..04のmerged predictionを結合し、3ヶ月validation分布の経験CDFでholding-shortening quantile列を生成した。
- 2025-02..04の各月に同じmultimonth CDFを適用し、threshold/cap gridを再評価した。
- 3ヶ月validation最良 `0.75 / cap60` を2025-05へ再探索なしで固定適用した。
- 2025-05のpost-hoc gridとdelta診断も確認した。
- report: `docs/reports/00165_2026-06-29_holding_shortening_multimonth_quantile_check.md`
- 採番と最新判断は、ファイルシステムの更新時刻や `更新日時` ではなく、レポートファイル内の作成時刻 `日時` を基準にする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

結果:

| variant | validation total | fixed 2025-05 adjusted pnl | note |
|---|---:|---:|---|
| disabled | `-172.4522` | `-179.2516` | no cap |
| raw validation best `0.60 / 60` | `-53.9566` | n/a | 2025-05 chronological raw `0.60` は前回発火0 |
| single-month quantile `0.25 / 60` | n/a | `-89.7428` | 2025-04 CDF |
| multimonth quantile `0.75 / 60` | `-75.2444` | `-186.1276` | 2025-02..04 CDF |

判断:

- 複数月quantileでもraw threshold版のvalidation bestを超えず、2025-05固定ではdisabledより悪化した。
- 2025-05ではshort側のmultimonth quantile `>=0.75` が464行しかなく、OOF validation分布とchronological apply分布のズレが残る。
- holding-shortening probabilityを直接cap発火に使う方向は本流から外す。
- 次はこのprobabilityをentry/exit risk modelの補助featureに戻し、長く持つ予測の信用度やexit regret/EV過大評価の校正に使う。
