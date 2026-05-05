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

---

## [2026-05-06] Generator Kimi（BL-024 F006 retroactive hotfix 起源）+ Planner johnsong 实战 Q2 ops 实地核查 — v0.9.13 候选 #1：spec acceptance 改 deploy-script 时同 commit 必须改对应 yml workflow

**类型：** 新规律（铁律级别 — 与 v0.9.12 §deploy-patterns.md §5 互动延伸）

**内容：** BL-034 F001 spec acceptance 已 done @ dbbfbb3（deploy-prod.sh 加 ALTER ROLE 段 line 71-81）但漏了同 commit 改 .github/workflows/deploy-prod.yml script 块加 `set -a; source .env.production; set +a` 桥接 → GH Actions Run 时 KOLMATRIX_APP_PASSWORD env var 不会 export 到 shell 环境 → ALTER ROLE 段 silent skip → prod kolmatrix_app 角色实际仍用 init migration 字面 'kolmatrix_app' 弱密码（CRIT-1 fix 未在 prod 生效 1+ 周）。

Planner johnsong 在 BL-024 prod redeploy ops 准备阶段（2026-05-05 ~23:00）实地核查 deploy-prod.sh 注释「Reads KOLMATRIX_APP_PASSWORD from .env.production via the SSH workflow's `set -a; source .env.production; set +a` (added in the GH Actions step)」与 deploy-prod.yml script 块实际内容对比才发现 — 注释明示但 yml 实装漏。需要 BL-024 F006 retroactive hotfix（用户 2026-05-05 23:05 决议方案 A，commit eacbbbb 实装）。

**根因：** spec 起草时 Planner / Generator 对「deploy 链」的端到端理解仅停在 deploy-script 层，未明确「shell env 来源 = yml 桥接」这一上下游关系。

**建议写入：** `framework/harness/deploy-patterns.md` §5（v0.9.12 沉淀 auth-gated endpoint）追加 §5.1「spec acceptance 改 deploy-script 时同 commit 必须改对应 yml workflow」：

1. **任何修改 `scripts/deploy-*.sh` / `infrastructure/deploy-*.sh` 的 spec feature acceptance**，必须同 commit 改对应 `.github/workflows/deploy-*.yml`（如 deploy-script 引入新的 env var 依赖 → yml script 块必须 `set -a; source .env*; set +a`）

2. **Planner 起草 spec 时检查项：**
   ```bash
   # spec lock 前跑：
   git diff --stat scripts/deploy-*.sh infrastructure/deploy-*.sh .github/workflows/deploy-*.yml
   # deploy-script 改动数 > 0 + yml 改动数 = 0 → 立即修订 spec acceptance 加 yml 配套段落
   ```

3. **Generator 实装时检查项：** deploy-script 改动需 yml 桥接同 PR；不分 commit 推

4. **Reviewer L2 验收时检查项：** staging deploy 不仅看 health endpoint，还要验 deploy-script 内每个 env-var-依赖步骤 silent skip 检查（grep deploy log "skipping" / "unset" / "warning"）— BL-034 F001 silent skip 持续 1+ 周未发现的根因正是 Reviewer 没看 deploy log 中 "⚠️ KOLMATRIX_APP_PASSWORD unset — skipping" 这行 warning

**反面案例（已落 BL-024 F006 retroactive hotfix）：** BL-034 F001 spec acceptance 写 ALTER ROLE 段 done @ dbbfbb3 但 prod CRIT-1 实际未修 1+ 周，到 BL-024 prod redeploy ops 准备阶段才暴露。本可在 BL-034 F001 spec lock 时加「同 commit 改 yml」检查项 + Reviewer L2 deploy log warning 抓取避免。

**状态：** 待用户确认（v0.9.13 候选 #1，BL-024 done 2026-05-06 阶段提案）

---

## [2026-05-06] Planner johnsong（BL-024 Q2 ops + BL-035 F013 同源痛点）— v0.9.13 候选 #2：mcp__aigc-gateway create_action_version schema 应暴露 max_tokens 字段

**类型：** 模板修订（mcp tool schema 扩展提案 — 跨项目）

**内容：** Planner Q2 ops（2026-05-05 23:30）执行 BL-035 F013 aigcgateway 服务端协调时发现 `mcp__aigc-gateway create_action_version` schema 仅含 `messages / variables / changelog / set_active`，**完全无 max_tokens 字段暴露**。`mcp__aigc-gateway update_action` 也仅含 `name / description / model`。导致 v0.9.11 §ai-action-contract.md §4 max_tokens 矩阵 dogfood **无法通过 mcp 完整自动化**，必须用户登录 aigcgateway Dashboard UI 手工设。

**影响：** prod-mvp-readiness audit + BL-035 F013 / BL-024 Q2 ops 都需要这个能力做完整 dogfood 自动化；本项目 6 个 Action max_tokens 推 Soft-watch 已是历史第二次（BL-035 + BL-024 两个 batch 共 12 次推延 max_tokens 设到 UI）。

**建议写入：**

1. **跨项目 issue（aigcgateway 项目独立项目，非 KOLMatrix 范围）：** mcp 工具 `create_action_version` + `update_action` 应暴露 `max_tokens` 字段；同时 `get_action_detail` 返回应含 `activeVersion.maxTokens` 以便 dogfood 验证「目标值已设」。

2. **短期 KOLMatrix 端：** 在 `framework/harness/ai-action-contract.md §4` 加注：
   ```markdown
   ### 4.X mcp 自动化可达性（v0.9.13 — BL-024 Q2 ops 沉淀）
   截至 2026-05-06 mcp__aigc-gateway 工具集对 max_tokens 字段不暴露：
   - create_action_version：仅接受 messages / variables / changelog / set_active
   - update_action：仅接受 name / description / model
   - get_action_detail：返回 activeVersion 但不含 maxTokens
   
   后果：v0.9.11 §4 max_tokens 矩阵 dogfood 仅能通过 aigcgateway Dashboard UI 手工设。spec 起草时 Planner 不应假设 mcp 自动化全覆盖 §4 矩阵；max_tokens 部分必须列入 user 手工待办（spec §6.1）+ Soft-watch 兜底（与 BL-035 F013 / BL-024 同处理）。
   
   长期：等 aigcgateway 暴露 max_tokens 后回头清理 6+ Action 历史 Soft-watch；移除本节注解。
   ```

**状态：** 待用户确认（v0.9.13 候选 #2，BL-024 done 2026-05-06 阶段提案）
