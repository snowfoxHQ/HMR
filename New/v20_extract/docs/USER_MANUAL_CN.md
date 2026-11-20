# HMR v2.0 用户操作手册（中文）

**Hestia Memory Runtime — 持续认知运行时**

版本：v2.0.0

---

## 目录

1. [快速开始](#1-快速开始)
2. [安装](#2-安装)
3. [核心概念](#3-核心概念)
4. [基础 API](#4-基础-api)
   - [初始化](#41-初始化)
   - [摄入记忆 ingest](#42-摄入记忆-ingest)
   - [召回记忆 recall](#43-召回记忆-recall)
   - [运行时状态](#44-运行时状态)
   - [代理工作区](#45-代理工作区)
   - [记忆压缩](#46-记忆压缩)
5. [v2.0 新增：ThoughtChain 推理链](#5-v20-新增thoughtchain-推理链)
6. [v2.0 新增：Memory Policy 策略引擎](#6-v20-新增memory-policy-策略引擎)
7. [v2.0 新增：Self-Evolution 自我演化](#7-v20-新增self-evolution-自我演化)
8. [v1.5 高级组件回顾](#8-v15-高级组件回顾)
9. [完整工作流示例](#9-完整工作流示例)
10. [配置参考](#10-配置参考)
11. [系统状态监控](#11-系统状态监控)
12. [故障排除](#12-故障排除)

---

## 1. 快速开始

```python
from hmr.core.hmr import HMR
from hmr.engines.thought_chain import ThoughtType

# 初始化
hmr = HMR(storage_path="./my_project")

# ── 存入记忆（Policy 自动判断类型）─────────────────────────
hmr.ingest("IPC 队列积压导致超时，消费者线程不足", use_policy=True)
# → 自动分类为 execution，置信度 0.85

# ── 推理链：记录完整思考过程 ─────────────────────────────────
chain = hmr.start_thinking("排查 IPC 超时根因")
hmr.think(chain.chain_id, "队列深度持续 > 800",    ThoughtType.OBSERVATION)
hmr.think(chain.chain_id, "消费者线程可能不足",     ThoughtType.HYPOTHESIS)
hmr.think(chain.chain_id, "扩容消费者线程 x3",     ThoughtType.DECISION)
hmr.think(chain.chain_id, "已完成部署",             ThoughtType.ACTION)

# ── 反思：评估推理质量，洞察自动存入长期记忆 ─────────────────
ref = hmr.reflect_on(chain.chain_id, "延迟从 800ms 降至 50ms", rating=0.9)
print(ref.accuracy)    # 0.75
print(ref.insights)    # ['有效决策路径：...', '目标达成（90%）']

# ── 下次遇到类似问题，直接查历史最优决策 ─────────────────────
best = hmr.best_decision_for("IPC 积压")
# → "[历史参考 准确率=90%] 扩容消费者线程 x3 + 提升优先级"

# ── 召回：智能多策略检索 ─────────────────────────────────────
result = hmr.recall(query="为什么 IPC 超时", top_k=5)
print(result.recall_reasoning)   # "[HYBRID] JIT编译 2 步..."

# ── 保存认知状态 ──────────────────────────────────────────────
hmr.save_runtime_state(goal="优化 IPC 性能", plan=["分析 ✓", "扩容 ✓", "验证"])

# ── 重启后完整恢复 ────────────────────────────────────────────
hmr2 = HMR(storage_path="./my_project")
state = hmr2.restore_runtime_state()
# → goal="优化 IPC 性能"，向量索引、SM-2 状态、Policy 权重全部恢复

# ── 自我演化 ──────────────────────────────────────────────────
report = hmr.evolve()
print(report["summary"])   # "演化完成：抽象 1 个簇，解决 0 对矛盾"
```

---

## 2. 安装

### 基础安装（内置 TF-IDF，始终可用）

```bash
pip install pydantic numpy
```

### 推荐安装（更好的语义理解）

```bash
# 方案 A：OpenAI Embedding（效果最好）
pip install openai
export OPENAI_API_KEY="sk-..."

# 方案 B：本地模型（无需 API Key）
pip install sentence-transformers
```

HMR 启动时自动检测并选择最佳 Embedding 方案：

```
优先级：OpenAI > sentence-transformers > TF-IDF n-gram
```

### 验证安装

```python
from hmr.core.hmr import HMR
hmr = HMR()
s = hmr.get_system_status()
print(s["version"])            # 2.0.0
print(s["embedding_provider"]) # openai / sentence_transformers / tfidf
```

---

## 3. 核心概念

### 设计哲学

```
传统 AI:  记忆 = 存储
HMR v2.0: 记忆 = 持续认知运行时
           ├── 不只存"发生了什么"，还存"为什么这样想"
           ├── 不只检索，还预测、推理、反思
           ├── 不只积累，还自我演化、自我优化
           └── 跨会话完整连续——重启不是遗忘，是暂停
```

### v2.0 三个新概念

**ThoughtChain（思维链）**
- 推理过程的显式记录：观察 → 假设 → 决策 → 行动 → 反思
- 每次执行完毕后触发反思，标记哪些判断有误
- 洞察自动存入长期记忆，历史成功链可供后续参考

**Memory Policy（记忆策略）**
- 三个子策略：IngestPolicy（存什么）/ RecallPolicy（怎么取）/ ForgetPolicy（怎么忘）
- 每次 `feedback()` 调用都用 SGD 微调策略权重
- 中英文均支持，基于字符级匹配，无需分词库

**Self-Evolution（自我演化）**
- PatternDetector：发现相似度 > 75% 的记忆簇
- KnowledgeAbstractor：把记忆簇提炼为更高阶的 concept
- ContradictionResolver：找到语义相反的记忆对，保留置信度高的
- StrategyOptimizer：分析使用模式，推荐最优配置参数

### 记忆类型

| 类型 | 用途 | 示例 |
|------|------|------|
| `concept` | 抽象知识、设计原则、建议 | "建议使用异步消息队列" |
| `decision` | 已做出的决策 + 理由 | "决定采用 asyncio 方案" |
| `execution` | 执行轨迹、故障记录 | "IPC 积压导致超时" |
| `reflection` | 复盘分析、根因总结 | "因为死锁导致任务阻塞" |
| `project` | 项目上下文 | "HMR v2 项目目标" |
| `task` | 任务定义 | "实现优先级队列" |
| `agent_memory` | 代理私有记忆 | "agent_frontend UI 决策" |
| `workflow` | 流程定义 | "发布流程 SOP" |

### ThoughtType 思维类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `OBSERVATION` | 观察到的事实 | "队列深度持续 > 800" |
| `HYPOTHESIS` | 提出的假设 | "可能是消费者线程不足" |
| `DECISION` | 做出的决策 | "扩容消费者线程 x3" |
| `ACTION` | 执行的行动 | "已完成部署" |
| `OUTCOME` | 行动的结果 | "延迟降至 50ms" |
| `REFLECTION` | 事后反思 | "扩容策略有效，应作为首选" |
| `INSIGHT` | 提炼的洞察 | "消费者数量应随并发线性扩展" |

---

## 4. 基础 API

### 4.1 初始化

```python
from hmr.core.hmr import HMR
from hmr.engines.lifecycle import LifecycleConfig

hmr = HMR(
    storage_path="./hmr_data",              # 数据存储根目录
    embedding_model="text-embedding-3-small",# OpenAI 模型名
    llm_api_key="sk-...",                   # API Key（可用环境变量代替）
    lifecycle_config=LifecycleConfig(        # 生命周期配置（可选）
        max_memories_per_type=80,
        check_interval_ingests=10,
    )
)
```

**参数说明：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `storage_path` | `"./hmr_data"` | 所有数据持久化目录 |
| `embedding_model` | `"text-embedding-3-small"` | OpenAI Embedding 模型 |
| `llm_api_key` | `None` | 也可设置 `OPENAI_API_KEY` 环境变量 |
| `lifecycle_config` | 默认值 | 见 [配置参考](#10-配置参考) |

---

### 4.2 摄入记忆 ingest

```python
memory = hmr.ingest(
    content="IPC 队列在并发 > 500 时积压超 1000 条，响应超时",
    memory_type="execution",    # 手动指定类型，或省略让 Policy 自动判断
    title="IPC 积压故障记录",
    metadata={
        "tags": ["ipc", "故障", "超时"],
        "runtime_dependencies": ["IPC 设计原则", "调度器"],
        "confidence": 0.9
    },
    use_policy=False            # True = Policy 自动推断 type 和 confidence
)
```

**use_policy=True 模式：**

```python
# Policy 自动判断类型（中英文均支持）
m1 = hmr.ingest("IPC 积压导致超时，消费者线程不足", use_policy=True)
print(m1.type)        # execution

m2 = hmr.ingest("建议使用异步消息队列处理高并发", use_policy=True)
print(m2.type)        # concept

m3 = hmr.ingest("决定采用 asyncio + 优先级堆方案", use_policy=True)
print(m3.type)        # decision

m4 = hmr.ingest("因为死锁导致任务阻塞，根因是环形等待", use_policy=True)
print(m4.type)        # reflection
```

**ingest 自动触发：**
- 向量 Embedding 生成
- SM-2 时间状态初始化
- Memory Graph 实体提取
- 生命周期检查（后台异步）
- 认知图（CWG）更新

---

### 4.3 召回记忆 recall

```python
result = hmr.recall(
    query="为什么 IPC 超时",
    context={"active_goal": "排查超时", "pending_tasks": [...]},
    top_k=5,
    strategy="jit",     # 手动指定策略（可省略，自动调度）
    use_policy=True     # Policy 辅助调度决策（默认 True）
)

# 查看结果
print(result.recall_reasoning)    # "[JIT] JIT编译 2 步，..."
for mem in result.memory_objects:
    score = result.relevance_scores[mem.id]
    print(f"[{score:.2f}] [{mem.type}] {mem.title}")
```

**策略选项：**

| strategy | 适用场景 | 特点 |
|----------|---------|------|
| `"semantic"` | 简单相似查询 | 单次向量检索，最快 |
| `"temporal"` | 时间相关（"最近"、"上次"） | 按新鲜度排序 |
| `"jit"` | 复杂推理（"为什么"、"原因"） | 多步检索，最准 |
| `"hybrid"` | 有明确工作目标 | 语义 + 图路径组合 |
| `"graph"` | 实体关系查询 | 图路径补充候选 |
| `None` | 通用（推荐） | Scheduler 自动决策 |

**返回值：**

```python
result.memory_objects     # List[MemoryObject]，按相关性排序
result.recall_reasoning   # 策略说明和推理过程
result.relevance_scores   # Dict[memory_id, float]
result.predicted_need     # 系统预测的需求列表
```

---

### 4.4 运行时状态

#### 保存

```python
state = hmr.save_runtime_state(
    goal="设计异步调度器",
    plan=["研究 IPC ✓", "设计 API ✓", "实现", "压测"],
    context={
        "current_focus": "实现阶段",
        "blockers": [],
        "confidence": 0.85
    }
)
print(state.runtime_id)   # rt_a1b2c3d4
```

#### 恢复

```python
hmr2 = HMR(storage_path="./my_project")
state = hmr2.restore_runtime_state()           # 最新状态
# 或
state = hmr2.restore_runtime_state("rt_a1b2c3d4")  # 指定状态

print(state.active_goal)    # "设计异步调度器"
print(state.current_plan)   # ["研究 IPC ✓", ...]
```

**恢复自动执行：**
1. SM-2 记忆状态恢复（每条记忆的复习历史）
2. 按当前 goal 预加载最相关记忆
3. Policy 权重恢复

---

### 4.5 代理工作区

```python
# 获取或创建工作区（自动持久化）
ws = hmr.get_workspace("agent_backend")

ws.active_goal = "实现任务队列"
ws.push_task({"name": "设计接口", "status": "todo"})
ws.push_task({"name": "实现优先级堆", "status": "todo"})
ws.temporary_thoughts.append("考虑用 heapq 实现最小堆")

# 手动保存（或等待下次 ingest 自动触发）
hmr.save_workspace("agent_backend")

# 完成任务
done = ws.pop_task()   # 后进先出，返回最后推入的任务

# 重启后完整恢复
hmr2 = HMR(storage_path="./my_project")
ws2 = hmr2.get_workspace("agent_backend", create=False)
print(ws2.active_goal)         # "实现任务队列"
print(len(ws2.task_stack))     # 1（已完成一个）
```

---

### 4.6 记忆压缩

```python
# 按类型压缩
compressed = hmr.compress_memories(
    memory_type="execution",
    max_memories=20
)

# 按 ID 压缩
compressed = hmr.compress_memories(
    memory_ids=["mem_001", "mem_002", "mem_003"]
)

if compressed:
    print(compressed.title)    # "[压缩] 积压记录 + 故障"
    print(compressed.tags)     # [..., "compressed"]
```

压缩策略：有 OpenAI Key → LLM 提炼，无 Key → TF-IDF 关键词摘要。

---

## 5. v2.0 新增：ThoughtChain 推理链

### 核心理念

```
传统：只记录"发生了什么"（execution 记忆）
v2.0：记录"为什么这样想"（推理链 = 完整思维过程）

价值：
  1. 可追溯性 — 回溯当时的推理路径
  2. 反思学习 — 找出哪些判断有误
  3. 知识传递 — 接手任务时继承完整思维上下文
  4. 决策复用 — 历史成功链直接指导新问题
```

### API 详解

#### start_thinking — 创建思维链

```python
chain = hmr.start_thinking(
    goal="排查调度器 IPC 超时根因",
    expected_outcome="找到根因并给出解决方案",  # 可选，用于反思时对比
    agent_id="agent_backend"                     # 可选，关联代理
)
print(chain.chain_id)   # tc_a1b2c3d4
print(chain.status)     # ChainStatus.OPEN
```

#### think — 追加思维节点

```python
from hmr.engines.thought_chain import ThoughtType

# 每次 think 都接在上一个节点后（自动推断 parent_id）
hmr.think(chain.chain_id, "队列深度持续 > 800，消费速度 < 生产速度",
          ThoughtType.OBSERVATION, confidence=0.95)

hmr.think(chain.chain_id, "可能原因1：消费者线程数不足",
          ThoughtType.HYPOTHESIS, confidence=0.7)

hmr.think(chain.chain_id, "可能原因2：消费者被 CPU 密集任务抢占",
          ThoughtType.HYPOTHESIS, confidence=0.8)

# 附带相关记忆 ID（标注决策依据）
recall_result = hmr.recall(query="IPC 背压机制")
supporting_ids = [m.id for m in recall_result.memory_objects[:2]]

hmr.think(chain.chain_id, "选择：扩容消费者 x3 + 提升线程优先级",
          ThoughtType.DECISION, confidence=0.8, memory_ids=supporting_ids)

hmr.think(chain.chain_id, "已部署：消费者线程 x3 + 优先级提升",
          ThoughtType.ACTION, confidence=1.0)
```

#### reflect_on — 触发反思

```python
result = hmr.reflect_on(
    chain_id=chain.chain_id,
    actual_outcome="队列积压从 800 降至 50，超时消失",
    rating=0.92      # 0-1，1=完全成功；不传则自动推断
)

print(result.accuracy)          # 0.75（正确节点 / 总节点）
print(result.correct_nodes)     # 正确的思维节点 ID 列表
print(result.wrong_nodes)       # 错误的思维节点 ID 列表
print(result.key_mistakes)      # 主要错误描述
print(result.insights)          # 提炼的洞察
print(result.suggested_memory)  # 建议存入长期记忆的内容（自动执行）
```

反思后：
- 每个思维节点获得 `was_correct` 标记（True / False / None）
- 高价值洞察自动存为 `reflection` 类型记忆
- 链状态变为 `CLOSED`

#### best_decision_for — 查历史最优决策

```python
best = hmr.best_decision_for("IPC 队列积压问题")
# → "[历史参考 准确率=90%] 扩容消费者线程 x3 + 提升优先级"
# → 如果没有相关历史链则返回 None
```

#### 查看推理链

```python
# 获取单条链
chain_obj = hmr.thought_chain.get_chain(chain.chain_id)
print(chain_obj.to_summary())   # 人类可读的摘要

# 查找类似历史链
similar = hmr.thought_chain.find_similar_chains("IPC 超时", top_k=3)

# 统计
stats = hmr.thought_chain.get_stats()
print(stats["total_chains"])             # 总链数
print(stats["avg_reflection_accuracy"]) # 平均反思准确率
print(stats["active_chains"])           # 活跃链数
```

### 完整推理链示例

```python
from hmr.engines.thought_chain import ThoughtType

# 场景：多天排障任务
chain = hmr.start_thinking(
    goal="调度器高负载下响应超时根因分析",
    expected_outcome="响应时间 p99 < 100ms"
)

# Day 1：收集观察
hmr.think(chain.chain_id, "p99 延迟 1200ms，远超 SLA 100ms", ThoughtType.OBSERVATION)
hmr.think(chain.chain_id, "IPC 队列积压 > 1000 条",           ThoughtType.OBSERVATION)
hmr.think(chain.chain_id, "CPU 使用率仅 40%，不是 CPU 瓶颈",  ThoughtType.OBSERVATION)

# 提出假设
hmr.think(chain.chain_id, "假设：消费者线程数量不足",          ThoughtType.HYPOTHESIS, 0.7)
hmr.think(chain.chain_id, "假设：IO 阻塞导致消费者停滞",       ThoughtType.HYPOTHESIS, 0.6)

# Day 2：验证假设后做决策
hmr.think(chain.chain_id, "验证：消费者线程确实在等待 IO",     ThoughtType.OBSERVATION)
hmr.think(chain.chain_id, "决定：改用异步 IO + 扩容消费者",    ThoughtType.DECISION, 0.85)
hmr.think(chain.chain_id, "已完成异步 IO 改造和扩容部署",      ThoughtType.ACTION)

# 执行完毕后反思
ref = hmr.reflect_on(
    chain.chain_id,
    "p99 降至 45ms，优于 SLA 目标",
    rating=0.95
)

# 查看思维链摘要
print(hmr.thought_chain.get_chain(chain.chain_id).to_summary())
```

---

## 6. v2.0 新增：Memory Policy 策略引擎

### 核心理念

```
v1.x：存/取/忘策略全部硬编码
v2.0：从反馈中学习，策略权重动态更新

三个子策略：
  IngestPolicy  → 什么值得存？存成什么类型？置信度多少？
  RecallPolicy  → 用什么策略召回？top_k 设多少？
  ForgetPolicy  → 记忆以多快速度衰减？什么时候删除？
```

### feedback — 策略反馈（核心）

```python
# 召回结果有用
hmr.feedback(
    event_type="recall_hit",
    memory_ids=[m.id for m in result.memory_objects[:2]],
    signal=0.85,             # 正数 = 正向反馈
    query="IPC 超时原因",
    strategy="jit"
)

# 召回结果没用到
hmr.feedback(
    event_type="recall_miss",
    memory_ids=[m.id for m in bad_results],
    signal=-0.5
)

# 任务成功
hmr.feedback(
    event_type="task_success",
    memory_ids=related_memory_ids,
    signal=0.9,
    context={"memory_type": "execution"}
)

# 任务失败
hmr.feedback(
    event_type="task_failure",
    memory_ids=related_memory_ids,
    signal=-0.7
)

# 压缩后召回质量提升
hmr.feedback(
    event_type="compress_gain",
    memory_ids=[compressed_memory.id],
    signal=0.6
)
```

**event_type 说明：**

| 事件 | signal 范围 | 说明 |
|------|-----------|------|
| `recall_hit` | 0.5 ~ 1.0 | 召回结果被实际使用 |
| `recall_miss` | -1.0 ~ -0.1 | 召回结果完全无用 |
| `task_success` | 0.5 ~ 1.0 | 完整任务成功 |
| `task_failure` | -1.0 ~ -0.1 | 任务失败 |
| `compress_gain` | 0.3 ~ 0.8 | 压缩提升了召回质量 |

### Policy 辅助的 ingest / recall

```python
# ingest 时让 Policy 自动决策
mem = hmr.ingest(content, use_policy=True)
# Policy 自动推断 memory_type 和 confidence
# 中英文均支持，基于字符级关键词匹配

# recall 时让 Policy 辅助调度
result = hmr.recall(query, use_policy=True)  # 默认 True
# Policy 根据历史命中率调整 strategy 和 top_k
```

### 查看策略状态

```python
stats = hmr.policy.get_stats()
print(stats["total_feedback"])      # 总反馈次数
print(stats["positive_feedback"])   # 正向反馈次数
print(stats["positive_ratio"])      # 正向比例（越高策略越准）
print(stats["recall_hit_rate"])     # 召回命中率
print(stats["policy_updates"])      # 策略权重更新次数

# 当前权重偏置（调试用）
weights = hmr.policy.get_policy_weights_summary()
print(weights["ingest_type_bias"])      # 各类型的分类偏向
print(weights["recall_strategy_bias"]) # 各策略的使用偏向
```

### Policy 最佳实践

```python
# 1. 每次召回后及时反馈
result = hmr.recall(query="...")
used_memories = [result.memory_objects[0]]  # 实际用到的记忆
hmr.feedback("recall_hit", [m.id for m in used_memories], signal=0.8,
             query="...", strategy=result.recall_reasoning.split("]")[0].strip("["))

# 2. 任务结束时汇总反馈
if task_succeeded:
    hmr.feedback("task_success", all_related_memory_ids, signal=0.9)
else:
    hmr.feedback("task_failure", all_related_memory_ids, signal=-0.6)

# 3. 用 use_policy=True 让系统自动学习最优存储决策
for log_entry in daily_logs:
    hmr.ingest(log_entry, use_policy=True)
    # Policy 随时间学习该项目的记忆风格
```

---

## 7. v2.0 新增：Self-Evolution 自我演化

### 核心理念

```
问题：记忆库随时间膨胀，大量重复/冗余/矛盾记忆积累
解决：演化引擎主动优化记忆库结构

三个核心操作：
  abstract：相似记忆 → 抽象概念（知识提炼）
  resolve：矛盾记忆 → 保留高置信，降低低置信（冲突解决）
  suggest：分析使用模式 → 推荐最优配置参数
```

### evolve — 执行演化

```python
# 先预览（dry_run=True 只分析不修改）
preview = hmr.evolve(dry_run=True)
print(preview["summary"])
for action in preview["actions"]:
    print(f"  {action}")
# 输出：
# 演化完成：抽象 2 个簇，解决 1 对矛盾
#   [预览] 可抽象 5 条 [execution] 记忆
#   [预览] 矛盾：《IPC 应同步》vs《IPC 应异步》

# 确认后正式执行
report = hmr.evolve(dry_run=False)
print(report["summary"])
print(report["abstractions"])            # 抽象了几个簇
print(report["contradictions_resolved"]) # 解决了几对矛盾
print(report["suggestions"])             # 配置优化建议
```

### 演化报告解读

```python
report = hmr.evolve()

# summary：一句话总结
print(report["summary"])
# → "演化完成：抽象 2 个簇，解决 1 对矛盾，健康度: ✅ 健康"

# actions：每个操作的详情
for action in report["actions"]:
    print(action)
# → ✅ 抽象 6 条 [execution] → 《[抽象] 积压记录 + 超时》
# → 🔧 解决矛盾：《IPC 应同步》vs《IPC 应异步》（方向相反）
# → 💡 建议：某类型记忆数 120 过多，建议降低阈值到 80

# suggestions：配置优化建议
sugg = report["suggestions"]
print(sugg["suggested_config"])   # 推荐的 LifecycleConfig 参数
print(sugg["reasons"])            # 推荐理由
print(sugg["current_health"])     # 系统健康状态
```

### 演化频率建议

```python
# 方案 A：定期手动执行（推荐）
# 每积累 50-100 条新记忆后执行一次
if hmr.memory_fs.get_statistics()["total_memories"] % 100 == 0:
    hmr.evolve()

# 方案 B：每日定时
import schedule
schedule.every().day.at("02:00").do(lambda: hmr.evolve())

# 方案 C：任务结束后
# 每次重大任务完成后执行
hmr.evolve()
```

### 查看演化历史

```python
evo_stats = hmr.evolution.get_stats()
print(evo_stats["total_operations"])    # 总操作次数
print(evo_stats["by_operation"])        # 按类型分布
# {"abstract": 5, "resolve": 2}
print(evo_stats["recent_operations"])   # 最近 5 次操作
```

---

## 8. v1.5 高级组件回顾

### Memory Scheduler 调度器

```python
# 手动查看调度决策（不实际召回）
plan = hmr.scheduler.schedule(
    query="为什么 IPC 超时导致调度器响应慢",
    context={"active_goal": "优化调度器"}
)
print(plan.strategy.value)   # "jit"
print(plan.use_jit)           # True
print(plan.top_k)             # 8
print(plan.reasoning)         # "查询复杂，使用 JIT 多步检索"

# 调度统计
stats = hmr.scheduler.get_stats()
print(stats["strategy_counts"])    # 各策略使用次数
print(stats["cache_hit_rate"])     # 热缓存命中率
print(stats["dominant_strategy"]) # 最常用策略
```

### JIT Memory Compiler 即时编译器

```python
# 直接调用（recall 复杂查询时自动触发）
result = hmr.jit_compiler.compile(
    query="为什么 IPC 延迟导致调度器级联超时",
    context={"active_goal": "排查故障"},
    top_k=5,
    max_steps=3
)

# 查看多步检索详情
for step in result.steps:
    print(f"步骤{step.step+1}: {step.query}")
    print(f"  找到 {len(step.memories)} 条，置信度 {step.confidence}")
    print(f"  缺口: {step.gaps}")

print("查询轨迹:", result.query_trace)
```

### Memory Lifecycle 生命周期

```python
from hmr.engines.lifecycle import LifecycleConfig

# 自定义配置
config = LifecycleConfig(
    max_memories_per_type=80,       # 超过触发自动压缩
    prune_retrievability=0.05,      # SM-2 可提取性低于 5% 考虑删除
    prune_min_age_days=7,           # 至少存在 7 天才允许删除
    prune_require_zero_access=True, # 只删从未访问的记忆
    auto_enabled=True,
    check_interval_ingests=10,
)
hmr = HMR(storage_path="./data", lifecycle_config=config)

# 手动触发检查
report = hmr.lifecycle.check_now(memory_type="execution")
print(report.summary())   # "检查 50 条；删除 3 条；压缩 20 → 1 条"

# 记忆生命周期统计
lc_stats = hmr.lifecycle.get_lifecycle_stats()
print(lc_stats["by_state"])
# {"fresh": 5, "active": 30, "fading": 10, "dormant": 3}
```

### Memory Graph 记忆图层

```python
# 图随 ingest 自动构建
nodes = hmr.memory_graph.find_related("调度器", depth=2)
for n in nodes:
    print(f"[{n.node_type.value}] {n.label} ({len(n.memory_ids)} 条记忆)")

# 因果链
chain = hmr.memory_graph.get_causal_chain("死锁")
for node, edge in chain:
    print(f"→({edge.edge_type.value})→ {node.label}")

# 语义聚类
clusters = hmr.memory_graph.auto_cluster()

# 图统计
print(hmr.memory_graph.get_stats())
```

---

## 9. 完整工作流示例

### 场景一：多天技术攻关

```python
from hmr.core.hmr import HMR
from hmr.engines.thought_chain import ThoughtType

# ═══ 第一天：问题发现 ══════════════════════════════════════════
hmr = HMR(storage_path="./ipc_project")

# 记录问题背景
hmr.ingest("线上调度器 p99 延迟从 50ms 上升至 1200ms，持续 2 小时",
           memory_type="execution", title="线上延迟告警",
           metadata={"tags": ["线上", "告警", "p99"]})

# 开始推理链
chain = hmr.start_thinking(
    goal="排查调度器延迟从 50ms 上升至 1200ms 的根因",
    expected_outcome="找到根因，将 p99 恢复至 100ms 以下"
)
hmr.think(chain.chain_id, "p99 延迟 1200ms，CPU 使用率仅 40%",
          ThoughtType.OBSERVATION, 0.95)
hmr.think(chain.chain_id, "监控显示 IPC 队列深度持续 > 1000",
          ThoughtType.OBSERVATION, 0.95)
hmr.think(chain.chain_id, "非 CPU 瓶颈，怀疑是 IO 阻塞",
          ThoughtType.HYPOTHESIS, 0.7)

# 保存状态
hmr.save_runtime_state(
    goal="排查调度器延迟根因",
    plan=["收集监控数据 ✓", "提出假设 ✓", "验证假设", "修复", "验收"],
    context={"active_chain": chain.chain_id, "confidence": 0.5}
)
print("第一天完成，状态已保存")

# ═══ 第二天：验证和修复 ═══════════════════════════════════════
hmr2 = HMR(storage_path="./ipc_project")
state = hmr2.restore_runtime_state()
active_chain_id = state.current_context.get("active_chain")

# 智能召回（复杂查询自动触发 JIT）
result = hmr2.recall(
    query="IO 阻塞导致消费者停滞的排查方法",
    context={"active_goal": state.active_goal}
)
hmr2.feedback("recall_hit", [result.memory_objects[0].id], 0.8,
              query="IO 阻塞排查")

# 继续推理链
chain_obj = hmr2.thought_chain.get_chain(active_chain_id)
if chain_obj:
    hmr2.think(active_chain_id, "Profiling 确认：消费者线程在等待同步 IO",
               ThoughtType.OBSERVATION, 0.98)
    hmr2.think(active_chain_id, "决定：将同步 IO 改为异步，同时扩容消费者至 x3",
               ThoughtType.DECISION, 0.9)
    hmr2.think(active_chain_id, "已完成异步 IO 改造 + 消费者扩容部署",
               ThoughtType.ACTION, 1.0)

    # 部署后观察
    hmr2.think(active_chain_id, "p99 降至 45ms，低于 SLA 目标 100ms",
               ThoughtType.OUTCOME, 1.0)

    # 触发反思
    ref = hmr2.reflect_on(
        active_chain_id,
        "p99 从 1200ms 降至 45ms，恢复正常",
        rating=0.95
    )
    print(f"反思准确率: {ref.accuracy:.0%}")
    print(f"洞察: {ref.insights}")

# 记录经验
hmr2.ingest(
    "根因：消费者线程同步 IO 阻塞导致 IPC 队列积压。"
    "修复：异步 IO + 消费者 x3 扩容。效果：p99 从 1200ms 降至 45ms。",
    memory_type="reflection",
    title="IPC 延迟根因与修复总结",
    metadata={"tags": ["ipc", "延迟", "最佳实践"], "confidence": 0.95}
)

# 完成后演化
report = hmr2.evolve()
print(report["summary"])

# 下次遇到类似问题
best = hmr2.best_decision_for("IPC 队列积压延迟")
print(f"历史最优决策: {best[:60]}")
```

### 场景二：多代理协作

```python
hmr = HMR(storage_path="./team_project")

# ── 后端代理 ─────────────────────────────────────────────────
backend = hmr.get_workspace("agent_backend")
backend.active_goal = "实现调度器核心逻辑"
backend.push_task({"name": "实现优先级堆", "status": "in_progress"})

# 后端推理链
be_chain = hmr.start_thinking("设计任务优先级算法", agent_id="agent_backend")
hmr.think(be_chain.chain_id, "需要支持 1-10 优先级，高优先级先执行",
          ThoughtType.OBSERVATION)
hmr.think(be_chain.chain_id, "最小堆可高效实现优先级队列",
          ThoughtType.DECISION, 0.9)

# 存储 API 决策（让前端代理能查到）
hmr.ingest(
    "调度器 API：submit(task, priority=1-10)，cancel(task_id)，status(task_id)",
    memory_type="decision", title="调度器 API 设计",
    metadata={"tags": ["api", "scheduler"], "runtime_dependencies": ["调度器核心"]}
)
hmr.save_workspace("agent_backend")

# ── 前端代理 ─────────────────────────────────────────────────
frontend = hmr.get_workspace("agent_frontend")
frontend.active_goal = "构建调度器管理 UI"

# 前端查取后端 API 设计
api_result = hmr.recall(query="调度器 API 接口定义", strategy="semantic")
if api_result.memory_objects:
    api_doc = api_result.memory_objects[0]
    hmr.feedback("recall_hit", [api_doc.id], 0.9)
    print(f"前端获取到 API: {api_doc.content[:80]}")

hmr.save_workspace("agent_frontend")

# ── 重启后状态完整恢复 ───────────────────────────────────────
hmr2 = HMR(storage_path="./team_project")
ws_be = hmr2.get_workspace("agent_backend", create=False)
ws_fe = hmr2.get_workspace("agent_frontend", create=False)
print(f"后端: {ws_be.active_goal}")
print(f"前端: {ws_fe.active_goal}")
```

### 场景三：持续学习系统

```python
hmr = HMR(storage_path="./learning_system")

# 模拟 30 天的执行记录积累
for day in range(30):
    # 每天摄入若干条记录
    for run in range(3):
        hmr.ingest(
            f"Day{day+1} Run{run+1}: 调度器 p99={50+day%20}ms，"
            f"IPC 队列峰值 {run*100} 条，并发 {200+day*10} RPS",
            use_policy=True,   # Policy 自动分类
            title=f"日常运行记录 Day{day+1}-{run+1}"
        )

    # 每 10 天提供一次任务反馈
    if (day+1) % 10 == 0:
        status = hmr.get_system_status()
        memories = hmr.memory_fs.list_memories(memory_type="execution")
        hmr.feedback(
            "task_success",
            memory_ids=[m.id for m in memories[-5:]],
            signal=0.85
        )
        print(f"Day {day+1}: {status['memory_fs']['total_memories']} 条记忆")

# 30 天后：查看 Policy 学习成果
print(hmr.policy.get_stats())
print(hmr.policy.get_policy_weights_summary())

# 自我演化：压缩冗余，提炼规律
report = hmr.evolve()
print(report["summary"])
# → "演化完成：抽象 3 个簇，解决 0 对矛盾，健康度: ✅ 健康"

# 提炼的规律可直接参考
result = hmr.recall(query="调度器性能规律", top_k=3)
for mem in result.memory_objects:
    print(f"[{mem.type}] {mem.title}")
```

---

## 10. 配置参考

### LifecycleConfig 完整选项

```python
from hmr.engines.lifecycle import LifecycleConfig

LifecycleConfig(
    max_memories_per_type   = 80,    # 同类型超过此数触发自动压缩
    consolidation_batch     = 20,    # 每次最多压缩几条
    consolidation_keep_ratio= 0.3,   # 原记忆权重降为 30%（不删除）
    prune_retrievability    = 0.05,  # SM-2 可提取性低于 5% 考虑删除
    prune_min_age_days      = 7,     # 至少存在 7 天才允许删除
    prune_require_zero_access = True,# 只删从未访问过的记忆
    auto_enabled            = True,  # 开启自动生命周期管理
    check_interval_ingests  = 10,    # 每 10 次 ingest 检查一次
)
```

### 环境变量

```bash
OPENAI_API_KEY=sk-...    # OpenAI API Key
```

### 数据目录结构

```
hmr_data/
├── memories/            按类型存放的记忆文件
│   ├── concepts/
│   ├── executions/
│   ├── decisions/
│   └── ...
├── runtimes/            RuntimeState 文件
├── workspaces/          AgentWorkspace 文件
├── vector_store/        向量索引（持久化）
│   ├── vectors.json
│   └── vector_metadata.json
├── memory_graph/        实体图数据
│   └── memory_graph.json
├── thought_chains/      思维链文件（v2.0）
│   └── tc_*.json
├── policy/              Policy 权重（v2.0）
│   └── policy.json
├── evolution/           演化日志（v2.0）
│   └── evolution_logs.json
└── index/               索引文件
```

---

## 11. 系统状态监控

```python
status = hmr.get_system_status()

# 基础指标
print(status["version"])            # "2.0.0"
print(status["memory_fs"]["total_memories"])
print(status["vector_store"]["total_vectors"])
print(status["synced"])             # True = 向量与记忆数量同步

# v1.5 组件
print(status["memory_graph"]["total_nodes"])
print(status["memory_graph"]["total_edges"])
print(status["scheduler"]["dominant_strategy"])
print(status["scheduler"]["cache_hit_rate"])
print(status["lifecycle"]["by_state"])   # fresh/active/fading/dormant 分布

# v2.0 组件
print(status["thought_chain"]["total_chains"])
print(status["thought_chain"]["avg_reflection_accuracy"])
print(status["thought_chain"]["active_chains"])

print(status["policy"]["total_feedback"])
print(status["policy"]["positive_ratio"])
print(status["policy"]["recall_hit_rate"])

print(status["evolution"]["total_operations"])
print(status["evolution"]["by_operation"])  # {"abstract": N, "resolve": M}

# 其他
print(status["overdue_reviews"])    # 逾期需要复习的记忆数
print(status["active_workspaces"]) # 活跃代理数
print(status["embedding_provider"]) # openai/sentence_transformers/tfidf
```

---

## 12. 故障排除

### 启动时显示"重建向量索引"

```
[HMR] 重建向量索引（N 条）...
```

**正常现象**，首次启动或 `vector_store/` 被删除时触发，自动完成后不再出现。

---

### Policy 分类结果不符预期

```python
# 1. 查看分类决策详情
d = hmr.policy.decide_ingest(content, title=title)
print(d)   # {"should_store": True, "memory_type": "...", "reasoning": "..."}

# 2. 通过反馈纠正
m = hmr.ingest(content, memory_type="execution")  # 手动指定正确类型
hmr.feedback("task_success", [m.id], signal=0.9,
             context={"memory_type": "execution", "content": content})
# Policy 权重会在下次相似内容时得到纠正

# 3. 关键词不匹配时
# 确保内容包含 Policy 能识别的特征词：
# execution: 失败/错误/超时/崩溃/积压/fault/error/crash/timeout
# decision:  决定/采用/选择/determined/selected
# reflection:因为/原因/根因/because/cause/reason
# concept:   建议/推荐/模式/recommend/pattern/principle
```

---

### 召回结果不相关

```python
# 检查数据同步状态
status = hmr.get_system_status()
print(status["synced"])           # 应为 True
print(status["embedding_provider"])  # 查看当前 Embedding 方案

# 强制重建向量索引
hmr.vector_store.rebuild_from_memories(hmr.memory_fs.list_memories())

# 对复杂查询强制使用 JIT
result = hmr.recall(query="...", strategy="jit")
```

---

### evolve() 返回空操作

```python
# 原因：未达到触发条件（簇大小 < 3，或无矛盾）
# 检查记忆分布
stats = hmr.memory_fs.get_statistics()
print(stats["memory_types"])   # 各类型记忆数量

# 降低触发阈值（调试用）
report = hmr.evolution.evolve(
    memories=hmr.memory_fs.list_memories(),
    vector_store=hmr.vector_store,
    memory_fs=hmr.memory_fs,
)
```

---

### 思维链反思后洞察未自动存储

```python
# 检查 ingest_fn 是否已注册
print(hmr.thought_chain._ingest_fn is not None)  # 应为 True

# 手动存储洞察
ref = hmr.reflect_on(chain_id, actual_outcome)
if ref.suggested_memory:
    hmr.ingest(ref.suggested_memory, memory_type="reflection",
               title=f"[链洞察] {goal[:30]}")
```

---

*HMR v2.0 — 让 AI 不只记住答案，而是记住如何思考。*
