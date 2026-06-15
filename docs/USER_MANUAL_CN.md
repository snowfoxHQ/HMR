# HMR v1.5 用户操作手册

**Hestia Memory Runtime — 面向长期运行 AI 系统的持续认知运行时**

版本：v1.5.0 | 语言：中文

---

## 目录

1. [快速开始](#快速开始)
2. [安装](#安装)
3. [核心概念](#核心概念)
4. [主要 API](#主要-api)
   - [初始化](#初始化)
   - [摄入记忆 ingest](#摄入记忆-ingest)
   - [召回记忆 recall](#召回记忆-recall)
   - [运行时状态](#运行时状态)
   - [代理工作区](#代理工作区)
   - [记忆压缩](#记忆压缩)
   - [系统状态](#系统状态)
5. [高级组件](#高级组件)
   - [Memory Scheduler 调度器](#memory-scheduler-调度器)
   - [JIT Memory Compiler 即时编译器](#jit-memory-compiler-即时编译器)
   - [Memory Lifecycle Engine 生命周期引擎](#memory-lifecycle-engine-生命周期引擎)
   - [Memory Graph 记忆图层](#memory-graph-记忆图层)
6. [完整工作流示例](#完整工作流示例)
7. [配置参考](#配置参考)
8. [故障排除](#故障排除)
9. [版本历史](#版本历史)

---

## 快速开始

```python
from hmr.core.hmr import HMR

# 1. 初始化
hmr = HMR(storage_path="./my_project")

# 2. 存入记忆
hmr.ingest("IPC 应使用异步消息队列，避免阻塞", memory_type="concept", title="IPC 设计原则")

# 3. 保存当前工作状态
hmr.save_runtime_state(
    goal="设计调度器",
    plan=["研究 IPC", "设计 API", "实现"]
)

# 4. 几天后重启，恢复状态
state = hmr.restore_runtime_state()
print(state.active_goal)   # "设计调度器"

# 5. 智能召回相关记忆
result = hmr.recall(query="调度器 IPC 设计")
for mem in result.memory_objects:
    print(f"[{mem.type}] {mem.title}")
```

---

## 安装

> **重要提示（Windows 用户）**
> 不要把项目放在 `Documents`、`桌面`、`图片` 等被 OneDrive 同步的目录下，
> 否则 `pip install -e .` 会因 OneDrive 锁定文件而报错
> （`could not create 'hmr.egg-info': 系统找不到指定的文件`）。
> 请放到不被同步的路径，例如 `C:\hmr` 或 `C:\projects\hmr`。

### 第 1 步：安装依赖（始终可用）

```bash
pip install pydantic numpy
```

> 仅需这两个包，HMR 即可完整运行（内置 TF-IDF Embedding）。

### 第 2 步：安装 HMR

进入解压后、包含 `pyproject.toml` 的目录：

```bash
# Windows (PowerShell)
cd C:\hmr
pip install -e .

# Linux / macOS
cd /path/to/hmr
pip install -e .
```

或者**免安装**直接用：在你的 Python 脚本开头加两行指向项目目录：

```python
import sys
sys.path.insert(0, r"C:\hmr")   # 改成你的实际路径
from hmr.core.hmr import HMR
```

### （可选）更好的语义搜索

不装下面任何一个，HMR 也能用（自动回退到内置 TF-IDF）。装了效果更好：

```bash
# 方案 A：本地模型（推荐，免费、无需 API Key、不联网）
pip install sentence-transformers

# 方案 B：OpenAI Embedding（效果最佳，需要 API Key）
pip install openai
```

如果用方案 B，需要设置环境变量 `OPENAI_API_KEY`。
**下面分平台列出命令，请找到你自己的系统对照使用——不同系统的命令完全不同，用错会报错。**

#### Windows — PowerShell

```powershell
# 临时（仅当前 PowerShell 窗口有效，关闭即失效）
$env:OPENAI_API_KEY="sk-..."

# 永久（写入用户环境变量，需关闭并重开 PowerShell 才生效）
[System.Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-...", "User")

# 验证是否设置成功
echo $env:OPENAI_API_KEY
```

#### Windows — CMD（命令提示符）

```cmd
:: 临时（仅当前 CMD 窗口有效）
set OPENAI_API_KEY=sk-...

:: 永久（写入用户环境变量，需重开 CMD 才生效）
setx OPENAI_API_KEY "sk-..."

:: 验证是否设置成功
echo %OPENAI_API_KEY%
```

#### Linux / macOS — 终端

```bash
# 临时（仅当前终端会话有效，关闭即失效）
export OPENAI_API_KEY="sk-..."

# 永久（写入 shell 配置文件，对所有新终端生效）
# bash 用户：
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.bashrc && source ~/.bashrc
# zsh 用户（macOS 默认）：
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.zshrc && source ~/.zshrc

# 验证是否设置成功
echo $OPENAI_API_KEY
```

> **说明**：环境变量设置成功后，运行 HMR 时会自动读取，无需在代码里写 Key。
> HMR 启动时按 OpenAI → sentence-transformers → TF-IDF 顺序自动选择，
> 装了哪个、设了哪个就自动用哪个。
>
> 如果不想设环境变量，也可以在代码里直接传：
> `HMR(storage_path="./data", llm_api_key="sk-...")`

### 第 3 步：验证安装

把下面代码保存为 `verify.py`（**不要直接粘贴到终端 / PowerShell，那是 Python 代码，必须用 python 运行**）：

```python
from hmr.core.hmr import HMR

hmr = HMR(storage_path="./test_data")
print("版本:", hmr.VERSION)   # 应输出 1.5.0

status = hmr.get_system_status()
print("Embedding 方案:", status["embedding_provider"])  # openai / sentence_transformers / tfidf
print("数据同步:", status["synced"])                     # True
```

然后运行：

```bash
python verify.py
```

看到 `版本: 1.5.0` 和 `数据同步: True` 即安装成功。

---

## 核心概念

### 设计理念

```
传统 AI 记忆：  记忆 = 存储（你问，我搜）
HMR：          记忆 = 持续认知运行时（系统预测你需要什么，提前加载）
```

### 五个关键组件

| 组件 | 职责 | 类比 |
|------|------|------|
| **MemoryObject** | 记忆的基本单元，带类型、摘要、时间权重 | 大脑中的一条记忆 |
| **RuntimeState** | 当前认知状态：目标、计划、上下文 | 你工作时的"脑中状态" |
| **Memory Scheduler** | 决定用什么策略召回记忆 | 操作系统的进程调度器 |
| **JIT Compiler** | 多步推理检索，分析缺口再改写查询 | 编译器的多遍优化 |
| **Memory Graph** | 实体/因果/时序结构化网络 | 知识图谱 |

### 记忆类型

| 类型 | 用途 | 示例 |
|------|------|------|
| `concept` | 抽象知识、设计原则 | "异步优于同步" |
| `project` | 项目上下文 | "HMR v2 项目目标" |
| `decision` | 决策 + 理由 | "选择 Chroma 而非 Pinecone" |
| `execution` | 执行轨迹、失败记录 | "压测中发生死锁" |
| `task` | 任务定义 | "实现优先级队列" |
| `reflection` | 复盘和学习 | "死锁原因分析" |
| `agent_memory` | 代理私有记忆 | "agent_frontend 的 UI 决策" |
| `workflow` | 流程定义 | "发布流程 SOP" |

---

## 主要 API

### 初始化

```python
from hmr.core.hmr import HMR
from hmr.engines.lifecycle import LifecycleConfig

hmr = HMR(
    storage_path="./hmr_data",          # 数据存储路径（默认 ./hmr_data）
    embedding_model="text-embedding-3-small",  # OpenAI Embedding 模型
    llm_api_key="sk-...",               # 可选，也可通过环境变量 OPENAI_API_KEY 设置
    lifecycle_config=LifecycleConfig(   # 可选，自定义生命周期配置
        max_memories_per_type=100,
        check_interval_ingests=10,
    )
)
```

**参数说明：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `storage_path` | `"./hmr_data"` | 所有数据持久化目录 |
| `embedding_model` | `"text-embedding-3-small"` | OpenAI Embedding 模型名 |
| `llm_api_key` | `None` | OpenAI API Key（可选） |
| `lifecycle_config` | 默认配置 | 生命周期引擎配置 |

---

### 摄入记忆 ingest

将新知识、事件、决策存入 HMR。

```python
memory = hmr.ingest(
    content="在高并发下 IPC 队列积压，任务等待超过 500ms，导致下游超时",
    memory_type="execution",
    title="压测故障记录 #1",
    metadata={
        "tags": ["ipc", "压测", "超时"],
        "runtime_dependencies": ["IPC 设计原则", "调度器"],
        "confidence": 0.9
    }
)

print(memory.id)             # mem_a1b2c3d4
print(memory.semantic_summary)  # 自动生成的摘要
```

**参数说明：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | str | ✅ | 记忆内容（支持长文本） |
| `memory_type` | str | 否 | 记忆类型，默认 `"concept"` |
| `title` | str | 否 | 标题，默认自动生成 |
| `metadata` | dict | 否 | 包含 tags、runtime_dependencies、confidence |

**ingest 自动触发：**
- 向量 Embedding 生成
- SM-2 时间状态初始化
- Memory Graph 实体提取
- 生命周期检查（每 N 次）
- 认知图（CWG）更新

---

### 召回记忆 recall

智能召回相关记忆，由 Memory Scheduler 自动选择最优策略。

```python
result = hmr.recall(
    query="为什么 IPC 延迟导致调度器超时",
    context={"active_goal": "优化调度器"},  # 可选，提供更好的上下文
    top_k=5,
    strategy="jit"   # 可选，手动指定策略
)

print(result.recall_reasoning)   # "[JIT] JIT编译 2 步，查询轨迹..."
for mem in result.memory_objects:
    score = result.relevance_scores[mem.id]
    print(f"  [{score:.2f}] {mem.title}")
```

**参数说明：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `query` | str | None | 查询字符串 |
| `context` | dict | None | 当前上下文（含 active_goal 等） |
| `top_k` | int | 5 | 返回记忆数量 |
| `strategy` | str | None | 手动指定策略，见下表 |

**策略选项（strategy）：**

| 值 | 适用场景 | 特点 |
|----|---------|------|
| `"semantic"` | 简单相似性查询 | 单次向量检索，最快 |
| `"temporal"` | 时间相关查询（"最近的...""上次..."） | 按时间权重排序 |
| `"jit"` | 复杂推理查询（"为什么...""原因..."） | 多步检索，最准 |
| `"hybrid"` | 有明确工作目标时 | 语义 + 图路径组合 |
| `"graph"` | 需要实体关系时 | 图路径补充候选 |

> 不指定 `strategy` 时，Scheduler 自动根据查询特征决策。

**返回值 RecallResult：**

```python
result.memory_objects    # List[MemoryObject]，按相关性排序
result.recall_reasoning  # str，说明用了什么策略和推理过程
result.relevance_scores  # Dict[str, float]，每条记忆的得分
result.predicted_need    # List[str]，系统预测的需求
```

---

### 运行时状态

保存和恢复 AI 的完整认知状态，实现跨会话连续性。

#### 保存状态

```python
state = hmr.save_runtime_state(
    goal="设计异步调度器",
    plan=[
        "研究 IPC 协议 ✓",
        "设计任务队列 API",
        "实现优先级调度",
        "压测验证"
    ],
    context={
        "current_focus": "任务队列 API 设计",
        "blockers": ["需要确认 IPC 协议规格"],
        "confidence": 0.7
    }
)

print(state.runtime_id)   # rt_a1b2c3d4
```

#### 恢复状态

```python
# 重启后
hmr2 = HMR(storage_path="./my_project")

# 恢复最新状态
state = hmr2.restore_runtime_state()

# 或恢复特定状态
state = hmr2.restore_runtime_state(runtime_id="rt_a1b2c3d4")

if state:
    print(state.active_goal)     # "设计异步调度器"
    print(state.current_plan)    # ["研究 IPC 协议 ✓", ...]
    print(state.current_context) # {"current_focus": "任务队列 API 设计", ...}
```

**恢复后自动执行：**
1. 恢复 SM-2 记忆状态（哪些记忆复习过几次）
2. 预加载与当前 goal 最相关的记忆
3. 输出预加载的策略说明

---

### 代理工作区

每个代理（Agent）拥有独立的工作区，持久化到磁盘。

```python
# 获取或创建工作区
ws = hmr.get_workspace("agent_backend")

# 设置当前目标和任务
ws.active_goal = "实现任务队列"
ws.push_task({"name": "设计队列接口", "status": "todo", "priority": 1})
ws.push_task({"name": "实现优先级堆", "status": "todo", "priority": 2})

# 临时记录思考（不写入长期记忆）
ws.temporary_thoughts.append("考虑使用 heapq 实现最小堆")

# 手动保存工作区（ingest 后会自动保存，也可手动触发）
hmr.save_workspace("agent_backend")

# 完成一个任务
completed = ws.pop_task()
print(completed["name"])  # "实现优先级堆"（后进先出）

# 多代理场景
ws_frontend = hmr.get_workspace("agent_frontend")
ws_frontend.active_goal = "构建管理界面"

# 重启后工作区自动恢复
hmr2 = HMR(storage_path="./my_project")
ws_recovered = hmr2.get_workspace("agent_backend", create=False)
print(ws_recovered.active_goal)    # "实现任务队列"
print(len(ws_recovered.task_stack))  # 1（已完成一个）
```

---

### 记忆压缩

将多条相关记忆压缩为一条抽象知识，控制记忆总量。

```python
# 压缩指定类型的记忆
compressed = hmr.compress_memories(
    memory_type="execution",   # 压缩所有执行记录
    max_memories=20            # 最多处理 20 条
)

# 压缩指定 ID 的记忆
compressed = hmr.compress_memories(
    memory_ids=["mem_001", "mem_002", "mem_003"]
)

if compressed:
    print(compressed.title)    # "[压缩] 故障记录 + 压测"
    print(compressed.content)  # 提炼的抽象知识
    print(compressed.tags)     # [..., "compressed"]
```

**压缩策略：**
- 有 OpenAI API Key → LLM 提炼核心规律和模式
- 无 API Key → TF-IDF 关键词摘要

**自动压缩：**  
配置 `LifecycleConfig.max_memories_per_type` 后，当同类型记忆超过阈值时，
生命周期引擎会在后台自动触发压缩，无需手动调用。

---

### 系统状态

```python
status = hmr.get_system_status()

print(f"版本:          {status['version']}")
print(f"记忆总数:      {status['memory_fs']['total_memories']}")
print(f"向量总数:      {status['vector_store']['total_vectors']}")
print(f"数据同步:      {status['synced']}")         # True/False
print(f"Embedding:     {status['embedding_provider']}")  # openai/sentence_transformers/tfidf
print(f"图节点数:      {status['memory_graph']['total_nodes']}")
print(f"图边数:        {status['memory_graph']['total_edges']}")
print(f"调度主策略:    {status['scheduler']['dominant_strategy']}")
print(f"缓存命中率:    {status['scheduler']['cache_hit_rate']}")
print(f"逾期复习:      {status['overdue_reviews']} 条")
print(f"活跃工作区:    {status['active_workspaces']}")

# 生命周期状态
lc = status['lifecycle']
print(f"新鲜记忆:      {lc['by_state']['fresh']}")
print(f"活跃记忆:      {lc['by_state']['active']}")
print(f"衰退记忆:      {lc['by_state']['fading']}")
print(f"休眠记忆:      {lc['by_state']['dormant']}")
print(f"风险记忆:      {len(lc['at_risk'])} 条（即将被自动删除）")
```

---

## 高级组件

### Memory Scheduler 调度器

调度器决定每次召回用什么策略，是 HMR 从"检索工具"变成"记忆操作系统"的关键。

```python
# 查看调度统计
stats = hmr.scheduler.get_stats()
print(stats["strategy_counts"])   # 各策略使用次数
print(stats["cache_hit_rate"])    # 热缓存命中率
print(stats["dominant_strategy"]) # 最常用的策略

# 手动生成调度计划（不执行召回，只看调度决策）
plan = hmr.scheduler.schedule(
    query="为什么队列积压导致超时",
    context={"active_goal": "优化调度器"}
)
print(plan.strategy.value)  # "hybrid"
print(plan.use_jit)         # True
print(plan.top_k)           # 6
print(plan.reasoning)       # "有活跃目标（优化调度器），混合策略"

# 手动管理热缓存
hmr.scheduler.invalidate_cache("mem_001")  # 记忆更新后使相关缓存失效
```

**热缓存说明：**
- 容量：50 条（可在 `HotCache` 初始化时调整）
- TTL：300 秒（5分钟）
- 策略：LRU（最近最少使用自动淘汰）
- 同一查询的第二次请求直接从缓存返回，不再检索

---

### JIT Memory Compiler 即时编译器

把单次向量检索升级为多步推理检索，适合复杂问题。

```python
# 直接使用 JIT Compiler（recall 会自动调用，也可手动使用）
result = hmr.jit_compiler.compile(
    query="为什么 IPC 延迟导致调度器级联超时",
    context={"active_goal": "排查线上故障"},
    top_k=5,
    max_steps=3   # 最多 3 步检索
)

# 查看每步检索详情
for step in result.steps:
    print(f"第{step.step + 1}步: {step.query}")
    print(f"  找到: {len(step.memories)} 条")
    print(f"  置信度: {step.confidence}")
    print(f"  缺口: {step.gaps}")

# 查看查询改写轨迹
print("查询轨迹:", result.query_trace)
# ["为什么 IPC 延迟导致调度器级联超时", "IPC 设计原则 超时", "调度器 超时"]

print(result.reasoning)
# "JIT编译 2 步，查询轨迹：原始 → 改写1 → 改写2，候选 15 条 → 精选 5 条（置信度：0.82）"
```

**JIT 何时触发：**
- 查询包含"为什么"、"原因"、"cause"等推理词 → 自动触发
- 查询包含"历史"、"演化"、"timeline"等时间跨度词 → 自动触发
- `recall(strategy="jit")` 手动指定

---

### Memory Lifecycle Engine 生命周期引擎

记忆会自然衰退，不再需要的记忆自动清理。

```python
from hmr.engines.lifecycle import LifecycleConfig

# 自定义配置
config = LifecycleConfig(
    max_memories_per_type=80,      # 同类型超过 80 条触发自动压缩
    prune_retrievability=0.05,     # SM-2 可提取性低于 5% 考虑删除
    prune_min_age_days=7,          # 至少存在 7 天才允许删除
    prune_require_zero_access=True,# 只删除从未被访问的记忆
    consolidation_batch=20,        # 每次压缩最多 20 条
    auto_enabled=True,             # 是否开启自动检查
    check_interval_ingests=10,     # 每 10 次 ingest 检查一次
)

hmr = HMR(storage_path="./my_project", lifecycle_config=config)

# 手动触发完整检查
report = hmr.lifecycle.check_now(memory_type="execution")
print(report.summary())
# "检查 50 条；删除 3 条；压缩 20 → 1 条"
print(report.reasons)
# ["删除 [execution]《压测记录#1》（可提取性=0.02，存在14天，访问0次）", ...]

# 查看生命周期统计
stats = hmr.lifecycle.get_lifecycle_stats()
print(stats["by_state"])   # {"fresh": 5, "active": 30, "fading": 10, "dormant": 3}
print(stats["at_risk"])    # 即将被删除的记忆列表
```

**记忆生命周期状态：**

| 状态 | 条件 | 说明 |
|------|------|------|
| `fresh` | 创建不到 1 天 | 新摄入的记忆 |
| `active` | SM-2 可提取性 > 0.7 | 最近被访问，记忆清晰 |
| `fading` | 可提取性 0.3–0.7 | 正在褪色，需要复习 |
| `dormant` | 可提取性 < 0.3 | 久未使用，接近遗忘 |
| `pruned` | 可提取性 < 0.05 + 从未访问 + 存在 7 天+ | 自动删除 |

---

### Memory Graph 记忆图层

自动从记忆中提取实体和关系，构建结构化认知网络。

```python
# 图层随 ingest 自动更新，也可手动查询

# 查找与某实体相关的所有节点（深度 2 跳）
nodes = hmr.memory_graph.find_related("调度器", depth=2)
for node in nodes:
    print(f"[{node.node_type.value}] {node.label}  ({len(node.memory_ids)} 条记忆)")

# 获取因果链
chain = hmr.memory_graph.get_causal_chain("死锁")
for node, edge in chain:
    print(f"  →({edge.edge_type.value})→ {node.label}")
# →(causal)→ 队列积压 →(causal)→ 响应超时

# 图路径召回（找实体相关的所有记忆 ID）
memory_ids = hmr.memory_graph.get_memory_ids_for_query("IPC 超时原因")
print(f"图路径找到 {len(memory_ids)} 条相关记忆")

# 自动语义聚类
clusters = hmr.memory_graph.auto_cluster()
for c in clusters:
    print(f"聚类「{c.label}」: {len(c.node_ids)} 个节点")

# 图统计
stats = hmr.memory_graph.get_stats()
print(stats)
# {"total_nodes": 25, "total_edges": 38,
#  "node_types": {"entity": 15, "episode": 8, "concept": 2},
#  "edge_types": {"causal": 10, "temporal": 8, "semantic": 12, "part_of": 8}}
```

**图节点类型：**

| 类型 | 说明 | 来源 |
|------|------|------|
| `entity` | 系统/组件名（调度器、IPC、Agent） | 大写词 + 技术名词 |
| `episode` | 完整事件情节 | `execution` / `reflection` 类型记忆 |
| `concept` | 抽象概念（异步、死锁、优先级） | 中文技术名词 |

**图边类型：**

| 类型 | 含义 | 示例 |
|------|------|------|
| `causal` | 因果 A → B | 死锁 → 超时 |
| `temporal` | 时序 A 先于 B | 队列满 → 消息丢失 |
| `semantic` | 语义相近 | IPC ≈ 消息队列 |
| `part_of` | 组成 A ∈ B | 队列 ∈ 调度器 |

---

## 完整工作流示例

### 场景：多天开发项目

```python
from hmr.core.hmr import HMR

# ═══ 第一天：研究阶段 ═══════════════════════════════════════

hmr = HMR(storage_path="./scheduler_project")

# 记录研究发现
hmr.ingest(
    "IPC 应采用异步消息队列，基于 backpressure 控制背压，"
    "避免生产者速度超过消费者导致内存溢出",
    memory_type="concept",
    title="IPC 设计原则",
    metadata={"tags": ["ipc", "async", "backpressure"]}
)

hmr.ingest(
    "尝试了基于线程锁的同步调度，在并发 > 50 时出现死锁，"
    "根因是任务 A 等待任务 B 释放锁，形成环形等待",
    memory_type="execution",
    title="同步调度失败记录",
    metadata={"tags": ["failure", "deadlock"], "confidence": 0.95}
)

# 保存状态
hmr.save_runtime_state(
    goal="设计异步调度器",
    plan=["研究 IPC 协议 ✓", "研究调度算法 ✓", "设计 API", "实现", "压测"],
    context={"current_phase": "设计", "confidence": 0.6}
)

print("第一天工作完成，状态已保存")

# ═══ 第三天：继续开发 ════════════════════════════════════════

hmr = HMR(storage_path="./scheduler_project")   # 新进程启动

# 恢复状态（自动预加载相关记忆）
state = hmr.restore_runtime_state()
print(f"继续：{state.active_goal}")
print(f"计划进度：{state.current_plan}")

# 复杂查询，自动触发 JIT 多步检索
result = hmr.recall(
    query="为什么之前的同步方案会死锁，异步如何解决这个问题",
    context={"active_goal": state.active_goal}
)
print(f"召回策略: {result.recall_reasoning[:50]}")

# 记录新决策
hmr.ingest(
    "决定采用 asyncio 事件循环 + 优先级堆实现调度器，"
    "完全消除线程锁，用协程切换替代上下文切换",
    memory_type="decision",
    title="调度器技术选型决定",
    metadata={
        "tags": ["asyncio", "scheduler", "decision"],
        "runtime_dependencies": ["IPC 设计原则", "同步调度失败记录"]
    }
)

# 更新进度
hmr.save_runtime_state(
    goal="设计异步调度器",
    plan=["研究 IPC 协议 ✓", "研究调度算法 ✓", "设计 API ✓", "实现", "压测"],
    context={"current_phase": "实现", "confidence": 0.85}
)
```

### 场景：多代理协作

```python
hmr = HMR(storage_path="./team_project")

# 代理 A：后端
backend = hmr.get_workspace("agent_backend")
backend.active_goal = "实现调度器核心逻辑"
backend.push_task({"name": "实现优先级堆", "status": "in_progress"})

hmr.ingest(
    "调度器 API：scheduler.submit(task, priority=1-10)，"
    "scheduler.cancel(task_id)，scheduler.get_status(task_id)",
    memory_type="decision",
    title="调度器 API 设计",
    metadata={"tags": ["api", "scheduler"]}
)
hmr.save_workspace("agent_backend")

# 代理 B：前端
frontend = hmr.get_workspace("agent_frontend")
frontend.active_goal = "实现调度器管理 UI"
frontend.push_task({"name": "设计任务列表页面", "status": "todo"})

# 前端从记忆中获取后端 API 设计
result = hmr.recall(
    query="调度器 API 接口",
    strategy="semantic"
)
api_doc = result.memory_objects[0] if result.memory_objects else None
print(f"前端获取到 API 文档: {api_doc.title if api_doc else '未找到'}")

hmr.save_workspace("agent_frontend")

# 重启后两个代理的工作区都完整恢复
hmr2 = HMR(storage_path="./team_project")
ws_b = hmr2.get_workspace("agent_backend", create=False)
ws_f = hmr2.get_workspace("agent_frontend", create=False)
print(f"后端代理目标: {ws_b.active_goal}")
print(f"前端代理目标: {ws_f.active_goal}")
```

---

## 配置参考

### LifecycleConfig 完整配置

```python
from hmr.engines.lifecycle import LifecycleConfig

config = LifecycleConfig(
    # 自动压缩触发条件
    max_memories_per_type=80,       # 同类型记忆超过此数触发压缩（默认 80）
    consolidation_batch=20,         # 每次最多压缩多少条（默认 20）
    consolidation_keep_ratio=0.3,   # 压缩后原记忆权重降为原来的 30%（默认 0.3）

    # 自动删除条件（以下条件同时满足才删除）
    prune_retrievability=0.05,      # SM-2 可提取性阈值（默认 0.05 = 5%）
    prune_min_age_days=7,           # 最少存在天数（默认 7 天）
    prune_require_zero_access=True, # 是否要求从未被访问（默认 True）

    # 运行控制
    auto_enabled=True,              # 是否开启自动生命周期（默认 True）
    check_interval_ingests=10,      # 每 N 次 ingest 检查一次（默认 10）
)
```

### 环境变量

```bash
OPENAI_API_KEY=sk-...         # OpenAI API Key（用于 Embedding 和 LLM 摘要）
```

### 目录结构

```
hmr_data/
├── memories/
│   ├── concepts/           # concept 类型记忆
│   ├── executions/         # execution 类型记忆
│   ├── decisions/          # decision 类型记忆
│   └── ...
├── runtimes/               # RuntimeState 文件
├── workspaces/             # AgentWorkspace 文件
├── vector_store/
│   ├── vectors.json        # 向量数据（持久化）
│   └── vector_metadata.json
├── memory_graph/
│   └── memory_graph.json   # 图数据（持久化）
├── index/
│   ├── memory_index.json
│   └── runtime_index.json
└── schema_version.json
```

---

## 故障排除

### 问题：启动时显示"重建向量索引"

```
[HMR] 检测到向量为空，从 MemoryFS 重建（N 条）...
```

**正常现象**，首次启动或 `vector_store/` 目录被删除时触发。
重建完成后不再出现，等待即可。

### 问题：召回结果不相关

可能原因和解决方案：

```python
# 1. 检查 Embedding 提供者
status = hmr.get_system_status()
print(status["embedding_provider"])
# 如果是 "tfidf"，建议安装更好的 Embedding

# 2. 手动指定 JIT 策略
result = hmr.recall(query="...", strategy="jit")

# 3. 检查向量和记忆是否同步
print(status["synced"])  # 应为 True

# 4. 重建向量索引（当 synced=False 时）
hmr.vector_store.rebuild_from_memories(hmr.memory_fs.list_memories())
```

### 问题：compress_memories 返回 None

```python
# 原因：满足压缩条件的记忆不足 2 条
# 检查有多少条低权重记忆
memories = hmr.memory_fs.list_memories(memory_type="execution")
low_weight = [m for m in memories if m.temporal_weight < 0.5]
print(f"可压缩记忆: {len(low_weight)} 条")

# 如需强制压缩，降低阈值（手动修改后再写回）
for m in memories[:5]:
    m.temporal_weight = 0.3
    hmr.memory_fs.write_memory(m)
result = hmr.compress_memories(memory_type="execution")
```

### 问题：Memory Graph 节点数为 0

```python
# 规则提取器依赖技术名词格式
# 确保记忆内容包含大写英文词或中文技术术语

# 好的记忆内容（会提取到实体）
hmr.ingest("Scheduler 调度器在高并发下出现 IPC 积压", ...)

# 不好的内容（难以提取实体）
hmr.ingest("有问题了，查了一下，发现有点慢", ...)
```

### 问题：工作区重启后消失

```python
# 确保调用了 save_workspace
ws = hmr.get_workspace("my_agent")
ws.active_goal = "..."
hmr.save_workspace("my_agent")  # ← 必须调用，或等待 ingest 触发自动保存
```

---

## 版本历史

| 版本 | 主要变化 |
|------|---------|
| **v1.5.0** | 新增 JIT Compiler、Memory Scheduler、Lifecycle Engine、Memory Graph |
| **v1.1.0** | 修复 VectorStore 持久化、真实 Embedding、SM-2 算法、Workspace 持久化 |
| **v1.0.0** | 初始版本，基础记忆存储和召回 |

---

*HMR v1.5 — 让 AI 系统真正记住，而不只是查询。*
