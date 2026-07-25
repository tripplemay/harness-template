# Transport: local-cli —— 本地异构 CLI 适配规范

> 编排者把一个阶段的活派给**本机另一个厂商的 CLI 子进程**（Codex / Gemini / …），
> 在机件 #7 沙箱内执行，凭产物取回结论。规范主文见 `harness/dispatch-mode.md`。
>
> **定位：** 这条 transport 提供的是**模型异构**，不是**地理异构**。跨机器、真异步、断线重订阅
> 属于 `transports/a2a.md`（接口预留，未实装）。

---

## 1. 一次派活的完整时序

```
编排者
 ├ 1. 解析 descriptor（.agents-registry.json）→ 确认 transport=local-cli、roles 含目标角色
 ├ 2. 组装信封 → validate-dispatch.sh envelope（字段白名单校验）
 ├ 3. sandbox-profile.sh --agent <id> --envelope <f>
 │     ├ worktree add --detach @sha        独立工作副本
 │     ├ env -i <白名单>                    没凭据就花不了钱
 │     ├ GIT_CONFIG pushurl=DISABLED       禁 push（env 级覆盖，不污染主仓 config）
 │     └ timeout <timeout_s> <argv>        wall-clock 封顶
 ├ 4. validate-dispatch.sh receipt run-meta.json    → 回执推断（§4）
 ├ 5. COMPLETED → 产物过 deliverable.schema → 机械回写状态机（铁律 12 原样）
 │   WAITING     → 硬停交人类
 │   FAILED/CANCELED → 凭 task_id 幂等重派，上限 1 次
 └ 6. generator 类：校验 commit tag 归属 → spec-lock critic 稽核 → 回流主仓（§6）
```

## 2. 信封投递（`envelope_delivery`）

| 值 | 做法 | 适用 |
|---|---|---|
| `stdin` | 信封 JSON 从标准输入喂给 CLI | 支持读 stdin 当 prompt 的 CLI（Codex 默认） |
| `argv` | 信封路径渲染进 argv 的 `{{envelope}}` 占位 | 只接受 `-p <file>` 类参数的 CLI |
| `env` | 仅靠 `HARNESS_ENVELOPE` 环境变量传路径 | CLI 有自己的 prompt 组装逻辑时 |

三种方式下 `HARNESS_ENVELOPE` / `HARNESS_ARTIFACT` / `HARNESS_BATCH` / `HARNESS_TASK_ID`
都会注入环境，适配器可任选其一读取。

## 3. 产物约定

对方**唯一**的交付义务是：在 worktree 内把产物写到 `deliverable.artifact` 路径，且满足
`deliverable.schema`。**不要求它读仓内任何指令文件**——契约随信封的 `contract` 字段走。

产物里的 `waiting` 字段是中断态的降维表达（一次性进程无法「挂起等你」）：

| `waiting` | 含义 | 编排者动作 |
|---|---|---|
| `null` / 缺省 | 活干完了 | 继续状态机 |
| `"auth"` | 撞 L2 边界（真实外部服务 / 计费 / 生产写入）而 `l2_authorized=false` | **硬停**，等用户授权 |
| `"adjudication"` | 规格歧义 / acceptance 无法客观判定 | **硬停**，转 pre-impl 审计 |

对方写完 `waiting` 后**正常退出**（exit 0），不要靠非零退出码表达「我需要人」——
那会被回执推断判成 FAILED 并触发无意义重派。

## 4. 回执推断表（`validate-dispatch.sh receipt` 的实现）

| 子进程情况 | 判定 | 后续 |
|---|---|---|
| exit 0 + 产物合 schema + `waiting` 空 | `COMPLETED` | 机械回写 |
| exit 0 + `waiting: "auth"` | `AUTH_REQUIRED` | 硬停 |
| exit 0 + `waiting: "adjudication"` | `INPUT_REQUIRED` | 硬停 |
| **exit 0 但产物缺失** | **`FAILED`** | 重派上限 1 次 |
| exit 0 + 产物 JSON 非法 / 不合 schema | `ARTIFACT_INVALID` | 重派上限 1 次 |
| 非零退出 | `FAILED` | 重派上限 1 次 |
| 超时（124/137） | `CANCELED` | 凭 `task_id` 幂等重派 |

**加粗那行是这张表存在的理由。** 退出码 0 不等于活干完了——外部 CLI「礼貌地失败」
（打印一段说明然后正常退出）是常态。不写死这条，礼貌失败会被当成验收通过。

重派上限 1 次后仍不过 → `evaluator_cannot_verify` / `generator_cannot_deliver` 硬停 + 通知，
**绝不静默无限重跑**（沿用 autonomous-mode.md §9 的同类约束）。

## 5. 沙箱四道锁（机件 #7）

见 `sandbox-profile.sh`。摘要：

| 锁 | 实现 | 拦住 |
|---|---|---|
| env 白名单 | `env -i` + descriptor 显式列名 | prod 凭据 / 部署 token / 他家 API key |
| 独立 worktree | `git worktree add --detach <sha>` | 污染工作区、并行互踩 |
| 禁 push | `GIT_CONFIG_*` env 级覆盖 `remote.origin.pushurl` | 直接改 main |
| wall-clock 封顶 | `timeout -k 10 <timeout_s>` | 跑飞挂死 |

⚠️ **禁 push 绝不能用 `git remote set-url`** —— worktree 与主仓共享 `.git/config`，
那样会把主仓的 push 地址一起改掉。必须用 env 级 config 覆盖（只影响子进程，不落盘）。

## 6. generator 类产物的回流（v1.1 放开外部 generator 后新增）

外部 generator 的 `constraints.push` 恒为 `false`，产物是 worktree 里的 commit。回流四步：

1. **tag 归属校验**：`feat(<batch>-F<num>):` 必须映射 `features.json` 真实条目（铁律 10）。
   外部 CLI 未必守这个格式 → 不合规就 rewrite tag 或拒收，不许带进主仓
2. **spec-lock critic 稽核**：跑机件 #2（`.claude/agents/spec-lock-critic.md`）比对 diff 与 scope，
   稽核时机从「writeback 前」前移到「拉回主仓前」
3. **L1 全绿**：`lint / tsc / test` 是外部 generator 唯一的硬证据——代码 diff 比 verdict 更好机械核验
4. 通过后由编排者 cherry-pick / merge 进 main 并统一 push

## 7. 新增一家 CLI 的核对清单

`adapters/<name>.json` 五个字段填完即可（schema 见 `agents-registry.schema.json` 的 adapter 段），
但**开车前必须逐条实测核对**，把 `_verified` 置 `true` 并记录 CLI 版本：

- [ ] `argv` 在当前 CLI 版本下语法正确（flag 名、`--cd` 语义、是否需要 `--yes/--yolo` 类免交互开关）
- [ ] 该 CLI 在 `env -i` 白名单环境下能正常启动（认证不依赖白名单外的变量）
- [ ] 非交互模式确实不会卡在 TTY 等待输入（否则只能靠 timeout 兜底，浪费一个封顶周期）
- [ ] 它写产物的路径与 `artifact_relpath` 一致
- [ ] 它撞 L2 时会写 `waiting` 而不是非零退出
- [ ] `sandbox.home_dir` 指向的专用 HOME 里已放好该 CLI 的认证

**首家（Codex）尚未端到端演练** —— `adapters/codex.json._verified = false`。
沿用 autonomous-mode.md §10「机件没建好不许开车」：核对未过不许接 autodrive。
