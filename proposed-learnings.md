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

---

## [2026-05-08] Planner johnsong — 来源：BL-012 F002 fix-round 2 prod zod schema mismatch

**类型：** 铁律 1 v0.9.14 / v0.9.15 / v0.9.17 同源延伸（外部 API response shape 实物核查）

**内容：** Planner 起草 spec / Generator 实装 **zod schema for external API response** 时，必须 ≥5-10 真数据 row sample 验证 schema 兼容，不能仅依赖文档/sample/字面假设。尤其当外部 API 可能返回 **union shape**（`string | object`）/ **record vs array** 等灵活类型时，audit 阶段 sample 不足导致严格 schema 在 prod 真数据触发 parse error。

**实物范例（BL-012 5/8 19:00）：**

1. 5/8 02:00 Planner johnsong audit fork @ `gh api repos/guang-tech/apify` — 抽样审 README + .env.example + docs/specs/2026-05-07-tikhub-migration-design.md + ai-usage.md 前 120 行（response shape 注释 "IG 的多外链原结构"），但**未 SSH 拉真数据 row sample 验证**
2. 5/8 02:30 spec v2 §3.1 数据契约段写：
   ```ts
   "externalUrls": [...],     // IG 的多外链原结构（注释含糊 — 实际是 [{url, title}] not [string]）
   "aggregatorLinks": null,   // L2 Linktree (实际 null OR array OR record，未明示）
   ```
3. 5/8 ~14:00 Generator F002 实装 zod schema 按字面假设：
   ```ts
   externalUrls: z.array(z.string()),                       // ❌ 严格 string array
   aggregatorLinks: z.record(z.string(), z.unknown()),     // ❌ 严格 record
   ```
4. 5/8 ~16:00 单测 mock 用 string array 通过（未触发 union shape）→ Reviewer signoff PASS
5. 5/8 ~17:00 staging admin@... 实地审视 — 24h 未足，数据稀少未触发
6. 5/8 ~19:00 prod 真数据触发 — 50 KOL 中 41 row externalUrls 是 `[{url, title}]` + 1 row aggregatorLinks 是 array → zod safeParse 41 fields error → preview 页加载失败
7. 5/8 ~19:00 Planner 修订 F002 acceptance addendum (fix-round 2)：
   ```ts
   externalUrls: z.array(z.union([
     z.string(),
     z.object({ url: z.string(), title: z.string().optional() }).passthrough(),
   ])).nullable().optional(),
   aggregatorLinks: z.union([
     z.record(z.string(), z.unknown()),
     z.array(z.unknown()),
     z.null(),
   ]).optional(),
   ```

**根因：**

- v0.9.14 铁律 1 已覆盖"spec / audit 起草前 grep 实物状态"，但**对外部 API response shape 仍存在盲区** — 文档注释"多外链原结构"是 union 信号，audit 阶段未拉真数据 row sample 验证 → spec / zod schema 严格化 → prod 真数据触发 parse error
- v0.9.17 已覆盖"记忆条目陈旧风险"（外部协作方 / 第三方仓库的"X 已交付"类断言核查），但**对外部 API response shape 的 union 多 shape 验证**未明示 — Sample 1-2 row 不足以发现 union shape，必须 ≥5-10 row + 多种边界（不同 platform / nano vs mega / 含 / 不含 emails 等）

**修订规则：**

Planner 起草 spec / Generator 实装 zod schema for external API response 前，**必须 ≥5-10 真数据 row sample 验证**：

| 场景 | 核查动作 |
|---|---|
| 外部 API（fork / 第三方 / 跨服务）GET response shape | SSH service deployed → curl 真 endpoint → 拉 ≥5-10 row sample → JSON parse 验证 zod schema 兼容；尤其当文档注释含"原结构 / 多 / 灵活"等 union 信号 |
| Union shape 候选（string \| object / record vs array / null vs undefined） | union 类型 zod schema (`z.union([...])`) 优于严格单 shape；passthrough 容忍未知字段 |
| Schema 边界 case 覆盖 | sample 必须含多 platform / 多 tier / 多边界（含 emails / 不含 / null fields）；单测必须含 union 类型每种 shape |

**反面（不修订时）：**

- spec / zod schema 严格化 → 单测 mock 用文档 sample shape 全过 → 真数据触发 schema mismatch → prod parse error → 用户体验破 / 紧急 fix-round
- BL-012 5/8 案例：F002 single-shape zod schema 通过单测 + signoff，但 prod 真数据 41 fields error → 必须 fix-round 2 + zod union 修订

**建议写入：** `framework/harness/planner.md` 铁律 1 检查矩阵新增 1 行（v0.9.19）：

| 内容（v0.9.19 新增） | 核查动作 |
|---|---|
| 外部 API response zod schema（fork / 第三方 / 跨服务 GET 响应） | SSH 拉 ≥5-10 真数据 row sample → JSON parse 验证 zod schema 兼容；文档注释含"多 / 原结构 / 灵活"等 union 信号必须 union 类型；passthrough 容忍未知字段 |

**状态：** 待确认
