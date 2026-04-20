# Deploy Patterns（框架沉淀）

> 跨批次通用的生产部署 / 运行时进程管理 / 反向代理模式。Planner 在写涉及 deploy / PM2 / process management / nginx 的 spec 时必读。

---

## 1. PM2 cluster zero-downtime reload 的 3 个必要条件

### 1.1 坑

`pm2 reload` 做到"零丢包"**不是** "cluster mode + instances ≥ 2" 自动拥有的能力。常见的错误假设（BI2 Planner v1 犯过）：

> "PM2 cluster 会 hijack `listen` 调用，let master 代为分发端口；两个 instance 滚动替换即 zero-downtime。"

这只在"worker 进程是 PM2 的直接子进程 + app 主动发 ready 信号"时成立。KOLMatrix BI2-F002 两轮实测证伪该假设：

- **Round A**: `script: "npm", args: "start"` + `instances: 2` → `npm` 是 PM2 直接子进程，但 `npm` 再 spawn 孙子 `next`；`cluster` 模块只 hook 直接子进程的 `listen()`，孙子 `server.listen(3001)` 直接走 OS 端口 → **EADDRINUSE crash loop 116×**
- **Round A'**: `script: "node_modules/next/dist/bin/next"` 直连 + `instances: 2`（绕过 npm 双层进程）→ cluster hook 生效，两 worker 稳定，但 **60× curl + reload 只有 56/60 = 93%**（4× 超时），原因：没有 `process.send('ready')` 信号，PM2 走 `listen_timeout` 默认 3s 估算，new/old worker 切换窗口重叠 2-3s

### 1.2 真正 zero-downtime 的 3 个必要条件

**条件 1 — worker 是 PM2 直接子进程：**

不能用 `npm start` / `yarn start` / shell wrapper 脚本。PM2 fork/spawn 出来的**第一层**进程必须就是 app 进程。

**条件 2 — app 主动发 `process.send('ready')` 信号：**

在 `server.listen(port, callback)` 的 callback 里发 ready。PM2 靠这个信号精确感知"新 worker 已 accept 连接"，才去 SIGTERM 老 worker。没有此信号，PM2 只能用 `listen_timeout` 做超时估算，切换窗口重叠。

**条件 3 — `ecosystem.config.js` 配 `wait_ready: true` + 合理 `listen_timeout`：**

```js
{
  name: 'app',
  script: 'server.js',        // 条件 1：直接 JS 入口
  exec_mode: 'cluster',
  instances: 2,
  wait_ready: true,            // 条件 3：告诉 PM2 必须等 ready 信号
  listen_timeout: 10000,       // 10s 上限，Next cold start ~450ms 绰绰有余
  kill_timeout: 5000,          // SIGTERM 后给 drain in-flight 请求 5s
}
```

### 1.3 Next.js 生产部署的唯一可靠路径

对 Next.js `production build`，**唯一**同时满足 3 个条件的方式是 custom `server.js`：

```js
// server.js (~22 行)
const { createServer } = require("node:http");
const next = require("next");

const port = Number(process.env.PORT) || 3001;
const hostname = process.env.HOSTNAME || "0.0.0.0";
const app = next({ dev: false });
const handle = app.getRequestHandler();

app.prepare().then(() => {
  const server = createServer((req, res) => handle(req, res));
  server.listen(port, hostname, () => {
    console.log(`[server] listening on ${hostname}:${port}`);
    if (process.send) {
      process.send("ready");   // ← 条件 2：ready 信号
    }
  });

  for (const sig of ["SIGINT", "SIGTERM"]) {
    process.once(sig, () => {
      console.log(`[server] ${sig} received, closing connections`);
      server.close(() => process.exit(0));
    });
  }
});
```

该方式不失去任何 Next.js 特性（middleware / instrumentation.ts / app router / React 19 / server actions 全兼容）。丢失的只有 Turbopack dev 优化（dev 不用 server.js，跑 `next dev`）。

### 1.4 Planner spec 起草期检查清单

涉及 PM2 deploy 的 spec（BI2 F002 / BI3 F003 staging / B5+ worker 进程等），Planner **必须**核对：

- [ ] `script:` 是否指向**可执行 JS 文件**（非 `npm` / `yarn` / shell wrapper）？
- [ ] app 代码里是否有 `if (process.send) process.send('ready')`？（custom server 或 instrumentation.ts）
- [ ] `ecosystem.config.js` 是否配 `wait_ready: true`？
- [ ] `listen_timeout` 是否与 app 实际冷启动时间匹配（prod Next.js ~500ms，设 10s 有余量）？
- [ ] `kill_timeout` 是否足够 drain in-flight 请求（Next.js SSR 默认 1.6s 短，改 5s）？
- [ ] Acceptance 写"reload 0 掉包"时，是否附"60× curl 叠加 reload + 两 worker uptime 交错"两条可证伪指标？

### 1.5 反面案例（BI2 Planner v1 路径，已作废）

| 假设 | 结果 |
|---|---|
| `npm start` + cluster + instances=2 自动 zero-downtime | EADDRINUSE crash loop |
| `next` 直连 + cluster + instances=2（无 wait_ready）自动 zero-downtime | 93%（2-3s 窗口丢包） |
| fork mode + `increment_var: PORT` + nginx upstream | 架构更散，仍需 wait_ready，nginx 成状态依赖，不推荐 |

---

## 来源

- KOLMatrix BI2-F002 两轮重裁决 + Round 2 实测证伪（2026-04-20）
- 裁决文档：`docs/specs/BI2-f002-zero-downtime-fix.md` v2
- 交接文档：`docs/specs/BI2-f002-round2-adjudication.md`
- 修复 commits：`ba11e6b`（custom server.js）+ `bc1de3b`（eslint-disable）

---

## 版本历史

| 日期 | 修订 | 来源 |
|---|---|---|
| 2026-04-20 | 初版沉淀（§1 PM2 zero-downtime 3 条件 + Next.js custom server 路径）| KOLMatrix BI2-F002 两轮证伪 |
