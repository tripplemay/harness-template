# Framework 提案暂存区

> Generator 和 Evaluator 在工作中发现值得沉淀的经验时，追加到本文件。
> Planner 在 done 阶段读取本文件，逐条提交给用户确认。
> 确认后由 Planner 正式写入 `framework/` 对应文件，并在 `CHANGELOG.md` 追加记录，最后从本文件移除已确认条目。
> 已闭环条目归档到 `framework/archive/proposed-learnings-archive-vX.Y.md`。

---

<!-- 待确认的提案出现在此处，示例格式：

## [YYYY-MM-DD] [角色] — 来源：F-XXX

**类型：** 新规律 / 新坑 / 模板修订 / 铁律补充

**内容：** [一句话描述]

**建议写入：** `framework/README.md` §经验教训 / `framework/harness/xxx.md` / 其他

**状态：** 待确认

-->

<!-- 2026-05-04: v0.9.9 沉淀完成（8 条 learnings 来源 BL-030/BL-031/BL-032），全部已写入 framework/ 对应文件 + CHANGELOG。 -->

## [2026-05-04] Planner Kimi — 来源：prod-mvp-readiness-audit-2026-05-04

**类型：** 模板修订 + 新规律

**内容：** Claude CLI 独立任务模式产出 168 行 prod MVP 上线前体检报告，覆盖 4 个池子 18 项阻塞 + 文件:行级精度。报告价值：(1) 比常规 Reviewer signoff 范围广，跨多批次结论 + PRD spec 对齐；(2) 锁文件:行可直接转 backlog 条目（本次 BL-020/BL-024 增补 + 新增 BL-040/041 的实际依据）；(3) 用户视角 vs 工程内部视角双轨判断。建议把"prod 上线前安全 + 完整性体检"作为独立 audit 模式制度化。

**建议写入：**

1. `framework/templates/` 新建 `prod-launch-audit-template.md`（参照本次 168 行报告结构）：6 章节模板（TL;DR + 部署版本对位 + 池子 A/B/C/D 分类 + DoD 七步对照 + 推荐执行顺序 + 风险提示）+ 必查 6 维度 checklist（部署版本 / 业务流 7 步 / 安全 6 项 / ghost controls / PRD 对齐 / 数据状态）+ 触发时机（每个 MVP 上线节点 + 重大邀请客户前 + 真客户上线前）

2. `framework/harness/planner.md` 加节「上线前 audit 触发条件」：满足以下任一即触发独立 audit task（不入状态机批次，作 Planner 旁路任务）：
   - MVP 邀请第一批种子用户前
   - 真客户对外发布前
   - 1+ sprint 没做安全 / 完整性审计的连续工作日 ≥ 5
   - 用户主动请求

3. v0.9.10 CHANGELOG 标志性变更："Prod-launch audit 模板化 + Planner 触发规则"

**状态：** 待确认（下一 done 阶段处理；可与 BL-033 done 合并入 v0.9.10）
