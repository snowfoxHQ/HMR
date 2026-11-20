# HMR 借鉴 MemoraX Code 基准方案

> 分析对象：`memorax-code-main.zip`（MIT，TypeScript/Node，809 文件）
> 结论日期：2026-11-21
> 状态：P0–P3 与 S1–S3 均已完成（2026-11-21），P4/P5 暂缓
> 补充批次 S1–S3：依据 MemoraX 自动写回测试审计结论冻结，聚焦写入可信性与持久化可靠性

## 一句话原则

借鉴 MemoraX 的**记忆边界与写入治理**，不借鉴它的云端检索与 IDE 适配生态；HMR 已有的向量召回、JIT、SM-2、演化引擎保持不动。

## 来源机制对照

| MemoraX 机制 | 实现位置 | HMR 现状 | 处理 |
|---|---|---|---|
| 四类边界 Coding/Repo/Personal/Procedure | README 267-274 | 仅有 9 类 `type`，无边界/作用域 | P0 借鉴 |
| `CODE_AGENT_MEMORY` 11 字段卡片 + 已验证门槛 | `references/memorax-add.md:46-82` | metadata 被 `ingest()` 丢弃 | P1 借鉴 |
| Preference schema + 冲突规则 + 原子写 | `personal-memory/user-profile.ts` | 无用户画像层 | P2 借鉴 |
| Procedure topic 文件 + cadence 注入 | `hooks/memory-skill-reminder-policy.mjs` | 无 | P2 借鉴 |
| Trace JSONL / 幂等 / 脱敏 / 7 天保留 | `src/trace/store.ts` | 仅 `get_system_status()` | P3 借鉴 |
| Repo Memory wiki + git delta | `src/repo-memory/detect-updates.ts` | `MemoryGraph` 不含代码结构 | P4 暂缓，先与 HKC 划界 |
| 自动写回管线 | `src/memory/automatic-writeback.ts` | 无 turn 事件源 | P5 暂缓，等接入点确定 |
| 云端 dense+sparse / Jev judge / npm 适配 | `provider/memorax`, `provider/jev` | HMR 自有更强检索 | 不借鉴 |

## 阶段计划

每阶段独立可测、回归通过后立即提交，不攒批。

| 阶段 | 内容 | 估算 | 状态 |
|---|---|---|---|
| P0 | `MemoryObject` 增加 `boundary/scope/source/evidence/status`；`ingest()` 透传完整 metadata；Policy 增加边界判定 | 1.5 人日 | 已完成 |
| P1 | `hmr/engines/memory_card.py`：11 字段解析/渲染/校验 + 验证门槛 | 2 人日 | 已完成 |
| P2 | `hmr/personal/`：`profile.py` / `procedure.py` / `context.py`，首轮 + 5 轮 cadence | 3 人日 | 已完成 |
| P3 | `hmr/observability/trace.py`：JSONL、event_id 去重、metadata-only、脱敏、保留期 | 2 人日 | 已完成 |
| P4 | Repo Memory 轻量版（仅本地 git，需先确认 HKC 边界） | 3–4 人日 | 暂缓 |
| P5 | 自动写回（需先确认 turn 源） | 3–5 人日 | 暂缓 |
| S1 | 存储一致性：文件优先写入 + 失败回滚、孤儿向量防御、删除三处同步、启动反向对账 | 2 人日 | 已完成 |
| S2 | 写入可信性：来源身份、作用域校验、写前脱敏、单进程幂等去重 | 3 人日 | 已完成 |
| S3 | 写入恢复：Pending accepted/persisted/failed、Retry 退避、重启恢复、ThoughtChain 洞察补偿 | 3.5 人日 | 已完成 |

P0–P3 约 8.5 人日；S1–S3 约 8.5 人日（1 人日 = 6h 有效编码 + 自测）。

## 写入可靠性补充批次（S1–S3）

依据 MemoraX 自动写回测试审计结论，把三处未充分证明的边界转成 HMR 的强制验收项：

1. 普通写入也要有崩溃恢复测试，不只依赖某客户端专属机制；
2. 最终可检索性必须端到端验证（`ingest → recall`），不能只验证写入 API 返回成功；
3. 去重保证分层声明并分别测试：单 Runtime、单进程、多进程，达标到哪层写清楚。

边界：只做到单 Runtime / 单进程幂等；不做 transcript 抓取、多客户端 Hook、云端全局幂等。

## 硬边界

1. 不接 MemoraX 云、不引入 Node/npm 依赖、不新增第三方包（保持 `pydantic` + `numpy`）。
2. 不新建 embedding 模型或 LLM client；复用 `VectorStore.EmbeddingProvider`，如需共享模型先确认 HKC `get_st_model` / `encode_cached`。
3. 不触碰 `mini/` 目录（mini/gateway 工作已 parked）。
4. 所有新增字段对旧数据向后兼容，缺省值保证旧 JSON 可直接读入。
5. 每阶段跑 `test.py`、`verify.py` 后单独 commit。

## 验收

- `python test.py` 与 `python verify.py` 通过。
- P0：旧 `hmr_data` 无需迁移即可加载。
- P1：卡片可被 `ingest()` 原样解析，未验证正面经验被拒。
- P2：preferences.md 条目数不符时抛错而非静默；无新包依赖。
- P3：trace 失败不影响 recall 主链路。
- S1：向量写失败回滚文件；孤儿向量不触发 `None.reinforce()`；删除后文件/index/向量三处无残留。
- S2：同 Turn 重复提交只产生一条记忆；不同来源的同正文各自保留；来源工作区不匹配被拒；脱敏覆盖截断边界。
- S3：失败后 Pending 保留、重放后不重复；重启自动恢复；ThoughtChain 洞察写入失败可补偿。
