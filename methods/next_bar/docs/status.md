# Next-bar research status

更新日時: 2026-08-10 19:06 JST

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
- Full Path 0.53をselective confidence forward candidateとして採用し、15候補registryのselective履歴championへ更新した。Distribution/Extra Treesは比較用に残すが、authoritative confidence、odds、adoption/paper/live policyは完全未使用期間まで変更しない。

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
7. M30 candidateは高信頼lane以外へ適用しない。全体accuracyとECEの悪化が解消するまで全体モデルには昇格しない。
8. tree lag、TCN単体、Transformer単体は棄却済み。TCN confidence shadow 0.52だけを固定監視し、sequence architectureの履歴内再調整は停止する。
9. logistic confidence blendは新規期間でBrier、log loss、ECEを並行出力し、3指標すべてがbaseline以下の場合だけconfidence昇格を検討する。
10. training windowはexpandingを標準とする。`--train-window-days` は再現実験専用で、別のwindow長を履歴へ合わせて最適化しない。
11. Extra Trees confidence blendはconfidence 0.53を変更せずforward運用し、accuracy、selection score、Brierがすべてbaseline以上の場合だけ高信頼採用laneへの昇格を検討する。
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
26. XGBoostは再現用学習器とする。通常教師・clear-body教師とも既存採用候補を超えないため、同じ履歴でtree parameterやblend weightを最適化しない。
27. Haar multiscaleは再現専用とする。developmentで選んだ0.525 laneがconfirmationで悪化したため、同じ履歴で窓長・系列・blend weightを再調整しない。
28. disagreement confidence 0.515は研究shadowとして完全未使用期間だけを測る。今回の履歴でモデル部分集合、weight、penalty、閾値を再探索せず、clear-body/signed-body候補を置換しない。
29. causal online expert weightingは再現専用とする。history rows、学習率、expert subsetを同じ履歴で再探索せず、固定等重みおよびsigned-body候補を置換しない。
30. session-relative confidenceは0.525研究shadowとして完全未使用期間を測る。同じ履歴でwindow、時間group粒度、clip、blend weight、閾値を変えず、clear-body 0.525と並行比較する。
31. four-class body confidenceは0.525教師表現shadowとして固定する。class境界・class数・HGB parameter・blend weightを履歴内再探索せず、clear-bodyを置換しない。
32. candidate registryの4 role championと2 accuracy challengerだけを固定forward比較する。fresh期間では同じgateを再計算し、championの閾値・weight・role境界を履歴へ合わせて変更しない。
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
56. CatBoostは再現専用学習器とする。Ordered/Plain、depth、iterations、learning rate、regularization、blend weight、confidence閾値を同じ履歴で再探索せず、Signed-body Quantile/Clear-body 0.525を維持する。
57. Temperature scalingは再現専用校正とする。温度範囲、期間平滑化、confidence閾値を同じ履歴で再探索せず、Platt標準校正とIntrabar Structure 0.55 precision championを維持する。
58. Intrabar Ordinal Shapeは再現専用とする。pattern長、tie処理、pattern subset、blend weight、confidence閾値を同じ履歴で再探索せず、Volatility Shape方向候補、Distribution/Extra Trees 0.53、Structure 0.55を維持する。
59. LightGBMは再現専用学習器とする。leaves、trees、learning rate、sampling、regularization、blend weight、confidence閾値を同じ履歴で再探索せず、Signed-body Quantile/Clear-body 0.525を維持する。
60. Directional Clarity教師filterは再現専用とする。clarity cutoff、保持率、body/ATRとの合成、blend weight、confidence閾値を同じ履歴で再探索せず、Distribution Shape/Extra Trees 0.53を維持する。
61. Signed Clarity連続教師は再現専用とする。target非線形化、loss、blend weight、confidence閾値を同じ履歴で再探索せず、Volatility Shape/Pressure方向候補とSigned-body Quantile/Clear-body 0.525を維持する。
62. Directional Clarity sample weightingは再現専用とする。weight offset、非線形化、上限、blend weight、confidence閾値を同じ履歴で再探索せず、Signed-body Quantile/Clear-body 0.525を維持する。
63. Intrabar Full Path方向維持0.53をselective confidenceの固定forward championとする。15地点、正規化、25% weight、閾値を履歴内再探索せず、完全未使用期間でDistribution Shape/Extra Trees以上のaccuracy・selection score・Brierとdown-normal局所整合を同時に確認するまでauthoritative confidence・odds・売買policyへ昇格しない。
