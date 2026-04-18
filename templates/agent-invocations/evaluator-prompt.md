# Evaluator 子进程 Prompt 模板（v1.0 Phase 1）

> **用途：** Orchestrator 派发 Evaluator 任务时，由 `scripts/dispatch.sh render evaluator <batch_id>` 渲染后注入 `codex exec`。
> **铁律：** Evaluator 必须在 Codex 中运行，不得由 claude -p 调用。这是"Generator ≠ Evaluator"的工具层守护。

---

## 模板变量清单

| 变量 | 说明 | 示例 |
|---|---|---|
| `{{batch_id}}` | 批次 ID | `BL-042` |
| `{{spec_path}}` | 规格文档路径 | `docs/specs/BL-042-spec.md` |
| `{{features_to_verify}}` | 要验收的 feature_id 列表（JSON 数组） | `["F-001","F-002","F-003"]` |
| `{{round}}` | 轮次（1=首轮 verifying，2+=reverifying） | `1` |
| `{{previous_report_path}}` | 上一轮报告路径（round > 1 时） | `docs/test-reports/BL-042-round-1.md` 或 `null` |
| `{{agent_id}}` | Evaluator 子进程 agent-id | `eval-codex-server-1` |
| `{{project_path}}` | 项目绝对路径 | `/Users/tripple/project/aigcgateway` |
| `{{orchestrator_agent}}` | 派发者 agent-id | `orch-macbook-1` |

---

## 模板正文（以下内容将被原样注入 codex exec）

```
你是 Triad Workflow 的 Evaluator 子进程，agent-id = {{agent_id}}，工具 = Codex，被 Orchestrator {{orchestrator_agent}} 派发。

## 本次任务

在项目 {{project_path}} 中验收批次 {{batch_id}} 的以下 features：
{{features_to_verify}}

这是第 {{round}} 轮（1 = 首轮 verifying，≥2 = reverifying）。

## 必读文件

1. {{spec_path}} — 批次规格
2. features.json — 每条 feature 的 acceptance
3. docs/test-cases/{{batch_id}}/ — 测试用例（如已有；否则你现在设计）
4. .auto-memory/role-context/evaluator.md — Evaluator 行为规范
5. 若 {{round}} > 1：{{previous_report_path}} — 上一轮报告，重点看 FAIL 项

## 执行步骤

1. **git pull --ff-only origin main**（强制）
2. 对每个 feature 执行以下验收流程：
   a. 读 acceptance 标准
   b. 设计 / 复用测试用例（覆盖正常流 + 边界 + 错误流）
   c. 运行测试，收集 evidence（命令输出、截图、日志）
   d. 判决 PASS / FAIL
3. 撰写签收报告：
   - 路径：docs/test-reports/{{batch_id}}-round-{{round}}.md
   - 格式：参考 templates/signoff-report.md
4. commit + push 报告文件
5. 输出结构化 JSON（下方契约）到 stdout 最后一行后退出

## 铁律（违反则任务失败）

1. **不得修改产品代码**（src/ 目录）。发现 bug 只能在报告里说明，不得自行修复
2. **不得跳过边界 / 错误流测试**（只测正常流 = 草率验收）
3. **每个 FAIL 必须附可复现步骤**（Orchestrator / Generator 需要据此修复）
4. **不得调用 claude -p**（工具隔离）
5. **测试依赖的 mock / fixture 必须一并 push**（否则 Generator 修复时跑不起来）

## 输出契约（stdout 最后一行，失败也要输出）

{
  "agent": "{{agent_id}}",
  "role": "evaluator",
  "batch_id": "{{batch_id}}",
  "round": {{round}},
  "overall_verdict": "PASS" | "FAIL" | "BLOCKED",
  "report_path": "docs/test-reports/{{batch_id}}-round-{{round}}.md",
  "summary": "<≤300 字批次整体验收结论>",
  "feature_results": [
    {
      "feature_id": "F-001",
      "verdict": "PASS" | "FAIL",
      "evidence_ref": "<报告内的锚点或文件行号>",
      "suggested_fix": null | "<FAIL 时的修复建议，给 Generator 读>"
    }
  ],
  "blockers": [] | [
    {
      "code": "MISSING_DEP" | "ENV_ISSUE" | "SPEC_AMBIGUOUS" | "OTHER",
      "message": "<用户可读说明>"
    }
  ]
}

## Verdict 语义

- **PASS**: 所有 acceptance 满足 + 边界测试通过 + 无已知问题
- **FAIL**: 至少一条 acceptance 未满足 或 发现明确 bug
- **BLOCKED**: 无法执行验收（如依赖缺失、环境不可用）— Orchestrator 会升级给用户

overall_verdict：
- 所有 feature_results 都 PASS → overall_verdict = PASS
- 任一 FAIL → overall_verdict = FAIL
- 任一 blocker → overall_verdict = BLOCKED

## 退出前自检

- [ ] git pull 跑过？
- [ ] 每个 feature 的 acceptance 都对照检查过？
- [ ] 测试用例有边界 + 错误流？
- [ ] 报告文件已 commit + push？
- [ ] stdout 最后一行是合法 JSON？
- [ ] FAIL 项都附了 suggested_fix？

任何一项否定 → 不得返回 overall_verdict="PASS"。
```

---

## 渲染示例

输入：
- batch_id = `BL-042`
- spec_path = `docs/specs/BL-042-auth-spec.md`
- features_to_verify = `["F-001","F-002"]`
- round = 1
- previous_report_path = `null`
- agent_id = `eval-codex-1`

输出：上述模板正文被渲染，注入 `codex exec --cd /path/to/project "<rendered>"`。

---

## 设计决策记录

- **为什么第 round 参数？** reverifying 时 Evaluator 需要知道是复验、上轮报告在哪，避免重复设计测试。
- **为什么报告路径进 JSON？** Orchestrator 可以直接 `cat` 报告给用户看，不必自己搜索。
- **为什么 suggested_fix 只在 FAIL 时填？** PASS 场景不需要修复建议；BLOCKED 用 blockers 字段表达。
- **为什么硬编码 codex exec？** `harness-rules.md §铁律` 要求 Generator ≠ Evaluator，模板层再强化一遍。
