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

<!-- 2026-05-06: v0.9.14 沉淀完成（2 条 learnings 来源 BL-040 + BL-041 audit 过期 + BL-043 staging fix），全部已写入 planner.md 铁律 1 矩阵 +2 行延伸 + deploy-patterns.md §1.7（v0.9.7 §1.6 范围扩展）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.14.md。 -->

<!-- 2026-05-07: v0.9.15 沉淀完成（2 条 learnings 来源 BL-021 F002 撤再翻盘 + BL-049 测试基建 audit），全部已写入 planner.md 铁律 1 矩阵 +2 行（v0.9.15 #1 跨 pool 复现 + #2 stub environment-agnostic）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.15.md。 -->

<!-- 2026-05-08: v0.9.16 沉淀完成（1 条 learning 来源 BL-052 verifying P5 裁决），全部已写入 planner.md §"Planner 裁决职责" §P5.2 段 + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.16.md。 -->

<!-- 2026-05-08: v0.9.17 沉淀完成（1 条 learning 来源 BL-012 apify-kol fork audit），全部已写入 planner.md 铁律 1 矩阵 +1 行（v0.9.17 记忆条目陈旧风险）+ 反面案例段（BL-012 5/7→5/8 实战）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.17.md。 -->

<!-- 2026-05-08: v0.9.18 沉淀完成（1 条 learning 来源 BL-012 F001 fix-round 1 admin role enum mismatch），全部已写入 planner.md 铁律 1 矩阵 +1 行（v0.9.18 auth role enum 实物核查）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.18.md。 -->

<!-- 2026-05-08: v0.9.19 沉淀完成（1 条 learning 来源 BL-012 F002 fix-round 2 prod zod schema mismatch），全部已写入 planner.md 铁律 1 矩阵 +1 行（v0.9.19 external API response zod schema 实物 sample 验证）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.19.md。 -->

---

## [2026-05-09] Claude CLI — 来源：BL-060-soft-delete-ui-filter-hotfix fix-round 1（cc82a54）

**类型：** 新坑 / 模板修订

**内容：** Playwright e2e spec 跨文件 `login()` helper 实现漂移。`tests/e2e/database-fidelity.spec.ts` 用严格正则 `/(en|zh|ja|ko|es)/dashboard(/|$)/`，而 `marketer-dashboard.spec.ts` + `login-cinematic.spec.ts` 用宽松 `/dashboard(/|$)/`。staging 上 RSC prefetch + next-intl middleware rewrite 偶发慢 → 严格正则在 login redirect 中间态等不到「locale 段已 rewrite 完毕」的最终 URL → `waitForURL` 超时；宽松正则可吸收中间态。BL-060 fix-round 1 单点放宽 database-fidelity 一份修复（commit cc82a54），但根因（三个 spec 各自写 login helper = 配置漂移）未根治。

**教训三段：**
1. e2e helper 应跨 spec 文件保持一致 — 推荐抽出 `tests/e2e/helpers/auth.ts` 的共用 `login()` 实现，禁止各 spec 自写 helper
2. 凡涉及 next-intl middleware rewrite 的 URL 等待，**必须**用宽松正则 `/\/dashboard(\/|$)/` 形式吸收中间态，不要用 `/(en|zh|ja|ko|es)/dashboard(\/|$)/` 严格形式（除非显式要测 locale 路由本身）
3. 三个 spec 各写一份 helper = 已知反模式（test-double-disease 子类）

**建议写入：**
- 主位置：`.auto-memory/role-context/evaluator.md` 新增 § "E2E helper 一致性 / Playwright login waitForURL 模式"（~10 行）
- 备选：可同步在 `docs/dev/rules.md` 加一条"Playwright login() 等待用宽松正则"注解
- 后续动作（独立 batch，建议归 BL-054-flaky 批次）：抽出 `tests/e2e/helpers/auth.ts` 共用 login 实现

**状态：** 待确认
