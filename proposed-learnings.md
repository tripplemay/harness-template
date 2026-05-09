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

## [2026-05-09] Claude CLI — 来源：BL-060-soft-delete-ui-filter-hotfix fix-round 1 复验 PARTIAL（cc82a54 → 41b2f83）

**类型：** 新坑 / 模板修订

**事实链（按时间顺序）：**

1. **verifying 首轮：** Reviewer 17:16 PARTIAL — `database-fidelity.spec.ts` 5+ case 中 3 条在 `beforeEach.login()` 的 `waitForURL` 超时，单 worker + 60s timeout 仍复现
2. **首轮诊断（5 分钟）：** 三个 e2e spec 的 `login()` helper 实现漂移：
   - `database-fidelity.spec.ts` 用**严格**正则 `/(en|zh|ja|ko|es)/dashboard(/|$)/`
   - `marketer-dashboard.spec.ts` + `login-cinematic.spec.ts` 用**宽松** `/dashboard(/|$)/`
   - 假设：staging 上 RSC prefetch + next-intl middleware rewrite 偶发慢 → 严格正则在 redirect 中间态等不到 locale 段 rewrite 完成 → 超时
3. **fix-round 1（cc82a54）：** 单点放宽 database-fidelity 的正则，对齐宽松形式 + CI 全绿 + staging healthy
4. **reverifying（19:01）：** Reviewer 复验 PARTIAL — 7 case 中 **5 PASS + 2 FAIL**，剩余 FAIL 仍在 `beforeEach.login()` 的 `waitForURL` 超时：
   - ❌ `Bulk Action Bar mounts after a row checkbox toggles (state contract)`
   - ❌ `header CTAs (Export / Import / Add KOL) are wired and enabled (BL-024 F001-1/2/3)`
5. **关键差异化信号：** 这 2 条**单例跑能过**，但**整组跑时**在 beforeEach login() 超时 → 不是页面挂死、也不只是正则问题，是 **e2e suite 级稳定性 / 测试隔离 / 累积负载**问题

**升级后的教训（基于复验事实）：**

A. **正则一致性是必要不充分条件：** 跨 spec login helper 漂移确实是反模式（应抽 `tests/e2e/helpers/auth.ts`），但**统一为宽松正则后并未根治** → 说明 staging 偶发超时还有更深层因素

B. **整组 vs 单例差异 = suite-level 反模式信号：** 单 case 能过、suite 跑时后置 case 失败 → 候选根因清单（Reviewer 暂未确认哪个为主）：
   - 每个 case `beforeEach` 重新 `page.goto('/login') + 填表 + waitForURL` → 累积 7 次完整登录流，前 5 次成功后 staging 资源（PG 连接池 / next-intl cache / pm2 worker） pressure 累积
   - Playwright `storageState` 没复用：每 case 一次 cold start，staging 8GB RAM PM2 single-instance 扛不住
   - **根治方向：** 抽 `tests/e2e/global-setup.ts` 做一次性登录 + 写 `playwright/.auth/state.json` + 各 spec `use({ storageState })` 复用 cookie，比 `beforeEach.login()` 重做 N 次更稳定且更快

C. **单点正则放宽是 quick-fix 不是根治：** fix-round 1 的修法把 BL-060 的范围从"5 处 query filter"被动扩展到了"e2e infrastructure"，但只单点放宽一份 spec 的正则没解决底层 suite 稳定性。**正确做法本应：** 一旦发现是 suite-level e2e infra 问题，立即 surface 给 Planner 评估"扩 BL-060 范围 vs 拆独立 batch"，而非 Generator 单边判断"5 分钟修一行正则"

**建议写入（待 BL-060 done 后用户逐条确认）：**

1. **主位置：** `.auto-memory/role-context/evaluator.md` 新增 § "E2E suite 稳定性诊断"（~15 行）
   - 单例 PASS / suite FAIL 的差异化信号 = suite-level isolation 问题，不是 case 逻辑问题
   - Playwright `storageState` 共用 vs `beforeEach.login()` 的取舍
   - staging 资源约束（8GB RAM single PM2 instance）下的 e2e 容量上限
2. **次位置：** `framework/harness/generator.md` 新增 § "扩范围 vs 单点修的判断"
   - Generator 在 fixing 阶段发现"问题超出原 spec 范围"时的上报义务（不能单边判断）
   - 5 分钟修一行 ≠ 根治，需要给 Planner 范围评估机会
3. **后续 batch（独立）：** 归 BL-054-flaky 或新起 BL-061-e2e-infra：
   - 抽 `tests/e2e/helpers/auth.ts` + `global-setup.ts` + `storageState` 复用
   - 标准化所有 e2e spec 的 login 流程
   - 测 staging RAM/PM2 容量下 e2e suite 稳定上限

**状态：** 待确认（修订自首版 — 首版基于"fix-round 1 已修好"的错误前提，复验 PARTIAL 后升级到 suite-level 视角）
