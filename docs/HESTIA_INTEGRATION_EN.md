# HMR v1 in Hestia OS

## Integration Overview

HMR (Hestia Memory Runtime) is the **memory and cognitive state infrastructure** at the core of Hestia OS.

```
Hestia OS Architecture
│
├── Kernel                    (Low-level process management)
├── Scheduler                 (Task scheduling)
├── Agent Runtime             (Agent execution engine)
├── Execution Engine          (Command/action execution)
│
├── HMR ★ (Memory Infrastructure)
│   ├── MemoryFS              (Structured memory storage)
│   ├── Semantic Memory       (Vector-based retrieval)
│   ├── Runtime State         (Cognitive state persistence)
│   ├── CWG                   (Runtime dependency tracking)
│   ├── Agent Workspaces      (Per-agent memory)
│   ├── Temporal Engine       (Memory aging/forgetting)
│   └── Active Recall         (Predictive memory loading)
│
└── World Model Layer         (Environmental understanding)
```

## HMR as OS Layer

### Why HMR is not a library

Traditional memory: **external component** you optionally add

HMR in Hestia: **core OS infrastructure** - all operations flow through it

```
Traditional Agent:
User Input → Process → Output
(Memory is optional, external)

Hestia with HMR:
User Input → Ingest → Process → Save State → Output
(Memory is central to every operation)
```

## Core Responsibilities

### 1. Runtime Continuity

```python
# When Hestia scheduler needs to resume an agent:

# Before (without HMR):
agent.restart()  # → Lost all context

# With HMR:
state = hmr.restore_runtime_state(agent_id)
agent.continue_from(state)  # → Full context restored
```

### 2. Cognitive State Persistence

```python
# HMR tracks what agent is thinking

# At checkpoint:
hmr.save_runtime_state(
    goal=agent.current_goal,
    plan=agent.plan,
    context=agent.active_context,
    pending_tasks=agent.task_queue
)

# After restart:
state = hmr.restore_runtime_state()
# Agent continues: "I was working on...", remembers everything
```

### 3. Multi-Agent Coordination

```python
# Each agent has workspace
agent_a_ws = hmr.get_workspace("agent_frontend")
agent_b_ws = hmr.get_workspace("agent_backend")

# CWG tracks dependencies
hmr.cwg.add_edge(
    agent_b_node,  # backend blocks
    agent_a_node,  # frontend
    "blocks"
)

# Check if agent is blocked
blockers = hmr.cwg.get_blockers(agent_a_node)
if blockers:
    agent_a.wait_for(blockers[0])
```

### 4. Intelligent Context Loading

```python
# When agent resumes:

# Without HMR:
agent.process(user_input)  # No prior context

# With HMR:
prior_context = hmr.recall(
    query=user_input,
    context=current_runtime
)  # Preloads relevant memories
agent.process(user_input, context=prior_context)
```

## Integration Points

### 1. Scheduler Integration

```python
# In Hestia Scheduler

class Agent:
    def __init__(self, agent_id, hmr: HMR):
        self.hmr = hmr
        self.workspace = hmr.get_workspace(agent_id)
    
    async def execute_task(self, task):
        # Load runtime state
        state = self.hmr.restore_runtime_state()
        
        # Execute
        result = await self.process(task, context=state.current_context)
        
        # Save state
        self.hmr.save_runtime_state(
            goal=self.current_goal,
            plan=self.plan,
            context=self.current_context
        )
        
        return result
```

### 2. Kernel Integration

```python
# In Hestia Kernel - process management

class ProcessManager:
    def __init__(self, hmr: HMR):
        self.hmr = hmr
    
    def suspend_process(self, process_id):
        # Before killing, save state
        runtime_state = self.hmr.snapshot()
        process.save(runtime_state)
        process.kill()
    
    def resume_process(self, process_id):
        # Restore from saved state
        runtime_state = process.load()
        self.hmr.restore_snapshot(runtime_state)
        process.resume()
```

### 3. World Model Integration

```python
# In World Model layer

class WorldModel:
    def __init__(self, hmr: HMR):
        self.hmr = hmr
    
    def observe(self, observation):
        # Record observation as memory
        self.hmr.ingest(
            content=str(observation),
            memory_type="execution",
            metadata={"source": "sensor", "timestamp": now()}
        )
        
        # Update model
        self.update(observation)
```

## Configuration for Hestia

### environment.yaml

```yaml
hestia:
  os:
    memory:
      engine: "hmr"
      storage_path: "/var/hestia/hmr_data"
      embedding_model: "text-embedding-3-small"
    
    # Agent configuration
    agents:
      default:
        memory_capacity: "1GB"
        temporal_decay_factor: 0.05
        active_recall_enabled: true
      
      long_running:
        memory_capacity: "5GB"
        temporal_decay_factor: 0.02
```

## Typical Hestia+HMR Workflow

### Project: Multi-Day Development

```
Day 1 - Session 1:
├─ Agent created
├─ Research phase
│  ├─ Ingest: IPC findings
│  ├─ Ingest: Design approaches
│  └─ Ingest: Failed attempts
├─ Save runtime state (goal, plan, context)
└─ Agent paused

[Days pass...]

Day 3 - Session 2:
├─ Agent resumed
├─ Restore runtime state
│  ├─ Goal: "Design Scheduler"
│  ├─ Plan: [Research ✓, Design, Implement]
│  └─ Context: Loads automatically
├─ Active recall preloads
│  ├─ IPC findings
│  ├─ Design approaches
│  └─ Failed attempts
├─ Agent continues: "I was designing the scheduler..."
├─ Implementation phase
├─ Save updated runtime state
└─ Agent paused

[Next iteration...]
```

## Performance in Hestia

### Memory Efficiency

```
Per Agent:
- Runtime state: ~50KB
- Workspace: ~20KB
- Active memories (cached): ~500KB-10MB

System:
- 100 agents = 50MB+ runtime state
- CWG graph = 1-100MB (depends on complexity)
```

### Access Patterns

```
Fast path (milliseconds):
- Load runtime state ← Already cached
- Recall (with filters) ← Vector search ~50-100ms
- Update workspace ← In-memory

Slow path (seconds):
- Full MemoryFS scan
- Recompute embeddings
- Rebuild indices
```

## Advanced Features in Hestia

### 1. Distributed HMR

```python
# In Hestia cluster

class DistributedHMR:
    """HMR across multiple nodes"""
    
    def __init__(self):
        self.local_hmr = HMR()  # Local memory
        self.shared_hmr = RemoteHMR("hmr-service")  # Network
    
    def ingest(self, memory):
        # Local copy
        self.local_hmr.ingest(memory)
        
        # Sync to cluster
        self.shared_hmr.ingest(memory)
```

### 2. Persistent Checkpoints

```python
# Hestia fault tolerance using HMR

class CheckpointManager:
    def create_checkpoint(self, hmr: HMR):
        # Snapshot entire system state
        snapshot = hmr.snapshot()
        
        # Save to durable storage
        storage.save(snapshot)
    
    def recover_from_checkpoint(self, checkpoint_id):
        # Restore entire system
        snapshot = storage.load(checkpoint_id)
        hmr.restore_snapshot(snapshot)
```

### 3. Learning Over Time

```python
# Hestia OS self-improvement

async def daily_learning():
    # Compress execution traces
    compression_result = hmr.compress_memories(
        memory_type="execution"
    )
    
    # Extract patterns
    patterns = extract_patterns(compression_result)
    
    # Store as learnings
    hmr.ingest(
        patterns,
        memory_type="concept",
        title="Learned Pattern"
    )
```

## Hestia+HMR Advantages

### vs Traditional Agents

| Feature | Traditional | Hestia+HMR |
|---------|-----------|-----------|
| Context | Lost on restart | Fully restored |
| State | Volatile | Persistent |
| Multi-agent | Independent | Coordinated |
| Learning | Session-based | Continuous |
| Recovery | From scratch | From checkpoint |

### vs Other Memory Systems

| Feature | RAG | Claude Memory | HMR in Hestia |
|---------|-----|---------------|--------------|
| Architecture | Document retrieval | Session facts | OS infrastructure |
| Scope | Query-based | Conversation | System-wide |
| Persistence | Database | Session | Runtime checkpoints |
| Agents | N/A | N/A | First-class |
| Time awareness | None | None | Forgetting curves |

## Deployment

### Single-Machine Hestia

```bash
# Install Hestia + HMR
pip install hestia-os

# HMR data stored locally
/var/hestia/hmr_data/
├── memories/
├── runtimes/
└── index/
```

### Distributed Hestia

```bash
# Hestia on multiple nodes
# HMR synced across cluster

# Node 1 (primary)
hmr-service --primary --listen 0.0.0.0:9000

# Node 2 (replica)
hmr-service --replica --peer node1:9000
```

## Monitoring

### HMR Health Metrics

```python
# In Hestia monitoring

metrics = {
    "hmr_memory_footprint": get_memory_usage(),
    "hmr_disk_usage": mfs.get_statistics()['disk_usage_mb'],
    "active_memories": len(mfs.list_memories()),
    "vector_index_size": vs.get_stats()['total_vectors'],
    "active_runtimes": len(runtime_engine.get_active_runtimes()),
    "recall_latency_p95": measure_recall_latency(),
}
```

## Roadmap

### v1.1 ✅ 已发布
- ✅ Core HMR stable
- 🔲 Distributed HMR prototype
- 🔲 Hestia integration examples

### v2.0 ✅ 已发布
- 🔲 ThoughtChain engine
- 🔲 Advanced compression
- 🔲 Self-optimization

### v3.0 🔲 规划中
- 🔲 Full Cognitive OS
- 🔲 Multi-agent ecosystems
- 🔲 Autonomous learning

## Contributing to Hestia+HMR

To contribute, please open an issue or pull request on GitHub.

## License

HMR Core: **MIT License** (Open)

> **Note on enterprise features:** An enterprise tier is planned for future releases (audit log export, private deployment support, SLA guarantees). The scope is not yet finalised. All features in the current release are covered by the MIT License.

---

**HMR is the brain of Hestia OS. Making cognitive persistence the foundation of AI systems.**
