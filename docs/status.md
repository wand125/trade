# Current Status

最終更新: 2026-06-28 JST

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

1. 2025-02 のshort失敗tradeを regime/session/entry timing/exit timing で分解する。
2. exit timing targetを fixed horizon、barrier time、hazard-like close probability へ拡張する。
3. profit barrierを0/1予測ではなく確率として保存し、閾値をcalibrateする。
4. calibration採用基準にentry数上限、fold間trade分布、side別/regime別direction accuracyを追加する。
5. train OOFを月単位またはwalk-forward OOFに細分化し、4ヶ月blocked OOF依存を確認する。
6. shared representationを持つ小型MLP/TCNでmulti-task学習を試す。
7. 追加holdout月を用意し、2024-12/2025-02に過剰適合しない評価へ移る。

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

トレードMLの汎化原則を `docs/trading_ml_generalization_principles.md` に整理し、現状レビューを `docs/reports/2026-06-28_generalization_principles_review.md` に作成した。現状は、NoTrade比較、月別評価、実行可能backtest、失敗trade analyzerは良い。一方で、purging/embargo、regime別標準評価、spread/slippage/delay感度、validationを見すぎない運用が不足している。

低LR1280モデルの失敗trade分析を `docs/reports/2026-06-28_trade_failure_analysis.md` に追加した。2024-12/2025-02では予測EVが実現PnLに対して平均約22ドル過大で、actual barrier miss、direction error、exit regretが損失の中心。`min_entry_rank=0.5` のfocused sweepは損失を抑えたがNoTradeには届かない。

汎化レビューの不足項目に対応し、regime feature/label、明示的なspread/slippage/execution delay、`model-cost-sensitivity`、学習時のpurged/embargo splitを実装した。詳細は `docs/reports/2026-06-28_regime_cost_purge_controls.md`。

1.0/1.2 datasetをregime列込みで再生成し、purge有効・embargo 24hでHGB 80iter policy modelを再学習した。validation 10 trades/fold条件では全foldプラス候補が出たが、fixed testは 2024-12 `-35.7010`、2025-02 `-47.6716` でNoTradeに負けた。regime分析では両testとも `low_vol` に集中し、2025-02は `asia` と `rollover` で損失が大きい。次はregime gateとside/regime別calibrationを優先する。

hard regime gateを `model-policy` / `model-sweep` に追加した。`asia`、`rollover`、`asia,rollover` をvalidationで比較したところ、validation上はeligible候補が残ったが、fixed testでは安定しなかった。`asia,rollover` を前回候補に足すと 2024-12 `+5.8384`、2025-02 `+24.0720` まで損失回避できたが、7 trades / 3 trades と薄すぎる。hard gateは採用policyではなく診断・ablation用とし、次はside/regime別EV calibrationとsoft threshold調整へ進む。

side/regime別EV calibrationを追加した。validation内OOFで各月をholdoutし、`volatility_regime,session_regime` ごとにEVを補正する。OOF validationでは強い候補が出たが、fixed testでは悪化した。offset型のtop OOF候補は 2024-12 `-185.8364`、2025-02 `-65.1476`、保守候補でも 2024-12 `-149.2616`、2025-02 `-10.7646`。raw EVの前回候補より悪く、calibrationは採用不可。次はvalidation 4ヶ月だけで補正するのではなく、train期間OOF predictionsを作ってcalibration fit月数を増やすか、exit timing target改善へ進む。

train期間OOF predictions生成基盤を追加した。`trade_data.modeling oof` で、指定月をfoldごとにholdoutし、その月を学習に使っていないHGB予測を `predictions_oof.parquet` として保存できる。軽量smoke runは `experiments/20260627_222746_oof_smoke_policy/` で完了。次は HGB 80iter regime/purge v2 と同じtrain monthsに対して本番OOFを実行し、side/regime calibrationのfitデータを増やす。

train期間OOFを4ヶ月holdout単位で生成し、side/regime calibrationの各validation foldへ `train OOF + 他validation月` をfitデータとして追加できるようにした。あわせて評価倍率を profit 1.0 / loss 1.20 に統一し、`trade_data.dataset` と `trade_data.backtest` のデフォルトも 1.0 / 1.20 に更新した。shrink 0.65 calibration のvalidation top-min候補は 4fold全てプラス、min pnl `41.1354`、min trades `10` だったが、fixed testは 2024-12 `+18.8306`、2025-02 `-44.5990`。offset calibrationはvalidation平均が高いが、fixed testは 2024-12 `-63.2266`、2025-02 `-44.3740`。loss 1.20統一で数値は改善したが、NoTradeを安定して超える状態ではない。次は2025-02のshort失敗trade分解とexit timing target改善を優先する。

calibrated EV列を指定したtrade failure分析に修正し、shrink065 top-minを再分析した。2025-02は 12 trades / adjusted pnl `-44.5990`、direction error rate `0.7500`、predicted side error rate `0.7500`。実績best sideがshortだった8 tradesは全てlongで入り、唯一のshortは `asia/up/low_vol` で大きく外した。問題は「shortが多すぎる」ではなく、calibrated EVの方向選択が未知月で壊れていること。あわせて固定保有 60/240/720 分のlong/short adjusted pnl targetを追加した。次は固定horizon target入りdatasetを再生成し、exit policyとside/regime安全marginを検証する。

## 直近の実験

- `docs/reports/2026-06-28_calibrated_trade_failure_exit_targets.md`
- `docs/reports/2026-06-28_baseline_backtest_2025-01.md`
- `data/reports/backtests/20260627_165623_benchmark_2025-01/`
- `data/processed/datasets/xauusd_m1/xauusd_m1_2025-01_h24_edge15.summary.json`
- `docs/decisions/0002_multitask_targets.md`
- `experiments/20260627_171852_hgb_multitask_edge15/`
- `docs/reports/2026-06-28_hgb_multitask_initial.md`
- `data/reports/backtests/20260627_172832_model_sweep_2024-07/`
- `data/reports/backtests/20260627_172849_model_stateful_ev_2025-01/`
- `docs/reports/2026-06-28_executable_model_policy_2025-01.md`
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
- `docs/reports/2026-06-28_mixed_regime_weighted_training.md`
- `experiments/20260627_185200_hgb_multitask_edge15/`
- `data/reports/backtests/20260627_190009_model_sweep_summary/`
- `data/reports/backtests/20260627_190023_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_190023_model_timed_ev_2025-02/`
- `docs/reports/2026-06-28_dense_entry_quality_targets.md`
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
- `docs/reports/2026-06-28_training_time_and_generalization.md`
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
- `docs/reports/2026-06-28_research_direction_review.md`
- `docs/trading_ml_generalization_principles.md`
- `docs/reports/2026-06-28_generalization_principles_review.md`
- `docs/reports/2026-06-28_trade_failure_analysis.md`
- `docs/reports/2026-06-28_regime_cost_purge_controls.md`
- `docs/reports/2026-06-28_regime_gate_experiment.md`
- `docs/reports/2026-06-28_side_regime_ev_calibration.md`
- `docs/reports/2026-06-28_train_oof_predictions_infra.md`
- `docs/reports/2026-06-28_train_oof_calibration_loss120.md`
