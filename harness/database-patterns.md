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

## 2. 数据库命名 / 角色 / Grant 对象必须与 migration 硬编码一致（Planner spec 起草期必扫）

### 2.1 坑

init migration 常含硬编码的 DB 名 / 角色名 / 权限对象名，例如：

```sql
-- prisma/migrations/20260418010000_app_role/migration.sql
CREATE ROLE kolmatrix_app NOLOGIN;
GRANT CONNECT ON DATABASE kolmatrix TO kolmatrix_app;
--                     ↑ 这里硬编码了 DB 名
```

一旦 migration 被执行，该命名就成了**事实**：
- 生产 DB 必须叫 `kolmatrix`（否则 `GRANT CONNECT ON DATABASE kolmatrix` 失败）
- spec / architecture.md / environment.md 里写 `kolmatrix_prod` 就是漂移

### 2.2 后果

Planner spec 文档里假设一个 DB 名（如 "kolmatrix_prod"），但 init migration 写的是另一个（如 "kolmatrix"），导致：
- 首次 bootstrap 生产被迫按 migration 命名（硬编码无法绕过），与 spec 不符
- 所有引用 DB 名的下游文档（runbook / infrastructure.md / backup 脚本 / env file / deploy script）都要做一次对齐
- Generator 要反复 SSH 修文件、Planner 要出裁决、多一次 round-trip

KOLMatrix BI2 案例：prod bootstrap 时发现 migration 硬编码 `kolmatrix`，spec 和 5 份 docs 都写 `kolmatrix_prod`，最终 Planner 裁决方案 A（统一 follow migration 固定名 `kolmatrix`）全文档追随。

### 2.3 Planner spec 起草期检查清单

写涉及 database / role / grant 的 spec 前，**必须**先扫一遍：

```bash
# 查 migration 里所有硬编码的 DB 名、角色名、权限对象名
grep -rE 'DATABASE|CREATE ROLE|GRANT|REVOKE|ALTER ROLE' prisma/migrations/*/migration.sql
```

- [ ] spec / architecture / environment / runbook / backup-script 里出现的 DB 名，与 migration 硬编码**完全一致**？
- [ ] spec / role 相关段落里出现的 PG 角色名，与 migration `CREATE ROLE` 完全一致？
- [ ] spec 里写的 "XXX user has Y privilege" 与 migration `GRANT/REVOKE` 一致？
- [ ] 如果 spec 和 migration 冲突，**以 migration 为准**（已执行的事实）；不一致时 Planner 改 spec，不改 migration

### 2.4 更深一层：为什么不能"改 migration"

Prisma migration 一旦 `migrate deploy` 成功，记录进 `_prisma_migrations` 表，不能再改原文件（会 hash 不匹配）。修正名字需要新 migration `ALTER DATABASE ... RENAME` + `REVOKE / REGRANT`，生产执行风险远高于"文档追随 migration"。所以 Planner **主动对齐到 migration** 是正确方向。

---

## 来源

- KOLMatrix BI1-F008 marketer E2E flaky 根因（§1，2026-04-19）
- KOLMatrix BI2 DB 命名 spec 漂移（§2，2026-04-20）
- 相关文档：`docs/specs/BI1-f008-rls-nullif-fix.md` / `docs/specs/BI2-deployment-automation-spec.md`

---

## 3. Prisma 7+ JSON 列写入需 `as Prisma.InputJsonValue` cast（或函数返回类型收紧）

### 3.1 坑

KOLMatrix B5 F004 / F006 同坑（commits 3349a9a + 类似）：

```typescript
// recent-videos.ts:140
await tx.kol.update({
  where: { id: opts.kolId },
  data: { metadata: mergeMetadata(opts.metadata, next) },
  //              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  //              TS2322: Type 'Record<string, unknown>' is not assignable
  //              to type 'InputJsonValue | NullableJsonNullValueInput | undefined'
});
```

`mergeMetadata()` 返回 `Record<string, unknown>`，Prisma 7 的 `Json` 列输入是 `InputJsonValue` 联合类型（不接受 `unknown` 类内的任意 shape）。

### 3.2 正解

**优先：函数返回类型收紧到 `Prisma.InputJsonValue`** —— 一处改、调用点全部受益：

```typescript
import type { Prisma } from "@prisma/client";

export function mergeMetadata(
  existing: Prisma.JsonValue | null,
  patch: Record<string, unknown>
): Prisma.InputJsonValue {
  // ... merge logic
  return merged as Prisma.InputJsonValue;
}
```

**次选：调用点 cast** —— 如果 `mergeMetadata` 是公共 util 不能改返回类型：

```typescript
data: { metadata: mergeMetadata(opts.metadata, next) as Prisma.InputJsonValue }
```

### 3.3 Spec / Generator checklist

任何 lib 函数返回 → Prisma JSON 列写入 → spec § acceptance 必含：

- [ ] 返回类型是 `Prisma.InputJsonValue` 或显式 cast
- [ ] CI typecheck 全绿（不能依赖 `// @ts-ignore` 抑制）

CI 容易漏掉这一条因为 `chore(state)` paths-ignore 跳过 typecheck。Generator 推 product code commit 时**必须验证 typecheck 实跑通**（不要靠后续 chore commit 推时再 retrigger）。

来源：KOLMatrix B5-F004 (commit 0dd1697 latent / 3349a9a fix) + B5-F006 (commit 3349a9a)。

---

## 4. RLS 旁路矩阵 + cross-tenant ops 决策树

### 4.1 坑

`withPlatformAdmin` 名字让人以为它是"通用 RLS 旁路"，实际只对 `user` 表的 `user_isolation` 策略生效（policy 显式判 `app.is_platform_admin = true`）。其它带 RLS 的表（`product` / `asset` / `kol` / `campaign` / `email_template` / `email_log` / `kol_campaign` / `campaign_metric` / `weekly_report`）只认 `app.tenant_id`，没看到匹配 tenant 就**静默返 0 行**——不会抛错，看上去查询正常但结果是空。

KOLMatrix BL-030-F003 backfill 脚本就踩了这个坑：用 `withPlatformAdmin` 跨 tenant 扫 `product` 表，prod 跑出来 0 行，到 BL-031 才暴露。生产 5 个 product 的 ai_assets 内容延迟一天进 Asset 表。

### 4.2 旁路矩阵

| 表 | RLS 状态 | 旁路条件 |
|---|---|---|
| `tenant` | **未启用 RLS** | 任何 connection 都可读（credentials auth 流的 lookup 表） |
| `user` | RLS on | `app.tenant_id` = uuid **OR** `app.is_platform_admin` = true |
| `product` / `asset` / `kol` / `campaign` / `email_template` / `email_log` / `kol_campaign` / `campaign_metric` / `weekly_report` | RLS on | 仅 `app.tenant_id` = uuid（platform_admin 不解） |

### 4.3 cross-tenant ops 决策树

应用层（Prisma client 走 `kolmatrix_app` role）想跨 tenant 操作时：

1. **是否能枚举 tenant 列表？** `prisma.tenant.findMany` 直接读（tenant 表无 RLS）
2. **每个 tenant 的业务读写 →** `withTenant(tenantId, tx => ...)` 串行循环，policy 自动生效
3. **绕不过 RLS（跨 tenant 直接 SELECT 业务表）→** ops 层走 sudo postgres `psql` 直跑（superuser 绕 RLS）；migration / backfill / 一次性 admin 任务专用，不进应用代码路径

应用代码**不应**出现 `SET LOCAL row_security = off`、`SET ROLE postgres` 等 superuser 切换——这把 RLS 完全卸了，是 audit 灾难。需要这种力度的操作 = 该任务属于 ops 层而非 app 层。

### 4.4 BL-030 案例的正解

`scripts/migrate-product-aiassets-to-asset.ts` 的 `scanProducts`：

```typescript
// ❌ 错的：withPlatformAdmin 对 product 表无效，silently 返 0 rows
return withPlatformAdmin((tx) => tx.$queryRaw`SELECT ... FROM product`);

// ✅ 对的：tenant.findMany 直读 + per-tenant withTenant 累加
const tenants = await prisma.tenant.findMany({ select: { id: true } });
const rows: ProductScanRow[] = [];
for (const { id: tenantId } of tenants) {
  const slice = await withTenant(tenantId, (tx) => tx.$queryRaw`SELECT ... FROM product`);
  rows.push(...slice);
}
return rows;
```

### 4.5 Generator / Planner 检查清单

- [ ] 任何用 `withPlatformAdmin` 的代码点：被读的表是否真的是 `user` 或无 RLS 表？读 `product` / `asset` / `kol` 等业务表时它**不生效**
- [ ] 跨 tenant 扫描需求 = 要么 `tenant.findMany` + `withTenant` 循环，要么标注为 ops 层任务走 sudo postgres
- [ ] 应用代码内出现 `SET LOCAL row_security = off` / `SET ROLE postgres` = 立即换 ops 层路径
- [ ] backfill / migration 脚本：fixture 必须含 ≥2 tenant，验证扫到所有 tenant 而非首 tenant 或 0

---

## 版本历史

| 日期 | 修订 | 来源 |
|---|---|---|
| 2026-04-20 | 初版沉淀（§1 RLS NULLIF） | KOLMatrix BI1-F008 |
| 2026-04-20 | §2 DB 命名 / 角色 / Grant 与 migration 一致性 | KOLMatrix BI2 DB 命名坑 |
| 2026-05-01 | §3 Prisma 7+ JSON 列写入需 InputJsonValue cast | KOLMatrix B5-F004/F006 同坑 |
| 2026-05-04 | §4 RLS 旁路矩阵 + cross-tenant ops 决策树 | KOLMatrix BL-030-F003 backfill scanProducts 0 行（BL-031-F003 hotfix） |
