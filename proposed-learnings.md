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

## [2026-04-20] Claude CLI（johnsong）— 来源：BI3-F005 Resend 发件域实测

**类型：** 新坑 / 文档与实际状态分歧

**内容：** `.auto-memory/environment.md` 标注发件地址为 `marketer@send.kolquest.com`，但 Resend API 实测：`send.kolquest.com` 子域未作为独立 domain 加入 Resend（curl 返回 403 validation_error），而 `kolquest.com` 根域已 verified + sending enabled + region=ap-northeast-1。实际可用发件地址是 `marketer@kolquest.com`。F005 脚本已按实测值写入，但 environment.md 仍是旧值，BI4+ 接入邮件的人会踩坑。

**建议写入：** `.auto-memory/environment.md`（Planner 维护）更正发件地址为 `marketer@kolquest.com`，或补充说明 send.kolquest.com 的 MX 是收件路径、发件用根域。

**状态：** 待确认
