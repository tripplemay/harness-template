# CLAUDE.md

> 给 Claude Code (`claude`) 启动时读取的上下文。

---

## 这个 repo 是什么

这是 **Triad Workflow 框架的源码 repo**（`tripplemay/harness-template`）。

- **不是** 一个使用 Triad Workflow 的项目
- **不走** 状态机（没有 `progress.json` / `features.json` / `backlog.json`）
- **不需要** `.auto-memory/`、`.agent-id`、角色文件
- 它本身是"被使用"的对象，不是"正在使用 Triad Workflow"的主体

完整介绍见 [README.md](README.md)，贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 常见操作

### 编辑框架规则 / 文档
- `harness/*.md` — 状态机规则 + 三个角色指令
- `docs/01~04-*.md` — 用户文档（概念 / 用法 / quickstart / 接入指南）
- `docs/imgs/*.svg` — 三张 SVG 图
- `templates/*.md` + `templates/features.template.json` — 项目初始化模板
- `memory/*.md` + `memory/role-context/*.md` — `.auto-memory/` 的模板

### 改 bootstrap 脚本
- `bootstrap.sh` — greenfield 新项目用（覆盖式）
- `bootstrap-adopt.sh` — 现有项目接入用（非破坏性）
- 改后在临时目录测试，细节见 CONTRIBUTING.md §本地开发

### 发布新版本
- 更新 `CHANGELOG.md`（新条目在**顶部**）
- Commit：`chore(framework): release vX.Y.Z — 副标题`
- `git push origin main`
- 打 tag：`git tag vX.Y.Z && git push origin vX.Y.Z`
- 版本号策略（SemVer-ish）见 CONTRIBUTING.md

### 从 aigcgateway 同步经验
- 用户会告诉你 aigcgateway 积累的 proposed-learnings
- 逐条判断是否"通用"（见下方规则），通用的写入对应文件
- CHANGELOG 加新版本条目 + commit + push + tag

---

## 编辑前的唯一铁律

**提问自己：这条规则是通用的（对所有项目有效），还是只对某个项目有效？**

- 通用 → 沉淀到本 repo（写入 `harness/*.md` 或 `docs/*.md`）
- 项目特定 → 不沉淀。让提案发起人放回项目自己的 `.auto-memory/` 或记在项目文档里

**举例：**
- ✓ 通用："Planner 写 spec 涉及代码细节时必须 Read 源码核实"
- ✗ 项目特定："火山引擎 API 调用必须传 ep-xxx 而非模型名"（这是 aigcgateway 的接入知识）

判断不了时，询问用户，不要擅自决定。

---

## 不做的事

- **不要**把本 repo 当作 Triad Workflow 项目去创建 `progress.json` / `.auto-memory/`
- **不要**自动写 regression test（本 repo 几乎没有可运行代码，主要是文档和 shell 脚本）
- **不要**未经用户确认就打新 tag / 发布新版本
- **不要**改变 Triad Workflow 的核心身份（三角色分离 / 无自评 / 状态机驱动）—— 这是产品身份，改之前一定要和用户深度确认

---

## 辅助信息

- **GitHub URL:** https://github.com/tripplemay/harness-template
- **维护者:** tripple (tripplezhou@gmail.com)
- **最大下游用户:** `tripplemay/aigcgateway`（通过 dogfooding 验证框架）
- **分发方式:** `npx degit tripplemay/harness-template my-project`

---

## 工作语言

中文为主（用户偏好）。写入 repo 的代码注释、commit message、CHANGELOG、文档以中文为主；脚本里的 echo 和 bash 注释可以双语或英文。
