# Framework 提案暂存区

> Generator 和 Evaluator 在工作中发现值得沉淀的经验时，追加到本文件。
> Planner 在 done 阶段读取本文件，逐条提交给用户确认。
> 确认后由 Planner 正式写入 `framework/` 对应文件，并在 `CHANGELOG.md` 追加记录，最后从本文件移除已确认条目。
> 已闭环条目归档到 `framework/archive/proposed-learnings-archive-vX.Y.md`。

---

<!-- 2026-05-04: v0.9.9 沉淀完成（8 条 learnings 来源 BL-030/BL-031/BL-032），全部已写入 framework/ 对应文件 + CHANGELOG。 -->

<!-- 2026-05-04: v0.9.10 沉淀完成（3 条 learnings 来源 BL-033 + prod-mvp-readiness-audit），全部已写入 framework/ 对应文件 + CHANGELOG。 -->

<!-- 2026-05-05: v0.9.11 沉淀完成（5 条 learnings 来源 BL-020 + backend-full-scan-2026-05-04 audit），全部已写入 framework/ 对应文件 + 项目根 .nvmrc + .auto-memory/environment.md + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.11.md。 -->

<!-- 2026-05-05: v0.9.12 沉淀完成（3 条 learnings 来源 BL-034），全部已写入 pre-impl-adjudication.md §11 + database-patterns.md §8.1 + deploy-patterns.md §5 + evaluator.md §17 + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.12.md。 -->

<!-- 2026-05-06: v0.9.13 沉淀完成（2 条 learnings 来源 BL-024），全部已写入 deploy-patterns.md §5.1 + ai-action-contract.md §4.7 + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.13.md。 -->

---

## [2026-05-06] Planner johnsong（BL-040 planning 实地核查发现 BL-041 audit 过期）— v0.9.14 候选 #1：audit 起草前必须 grep 实物状态（v0.9.9 铁律 1 反向应用）

**类型：** 铁律延伸（v0.9.9 铁律 1「spec 涉及具体代码细节时必须核查源码」反向应用到 audit 起草）

**内容：** 2026-05-06 Planner johnsong 在 BL-040 planning 实地核查时发现 `prod-mvp-readiness-audit-2026-05-04.md §5 D2`「Dashboard 缺 PRD §4.1 三元素」与 prod 实际代码状态不符 — dashboard 3 元素（WorkflowSteps + CompetitorCpiCard + DashboardRoiTrendCard）实际在 commit `4fd778b @ 2026-05-01 11:25` 已由 MVP-internal-demo-prep-F001 完整实装，**audit 起草人（Planner Kimi 2026-05-04）写 D2 时未先 grep `dashboard/page.tsx` 当前 import / component 调用状态**。

后果：
- BL-041 在 backlog 至 2026-05-06 才被发现已 done（3 天 Soft-watch 错误信号）
- 用户 2026-05-05 22:30 锁下一批次时基于 audit 误判将 BL-040+BL-041 合批，浪费 ~10 min planning 评估
- v0.9.9 铁律 1 仅明示 spec 起草核查 — audit / review 类文档**也需要同等核查标准**

**根因：** v0.9.9 铁律 1 现行表述局限于「spec 起草」语境，未明示「audit / review / report 类文档」也适用同一规则。审计类文档常引用「文件:行 + 当前状态描述」，如不基于源码核查，轻则误导团队规划，重则误产生不必要的工作。

**建议写入：** `framework/harness/planner.md` 铁律 1 检查矩阵扩范围 — 从「spec 起草」扩到「spec / audit / review / readiness-report 起草」：

| 文档类型（v0.9.14 新增）| 核查动作 |
|---|---|
| **audit / review / readiness-report**（如 prod-mvp-readiness-audit / backend-full-scan / 安全审计 / 代码 review）| spec 同模式：涉及「文件:行 + 当前状态描述」必须 Read 实物 + grep 验证；引用「未含 / 缺 X / 待实装」必须先 grep 当前 import / component / migration 状态确认 |

**起草前 checklist（追加到 v0.9.9 铁律 1 现有 4 类后）：**
- [ ] audit / review 涉及「dashboard/page.tsx 未含 X」类断言 → 先 `grep -n "X" dashboard/page.tsx` 验证
- [ ] audit 涉及「component Y 缺」→ 先 `ls src/features/.../Y.tsx` + `grep import.*Y`
- [ ] audit 涉及「migration 待实装 Z」→ 先 `ls prisma/migrations/ | grep Z` + `grep "Z" prisma/schema.prisma`
- [ ] 任意「现状描述」与 git 最新 commit / `find` / `grep` 结果不一致 → 立即修订 audit 文本

**反面案例（已落 BL-040 单独 mini-batch；BL-041 retroactive 关闭）：** prod-mvp-readiness-audit-2026-05-04.md §5 D2 描述「dashboard/page.tsx 未含」，但 grep 即可发现 line 79+88+89 已引用 WorkflowSteps + CompetitorCpiCard + DashboardRoiTrendCard。本可在 audit 起草时 5 sec grep 验证避免。

**辅助沉淀（同模式）：** v0.9.13 §5.1「spec acceptance 改 deploy-script 时同 commit 必须改对应 yml workflow」也是「未核查实物 → silent skip 1+ 周」同根问题（实战中 BL-034 F001 注释明示 yml 桥接但实装漏）。两条规律共同强调：**任何引用「文件:行 + 行为描述」的文档必须基于源码，不靠记忆 / 假设 / 注释字面**。

**状态：** 待用户确认（v0.9.14 候选 #1，BL-040 done 阶段决议；与 v0.9.9 铁律 1 + v0.9.13 §5.1 互动延伸）
