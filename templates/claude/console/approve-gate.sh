#!/usr/bin/env bash
# console-mode.md —— 人类批准闸门的本机入口（控制台之外的另一条合法路径）。
#
# ⚠️ **必须由你本人运行**，不要让 agent 代跑。在 Claude Code 里用 `!` 前缀自己执行：
#     ! bash .claude/console/approve-gate.sh --approve --by yixing
#
# 为什么必须你自己跑：`pending_gate.decision` 是「人类批准」在 git 里的唯一表示。
# agent 若能写它，「阶段推进键归人」「L2 需授权」就全部退化成自觉。
# 本脚本走 Bash，不触发 PostToolUse hook；写完立即 commit，使 guard 在后续 agent 写入时放行。
#
# 用法：
#   approve-gate.sh --approve  --by <你的标识> [--note "..."] [--progress progress.json] [--no-commit]
#   approve-gate.sh --reject   --by <你的标识> [--note "..."]
#   approve-gate.sh --show                      只看当前待批闸门

set -euo pipefail
ACTION=""; BY=""; NOTE=""; PROG="progress.json"; COMMIT=1

while [ $# -gt 0 ]; do
  case "$1" in
    --approve)  ACTION="approve"; shift ;;
    --reject)   ACTION="reject"; shift ;;
    --show)     ACTION="show"; shift ;;
    --by)       BY="$2"; shift 2 ;;
    --note)     NOTE="$2"; shift 2 ;;
    --progress) PROG="$2"; shift 2 ;;
    --no-commit) COMMIT=0; shift ;;
    *) echo "[gate] ⛔ 未知参数：$1" >&2; exit 2 ;;
  esac
done

[ -f "$PROG" ] || { echo "[gate] ⛔ 不存在：$PROG" >&2; exit 2; }

if [ "$ACTION" = "show" ] || [ -z "$ACTION" ]; then
  python3 - "$PROG" <<'PY'
import json, sys
g = (json.load(open(sys.argv[1])) or {}).get("pending_gate")
if not g:
    print("[gate] 当前无待批闸门"); sys.exit(0)
print(f"闸门 {g['id']}")
print(f"  类型    {g['kind']}")
print(f"  批次    {g['batch']}   {g.get('from_status')} → {g.get('to_status')}")
print(f"  举起于  {g['raised_at']}  by {g['raised_by']}")
print(f"  说明    {g['detail']}")
for e in (g.get("evidence") or []):
    print(f"  取证    {e}")
d = g.get("decision")
print(f"  决策    {'待批' if not d else d['action'] + ' by ' + d['by'] + ' @ ' + d['at']}")
PY
  [ "$ACTION" = "show" ] && exit 0
  echo "[gate] 需指定 --approve / --reject / --show" >&2; exit 2
fi

[ -n "$BY" ] || { echo "[gate] ⛔ 缺 --by <你的标识> —— 批准必须可归属" >&2; exit 2; }

NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - "$PROG" "$ACTION" "$BY" "$NOTE" "$NOW" <<'PY'
import json, sys
path, action, by, note, now = sys.argv[1:6]
prog = json.load(open(path))
g = prog.get("pending_gate")
if not g:
    print("[gate] ⛔ 当前无待批闸门，无可批准"); sys.exit(2)
if g.get("decision"):
    print(f"[gate] ⛔ 闸门 {g['id']} 已有决策（{g['decision']['action']} by {g['decision']['by']}），"
          f"不覆盖。如需改判，请让机器先消费再重新举闸门。"); sys.exit(2)
d = {"gate_id": g["id"], "action": action, "by": by, "at": now, "scope": {"once": True}}
if note: d["note"] = note
g["decision"] = d
json.dump(prog, open(path, "w"), ensure_ascii=False, indent=2)
open(path, "a").write("\n")
print(f"[gate] ✓ 闸门 {g['id']} 已{'批准' if action=='approve' else '驳回'}（by {by}，最小授权：仅此一次）")
PY

bash "$(dirname "${BASH_SOURCE[0]}")/validate-pending-gate.sh" schema "$PROG" || exit 2

if [ "$COMMIT" -eq 1 ] && git rev-parse --git-dir >/dev/null 2>&1; then
  GID="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['pending_gate']['id'])" "$PROG")"
  git add "$PROG"
  git commit -q -m "chore(gate): ${ACTION} ${GID} by ${BY}" || true
  echo "[gate] ✓ 已提交。机器侧 \`git pull\` 后本决策即随 HEAD 到达，guard 自动放行。"
  echo "[gate]   如需其他机器立刻看到，记得 git push。"
else
  echo "[gate] ⚠️ 未提交（--no-commit 或非 git 仓库）。未提交前 guard 会把它当作本地改动而拒绝 agent 的后续写入。"
fi
