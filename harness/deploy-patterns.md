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

### 1.6 PM2 6.0.14 `env_file` 不可靠 anti-pattern

KOLMatrix B5 fixing-4 暴露：

- `ecosystem.config.js` 用 `env_file: /opt/<app>/.env.<env>` 字段
- 初次部署时 PM2 daemon 把 shell 环境变量（`source .env` 之后）作快照锁住
- **多次 `pm2 reload --update-env` / `pm2 restart --update-env` 后 env_file 不重读** —— 新增 env var 永远不进入 process env
- `/proc/<pid>/environ` 直接 dump 看不到新变量，但 .env 文件已含

**正确流程**（新增 env var 后）：

```bash
cd /opt/<app>
pm2 delete <app>                          # 不是 reload / restart
set -a && source .env.<env> && set +a     # 显式注入当前 shell
pm2 start ecosystem.config.js --only <app>  # PM2 从 shell 继承所有变量
sudo cat /proc/<NEW_PID>/environ | tr '\0' '\n' | grep <NEW_VAR>  # 验证
```

**spec 起草陷阱：** `ecosystem.config.js` 的 `env_file:` 字段名给人「PM2 会管」的强烈错觉。实际它只在初次 spawn 读一次。任何依赖「reload 自动注入新 env」的 runbook 都会踩。如果你的 deploy runbook 里写 `pm2 reload <app> --update-env`，**那是错的**，必须改成 delete + sourced-shell start。

---

## 2. VPS working tree 卫生 + artifact in-git 强制

### 2.1 两个关联 gap 的典型触发链

**Gap 1（严重）：** Reviewer 签收"在 VPS 上产出某 artifact"类 feature 时只核对"artifact 存在 VPS"，**未核对"artifact 是否 in git"**。BI3-F005 `scripts/cert-expiry-check.sh` 被 Generator 在 VPS 直接编辑创建，Reviewer 确认脚本存在 + cron + email 告警链路通后签收 PASS，**但脚本从未 commit 入 git**。86 行可执行代码活在 prod 单机 3 天，任何 re-deploy / 迁机器 / 灾后恢复都会丢失。

**Gap 2（工作区卫生）：** Generator 在 VPS SSH 直接编辑 `src/middleware.ts` 加 `console.log` 诊断 BI2-F002 的 UntrustedHost 问题后**未清理也未 commit**。3 天后 BAux1 触发 prod deploy，`deploy-prod.sh` 跑 `git checkout` 时被 working tree 冲突阻塞。

### 2.2 症状（如何知道坑了）

- `deploy-prod.sh` 在 "3/8 git fetch + checkout" 步骤失败
- 失败信息：`error: Your local changes to the following files would be overwritten by checkout` 或 `The following untracked working tree files would be overwritten by checkout`
- Deploy run 耗时不到 1 分钟（早 fail）
- VPS 上 `git status` 显示有 ` M` 或 `??` 文件

### 2.3 3 条防御规律

**规律 1（Reviewer 签收清单）：** Feature acceptance 写"在 VPS 上产出 X"时，**Reviewer 签收清单必须核对该 artifact 是否 `git ls-files` 能找到**：

```bash
ssh <vps> "cd /opt/<project> && git ls-files <artifact-path>"
# 应该输出该路径；空输出 = artifact 只活在 VPS 单点 = 拒绝签收
```

**规律 2（Generator + Planner 自律）：** VPS 上任何 `/opt/<project>` 内的 ad-hoc 编辑（SSH debug 改代码 / 临时加脚本）完成后必须：
- **要么 clean checkout 丢弃**（`git checkout -- <file>`、`rm <file>`）
- **要么 push 回 git**（`cd` 本地 repo → edit → commit → push → VPS `git pull`）
- 不允许长期保留 working tree 脏态（超过本次 debug session）

**规律 3（deploy-prod.sh 前置 check）：** 部署脚本加 `git status --porcelain` early fail：

```bash
# 在 scripts/deploy-prod.sh step 1 "记 prev-sha" 之前加：
STATUS=$(git status --porcelain)
if [[ -n "$STATUS" ]]; then
  echo "❌ VPS working tree not clean, aborting:"
  echo "$STATUS"
  exit 1
fi
```

Early fail 好过 step 3 失败时备份已跑一半 + 状态难清理。

### 2.4 Reviewer 签收新 checklist 模板

涉及 VPS 产出的 feature，L1 自动化验收之后补一步：

| 检查项 | 命令 | 期望 |
|---|---|---|
| artifact 存在 VPS | `ssh … "ls -la <path>"` | 文件存在 + 权限合理 |
| **artifact 在 git tracked** | `ssh … "cd /opt/<project> && git ls-files <path>"` | **输出非空**（该路径在 git index 中）|
| artifact 与 git 版本一致（可选）| `ssh … "cd /opt/<project> && git diff <path>"` | 空输出（无 diff）|

前两项**必检**，第三项可选（如果 VPS 有合法本地改动等待 push）。

### 2.5 Planner spec 起草期的 counter-check

涉及 VPS 部署 / 脚本 / cron 的 spec acceptance 写作时，**必须**包含以下 2 类验收项：

```
- [ ] 脚本 / config file 在 git tracked（`git ls-files <path>` 非空）
- [ ] VPS 上 artifact 与 git 版本 byte-identical（或明确声明允许 drift）
```

仅写"VPS 上脚本存在"是不够的 —— 这会让 Reviewer 走短路径签收。

---

## 3. Staging/Prod deploy 完整链 checklist（schema + 数据回填一并验）

### 3.1 坑

KOLMatrix B5 fixing-2 → fixing-3 → fixing-7 + MVP fixing-2 累积暴露：

- **fixing-2**（commit cfd9c1e）：staging DB 缺 F001 migration → 三页 P2022 ColumnNotFound on `kol.channel_created_at`。F001 commit 时 migration 文件入了 git，但 staging deploy 步骤里没列 `npx prisma migrate deploy`。
- **fixing-3**（commit 3066551）：staging F002 enrich 历史从未跑 → 5/5 抽样 KOL banner/age/videoCount 全空。F002 commit 时脚本入了 git，但 staging deploy 没跑 `npm run enrich:kol-youtube`。
- **fixing-7**（commit ec9340b）：staging /api/health.git_sha = 之前的 chore commit ee45543，本地 HEAD = e493ab4 → Reviewer 严卡 SHA 对齐。e493ab4 仅是 chore(state) progress.json 改动 paths-ignore，不会触发自动 staging deploy。
- **MVP fixing-2**：staging seed 漏 KolCampaign rows + KOL.email → C-10 outreach 不可用（看似 prod redeploy 完成实际数据未到位）。

共同 root cause：**「spec 里写了脚本/migration 入 git」≠「staging 实际跑通」**。runbook 不显式列每一步 = 必踩。

### 3.2 完整链 checklist

任何批次 status `building → verifying` 切换前，Generator 必须按下面顺序在 staging VM 跑通；缺任何一步 = 拒切：

```bash
# 1. SSH 进 staging（KEX 设置见 environment.md）
ssh tripplezhou@<staging-ip>

# 2. 拉代码到 deploy 路径
cd /opt/<app>-staging
git pull --ff-only origin main

# 3. 装依赖（npm ci 而非 install，保锁版）
set -a && source .env.<staging> && set +a
npm ci --include=dev

# 4. ⚠️ Schema 迁移（必跑，即便本批次没改 schema 也跑 — 防漏）
npx prisma migrate deploy

# 5. ⚠️ 数据回填脚本（如本批次含 enrich/seed）
npm run db:seed                     # 或 npm run enrich:kol-youtube 等
# 如批次含数据回填脚本，spec § 必须显式列脚本名

# 6. Build（注意 OOM）
NODE_OPTIONS='--max-old-space-size=4096' GIT_SHA=$(git rev-parse --short HEAD) npm run build

# 7. PM2 重启（按 §1 anti-pattern：必须 delete + sourced-shell start）
pm2 delete <app>-staging
pm2 start ecosystem.config.js --only <app>-staging

# 8. 验证 SHA 对齐
curl -sS https://staging.<domain>/api/health | jq .git_sha
# 必须等于 git rev-parse --short HEAD

# 9. 抽样验证数据（如本批次含 enrich/seed）
psql ... 'SELECT COUNT(*) FROM <table> WHERE <new_col> IS NOT NULL'
# 抽 5 个白名单 ID 在浏览器走查
```

### 3.3 Spec 起草期 checklist 对应（Planner）

每条 spec § "staging deploy 步骤" 必含：

- [ ] `prisma migrate deploy`（不论本批次是否改 schema）
- [ ] 数据回填脚本名 + 抽样验证条件（如含数据填充）
- [ ] `pm2 delete + sourced-shell start`（不要写 reload）
- [ ] `/api/health.git_sha = HEAD` 验证步骤
- [ ] Planner 提供白名单 ID 给 Reviewer 抽样（防 BL-012-style 数据池污染）

### 3.4 chore(state) commits 不触发 staging deploy + Reviewer SHA 严收紧的边界

`chore(state)` / `chore(planner)` / `test(...)` 类 commits 本质是状态机维护文件改动（progress.json / .auto-memory / docs/test-reports/），paths-ignore 配置使其**不触发** staging/prod deploy（设计如此，避免无意义重 build）。

**但 Reviewer 严收紧 SHA 对齐时**，本地 HEAD = chore commit、staging git_sha = 上一个 prod commit → 误判 mismatch。

两种处理（按情境选）：

- **(a) Planner 主动同步 SHA**：chore commit 后 Planner 自己 SSH staging 跑 §3.2 步骤 6-8（build + pm2 + SHA 验证），把 staging SHA 推齐到 chore HEAD。
- **(b) Reviewer 签收规则容许 chore-only 差异**：white-list SHA-1...SHA-2 区间内仅 paths-ignore matched 的差异 = 等价部署（见 `evaluator.md` "SHA 对齐严收紧的边界"）。

**默认推 (a)** —— 简单、无歧义、不需要 Reviewer 自己判 paths-ignore 范围。

---

## 4. Visual baseline regen 注意事项

### 4.1 GITHUB_TOKEN push 不触发下游 workflow

KOLMatrix B5 F006 case（commits 14ea522 / 172c2df / 5b2f622）：

- `update-visual-baselines.yml` workflow 跑完 → 用 GITHUB_TOKEN 推 commit 把新 baseline 入 git
- GitHub 默认 policy：**用 GITHUB_TOKEN 推的 commit 不触发其他 workflow**（防 infinite loop）
- 结果：visual baseline 重生后 visual regression CI 没跑 → 没人知道 baseline 是否真匹配 → 后续 PR 跑 visual regression 才发现 baseline still off

**解决方法：** baseline regen workflow 之后**必须跟一个 real-content commit 触发下游 CI**。空 commit 不够（paths-ignore matches all 时 CI skip）。

### 4.2 Spec / Generator checklist

任何 feature 改 UI layout（dashboard / discovery / detail / login 等）= 必有 visual baseline 重生：

- [ ] feature 改 UI 后 commit + push 触发 PR → visual regression workflow 失败（baseline mismatch 是预期的）
- [ ] 跑 `update-visual-baselines.yml` workflow → baseline 入 git（用 GITHUB_TOKEN）
- [ ] **跟一个 real-content commit**（如 `chore(visual): regenerate baselines via update-visual-baselines workflow` + 一行任意修改）触发 visual regression workflow 跑通
- [ ] 验证 visual regression workflow 全绿才算 baseline 真匹配

### 4.3 Visual test 选择器要 deterministic

KOLMatrix B5 F006 case：

- `firstCard = .first()` 选择器依赖默认排序，遇到平台条件渲染（recent videos / topic cloud 仅 youtube KOL 有）变成 flake
- 应改：`page.locator('[data-kol-platform="youtube"]').first()` — 显式锚点

任何条件渲染的 UI 元素，visual test 必须用 stable data-attribute 锚点而非位置 selector。

---

## 来源

- KOLMatrix BI2-F002 两轮重裁决 + Round 2 实测证伪（2026-04-20）
- KOLMatrix BI3-F005 脚本未入 git + BAux1 deploy 失败（2026-04-23）
- KOLMatrix B5 fixing-2/3/4/6/7（schema migration / enrich / PM2 env_file / timeout / SHA 对齐 多坑，2026-04-30 ~ 2026-05-01）
- KOLMatrix MVP-internal-demo-prep fixing-1/2/3（KolCampaign+email seed gap / SHA mismatch / aigcgateway contract drift，2026-05-01）
- 裁决文档：`docs/specs/BI2-f002-zero-downtime-fix.md` v2
- 交接文档：`docs/specs/BI2-f002-round2-adjudication.md`
- 修复 commits：`ba11e6b` / `bc1de3b` / `4f86fc0`（salvage cert-expiry-check.sh）/ `cfd9c1e` / `3066551` / `4d1057c` / `ee45543` / `ec9340b` / `8cd80f2` / `912fbc7`

---

## 版本历史

| 日期 | 修订 | 来源 |
|---|---|---|
| 2026-04-20 | 初版沉淀（§1 PM2 zero-downtime 3 条件 + Next.js custom server 路径）| KOLMatrix BI2-F002 两轮证伪 |
| 2026-04-23 | §2 VPS working tree 卫生 + artifact in-git 强制（3 条规律 + Reviewer checklist）| KOLMatrix BI3-F005 签收漏 + BAux1 deploy 失败 |
| 2026-05-01 | §1 扩展 PM2 6.0.14 env_file anti-pattern；§3 完整链 checklist（schema + enrich + SHA 对齐边界）；§4 Visual baseline regen 注意事项 | KOLMatrix B5 7 轮 fixing + MVP-internal-demo-prep 3 轮 fixing 累积 |
