# 00132 Shared Windows GPU Coordination

日時: 2026-08-11 23:09 JST

## 結論

新規学習のcanonical環境は引き続きWindows/WSL2とする。ただし同じ機械で画像生成、ローカルAI、対話処理が動くため、次足研究はCPU低優先度を標準にし、GPUは標準無効へ変更した。Intel Macは軽い確認・障害時の補助には使えるが、32GB RAM、Intel CPU、platform provenance混在を考えるとcanonical学習先には戻さない。

## 確認した競合

確認時のWSLは32 logical CPU、約30GiB memoryを認識し、約19GiB available、swapは約8GiB使用中だった。GPUはRTX 5090 32GBで、確認瞬間は約3.4GB使用・2% utilizationだったが、ComfyUIが常駐していた。瞬間的な低utilizationだけでは、その直後に始まる画像生成との競合を防げない。

画像生成や既存AIサービスは停止していない。WSLのmemory 40GB、24 logical processors、swap 16GBという次回自然再起動後の上限も変更せず、今回もWSL再起動を行っていない。

## CPU workerの標準

- 単独worker lock
- 8 threads
- nice 10、I/O priority 7
- available memory 16GiB以上
- 1分load 8以下
- `CUDA_VISIBLE_DEVICES` を空にし、CPU jobが暗黙にGPUを取得しない
- gate不成立はexit 75で延期し、他処理を止めない

通常の研究は次で実行する。

```bash
methods/next_bar/scripts/run_low_priority_worker.sh COMMAND [ARG ...]
```

## GPU workerの例外条件

GPU研究は、画像生成を止めた専用時間帯を利用者が確認した場合だけ許可する。次の3指定をすべて要求する。

```bash
TRADE_ENABLE_GPU=1 \
TRADE_REQUIRE_IDLE_GPU=1 \
TRADE_GPU_EXCLUSIVE_WINDOW=1 \
methods/next_bar/scripts/run_low_priority_worker.sh COMMAND [ARG ...]
```

さらに開始時のGPU使用量2,048MB以下、utilization 10%以下を要求する。ComfyUIがmodelを保持した現在の約3.4GBでは開始を延期する。exclusive windowは開始時snapshotだけでなく、そのjob中に画像生成を再開しないという運用上の予約を表す。

## 移管範囲と安全性

repository、共通OHLC履歴、選択済みnext-bar artifactという移管範囲は変えない。runtime、MT5口座状態、login、credential、secret、private keyは移さない。今回新しいデータ転送や口座情報のコピーは行っていない。

CPUでの新規学習はWindows/x86 Linux canonical、既存Mac artifactはserialized inference専用というplatform規則も維持する。Intel Macへ再学習を分散して同一candidate比較へ混ぜない。

## 実装

- `run_low_priority_worker.sh`: CPU defaultのGPU遮断、GPU明示許可、exclusive window、強化memory/load/GPU gate
- `windows_wsl_research_worker_v1.json`: machine-readable policy更新
- `test_next_bar_worker_policy.py`: CPU defaultとGPU二重gateの単体テスト

対象30 testとMac/Windows全体回帰を通した。全体結果は両方とも `1378 passed, 1 deselected, 83 subtests passed`。変更・転送対象の機密情報scanは0件だった。
