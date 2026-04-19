# Database Patterns（框架沉淀）

> 跨批次通用的数据库设计 / schema 写作坑。Planner 在写涉及 DB schema、migration、RLS 的 spec 时必读本文件核对。

---

## 1. PostgreSQL RLS 策略：`current_setting` 必须 NULLIF 兜底

### 1.1 坑

`current_setting('app.xxx', true)::uuid` 直接强 cast，在 session 生命周期内会遇到 3 种返回状态：

| session 状态 | `current_setting(...)` 返回 | 直接 `::uuid` 行为 |
|---|---|---|
| 从未触达过该 GUC | `NULL` | `NULL::uuid = NULL`（安全） |
| SET LOCAL 触达过后 tx 结束 | `''`（空串，非 NULL） | **THROW** `invalid input syntax for type uuid: ""` |
| 当前 tx 内 SET LOCAL | 具体值 | 正常 cast |

**关键陷阱：** `current_setting(key, true)` 的 `true` 参数只是"missing 时不报错"，但只要 session 对某个 GUC 触达过（SET 或 SET LOCAL），该 key 在 session 剩余生命周期内值会变成 `''`——**不会**恢复到 missing 状态。

### 1.2 后果

- RLS USING 谓词直接 raise → 整个查询失败
- Postgres OR 不短路异常：即使 `OR is_platform_admin = true` 右侧应该成立，左侧的 cast 异常在执行期已抛
- 连接池复用场景（Prisma、node-pg Pool）：**flaky** —— 随机命中受污染连接时 throw，没被污染时 pass
- 典型症状：E2E 测试 workers=1 也会偶发失败，"有时 PASS 有时 FAIL"，调试期生产 fixtures 的超级管理员绕过路径不稳

### 1.3 正确模板

```sql
-- ✅ 正确：所有 RLS 策略统一用 NULLIF(..., '')::uuid 兜底
CREATE POLICY tenant_isolation ON "kol"
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY user_isolation ON "user"
  USING (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    OR current_setting('app.is_platform_admin', true)::bool = true
  );
```

`NULLIF('', '')` → `NULL`，使 `tenant_id = NULL::uuid` 为 NULL（默认拒，符合 RLS 语义）。三态都稳定：

| session 状态 | `NULLIF(current_setting(...), '')::uuid` | RLS 判定 |
|---|---|---|
| 从未 SET | NULL | `tenant_id = NULL` = NULL → 过滤（默认拒） |
| SET 后 tx 结束 | NULL（NULLIF 把空串转 NULL） | 过滤（默认拒） |
| 当前 tx 内 SET | 具体 uuid | 匹配或过滤 |

### 1.4 反面案例（不推荐的替代方案）

| 方案 | 评价 |
|---|---|
| 在 `withTenant` 每次 tx 开头 `RESET app.tenant_id` | 治标：RESET 不会抹除"touched"状态，GUC 值仍可能是 `''`；还会遮蔽真实 bug |
| `SET LOCAL app.tenant_id = '00000000-...-0000'` 哨兵值 | 引入魔数，业务代码读 GUC 要处处特判 all-zero uuid |
| `ALTER DATABASE SET app.tenant_id = 'NULL'` | 依赖超级用户权限；仍可能与 SET LOCAL 交互出新坑 |

`NULLIF` 是最小面积、最直接语义的方案。

### 1.5 Planner 检查清单

新批次涉及以下场景时，Planner 审核期必须逐条核对：

- [ ] 任何新增 RLS 策略的 USING / WITH CHECK 谓词是否都用 `NULLIF(current_setting(...), '')::uuid`？
- [ ] 任何引用自定义 GUC 的 SQL（不限 RLS）是否考虑了空串返回？
- [ ] 相关 Prisma migration 是否有 rollback 段？
- [ ] 集成测试 `tests/integration/rls-*.test.ts` 是否稳定断言"不带上下文 → 0 rows"而非 try/catch 接受 throw？

---

## 来源

- KOLMatrix BI1-F008 marketer E2E flaky 根因（2026-04-19）
- 裁决文档：`docs/specs/BI1-f008-rls-nullif-fix.md`
- 修复 commit：`d438777`（NULLIF migration）

---

## 版本历史

| 日期 | 修订 | 来源 |
|---|---|---|
| 2026-04-20 | 初版沉淀 | KOLMatrix BI1-F008 RLS flaky 根因分析 |
