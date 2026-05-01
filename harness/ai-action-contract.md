# AI Action Contract（aigcgateway / 类似 LLM 网关 集成规范）

> 来源：KOLMatrix B5 fixing-5/6 + MVP-internal-demo-prep fixing-3 累积经验。
> 本文件适用于通过 aigcgateway 或类似「prompt template + variables → JSON 输出」的 LLM action 集成。

---

## 1. Action 集成开工前必跑 dry-run + parser 双 shape 兼容

### 1.1 坑

KOLMatrix B5 F006 词云 + F006-fixing-5 case：

- Spec 文档说 action `kol-topic-extract` 输出 `{ keywords: [{term, weight}, ...] }`
- Generator 按 spec 写 parser：`parsed.keywords` → `normalizeKeywords(parsed.keywords)`
- 实际 prod 跑出来：`output` 字段是**裸 JSON 数组** `[{term, weight}, ...]`（无包装对象）
- 结果：`parsed.keywords` = undefined → normalizeKeywords([]) → 0 keywords → 走 fallback → empty state 永远渲染（看似正常但不出内容）

KOLMatrix MVP fixing-3 同类坑（commit 912fbc7）：

- Generator 实现 `customizeEmail` 时把 input 写成 `variables: { ... }` 包装，但实际 action 接受 `{ ... }` 直入（contract drift 反向）

### 1.2 真正可靠的开工流程

任何新 action 集成，**第一步不写代码，先 curl 看真 response**：

```bash
curl -X POST https://aigc.guangai.ai/v1/actions/run \
  -H "Authorization: Bearer $AIGCGATEWAY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "action_id": "<your_action_id>",
    "variables": { ...典型输入... }
  }' | jq '.'
```

观察 `output` 字段的真实形态：是字符串？JSON 对象？JSON 数组？带 markdown fence？嵌套层级几层？

**记录下来贴进 spec § Action 契约**，不可假设 spec 文档当前版本与 prod 一致。

### 1.3 Parser 双 shape 兼容范式

Parser 设计原则：**永远预期 shape 会漂移，写 parser 时同时接受多种合法形态**。

```typescript
// 反面：硬编码 shape，shape 漂移即崩
const parsed = parseFencedJson<{ keywords: Keyword[] }>(body.output);
return normalizeKeywords(parsed.keywords);  // ← undefined 时空数组

// 正面：双 shape 兼容
const parsed: unknown = parseFencedJson<unknown>(body.output);
const raw = Array.isArray(parsed)
  ? parsed                                              // 裸数组
  : (parsed as { keywords?: unknown } | null)?.keywords; // 包装对象
return normalizeKeywords(raw);
```

代价：parser 多 2 行，省下未来 fixing 1-2 轮（每轮 ~半天工时）。

### 1.4 Spec 起草 checklist（Planner）

新 AI action 集成功能的 spec 必含：

- [ ] action_id 列出且 prod 已 ready（dry-run PASS）
- [ ] action 真实 output shape 写入 spec（curl 实测，不要复制 console 文档）
- [ ] action variables 真实接受形态（包装 / 直入 / 数组）
- [ ] parser 设计明示「双 shape 兼容」（裸数组 vs 包装对象 等价处理）
- [ ] 失败 fallback 路径（5xx / timeout / parse 失败 → 友好状态，不可 silent 写空 cache）

---

## 2. AI Action timeout 起步 10s + CJK 内容 15s + fallback 不可 silent

### 2.1 坑

KOLMatrix B5 fixing-6 case：

- topic-cloud.ts 默认 timeout 5s
- 4/5 KOL（英/韩文标题）AI 回包 <2s 正常
- 1/5 KOL（日文，6 个标题 prompt token ≈ 606 + completion 155 ≈ 761 total）偶发踩到 5s 边界 → fail
- topic-cloud.ts 失败时返回 null 但**不写 cache** → 每次复访都重试都 timeout → cache 永远空 → empty state 渲染（不报错但功能不可用）
- 后续 staging 直接 SQL update pre-warm cache 才让 Reviewer 复验通过

### 2.2 真正可靠的 timeout 设置

**多字节语言（中/日/韩）+ 重 token 内容下，aigcgateway action P95 latency 可能 5-10s。** 5s 默认不够。

| 场景 | 推荐 timeout |
|---|---|
| 英文 / 短文本（< 100 token） | 5s 起步 |
| 一般业务（< 500 token） | **10s** 起步（默认值）|
| CJK / 长文本（≥ 500 token / 6+ 视频标题级别）| **15s** |
| 批量任务（一次多 prompt） | 30s + |

环境变量化（默认值锁 10s）：

```typescript
const AIGC_TIMEOUT_MS = Number(process.env.AIGC_TIMEOUT_MS ?? 10_000);
```

部署时若发现 P95 超过默认，可调高 env var 不动代码。

### 2.3 失败 fallback 不可 silent 写空 cache

**反模式：**

```typescript
try {
  const result = await fetchAction(...);
  await writeCache({ keywords: result });
} catch {
  await writeCache({ keywords: [] });   // ← 永久毒化 cache，下次还会读到空
}
```

**正模式：**

```typescript
try {
  const result = await fetchAction(...);
  await writeCache({ keywords: result, fetchedAt: now });
  return result;
} catch (e) {
  // 不写 cache，让下次访问重试；UI 层显示友好 retry CTA
  return null;
}
```

UI 层必须有：

- **Loading state** — 显示 "正在分析..." 而非空白
- **Error state with retry** — 失败时给用户「重试」按钮（不依赖刷新页面）
- **Cache hit fast path** — 成功结果 cache 7d / 24h（按数据时效性）

### 2.4 AIGC 月预算监控

aigcgateway 月预算（典型 $100）容易被批量任务 / 团队点 generate 消耗。每个新 action 集成的 spec 必含「月增量预估」段：

```
F006 wordcloud 调用频率：每个 KOL 详情页首访 1 次 / cache 7d
预估：每月活跃 KOL ~500 个 × $0.001/次 × 1.5 (cache miss 率) ≈ $0.75/月
余量：月预算 $100 - 现有支出 $50 = $50 充裕 ✅
```

不写预估 = 用户在 spec 阶段无法 sanity check 是否过度调用。

---

## 来源

- KOLMatrix B5-F006 fixing-5（output shape 漂移；commit 4d1057c）
- KOLMatrix B5-F006 fixing-6（timeout 5s 紧；commit ee45543）
- KOLMatrix MVP-internal-demo-prep F C-10 fixing-3（variables contract drift；commit 912fbc7）
- 用户 2026-05-01 决议：12 条 learnings 全部入 framework

---

## 版本历史

| 日期 | 修订 | 来源 |
|---|---|---|
| 2026-05-01 | 初版（§1 Action 集成 dry-run + parser 双 shape；§2 timeout 10s + fallback 不可 silent；§ 月预算监控） | KOLMatrix B5 fixing-5/6 + MVP fixing-3 |
