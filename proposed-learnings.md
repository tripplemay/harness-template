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

<!-- 2026-05-04: v0.9.9 沉淀完成（8 条 learnings 来源 BL-030/BL-031/BL-032），全部已写入 framework/ 对应文件 + CHANGELOG。 -->

<!-- 2026-05-04: v0.9.10 沉淀完成（3 条 learnings 来源 BL-033 + prod-mvp-readiness-audit），全部已写入 framework/ 对应文件 + CHANGELOG。 -->

<!-- 2026-05-05: v0.9.11 沉淀完成（5 条 learnings 来源 BL-020 + backend-full-scan-2026-05-04 audit），全部已写入 framework/ 对应文件 + 项目根 .nvmrc + .auto-memory/environment.md + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.11.md。 -->

---

## [2026-05-05] Reviewer (CLI 临时担任 evaluator) — 来源：BL-034 F005 building 中段良性 partial-pending → Planner 短格式裁决 → fix-round 1 → reverifying done

**类型：** 新规律（短格式裁决模式 building 中段变种）

**内容：** Generator Kimi 在 BL-034 building 末尾做 F005 时遇到 spec/现实的良性偏差（spec 列 9 处 max_tokens 中 7 处走 aigcgateway /v1/actions/run 服务端 Action 模板，KOLMatrix 客户端代码不可覆盖；同理 4 处 wrap 中 topic-cloud videoTitles 走 actions/run）。Generator 主动停下 + 提交 generator_handoff 详细列出 spec/现实 gap + 推荐方案，**而非盲目实装错的目标**。Planner johnsong 14:00 短格式裁决方案 A（accept partial 进 fixing 完成可控范围 cost cap MVP，第 4 wrap + 7 处 max_tokens 推 BL-035 F013）→ Generator fix-round 1 cost-cap MVP（bb11ed1）+ deploy-staging.sh graceful-degrade fix-up（07a6db4）→ Reviewer reverifying 验收 → done。

这是 v0.9.11 §pre-impl-adjudication.md 短格式裁决模式的 **building 中段变种**：触发时机不是 pre-impl audit 阶段，而是 building 中段实装时；机制相同（Generator 主动停 + Planner 决策 + Generator 单步实装）。状态机流转：`building (7/8 + partial) → fixing (fix_rounds=1) → reverifying → done`。

**建议写入：** `framework/harness/pre-impl-adjudication.md` 加 §B「building 中段良性 partial-pending 变种」段落（与现有 §A pre-impl audit 互补），含触发条件 / Generator 行为指引 / Planner 短格式裁决格式 / 状态机切换规则（building → fixing 而非 verifying）

**状态：** 待确认（v0.9.12 候选）

---

## [2026-05-05] Reviewer (CLI 临时担任 evaluator) — 来源：BL-034 F003 logAudit RLS 启用 silent-fail 风险 + F007 deploy script 死循环

**类型：** 新坑（双坑）

**内容：**

**新坑 #1：F003 logAudit RLS 启用必须同 commit 配套改 logEvent。** spec §F003 原仅要求 `logAudit` 改 `withTenant`，但同 migration 启用 audit_log + event_log 两表 RLS 导致 `logEvent` 33 处调用方 silent fail（withTenant 无 tenantId 时空字符串 `app.tenant_id` 触发 RLS 拒写 INSERT）。Generator Kimi 主动同 commit a23d24d 配套修，避免 prod 静默丢事件 + 后续 317cf1c fix-up 修 kol-profile race + crm-overview RLS read。这是 cross-cutting helper（logAudit / logEvent / metrics 等）在 RLS 启用时的典型坑。

**新坑 #2：deploy script + new auth-gated endpoint 死循环 + bash 旧 bytecode。** F007 实装后 staging health endpoint 默认无 token 不返 git_sha；deploy-staging.sh 严格 grep git_sha → exit 1 → staging deploy 失败 → 用户无法落地 HEALTH_DETAIL_TOKEN env → deploy 持续红。Generator 在 fix-round 1 同步加 graceful-degrade 路径（commit 07a6db4：token 未配置时 warning + skip strict check）解死循环。但第二次 deploy 仍 fail：bash 旧 bytecode 已读取 — git pull 更新了文件但 bash 还跑旧版本；第三次 deploy 重启进程才生效。

**建议写入：**
- `framework/harness/database-patterns.md` §8 RLS template 加注：「同 migration 启用多表 RLS 时，所有 cross-cutting helper（logAudit / logEvent / metrics 等）必须在同 commit 配套改 withTenant，否则启用 RLS 后 silent fail 33+ 调用方。Generator 开工前必 grep helper 调用站点 + 列出 tenantId 来源核查清单作 spec acceptance 一项」
- `framework/harness/deploy-patterns.md` 加 §「new auth-gated endpoint 配套 deploy script」：(1) 新增 default-deny 健康检查端点时同 commit 修 deploy script 兼容；(2) deploy script 改动同 commit 后必须重启 deploy run（bash 旧 bytecode 已读取）；(3) 严格检查模式与宽容模式的切换条件须明文（如 env present-vs-absent）

**状态：** 待确认（v0.9.12 候选；与本会话 #1 短格式裁决变种合并处理）

---

## [2026-05-05] Reviewer (CLI 临时担任 evaluator) — 来源：BL-034 F007/F008 测试文件 unused import warning

**类型：** 模板修订

**内容：** BL-034 在 `src/app/api/health/__tests__/route.test.ts:18` 与 `tests/integration/db-platform-admin-nullif.test.ts:13` 各引入 1 个 unused import warning（'afterEach' / 'beforeEach'）— lint 0 errors / 3 warnings（其中 1 既有 youtube 无关 + 2 BL-034 引入），不阻断 PASS（exit code 0）。但 reverifying 阶段对 warning 类的处理无明文：是否切 fixing fix-round 2 让 Generator 处理？还是 Soft-watch 入 backlog？

**建议写入：** `framework/harness/evaluator.md` 在 §15 之后新增 §17「lint warnings reverifying 处理」：

| 情境 | 处理 |
|---|---|
| 0 errors + ≤3 unused-import-style warning（含 BL-034 之前的既有） | Soft-watch 不阻断 done；建议下批次顺手清理（1 行 edit） |
| 0 errors + ≥4 warning，或非 unused-import 类 warning（如 explicit-any / no-empty-function / no-explicit-any） | 切 fixing fix-round +1 让 Generator 处理 |
| ≥1 error | 必切 fixing |

来源：BL-034 F007 + F008 测试文件 unused import 入 Soft-watch S8。

**状态：** 待确认（v0.9.12 候选；与本会话 #1+#2 合并处理）
