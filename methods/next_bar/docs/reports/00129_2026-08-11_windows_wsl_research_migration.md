# 00129 Windows/WSL Research Migration

日時: 2026-08-11 21:51 JST

## 結論

次足研究の新規学習先をWindows/WSL2へ移した。Ryzen 9 9950X、64GB RAM、RTX 5090 32GB、WSL内SSDという構成で、M4 Pro/48GBの母艦とIntel Mac/32GBより、CPU学習、将来のdeep learning、保存容量の余力が大きい。

ただし移管先ではComfyUI、ローカルAIサービス、対話処理も稼働する。研究処理は共有マシンの低優先度ワーカーとし、既存処理を停止せず、単独worker、8 thread、nice 10、低I/O優先度、空きmemory/load gateを標準にした。GPUを使う処理は、開始時の使用量12GB以下かつ利用率25%以下を要求する明示gateを付ける。

## WSL資源配分

次回の自然なWSL再起動から、上限をmemory 40GB、24 logical processors、swap 16GBとする設定へ変更した。Windows側へ24GB RAMと8 logical processorsを残しつつ、画像生成と研究が同じWSL内で共存できる配分である。

移管時点ではComfyUI等が稼働していたため、設定反映だけを行い、WSL再起動は実施しなかった。現行VMの資源上限は次回自然再起動まで旧設定のままである。

## 移管範囲

- repository: `/srv/trade` のWSL ext4へclone
- Python: uv 0.12.3、Python 3.12.13、project `.venv`
- 共通履歴: `data/processed/histdata/xauusd` の3ファイル、182,657,153 bytes
- 研究成果: baseline/reference/current candidateとState Correctnessを含む選択済みnext-bar artifact
- `runtime/`: 内容をコピーせず、空ディレクトリだけ作成

口座、login、credential、secret、private keyに該当するファイル名は0件、転送対象textの構造化secret keyも0件だった。MT5 runtime、口座状態、認証情報は移していない。

raw M1とM30 baseline prediction parquetのSHA-256は送受信元で一致した。M1保存済みartifactの最新推論も、方向、confidence、eligibility、odds validityまでMacとWindowsで一致した。

## 環境固定

Windows環境はNumPy 1.26.4、pandas 2.3.3、PyArrow 24.0.0、scikit-learn 1.7.2、SciPy 1.15.3へ揃えた。NumPy 2系への意図しない更新を避けるため、project constraintを `numpy>=1.26,<2` とした。

TorchはWindowsが2.13.0+cu130、過去Mac環境が2.2.2で一致しない。現行State CorrectnessのHGB/PlattはTorchを使わない。今後のGPU/deep learningは過去artifactの再現とみなさず、新しいWindows canonical seriesとして開始する。

## Platform再学習の扱い

同一input hash、NumPy 1.26.4、scikit-learn 1.7.2でも、ARM macOSとx86 LinuxのHGB再学習ではconfidenceに差が出た。M30で方向は全行一致した一方、confidence平均絶対差は0.2203pt、最大差は4.0050ptで、0.505採用maskは2,335行異なった。

Windows内ではNumPy 2.4.6から1.26.4へ変えた再実行の最大確率差が2.22e-16、0.505 mask完全一致で、Windows環境内の再現性は確認できた。転送破損ではなくplatform/compiled numerical implementation差と判断する。

以後は次のprovenance規則を固定する。

1. 新規学習はWindows/x86 Linuxをcanonicalとする。
2. 既存Mac学習artifactはserialized modelを保存し、推論parityにだけ使う。
3. Mac再学習とWindows再学習のartifactを同一candidate比較へ混在させない。
4. 移管途中だったM5/M15/M30 State CorrectnessはWindowsで全て再実行してから採否判断する。
5. 損失倍率は標準1.0だけを使う。

## 検証

WindowsでState Correctness対象5 testと保存artifactのlatest推論を確認した。全体testは低優先度workerで `1374 passed, 1 deselected, 83 subtests passed` だった。deselectしたEntry EVのdocs時刻testは既知の非next-bar項目である。

初回cloneでは、swing-evalの4 testが無視対象 `runtime/` の不在で失敗した。空ディレクトリで3件は解消し、残る1件は母艦の `runtime/latest_bridge_recovery_plan.json` を暗黙参照していた。test内に最小bridge fixtureを明示し、runtimeや口座情報に依存しない密閉testへ修正した。

## 運用

> 2026-08-11 23:09 JST追記: 画像生成との同時利用をさらに確認したため、GPU運用はreport 00132のCPU-default・exclusive-window方式へ強化した。以下のGPU例は履歴記録であり、現在の実行条件には使わない。

CPU研究は次のwrapperを必ず通す。

```bash
methods/next_bar/scripts/run_low_priority_worker.sh COMMAND [ARG ...]
```

GPU研究ではidle gateを追加する。

```bash
TRADE_REQUIRE_IDLE_GPU=1 methods/next_bar/scripts/run_low_priority_worker.sh COMMAND [ARG ...]
```

gateが忙しいと判定した場合は終了code 75で延期し、画像生成や他のAI処理を中断しない。長い学習の並列起動は避け、M5/M15/M30を順番に実行する。

## 成果物

- worker: `methods/next_bar/scripts/run_low_priority_worker.sh`
- machine-readable policy: `methods/next_bar/config/windows_wsl_research_worker_v1.json`
- environment lock: `pyproject.toml`, `uv.lock`
- hermetic migration test fix: `methods/swing_eval/tests/test_analysis.py`
