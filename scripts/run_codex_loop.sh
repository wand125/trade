#!/usr/bin/env bash
# Codex 無人ループ — status.md の「次の検証」を1件ずつ処理し、commit/push まで行う。
#
#   起動: tmux new-session -d -s codexloop -c /srv/trade 'scripts/run_codex_loop.sh'
#   停止: touch /srv/trade/.codex-loop.stop   （実行中の1件を終えてから止まる）
#   監視: tail -f /srv/trade/.codex-loop.log
#
# 設計の要点:
#   - 1起動=1件。まとめて進めない（レポート単位でレビューできるようにするため）
#   - 確認プロンプトを出さない: approval_policy=never + sandbox=workspace-write
#   - git push のためにサンドボックスのネットワークを開ける
#   - nice/ionice で最低優先度。ComfyUI/Ollama 等の常駐処理を邪魔しない
#   - 認証切れを検知したら即停止する（無人で空回りさせない）

set -uo pipefail

REPO=/srv/trade
LOG="$REPO/.codex-loop.log"
STOP="$REPO/.codex-loop.stop"
PROMPT="$REPO/scripts/codex_loop_prompt.md"

# 1件処理したあとの待ち時間（秒）
SLEEP_OK=${SLEEP_OK:-300}
# 着手できるものが無かった / ブロックされたときの待ち時間
SLEEP_IDLE=${SLEEP_IDLE:-3600}
# 連続で BLOCKED / NOTHING_TO_DO がこの回数続いたらループを終える
MAX_IDLE=${MAX_IDLE:-3}

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }

cd "$REPO" || { echo "cannot cd $REPO"; exit 1; }
[ -f "$PROMPT" ] || { echo "prompt not found: $PROMPT"; exit 1; }
rm -f "$STOP"

# --- 事前確認: 認証 ---
if ! codex login status 2>&1 | grep -qi "logged in"; then
  log "ABORT: codex is not logged in. Run 'codex logout && codex login' first."
  exit 1
fi
log "=== codex loop start (pid $$) ==="
log "branch: $(git branch --show-current)  head: $(git log --oneline -1)"

idle_streak=0
iter=0

while true; do
  if [ -f "$STOP" ]; then
    log "stop file found -> exiting"
    break
  fi

  iter=$((iter + 1))
  log "--- iteration $iter start ---"

  out=$(nice -n 19 ionice -c3 codex exec \
          --sandbox workspace-write \
          --skip-git-repo-check \
          -c approval_policy="never" \
          -c sandbox_workspace_write.network_access=true \
          "$(cat "$PROMPT")" 2>&1)
  rc=$?

  printf '%s\n' "$out" >> "$LOG"

  # --- 認証切れの検知（exec は 401 でも exit 0 を返すことがあるため文字列で見る） ---
  if printf '%s' "$out" | grep -qiE '401 Unauthorized|refresh token was revoked|Not logged in'; then
    log "ABORT: authentication failed. Run 'codex logout && codex login' and restart the loop."
    break
  fi

  status_line=$(printf '%s' "$out" | grep -oE 'LOOP_STATUS: (DONE|NOTHING_TO_DO|BLOCKED).*' | tail -1)
  log "iteration $iter end (rc=$rc) ${status_line:-LOOP_STATUS: (not reported)}"

  case "$status_line" in
    LOOP_STATUS:\ DONE*)
      idle_streak=0
      sleep_for=$SLEEP_OK
      ;;
    LOOP_STATUS:\ NOTHING_TO_DO*|LOOP_STATUS:\ BLOCKED*)
      idle_streak=$((idle_streak + 1))
      sleep_for=$SLEEP_IDLE
      ;;
    *)
      # 状態を報告しなかった場合も idle 扱いにする（暴走させないため）
      idle_streak=$((idle_streak + 1))
      sleep_for=$SLEEP_IDLE
      ;;
  esac

  if [ "$idle_streak" -ge "$MAX_IDLE" ]; then
    log "idle streak reached $MAX_IDLE -> exiting (human input needed)"
    break
  fi

  log "sleeping ${sleep_for}s"
  sleep "$sleep_for"
done

log "=== codex loop end (iterations: $iter) ==="
