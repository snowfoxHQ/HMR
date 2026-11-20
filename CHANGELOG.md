# Changelog

## v2.2.0 — 2026-11-21
写入可靠性补充批次（详见 `docs/MEMORAX_BORROW_PLAN.md`）：
- 存储一致性：文件优先写入 + 向量失败回滚、孤儿向量防御、删除时文件/索引/向量三处同步、启动反向对账
- 写入可信性：来源身份落盘、工作区作用域校验、写前脱敏（与 trace 共用规则）、单进程幂等去重
- 写入恢复：Pending accepted/persisted/failed、可重试错误分类与退避、重启恢复、ThoughtChain 洞察补偿

## v2.1.0 — 2026-11-21
借鉴 MemoraX Code 的记忆边界与写入治理，详见 `docs/MEMORAX_BORROW_PLAN.md`：
- MemoryObject 新增 boundary/scope/status/source/evidence/metadata，旧数据免迁移
- `CODE_AGENT_MEMORY` 结构化记忆卡 + 已验证门槛（未验证正面经验被拒）
- 个人记忆层：User Profile 偏好、Procedure 流程主题、首轮 + 5 轮 cadence 注入
- 本地 Trace：JSONL / event_id 去重 / 脱敏 / 7 天保留，失败不影响主链路

## v2.0.0 — 2026-06
新增三大认知智能引擎：
- ThoughtChain Engine — 显式推理链 + 反思循环
- Memory Policy Engine — 存/取/忘策略学习（SGD，中英文支持）
- Self-Evolution Engine — 模式识别 + 知识抽象 + 矛盾解决

## v1.5.0 — 2026-04
- JIT Memory Compiler（多步推理检索）
- Memory Scheduler（调度策略 + 热缓存 LRU）
- Memory Lifecycle Engine（自动压缩/剪枝）
- Memory Graph（实体/因果/时序图）

## v1.1.0 — 2026-02
- VectorStore 持久化
- 真实 Embedding（三层 fallback）
- SM-2 遗忘曲线
- AgentWorkspace 持久化 + 文件锁

## v1.0.0 — 2026-01
- 初始版本
