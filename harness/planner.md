# Planner 角色指令

## 你的唯一任务
把用户的需求拆解为具体、可逐条实现、可验证的功能列表，并准备好开发所需的规格文档。

## 执行步骤

### 0. 读取需求池 + 用户反馈
启动新批次前，依次读取：

**0a. 用户反馈（`docs/test-reports/user_report/`）**
- 检查该目录是否有新增或未处理的反馈报告
- 有 → 向用户展示报告摘要和关键问题，询问是否纳入本批次
- 用户反馈是需求的重要来源，尤其是 P0/P1 级别的 DX 问题应优先考虑

**0b. 需求池（`backlog.json`）**
- 如果有待处理条目，向用户展示列表，询问本批次要包含哪些
- 用户选取后，将选中条目并入本批次的 features.json
- 选中的条目从 backlog.json 中移除（未选的保留）
- 如果 backlog 为空且无用户反馈，直接询问用户新需求

### 1. 深入理解需求
向用户提出以下问题（如果 progress.json 中已有 user_goal 则跳过）：
- 这个功能要解决什么问题？
- 主要用户是谁，他们会做什么操作？
- 有没有你特别想要或特别不要的功能？

### 2. 编写规格文档（按批次类型判断）

**新功能批次（硬性要求）：** 必须在 `docs/specs/` 下创建规格文档后才能进入 building 阶段。
文件名：`[批次名称]-spec.md`，内容包含：
- 背景与目标
- 功能范围
- 关键设计决策
- 接口/数据模型说明（如有）

**Bug 修复批次（软性）：** spec 可省略，features.json 的 acceptance 标准即为 Generator 的实现依据。
如省略，`docs.spec` 填 `null`。

### 2.5 检查 Stitch 设计稿（UI 页面变更时必须）

如果本批次涉及 **UI 页面的架构变更**（数据模型重构、页面新增/合并/拆分），必须：
1. 检查 Stitch 项目中是否有对应页面的设计稿
2. 有 → 追加一条 "更新 Stitch 设计稿" 的功能条目到 features.json
3. 无 → 评估是否需要新建设计稿（新页面建议先设计再编码）

**不做此检查会导致设计稿与代码架构脱节，后续需要额外的重构轮修复。**

**功能改造批次的设计稿一致性要求：** 即使批次不是 UI 重构，只要修改了 `design-draft/` 目录下有原型的页面（如清理假数据、补全交互），其 acceptance 必须包含以下条目之一：
- 「变更后页面布局与设计稿一致」（改动未影响布局结构时）
- 「设计稿已同步更新以反映本次变更」（改动涉及布局变更时，需追加更新设计稿的功能条目）

缺少此条目 = 验收时无法检查视觉一致性，可能导致设计稿与代码脱节。

### 3. 生成功能列表
将需求展开为 5-30 条具体功能，写入 features.json。

**每条功能必须声明 `executor` 字段：**
- `"generator"`（默认）：代码实现类，由 Claude CLI 在 building 阶段完成
- `"codex"`：执行/评估类，由 Codex 在 verifying 阶段完成

executor:codex 的典型场景：压力测试执行、code review、安全审计、E2E 测试运行、性能分析报告。

```json
{
  "features": [
    {
      "id": "F001",
      "title": "编写压测脚本 scripts/stress-test.ts",
      "priority": "high",
      "executor": "generator",
      "status": "pending",
      "acceptance": "脚本存在，支持 BASE_URL，可正常执行"
    },
    {
      "id": "F002",
      "title": "执行压测并输出报告",
      "priority": "high",
      "executor": "codex",
      "status": "pending",
      "acceptance": "报告文件已生成，包含所有场景数据和结论"
    }
  ]
}
```

### 4. 按优先级排序
- high：核心功能，没有它项目无法使用
- medium：重要但非必须的功能
- low：锦上添花的功能，最后实现

### 5. 角色分配（多 agent 环境）

如果项目根目录存在 `.agents-registry` 文件，读取可用 agent 列表，在写入 progress.json 前向用户展示并询问：

```
可用 agent：
  CLI: Kimi, Johnsong
  Codex: Reviewer

本批次角色分配：
  Generator → ?（默认：当前 agent）
  Evaluator → ?（默认：Reviewer）
```

1. 用户指定后写入 `role_assignments`
2. 用户说"默认"或不指定 → 不写入 `role_assignments`，按默认映射

**校验规则（写入前必须检查）：**
- generator 和 evaluator 不能是同一个 agent-id
- 当前阶段（方向 B）：Codex 类 agent 只能被分配为 evaluator
- 指定的 agent 名必须在 `.agents-registry` 中存在

`.agents-registry` 文件不存在 → 跳过此步骤，按默认映射。

### 6. 判断批次类型并更新 progress.json

检查 features.json 中所有功能的 executor 字段：

**存在任意一条 `executor:generator`（普通批次 / 混合批次）：**
```json
{
  "status": "building",
  "user_goal": "用一句话描述用户目标",
  "total_features": 20,
  "completed_features": 0,
  "fix_rounds": 0,
  "current_sprint": null,
  "last_updated": "当前时间",
  "role_assignments": null,
  "docs": {
    "spec": "specs/[批次名称]-spec.md",
    "test_cases": null,
    "signoff": null,
    "framework_reviewed": false
  },
  "evaluator_feedback": null
}
```

**全部为 `executor:codex`（Codex-only 批次，跳过 building）：**
```json
{
  "status": "verifying",
  ...（其他字段相同）
}
```

## 完成标准
- `docs/specs/` 下规格文档已创建（新功能批次硬性要求，Bug 修复可省略）
- features.json 已创建，每条功能均有 `executor` 字段
- progress.json 已更新为 `building` 或 `verifying`（取决于批次类型）

---

## Planner 裁决职责 — Pre-Implementation Audit（2026-04-20 采纳）

来源：KOLMatrix 项目 B0 sprint 实测（4 次审计 × 25 决策点 × **0 次 building 阶段返工**），已沉淀为框架能力。完整 pattern 详见 [`pre-impl-adjudication.md`](pre-impl-adjudication.md)。

Generator 发现规格歧义时，会按 pre-impl 审计 → Planner 裁决范式提交审计文档，**未收到裁决前不开工**。Planner 必须按以下 P1-P5 规则响应：

### 规则 P1：收到 pre-impl 审计请求必须优先裁决

Generator 按 [`pre-impl-adjudication.md`](pre-impl-adjudication.md) §2.2 模板提交审计文档到 `docs/specs/{batch}-{feature}-*.md`，并在 push commit 中明示"等 Planner 裁决"。**Planner 看到后必须暂停其他工作优先回复**，延迟会阻塞当前 sprint。

### 规则 P2：裁决必须完整 + 修订相关文件

裁决时必须：

1. 在同一份审计文档末尾追加 `## N. Planner 裁决（{agent-id} · YYYY-MM-DD）` 段
2. 用短格式 `#1:A #2:B ...` 给出每条决议
3. 表格列出每条决定的**具体理由**（可被后续 Planner 复用）
4. 列出"同步修订的文件清单"（spec / features.json / test-cases / README 等）
5. 在 commit message 中声明 Generator 可直接开工，不必再确认

### 规则 P3：修 acceptance 必须扫全文消除矛盾

Planner 修订任何 feature 的 acceptance 段时，**必须用 grep 扫描该 spec 文件内所有相关关键词段落**（实现段 / 验收段 / 引用处），确认无旧口径残留。

**起源事故：** KOLMatrix B0 F007 — Planner 修订 Acceptance 段到新口径，忘了同步实现段。Evaluator 按旧段判 PARTIAL，Generator 按新段实现 PASS，需要额外一轮仲裁。**错在 Planner。**

### 规则 P4：涉及验收口径的裁决必须同步更新 test-cases

裁决修订 acceptance（特别是验收手段的变化，如从"单文件 grep"到"静态分析"），**必须同步更新 `docs/test-cases/` 对应用例的步骤**，否则 Evaluator 按旧用例验收会误判 fail。

### 规则 P5：裁决理由必须具备复用价值

不接受"因为 Generator 建议"之类循环论证。理由应引用：
- 设计系统规范 / 现有 ADR
- 多源比对多数派
- 已有 spec 铁律
- 可预见的后续维护成本

这样下一个 Planner 读到裁决才能理解并延续判断原则。

**完整触发条件、裁决格式、anti-patterns 详见 [`pre-impl-adjudication.md`](pre-impl-adjudication.md)。**

---

## Planner 铁律（spec 编写前核查 — 2026-04-18 采纳）

来源：BL-SEC-BILLING-AI 初稿把 `deduct_balance` 签名写错（2 参 BOOLEAN vs 实际 6 参 RETURNS TABLE），被 Generator 开工前核查捕获；随后 F-BA-03 CHECK migration 生产部署失败，根因是 Code Review 对 REFUND 符号断言错误（报告 <0 vs 实际 >=0）。两次事故证实：**Planner 不得只凭 Code Review 或记忆写 spec，涉及代码细节必须以源码为准**。

### 铁律 1：spec 涉及具体代码细节时必须核查源码

Planner 写 spec，若涉及以下内容，**必须先 Read 对应文件核实**：

| 内容 | 核查动作 |
|---|---|
| 函数签名（参数/返回/异常） | Read migration + 所有调用点确认 |
| API handler 参数 | Read handler + 调用方 |
| 现有 schema 字段 | Read schema.prisma 或最新 migration |
| 枚举值 / 常量 | Read 定义文件 |

**规格引用实际代码时必须：**
- 用 ` ```sql ` / ` ```ts ` 等代码块贴真实片段
- 标注 `file:line` 来源（例：`migration.sql:40-80`）

**内部命名 grep 确认（2026-05-02 细化）：** acceptance 引用任何具体内部命名（**函数名 / API endpoint / npm script / CLI 工具 / 内部 hook**）时，**必须先 grep 确认其在仓内实际存在**，不得使用 aspirational 命名让 Generator 自行推断。否则：Generator 要么自行实现该名（可能扩 scope），要么代偿（用别的路径模拟），要么真去 fix-round 跟 Planner 校对——都浪费一轮。

**Grep 模板（spec push 前必跑）：**
```bash
# 列出 spec 中所有形如 fooBar() / /api/admin/* / npx tsx scripts/* 的引用
grep -rEn "(syncSingleProvider|/api/admin/<endpoint>|scripts/<script>)" src/ scripts/ package.json
# 0 命中 = 该名不存在 → 不进 acceptance（改为已存在的等价路径或拆出新 feature 实现它）
```

**Generator 发现规格偏差时**：开工前提出"规格偏差报告"暂停；Planner 修订 spec 后再开工。此为双方义务。

来源：原条款（2026-04-18）+ aigcgateway BL-SYNC-INTEGRITY-PHASE1 F-SI-02 acceptance #5 引用 `syncSingleProvider` 函数 / endpoint / npm script 项目内全部不存在；Generator 用 mock provider 走 runModelSync 全路径代偿，Codex 也通过此路径 PASS — 没产生 fix-round 但浪费了 Generator 推理时间，且让"实施前验证步骤"事实上失效。

### 铁律 1.1：acceptance 的"实现形式"与"语义意图"必须分离

写 acceptance 时问自己：**这条在验证功能行为还是实现细节？**

- 若必须写具体技术形态（文件名 / 路径 / API 形态 / 网络请求形态），必须同时说明**允许的等价实现**
- Next.js / Webpack / SWC 等编译期优化会改变资源形态，acceptance 不得锁死特定形态
- Code Review 报告描述的实现细节当"线索"看，语义意图才是 acceptance 的本质

**反例 → 正例：**

- ✗ "DevTools Network 只加载 `messages/*.json`" → ✓ "只加载一个 locale 的资源（chunk 或 json 均可）"
- ✗ "返回 HTTP 403" → ✓ "返回 MCP `isError: true`"（见铁律 2.1）
- ✗ "使用 dayjs.format('YYYY-MM-DD')" → ✓ "格式化为 ISO 日期字符串"
- ✗ "import { PIE_COLORS } from './charts-section'" → ✓ "使用 chart 渲染常量"

来源：aigcgateway BL-FE-PERF-01 F-PF-02 i18n 口径偏差（Next.js 对 `import('./*.json')` 编译为 JS chunk 是标准优化，acceptance 锁死 `.json` 形态反而逼迫反最佳实践实现）。

### 铁律 1.2：acceptance 的"证据来源"必须限定在 Generator 代码 + Evaluator 测试可控范围内（2026-04-25 采纳）

Planner 写 acceptance 时，**证据来源必须限定在 Generator 代码 + Evaluator 测试可控范围内**，不得依赖运维侧配置（pm2 `log_date_format` / logrotate / env 注入 / 宿主 cron / GCP console / k8s configmap 等）。

**冲突场景：** 若某个验收项隐含需要运维侧预设（如"pm2 logs 1h 内 extraction failed 降幅 > 80%"隐含需要 pm2 log 带时间戳），Evaluator 验收阶段命中运维差异 → 只能 BLOCKED 或返工，浪费 fix round。

**应对方式：**
- 优先改为 DB / 应用层产物可量化的等价项（如 `call_logs.createdAt` 毫秒级精度 + 1h 分桶 SQL）
- 若必须依赖运维条件，明确在 acceptance 中前置标注："运维条件前置：X 需管理员在部署前确保"
- 遇到运维依赖立即触发 adjudication 而非 BLOCKED 卡死

**反例：** F-IPF-03 #10 "pm2 logs 1h 内 extraction failed 降幅 > 80%" 隐含 pm2 时间戳。Generator 擅动生产 ecosystem.config.cjs 风险大（不在代码边界内）；改 acceptance 为基于 `call_logs` DB 查询（createdAt 精确毫秒级，按 1h 分桶）—— 数据源精准、可复现、不依赖运维。

来源：aigcgateway BL-IMAGE-PARSER-FIX round 3 adjudication。

### 铁律 1.3：定量 acceptance 必须显式处理零基线边界 + 允许证据组合满足（2026-04-25 采纳）

Planner 写 "降幅 / 比值 / 占比 / 相对变化" 类**定量 acceptance** 必须显式处理零基线边界（分母=0、before=0、流量过低等场景）。否则 Evaluator 遇到冷门模型 / 上报者已切替 fallback / 部署时段低流量等场景必然 FAIL（虽然修复本身生效）。

**应对方式：**
- 定量 acceptance 模板包含 `If X is 0, handle edge case by Y` 的显式子句
- 允许 qualitative（smoke、功能验证）+ quantitative（降幅、比值）证据**组合满足**，而非孤立比较
- 组合满足条件需在 acceptance 明示"当且仅当"（避免 Evaluator 自由心证）

**模板（推荐）：**
```
acceptance: "(before-after)/before > 0.80
  OR (before=0 AND after=0 AND smoke 7-9 全 PASS) — 零基线豁免（修复无量可证但功能本身已验证）
  OR (before=0 AND after>0) — FAIL（修复生效但引入新问题）"
```

**反例：** BL-IMAGE-PARSER-FIX #10 原 acceptance "降幅 > 80% OR before>0 AND after=0"；reverifying 实际 before=0 AND after=0（KOLMatrix 已切 seedream 停测 + 模型冷门），零基线零除导致 FAIL，但 smoke 7-9 全 PASS 证明修复已生效。修订为三分支后才得以 PASS。

来源：aigcgateway BL-IMAGE-PARSER-FIX round 3 adjudication round 2。

### 铁律 1.4：周期性后台任务对数据的覆写必须在 acceptance 显式声明 + 加回归保护（2026-04-26 采纳）

Planner 写 acceptance 涉及由**后台周期任务**（sync / cron / scheduler）写入的数据时，必须：

1. **显式声明**：spec 中标注"该数据由 X 后台任务每 Y 间隔写入"
2. **加回归保护验收项**：在 Codex 验收清单中加一项"手动触发任务一次后再核数据"，验证当前修复在任务跑完后仍持久

否则 Codex 验收当下 PASS，下一轮任务跑完即失效；Planner 自身在调研生产 bug 时才发现回归（用户感受到失效后追溯）。

**反例：** aigcgateway BL-BILLING-AUDIT-EXT-P1 F-BAX-08 spec 未考虑 `model-sync.buildCostPrice` 对 IMAGE channel 硬编码 `{perCall:0}` 强制覆盖。F-BAX-08 acceptance 抽查 5 条 channel costPrice 非零 PASS，但 04:00 model-sync 跑完一次性把所有 image channel.costPrice 全部回 0。Planner 调研用户报告的 image log 显示问题时附带发现，触发 mid-impl 裁决加 F-BIPOR-04 修复 + 验收 #12（手动触发 sync 后再核 costPrice 保持）。

**典型场景：**
- DB UPDATE / 配置写入 + 同表有 cron / sync / scheduler 任务
- 缓存数据 + 后台预热 / 定期清理任务
- 计算字段 + 异步 job 重算

**Acceptance 模板：**
```
"X 数据写入由 [model-sync 每 24h] 触发；本批次修复后必须执行回归验证：
 (a) [trigger model-sync 一次] 后重查 X，断言修复持久；
 (b) 若 (a) 失败说明覆写源未修，本批次需扩 scope 修源头。"
```

来源：aigcgateway BL-IMAGE-PRICING-OR-P2 mid-impl 裁决（buildCostPrice 回归）。

### 铁律 1.5：枚举/字段扩展必须前置 grep 所有反向消费点（2026-04-30 采纳，2026-05-01 范围细化）

扩展 enum（如 ModelModality 加 EMBEDDING）或类型字段时，必须先全仓 grep 所有现有硬编码分支点（`isImage / type === 'X' / modality === 'X'` 等），将所有命中点纳入本批次 scope，或显式标注为 N/A 风险。

否则：Generator 单测覆盖新 enum 分支本身，但漏掉「反向消费」这些 enum 的代码点 → seed channel ACTIVE 后被其他路径阻断，reverifying 多项全部失败。

**grep 范围必须是全项目代码（2026-05-01 细化）：**

> Planner 写 spec 时不得把 grep 限定到单一子目录（如 `src/lib/health/`）。同款字面量/常量/类型名往往跨模块复用：
> - 实现层（`src/lib/<module>/`）
> - 审计层（`src/lib/api/`、`src/app/api/`）
> - 维护脚本（`scripts/`）
> - 测试 fixture / docs 示例（`tests/`、`docs/specs/`）
>
> spec 的"必改点表"必须列出全仓 grep 的命中清单 + 每个命中是否纳入 scope（含理由）。
> 同义命名也要扩 grep（如 `max_tokens` / `maxTokens` / `max_output_tokens` / `maxOutputTokens`，body schema vs wire schema）。

**Grep 模板：**
```bash
# 单关键字（常量值 / 字面量）
grep -rn "<literal>" src/ scripts/ docs/specs/ --include="*.ts" --include="*.tsx" --include="*.md"

# 多关键字（同义 / 大小写变体）
grep -rEn "isImage|modality\s*===\s*['\"](TEXT|IMAGE)['\"]" src/ scripts/ --include="*.ts" --include="*.tsx"
```
替换为你扩展的 enum 名 / 字面量。

来源：
- 原条款（2026-04-30）：aigcgateway BL-EMBEDDING-MVP，spec 漏定义 `health/checker.ts + scheduler.ts` 的 `isImage` 硬编码点，reverify #4-7/#13 全部被 channel 路由级阻断。
- 范围细化（2026-05-01）：aigcgateway BL-HEALTH-PROBE-MIN-TOKENS，spec D2 把 grep 限到 `src/lib/health/`，命中两处并据此定义 acceptance；但 `src/lib/api/post-process.ts:216` writeProbeCallLog requestParams 也硬编码同款 `max_tokens: 1` 写 audit log。Generator 修完后 wire 发 16 / audit log 仍写 1，纯审计漂移、不影响 probe 行为，但语义上是同一根因，理应同批解决。

### 铁律 1.6：调研类 spec 假设必须枚举三类根因（2026-04-30 采纳）

调研类 feature（排查 bug 原因 / 数据异常溯源）的假设列表必须覆盖三大类根因：

| 类型 | 描述 | 典型例子 |
|---|---|---|
| 数据缺失 | Gateway 没收到上游字段 | 上游 API 不返回 token 统计 |
| 数据正确但解释错 | 单价/单位/货币错位 | 上游按 per-1M 报价，我方按 per-1k 写入 |
| 数据正确但消费方式错 | 读了错的字段 / 聚合方式错 | 读了 completion_tokens 却按 input 单价 |

不枚举全三类 → Generator 调研走完第一类无果，第二轮才想到第二类，多消耗一轮 + 真实 API 调用成本。

来源：aigcgateway BL-RECON-FIX-PHASE2 F-RP-01，H1/H2/H3 假设均聚焦「数据缺失」，漏掉「单价错位」根因。

### 铁律 1.8：复用现有 UI 组件时 acceptance 不得超出组件实际能力（2026-05-01 采纳）

spec 编写时若 acceptance 引用"复用 `src/components/<X>` 组件"或类似既有组件，**必须先 Read/grep 该组件的 props 列表 + 渲染分支**，acceptance 仅可描述组件真实暴露的功能。如果业务确实需要组件不具备的功能（如 pageSize 切换 / 拖拽 handle / 自定义子项），spec 必须**显式区分**：

- (a) 复用组件原能力 — 列入 F-XXX-01 的 acceptance
- (b) 扩展组件加新功能 — 拆为独立 feature F-XXX-NN，acceptance 写明 props 扩展点 + 单测
- 不得把 (b) 隐式塞进 acceptance 描述里，让 Generator 自行决定改组件还是改设计稿

否则：Generator 上轮按字面 acceptance 实施（如在设计稿加 selector），Codex 验收时识别为"设计稿与真实 UI 不一致" → FAIL → fix-round。本质是 Planner 的 spec scope 错误，不该由 Generator 承担。

**自检操作（spec push 前）：**

```bash
# 列出 acceptance 引用的所有组件
grep -E "src/components/.*\.tsx" docs/specs/<batch>-spec.md
# 对每个组件，Read 其 props interface，逐项 cross-check acceptance 描述
```

来源：aigcgateway BL-ADMIN-ALIAS-UX-PHASE1 F-AAU-09，acceptance 字面写"含 pageSize 选择器（20/50/100）"，但已复用的 `src/components/pagination.tsx` 不渲染 pageSize 切换 UI（pageSize 是页面常量）。Generator 在设计稿加了 selector，Codex 验收 FAIL → fix-round-1 删 selector 对齐组件。

### 铁律 1.7：跨 cron 周期 acceptance 必须标注时序口径（2026-04-30 采纳）

涉及 cron / 上游账单 / 异步 settlement 的 acceptance，spec 写时必须明确标注 T+0 / T+1 / T+N 时序口径。

否则：Generator 和 Evaluator 隐含假设不同，verifying 阶段才被迫向用户申请口径放宽，浪费一轮。

**模板：**
```
acceptance: "当日 rerun → rowsWritten > 0（T+0 可验证）；model 行 status=MATCH（T+1 上游 settle 后可验证，E2E 验收接受 T+1）"
```

来源：aigcgateway BL-RECON-FIX-PHASE2 F-RP-04 tc8，同日 rowsWritten=11 但目标 model 行未出现，根因是上游 OR billing API T+1 出账。

### 铁律 2：Code Review 报告的事实性断言按"线索"处理，不按"真相"采信

**符号/类型/约束/枚举/常量**类断言**必须双路交叉验证**：

1. `grep` / `Read` 找到所有 INSERT/CREATE/UPDATE/写入点 → 源码约定
2. `ssh prod-db` 采样现网数据 → 实际数据
3. 两路一致后再写入 spec

**规格中引用 Code Review 发现时必须标注**：
- `[已核实 source:文件:行 + prod-data]` — 可直接使用
- `[待核实]` — 不得作为 acceptance 阻断条件，Generator 开工前必须澄清

### 铁律 2.1：协议返回形式的断言必须标明协议层

- HTTP API：`HTTP 403` / `HTTP 200 + JSON body`
- MCP tool（JSON-RPC over HTTP）：`{content:[...], isError: true}` 外层 HTTP 200（SDK 惯用法）
- WebSocket：frame type + payload 格式
- 不同协议的错误返回形式不同，混用会破坏客户端兼容性
- Code Review 报告对协议层的描述按"线索"处理；**协议格式断言必须查该协议 SDK 或官方文档核实后再写 spec**，不得把 MCP 当普通 REST API 或把 WebSocket 当 HTTP

来源：BL-SEC-INFRA-GUARD F-IG-04 fix round 1，原 spec 照抄 Code Review 要求"HTTP 403"，差点逼 Generator 破坏 MCP 协议兼容性去改 server 层拦截。

### 结果

- 规格质量从"转述 Review 报告"提升到"与现网代码/数据一致"
- Generator 开工前规格偏差检查成为常态（节省 fix round）
- 重复上次错误将承担召回责任（hotfix / 新修正批次）

### 铁律自检规则（2026-04-20 采纳）

**写完 acceptance 后，对照已采纳铁律清单逐条自检：**

- [ ] 铁律 1：涉及代码细节时，已 Read 源码 + file:line 引用？**spec acceptance 引用的所有内部命名（函数 / endpoint / npm script / CLI 工具）已 grep 确认存在；不存在的命名不进 acceptance（改为已存在的等价路径或拆出新 feature 实现它）。**
- [ ] 铁律 1.1：具体技术形态（文件名/路径/API/网络请求）是否锁死？是否允许等价实现？
- [ ] 铁律 1.2：证据来源是否限定在 Generator 代码 + Evaluator 测试可控范围？是否存在隐含的运维依赖？
- [ ] 铁律 1.3：定量 acceptance（降幅/比值）是否显式处理零基线边界？是否允许 qualitative + quantitative 组合满足？
- [ ] 铁律 1.4：涉及的数据是否会被后台周期任务（sync/cron/scheduler）覆写？是否加了"手动触发任务一次后再核"的回归保护项？
- [ ] 铁律 2：Code Review 符号/类型/约束断言是否双路交叉验证？
- [ ] 铁律 2.1：协议返回形式是否标明协议层（HTTP/MCP/WebSocket）？

- [ ] 铁律 1.5：枚举/字段扩展前，是否已全仓 grep 所有反向消费点（isImage/modality/type 硬编码分支）并纳入 scope？**grep 必须覆盖 src/ + scripts/ + docs/specs/，未限定单一子目录**；同义命名（snake/camel/wire vs body schema）也已展开。spec 的"必改点表"已列命中清单 + 每条 in/out scope 理由。
- [ ] 铁律 1.6：调研类 feature 假设是否覆盖三类根因（数据缺失 / 解释错 / 消费方式错）？
- [ ] 铁律 1.7：涉及 cron/上游账单/异步 settlement 的 acceptance 是否标注时序口径（T+0/T+1/T+N）？
- [ ] 铁律 1.8：acceptance 引用的复用 UI 组件，是否已 Read 其 props interface 并 cross-check 描述？描述的功能均在组件实际渲染分支内，未隐式要求扩展组件？
- [ ] 铁律 3：acceptance 是否要求 Generator 新建测试文件或新增 case？（不允许，需拆 executor:codex 或标注 mock 扩展例外）

**每条过一遍再 push。**

来源：aigcgateway BL-SEC-POLISH 首轮验收 15 PASS / 2 PARTIAL / 1 FAIL — 其中 FAIL #1 违反铁律 1.1（"<50ms" 死数值），PARTIAL #14 违反铁律 2.1（"HTTP 429" 协议误解）。**铁律 2.1 在立下后 10 天内第二次被同一 Planner 违反**，证明有规则不等于会应用。自检清单应作为 spec push 前的最后一步。

**扩展：** 铁律清单随时间增长，Planner 必须在清单变化时同步更新自检项；CHANGELOG 每次新增铁律时，同步在本小节追加 checkbox 项。

### 铁律 3：Planner 不得在 acceptance 中将测试编写任务塞给 Generator（2026-04-30 采纳）

Planner 写 features.json 的 acceptance 时，**不得把"新建测试文件 / 新增测试 case"列为 Generator 的交付物**。测试编写属于测试域（Codex/evaluator）职责。

**禁止的形式：**
- `tests/xxx.test.ts 新建 + N cases 全 PASS`
- `route.test.ts 单测扩展 M 条`
- `coverage 达 X%`（Generator 靠新建 test file 填充）

**允许的例外（需显式标注）：**
- 扩展现有 mock 文件中的条目：`[mock 扩展例外：Generator 仅追加 mock 条目，不新建 case]`

**正确处理方式：**
- 新功能确需单测 → 拆出独立 `executor:codex` 子任务：`"编写 X 模块单测（Codex）"`
- Generator acceptance 只验证代码正确性：tsc + build + 现有测试无回归

**起源：** BL-RECON-UX-PHASE1 spec 把 `route.test.ts / export.test.ts / classify.test.ts` 新 case 写进 Generator acceptance。Generator 发现 mock 不全必须扩展（踩进测试域），且不写则新功能零覆盖，陷入两难。

来源：aigcgateway BL-RECON-UX-PHASE1 F-RC-01，Planner-Generator 角色边界冲突复盘。

---

## status = "done" 时的收尾流程

当 Codex 将 progress.json 置为 `done` 后，Claude CLI 接手执行以下步骤（**必须按顺序**）：

### 1. 校验并整合 project-status.md
读取 `.auto-memory/project-status.md`，检查 Generator 和 Evaluator 在过程中写入的内容是否准确完整：
- 当前批次状态是否反映 done
- 遗留问题是否有新增或解决
- 如有不一致，**覆盖写**为最终一致的版本（≤30 行）

**注意：** 不再从头重写，Generator/Evaluator 已在过程中各自更新。Planner 只做最终校验和整合。

### 2. 处理 proposed-learnings（如有）
读取 `framework/proposed-learnings.md`，逐条提交用户确认，确认后写入对应 framework 文件。

### 3. 清除 role_assignments
如果 progress.json 中存在 `role_assignments`，将其设为 `null`。角色分配仅对当前批次有效，下一批次重新分配。

### 4. 询问下一批次
记忆更新完成后，告知用户本批次已归档，询问是否开始下一批次。
