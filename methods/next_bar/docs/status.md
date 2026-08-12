# Next-bar research status

更新日時: 2026-08-12 12:47 JST

## 現在の状態

- M1 共通データから M1/M5/M15/M30 の完成足を生成できる。
- 次の連続完成足の up/down ラベルを作り、時間境界をまたぐラベルを purge できる。
- 各時間足の独立モデルを学習し、後続期間で確率校正し、完全未使用期間で評価できる。
- 保存済みモデルから各時間足の最新予測と校正済み信頼度を出力できる。
- 正式ベースライン `experiments/next_bar/baseline_001` を完了した。
- 2022〜2026年途中を未知testとする5foldの `experiments/next_bar/walk_forward_001` を完了した。
- 生のOHLC価格水準がモデル特徴量に入ると停止するガードを実装した。
- 加工特徴を追加した `walk_forward_enhanced_manual_001` を同じ5foldで比較し、全時間足一括採用を棄却した。
- 方向別Platt confidenceとcontext HGB confidenceを比較し、どちらも全時間足共通方式として棄却した。
- 同じ加工入力を使う2層MLPをM15/M30で比較し、HGBより悪化したため棄却した。
- 7foldで確認したabstention条件を `methods/next_bar/config/context_policy_v1.json` に固定した。
- `experiments/next_bar/deployment_candidate_001` を生成し、policy付き最新推論まで通した。
- accuracyとcoverageを同時に扱う採用条件optimizerを実装した。Wilson正答率下限を使い、少数サンプルの見かけ上の高精度を罰する。
- 5foldのout-of-sample予測から `methods/next_bar/config/optimized_policy_v1.json` を生成し、過去foldで選択して次foldで測るnested chronological validationを完了した。
- 予測方向が正しい確率をフェアオッズとして検証するnested odds calibrationを実装し、`methods/next_bar/config/odds_calibration_v1.json` を生成した。
- 追加の階層実績校正は全時間足でBrier/log lossを悪化させたため採用せず、既存Platt model confidenceをオッズ源として選択した。全時間足でnested ECE 0.21%以下、null Brierを改善した。
- 最新出力へconfidence interval、fair decimal odds、odds ratio、support、odds validity、strict eligibilityを追加した。
- 方向オッズを売買へ変換する独立層 `next_bar_ev` を追加した。値幅、tail risk、損失重み付きEV、損益分岐確率、Kelly参考値を方向モデルとは別に学習する。
- M15の次足単独売買、ATR stop、既存Entry EVへの単純方向overlayをchronological OOSで検証した。損失1.2倍は標準条件から廃止。通常損益ではM15 confidence 0.54以上が6/6 fold positive、cost 0.05後も6/6 positiveだがcost ceilingが0.05415と薄いためpaper candidateに留めた。
- baseline 75% + enhanced-manual 25%の固定M15 ensembleは7fold合算accuracyを51.816%から51.866%へ改善し、6/7 foldで改善した。ただし過去foldからweightを選ぶadaptive nested方式はbaselineを0.031pt下回ったため、現行置換はしない。
- M15/M5/M1の同時刻OOS確率を使うcross-timeframe logistic meta modelを実装した。M15 75% + meta 25%は完全chronological 6foldでaccuracyを51.645%から51.718%へ+0.073pt、balanced accuracy +0.057pt、5/6 fold改善。Brier、log loss、ECEも改善した。
- confidence 0.54以上はaccuracy 54.408%から54.479%へ改善、coverageは14.261%から13.894%へ低下した。
- `m15_cross_tf_meta_candidate_v1.json` と全OOS fold学習済みfinal meta modelを生成した。hyperparameterを今回比較後に固定したcandidateなので、次の完全未使用期間までは現行モデルを置換しない。
- paired比較はbaseline誤り修正1,740件、新規誤り1,652件、純改善88件。McNemar近似p=0.135で、現時点では統計的に十分強い差ではない。
- ATR正規化した直近8本×5値の `sequence_manual` を7foldで試したが、accuracyは51.816%から51.708%、Brier/log loss/ECEも悪化したため棄却した。
- M15 class confidence 0.54以上をM15/M5/M1の同時刻方向一致で絞ると、全7foldでaccuracy 54.918%から55.055%、2024〜2026途中のconfirmationで55.356%から55.742%へ改善した。
- 方向一致は全期間のselection scoreを0.01610から0.01572へ下げる一方、confirmationでは0.01141から0.01217へ上げた。主policyは変えず `m15_cross_tf_agreement_shadow_v1.json` として次の未使用期間を測る。
- cross-timeframe meta candidateと方向一致を重ねても、confirmation accuracyは55.664%から55.956%へ改善したが全期間selection scoreは低下した。探索後candidate同士のため昇格には使わない。
- 通常損益では方向一致によりgross meanが0.09959から0.12657/ozへ上がったが、all-fold cost ceilingは0.05500から0.05052へ下がった。cost 0.05余力が薄いためpaper policyは置換しない。
- M30予測を未来参照なし・最大age 15分でM15 metaへas-of結合できるようにした。M30の2020〜2021 OOS foldも同じbaseline設定で補完した。
- M30を全行へ使うと全体accuracyは51.684%から51.666%、ECEも0.441%から0.465%へ悪化したため、全体モデルへの追加は棄却した。Brier/log lossはわずかに改善した。
- fresh M30があれば4時間足meta、無ければ3時間足metaへfallbackする高信頼専用laneは、confidence 0.54以上でaccuracy 54.479%から54.637%、coverage 13.894%から13.951%、selection score 0.01388から0.01450へ改善した。developmentとconfirmationの両方でselection scoreが改善したため `m15_cross_tf_m30_high_conf_candidate_v1.json` として固定した。
- M30高信頼laneの通常損益はgross mean 0.11357から0.11663/oz、cost 0.05 positive fold 5/6から6/6へ改善したが、最悪fold余力は0.00140/ozのためpaper policyは維持する。
- baseline加工特徴を使うL2 logistic regressionをM15の7foldで追加した。単体accuracyは51.747%でHGBの51.816%を下回り、通常25% blendもconfirmation accuracyを0.105pt下げたため方向モデルとして棄却した。
- HGB方向を固定し、logistic 25%をconfidence edgeの強さだけへ使う方向維持型blendを実装した。accuracyは完全に同じまま、7fold ECE 0.347%から0.248%、Brier 0.2494261から0.2494093、log loss 0.6919985から0.6919643へ改善した。
- calibration改善はdevelopmentとconfirmationの両方で再現したため `m15_logistic_confidence_blend_candidate_v1.json` として代替confidence/odds候補に固定した。ただしconfidence 0.54のselection scoreはcoverage減少で悪化するため、現行採用policyには使わない。
- HGB/logisticの不一致と市場contextからHGB correctnessを直接学ぶchronological logistic metaを試したが、ECE 0.525%から1.106%へ悪化した。過去foldだけのnested selectorでも全5foldで従来HGB confidence 0.53が選ばれ、追加metaは一度も採用されなかったため棄却した。
- trainを各fold直前1095日へ制限する固定3年rolling HGBを試したが、全体accuracy 51.816%から51.439%、confirmation 51.501%から51.064%へ悪化した。confidence 0.54のselection scoreも0.01568から0.01034へ低下したため棄却し、expanding trainingを維持する。
- baseline加工特徴を使うExtra Treesを固定parameterの7foldで追加した。単体accuracyは51.773%でHGBを下回り、通常25% blendは全体51.862%へ改善したがconfirmationが51.501%から51.471%へ悪化したため、方向モデルとしては棄却した。
- HGB方向を固定したExtra Trees confidence blendはaccuracyを変えず、Brier、log loss、ECEをdevelopmentとconfirmationの両方で改善した。developmentで選んだconfidence 0.53では全期間accuracy 54.357%から54.522%、selection score 0.01942から0.02006、confirmationでも54.479%から54.664%、0.01511から0.01574へ改善した。
- confidence 0.53のcandidateは年別accuracy 7/7 fold、selection score 6/7 foldで改善したため `m15_extra_trees_confidence_blend_candidate_v1.json` に固定した。履歴OOSから選んだ候補なので、authoritative confidenceと現行policyは次の完全未使用期間まで置換しない。
- HGBの確率校正をPlattからisotonicへ置換する7foldを実施した。全体accuracy 51.730%、Brier 0.2496438、log loss 0.6933424、ECE 0.713%で全て現行より悪化し、confirmation accuracyも51.501%から51.259%へ低下した。
- HGB方向を固定したconfidence単独診断でもBrier/log loss/ECEがdevelopment・confirmationの両方で悪化した。confidence 0.54のselection scoreはdevelopmentで上がったがconfirmationで0.01116から0.00832へ低下したためisotonicを棄却し、Plattを標準校正として維持する。
- 次足実体を判定時ATRで正規化した固定sample weightをHGBのtrainだけへ適用した。weighted単体は全体accuracy 51.646%で方向モデルとしては棄却したが、高信頼度帯の精度は改善した。
- HGB方向を固定しweighted HGB 25%でconfidence edgeだけを補正すると、Brier/log loss/ECEがdevelopment・confirmationの両方で改善した。confidence 0.54では全体accuracy 54.809%から55.198%、selection score 0.01568から0.01652、confirmationでも55.270%から55.465%、0.01116から0.01125へ改善した。
- confidence 0.54のcandidateは年別accuracy 7/7、selection score 5/7 foldで改善したため `m15_body_atr_weighted_confidence_candidate_v1.json` に精度重視forward候補として固定した。0.53はselection scoreが悪化するため採用しない。
- 完成M15内部のM1から足内return分散、上昇比率、実体方向効率、実体集中度、序盤/終盤動向の7加工特徴を追加した。intrabar単体はdevelopmentで改善したがconfirmation accuracy 51.501%から51.380%へ悪化したため方向モデルとして不採用。
- baseline 75% + intrabar 25%の通常blendは方向accuracyを全体51.816%から51.848%、confirmation 51.501%から51.526%へ改善したが、純改善46件、p=0.475、fold改善3/7のためshadowに留めた。
- HGB方向を固定したintrabar confidence blendはBrier/log loss/ECEをdevelopment・confirmationの両方で改善した。confidence 0.55では全体accuracy 55.501%から55.928%、selection score 0.01306から0.01396、confirmationでも55.750%から56.459%、0.00642から0.00723へ改善した。
- confidence 0.55のcandidateは年別accuracy・selection scoreとも6/7 fold改善したため `m15_intrabar_confidence_candidate_v1.json` に高精度forward候補として固定した。0.53はselection scoreが悪化するため採用しない。
- train内の `volatility_20` 3分位でlow/normal/high専用HGBへ分ける `regime_hgb` を実装した。境界は各foldのtrainだけで固定し、calibration/testへ適用する。
- regime HGB単体は全体accuracy 51.623%、confirmation 51.380%でbaselineより悪く、通常25% blendもconfirmationを51.501%から51.430%へ下げたため方向用途は棄却した。
- HGB方向を固定したregime confidence blendはECEを全体0.347%から0.200%、confirmation 0.298%から0.196%へ改善したが、Brier/log lossのfold改善は2/7、高信頼selection scoreは全thresholdで悪化した。`m15_regime_hgb_confidence_shadow_v1.json` にECE診断用shadowとして固定し、採用policyは変更しない。
- 完成M15内のM1高値/安値位置、順序、方向転換率、経路効率、実現分散/range、最大runup/drawdownを加工した `intrabar_structure` 8特徴を追加した。既存intrabar 7特徴と合わせた15特徴で、因果性・価格水準排除・最新推論をテストした。
- structure単体はdevelopmentで改善したがconfirmation accuracyが51.501%から51.339%へ悪化し、通常25% blendも51.430%へ低下したため方向用途は棄却した。
- HGB方向を固定したstructure confidence blendはBrier/log loss/ECEをdevelopment・confirmationの両方、各6/7 foldで改善した。confidence 0.55では全体accuracy 55.501%から56.010%、selection score 0.01306から0.01431、confirmationでも55.750%から56.437%、0.00642から0.00722へ改善した。
- confidence 0.55 accuracyは7/7 fold改善したため `m15_intrabar_structure_confidence_candidate_v1.json` にforward候補として固定した。既存intrabar候補と同じ履歴から派生したため、両者はfresh期間でhead-to-headし、履歴上の勝者選択やstackは行わない。
- `log(p)` と `-log(1-p)` を使う単調制約付きbeta probability calibrationを実装した。各foldのcalibration期間だけで係数を学習し、保存artifactと最新推論まで再現できる。
- betaはconfirmation方向精度を51.501%から51.549%へ僅かに上げたが、Brier/log lossがdevelopment・confirmationの両方で悪化した。方向固定でもBrier/log loss/ECEが合算で全て悪化し、confidence 0.55のconfirmation selection scoreは0.00642から0.00495へ低下したため棄却した。
- 次足実体を判定時ATRで正規化し、符号付き `asinh` 連続教師として学ぶ `signed_body_hgb` を実装した。未来値幅は教師にだけ使用し、入力特徴には含めない。
- signed-body単体は全体accuracy 51.349%、confirmation 50.959%で、通常25% blendもbaselineを下回ったため方向用途は棄却した。
- HGB方向を固定したsigned-body confidence blendはBrier/log loss/ECEをdevelopment・confirmationの両方で改善した。developmentで選んだconfidence 0.52では全体accuracy 53.228%から53.738%、selection score 0.01865から0.02004、confirmationでも52.918%から53.594%、0.01353から0.01580へ改善した。
- confidence 0.52 accuracyは7/7 fold、selection scoreは6/7 fold改善したため `m15_signed_body_confidence_candidate_v1.json` に広coverage forward候補として固定した。0.55はaccuracyが上がってもcoverage-aware scoreが下がるため採用しない。
- 符号付き次足実体について25/50/75%分位HGBを学習し、中央値を四分位幅で割ったdistributional scoreを使う `signed_body_quantile_hgb` を実装した。
- quantile単体と通常25% blendは方向accuracyがbaselineを下回ったため方向用途として棄却した。
- 方向維持型quantile confidence blendはBrier/log lossをdevelopment・confirmationの両方、6/7 foldで改善した。developmentで選んだconfidence 0.525では全体accuracy 53.834%から54.080%、selection score 0.01961から0.02100、confirmationでも53.777%から54.086%、0.01527から0.01689へ改善した。
- confidence 0.525 accuracy・selection scoreは6/7 fold改善したため `m15_signed_body_quantile_confidence_candidate_v1.json` に中coverage選別候補として固定した。confirmation ECEは僅かに悪化したためfair odds置換には使わない。
- 各foldのtrain内で次足実体/ATRが中央値以上の教師だけを残す `body_atr_upper_half` filterを実装した。閾値はtrainだけで決め、未来値幅を入力特徴には使わない。
- filtered単体は全体accuracy 51.707%、confirmation 51.312%で方向用途として棄却した。通常25% blendも純改善2件、p=0.989で方向edgeではない。
- 方向維持型filtered confidence blendはBrier/log lossを7/7 fold、ECEを5/7 foldで改善した。developmentで選んだconfidence 0.525では全体accuracy 53.834%から54.182%、selection score 0.01961から0.02088、confirmationでも53.777%から54.201%、0.01527から0.01675へ改善した。
- confidence 0.525のaccuracy・selection scoreは7/7 fold改善したため `m15_body_atr_upper_half_confidence_candidate_v1.json` に中coverage forward候補として固定した。signed-body quantile 0.525とはfresh期間で並行比較し、履歴上でstack・勝者選択しない。
- PyTorchを条件付き依存へ追加し、直近16本×5加工系列をtrain内標準化して学ぶ2層因果TCNを実装した。未来改変への因果性、artifact保存、latest推論をテストした。Intel macOSは互換上PyTorch 2.2/NumPy 1.26へ限定する。
- TCN単体は全体accuracy 51.642%、confirmation 51.250%で方向用途として棄却した。通常25% blendの全体改善は13件、p=0.873で、confirmationは悪化した。
- 方向維持型TCN confidence blendのdevelopment選択0.52は全体accuracy 53.228%から53.456%、selection score 0.01865から0.01956、confirmationでも52.918%から53.216%、0.01353から0.01461へ改善し、6/7 foldで再現した。
- TCN 0.52は同じ広coverage目的のsigned-body 0.52より評価関数が低いため `m15_tcn_confidence_shadow_v1.json` に限定した。epochや窓長を今回の履歴へ合わせて再探索しない。
- 同じ16本×5加工系列を使う1層・2,625 parameterの因果Transformerを実装した。learned position、dimension 16、4-head、feed-forward 32、dropout 0、8 epochを結果前に固定し、artifact保存、同一seed一致、latest推論をテストした。
- Transformer単体は全体accuracy 51.536%、confirmation 51.153%で方向用途として棄却した。通常25% blendも全体51.769%、confirmation 51.412%、paired p=0.402で方向edgeはない。
- 方向維持型Transformer confidence 0.52は全体accuracy 53.228%から53.501%、selection score 0.01865から0.01963、confirmationでも52.918%から53.282%、0.01353から0.01496へ改善した。accuracyは6/7、scoreは5/7 fold改善した。
- 一方でconfirmation Brier/log lossが悪化し、fold改善も各3/7。signed-body 0.52よりdevelopment・confirmation・全体selection scoreがすべて低いためforward configを発行せず、再現実装だけを残した。
- 全教師を残し、次足実体/ATRに応じて教師確率を0.5から0/1へ連続化する固定 `tanh` soft target HGBを実装した。未来値幅は教師だけに使い、特徴除外・artifact・latest推論をテストした。
- soft-target単体は全体accuracy 51.565%、confirmation 51.440%で方向用途として棄却した。通常25% blendはconfirmationだけ改善したが全体/developmentは悪化し、paired p=0.569だった。
- 方向維持型soft-target confidence 0.525は全体accuracy 53.834%から54.180%、score 0.01961から0.02020、confirmationでも53.777%から54.092%、0.01527から0.01558へ改善した。accuracy 7/7、score 5/7、Brier/log loss/ECE 5/7 fold改善だった。
- 同じ0.525のclear-body filterは全体coverage 31.419%対29.672%、accuracy 54.182%対54.180%、score 0.02088対0.02020、confirmationでも3指標すべてsoft target以上。soft targetを採用せず、明確足教師candidateはclear-bodyへ集約した。
- DI/ADX、ATR正規化MACD、volatility compression、短長実現volatility balance、方向entropyを定常加工した `trend_structure` 11特徴を追加した。価格水準排除、未来改変への因果性、artifact最新推論をテストした。
- trend-structure単体は全体accuracy 51.759%、confirmation 51.328%で、通常25% blendもbaselineを下回ったため方向用途として棄却した。
- 方向維持型trend-structure confidence 0.525は全体accuracy 53.834%から53.971%、selection score 0.01961から0.02018、confirmationでも53.777%から53.951%、0.01527から0.01598へ改善し、5/7 foldで再現した。
- ただしclear-body 0.525は全体accuracy 54.182%、score 0.02088、confirmation 54.201%、0.01675で上回り、trend版のconfirmation Brier/log lossも僅かに悪化した。forward configは発行せず再現用特徴として残した。
- 符号付きefficiency、variance ratio、return autocorrelation、方向転換率、方向別transition persistence、符号付きstreakを加工した `path_persistence` 14特徴を追加した。価格水準排除、未来改変への因果性、artifact最新推論をテストした。
- path-persistence単体は全体accuracyがbaselineと実質1件差でBrier/log lossは悪化した。通常25% blendは全体14件純改善したがconfirmation accuracyが51.501%から51.433%へ低下し、paired p=0.832のため方向用途として棄却した。
- 方向維持型path-persistence confidence 0.525は全体accuracy 53.834%から53.959%、score 0.01961から0.02016、confirmationでも53.777%から53.976%、0.01527から0.01631へ改善した。Brier/log lossは6/7 fold改善した。
- ただしaccuracy・score改善は5/7 foldで、clear-bodyおよびsigned-body quantile 0.525より目的関数が低い。forward configは発行せず再現用特徴として残した。
- XGBoost 3.4.0を導入し、300 trees、depth 4、learning rate 0.03、min child weight 20、row/column subsample 0.8、L2 5の固定条件を実装した。加工特徴だけを入力し、artifact保存と最新推論をテストした。
- Intel macOSのXGBoost/PyTorch OpenMP競合を避けるため両backendを遅延importし、各CLI processが選択modelだけを読み込む構成にした。
- 通常教師XGBoostはdevelopmentで改善したがconfirmation accuracyが51.501%から51.294%へ悪化した。通常25% blendもconfirmationで悪化し、方向維持型0.53のselection scoreも0.01511から0.01472へ低下したため棄却した。
- clear-body教師XGBoostの方向維持型0.525は全体accuracy 53.834%から54.075%、score 0.01961から0.02059、confirmationでも53.777%から53.917%、0.01527から0.01576へ改善した。accuracy/scoreは6/7、Brier/log lossは7/7 fold改善した。
- 既存clear-body HGBは全体54.182%・score 0.02088、confirmation 54.201%・0.01675でXGBoost版を上回り、確率品質も良い。XGBoost版のforward/shadow configは発行せず再現用に残した。
- 4/8/16/32本の前半対後半から標準化return差、absolute-return構成差、方向比率差を作る `haar_multiscale` 12特徴を追加した。価格水準排除、未来改変への因果性、artifact最新推論をテストした。
- Haar単体は全体accuracy 51.763%、confirmation 51.362%で方向用途として棄却した。通常25% blendもconfirmationで悪化し、paired純改善3件、p=0.974だった。
- 方向維持型Haar 0.525はdevelopment scoreを0.02048から0.02115へ改善したが、confirmation accuracyは53.777%から53.733%、scoreは0.01527から0.01492へ悪化した。forward/shadow configは発行しない。
- candidate比較を `methods/next_bar/scripts/analyze_candidate.py` へ恒久化し、期間別指標、固定grid、年別lane、proper score、paired exact testを同一手順でJSON保存できるようにした。
- baseline、clear-body、Extra Trees、signed-body、intrabar-structureの5モデルを等重みで集約し、baseline方向へ揃えた確率edgeの平均・標準偏差へ加工するdisagreement ensembleを実装した。145,140行・7foldの完全整列を検証してから集約する。
- 事前の1 sigma lower-bound confidenceはdevelopment scoreを0.02048から0.02011へ下げ、Brier/log loss/ECEのfold改善も3/7、3/7、2/7だったため棄却した。
- 方向を固定しない等重み平均は全体accuracyを51.816%から51.868%へ上げたが、confirmationでは6件悪化し、paired p=0.497だったため方向置換には使わない。一方でBrier/log loss/ECEはdevelopmentとconfirmationの両方で改善した。
- 結果確認後の構造ablationとして分散罰則を0にし、平均edgeだけをbaseline方向のconfidenceへ使うと、development選択0.515はconfirmation accuracyを52.574%から52.766%、scoreを0.01395から0.01418へ改善した。Brier/log lossは6/7 fold改善したが、ECEは3/7、2026途中は悪化し、既存clear-body/signed-body候補よりscoreが低い。`m15_disagreement_confidence_shadow_v1.json` の研究shadowに限定する。
- 同じ5モデルをexpertとし、各decisionまでに確定した直近2,000件のbinary log lossから学習率1でweightを更新する因果的online ensembleを実装した。現在target、未確定target、rolling除外、不正時刻を単体テストした。
- 方向自由版はdevelopmentで改善したがconfirmation accuracyを51.501%から51.430%へ下げ、paired p=0.932だったため方向用途として棄却した。
- baseline方向固定online confidenceのdevelopment選択0.515はconfirmation accuracyを52.574%から52.834%、scoreを0.01395から0.01482へ改善した。Brier/log lossは6/7、ECEは4/7 fold改善した。
- ただし固定等重みより全体Brier/log loss/ECEが悪く、development 0.515 scoreも低い。signed-body 0.52のconfirmation score 0.01580にも届かないためconfigは発行せず、因果的学習フローの再現実装だけを残した。
- baselineにUTC時刻sin/cosが既にあり、M1 volumeは全602万行で0であることを確認した。新しい情報として同じ曜日×UTC時の過去32本だけでreturn/body/rangeを標準化する `session_relative` 5特徴を追加した。
- session-relative単体と通常25% blendはconfirmation方向精度を下げたため方向用途として棄却した。
- baseline方向固定session confidenceのdevelopment選択0.525はconfirmation accuracyを53.777%から54.166%、scoreを0.01527から0.01697へ改善した。Brier/log lossは6/7、ECEは5/7 fold改善した。
- ただしclear-body 0.525との直接比較ではsession版のaccuracy/score改善が3/7 fold、proper score改善も各3/7で、development・全体・確率品質はclear-bodyが上回った。`m15_session_relative_confidence_shadow_v1.json` に固定するがforward candidateへは昇格しない。
- 次足をsampled train内body/ATR中央値でdown-large/down-small/up-small/up-largeへ分ける4クラスHGBを実装した。up側2クラス確率を合算し、後続calibration期間で二値方向確率へPlatt校正する。calibration/testの実体値は入力・境界決定に使わない。
- 4クラス単体は全体accuracy 51.793%でBrier/log lossも悪化し、通常25% blendの全体方向精度も悪化したため方向用途として棄却した。
- baseline方向固定multiclass confidenceのdevelopment選択0.525はconfirmation accuracyを53.777%から54.115%、scoreを0.01527から0.01609へ改善し、accuracy・scoreとも7/7 fold改善した。Brier/log loss/ECEは各5/7 fold改善した。
- clear-body 0.525との直接比較ではmulticlassのaccuracy改善1/7、score3/7、Brier/log loss各3/7で、3期間の目的関数もclear-bodyが上回った。`m15_body_multiclass_confidence_shadow_v1.json` に固定するがforward candidateへは昇格しない。
- M15方向維持型confidence候補14件・145,140 OOS行を設定JSONと予測parquetから再計算するcandidate registryを実装した。暗黙閾値を禁止し、全候補のkey整列、coverage、accuracy、Wilson下限、selection score、Brier/log loss/ECE、7fold安定性を検証する。
- developmentだけで選ぶ役割別objective championは、broad=intrabar profile 0.515、balanced=signed-body quantile 0.525、selective=Intrabar Distribution Shape 0.53、precision=intrabar structure 0.55となった。4件ともhistorical gateを通過した。
- balancedのaccuracy leaderはclear-body 0.525、selectiveのaccuracy leaderはbody/ATR weighted 0.54、coverage leaderはExtra Trees 0.53であり、Pareto challengerとして保持する。logistic 0.54と既存intrabar 0.55はdevelopmentでdominated、各shadowはchampion選択対象外とした。
- `m15_candidate_registry_v1.json` を機械可読な正本とする。confirmationは監査だけに使い、authoritative confidence、fair odds、paper policyは新しい完全未使用期間まで置換しない。
- baseline、clear-body、Extra Trees、signed-body、intrabar structureのlogit確率を入力し、各test foldより前のOOSだけでL2 logistic weightを学ぶchronological stackingを実装した。test2020は過去OOSがないためbaselineへfallbackする。
- stack単体はconfirmation accuracy 51.501%から51.251%、Brier/log loss/ECEも悪化した。通常25% blendもconfirmation accuracyを51.358%へ下げ、paired純改善-16件、p=0.805だったため方向用途として棄却した。
- baseline方向固定stacking confidenceのdevelopment選択0.53はscoreを0.02027から0.02069へ上げたが、confirmationではaccuracy 54.479%から54.330%、coverage 18.438%から17.405%、score 0.01511から0.01394へすべて悪化した。forward/shadow configを発行しない。
- 完成M15内部のM1終値経路をrange正規化し、20/40/60/80%地点、直線trajectoryからの偏差、平均/RMS/上下最大偏差へ加工するintrabar profile 12特徴を追加した。価格水準不変性、未来改変への因果性、artifact最新推論をテストした。
- profile単体と通常25% blendはconfirmation方向精度を下げたため方向用途として棄却した。方向維持型はBrier/log lossを6/7、ECEを5/7 fold改善した。
- developmentで選んだprofile confidence 0.515はconfirmation accuracyを52.574%から52.743%、scoreを0.01395から0.01513へ改善し、accuracy・scoreとも6/7 fold改善した。broad coverage forward candidateへ採用した。
- profile 0.515はdevelopment scoreとcoverageでsigned-body 0.52を上回りregistryのbroad championになった。signed-bodyは全期間のaccuracyとconfirmation scoreが高いためaccuracy leader兼Pareto challengerとして維持する。
- 親のintrabar structureを現行gridで再解析し、Profileと同じ0.515で直接ablationした。Structure 0.515はdevelopmentでbaseline scoreを0.02048から0.02030へ悪化させた一方、Profileは0.02134へ改善した。
- Profile 0.515はStructureに対しdevelopment/confirmation/allのaccuracy・selection scoreをすべて改善し、scoreは7/7、accuracyは6/7 fold勝った。選択集合は約92%重なるため、trajectory特徴が境界行を有効に入れ替えた増分edgeと判断した。
- 同じIntrabar Profile定義をM5/M30へ変更せず移植し、独立7foldでcross-timeframe検証した。無変動M5足の0/0で46行欠落する問題を見つけ、profile・body/path効率・realized variance/rangeへ意味的ゼロを定義し、M5全439,881行のbaseline整列を回復した。
- M5単体は全体accuracyを51.556%から51.600%へ上げたが、confirmation 1/3 fold勝、paired p=0.333で方向置換には弱い。通常25% blendもp=0.817のため方向用途は棄却した。
- M5方向維持Profile 0.515はconfirmation accuracyを52.355%から52.412%、selection scoreを0.01199から0.01231へ改善した。accuracy・scoreは6/7、Brier/log loss/ECEは7/7 fold改善したため `m5_intrabar_profile_confidence_candidate_v1.json` にbroad forward候補として固定した。
- M5 Profileは親Structure 0.515に対してもdevelopment/confirmation/allのselection scoreを改善し、accuracy・scoreとも6/7 fold勝った。追加trajectory特徴の増分edgeがM5にも移植できたと判断した。
- M30 Profileは単体と通常blendの方向accuracyが悪化した。方向維持版はBrier/log lossを7/7、ECEを5/7 fold改善したが、0.515のconfirmation accuracy・coverage・selection scoreが全て悪化したため `m30_intrabar_profile_calibration_shadow_v1.json` の校正診断shadowに限定した。
- 固定confidence帯のaccuracy、mean confidence、calibration gap、Wilson上下限、support、単調性をdevelopment/confirmation別に比較する `compare_confidence_reliability.py` を追加した。
- M5 Profileのconfirmation 0.515以上は62,885件・accuracy 52.412%・mean confidence 52.454%で、Wilson区間内かつ下限52.021%。baselineよりaccuracyを上げ、絶対calibration gapを0.105ptから0.042ptへ縮めた。
- confirmationでは0.525以上53.498%、0.535以上55.249%、0.550以上57.784%とconfidence上昇に沿ってaccuracyも上がり、各laneのWilson下限は50%超だった。ただし0.550は668件、0.575は12件だけなので採用閾値は0.515から変更しない。
- M5 Profileを過去OOSだけで校正し次foldを測るnested odds検証では、元model confidenceがbaselineよりBrier/log loss/ECEをすべて改善しglobal gateを通過した。階層実績再校正は3指標すべて悪化したため棄却した。
- development 0.515はmean confidenceがWilson上限を0.334pt超える軽い過信で、deployable runtime blendも未検証。`m5_intrabar_profile_odds_shadow_v1.json` にforward odds shadowとして固定するがauthoritative fair oddsへは昇格しない。
- OOSとruntimeが共有するprobability blend関数、latest artifactのsplit・主要学習設定guard、最新予測key整合、context/odds適用を `next_bar_ensemble.py` と `predict_latest_ensemble.py` に実装した。
- 既存deployment baselineとProfile latestはsplit境界が違うため混合せず、Profileと同じ60/20/20条件で `baseline_m5_latest_artifact_001` を生成した。artifact parityで境界・主要設定の一致を確認した。
- 実データ最新値はbaseline up 0.533271、Profile up 0.531473、75/25 blend up 0.532822で、共通式との差は1.11e-16。方向維持、局所校正gate、0.515 policyを通過した。
- shadow段階の統計gateと運用認可を分離した。現在は `odds_calibration_gate_passed=true` でも `odds_runtime_authorized=false` のため `odds_valid=false`、`strict_prediction_eligible=false` を強制する。runtime parityは達成したがauthoritative oddsは据え置く。
- 完成M15内のM1 close-location、body、wick、rangeを総rangeやM1 rangeで正規化する `intrabar_pressure` 11特徴を追加した。scale不変、未来改変不影響、flat足有限値、artifact/latest経路をテストした。
- Pressure単体はbaseline方向accuracyをdevelopment/confirmationと5/7 foldで改善したが、全体p=0.695のため単体置換しない。
- baseline 75% + Pressure 25%の通常方向blendはaccuracyをdevelopment 52.014%から52.072%、confirmation 51.501%から51.565%、全体51.816%から51.876%へ改善した。accuracy 5/7、Brier/log loss 7/7 fold改善、paired p=0.224だった。
- Pressure方向blendは親Profile方向blendよりconfirmation +0.127pt、全体+0.039ptだがdevelopment -0.017pt、fold勝敗4/7。`m15_intrabar_pressure_direction_candidate_v1.json` にparallel forward candidateとして固定するが現行方向は置換しない。
- M15で固定したIntrabar PressureをM5へ変更せず移植した。439,881行の25%方向blendはdevelopment 51.879%から51.923%、confirmation 51.041%から51.051%、全体51.556%から51.587%へ改善した。accuracy 5/7、Brier/log loss 7/7、ECE 5/7 fold改善、paired p=0.180である。
- M5 Pressure方向blendは親Profile方向blendをdevelopment/confirmation/allで上回り、accuracy 6/7 fold勝った。`m5_intrabar_pressure_direction_candidate_v1.json` にparallel forward candidateとして固定するが現行方向は置換しない。
- M5 Pressure 0.515はbaseline比accuracy/score 6/7、proper score 7/7 fold改善したが、既存Profile 0.515との直接比較は3/7対4/7で選択集合も95%重複した。重複confidence候補には採用しない。
- baseline 75% + Profile 12.5% + Pressure 12.5%のconfidence平均はProfile単体よりconfirmation/allのselection scoreが悪化したため棄却した。ensemble成果物を再入力した際の列衝突を修正し、即時入力成分の確率へ置き換えるnested ensembleテストを追加した。
- Intrabar PressureをM30へ同一定義で移植した。単体方向は全体51.807%から51.563%、通常25% blendも51.737%へ悪化したため方向用途は棄却した。
- M30方向維持Pressureのdevelopment選択0.52はconfirmation accuracyを53.636%から53.735%、selection scoreを0.01445から0.01479へ改善した。accuracy 7/7、score 6/7 fold改善のため `m30_intrabar_pressure_confidence_candidate_v1.json` にselective forward候補として固定した。
- M30 Pressure 0.52は親Profile 0.52にaccuracy/score 5/7 fold勝ち、development/all scoreも上回ったが、confirmation合算はProfileが上だった。fresh期間のhead-to-headを昇格条件とし、現行confidenceは置換しない。
- M30 Pressureのnested model confidenceは59,838件でbaselineよりBrier/log loss/ECEを全て改善した。階層実績再校正は3指標すべて悪化したため棄却し、元model confidenceをodds shadowに固定した。runtime parityは通過したが局所gate/運用認可は未達で `odds_valid=false` のままとする。
- Pressure方向維持confidenceはdevelopment選択0.53がconfirmationでaccuracy/scoreを悪化させ、親Profileと同じ0.515でも直接比較3/7だったためconfidence registryへ追加しない。
- 同一splitのbaseline/Pressure latest artifactとruntime blendを生成した。最新はup 0.578761、artifact parity通過、odds未接続のため `odds_valid=false` のままである。
- 完成M15内のM1値幅・close-to-close分散について、集中度、上位3本構成比、時間重心、序盤/終盤構成比を作る `intrabar_volatility_shape` 14特徴を追加した。scale不変、未来改変不影響、flat足有限値、41 intrabar特徴、artifact/latest経路をテストした。
- Shape単体方向はbaseline accuracyをdevelopment 52.014%から52.275%、confirmation 51.501%から51.583%、全体51.816%から52.008%へ改善した。accuracy 6/7、Brier/log loss 5/7 fold改善、純改善278件、paired p=0.0501である。
- 親Profile単体にもdevelopment/confirmation/allで勝ち、accuracy 5/7 fold、純改善295件、paired p=0.0135だった。`m15_intrabar_volatility_shape_direction_candidate_v1.json` に単体parallel forward候補として固定するが現行方向は置換しない。
- 通常25%方向blendはconfirmationで悪化したため棄却した。方向維持Shape 0.515はbaselineより改善したがProfile 0.515との直接比較3/7で、Profile/Shape confidence平均もdevelopment/all scoreを悪化させたためconfidence registryとfair oddsへ追加しない。
- Shape単体は既存Pressure 25%方向候補より合算accuracyが高いが年別4/7、paired p=0.146でproper scoreも一貫優位ではない。履歴上でPressureを置換せずfresh期間で並行比較する。
- Volatility Shapeを定義・HGB/Platt・7fold・25% weightを変更せずM5/M30へ移植した。M5 439,881行、M30 71,260行は既存baselineとfold/timestamp/targetが完全整列した。
- M5 Shape単体は全体accuracyを51.556%から51.592%、通常blendは51.575%へ上げたが、confirmationはそれぞれ51.041%から50.988%、51.030%へ悪化した。通常blendのBrier/log lossは7/7 fold改善しても方向候補には採用しない。
- M5 Shape 0.515 confidenceもdevelopmentの僅かな改善がconfirmationで反転し、Profile 0.515との直接比較はaccuracy/score各1/7対6/7だった。既存M5 Profile confidenceとPressure方向候補を維持する。
- M30 Shape単体・通常blendはdevelopment/confirmationの方向accuracyをともに悪化させた。方向維持0.52はconfirmation accuracyが僅かに上がったがcoverage低下でselection scoreが0.01445から0.01412へ悪化した。
- M30 Shape 0.52は既存Pressureにaccuracy/score各2/7、Profileにもscore 2/7で、confirmation scoreを大きく下回った。M5/M30 Shapeはconfigを発行せず再現専用とし、時間足別subset・weight・閾値を履歴内再探索しない。
- M15内M1 returnをupside/downside semivariance、方向別集中度・時間重心、bipower/jump、最大jump除外continuous成分へ分ける `intrabar_signed_variation` 14特徴を追加した。scale不変、未来改変不影響、flat足有限値、構成比・範囲、55 intrabar特徴、artifact/latest経路をテストした。
- Signed Variation単体はbaseline accuracyをdevelopment 52.014%から52.197%、confirmation 51.501%から51.560%、全体51.816%から51.951%へ上げたが、accuracy 4/7、paired p=0.173である。
- 親Volatility Shape単体にはdevelopment/confirmation/all、accuracy/Brier/log loss各2/7で敗れ、純改善-82件、p=0.488だった。通常25% blendもconfirmation accuracyを悪化させたため方向用途には採用しない。
- 方向維持Signed Variationのdevelopment選択0.525はbaseline比accuracy/score 5/7、Brier/log loss 6/7、ECE 5/7 fold改善したが、2025/2026途中はaccuracy/scoreが悪化した。
- Signed Variation 0.525はclear-bodyにaccuracy 1/7・score 2/7、signed-body quantileにaccuracy 3/7・score 2/7しか勝てず、confirmation scoreも既存Profile/Pressureより低い。confidence registryへ追加せず再現専用とする。
- 固定Extra Trees 200 trees、depth 12、min leaf 50、max features 0.75へVolatility Shapeを入力した。加工なしExtra Treesに対しaccuracy 5/7、全体51.773%から51.908%、純改善195件、paired p=0.070を示し、特徴情報は別学習器でも一部再現した。
- Shape Extra Treesは正式baselineにdevelopmentで勝ったがconfirmation 51.501%対51.303%で敗れ、HGB Shapeにもconfirmation 51.583%対51.303%で敗れた。正式baselineとの25%方向blendもconfirmationを51.453%へ下げたため方向用途は棄却した。
- 方向維持Shape Extra Treesのdevelopment選択0.525はbaseline比でdevelopment/confirmation scoreを改善し、Brier/log loss/ECE各6/7 fold改善したが、lane accuracy/score改善は4/7だった。
- 加工なしExtra Treesとの直接比較ではShape版が0.525でaccuracy/score各2/7、採用済み0.53で各1/7しか勝てず、development/confirmation/all scoreをすべて下げた。configを発行せず、既存Extra Trees 0.53 confidence候補を維持する。
- M15 Shape自身の方向confidenceを固定帯で監査した。confirmationの0.515/0.525/0.535/0.55はaccuracy 52.525%/53.428%/54.237%/56.158%、coverage 50.438%/27.165%/12.716%/3.027%で、すべて局所整合・Wilson edge通過、帯別accuracyも単調増加した。一方development累積帯は0.535以外が過信である。
- 2021〜2026途中121,950件のnested oddsではShape model confidenceがaccuracy 51.753%、Brier 0.2495824、log loss 0.6923127、ECE 0.420%で、同一行baselineの51.622%、0.2495873、0.6923225、0.525%を全て改善した。階層実績再校正は3指標を悪化させたため棄却した。
- `m15_intrabar_volatility_shape_odds_shadow_v1.json` を発行し、Shape model confidenceを自身の方向に対応するodds shadowとして接続した。最新up 0.564871は局所Wilson上限0.564547を僅かに超え、runtime gateが停止した。`odds_valid=false` の非認可shadowとし、高信頼選別candidate、authoritative odds、paper policyは変更しない。
- fixed side × volatility subgroup監査を追加した。confirmationの0.535以上はupのlow/normal/highとdown-highでWilson edgeを通る一方、down-low 263件はaccuracy 51.331%・下限45.314%、down-normal 564件は51.950%・下限47.828%で未達だった。期間非対称を平均値で隠さずfresh監視するが、confirmation後付けのside/regime gateは採用しない。
- M15 Shapeへ各fold calibration期間だけで学ぶpredicted-side別correctness Plattを適用した。方向は完全一致するが、nested 121,950件のBrier/log loss/ECEは元class confidenceの0.2495824/0.6923127/0.420%から0.2496217/0.6923922/0.530%へ全て悪化した。
- side Platt 0.535はaccuracyをdevelopment 54.718%から54.793%、confirmation 54.237%から54.501%へ上げたが、coverage低下でselection scoreは0.02023から0.01966、0.01098から0.01032へ悪化した。0.515/0.525/0.55も両期間でscore改善せず、side Plattを棄却する。
- correctness confidence監査を `[0, 1]` へ一般化し、0.5未満を独立表示するようにした。side Plattが0.5未満としたconfirmation 2,857件は実accuracy 52.048%、mean 49.693%で過小評価だった。元Shape class confidence odds shadowを維持する。
- 完成M15内のM1 returnを固定DCT k1〜k4 energy比、low/mid/high構成、lag 1〜3自己相関へ、M1 rangeを低周波比へ加工する `intrabar_frequency_shape` 12特徴を追加した。53 intrabar特徴についてscale不変、未来改変不影響、flat有限0、artifact/latest経路をテストした。
- Frequency Shape単体は正式baseline accuracyをdevelopment 52.014%から52.127%、confirmation 51.501%から51.560%へ上げたが、親Shape 52.275%/51.583%には敗れた。親比accuracy 1/7、Brier/log loss各2/7、純改善-145件、p=0.225で方向用途には不採用。
- baseline 75% + Frequency 25%方向blendはconfirmation accuracyを51.391%へ悪化させた。方向維持confidenceのdevelopment選択0.53もconfirmation selection scoreを0.01511から0.01489へ下げたため不採用。
- Frequency単体0.55は親Shapeにdevelopment/confirmationとaccuracy・score各5/7 fold勝ったが、precision champion Structure 0.55がdevelopmentでaccuracy 55.934%対55.788%、coverage 10.888%対10.763%、score 0.01631対0.01572と全面優位だった。Frequencyはregistryへ追加せず再現専用とする。
- 各roleの候補を過去OOSのselection scoreだけで年次選択するchronological routerを追加した。confirmationでbalanced/selective/precisionは固定championと同一、broadだけ切り替わったがscoreは0.01513から0.01399へ悪化した。全nestedでも4 role中3 role悪化・1 role同一のため不採用。
- broadの年別scoreはProfileが5/7年、Signed-bodyが2/7年勝ち、前年勝者を追う切替は平均回帰で失敗した。候補交代は履歴winner chasingではなく、固定並行運用したfresh期間のgateで行う。
- Shape confidenceへ過去OOSだけで学ぶcorrectness isotonic/Platt再校正を実施した。121,950件の元confidence Brier/log loss/ECE 0.2495824/0.6923127/0.420%に対し、isotonicは0.2499363/0.6964012/0.742%、Plattは0.2497004/0.6925555/0.668%へ全て悪化したため棄却した。
- 完成M15内M1 returnのq10/q25/q50/q75/q90、Bowley/tail skew、IQR対tail幅、MADをRMS等で正規化した `intrabar_distribution_shape` 9特徴を追加した。価格scale不変、未来改変不影響、flat有限0、artifact/latest parityをテストした。
- Distribution単体は正式baseline accuracyを全体51.816%から51.852%へ上げたが、親Volatility Shape 52.008%にpaired p=0.049で負けた。通常25%方向blendも全体-48件、confirmation-49件で方向用途は棄却した。
- baseline方向固定25% confidenceはBrier/log lossを7/7、ECEを5/7 fold改善した。固定0.53ではdevelopment accuracy/coverage/score 54.575%/29.111%/0.02141、confirmation 54.551%/17.894%/0.01512で、baseline gateを全項目通過した。
- Distribution 0.53はExtra Trees 0.53にdevelopment score 0.02141対0.02094、全体0.02018対0.02006、年別5/7で勝った。一方confirmationは0.01512対0.01574でExtra Trees優位。registry規定どおりDistributionをselective履歴championにし、両者をfresh期間まで並行維持する。
- UTC日paired block bootstrap 5,000回では、Distribution−Extra Treesの全体accuracy差+0.046ptの95%区間は-0.158〜+0.254pt、selection score差+0.000112は-0.000910〜+0.001150で、優位を確定できなかった。点推定championと統計的置換根拠を区別する。
- Distribution−baselineは全体accuracy差+0.212ptの95%区間+0.017〜+0.411pt、Brier差も全区間負で改善を支持したが、selection score区間は0を跨いだ。forward候補維持は妥当だがauthoritative昇格には不足する。
- Distribution 0.53 confirmationの固定side×volatility監査ではup全regimeとdown-highがWilson edgeを通った一方、down-lowは未達、down-normal 859件はaccuracy 49.942%、mean confidence 53.817%で局所不整合だった。後付けfilterにはせずfresh必須gateへ追加した。
- Intrabar Pressure 11列とVolatility Shape 14列を固定unionにした `intrabar_flow_shape` を追加した。共通Profile等を含む52 intrabar列についてscale不変、未来改変不影響、flat有限0、artifact/latest経路をテストした。
- Flow Shape単体はbaseline方向accuracyをdevelopment/confirmationで上回ったが、親Volatility Shapeにdevelopment 52.072%対52.275%、all 51.877%対52.008%で敗れ、paired純改善-189件、p=0.105だった。通常25%方向blendもconfirmationを悪化させたため方向用途は棄却した。
- 方向維持Flow 0.53はdevelopment selection scoreをbaseline 0.02027、Distribution 0.02141に対し0.02181へ上げたが、confirmationは0.01397でbaseline 0.01511、Distribution 0.01512を下回った。Distributionとのlane accuracyは2/7 foldしか勝てず、confidence用途も棄却した。
- 日次bootstrapのFlow−Distribution confirmation差はaccuracy -0.275pt、95%区間-0.602〜+0.076pt、selection score -0.001153、区間-0.002534〜+0.000334だった。feature setは再現用に残すがconfig/registry/latest artifactは発行しない。
- 完成M15内で直前M1高安値に対する終値breakout、更新後のrejection、inside/outside、range expansion、方向continuation/reversal、最長run差を12比率へ加工する `intrabar_breakout_state` を追加した。手作りOHLCの厳密値、scale不変、未来改変不影響、flat有限0、artifact/latest経路をテストした。
- Breakout State単体は親Profileより全体+66件だったがp=0.567で、Volatility Shape方向候補にはdevelopment/confirmation/allで負け、全体-229件、p=0.059だった。通常25%方向blendもbaseline比全体+4件、p=0.966のため方向用途は棄却した。
- 方向維持Breakout 0.515はbaseline比accuracy/score 6/7、Brier/log loss 6/7 fold改善し、confirmation scoreを0.01395から0.01538へ上げた。しかし親Profileとの直接比較ではaccuracy 3/7、score 2/7で、development/all objectiveはProfileが上だった。
- 日次bootstrapではBreakout−Profileの全期間Brier/log loss差が95%区間を含め正、すなわちBreakoutの悪化を支持した。breakout feature setは再現用に残すがconfig/registry/latest artifactは発行せず、Profile 0.515 broad championを維持する。
- CatBoost 1.2.10を依存へ追加し、baseline加工特徴を固定Ordered boosting・symmetric depth 6・300 iterationで学ぶ `model_type=catboost` を実装した。artifact保存とlatest推論をround-tripテストした。
- CatBoost単体はconfirmation方向accuracyを51.501%から51.367%へ下げた。通常25% blendもdevelopmentは改善したがconfirmationを51.453%へ下げ、全期間純改善38件、p=0.559のため方向用途は棄却した。
- 方向維持CatBoostのdevelopment選択0.525はconfirmation accuracyを53.777%から54.005%、scoreを0.01527から0.01640へ上げ、accuracy/score 5/7、Brier/log loss 6/7 fold改善した。
- ただしSigned-body Quantile 0.525にdevelopment/confirmation/allのaccuracy・scoreがすべて負け、直接比較も3/7だった。Clear-body 0.525にもaccuracy 2/7、score 3/7で敗れたためregistryへ追加しない。
- CatBoost−Signed-bodyの日次bootstrap全期間score差は-0.000457、95%区間-0.001284〜+0.000381、CatBoost優位確率15.5%だった。学習器は再現用に残すがparameterや閾値を履歴内再探索しない。
- 生確率の方向を維持する `sigmoid(logit(p) / T)` temperature scalingを実装した。各foldのcalibration期間だけで正の温度を学習し、artifact/latest経路と方向維持をテストした。7foldの温度は1.217〜2.655で、すべてconfidenceを0.5側へ縮めた。
- Temperatureはdevelopment Brier/log lossを改善したが、confirmationではPlattより方向accuracyが51.501%から51.376%、Brier 0.2495525から0.2496663、log loss 0.6922506から0.6924789へ悪化した。全期間方向も-182件、p=0.232だった。
- development選択0.52はconfirmation accuracy/coverage/scoreを52.918%/36.650%/0.01353から52.521%/30.107%/0.00970へ下げた。固定0.55はaccuracy 57.664%でもcoverage 1.466%で、Structureの56.437%/3.104%よりscoreが低かった。
- Temperature−Structureの日次bootstrapは全期間coverage差-1.114ptの95%区間が全て負で、score差-0.000557の区間は0を跨いだ。confirmation Brier/log loss差の区間は全て正で悪化を支持したため、Temperatureは再現専用、Plattを標準として維持する。
- 完成M15内の連続3本M1 returnを6順序pattern比率と正規化permutation entropyへ加工する `intrabar_ordinal_shape` 7特徴を追加した。scale不変、未来不参照、pattern和1、flat有限0、artifact/latest経路をテストした。
- Ordinal単体はbaseline方向accuracyをdevelopment 52.014%から52.141%、confirmation 51.501%から51.548%へ上げたが、親Volatility Shapeには全期間-139件、p=0.194、accuracy/Brier/log loss各2/7 foldで負けた。通常25%方向blendもconfirmationを51.385%へ下げたため方向用途は棄却した。
- 方向維持Ordinal 0.53はBrier/log loss 6/7、ECE 5/7 fold改善したが、development score 0.02113の改善がconfirmation 0.01419へ反転した。Distribution 0.53にも全期間区分・年別で負けたためselective候補へ追加しない。
- Ordinal自身の0.55は親Shapeにaccuracy 5/7、score 6/7勝ち、confirmation accuracy 57.347%、coverage 2.877%だった。しかしStructure 0.55よりdevelopment scoreが低く、年別scoreは3/7、日次bootstrap全期間score差+0.000162の95%区間-0.002049〜+0.002441で優位未確定のためprecision候補へ追加しない。
- LightGBM 4.7.0を依存へ追加し、baseline加工特徴を固定leaf-wise GBDT、31 leaves、300 trees、row/column sample 0.8で学ぶ `model_type=lightgbm` を実装した。OpenMP runtime混在を避けるsubprocess隔離でartifact/latest推論をround-tripテストした。
- LightGBM単体はbaseline方向accuracyをdevelopment 52.014%から51.976%、confirmation 51.501%から51.458%へ下げた。通常25% blendもconfirmation 51.455%、全期間-20件、p=0.746のため方向用途は棄却した。
- 方向維持LightGBM 0.525はbaseline比accuracy/score 5/7、Brier/log loss 6/7 fold改善し、confirmation scoreを0.01527から0.01563へ上げた。しかしSigned-body Quantileにはaccuracy 1/7・score 2/7、Clear-bodyにもaccuracy 2/7・score 3/7で負けた。
- LightGBM−Signed-bodyの日次bootstrap全期間差はaccuracy -0.125pt、score -0.000694、LightGBM優位確率4.5%/5.2%だった。学習器と依存は再現用に残すがregistryへ追加せず、parameterや閾値を履歴内再探索しない。
- 次足の実体/range比率を教師品質とする `body_range_upper_half` を追加した。各foldのtrain内中央値（約0.456）以上の約半数だけでHGBを学習し、calibration/testは全件、教師品質列はfeature外とした。
- Directional Clarity単体はbaseline方向accuracyをdevelopment 52.014%から51.902%、confirmation 51.501%から51.312%へ下げた。通常25% blendも全期間-10件、p=0.897のため方向用途は棄却した。
- 方向維持Directional ClarityはBrier/log loss 7/7、ECE 6/7 fold改善したが、development選択0.53のscore改善0.02027→0.02178がconfirmationで0.01511→0.01427へ反転した。
- Distribution Shape 0.53との全期間差はaccuracy -0.038pt、score -0.000032で、日次bootstrap 95%区間はいずれも0を跨いだ。confirmationと年別安定性で負けるためregistryへ追加せず、Selective champion/challengerを維持する。
- 全教師を残し、次足実体/rangeを−1〜+1の符号付き連続教師へ加工する `model_type=signed_clarity_hgb` を追加した。教師rangeは特徴・校正・test入力へ渡さず、回帰scoreを後続期間でPlatt校正する。
- Signed Clarity単体はbaselineと全期間−2件、p=0.994。通常25%方向blendはdevelopment +40件、confirmation +20件、全期間+60件、p=0.349、Brier/log loss 6/7 fold改善した。
- ただしSigned Clarity方向blendはPressure blendとVolatility Shapeにaccuracy各2/7対5/7で負け、development/confirmation/allも下回るため方向候補へ追加しない。
- 方向維持Signed Clarity 0.525はbaseline比accuracy/score 6/7、Brier/log loss 6/7 fold改善し、confirmation scoreを0.01527から0.01570へ上げた。
- Signed-body Quantile 0.525には全期間accuracy 54.039%対54.080%、score 0.02052対0.02100、coverage 32.666%対33.366%で同時に負け、Clear-bodyにもaccuracy/score各1/7対6/7だった。registryへ追加しない。
- 方向0/1教師と全行を維持し、次足実体/rangeから0.5〜1.5、平均1、最大比3倍のsample weightを作る `train_weighting=directional_clarity` を追加した。未来rangeは重みにだけ使い特徴へ渡さない。
- Clarity Weighted単体はbaseline比development -22件、confirmation +33件、全期間+11件、p=0.932。通常25% blendもdevelopment -10件、confirmation +26件、全期間+16件、p=0.798で方向候補には採用しない。
- 方向維持Clarity Weighted 0.525はdevelopment/confirmationのscoreを0.02048→0.02135、0.01527→0.01591へ改善したが、accuracy 5/7、score 4/7に留まった。
- Signed-body Quantile 0.525には全期間accuracy 53.987%対54.080%、score 0.02040対0.02100、coverage 33.179%対33.366%で負け、日次bootstrapのscore優位確率7.5%。Clear-bodyにも2/7対5/7で、registryへ追加しない。
- 完成M15内15本のM1 close経路について、親Profileが持つ3/6/9/12番目以外の11地点をM15 rangeで正規化した `intrabar_full_path` を追加した。15点の元M1との厳密対応、価格scale不変、未来不参照、flat有限0、artifact/latest parityをテストした。
- Full Path単体は親Profileにaccuracy 6/7 fold、全期間proper scoreとECEで勝った。正式baseline比はdevelopment +227件、p=0.0423だがconfirmation -11件、通常25%方向blendも全期間-45件のため方向用途には採用しない。
- baseline方向固定25% confidenceはBrier/log loss 7/7、ECE 6/7 fold改善した。固定0.53でdevelopment accuracy/coverage/score 54.580%/29.801%/0.02173、confirmation 54.905%/17.311%/0.01628、全体54.667%/24.977%/0.02076となった。
- Full Path 0.53は親Profileへaccuracy 6/7、Distribution Shapeへaccuracy/score各5/7、Extra Treesへ各4/7勝った。Distribution比の全期間Brier/log lossとconfirmation accuracy改善は日次bootstrap 20,000回の95%区間でも支持されたが、全期間selection score差は0を跨いだ。
- 正式baseline比の日次bootstrapは全期間accuracy差+0.311pt、selection score差+0.001347、Brier/log loss差の95%区間がすべて改善側だった。Distributionで局所不整合だったconfirmation down-normalもaccuracy 51.256%、mean confidence 53.779%で局所整合を回復した。
- Full Path 0.53をselective confidence forward candidateとして採用し、16候補registryのselective履歴championへ更新した。Distribution/Extra Treesは比較用に残すが、authoritative confidence、odds、adoption/paper/live policyは完全未使用期間まで変更しない。
- Full Pathの11追加列とVolatility Shapeの14列を固定unionにした `intrabar_full_path_volatility_shape` を追加した。52 intrabar・全90特徴についてscale不変、未来不参照、flat有限0、stationary validator、artifact/latest経路をテストした。
- union単体はbaseline比全体+75件、p=0.603、通常25% blendは+31件、p=0.673で、confirmation blendは-63件だった。単体はFull Pathにaccuracy 2/7、Volatility Shapeに0/7のため方向用途を棄却した。
- 方向維持unionはdevelopmentで0.525を選択し、baseline比accuracy 6/7、score 4/7、Brier/log loss 7/7 fold改善した。confirmation scoreも0.01527から0.01563へ上げたが、scoreの採用gate 5/7には届かなかった。
- 同じ0.525で親Full Path/Volatility Shapeにaccuracy・score各3/7、Signed-body Quantileに各1/7、Clear-bodyに各2/7だった。Signed-body Quantile比の日次bootstrapはunion score優位確率9.31%で、proper score改善だけでは主目的の劣化を補えない。
- unionは再現専用としconfig/registry/latest artifactを発行しない。Full Path 0.53 selective champion、Volatility Shape方向候補、Signed-body Quantile/Clear-body 0.525を維持する。
- cross-timeframe metaへtarget/context別OOS sourceを渡す経路を追加し、Full Path M15と既存M5/M1を同一decision timestampで時系列学習した。固定25%は方向を全6foldで悪化させ、全体-90件、p=0.0969。Brier/log lossは僅かに改善したがECEと0.53〜0.55のaccuracy/coverageは改善しなかった。
- 25%失敗後のweight感度では10%が全体+36件だったが、development +58件からconfirmation -22件へ反転した。0.53 scoreの全期間日次bootstrap区間は0を跨ぎ、development scoreはFull Pathより低かった。
- 各foldより前のOOS 0.53 scoreだけでweightを選ぶchronological監査はFull Path比方向-11件、0.53 accuracy/coverage/scoreも全て悪化した。M30追加、config/registry/latest発行は行わず、既存cross-TF候補とFull Path 0.53 championを維持する。
- 時間×正規化closeの区分線形経路をChen積で合成し、level 2 signed areaとlevel 3 bracket 2列へ加工する `intrabar_path_signature` を追加した。Full Pathへ3列、全79特徴とし、直線ゼロ、順序感応、scale不変、未来不参照、flat有限0、artifact/latest経路をテストした。
- Path Signature単体はbaseline方向をdevelopment/confirmationで改善し全体+141件、p=0.316だったが、親Full Pathには全体-75件、accuracy 3/7だった。通常25% blendも全体-28件のため方向用途には採用しない。
- 方向維持0.53はbaseline比accuracy 6/7、score 5/7、Brier/log loss 7/7 fold改善した。しかし親Full Path比はaccuracy 4/7、score 3/7で、confirmation scoreが0.01628から0.01571へ低下。全期間score差は+0.0000035、日次bootstrap優位確率50.2%だった。
- Distribution Shape/Extra Treesには年別で勝つが直接の親championへ増分edgeがないため再現専用とし、config/registry/latestは発行しない。Full Path 0.53 selective championを維持する。
- 完成M15間のvol-of-vol、volatility加速度、range clustering/圧縮、bipower jump、Parkinson/Garman–Klass balanceを11定常列へ加工する `volatility_state` を追加した。scale不変、未来不参照、flat有限0、範囲、artifact/latest経路をテストした。
- Volatility State単体はbaseline方向比-122件、通常25% blendは-74件。confirmation blendは純-74件、p=0.0477で悪化が支持されたため方向用途を棄却した。
- 方向維持0.525はdevelopment scoreを0.02048から0.02159へ上げたが、confirmationは0.015268から0.015271の実質横ばいでaccuracyも低下。accuracy/score各4/7に留まった。
- Signed-body Quantile 0.525にはaccuracy/score各3/7、Clear-bodyには0/7・2/7で負けた。再現専用としconfig/registry/latestは発行しない。
- Full Pathをexpanding履歴と固定1095日履歴で別学習し、両edgeの1σ下限をtemporal uncertainty confidenceとする実験を行った。recent Full Path単体はaccuracy 51.291%でexpandingに7/7 fold負けた。
- temporal overlayはFull Path方向を維持し、0.515 accuracyを全7foldで上げたがcoverageを全体55.658%から29.091%へ半減させ、scoreを0.01924から0.01801へ下げた。Brier/log loss/ECEも各2/7しか改善しなかった。
- 既存異種disagreement 0.515にもdevelopment/confirmation/all scoreが全て負けた。window/penalty/weightを再探索せず再現専用とし、Full Path 0.53 championと異種disagreement shadowを維持する。
- cross-timeframe metaを任意target/context時間足へ一般化し、target自身のcontext再利用、duplicate、exact/as-of重複を停止した。M1 targetへ確定済みM5/M15を最大14分のbackward as-ofで結合し、評価元の97.979%、1,801,567行を未来不参照で保持した。
- 固定25% metaはM1方向accuracyを50.6443%から50.6322%へ下げ、純-218件、p=0.3095。方向は1/6 fold、Brier/log lossは各3/6しか改善せず、M15係数も正負に揺れた。
- development選択0.51はconfirmation accuracyを+0.088pt上げたがcoverageを2.070pt下げ、developmentと全期間のselection scoreは悪化した。accuracy/score改善は各2/6 foldのため再現専用とし、config/registry/latestは発行しない。
- M1へPath Persistence 14特徴を固定移植した。完全無変動・片方向窓の0/0を意味的ゼロへ直し、flat有限0テストを追加。旧artifactとのintersection比較を避け、現コードでbaselineも再学習してusable 5,737,928行、OOS 2,183,717行を完全一致させた。
- Path単体は全体+289件、p=0.548、accuracy 4/7foldで不採用。一方baseline 75% + Path 25%の通常方向blendはaccuracyを50.80695%から50.85009%へ上げ、開発+556件、確認+386件、全体+942件、accuracy 7/7fold、Brier/log loss各6/7fold改善した。
- UTC日paired bootstrap 20,000回のaccuracy差95%区間は開発+0.0135〜+0.0694pt、確認+0.0114〜+0.0806pt、全体+0.0216〜+0.0648pt。M1方向専用parallel forward候補へ固定した。
- development選択0.51 confidenceは確認3/3foldでaccuracy・scoreが反転したため不採用。authoritative方向/confidence/odds/policyは置換せず、完全未使用期間まで特徴窓・subset・25% weight・閾値を再探索しない。
- M1へTrend Structure 11特徴を固定移植し、無変動窓のDI/ADX、MACD/ATR、volatility比などの0/0を意味的ゼロへ修正した。flat有限0テストと現baselineとのusable 5,737,928行、OOS 2,183,717行完全一致を確認した。
- Trend単体は全体+369件、p=0.445、accuracy 4/7foldで不採用。通常25%方向blendは開発+361件、確認+316件、全体+677件、p=0.0053で、accuracy/Brier/log lossを各6/7fold改善した。
- TrendのUTC日bootstrap accuracy差はconfirmation +0.0031〜+0.0719pt、全体+0.0089〜+0.0530ptで改善側だが、developmentは-0.0018〜+0.0553ptで0を跨いだ。M1方向secondary challengerへ固定した。
- Pathとの直接比較はTrendが全期間-0.0121pt、年別3/7対4/7。accuracy/proper score差の日次区間は0を跨ぐため統計的置換とはせず、Pathをpoint champion、Trendを独立challengerとして並行維持する。union・再weightは行わない。
- Trend confidenceのdevelopment選択0.515は確認aggregate scoreが僅かに上がったが改善は1/3foldのため不採用。authoritative confidence・odds・policyは変更しない。
- M15で固定済みの16本×5定常系列・2層1,073 parameter因果TCNをM1へ変更せず移植した。完全無変動足のATR比/close location 0/0を意味的ゼロへ修正し、flat区間80列の有限0、未来不参照、baselineとのusable 5,737,928行・OOS 2,183,717行完全一致を確認した。
- TCN単体はbaseline比-1,970件、p=0.00615で悪化。通常25%方向blendは全体+587件でもp=0.0945、確認+125件・p=0.565、accuracy 5/7foldで、Path方向候補より弱いため方向用途を棄却した。
- baseline方向固定TCN confidenceのdevelopment選択0.515は確認accuracyを52.509%から53.041%、coverage-aware scoreを0.006837から0.007506へ改善した。accuracy 7/7、score 6/7、Brier/log loss各6/7fold改善し、UTC日bootstrapのaccuracy/score差もdevelopment・confirmation・allで改善側だった。
- 0.515確認laneは67,042件、mean confidence 51.972%に対してaccuracy 53.041%で局所的に過小評価した。nested global Brier/log loss/ECEはbaselineを上回るが、0.55は58件だけでedge未確認。`m1_tcn_confidence_candidate_v1.json` にselective forward候補として固定し、fair odds/runtime authorizationとauthoritative confidence・policyは変更しない。
- 確認0.515の固定side×volatility監査はdown/up highとup-normalだけWilson edgeが成立した。履歴からsubgroup filterを作らず、6セルを完全未使用期間の監視gateとする。
- M15固定のSession Relative 5特徴をM1へ移植した。M1では同じ曜日×時内の直近分足regimeが中心になることを明記し、prior分散/平均0の0/0を意味的ゼロ、非ゼロ/0をclip端へ定義した。flat有限0、未来不参照、価格水準排除をテストした。
- Session単体は全体+639件だがaccuracy/Brier/log loss各4/7foldで不採用。通常25%方向blendは開発+339件、確認+326件、全体+665件・p=0.0268で、accuracy/Brier/log lossを7/7、ECEを5/7fold改善した。
- UTC日bootstrapは全期間accuracy差+0.0034〜+0.0575pt、Brier/log lossはdevelopment・confirmation・allで改善側。Pathにはaccuracy 2/7で負けるがproper scoreを明確に改善し、Trendとはaccuracy同等・4/7勝でproper scoreが明確に良かった。
- Session検証時点ではPathをM1 accuracy champion、Sessionをprobability-quality secondary、Trendをtertiary方向challengerへ整理した。後続Volatility検証後の現役割は下記のbalanced secondary／specialist区分を優先する。候補をstack・union・再weightせず、authoritative方向・policyは変更しない。
- Session confidenceのdevelopment選択0.51は確認scoreがbaselineを僅かに下回ったため不採用。候補別固定閾値bootstrapではSession 0.51とTCN 0.515のscore差が未確定であり、同閾値baselineを改善するTCNをselective confidence候補として維持する。
- M15固定のVolatility State 11特徴をM1へ移植した。vol-of-vol、加速度、range clustering/圧縮、jump、range-based variance balanceを生価格水準なしで加工し、flat有限0、scale不変、未来不参照、baselineとのusable 5,737,928行・OOS 2,183,717行完全一致を確認した。
- Volatility単体は全体-311件で棄却。通常25%方向blendは開発+348件、確認+414件・p=0.0297、全体+762件・p=0.0104で、accuracy 6/7、Brier/log loss 7/7、ECE 5/7foldを改善した。
- UTC日bootstrapはconfirmation/allのaccuracy差とdevelopment/confirmation/allのBrier/log loss差が改善側。Pathより全体accuracyは-0.00824ptだがproper scoreが良く、Sessionとはaccuracy/proper score差が未確定のため、balanced secondary方向候補に固定した。
- Volatility confidence 0.515はbaselineを改善したが、TCNよりconfirmation accuracy -0.300pt、all -0.095ptで日次bootstrapも劣位。coverage差でselection scoreは未確定のため不採用とし、TCN 0.515をselective confidence候補として維持する。
- M15固定のHaar Multiscale 12特徴をM1へ移植した。4/8/16/32本の前半対後半からreturn・absolute return・方向のdetailを加工し、完全無変動0/0を変化なしの0へ定義した。flat有限0、価格scale不変、未来不参照、baselineとのusable 5,737,928行・OOS 2,183,717行完全一致を確認した。
- Haar単体はdevelopmentで悪化しproper scoreも3/7のため不採用。通常25%方向blendは開発+425件・p=0.0204、確認+267件・p=0.0668、全体+692件・p=0.00307で、accuracy/Brier/log lossを7/7、ECEを5/7fold改善した。
- UTC日bootstrapはdevelopment/allのaccuracyと全期間のBrier/log lossが改善側。Path/Volatility/Session/Trendとの直接accuracy差は全て未確定で、Volatility/Sessionよりproper scoreが悪いため、tertiary multiscale方向challengerに限定した。Trendは独立structural challengerとして残す。
- Haar confidence 0.515はaggregate baselineを改善するが、TCNにaccuracy・selection score各0/7対7/7で負けるため不採用。TCN 0.515をselective confidence候補として維持する。
- M15固定のLightGBM 4.7.0、31 leaves、300 trees、learning rate 0.03、min child 100、row/column sample 0.8、L2 5をM1加工済みbaseline特徴へ適用した。独立CLI processで7foldを学習し、baselineとのusable 5,737,928行・OOS 2,183,717行完全一致、保存artifactからのlatest推論を確認した。
- LightGBM単体は開発+275件、確認+663件・p=0.0185、全体+938件・p=0.0395。accuracy/Brier/log lossは各5/7foldだが、UTC日bootstrapのaccuracy差はconfirmation/allで改善側だった。Pathとは全体4件差、年別4/7対3/7、直接accuracy差区間0跨ぎのため、異種学習器accuracy co-challengerに固定した。
- HGB 75% + LightGBM 25%は全体+770件・p=0.000897、accuracy/Brier/log loss 7/7foldで安定するが単体より点精度が低く、Volatility/Sessionのproper-score役割も超えない。別configを増やさずsupporting sensitivity成果物に留めた。
- LightGBM confidence 0.515はbaseline比accuracy/score 6/7、Brier/log loss 7/7foldでも、TCNよりconfirmation accuracy -0.458pt、all -0.184ptでbootstrapも劣位。confidence・oddsには使わずTCN 0.515を維持する。
- M15固定のCatBoost 1.2.10、Ordered boosting、symmetric depth 6、300 iteration、learning rate 0.03、L2 5をM1加工済みbaseline特徴へ適用した。独立CLI processで7foldを学習し、baselineとのusable 5,737,928行・OOS 2,183,717行完全一致を確認した。
- CatBoost単体はbaseline比development +85件、confirmation +42件、全体+127件でpaired p=0.794。通常25%方向blendは全体+490件・p=0.0430、accuracy 6/7、Brier/log loss 7/7foldで、日次bootstrapもdevelopment/all accuracyと全期間proper scoreの改善を支持した。
- CatBoost blendはPath/LightGBMにaccuracy各2/7対5/7で、LightGBMへのconfirmation accuracy差95%区間は全て負だった。Volatility/Sessionのproper-score役割も超えず、追加方向候補には採用しない。
- CatBoost confidence 0.515はTCNよりcoverageが広いがaccuracy 0/7、score 1/7。confirmation/all accuracyと全期間Brier/log lossのbootstrapも劣位を支持したため、confidence・oddsには使わない。
- M15固定のXGBoost 3.4.0、300 trees、depth 4、learning rate 0.03、min child weight 20、row/column subsample 0.8、L2 5をM1加工済みbaseline特徴へ適用した。独立CLI processで7foldを学習し、baselineとのusable 5,737,928行・OOS 2,183,717行完全一致を確認した。
- XGBoost単体はbaseline比development +171件、confirmation +275件、全体+446件でaccuracy 3/7。通常25%方向blendは全体+607件・p=0.00587、accuracy/Brier/log loss 7/7foldで、日次bootstrapもconfirmation/all accuracyと全期間proper scoreの改善を支持した。
- XGBoost blendはPathにaccuracy 1/7対6/7、LightGBMに3/7対4/7で、Volatility/Sessionの確率品質も超えない。baseline補完性はsupporting sensitivityとして保存するが、追加方向候補には採用しない。
- XGBoost confidence 0.515はTCNよりcoverageが広いがaccuracy 0/7、score 2/7。confirmation/all accuracyと全期間Brier/log lossのbootstrapも劣位を支持したため、confidence・oddsには使わない。
- M15固定のExtra Trees 200 trees、depth 12、min leaf 50、max features 0.75をM1加工済みbaseline 38特徴へ適用した。7foldでbaselineとのusable 5,737,928行・OOS 2,183,717行完全一致を確認した。
- Extra Trees単体は全体+782件でもp=0.127、accuracy/Brier/log loss各4/7foldのため不採用。HGB 75% + Extra Trees 25%はdevelopment +610件・p=0.00286、confirmation +255件、all +865件・p=0.000879でaccuracy/Brier/log loss 7/7、ECE 5/7foldを改善した。
- UTC日bootstrapはall accuracy差+0.0162〜+0.0626ptと全期間Brier/log lossの改善を支持した。Pathには全体-77件でもaccuracy 4/7、proper scoreが良く、LightGBMには全体-73件・accuracy 2/7対5/7。既存point役割を置換せずheterogeneous learner stability方向challengerへ固定した。
- Volatility/Sessionより点accuracyは高いがproper scoreが悪く、両候補の役割を置換しない。Extra Trees confidence 0.515はTCNにaccuracy・score各0/7対7/7で、bootstrapもaccuracy劣位のため不採用。
- 保存済み最終foldから最新推論を復元し、2026-06-01 04:59 UTCはup、probability_up 0.501065を確認した。単体artifactの機能確認値で、異種75/25 runtime blendとoddsは未認可。全履歴特徴再計算に約137秒かかるため、運用昇格にはincremental latestとblend parityを要求する。
- 完成M1足のbody/wick/close pressure、range加重body/wickを3/8/21本で集約し、3本−8本の加速度を加えるCandle Pressure State 18特徴を実装した。scale不変、未来不参照、flat有限0、raw OHLC非使用、artifact latest経路をテストした。
- Pressure State単体は全体-15件・p=0.977で不採用。通常25%blendはdevelopment +466件、confirmation +116件、all +582件・p=0.0184、accuracy/Brier/log loss 6/7、ECE 5/7foldを改善した。日次bootstrapもall accuracyとproper score改善を支持した。
- 方向blendはPathにaccuracy 2/7、Extra Treesに1/7で、Sessionのconfirmation accuracyと全期間proper scoreも超えなかった。baseline補完性は再現したが、既存方向役割への増分がないため候補へ追加しない。
- Pressure State confidence 0.515はbaselineを改善したがTCNにaccuracy・score各0/7対7/7。confirmation accuracy差95%区間は-0.649〜-0.221pt、all proper scoreもTCNが有意に良いためconfidence・oddsへ使わない。
- 現在足を除く直前1/5/20本high/lowに対するclose breakout、wick rejection、inside/outside、方向付きrange expansion、ATR正規化境界距離を作るM1 Bar Breakout / Rejection 18特徴を実装した。scale不変、未来不参照、flat有限0、binary 0/1、artifact latest経路をテストした。
- Breakout単体は全体+5件・p=0.993でproper score悪化。通常25%blendはdevelopment +194件、confirmation +33件、all +227件・p=0.293、accuracy 5/7、Brier/log loss 7/7foldだった。
- 日次bootstrapは全期間のaccuracy差が0を跨ぎ、all Brier/log lossだけ改善側だった。Sessionとの直接比較はaccuracy 1/7対6/7で、development/confirmation/allのaccuracy・proper scoreを全て下回ったため確率品質shadowにも追加しない。
- development選択0.51 confidenceはconfirmationでaccuracy 51.8000%→51.7889%、coverage 24.21%→24.10%、score 0.007791→0.007716と反転した。confidence・oddsへ使わずTCN 0.515を維持する。
- M1固定方向候補5系統をfold内train由来のlow/normal/high volatility regimeで切り替えるrouterを実装した。固定development選択と、各評価foldより前のOOSだけで更新するchronological選択を分離し、alignment、有限確率、regime完全被覆、future非参照をテストした。
- 固定routerはlow=LightGBM、normal=Path、high=Extra Treesを選び、baseline比all +1,150件、accuracy/Brier/log lossの日次区間も改善側だった。一方confirmationはPath -89件、LightGBM -366件で、両直接差区間は0を跨いだ。chronological nestedもPath/LightGBMを下回り、既存候補への増分edgeは再現しなかった。
- 固定router 0.515はTCNよりcoverage +2.834ptでもaccuracy -0.213pt、selection scoreも低く、accuracy・score 0/7対7/7。bootstrapも精度劣位を支持したためconfidence・oddsには使わない。
- baseline HGB、Path HGB、Extra Trees、LightGBM、causal TCNの5モデルを等重みでbaseline方向へ整列し、平均edgeをconfidenceにするM1 disagreement 0.515を固定移植した。M15 shadow由来のpenalty 0・閾値をM1結果へ合わせて変更していない。
- disagreement 0.515はbaseline比でdevelopment/confirmation/allのaccuracyとselection scoreを日次bootstrapで改善し、accuracy・score 6/7fold。全行Brier/log lossも3期間すべてbootstrap改善側だった。
- TCN 0.515とはall accuracy 52.309%対52.303%で日次区間上は同等。coverage 19.896%対18.897%、selection score 0.009636対0.009348、score 6/7fold、all Brier/log lossはdisagreementが優位。TCNをaccuracy specialist、disagreementをbalanced coverage/probability-quality confidence challengerとして並行固定する。
- disagreement confirmationはmean confidence 51.970%に対しaccuracy 53.031%で約1.060pt過小評価する。固定6セルのdown-low/down-normal/up-lowもedge未確認なのでfair odds・policyには使わず、runtime parityとfresh局所校正を要求する。
- Disagreement confidenceへ各評価foldより前のOOSだけでcorrectness isotonic/Plattを学習するnested odds再校正を適用した。test2020を除く1,838,693行でraw・isotonic・Plattを同一行比較した。
- isotonicはECEを0.1463%→0.0260%へ改善したが、Brier/log lossは6/6fold悪化。0.515はall nestedでaccuracy +0.443ptでもcoverage -6.757pt、selection score 0.007471→0.006629となり、日次bootstrapも開発・確認・全期間のscoreとproper score悪化を支持した。
- Plattはall nested Brier/log loss/ECEを全て悪化させ、test2023以降の4foldとconfirmation全体で0.515以上が0件。両再校正を棄却し、元Disagreement confidenceを維持する。
- TCNと同じ16本×5加工系列を単層causal GRU hidden 16で学習するM1固定比較を追加した。GRUはPyTorchの2組gate biasを含む1,121 parameterでTCNより48（4.47%）多く、8 epoch・batch 2,048・AdamW・seed 42・train上限750,000・Plattを共通化した。7fold 2,183,717行はbaseline/TCNと時刻・target・foldが完全一致し、artifact別プロセス再読込も確認した。
- GRU単体はbaseline比-996件で不採用。通常25%方向blendはdevelopment +207件、confirmation +353件、all +560件、accuracy 6/7・Brier/log loss 5/7foldだが、all accuracy日次95%区間は-0.0068〜+0.0580pt、TCN blendとも同等で既存方向役割を超えなかった。
- GRU方向維持0.515はbaseline比accuracy・selection scoreを7/7fold改善し、all 52.2712% / coverage 19.7809% / score 0.009439。TCNよりcoverage +0.884ptでもaccuracy -0.0316pt、score差は未確定。5-model Disagreementにはaccuracy -0.0377pt、coverage -0.115pt、score -0.000198で、all Brier/log loss悪化の日次区間も確定したためconfidence候補へ追加しない。
- GRUを5-model Disagreementへ等重みで追加した6-model感度は、all 0.515 accuracyを+0.0258ptにしたがcoverage -0.624pt、score -0.0000495。confirmationでもscore低下、all proper-score差も未確定なので拡張を棄却し、元5-model DisagreementとTCNを維持する。GRUのwindow、hidden、epoch、学習率、weight、0.515以外の閾値を同じ履歴で再探索しない。
- M1 Direction Transition Bayesを実装した。現在方向×run length×反転率bucket×volatility状態の135 encoded slot中81状態が構造的に到達可能で、7foldすべて81/81状態・9/9親状態を観測した。state prior 64、parent prior 256、通常25% blend、Plattを固定し、scale不変・未来不参照・flat有限0・artifact/latest経路をテストした。
- 単体方向はaccuracy 50.4655%で不採用。通常25%方向blendはbaseline比全体+89件でaccuracy差区間が0を跨いだ。Brier/log loss改善は確定したがSession Relativeがaccuracy/proper scoreで点優位のため方向役割へ追加しない。
- 元の方向維持0.515はall accuracy 52.4006% / coverage 15.5185% / score 0.008794。TCNよりaccuracy +0.0978ptでもscore悪化が確定し、Disagreementよりcoverage・score・proper scoreが低いため単独採用しない。0.515→0.55で累積accuracyは単調上昇したがconfirmation 0.55は16件だけだった。
- development固定6セルでup×low volatilityだけが29,394件・accuracy 50.6022%・mean confidence 52.1284%と過信したため、このセルを0.5 abstentionへ固定してconfirmationを監査した。confirmationも1,208件・50.4967%で、guardはraw比all accuracy +0.1789pt、score +0.000235、両bootstrap区間を改善した。
- guard済み遷移confidenceをDisagreementへdevelopment grid選択50%で合成した。固定0.515はall accuracy 52.5827% / coverage 16.0178% / score 0.009674。baselineにはaccuracy・score各7/7fold、TCNにはaccuracy 7/7・score 6/7fold勝ち、TCN比accuracy差区間+0.1936〜+0.3652ptとなったため新accuracy specialistへ採用する。
- Disagreement比はaccuracy 7/7fold・all +0.2738ptでもcoverage -3.8781pt、score差区間-0.000294〜+0.000372、confirmation scoreは僅かに低い。Disagreementをbalanced coverage/probability-quality候補として維持する。最終confidenceはconfirmationで1.4021pt過小評価、0.55は39件・edge未確認なのでfair odds・policyは非認可のままとする。
- 実configからM1 candidate registryを再構築し、50/50方式が0.515 broad-role development score championかつdevelopment/confirmation accuracy leader、Disagreementがcoverage leaderのPareto challenger、TCNがdominatedであることを確認した。履歴championとforward候補の範囲に留め、authoritative運用へは自動昇格しない。
- M15棄却済みchronological expert stackingを、Disagreementと同じbaseline/Path/Extra Trees/LightGBM/TCNへC=0.10、stack 25%、方向維持、0.515のままM1固定移植した。各foldはprior OOSだけでfitし、test2020 fallbackを含む2,183,717行の整列を確認した。
- stack単体はbaseline比-193件でBrier/log loss/ECEも悪化。方向維持版はbaseline方向と完全一致しECEだけ改善したが、全行Brier/log lossは僅かに悪化した。0.515はall accuracy 52.0630% / coverage 21.0386% / score 0.008800だった。
- DisagreementとTransition guard 50/50 championには0.515 accuracy・score各0/7対7/7。champion比all accuracy差95%区間-0.6097〜-0.4304pt、score差-0.001241〜-0.000509、Brier/log loss悪化も確定したため棄却し、config・latest・oddsを発行しない。
- 確定済みM5/M15 OOS予測を最大age 15分でM1へbackward as-of結合し、C=0.10、25% weightを固定再検証した。元M1 2,183,717行中2,141,340行を結合でき、評価6foldは1,801,986行。M5 age中央値2分・最大14分、M15中央値7分・最大15分、未来context 0行を確認した。
- 全方向accuracyはaligned baseline比+194件、+0.0108ptだが、日次bootstrap 95%区間-0.0139〜+0.0352ptで未確定。Brier/log loss悪化区間は確定した。0.515 selection scoreはdevelopment・confirmation・allで低下し、現Transition guard championにaccuracy・score各0/6対6/6だった。
- champion比0.515はaccuracy -0.5908pt、score -0.000891で両bootstrap区間が悪化側に確定。高閾値でもchampion accuracyを上回らず過信が拡大したため、cross-TF metaを方向・confidenceとも再現専用として棄却し、config・latest・odds・policyを発行しない。
- M1の短期分布shiftを、直近128本の履歴順位、直近8本対直前非重複64本のlocation/scale・方向/tail占有率・candle pressure差の固定16列へ加工した。価格scale不変、未来不参照、flat全0、artifact/latest経路をテストし、baselineと同じ2,183,717 OOS行を7foldで生成した。
- Distribution Shift単体はbaseline比-465件で棄却したが、通常25% blendはdevelopment +485、confirmation +374、all +859件、accuracy/Brier/log lossを7/7fold改善した。日次bootstrapのaccuracyとproper scoreはdevelopment・confirmation・allすべて改善側だった。
- Pathにはaccuracy -83件だがBrier/log loss改善区間が確定。Extra Treesとはaccuracy -6件の同等でproper scoreを明確に改善し、confirmationも上回ったためstability研究役割を引き継ぐ。Volatility/Sessionとの直接差は未確定なので両候補を維持する。
- 方向維持0.51はall accuracy 51.7536% / coverage 35.6128% / score 0.009802。baseline比accuracy・score 6/7foldで、registryのdevelopment coverage leader/Pareto challengerへ採用した。Transition guard 0.515は精度とdevelopment scoreで維持する。局所校正が時期で反転しconfirmation down-lowがedge未確認なのでfair odds・policyは非認可とした。
- M15で固定済みの小型causal Transformerを、同じ16本×5加工系列、dimension 16、4-head、1層、2,625 parameter、8 epoch、train上限750,000、PlattのままM1へ移植した。7fold 2,183,717行はbaselineと完全整列し、全artifactでloss低下、確率欠損0を確認した。
- Transformer単体はbaseline比-1,667件で棄却。通常25%方向blendはdevelopment +301、confirmation +171、all +472件、accuracy/Brier/log lossを6/7fold改善したが、日次accuracy区間は全期間で0を跨ぎ、既存Path/Distribution Shiftの方向役割を超えなかった。
- 方向維持0.51はbaseline比accuracy 7/7、score 5/7fold、all 51.7312% / coverage 34.3071% / score 0.009477。confirmation accuracy差は改善側でもscore差は未確定で、Distribution Shift 0.51にscore 2/7、Transition guard 0.515にaccuracy 0/7だった。confirmation 0.55は24件だけでedge未確認のため、Transformerを再現専用として棄却しconfig・latest・oddsを発行しない。
- 親Distribution Shiftの54特徴を固定LightGBM 4.7.0、31 leaves、300 trees、learning rate 0.03、min child 100、row/column sample 0.8、L2 5、train上限750,000、Plattへ適用した。7fold 2,183,717行はbaseline/親HGBと完全整列し、保存artifact再読込とlatest推論を確認した。
- Shift × LightGBM単体はbaseline比-324件で、baseline-feature LightGBM単体にもall -0.0578pt、日次95%区間-0.1102〜-0.0044ptと悪化した。通常25% blendはall +287件、Brier/log loss 7/7foldでもaccuracy 3/7fold・日次区間0跨ぎのため方向候補へ追加しない。
- 方向維持0.51はbaseline比accuracy/score各6/7fold、all 51.7273% / coverage 36.1745% / score 0.009726。親HGBよりdevelopment coverage +0.4499ptだがscore 0.010333対0.010357で最大化対象を改善せず、confirmation 0.55も76件・accuracy 50%だった。再現専用として棄却し、親HGB Distribution Shift、config、odds、policyを維持する。
- 直近64完成M1足のreturn分布を、RMS正規化10/25/50/75/90%分位、Bowley/tail skew、中央spread比、L1/L2集中度の固定9列へ加工するRolling Distribution Shapeを実装した。全47特徴でscale不変、未来不参照、flat有限0、数値式、2,183,717 OOS行整列、artifact latest経路を確認した。
- Shape単体はbaseline比all +542件でもdevelopment -30件、日次accuracy区間はdevelopment/confirmation/allすべて0跨ぎ、Brier/log loss各2/7foldで不採用。通常25% blendもall +65件・p=0.792、accuracy 3/7foldで、proper scoreだけを理由に方向候補へ追加しない。
- 方向維持0.51はdevelopment 51.6506% / coverage 43.6951% / score 0.010065から、confirmation 51.7932% / 23.9284% / 0.007706へ反転し、baselineのaccuracy・coverage・scoreを全て下回った。Distribution Shiftにもaccuracy/score各1/7対6/7、confirmation 0.55は119件でedge未確認のため再現専用として棄却し、config・odds・policyを発行しない。
- 直近15完成M1足のjoint range内で、最初のopenから11時点のclose位置を表すRolling Full Pathを実装した。全49特徴でscale不変、未来不参照、flat有限0、式一致、2,183,717 OOS行整列、artifact latest経路を確認した。volume 6,025,170行は全0のため除外した。
- Full Path単体はbaseline比all +199件で不採用。通常25% blendはconfirmation +389件・日次accuracy区間改善、all +419件・Brier/log loss 6/7foldだったが、all accuracy区間は0を跨ぎ、既存Pathがdevelopment/allで有意に上回ったため方向候補へ追加しない。
- 方向維持0.515はall 52.1157% / coverage 21.1262% / score 0.009062でもconfirmation scoreが反転した。Disagreementはall accuracy 52.309% / score 0.009636、accuracy・score各6/7fold、3期間の日次bootstrapでも優位だった。confirmation 0.55は146件でedge未確認のため再現専用として棄却し、config・registry・odds・policyを発行しない。
- 現Transition guard × Disagreement championへ、各decisionまでに解決済みの直近90日だけを使うprequential hierarchical Beta correctness校正を実装した。global→固定confidence band→方向×volatilityを8,192/4,096/2,048で縮約し、未来correct非参照、方向不変、有限確率、2,183,717行・重複/欠損0を確認した。
- adaptive 0.515はall coverageを16.018%→17.799%へ広げたが、accuracyを52.583%→52.380%、scoreを0.009674→0.009376へ下げた。all accuracy差の日次区間は-0.3398〜-0.0675pt、Brier/log loss悪化区間も確定し、accuracy 1/7、score 3/7foldだった。
- confirmation 0.515もcoverage +5.028ptに対しaccuracy -0.828ptで悪化が確定し、0.55以上は0件。down-low/down-normal/up-lowの局所edgeも解消しないため再現専用として棄却し、raw champion、fair odds非認可、config・registry・policyを維持する。
- 直前64本で標準化したreturn/range innovationを、drift 0.25、alarm 5、score cap 20の正負CUSUMへ逐次蓄積するM1 Change-Point Stateを実装した。score/balance/alarm方向/ageの固定10列を追加し、scale不変、未来不参照、flat有限0、timestamp gap reset、48特徴artifact latest、2,183,717 OOS行整列を確認した。
- 単体はbaseline比all -460件。通常25%方向blendはall +265件、Brier/log loss 6/7foldでもaccuracy日次区間はdevelopment/confirmation/all全て0跨ぎだった。既存Pathがdevelopment/allで有意に上回りaccuracy・score各6/7fold勝ちのため方向候補へ追加しない。
- 方向維持0.515はbaseline比all accuracy 52.1185% / coverage 21.1789% / score 0.009087で、accuracy・proper scoreの3期間日次区間を改善した。ただしDisagreementはall accuracy +0.1904pt・score +0.000549、championはaccuracy +0.4642pt・score +0.000587、Distribution Shiftはcoverage +14.434pt・score +0.000715で、各役割の既存候補が優位だった。
- Change-Pointはall 0.55以上17,806件・55.0432%でもmean confidence 56.2125%と過信し、confirmationは170件だけだった。固定6セルのdown-low/down-normal/up-lowもedge未確認のため再現専用として棄却し、config・registry・odds・policyを発行しない。
- 直前64本で標準化したreturn/rangeの固定2σ event後を16本追跡し、shock方向/超過量/age、return response、最大continuation/reversal、range状態、同時eventの12列へ加工するM1 Shock / Recovery Stateを実装した。scale不変、未来不参照、flat有限0、gap reset、response式、50特徴artifact latest、2,183,717 OOS行整列を確認した。
- 単体はbaseline比all +598件でもp=0.201、Brier/log loss 2/7foldで不採用。通常25% blendはall +413件、accuracy/Brier/log loss 7/7foldでproper scoreの3期間日次区間も改善したが、accuracy区間はdevelopment/confirmation/all全て0を跨いだ。
- 既存Distribution Shift通常25%はShockよりaccuracy・score各6/7fold、Brier/log lossは3期間bootstrapで優位だった。方向維持0.51もShockのall 51.6585% / 36.1699% / 0.009312に対し、Shiftは51.7536% / 35.6128% / 0.009802、score 7/7foldで上回った。
- Shockのall 0.55以上は17,586件・54.7765%でもmean confidence 56.2100%と過信し、confirmation 0.55は156件、0.575以上0件だった。固定0.51も4/6セルだけedge確認のため再現専用として棄却し、config・registry・odds・policyを発行しない。
- M1 expanding training全体を保持し、sampled trainの最新decision timestampから730日ごとに重みを半減する `recency_half_life_730d` を実装した。0/730/1460日の比率1/0.5/0.25、平均1、timestamp guard、small pipeline、artifact latest経路をテストした。
- Recency単体はbaseline比all -1,686件で棄却。通常25%blendはall +621件、accuracy 5/7、Brier/log loss 6/7foldで、日次bootstrapもall accuracy・proper score改善を支持した。
- 通常blendは既存Distribution Shiftよりall accuracy/proper score点推定が低く、直接差区間も0を跨いだため同じ役割へ追加しない。方向維持0.515はbaselineを改善したが、同coverageのDisagreementにall accuracy +0.1144pt、score +0.000507と有意に負けた。
- confirmationのRecency 0.515は固定6セル中3セルだけedge確認、0.55以上112件、0.575以上0件だった。高信頼度をoddsへ使わず、config・registry・authoritative予測・fair odds・policyを変更しない。
- M15固定のDirectional-Clarity sample weightingを、重み式 `0.5 + abs(next body) / next range`、HGB/Platt、25% blendを変更せずM1へ移植した。train-only教師重み、平均1、全行保持、2,183,717 OOS行整列、artifact latest経路を確認した。
- 単体はbaseline比all +891件、accuracy 5/7、Brier/log loss 7/7fold。通常25% blendはdevelopment +596件、confirmation +272件、all +868件でaccuracy/Brier/log loss 7/7fold、all p=0.000219、日次bootstrapもall方向と3期間proper score改善を支持した。
- 通常blendはPathとall -74件で精度差未確定だがproper scoreは有意に良く、Distribution Shiftとは+9件で精度同等だがproper scoreが有意に悪かった。Extra Treesとは+3件、3勝3敗1分で、Session/Volatilityとのtradeoffも既存役割の中間に留まるため新規方向候補へ追加しない。
- 方向維持0.51はdevelopment改善がconfirmationで反転し、Distribution Shiftにaccuracy/score 1/7対6/7。confirmation 0.575以上0件、固定6セルも3/6だけedge確認のためconfidence・oddsには使わず、config・registry・policyを変更しない。
- M15固定のBody/ATR sample weightingを、0.5〜2.0教師重み、HGB/Platt、25% blendを変更せずM1へ移植した。train-only教師重み、平均1、全行保持、2,183,717 OOS行整列、artifact latest経路を確認した。
- 単体はbaseline比all -1,208件、accuracy 2/7、Brier/log loss 0/7foldで棄却。通常25% blendはdevelopment +483件、confirmation +230件、all +713件でaccuracy 7/7、Brier/log loss 6/7fold、all日次bootstrapも方向・proper score改善を支持した。
- 通常blendは同じ教師weight系のDirectional-Clarityよりall -155件でproper scoreも有意に悪く、Distribution Shiftにもaccuracy 2/7対5/7、proper scoreで敗れた。M1方向候補へ追加しない。
- 方向維持0.515はconfirmation accuracy +0.3108pt、score +0.000596で改善したが、Disagreementにall accuracy -0.1626pt、score -0.000658、score 0/7対7/7。confirmation 0.575以上0件、固定6セルも3/6だけedge確認のためM1 confidence・oddsには使わない。M15 0.54 forward candidateは維持する。
- M15固定のBody/ATR upper-half teacher filterを、各sampled train内中央値、HGB/Platt、25% blendを変更せずM1へ移植した。train-only教師選択、calibration/test全行保持、2,183,717 OOS行整列、artifact latest経路を確認した。
- 単体はbaseline比all -788件で棄却。通常25% blendはdevelopment +507件、confirmation +9件、all +516件、accuracy/Brier/log loss 6/7foldだった。日次bootstrapはdevelopment accuracyとdevelopment/all proper scoreを支持したが、confirmation/all accuracyは0を跨いだ。
- 通常blendは既存Distribution Shiftにall -343件、accuracy/score 1/7対6/7。方向維持0.51もShiftよりall accuracy -0.0762pt、coverage -0.1642pt、score -0.000478で、直接日次bootstrapは3指標すべてShift優位を支持したためM1方向・confidence候補へ追加しない。
- filter confidenceはall 0.55以上14,337件・55.2835%でもconfirmationは43件・44.1860%、0.575以上はconfirmation 0件だった。固定0.51もconfirmation 4/6セルだけedge確認のためfair oddsへ使わず、config・registry・authoritative予測・policyを変更しない。M15 0.525 forward candidateは維持する。
- PathとDistribution Shiftが反対方向を出す96,591行だけでPath正解確率を学ぶM1 chronological pairwise correctness gateを実装した。固定15列、Logistic C=0.10、閾値0.5で、各test foldより前のOOS不一致だけをfitし、test2020はPath fallbackとした。future target非参照、source整合、完全共線列除去、2,183,717行artifactを確認した。
- gateはPath比development +123件、confirmation -8件、all +115件、accuracy 4勝2敗1分、all p=0.5308だった。日次bootstrapのall accuracy差95%区間は-0.01136〜+0.02181ptで、proper score差も未確定のためPath point championを置換しない。
- Distribution Shift比はall +198件でもaccuracy区間が0を跨ぎ、Brier/log lossはdevelopment/confirmation/all全てShift優位が確定した。不一致gate accuracyもdevelopment 50.2931%からconfirmation 49.9947%へ反転したためstability/proper-score役割へ追加しない。
- gateの0.51 confidenceはPathとほぼ同一でconfirmation scoreが僅かに悪化し、0.525以上は完全一致した。残差gateを再現専用として棄却し、config・registry・authoritative方向/confidence・fair odds・policyを変更しない。
- 直近64完成M1 returnを固定DFT low/mid/high energy、low−high balance、k=1/2/4/8位相の12列へ加工するRolling Spectral Stateを実装した。scale不変、未来不参照、flat有限0、gap後64本reset、FFT厳密式、50特徴artifact latest、2,183,717 OOS行整列を確認した。
- Spectral単体はbaseline比all -136件で棄却。通常25% blendはdevelopment +145件、confirmation +108件、all +253件、accuracy 5/7foldだったが、p=0.3052、all日次accuracy区間-0.01115〜+0.03410ptで方向改善は未確定だった。Brier/log lossは3期間で有意に改善した。
- 通常blendはPathにaccuracy 1/7、Distribution Shiftに0/7foldで負け、Shift比Brier/log loss悪化もdevelopment・confirmation・allで確定した。両25% blendの固定50/50平均もShift比accuracy 1/7、Brier悪化、方向維持0.51 score -0.000228だったため多様化成分にも採用しない。
- Spectral confidence 0.51はall accuracy 51.6633% / coverage 35.8848% / score 0.009301で、Distribution Shiftの51.7536% / 35.6128% / 0.009802に日次bootstrapでも明確に負けた。all 0.55は17,368件・55.2741%でも約0.924pt過信、confirmationは124件だけなのでfair oddsへ使わず、config・registry・authoritative予測・policyを変更しない。
- 成果物QAで、共通OOS ensembleが更新後の`probability_up`/`confidence`に対して`probability_down`/`class_confidence`をbaseline値のまま残す不整合を検出した。補数と同一confidenceを必ず再計算するよう修正・回帰テスト追加し、今回の5 artifactを再生成した。評価は従来から`probability_up`を使用するため研究結果は不変である。
- 現在M1足をreturn方向、body/range、close位置、prior range中央値の4 bit・16状態へ加工し、結果確定済みの直前32/128本から同一状態next-up率をglobal up率へ固定強度8で縮約するRolling Transition Memory 9特徴を実装した。未来不参照、scale不変、flat/gap全0、厳密式、47特徴artifact latest、2,183,717 OOS行整列を確認した。
- Memory単体はbaseline比all -449件で棄却。通常25% blendはdevelopment +417件、confirmation +50件、all +467件、accuracy 6/7、Brier/log loss 6/7fold、p=0.0400だった。all日次bootstrapはaccuracy +0.0214ptとproper score改善を支持したが、confirmationの各区間は0を跨いだ。
- 通常blendはPathにaccuracy 2/7でconfirmation日次accuracyが有意に劣り、Distribution Shiftにaccuracy 3/7、Brier/log lossは3期間で有意に負けた。Path/Shiftへの固定50/50多様化追加も親候補を上積みしなかったため方向候補へ追加しない。
- 方向維持Memory 0.515はbaseline比all accuracy 52.1251% / coverage 21.0029% / score 0.009076で改善したが、Disagreementにaccuracy/score各1/7対6/7、Transition guardにaccuracy 0/7・score 1/7だった。all 0.55は17,525件・54.9330%でも約1.285pt過信、confirmationは143件だけなのでconfidence・fair oddsへ使わず、config・registry・authoritative予測・policyを変更しない。
- M1で固定したRolling Transition Memoryをwindow 32/128、4 bit・16状態、range基準20本、global shrinkage strength 8、HGB/Platt、25% weightのままM5へ移植した。5分gap、47特徴、M1/M5 artifact latest、正式baselineと439,881 OOS行完全整列を確認した。
- M5 Memory単体はbaseline比all -43件で棄却。通常25% blendはdevelopment +38件、confirmation +66件、all +104件、accuracy 4/7、p=0.2427で、日次方向区間は3期間とも0を跨いだ。proper scoreは3期間改善したが、既存Pressureよりall -32件でdevelopment/all proper scoreも有意に悪かった。
- M5 Memory 0.515はbaseline比confirmation accuracy 52.3550%→52.4533%、coverage 37.2423%→36.5559%、score 0.011993→0.012454、accuracy/score 5/7、proper score 6/7foldだった。ただしaccuracy/scoreの日次区間は0を跨ぎ、既存Profileよりall accuracy -0.0077pt、coverage -0.3401pt、score -0.000119でproper scoreも悪かった。
- M5 Memory 0.55はProfileを点推定で上回ったが、baselineにはall accuracy 56.0633%対56.0761%、score 0.012605対0.012865、fold 3/7対4/7で未達。confirmationは613件、test2026途中は108件・49.0741%、0.60はconfirmation 0件だった。Profile/Pressureとの固定50/50追加も親を上積みせず、M5でも再現専用としてconfig・registry・odds・policyを変更しない。
- M1仕様のRolling Transition Memoryを再探索せずM15/M30へ移植し、正式baselineとM15 145,140行、M30 71,260行を完全整列した。M15単体はbaseline比all +67件、accuracy 5/7foldでもall日次差95%区間-0.1147〜+0.2102pt、Brier/log lossは悪化し、通常25% blendはall -38件だった。既存Pressureはall accuracy・proper scoreで上回った。
- M15方向維持0.525はbaseline比developmentを改善したがconfirmationのaccuracy・coverage・scoreが反転した。既存Signed-body Quantileよりall accuracy -0.1604pt、coverage -0.3569pt、score -0.001049、年別accuracy/score 2/7対5/7だった。固定50/50平均も親を下回り、confidence・多様化候補へ追加しない。
- M30 Memory単体はdevelopment -176件でp=0.0272、通常25% blendもall -52件だった。0.515はbaselineのaccuracy・coverage・scoreを全期間区分で下回り、0.52は既存Pressureよりall accuracy -0.1613pt、score -0.001028。固定50/50平均はPressureにaccuracy/score 0/7対7/7で、追加価値がなかった。
- M30 Memory 0.575はall 990件・coverage 1.3893%・accuracy 57.6768%でも、baseline比accuracy差区間-0.8659〜+1.8454pt、Pressure比-1.1846〜+1.9981ptだった。test2020は21件・47.6190%、2foldは0件、約1.33pt過信のためfair oddsへ使わない。M15/M30移植も再現専用とし、既存候補、config、registry、authoritative予測、policyを変更しない。
- M15/M30で基準、baseline、Shape、ProfileのOOS確率と現在足regimeを24列へ加工し、各test foldより前のOOS正誤だけでLogistic C=0.10をfitするPrequential Selective Correctnessを実装した。test2020は元confidence fallbackとしてnested評価から除外し、確率0.5のdown tie不整合をQAで検出後、0.5±epsilonへ修正・全再生成した。
- M15 nested development選択0.53はSigned-body Quantile 0.525よりdevelopment score 0.016337対0.017935、confirmation 0.013715対0.016888で下回った。0.55もStructureよりdevelopment accuracy -0.8319pt、all -0.6783ptの日次区間が悪化側で、proper scoreも有意に悪かった。
- M30 nested development選択は0.50の全件採用まで崩れ、Pressure 0.52よりdevelopment/confirmation scoreが低かった。0.55はPressure比confirmation accuracy +2.3217ptでも区間-0.6064〜+5.2165pt、development -2.0245ptとall -1.5721ptは有意に悪化した。
- 両時間足とも0.55はdevelopmentで約4.0〜4.6pt過信しconfirmationで過小評価へ反転した。selective model、precision tail、fair oddsへ採用せず、研究再現専用としてconfig・registry・authoritative confidence・policyを変更しない。
- M15/M30で基準/Shape/Profileの内部candidate方向が2/3または3/3一致する場合だけ元confidenceを通す固定Component Consensus Filterを実装した。fit・係数・target情報を使わず、不一致行は0.5±epsilonへ戻す。145,140/71,260行整列、future target変更不影響、support厳密値、方向・確率・confidence整合を確認した。
- M15 2/3は0.525 laneからdevelopment 21件、confirmation 0件しか除外せず実質無作用だった。3/3はdevelopment accuracy +0.0861ptとproper score、all accuracy +0.0563ptを日次bootstrapで改善したが、confirmationはaccuracy -0.0106pt、coverage -0.1498pt、score -0.000114だった。
- M15 3/3がvetoした0.525 laneはdevelopment 611件・49.4272%からconfirmation 84件・55.9524%へ反転した。selection score差区間も全期間で0を跨ぎ、年別score 3/7対4/7のため採用しない。
- M30 2/3はaccuracy・coverage・scoreを3期間全て下げ、3/3もaccuracy微増よりcoverage減少が大きくscoreはdevelopment -0.000831、confirmation -0.000276、all -0.000632だった。両規則ともBrier/log lossが悪化し、固定consensusをconfig・registry・fair odds・policyへ追加しない。
- 完成M15/M30足の連続3 returnを6順序patternへ変換し、32/128本のmotif比率・正規化entropy・現在頻度・短長差からなるRolling Ordinal Motif 18特徴を実装した。手計算一致、scale不変、未来不参照、flat/gap全0、56特徴artifact/latest、正式baselineとの145,140/71,260 OOS行整列を確認した。
- M15 Motif単体・通常25% blendはaccuracyがdevelopment/confirmationともbaselineより悪く、方向維持0.525は既存Signed-body Quantileにaccuracy/score 2/7対5/7、all score差bootstrapも悪化側だった。0.55もconfirmationで反転したためM15用途へ採用しない。
- M30 Motif通常25% blendはbaseline比development +24件、confirmation +25件、all +49件、Brier/log loss 5/7foldで、all proper scoreの日次区間は改善を支持した。accuracy差区間はbaseline、既存Pressureの双方に対して0を跨ぐため、Motif単独は多様化素材に限定する。
- M30 Motif方向維持0.55はbaseline比all accuracy +0.6667ptでもconfirmationは+0.0679ptだけで、Pressure 0.55よりconfirmation -0.7042ptだった。固定50/50 confidence平均もconfirmation accuracy/scoreを悪化させ、M30 confidence、fair odds、policyへ使わない。
- Pressure通常25%とMotif通常25%の固定50/50方向平均はbaseline 75% + Pressure 12.5% + Motif 12.5%となる。baseline比development/confirmation/allのaccuracy・Brier/log loss点値を全て改善し、accuracy 5/7、Brier/log loss 6/7fold。all Brier/log loss差の日次区間も完全に改善側だった。
- 固定方向平均は既存Pressure方向blend比development +55件、confirmation +32件、all +87件、accuracy 6/7fold。all accuracy差+0.1221ptの日次95%区間は+0.0071〜+0.2359ptで、proper score悪化区間は0を跨いだ。predicted side 2/2、volatility 3/3でも点accuracyを上回った。
- `m30_pressure_ordinal_motif_direction_candidate_v1.json` にM30 parallel方向候補として固定する。authoritative baseline比accuracy区間は0を跨ぎruntime parityも未発行なので、authoritative方向/confidence、Pressure 0.52、fair odds、adoption/paper/live policy、runtime latestは変更しない。
- 完成M15/M30 returnを32/128本のcausal ridge AR(3)へ加工し、係数・正規化forecast・fitted energy・prior-model innovation・短長差からなるRolling Autoregressive State 15特徴を実装した。厳密ridge解、scale不変、未来不参照、flat/gap全0、53特徴artifact/latest、正式baselineとの145,140/71,260 OOS行整列を確認した。
- M15通常25% blendはbaseline比all -1件、accuracy 2/7foldで、0.525はSigned-body Quantileにaccuracy/score 0/7対7/7、0.55もconfirmationで反転した。M15方向/confidenceへ使わない。
- M30通常25% blendはbaseline比development +17件、confirmation -4件、all +13件、accuracy 5/7、Brier/log loss 6/7foldだったが、現行Pressure + Ordinal Motif方向候補より-24件で、固定方向平均も親を上積みしなかった。M30方向へ追加しない。
- M30 AR 0.52は既存Pressureにaccuracy/score 2/7対5/7で棄却。0.55単独はall 4,630件・56.0475%・coverage 6.4973%・score 0.011760でPressureを点推定上回ったが、accuracy 3/7foldかつ日次accuracy/score区間は0を跨いだため置換しない。
- PressureとAR confidenceの固定50/50 selector 0.55はdevelopment/confirmation/allのaccuracy・coverage・scoreを全て上げ、all 4,412件・56.1423%・coverage 6.1914%・score 0.011629、score 6/7foldだった。日次bootstrapはcoverage差+0.1527〜+0.2838ptのみ確定しaccuracy/scoreは未確定なので、`m30_pressure_ar_confidence_shadow_v1.json` のparallel forward shadowに限定する。authoritative confidence、fair odds、policy、runtime latestは変更しない。
- 次候補のrun-hazard加工は、既存Path PersistenceとDirection Transition Stateがrun length・方向別persistence・反転率・階層遷移を既に扱うため、独立性不足として実装前に中止した。履歴結果に合わせたrun定義の再加工は行わず、M1固定LightGBM学習フローの未検証M30移植へ切り替えた。
- baseline 38特徴、LightGBM 4.7.0、31 leaves、300 trees、learning rate 0.03、min child 100、row/column 0.8、L2 5、Platt、標準損失1.0を変更せずM30固定7foldへ移植した。71,260 OOS行整列と最終fold artifactからのlatest推論を確認した。
- LightGBM単体はbaseline比development +2件、confirmation +62件、all +64件。通常25% blendはdevelopment -7件、confirmation +44件、all +37件、accuracy 4/7、Brier/log loss 6/7foldで、現行Pressure + Ordinal Motif方向候補とall正解数が同率だった。
- 現行方向候補とLightGBM通常blendの固定50/50平均はbaseline 75% + Pressure 6.25% + Ordinal Motif 6.25% + LightGBM 12.5%となる。baseline比development +16件、confirmation +37件、all +53件。parent比development +2件、confirmation +14件、all +16件、accuracy 5/7foldで、all Brier/log loss/ECE点値も改善した。
- 固定方向平均のbaseline比日次bootstrapはall Brier差-0.00005756〜-0.00002104、log loss差-0.00011604〜-0.00004248で改善を支持した。accuracy差+0.0744ptの区間は-0.0474〜+0.1975pt、parent比+0.0225ptも-0.0743〜+0.1177ptで未確定なため、`m30_pressure_ordinal_lightgbm_direction_candidate_v1.json` のparallel co-challengerとしparentを置換しない。
- M30 LightGBM confidenceはdevelopment選択0.515がconfirmationで反転した。0.55も既存Pressure + AR shadowにaccuracy 2/7、score 3/7で、Pressure・AR・LightGBMの固定3等分は親shadowよりall accuracy・scoreと各5/7foldで悪化した。confidence、fair odds、policyへ使わない。
- M15/M1からparameterを変えず、Extra Trees 200本、depth 12、min leaf 50、max features 0.75、baseline 38特徴、Platt、標準損失1.0をM30固定7foldへ移植した。71,260 OOS行整列と最終fold artifactのlatest推論を確認した。
- Extra Trees単体はbaseline比development +38件、confirmation +34件、all +72件、accuracy 4/7、Brier/log loss 5/7fold。all Brier/log loss差の日次bootstrap区間は改善側だったが、accuracy差+0.1010ptの区間は-0.1922〜+0.3958pt、ECEは0.1608%→0.2023%へ悪化した。
- 通常25% blendはdevelopment +59件、confirmation +4件、all +63件、Brier/log loss 6/7foldで校正点値は良いが、確認期間の方向増分が弱いため採用しない。Extra Trees単体は現行Pressure + Ordinal + LightGBM co-challenger比development +22件、confirmation -3件、all +19件、accuracy 4/7対3/7だったが、accuracy/proper scoreの直接bootstrap区間は全て0を跨いだ。
- 現行co-challengerとExtra Trees通常blendの固定50/50平均はall僅か+1件、年別2/7で、confirmationを悪化させたため棄却する。Extra Trees単体だけを `m30_extra_trees_direction_challenger_v1.json` のparallel standalone確率品質challengerへ固定し、現行方向候補とauthoritative方向は置換しない。
- Extra Trees confidenceはdevelopment選択0.515がconfirmationで反転した。固定0.55も既存Pressure + AR shadowよりall accuracy 56.1423%→55.7949%、score 0.011629→0.011133、accuracy/score各3/7対4/7だったため、confidence、fair odds、policyへ使わない。
- M1/M15固定のHaar Multiscaleを、4/8/16/32本×return・absolute-return構成・方向平均の前半後半差12列、HGB/Platt、標準損失1.0のままM30へ移植した。71,260 OOS行整列、scale不変・未来不参照の既存テスト、最終fold artifactのlatest推論を確認した。
- Haar単体はbaseline比development +80件、confirmation +41件、all +121件、accuracy 5/7fold、ECE 0.1608%→0.0452%。通常25% blendは+52件、accuracy/Brier/log loss 5/7foldだが現行co-challengerよりall -1件でconfirmationも弱いため採用しない。
- Haar単体は現行Pressure + Ordinal + LightGBM co-challenger比development +64件、confirmation +4件、all +68件、accuracy 4/7fold。Extra Trees単体にもall +49件、accuracy 5/7foldだったが、両直接bootstrapのaccuracy/proper score区間は0を跨いだ。
- 現行co-challengerとHaar単体の固定50/50平均はbaseline比development +89件、confirmation +43件、all +132件、accuracy 6/7fold。parent比+73/+6/+79件、5/7fold、Haar比+11件となり、all accuracy 51.9927%、Brier 0.249427476、log loss 0.692000846だった。
- 固定平均のbaseline比日次bootstrapはall Brier差-0.00012372〜-0.00001847、log loss差-0.00024876〜-0.00003718で改善を支持した。accuracy差+0.1852ptは-0.0224〜+0.3928pt、parent比+0.1109ptも-0.0836〜+0.3016ptで未確定なため、`m30_pressure_ordinal_lightgbm_haar_direction_candidate_v1.json` のparallel co-challengerへ固定しparentを置換しない。
- Haar confidenceはdevelopment選択0.515でbaselineを下回り、0.52もPressureにaccuracy 1/7、score 2/7。固定方向平均0.55はall accuracy/score点値をPressure + ARより上げたが、confirmation score低下と年別3/7のためconfidence、fair odds、policyへ使わない。
- M1/M15固定のPath Persistenceを、5/10/20/50本efficiency、10/20本自己相関・反転率、50本variance ratio、20本方向持続率・streakの14列、HGB/Platt、標準損失1.0のままM30へ移植した。71,260 OOS行整列と最終fold artifactのlatest推論を確認した。
- Path単体はbaseline比development -167件、confirmation +7件、all -160件、accuracy 1/7fold。通常25% blendは+36/+4/+40件でもaccuracy 3/7で、Haar入り方向co-challengerよりall -92件。方向candidateやHaar候補への追加平均は採用しない。
- 方向維持Path 0.52はbaseline比development/confirmation/allのaccuracy・selection score点値とBrier/log loss 6/7foldを改善した。日次bootstrapもBrier/log loss改善を3期間で支持したが、all accuracy差区間-0.0347〜+0.3971pt、score差-0.000401〜+0.002215で未確定、coverageは-0.8239〜-0.4847ptへ低下した。
- Path 0.52はPressure 0.52にdevelopmentで負けconfirmationで勝ち、年別accuracy/score 4/7対3/7だったが、all accuracy 53.6671%対53.7577%、score 0.018557対0.019034でPressureが上だった。直接bootstrapも各差を確定できないため、新しいbroad confidence候補へ追加しない。
- PressureとPathの固定50/50 confidence平均は0.52でPressureにaccuracy/score 2/7、0.55でPressure + AR shadowに3/7。Pathの確率平滑化感度だけを保存し、config・registry・authoritative confidence・fair odds・policyを変更しない。
- M1/M15固定のSession Relativeを、曜日×UTC時刻groupのprior 32/min 12、5列、HGB/Platt、標準損失1.0のままM30へ移植した。group warmupでtest2020先頭44行だけを除き、baseline・既存候補と71,216 OOS行をtimestamp/targetで厳密整列し、最終fold artifactのlatest推論を確認した。
- Session単体はbaseline比development -61件、confirmation +77件、all +16件、accuracy 4/7fold、Brier/log loss 6/7fold。通常25%は-27/+14/-13件、3/7foldで、Haar入り方向候補への直接比較もaccuracy 2/7対5/7だったため方向用途へ採用しない。
- 方向維持Session 0.52はbaseline比accuracy/score点値を3期間で上げ、development/allのBrier/log loss日次区間も改善したが、all accuracy差区間-0.0109〜+0.4130pt、score差-0.000124〜+0.002461で未確定、coverageを-0.3633〜-0.0507pt下げた。
- Session 0.52はPressureよりconfirmation accuracy/scoreを上げたが、all accuracy 53.6898%対53.7641%、score 0.018828対0.019071、年別3/7対4/7だった。直接bootstrapで確定したのはcoverage増加だけで、proper score増分もない。
- PressureとSessionの固定50/50 confidence平均は0.52でPressureにaccuracy/score 1/7、0.55でPressure + AR shadowに2/7。periodic regimeの確率平滑化感度だけを保存し、config・registry・authoritative confidence・fair odds・policyを変更しない。
- M1/M15固定のVolatility Stateを、vol-of-vol・加速度・range状態・圧縮・jump・OHLC分散balanceの11列、HGB/Platt、標準損失1.0のままM30へ移植した。baseline・既存候補と71,260 OOS行を完全整列し、最終fold artifactのlatest推論を確認した。
- Volatility単体はbaseline比development -43件、confirmation +15件、all -28件、accuracy/Brier/log loss各3/7fold。通常25%は+16/-22/-6件、accuracy 2/7foldで、Haar入り方向候補に1/7対6/7だったため方向用途へ採用しない。
- 通常25%方向blendはall Brier/log lossの日次bootstrap区間を改善したが、accuracy差区間-0.1384〜+0.1211ptは0を跨いだ。aggregate確率平滑化だけを方向edgeと解釈しない。
- 方向維持Volatility 0.515はbaseline比all accuracy・coverage・scoreを下げ、年別3/7対4/7。Pressure 0.52にはaccuracy 0/7、score 3/7で、0.55もPressure + ARにaccuracy 2/7、score 1/7だった。
- PressureとVolatilityの固定50/50 confidence平均は0.52でPressureにaccuracy/score 2/7。0.55は年別accuracy 5/7でもall accuracy・coverage・scoreをPressure + ARより下げ、日次bootstrapもcoverage低下だけを確定した。M30 config・registry・authoritative予測・fair odds・policyを変更しない。
- baseline加工38特徴をXGBoost 300 trees、depth 4、learning rate 0.03、min child weight 20、row/column 0.8、L2 5、hist、Platt、標準損失1.0の固定仕様でM30へ移植した。71,260 OOS行を完全整列し、最終fold artifactのlatest推論を確認した。
- XGBoost単体はbaseline比development -35件、confirmation +10件、all -25件、accuracy 3/7fold。通常25% blendは-35/-9/-44件、accuracy 3/7foldで、単体もHaar入り方向候補にaccuracy 1/7対6/7だったため方向用途へ採用しない。
- 通常blendはall Brier/log lossの日次bootstrap区間を改善したが、accuracy差-0.0617ptの95%区間は-0.1889〜+0.0645ptだった。aggregate確率平滑化だけを方向edgeと解釈せず、劣る親モデルとの追加方向平均も行わない。
- 方向維持XGBoost 0.515はbaseline比all coverage +0.4757pt、accuracy +0.0021pt、score +0.000122で、proper scoreも改善した。しかしconfirmation accuracy -0.0656pt、score -0.000313へ反転し、Pressure 0.52にはaccuracy 0/7、score 3/7だった。0.55もPressure + ARにaccuracy 1/7、score 2/7で負けた。
- PressureとXGBoostの固定50/50 confidence平均は0.52でPressureにaccuracy 2/7、score 3/7。0.55はall coverage +0.1558ptでもaccuracy -0.0512pt、confirmation score -0.000495で、objective差区間はいずれも0を跨いだ。M30 config・registry・authoritative予測・fair odds・policyを変更しない。
- M1固定のDirectional-Clarity sample weightingを、次足body/rangeから作る0.5〜1.5・平均1のtrain weight、baseline 38特徴、HGB/Platt、全教師、標準損失1.0のままM30へ移植した。未来足情報はtrain weightだけへ使い、71,260 OOS行整列とlatest推論を確認した。
- Clarity単体はbaseline比development +66件、confirmation +77件、all +143件、accuracy 4/7fold。通常25% blendは+27/+5/+32件、accuracy 4/7fold、Brier/log loss 6/7foldだった。単体all accuracy差+0.2007ptの日次区間は-0.0673〜+0.4725ptで未確定だった。
- Clarity単体は現行Haar入り方向候補よりdevelopment -23件、confirmation +34件、all +11件、年別3/7対4/7。固定50/50方向平均はbaseline比+106/+54/+160件、5/7foldでdevelopment/all proper score区間も改善したが、親比は+17/+11/+28件、3/7foldで直接差区間を確定できなかった。新しい方向候補へ追加しない。
- 方向維持Clarity 0.51はbaseline比all coverage +0.8855pt、accuracy +0.0572pt、score +0.000601でもconfirmation accuracy/scoreが反転した。Pressure 0.52にはaccuracy 0/7、score 1/7で、broad confidenceへ使わない。
- Clarity 0.55はPressure + ARにall score +0.000014、confirmation score +0.000840でもdevelopment score -0.000320、年別accuracy 3/7、score 4/7で差区間は0を跨いだ。Pressureとの固定50/50平均はall score +0.000129でもconfirmation score -0.000571、年別accuracy/score各2/7だった。config・registry・authoritative予測・fair odds・policyを変更しない。
- M1固定のBody/ATR sample weightingを、次足body/判定時ATRから作る0.5〜2.0・平均1のtrain weight、baseline 38特徴、HGB/Platt、全教師、標準損失1.0のままM30へ移植した。未来足情報はtrain weightだけへ使い、71,260 OOS行整列とlatest推論を確認した。
- Body/ATR単体はbaseline比development -132件、confirmation -13件、all -145件、accuracy/Brier/log loss各2/7fold。通常25% blendは-35/+8/-27件、accuracy 3/7foldで、all accuracy・proper scoreの日次区間は0を跨いだため方向用途へ採用しない。
- 通常25% blendはDirectional-Clarityよりdevelopment -62件、confirmation +3件、all -59件、年別3/7対4/7。日次bootstrapはall Brier/log lossでClarity優位を支持したため、絶対振幅教師を相対的な方向明瞭度教師へ追加しない。
- 方向維持Body/ATR 0.515はbaseline比all coverage -1.1255pt、accuracy -0.0774pt、score -0.000793で、confirmation accuracy -0.2850pt、score -0.002053へ反転した。Pressure 0.52にはaccuracy 0/7、score 1/7、0.55もPressure + ARにaccuracy/score各3/7だった。
- Pressureとの固定50/50 confidence平均は0.52でPressureにaccuracy 2/7、score 3/7。0.55はall点accuracy +0.0243ptでもcoverage・scoreを下げ、confirmation accuracy 54.9296%対56.0088%、score 0.002762対0.004997へ悪化した。M15候補は独立維持し、M30 config・registry・authoritative予測・fair odds・policyを変更しない。
- 次足body/rangeと方向側close到達度の積を0〜1の教師品質へ加工し、0.5〜1.5・平均1の `train_weighting=directional_follow_through` を追加した。未来OHLCはtrain sample weightだけへ使い、特徴・calibration・test・latestへ渡さない。境界、平均、非漏洩、artifact/latestをテストした。
- M30 Follow-through単体はbaseline比development +22件、confirmation +90件、all +112件、accuracy 4/7fold。日次bootstrapはdevelopment/all Brier/log loss改善を支持したがaccuracy区間は0跨ぎ、通常25% blendは-3/-2/-5件・accuracy 2/7foldだった。
- Follow-through単体はClarityに-44/+13/-31件、Extra Treesに-16/+56/+40件、Haar方向候補に-67/+47/-20件で、各直接accuracy差を確定できなかった。新しい方向candidateへ追加しない。
- Haar親との固定50/50平均は親比+3/-3/0件、accuracy 4/7foldで方向増分はなかったが、Brier/log lossの日次区間をdevelopment/confirmation/allで改善した。この確率を固定0.55だけで高信頼度監査した。
- 固定平均0.55はPressure + AR比all coverage 7.0937%対6.1914%、accuracy 56.6568%対56.1423%、score 0.014079対0.011629、accuracy 4/7、score 6/7fold。日次bootstrapはdevelopment/all score、all coverage・proper score改善を支持した。confirmation scoreは0.004971対0.004997で同等域だった。
- 0.55 all accuracy 56.6568%とmean confidence 56.6480%は整合したが、confirmationのup-low/up-normalが疎く不安定である。同履歴から除外guardを作らず、`m30_haar_directional_follow_through_confidence_shadow_v1.json` のparallel forward shadowに限定する。authoritative confidence、Pressure + AR、fair odds、policyは変更しない。
- M30で固定したDirectional Follow-through教師重みを、式、baseline 38特徴、HGB/Platt、25% blend、標準損失1.0のままM5へ移植した。439,881 OOS行を既存baseline・Pressure・Profileと完全整列し、artifact latest推論を確認した。
- 単体はbaseline比-162/+105/-57件、通常25%方向blendは+4/+47/+51件だった。通常blendは現行Pressure方向候補に-115/+30/-85件、accuracy 1/7対6/7で、proper scoreも劣るため方向候補へ追加しない。
- 方向維持0.515はProfileよりall coverage +2.3456ptでもaccuracy -0.0597pt、confirmation score -0.000010、all score差の日次区間0跨ぎ、Brier/log loss悪化だった。Profile broad confidenceを維持し、固定50/50 confidence平均も使わない。
- 固定0.55はProfile比all coverage 5.8368%対5.4333%、accuracy 56.1597%対55.8828%、score 0.013413対0.012243、score 7/7foldだった。日次bootstrapはall accuracy・coverage・score改善を支持し、追加3,391件も56.9154%正解だった。
- 0.55のmean confidence 56.3320%は実測56.1597%と局所整合したが、confirmationは1,277件でruntime parityも未達である。`m5_directional_follow_through_high_confidence_shadow_v1.json` のparallel shadowに限定し、Pressure方向、Profile 0.515、authoritative confidence、fair odds、policyを変更しない。
- Directional Follow-through教師重みを式、baseline 38特徴、HGB/Platt、通常/方向維持25%、標準損失1.0のままM15へ移植した。145,140 OOS行を既存baseline・方向・confidence候補と完全整列し、artifact latest推論を確認した。
- 単体はbaseline比-65/-14/-79件、通常25%方向blendは-14/-40/-54件、accuracy 0/7foldだった。通常blendはPressure方向に-65/-76/-141件、固定50/50平均もparentに-106件。Directional-Clarity単体にもall -90件で、方向用途へ採用しない。
- 方向維持0.53はbaseline比development accuracy/scoreと3期間proper scoreを改善したが、confirmation scoreは僅かに反転した。all accuracy 54.4998%とmean confidence 54.6705%は局所整合した。
- 各role championとの固定閾値比較はProfile 0.515にaccuracy/score各1/7、Signed-body Quantile 0.525に0/7、Full Path 0.53に3/7、Structure 0.55に1/7だった。Full Path比confirmation accuracyとall proper scoreのbootstrap区間も明確に劣った。
- Full Pathとの固定50/50 confidence平均はparent比score 2/7対5/7。Follow-through 0.55はall accuracy 55.4375%対mean confidence 56.5524%でWilson上限を超えて過信した。M15ではconfig・registry・authoritative予測・fair odds・policyを変更しない。
- 同じDirectional Follow-through教師重みをM1へ固定移植し、baseline 38特徴、HGB/Platt、全教師、expanding、通常/方向維持25%、標準損失1.0で2,183,717 OOS行とartifact latest推論を確認した。
- 単体はbaseline比+10/+636/+646件、通常25%方向blendは+301/+175/+476件でaccuracy/Brier/log lossを7/7fold改善した。しかし通常blendはPath/Shiftにaccuracy各2/7、Directional-Clarityに0/7・1 tieで、Clarity比all accuracy bootstrap区間も劣った。
- 方向維持0.515はbaseline比development/confirmation/allのaccuracy・coverage・score・proper scoreを日次bootstrapで改善し、accuracy/score 6/7、Brier/log loss 7/7foldだった。ただしTransition guardにaccuracy 0/7、score 1/7、Disagreementに0/7、Distribution Shiftにscore 2/7だった。
- Transition guardとの固定50/50 confidence平均はparent比accuracy 0/7、score 2/7。Follow 0.55はall 18,075件・54.8769%でも1.3288pt過信、confirmation 119件でedge未確認、0.575はconfirmation 0件だった。M1ではconfig・registry・authoritative予測・fair odds・policyを変更しない。
- M1 Transition guard 0.515とDistribution Shift 0.51を、確率を混ぜずfirst/second/union/intersectionの固定採用集合として比較した。全2,183,717行のkey・方向を整列し、各source confidenceの局所整合と明示boolean採用列の日次bootstrapも追加した。
- guard集合はall 349,784行中349,101行がShiftと共通で99.80%以上包含された。guard-onlyは683行・52.1230%だがWilson下限48.3751%、confirmationは23行・43.4783%で、独立した追加edgeを確認できなかった。
- union−Shiftとintersection−guardの日次bootstrapはdevelopment/confirmation/allのaccuracy・selection scoreが全て0跨ぎで、確定したのは最大0.0313ptのcoverage増減だけだった。development目的関数首位も既存guardのままである。
- developmentではguard confidenceが集合内実績に整合したが、confirmationはguard laneでmean 51.9539%に対し実績53.3560%、Shift laneで51.5327%に対し51.8985%となり期間間で過信から過小評価へ移った。集合演算は新しい各行oddsを定義しないためunion/intersectionを再現専用とし、既存3 confidence役割、config・registry・fair odds・policyを変更しない。
- 正式configを持つM1 confidence 4候補、TCN 0.515、Disagreement 0.515、Transition guard 0.515、Distribution Shift 0.51の全6 pairを固定採用集合で一括監査した。developmentではunionが両親の目的関数を上回り、両exclusive集合のWilson下限が50%超の場合だけ選択し、confirmationを選択へ使わない。
- development gateを通ったのはDisagreement + Shiftだけで、union scoreは良い親より+0.0000454、Disagreement-only 6,079行・51.6203%・Wilson下限50.3634%、Shift-only 224,632行・50.9683%・下限50.7615%だった。
- confirmationではDisagreement-onlyが386行・48.1865%・Wilson下限43.2442%へ反転し、union scoreはShift 0.008142に対し0.008116へ低下した。他5 pairはdevelopmentで棄却済みである。
- 20,000回日次bootstrapではunion−Shiftのdevelopment/confirmation/all score差が全て0跨ぎで、coverage増加だけが確定した。union−Disagreementは3期間でaccuracy低下が確定しscoreは未確定。source confidenceもdevelopment過信からconfirmation過小へ反転したため、全pairを再現専用とし既存候補・fair odds・policyを変更しない。

133. 流動性摩擦をOHLC水準ではなくCorwin–Schultz実効spread、Roll自己共分散spread、Parkinson range/close energy、prior-only near-zero return率の固定10特徴へ加工した。0〜1境界、scale不変、未来不参照、gap reset、flat全0、48全特徴のraw OHLC排除、train/latestをテストした。M5 Windows canonicalの439,881 OOS行で単体はbaseline比-291件、通常25%方向blendは-33件で方向用途を不採用。方向維持25% confidenceのdevelopment固定0.515はbaseline比accuracy/score各6/7fold、all accuracy +0.04833pt、score +0.000278だが、20,000回日次bootstrap区間はaccuracy -0.00254〜+0.09915pt、score -0.000083〜+0.000639で未確定。Profileに対しdevelopment score +0.000347がconfirmation -0.000639へ反転し、all Brier/log lossは95%区間で有意に悪化した。Profileとの固定50/50 confidence平均もconfirmation 3/3、全体で5/7fold負けた。0.55はProfile比all accuracy/scoreが低く、特徴実装とWindows成果物は再現用に保存するがconfig・registryに採用しない。Profile 0.515、Follow-through 0.55 shadow、authoritative confidence・fair odds・policyを維持し、window・特徴subset・weight・閾値を同じ履歴で再探索しない。共有高負荷処理を停止せず、単独8 thread・nice/I/O低優先度・CPU only・標準損失1.0で実行した。

134. Variance Ratio案は既存Path Persistenceのvariance ratio・自己相関・方向持続性と重複するため実装前に中止し、独立なEWMA Asymmetry Stateへ切り替えた。半減期4/16/64のreturn innovation・drift/volatility、cross-scale volatility balance、上下energy balance、lagged-return×current-variance leverage momentの固定12特徴を追加し、[-1,1]境界、scale不変、未来不参照、gap reset、flat全0、50全特徴のraw OHLC排除、厳密式、train/latestをテストした。M5 Windows canonical 439,881 OOS行で単体方向はbaseline比-8件、通常25%方向blendは+21件・p=0.81931のため方向用途は不採用。方向維持25% confidenceのdevelopment固定0.515はbaseline比accuracy 5/7、score 6/7、Brier/log loss 7/7fold、confirmation accuracy +0.11681ptのbootstrap区間+0.01697〜+0.21539pt、score +0.000681の区間+0.000069〜+0.001283、all Brier/log lossも改善側だった。Profile 0.515とはall accuracy +0.01266pt、score +0.000080で区間0跨ぎ、confirmationは-0.03279pt。固定50/50もconfirmationを下げるため置換・stackせず、`m5_ewma_asymmetry_confidence_candidate_v1.json` のWindows canonical parallel broad候補として採用する。confirmation 0.515はmean confidence 52.48282%と実測52.48281%が整合したが、down-normalは4,297件・50.6633%・Wilson下限49.1685%でedge未確認。同履歴からfilterを作らず、0.55も最新229件・47.5983%のため不採用。Profile 0.515、Follow-through 0.55、authoritative confidence・fair odds・policyを維持する。共有高負荷処理を停止せず、単独8 thread・nice/I/O低優先度・CPU only・標準損失1.0で実行した。

135. M5採用EWMA Asymmetryを定義・半減期・HGB/Platt・25% weight・閾値grid・標準損失1.0のままM15へ固定移植した。Windows canonical 145,140 OOS行で単体方向はbaseline比-87件、通常25%方向blendは-10件・p=0.87712のため不採用。方向維持0.515はbaseline比accuracy 5/7、score 4/7、Brier/log loss 6/7foldで、development/confirmation/allのaccuracy・score点値とconfirmation/all proper scoreを改善したが、accuracy・scoreの20,000回日次bootstrap区間は全て0跨ぎだった。Profile 0.515にはaccuracy 6/7、score 5/7、all accuracy差+0.11016ptの区間+0.00129〜+0.21871pt、proper scoreも改善した。一方、現行Distribution Shift 0.515にall accuracy -0.01977pt、score -0.000134、Brier +0.00000519、log loss +0.00001044と全主指標で点劣後し、直接bootstrapは全て未確定だった。confirmation 0.515は27,746件・52.62741%、mean 52.88087%で整合したがdown-low/down-normalはWilson edge未確認、0.55もShiftを超えない。新candidateを発行せず再現専用とし、Shift 0.515、既存precision候補、authoritative confidence・fair odds・policyを維持する。同履歴でhalf-life・clip・subset・weight・閾値を再探索しない。Windows workerは単独8 thread・nice/I/O低優先度・CPU onlyで、画像生成等を停止していない。

136. 同じEWMA Asymmetryを定義・半減期・HGB/Platt・25% weight・閾値grid・標準損失1.0のままM30へ固定移植した。Windows canonical 71,260 OOS行で単体方向はbaseline比+39/+31/+70件、accuracy 5/7foldだったが、3期間のaccuracy・Brier・log loss日次bootstrap区間は全て0跨ぎ、confirmation proper scoreが悪化した。通常25% blendは+38/-3/+35件・accuracy 3/7foldで方向用途へ採用しない。方向維持0.52はdevelopmentのaccuracy/scoreを改善したがconfirmationでaccuracy -0.16687pt、score -0.000921へ反転し、baseline比accuracy/score各3/7foldだった。現行Distribution Shift 0.52にはaccuracy/score各1/7、all accuracy -0.16588pt、score -0.000956。coverageだけconfirmation/allで増加確定でも精度低下を伴い、新roleにしない。Shiftとの固定50/50も各1/7、0.55/0.575もShiftを超えず不採用。runtime artifactの設定一致とlatest推論を通したがconfig・registry・authoritative方向/confidence・fair odds・policyを変更しない。Pressure 0.52、Shift 0.52、Pressure + AR 0.55を維持し、同じ履歴でhalf-life・clip・subset・weight・閾値を再探索しない。Windows workerは単独8 thread・nice/I/O低優先度・CPU onlyで、画像生成等を停止していない。

137. EWMA Asymmetryを同じ定義・半減期・HGB/Platt・25% weight・閾値grid・標準損失1.0のままM1へ固定移植した。Windows canonicalでbaseline、Shift、Pathを同一2,183,717行・7foldから再学習した。単体方向はbaseline比+343/+278/+621件でもaccuracy区間が0跨ぎ、confirmation proper scoreが有意に悪化。通常25% blendは+283/+69/+352件・proper score 6/7fold改善でもaccuracy区間0跨ぎで、Path 25%にaccuracy 2/7対5/7だった。方向維持0.51はbaselineへaccuracy/score各7/7、proper score各6/7fold、development/confirmation/all accuracyとdevelopment/all scoreの日次区間を改善し、有効な加工感度を確認した。一方、現行Shift 0.51にはaccuracy 2/7、score 1/7、all accuracy -0.05302pt、score -0.000287、Brier +0.00000309、log loss +0.00000620で4指標の日次区間が全て劣後側だった。Shift/EWMA固定50/50もaccuracy 3/7、score 2/7。0.55はconfirmation 153件・Wilson edge未確認、最終fold101件・48.5149%へ崩れた。M1 EWMAを再現専用とし、Path方向、Shift方向/0.51、Transition guard、Disagreementを維持する。全時間足transferを完了し、EWMA採用はM5 0.515固有、M1/M15/M30は各Shift候補を維持する。同履歴でhalf-life・clip・subset・weight・閾値を再探索せず、config・registry・authoritative方向/confidence・fair odds・policyを変更しない。Windows workerは単独8 thread・nice/I/O低優先度・CPU onlyで、画像生成等を停止していない。

138. M1/M15で固定済みのPath Persistenceを5/10/20/50本efficiency、自己相関、方向転換率、variance ratio、方向持続率、streakの14列、HGB/Platt、25% blend、標準損失1.0のままM5へ移植した。Windows canonical 439,881 OOS行で通常方向blendはbaseline比+21/+43/+64件、accuracy 5/7、proper score 6/7fold改善したがaccuracy日次区間は0跨ぎ。同条件で再構築した現行Pressureにall 32件、accuracy 3/7対4/7で負け、Pathのall Brier/log loss差もbootstrapで有意に悪かった。方向維持0.515はbaseline比accuracy/score各5/7、proper score各6/7foldでも、EWMAにaccuracy/score各2/7、Profileに各3/7で、all proper scoreはProfileへ有意に劣後した。0.55はconfirmation 923件・58.6132%でも、Windows再構築Follow-throughにall accuracy -0.2590pt、score -0.000678で両bootstrap区間が劣後側、score 1/7だった。Path confidenceはconfirmation累積帯で局所整合したがdevelopment/all 0.515は過信し、down-normal 4,256件はWilson edge未確認。artifact境界一致とlatest 52特徴推論を通したが、M5 Pathを再現専用とし、Pressure方向、Profile/EWMA 0.515、Follow-through 0.55、config・registry・authoritative confidence・fair odds・policyを変更しない。同じ履歴でwindow・subset・weight・閾値・subgroup filterを再探索しない。共有画像生成等を停止せず、単独8 thread・nice/I/O低優先度・CPU onlyで実行した。

139. M15/M1で固定済みの16本×5加工系列、2層1,073 parameter causal TCN、8 epoch、Platt、25% blend、標準損失1.0を変更せずM5へ移植した。Windows canonical 439,881 OOS行でTCN単体はbaseline比-741件、通常方向blendは+61件でもaccuracy 4/7、日次区間0跨ぎ、Pressureにも-35件で方向用途を不採用。TCN単独0.515はbaseline比all accuracy +0.08121ptの区間が改善側でもscore区間0跨ぎ、proper score各3/7foldで、Profileにaccuracy 5/7・score 3/7、EWMAに4/7・2/7、0.55はFollow-throughへaccuracy/score区間とも劣後した。Profile confidenceとTCN confidenceの固定50/50平均0.515だけはbaseline比accuracy 7/7、score 6/7、proper score 5/7fold、confirmation/all accuracy・scoreとall proper scoreの日次区間が改善側だったため `m5_profile_tcn_confidence_shadow_v1.json` の非権威sequence-diversity shadowへ固定する。ただし親Profileにはaccuracy 5/7、score 4/7、all accuracy/score区間0跨ぎ、confirmation score -0.000180、coverage -0.79590ptで置換証拠がない。confirmation 0.515は61,901件・実測52.51773%・mean 52.44379%で整合したがdevelopment/allは過信し、down-normal 4,152件はWilson edge未確認。TCN latest 118特徴推論を通したがfull ensemble runtimeは未発行とし、Profile/EWMA 0.515、Pressure方向、Follow-through 0.55、authoritative confidence・fair odds・policyを変更しない。sequence、network、epoch、weight、閾値、subgroup filterを履歴内再探索せず、共有GPU処理を止めず単独8 thread・nice/I/O低優先度・CPU onlyで実行した。

140. M1/M30で有効だったHaar Multiscaleを、4/8/16/32本の前半後半return・absolute-return構成・方向平均差12列、HGB/Platt、25% blend、標準損失1.0のままM5へ固定移植した。Windows canonical 439,881 OOS行で単体はbaseline比-42件、通常方向blendは+111件・accuracy 4/7でもaccuracy区間0跨ぎ。Pressureよりall +15件でもdevelopmentとall proper scoreで劣り、Pressure×Haar平均もPressureにaccuracy/score 2/7なので方向用途を不採用。方向維持0.515はbaseline比accuracy/score各5/7、proper score各6/7fold、confirmation/allのaccuracy・selection score・Brier・log loss日次区間が全て改善側で、all 221,540件・coverage 50.36362%・accuracy 52.69838%・score 0.017674となったため `m5_haar_multiscale_confidence_candidate_v1.json` の独立parallel broad challengerへ固定する。ただしProfileにはaccuracy/score 5/7でもall proper scoreが有意に悪く、EWMAに4/7、Profile×TCNに3/7。Profile×Haar平均もProfile×TCNに1/7、0.55はFollow-throughよりconfirmation/all scoreが低いため既存候補を置換・stackしない。confirmation 0.515は63,218件・実測52.51985%・mean 52.48034%で整合したがdevelopment/allは過信し、down-normal 4,239件はWilson edge未確認。50特徴latest `p(up)=0.5184021044` を確認したがfull blend runtimeは未発行とし、authoritative confidence・fair odds・policyを変更しない。共有GPU処理を止めず単独8 thread・nice/I/O低優先度・CPU onlyで実行した。

## ベースライン評価

2025-01-01〜2026-06-01 の test では、校正後 accuracy は M1 50.89%、M5 51.32%、M15 51.86%、M30 51.65%。balanced accuracy は 50.75%〜51.27%であり、現時点の方向エッジは小さい。

確率校正は全時間足で ECE、Brier score、log loss を改善した。一方、confidence 0.55 以上の coverage は M1 0.006%、M5 0.063%、M15 4.95%、M30 6.73%。M1/M5 は実用的な高信頼度帯をまだ作れていない。

## 次の作業

1. optimized policyとodds calibrationを新規データで固定運用し、accuracy/coverage/Brier/ECEを継続監視する。
2. `coverage_power` は0、0.5、1の事前固定候補だけを比較し、目的に合うquality/coverage比を決める。
3. `next_bar_ev` は新しい完全未使用期間で方向edge、cost headroom、EV biasを監視する。
4. M1/M5 entry delayは実装済みだがadmission fail。現条件を変更せず追加期間で確認する。
5. `m15_cross_tf_meta_candidate_v1` を次の完全未使用期間へ固定適用し、accuracyとBrierの両方がbaseline以上か確認する。
6. 3TF方向一致shadowとM30 high-confidence candidateを固定運用し、次の完全未使用期間でselection scoreを比較する。
7. M30 Pressure 0.52は高信頼laneだけへ適用する。別枠のPressure 12.5% + Ordinal Motif 12.5%方向candidateは固定shadowとして完全未使用期間を測り、baseline以上のaccuracy、Brier、log lossとruntime parityを同時に満たすまで全体モデルへ昇格しない。
8. tree lag、TCN単体、Transformer単体は棄却済み。TCN confidence shadow 0.52だけを固定監視し、sequence architectureの履歴内再調整は停止する。
9. logistic confidence blendは新規期間でBrier、log loss、ECEを並行出力し、3指標すべてがbaseline以下の場合だけconfidence昇格を検討する。
10. training windowはexpandingを標準とする。`--train-window-days` は再現実験専用で、別のwindow長を履歴へ合わせて最適化しない。
11. M15 Extra Trees confidence blendはconfidence 0.53を変更せずforward運用し、accuracy、selection score、Brierがすべてbaseline以上の場合だけ高信頼採用laneへの昇格を検討する。
12. isotonic校正は棄却済み。`--probability-calibration isotonic` は再現専用とし、履歴に合わせたstep smoothingや閾値の再探索は行わない。
13. body/ATR weighted confidence blendは0.54を変更せずforward運用し、Extra Trees 0.53のcoverage重視laneと別々にaccuracy・coverage・selection scoreを比較する。
14. intrabar confidence blendは0.55を変更せず高精度laneとしてforward運用する。通常方向blendはshadow出力だけを行い、fresh期間でfold安定性が確認できるまで方向を置換しない。
15. regime confidence blendはECE診断専用shadowとする。fresh期間でBrier、log loss、ECE、高信頼selection scoreが同時改善しない限りconfidence/oddsへ昇格しない。
16. intrabar structure confidence blendは0.55を固定して既存intrabar 0.55と並行forward運用する。fresh期間のaccuracy、coverage、selection score、Brier/log loss/ECEでhead-to-headし、履歴データから再選択しない。
17. beta calibrationは再現専用とする。Plattを標準校正として維持し、beta係数制約や正則化を履歴データへ合わせて再調整しない。
18. signed-body confidence blendは0.52を変更せず広coverage laneとしてforward運用する。他のconfidence候補と履歴上でstackせず、fresh期間のaccuracy、coverage、selection score、確率品質で比較する。
19. signed-body quantile confidence blendは0.525を中coverage選別laneとして固定運用する。ECEがfresh期間でもbaseline以下になるまでauthoritative oddsには使わない。
20. body-at-ATR upper-half confidence blendは0.525を中coverage laneとして固定し、signed-body quantile 0.525とfresh期間でaccuracy、coverage、selection score、Brier/log loss/ECEを比較する。
21. TCN confidence blendは0.52 shadowのまま監視する。signed-body 0.52をselection scoreで上回るfresh evidenceが出るまで広coverage候補へ昇格しない。
22. causal Transformerは再現専用とする。confirmation Brier/log lossとproper fold安定性が改善しない限りconfidence shadowにも昇格しない。
23. body/ATR soft targetは再現専用とする。同じ教師情報のclear-body 0.525がcoverage/accuracy/selection scoreとfold安定性で上回るため、softening関数を履歴へ合わせて再探索しない。
24. trend-structure 0.525は再現専用とする。clear-body 0.525より目的関数が低いためforward laneへ追加せず、同じ履歴でDI/ADX/MACD期間や閾値を再調整しない。
25. path-persistence 0.525は再現専用とする。confirmationで複数指標を改善したが既存0.525候補の目的関数を超えないため、同じ履歴で窓長・variance aggregation・blend weightを再調整しない。
26. M15 XGBoostは再現用学習器とする。通常教師・clear-body教師とも既存採用候補を超えないため、同じ履歴でtree parameterやblend weightを最適化しない。M1の後続固定移植は下記78を優先する。
27. Haar multiscaleは再現専用とする。developmentで選んだ0.525 laneがconfirmationで悪化したため、同じ履歴で窓長・系列・blend weightを再調整しない。
28. disagreement confidence 0.515は研究shadowとして完全未使用期間だけを測る。今回の履歴でモデル部分集合、weight、penalty、閾値を再探索せず、clear-body/signed-body候補を置換しない。
29. causal online expert weightingは再現専用とする。history rows、学習率、expert subsetを同じ履歴で再探索せず、固定等重みおよびsigned-body候補を置換しない。
30. session-relative confidenceは0.525研究shadowとして完全未使用期間を測る。同じ履歴でwindow、時間group粒度、clip、blend weight、閾値を変えず、clear-body 0.525と並行比較する。
31. four-class body confidenceは0.525教師表現shadowとして固定する。class境界・class数・HGB parameter・blend weightを履歴内再探索せず、clear-bodyを置換しない。
32. candidate registryの4 role championと各roleの非劣位challengerだけを固定forward比較する。fresh期間では同じgateを再計算し、championの閾値・weight・role境界を履歴へ合わせて変更しない。
33. chronological stackingは再現専用とする。同じ履歴でregularization、expert subset、stack weight、閾値を再探索せず、固定候補の単純confidence blendを維持する。
34. intrabar profile 0.515とsigned-body 0.52をbroad roleのobjective/accuracy pairとして固定forward比較する。profile地点、特徴subset、blend weight、閾値を同じ履歴へ合わせて再探索しない。
35. 派生特徴candidateは親モデルと同じ固定閾値で `compare_fixed_candidates.py` を実行し、incremental edgeがない候補をregistryへ追加しない。
36. M5 intrabar profile 0.515をbroad confidence候補として完全未使用期間へ固定する。方向モデルは置換せず、accuracy、coverage、selection score、Brier/log loss/ECEがbaseline以上の場合だけ昇格を検討する。
37. M30 intrabar profileはaggregate calibration shadowに限定する。0.515選別laneとfair oddsには使わず、fresh期間でaccuracy・coverage・selection scoreも同時改善するまで候補へ昇格しない。
38. M5 Profile odds shadowはmodel confidenceをそのまま使い、階層実績再校正を適用しない。runtime blend parityは達成済み。fresh期間の0.515局所整合・Wilson下限・Brier/log loss/ECEが全て通るまで `--authorize-odds` を使わずauthoritative fair oddsへ昇格しない。
39. M15 Intrabar Pressure 25%方向blendを完全未使用期間へ固定する。weight・特徴subsetを履歴内再探索せず、accuracy、Brier、log lossがbaseline以上の場合だけ方向モデル昇格を検討する。confidence用途には使わない。
40. M5 Intrabar Pressure 25%方向blendも完全未使用期間へ固定する。M15と同じ定義・weightを維持し、accuracy、Brier、log lossがbaseline以上の場合だけ方向モデル昇格を検討する。confidenceは既存Profile 0.515を維持する。
41. M30 Intrabar Pressure 0.52をselective confidence候補として完全未使用期間へ固定する。baselineとProfile 0.52の両方にaccuracy、selection score、Brier、log lossで劣らない場合だけ昇格を検討し、`--authorize-odds` は使わない。
42. M15 Intrabar Volatility Shape単体をparallel方向候補として完全未使用期間へ固定する。baselineとPressure方向候補にaccuracy、Brier、log lossで劣らない場合だけ方向昇格を検討する。Shape probabilityは自身の方向odds shadowには使うが、fresh期間でglobal/local校正とedgeを再確認するまでauthoritative fair oddsには使わない。
43. M5/M30 Intrabar Volatility Shapeは棄却済みとする。proper scoreだけの改善を理由に方向・confidence候補へ戻さず、M5 Profile/PressureとM30 Pressureの既存候補を維持する。
44. Intrabar Signed Variationは棄却済みとする。semivariance/jump定義、特徴subset、blend weight、閾値を同じ履歴で再探索せず、M15 Shape方向と既存0.525 confidence候補を維持する。
45. Volatility Shape × Extra Treesは棄却済みとする。Extra Trees parameter、Shape subset、blend weight、confidence閾値を履歴内再探索せず、HGB Shape方向とbaseline-feature Extra Trees 0.53 confidence候補を維持する。
46. M15 Shape oddsは元model confidenceを非認可shadowとして固定する。階層実績再校正と高信頼閾値の再探索を行わず、完全未使用期間でbaseline以上のaccuracy/Brier/log loss/ECE、局所整合、Wilson edgeが同時に成立するまで `--authorize-odds` を使わない。
47. Shape confidenceはpredicted direction × volatility regimeの固定6セルも監視する。confirmationで見つかったup/down非対称を今の履歴へ合わせたfilterにはせず、各セルのsupport、accuracy、mean confidence、Wilson edgeをfresh期間でそのまま再評価する。
48. Shape side Plattは棄却済みとする。side別correctness校正、0.5未満abstention、閾値を同じ履歴で再探索せず、元class confidenceと固定side × volatilityセルをfresh期間で監視する。
49. Intrabar Frequency Shapeは再現専用とする。DCT frequency数、autocorrelation lag、feature subset、blend weight、confidence閾値を同じ履歴で再探索せず、親Shape方向候補とStructure 0.55 precision championを維持する。
50. chronological role routerは再現・安定性監査専用とする。過去foldの一時的winnerへ切り替えず、registryの固定champion/challengerをfresh期間まで並行維持する。
51. Shape correctness isotonic/Plattは棄却済みとする。元Shape model confidenceを非認可odds shadowとして維持し、別の写像や平滑化parameterを同じ履歴で再探索しない。
52. Intrabar Distribution Shapeは方向用途には使わず、方向維持0.53をselective confidence forward candidateとして固定する。Extra Trees 0.53とのfresh比較でaccuracy・selection score・Brierが同時に下回らない場合だけauthoritative confidenceへの昇格を検討し、分位点・blend weight・閾値を履歴内再探索しない。
53. candidate差が小さい場合はM15行単位の点推定だけで昇格せず、固定UTC日paired bootstrapとside×volatilityセルを併記する。Distributionはfresh down-normal局所整合も必須とし、現在の履歴からsubgroup除外ruleを作らない。
54. Intrabar Flow Shape unionは棄却済みとする。Pressure/Shape subset、union weight、confidence閾値を同じ履歴で再探索せず、Volatility Shape方向候補とDistribution/Extra Trees 0.53 selective候補を維持する。
55. Intrabar Breakout Stateは棄却済みとする。breakout/rejection定義、特徴subset、blend weight、0.515以外の閾値を同じ履歴で再探索せず、Profile 0.515 broad championとsigned-body 0.52 challengerを維持する。
56. M15 CatBoostは再現専用学習器とする。Ordered/Plain、depth、iterations、learning rate、regularization、blend weight、confidence閾値を同じ履歴で再探索せず、Signed-body Quantile/Clear-body 0.525を維持する。M1の後続固定移植は下記77を優先する。
57. Temperature scalingは再現専用校正とする。温度範囲、期間平滑化、confidence閾値を同じ履歴で再探索せず、Platt標準校正とIntrabar Structure 0.55 precision championを維持する。
58. Intrabar Ordinal Shapeは再現専用とする。pattern長、tie処理、pattern subset、blend weight、confidence閾値を同じ履歴で再探索せず、Volatility Shape方向候補、Distribution/Extra Trees 0.53、Structure 0.55を維持する。
59. M15 LightGBMは再現専用学習器とする。leaves、trees、learning rate、sampling、regularization、blend weight、confidence閾値を同じ履歴で再探索せず、Signed-body Quantile/Clear-body 0.525を維持する。M1の後続固定移植は下記76を優先する。
60. Directional Clarity教師filterは再現専用とする。clarity cutoff、保持率、body/ATRとの合成、blend weight、confidence閾値を同じ履歴で再探索せず、Distribution Shape/Extra Trees 0.53を維持する。
61. Signed Clarity連続教師は再現専用とする。target非線形化、loss、blend weight、confidence閾値を同じ履歴で再探索せず、Volatility Shape/Pressure方向候補とSigned-body Quantile/Clear-body 0.525を維持する。
62. Directional Clarity sample weightingは再現専用とする。weight offset、非線形化、上限、blend weight、confidence閾値を同じ履歴で再探索せず、Signed-body Quantile/Clear-body 0.525を維持する。
63. Intrabar Full Path方向維持0.53をselective confidenceの固定forward championとする。15地点、正規化、25% weight、閾値を履歴内再探索せず、完全未使用期間でDistribution Shape/Extra Trees以上のaccuracy・selection score・Brierとdown-normal局所整合を同時に確認するまでauthoritative confidence・odds・売買policyへ昇格しない。
64. Intrabar Full Path × Volatility Shape unionは再現専用とする。特徴subset、別weight、0.525以外の閾値、tree capacityを同じ履歴で再探索せず、Full Path 0.53、Volatility Shape方向、Signed-body Quantile/Clear-body 0.525を維持する。
65. Intrabar Full Path × cross-timeframe metaは再現専用とする。M1/M5/M30 subset、regularization、weight、閾値を同じ履歴で再探索せず、既存cross-TF候補とFull Path 0.53 selective championを独立に維持する。
66. Intrabar Path Signatureは再現専用とする。signature level、時間/価格path定義、特徴subset、blend weight、0.53以外の閾値を同じ履歴で再探索せず、Full Path 0.53 selective championを維持する。
67. Volatility Stateは再現専用とする。rolling window、jump/variance定義、特徴subset、blend weight、0.525以外の閾値を同じ履歴で再探索せず、既存方向候補と0.525 confidence候補を維持する。
68. Full Path temporal uncertaintyは再現専用とする。training window、window数、uncertainty penalty、モデルweight、0.515以外の閾値を同じ履歴で再探索せず、expanding Full Path 0.53と既存異種disagreement shadowを維持する。
69. M1 × M5/M15 as-of metaは再現専用とする。context subset、最大age、regularization、blend weight、0.51以外の閾値を同じ履歴で再探索せず、次のM1候補は確定済みmicrostructure/regime特徴を独立に加工して評価する。
70. M1 Path Persistence 25%を方向専用parallel forward候補とする。14特徴、degenerate窓=0、HGB/Platt、25% weightを固定し、完全未使用期間でbaseline以上のaccuracy、Brier、log lossを同時に確認するまでauthoritative方向・confidence・odds・paper/live policyを変更しない。
71. M1 Trend Structure 25%を方向専用secondary challengerとする。11特徴、degenerate窓=0、HGB/Platt、25% weightを固定し、Pathとunion・再weightせず完全未使用期間で独立比較する。Path point championとauthoritative方向・confidence・odds・policyは変更しない。
72. M1 causal TCN方向維持0.515をselective confidenceのparallel forward候補とする。16本×5系列、2層1,073 parameter、8 epoch、25% weight、閾値を再探索せず、完全未使用期間でaccuracy・selection score・Brier・log loss、固定side×volatility 6セル、runtime parity、局所校正が通るまでauthoritative confidence・fair odds・policyへ昇格しない。方向用途には使わずPath方向候補とstackしない。
73. M1 Session Relative 25%をprobability-quality specialist方向候補とする。曜日×UTC時、prior 32/min 12、5特徴、degenerate定義、25% weightを固定し、完全未使用期間でbaseline以上のaccuracy/Brier/log lossを同時に要求する。Path accuracy champion、Volatility balanced secondary、Trend tertiary、TCN confidenceとはstackせず、Session confidence 0.51は使わない。
74. M1 Volatility State 25%をbalanced secondary方向候補とする。11特徴、degenerate窓=0、HGB/Platt、25% weightを固定し、完全未使用期間でbaseline以上のaccuracy/Brier/log lossを同時に要求する。Path/Session/Trendとunion・再weightせず、Volatility confidence 0.515は使わない。
75. M1 Haar Multiscale 25%をtertiary multiscale方向challengerとする。4/8/16/32本×3系列、degenerate窓=0、HGB/Platt、25% weightを固定し、完全未使用期間でbaseline以上のaccuracy/Brier/log lossを同時に要求する。既存方向候補とunion・再weightせず、Haar confidence 0.515は使わない。
76. M1 standalone LightGBMを異種学習器accuracy co-challengerとする。31 leaves、300 trees、learning rate 0.03、min child 100、row/column sample 0.8、L2 5、expanding、Plattを固定し、完全未使用期間でbaseline以上のaccuracy/Brier/log lossを同時に要求する。Pathを4件差のpoint championとして維持し、stack・router・parameter再探索を行わず、LightGBM confidence 0.515は使わない。
77. M1 CatBoostは再現専用学習器とする。通常25%方向blendのbaseline改善はsupporting sensitivityとして保存するが、Path/LightGBM、Volatility/Session、TCN confidenceの各役割を置換しない。Ordered/Plain、depth、iterations、learning rate、regularization、blend weight、0.515以外の閾値を同じ履歴で再探索せず、config・latest・oddsを発行しない。
78. M1 XGBoostは再現専用学習器とする。通常25%方向blendの7/7fold baseline改善はsupporting sensitivityとして保存するが、Path/LightGBM、Volatility/Session、TCN confidenceの各役割を置換しない。tree数、depth、learning rate、min child、sampling、regularization、blend weight、0.515以外の閾値を同じ履歴で再探索せず、config・latest・oddsを発行しない。
79. M1 Extra Trees 25% normal blendは異種学習器比較候補として維持するが、stability方向役割は89のDistribution Shiftへ引き継ぐ。200 trees、depth 12、min leaf 50、max features 0.75、25% weightを再探索せず、Extra Trees confidence 0.515は使わない。
80. M1 Candle Pressure Stateは再現専用とする。3/8/21本、body/wick/close pressure、range加重pressure、3−8加速度、18列、25% weightを同じ履歴へ合わせて再探索しない。baseline補完性は保存するがPath/LightGBM、Extra Trees、Volatility/Session、TCNの各役割を置換せず、config・latest・oddsを発行しない。
81. M1 Bar Breakout / Rejectionは再現専用とする。prior-only 1/5/20本境界、breakout/rejection、inside/outside、range expansion、ATR距離、18列、25% weight、0.51を同じ履歴へ合わせて再探索しない。aggregate proper-score改善だけで候補を増やさず、既存方向・probability-quality・TCN confidenceを維持する。
82. M1 Volatility Regime Candidate Routerは再現・安定性監査専用とする。low/normal/high境界、Path/Volatility/Session/Extra Trees/LightGBMの候補pool、accuracy選択、cross cell、0.515を同じ履歴で再探索しない。baseline改善を新規独立edgeと解釈せず、Path/LightGBM、Volatility/Session、TCN confidenceを固定並行維持する。
83. M1 Five-model Disagreement方向維持0.515をbalanced coverage/probability-quality confidence challengerとして固定する。baseline/Path/Extra Trees/LightGBM/TCN、等重み、penalty 0、0.515を同じ履歴で再探索しない。86のTransition guard 50/50 accuracy specialistと完全未使用期間でaccuracy・coverage・selection score・Brier/log loss・固定6セルを比較し、runtime parityと局所整合が通るまでauthoritative confidence・fair odds・policyへ昇格しない。
84. M1 Disagreement chronological correctness isotonic/Plattは再現専用として棄却する。isotonicのECEだけを理由に採用せず、smoothing、Platt regularization、rolling期間、別写像、0.515以外の閾値を同じ履歴で再探索しない。元equal-mean confidenceを維持し、fair oddsはfresh global/local整合まで非認可とする。
85. M1 causal GRUとGRU追加6-model Disagreementは再現専用とする。16本×5系列、hidden 16、1,121 parameter、8 epoch、25% blend、6-model等重み、0.515を同じ履歴で再探索しない。方向は既存Path/LightGBM等、confidenceは86のTransition guard 50/50 accuracy specialistと5-model Disagreement balanced challengerを維持し、GRU/TCNは比較再現用としてconfig・latest・oddsを新規発行しない。
86. M1 Direction Transition Bayes単体・通常方向blend・raw confidenceは再現専用とする。state/parent prior、状態境界、25% weightを再探索しない。development固定のup×low abstentionとDisagreement 50/50、0.515だけをaccuracy-specialist confidence候補として完全未使用期間へ固定する。TCNの同役割を履歴上で更新するが、Disagreement balanced候補、authoritative方向/confidence、fair odds、paper/live policyは変更しない。
87. M1 chronological expert stackingは再現専用として棄却する。C=0.10、baseline/Path/Extra Trees/LightGBM/TCN、25% weight、方向維持、0.515を同じ履歴で再探索しない。equal-mean DisagreementとTransition guard 50/50 championを維持し、学習weightを理由に候補・odds・policyを増やさない。
88. M1 × M5/M15 as-of meta再検証は再現専用として棄却する。最大age 15分、C=0.10、25% weight、0.515を固定し、M30追加、context subset、age、regularization、weight、閾値を同じ履歴で再探索しない。Transition guard 50/50 accuracy championと5-model Disagreement balanced challengerを維持する。
89. M1 Distribution Shift通常25% blendをstability/proper-score方向challenger、方向維持0.51をultra-broad coverage Pareto confidence challengerへ固定する。8/64/128窓、quantile、16列、HGB、25% weight、0.51を同じ履歴で再探索しない。Path accuracy、Transition guard 0.515 accuracy-confidence、Disagreement balanced-confidenceを置換せず、fresh方向3指標、0.51 score、固定6セル、runtime parity、局所校正が通るまでauthoritative方向/confidence・fair odds・policyへ昇格しない。
90. M1 causal Transformerは再現専用とする。16本×5系列、dimension 16、4-head、1層、feed-forward 32、8 epoch、25% weight、0.51を同じ履歴で再探索しない。方向はPath/Distribution Shift、confidenceはTransition guard/Disagreement/Distribution Shiftを維持し、Transformerのaggregate proper-score改善や疎な高閾値を理由にconfig・odds・policyを増やさない。
91. M1 Distribution Shift × LightGBMは再現専用とする。54特徴、31 leaves、300 trees、learning rate 0.03、min child 100、row/column sample 0.8、L2 5、25% weight、0.51を同じ履歴で再探索しない。親HGB Distribution Shiftを維持し、僅かなcoverage増加やaggregate proper-scoreだけを理由にconfig・registry・odds・policyを増やさない。
92. M1 Rolling Distribution Shapeは再現専用とする。64本、10/25/50/75/90%分位、9列、HGB、25% weight、0.51を同じ履歴で再探索しない。確認期間でobjectiveが反転したため、単体のconfirmation点精度や高閾値の疎なaccuracyを理由にconfig・registry・odds・policyを増やさず、既存Distribution Shiftを維持する。
93. M1 Rolling Full Pathは再現専用とする。15本、11採取点、joint range正規化、HGB、25% weight、0.515を同じ履歴で再探索しない。confirmation方向改善だけを理由に候補を増やさず、既存Path/Distribution Shift方向、Transition guard/Disagreement/Distribution Shift confidenceを維持し、config・registry・odds・policyを発行しない。
94. M1 champion prequential hierarchical Beta oddsは再現専用とする。90日、8,192/4,096/2,048 prior、固定band、方向×volatility階層、posterior下限、0.515を同じ履歴で再探索しない。ECE局所改善だけを理由に採用せず、元Transition guard × Disagreement confidenceを維持し、fresh global/local整合までfair oddsを認可しない。
95. M1 Change-Point Stateは再現専用とする。64本reference、drift 0.25、alarm 5、score cap 20、age cap 64、return/rangeの10列、HGB、25% weight、0.515を同じ履歴で再探索しない。baseline confidence改善は保存するが、Path/Distribution Shift方向とTransition guard/Disagreement/Distribution Shift confidenceの既存役割を置換せず、疎な高信頼度tailを理由にconfig・registry・odds・policyを増やさない。
96. M1 Shock / Recovery Stateは再現専用とする。64本reference、2σ、16本追跡、response cap 3、return/rangeの12列、HGB、25% weight、0.51を同じ履歴で再探索しない。baseline proper-score改善は保存するが、既存Distribution Shiftの方向・ultra-broad confidence役割を置換せず、高信頼度tailや確認期間の単体点精度を理由にconfig・registry・odds・policyを増やさない。
97. M1 Recency Half-Life 730 Daysは再現専用とする。expanding履歴の等間隔sample、730日半減、平均1、HGB/Platt、25% weight、0.515を同じ履歴で再探索しない。baseline補完性とproper-score改善は保存するが、Distribution Shift方向とDisagreement confidenceの既存役割を置換せず、config・registry・odds・policyを増やさない。
98. M1 Directional-Clarity sample weightingは再現専用とする。M15固定の0.5〜1.5教師重み、平均1、HGB/Platt、25% weight、0.51を同じ履歴で再探索しない。baselineへの7/7fold改善は有効なlearning-flow sensitivityとして保存するが、Path/Distribution Shift/Extra Trees/Session/Volatilityの既存方向役割とTransition guard/Disagreement/Distribution Shift confidenceを置換せず、config・registry・odds・policyを増やさない。
99. M1 Body/ATR sample weightingは再現専用とする。M15固定の0.5〜2.0教師重み、平均1、HGB/Platt、25% weight、0.515を同じ履歴で再探索しない。baseline方向7/7foldとconfirmation confidence改善は保存するが、Directional-Clarity/Distribution Shift方向とDisagreement confidenceを置換せず、M1 config・registry・odds・policyを増やさない。M15 0.54候補は時間足独立で維持する。
100. M1 Body/ATR upper-half teacher filterは再現専用とする。各fold train内中央値、上位半分保持、HGB/Platt、25% weight、0.51を同じ履歴で再探索しない。baselineへのproper-score改善は教師品質加工の感度として保存するが、Distribution Shiftの方向・ultra-broad confidence役割を置換せず、疎く期間移行しない高信頼度tailを理由にconfig・registry・odds・policyを増やさない。M15 0.525候補は時間足独立で維持する。
101. M1 Path × Distribution Shift chronological pairwise correctness gateは再現専用とする。固定15列、Logistic C=0.10、prior-OOS不一致学習、hard threshold 0.5、test2020 Path fallbackを同じ履歴で再探索しない。全期間point accuracyの僅かな上昇を採用根拠にせず、Path point championとDistribution Shift stability/proper-score候補を独立維持し、config・registry・odds・policyを増やさない。
102. M1 Rolling Spectral Stateは再現専用とする。64本、low k1〜2、mid k3〜6、residual high、k=1/2/4/8位相、HGB/Platt、通常/方向維持25%、Shiftとの固定50/50平均を同じ履歴で再探索しない。baseline proper-score改善は加工特徴の感度として保存するが、Path/Distribution Shiftの各役割を置換せず、高信頼度tailをfair oddsへ使わない。
103. M1 Rolling Transition Memoryは再現専用とする。32/128本、4 bit・16状態、prior range median 20、global shrinkage strength 8、HGB/Platt、通常/方向維持25%、Path/Shiftとの固定50/50平均を同じ履歴で再探索しない。baseline改善は局所学習感度として保存するが、Path/Distribution Shift方向とDisagreement/Transition guard confidenceを置換せず、疎く過信するtailをfair oddsへ使わない。
104. M5 Rolling Transition Memory固定移植も再現専用とする。M1と同じ32/128本、16状態、range基準20、prior 8、HGB/Platt、通常/方向維持25%、Profile/Pressureとの固定50/50平均を変更・再探索しない。baseline proper-score改善とconfirmation点精度は保存するが、Pressure方向とProfile broad confidenceを置換せず、最新foldで反転した高信頼度tailをfair oddsへ使わない。
105. M15/M30 Rolling Transition Memory固定移植も再現専用とする。M1と同じ32/128本、16状態、range基準20、prior 8、HGB/Platt、通常/方向維持25%、既存候補との固定50/50平均を変更・再探索しない。M15単体の僅かな点accuracyとM30 0.575の疎なtailを採用根拠にせず、M15 Pressure/Volatility Shape方向、Signed-body Quantile等のconfidence、M30 Pressure 0.52を維持する。config・registry・authoritative予測・fair odds・policyを増やさない。
106. M15/M30 Prequential Selective Correctnessは再現専用とする。基準/baseline/Shape/Profile確率とregimeの固定24列、Logistic C=0.10、expanding prior-OOS fit、固定gridを同じ履歴で再探索しない。M15 0.53、M30 0.50、両0.55 tailはいずれも既存候補の時系列安定性とproper scoreを超えないため、Signed-body Quantile/Structure/Pressureを維持し、config・registry・authoritative confidence・fair odds・policyを増やさない。
107. M15/M30 Fixed Component Consensus Filterは再現専用とする。基準/Shape/Profileの固定3本、2/3・3/3、edge許容値1e-15、元閾値0.525/0.52を同じ履歴で再探索しない。M15 development改善はveto集合がconfirmationで正解側へ反転し、M30は目的関数を下げたため、既存confidence候補を維持し、config・registry・authoritative confidence・fair odds・policyを増やさない。
108. Rolling Ordinal Motifは3 return・6 pattern、辞書順tie、32/128本、18特徴、HGB/Platt、通常/方向維持25%を固定し、motif長・window・weight・閾値を履歴内再探索しない。M15とM30 confidenceは再現専用。M30だけbaseline 75% + Pressure 12.5% + Motif 12.5%をparallel方向候補へ固定し、fresh accuracy/Brier/log lossとruntime parityまでauthoritative方向/confidence・fair odds・policyを変更しない。
109. Rolling Autoregressive StateはAR(3)、32/128本、scale-adaptive ridge 0.05、15特徴、HGB/Platt、通常/方向維持25%を固定し、次数・window・ridge・weight・閾値を履歴内再探索しない。M15とM30方向、M15 confidence、M30 0.52/AR単独0.55は再現専用。PressureとAR confidenceの固定50/50 selector 0.55だけをparallel forward shadowとし、fresh accuracy・coverage・selection scoreとruntime parityまでauthoritative confidence・fair odds・policyを変更しない。
110. M30 LightGBM固定移植はbaseline 38特徴、31 leaves、300 trees、learning rate 0.03、min child 100、row/column 0.8、L2 5、Platt、25% blendを固定し、parameter・weight・閾値を履歴内再探索しない。LightGBM単体/25%単独とconfidenceは再現専用。Pressure + Ordinal Motif候補とLightGBM 25%の固定50/50方向平均だけをparallel co-challengerとし、fresh accuracy/Brier/log loss、parent head-to-head、full runtime parityまでauthoritative方向・parent候補・confidence・fair odds・policyを変更しない。
111. M30 Extra Trees固定移植はbaseline 38特徴、200 trees、depth 12、min leaf 50、max features 0.75、Platt、expanding、uniform sampleを固定し、parameter・weight・閾値を履歴内再探索しない。通常25% blend、0.515/0.55 confidence、現行co-challengerとの固定平均は再現専用。Extra Trees単体だけをparallel standalone確率品質方向challengerとし、fresh accuracy/Brier/log lossと現行co-challenger head-to-headが揃うまでauthoritative方向・現行候補・confidence・fair odds・policyを変更しない。
112. M30 Haar Multiscale固定移植は4/8/16/32本、3系列・12列、HGB/Platt、expanding、uniform sample、標準損失1.0を固定し、window・feature・parameter・weight・閾値を履歴内再探索しない。Haar単体/通常25%とHaar/equal confidenceは再現・構成要素専用。現行Pressure + Ordinal + LightGBM co-challengerとHaar単体の固定50/50方向平均だけをparallel co-challengerとし、fresh accuracy/Brier/log loss、parent head-to-head、full runtime parityまでauthoritative方向・parent候補・confidence・fair odds・policyを変更しない。
113. M30 Path Persistence固定移植は5/10/20/50本、14列、HGB/Platt、expanding、uniform sample、標準損失1.0を固定し、window・feature・parameter・weight・閾値を履歴内再探索しない。単体/通常25%方向、方向維持0.52、Pressureとの固定50/50 confidence平均を再現専用とする。baseline proper-score改善は確率平滑化感度として保存するが、Haar入り方向、Pressure 0.52、Pressure + AR 0.55の既存役割を置換せず、config・registry・authoritative予測・fair odds・policyを増やさない。
114. M30 Session Relative固定移植は曜日×UTC時刻、prior 32/min 12、5列、HGB/Platt、expanding、uniform sample、標準損失1.0を固定し、window・group粒度・最低本数・clip・weight・閾値を履歴内再探索しない。単体/通常25%方向、方向維持0.52、Pressureとの固定50/50 confidence平均を再現専用とする。baseline proper-score改善はperiodic regime感度として保存するが、Haar入り方向、Pressure 0.52、Pressure + AR 0.55の既存役割を置換せず、config・registry・authoritative予測・fair odds・policyを増やさない。
115. M30 Volatility State固定移植はvol-of-vol・加速度・range状態・圧縮・jump・OHLC分散balanceの11列、HGB/Platt、expanding、uniform sample、標準損失1.0を固定し、window・jump定義・variance estimator・feature・weight・閾値を履歴内再探索しない。単体/通常25%方向、方向維持0.515/0.55、Pressureとの固定50/50 confidence平均を再現専用とする。aggregate proper-score改善は変動状態感度として保存するが、Haar入り方向、Pressure 0.52、Pressure + AR 0.55の既存役割を置換せず、config・registry・authoritative予測・fair odds・policyを増やさない。
116. M30 XGBoost固定移植はbaseline加工38特徴、300 trees、depth 4、learning rate 0.03、min child weight 20、row/column 0.8、L2 5、hist、Platt、expanding、uniform sample、標準損失1.0を固定し、tree parameter・feature・weight・閾値を履歴内再探索しない。単体/通常25%方向、方向維持0.515/0.55、Pressureとの固定50/50 confidence平均を再現専用とする。aggregate proper-score改善とcoverage感度は保存するが、確認期間の目的反転を優先し、Haar入り方向、Pressure 0.52、Pressure + AR 0.55の既存役割を置換せず、config・registry・authoritative予測・fair odds・policyを増やさない。
117. M30 Directional-Clarity sample weighting固定移植は0.5〜1.5・平均1のtrain weight、baseline 38特徴、HGB/Platt、全教師、expanding、標準損失1.0を固定し、weight式・feature・blend weight・閾値を履歴内再探索しない。単体/通常25%方向、方向維持0.51/0.55、Pressureとの固定confidence平均を再現専用とする。Haar入り候補との固定50/50方向平均はbaseline感度として保存するが、親への年別3/7・不確定な増分を優先し、新candidateを発行しない。現行Haar方向、Pressure 0.52、Pressure + AR 0.55を維持し、config・registry・authoritative予測・fair odds・policyを増やさない。
118. M30 Body/ATR sample weighting固定移植は0.5〜2.0・平均1のtrain weight、baseline 38特徴、HGB/Platt、全教師、expanding、標準損失1.0を固定し、weight式・feature・blend weight・閾値を履歴内再探索しない。単体/通常25%方向、方向維持0.515/0.55、Pressureとの固定confidence平均を再現専用とする。M30では方向悪化、confirmation confidence反転、Directional-Clarityへのproper score劣後を優先し、新candidateを発行しない。M15 0.54候補は時間足独立で維持し、現行Haar方向、Pressure 0.52、Pressure + AR 0.55、config・registry・authoritative予測・fair odds・policyを変更しない。
119. M30 Directional Follow-through sample weightingは次足body/range×方向側close到達度、0.5〜1.5・平均1のtrain weight、baseline 38特徴、HGB/Platt、全教師、expanding、標準損失1.0を固定し、式・parameter・blend weight・0.55・subgroupを履歴内再探索しない。単体/通常25%方向は再現専用、Haar親との固定50/50平均も方向候補へ追加しない。固定平均0.55だけをparallel confidence shadowへ採用し、fresh Pressure + AR head-to-head、confirmation score、固定セル整合、full runtime parityまでauthoritative confidence・fair odds・policyを変更しない。
120. M5 Directional Follow-through固定移植はM30と同じ教師品質式、0.5〜1.5・平均1、baseline 38特徴、HGB/Platt、全教師、expanding、通常/方向維持25%、標準損失1.0を固定し、式・parameter・blend weight・0.55を履歴内再探索しない。単体/通常方向、0.515 broad、Pressure/Profileとの固定50/50平均は再現専用。方向維持0.55だけをparallel high-confidence shadowへ採用し、fresh Profile 0.55 head-to-head、global/local calibration、full runtime parityまでPressure方向、Profile broad confidence、authoritative confidence・fair odds・policyを変更しない。
121. M15 Directional Follow-through固定移植は同じ教師品質式、0.5〜1.5・平均1、baseline 38特徴、HGB/Platt、全教師、expanding、通常/方向維持25%、標準損失1.0を固定し、式・parameter・blend weight・閾値を履歴内再探索しない。単体/通常方向、方向維持confidence、Pressure/Full Pathとの固定50/50平均を再現専用とし、Directional-Clarity方向とProfile/Quantile/Full Path/Structure confidenceを維持する。M15 config・registry・authoritative予測・fair odds・policyを変更しない。
122. M1 Directional Follow-through固定移植は同じ教師品質式、0.5〜1.5・平均1、baseline 38特徴、HGB/Platt、全教師、expanding、通常/方向維持25%、標準損失1.0を固定し、式・parameter・blend weight・閾値・subgroupを履歴内再探索しない。baseline改善は教師品質加工の感度として保存するが、方向はPath/Distribution Shift/Directional-Clarity、confidenceはTransition guard/Disagreement/Distribution Shiftを維持する。単体/通常/confidence/固定平均を再現専用とし、config・registry・authoritative予測・fair odds・policyを変更しない。
123. M1 Transition guard 0.515とDistribution Shift 0.51の固定採用集合union/intersectionは再現専用とする。親の確率・confidenceを混ぜずboolean集合だけを比較したが、guardの99.80%以上がShiftに含まれ、accuracy・selection scoreのbootstrap増分と新しいfair oddsを得られなかった。閾値、source順、集合固有校正を履歴内再探索せず、Transition guard accuracy specialist、Distribution Shift ultra-broad、Disagreement balanced challengerを独立維持する。
124. M1正式confidence 4候補の全6 pair補完性監査は再現専用とする。developmentで両exclusive Wilson edgeとunion目的関数改善を要求するとDisagreement 0.515 + Distribution Shift 0.51だけが選ばれたが、confirmationのDisagreement-onlyは386行・48.1865%へ反転しunion scoreも親を下回った。同じ候補のpair、集合演算、閾値、source順、集合固有校正を履歴内再探索せず、異なる加工情報から独立した次候補を作る。
125. M1 State Correctnessはbaseline方向の正否を過去OOSだけからDistribution Shift市場状態54列+reference状態3列のHGB/Plattで学ぶ。development主目的で選んだ0.505はDistribution Shift 0.51へconfirmation/allで明確に劣るため棄却する。事前固定0.55の6セル監査からdevelopment Wilson edgeと局所整合を満たしたup×normal/highだけを固定precision forward shadowへ採用する。confirmation 2,063件・58.1677%、all 3,615件・57.3167%で、既存Transition guard/Disagreement 0.55へのall accuracy・score bootstrap改善を確認した。coverage 0.1966%、セル選択の多重比較、全行proper-score非優位が残るためauthoritative方向/confidence・fair odds・paper/live policyは変更せず、完全未使用1,000件以上とruntime固定条件で昇格を再評価する。損失倍率は標準1.0のみとする。
126. 新規学習のcanonical環境をWindows/WSL2 x86 Linuxへ移す。共有マシン上の画像生成・ローカルAI処理を優先し、単独worker、標準8 thread、nice/I/O低優先度、memory/load gate、GPU idle gateを固定する。次回自然再起動後のWSL上限は40GB RAM・24 logical processors・16GB swapとし、移管時の再起動は行わない。履歴と選択済みnext-bar artifactだけを移し、runtimeは空、口座・login・credentialは移さない。既存Mac artifactはserialized inference専用、新規再学習はWindows canonicalとし、platformを跨ぐ再学習artifactを同じ比較へ混在させない。移管途中のM5/M15/M30 State CorrectnessはWindowsで再実行してから採否を決める。
127. M5/M15/M30 State CorrectnessをWindows canonical環境で固定再実行した。development選択はM5 0.515、M15 0.51、M30 0.505だが、M5/M15は既存Profile/baselineへconfirmation/all selection scoreとproper scoreで劣り、M30もdevelopmentの僅かなscore増をconfirmationで再現せず採用しない。固定0.55とM1由来up×normal/high guardも既存precision championへscoreで明確に劣る。M15 guardはall 3,059件・56.1621%、Structureより点accuracy+1.0640ptだがaccuracy区間は0跨ぎ、all score差95%区間-0.007300〜-0.001659、confirmation 538件である。3時間足とも再現専用とし、config・registry・authoritative confidence・fair odds・policyを変更しない。損失倍率は標準1.0のみとする。
128. M5 baseline確率と同一decision timestampのM1 baseline確率をC=0.10のchronological logisticへ入れ、方向維持confidence blendを固定検証した。developmentだけで選んだweight 0.50・閾値0.51はbaseline比accuracy 6/6 fold、score 5/6、all accuracy +0.0846ptでbootstrap区間も正だったが、proper scoreはBrier/log loss各2/6 foldしか改善しない。既存Profile 0.515にはaccuracy 0/6 fold、all −0.3323ptで明確に負け、0.55もFollow-throughへscore 0/6だった。再現専用とし、config・registry・authoritative confidence・fair odds・policyを変更しない。raw volumeは全6,025,170行が0で特徴不採用。損失倍率は標準1.0のみとする。
129. Windows/WSLは画像生成・ローカルAIとの共有機なので、CPU低優先度を標準としGPUをdefaultで非表示にする。単独8 thread、nice/I/O低優先度、available memory 16GiB、load 8のgateへ強化する。GPU研究は明示enable、idle gate、画像生成を止めたexclusive windowの3条件と開始時2,048MB/10%以下を全て要求し、競合時はexit 75で延期する。canonical/platform規則、次回自然再起動後40GB/24 processor/16GB swap、口座・runtime・credential非移管を維持する。
130. M1で有効だったDistribution Shift 16特徴を8/64/128本、HGB/Platt、25% blend、標準損失1.0のままM5へ固定移植した。Windowsでbaseline/Shift/Profileを同一7fold再学習しplatformを混ぜていない。Shift単体はbaseline比all -43件、通常方向blendは-2件・accuracy 3/7で不採用。development選択0.515の方向維持blendはbaseline比accuracy/score各5/7、proper scoreを改善したが、Profileにconfirmation score 0.012316対0.013020、all 0.017391対0.017565、accuracy/score各2/7対5/7で負けた。0.55もconfirmation 831件・56.4380%・score 0.002132でProfile未達。再現専用とし、Profile broad confidence、Follow-through high-confidence shadow、config・registry・authoritative confidence・fair odds・policyを維持する。
131. 同じDistribution ShiftをM15へ固定移植し、Windows canonicalでbaseline/Shift/Profileを同一145,140行・7foldから再学習した。単体方向はbaseline比all +34件でもconfirmation -54件、通常25%方向blendも+20件・p=0.75847で方向用途には採用しない。方向維持0.515はbaseline比accuracy 6/7、score 5/7、proper score 6/7fold、all 52.99798% / coverage 54.44399% / score 0.019552。Profile 0.515にはaccuracy/score各7/7fold、all accuracy +0.12993ptのbootstrap区間+0.01935〜+0.24133pt、Brier/log lossも改善側だったため `m15_distribution_shift_confidence_candidate_v1.json` のWindows canonical broad forward候補に採用する。0.55はProfileへscore 4/7だけなのでprecision用途には使わない。旧Mac artifactを含むregistryは混在更新せず、M15全候補の同一platform再構築、latest parity、fresh局所校正までauthoritative confidence・fair odds・paper/live policyを変更しない。共有画像生成・ローカルAIを停止せず、単独8 thread・nice/I/O低優先度・CPU only・標準損失1.0で実行した。
132. Distribution Shiftを同条件でM30へ固定移植し、Windows canonicalでbaseline/Shift/Pressure/Profileを同一71,260行・7foldから再学習した。Shift単体はbaseline比all -17件、通常方向blendは+4件・p=0.95278、accuracy 2/7で方向用途に使わない。方向維持0.52はbaseline比accuracy 5/7、score 4/7、proper score 6/7fold、all 53.42012% / coverage 37.72804% / score 0.017342。baseline比all accuracy差+0.26254ptのbootstrap区間+0.05052〜+0.47706pt、score・Brier・log lossも改善側だった。Pressure/Profileにはaccuracy/score差未確定だがall coverageを+0.47853/+0.28908pt、confirmationを+1.23640/+0.55674pt広げる区間が改善側のため `m30_distribution_shift_confidence_candidate_v1.json` のparallel coverage challengerに採用する。0.55はPressureにscore 3/7、Shift/Pressure固定50/50はdevelopment/all scoreを下げたため不採用。Pressure 0.52、Pressure+AR 0.55、authoritative confidence・fair odds・policyを置換せず、latest parityとfresh head-to-head/local calibrationを要求する。単独8 thread・nice/I/O低優先度・CPU only・標準損失1.0を維持した。
133. M5 Path Persistence固定移植は5/10/20/50本、14列、HGB/Platt、expanding、uniform sample、標準損失1.0を固定し、window・feature・weight・閾値・subgroup filterを履歴内再探索しない。単体/通常25%方向と方向維持0.515/0.55を再現専用とする。baseline proper-score改善とconfirmation局所整合は加工感度として保存するが、Pressure方向、Profile/EWMA 0.515、Follow-through 0.55を置換せず、config・registry・authoritative予測・fair odds・policyを増やさない。
134. M5 causal TCN固定移植は16本×5加工系列、2層1,073 parameter、8 epoch、Platt、expanding、uniform sample、標準損失1.0を固定し、sequence、channel、network、epoch、weight、閾値、subgroup filterを履歴内再探索しない。TCN単体/通常25%方向、TCN単独0.515/0.55、Pressure×TCN方向平均を再現専用とする。Profile×TCN固定50/50 confidence 0.515だけを非権威parallel shadowとし、完全未使用期間でProfile以上のaccuracy・selection score・Brier・log loss、down-normal Wilson edge、global/local calibration、full runtime parityが揃うまでProfile/EWMA 0.515、Pressure方向、Follow-through 0.55、authoritative予測・fair odds・policyを変更しない。
135. M5 Haar Multiscale固定移植は4/8/16/32本、return・absolute-return構成・方向平均の前半後半差12列、HGB/Platt、expanding、uniform sample、標準損失1.0を固定し、window、feature、parameter、weight、閾値、subgroup filterを履歴内再探索しない。単体/通常25%方向、Pressure×Haar方向平均、0.55 high-confidence、Profile×Haar confidence平均を再現専用とする。方向維持0.515だけを独立parallel broad-confidence challengerとし、完全未使用期間でProfile/Profile×TCN以上のaccuracy・selection score、Profile以下のBrier・log loss、down-normal Wilson edge、global/local calibration、full runtime parityが揃うまでProfile/EWMA、Profile×TCN shadow、Pressure方向、Follow-through 0.55、authoritative予測・fair odds・policyを変更しない。
