# Next-bar direction research

M1、M5、M15、M30 の「次に確定する1本」の方向と、その予測の信頼度を研究する独立手法。
`entry_ev` の売買期待値・決済最適化とはモデルも評価も分離し、共通の UTC M1 OHLC データだけを再利用する。

## 目的と境界

- 各時間足を別々の二値分類問題として扱う。
- 判定時点までに確定済みの足だけを特徴量に使う。
- 生の `open/high/low/close` 価格水準はモデルへ渡さない。リターン、比率、rolling統計、指標へ変換し、価格水準の暗記を防ぐ。
- 正解は、直後の連続した完成足について `close > open` なら up、それ以外なら down とする。
- `abs(close - open) <= flat_tolerance` は曖昧足として学習・評価から除外する。既定値は 0。
- 予測信頼度は、学習期間より後の calibration 期間で標準のPlatt calibrationを適用した「予測方向が正しい確率」とする。
- この段階では売買損益を最適化しない。方向予測が検証できた後に、別の policy 層で複数時間足の確率、コスト、見送り、リスクを売買へ変換する。

## 時系列分割

```text
train           calibration             test
モデル学習       確率の校正                完全未使用の最終評価
```

境界をまたいで次足ラベルが未来側へ入る行は除外する。モデルの early stopping は内部ランダム分割を避けるため無効にしている。最終判断は test の一回の数字ではなく、次段階で expanding walk-forward を複数窓実行して行う。

## 実行

リポジトリルートから実行する。

```bash
uv run python methods/next_bar/scripts/run.py train-evaluate \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --output-dir experiments/next_bar/baseline_01 \
  --timeframes 1,5,15,30 \
  --train-end 2023-01-01 \
  --calibration-end 2024-01-01 \
  --test-end 2026-01-01
```

日付を省略した場合は、全期間を時刻順に 60% / 20% / 20% に分ける。研究結果を比較するときは明示日付を使う。

学習成果物:

- `manifest.json`: モデル一覧と特徴量
- `metrics.json`: 時間足別の精度・校正・信頼度別カバレッジ
- `m*_model.joblib`: モデルと確率校正器
- `m*_test_predictions.parquet`: 完全未使用期間の行単位予測

最新の完成足から推論する:

```bash
uv run python methods/next_bar/scripts/run.py predict-latest \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --model-dir experiments/next_bar/baseline_01 \
  --context-policy methods/next_bar/config/context_policy_v1.json \
  --output runtime/latest_next_bar_predictions.json
```

context policyは方向予測を変更せず、検証済みcontext以外を `prediction_eligible=false` として見送る。これは売買policyではなく、次足予測のaccuracy/coverageを管理するabstention層である。

walk-forwardのout-of-sample予測から採用条件を最適化する:

```bash
uv run python methods/next_bar/scripts/run.py optimize-policy \
  --predictions-dir experiments/next_bar/walk_forward_001 \
  --output methods/next_bar/config/optimized_policy_v1.json \
  --min-rows 500 \
  --min-coverage 0.01 \
  --coverage-power 0.5
```

最適化する評価関数は次の通り。

```text
selection_score = coverage^coverage_power
                  * (Wilson accuracy lower bound - break-even accuracy)
```

既定値はcoverage power 0.5、break-even 0.50、Wilson z 1.96。`coverage-power=1` は全予測機会あたりの正答超過を重視し、0に近づけるほど狭い高品質条件を重視する。候補はconfidence閾値、予測方向、volatility regime、UTC hour/6時間帯から選ぶ。最低件数と最低coverageを満たさない候補は除外する。

条件選択のリークを避けるため、レポートには「過去のout-of-sample foldで条件選択し、次foldだけで評価」するnested chronological validationを含める。全foldから作る最終ruleのreference値より、nested summaryを実運用品質の判断に優先する。

複数の expanding walk-forward 窓を実行する:

```bash
uv run python methods/next_bar/scripts/run.py walk-forward \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --output-dir experiments/next_bar/walk_forward_001 \
  --fold wf2022,2021-01-01,2022-01-01,2023-01-01 \
  --fold wf2023,2022-01-01,2023-01-01,2024-01-01 \
  --fold wf2024,2023-01-01,2024-01-01,2025-01-01 \
  --fold wf2025,2024-01-01,2025-01-01,2026-01-01
```

各foldは、それ以前をtrain、次の期間を確率校正、その次をtestにする。出力にはfold別・全fold合算の精度と、月、UTC hour、volatility regime、実際の方向別診断を含む。

固定長training windowの再現には `--train-window-days` を使う。0は全履歴のexpanding training。M15で1095日の固定3年windowを試した結果、全体・confirmation・高信頼selection scoreが悪化したため標準設定は0のままとする。

同じFull Pathのexpanding/固定3年モデル間disagreementを1σ下側edgeへ変換するtemporal uncertaintyも検証した。0.515 accuracyは上がったがcoverageがほぼ半減し、selection scoreとBrier/log loss/ECEが悪化した。固定3年モデルの情報不足を測る結果になったため再現専用とし、window・penalty・weightを履歴内再探索しない。

非線形なisotonic確率校正は `--probability-calibration isotonic` で再現できる。M15の同一7foldではBrier、log loss、ECEとconfirmation accuracyが悪化し、高confidenceを大幅に過大評価したため、標準は `--probability-calibration platt` のままとする。

単調制約付きbeta calibrationは `--probability-calibration beta` で再現できる。`log(p)` と `-log(1-p)` の非負係数を各foldのcalibration期間だけで学習する。M15の同一7foldではBrier/log lossがdevelopment・confirmationの両方で悪化し、confidence 0.55のconfirmation selection scoreも低下したため棄却した。実験再現用に限り、標準はPlattのままとする。

方向境界を維持するtemperature scalingは `--probability-calibration temperature` で再現できる。各foldのcalibration期間だけで `sigmoid(logit(p) / T)` の正の温度を学習する。M15の同一7foldではdevelopmentのBrier/log lossだけ改善したがconfirmationで悪化した。development選択0.52はconfirmationのaccuracy・coverage・selection scoreがすべて低下し、固定0.55もIntrabar Structure precision championよりcoverage-aware scoreが低いため棄却した。標準はPlattのままとする。

次足実体を判定時ATRで正規化してtrain sample weightへ使う方式は `--train-weighting body_atr` で再現できる。未来の次足実体は教師重みにだけ使用し、入力特徴・calibration・test推論には使用しない。weighted HGB単体は方向精度が悪化したため不採用だが、HGB方向を維持した25% confidence blendは `config/m15_body_atr_weighted_confidence_candidate_v1.json` のconfidence 0.54精度重視候補として固定した。標準学習は `--train-weighting uniform` のままである。

方向0/1教師と全行を維持しつつ次足の方向明瞭度をsample weightへ使う場合は `--train-weighting directional_clarity` を指定する。重みは平均1へ正規化した `0.5 + abs(next body) / next range` で、未来rangeは特徴へ入れない。M15方向維持0.525はdevelopment/confirmationを改善したが、Signed-body Quantile/Clear-bodyよりaccuracy・selection score・fold安定性が低いため再現専用とする。

明確な次足だけを教師に残す方式は `--train-target-filter body_atr_upper_half` で再現できる。各foldのtrain内 `next_bar_body_atr` 中央値以上だけで方向HGBを学習し、calibration/testは全件を保つ。単体方向モデルは不採用だが、方向維持型25% blendのconfidence 0.525はaccuracy・selection scoreを7/7 foldで改善したため、`config/m15_body_atr_upper_half_confidence_candidate_v1.json` の中coverage候補に固定した。標準は `--train-target-filter all` のままである。

次足の実体がhigh-low rangeを占める比率で方向の明瞭さを選ぶ場合は `--train-target-filter body_range_upper_half` を使う。各foldのtrain内 `abs(next close - next open) / (next high - next low)` 中央値以上だけで学習し、値は教師選択専用で特徴へ入れない。M15方向維持0.53はBrier/log lossを7/7 fold改善したが、developmentのselection score改善がconfirmationで反転し、Distribution Shape/Extra Trees 0.53を上回らないため再現専用とする。

全教師を残し、次足実体/ATRが小さいほど教師確率を0.5へ近づけるbounded soft labelは `--model-type body_atr_soft_hgb` で再現できる。固定式 `0.5 + sign * 0.5 * tanh(body/ATR)` をHGB回帰する。方向維持型0.525はaccuracyを7/7 foldで改善したが、coverage-aware scoreと確率品質のfold安定性がclear-body 0.525より低いため採用せず、softening関数の履歴内再探索も行わない。

次足の方向と実体大小を同時分類する場合は `--model-type body_multiclass_hgb` を使う。各foldのsampled train内 `next_bar_body_atr` 中央値でdown-large/down-small/up-small/up-largeへ分け、up側2クラスの確率を合算して後続期間でPlatt校正する。方向維持型0.525はaccuracy・selection scoreを7/7 foldで改善したため `config/m15_body_multiclass_confidence_shadow_v1.json` に固定したが、同じ教師情報のclear-body 0.525より全期間の目的関数とproper scoreが低いためshadowに限定する。

加工特徴candidateを比較する場合は、同じfoldへ `--feature-set enhanced_manual` を追加する。追加されるのは方向系列、実体/ATR、rolling up比率、trend/volatility比、volatility/ATR比、return autocorrelation/skew、EMA差/ATRであり、生価格水準は含まれない。

トレンド強度と相場構造を定常加工する場合は `--feature-set trend_structure` を使う。DI/ADX、ATR正規化MACD、ATR/volatility compression、短長実現volatility balance、方向entropyの11列を追加し、raw価格水準は含めない。M15単体と通常方向blendは不採用。方向維持型25% blendのconfidence 0.525はdevelopment/confirmationの両方でselection scoreを改善したが、既存clear-body 0.525よりaccuracyと評価関数が低く、confirmation Brier/log lossも改善しないためforward configは発行しない。

完成足間の変動状態遷移を使う場合は `--feature-set volatility_state` を指定する。vol-of-vol、volatility加速度、range clustering/中央値乖離/圧縮継続、bipower jump、Parkinson/Garman–Klass対close分散balanceの11列を追加する。単体・通常方向blendはconfirmationで悪化し、方向維持0.525もscore 4/7、既存Signed-body Quantile/Clear-bodyを下回ったため再現専用とする。

直近経路の継続性を定常加工する場合は `--feature-set path_persistence` を使う。符号付きefficiency、variance ratio、return autocorrelation、方向転換率、方向別transition persistence、符号付きstreakの14列を追加する。完全無変動・片方向窓の0/0は「持続性の証拠なし」の0へ定義し、flat系列の全列有限0とbaselineとの行整合をテストする。M15の方向維持型25% confidence 0.525は既存clear-body/signed-body quantileを超えず再現専用である。一方、定義を変えずM1へ移植した通常25%方向blendはaccuracyを7/7fold、開発・確認、UTC日bootstrapで改善したため `config/m1_path_persistence_direction_candidate_v1.json` のparallel forward候補に固定した。M1の0.51 confidence laneは確認3/3foldで反転したため使わない。

経路の加速・減速をマルチスケール加工する場合は `--feature-set haar_multiscale` を使う。4/8/16/32本窓の前半対後半について、標準化return差、absolute-return構成差、方向比率差の12特徴を追加する。方向維持型0.525はdevelopmentで改善したがconfirmationのaccuracyとselection scoreが悪化したため再現専用とし、forward configは発行しない。

同じ曜日×UTC時の通常値動きからの乖離を使う場合は `--feature-set session_relative` を使う。現在足を除く過去32本からreturn/body z-score、absolute-return/range ratio、方向biasの5特徴を作る。方向維持型0.525はbaselineをdevelopment/confirmationと5/7 foldで改善したため `config/m15_session_relative_confidence_shadow_v1.json` に固定した。ただしclear-body 0.525よりdevelopment、全体、直接fold安定性、確率品質が低いため研究shadowに限定する。

直近8本の順序を保持したATR正規化特徴は `--feature-set sequence_manual` で再現できる。ただしM15の7fold比較でaccuracy、Brier、log loss、ECEがすべて悪化したため、現在は研究再現専用で採用候補ではない。

直近16本×5加工系列を小型の因果TCNで学ぶ場合は `--feature-set tcn_sequence --model-type tcn` を使う。channelはATR正規化return/body/range、中心化close location、ATR正規化wick balanceで、生価格水準は含まない。各foldのtrainだけでchannel標準化し、2層1,073 parameterを8 epoch学習する。単体と通常方向blendは不採用。方向維持型25% blendのconfidence 0.52は6/7 foldでselection scoreを改善したが、同じ広coverage目的のsigned-body候補よりscoreが低いため `config/m15_tcn_confidence_shadow_v1.json` のshadowに限定する。

同じ16本×5加工系列をself-attentionで比較する場合は `--feature-set tcn_sequence --model-type causal_transformer` を使う。learned position、dimension 16、4-head、encoder 1層、feed-forward 32、dropout 0の2,625 parameterを8 epoch学習する。単体と通常方向blendは不採用。方向維持型25% blendのconfidence 0.52はselective accuracyを6/7 foldで改善したが、confirmation Brier/log lossとproper fold再現性が悪く、既存signed-body 0.52よりselection scoreも低いためforward configは発行しない。

完成M15内部のM1経路を加工する特徴は `--feature-set intrabar_manual` で再現できる。足内return分散、上昇比率、実体方向効率、実体集中度、序盤/終盤動向の7列を追加し、未来M1やraw価格水準は使わない。単体方向モデルはconfirmationで悪化したため不採用。HGB方向を維持した25% confidence blendは `config/m15_intrabar_confidence_candidate_v1.json` のconfidence 0.55高精度候補である。

足内の極値時刻と経路形状まで使う場合は `--feature-set intrabar_structure` を使う。既存7特徴へ高値/安値位置、極値順序、M1方向転換率、経路効率、実現分散/range、最大runup/drawdownの8加工特徴を加える。単体方向モデルはconfirmationで悪化したため不採用だが、方向維持型25% blendはconfidence 0.55で全7foldのaccuracyを改善し、`config/m15_intrabar_structure_confidence_candidate_v1.json` にforward候補として固定した。既存intrabar候補との選択・stackはfresh期間まで行わない。

完成した上位足内の途中trajectoryまで使う場合は `--feature-set intrabar_profile` を使う。既存intrabar structureへ、上位足rangeで正規化した20/40/60/80%地点のM1 close level、始値から最終終値までの直線pathとの差、足内全地点の平均/RMS/上下最大偏差の12特徴を追加する。M15の方向維持型25% blend 0.515は `config/m15_intrabar_profile_confidence_candidate_v1.json` のbroad coverage候補で、candidate registryのdevelopment目的関数championである。定義を変更しないM5移植も0.515でaccuracy・selection scoreを6/7 fold、Brier/log loss/ECEを7/7 fold改善したため `config/m5_intrabar_profile_confidence_candidate_v1.json` に固定した。M30はproper scoreだけ改善し高信頼laneが悪化したため `config/m30_intrabar_profile_calibration_shadow_v1.json` の校正診断shadowに限定する。M1は独立した下位足経路がないため対象外である。

M15内15本のM1 close経路を順序ごと保持する場合は `--feature-set intrabar_full_path` を使う。Profileが持つ3/15、6/15、9/15、12/15地点に、欠けている11地点をM15 rangeで正規化して追加する。単体は親Profileにaccuracy 6/7 fold勝ったが正式baselineのconfirmationを上積みできず、通常方向blendも悪化したため方向用途には使わない。baseline方向を維持する25% blendの固定0.53 laneはdevelopment/confirmation score、baseline比accuracy 7/7、Brier/log loss 7/7 foldを改善し、Distribution Shapeにもaccuracy/score各5/7勝ったため `config/m15_intrabar_full_path_confidence_candidate_v1.json` に固定した。candidate registryのselective履歴championだが、完全未使用期間まではauthoritative confidence・odds・売買policyを置換しない。

Full Pathの15地点を時間×正規化close経路としてまとめる場合は `--feature-set intrabar_path_signature` を使う。Chen積でlevel 2 signed areaとlevel 3の2 bracket、計3列をFull Pathへ追加する。baseline方向と0.53 confidenceは改善したが、親Full Path 0.53との全期間scoreは実質同値、confirmation scoreは悪化し、直接年別scoreも3/7だった。再現専用とし、signature level・subset・weight・閾値を同じ履歴で再探索しない。

Full Pathの順序とVolatility Shapeの変動集中を同時に使う固定unionは `--feature-set intrabar_full_path_volatility_shape` で再現できる。52 intrabar・全90特徴になる。単体方向はVolatility Shapeに0/7、方向維持0.525 confidenceも親2候補に各3/7、Signed-body Quantileに1/7、Clear-bodyに2/7しか勝てなかった。Brier/log lossは改善したが高信頼帯の主評価関数を上積みできないため再現専用とし、forward configは発行しない。

完成上位足内のM1買い／売り圧力proxyを使う場合は `--feature-set intrabar_pressure` を使う。Intrabar Profileへ、M1 close-locationの平均/分散/序盤/終盤、range-weighted close-location、signed range、wick/body pressure、両者の乖離、方向一致率の11定常特徴を追加する。M15単体とconfidence用途は不採用。baseline 75% + Pressure 25%の通常方向blendはdevelopment/confirmationの両方、accuracy 5/7、Brier/log loss 7/7 foldを改善したため `config/m15_intrabar_pressure_direction_candidate_v1.json` のparallel forward候補に固定した。paired p=0.224なので現行方向モデルは置換しない。

同じPressure定義と25% weightのM5移植もdevelopment/confirmationの方向accuracy、accuracy 5/7、Brier/log loss 7/7 foldを改善し、親Profile方向blendに6/7 fold勝ったため `config/m5_intrabar_pressure_direction_candidate_v1.json` のparallel forward候補に固定した。paired p=0.180なので現行方向は置換しない。Pressure 0.515 confidenceは既存Profileと95%重複してfold比較3/7、両者の固定平均もconfirmation scoreが悪化したため採用しない。

M30 Pressureの単体・通常方向blendは悪化したため方向用途には使わない。方向維持版のdevelopment選択0.52はconfirmationでもaccuracy/selection scoreを改善し、accuracy 7/7、score 6/7 fold改善したため `config/m30_intrabar_pressure_confidence_candidate_v1.json` のselective forward候補に固定した。nested model confidenceもbaselineよりBrier/log loss/ECEを改善したが、親Profileのconfirmation scoreが高く、runtime odds gateも未達なのでauthoritative confidence/fair oddsへは昇格しない。

完成M15内で値幅とclose-to-close分散がどこへ集中したかを使う場合は `--feature-set intrabar_volatility_shape` を使う。Intrabar Profileへ、集中度、上位3本構成比、時間重心、序盤・終盤1/3構成比など14定常特徴を追加する。単体方向モデルはbaselineをdevelopment/confirmationと6/7 foldで改善し、親Profile単体にも5/7 fold、paired p=0.0135で勝ったため `config/m15_intrabar_volatility_shape_direction_candidate_v1.json` のparallel forward候補に固定した。通常25% blendはconfirmationで悪化し、confidenceはProfile 0.515を上回らないため採用しない。

同じVolatility Shape定義をM5/M30へ移植したが、M5単体・通常blendはconfirmation方向accuracyが悪化し、0.515 confidenceもProfileにaccuracy/score各1/7しか勝てなかった。M30も単体・通常blendの方向accuracyが両期間で悪化し、0.52 confidenceはconfirmation scoreとcoverageが低下してPressureに2/7だった。M5/M30は再現成果物だけを残し、時間足別のsubset・weight・閾値を履歴へ合わせて再探索しない。

M15内M1変動をupside/downside semivariance、方向別集中度・時間重心、bipower/jump、最大jump除外後の連続成分へ分ける場合は `--feature-set intrabar_signed_variation` を使う。親Volatility Shapeへ14特徴を追加する。単体はbaselineをdevelopment/confirmationで上回ったが親Shapeを両期間・accuracy/proper score各2/7で下回り、通常blendもconfirmationで悪化した。方向維持0.525はbaseline比accuracy/score 5/7、Brier/log loss 6/7改善したが、clear-bodyとsigned-body quantileの既存0.525候補を下回るため再現専用とする。

Volatility Shapeを固定Extra Treesで学ぶ実験では、加工なしExtra Treesより方向accuracyを5/7 fold、全体+0.134pt改善したが、正式baselineとHGB Shapeにconfirmationで敗れた。方向維持confidenceもaggregate proper scoreは改善した一方、加工なしExtra Treesとの直接比較で0.525はaccuracy/score各2/7、既存採用0.53は各1/7しか勝てなかった。Shape × Extra Treesは再現専用とし、HGB Shape方向候補とbaseline-feature Extra Trees 0.53 confidence候補を維持する。

同じ加工特徴を2層MLPで比較する場合は `--model-type mlp --max-iter 50` を使う。MLPにもOHLC価格水準は渡さず、HGBと同じ加工済みfeature matrixを標準化して入力する。

同じbaseline加工特徴をL2 logistic regressionで比較する場合は `--model-type logistic --logistic-c 0.10` を使う。方向モデルとしては不採用だが、異なる確率形状をconfidence ensembleへ利用できる。

同じ加工特徴をランダム化した多数の独立木で比較する場合は、`--model-type extra_trees --extra-trees-estimators 200 --extra-trees-max-depth 12 --extra-trees-min-samples-leaf 50 --extra-trees-max-features 0.75` を使う。Extra Trees単体はM15方向モデルとして不採用だが、HGBと異なる誤りをconfidence ensembleへ利用できる。

XGBoostを比較する場合は `--model-type xgboost` を使う。300 trees、depth 4、learning rate 0.03、min child weight 20、row/column subsample 0.8、L2 5を固定し、hist tree methodで学習する。通常教師はconfirmationで悪化したため不採用。`--train-target-filter body_atr_upper_half` との方向維持型0.525は6/7 foldでaccuracy・selection scoreを改善したが、既存clear-body HGBがconfirmation、全体、確率品質で上回るためforward configは発行しない。

次足の方向だけでなく実体値幅も教師にする場合は `--model-type signed_body_hgb` を使う。次足実体を判定時ATRで正規化し、符号付き `asinh` 連続値をHGB回帰する。未来値幅は教師だけに使用し、特徴には入れない。単体方向モデルは不採用だが、方向維持型25% blendは `config/m15_signed_body_confidence_candidate_v1.json` のconfidence 0.52広coverage候補である。

次足方向と足自体の方向明瞭度を全教師から同時に学ぶ場合は `--model-type signed_clarity_hgb` を使う。教師は−1〜+1の `next_bar_body / next_bar_range` で、未来rangeは特徴へ入れない。M15の通常25%方向blendと方向維持0.525 confidenceはdevelopment/confirmationをともに改善したが、方向はPressure/Volatility Shape、confidenceはSigned-body Quantile/Clear-bodyを下回るため再現専用とする。

同じ連続教師の不確実性幅まで使う場合は `--model-type signed_body_quantile_hgb` を使う。25/50/75%分位HGBから `q50 / abs(q75 - q25)` を作り、後続期間で方向確率へ校正する。単体方向モデルは不採用。方向維持型25% blendのconfidence 0.525は `config/m15_signed_body_quantile_confidence_candidate_v1.json` の中coverage選別候補だが、confirmation ECEが僅かに悪化したためfair oddsには使わない。

判定時点の `volatility_20` でlow/normal/high専用HGBへ分ける場合は `--model-type regime_hgb` を使う。分位境界は各foldのtrainだけで決め、calibration/testでは固定する。M15の7foldでは単体方向精度と通常blendのconfirmation精度が悪化し、高信頼selection scoreも全thresholdでbaselineを下回ったため採用しない。方向維持型25% blendはaggregate ECEだけが強く改善したので `config/m15_regime_hgb_confidence_shadow_v1.json` の校正診断shadowに限定する。

2つの同一target予測を固定weightでブレンドする:

```bash
uv run python methods/next_bar/scripts/ensemble.py \
  --baseline-dir experiments/next_bar/walk_forward_001 \
  --candidate-dir experiments/next_bar/walk_forward_enhanced_manual_001 \
  --output-dir experiments/next_bar/ensemble_walk_forward_001 \
  --timeframes 15 \
  --candidate-weight 0.25
```

複数の連続したbaseline成果物をまとめ、baseline方向を変えずconfidence edgeだけをblendする場合:

```bash
uv run python methods/next_bar/scripts/ensemble.py \
  --baseline-dir experiments/next_bar/context_confirmation_001 \
  --baseline-dir experiments/next_bar/walk_forward_001 \
  --candidate-dir experiments/next_bar/walk_forward_logistic_001 \
  --output-dir experiments/next_bar/logistic_confidence_blend_001 \
  --timeframes 15 \
  --candidate-weight 0.25 \
  --preserve-baseline-direction
```

`--preserve-baseline-direction` はcandidateがbaseline方向を否定した時に、その不一致を反対方向の強いconfidenceへ変換せず、confidenceを0.50付近へ落とす。logistic版は `config/m15_logistic_confidence_blend_candidate_v1.json` の確率校正候補。Extra Trees版は `config/m15_extra_trees_confidence_blend_candidate_v1.json` のconfidence 0.53以上high-confidence採用候補であり、どちらもauthoritative confidenceはまだ置換しない。

複数モデルを等重みで集約し、baseline方向へ揃えた確率edgeの平均と分散をconfidenceへ加工する:

```bash
uv run python methods/next_bar/scripts/disagreement_ensemble.py \
  --baseline-dir experiments/next_bar/context_confirmation_001 \
  --baseline-dir experiments/next_bar/walk_forward_001 \
  --candidate-dir experiments/next_bar/walk_forward_body_atr_upper_half_001 \
  --candidate-dir experiments/next_bar/walk_forward_extra_trees_001 \
  --candidate-dir experiments/next_bar/walk_forward_signed_body_hgb_001 \
  --candidate-dir experiments/next_bar/walk_forward_intrabar_structure_001 \
  --timeframe 15 \
  --uncertainty-penalty 0 \
  --preserve-baseline-direction \
  --output-dir experiments/next_bar/disagreement_mean_direction_preserved_001
```

confidence edgeは `mean(baseline-aligned edge) - penalty * population std` の0以上部分である。1 sigma版はdevelopmentで悪化したため棄却した。penalty 0の平均edge版は0.515 laneと確率品質をdevelopment/confirmationの両方で改善したが、結果確認後のablationで既存clear-body候補よりselection scoreが低いため `config/m15_disagreement_confidence_shadow_v1.json` の研究shadowに限定する。

直近の確定済みOOS成績からモデルweightを因果的に更新する:

```bash
uv run python methods/next_bar/scripts/online_ensemble.py \
  --baseline-dir experiments/next_bar/context_confirmation_001 \
  --baseline-dir experiments/next_bar/walk_forward_001 \
  --candidate-dir experiments/next_bar/walk_forward_body_atr_upper_half_001 \
  --candidate-dir experiments/next_bar/walk_forward_extra_trees_001 \
  --candidate-dir experiments/next_bar/walk_forward_signed_body_hgb_001 \
  --candidate-dir experiments/next_bar/walk_forward_intrabar_structure_001 \
  --timeframe 15 \
  --history-rows 2000 \
  --preserve-baseline-direction \
  --output-dir experiments/next_bar/online_logloss_2000_direction_preserved_001
```

各decisionでは、その時刻までにtargetが確定した直近2,000件のbinary log lossだけから `weight ∝ exp(-loss sum)` を計算する。0.515 laneはbaselineをdevelopment/confirmationの両方で改善したが、固定等重みより確率品質が悪く、signed-body 0.52よりconfirmation selection scoreが低いため再現実験専用とする。窓長や学習率は同じ履歴へ合わせて再探索しない。

複数expertのweightを過去OOS foldだけから学習するchronological stacking:

```bash
uv run python methods/next_bar/scripts/chronological_stacking.py \
  --baseline-dir experiments/next_bar/context_confirmation_001 \
  --baseline-dir experiments/next_bar/walk_forward_001 \
  --expert clear_body=experiments/next_bar/walk_forward_body_atr_upper_half_001 \
  --expert extra_trees=experiments/next_bar/walk_forward_extra_trees_001 \
  --expert signed_body=experiments/next_bar/walk_forward_signed_body_hgb_001 \
  --expert intrabar_structure=experiments/next_bar/walk_forward_intrabar_structure_001 \
  --regularization-c 0.10 \
  --stack-weight 0.25 \
  --preserve-baseline-direction \
  --output-dir experiments/next_bar/chronological_stacking_direction_preserved_001
```

各test foldでは、それ以前のexpert OOS予測だけで標準化L2 logisticを学習する。過去OOSのない最初のfoldはbaselineへfallbackする。固定5モデルではstack単体と通常方向blendがconfirmationで悪化し、方向維持版もdevelopment選択0.53がconfirmationでaccuracy・coverage・selection scoreをすべて悪化させたため再現専用とする。regularization、expert subset、stack weightを同じ履歴へ合わせて再探索しない。

candidateを同じdevelopment/confirmation規則で比較し、結果JSONを保存する:

```bash
uv run python methods/next_bar/scripts/analyze_candidate.py \
  --baseline-dir experiments/next_bar/context_confirmation_001 \
  --baseline-dir experiments/next_bar/walk_forward_001 \
  --single-dir experiments/next_bar/walk_forward_candidate_001 \
  --normal-blend-dir experiments/next_bar/ensemble_candidate_25_001 \
  --confidence-blend-dir experiments/next_bar/candidate_confidence_blend_001 \
  --output experiments/next_bar/candidate_analysis.json
```

既定では2020〜2023をdevelopment、2024〜2026途中をconfirmationとし、0.515〜0.60の固定gridからdevelopment selection score最大の閾値を一度だけ選ぶ。

発行済みM15 confidence候補を固定閾値のまま一括監査する:

```bash
uv run python methods/next_bar/scripts/build_candidate_registry.py \
  --baseline-dir experiments/next_bar/context_confirmation_001 \
  --baseline-dir experiments/next_bar/walk_forward_001 \
  --output methods/next_bar/config/m15_candidate_registry_v1.json
```

台帳は16候補の145,140 OOS行を再読込してkey整列を検証し、development/confirmation/allのcoverage、accuracy、Wilson下限、selection score、Brier/log loss/ECE、fold安定性を同一定義で再計算する。championはdevelopment目的関数だけでbroad・balanced・selective・precisionの各役割から選び、confirmationは監査にしか使わない。目的関数首位とは別にaccuracy leaderとPareto challengerも保持する。固定閾値がconfigに明示されていない候補はエラーにし、実行時の閾値再探索は行わない。

派生candidateが親モデルへ本当に増分edgeを持つか、同一閾値で直接比較する:

```bash
uv run python methods/next_bar/scripts/compare_fixed_candidates.py \
  --first-dir experiments/next_bar/intrabar_profile_confidence_blend_001 \
  --first-name profile \
  --second-dir experiments/next_bar/intrabar_structure_confidence_blend_001 \
  --second-name structure \
  --threshold 0.515 \
  --output experiments/next_bar/intrabar_profile_vs_structure_0515_analysis.json
```

期間別の確率品質・lane指標に加え、選択集合のJaccard、片側だけが選んだ行数、fold別accuracy/selection score勝敗を出力する。ProfileはStructureへscore 7/7、accuracy 6/7 foldで勝ち、同じ広coverage閾値での増分効果を確認した。

2つのconfidence候補を固定した非重複帯・累積閾値で比較し、信頼度をオッズとして監査する:

```bash
uv run python methods/next_bar/scripts/compare_confidence_reliability.py \
  --first-dir experiments/next_bar/baseline_m5_complete_001 \
  --first-name baseline \
  --second-dir experiments/next_bar/intrabar_profile_m5_confidence_blend_001 \
  --second-name profile \
  --timeframe 5 \
  --output experiments/next_bar/intrabar_profile_m5_reliability_analysis.json
```

既定帯は0.500/0.515/0.525/0.535/0.550/0.575/0.600/1.000で、development/confirmationごとにaccuracy、mean confidence、calibration gap、Wilson上下限、局所整合、edge下限、帯別単調性を出す。M5 Profileはconfirmationの0.515〜0.550で局所整合とedge下限を満たしたが、development 0.515は軽い過信だったため `config/m5_intrabar_profile_odds_shadow_v1.json` のforward shadowに限定する。

保存済みbaseline/Profile artifactからOOSと同じ固定blendを最新推論する:

```bash
uv run python methods/next_bar/scripts/predict_latest_ensemble.py \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --baseline-model-dir experiments/next_bar/baseline_m5_latest_artifact_001 \
  --candidate-model-dir experiments/next_bar/intrabar_profile_m5_latest_artifact_001 \
  --candidate-weight 0.25 \
  --preserve-baseline-direction \
  --context-policy methods/next_bar/config/m5_intrabar_profile_runtime_shadow_policy_v1.json \
  --odds-calibration experiments/next_bar/intrabar_profile_m5_odds_calibration.json \
  --output experiments/next_bar/intrabar_profile_m5_latest_ensemble_001/latest_prediction.json \
  --parity-output experiments/next_bar/intrabar_profile_m5_latest_ensemble_001/parity.json
```

split境界と主要学習設定が一致しないartifactは停止する。OOS/runtimeは同じblend関数を使い、時間足・bar start・decision timestampも完全一致を要求する。統計calibration gateと運用認可は別で、`--authorize-odds` を明示しない限り `odds_valid=false`、`strict_prediction_eligible=false` のshadow出力になる。現在のM5候補ではこのflagを使わない。

M15予測へ同時刻のM5/M1 OOS確率を追加するchronological meta model:

```bash
uv run python methods/next_bar/scripts/cross_timeframe_meta.py \
  --predictions-dir experiments/next_bar/context_confirmation_001 \
  --predictions-dir experiments/next_bar/walk_forward_001 \
  --output-dir experiments/next_bar/cross_timeframe_meta_001 \
  --regularization-c 0.10 \
  --meta-weight 0.25
```

各test foldのmeta modelは、それ以前のdirection-model OOS予測だけで学習する。M15/M5/M1のjoinは同じ `decision_timestamp` に限定し、時刻の新しい短期足を混ぜない。現在の固定候補は `config/m15_cross_tf_meta_candidate_v1.json` で、次の完全未使用期間までは現行モデルを置換しない。

M15 targetとM5/M1 contextが別artifactにある場合は `--target-predictions-dir` と `--context-predictions-dir` を使う。Full Path M15へ既存M5/M1を追加した検証では、固定25% metaは方向accuracyを6/6 fold悪化させ、0.53〜0.55のaccuracy/coverageも同時改善しなかった。小weight感度の点推定最大は時系列weight選択で再現しなかったため、split-source経路は再現専用とし、Full Path 0.53 confidenceを維持する。

target時間足を変更する場合は `--target-timeframe`、同時刻contextは `--context-timeframes`、直近の確定済みcontextは `--asof-context-timeframes` で明示する。M1 targetへM5/M15を最大14分のbackward as-ofで追加した固定25% metaは、未来不参照で評価行の97.98%を保持したが、全方向accuracy -0.012pt、0.51 selection scoreも全期間で僅かに悪化した。M15係数の符号と年別改善も安定しないため再現専用とし、context subset、age、weight、閾値を同じ履歴で再探索しない。

```bash
uv run python methods/next_bar/scripts/cross_timeframe_meta.py \
  --predictions-dir experiments/next_bar/context_confirmation_001 \
  --predictions-dir experiments/next_bar/walk_forward_001 \
  --output-dir experiments/next_bar/cross_timeframe_meta_m1_asof_m5_m15_001 \
  --target-timeframe 1 \
  --context-timeframes '' \
  --asof-context-timeframes 5,15 \
  --asof-max-age-minutes 14 \
  --regularization-c 0.10 \
  --meta-weight 0.25
```

発行済みの最新M30予測を最大15分だけ保持して追加する場合:

```bash
uv run python methods/next_bar/scripts/cross_timeframe_meta.py \
  --predictions-dir experiments/next_bar/context_confirmation_001 \
  --predictions-dir experiments/next_bar/context_confirmation_m30_001 \
  --predictions-dir experiments/next_bar/walk_forward_001 \
  --output-dir experiments/next_bar/cross_timeframe_meta_m30_asof_001 \
  --regularization-c 0.10 \
  --meta-weight 0.25 \
  --asof-context-timeframes 30 \
  --asof-max-age-minutes 15
```

as-of contextはtarget判定時刻以前だけを検索し、最大ageを超えた値を欠損にする。M30追加は全体方向には不採用で、`config/m15_cross_tf_m30_high_conf_candidate_v1.json` のconfidence 0.54以上forward laneだけに使う。fresh M30が無い場合はM15/M5/M1 metaへfallbackする。

M15 class confidence 0.54以上かつM15/M5/M1の方向が同時刻で一致する条件は、`config/m15_cross_tf_agreement_shadow_v1.json` に固定した。確認期間の高信頼accuracyとselection scoreは改善したが、全期間のselection scoreと売買cost余力が十分でないためshadow専用である。

## 主評価指標

- accuracy と balanced accuracy
- log loss と Brier score
- expected calibration error (ECE)
- 信頼度閾値ごとの coverage と accuracy
- 採用条件のWilson accuracy lower bound、selection score、quality score
- 学習期間の多数派予測、および前足方向の継続予測との比較

高信頼度だけを選ぶと見かけの正答率は上がりやすいため、accuracy と coverage を必ず対で扱う。
`quality_score` はWilson下限の50%超過分を0〜100へ正規化した値で、0は統計下限が偶然水準以下、100は下限100%を表す。売買収益性のqualityではない。

## 予測オッズ

walk-forwardのout-of-sample予測だけを使って、予測方向が正しい確率を検証・校正する:

```bash
uv run python methods/next_bar/scripts/run.py build-odds-calibration \
  --predictions-dir experiments/next_bar/walk_forward_001 \
  --output methods/next_bar/config/odds_calibration_v1.json \
  --bins 10 \
  --min-support 500 \
  --prior-strength 500
```

OOS foldが複数ディレクトリに分かれている場合は `--predictions-dir` を繰り返す。各時間足は結合後に時系列sortされ、同じfold/timestampが重複する入力は停止する。

M15 Volatility Shape単体方向についても、自身のPlatt confidenceをnested検証した。121,950件でbaselineよりaccuracy、Brier、log loss、ECEをすべて改善し、追加の階層実績校正は全proper metricを悪化させた。このため `config/m15_intrabar_volatility_shape_odds_shadow_v1.json` に元model confidenceを固定した。ただしdevelopmentの累積高信頼帯は過信が残り、最新値も局所区間外だったため、`--authorize-odds` を付けない非認可shadowに限定する。

directionやvolatility regimeに偏った校正を監査する場合は、固定subgroup分析を使う:

```bash
env PYTHONPATH=src .venv/bin/python methods/next_bar/scripts/analyze_confidence_subgroups.py \
  --predictions-dir experiments/next_bar/walk_forward_intrabar_volatility_shape_m15_001 \
  --timeframe 15 \
  --group-columns predicted_direction,volatility_regime \
  --thresholds 0.515,0.525,0.535,0.55 \
  --output experiments/next_bar/intrabar_volatility_shape_m15_direction_subgroup_reliability.json
```

Shape confirmationでは0.535以上のupは全volatilityでWilson edgeを通ったが、downはhighだけが通り、low/normalは未達だった。この区分は診断後に分かったため採用filterへ変換せず、同じ6セルをfresh期間で監視する。

Shapeへpredicted up/down別correctness Plattを適用する実験も行った。方向は完全に同じだが、nested 121,950件のBrier/log loss/ECEがすべて元class confidenceより悪化し、confidence 0.535以上のaccuracy改善もcoverage低下でdevelopment/confirmationのselection scoreをともに下げたため棄却した。correctness confidenceは0.5未満も有効な確率値なので、reliability出力は `[0, 1]` を受け入れ、0.5未満を `below_first_edge` に分離する。今回side Plattが0.5未満としたconfirmation 2,857件は実際には52.048%正解しており、安定したabstention laneではなかった。

完成上位足内のM1 returnを固定DCT k1〜k4 energy比、low/mid/high周波数構成、lag 1〜3自己相関、M1 range低周波比へ加工する場合は `--feature-set intrabar_frequency_shape` を使う。親Volatility Shapeへ12列を追加するが、M15方向accuracyは親に6/7 fold敗れた。単体0.55 laneは親Shapeをdevelopment/confirmationと5/7 foldで改善した一方、現行Intrabar Structure 0.55 precision championがdevelopmentのaccuracy・coverage・selection scoreをすべて上回るため、Frequency Shapeは再現専用とする。

完成M15内の連続3本のM1 returnを6種類の順序patternと正規化permutation entropyへ加工する場合は `--feature-set intrabar_ordinal_shape` を使う。親Volatility Shapeへ振幅非依存の固定7列を追加する。単体方向はbaselineを上回ったが親Shapeに負け、方向維持0.53 confidenceもconfirmationで反転した。自身の0.55 laneは親Shapeにaccuracy 5/7・selection score 6/7 fold勝ったが、Intrabar Structure 0.55よりdevelopment objectiveが低く、日次bootstrapでも優位未確定のため再現専用とする。

完成M15内のM1 return分布を価格水準非依存で使う場合は `--feature-set intrabar_distribution_shape` を使う。親Volatility ShapeへRMS正規化q10/q25/q50/q75/q90、Bowley/tail skew、IQR/interdecile range、MAD/RMSの固定9列を追加する。単体方向と通常25%方向blendは親Shape・baselineを置換できなかった。一方baseline方向を固定した25% confidenceの0.53 laneはdevelopment/confirmationの採用gateを通り、Extra Treesにdevelopment objectiveと5/7 foldで勝ったため `config/m15_intrabar_distribution_shape_confidence_candidate_v1.json` に固定した。後続Full Path 0.53がdevelopment objective、confirmation、年別5/7、proper scoreで上回ったため現registryのselective championではないが、比較用forward候補として固定条件を維持する。

候補差が小さい場合は連続M15足を独立と仮定せず、固定UTC日paired bootstrapも使う:

```bash
env PYTHONPATH=src .venv/bin/python methods/next_bar/scripts/bootstrap_fixed_candidates.py \
  --first-dir experiments/next_bar/intrabar_distribution_shape_m15_confidence_blend_001 \
  --first-name distribution_shape \
  --second-dir experiments/next_bar/extra_trees_confidence_blend_001 \
  --second-name extra_trees \
  --threshold 0.53 \
  --timeframe 15 \
  --iterations 5000 \
  --random-seed 42 \
  --output experiments/next_bar/intrabar_distribution_shape_vs_extra_trees_m15_053_daily_bootstrap.json
```

DistributionとExtra Treesのaccuracy・selection score差は95%区間が0を跨いだため、当時のpoint championを統計的な置換確定とは解釈しない。後続Full PathもDistribution/Extra Treesへのselection score優位はbootstrapで未確定なので、registry順位と統計的置換確定を区別する。fixed subgroup監査で見つかったdown-normalの不整合はFull Pathで局所整合を回復したが、fresh gateとして残し、履歴後付けfilterにはしない。

PressureのCLV・wick・body圧力11列とVolatility Shapeの集中度・時間重心14列を同時に使う固定unionは `--feature-set intrabar_flow_shape` で再現できる。52 intrabar列・全90特徴になる。M15単体方向はbaselineを上回ったが親Volatility Shapeを上積みできず、方向維持0.53 confidenceもdevelopmentの改善がconfirmationで反転した。単純unionは棄却し、subset・weight・閾値を同じ履歴で再探索しない。

直前M1高安値に対するclose breakout、更新後のrejection、inside/outside、range expansion、方向continuation/reversal、最長run差を使う場合は `--feature-set intrabar_breakout_state` を指定する。親Profileへ固定12列を加える。M15方向は既存Volatility Shapeに負け、方向維持0.515 confidenceもbaselineには勝ったが親Profileとの年別scoreは2/7、全期間proper scoreも有意に悪化したため再現専用とする。

CatBoostの再現には `--model-type catboost` を使う。Ordered boosting、symmetric depth 6、300 iteration、learning rate 0.03、L2 5を標準固定値とし、後続calibration期間のPlattは他学習器と共通である。M15方向はconfirmationで悪化した。方向維持0.525 confidenceはbaseline gateを通ったが、Signed-body Quantile/Clear-body 0.525のaccuracy・selection scoreを超えないため再現専用とする。

LightGBMの再現には `--model-type lightgbm` を使う。leaf-wise GBDT、31 leaves、300 trees、learning rate 0.03、min child 100、row/column sample 0.8、L2 5を固定し、後続Platt校正を共通にする。M15方向はconfirmationで悪化した。方向維持0.525 confidenceはbaselineを改善したが、Signed-body Quantileにaccuracy 1/7・score 2/7、Clear-bodyにもaccuracy 2/7・score 3/7しか勝てないため再現専用とする。

registry候補を各評価年より前のOOS scoreだけで選ぶ安定性監査は次で再現できる:

```bash
env PYTHONPATH=src .venv/bin/python methods/next_bar/scripts/chronological_role_router.py \
  --registry methods/next_bar/config/m15_candidate_registry_v1.json \
  --baseline-dir experiments/next_bar/context_confirmation_001 \
  --baseline-dir experiments/next_bar/walk_forward_001 \
  --timeframe 15 \
  --output-dir experiments/next_bar/chronological_role_router_m15_001
```

このrouterはfuture foldを選択に使わないが、全nestedで固定championに3 roleで負け、1 role同一だったため運用には採用しない。候補poolは研究後に確定しているため、結果はcandidate生成まで含む完全なunbiased評価ではない。

Shapeのconfidence-to-correctnessをprior OOSだけでisotonic/Platt再校正する研究経路は次の通り:

```bash
env PYTHONPATH=src .venv/bin/python methods/next_bar/scripts/chronological_odds_recalibration.py \
  --predictions-dir experiments/next_bar/walk_forward_intrabar_volatility_shape_m15_001 \
  --timeframe 15 \
  --output-dir experiments/next_bar/intrabar_volatility_shape_m15_chronological_odds_recalibration_001
```

両再校正とも元Shape confidenceよりBrier/log loss/ECEが悪化した。authoritative oddsへは使わず、元confidenceの非認可shadowを維持する。

最新推論では `--odds-calibration methods/next_bar/config/odds_calibration_v1.json` を追加する。出力の意味は次の通り。

- `model_confidence`: 方向モデルをPlatt校正した予測方向の確率。
- `confidence`: nested検証で選ばれた最終オッズ確率。今回は全時間足でmodel confidenceが選ばれた。
- `fair_decimal_odds`: `1 / confidence`。
- `odds_ratio`: `confidence / (1 - confidence)`。
- `confidence_lower/upper`: 同方向・同volatility・同confidence binの縮約実績区間。
- `odds_valid`: nested全体の校正が有効で、現在値が局所実績区間内にある。
- `odds_edge_confirmed`: 局所実績区間の下限が50%を超える。
- `strict_prediction_eligible`: 採用policy、odds validity、odds edgeの3条件をすべて満たす。

`odds_valid` はオッズ推定が整合していることを表し、50%超のedgeを保証しない。強い採用判定には `strict_prediction_eligible` を使う。

## 記録

- `status.md`: 現在の到達点と次の作業
- `reports/`: 実験ごとの番号付きレポート。`00001_YYYY-MM-DD_slug.md` の形式で保存する。
