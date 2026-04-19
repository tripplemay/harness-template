# Proposed Learnings Archive — v0.9.x

> 已闭环的提案归档。每条记录：原始提案、用户裁决、落地位置。

---

## [2026-04-19] Planner (Kimi) — 来源：BI1-F008 RLS empty-string GUC flaky

**类型：** 新坑（技术坑）

**原始提案：**
PostgreSQL RLS 策略用 `current_setting('app.xxx', true)::uuid` 直接 cast 存在 session 污染坑 —— GUC 被 SET LOCAL 触达过后返回 `''` 而非 NULL，空串 cast 抛 `invalid input syntax`，导致 RLS USING 谓词失败、`withPlatformAdmin` 绕过设计失效，表现为 Prisma 连接池复用下的随机 flaky。**所有 RLS 策略模板必须用 `NULLIF(current_setting(...), '')::uuid` 兜底**。

**用户裁决（2026-04-20）：** ✅ 采纳

**落地位置：** 新增 `framework/harness/database-patterns.md` §1（v0.9.1）

---

## [2026-04-19] Planner (Kimi) — 来源：BI1-F010 CI job acceptance 偏离

**类型：** 新规律（Planner 自律）

**原始提案：**
Planner 写 CI workflow job acceptance 时，必须先与**同批次的 helper/策略设计**交叉核对，避免 acceptance 文案与实现冲突。具体：如批次选 Testcontainers（测试代码自启容器），CI acceptance 就不应写 "service container"；两者互斥，混用会制造死代码 + 维护困惑。通用化表述：「Acceptance 文案必须与同批次 F00x helper/config spec 交叉核对一次再定稿」。

**用户裁决（2026-04-20）：** ✅ 采纳

**落地位置：** `framework/harness/pre-impl-adjudication.md` §9.1 Planner 写 spec 自检清单（v0.9.1）
