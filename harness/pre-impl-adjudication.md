# Pre-Implementation Audit → Planner Adjudication Pattern

> **沉淀来源：** KOLMatrix 项目 B0 sprint（2026-04-18 ~ 2026-04-19）
> **验证数据：** 4 次 pre-impl 审计 × 25 决策点 × **0 building 阶段返工**
> **适用场景：** 任何涉及规格歧义、视觉还原、跨页一致性、组件 API 设计的 Generator 任务

---

## 1. 问题定义

Generator 按 spec 直接开工时，常见 3 类代价高昂的错误：

1. **规格内部矛盾** —— spec 头部说 A，acceptance 段说 B（Planner 修订 acceptance 忘改实现段）
2. **跨参考源漂移** —— 设计稿 / HTML / designMd / spec 四处描述同一组件但细节不一致
3. **Generator 凭本能填空** —— spec 有灰色地带（如 "必须使用 12 个组件" 如何定义"使用"？），Generator 自己解释后开工，Reviewer 按不同解释判 fail

**传统流程成本：** 发现矛盾时已经写了大量代码，需要回退重写（building → verifying → fixing 循环）。

## 2. Pattern 核心

**Generator 在动代码之前，主动提交 pre-impl 审计文档，列出发现的所有歧义 + 跨源漂移 + 候选方案，请 Planner 裁决。Planner 裁决后才开工。**

### 2.1 触发条件（Generator 必须提交审计的场景）

| 场景 | 例 |
|---|---|
| 规格文字含糊 | "必须使用 12 个组件" —— 直接 import 还是渲染树包含？ |
| 多份参考源冲突 | dashboard.html 7 个 nav vs designMd 8 个 |
| 组件 API 需要决策 | StatCard `sparkline` 是可选 prop 还是必带？ |
| 跨页变体 | KolCard grid 和 row 两种布局 —— 单组件 variant 还是两组件？ |
| 非 token 色使用 | 平台品牌色（YouTube red）是否需要扩 @theme？ |
| 发现原型 bug | HTML 快照与 canonical 不一致时如何处理？ |
| 数据模型 gap | `Campaign.openRate` 字段不存在，是加 migration 还是动态计算？ |

### 2.2 审计文档模板（Generator 写）

存放位置：`docs/specs/{batch}-{feature}-{topic}.md`（例 `B0-app-shell-canonical-review.md`、`B0-f010-component-map.md`）

```markdown
# {Batch} {Feature} · {Topic} 规划稿 / 审计请求

> **发起者：** {agent-id} (Generator)
> **日期：** YYYY-MM-DD
> **触发：** {feature} 开工前审计，按 pre-impl 审计 → Planner 裁决工作范式
> **状态：** 等待 Planner 明确回复，**未收到前不开工**

## 1. 背景 & 目标
{简述该 feature 做什么，关键约束有哪些}

## 2. {跨源比对 / 路由 migration / 组件映射 / 数据 gap} 审计

{表格或列表列出发现的事实差异。例：7 份 HTML 比对表 / Props API 草案 / Prisma schema 核对结果}

## 3. N 条决议请求

| # | 决议点 | A 方案 | B 方案 | 多数派参考 | 建议 |
|---|---|---|---|---|---|
| 1 | ... | ... | ... | ... | **A** |
| 2 | ... | ... | ... | ... | **B**（理由...） |

### 裁决格式要求
请 Planner 就每条给出明确的 **A / B / C** 选择 + 简短理由（偏离建议时）。
用 `#1:A #2:B #3:A...` 短格式回复即可。

## 4. 原型 bug / 已知漂移追加（如有）

{扫描发现的 HTML/设计稿 bug，是否回修或仅登记}

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

1. **短格式决议**（可一行列全）：`#1:A #2:B #3:A #4:A...`
2. **逐条理由**（表格）：
   | # | 决定 | 理由 |
   |---|---|---|
   | 1 | A | ... |
3. **同步文档更新清单**：Planner 同时修订 spec / features.json / 相关文件，并列出修订列表
4. **额外叮嘱**（非阻塞）：实现时容易踩的坑 / 命名建议 / 未来 gotchas

**裁决推送 main 后，Generator 可立即开工，无需再确认。**

### 2.4 状态机配合

审计期间状态机不移位（保持 `building`），但 Generator **事实上处于"等待裁决"非工作态**。

完整流程：
```
building 开始
    ↓
Generator 开工审计（生成 pre-impl 审计文档）
    ↓ push main（状态仍 building）
Planner 看到审计请求，作裁决（同文档末尾追加 + 修 spec）
    ↓ push main
Generator git pull 看到裁决 → 真正开始实现
    ↓
走闸门 → 更新 features.json status=completed → push
```

---

## 3. 决策类型分类（常见 4 种）

按 B0 经验，决议点落到这 4 类：

### 3.1 Canonical 选择（多源漂移）
**特征：** 多份参考源说法不同，选一个作为"真相"。
**例：** B0 F005 sidebar HTML tag（`<aside>` vs `<nav>`）、sidebar padding（`px-4` vs `px-6`）
**处理：** Planner 通常采纳多数派 + designMd 一致 + 语义合理。少数派登记为"已知漂移"，不回修源。

### 3.2 Props API 决策
**特征：** 组件暴露多少可变性，拆粒度如何。
**例：** StatCard 的 sparkline 可选 vs 必带、KolCard 单组件 variant vs 两组件
**处理：** Planner 通常倾向"最小 surface + 渐进扩展"（可选 prop / variant 切换）。

### 3.3 Spec 字面冲突（Planner 自锅）
**特征：** 同 spec 文件内不同段落自相矛盾（多半因 Planner 修订 acceptance 忘改实现段）。
**例：** B0 F007 "必须 import 12 组件" vs §11.2 "渲染树 12 全覆盖"
**处理：** Planner **必须承认责任**、修订一致、不让 Generator 或 Reviewer 背锅。

### 3.4 范围与依赖决策
**特征：** 本 feature 是否包含某些前置动作。
**例：** F007 sprint 是否合并 Campaign.openRate migration + seed 补齐
**处理：** 按"自然叙事" vs "git 历史清晰度" 权衡，通常前者胜（一次 PR 包完整故事）。

---

## 4. Anti-patterns（不得出现）

### 4.1 Planner 凭印象裁决
**错误：** Planner 没读代码就下结论
**正确：** 按 `planner.md` 铁律 1「涉及代码细节必须核查源码」，Read 现状再判

### 4.2 Generator 审计过度笼统
**错误：** "F005 有歧义，请 Planner 确认" —— 没列具体分歧点
**正确：** 每个歧义点 → A/B 两个明确方案 + 自己建议 + 理由

### 4.3 Planner 修 acceptance 不扫 spec 全文
**错误：** 只改 acceptance 段，忘了前面实现段描述
**正确：** 用 grep 扫 spec 文件内所有相关关键词段落，确认无旧口径残留

### 4.4 审计被当成"正常步骤"漫反射
**错误：** 每个 feature 都写一份漫长 pre-impl 审计，即使 spec 清晰无歧义
**正确：** 只在触发条件命中时写。简单 feature 直接开工即可。

### 4.5 Reviewer 按旧 spec 验收
**错误：** Planner 修订 spec 后，Reviewer 引用旧版判 fail
**正确：** Planner 推送新版后，在 session_notes 或 test-cases 更新通知 Reviewer

### 4.6 Generator 自裁决（2026-04-26 加）
**错误：** Generator 写完 audit §7 自己填"自裁决；方案 A"，不等 Planner 提交 main 就开工

**正确：** audit 推 main 后 Generator **必须等待** Planner 回复 + Planner 提交 main 裁决 commit；即使决议看起来全 A 明显，也要走 Planner 一圈。

**豁免：** Planner 和 Generator 是同一 agent-id（如 `role_assignments.planner == role_assignments.generator`）时，Planner 裁决可在同一 commit 完成，但**必须分段标注角色切换**；不得省略裁决段。

**典型触发链（来源 KOLMatrix MVP-visual-fidelity-hotfix F001 越界事件）：** Generator 在 BM2 F005 完成后写 hotfix F001 audit + §7 自裁决"全 A 无偏离方案；跨批次执行已用户授权"（实际用户未给此授权，Generator 误读了 Planner Phase 2 三点决议）→ 直接开工 hotfix F001 七文件改动。技术产出合理但流程违规。

### 4.7 Generator 跨批次启动（2026-04-26 加）
**错误：** Generator 看到有"未来批次"的工作可做，自己判断"顺便做了吧" + "用户应该会同意"直接开工

**正确：** 只做当前批次 features.json 列出的工作；跨批次启动**必须 Planner 裁决 + 用户确认两道门**（commit 形式留痕）

**边界：** "当前批次前置依赖"（如抽通用组件给后续 feature 用）可在当前批次 feature 范围内做，但必须在该 feature 的 spec acceptance 明示；不得新开无归属的灰色工作。

**判定原则：** 任何 spec-driven 工作必须有 features.json feature 号归属（即 commit message 的 `feat(<batch>-F<num>):` 标签能对得上 features.json）；无归属的代码修改 = 越界。

---

## 5. 统计口径

评估 pattern 有效性的指标：

| 指标 | 含义 | 目标值 |
|---|---|---|
| **审计→裁决延迟** | 从 pre-impl push 到 Planner 裁决 push 的时间 | < 2 小时（同步会话）/ < 半天（异步） |
| **审计命中率** | 裁决点 ÷ 总 feature 数 | 0.5-3（太少 = 审计不足；太多 = spec 质量低） |
| **返工率** | building/fixing 阶段需要推翻审计决定的次数 | **0** |
| **Reviewer 争议率** | signoff 阶段仍因审计未决议的点判 fail 的次数 | **0** |

B0 sprint 实测：
- 4 次审计 × 25 决策 × 1.5 小时均延迟 = pattern 可接受
- 审计命中率 25 / 10 = 2.5（合理）
- 返工率 0（4 features 全达标）
- Reviewer 争议率 1（F007 口径，但根因是 Planner 修 spec 不彻底，已补正为 §5 铁律）

---

## 6. Planner 裁决时必加项（根据 B0 经验沉淀）

### 6.1 修订 spec 的"扫全文"铁律
每次 Planner 修订 acceptance 后，**必须 grep 扫 spec 文件内所有相关关键词段落**，确认无旧口径残留。否则易造成 §3.3 Spec 字面冲突 anti-pattern。

### 6.2 Reviewer 同步通知
修订涉及验收口径时（如 TC-L1-003 verify 方式变更），**必须同步更新 `docs/test-cases/` 对应用例** + session_notes 通知。

### 6.3 决议可复用性
裁决理由应具备复用价值。"因为 johnsong 这么建议" 不够 —— 要说明"同 designMd / 同 Stitch 多数派 / 减少后续维护成本"等可被下个 Planner 理解的逻辑。

---

## 7. 与其他 harness 机制的关系

| 机制 | 关系 |
|---|---|
| `铁律 6` Generator 不得执行 `executor:codex` | pre-impl 审计仍由 Generator 主动发起，不违反 |
| `铁律 9` 生产紧急故障也走流程 | hotfix 批次同样适用 pre-impl 审计（时间压力下可缩略） |
| Planner `铁律 1` spec 必须核查源码 | 裁决前 Planner 必须 Read 实现文件确认现状 |
| Role assignments | 多 Planner 项目：审计请求发给 `role_assignments.planner` |

---

## 8. 最小化使用示例

**极简 case：** 简单 feature 无歧义，但 Generator 发现 1 个小 gap。

```markdown
# B2 F003 · {组件} 前置审计

- Spec 要求：{简短}
- 发现 gap：{列 1-2 项}
- 决议请求：
  1. {gap 1} → 建议 A
- 开工条件：Planner 回复 `#1:A` 即可

（5 分钟能写完，Planner 5 分钟回复）
```

不是所有审计都要写 200 行。**复杂度 match feature 风险**。

---

## 9. 落地检查清单（给 Planner）

新 sprint 启动时，Planner 确认：

- [ ] `planner.md` 引用了本文件（§规格偏差处理）
- [ ] `generator.md` 引用了本文件（§开工前审计）
- [ ] `.auto-memory/MEMORY.md` T2 条目触发条件含"pre-impl 审计"
- [ ] `features.json` 的 acceptance 足够清晰，不留 3 类错误场景（§1）

### 9.1 Planner 写 spec 自检清单（acceptance 定稿前必扫）

> 来源：BI1-F010 acceptance 偏离案例 —— Planner 写 CI `integration-tests` job acceptance 为 "PG + Redis service container"，与 F002 Testcontainers helper 设计冲突，导致 Reviewer 字面判 PARTIAL，最终走 Planner Adjudication 修订文案。

写完 acceptance 初稿后，Planner 必须在定稿前逐条核对：

- [ ] **内部一致性：** acceptance 描述与**同批次**其他 feature 的 spec/helper 设计是否对齐？（典型冲突点：测试策略、容器方案、外部服务依赖、路径约定）
- [ ] **网络/容器/外部服务：** 如批次选 Testcontainers，CI acceptance 就不应写 "service container"；如批次用 mocks，生产环境依赖描述就不应出现真实 endpoint。两者混用 = 死代码 + 维护困惑。
- [ ] **引用路径：** spec 中提到的 `tests/helpers/*.ts` / `src/lib/*.ts` 路径是否与其他 feature 一致？
- [ ] **术语统一：** 同一概念（"租户" / "tenant" / "tenant_id"）在整个 spec 中是否用同一词？
- [ ] **与 ADR 对齐：** 批次所用技术栈、设计原则是否与 `docs/adr/` 中现有决策一致？不一致必须有新 ADR。

这 5 条任一项没过，说明 Planner 还没准备好定稿——返回审阅。

---

## 10. 版本历史

| 日期 | 修订 | 来源 |
|---|---|---|
| 2026-04-19 | 初版沉淀 | KOLMatrix B0 sprint 实测 |
| 2026-04-20 | §9.1 Planner 写 spec 自检清单 | KOLMatrix BI1-F010 acceptance 偏离案例 |
