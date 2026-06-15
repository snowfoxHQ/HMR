# HMR v1 在 Hestia OS 中 (中文)

## 集成概述

HMR (Hestia Memory Runtime) 是 **Hestia OS 中的记忆和认知状态基础设施**的核心。

```
Hestia OS 架构
│
├── Kernel                    (低级进程管理)
├── Scheduler                 (任务调度)
├── Agent Runtime             (代理执行引擎)
├── Execution Engine          (命令/动作执行)
│
├── HMR ★ (记忆基础设施)
│   ├── MemoryFS              (结构化记忆存储)
│   ├── Semantic Memory       (向量基检索)
│   ├── Runtime State         (认知状态持久化)
│   ├── CWG                   (运行时依赖追踪)
│   ├── Agent Workspaces      (每个代理的记忆)
│   ├── Temporal Engine       (记忆衰变/遗忘)
│   └── Active Recall         (预测性记忆加载)
│
└── World Model Layer         (环境理解)
```

## HMR 为什么是操作系统层

### 传统记忆：**外部组件** 你可选地添加

HMR 在 Hestia：**核心操作系统基础设施** - 所有操作都通过它流动

```
传统代理:
用户输入 → 处理 → 输出
(记忆是可选的，外部的)

Hestia 带 HMR:
用户输入 → 摄入 → 处理 → 保存状态 → 输出
(记忆在每个操作中都很核心)
```

## 核心职责

### 1. 运行时连续性

```python
# 当 Hestia 调度器需要恢复一个代理时:

# 之前 (没有 HMR):
agent.restart()  # → 丢失所有上下文

# 使用 HMR:
state = hmr.restore_runtime_state(agent_id)
agent.continue_from(state)  # → 完整上下文恢复
```

### 2. 认知状态持久化

```python
# HMR 追踪代理的思考

# 在检查点:
hmr.save_runtime_state(
    goal=agent.current_goal,
    plan=agent.plan,
    context=agent.active_context,
    pending_tasks=agent.task_queue
)

# 重启后:
state = hmr.restore_runtime_state()
# 代理继续: "我在处理...", 记得一切
```

### 3. 多代理协调

```python
# 每个代理有工作区
agent_a_ws = hmr.get_workspace("agent_frontend")
agent_b_ws = hmr.get_workspace("agent_backend")

# CWG 追踪依赖
hmr.cwg.add_edge(
    agent_b_node,  # 后端阻塞
    agent_a_node,  # 前端
    "blocks"
)

# 检查代理是否被阻塞
blockers = hmr.cwg.get_blockers(agent_a_node)
if blockers:
    agent_a.wait_for(blockers[0])
```

### 4. 智能上下文加载

```python
# 当代理恢复时:

# 没有 HMR:
agent.process(user_input)  # 没有先前上下文

# 使用 HMR:
prior_context = hmr.recall(
    query=user_input,
    context=current_runtime
)  # 预加载相关记忆
agent.process(user_input, context=prior_context)
```

## 集成点

### 1. Scheduler 集成

```python
# 在 Hestia Scheduler 中

class Agent:
    def __init__(self, agent_id, hmr: HMR):
        self.hmr = hmr
        self.workspace = hmr.get_workspace(agent_id)
    
    async def execute_task(self, task):
        # 加载运行时状态
        state = self.hmr.restore_runtime_state()
        
        # 执行
        result = await self.process(task, context=state.current_context)
        
        # 保存状态
        self.hmr.save_runtime_state(
            goal=self.current_goal,
            plan=self.plan,
            context=self.current_context
        )
        
        return result
```

### 2. Kernel 集成

```python
# 在 Hestia Kernel - 进程管理

class ProcessManager:
    def __init__(self, hmr: HMR):
        self.hmr = hmr
    
    def suspend_process(self, process_id):
        # 在杀死之前，保存状态
        runtime_state = self.hmr.snapshot()
        process.save(runtime_state)
        process.kill()
    
    def resume_process(self, process_id):
        # 从保存的状态恢复
        runtime_state = process.load()
        self.hmr.restore_snapshot(runtime_state)
        process.resume()
```

### 3. World Model 集成

```python
# 在 World Model 层

class WorldModel:
    def __init__(self, hmr: HMR):
        self.hmr = hmr
    
    def observe(self, observation):
        # 记录观察为记忆
        self.hmr.ingest(
            content=str(observation),
            memory_type="execution",
            metadata={"source": "sensor", "timestamp": now()}
        )
        
        # 更新模型
        self.update(observation)
```

## Hestia 配置

### environment.yaml

```yaml
hestia:
  os:
    memory:
      engine: "hmr"
      storage_path: "/var/hestia/hmr_data"
      embedding_model: "text-embedding-3-small"
    
    # 代理配置
    agents:
      default:
        memory_capacity: "1GB"
        temporal_decay_factor: 0.05
        active_recall_enabled: true
      
      long_running:
        memory_capacity: "5GB"
        temporal_decay_factor: 0.02
```

## 典型的 Hestia+HMR 工作流

### 项目：多日开发

```
第一天 - 会话 1:
├─ 代理已创建
├─ 研究阶段
│  ├─ 摄入: IPC 发现
│  ├─ 摄入: 设计方法
│  └─ 摄入: 失败的尝试
├─ 保存运行时状态 (目标、计划、上下文)
└─ 代理暂停

[几天过去...]

第三天 - 会话 2:
├─ 代理已恢复
├─ 恢复运行时状态
│  ├─ 目标: "设计调度器"
│  ├─ 计划: [研究 ✓, 设计, 实现]
│  └─ 上下文: 自动加载
├─ 主动召回预加载
│  ├─ IPC 发现
│  ├─ 设计方法
│  └─ 失败的尝试
├─ 代理继续: "我在设计调度器..."
├─ 实现阶段
├─ 保存更新的运行时状态
└─ 代理暂停

[下一个迭代...]
```

## Hestia 中的性能

### 内存效率

```
每个代理:
- 运行时状态: ~50KB
- 工作区: ~20KB
- 活跃记忆 (缓存): ~500KB-10MB

系统:
- 100 个代理 = 50MB+ 运行时状态
- CWG 图 = 1-100MB (取决于复杂性)
```

### 访问模式

```
快速路径 (毫秒):
- 加载运行时状态 ← 已缓存
- 召回 (带过滤) ← 向量搜索 ~50-100ms
- 更新工作区 ← 内存中

慢速路径 (秒):
- 完整 MemoryFS 扫描
- 重新计算嵌入
- 重建索引
```

## Hestia 中的高级特性

### 1. 分布式 HMR

```python
# 在 Hestia 集群中

class DistributedHMR:
    """跨多个节点的 HMR"""
    
    def __init__(self):
        self.local_hmr = HMR()  # 本地记忆
        self.shared_hmr = RemoteHMR("hmr-service")  # 网络
    
    def ingest(self, memory):
        # 本地副本
        self.local_hmr.ingest(memory)
        
        # 同步到集群
        self.shared_hmr.ingest(memory)
```

### 2. 持久检查点

```python
# Hestia 容错使用 HMR

class CheckpointManager:
    def create_checkpoint(self, hmr: HMR):
        # 快照整个系统状态
        snapshot = hmr.snapshot()
        
        # 保存到持久存储
        storage.save(snapshot)
    
    def recover_from_checkpoint(self, checkpoint_id):
        # 恢复整个系统
        snapshot = storage.load(checkpoint_id)
        hmr.restore_snapshot(snapshot)
```

### 3. 随时间学习

```python
# Hestia OS 自我改进

async def daily_learning():
    # 压缩执行轨迹
    compression_result = hmr.compress_memories(
        memory_type="execution"
    )
    
    # 提取模式
    patterns = extract_patterns(compression_result)
    
    # 存储为学习
    hmr.ingest(
        patterns,
        memory_type="concept",
        title="学到的模式"
    )
```

## Hestia+HMR 优势

### vs 传统代理

| 特性 | 传统 | Hestia+HMR |
|------|------|-----------|
| 上下文 | 重启时丢失 | 完全恢复 |
| 状态 | 易失性 | 持久性 |
| 多代理 | 独立 | 协调 |
| 学习 | 仅会话 | 连续 |
| 恢复 | 从头开始 | 从检查点 |

### vs 其他记忆系统

| 特性 | RAG | Claude 记忆 | HMR in Hestia |
|------|-----|-----------|--------------|
| 架构 | 文档检索 | 会话事实 | 操作系统基础设施 |
| 范围 | 基于查询 | 对话 | 系统级 |
| 持久性 | 数据库 | 仅会话 | 运行时检查点 |
| 代理 | N/A | N/A | 一流的 |
| 时间 | 无 | 无 | 遗忘曲线 |

## 部署

### 单机 Hestia

```bash
# 安装 Hestia + HMR
pip install hestia-os

# HMR 数据存储在本地
/var/hestia/hmr_data/
├── memories/
├── runtimes/
└── index/
```

### 分布式 Hestia

```bash
# 多节点上的 Hestia
# HMR 跨集群同步

# 节点 1 (主)
hmr-service --primary --listen 0.0.0.0:9000

# 节点 2 (副本)
hmr-service --replica --peer node1:9000
```

## 监控

### HMR 健康指标

```python
# 在 Hestia 监控中

metrics = {
    "hmr_memory_footprint": get_memory_usage(),
    "hmr_disk_usage": mfs.get_statistics()['disk_usage_mb'],
    "active_memories": len(mfs.list_memories()),
    "vector_index_size": vs.get_stats()['total_vectors'],
    "active_runtimes": len(runtime_engine.get_active_runtimes()),
    "recall_latency_p95": measure_recall_latency(),
}
```

## 路线图

### v1.1 (下个月)
- ✅ HMR 核心稳定
- 🔲 分布式 HMR 原型
- 🔲 Hestia 集成示例

### v2.0 (下个季度)
- 🔲 ThoughtChain 引擎
- 🔲 高级压缩
- 🔲 自优化

### v3.0 (未来)
- 🔲 完整认知操作系统
- 🔲 多代理生态
- 🔲 自主学习

## 贡献给 Hestia+HMR

如需贡献，请在 GitHub 上提交 Issue 或 Pull Request。

## 许可证

HMR Core: **MIT 许可证** (开放)

> **企业版说明：** 企业版（审计日志导出、私有化部署、SLA 保证）正在规划中，具体功能范围尚未最终确定。当前版本的全部功能均遵循 MIT 许可证。

---

**HMR 是 Hestia OS 的大脑。让认知持久性成为 AI 系统的基础。**
