# 架构决策记录（Architecture Decision Records）

> 本项目所有**跨批次影响 / 不可逆 / 当时有过辩论**的关键决策记录。
> 建立日期：YYYY-MM-DD（填首次引入 ADR 系统的日期）

---

## 什么时候该写 ADR

**写：**
- 决策影响多个批次
- 反转需要返工（不可逆或成本高）
- 当时讨论过多个方案
- 会影响未来新 agent 的判断
- 技术栈 / 架构 / 流程 / 验收口径

**不写：**
- 一次性实现细节（库选型：如"用 recharts"—— 换一个不影响架构）
- Spec 级细节（功能列表 / 字段定义 —— 在 spec 里）
- 个人偏好（commit 格式 / 命名风格 —— 在 CLAUDE.md）
- Bug 修复（没决策，只有修复）

---

## 如何使用

### 新 agent 上手

1. 读本 README 1 分钟，看决策总览
2. 按主题 / 按时间挑选 2-3 份 ADR 深读

### 做新决策前

1. 检查本索引是否已有相关 ADR
2. 读相关 ADR 确认新决策不冲突
3. 如果冲突：新 ADR 标 `Supersedes ADR-XXX`，同时改旧 ADR 状态为 `Superseded by ADR-YYY`

### 遇规格争议

1. 先查 ADR（很多争议本质是历史决策被忽略）
2. ADR 无记录 → 按 [`harness/pre-impl-adjudication.md`](../../harness/pre-impl-adjudication.md) 流程发审计请求

---

## 决策状态流转

```
Proposed ──► Accepted ──► [Deprecated | Superseded by ADR-YYY]
```

- **Proposed：** 提议中，未生效
- **Accepted：** 当前生效（默认状态）
- **Deprecated：** 不再适用，但无替代方案
- **Superseded：** 被更新的 ADR 取代

---

## 编号约定

- 3 位数字（001, 002, ..., 099, 100, 101, ...）
- 新 ADR 取下一个未用编号
- 被弃用的 ADR **编号保留不删**（ADR-005 永远是 ADR-005，不重新利用）

---

## 已接受的决策（按编号）

<!-- 新增 ADR 时追加一行 -->

| # | 标题 | 一行摘要 | 状态 | 日期 |
|---|---|---|---|---|
| — | 尚未建立任何 ADR | 待首份决策时删除此行 | — | — |

---

## 按主题索引

<!-- 常见主题分类（新项目按需删除未使用的组）-->

### 工程流程
- —

### 技术栈
- —

### 架构 / 数据
- —

### 视觉 / UI
- —

### 外部服务集成
- —

### 安全 / 合规
- —

---

## 贡献 ADR

1. 复制 `000-template.md` 为 `ADR-XXX-kebab-title.md`
2. 按模板填写
3. 更新本 README 的两个表（编号索引 + 主题索引）
4. push commit message 用 `docs(adr): ADR-XXX 标题`

---

## 相关文档

- [`harness/pre-impl-adjudication.md`](../../harness/pre-impl-adjudication.md) — pre-impl 审计 → Planner 裁决机制（决策流程与裁决规范）
- [`.auto-memory/MEMORY.md`](../../.auto-memory/MEMORY.md) T2 条目 — 本索引的记忆系统接入点
