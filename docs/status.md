# Current Status

最終更新: 2026-06-28 18:48 JST

## 現在の状態

データ取得・変換パイプラインは作成済み。

研究ドキュメント構造は作成済み。

バックテスト基盤とベースライン戦略は作成済み。

特徴量・教師ラベル生成パイプラインは作成済み。

entry quality を密に学習するための追加教師targetは実装済み。主datasetの再生成、HGB再学習、quality filter付きpolicy評価まで完了。

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

entry penalty + holding shrink小gridをvalidation 4foldで比較済み。`time_exit_penalty=6`, `loss_first_penalty=6`, `time_exit_holding_shrink=0.50`, max hold `720` はstrict eligibleで min pnl `85.1886` とentry penalty単独 `75.1682` を上回ったが、total pnlは `493.4848` でentry penalty単独 `531.6246` より低い。2024-12反証月では validation 2位の `time_exit_holding_shrink=0.25` が adjusted pnl `-159.0158`, profit factor `0.5211` でentry penalty単独 `-172.7944` より改善したが、NoTradeには大きく負ける。標準policyには昇格しない。次は保有中にprobabilityを再評価するdynamic / hazard-like exit policyを実装する。詳細は `docs/reports/00055_2026-06-28_entry_penalty_holding_shrink_combo.md`。

`docs/reports` の実験レポートは、`00001_YYYY-MM-DD_slug.md` の通し番号形式へ統一済み。番号はファイル更新時刻や `更新日時` ではなく、レポートファイル内の `日時: YYYY-MM-DD HH:MM JST` の昇順で決める。既存レポートの確認、再採番、直近レポート参照でも、ファイルシステムのmtimeではなくファイル内の `日時` を正とする。通し番号はその順序に由来する補助情報として扱う。各レポート冒頭には `日時` と `更新日時` を `YYYY-MM-DD HH:MM JST` 形式で置く。

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

1. raw fixed horizon + `score_mode=max` + `profit_barrier_miss_penalty=0.0` + `min_trade_quality=-inf` を現行基準にする。
2. selected-trade qualityのgroup平均gateと小型HGB gateは標準採用しない。診断基盤として残す。
3. holding cap付きexit-event candidateは、2024-12 holdout失敗を反証として扱い、現状では標準評価へ昇格しない。
4. combined regime gateはhard採用ではなく、candidate tie-break / failure analysisとして使う。
5. exit-event datasetを2025-02以降にも拡張し、候補固定後に複数blind月へ適用する。
6. side/entry calibrationを直接扱う。`best_side`, profit barrier miss, EV overestimateを教師信号またはcalibration targetにする。profit barrierは全体平均ではなくside別・bucket別actual hit rateとsupportを必ず確認する。
7. exit-event probability penalty、holding shrink単独、両者の小gridは標準採用しない。次は保有中にprobabilityを再評価するdynamic / hazard-like exitをholding cap付きpolicyと比較する。
8. `side-confidence-report` をより広いwalk-forward OOF予測へ適用し、representative smokeの過大確信が安定して出るか確認する。
9. side-confidence penalty tuningは、まずviable candidate上で試す。NoTradeに大きく負ける候補をside confidenceだけで救う方向には寄せない。
10. diagnostic gateとgroup-loss penaltyは、validation候補を全滅させない範囲でtie-breakとして使う。2025-07 smoke-likeの厳しい閾値や単月post-hocのpenalty採用は使わない。
11. profit-barrier probability単独のhard gate/global linear penalty探索は打ち切る。今後はdirection/sessionやcombined regimeのrisk penaltyと同時に扱う場合だけ再評価する。
12. 保有中にprobabilityを再評価して途中決済するdynamic / hazard-like exit policyを実装し、entry penalty + holding shrink comboと同じvalidation/2024-12反証月で比較する。
13. shared representationを持つ小型MLP/TCNでmulti-task学習を試す。

## 未決定事項

- M1 バックテストの約定価格を、次足 open にするか、より保守的な Bid/Ask 推定にするか。
- Tick を全期間取得するか、研究対象月の周辺だけ取得するか。
- 1 か月最適化の評価月を、固定月にするかランダム抽出にするか。
- エントリー/決済を独立モデルにするか、1 つの policy model にするか。
- 現行の profit 1.0 / loss 1.20 に加えて、明示的なスプレッドコストを標準評価へ入れるか。

## 直近の推奨作業

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
