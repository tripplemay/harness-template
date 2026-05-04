# Framework 提案暂存区

> Generator 和 Evaluator 在工作中发现值得沉淀的经验时，追加到本文件。
> Planner 在 done 阶段读取本文件，逐条提交给用户确认。
> 确认后由 Planner 正式写入 `framework/` 对应文件，并在 `CHANGELOG.md` 追加记录，最后从本文件移除已确认条目。
> 已闭环条目归档到 `framework/archive/proposed-learnings-archive-vX.Y.md`。

---

<!-- 待确认的提案出现在此处，示例格式：

## [YYYY-MM-DD] [角色] — 来源：F-XXX

**类型：** 新规律 / 新坑 / 模板修订 / 铁律补充

**内容：** [一句话描述]

**建议写入：** `framework/README.md` §经验教训 / `framework/harness/xxx.md` / 其他

**状态：** 待确认

-->

## [2026-05-04] Planner Kimi — 来源：BL-030 backfill ops → BL-031 暴露 FK orphan

**类型：** 新坑 + 铁律补充

**内容：** Planner 在 BL-030 done 阶段为不阻塞用户，绕过 Generator F003 backfill 脚本 RLS bug，用 SQL 直跑 INSERT 25 条 Asset 行（绕过 createAsset mutation）。**后果：** createAsset 内的 dualWriteEmailTemplateOnCreate 副作用未跑，15 条 ai_generated email 在 email_template 表无镜像；email_log.template_id 有 FK 到 email_template.id → 一旦用户 send 必撞 FK 500。隐藏不到 24h，BL-031 启动 Phase 1 调研时 Planner 自查发现并修补。

**根因：** Planner 决定 ops 路径时，看的是 mutation 的"主写"（INSERT into asset），未列写其内部所有副作用 checklist（dual-write / audit log / cache invalidation / 其它表 mirror 等）。"绕过 mutation = 等价于跑相同 SQL" 是错误等价。

**建议写入：**
1. `framework/harness/planner.md` 新增铁律 5「Planner ops 绕业务 mutation 函数前必须列写 mutation 内所有副作用 checklist 同步执行」 — Planner 决策"用 SQL ops 替代 mutation"前，必须 grep mutation 函数内所有 await 调用（dual-write / logAudit / queue.push / cache.invalidate 等），列入 ops SQL 一并执行；不能仅做主表 INSERT。
2. `framework/templates/migration-batch-checklist.md` §四 (Planner done 收尾) 加 checklist 项：「若批次中 Planner 用过 SQL ops 替代 mutation 调用，必须列出对应 mutation 的所有副作用并人工验证 / SQL 补齐」。

**状态：** 待确认（BL-031 done 阶段处理）
