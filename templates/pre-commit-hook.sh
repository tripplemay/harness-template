#!/usr/bin/env bash
# State-machine JSON validation pre-commit hook
# Place this at .git/hooks/pre-commit and chmod +x
#
# Source: harness-rules.md 铁律 #11
# 触发：MVP-internal-demo-prep commit b44b79d 推上去 progress.json 缺闭合 } 进入 main
# 防御：commit 前自动 parse 校验，挂钩失败拒提交

set -e

STATE_FILES=(
  "progress.json"
  "features.json"
  "backlog.json"
)

failed=0
for file in "${STATE_FILES[@]}"; do
  # 仅检查本次 commit 中实际改动的状态机文件（不阻塞无关 commit）
  if git diff --cached --name-only | grep -q "^${file}$"; then
    if ! python3 -c "import json; json.load(open('${file}'))" 2>/dev/null; then
      echo "❌ pre-commit: ${file} JSON parse failed."
      python3 -c "import json; json.load(open('${file}'))" 2>&1 | head -5
      failed=1
    else
      echo "✓ pre-commit: ${file} JSON valid"
    fi
  fi
done

if [ $failed -ne 0 ]; then
  echo ""
  echo "提交被拒：状态机 JSON 文件解析失败。"
  echo "修复后重新 commit；或临时绕过用 'git commit --no-verify'（不建议）。"
  exit 1
fi

exit 0
