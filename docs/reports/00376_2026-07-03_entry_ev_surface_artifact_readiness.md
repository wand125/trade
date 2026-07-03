# Entry EV Surface Artifact Readiness

日時: 2026-07-03 21:40 JST
更新日時: 2026-07-03 21:40 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00375で「current-negative evaluated targetを増やす必要がある」と分かったため、00370 inventoryに出ている過去artifactが00368/00373系のselector surfaceへそのまま流用できるかを棚卸しした。
- `scripts/experiments/entry_ev_surface_artifact_readiness_diagnostics.py` を追加し、各metric parentの近傍にある `*trades.csv` と `config.json` を検査した。
- 17 metric parentsを検査した結果、`surface_ready_without_conversion=True` は0件。
- trade schemaだけを見ると10/17 parentsはsurface入力に必要な列を持つ。代表は `00310_position_quality_proxy_overlay_s1` と `short_entryblock_replacement_holdext_block_overlay_s1` の `entry_block_overlay_trades.csv`。
- ただし17/17 parentsでsurface用config key (`current_trades`, `family_predictions`, `candidate`) が不足した。次はschema-ready artifactへ既存00318 configのprediction/repair target設定を合成して試す必要がある。
- hold-extension stateful系の7 parentsは `entry_block_rule`, `entry_blocked`, `selector_variant` が足りず、trade schema変換も必要。

## Artifacts

- `data/reports/backtests/20260703_123616_20260703_entry_ev_00376_surface_artifact_readiness/`

Outputs:

- `surface_artifact_readiness_parent_summary.csv`
- `surface_artifact_readiness_trade_files.csv`
- `surface_artifact_readiness_support_targets.csv`
- `surface_artifact_readiness_meta.json`

## Method

Input:

- `data/reports/backtests/20260703_075023_20260703_entry_ev_00370_support_negative_month_inventory/`

Required surface config keys:

```text
current_trades
family_predictions
candidate
```

Required trade columns:

```text
role
family
month
candidate
selector_variant
entry_block_rule
entry_blocked
entry_decision_timestamp
exit_decision_timestamp
```

The diagnostic does not run a policy. It only ranks existing artifacts by:

- support-sufficient negative target count
- distinct target identity count
- whether a nearby trade file already has the surface schema
- whether the nearby config can be consumed directly by the selector surface

## Result

Overall readiness:

| metric | value |
|---|---:|
| metric parents scanned | 17 |
| ready without conversion | 0 |
| trade schema ready | 10 |
| needs trade schema conversion | 7 |
| needs surface config | 17 |
| max support-sufficient negative count | 6 |
| max target identity count | 9 |

Top candidates:

| metric parent | support neg | identities | trade schema | config ready | next action |
|---|---:|---:|---|---|---|
| `20260702_082037_20260702_entry_ev_00310_position_quality_proxy_overlay_s1` | 6 | 9 | yes | no | synthesize surface config |
| `20260702_074738_20260702_entry_ev_short_entryblock_replacement_holdext_block_overlay_s1` | 6 | 9 | yes | no | synthesize surface config |
| `20260702_074716_20260702_entry_ev_short_entryblock_replacement_hold_extension_stateful_s1` | 6 | 9 | no | no | convert trade schema + config |
| `20260702_075050_20260702_entry_ev_short_entryblock_replacement_holdext_reqmodel_block_overlay_s1` | 6 | 8 | yes | no | synthesize surface config |
| `20260702_080749_20260702_entry_ev_00309_veto_block_overlay_s1` | 6 | 8 | yes | no | synthesize surface config |

Schema-ready files:

- `entry_block_overlay_trades.csv`
- `confidence_gate_overlay_trades.csv`
- `month_warmup_overlay_trades.csv`

Schema-missing stateful files:

- `hold_extension_stateful_trades.csv`

Missing columns:

```text
entry_block_rule
entry_blocked
selector_variant
```

## Important Detail

The best-looking inventory rows are not automatically valid surface evidence.

Example: `00310_position_quality_proxy_overlay_s1` contains strong current-negative rows such as `refit2025 2025-05 -112.1634` under `loss_exit30_cd15__holdext_isolated_large_loss_t-5_h720` variants. The existing 00317 repair target config, however, mainly filters `loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720` variants.

So the next replay must align:

- `current_trades`
- `selector_variant_contains`
- `entry_block_rule`
- `repair_targets` filter
- `family_predictions`

Mixing nonmatching variant families would create a misleading target set.

## Decision

Accepted:

- surface artifact readiness diagnostic
- using 00370 inventory as a map for finding additional current-negative evaluation targets
- treating `00310_position_quality_proxy_overlay_s1` and `short_entryblock_replacement_holdext_block_overlay_s1` as first candidates for config synthesis

Rejected:

- treating inventory rows as independent samples
- treating an artifact as surface-ready only because the trade CSV has the required columns
- mixing `holdext_isolated_large_loss_t-5_h720` current rows with `holdext_isolated_large_loss_long_t-5_h720` repair target filters without explicit alignment

Standard policy remains NoTrade.

## Next

1. Build a small generated surface config for `00310_position_quality_proxy_overlay_s1` by combining its `entry_block_overlay_trades.csv` with the existing 00318 prediction/repair target config.
2. First use aligned `loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720` variants to avoid mixing target families.
3. Run winner-damage selector surface and replacement abstention on the aligned current-negative target set.
4. If support-limited targets are included, record them as a separate lane from support-sufficient negative-month repair.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_surface_artifact_readiness_diagnostics.py tests/test_entry_ev_surface_artifact_readiness_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_surface_artifact_readiness_diagnostics`: OK
- readiness diagnostic run: OK
