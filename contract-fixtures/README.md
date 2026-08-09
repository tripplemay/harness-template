# contract-fixtures —— 跨仓契约的机器可校验金标（TEST-ONLY）

> **状态：v1.8.0 引入。** 来源：tokenizer BL-REPO-MECH（keep-separate 裁决的「三件增量机械化」第一件）。
> 消费方：任何通道 B 控制台实现（tokenizer 是第一个）在自己的 CI 里 checkout 本仓
> `harness.json.framework.commit` 钉住的版本，对这份金标跑双向契约测试——服务端签发物过本仓验签器、
> 本仓 fixture 灌进服务端解析器。契约两侧从此没有绿灯合不进任何一侧。

## 内容

| 路径 | 内容 |
|---|---|
| `canonical-json/vectors.json` | 规范化 JSON 的字节级向量（递归键排序 · 紧凑分隔符 · `ensure_ascii=False` · UTF-8）。**含中文/emoji 用例**——非 ASCII 不转义是契约的一部分（`validate-pending-gate.sh` 与 Node `canonicalJson` 两侧都以此为准） |
| `pending-gate/{valid,invalid}/` | 完整 `pending_gate` 块，decision 带金标 Ed25519 签名。invalid 覆盖：**签名后篡改 scope（once→永久的历史攻击）**、坏签名、缺签名、陈旧 gate_id、白名单外字段 |
| `mode-intent/{valid,invalid}/` | `harness.json.project.mode_defaults` 块（v2 fast profile，签名/形状/白名单面）。invalid 覆盖：签名后篡改、缺签名、白名单外字段、autonomy off 携带多余字段 |
| `keys/` | **TEST-ONLY** Ed25519 密钥对——金标可复算、可验证的前提。**绝不可用于任何真实项目**（真实项目的 `console.pub` 由 `gen-console-key.sh` 各自生成） |
| `fixtures.json` | 清单：framework_version（须等于根 `VERSION` 与发布清单末项）、两个 schema 的快照 sha256、文件枚举 |
| `make-contract-fixtures.py` | 再生成器。给定已提交的密钥对，输出逐字节确定 |

## 校验

```bash
python3 scripts/validate-contract-fixtures.py   # 用真机件逐 fixture 重放（CI 同款）
python3 tests/test-contract-fixtures.py         # 负向：篡改任何一处必须翻红
```

`release-contract.yml` 在 push/PR 时同时跑两者；`fixtures.json` 的版本与 schema 快照锚定使
「改 schema 不重生成 fixture」「发版不重打 fixture 版本戳」都在 CI 阶段被拒。

## 刻意的取舍（勿当缺陷修）

- **valid fixture 的有效期取一个世纪后（2126）**：静态金标不得依赖墙钟——「过期拒收」这类
  时间性行为由 `templates/claude/console/test-*.py` 的动态用例覆盖，不属于本目录职责。
- **mode-intent 只有 fast profile 的 valid 用例**：本目录钉的是**签名/规范化/白名单**契约面；
  heterogeneous/slow 的 registry 解析保真度由 `test-mode-intent.py` 动态覆盖（它们依赖
  adapter 目录与候选池，不适合静态化）。
- **密钥轮换**：删除 `keys/` 两文件后重跑 `make-contract-fixtures.py` 即整套重签。
