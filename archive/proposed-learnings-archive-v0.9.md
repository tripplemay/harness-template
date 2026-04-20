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

---

## [2026-04-20] Planner (Kimi) — 来源：BI2 DB 命名坑

**类型：** 新规律（Planner 自律）

**原始提案：**
涉及数据库命名 / 角色名 / grant 对象的 spec 写作前，Planner 必须先扫一遍项目现存 `prisma/migrations/*/migration.sql`，提取 migration 里硬编码的 DB 名 / 角色名 / 权限对象名。spec 和 environment docs 的字面命名必须与 migration 硬编码**完全一致**；如冲突以 migration 为准（migration 已执行过就是事实，文档必须追随）。

**用户裁决（2026-04-20）：** ✅ 采纳

**落地位置：** `framework/harness/database-patterns.md` §2 "数据库命名 / 角色 / Grant 对象必须与 migration 硬编码一致"（v0.9.2）

---

## [2026-04-20] Planner (Kimi) — 来源：BI2-F002 PM2 zero-downtime 两轮证伪

**类型：** 新坑（技术坑 + Planner 自律）

**原始提案：**
PM2 cluster 的 zero-downtime reload **不是** "cluster mode + instances ≥ 2" 自动拥有的能力，必须同时满足 3 条：(1) worker 是 PM2 直接子进程；(2) app 主动 `process.send('ready')`；(3) `wait_ready: true` + 合理 `listen_timeout`。Next.js 生产 + PM2 cluster 唯一可靠路径 = custom `server.js` + `wait_ready`，不是可选优化。

**用户裁决（2026-04-20）：** ✅ 采纳

**落地位置：** 新增 `framework/harness/deploy-patterns.md` §1 "PM2 cluster zero-downtime reload 的 3 个必要条件"（v0.9.2）
