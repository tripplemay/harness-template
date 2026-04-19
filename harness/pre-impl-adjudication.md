# Pre-Implementation Audit → Planner Adjudication Pattern

> **沉淀来源：** KOLMatrix 项目 B0 sprint 实测（4 次审计 × 25 决策点 × **0 building 阶段返工**）
> **适用场景：** 任何涉及规格歧义、跨源漂移、组件 API 设计、数据模型 gap 的 Generator 任务
> **版本：** v0.9.2（2026-04-20 回流到 harness-template）

---

## 1. 问题定义

Generator 按 spec 直接开工时，常见 3 类代价高昂的错误：

1. **规格内部矛盾** — spec 头部说 A，acceptance 段说 B（Planner 修订某段忘同步其他段）
2. **跨参考源漂移** — 设计稿 / 原型 HTML / spec / ADR 四处描述同一事物但细节不一致
3. **Generator 凭本能填空** — spec 有灰色地带，Generator 自己解释后开工，Reviewer 按不同解释判 fail

**传统流程的成本：** 发现矛盾时已经写了大量代码，需要回退重写（`building → verifying → fixing` 循环）。

## 2. Pattern 核心

**Generator 在动代码之前，主动提交 pre-impl 审计文档，列出发现的所有歧义 + 跨源漂移 + 候选方案，请 Planner 裁决。Planner 裁决后才开工。**

### 2.1 触发条件（Generator 必须提交审计的场景）

| 场景 | 典型例子 |
|---|---|
| 规格文字含糊 | "必须使用 N 个组件" — 直接 import 还是渲染树包含？|
| 多份参考源冲突 | 设计稿 A 版 vs B 版；原型 HTML vs spec 文字描述 |
| 组件 API 需要决策 | 某 prop 是可选还是必带？是 variant 切换还是拆两个组件？|
| 跨页 / 跨批次变体 | 同功能多种布局 / 同组件多种用法 |
| 非设计系统 token | 品牌色 / 特殊间距是否需要扩展 theme？|
| 发现原型 / 参考源 bug | 是回修源，还是只登记"已知漂移"？|
| 数据模型 gap | 现有 schema 缺某字段，是加 migration 还是动态计算？|

**不触发审计的场景：** spec 清晰无歧义的简单 feature（加 button、改文案、单字段 CRUD 等）—— 直接开工即可。"**复杂度匹配风险**"是核心原则。

### 2.2 审计文档模板（Generator 写）

**存放位置：** `docs/specs/{batch}-{feature}-{topic}.md`（例：`B0-app-shell-canonical-review.md`、`F-AUTH-props-api-audit.md`）

```markdown
# {Batch} {Feature} · {Topic} 规划稿 / 审计请求

> **发起者：** {agent-id} (Generator)
> **日期：** YYYY-MM-DD
> **触发：** {feature} 开工前审计，按 pre-impl 审计 → Planner 裁决工作范式
> **状态：** 等待 Planner 明确回复，**未收到前不开工**

## 1. 背景 & 目标
{简述该 feature 做什么，关键约束有哪些}

## 2. {跨源比对 / Props API 草案 / 数据 gap 核对 / ...} 审计

{表格或列表列出发现的事实差异。例如：多份参考源并排对比表、schema 现状 vs 需求对比}

## 3. N 条决议请求

| # | 决议点 | A 方案 | B 方案 | 多数派参考 | 建议 |
|---|---|---|---|---|---|
| 1 | ... | ... | ... | ... | **A** |
| 2 | ... | ... | ... | ... | **B**（理由…） |

### 裁决格式要求
请 Planner 就每条给出明确的 **A / B / C** 选择 + 简短理由（偏离建议时）。
用 `#1:A #2:B #3:A…` 短格式回复即可。

## 4. 原型 bug / 已知漂移追加（如有）

{扫描发现的参考源 bug，是否回修或仅登记}

## 5. 开工条件

收到 Planner 对 {N 条决议 + 其他确认} 的明确回复后，Generator 将：
1. 按决议实现 {具体动作}
2. 走 {闸门列表}
3. Push 到 main

**未收到明确回复前不开工。**

## 6. 估算开工时长

| 环节 | 预估 |
|---|---|
| ... | ... |
| **总计** | **~X h** |

## 7. 相关文档
- {spec 路径}
- {依赖 / 参考源路径}
```

### 2.3 Planner 裁决回复格式

在同一份审计文档末尾追加 `## N. Planner 裁决（{agent-id} · YYYY-MM-DD）`，含：

1. **短格式决议**（一行列全）：`#1:A #2:B #3:A #4:A…`
2. **逐条理由**（表格）：

   | # | 决定 | 理由（必须可复用）|
   |---|---|---|
   | 1 | A | 多数派 + 设计系统一致 |

3. **同步文档更新清单**：Planner 同时修订 spec / features.json / test-cases / 相关文件，并列出修订文件 + 段落
4. **额外叮嘱**（非阻塞）：实现时容易踩的坑 / 命名建议 / 未来 gotchas

**裁决推送 main 后，Generator 可立即开工，无需再确认。**

### 2.4 与状态机配合

审计期间状态机不移位（保持 `building`），但 Generator **事实上处于"等待裁决"非工作态**。

完整流程：
```
building 开始
    ↓
Generator 开工审计（生成 pre-impl 审计文档）
    ↓ push main（状态仍 building）
Planner 看到审计请求，作裁决（同文档末尾追加 + 修 spec + 修 features.json）
    ↓ push main
Generator git pull 看到裁决 → 真正开始实现
    ↓
走闸门 → 更新 features.json status=completed → push
```

---

## 3. 决策类型分类（常见 4 种）

按 KOLMatrix B0 sprint 经验，决议点通常落到这 4 类：

### 3.1 Canonical 选择（多源漂移）
**特征：** 多份参考源说法不同，选一个作为"真相"。
**示例：** 同一 UI 组件的 HTML tag 或 padding 值在 7 份参考稿里不一致。
**处理：** Planner 通常采纳"多数派 + 设计系统一致 + 语义合理"的方案。少数派登记为"已知漂移"，不回修源。

### 3.2 Props / API 决策
**特征：** 组件 / 接口暴露多少可变性，拆分粒度如何。
**处理：** Planner 通常倾向"最小 surface + 渐进扩展"（可选 prop / variant 切换，而非一开始就拆多组件）。

### 3.3 Spec 字面冲突（Planner 自锅）
**特征：** 同一 spec 文件内不同段落自相矛盾，多半是 Planner 修订某段忘同步其他段。
**处理：** Planner **必须承认责任**、修订一致、不让 Generator 或 Evaluator 背锅。之后必须按 §6.1 铁律 grep 扫全文。

### 3.4 范围与依赖决策
**特征：** 本 feature 是否包含某些前置动作（如同批补一个 migration、同 PR 更新文档）。
**处理：** 按"自然叙事 vs git 历史清晰度"权衡，通常前者胜（一次 PR 包含完整故事）。

---

## 4. Anti-patterns（不得出现）

### 4.1 Planner 凭印象裁决
**错：** Planner 没 Read 代码就下结论。
**对：** 按 `planner.md §Planner 铁律 1` "涉及代码细节必须核查源码"，Read 现状再判。

### 4.2 Generator 审计过度笼统
**错：** "F005 有歧义，请 Planner 确认" — 没列具体分歧点。
**对：** 每个歧义点 → A/B 两个明确方案 + 自己建议 + 理由。

### 4.3 Planner 修 acceptance 不扫 spec 全文
**错：** 只改 acceptance 段，忘了前面实现段描述。
**对：** 用 grep 扫 spec 文件内所有相关关键词段落（实现段 / 验收段 / 引用处），确认无旧口径残留。

### 4.4 审计被当成"正常步骤"漫反射
**错：** 每个 feature 都写一份漫长 pre-impl 审计，即使 spec 清晰无歧义。
**对：** 只在 §2.1 触发条件命中时写。简单 feature 直接开工即可。

### 4.5 Evaluator 按旧 spec 验收
**错：** Planner 修订 spec 后，Evaluator 仍引用旧版判 fail。
**对：** Planner 推送新版后，在 session_notes 或 test-cases 更新通知 Evaluator，或通过 P4 同步更新 test-cases。

---

## 5. 统计口径

评估 pattern 有效性的关键指标：

| 指标 | 含义 | 目标值 |
|---|---|---|
| **审计 → 裁决延迟** | 从 pre-impl push 到 Planner 裁决 push 的时间 | < 2 小时（同步会话）/ < 半天（异步） |
| **审计命中率** | 审计次数 ÷ 批次总 feature 数 | 0.3 - 3（太少 = 审计不足；太多 = spec 质量问题）|
| **building 返工率** | building 阶段推翻审计决定的次数 | **0** |
| **signoff 争议率** | 验收阶段因审计未决议的点判 fail 的次数 | **0** |

**首次实测基线（KOLMatrix B0 sprint，2026-04-19）：**
- 4 次审计 × 25 决策点 × 均延迟 ~1.5 小时
- 审计命中率 25 ÷ 10 = 2.5（合理）
- building 返工率 0 ✓
- signoff 争议率 1（因 Planner 修 spec 不彻底，已补成 §6.1 铁律）

---

## 6. Planner 裁决必加项（从实测经验沉淀）

### 6.1 修订 spec 的"扫全文"铁律

每次 Planner 修订 acceptance 后，**必须 grep 扫 spec 文件内所有相关关键词段落**，确认无旧口径残留。否则易造成 §3.3 Spec 字面冲突 anti-pattern。

### 6.2 Evaluator 同步通知

修订涉及验收口径时（如测试用例的 verify 方式变更），**必须同步更新 `docs/test-cases/` 对应用例** + session_notes 通知 Evaluator。

### 6.3 决议可复用性

裁决理由应具备复用价值。"因为 Generator 这么建议"不够 — 要说明"同设计系统 / 同多数派 / 减少后续维护成本"等可被下个 Planner 理解的逻辑。

---

## 7. 与其他 harness 机制的关系

| 机制 | 关系 |
|---|---|
| **harness-rules.md 铁律 4** "不得自评代码" | pre-impl 审计仍由 Generator 主动发起，不涉及自评 |
| **harness-rules.md 铁律 9** "hotfix 也走流程" | hotfix 批次同样适用 pre-impl 审计（时间压力下可用 §8 极简格式）|
| **planner.md 铁律 1** "spec 必须核查源码" | 裁决前 Planner 必须 Read 实现文件确认现状（§4.1）|
| **role_assignments** | 多 Planner 项目：审计请求发给 `role_assignments.planner` |
| **v1.0 Orchestrator 模式** | 正交互补。Orchestrator 解决"怎么派发"，本 pattern 解决"怎么对齐"|

---

## 8. 最小化使用示例

**极简 case：** 简单 feature 无歧义，但 Generator 发现 1 个小 gap。

```markdown
# {Batch} {Feature} · 前置审计

- Spec 要求：{简短}
- 发现 gap：{列 1-2 项}
- 决议请求：
  1. {gap 1} → 建议 A
- 开工条件：Planner 回复 `#1:A` 即可

（5 分钟能写完，Planner 5 分钟回复）
```

不是所有审计都要写长篇。**复杂度匹配风险** 是核心原则。

---

## 9. 落地检查清单（给 Planner）

新批次启动时，Planner 确认：

- [ ] `planner.md` 已引用本文件（§Planner 裁决职责段）
- [ ] `generator.md` 已引用本文件（§2.5 开工前审计段）
- [ ] `.auto-memory/MEMORY.md` T2 条目触发条件含"pre-impl 审计"
- [ ] `features.json` 的 acceptance 足够清晰，不留 §1 的 3 类错误场景

---

## 10. 附录：fixing 阶段的裁决变体（mid-impl）

来源：aigcgateway BL-SEC-POLISH 首轮验收（Round 1）— 首次应用 fixing 阶段裁决流程。

### 10.1 场景差异

| 维度 | Pre-Impl（§1-8） | Mid-Impl（本附录） |
|---|---|---|
| 触发时机 | 开工前（building 开始之前） | 开工后（fixing 阶段，某 feature 已 FAIL/PARTIAL） |
| 发现者 | Generator 读 spec 时 | Generator 收到 Evaluator feedback 后 |
| 文件位置 | `docs/specs/{batch}-{feature}-*.md`（审计与 spec 同目录） | `docs/adjudications/{batch}-adjudication-request-{YYYY-MM-DD}.md` |
| 典型触发 | 规格歧义 / 跨源漂移 / API 设计 | **spec acceptance 条款内部矛盾** / acceptance 与协议规范冲突 / acceptance 与 Planner 设计意图冲突 |

### 10.2 触发条件（Generator 必须落盘裁决申请）

fixing 阶段发现 Evaluator 按 acceptance 字面判 FAIL，但代码实现**有合理理由不动**：

- (a) **spec 内部矛盾** — acceptance 某条与同 spec 内的背景 / 风险分析 / 设计决策冲突（示例：acceptance 要求 <50ms，spec 背景却说"抗时序枚举"）
- (b) **协议 / 语言 / 平台规范** — acceptance 违反 MCP SDK / HTTP 标准 / Next.js 约定等（示例：要求 MCP tool 返 HTTP 429，但 MCP 协议不支持）
- (c) **Planner session_notes 设计目标** — acceptance 与 Planner 显式写入 progress.json 的设计意图冲突

### 10.3 流程

1. Generator 落盘 `docs/adjudications/<batch>-adjudication-request-<date>.md`，包含：
   - 冲突描述（acceptance 原文 vs 冲突源的原文引用）
   - Generator 当前实现 + 实测数据
   - 2-3 个候选方案（含 "保留当前实现 + 修订 spec" 方案）
   - Generator 意见 + 需要 Planner 决定的选项
2. commit + push；commit message 明示"等 Planner 裁决"
3. **Generator 不自主回退或坚持**，等裁决
4. Planner 读取后在文件末尾填裁决栏：`裁决点 #X：[A/B/其他] + 修订说明`
5. Planner 同步修订 spec / features.json（若选 A = 保留实现 + 修订口径）或指示回退（若选 B）
6. push 后 Generator / Evaluator 按新口径继续

### 10.4 Mid-Impl 裁决的特殊要求

- **Planner 自检优先：** 收到 mid-impl 裁决请求，优先核查是否违反了自己立过的铁律（见 `planner.md` §铁律自检规则）。若是，不修代码修 spec，并承认失误。
- **修订 spec 时必须注明来源：** acceptance 旁加 `【2026-04-XX 裁决修订】`，防止未来二次困惑
- **同步追加到 proposed-learnings：** 若此类冲突为 pattern（非个案），沉淀为新的 Planner 铁律

### 10.5 aigcgateway 首次应用（参考案例）

- 批次：BL-SEC-POLISH
- 文件：`docs/adjudications/BL-SEC-POLISH-adjudication-request-2026-04-19.md`
- 裁决点 #1（acceptance <50ms vs 抗时序枚举）+ #14（HTTP 429 vs MCP isError）
- Planner 全部采纳方案 A（保留实现 + 修订 spec），并承认 2 次违反自己立的铁律（1.1 和 2.1）
- 效果：Generator 只改 #13 一个纯 bug，reverifying 通过；避免了按错误 acceptance 回退实现引入新漏洞

---

## 11. 版本历史

| 日期 | 修订 | 来源 |
|---|---|---|
| 2026-04-19 | 初版沉淀 | KOLMatrix B0 sprint 实测 |
| 2026-04-20 | 回流 harness-template | 去除项目特定示例，保留通用 pattern |
| 2026-04-20 | 新增 §10 附录：fixing 阶段的 mid-impl 裁决变体 | aigcgateway BL-SEC-POLISH 首次应用 |
