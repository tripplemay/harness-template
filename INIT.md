# INIT.md — 项目初始化引导（给 Claude Code 的一次性任务）

> 用户在 bootstrap.sh 执行完毕后，对 Claude Code 说「按 INIT.md 初始化项目」触发本流程。
> 本文件是一次性工件，流程完成后删除。

## 你要做什么

把 bootstrap.sh 铺好的占位符模板填充为可用的项目配置。**先收集信息 → 展示填充计划等确认 → 再动手写。**

## 第 1 步：交互式收集 6 项信息

用一次提问（可用选项卡形式）收集，已能从现有文件/目录推断的项直接给出推断值让用户确认：

1. **项目名 + 一句话描述** — 填 `CLAUDE.md §Project Overview`
2. **技术栈与常用命令**（dev / build / migrate / lint / typecheck / test）— 填 `CLAUDE.md §Commands`；若项目已有 package.json / Makefile 等，先读取推断再确认
3. **生产 / Staging 环境**（地址、服务器、部署方式；没有则填 "暂无"）— 填 `.auto-memory/environment.md`
4. **实例身份**：本机主实例名（如 Andy）；是否有独立 evaluator 实例（慢车道才需要，默认无）— 生成 `.agent-id`
5. **用户角色与偏好**（身份、技术背景、沟通语言与风格）— 填 `.auto-memory/user-role.md`
6. **生产测试策略**（`PRODUCTION_STAGE` / `PRODUCTION_DB_WRITE` / `HIGH_COST_OPS`；新项目默认 RND / DENY / DENY）— 填 `AGENTS.md §4`

## 第 2 步：展示填充计划，等用户确认

列出「文件 → 将写入的内容摘要」清单，用户确认后才执行。

## 第 3 步：执行填充

- `CLAUDE.md`：项目名、描述、Tech Stack、Commands
- `AGENTS.md`：端口、生产策略三值（无独立 evaluator 实例时保留占位符并注明"慢车道启用时填写"）
- `.auto-memory/project-status.md`：覆盖写为初始状态（当前批次：无；下一步：等待第一个需求批次）
- `.auto-memory/environment.md` / `user-role.md`：按收集信息填充
- `.agent-id`（不入 git）：
  ```
  main: [主实例名]
  evaluator: [独立 evaluator 实例名，无则省略此行]
  ```
- 确认 `.claude/hooks/*.sh` 有执行权限（bootstrap 已 chmod，验证即可）

## 第 4 步：git 初始化与首次提交

```bash
git init -b main          # 已是 git 仓库则跳过
git add -A
git commit -m "chore: bootstrap Triad Workflow v1.0 骨架 + 项目初始化"
```

确认 `.gitignore` 含 `.agent-id`。

## 第 5 步：清理与交接

1. `rm INIT.md`（本文件是一次性工件）
2. 提示用户后续手动步骤：
   ```
   git remote add origin git@github.com:USERNAME/REPO.git
   git push -u origin main
   ```
3. 告知用户：初始化完成，说「根据 harness 规则，开发 [第一个需求]」或直接 `/plan` 即可开始第一个批次。**新项目如含 UI，第一个批次必须是设计系统**（颜色 token、排版、基础组件、公共 hook、布局框架），不是第一个业务页面——见 `framework/docs/01-concepts.md` §经验教训。
