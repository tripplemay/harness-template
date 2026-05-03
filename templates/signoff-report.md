# [批次名称] Signoff YYYY-MM-DD

> 状态：**待 Evaluator 验收**（progress.json status=verifying）
> 触发：[触发原因一句话]

---

## 变更背景

[描述本批次改动的背景和动机]

---

## 变更功能清单

### F-XXX-01：[功能标题]

**Executor：** generator / codex

**文件：**
- `path/to/file.ts`（新增 / 修改）

**改动：**
[描述具体改动内容]

**验收标准：**
- [可验证的标准1]
- [可验证的标准2]

---

<!-- 重复上面的块，每个功能一块 -->

## 未变更范围

| 事项 | 说明 |
|---|---|
| [未改动模块] | [为什么不改] |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| [指标] | [数值] | [数值] |

---

## 类型检查 / CI

```
[tsc / eslint 执行结果]
[gh run list --limit 1 --branch main 输出]
```

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → reverifying → done）交付。
`progress.json` 已设为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Soft-watch（不阻塞 done，需后续跟进）

> 本节由 Evaluator 在签收时填写。低-中风险或边界条件遗留事项列入此处，记录"非 bug 但要记账"的事实。每条声明 ID / 描述 / 风险等级 / 建议处置。
> 无 Soft-watch 项时本节可写"无"但不可删。

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | [描述] | low / medium / high | [建议] |

---

## Framework Learnings

> 本节由 Evaluator 在签收时填写提案，Planner 在 done 阶段消化、与用户确认后写入 `framework/`，并在 `framework/CHANGELOG.md` 追加记录。
> 不紧急的提案应先追加到 `framework/proposed-learnings.md`，由 Planner 在 done 阶段集中处理。
> 无 learnings 时三小节可整体删，但保留本 H2 标题 + 一行"本批次无 framework learnings"。

### 新规律
- [描述：发现了什么新的规律或最佳实践]
  - 来源：[哪个 feature / 哪次故障]
  - 建议写入：`framework/README.md` §经验教训 / `framework/harness/evaluator.md`

### 新坑
- [描述：踩到了什么坑，下次怎么避免]
  - 来源：[哪个 feature / 哪次故障]
  - 建议写入：`framework/README.md` §经验教训

### 模板修订
- [描述：某个模板文件需要补充或修改]
  - 建议修改：`framework/templates/xxx.md` 第 N 行
