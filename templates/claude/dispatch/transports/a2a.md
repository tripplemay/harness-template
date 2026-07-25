# Transport: a2a —— 跨机器 / 跨组织（接口预留，**未实装**）

> **状态：未实装。** 本文件锁定接口形状，使将来接上时只改一个 transport 实现，
> 不动 descriptor / 信封 / 状态机 / 回执语义。
>
> 依据：A2A 协议 v1.0（Linux Foundation, Apache 2.0）研究结论，
> `docs/a2a-harness-research-2026-07-25.md`。

---

## 1. 为什么现在不做

- **local-cli 已覆盖模型异构。** A2A 额外提供的是**地理异构 + 真异步 + 断线重订阅**；
  单机场景下这些是负资产（研究结论：单机单人跑 OAuth/mTLS 基建为负资产）。
- **对端稀缺。** Claude Code / Codex / Gemini CLI 都是一次性进程，不是 HTTP server。
  接 A2A 需要为每家写 runner shim（A2A server 包 CLI），今天现成的对端 ≈ ADK 系。
- **协议尚年轻。** v1.0 刚发布，预期仍有 breaking change。把协议细节封在单个 transport 实现里，
  是对这个风险的结构性隔离。

## 2. 语义映射（已在 v1.1 提前落地，无需等实装）

harness 已经借用了 A2A 的这些语义，local-cli 上就在用：

| A2A 机制 | harness 落点 | 状态 |
|---|---|---|
| Agent Card（provider / skills / security） | `.agents-registry.json` descriptor | ✅ 已实现（L1） |
| `Artifact` 与 Message 强制分离 | `deliverable.artifact` 落盘 + 消息只传指针 | ✅ 已实现（L2） |
| `INPUT_REQUIRED` / `AUTH_REQUIRED` | 产物内 `waiting: adjudication\|auth` | ✅ 已实现（降维版） |
| 幂等键（at-least-once 投递） | `task_id` | ✅ 已实现 |
| required profile extension | `contract_version: harness/1.1` | ✅ 已实现 |
| Opaque Execution | 信封只传 repo ref + 路径，对方自行取证 | ✅ 已实现 |
| taskId 重订阅 / 长任务续接 | — | ⬜ 待 A2A |
| 服务端推送（webhook / SSE） | — | ⬜ 待 A2A |
| 签名 Card（RS256 JWS）验真 | — | ⬜ 待 A2A |

**这张表是本次升级的核心杠杆：** 真正需要协议栈的只有最后三行；前六行的价值
不依赖 A2A 实装就已兑现。

## 3. 实装时的接口约定（改这些，不改别的）

```jsonc
// descriptor
{ "id": "reviewer-adk", "transport": "a2a", "model_family": "gemini",
  "endpoint": "https://…",          // Agent Card 在 <endpoint>/.well-known/a2a-agent-card
  "auth": { "type": "bearer", "env": "A2A_REVIEWER_TOKEN" } }
```

- 编排者实现 **A2A client**，对端是 server；**hub 形态，状态机永远在编排者手里**
  （A2A 是点对点委托，无全局工作流概念；链式转委托无人持有全局真相）
- 任务载荷 = 同一份 `dispatch-envelope.json`（一份信封三种 transport）
- 状态映射：`WORKING`=执行中 · `INPUT_REQUIRED`/`AUTH_REQUIRED`=硬停 ·
  `COMPLETED`+Artifact=产物落盘 · `REJECTED`=拒收 spec · `FAILED`/`CANCELED`=凭 `task_id` 重派
- 回执推断表（local-cli.md §4）直接复用——A2A 的 8 态是它的超集，映射后语义一致
- 第一版建议：**loopback / 局域网 + Bearer token，不上 OAuth/mTLS**

## 4. 实装前必须先解决

- 每家一个 runner shim（A2A server → fork CLI → 退出码/产物映射回 8 态）——这是主要工作量
- 机件 #7 沙箱在远端失效：跨机器时沙箱责任转移到对端，需要契约层声明与验证手段
- A2A 扩展注册生态、错误恢复细节（Resume Agents）文档仍薄弱，试点前需实测
