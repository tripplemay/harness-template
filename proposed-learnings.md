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

## [2026-05-04] Planner Kimi — 来源：BL-030 prod backfill 执行

**类型：** 新坑 + 铁律补充

**内容：** BL-030-F003 backfill 脚本用 `withPlatformAdmin` 期望跨 tenant 扫 product 表 → 实际返回 0 行。RLS 调研：`withPlatformAdmin` 只设 `app.is_platform_admin='true'`，但 `product` 表 RLS 策略 (`tenant_isolation`) **只检查 `app.tenant_id`，不检查 `app.is_platform_admin`**。只有 `user` 表 RLS（user_isolation 策略）含 platform admin 旁路。Generator 误以为 `withPlatformAdmin` 是通用 RLS 旁路；spec §3.6 也未核对 product 表 RLS 实际策略。Planner 当时未 grep `pg_policy` 验证。**Planner 决策时落到 SQL 直跑（superuser 绕 RLS），25 行成功入库 + Product.aiAssets 缩水 + 幂等可重跑**。脚本本身 bug 留待后续 hotfix（不影响本批次 prod 已修）。

**建议写入：**
1. `framework/harness/planner.md` 铁律 1 加补充：spec 涉及 RLS / 跨租户扫描代码细节时，必须 grep `prisma/migrations/*` 中对应表的 `CREATE POLICY` 或 `pg_policy` 实测，确认 `withPlatformAdmin` / `withTenant` / 自定义 setting 在该表上的实际行为，不能假设"platform admin 万能"。
2. `framework/harness/database-patterns.md`（如不存在则新建）记录"RLS 旁路矩阵"：哪些表的 policy 含 `app.is_platform_admin` 旁路、哪些只认 `app.tenant_id`、哪些有其他自定义 setting。当前已知：`user` 表含旁路（auth credentials 流必需）；`product` / `asset` / `audit_log` 等只认 tenant_id。

**状态：** 待确认（BL-030 done 后 Planner 在下一 done 阶段或独立 hotfix 批次处理）
