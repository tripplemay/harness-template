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

---

## [2026-05-08] Planner johnsong — 来源：BL-012 apify-kol fork audit 2026-05-08

**类型：** 铁律 1 v0.9.14 延伸（记忆条目陈旧风险 — 涉及外部协作方 / 第三方仓库的"X 已交付/已审过"类断言）

**内容：** project-status.md 涉及外部协作方 / 第三方仓库 / 跨项目状态的记忆条目（"爬虫团队 5/7 提前交付"、"X 团队已部署"、"fork audit 推荐方案 A"等）可能 stale at write-time —— 前一轮 Planner 写时反映当时事实，但实物在后续被外部协作方主动更新。后续 Planner 起 spec / 起批次时若不实物核查，会引入"基于过期记忆"的偏差，导致 spec 字面与 fork 实物脱节 → Generator 开工撞实物差异 → 多 1 轮 fix-round 或 retroactive spec 修订。

**实物范例（BL-012 5/7 → 5/8）：**

1. Planner Kimi 5/7 在 `.auto-memory/project-status.md:16` 写「爬虫团队 5/7 提前交付 fork audit 推荐方案 A 分平台分源 IG/TT 给 apify YouTube 给 B6」
2. 但同期 5/7 16:57 fork 实物（`guang-tech/apify`）已完成 **Apify → TikHub 全迁移** + 新增 **X(Twitter)** 平台 = **4 平台齐全**（不是 project-status 写的"3 平台分流"）
3. Planner johnsong 5/8 启动 BL-012 planning 时若信任 project-status:16 仅 grep "apify" → 起 spec 会按 3 平台 IG/TT/YT-via-apify 设计字段映射 → Generator 实装时撞 fork 实物 X 平台不在覆盖中 / fork 已不用 Apify 而用 TikHub → spec 漂移 / fix-round
4. 实地补 audit（`gh api` 抓 README + `.env.example` + `docs/specs/2026-05-07-tikhub-migration-design.md`）才发现实物 5/7 重大变化
5. audit 输出 `docs/reviews/apify-fork-audit-2026-05-08.md`（462 行）+ 用户决议 5 项 + 修订 BL-012 spec 起草口径

**根因：** 铁律 1 v0.9.14 已覆盖"spec / audit / readiness-report 起草前 grep 实物状态"，但**对项目 `.auto-memory/` 内涉及外部协作方的记忆条目**仍存在盲区 — Planner 默认信任记忆 = 信任前一轮写入的快照，但外部协作方 / 第三方仓库可能在记忆写入后被独立更新。

**修订规则：** Planner Step 0 启动新批次前，对 `.auto-memory/project-status.md` 涉及外部协作方 / 第三方仓库 / 跨项目状态的记忆条目（含 "X 团队已交付 / 已部署 / 已审过 / 已上线"类断言），**必须先 grep 实物当前状态**：

| 内容类型 | 核查动作 |
|---|---|
| 第三方 GitHub repo | `gh api repos/<owner>/<repo>` 抓元数据 + 看 `updatedAt` 是否后于记忆写入时间 |
| 内部 fork / mirror | `git log --all --since=<记忆时间戳>` 看是否有后续 commits |
| 跨项目部署状态 | `curl <service-url>/health` + 看响应版本 / sha |

**时间戳 ≥3 天的"提前交付"类条目尤其要查**——3 天足以让协作方完成大改动而记忆未同步。

**反面（不修订时）：** project-status 记忆驱动 spec 起草 → spec 字面与 fork 实物脱节 → Generator 开工撞实物差异 → 多 1 轮 fix-round 或 retroactive spec 修订 → 浪费上线 buffer。BL-012 5/8 案例：若 Planner johnsong 信任记忆字面起 spec，撞 5/7 X 平台 + TikHub 全迁移会导致 ≥1 轮 spec retroactive 修订 + Generator fix-round。

**建议写入：** `framework/harness/planner.md` 铁律 1 检查矩阵新增 1 行（v0.9.17）：

| 内容（v0.9.17 新增） | 核查动作 |
|---|---|
| `.auto-memory/project-status.md` / `session_notes` 等记忆涉及外部协作方 / 第三方仓库 / 跨项目状态的条目（"X 团队已交付/已部署/已审过"类断言） | `gh api` / `git log --all` / `curl health` 实物核查仓库当前状态 + 看时间戳是否后于记忆写入时间；时间戳 ≥3 天必查 |

**状态：** 待确认
