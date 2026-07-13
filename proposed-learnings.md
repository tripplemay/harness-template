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

<!-- 2026-05-10: v0.9.20 沉淀完成（1 条 learning 来源 BL-060 fix-round 1→2 e2e suite-level isolation vs 单 case 信号区分），写入 .auto-memory/role-context/evaluator.md §"E2E suite 稳定性诊断" + .auto-memory/role-context/generator.md §"扩范围 vs 单点修的判断"。后续 batch 候选（抽 tests/e2e/helpers/auth.ts + global-setup.ts + storageState 复用）入 backlog 跟踪。归档暂未写 framework/archive/proposed-learnings-archive-v0.9.20.md（git history 已有 commits cae1f8f / 821c094 完整记录）。-->

<!-- 2026-07-09: v1.0.0 沉淀完成（1 条 learning 来源 BL-064 IA refactor redirect scope），写入 memory/role-context/generator.md §"IA refactor redirect scope 评估" + memory/role-context/planner.md §"IA refactor 类批次 redirect 清单评估" + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v1.0.md。 -->

---

## [2026-07-12] Claude（harness-fit 分析 · 独立任务）— 来源：单工具 Claude + dynamic Workflow 工作流契合度评估（本会话 workflow wt27gd5xu，三视角 + 红队对抗复核）

**背景：** 用户已把主 coding 工作流收敛到单工具（仅 Claude Code），编码阶段用 Claude dynamic Workflow 编排。评估结论：harness 高契合且真提质，但价值不对称——**契约纪律 + 持久骨架**是纯增量（引擎给不了），**阶段内部编排**与引擎重叠、**多工具/多机底座**大部分是死重。以下提案已经过红队校准（推翻了"状态机=冗余仪式""慢车道=死重""Workflow 1:1 替代无自评"三个过度自信结论）。

---

### P0 —— 正确性前置（naive 上 Workflow 会踩的坑）

**P0-1 · 类型：新坑 / 铁律补充**
- **内容：** Claude Workflow 的 loop-until-done 天生会自主推进到"完成"并自排下一步，直接违反 `orchestration-patterns.md` §6 硬铁律「→verifying / →done 不得在无人值守循环中自动完成」。把阶段内部交给 Workflow 时，若不定契约就是**正确性回归**，不只是重复仪式。
- **建议写入：** `harness/orchestration-patterns.md` 新增「§8 Workflow run ⇄ progress.json 日志契约」小节（引擎只跑阶段内部、绝不 flip status 跨阶段；每步结果落盘持久文件；中途崩溃逐条对账）+ `harness-rules.md` 铁律区补一条呼应。
- **状态：** 部分落地 —— §8 已写入 `orchestration-patterns.md`（CHANGELOG v1.0.2）；剩余待确认：`harness-rules.md` 铁律区呼应条。

**P0-2 · 类型：新坑（最高风险）**
- **内容：** 沉淀闭环是事故驱动的，靠每批次一份 Evaluator 验收记录喂养。in-tool Workflow 若只在 context 里验完、不落"命名验收工件（BL-id + verdict + fix_round）"，`proposed-learnings.md` 会因**无 emitter 而静默饿死**（本文件现已显示"当前无待确认提案"即征兆）。这是模块级、产品级的静默失败——维护闭环本身就是本框架的产品。
- **建议写入：** `harness/orchestration-patterns.md` §4 + §8 + `templates/claude/skills/verify/SKILL.md`（verify 每轮必须持久化命名验收工件回喂沉淀，不可省）。
- **状态：** 部分落地 —— §8 契约 4 已写入 `orchestration-patterns.md`（CHANGELOG v1.0.2）；剩余待确认：verify SKILL.md 改写（Patch B，未落）。

**P0-3 · 类型：模板修订**
- **内容：** `/verify` step 3、`/build` step 5 把 fan-out/并行以**散文指针**（"按 §4 / §3"）交付，未真正 invoke Workflow——按框架自己"装进工具链才是强制"的标准，这层仍停在"写在文件里"。注意：fan-out 是**尾部场景**（触发门 ≥4 features），日常默认=单个隔离 evaluator subagent 本就 native，**不要把机制化 fan-out 当最高优先级**（红队降级）。
- **建议写入：** `templates/claude/skills/verify/SKILL.md` step 3 / `templates/claude/skills/build/SKILL.md` step 5 改为触发门命中时真正调 Workflow，并显式"停在阶段边界交还用户"。
- **状态：** 待确认

### P1 —— 结构精简 + 定位重申

**P1-1 · 类型：新规律（红队纠正，勿一刀切）**
- **内容：** 慢车道拆分：git **同步总线**语义单机确为死重，但两样单机也真实的能力搭在同一标签上不可一起砍——① **独立会话 evaluator** 是比 subagent **更强**的独立性（无编排者写的 prompt，免疫铁律 12 的作者污染风险）；② **跨会话/抗压缩交接**（多日批次 + 压缩会在同一会话内重现"新读者"问题）。
- **建议写入：** `docs/01-concepts.md` 慢车道段 + `harness/orchestration-patterns.md` §7（区分"同步总线"与"独立会话隔离 / 跨会话持久"两类，前者可选、后者保留）。
- **状态：** 待确认

**P1-2 · 类型：模板修订**
- **内容：** 快车道热路径剥离慢车道底座：`/plan /build /verify` step 1 的 `git pull --ff-only` + `.agent-id`/`.agents-registry` 读、`session-start.sh` 的 `role_assignments` 注入、`bootstrap.sh:71` 无条件铺 `AGENTS.md`——单机全是空转仪式，改为多机模式 opt-in。
- **建议写入：** 三个 skill SKILL.md step 1 + `templates/claude/hooks/session-start.sh` + `bootstrap.sh`。
- **状态：** 待确认

**P1-3 · 类型：新规律（定位重申）**
- **内容：** 把 harness 明确定位为坐在 Workflow 引擎之上的**薄契约纪律 + 持久骨架层**：引擎给编排**形状**，harness 给**常设默认强制 + 约束载荷（受限工具集 / 只认实物 / 误报预检 / 测试设计权）+ 用户闸门 + 抗压缩骨架**——这四样引擎都没有。
- **建议写入：** 新增 `harness/workflow-bridge.md`（角色 ⇄ Workflow stage 映射；标注哪些规则由引擎结构性强制、哪些仍是散文护栏）。
- **状态：** 待确认

### P2 —— 清理与补缺（须外科式，勿误伤承重项）

**P2-1 · 类型：铁律澄清（红队纠正）**
- **内容：** 机制化其实比宣传的薄：唯一硬阻断是 `validate-state-json.sh`（还只查 JSON **语法**，不查"status=done 但 signoff 为空"这种语义）；无自评 / done-门 / 裁决不洗白 / spec 源码核查**都活在散文里**。推论："砍散文仪式"必须外科式，勿把承重约定当仪式误删。
- **建议写入：** `harness-rules.md` §机制化守门（标注"当前硬阻断仅覆盖 JSON 语法，语义门仍靠约定"）。
- **状态：** 待确认

**P2-2 · 类型：新坑**
- **内容：** `executor:generator|evaluator` 是**活的路由位**（把报告类任务路进 verifying、选 Evaluator-only 批次流），与已死的 `executor:"codex"` 别名同段落；清 Codex 血缘时须**外科分离**，勿连带误删路由。
- **建议写入：** `harness-rules.md` lines 47/108 + `evaluator.md` + `planner.md` 相关行的清理注意事项。
- **状态：** 待确认

**P2-3 · 类型：新坑**
- **内容：** 对抗复核的误报目录（`patterns/testing-env-patterns.md`）是 **stack-coupled**（Prisma/Next/Postgres-RLS），换技术栈大半不可移植，且框架无"给新栈重播种目录"的机制。
- **建议写入：** `patterns/testing-env-patterns.md` 顶部标注适用栈 + 提供"新栈重播种"指引。
- **状态：** 待确认

**P2-4 · 类型：模板修订（与上一轮接入缺口同源）**
- **内容：** 补存量项目接入路径：`bootstrap.sh` 遇 `harness-rules.md` 存在即 abort（仅 greenfield）；加 `--adopt` 模式只装 `.claude/` 机制层（hooks + evaluator subagent + skills + progress.json），跳过 memory/spec 脚手架。
- **建议写入：** `bootstrap.sh` + `docs/03-quickstart.md` 补一节「已有项目接入」。
- **状态：** 待确认

**P2-5 · 类型：铁律澄清**
- **内容：** commit 粒度：per-feature commit 的**跨设备恢复**理由单机已失效，仅**抗压缩**承重（写状态文件即可恢复，逐 feature 打 git commit 是额外审计/回滚开销）；可放宽为 per-phase-boundary commit（保留状态文件写入 + JSON hook）。
- **建议写入：** `harness-rules.md` 铁律 2/3 理由重述（"跨设备恢复 + 抗压缩" → "抗压缩持久 + 审计轨迹"）。
- **状态：** 待确认

---

## [2026-07-12] Claude（自主开发架构设计 · 独立任务）— 来源：多 agent 自主 driver 架构设计 workflow w05dglv38（4 立场架构师 → 4 评委对抗打分 → 红队攻击领先方案）

**背景：** 用户问"能否在本框架下实现多 agent 自主推进 / 自主开发"。经 design workflow 评估：**可以，且状态机脊椎天然适合当自主骨架**。推荐架构 = S2 Heartbeat（`/loop` 心跳把 progress.json.status 当程序计数器，31/40 领先）+ S3/S4 安全机件嫁接。红队核心发现：所有架构把硬保证放在**状态迁移高度**，但危险动作（deploy/prod/花钱）是**阶段内部工具调用**，闸门分类器看不到——真正的强制在**工具层 deny-list**。

**S1（deterministic-first）架构师本轮 API stall 失败未参评**（其"临时 Workflow 当整个骨架"路线抗压缩最弱，损失不大）。

---

**A1 · 类型：新模板（设计规范草案，已落盘待确认）**
- **内容：** 已写 `harness/autonomous-mode.md`（提案草案）：Heartbeat 底盘 + 6+1 硬化机件 + 闸门三分类 + 建造顺序 + 前置纪律。描述的 `/autodrive`、deny-list、受限 generator subagent、Gate Arbiter、`autonomy-policy.json` **均待建**——机件没建成前不得开自主。定位 T2 按需加载，不进"每批次必读"。
- **建议写入：** 确认后 `harness/autonomous-mode.md` 由草案转正 + `harness-rules.md` 加一条指针（自主模式见该文）+ CHANGELOG。
- **状态：** 待确认（规范草案在 `harness/autonomous-mode.md`；机件初稿在 `harness/autonomous-mode/`：受限 generator subagent + spec-lock critic subagent + deny-list + policy schema + 校验 hook + Gate Arbiter〔build/plan 接线 + #6 去偏〕 + `/autodrive` skill 本体 + progress.json autonomy 字段模板 + verdict 工件 schema/校验）

**A2 · 类型：新坑（安全缺口，独立于自主模式亦值得修）🔴**
- **内容：** 框架只发布了 `evaluator.md` 受限工具集，**没有 generator/fix subagent 定义**。一旦用并行 §3 build subagent 或未来自主 fix wake，这些 subagent 继承 Bash + 全部 MCP 工具（含 aigc-gateway `generate_image`/`run_action` 等**花钱**工具）——可无人察觉地触发 deploy/`prisma migrate deploy`/prod 写入/花钱调用。硬闸门当前建在"状态迁移"高度，看不到"阶段内部工具调用"。
- **建议写入：** 新增受限 generator/fix subagent 定义（镜像 `templates/claude/agents/evaluator.md`）+ 一份可选 deny-list settings 模板（deploy/migrate/prod 主机名/prod 分支 push/aigc-gateway 花钱工具）；`orchestration-patterns.md` §3 并行 building 补一句"并行 subagent 应跑受限工具集"。
- **状态：** 待确认（修复初稿已落 `harness/autonomous-mode/agent-generator-restricted.md` + `settings.autodrive.json`；缺 `templates/claude/agents/generator.md` 转正 + §3 补句）

**A3 · 类型：铁律澄清（红队暴露的机制化盲区）**
- **内容：** 铁律 12（不污染 evaluator prompt）当前是**模型自律**，非机制化——长 wake 里累积的实现叙述可能漏进 evaluator prompt。应把 verify 的 evaluator prompt 做成**固定模板**，只插值 {批次, spec/feature 路径, L2-flag}，无自由文本字段，从 fresh 子上下文派发。
- **建议写入：** `templates/claude/skills/verify/SKILL.md`（prompt 组装确定化）+ `harness-rules.md` 铁律 12 补"机制化优先"。
- **状态：** 待确认

---

## [2026-07-12] Claude（进度看板机制 · 独立任务）— 来源：用户希望长时开发中有图形化看板观测研发进度

**背景：** 利用 Claude Artifact 做项目进度看板。关键约束：Artifact 严格 CSP **禁 fetch**——读不了磁盘 JSON，故看板是**快照**，由 harness 在阶段边界**重渲染 + 重发到同一 URL**（存 `progress.json.dashboard_url`）。数据零额外来源——全来自已落盘状态文件。样例已发布验证观感。

**D1 · 类型：新模板 + 新 skill（草案已落盘待确认）**
- **内容：** 已写 `harness/dashboard/`（草案，未安装）：`dashboard.template.html`（内联 CSS 自包含渲染骨架，tokenized + REPEAT 块）+ `skill-dashboard.md`（`/dashboard`：读 progress/features/backlog → 套模板 → 首发写回 `dashboard_url`/后续传 `url` 更新同一看板）。看板是**只读镜像非真相源**，只读状态+发布、不 flip status。
- **建议写入：** 转正后 `dashboard.template.html` → `templates/dashboard.template.html`；`skill-dashboard.md` → `templates/claude/skills/dashboard/SKILL.md`；`progress.json` 加 `dashboard_url` 字段（`progress.init.json` 初值 `null`）；`bootstrap.sh` 铺入；`harness-rules.md` §四阶段边界例程 + CLAUDE.md 启动流程各加一句"顺手刷看板"；CHANGELOG。
- **状态：** 待确认（样例 artifact 已发布验证观感）

**D2 · 类型：新规律（顺带红利）**
- **内容：** 看板默认私有、可从 artifact 页分享只读链接给非技术干系人；与自主模式天然搭——`/autodrive` 隔夜每唤醒的阶段边界顺手刷，早上打开即一夜进度；`autonomy_ledger` 可喂 token/成本 sparkline。
- **建议写入：** `harness/autonomous-mode.md` 补一句"每唤醒阶段边界顺手 /dashboard"；`harness/dashboard/skill-dashboard.md` 已含分享说明。
- **状态：** 待确认
