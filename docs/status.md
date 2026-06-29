# Current Status

最終更新: 2026-06-29 15:39 JST

## 現在の状態

データ取得・変換パイプラインは作成済み。

研究ドキュメント構造は作成済み。

バックテスト基盤とベースライン戦略は作成済み。

特徴量・教師ラベル生成パイプラインは作成済み。

selected trade failure modelに `pred_hit_actual_miss` と `ev_overestimate_high` targetを追加済み。2025-05 highcostでは `failure only risk10` が adjusted PnLを `-52.9764 -> -7.1330` へ改善したが、OOF validation 2024-11..2025-04ではbaseline `407.8172` に対して `325.8466` と悪化した。`stateful + predhit w1` もvalidation `240.9596` で悪化。したがって今回のrisk penaltyは標準policyへ採用せず、`pred_hit_actual_miss` はexit timing / EV calibration / ranking feature候補として残す。詳細は `docs/reports/00145_2026-06-29_pred_hit_actual_miss_failure_target.md`。

failure probabilityをtrade quality modelのoptional side featureへ接続済み。OOF quality指標ではfailure-prob feature入りがbaselineよりbias/overestimate/MAEをわずかに改善したが、RMSE/R2は改善しない。2025-05の `min_trade_quality` hard filterはbaseline quality `-92.2498`、failure-prob quality `-101.9736` と悪化したため採用しない。配線は残し、near-tie ranking / EV overestimate residual / 連続targetへ回す。詳細は `docs/reports/00146_2026-06-29_failure_probability_quality_feature.md`。

failure-prob qualityをnear-tie secondary scoreに使う検証も完了。margin 5はbaseline同一、margin 10はvalidation total `407.8172 -> 154.2024`、margin 20は `-84.8690` に悪化した。2025-04だけは改善するが2025-03/2024-11を壊すため採用しない。2025-05固定適用も行わず、次は同一side内rankingまたはEV overestimate residualの連続/分位targetへ進む。詳細は `docs/reports/00147_2026-06-29_quality_secondary_tiebreak_validation.md`。

EV overestimate residualの連続targetを実装済み。`trade_overestimate_target_amount = max(pred_taken_ev - adjusted_pnl, 0)` を月抜きOOFで学習し、2024-11..2025-04 highcost risk5 selected tradesでは R2 `0.1273`, high-overestimate AUC `0.6814`。amount全体を直接penaltyする方式はvalidationを悪化させたが、prediction分布q90超過分だけをpenaltyする `q90 w2.0` はvalidation total `407.8172 -> 460.6640`, min month `-16.9006 -> -2.3046`, max DD `224.7524 -> 204.8324` に改善。2025-05 fixed applyでも `-52.9764 -> +25.5248` に改善した。max DDは2025-05で `137.4392 -> 151.0632` と悪化するため、標準policyへ即採用せず固定候補として未使用月・trade delta診断へ進める。詳細は `docs/reports/00148_2026-06-29_trade_overestimate_amount_model.md`。

entry quality を密に学習するための追加教師targetは実装済み。主datasetの再生成、HGB再学習、quality filter付きpolicy評価まで完了。

candidate quality downside calibrationを追加済み。OOF candidate examplesからside/regime/quality bucket別にtarget mean/lower、downside probability、overestimate risk、support/sourceを出力できる。fixed componentではvalidation合計PnLを改善するrisk penalty候補が出たが、high costとholdoutの最低月が悪化したため、標準policy riskとしては採用せず、診断・ranking特徴量として残す。詳細は `docs/reports/00104_2026-06-29_candidate_quality_downside_calibration.md`。

entry timingの `wait_regret` hard gateを再検証済み。`max_wait_regret=4` はvalidationとhigh costでdrawdownを下げるがsum/min monthを落とし、`2` はvalidation 2024-11でマイナス化する。holdoutでは `2` が良く見えるが、後付けの低頻度化として扱い標準採用しない。`min_entry_rank=0.7` は現行予測スケールでは0 trade。詳細は `docs/reports/00105_2026-06-29_entry_timing_wait_regret_gate.md`。

entry timingのsupport-aware calibrationを追加済み。`entry-timing-calibration` はactual/predicted wait regretをside / regime / predicted bucket別にOOF校正し、`bad_wait_prob_risk` / `wait_excess_risk` / `wait_underestimate_risk` を出力できる。実装は診断・ranking特徴として採用するが、代表4ヶ月validationではrisk `0` が最上位で、soft penaltyはsum/min monthとEV overestimateを悪化させたため標準policyには採用しない。詳細は `docs/reports/00106_2026-06-29_entry_timing_calibration.md`。

候補選定rankingへfold-to-fold PnL安定性診断を追加済み。`model-sweep-summary` は `total_adjusted_pnl_std` を出力し、`model-candidate-selection --near-top-pnl-stability-weight` でbase/costのfold別adjusted PnL標準偏差の大きいnear-top候補を下げられる。既存base + moderate/high cost validationではweight `0/0.5/1.0` のtopは同じ `down5,up10` で、安定性は採用ルールではなく診断・tie-breakとして扱う。詳細は `docs/reports/00107_2026-06-29_pnl_stability_candidate_ranking.md`。

候補選定のleave-one-fold-out診断を追加済み。`model-candidate-selection-jackknife` は保存済みselection `config.json` を読み、各validation月を1つ抜いて候補を再選定し、抜いた月のbase/costで評価する。`00107` のw0/w1 selectionでは4fold全てholdout pass、3/4foldでfull top一致。2024-11を抜いたときだけ `down5,range5` に変わったが、抜いた2024-11でもcost min `86.0172` で通過した。詳細は `docs/reports/00108_2026-06-29_candidate_selection_jackknife.md`。

jackknife選定候補を既存holdout stressへ固定監査済み。`model-holdout-audit` はvalidation summary側の重複candidate keyをmerge前に落とすよう修正した。jackknife候補はvalidation内では通過するが、既存holdout stressでは `down5,up10` が9case中6通過で2024-12全コスト負け、`down5,range5` は6case中2通過で合計PnLも負。したがって標準policyへは昇格しない。詳細は `docs/reports/00109_2026-06-29_jackknife_holdout_gap.md`。

選択済みtrade露出の横断診断 `model-trade-exposure` を追加済み。`down5,up10` の2024-12失敗は月全体のregime mixより、選択trade上の `long:down_low_vol`, `long:up_low_vol`, `long:london`, `short:asia` とEV過大評価に出る。ただし、これらの露出はvalidationでは概ね利益寄与しており、`long:london` / `short:asia` のblockは2024-12を `-39.0314` へ悪化、penalty5は2024-12を `+13.2610` に戻すがvalidation minを `40.1824` まで壊した。採用せず、診断・教師/特徴へのフィードバックに留める。詳細は `docs/reports/00110_2026-06-29_trade_exposure_failure_profile.md`。

side confidence / calibrated EV のsoft補正を再検証済み。`side_confidence_penalty=2` はvalidation合計 `691.1634`, min `151.6892` でbaseを上回るが、holdoutではsum `192.9620`, min `-34.8578` とbaseより悪い。`min_side_confidence` はvalidationで取引数とPnLを落とし、`pred_calibrated_*_best_adjusted_pnl` への単純差し替えもvalidation min `-90.7698` で壊れる。標準policyへは採用せず、次は教師側でside不確実性と実現EV分布を直接扱う。詳細は `docs/reports/00111_2026-06-29_side_confidence_ev_calibration_recheck.md`。

side-outcome EV分布校正を追加済み。`side-outcome-calibration` はside別EV bucket、side confidence bucket、`combined_regime`, `session_regime` から、target mean/lower、no-edge確率、large-loss確率、wrong-side確率、EV過大評価riskを出力する。validation OOFでは `wrong_side_risk >= -0.45` がsum `663.4534`, min `148.1228` でraw base `622.6486` / `138.0338` を上回ったが、holdoutではraw sum `242.5008`, min `-20.8252` に対し `145.5712`, `-57.7274` と悪化した。`conservative_ev_score >= 10` もholdoutでraw未満。標準policy gateには採用せず、診断・stacking特徴量として残す。詳細は `docs/reports/00112_2026-06-29_side_outcome_evdist_calibration.md`。

side-outcome/component列をcandidate-quality二段目modelの特徴量へ追加済み。`side_outcome_stack_fixed` はOOF fixed component targetで mean R2 `0.0168`, mean bias `0.0298` と薄く前進した。validationでは `mean>=0` gateがsum `673.0854`, min `148.8660` でrawを上回るが、holdoutではmin `-20.8252 -> -18.7302`, maxDD `122.9852 -> 109.2604` と少し改善する一方、sumは `242.5008 -> 155.4990` に落ち、2025-03を `84.0776 -> -5.2898` へ壊す。標準policy gateには採用せず、ranking/tie-breakまたはrisk budget別評価の特徴として残す。詳細は `docs/reports/00113_2026-06-29_side_outcome_stacking_features.md`。

raw vs stack gateの取引差分診断 `model-trade-delta` を追加済み。`entry_decision_timestamp + direction` で `common` / `only_base` / `only_candidate` を分解し、candidate側のquality列も結合する。2025-03悪化の主因は、`only_base long` の利益 `+73.4000` を失い、`only_candidate short` `-45.9878` と `only_candidate long` `-18.8318` を追加したこと。`only_base` のquality `0-5` bucketにも `+51.0784` の利益があり、hard gateは一玉制約の経路依存で後続の良い取引を壊す。次は hard gateではなく、近接候補の優先順位、risk budget、`blocking_cost` / `replacement_regret` / `stateful_entry_value` 系教師へ進む。詳細は `docs/reports/00114_2026-06-29_side_outcome_stack_trade_delta.md`。

`model-trade-delta` にstateful blocking診断を追加済み。candidate取引の保有中に消えたbase-only取引を `blocking_pairs.csv` と `group_by_blocking_candidate_*` に出力する。2025-03では `only_candidate long` が自身 `-18.8318` に加えbase側純利益 `+51.0776` をブロックし、stateful net `-69.9094`。`only_candidate short` もstateful net `-53.1846`。品質meanは正なので、pointwise qualityは「保有中に逃す機会」を見ていない。次は `stateful_entry_value` / `stateful_positive_cost_value` をOOFで作り、hard gateではなくranking/tie-breakまたはEV補正として検証する。詳細は `docs/reports/00115_2026-06-29_stateful_blocking_diagnostics.md`。

`model-trade-delta` は `stateful_candidate_examples.csv` も出力する。候補例は `target`, `stateful_entry_value`, `stateful_positive_cost_value`, `blocking_cost`, `replacement_regret`, `side`, `decision_timestamp` などを持ち、candidate-quality-styleの学習入力として使える。2024-12/2025-03 smokeでは220例、target mean `-0.0655`、raw EV mean `18.4353`、raw bias `18.5008`。2025-03 `only_candidate long` はtarget sum `-69.9094`、blocking cost `75.3170`。次は代表validation月で同じexamplesを作り、月抜きOOFでstateful value modelを学習する。詳細は `docs/reports/00116_2026-06-29_stateful_candidate_examples.md`。

代表validation 4ヶ月でも `stateful_candidate_examples.csv` を作成済み。254例、target mean `2.4123`、raw EV mean `16.4274`、raw bias `14.0151`、`target<=0` 率 `0.3976`。stack0 policyは4ヶ月合計ではrawを上回るが、raw EVはstateful targetをまだ大きく過大評価している。次は月抜きOOFで `stateful_entry_value` modelを作り、hard gateではなくEV補正/ranking tie-breakとして検証する。詳細は `docs/reports/00117_2026-06-29_validation_stateful_candidate_examples.md`。

`oof-stateful-value-model` を追加済み。`stateful_entry_value` のvalidation OOFではraw bias `14.0151` がmean bias `0.0753` まで縮み、raw overestimate meanも `15.0311 -> 4.2816` に下がった。ただしR2は `-0.0141` で順位付け能力は弱い。stateful meanのdirect EV replacementはvalidation threshold `3.5` でsum `148.5810`, min `-0.4126` だが2024-09が0 trade、apply 3ヶ月も全月0 trade。標準policyには採用せず、raw EVとの混合・tie-break・追加examplesへ進む。詳細は `docs/reports/00118_2026-06-29_stateful_value_model.md`。

stateful overestimate riskをraw EVの線形penaltyとして検証済み。`risk_penalty=0.10/0.25/0.50/0.75` はvalidation 4ヶ月でbaseline `0` を超えず、`0.10` でもsum `622.6486 -> 571.1410`, min month `138.0338 -> 70.0596` に悪化した。apply 3ヶ月でも `0.10` は2024-12を `-20.8252 -> -10.1916` に改善する一方、2025-03を `84.0776 -> -25.6206` へ壊した。標準policyには採用せず、次は `stateful_positive_cost_value`、tie-break利用、追加examplesへ進む。詳細は `docs/reports/00119_2026-06-29_stateful_ev_blend_risk.md`。

`stateful_positive_cost_value` modelを作成済み。OOFではraw bias `14.7685` がmean bias `0.0853` へ縮むが、R2は `-0.0085`。direct replacementはvalidation bestでもsum `270.3750`, min `-64.5430` とbaseline未満。positive-cost overestimate riskもvalidation `risk=0.10` がsum `606.7320`, min `73.5066`、apply `risk=0.10` がsum `14.1920`, min `-38.4826` でbaselineを下回る。scalar penaltyには採用せず、次はprimary raw EVを維持したnear-tie専用secondary scoreを実装する。詳細は `docs/reports/00120_2026-06-29_stateful_positive_cost_value.md`。

near-tie専用secondary scoreを `model-policy` / `model-sweep` に追加済み。primary raw EVのentry判定は維持し、`secondary_score_tie_margin` 内だけ `stateful_positive_cost_value` 系scoreでsideを選び直せる。validation 4ヶ月ではbaseline `sum=622.6486`, min `138.0338` に対し、margin `10` はsum `563.7984`, min `115.1392`、margin `20` はsum `582.2844`, min `120.2830` で悪化した。実装は探索軸として残すが、今回のtie-break設定は標準policyに採用しない。詳細は `docs/reports/00121_2026-06-29_stateful_secondary_tiebreak.md`。

near-tie局所診断 `stateful-near-tie-report` を追加済み。validation examples 254件で `stateful_positive_cost_value` secondary scoreを調べると、biasはraw `14.7685` から `0.0853` へ縮むが、target Spearmanはmargin `20` で `-0.1327`。secondary top25 liftは一部正でもtop-bottom25 spreadは全marginで負、margin `20` の最高score bucketはtarget mean `-0.1244` と最悪だった。したがって同scoreをentry優先順位/risk budgetへも使わず、次は追加examplesと `blocking_cost` / `replacement_regret` の分類・下方リスクtargetへ進む。詳細は `docs/reports/00122_2026-06-29_stateful_near_tie_local_diagnostics.md`。

stateful blocking risk modelを追加済み。`positive_blocking`, `positive_replacement_regret_high`, `stateful_nonpositive` を月抜きOOF分類し、side別 `prob/risk` 列をprediction parquetへ出力できる。OOF AUCは `positive_blocking=0.4878`, `positive_replacement_regret_high=0.4869`, `stateful_nonpositive=0.4520` とrank能力は弱い。validationでは `positive_blocking risk=5` がsum/min/DDを `622.6486 / 138.0338 / 85.0166` から `675.7414 / 157.0628 / 74.7688` へ改善したが、apply 3ヶ月ではsum `242.5008 -> 198.9860`, maxDD `122.9852 -> 128.1944` に悪化。実装は採用するが標準riskにはせず、追加walk-forwardで固定評価する事前登録候補として扱う。詳細は `docs/reports/00123_2026-06-29_stateful_blocking_risk_model.md`。

`positive_blocking risk=5` を2025-04へ固定外挿した。2025-04は baseline `-503.8224`, risk `5` `-509.6742`, risk `20` `-486.2782` で、追加月ではrisk `5` が改善せず、riskを強くしても根本解決しない。apply 4ヶ月合計でも baseline sum/min/DD `-261.3216 / -503.8224 / 718.7252` に対し、risk `5` は `-310.6882 / -509.6742 / 729.0912`。`positive_blocking risk=5` は事前登録候補からも降格し、次はstateful riskではなくholding guard/fallbackを本流に戻す。詳細は `docs/reports/00124_2026-06-29_stateful_blocking_risk_2025_04_fixed_check.md`。

MLP holding guard/fallbackをvalidation/applyで再評価済み。代表validation 4ヶ月では `min_valid=-inf/30/60/120` が完全に同じで、PnL最適化の根拠にはならない。一方、apply 4ヶ月では従来挙動が2025-04で異常高回転化し、`skip min_valid=30` が base sum PnL `-261.3216 -> 246.8762`, high cost sum PnL `-1435.1746 -> 132.6970` へ改善した。`fallback` はskipより弱い。今後、MLP holdingを使う `timed_ev` 実験では `min_valid_predicted_hold_minutes=30` の fail-close skipを標準安全制約として固定する。これはvalidation edgeではなく、外挿破綻値を売買ルールへ渡さないための制約。詳細は `docs/reports/00125_2026-06-29_holding_guard_validation_apply.md` と `docs/decisions/0009_mlp_holding_fail_close_guard.md`。

MLP holding fail-close guardをCLI標準に反映済み。`model-policy` では `--min-valid-predicted-hold-minutes` を省略した場合、holding columnが `pred_mlp_*` なら `30`、それ以外なら従来通り `-inf` に解決する。`model-sweep` のdefault `auto` も同じ解決を行う。明示的に `-inf` や数値CSVを渡した場合はそちらを優先する。2025-04 smokeでは自動解決された `min_valid=30.0` で、前回の `skip min_valid=30` と同じ adjusted PnL `-18.7168`, trades `77`, max DD `249.9600` を再現した。詳細は `docs/reports/00126_2026-06-29_mlp_holding_auto_guard_cli.md`。

guard固定後のentry/side小gridを再評価済み。validationでは `entry=14`, short offset `4`, side margin `5`, `short down5/up10/range5` がbase/high cost min月を `154.4590 / 138.6648` まで上げ、現行標準の `138.0338 / 96.8776` を上回った。しかし同候補をapply 4ヶ月へ固定すると base sum/min `-42.4328 / -50.1562`, high cost sum/min `-157.7340 / -69.2394` で、現行標準guard候補の `246.8762 / -18.7168`, `132.6970 / -34.3748` を大きく下回った。したがってvalidation top候補は棄却し、entry threshold/short offset/side penaltyの追加最適化は本流にしない。詳細は `docs/reports/00127_2026-06-29_guard_fixed_entry_side_grid.md`。

guard固定後entry/side候補のtrade-level drift診断を実施済み。validation topはvalidationで `only_candidate +359.4784` が `only_base +328.6498` の喪失を上回って勝ったが、applyでは標準専用trade `+261.9228` を捨て、top専用tradeは `+19.6058` に留まった。high cost applyではtop専用tradeも `-26.6700` へ悪化。stateful target meanもvalidationでは全月プラスだが、apply baseでは2025-02/03/04が `-1.7983 / -0.1697 / -2.1726` とマイナス化した。特に2025-02 `long:up_low_vol` は自身 `-42.9714` と標準側 `+101.6036` のblockingによりstateful net `-144.5750`。結論としてvalidation topは採用せず、entry/side grid拡張ではなくOOF calibration、stateful blocking / replacement regret target、より広いwalk-forwardへ戻る。詳細は `docs/reports/00128_2026-06-29_guard_fixed_entry_side_drift_diagnostics.md`。

`model-trade-delta` は複数月run入りの親ディレクトリを直接比較できるようになった。親ディレクトリを展開し、各runの `config.json` 内 `backtest_config.evaluation_start` の月でbase/candidateを対応付ける。月の重複・不一致はfail-fastする。標準候補 vs validation top候補を親ディレクトリ指定だけで再診断し、`00128` と同じ validation delta `+62.8970 / +86.4218`, apply delta `-289.3090 / -290.4310` を再現した。今後は候補採用前にこのCLIで `only_base`, `only_candidate`, blocking group, `stateful_candidate_examples.csv` を確認する。詳細は `docs/reports/00129_2026-06-29_model_trade_delta_parent_pairing.md`。

`model-trade-delta-preflight` を追加済み。複数の `model-trade-delta` runをvalidation/holdoutに分け、case別の合計PnL delta、worst-month PnL delta、worst-month stateful targetを集計する。標準候補 vs validation top候補ではvalidation 2件がpassした一方、apply/holdout 2件は `pnl_delta_sum -289.3090 / -290.4310`, worst-month stateful target `-2.1726 / -2.4973` でfailし、preflight全体は `False`。今後の候補採用ではvalidation summaryだけでなく、このholdout preflightを反証ゲートとして使う。詳細は `docs/reports/00130_2026-06-29_model_trade_delta_preflight.md`。

`model-trade-delta-preflight` はstatus/direction/combined_regime別のgroup driftも出力する。標準候補 vs validation top候補では、通常PnLのvalidation-positive/holdout-negative groupが10件、stateful groupも10件。`only_candidate long down_low_vol` は通常PnL `+84.3218 -> -93.4838`, stateful `+107.4676 -> -136.4816`、`only_candidate short down_normal_vol` は通常PnL `+25.4090 -> -91.0014`, stateful `+25.4090 -> -228.1214` に反転した。これを直接hard blockせず、追加walk-forwardで再現性を確認してからOOF/downside/stateful targetへ戻す。詳細は `docs/reports/00131_2026-06-29_model_trade_delta_preflight_group_drift.md`。

`model-trade-delta-drift-stability` を追加済み。複数preflight runでvalidation-positive / holdout-negativeが繰り返すgroupを集計する。guard top比較とstack0比較の2つでは、通常PnLのcommon flipが3件、stateful netのcommon flipが6件。通常PnLでは `only_candidate long down_low_vol` が validation合計 `+223.8686` からholdout合計 `-159.6508`、`only_candidate short down_normal_vol` が `+52.0400 -> -101.0994`、`only_candidate short up_normal_vol` が `+49.9340 -> -36.5278` に反転した。これはhard blockではなく、regime drift / downside / stateful opportunity-cost特徴の候補として扱う。詳細は `docs/reports/00132_2026-06-29_model_trade_delta_drift_stability.md`。

`model-trade-delta-drift-stability` は共通flip groupの月別supportも出力する。guard top / stack0の実行では通常PnL support 49行、stateful support 99行。`only_candidate long down_low_vol` はguard topでvalidation 4ヶ月/holdout 3ヶ月、stack0でvalidation 3ヶ月/holdout 2ヶ月に出ており単月偶然ではない。一方validation内にも負月が混じるため、hard blockにはしない。次は `direction + combined_regime + candidate-added文脈` をOOF downside/stateful targetへ戻す。詳細は `docs/reports/00133_2026-06-29_drift_stability_monthly_support.md`。

`model-trade-delta-preflight` / `model-trade-delta-drift-stability` に、`delta_status` を落としたavailable-context driftを追加済み。これは比較後にしか分からない `only_candidate` をlive特徴として使わず、予測時点で見える `direction + combined_regime` だけで反転が残るかを見る。guard top / stack0を再実行すると、通常PnLの共通available flipは `short/down_normal_vol` 1件、statefulの共通available flipは `long/down_low_vol`, `long/up_normal_vol` 2件。ただしstateful OOF validation上では `short/down_normal_vol` target mean `+4.7383`, `long/down_low_vol` target mean `+2.1228` で、既存validation教師だけではholdout崩れを悪い文脈として学べていない。したがってavailable contextはhard ruleや単純特徴追加ではなく、追加walk-forward / stress-aware target / regime drift診断として扱う。詳細は `docs/reports/00134_2026-06-29_available_context_drift.md`。

`stateful-examples-drift` を追加済み。複数の `stateful_candidate_examples.csv` をvalidation/holdoutに分けて読み、decision-time contextごとのtarget sum/mean、downside率、raw EV過大評価、validation-positive/holdout-negative反転を出す。guard validation/highcost + stack0 validation 対 guard apply/highcost + stack0 smoke の1544例では、`candidate_side + combined_regime` で15group中6groupがmean/sumとも反転。`short/range_normal_vol` はtarget sum `+501.7660 -> -298.2216`、`long/down_low_vol` は `+358.3530 -> -234.8292`、`short/down_normal_vol` は `+303.8836 -> -19.4788`。sessionまで足すと52group中10groupが反転し、`long/up_low_vol:london` が `+254.3226 -> -284.4936`、`short/range_normal_vol:rollover` が `+125.9528 -> -227.1028`。これはhard ruleではなく、stress-aware targetと追加walk-forward評価の監査軸として使う。詳細は `docs/reports/00135_2026-06-29_stateful_examples_drift.md`。

`stateful-examples-drift` はstress-aware target監査列も出力するようになった。`context_stress_flag` はvalidation meanが正でholdout meanが負に反転したcontext、`context_stress_penalty` はそのmean低下幅、`target_context_stress_adjusted` は元targetからpenaltyを引いた値。available contextでは1544例中1083例がstress flag、target meanは `+0.6154` からstress-adjusted mean `-3.0618`。session contextでは387例がflag、stress-adjusted mean `-2.1435`。これはholdoutを使うためlive学習targetではなく、候補採用前監査と、将来のwalk-forward由来stress target設計の材料として扱う。詳細は `docs/reports/00136_2026-06-29_stateful_context_stress_target.md`。レポート採番と最新判断はファイルシステム更新時刻や `更新日時` ではなく、各レポート本文内の作成時刻 `日時` を基準にする。

`stateful-examples-walkforward-stress` を追加済み。全stateful examplesを月順に並べ、対象月より前の月だけでpseudo validation / pseudo holdout profileを作り、`walkforward_context_stress_flag`, `walkforward_context_stress_penalty`, `target_walkforward_context_stress_adjusted` を出す。available contextはsupport `20/10` で1544例中397例がflag、target mean `+0.6154` からwalk-forward stress-adjusted mean `-1.2823`。session contextはsupport `10/5` で208例がflag、stress-adjusted mean `-0.7835`。未来月を見ないため、次のstateful value model target候補として使える。詳細は `docs/reports/00137_2026-06-29_stateful_walkforward_stress_target.md`。

`oof-stateful-value-model` にchronologicalな `--oof-scheme expanding` と `--min-train-months` を追加済み。`00137` のwalk-forward targetを比較したところ、leave-one-monthではbase targetだけR2 `+0.0052` だったが、expanding OOFではbase targetもR2 `-0.0113`, bias `+1.5287` へ悪化した。available/session floor targetはMAE/RMSEを下げる一方で、expandingではR2 `-0.0945` / `-0.0498`、bias `+4.1365` / `+3.1195` と過大評価が強い。現時点ではpolicyへの直接EV replacementやhard gateには使わず、下方リスク分類、support-aware calibration、追加月でのchronological OOF診断に回す。詳細は `docs/reports/00138_2026-06-29_stateful_value_walkforward_target_comparison.md`。

`oof-stateful-risk-model` にchronological OOFとwalk-forward stress/floor分類targetを追加済み。expanding OOFではavailable `walkforward_stress_flag` AUC `0.6512`、session `walkforward_floor_lowered` AUC `0.6473` と、回帰よりはrank signalがある。ただしpredicted meanがprevalenceを大きく下回りcalibrationは弱い。6ヶ月policy接続では `session_floor_lowered risk=10` がbase最悪月 `-18.7168 -> +8.0320`、high cost最悪月 `-34.3748 -> -20.8080` を改善したが、合計PnLをbase `543.9972 -> 422.1416`、high cost `391.2374 -> 311.0372` へ削った。標準policyには採用せず、risk budget / drawdown-aware ranking / candidate selectionの補助特徴として残す。詳細は `docs/reports/00139_2026-06-29_stateful_downside_risk_policy.md`。

stateful downside riskにmean-match probability calibrationを追加済み。`session_floor_lowered` expanding OOFではpredicted mean `0.1051 -> 0.1214`、Brier `0.2181 -> 0.2129` と校正が少し改善したが、AUCは `0.6473 -> 0.6371` へ低下した。6ヶ月policy接続では `risk=5` がbase合計をほぼ維持しつつ最悪月を `-18.7168 -> +8.0868` に改善し、high costも合計 `391.2374 -> 407.8172`、最悪月 `-34.3748 -> -16.9006`、max DD `259.0392 -> 224.7524` へ改善した。candidate selectionでは `risk=5` だけが通過したが、同じ6ヶ月診断セット上で選んだため標準policyには採用せず、次の未使用月で固定確認する事前登録candidateにする。詳細は `docs/reports/00140_2026-06-29_stateful_downside_mean_match_risk_budget.md`。

`mean_match + session_floor_lowered risk=5` を2025-05へ固定適用済み。baseは `13.9990 -> 25.3104`、highcostは `-66.1420 -> -52.9764` へ改善し、防御方向の効果は残った。ただしhighcostはNoTrade未満で、`00140` のcost min基準 `>= -20` を満たさない。trade-deltaでは改善が少数の入れ替えに依存し、common tradeに `long:down_low_vol` と `short:up_normal_vol` の大きな損失が残った。標準採用せず、candidate ranking / diagnostic featureへ降格寄りに扱う。詳細は `docs/reports/00141_2026-06-29_stateful_downside_mean_match_2025_05_fixed.md`。

selected trade用の `model-trade-context-walkforward-stress` を追加済み。候補差分ではなく実際に選択されたtradeを対象に、対象月より前の月だけでcontext stressとall-prior context floorを作る。2025-05 risk=5の未解決損失では、広い文脈の `long:down_low_vol` と `short:up_normal_vol` は過去月だけのstressで捕捉できた。session分解では `long:down_low_vol:london` と `short:up_normal_vol:asia` が全過去平均でも負。一方 `short:up_normal_vol:london` は過去平均が正で、contextだけでは捕捉しにくい。これらはhard blockせず、`target_walkforward_context_stress_adjusted` と `target_walkforward_prior_context_mean_floor` をdownside分類・EV校正・ranking featureへ戻す。詳細は `docs/reports/00142_2026-06-29_selected_trade_walkforward_context.md`。

`target_walkforward_prior_context_mean_floor` をstateful downside risk targetへ戻した。`walkforward_prior_floor_nonpositive` はAUC `0.6240`, bias `-0.0741` でsignalはあるが、単独risk penaltyでは広く削りすぎる。2024-11..2025-05の7ヶ月では `prior_lowered risk=5` がbase/highcost total `491.7438 / 278.3902` で、既存 `floor_lowered risk=5` の `567.7900 / 354.8408` に負けた。単独penaltyには採用せず、EV calibration / ranking feature候補に降格する。詳細は `docs/reports/00143_2026-06-29_prior_context_floor_risk_target.md`。

selected tradeのexit/EV/confidence診断 `model-trade-exposure-diagnostics` を追加済み。2025-05 highcost risk5の残存損失は `long/down_low_vol/london` `-87.6396`, `short/up_normal_vol/asia` `-56.7420`, `short/up_normal_vol/london` `-54.5500` が中心。特に `short/up_normal_vol/london` はside gap mean `14.6367`, confidence mean `0.6674`, predicted profit-barrier hit rate `1.0000` に対しactual hit rate `0.3750` で、低confidenceではなくprofit-barrier/EV/exit timingの過大評価が主因。`min_side_confidence=0.75` は7ヶ月highcost minを `-12.2140` に縮めるが22 tradesしか残らないため標準採用しない。次は `pred_hit_actual_miss`, `ev_overestimate_vs_realized`, `exit_regret`, `holding_ratio_actual_vs_pred` をchronological OOF target/featureへ戻す。詳細は `docs/reports/00144_2026-06-29_selected_trade_exit_ev_confidence_diagnostics.md`。

初回の軽量 multi-task 学習ベンチマークは作成済み。

モデル予測を使う実行可能 backtest policy は作成済み。

複数 validation fold の `model-sweep` を集計する `model-sweep-summary` は作成済み。

トレードMLの汎化原則と現状レビューを追加済み。

short/long別のentry threshold offsetを `model-policy` / `model-sweep` に追加済み。short専用offsetは有効な調整軸だが、fixed testを見た後の候補採用は避ける方針。

no-cost/cost-aware validationを同時に評価する `model-candidate-selection` を追加済み。2025-03 blind holdoutで、選択候補がNoTradeに負ける反証が出たため、short offset単独の採用はしない。

profit barrier probability列と閾値gateを追加済み。2025-03 blindでは損失を `-49.7004` から `-29.5462` へ縮めたが、NoTradeには届かないため採用しない。

side-specific regime suppressionを追加済み。`short:session_regime=asia` は2025-03 / 2025-04 / 2025-05 blindではNoTradeを上回ったが、2025-06 blindで adjusted pnl `-100.4662`、short pnl `-101.0232`、worst direction/session `short:london` `-101.2102` と崩れた。したがって暫定採用候補から降格する。session hard blockを増やすと実質NoTradeに近づくため、次はshort exposure concentration、direction/session loss、support-aware barrier calibrationをvalidation側で扱う。

candidate selectionへ direction/session別損失集中gateを追加済み。`model-sweep` metricsに `direction_session_adjusted_pnl_min` / `worst_direction_session` を保存し、`model-candidate-selection --max-direction-session-loss-per-fold` で `short:asia` のような局所崩れを落とせる。2025-05 smokeではblockなし候補が `worst_direction_session=short:asia`, `-100.5254` で落ち、blockあり候補がeligibleに残った。

candidate selectionへ predicted/actual profit barrier miss率gateを追加済み。`model-sweep` metricsに `predicted_profit_barrier_miss_rate` / `actual_profit_barrier_miss_rate` 系の列を保存し、`model-candidate-selection --max-predicted-profit-barrier-miss-rate` / `--max-actual-profit-barrier-miss-rate` で候補を落とせる。2025-05 smokeでは、direction/session gateを緩めてもblockなし候補が `actual_profit_barrier_miss_rate_max_all=0.5000` で落ち、blockあり候補が `0.464286` でeligibleに残った。

profit barrier probability bucket別のactual hit rate診断を追加済み。`model-sweep` metricsに `profit_barrier_calibration_*` 系の列を保存し、`model-candidate-selection --max-profit-barrier-calibration-overestimate` で候補を落とせる。ただし2025-05 smokeでは、PnLが良い `short:session_regime=asia` block候補のほうが0.6-0.8 bucketの過大評価が大きかったため、このgateは当面hard採用せず診断軸として扱う。

short exposure concentrationとsupport-aware barrier gateを追加済み。`model-sweep` metricsに `long_trade_share` / `short_trade_share` / `max_side_trade_share` と Laplace-smoothed miss/calibration列を保存し、`model-candidate-selection --max-short-trade-share` / `--max-side-trade-share` / `--max-smoothed-actual-profit-barrier-miss-rate` / `--max-smoothed-profit-barrier-calibration-overestimate` で候補選定に使える。2025-06 smokeでは失敗候補が `short_trade_share=0.933333` で `short_trade_share_ok=false` になり、eligibleから落ちた。

validation 4foldで high-turnover gate比較を実施済み。前回候補周辺gridは月10trades条件を満たせなかったが、`min_entry_rank=0/0.5`, `max_wait_regret=4/inf`, `profit_barrier_threshold=0.0/0.2` を含めた high-turnover gridでは候補が残った。暫定基準は `min-trades-per-fold=10`, `max-forced-exit-rate=0.05`, `max-direction-session-loss-per-fold=60`, `max-short-trade-share=0.65`, `max-smoothed-actual-profit-barrier-miss-rate=0.55`。smoothed calibrationはhard gateにせず、diagnostic/tie-breakに留める。詳細は `docs/reports/00028_2026-06-28_high_turnover_gate_validation.md`。

固定済み候補Aを2025-07 blindで評価済み。no-costでは adjusted pnl `+1.5838` と薄く、standard cost-aware caseでは `-12.7764`, 66 trades, profit factor `0.9049` でNoTradeに負けた。short concentrationは避けたが、損失は long / `ny_overlap` / `low_vol` / `down_low_vol` に移った。候補Aは採用候補から外し、2025-07はblind failureとして扱う。詳細は `docs/reports/00029_2026-06-28_blind_2025_07_candidate_a.md`。

trade-analysis diagnostic gateを追加済み。`model-sweep` metricsに `direction_error_rate`, `predicted_side_error_rate`, `exit_regret_mean`, `ev_overestimate_vs_realized_mean` などを保存し、`model-candidate-selection --max-direction-error-rate` / `--max-exit-regret-mean` / `--max-ev-overestimate-vs-realized-mean` などで候補を落とせる。2025-07候補Aのpost-hoc smokeでは、direction error `0.5303`, exit regret mean `17.4505`, EV overestimate vs realized `15.6821` によりeligibleから落ちた。詳細は `docs/reports/00030_2026-06-28_trade_analysis_diagnostic_gates.md`。

validation 4foldのhigh-turnover gridを新diagnostic列入りで再生成し、diagnostic gateの閾値台地を確認済み。2025-07 smoke-like gate (`exit_regret_mean<=15`, `EV overestimate<=10`) はvalidation候補を0件にするためhard採用しない。`balanced` gateは候補5件を維持するが選別力は弱く、`focused` / `strict` は2件/1件に縮むため台地が弱い。現時点ではdiagnosticを主hard gateにせず、tie-breakと失敗分析に使う。詳細は `docs/reports/00031_2026-06-28_diagnostic_gate_validation.md` と `docs/decisions/0008_trade_analysis_diagnostic_gate_policy.md`。

時間別profit barrier targetを追加済み。`long_profit_barrier_hit_60m/240m/720m` と `short_profit_barrier_hit_60m/240m/720m` をdatasetに生成し、`target-set policy` / `full` のclassification targetへ追加した。主datasetを 2023-01 から 2025-07 まで再生成し、policy HGBを再学習した。240m/720m probabilityのvalidation sweepでは候補は残ったが、topはthreshold `0.0` のままで、24h probability threshold `0.2` 候補のcost-aware validationを超えなかった。現時点ではtime-limited barrierをhard gateへ昇格しない。詳細は `docs/reports/00032_2026-06-28_time_limited_profit_barrier_targets.md` と `docs/reports/00033_2026-06-28_timebarrier_validation_sweep.md`。

`fixed_horizon_ev` の固定horizon score aggregation modeを追加済み。`max/mean/median/min` をvalidation 4foldで比較したが、eligibleに残ったのは従来の `max` のみ。`mean/median/min` はshort exposureを強く落とし、ほぼlong-only化してfold最低PnLを壊した。単純な保守的horizon集約は採用せず、EV過大評価対策はOOF calibration/penaltyへ進める。詳細は `docs/reports/00034_2026-06-28_fixed_horizon_score_mode_validation.md`。

fixed horizon EV予測に対するOOF calibration基盤を追加済み。`volatility_regime,session_regime` 別補正はentry分布を壊してstrict validation候補0件になったため採用しない。global bias補正は固定horizon targetのbiasを大きく下げたが、strict gateではeligible 0件、緩和診断ではeligible 3件ながらEV overestimateはraw topとほぼ同水準だった。現時点では raw fixed horizon + `score_mode=max` を維持し、次はtrade selection後の実現PnL penalty / profit-barrier miss / hazard型exit timing targetを優先する。詳細は `docs/reports/00035_2026-06-28_fixed_horizon_oof_calibration.md`。

profit barrier hit probabilityを使った線形miss penaltyを追加済み。`profit_barrier_miss_penalty=2/4/6/8` をvalidation 4foldで試したが、delay 0 / delay 1 のcost-aware候補選定ともeligibleはpenalty `0.0` のみだった。非zero penaltyはtrade集合の実現品質を改善せず、smoothed missやEV overestimateも悪化したため採用しない。実装は探索軸として残し、標準設定は `profit_barrier_miss_penalty=0.0` を維持する。詳細は `docs/reports/00036_2026-06-28_profit_barrier_miss_penalty_sweep.md`。

selected-trade realized PnL calibration基盤を追加済み。現行基準候補のcost-aware trades 246件から、side/regime別に `pred_taken_ev -> adjusted_pnl` をOOF補正した。raw biasは `0.628560` から calibrated bias `-0.078209` へ下がったが、R2は `-0.017978`。`min_trade_quality` gateをvalidation 4foldで試すと、eligible topはgateなし `-inf` のままで、`0` 以上はcost min pnlを大きく落とした。現時点では採用しない。詳細は `docs/reports/00037_2026-06-28_selected_trade_quality_calibration.md`。

selected-trade realized PnLを小型HGBで学習するOOF基盤を追加済み。246 selected tradesで、group補正よりMAEはわずかに改善したが、bias/R2は悪く、`min_trade_quality` gateはvalidation topを改善しなかった。`0.0` gateはtop候補と同じcost min pnl `27.2158` を維持するだけで、`1.0` 以上はtrade数とfold最低PnLを削る。現時点では採用しない。詳細は `docs/reports/00038_2026-06-28_selected_trade_quality_model.md`。

exit event timing targetを追加済み。side別に `time_exit/profit_first/loss_first` とevent到達までのminutesをdatasetへ追加し、`policy` / `full` target setで学習できるようにした。軽量smokeでは `pred_long_exit_event_minutes` / `pred_short_exit_event_minutes` が保存され、既存 `timed_ev` のholding columnとしてbacktestへ接続できることを確認した。詳細は `docs/reports/00039_2026-06-28_exit_event_timing_targets.md`。

exit event holdingをvalidation 4foldで検証済み。`pred_*_exit_event_minutes` は従来 `pred_*_best_holding_minutes` よりcost min pnlの上限を `30.2476` から `75.8344` へ押し上げたが、strict `max_forced_exit_rate=0.05` ではeligible 0件。多クラスclassifierの `pred_*_exit_event_prob_<class>` 出力を追加し、profit-first class `1` をgateに使うとsmoothed missは改善した。診断として `max_forced_exit_rate=0.10` なら2候補が残るが、採用基準はまだ緩めない。詳細は `docs/reports/00040_2026-06-28_exit_event_holding_validation.md`。

predicted holding capを`model-sweep`の探索軸とcandidate keyへ追加済み。`max_predicted_hold_minutes=240,480,720,960,1200,1440` の4fold sweepでは、strict `max_forced_exit_rate=0.05` でも20候補がeligibleに復活した。topは `entry=10`, `short offset=8`, `profit-first threshold=0.4`, `max hold=720` で、cost-aware min pnl `84.7072`, min trades `32`, forced exit max `0.028571`。delay `1` 固定診断でも4fold全てプラスだが、smoothed missが最大 `0.552632` と現行gate `0.55` をわずかに超えるため、まだblind-tested candidateではない。詳細は `docs/reports/00041_2026-06-28_holding_cap_sweep.md`。

delay `1` full-gridを新しいcombined regime診断付きで再生成し、`combined_regime` / `direction:combined_regime` の最悪損益gateを追加済み。baseline support-aware selectionは13候補、topは `entry=5`, `short offset=12`, `max hold=720`, cost min pnl `58.2310`。combined gate `60/60` はeligible 0件、`60/65` は3件残り、topは `entry=5`, `short offset=20`, `max hold=480`, cost min pnl `45.4484`。ただしこのtopを2024-12 holdoutへ固定適用すると adjusted pnl `-149.7354`, profit factor `0.3820` と悪化したため、採用しない。詳細は `docs/reports/00042_2026-06-28_delay1_combined_regime_holdout.md`。

`best_side` auxiliary targetとside-confidence policy gateを追加済み。`best_side` は no-trade edge を満たすかとは独立に、long/short のどちらが相対的に有利だったかを保持する。2024-09..2024-12 smokeでは `best_side` balanced accuracy が validation `0.5464`、test `0.4797`。side-confidence gateは2024-12 testの損失を `-220.5348` から `-109.8978` へ縮めたが、NoTradeには負けるため採用せず、診断・calibration信号として扱う。詳細は `docs/reports/00043_2026-06-28_best_side_confidence_smoke.md`。

`side-confidence-report` を追加済み。予測済みparquetから `best_side` 確率のaccuracy、confidence、overconfidence、月/regime/bucket別の壊れ方を集計できる。smoke valid+testではconfidence平均 `0.5861` に対してaccuracy `0.5089`、2024-12 testではaccuracy `0.4770` / overconfidence `0.1074`。testの `range_normal_vol` と `london`、validの `down_low_vol` で過大確信が大きく、単純な `min_side_confidence` gateは危険。詳細は `docs/reports/00044_2026-06-28_side_confidence_calibration_report.md`。

`side_confidence` target setを追加し、代表4ヶ月のblocked OOF診断を実施済み。targetは `long_best_adjusted_pnl`, `short_best_adjusted_pnl`, `best_side` のみに絞る。2024-07/09/11/2025-01 OOFでは `best_side` balanced accuracy `0.5519`、confidence平均 `0.5685`、accuracy `0.5666` でglobalにはほぼ校正された。一方で `high_vol`, `down_normal_vol`, `up_normal_vol`, 2024-09, `normal_vol` では過大確信が残り、0.70-0.80 confidence bucketはaccuracy `0.3309` と危険。詳細は `docs/reports/00045_2026-06-28_side_confidence_oof_representative.md`。

regime-aware side-confidence penalty ruleを追加済み。`--side-confidence-penalty-rules` は matching regimeで `penalty * (1 - confidence)`、`--side-confidence-overfit-penalty-rules` は `penalty * confidence` をEVから引く。ただし2024-12 smokeでは prior global confidence gate `-109.8978` に対し、low-confidence rule `-222.3816`、overfit rule `-249.2666` と悪化したため採用しない。詳細は `docs/reports/00046_2026-06-28_regime_side_confidence_penalty_smoke.md`。

candidate selectionへ group-loss soft ranking penaltyを追加済み。`--group-loss-penalty-weight` は side / direction-session / combined-regime / direction-combined-regime の最悪損失深さを合算し、eligible候補の `robust_total_adjusted_pnl_min_cost` を下げて順位付けする。delay `1` 4fold smokeではtopが `entry=5, short offset=12, max hold=720` から `entry=5, short offset=20, max hold=720` へ変わり、2024-12 holdoutは `-149.7354` から `-126.0770` へ改善したがNoTradeには大きく負けた。採用ではなく診断/tie-break軸に留める。詳細は `docs/reports/00047_2026-06-28_group_loss_penalty_ranking.md`。

`profit-barrier-report` を追加済み。prediction parquet全体をlong/short縦持ちにし、profit-barrier確率のactual hit rate、overestimate、Brier scoreをsplit/月/regime/bucket別に見られる。exit-event probabilityモデルのvalid+test smokeでは全体は actual hit `0.3661` / predicted mean `0.3299` でやや過小評価だが、testの `0.4-0.6` bucketは actual hit `0.1807` / predicted mean `0.4447` で強く過大評価。threshold `0.4` gateの危険性が確認された。詳細は `docs/reports/00048_2026-06-28_profit_barrier_prediction_calibration.md`。

`profit_barrier` target setを追加し、代表4ヶ月blocked OOFでprofit-barrier確率を診断済み。OOF全体は actual hit `0.3734` / predicted mean `0.3295` で過小評価、`0.4-0.6` bucketも actual `0.4759` / predicted `0.4341` で前回testの崩れは全体再現しなかった。一方、`probability>=0.4` のshort側は actual `0.3376` / predicted `0.4545`、`probability>=0.5` はlong/shortとも約 `0.19-0.21` 過大評価。profit-barrier確率は単純なhard gateではなく、side別・bucket別・support-aware calibrationへ進める。詳細は `docs/reports/00049_2026-06-28_profit_barrier_oof_representative.md`。

`profit-barrier-calibrate` を追加済み。side別・probability bucket別の実測hit率をLaplace smoothingし、`pred_*_profit_barrier_hit_calibrated_prob` / `*_lower` / support/source列を保存できる。`--oof-column dataset_month` による月別OOF診断では、global Brierが raw `0.2272` から calibrated `0.2250` に改善し、全体biasも `-0.0439` から `-0.0027` へ縮んだ。一方、calibrated `>=0.5` は actual `0.4106` / predicted `0.5234` で過大評価、月×sideでも 2024-11 long `+0.1378`、2024-11 short `-0.1228` と不安定。校正列は診断・tie-break候補として使い、hard gate直結はしない。詳細は `docs/reports/00050_2026-06-28_profit_barrier_bucket_calibration.md`。

calibrated/lower profit-barrier列を `model-policy` / `model-sweep` に渡してvalidation比較済み。policy validの月別OOFではBrierが raw `0.2270` から calibrated `0.2191` に改善したが、valid全体fitを2024-12へ外挿すると raw `0.2310` に対して calibrated `0.2488` / lower `0.2484` と悪化。validation gridでもcalibrated/lowerは2024-11で adjusted pnl `-48.8580` になりbasic gateを満たさない。rawはvalidation上 `entry=10`, short offset `8`, threshold `0.35`, max hold `720` がbasic eligibleだが、2024-12では adjusted pnl `-184.9344` と崩れた。profit-barrier probabilityはhard gateへ昇格せず、penalty/tie-break用途へ回す。詳細は `docs/reports/00051_2026-06-28_profit_barrier_policy_column_validation.md`。

profit-barrier probabilityの線形EV penaltyをvalidation 4foldで比較済み。calibrated/lower `penalty=6`, max hold `480` はstrict validationで min pnl `52.3018`, total pnl 約 `462` と改善したが、2024-12反証月では calibrated `-212.1886`, lower `-214.3986` と崩れた。raw `penalty=8`, max hold `720` は2024-12損失を `-227.4118` から `-141.9282` へ縮めたが、NoTradeには大きく負ける。profit-barrier probability単独のhard gate/global linear penalty探索はいったん打ち切り、次はexit timing / time-exit probability / hazard-like exit policyを優先する。詳細は `docs/reports/00052_2026-06-28_profit_barrier_ev_penalty_validation.md`。

exit-event probability penaltyを追加済み。`time_exit_penalty` は `pred_*_exit_event_prob_0`、`loss_first_penalty` は `pred_*_exit_event_prob_2` を使って `EV -= penalty * probability` でentry scoreを落とす。validation 4foldでは `time=6`, `loss=6`, max hold `720` がstrict eligible、min pnl `75.1682`, total pnl `531.6246` と強かったが、2024-12反証月では adjusted pnl `-172.7944`, profit factor `0.4960` でNoTradeに大きく負けた。実装は探索軸として残すが、標準policyには昇格しない。詳細は `docs/reports/00053_2026-06-28_exit_event_probability_penalties.md`。

exit-event probabilityによるholding shrinkを追加済み。`time_exit_holding_shrink` / `loss_first_holding_shrink` は `timed_ev` / `fixed_horizon_ev` の予定保有時間に `1 - shrink * probability` をかけ、entry scoreは維持したまま予定決済を早める。validation 4fold topは `time=0.25`, `loss=0.75`, max hold `720` でstrict eligible、min pnl `55.5528`, total pnl `450.7384`。ただし2024-12反証月では adjusted pnl `-209.0802`, profit factor `0.4728` で、no-shrink `-227.4118` よりは改善したが、entry penalty top `-172.7944` に届かずNoTradeにも大きく負けた。実装は探索軸として残すが標準policyには昇格しない。詳細は `docs/reports/00054_2026-06-28_holding_shrink_validation.md`。

entry penalty + holding shrink小gridをvalidation 4foldで比較済み。`time_exit_penalty=6`, `loss_first_penalty=6`, `time_exit_holding_shrink=0.50`, max hold `720` はstrict eligibleで min pnl `85.1886` とentry penalty単独 `75.1682` を上回ったが、total pnlは `493.4848` でentry penalty単独 `531.6246` より低い。2024-12反証月では validation 2位の `time_exit_holding_shrink=0.25` が adjusted pnl `-159.0158`, profit factor `0.5211` でentry penalty単独 `-172.7944` より改善したが、NoTradeには大きく負ける。標準policyには昇格しない。詳細は `docs/reports/00055_2026-06-28_entry_penalty_holding_shrink_combo.md`。

dynamic / hazard-like exit thresholdを追加済み。保有中に現在sideの `time_exit` / `loss_first` probabilityを再評価し、`time_exit_exit_threshold` / `loss_first_exit_threshold` 以上なら途中決済signalへ切り替える。validation 4foldでは `penalty=6/6`, `time_exit_holding_shrink=0.25`, `time_exit_exit_threshold=0.90`, `loss_first_exit_threshold=0.75`, max hold `720` がbasic eligibleで min pnl `81.1178`, total pnl `528.8282`。`actual_profit_barrier_miss_rate_smoothed` 基準のstrict候補は残るが、`predicted_profit_barrier_miss_rate_smoothed` は `0.928571` と高い。2024-12反証月では adjusted pnl `-162.9304` でNoTradeに大きく負け、no-dynamic combo `-159.0158` よりわずかに悪い。標準policyには昇格しない。詳細は `docs/reports/00056_2026-06-28_dynamic_exit_probability.md`。

combined side-confidence / miss controlを検証済み。現行dataset生成コードで `best_side` とexit-event/profit-barrier targetsを同居させた `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/` を生成し、`experiments/20260628_101740_policy_combined_side_exit_p1_l1p2/` を学習した。best_side confidenceはoverall accuracy `0.4750`, balanced accuracy `0.4856`, confidence mean `0.5404` と弱い。joint sweepではvalidation topは前回同様 `penalty=6/6 + time_shrink=0.25` で、side-confidenceやprofit-barrier miss penaltyを足さない候補。`min_side_confidence=0.55` は2024-12を `-91.9786` まで改善したが、validation min pnlは `65.0410` に下がり、NoTradeにも届かない。標準policyには昇格しない。詳細は `docs/reports/00057_2026-06-28_combined_side_miss_joint.md`。

side-confidence専用学習とtarget-aware weightingを検証済み。`target-set side_confidence` の `month_label` 学習はpolicy combined内の `best_side` と完全に同じoverall accuracy `0.4750`, balanced accuracy `0.4856` になった。現行HGBはtargetごとに独立fitなので、multi-task crowdingは主因ではない。新規 `--sample-weighting month_target` はoverall balanced accuracyを `0.4896`、overconfidenceを `0.0605` へ少し改善したが、policy予測のside confidenceだけを差し替えたvalidation 4foldでは `min_side_confidence=0.55` が min pnl `-15.2120`, total pnl `178.8212` まで悪化した。2024-12は `-88.1826` とわずかに改善したが、validation優先で採用しない。詳細は `docs/reports/00058_2026-06-28_side_confidence_target_weighting.md`。

candidate selectionへ複合diagnostic soft penaltyを追加済み。direction error、actual profit barrier miss、EV overestimateが閾値を超えた分をpenalty化し、eligible候補の `robust_total_adjusted_pnl_min_cost` を下げて順位付けできる。`combined_side_miss_joint` 4foldではtopがholding shrink `0.25` からno-shrink entry penalty候補へ変わったが、2024-12反証月では adjusted pnl `-172.7944` とprior holding shrink combo `-159.0158` より悪化した。インフラはtie-break/診断として残すが、今回のrankingは標準policyへ昇格しない。詳細は `docs/reports/00059_2026-06-28_diagnostic_soft_penalty_ranking.md`。

shared representation検証の入口として `train-shared-mlp` を追加済み。scikit-learn `MLPRegressor` をmulti-output regressionとして使い、policy regression targetsを1つのモデルで同時学習する。極小smokeではartifact生成と `timed_ev` 接続は成功したが、2024-12 executable backtestは adjusted pnl `-88.1778`, 689 trades, profit factor `0.8632` で、取引過多・long偏り・コスト負けが出た。これは接続確認であり採用実験ではない。詳細は `docs/reports/00060_2026-06-28_shared_mlp_regression_smoke.md`。

shared MLP用のblocked OOF CLI `oof-shared-mlp` を追加済み。2ヶ月smokeでは `predictions_oof.parquet` を生成し、各holdout月の `timed_ev` backtestへ接続できた。2024-07 adjusted pnl `+47.3170`, 562 trades、2024-09 adjusted pnl `+32.6390`, 985 trades。ただしsample 2%、max_iter 2で未収束かつ取引過多・side偏りがあるため、採用判断には使わない。詳細は `docs/reports/00061_2026-06-28_shared_mlp_blocked_oof.md`。

shared MLP代表4fold pilotを実施済み。exit timing targetは `R2 ~= 0.34` と相対的に学習できたが、best adjusted pnlやside scoreはR2が負で、固定 `timed_ev` は4fold合計 adjusted pnl `-1.8770`、2024-11 `-171.2478` と不安定。strict candidate selectionは `eligible=0`。片側偏りを `max_side_trade_share=1.0` まで緩めると4候補が残るが、これは実運用候補ではなく、低頻度・片側寄りに逃げた診断結果として扱う。詳細は `docs/reports/00062_2026-06-28_shared_mlp_4fold_pilot.md`。

HGB entry/side + MLP exit timing hybridを検証済み。validationではHGB holding baseのtop min pnl `78.4344` / sum `369.5736` に対し、MLP holding hybridは min pnl `81.5352` / sum `396.9782` へ小幅改善した。しかし2024-12固定testではhybrid top + MLP holdingでも adjusted pnl `-54.6032`、direction error `0.6327`、EV over realized `23.0714` でNoTradeに負けた。MLP exit timingは補助信号として残すが、標準policyへ昇格しない。詳細は `docs/reports/00063_2026-06-28_hgb_mlp_exit_hybrid.md`。

group-loss / diagnostic reselectionを実施済み。soft penaltyはhybrid topを変えず、group gate60は validation eligible を11件まで絞ったが、2024-12固定testでは MLP holding `-97.6568`、HGB holding `-69.0240` と悪化した。posthocに `long:session_regime=ny_late` をblockすると2024-12は `-5.4938` まで縮むが、これは後付け診断であり採用証拠ではない。次は `long:ny_late` / `long:range_low_vol` をvalidation gridの事前候補として入れ、2024-12を見ずに再選定する。詳細は `docs/reports/00064_2026-06-28_group_loss_gate_posthoc_failure.md`。

`model-sweep` に `--side-block-rule-sets` / `--side-extra-margin-rule-sets` を追加し、long側risk-controlをvalidation gridで事前評価できるようにした。単一policy sweepではprediction parquetをpreloadするが、欠損行dropは候補ごとの必須列で評価直前に行う。local gridではruleなしhybrid topが引き続き1位で、`long:ny_late` blockはmin pnl `79.7192` / `78.0572` で2-3位に残った。2024-12固定testでは `long:ny_late` block + `min_entry_rank=0.5` が adjusted pnl `-5.4938` まで改善したがNoTradeには届かない。`long:range_low_vol` 系は `-141.5698` / `-144.2494` と悪化したため棄却する。詳細は `docs/reports/00065_2026-06-28_long_rule_validation_grid.md`。

candidate selectionへ near-top risk rankingを追加済み。`--candidate-rank-mode near_top_risk` はbest eligible cost min PnLから許容劣化幅内の候補だけをrisk proxyで並べ替える。直近long rule gridでは、複合risk scoreだとruleなしが引き続きtopで、`long:ny_late` はgroup loss、EV overestimate、exit regret、side concentrationが悪化するため選ばれなかった。drawdown-onlyの極端な感度では `long:ny_late` を選べるが、max DD改善は `1.1256` と小さく、sum pnl / group loss / EVを悪化させるため標準基準にしない。詳細は `docs/reports/00066_2026-06-28_near_top_risk_selection.md`。

side/regime EV penaltyを追加済み。`--side-ev-penalty-rules` は `side:column=value+...:penalty` 形式で、side選択前にmatching sideのEVを直接減点する。HGB entry/side + MLP exit hybridのlocal gridでは `long:session_regime=ny_late:15` がvalidation min pnlをruleなし `81.5352` から `93.8904` へ上げた。near-top riskでは同じ減点15 + `min_entry_rank=0.5` がtopになり、2024-12反証月はruleなし `-54.6032` に対して `-5.4938` まで改善した。2024-12 cost stressでも高コスト条件のbaseline `-76.3910` に対してrisk top `-26.0816` まで損失を縮めた。2025-02追加固定testではbaseline `+81.8334`, risk top `+79.4018` と両方プラスで、高コスト + delay 1でもbaseline `+21.3628`, risk top `+19.5898`。ただし2025-02ではbaselineがrisk topをわずかに上回るため、side EV penaltyは標準policyへ昇格しない。詳細は `docs/reports/00067_2026-06-28_side_regime_ev_penalty.md`, `docs/reports/00068_2026-06-28_side_ev_penalty_cost_stress.md`, `docs/reports/00069_2026-06-28_side_ev_penalty_2025_02_holdout.md`。

`short:combined_regime=up_low_vol` のside EV penaltyを検証済み。short shareは下がるが、validation最悪月PnLが `long:ny_late:15` 単独の `93.8904` からcombo `69.8078` / `63.6080` へ落ち、short-onlyは `50.2796` まで悪化した。固定testでもcomboは2024-12 `-77.3720` / `-79.1486`、2025-02 `+28.5478` / `+64.0924` で、既存baselineや `long:ny_late` risk topを上回らない。したがって直接減点は採用しない。詳細は `docs/reports/00070_2026-06-28_short_up_low_vol_ev_penalty.md`。

複数holdout同時監査 `model-holdout-audit` を追加済み。`model-policy` / `model-cost-sensitivity` artifactの `config.json` から候補keyを復元し、validation summaryとmergeしてholdout月・cost caseを同時に監査できる。直近のside EV penalty候補群では、validation上eligibleでも、2024-12/2025-02標準holdoutとcost stressの両方で `audit_eligible=True` は0件。`long:ny_late:15` risk topが相対最良だが、標準holdout min pnl `-5.4938`、cost stress min pnl `-26.0816` でNoTradeを安定して超えない。詳細は `docs/reports/00071_2026-06-28_multi_holdout_candidate_audit.md`。

support-aware lower EV calibration列を追加済み。`pred_regime_calibrated_*_best_adjusted_pnl_lower` はgroup supportに応じたconservative marginをcalibrated EVから差し引く。validation OOFのselected-side品質は改善したが、executable validationでは `lower_z=0.5` が2024-11を壊し、4fold min adjusted pnl `-127.7796` / `-134.5254` でeligible 0件。fixed holdoutでも2025-02は `+135.2708` / `+106.2222` と強い一方、2024-12は `-101.7542` / `-133.4082` で悪化。標準採用しない。詳細は `docs/reports/00072_2026-06-28_support_aware_lower_ev_calibration.md`。

regime residual penalty列を追加済み。`pred_regime_residual_penalized_*_best_adjusted_pnl` はside平均より過大評価が大きいregimeだけEVを減点する。`session_regime`, weight `10` はvalidation 4foldでeligible、min adjusted pnl `85.7296` / `81.0356` だったが、fixed holdoutでは2024-12が `-156.1742` / `-159.1944` と大幅悪化。`volatility_regime,session_regime`, weight `10` も2024-12 `-166.4110` / `-159.6254` で弱い。row-level residualは実行売買の壊れる方向を十分に表さないため標準採用しない。詳細は `docs/reports/00073_2026-06-28_regime_residual_penalty.md`。

candidate-entry residual penaltyを追加済み。`candidate_entry_only=true` では、side別entry threshold offset、side margin、entry local rankを通った候補行だけで residual overestimate をfitする。`session_regime`, weight `1`, rank `0.5` は2024-12 fixed holdoutを raw hybrid baseline `-54.6032` から `-17.1780` へ改善したが、validation 4fold min adjusted pnlは `50.5324` で既存baseline `81.5352` や `long:ny_late:15` risk top `85.7834` より弱い。2025-02も baseline `+81.8334` に対し `+78.0748`。標準採用せず、selected trade realized residual / side failureの診断基盤として残す。詳細は `docs/reports/00074_2026-06-28_candidate_entry_residual_penalty.md`。

selected-trade quality calibrationを直近hybrid top policyへ再適用済み。実行trade 106件のOOFでは raw bias `15.8005` が calibrated bias `-0.4206`、raw overestimate mean `17.3736` が `5.8545` へ改善した。しかし `min_trade_quality` gateはvalidation topを改善せず、`min_trade_quality=4` は2024-12を `-4.6296` まで縮める一方で2025-02を `+8.5648` へ削りすぎた。標準採用せず、次はhard gateではなく校正EV置換、soft overestimate penalty、または実行trade failure classifierへ進む。詳細は `docs/reports/00075_2026-06-28_selected_trade_quality_hybrid_gate.md`。

selected-trade qualityの校正済み値をentry EVへ直接置換してvalidation 4foldを再評価済み。strict eligible候補は0件で、最良near-missでも validation min adjusted pnl `-4.1156`, sum `36.1418`, min trades `5` と、直前hybrid基準の min `81.5352`, sum `396.9782`, min trades `23` を大きく下回った。fixed holdoutも2024-12 `-24.2766`, 2025-02 `-41.1456` と両方NoTradeに負けた。校正済みqualityの全面置換は標準採用せず、次は過大評価soft penaltyまたはtrade failure classifierへ進む。詳細は `docs/reports/00076_2026-06-28_selected_trade_quality_ev_replacement.md`。

selected-trade qualityから `raw EV - calibrated quality` の過大評価幅を作り、既存 `risk_penalty` で部分的にEVから引くsoft penaltyを検証済み。`add_trade_quality_columns` は `pred_trade_quality_*_overestimate` と `*_overestimate_risk` を出力する。validation 4foldでは `risk_penalty=0.25` が min pnl `86.9174`, sum `442.9766` で直前hybrid基準を上回ったが、fixed holdout 2024-12で `-128.2556` と崩れ、`risk=0.10` / `0.50` も2024-12で `-222.7318` / `-77.5040`。標準採用せず、次は実行trade failure分類targetへ進む。詳細は `docs/reports/00077_2026-06-28_selected_trade_quality_overestimate_soft_penalty.md`。

実行trade failure classifier基盤を追加済み。`oof-trade-failure-model` は `large_loss`, `wrong_side`, `profit_barrier_miss`, `exit_regret_high`, `any_failure` のside別probabilityと `risk=-probability` を出力する。OOFでは `large_loss` だけAUC `0.5736` と薄く使え、validation 4fold full sweepで `entry=12`, `short offset=6`, `side margin=5`, `risk_penalty=10`, `min_entry_rank=0.5` が min pnl `92.8530`, sum `402.2514`。fixed 2024-12は baseline `-54.6032` から `-37.2928` へ改善したがNoTrade未満、2025-02は baseline `+81.8334` から `+76.9254` へ少し悪化。標準採用は保留し、次は `large_loss` threshold/校正/使い方を改善する。詳細は `docs/reports/00078_2026-06-28_trade_failure_classifier_risk.md`。

`large_loss` threshold `5/10/15` を比較済み。OOF AUCは `5=0.4042`, `10=0.5736`, `15=0.5665`。validation 4fold topの最悪月PnLは `5=88.8168`, `10=92.8530`, `15=87.4970` で `10` が最良。fixed holdoutでは `5` が2024-12 `+22.3498` だが2025-02 `-19.6600`、`10` は2024-12 `-37.2928` / 2025-02 `+76.9254`、`15` は2024-12 `-55.4970` / 2025-02 `+21.5216`。threshold調整だけでは標準採用に足りないため、`threshold=10` を基準信号として side/regime別校正またはcandidate-entry集合拡張へ進む。詳細は `docs/reports/00079_2026-06-29_large_loss_threshold_comparison.md`。

trade failure probabilityのside/regime別OOF校正CLIを追加済み。`oof-trade-failure-calibration` は `pred_trade_failure_<target>_<side>_calibrated_prob/risk` と support-aware `upper_prob/risk` を出力する。`large_loss threshold=10` で試したところ、OOF AUCは `volatility_regime+session_regime` が raw `0.5736` から `0.5837` へ少し上がったが、実行policyでは改善しなかった。`combined_regime` full grid topはrisk `0` に戻り min pnl `82.7176` でraw t10 top `92.8530` 未満。`vol+session calibrated risk=30` はvalidation sumを上げるがmin pnl `62.7122`、fixed 2024-12 `-159.2242` と大きく崩れた。標準採用せず、次はcandidate-entry集合へfailure targetを広げる。詳細は `docs/reports/00080_2026-06-29_trade_failure_probability_calibration.md`。

candidate-entry failure modelを追加済み。`oof-candidate-failure-model` はentry候補行をside別に展開し、`large_adverse = max_adverse_pnl <= -10` をOOF分類して `pred_candidate_failure_<target>_<side>_prob/risk` を出力する。学習例はselected trades 106件からcandidate `9091` 件へ増えたが、OOF AUCは `0.3738` と逆相関気味。通常riskはvalidation min pnlをriskなし `82.7176` からrisk10 `5.9462` へ壊し、反転riskでもrisk5 `39.9032` でriskなしを超えない。fixed holdoutではrisk10が2024-12 `+19.2252` へ改善する一方、2025-02 `-18.6000` へ悪化。標準採用せず、次はcandidate rowの連続期待値・下方分位・exit timing込みtargetを検討する。詳細は `docs/reports/00081_2026-06-29_candidate_entry_failure_model.md`。

candidate-entry quality quantile modelを追加済み。`oof-candidate-quality-model` はentry候補行のside別実現可能PnLを平均回帰と下方分位回帰で学習し、`pred_candidate_quality_*_adjusted_pnl` / `*_lower_adjusted_pnl` / `*_overestimate_risk` を出力する。candidate `9091` 件のOOFでは平均モデル `R2=-0.0509`、lower coverage `0.6845`。mean/lowerをEVへ直接使うとvalidation min pnlは `-190.2562` / `-152.8084` へ崩れ、lower overestimate riskも最良はrisk `0` のまま。fixed holdoutではrisk `0.5` が2024-12を `-4.8092` へ縮める一方、2025-02を `-45.8502` へ壊す。標準採用せず、quality列は診断・calibration補助に残す。詳細は `docs/reports/00082_2026-06-29_candidate_entry_quality_quantile.md`。

candidate-entry qualityにbarrier event targetを追加済み。`oof-candidate-quality-model --target-mode barrier_event_adjusted_pnl` はprofit firstを `+15`、loss firstを `-15`、time exitをforced PnLまたは `fixed_720m_adjusted_pnl` fallbackで学習する。candidate `9091` 件のOOFではtarget mean `1.5739`、raw bias `20.4316`、mean bias `0.9855`、mean `R2=-0.1730`、lower coverage `0.9925`。overestimate riskはvalidation最良がrisk `0` のままで、risk `0.10` はmin pnl `82.7176` から `27.1240` へ悪化。fixed 2024-12はrisk `0.10` で `-2.2914` まで改善するが、2025-02を `-17.9024` へ壊す。標準採用せず、exit timing込みtargetの診断軸として残す。詳細は `docs/reports/00083_2026-06-29_candidate_quality_barrier_target.md`。

prediction artifactのforced PnL欠落を修正済み。`prediction_frame` は `long_forced_raw_pnl`, `short_forced_raw_pnl`, `long_forced_adjusted_pnl`, `short_forced_adjusted_pnl`, `forced_side_score` を保存する。既存artifact向けに `trade_data.modeling enrich-predictions` を追加し、datasetの `dataset_month` + `decision_timestamp` でtarget contextをjoinできる。enriched hybrid OOFは `115252` 行でforced列欠損0。forced列でbarrier targetを再実行するとtime exit sourceは `long/short_forced_adjusted_pnl` だけになりfallbackは解消したが、validation topはrisk `0` のまま。標準採用せず、target semantics修正として扱う。詳細は `docs/reports/00084_2026-06-29_forced_prediction_targets.md`。

candidate-entry qualityにjoint exit targetを追加済み。`oof-candidate-quality-model --target-mode joint_exit_adjusted_pnl` はtimed barrier成分、fixed horizon実現PnL、clipped best PnLを混合する。candidate `9091` 件のOOFではforced barrier targetよりmean MAEが `14.6941` から `10.7047`、mean RMSEが `15.5222` から `11.4542` へ改善した。ただし実行policyではvalidation topがrisk `0` のままで、mean/lower overestimate riskはforced barrier riskを超えない。fixed smokeでも2024-12と2025-02の改善が両立しないため標準採用しない。詳細は `docs/reports/00085_2026-06-29_joint_exit_candidate_quality_target.md`。

candidate-entry qualityのjoint成分を個別targetへ分解済み。`timed_barrier_component_adjusted_pnl`, `fixed_horizon_component_adjusted_pnl`, `clipped_best_adjusted_pnl` を追加し、component別のOOF回帰とvalidation 4fold risk penaltyを比較した。OOFではfixed horizon componentが最もましなR2 `-0.0895`、clipped bestが最小MAE `4.9377` だが、実行policyでは全targetのvalidation topが `risk_penalty=0` のまま。best positive-risk候補でもfold最低PnLはtimed `62.5366`, fixed `43.6626`, clipped `41.7588` でbaseline `82.7176` を下回る。component分解は診断として残すが、scalar risk penaltyとして標準採用しない。詳細は `docs/reports/00086_2026-06-29_candidate_quality_component_targets.md`。

candidate-entry quality出力に `--prediction-prefix` を追加済み。timed/fixed/clipped component列を同じprediction parquetへ共存できる。prefix列を使い、各component meanを `min_trade_quality` gateとしてvalidation 4foldで試したが、baseline `min pnl=82.7176`, `sum=406.6546` を超えない。fixed component gate `quality>=0` はforced exit maxを `0` にできるが、min pnl `71.1944`、sum `367.3486` で標準採用不可。prefix列は診断・multi-feature stacking基盤として残す。詳細は `docs/reports/00087_2026-06-29_candidate_quality_prefixed_component_gates.md`。

prefixed candidate quality componentを合成する `combine-candidate-quality-components` を追加済み。`mean`, `min`, fixed成分重視 `weighted_mean(0.25,0.5,0.25)` をvalidation 4foldで試した。`component_fixed_weighted quality>=0` はbaselineと同じfold最低PnL `82.7176` を保ち、sum `406.6546 -> 410.7146`、EV overestimate mean `15.5226 -> 15.4567` と小改善。ただし改善幅は小さく、fixed holdout未適用のため標準採用はしない。tie-break候補として残し、次はprefixed applyを作って複数holdoutで確認する。詳細は `docs/reports/00088_2026-06-29_candidate_quality_component_composite.md`。

`component_fixed_weighted` のprefixed applyを2024-12/2025-02へ生成して固定適用済み。事前選択候補 `quality>=0` は両holdoutでbaselineと完全に同じになり、filterとして働かなかったため標準採用しない。診断上は `quality>=2` が2024-12 `-31.7576 -> -16.4354`, 2025-02 `47.1824 -> 62.7588` と改善したが、validationでは min pnl `82.7176 -> 71.1944`, sum `410.7146 -> 363.5200` に悪化する。`quality>=5` は2024-12だけ良く、validation/2025-02を壊すpost-hoc overfit。次は同一HGB+MLP+forced形式の2025-03以降predictionを生成して、`quality>=2` を事前登録候補として確認する。詳細は `docs/reports/00089_2026-06-29_candidate_quality_component_holdout_apply.md`。

2025-03へ同一HGB entry + MLP exit + forced target frameを生成し、`component_fixed_weighted quality>=2` を追加holdoutで確認済み。baseline/quality `0` は adjusted pnl `-48.6826`, 112 trades、事前登録候補 `quality>=2` は `-55.7516`, 104 tradesへ悪化した。`quality>=5` は2025-03単月では `-45.2572` へ小改善するが、validationと2025-02を壊すためpost-hoc採用しない。`quality>=8` 以上は取引ゼロでNoTrade化し、月10trades条件を満たさない。`component_fixed_weighted` hard gateは標準採用せず、今後は診断特徴またはmulti-feature stacking入力として扱う。詳細は `docs/reports/00090_2026-06-29_candidate_quality_component_2025_03_apply.md`。

2025-03のshort偏重と `short:asia` 損失集中を受けて、side-confidence gate、side-confidence penalty、short combined-regime side EV penalty、entry tightening、cost stressを確認済み。side-confidence hard/soft gateはvalidationを壊したため採用しない。`short:combined_regime=down_low_vol:5,short:combined_regime=up_low_vol:15,short:combined_regime=range_low_vol:10` はzero-cost固定holdout 2024-12/2025-02/2025-03を全てプラスにしたが、2024-12はmoderate costで `-22.8348`、high costで `-53.7684` へ落ちるため標準採用しない。`entry=16` tighteningも2024-12/2025-02をzero-cost時点で壊した。今後はcost-aware validationを選定基準に組み込み、side EV penalty探索を広げすぎずmulti-feature stacking/rankingへ進む。詳細は `docs/reports/00091_2026-06-29_short_lowvol_side_ev_penalty_cost_stress.md`。

short low-vol rule set gridをmoderate cost validationでも再評価し、既存 `model-candidate-selection` でbase/cost両方を満たす候補を選定済み。strict selection topは `short:combined_regime=down_low_vol:5,short:combined_regime=up_low_vol:10,short:combined_regime=range_low_vol:5` で、validation base min `138.3706`, cost min `121.9972`。しかし固定holdout cost stressでは2024-12 no-cost `-0.0572`, moderate cost `-11.7670`、2025-03 high cost `-15.6634` と崩れた。cost-aware selectionは前進だが、標準採用には未達。次はrule set探索を広げず、stress-aware drawdown、月別下振れ、局所direction/session損失、EV overestimateを同時にrankingへ入れる。詳細は `docs/reports/00092_2026-06-29_cost_aware_lowvol_selection_holdout.md`。

high cost validation (`spread=0.2`, `slippage=0.1`, `delay=1`) を追加し、base + moderate + high costを同時に満たすcandidate selectionを実施済み。`model-candidate-selection` は `--min-base-folds` / `--min-cost-folds` を追加し、base/no-cost 4foldとcost scenario 8foldを別々に要求できる。explicit selection topは `down5,up10,range5` で validation cost min `107.1572` だが、固定holdout stressではmin pnl `-32.4176`、high cost合計 `-31.6628`、max drawdown `181.6922` へ悪化した。`down10,up10,range10` はholdout全scenario合計とdrawdownのバランスが相対的に良く、現行rankingでは拾えていない。標準採用候補はまだない。詳細は `docs/reports/00093_2026-06-29_highstress_cost_selection_failure.md`。

stress-aware rankingとして `model-candidate-selection --candidate-rank-mode stress_score` を追加済み。既存 `near_top_risk_score` にvalidation cost/base scenario合計PnL rewardを加える。`model-holdout-audit` も `model-sweep` の `metrics.csv` gridを読めるようにした。base 4fold + moderate/high cost 8foldのstress score topは `down5,up10` だが、既存holdout stressでは min pnl `-57.7402`, sum `473.2982`。全候補が9 holdout cases全通過には届かず、標準採用候補はまだない。次は2025-04以降へ同一形式predictionを生成し、未使用holdoutで確認する。詳細は `docs/reports/00094_2026-06-29_stress_score_ranking_audit.md`。

2025-04へ同一形式の dataset/HGB/MLP/forced target/component predictionを生成し、未使用holdoutで stress score topを確認済み。MLP exit minutesは2025-04で外挿破綻し、中央値が long `-163.75`, short `-145.39`、1分未満率が約65%になった。MLP holding本線ではbestでも base `-475.6374`, high `-1442.3792`、stress top `down5,up10` は base `-503.8224`, high `-1503.3702`。HGB holding fallbackでは高回転は止まるがbest/strict `down5,up10,range5` でも base `-157.1394`, high `-167.4006`。標準採用不可。次は exit minutes の unconstrained regression をやめ、log/bin/hazard targetとfail-close guardを入れる。詳細は `docs/reports/00095_2026-06-29_2025_04_stress_score_holdout.md`。

`timed_ev` に raw holding predictionのfail-close/fallback guardを追加済み。`min_valid_predicted_hold_minutes` を有限値にすると、raw holdingが非finiteまたは閾値未満のsideはentry不可になる。fallback列を指定した場合だけ、primary holding無効時にfallback holdingへ差し替える。2025-04 strict top診断では、HGB fallbackが base `-170.7302`, high `-182.3386`、fail-close skipが base `-111.2648`, high `-129.9124` まで損失を縮めた。ただしNoTradeには届かないため、guardは採用シグナルではなく破綻抑制の安全装置として扱う。詳細は `docs/reports/00096_2026-06-29_timed_ev_holding_guard.md`。

exit event minutesのlog targetを追加済み。`long_exit_event_log_minutes` / `short_exit_event_log_minutes` を学習し、予測時に `pred_long_exit_event_minutes_from_log` / `pred_short_exit_event_minutes_from_log` として `0..1440` 分へ戻す。小型MLP smokeではlog targetのR2は負でモデル候補にはならないが、raw minutes回帰の負値・異常大値をpolicy holdingへ直結しない配線は確認できた。2025-04 backtest smokeは base `-28.4370`, high cost `-57.1444` でNoTrade未満。詳細は `docs/reports/00097_2026-06-29_log_exit_event_minutes_target.md`。

exit time-bin classifier由来のholding派生列を追加済み。`pred_*_exit_event_time_bin_minutes` はclass labelをbin上限分へ、`pred_*_exit_event_time_bin_expected_minutes` はclass probabilityの期待分へ変換する。小型HGB smokeでは2025-04のtime-bin分類balanced accuracyがlong `0.2765`, short `0.2439` と弱くモデル候補にはしないが、time-bin expected holdingを `timed_ev` に渡す配線は確認できた。詳細は `docs/reports/00098_2026-06-29_exit_time_bin_holding_columns.md`。

既存predictionへexit holding派生列を後付けする `derive-exit-holding-columns` を追加済み。代表4ヶ月validation (`2024-07`, `2024-09`, `2024-11`, `2025-01`) でholding sourceを比較したところ、base/high costとも `bin_expected cap=480` が最上位だった。base min pnl `145.5682`, high cost min pnl `120.5842`。ただし `raw_event cap=480` との差は小さく、log-derived holdingは既存artifactにlog予測がないため未比較。詳細は `docs/reports/00099_2026-06-29_exit_holding_multifold_comparison.md`。

`bin_expected cap=480` を固定holdout stressへ適用済み。2024-12 / 2025-02 / 2025-03 / 2025-04の4ヶ月では、base groupが min pnl `-223.7292`, sum pnl `-116.0564`、high cost groupが min pnl `-200.9822`, sum pnl `-186.3262`。比較対象の `raw_event cap=480` はbase min `-157.1394`, high cost min `-167.4006` で、holdoutでは `bin_expected` を上回った。2025-04の損失は `short:range_normal_vol`, `short:up_normal_vol`, `long:range_normal_vol`, `rollover`, `ny_late` に集中。`bin_expected` は標準昇格せず、次はnormal-vol/time-session riskをvalidation側で事前登録して検証する。詳細は `docs/reports/00100_2026-06-29_exit_holding_holdout_stress.md`。

normal-vol / time-session risk ruleを代表4ヶ月validationで検証済み。`model-candidate-selection` のカテゴリplateau列バグを修正し、`side_ev_penalty_rules` をplateau columnにしても落ちないようにした。normal-vol short直接減点 (`short_norm5/10`) はhigh cost最低月がマイナスへ落ち、台地なし。`time5` はhigh cost min pnlを `120.5842 -> 125.4900` に小改善したが、base/cost sumを削るため標準昇格しない。`long_range5` も診断候補止まり。詳細は `docs/reports/00101_2026-06-29_normal_time_risk_validation.md`。

candidate-entry failure targetをsession/regime別に拡張済み。`large_loss`, `wrong_side`, `range_normal_vol_selected_failure`, `normal_vol_selected_failure`, `time_session_selected_failure`, `any_failure` を `oof-candidate-failure-model` へ追加した。CLI defaultは互換性維持のため従来通り `large_adverse` のまま。validation OOFでは `normal_vol_selected_failure` がAUC `0.6418` と薄く使えそうに見え、policy接続でもbase/high cost validationを小改善したが、2024-12 / 2025-02 / 2025-03 / 2025-04 holdout baseではrisk `20` が全月で悪化し、sum pnl `-105.0100 -> -183.7474`, max DD `474.6194 -> 516.4888`。標準採用しない。詳細は `docs/reports/00102_2026-06-29_candidate_failure_regime_session_targets.md`。

candidate quality downside drift診断を追加済み。`trade_data.meta_model candidate-quality-report` は `validation_oof_candidate_quality_examples.csv` を読み、月・side・regime・prediction bucket別にtarget分布、bias、overestimate、lower coverage、downside prevalenceを出す。timed/fixed/clipped componentを診断した結果、fixed componentがoverallでは最も現実的だが、2024-11のlower coverage `0.6125`, `target<=-15` `0.1151`、bucket上位 `q09/q10` のmean overestimate `6.5076` / `6.3060` が悪い。quality scoreは単調なrankとして使えないため、global hard gateやscalar risk直結は採用しない。次はfixed component中心にmonth/regime/bucket別のsupport-aware calibrated downside featureへ進む。詳細は `docs/reports/00103_2026-06-29_candidate_quality_downside_drift_report.md`。

`docs/reports` の実験レポートは、`00001_YYYY-MM-DD_slug.md` の通し番号形式へ統一済み。番号はファイルシステムの更新時刻(mtime)や本文の `更新日時` ではなく、レポートファイル内の `日時: YYYY-MM-DD HH:MM JST` の昇順で決める。既存レポートの確認、再採番、直近レポート参照でも、ファイルシステムのmtimeではなくファイル内の `日時` を正とする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。通し番号はその順序に由来する補助情報として扱う。各レポート冒頭には `日時` と `更新日時` を `YYYY-MM-DD HH:MM JST` 形式で置く。

利用可能なデータ:

- M1: `data/processed/histdata/xauusd/xauusd_m1.parquet`
- M5: `data/processed/histdata/xauusd/xauusd_m5.parquet`
- Tick sample: `data/processed/histdata/xauusd/tick/year=2025/month=01/HISTDATA_COM_ASCII_XAUUSD_T_202501.parquet`
- Dataset edge1: `data/processed/datasets/xauusd_m1/xauusd_m1_2025-01_h24_edge1.parquet`
- Dataset edge15: `data/processed/datasets/xauusd_m1/xauusd_m1_2025-01_h24_edge15.parquet`
- Multi-month Dataset edge15: `data/processed/datasets/xauusd_m1/xauusd_m1_2023-01_h24_edge15.parquet` から `data/processed/datasets/xauusd_m1/xauusd_m1_2025-12_h24_edge15.parquet`

確認済み内容:

- M1 は 2009-03-15 22:00 UTC から 2026-06-01 04:58 UTC まで。
- M1 は 6,025,170 行。
- M5 は 1,214,607 行。
- Tick sample は 2025 年 1 月で 5,798,226 行。
- 検証時点で、重複 timestamp、NULL、OHLC 不整合、Bid/Ask 逆転は検出されていない。

## 次の作業

直近更新: EV overestimate residualの連続targetは有効なrank signalを持つ。amount全体の直接penaltyは不採用だが、validation OOF prediction分布のq90超過分だけをpenaltyする `q90 w2.0` はvalidationと2025-05 applyの両方で改善した。次はこの候補を固定し、未使用月・chronological validation・trade deltaで過適合を確認する。

1. `q90 w2.0` を固定候補として、未使用月または対象月より前だけでfitするchronological foldへ適用する。q90 thresholdとlambdaは追加月を見て再調整しない。
2. baseline stateful risk5 vs `q90 w2.0` を `model-trade-delta` で比較し、only_candidate / only_base / blocking / regime別の改善源を確認する。
3. q90 thresholdをvalidation OOF prediction分布で固定する方式と、fit側selected-trade target分位で固定する方式を比較する。apply月の分布を見てthresholdを決めない。
4. MLP holdingを使う `timed_ev` 実験ではCLI defaultのauto guardにより `min_valid_predicted_hold_minutes=30` の fail-close skipを標準安全制約にする。従来のclip-only挙動を再現する場合だけ明示的に `--min-valid-predicted-hold-minutes -inf` を渡す。
5. selected-trade qualityのgroup平均gateと小型HGB gateは標準採用しない。診断基盤として残す。
6. holding cap付きexit-event candidateは、2024-12 holdout失敗を反証として扱い、現状では標準評価へ昇格しない。
7. combined regime gateはhard採用ではなく、candidate tie-break / failure analysisとして使う。
8. exit-event datasetとlog exit minutes targetを複数foldへ拡張し、候補固定後に複数blind月へ適用する。
9. side/entry calibrationを直接扱う。`best_side`, profit barrier miss, EV overestimateを教師信号またはcalibration targetにする。profit barrierは全体平均ではなくside別・bucket別actual hit rateとsupportを必ず確認する。
10. exit-event probability penalty、holding shrink単独、両者の小grid、dynamic / hazard-like exit threshold、side-confidence hard/min gateはいずれも標準採用しない。探索軸として残す。
11. exit timingの複数fold比較では `bin_expected cap=480` がvalidation暫定最上位だったが、固定holdout stressで2025-04が大きく崩れたため標準昇格しない。normal-vol / rollover / ny_late risk ruleのvalidationでは、normal-vol short直接減点は台地なし、`time5` と `long_range5` は診断候補止まり。session/regime別の選択失敗targetもvalidation小改善後にholdoutで悪化したため、分類probability直結は採用しない。candidate quality drift診断ではfixed componentが最も現実的だが、月別・bucket別の過大評価が強い。entry timing calibrationも単独soft penaltyではvalidationを改善しなかったため、次はこれらをglobal hard gateではなくstacking/ranking特徴として統合する。log-derived比較用にはdataset/train artifactを再生成する。
12. `target-set side_confidence` との同一月比較は完了。専用化だけでは改善せず、`month_target` もvalidationを壊したため、side-confidence hard/min gate探索は止めてOOF calibration/diagnosticへ戻す。
13. side-confidence penalty tuningは、calibration改善後にviable candidate上で試す。NoTradeに大きく負ける候補をside confidenceだけで救う方向には寄せない。shared representationを持つMLP/TCNを試す場合は、HGBのtarget独立fitでは得られない表現共有が本当に効くかを検証点にする。
14. diagnostic gate、group-loss penalty、diagnostic soft penaltyは、validation候補を全滅させない範囲でtie-breakとして使う。2025-07 smoke-likeの厳しい閾値や単月post-hocのpenalty採用は使わない。diagnostic soft penaltyの今回topは2024-12で悪化したため、標準policyへ昇格しない。
15. profit-barrier probability単独のhard gate/global linear penalty探索は打ち切る。今後はdirection/sessionやcombined regimeのrisk penaltyと同時に扱う場合だけ再評価する。
16. 次はside/entry calibrationとprofit-barrier missの同時制御へ戻る。exit timingだけで負け月を救う方向には寄せすぎない。
17. `oof-shared-mlp` の代表validation 4foldは完了。exit timing signalはあるが、EV/side予測が弱く、strict横断候補は0件だったため標準policyへ昇格しない。
18. HGB entry/side + MLP exit timing hybridは、validationでは小幅改善したが2024-12でNoTradeに負けたため標準採用しない。
19. group-loss hard gate / soft penaltyは、2024-12の `long:ny_late` failureを事前に止められなかったため標準採用しない。
20. `long:range_low_vol` hard block / extra marginは2024-12で大きく悪化したため棄却する。
21. near-top risk rankingは実装済み。複合riskでは `long:ny_late` を採用せず、drawdown-only採用は脆いため標準基準にしない。
22. `long:ny_late:15` side EV penalty risk topは2024-12を防御し、2025-02でも非破綻だったが、2025-02ではbaselineを上回らない。標準採用は保留する。
23. `short:up_low_vol` の直接side EV penaltyはvalidation最悪月と2024-12固定testを壊すため採用しない。short偏重riskはpost-hocなgroup減点ではなく、support-aware target、side/regime別calibrated EV、複数holdout同時rankingで扱う。
24. `model-holdout-audit` による2ヶ月同時監査では現候補が全滅した。次はside EV penalty探索を広げず、entry/side EV calibrationとsupport-aware realized-PnL targetへ戻る。
25. support-aware lower EVは、OOF selected-side品質を改善しても executable validationを壊した。次はEV全体を一律に下げず、side/regime別calibration residual targetやregime-conditioned side confidenceで「壊れる方向」を学習する。
26. row-level residual penaltyはvalidation OOFのselected avgを上げても、fixed holdoutで2024-12を大きく悪化させた。次は全rowの教師ではなく、entry条件通過候補または実行tradeに限定した residual/failure target を作る。
27. candidate-entry residual penaltyは2024-12を一部改善したが、validation robustnessが弱く標準採用しない。次は候補行のgroup平均ではなく、1玉制約で実際に選ばれたtradeの realized residual / side failure / exit regret をOOFまたはwalk-forwardで学習する。
28. selected-trade qualityのgroup平均下限gateは、過大評価の平均補正には効くが、未来月で良いtradeも落とす。hard gateは採用しない。
29. selected-trade qualityの校正済み値をentry EVへ全面置換すると、validationとfixed holdoutの両方を壊した。次は全面置換ではなく、`pred_taken_ev - calibrated_quality` の過大評価soft penalty、またはtrade failure分類targetとして使う。
30. selected-trade qualityの過大評価soft penaltyはvalidation上だけ改善し、fixed 2024-12で既存baselineより悪化した。過大評価幅の回帰的penaltyはいったん止め、`large_loss`, `wrong_side`, `profit_barrier_miss`, `exit_regret_high` などの実行trade failure分類targetへ進む。
31. trade failure classifierでは `large_loss` だけが薄く有効。validation min pnlと2024-12固定testは改善したが、NoTradeを超えず、2025-02を少し削る。標準採用は保留し、次は `large_loss` threshold、side/regime別校正、candidate-entry集合への拡張を試す。
32. `large_loss` threshold比較では `10` がOOF/validation/2ヶ月合計で最も筋がよいが、2024-12はまだNoTrade未満。thresholdだけの最適化は止め、`threshold=10` のprobabilityをside/regime別に校正するか、candidate-entry集合へ学習対象を広げる。
33. side/regime別failure probability校正は、OOF AUCを少し改善しても実行policyを改善しなかった。実行trade 106件のgroup校正は不安定なので、次はcandidate-entry集合へfailure targetを広げて学習量を増やす。
34. candidate-entry qualityの平均/下方分位は、直接EV置換でもsoft riskでもvalidationを改善しなかった。
35. barrier event targetはraw EV過大評価の診断には有効だが、mean/lower/risk policyはいずれも標準採用できない。
36. forced PnL列はprediction artifactへ残せるようになった。forced target単独のriskは標準採用しない。
37. joint exit targetはOOF回帰指標を改善したが、単一scalar risk penaltyとしては実行policyを改善しない。
38. joint成分をtimed barrier、fixed horizon、clipped bestへ分解しても、scalar risk penaltyではvalidation baselineを超えない。次はcomponentを潰さず、exit class、time-to-event、fixed horizon成分、side/regime別residualを別々の特徴またはmulti-output診断として扱う。
39. component meanを単独quality gateとして使ってもbaselineを超えない。prefix付きcomponent列は残し、今後はhard gateではなく、diagnostic/tie-break/multi-feature stackingの入力として扱う。
40. deterministic component ensembleでは `component_fixed_weighted quality>=0` だけがbaselineを小幅改善した。ただしfold最低PnLは同じで、fixed holdout未確認。標準採用せず、tie-break候補として複数holdoutへ進める。
41. `component_fixed_weighted quality>=0` はfixed holdoutで取引を落とさずbaseline同一。`quality>=2` は2024-12/2025-02を改善するがvalidationを悪化させ、2025-03追加holdoutでも `-48.6826 -> -55.7516` に悪化したため採用しない。
42. 2025-03ではHGB entry/sideが崩れ、short偏重と `short:asia` 損失集中が出ている。次はquality hard gateを深掘りせず、side/entry calibration、short exposure concentration、direction/session別risk検知、またはcandidate quality componentをmulti-feature stackingで扱う。
43. side-confidence hard/soft gateは標準採用しない。short low-vol side EV comboはzero-costでは有望だが、cost stressで脆いため標準採用しない。
44. 次はzero-costだけでなくmoderate costのvalidation min pnlを同時に満たす選定基準を使う。entry thresholdを単純に上げる方向はholdoutで悪化したため、本流から外す。
45. cost-aware validation selection topも固定holdout cost stressで未達。次はrule set数を増やすのではなく、stress-aware drawdownと月別下振れを候補rankingへ組み込む。
46. high-stress validation selectionでも固定holdout stressへ外挿できなかった。holdout結果を直接最適化せず、validation fold内で cost scenario合計、drawdown max、group損失、EV overestimateを含むstress-aware rankingを定義し、未使用holdout月で確認する。
47. `stress_score` rankingは実装済みだが、既存holdout stressでは全候補に負けcaseが残る。既存holdoutに合わせたweight調整はpost-hocになるため、次は2025-04以降の `xauusd_m1_p1_l1p2_policy_combined` datasetと同一HGB+MLP+component predictionを生成して未使用holdoutで確認する。
48. 2025-04未使用holdoutでは、MLP exit minutesが負方向へ外挿破綻して高回転化した。HGB holding fallbackでもNoTradeに負けるため、exit timing targetとentry/side EVの両方に月外汎化問題がある。
49. `timed_ev` holding guard、log exit minutes target、time-bin由来holding列は実装済み。既存4foldでは `bin_expected cap=480` がbase/high costで最上位だったが、固定holdoutでは `raw_event cap=480` より悪く、2025-04でNoTradeに大きく負けた。log-derivedは未比較なので、log対応artifact再生成は別途行う。
50. `model-candidate-selection` のplateau supportは、数値列だけでなくカテゴリrule set列にも対応済み。文字列plateauは同一カテゴリのeligible supportを数える。現時点では `side_ev_penalty_rules` のカテゴリplateauを採用条件には使わず、候補比較の互換修正として扱う。
51. candidate-entry failure targetは `large_adverse` 以外にも拡張済み。ただし `normal_vol_selected_failure` riskはholdoutで悪化し、`wrong_side` / `time_session_selected_failure` はOOFで逆相関寄り。分類targetをentry scoreへ直接penalty接続する方向は標準採用せず、診断特徴として残す。
52. candidate quality drift診断では、fixed componentがtimed/clippedよりdownside targetとして現実的。ただし上位prediction bucketほど過大評価が強く、2024-11/2025-01でdownside prevalenceが上がる。quality scoreは単調rankではなく、support-aware calibrated downside featureとして扱う。
53. guard固定後のentry/side小gridでも、validation top (`entry=14`, short offset `4`, `range_low_vol` 追加penalty) はapplyへ外挿せず現行標準を大きく下回った。今後はentry threshold/side penaltyのパラメータ探索を増やさず、OOF校正・downside feature・regime drift診断へ戻る。
54. stateful value target比較は、leave-one-monthではなくchronologicalな `--oof-scheme expanding` を標準診断にする。floor targetは直接EV回帰として使わず、下方リスク分類やsupport-aware calibrationへ変換して試す。
55. walk-forward floor分類targetのうち `session_floor_lowered` は防御signalとして有望だが、単独risk penaltyは合計PnLを削りすぎる。標準policyに固定せず、drawdown-aware candidate rankingかcalibrated risk budgetへ回す。
56. `mean_match + session_floor_lowered risk=5` は6ヶ月診断ではbase/high costの最悪月とdrawdownを改善したが、同じ期間で選抜した候補である。これ以上この6ヶ月で細かく調整せず、未使用月へ固定適用して反証する。
57. 2025-05固定では `risk=5` がbase/highcostを改善したが、highcostはNoTrade未満で事前基準に届かない。直接policy採用は止め、残ったcommon trade損失をwalk-forward downside/context targetへ戻す。

## 未決定事項

- M1 バックテストの約定価格を、次足 open にするか、より保守的な Bid/Ask 推定にするか。
- Tick を全期間取得するか、研究対象月の周辺だけ取得するか。
- 1 か月最適化の評価月を、固定月にするかランダム抽出にするか。
- エントリー/決済を独立モデルにするか、1 つの policy model にするか。
- 現行の profit 1.0 / loss 1.20 に加えて、明示的なスプレッドコストを標準評価へ入れるか。

## 直近の推奨作業

2026-06-29 15:39 JST 更新: `trade_overestimate_target_amount = max(pred_taken_ev - adjusted_pnl, 0)` のOOFモデルを追加した。highcost risk5 2024-11..2025-04では R2 `0.1273`, high-overestimate AUC `0.6814`。amount全体の直接penaltyはvalidationを悪化させたが、validation OOF prediction分布のq90超過分だけを使う `q90 w2.0` はvalidation total `407.8172 -> 460.6640`, min month `-16.9006 -> -2.3046`, max DD `224.7524 -> 204.8324` に改善し、2025-05 fixed applyも `-52.9764 -> +25.5248` に改善した。max DDは2025-05で悪化するため即標準採用ではなく、固定候補として未使用月・chronological validation・trade delta診断へ進める。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の作成時刻 `日時` を基準にする。

2026-06-29 15:17 JST 更新: failure-prob quality scoreをnear-tie secondary scoreへ使った。margin 5はbaseline同一、margin 10はvalidation total `407.8172 -> 154.2024`、margin 20は `-84.8690` に悪化。margin 10は2025-04を改善するが2025-03を `27.1660 -> -156.0008` へ壊し、margin 20は2024-11を `129.9968 -> -212.8968` へ壊した。採用せず、2025-05固定適用もしない。次はEV overestimate residualの連続/分位targetへ進む。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の作成時刻 `日時` を基準にする。

2026-06-29 15:09 JST 更新: failure probabilityをtrade quality modelのoptional side featureへ接続した。OOF qualityではfailure-prob feature入りが calibrated bias `0.2061`, overestimate mean `4.4255`, MAE `8.6450` で、baseline qualityの `0.2806`, `4.4680`, `8.6555` より微改善。ただしRMSE/R2は改善せず、2025-05 policyでは `min_trade_quality=0.5` がbaseline quality `-92.2498`, failure-prob quality `-101.9736` と悪化した。quality hard filterには採用せず、near-tie ranking / EV overestimate residual / 連続targetへ回す。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の作成時刻 `日時` を基準にする。

2026-06-29 14:58 JST 更新: `pred_hit_actual_miss` / `ev_overestimate_high` をselected trade failure targetへ追加した。`pred_hit_actual_miss` はOOF AUC `0.9626` だが、profit-barrier予測列を条件にするためAUCは過大評価しない。2025-05 highcostでは `failure only risk10` が `-52.9764 -> -7.1330` に改善した一方、OOF validation 2024-11..2025-04ではbaseline `407.8172` に対して `325.8466` と悪化し、`stateful + predhit w1` も `240.9596` に悪化した。標準policyには採用せず、exit timing / EV calibration / ranking featureとして使う。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の作成時刻 `日時` を基準にする。

2026-06-29 12:36 JST 更新: `mean_match + session_floor_lowered risk=5` を2025-05へ固定適用した。baseは `13.9990 -> 25.3104`、highcostは `-66.1420 -> -52.9764` に改善し、防御signalとしては一部再現した。ただしhighcostはNoTrade未満で、事前のcost min基準 `>= -20` を満たさない。trade-deltaでは改善が少数の入れ替えに依存し、common `long:down_low_vol` / `short:up_normal_vol` 損失が残る。標準採用せず、diagnostic/ranking featureへ降格寄りに扱う。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の作成時刻 `日時` を基準にする。

2026-06-29 12:23 JST 更新: stateful downside riskにmean-match probability calibrationを追加した。`session_floor_lowered` のBrier/biasは少し改善し、6ヶ月policy接続では `risk=5` がbase最悪月を `-18.7168 -> +8.0868`、high cost最悪月を `-34.3748 -> -16.9006`、high cost max DDを `259.0392 -> 224.7524` に改善した。candidate selectionでも `risk=5` だけが通過したが、同じ6ヶ月診断セットで選んでいるため標準採用せず、次の未使用月で固定確認する。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の作成時刻 `日時` を基準にする。

2026-06-29 12:11 JST 更新: walk-forward stress/floor targetを下方リスク分類に変換し、stateful risk modelでexpanding OOF評価した。`session_floor_lowered` はAUC `0.6473` で、policy接続でもrisk `10` がbase/high costの最悪月を改善したが、合計PnLを大きく削るため標準採用しない。次は直接penaltyではなく、drawdown-aware ranking、risk budget、calibration改善、追加月再現性確認へ回す。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の作成時刻 `日時` を基準にする。

2026-06-29 11:56 JST 更新: `oof-stateful-value-model` にchronologicalなexpanding OOFを追加し、walk-forward stress/floor targetを比較した。expandingではbase targetのR2も `-0.0113` に落ち、available/session floorはMAE/RMSEを下げるがR2とbiasが悪化する。policyへの直接EV置換やhard gateには使わず、下方リスク分類、support-aware calibration、追加月でのchronological OOF診断へ回す。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の作成時刻 `日時` を基準にする。

2026-06-29 10:23 JST 更新: guard固定後にentry threshold / short offset / side margin / short low-vol penaltyの小gridをvalidationで再選定した。validation topは `entry=14`, short offset `4`, `down5/up10/range5` でbase/high cost min月 `154.4590 / 138.6648` と強いが、apply 4ヶ月ではbase sum/min `-42.4328 / -50.1562`, high cost sum/min `-157.7340 / -69.2394` に崩れ、現行標準guard候補を下回った。標準採用しない。次はパラメータ探索ではなく、OOF校正・downside feature・regime driftの扱いへ戻る。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の作成時刻 `日時` を基準にする。

2026-06-29 10:13 JST 更新: MLP holding fail-close guardをCLI標準に反映した。`model-policy` では `--min-valid-predicted-hold-minutes` 省略時、holding columnが `pred_mlp_*` なら `30`、それ以外なら `-inf` に解決する。`model-sweep` defaultの `auto` も同じ。2025-04 smokeではconfig上 `min_valid=30.0` を確認し、前回の `skip min_valid=30` と同じ adjusted PnL `-18.7168`, trades `77`, max DD `249.9600` を再現した。今後の代表候補再評価は、このguard固定後にentry/side EV calibrationとexit timing targetへ戻る。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の作成時刻 `日時` を基準にする。

2026-06-29 06:17 JST 更新: `candidate-quality-report` を追加し、timed/fixed/clipped componentのOOF examplesを月・regime・bucket別に診断した。fixed componentはoverallで mean bias `0.2982`, mean MAE `7.9169`, lower coverage `0.7055` と最も現実的だが、2024-11は lower coverage `0.6125`, `target<=-15` `0.1151`、prediction bucket `q09/q10` はmean overestimate `6.5076` / `6.3060` と過大評価が強い。global quality gateやscalar risk直結は採用しない。次はfixed component中心にmonth/regime/bucket別のsupport-aware calibrated downside featureをOOFで作り、policy適用前にvalidation/holdout反証する。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の `日時` を基準にする。

2026-06-29 06:04 JST 更新: candidate-entry failure targetをsession/regime別に拡張した。`normal_vol_selected_failure` はvalidation OOF AUC `0.6418`、validation policyでもhigh cost min pnl `120.5842 -> 124.4280` へ小改善したが、2024-12/2025-02/2025-03/2025-04 holdout baseではrisk `20` が全月で悪化し、sum pnl `-105.0100 -> -183.7474`、max DD `474.6194 -> 516.4888`。標準採用しない。次は分類probability直結ではなく、candidate rowの連続的なrealizable PnL / lower quantile / calibrated downsideへ進む。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の `日時` を基準にする。

2026-06-29 05:48 JST 更新: normal-vol / time-session risk ruleをvalidation 4foldで確認した。normal-vol short直接減点はhigh cost最低月がマイナスへ落ちるため採用しない。`time5` はhigh cost min pnlを `120.5842 -> 125.4900` に小改善したが、base/cost sumを削るため標準昇格しない。`long_range5` も診断候補止まり。次はruleを増やすより、session/regime別の選択失敗を教師化する。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の `日時` を基準にする。

2026-06-29 05:38 JST 更新: `bin_expected cap=480` を固定holdout stressへ適用した。baseでは `bin_expected` が min pnl `-223.7292`, sum `-116.0564`、`raw_event` が min `-157.1394`, sum `-52.2202`。high costでも `bin_expected` は min `-200.9822`, sum `-186.3262` で `raw_event` の min `-167.4006`, sum `-163.4272` を下回った。2025-04損失はnormal-volと `rollover` / `ny_late` に集中。`bin_expected` は標準昇格せず、次はnormal-vol/time-session riskをvalidation側で事前登録してcost-awareに検証する。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の `日時` を基準にする。

2026-06-29 05:28 JST 更新: `derive-exit-holding-columns` を追加し、代表4ヶ月validationで `raw_event`, `bin_upper`, `bin_expected`, `bin_expected_hazard` を比較した。base/high costとも `bin_expected cap=480` が最上位で、base min pnl `145.5682`, high cost min pnl `120.5842`。hazard系penalty/dynamicはPnLを削った。既存artifactにはlog予測列がないためlog-derived holdingは未比較。次は `bin_expected cap=480` を固定holdout stressへ出し、log比較用artifactを再生成する。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の `日時` を基準にする。

2026-06-29 05:18 JST 更新: `long_exit_event_time_bin` / `short_exit_event_time_bin` classifier出力から、`pred_*_exit_event_time_bin_minutes` と `pred_*_exit_event_time_bin_expected_minutes` を生成するようにした。2025-04小型HGB smokeではtime-bin分類balanced accuracyがlong `0.2765`, short `0.2439` と弱く、単月のbase/high costは採用根拠にしない。次は複数foldでlog-derived / time-bin upper / time-bin expected / hazard-event probabilityを同じgridで比較する。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の `日時` を基準にする。

2026-06-29 05:09 JST 更新: exit event minutesに `log1p(minutes)` targetを追加し、prediction artifactに `0..1440` 分へclip済みの `pred_*_exit_event_minutes_from_log` を保存するようにした。小型MLP smokeではlog targetのR2は負で採用候補ではないが、raw minutes回帰の負値・異常大値をpolicy holdingへ直結しない配線は確認できた。2025-04 backtest smokeは base `-28.4370`, high cost `-57.1444` でNoTrade未満。次は複数fold validationへ戻し、bin分類とhazard/event probability targetを比較する。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の `日時` を基準にする。

2026-06-29 04:57 JST 更新: `timed_ev` に raw holding predictionのfail-close/fallback guardを追加した。2025-04 strict top診断では、HGB fallbackが base `-170.7302`, high `-182.3386`、fail-close skipが base `-111.2648`, high `-129.9124` まで損失を縮めた。ただしNoTradeには届かないため、guardは標準候補ではなく破綻抑制の安全装置として採用する。次は exit minutes targetを `log1p(minutes)`, bin分類, hazard/event probability型へ作り直す。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の `日時` を基準にする。

2026-06-29 04:44 JST 更新: 2025-04へ同一形式predictionを生成し、stress score topを未使用holdoutで確認した。MLP exit minutesは中央値 long `-163.75`, short `-145.39`、1分未満率約65%で外挿破綻。MLP holding本線はbestでも base `-475.6374`, high `-1442.3792`、stress top `down5,up10` は base `-503.8224`, high `-1503.3702`。HGB holding fallbackでもbest/strict `down5,up10,range5` が base `-157.1394`, high `-167.4006` でNoTradeに負ける。2025-04へ直接weight最適化せず、次は exit minutes の unconstrained regression をやめ、log/bin/hazard targetとfail-close guardを入れる。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の `日時` を基準にする。

2026-06-29 04:26 JST 更新: `candidate_rank_mode=stress_score` と model-sweep grid対応の `model-holdout-audit` を追加した。stress score topは `down5,up10` だが、既存holdout stressでは min pnl `-57.7402`, sum `473.2982` で標準採用不可。`down10,up10,range10` はholdout balanceが良いがvalidation topではない。既存holdoutに合わせてweight調整せず、次は2025-04以降の同一形式prediction生成から未使用holdoutを確認する。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の `日時` を基準にする。

2026-06-29 04:14 JST 更新: high cost validationを追加し、base + moderate + high costを同時に満たすselectionを確認した。`model-candidate-selection` に `--min-base-folds` / `--min-cost-folds` を追加し、fold数の違うbase/cost評価を明示できるようにした。validation top `down5,up10,range5` は固定holdout stressでmin pnl `-32.4176`、high cost合計 `-31.6628`、max drawdown `181.6922` へ悪化。標準採用せず、次はvalidation fold内でstress-aware rankingを定義する。採番と最新判断はファイル更新時刻や `更新日時` ではなく、レポート本文内の `日時` を基準にする。

2026-06-29 03:38 JST 更新: 2025-03に同一HGB entry + MLP exit + forced target frameを生成し、`component_fixed_weighted quality>=2` を追加holdout確認した。baseline/quality `0` は `-48.6826`, 112 trades。事前登録候補 `quality>=2` は `-55.7516`, 104 tradesへ悪化。`quality>=5` は単月では `-45.2572` へ縮むが、validationと2025-02を壊すpost-hoc条件なので採用しない。`quality>=8` 以上は取引ゼロで月10trades条件を満たさない。標準採用せず、次はside/entry calibrationとshort exposure/risk検知へ戻る。

2026-06-29 03:24 JST 更新: `component_fixed_weighted` prefixed applyを2024-12/2025-02に生成し、固定policyへ適用した。validation選択の `quality>=0` は両holdoutでbaselineと完全に同じで、filterとして働かない。診断では `quality>=2` が2024-12 `-16.4354`, 2025-02 `62.7588` に改善したが、validation min pnlは `71.1944` へ下がる。標準採用せず、次は2025-03以降の同一HGB+MLP+forced predictionを生成して `quality>=2` を事前登録で確認する。

2026-06-29 03:10 JST 更新: `combine-candidate-quality-components` を追加し、timed/fixed/clipped component列を `mean`, `min`, `weighted_mean` で合成できるようにした。validation 4foldでは `component_fixed_weighted quality>=0` がbaselineと同じ min pnl `82.7176` を維持しつつ、sum `410.7146`、EV overestimate mean `15.4567` に小改善。`component_min` はtrade数とPnLを壊す。標準採用せず、次はprefixed applyを生成して2024-12/2025-02と追加holdoutへ固定適用する。

2026-06-29 02:57 JST 更新: `oof-candidate-quality-model --prediction-prefix` を追加し、timed/fixed/clipped component列を同じOOF parquetへ共存できるようにした。component meanを `min_trade_quality` gateとして試したが、timed/fixed/clippedいずれもbaseline `min pnl=82.7176`, `sum=406.6546` を超えない。fixed component `quality>=0` はforced exitを0にするがmin pnl `71.1944` で弱い。標準採用せず、prefix列は診断・tie-break・multi-feature stacking基盤として残す。

2026-06-29 02:43 JST 更新: `oof-candidate-quality-model` に `timed_barrier_component_adjusted_pnl`, `fixed_horizon_component_adjusted_pnl`, `clipped_best_adjusted_pnl` を追加した。OOFではfixed horizon componentのR2が `-0.0895` と最もましだが、validation 4foldでは全targetのtopが `risk_penalty=0` に戻る。best positive-riskでもmin pnlはtimed `62.5366`, fixed `43.6626`, clipped `41.7588` でbaseline `82.7176` を下回り、EV過大評価も改善しない。標準採用せず、次はcomponentをscalar penaltyにせず別特徴/別targetとして扱う。レポート採番と最新判断はファイル更新時刻や `更新日時` ではなく、本文内の作成時刻 `日時` を基準にする。

2026-06-29 02:28 JST 更新: `oof-candidate-quality-model --target-mode joint_exit_adjusted_pnl` を追加した。OOF上はforced barrier targetよりmean MAE `14.6941 -> 10.7047`、RMSE `15.5222 -> 11.4542` と改善したが、実行policyではvalidation topがrisk `0` のまま。mean-riskもlower-riskもfixed smokeで2024-12と2025-02を両立できない。標準採用せず、次はjoint成分をexit class/time-to-event/fixed horizon/side-regime residualへ分解する。

2026-06-29 02:11 JST 更新: `prediction_frame` がforced exit target列を保存するようにし、既存hybrid prediction向けに `trade_data.modeling enrich-predictions` を追加した。OOF `115252` 行、2024-12 `28763` 行、2025-02 `27441` 行へforced列をjoinし、欠損0を確認。forced barrier targetではtime exit sourceが `long/short_forced_adjusted_pnl` だけになりfallbackは解消したが、validation topはrisk `0` のまま。標準採用せず、次はexit event、time-to-event、fixed horizon PnL、EV calibration誤差のjoint targetへ進む。

2026-06-29 01:56 JST 更新: `oof-candidate-quality-model --target-mode barrier_event_adjusted_pnl` を追加した。profit/loss barrier順とtime exit PnLをtargetに入れると、OOF target meanは `1.5739` まで下がりraw EV bias `20.4316` が露出した。平均モデルはbiasを `0.9855` まで縮めるが `R2=-0.1730`、lowerはcoverage `0.9925` で保守的すぎる。validationではrisk `0` が最良、fixed 2024-12だけrisk `0.10` が改善して2025-02を壊す。標準採用せず、次はforced PnL列とjoint exit/EV calibration targetを整える。

2026-06-29 01:21 JST 更新: `oof-candidate-quality-model` を追加し、candidate rowの連続PnL平均と下方分位を学習した。OOFはcandidate `9091` 件、平均モデル `R2=-0.0509`、lower coverage `0.6845`。mean/lower直接EVはvalidation min pnl `-190.2562` / `-152.8084` で採用不可。lower overestimate riskもvalidation topはrisk `0`、fixed 2024-12だけ改善して2025-02を壊す。標準採用せず、次はexit timing込みtargetとEV calibration誤差の扱いを改善する。

2026-06-29 00:45 JST 更新: trade failure probabilityのside/regime別OOF校正CLIを追加した。`volatility_regime+session_regime` はOOF AUCを `0.5736` から `0.5837` に上げたが、実行policyでは改善せず、`combined_regime` full grid topはrisk `0`、`vol+session calibrated risk=30` はvalidation min pnl `62.7122` でraw t10 top `92.8530` 未満。fixed 2024-12も `-159.2242` と大きく崩れたため標準採用しない。次はcandidate-entry集合へfailure targetを広げる。

2026-06-29 00:22 JST 更新: `large_loss` threshold `5/10/15` を比較した。OOF AUCは `5=0.4042`, `10=0.5736`, `15=0.5665`、validation top min pnlは `5=88.8168`, `10=92.8530`, `15=87.4970`。fixed holdoutでは `5` が2024-12を `+22.3498` にするが2025-02 `-19.6600`、`10` は2ヶ月合計では最良だが2024-12 `-37.2928`、`15` は2024-12 `-55.4970`。threshold調整だけでは標準採用に足りないため、`threshold=10` を基準にside/regime別校正またはcandidate-entry集合拡張へ進む。

2026-06-28 23:55 JST 更新: 実行trade failure classifierを追加した。`large_loss` はOOF AUC `0.5736`、validation top min pnl `92.8530`, sum `402.2514`。fixed 2024-12は `-37.2928` でbaseline `-54.6032` より改善するがNoTrade未満、2025-02は `+76.9254` でbaseline `+81.8334` より少し弱い。`wrong_side` / `profit_barrier_miss` / `exit_regret_high` / `any_failure` は単独riskでは最良がrisk `0`。次は `large_loss` targetに絞り、threshold比較、side/regime別校正、candidate-entry集合への拡張を行う。

2026-06-28 23:39 JST 更新: selected-trade qualityから過大評価soft penalty列を追加した。validationでは `risk_penalty=0.25` が min pnl `86.9174`, sum `442.9766` で改善したが、fixed 2024-12は `-128.2556` と既存baselineより悪化。`risk=0.10/0.50` も2024-12で崩れるため標準採用しない。次は過大評価回帰ではなく、実行trade failure分類targetへ進む。

2026-06-28 23:19 JST 更新: selected-trade quality calibrationを直近hybrid top policyに再適用した。OOF上はEV過大評価が大きく下がったが、`min_trade_quality` gateはvalidation topを改善しない。2024-12では `min_trade_quality=4` が `-4.6296` まで改善する一方、2025-02を `+8.5648` へ壊すため標準採用しない。次は校正EV置換またはsoft overestimate penaltyを試す。

2026-06-28 23:11 JST 更新: candidate-entry residual penaltyを追加し、entry条件を通った候補行だけでsession別の過大評価をfitした。weight `1`, rank `0.5` は2024-12を `-17.1780` まで縮めたが、validation 4fold min pnlは `50.5324` に落ち、2025-02もbaselineを超えない。標準採用せず、次はcandidate rowではなく実行trade単位の realized residual / side failure / exit regret を学習対象にする。

2026-06-28 23:01 JST 更新: `oof-residual-penalty` と residual penalized EV列を追加し、session / vol-session粒度で検証した。session weight `10` はvalidation上eligibleだが、2024-12 fixed holdout `-156.1742` / `-159.1944` で既存baselineより大きく悪化。row-level residualは実行売買の壊れ方を表さないため標準採用せず、次は selected-trade / candidate-entry residual targetへ進む。

2026-06-28 22:47 JST 更新: support-aware lower EV columnsを追加し、`lower_z=0.5` をvalidation/holdoutで検証した。OOF selected-side品質は改善したが、executable validationは2024-11で崩れ、4fold min adjusted pnl `-127.7796` / `-134.5254`。2024-12 fixed holdoutも `-101.7542` / `-133.4082` で既存baselineより悪化。標準採用せず、次はside/regime別calibration residual targetまたはregime-conditioned side confidenceへ進む。

2026-06-28 22:28 JST 更新: `model-holdout-audit` を追加し、validation eligible候補を2024-12/2025-02の標準holdoutとcost stressで同時監査した。標準条件でもcost stressでも `audit_eligible=True` は0件。`long:ny_late:15` risk topは相対最良だがNoTradeを安定して超えない。次はside EV penalty探索を広げず、support-aware realized-PnL targetやside/regime別EV calibrationへ戻る。

2026-06-28 22:12 JST 更新: `short:combined_regime=up_low_vol` のside EV penaltyをvalidation/base、cost-mid、2024-12/2025-02固定test、代表cost stressで確認した。short比率は下がるが、validation最悪月PnLと2024-12 holdoutが悪化するため直接減点は採用しない。次はshort偏重riskを、group post-hoc penaltyではなくsupport-aware targetやside/regime別calibrated EV、複数holdout同時rankingで扱う。

2026-06-28 22:03 JST 更新: `policy_combined` datasetに2025-02を追加し、同じtrain/valid splitでHGB entry/side + MLP exit hybrid predictionを生成した。2025-02固定testではbaseline `+81.8334`, risk top `+79.4018`, PnL top `+59.1854`。高コスト + delay 1でもbaseline `+21.3628`, risk top `+19.5898` はプラス。risk topは2024-12防御として有効だが、2025-02ではbaselineにわずかに負けるため標準採用しない。次は `short:up_low_vol` とshort偏重riskを複数holdoutで扱う。

2026-06-28 21:52 JST 更新: `long:session_regime=ny_late:15` side EV penalty候補を2024-12でspread/slippage/delay stressした。risk topは標準条件 `-5.4938`、高コスト条件 `-26.0816` で、baseline `-54.6032` / `-76.3910` より大きく改善した。ただしNoTradeを安定して超えないため標準採用しない。次は別holdout月を生成して同じ候補を固定再検証する。

2026-06-28 21:28 JST 更新: near-top risk rankingを追加し、long rule gridへ適用した。複合risk scoreではruleなしがtopのまま。`long:ny_late` はnear-top内に残るが、group loss / EV overestimate / exit regret / side concentrationが悪化する。drawdown-onlyなら `long:ny_late` を選ぶが、max DD改善が小さすぎるため標準採用しない。次はside/regime別EV calibrationかregime-conditioned risk targetへ進む。

2026-06-28 21:14 JST 更新: `model-sweep` にside rule set gridを追加し、`long:ny_late` / `long:range_low_vol` をvalidation local gridで事前評価した。validation topはruleなしのまま min pnl `81.5352`。`long:ny_late` blockは2-3位で min pnl `79.7192` / `78.0572`、2024-12は `-15.0538` / `-5.4938` まで改善したがNoTrade未満。`long:range_low_vol` 系は2024-12で `-141.5698` / `-144.2494` と崩れたため捨てる。

2026-06-28 20:45 JST 更新: hybrid候補にgroup-loss / diagnostic reselectionをかけたが、soft penaltyはtopを変えず、group gate60 topは2024-12で MLP holding `-97.6568` / HGB holding `-69.0240` と悪化した。posthocの `long:ny_late` blockは `-5.4938` まで損失を縮めるが、後付けなので採用不可。次は `long:session_regime=ny_late` と `long:combined_regime=range_low_vol` をvalidation gridに入れて、2024-12を見る前に選ぶ。

2026-06-28 20:38 JST 更新: HGB entry/side + MLP exit timing hybridを検証。validation strict selectionではhybrid topが base topを min pnl `78.4344` から `81.5352`、sum pnl `369.5736` から `396.9782` へ改善した。ただし2024-12固定testでは hybrid top + MLP holding が adjusted pnl `-54.6032` でNoTradeに届かず、direction error `0.6327` とEV過大評価 `23.0714` が残った。MLP exit timingは補助信号として残すが、本流はentry/side calibrationへ戻す。

2026-06-28 20:20 JST 更新: shared MLP 4fold pilotでは、exit timing targetは学習できている一方、EV/sideの汎化が弱く、strict candidate selectionは `eligible=0`。片側偏りを許すとプラス候補は出るが、未知regimeへの頑健性としては不十分。標準policy化せず、次はexit timing専用化、entry/side calibration、HGB classifierとのhybrid、またはshared classifier追加を検証する。レポートの最新判断はファイル属性の更新時刻ではなく、本文冒頭の `日時` を参照する。

旧倍率 target で学習し、新倍率 validation/test で評価する流れに更新した。2024-07、2024-09、2025-01 の validation sweep を横断集計し、各fold 30 trades以上、強制決済率 0、max drawdown 100以下、各fold adjusted pnl 0以上の条件で `timed_ev`, entry threshold 15, side margin 5, risk penalty 0 を暫定候補にした。

この候補を 2025-02 test に固定適用すると adjusted pnl `+23.7253`、raw pnl `+78.7070`、42 trades、profit factor `1.0863`、max drawdown `112.5325`、forced exits 0 だった。no_trade `0.0` と random `-14.0078` は上回ったが、drawdown 制約はtestでは 100 を少し超えたため、まだ安定モデルとはみなさない。

同じ候補を追加foldの 2024-10 test に固定適用すると adjusted pnl `+48.9555`、raw pnl `+99.6620`、43 trades、profit factor `1.1931`、max drawdown `77.1468`、forced exits 0 だった。2024-10 の no_trade `0.0` と random `+43.9895` を上回った。ただし signal は long 側に偏ったため、short 優勢相場での確認が必要。

short/down-regime 確認として、train 2023-01..2024-10、valid 2024-11、test 2024-12 のfoldを追加した。4fold strict summary では eligible candidate が消え、従来候補 `timed_ev`, entry 15, side margin 5, risk 0 は validation min pnl `-21.0065` まで悪化した。2024-12 test では adjusted pnl `-175.6668`、max drawdown `206.9538`、long adjusted pnl `-110.5037`、short adjusted pnl `-65.1630`。short signal は多かったため、問題は単純な long bias ではなく、下落/レンジ局面での entry/exit timing と EV calibration の崩れ。

学習品質改善として、非連続月指定と `month_label` sample weighting を実装した。混合regime train、valid 2024-07/2024-09/2024-11/2025-01、test 2024-12/2025-02 で実験したところ、validationの下落月は改善したが、2024-12 test は adjusted pnl `-183.5370` と崩れた。一方で 2025-02 test は `+54.9137`。学習データ混合とweightingだけでは過学習問題は解決しておらず、次は教師targetとregime featureを改善する。

entry timing を `long / short / stay_flat` に潰さず、`profit_barrier_hit`, `wait_regret`, `entry_local_rank`, `entry_urgency` に分解する方針を採用した。これは entry 正例の少なさを補い、1つのdecision rowから複数の教師信号を得るための変更。コード実装と単体テストは完了しており、次は旧倍率datasetの再生成と新target込みの学習。

dense entry quality target込みでHGBを再学習し、quality filter付きpolicyを追加した。validationでは `timed_ev entry=5 side_margin=5 risk=0.1 min_entry_rank=0.5` が4fold eligible になったが、testでは 2024-12 `-135.9573`、2025-02 `-101.0583` と no_trade に負けた。強く絞る候補は2024-12を `-9.5233` まで抑えたが、取引数が少なくedgeとはみなせない。独立HGBでは追加targetがEV予測を直接改善しないため、次は二段階meta modelまたはshared representationの深層学習に進む。

二段階meta EV modelを追加した。validation predictionsでfitするとvalidation上のR2は long `0.1837` / short `0.1980` まで上がるが、test適用では long `-0.0652` / short `-0.1921` と悪化。標準quality候補では 2025-02 は `+23.7068` へ戻る一方、2024-12 は `-240.5445` と大きく崩れた。meta modelも同じvalidationでfitと選択を行うと過学習するため、次はvalidation内walk-forwardでfit月と選択月を分ける。

validation内 leave-one-month-out meta を実施した。各holdout月では、残り3ヶ月でmetaをfitし、holdout月へmeta予測を付与してpolicy sweepした。4fold summaryでは `timed_ev entry=10 side_margin=5 risk=0.2 max_wait_regret=2 min_entry_rank=0.5` が、各fold10 trades以上、各fold pnl 0以上、max drawdown 100以下、forced exit 0の条件を満たした。OOF選択により同月fit/同月選択の漏れは減ったが、全validationでfitした最終metaをtestへ当てるとR2は引き続き long `-0.0652` / short `-0.1921`。固定policyのtestは 2024-12 `-97.3488`、2025-02 `-0.4358`。同じpolicyのmetaなしbase予測 2024-12 `-130.3193`、2025-02 `-47.2025` よりは改善したが、no_tradeにはまだ負ける。過学習は「悪化は抑えたが、解消していない」状態。

過学習対策パラメータと学習時間診断を追加した。HGBに `max_depth`, `max_features`, `early_stopping`, `validation_fraction`, `n_iter_no_change`, `tol` を追加し、`model_diagnostics` でtargetごとの `n_iter` を保存する。`target-set policy` を追加し、policyに必要なtargetだけで長時間学習を比較できるようにした。20ヶ月trainで `max_iter=80`、`320`、`1280` を比較したところ、全targetがmax_iterに到達した。iter320はvalidationではeligible候補を作れたが、testは 2024-12 `-99.9843`、2025-02 `-38.9125` でNoTradeに負けた。iter1280は30 trades/foldでも10 trades/foldでもeligibleなし。参考候補のtestは 2024-12 `-97.7620`、2025-02 `-97.0460`。学習時間不足の可能性は残るが、単純に長く回すだけではtest汎化は改善していない。

train/valid/testの倍率を1.0/1.2に揃えたdatasetも診断した。80iterは10 trades/foldでもeligibleなし。320iterはvalidationでeligible候補を作れたが、fixed testは 2024-12 `-131.6996`、2025-02 `-71.2528`。さらに長時間学習として `max_iter=1280` を同一LRと低LRで試した。低LR1280はvalidation 30 trades/fold条件で `min pnl=+40.8376`, `min trades=46` の強い候補を作ったが、fixed testは 2024-12 `-134.5306`、2025-02 `-110.0922` と崩れた。testで後付け選択すればプラス候補はあるが、その候補はvalidationではeligibleでない。したがってHGB反復数探索はいったん打ち切り、次は失敗trade分解、OOF標準化、side/regime別calibration、exit timing target、shared representationへ進む。

docs再読による方向性レビューを作成した。研究の大枠はずれていないが、同じvalidation sweepを繰り返して閾値を探すこと、独立HGBの反復数だけを伸ばすことは袋小路になりやすい。

トレードMLの汎化原則を `docs/trading_ml_generalization_principles.md` に整理し、現状レビューを `docs/reports/00011_2026-06-28_generalization_principles_review.md` に作成した。現状は、NoTrade比較、月別評価、実行可能backtest、失敗trade analyzerは良い。一方で、purging/embargo、regime別標準評価、spread/slippage/delay感度、validationを見すぎない運用が不足している。

低LR1280モデルの失敗trade分析を `docs/reports/00010_2026-06-28_trade_failure_analysis.md` に追加した。2024-12/2025-02では予測EVが実現PnLに対して平均約22ドル過大で、actual barrier miss、direction error、exit regretが損失の中心。`min_entry_rank=0.5` のfocused sweepは損失を抑えたがNoTradeには届かない。

汎化レビューの不足項目に対応し、regime feature/label、明示的なspread/slippage/execution delay、`model-cost-sensitivity`、学習時のpurged/embargo splitを実装した。詳細は `docs/reports/00012_2026-06-28_regime_cost_purge_controls.md`。

1.0/1.2 datasetをregime列込みで再生成し、purge有効・embargo 24hでHGB 80iter policy modelを再学習した。validation 10 trades/fold条件では全foldプラス候補が出たが、fixed testは 2024-12 `-35.7010`、2025-02 `-47.6716` でNoTradeに負けた。regime分析では両testとも `low_vol` に集中し、2025-02は `asia` と `rollover` で損失が大きい。次はregime gateとside/regime別calibrationを優先する。

hard regime gateを `model-policy` / `model-sweep` に追加した。`asia`、`rollover`、`asia,rollover` をvalidationで比較したところ、validation上はeligible候補が残ったが、fixed testでは安定しなかった。`asia,rollover` を前回候補に足すと 2024-12 `+5.8384`、2025-02 `+24.0720` まで損失回避できたが、7 trades / 3 trades と薄すぎる。hard gateは採用policyではなく診断・ablation用とし、次はside/regime別EV calibrationとsoft threshold調整へ進む。

side/regime別EV calibrationを追加した。validation内OOFで各月をholdoutし、`volatility_regime,session_regime` ごとにEVを補正する。OOF validationでは強い候補が出たが、fixed testでは悪化した。offset型のtop OOF候補は 2024-12 `-185.8364`、2025-02 `-65.1476`、保守候補でも 2024-12 `-149.2616`、2025-02 `-10.7646`。raw EVの前回候補より悪く、calibrationは採用不可。次はvalidation 4ヶ月だけで補正するのではなく、train期間OOF predictionsを作ってcalibration fit月数を増やすか、exit timing target改善へ進む。

train期間OOF predictions生成基盤を追加した。`trade_data.modeling oof` で、指定月をfoldごとにholdoutし、その月を学習に使っていないHGB予測を `predictions_oof.parquet` として保存できる。軽量smoke runは `experiments/20260627_222746_oof_smoke_policy/` で完了。次は HGB 80iter regime/purge v2 と同じtrain monthsに対して本番OOFを実行し、side/regime calibrationのfitデータを増やす。

train期間OOFを4ヶ月holdout単位で生成し、side/regime calibrationの各validation foldへ `train OOF + 他validation月` をfitデータとして追加できるようにした。あわせて評価倍率を profit 1.0 / loss 1.20 に統一し、`trade_data.dataset` と `trade_data.backtest` のデフォルトも 1.0 / 1.20 に更新した。shrink 0.65 calibration のvalidation top-min候補は 4fold全てプラス、min pnl `41.1354`、min trades `10` だったが、fixed testは 2024-12 `+18.8306`、2025-02 `-44.5990`。offset calibrationはvalidation平均が高いが、fixed testは 2024-12 `-63.2266`、2025-02 `-44.3740`。loss 1.20統一で数値は改善したが、NoTradeを安定して超える状態ではない。次は2025-02のshort失敗trade分解とexit timing target改善を優先する。

calibrated EV列を指定したtrade failure分析に修正し、shrink065 top-minを再分析した。2025-02は 12 trades / adjusted pnl `-44.5990`、direction error rate `0.7500`、predicted side error rate `0.7500`。実績best sideがshortだった8 tradesは全てlongで入り、唯一のshortは `asia/up/low_vol` で大きく外した。問題は「shortが多すぎる」ではなく、calibrated EVの方向選択が未知月で壊れていること。あわせて固定保有 60/240/720 分のlong/short adjusted pnl targetを追加した。次は固定horizon target入りdatasetを再生成し、exit policyとside/regime安全marginを検証する。

固定horizon target入りdatasetを 2023-01 から 2025-02 まで再生成し、`fixed_horizon_ev` policyと `extra-side-margin-rules` を追加した。`target-set full` のHGB 80iterで固定horizon EVを予測し、validation上は `entry=2`, `side_margin=2`, `max_wait_regret=4`, `min_entry_rank=0.5`, `asia/rollover +5` が top-min候補。validation mean pnl `27.2219`, min pnl `19.1398`, min trades `45`。fixed testは 2024-12 `+30.2662`, 2025-02 `+4.6898` と、同一候補で両test月NoTradeを上回った。ただし2025-02のedgeは薄く、slippage/spread込みでは崩れやすい。次はshort専用margin/threshold、barrier hit probability calibration、コスト込みvalidation選択へ進む。

2026-06-28 08:38 JST 更新: short/long別entry threshold offsetを実装し、short offset gridをvalidation 4ヶ月で検証した。no-cost / cost-aware validationのtop-minは `entry=0`, `short offset=4`, `side_margin=2` で一致したが、fixed testは 2024-12 `+22.7102`, 2025-02 `+0.3502` と前回候補より2025-02が薄くなった。validation rank-3の `short offset=8` は診断比較で 2024-12 `+27.4184`, 2025-02 `+26.8074` と良いが、testを見た後の採用は不可。次はcost-aware validation、周辺offsetの台地、side/regime別損益、drawdownを含む事前登録の選択基準と、新しいblind holdoutを用意する。

2026-06-28 08:53 JST 更新: `model-candidate-selection` を実装し、no-cost/cost-aware validation、side loss、cost drop、short offset plateauを同時に見て候補を選ぶようにした。2025-03 datasetを追加し、同じtrain/validationでtestだけ2025-03にしたblind holdoutモデルを学習。validationで選んだ `entry=0`, `short offset=8`, `side_margin=1` は2025-03で adjusted pnl `-49.7004`、short pnl `-49.3238`、profit factor `0.6751` とNoTradeに負けた。最大損失は `asia / range / low_vol` のshortで、predicted short profit barrier hitが `0` だった。short offset単独は採用せず、profit barrier確率calibrationとexit timing改善を優先する。

2026-06-28 09:08 JST 更新: binary classifierのclass 1 probabilityを `pred_<target>_prob` として保存し、`model-policy` / `model-sweep` に profit barrier probability thresholdを追加した。validation 4ヶ月で選んだ `entry=0`, `short offset=8`, `side_margin=1`, `barrier threshold=0.40` は、2025-03 blindで adjusted pnl `-29.5462`, 29 trades, profit factor `0.6742`。前回より損失は縮小したが、short pnl `-47.6306` でNoTradeには負けた。最大損失は同じ `asia / range / low_vol` short。barrier gate単独は採用せず、次はside-specific regime suppressionを優先する。

2026-06-28 09:26 JST 更新: `model-policy` / `model-sweep` に `--side-block-rules` と `--side-extra-margin-rules` を追加した。`short:session_regime=asia` はvalidation選択候補として2025-03 blind adjusted pnl `+18.0748`, 35 trades, profit factor `1.2700`。short pnlは `-0.0096` まで改善した。一方、direction error rate `0.4286`、predicted side error rate `0.4571`、exit regret sum `702.5012` は残る。これは「方向予測の改善」ではなく「壊れやすいasia shortのno-trade化」による改善なので、2025-04以降のblindで事前登録候補として検証する。

2026-06-28 09:39 JST 更新: 2025-04 / 2025-05を追加blindとして生成・学習し、事前登録候補 `entry=0`, `short offset=6`, `side_margin=1`, `barrier threshold=0.40`, `side block=short:session_regime=asia` を固定適用した。2025-04は adjusted pnl `+56.3148`, 31 trades, profit factor `1.3741`、2025-05は `+83.0630`, 28 trades, profit factor `1.5176`。blockなしの同条件はそれぞれ `-24.5976` / `-57.6474`。2025-04/05とも、blockなしではasia shortが約 `-100` の損失を作っていた。`short:session_regime=asia` は暫定採用候補へ昇格する。ただし2025-04のdirection error rateは `0.5161` で高く、次はside/session別損失集中をcandidate selectionに組み込む。

2026-06-28 09:51 JST 更新: `model-sweep` metricsへ `direction_session_adjusted_pnl_min`, `worst_direction_session`, `worst_direction_session_trade_count` を追加し、`model-candidate-selection` に `--max-direction-session-loss-per-fold` を追加した。2025-05 smokeでは、blockなし候補が `worst_direction_session=short:asia`, `direction_session_adjusted_pnl_min=-100.5254` で `direction_session_loss_ok=False`、blockあり候補は `+19.8400` でeligible。これでside/session別損失集中をvalidation内の候補選択に組み込める。

2026-06-28 09:54 JST 更新: 既存 `docs/reports/*.md` の旧形式レポートにも冒頭の `日時` / `更新日時` を追加し、`docs/README.md`, `docs/experiment_protocol.md`, `docs/templates/experiment_report.md` を同じ運用へ更新した。今後のレポートは作成時刻と更新時刻を明示する。

2026-06-28 10:06 JST 更新: `model-sweep` metricsへ predicted/actual profit barrier miss率を追加し、`model-candidate-selection` に `--max-predicted-profit-barrier-miss-rate` / `--max-actual-profit-barrier-miss-rate` を追加した。2025-05 smokeでは、blockなし候補が `actual_profit_barrier_miss_rate_max_all=0.5000` で `actual_profit_barrier_miss_ok=False`、`short:session_regime=asia` blockあり候補は `0.464286` でeligible。predicted miss率は両方 `0.0` で、barrier threshold通過後の過大評価はmiss率だけでは検出できないため、次はprobability bucket別actual hit rateを見る。

2026-06-28 10:19 JST 更新: `docs/reports` の既存24本を、各ファイル本文冒頭の `日時` 昇順に `00001_...` から `00024_...` へリネームした。採番基準はファイルシステムの更新時刻ではなく、レポート内の `日時`。`GOAL.md`, `docs/README.md`, `docs/experiment_protocol.md`, `docs/templates/experiment_report.md` もこの運用へ更新した。

2026-06-28 10:21 JST 更新: profit barrier probability bucket別のactual hit rateを `model-sweep` metricsへ追加し、`model-candidate-selection` に `--max-profit-barrier-calibration-overestimate` を追加した。2025-05 smokeでは、blockなし候補は calibration overestimate `0.054305`、`short:session_regime=asia` blockあり候補は `0.248089`。blockあり候補はPnLが良いがbarrier probabilityは過大評価しているため、このgateは当面hard採用せず診断軸として扱う。詳細は `docs/reports/00025_2026-06-28_profit_barrier_calibration_candidate_gate.md`。

2026-06-28 10:37 JST 更新: 2025-06 blindを追加した。事前登録候補 `short:session_regime=asia` blockは adjusted pnl `-100.4662`, 15 trades, profit factor `0.3444`, max drawdown `133.5832` でNoTradeに大きく負けた。損失中心は `short:london` で、direction error rate `0.6000`、profit barrier miss 7 trades / adjusted pnl `-152.0642`。post-hocにLondon shortもblockすると損失は消えるがtrade数は2以下で実質NoTradeに近い。validation back-checkでもLondon blockは事前支持されなかったため、`short:session_regime=asia` は暫定採用候補から降格する。詳細は `docs/reports/00026_2026-06-28_blind_2025_06_asia_short_block_failure.md`。

2026-06-28 10:47 JST 更新: short exposure concentration と support-aware barrier gateを追加した。2025-06 smokeでは失敗候補 `short:session_regime=asia` が `short_trade_share=0.933333` で `short_trade_share_ok=false`、all-short-block診断候補は1 tradeしかなく `eligible_base=false` / `eligible_cost=false`。smoothed actual missとsmoothed calibrationは、1 trade候補を raw 0.0 として過度に楽観しない値 `0.333333` に補正した。詳細は `docs/reports/00027_2026-06-28_short_exposure_support_aware_gates.md`。

2026-06-28 10:52 JST 更新: `docs/reports` の通し番号は、ファイルシステムの更新時刻や本文の `更新日時` ではなく、本文冒頭の `日時` だけを基準にすることを `GOAL.md`, `docs/README.md`, `docs/experiment_protocol.md`, 本ファイルに明記した。

2026-06-28 11:14 JST 更新: validation 4foldで short share / smoothed gate / high-turnover条件を比較した。前回候補周辺gridは月10trades条件を満たせなかったが、high-turnover gridでは `max-forced-exit-rate=0.05`, `max-direction-session-loss-per-fold=60`, `max-short-trade-share=0.65`, `max-smoothed-actual-profit-barrier-miss-rate=0.55` で5候補が残った。暫定候補Aは2025-06既知月でも cost adjusted pnl `+37.0572`、52 trades。calibration hard gateで選ばれるB候補は2025-06既知月で `-29.4530` とLondon short崩れを再発したため、smoothed calibrationはhard gateにしない。詳細は `docs/reports/00028_2026-06-28_high_turnover_gate_validation.md`。

2026-06-28 11:14 JST 更新: 2025-07 blind前の暫定選定基準を `docs/decisions/0007_high_turnover_gate_selection.md` に固定記録した。

2026-06-28 12:27 JST 更新: 固定済み候補Aを2025-07 blindに適用した。no-cost adjusted pnlは `+1.5838` だが、standard cost-aware caseは `-12.7764`, 66 trades, profit factor `0.9049` でNoTradeに負けた。short concentrationは回避した一方、損失は long / `ny_overlap` / `low_vol` / `down_low_vol` に移った。EV overestimate vs realized meanは `15.6821`、actual profit barrier miss rateは `0.6515`。候補Aは採用候補から外す。詳細は `docs/reports/00029_2026-06-28_blind_2025_07_candidate_a.md`。

2026-06-28 12:37 JST 更新: `model-sweep` metricsへ trade-analysis diagnostic列を追加し、`model-candidate-selection` で direction error、predicted side error、no-edge rate、exit regret mean、EV overestimate vs realized meanをgateできるようにした。2025-07候補Aのpost-hoc smokeでは、`max-direction-error-rate=0.5`, `max-exit-regret-mean=15`, `max-ev-overestimate-vs-realized-mean=10` によりeligibleから落ちた。詳細は `docs/reports/00030_2026-06-28_trade_analysis_diagnostic_gates.md`。

2026-06-28 12:48 JST 更新: validation 4foldのhigh-turnover gridを新diagnostic列入りで再生成し、diagnostic gateの閾値台地を確認した。no diagnostic / lenient / balanced はeligible 5件、focusedは2件、strictは1件、2025-07 smoke-like gateは0件。したがって2025-07 post-hoc閾値はhard採用せず、diagnosticは当面tie-breakと失敗分析へ回す。既存reports 30本は、ファイル更新時刻ではなく本文内 `日時` 順で採番が一致することも確認した。詳細は `docs/reports/00031_2026-06-28_diagnostic_gate_validation.md`。

2026-06-28 12:58 JST 更新: 時間別profit barrier targetを追加した。`long/short_profit_barrier_hit_60m/240m/720m` は既存policyのprofit barrier columnに差し替え可能。2025-01 smokeでは60m targetは正例が少なすぎるためまず診断扱い、240m/720m targetを次のvalidation sweep候補にする。詳細は `docs/reports/00032_2026-06-28_time_limited_profit_barrier_targets.md`。

2026-06-28 13:53 JST 更新: 主dataset `data/processed/datasets/xauusd_m1_p1_l1p2/` を時間別profit barrier target込みで 2023-01 から 2025-07 まで再生成し、policy HGBを再学習した。`target-set policy` に固定horizon回帰targetが不足していたため、`EXIT_FIXED_HORIZON_TARGETS` を追加した。240m/720m probabilityをprofit barrier columnに使ったvalidation sweepではeligible候補は残ったが、topはthreshold `0.0` のまま。fine thresholdでも 240m `0.02` / 720m `0.1` が少数残るだけで、24h probability threshold `0.2` のcost min pnl `27.2158` を超えなかった。time-limited barrier probabilityはhard gateへ昇格せず、診断・tie-breakに留める。詳細は `docs/reports/00033_2026-06-28_timebarrier_validation_sweep.md`。

2026-06-28 14:10 JST 更新: `fixed_horizon_ev` に `--fixed-horizon-score-mode(s)` を追加し、60/240/720m固定horizon予測のentry scoreを `max/mean/median/min` で切り替えられるようにした。validation 4foldのcandidate selectionでは `max` のみeligible 7件、`mean/median/min` はeligible 0件。保守的集約はEV過大評価を十分下げず、short exposureを落としすぎてlong-only寄りの損失を増やした。採用候補は `max` 維持。詳細は `docs/reports/00034_2026-06-28_fixed_horizon_score_mode_validation.md`。

## 直近の実験

- `docs/reports/00018_2026-06-28_fixed_horizon_exit_policy.md`
- `docs/reports/00019_2026-06-28_side_specific_entry_offsets.md`
- `docs/reports/00020_2026-06-28_blind_holdout_candidate_selection.md`
- `docs/reports/00021_2026-06-28_profit_barrier_probability_gate.md`
- `docs/reports/00022_2026-06-28_side_specific_regime_suppression.md`
- `docs/reports/00023_2026-06-28_direction_session_candidate_gate.md`
- `docs/reports/00024_2026-06-28_profit_barrier_miss_candidate_gate.md`
- `docs/reports/00025_2026-06-28_profit_barrier_calibration_candidate_gate.md`
- `docs/reports/00026_2026-06-28_blind_2025_06_asia_short_block_failure.md`
- `docs/reports/00027_2026-06-28_short_exposure_support_aware_gates.md`
- `docs/reports/00028_2026-06-28_high_turnover_gate_validation.md`
- `docs/reports/00029_2026-06-28_blind_2025_07_candidate_a.md`
- `docs/reports/00030_2026-06-28_trade_analysis_diagnostic_gates.md`
- `docs/reports/00031_2026-06-28_diagnostic_gate_validation.md`
- `docs/reports/00032_2026-06-28_time_limited_profit_barrier_targets.md`
- `docs/reports/00033_2026-06-28_timebarrier_validation_sweep.md`
- `docs/reports/00034_2026-06-28_fixed_horizon_score_mode_validation.md`
- `docs/reports/00035_2026-06-28_fixed_horizon_oof_calibration.md`
- `docs/reports/00036_2026-06-28_profit_barrier_miss_penalty_sweep.md`
- `docs/reports/00037_2026-06-28_selected_trade_quality_calibration.md`
- `docs/reports/00038_2026-06-28_selected_trade_quality_model.md`
- `docs/reports/00039_2026-06-28_exit_event_timing_targets.md`
- `docs/reports/00040_2026-06-28_exit_event_holding_validation.md`
- `docs/reports/00041_2026-06-28_holding_cap_sweep.md`
- `docs/reports/00042_2026-06-28_delay1_combined_regime_holdout.md`
- `docs/reports/00043_2026-06-28_best_side_confidence_smoke.md`
- `docs/reports/00044_2026-06-28_side_confidence_calibration_report.md`
- `docs/reports/00045_2026-06-28_side_confidence_oof_representative.md`
- `docs/reports/00046_2026-06-28_regime_side_confidence_penalty_smoke.md`
- `docs/decisions/0007_high_turnover_gate_selection.md`
- `docs/decisions/0008_trade_analysis_diagnostic_gate_policy.md`
- `experiments/20260628_062101_exit_event_target_smoke/`
- `data/reports/backtests/20260628_062138_model_timed_ev_2024-09/`
- `experiments/20260628_060718_trade_quality_model_oof_fixed_horizon/`
- `data/reports/backtests/20260628_061118_model_candidate_selection/`
- `experiments/20260628_055648_trade_quality_oof_fixed_horizon/`
- `data/reports/backtests/20260628_055927_model_candidate_selection/`
- `data/reports/backtests/20260628_053757_model_candidate_selection/`
- `data/reports/backtests/20260628_053630_model_candidate_selection/`
- `data/reports/backtests/20260628_050919_horizon_score_mode_candidate_selection/`
- `data/reports/backtests/20260628_horizon_score_mode_candidate_selection_summary.csv`
- `experiments/20260628_040828_policy_timebarrier_p1_l1p2/`
- `data/reports/backtests/20260628_timebarrier_candidate_selection_summary.csv`
- `data/reports/backtests/20260628_timebarrier_fine_candidate_selection_summary.csv`
- `data/reports/backtests/20260628_045220_barrier240_fine_candidate_selection/`
- `data/reports/backtests/20260628_045221_barrier720_fine_candidate_selection/`
- `experiments/20260628_035801_exit_target_smoke/`
- `data/reports/backtests/20260628_034513_model_candidate_selection/`
- `data/reports/backtests/20260628_124813_diagnostic_gate_threshold_comparison.csv`
- `data/reports/backtests/20260628_033639_model_sweep_2025-07/`
- `data/reports/backtests/20260628_033650_model_sweep_2025-07/`
- `data/reports/backtests/20260628_033702_model_candidate_selection/`
- `experiments/20260628_032236_full_fixed_horizon_blind_2025_07_barrier_prob_p1_l1p2/`
- `data/reports/backtests/20260628_032236_candidate_a_2025_07_blind_comparison.csv`
- `data/reports/backtests/20260628_032312_model_fixed_horizon_ev_2025-07/`
- `data/reports/backtests/20260628_032314_model_fixed_horizon_ev_2025-07/`
- `data/reports/backtests/20260628_032410_candidate_a_2025_07_cost_analysis/`
- `data/reports/backtests/20260628_032641_model_cost_sensitivity_2025-07/`
- `data/reports/backtests/20260628_021208_model_candidate_selection/`
- `data/reports/backtests/20260628_021217_known_2025_06_regression_candidates.csv`
- `data/reports/backtests/20260628_014713_model_sweep_2025-06_1/`
- `data/reports/backtests/20260628_014727_model_candidate_selection/`
- `experiments/20260628_013141_full_fixed_horizon_blind_2025_06_barrier_prob_p1_l1p2/`
- `data/reports/backtests/20260628_013232_model_fixed_horizon_ev_2025-06_1/`
- `data/reports/backtests/20260628_013257_side_specific_asia_short_block_2025-06/`
- `data/reports/backtests/20260628_013608_model_candidate_selection/`
- `data/reports/backtests/20260628_011509_model_candidate_selection/`
- `data/reports/backtests/20260628_010550_model_candidate_selection/`
- `data/reports/backtests/20260628_005032_model_candidate_selection/`
- `experiments/20260628_003331_full_fixed_horizon_blind_2025_04_barrier_prob_p1_l1p2/`
- `experiments/20260628_003756_full_fixed_horizon_blind_2025_05_barrier_prob_p1_l1p2/`
- `data/reports/backtests/20260628_003401_model_fixed_horizon_ev_2025-04/`
- `data/reports/backtests/20260628_003424_model_cost_sensitivity_2025-04/`
- `data/reports/backtests/20260628_003824_model_fixed_horizon_ev_2025-05/`
- `data/reports/backtests/20260628_003846_model_cost_sensitivity_2025-05/`
- `data/reports/backtests/20260628_002217_model_candidate_selection/`
- `data/reports/backtests/20260628_002235_model_fixed_horizon_ev_2025-03/`
- `data/reports/backtests/20260628_002255_model_cost_sensitivity_2025-03/`
- `data/reports/backtests/20260628_002507_side_specific_asia_short_block_2025-03/`
- `data/reports/backtests/20260628_000706_model_candidate_selection/`
- `experiments/20260628_000509_full_fixed_horizon_blind_2025_03_barrier_prob_p1_l1p2/`
- `data/reports/backtests/20260628_000729_model_fixed_horizon_ev_2025-03/`
- `data/reports/backtests/20260628_000839_model_cost_sensitivity_2025-03/`
- `data/reports/backtests/20260627_235220_model_candidate_selection/`
- `experiments/20260627_235034_full_fixed_horizon_blind_2025_03_p1_l1p2/`
- `data/reports/backtests/20260627_235231_model_fixed_horizon_ev_2025-03/`
- `data/reports/backtests/20260627_235330_model_cost_sensitivity_2025-03/`
- `data/reports/backtests/20260627_233509_model_sweep_summary/`
- `data/reports/backtests/20260627_233552_model_sweep_summary/`
- `data/reports/backtests/20260627_233636_model_fixed_horizon_ev_2024-12/`
- `data/reports/backtests/20260627_233637_model_fixed_horizon_ev_2025-02_1/`
- `docs/reports/00016_2026-06-28_calibrated_trade_failure_exit_targets.md`
- `docs/reports/00001_2026-06-28_baseline_backtest_2025-01.md`
- `data/reports/backtests/20260627_165623_benchmark_2025-01/`
- `data/processed/datasets/xauusd_m1/xauusd_m1_2025-01_h24_edge15.summary.json`
- `docs/decisions/0002_multitask_targets.md`
- `experiments/20260627_171852_hgb_multitask_edge15/`
- `docs/reports/00003_2026-06-28_hgb_multitask_initial.md`
- `data/reports/backtests/20260627_172832_model_sweep_2024-07/`
- `data/reports/backtests/20260627_172849_model_stateful_ev_2025-01/`
- `docs/reports/00004_2026-06-28_executable_model_policy_2025-01.md`
- `data/reports/backtests/20260627_180433_model_sweep_2024-07/`
- `data/reports/backtests/20260627_180029_model_sweep_2025-01/`
- `data/reports/backtests/20260627_180908_model_sweep_summary/`
- `data/reports/backtests/20260627_180701_model_timed_ev_2025-02/`
- `experiments/20260627_183038_hgb_multitask_edge15/`
- `data/reports/backtests/20260627_183050_model_sweep_2024-09/`
- `data/reports/backtests/20260627_183241_model_sweep_summary/`
- `data/reports/backtests/20260627_183253_model_timed_ev_2024-10/`
- `experiments/20260627_183919_hgb_multitask_edge15/`
- `data/reports/backtests/20260627_183932_model_sweep_2024-11/`
- `data/reports/backtests/20260627_184136_model_sweep_summary/`
- `data/reports/backtests/20260627_184333_model_timed_ev_2024-12/`
- `docs/reports/00006_2026-06-28_mixed_regime_weighted_training.md`
- `experiments/20260627_185200_hgb_multitask_edge15/`
- `data/reports/backtests/20260627_190009_model_sweep_summary/`
- `data/reports/backtests/20260627_190023_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_190023_model_timed_ev_2025-02/`
- `docs/reports/00007_2026-06-28_dense_entry_quality_targets.md`
- `experiments/20260627_192112_hgb_multitask_edge15/`
- `data/reports/backtests/20260627_192904_model_sweep_summary/`
- `data/reports/backtests/20260627_192921_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_192921_model_timed_ev_2025-02/`
- `experiments/20260627_193559_meta_ev_dense_entry_quality/`
- `data/reports/backtests/20260627_193642_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_193655_model_timed_ev_2025-02/`
- `experiments/20260627_194501_meta_oof_2024-07/`
- `experiments/20260627_194501_meta_oof_2024-09/`
- `experiments/20260627_194501_meta_oof_2024-11/`
- `experiments/20260627_194501_meta_oof_2025-01/`
- `data/reports/backtests/20260627_194724_model_sweep_summary_1/`
- `experiments/20260627_194740_meta_all_valid_to_test_oof_selected/`
- `data/reports/backtests/20260627_194758_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_194758_model_timed_ev_2025-02/`
- `docs/reports/00009_2026-06-28_training_time_and_generalization.md`
- `experiments/20260627_201301_policy_iter80_base_train/`
- `experiments/20260627_201455_policy_iter320_base_train/`
- `data/reports/backtests/20260627_201754_model_sweep_summary_1/`
- `data/reports/backtests/20260627_201806_model_sweep_summary/`
- `data/reports/backtests/20260627_201822_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_201822_model_timed_ev_2025-02/`
- `experiments/20260627_202929_policy_iter1280_base_train/`
- `data/reports/backtests/20260627_203101_model_sweep_summary/`
- `data/reports/backtests/20260627_203101_model_sweep_summary_1/`
- `data/reports/backtests/20260627_203117_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_203117_model_timed_ev_2025-02/`
- `experiments/20260627_203932_policy_iter80_p1_l1p2/`
- `experiments/20260627_204140_policy_iter320_p1_l1p2/`
- `experiments/20260627_205602_policy_iter1280_p1_l1p2/`
- `experiments/20260627_210612_policy_iter1280_lr001_p1_l1p2/`
- `data/reports/backtests/20260627_210812_model_sweep_summary/`
- `data/reports/backtests/20260627_210833_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_210833_model_timed_ev_2025-02/`
- `docs/reports/00008_2026-06-28_research_direction_review.md`
- `docs/trading_ml_generalization_principles.md`
- `docs/reports/00011_2026-06-28_generalization_principles_review.md`
- `docs/reports/00010_2026-06-28_trade_failure_analysis.md`
- `docs/reports/00012_2026-06-28_regime_cost_purge_controls.md`
- `docs/reports/00013_2026-06-28_regime_gate_experiment.md`
- `docs/reports/00014_2026-06-28_side_regime_ev_calibration.md`
- `docs/reports/00015_2026-06-28_train_oof_predictions_infra.md`
- `docs/reports/00017_2026-06-28_train_oof_calibration_loss120.md`
