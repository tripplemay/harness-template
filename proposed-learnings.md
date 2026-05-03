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

## [2026-05-04] Reviewer (CLI as Codex) — 来源：BL-030-F002

**类型：** 模板修订

**内容：** Planner 在 spec acceptance 列出"跳转 / 链接 /xxx/{id}"等具体路由前，应核对项目实际路由是否存在（`grep -r "\[id\]/page.tsx" src/app` 或 `find src/app -name 'page.tsx' -path '*[*]*'`）。BL-030 spec §F002 写"跳转 /assets/{id}"但项目无该 detail 路由，Generator 实装链 `/assets?productId=X` 过滤页 — UX 等价但 Reviewer 验收时需判定是否 deviation。Spec 文字与项目路由错配让 Generator 被迫做"创造性翻译"，徒增审计负担。

**建议写入：** `framework/harness/planner.md` § Spec 写作 + 路由核对 checklist（"acceptance 中提到的 URL / 路由 / 端点必须先 grep 项目实际存在性"）

**状态：** 待确认

## [2026-05-04] Reviewer (CLI as Codex) — 来源：BL-030 整体

**类型：** 新规律 + 模板修订

**内容：** 数据通路迁移批次（写源 + 读源同时切换 + 历史 backfill）应在 D3 类决策中明确字段保留 / 删除策略 + 1 sprint 观察期清理批次预告，避免"幽灵字段"长期累积。BL-030 D3 选"A 方案保留 status 字段、内容字段不写、留 1 sprint 观察后单独清理批次"— 这个三段式（保留 / 不写 / 后清理）应作迁移批次模板。配套必备：(1) backfill 脚本默认 dry-run + idempotent + metadata 标记可批删；(2) 命名 / role 工具函数从 live 路径导出，backfill 共用同源真值防漂移；(3) deploy-checklist 列 5 product id 硬编码（防迁移漏）+ rollback DELETE WHERE metadata.backfilledFrom IS NOT NULL（幂等可重跑）。

**建议写入：** `framework/templates/migration-batch-checklist.md`（新增），或 `framework/harness/deploy-patterns.md` 加 § "数据通路迁移批次模板"

**状态：** 待确认
