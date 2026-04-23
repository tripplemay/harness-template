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

## [2026-04-23] Planner (Kimi) — 来源：BI3-F005 + BAux1 deploy 失败（2026-04-23）

**类型：** 新坑 + 签收流程补丁（合并 2 个关联 gap）

**内容：**

**Gap 1（签收严重漏）：** Reviewer 签收"VPS 上产出某 artifact"类 feature 时只核对"artifact 存在 VPS 上"，**未核对"artifact 是否 in git"**。BI3-F005 的 `scripts/cert-expiry-check.sh` 被 Generator 在 VPS 直接编辑创建，Reviewer 确认脚本存在后签收通过，但脚本**从未 commit 入 git**。86 行可执行代码活在 prod 单机，任何 re-deploy / 迁机器 / 灾后恢复都会丢失。3 天后 BAux1 触发 prod deploy 才因 git checkout 冲突暴露此漏。

**Gap 2（工作区卫生）：** Generator/Planner 在 VPS SSH 直接编辑 `src/middleware.ts` 加 debug log 诊断问题后**未清理也未 commit 回本地**。3 天后 `deploy-prod.sh` 跑 `git checkout` 时被 working tree 冲突阻塞。

**规律总结：**
1. Feature acceptance 写"在 VPS 上产出 X"时，Reviewer checklist 必须加一行："该 artifact 是否 `git ls-files` 能找到？"
2. VPS 上任何 `/opt/kolmatrix` 内的 ad-hoc 编辑（SSH debug 改代码 / 加脚本）完成后必须：**要么 clean checkout 丢弃、要么 push 回 git**。不允许长期保留 working tree 脏态。
3. `deploy-prod.sh` 应前置 `git status --porcelain` 检查，如非空直接拒绝部署（early fail 好过 checkout 半路失败）。

**建议写入：**
- `framework/harness/deploy-patterns.md` 新增 §2 "VPS working tree 卫生 + artifact in-git 强制"（含 3 条规律 + checklist 模板）
- 同步更新 `role-context/evaluator.md` 签收清单（新增一条 `git ls-files` 核对）

**建议同步动作：**
- `scripts/deploy-prod.sh` 加 git status 前置 check（BI2 F003 范畴，可作为 hotfix 后续加）
- Reviewer 下次签收类似"VPS 产出"feature 时应用此 checklist

**状态：** 待确认
