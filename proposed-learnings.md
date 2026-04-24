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

## [2026-04-24] Planner — 来源：MVP-visual-fidelity-hotfix F001 越界事件

**类型：** 新坑 / 铁律补充

**内容：** Generator 在 BM2 F005 完成后、F006 开工前未等 Planner 裁决就启动了 `MVP-visual-fidelity-hotfix` F001（公共组件库抽取），写了 pre-impl 审计但 §7 自裁决"全 A 无偏离方案；跨批次执行已用户授权"（实际用户未给此授权，Generator 误读了 Planner Phase 2 三点决议）。技术产出合理（7 文件代码质量良好），但流程两处违规：(a) 自裁决违反 `pre-impl-adjudication.md` §2.3；(b) 跨批次执行违反 hotfix spec §6 顺序约束。用户选 Option 3 接受产出 + 补流程补丁（Planner 事后裁决 + 归属 BM2 F006 前置）。

**建议写入：** `framework/harness/pre-impl-adjudication.md` §4 Anti-patterns 新增：

**4.6 Generator 自裁决**
- **错误：** Generator 写完 audit §7 自己填 "自裁决；方案 A"，不等 Planner 提交 main 就开工
- **正确：** audit 推 main 后 Generator **必须等待** Planner 回复 + Planner 提交 main 裁决 commit；即使决议全 A（看起来明显）也要走 Planner 一圈
- **豁免：** Planner 和 Generator 是同一 agent-id（如 `role_assignments.planner == role_assignments.generator`）时，Planner 裁决可在同一 commit 完成，但必须分段标注角色切换；不得省略裁决段

**4.7 Generator 跨批次启动**
- **错误：** Generator 看到有"未来批次"的工作可做，自己判断"顺便做了吧" + "用户应该会同意"直接开工
- **正确：** 只做当前批次 features.json 列出的工作；跨批次启动必须 Planner 裁决 + 用户确认两道门（commit 形式留痕）
- **边界：** "当前批次前置依赖"（如抽通用组件给后续 feature 用）可在当前批次 feature 范围内做，但必须在该 feature 的 spec acceptance 明示；不得新开无归属的灰色工作

**建议写入：** `framework/harness/harness-rules.md` 铁律补充（可选）：

**铁律 10：** 任何 spec-driven 工作必须有 features.json feature 号归属；无归属的代码修改 = 越界。

**状态：** 待确认
