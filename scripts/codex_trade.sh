#!/usr/bin/env bash
# Codex 対話セッション（確認プロンプトなし）
#
#   新規:   scripts/codex_trade.sh
#   再開:   scripts/codex_trade.sh resume <session-id>
#           scripts/codex_trade.sh resume --last
#
# 設定の意味:
#   approval_policy=never                        コマンド実行のたびの確認を出さない
#   --sandbox workspace-write                    リポジトリ配下への書き込みを許可
#   sandbox_workspace_write.network_access=true  git push / pip 等のネットワークを許可
#
# いずれも `codex exec --strict-config` で有効性を実測確認済み（2026-08-16）。
#
# 排他: 同じリポジトリで Codex を2つ走らせると status.md と git index を奪い合う。
#       他の codex が動いていたら起動しない。

set -uo pipefail

REPO=/srv/trade
cd "$REPO" || exit 1

# --- 排他チェック（自分自身と、このスクリプト経由の子は除く） ---
others=$(pgrep -af "codex (exec|resume)" | grep -v "^$$ " | grep -v "codex_trade.sh" || true)
if [ -n "$others" ]; then
  echo "ERROR: 別の Codex が稼働中です。同一リポジトリで2つ走らせると衝突します。" >&2
  echo "$others" >&2
  echo "" >&2
  echo "先に停止してください（無人ループなら touch $REPO/.codex-loop.stop）。" >&2
  exit 1
fi

if ! codex login status 2>&1 | grep -qi "logged in"; then
  echo "ERROR: codex is not logged in. 'codex logout && codex login' を先に実行してください。" >&2
  exit 1
fi

exec codex "$@" \
  --sandbox workspace-write \
  -c approval_policy="never" \
  -c sandbox_workspace_write.network_access=true
