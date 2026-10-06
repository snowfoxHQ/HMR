# HMR v2.0 User Manual (English)

**Hestia Memory Runtime — Persistent Cognitive Runtime**

Version: v2.0.0

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Installation](#2-installation)
3. [Core Concepts](#3-core-concepts)
4. [Core API](#4-core-api)
   - [Initialisation](#41-initialisation)
   - [Ingesting Memory](#42-ingesting-memory)
   - [Recalling Memory](#43-recalling-memory)
   - [Runtime State](#44-runtime-state)
   - [Agent Workspaces](#45-agent-workspaces)
   - [Memory Compression](#46-memory-compression)
5. [v2.0 New: ThoughtChain Engine](#5-v20-new-thoughtchain-engine)
6. [v2.0 New: Memory Policy Engine](#6-v20-new-memory-policy-engine)
7. [v2.0 New: Self-Evolution Engine](#7-v20-new-self-evolution-engine)
8. [v1.5 Advanced Components Recap](#8-v15-advanced-components-recap)
9. [Complete Workflow Examples](#9-complete-workflow-examples)
10. [Configuration Reference](#10-configuration-reference)
11. [System Status Monitoring](#11-system-status-monitoring)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Quick Start

```python
from hmr.core.hmr import HMR
from hmr.engines.thought_chain import ThoughtType

# Initialise
hmr = HMR(storage_path="./my_project")

# ── Store memory (Policy auto-detects type) ──────────────────
hmr.ingest("IPC queue backup caused timeouts — consumer threads insufficient",
           use_policy=True)
# → automatically classified as 'execution', confidence 0.85

# ── Reasoning chain: record the full thought process ─────────
chain = hmr.start_thinking("Diagnose IPC timeout root cause")
hmr.think(chain.chain_id, "Queue depth sustained >800",      ThoughtType.OBSERVATION)
hmr.think(chain.chain_id, "Consumer threads may be too few", ThoughtType.HYPOTHESIS)
hmr.think(chain.chain_id, "Scale consumer threads to x3",    ThoughtType.DECISION)
hmr.think(chain.chain_id, "Deployment complete",              ThoughtType.ACTION)

# ── Reflect: evaluate reasoning quality; insights auto-stored ─
ref = hmr.reflect_on(chain.chain_id, "Latency dropped 800ms → 50ms", rating=0.9)
print(ref.accuracy)    # 0.75
print(ref.insights)    # ['Effective decision path: ...', 'Goal achieved (90%)']

# ── Next time: fetch the best historical decision ────────────
best = hmr.best_decision_for("IPC queue backup")
# → "[Historical ref, accuracy=90%] Scale consumer threads x3 + raise priority"

# ── Recall: intelligent multi-strategy retrieval ─────────────
result = hmr.recall(query="why does IPC time out", top_k=5)
print(result.recall_reasoning)   # "[HYBRID] JIT compiled 2 steps..."

# ── Save cognitive state ──────────────────────────────────────
hmr.save_runtime_state(goal="Optimise IPC performance",
                        plan=["Analyse ✓", "Scale ✓", "Validate"])

# ── After restart: full restoration ──────────────────────────
hmr2 = HMR(storage_path="./my_project")
state = hmr2.restore_runtime_state()
# → goal="Optimise IPC performance"
# → vector index, SM-2 state, Policy weights — all restored

# ── Self-evolve ───────────────────────────────────────────────
report = hmr.evolve()
print(report["summary"])   # "Evolution done: abstracted 1 cluster, resolved 0 contradictions"
```

---

## 2. Installation

### Minimal (built-in TF-IDF, always works)

```bash
pip install pydantic numpy
```

### Recommended (better semantic understanding)

```bash
# Option A: OpenAI Embeddings (best quality)
pip install openai
export OPENAI_API_KEY="sk-..."

# Option B: Local model (no API key required)
pip install sentence-transformers
```

HMR detects and selects the best Embedding provider automatically:

```
Priority: OpenAI > sentence-transformers > TF-IDF n-gram
```

### Verify

```python
from hmr.core.hmr import HMR
hmr = HMR()
s = hmr.get_system_status()
print(s["version"])             # 2.0.0
print(s["embedding_provider"]) # openai / sentence_transformers / tfidf
```

---

## 3. Core Concepts

### Design Philosophy

```
Traditional AI:  Memory = Storage
HMR v2.0:        Memory = Persistent Cognitive Runtime
                  ├── Stores *how* it thought, not just *what* happened
                  ├── Retrieves, predicts, reasons, and reflects
                  ├── Accumulates and then self-evolves
                  └── Continuous across sessions — restart = pause, not loss
```

### Three New Concepts in v2.0

**ThoughtChain**
- Explicit record of a reasoning process: Observation → Hypothesis → Decision → Action → Reflection
- After execution triggers reflection: marks which judgements were wrong
- Insights auto-stored as long-term memory; successful chains guide future decisions

**Memory Policy**
- Three sub-policies: IngestPolicy (what to store) / RecallPolicy (how to retrieve) / ForgetPolicy (how to forget)
- Every `feedback()` call nudges policy weights via SGD
- Works for both Chinese and English via character-level keyword matching — no tokeniser needed

**Self-Evolution**
- PatternDetector: finds clusters of memories with >75% similarity
- KnowledgeAbstractor: distils clusters into higher-order concepts
- ContradictionResolver: finds semantically opposite memory pairs, keeps the higher-confidence one
- StrategyOptimizer: analyses usage patterns, recommends optimal config parameters

### Memory Types

| Type | Purpose | Example |
|------|---------|---------|
| `concept` | Abstract knowledge, design principles, recommendations | "Recommend async message queue" |
| `decision` | Decisions made + rationale | "Decided to use asyncio approach" |
| `execution` | Execution traces, failure records | "IPC backup caused timeouts" |
| `reflection` | Post-mortems, root-cause summaries | "Deadlock caused task blockage" |
| `project` | Project context | "HMR v2 goals" |
| `task` | Task definitions | "Implement priority queue" |
| `agent_memory` | Agent-private memories | "agent_frontend UI decisions" |
| `workflow` | Process definitions | "Release process SOP" |

### ThoughtType Values

| Value | Meaning | Example |
|-------|---------|---------|
| `OBSERVATION` | Observed fact | "Queue depth sustained >800" |
| `HYPOTHESIS` | Proposed hypothesis | "Consumer threads may be too few" |
| `DECISION` | Decision made | "Scale consumer threads to x3" |
| `ACTION` | Action executed | "Deployment complete" |
| `OUTCOME` | Result of the action | "Latency dropped to 50ms" |
| `REFLECTION` | After-the-fact review | "Scaling was effective — use as first response" |
| `INSIGHT` | Distilled general knowledge | "Consumer count should scale linearly with concurrency" |

---

## 4. Core API

### 4.1 Initialisation

```python
from hmr.core.hmr import HMR
from hmr.engines.lifecycle import LifecycleConfig

hmr = HMR(
    storage_path="./hmr_data",                 # Root data directory
    embedding_model="text-embedding-3-small",   # OpenAI model name
    llm_api_key="sk-...",                       # Or set OPENAI_API_KEY env var
    lifecycle_config=LifecycleConfig(            # Optional lifecycle tuning
        max_memories_per_type=80,
        check_interval_ingests=10,
    )
)
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `storage_path` | `"./hmr_data"` | Root directory for all persistent data |
| `embedding_model` | `"text-embedding-3-small"` | OpenAI embedding model |
| `llm_api_key` | `None` | Also accepts `OPENAI_API_KEY` env var |
| `lifecycle_config` | Defaults | See [Configuration Reference](#10-configuration-reference) |

---

### 4.2 Ingesting Memory

```python
memory = hmr.ingest(
    content="IPC queue backed up >1000 entries at concurrency >500; responses timed out",
    memory_type="execution",       # explicit type, or omit and let Policy decide
    title="IPC Backup Incident",
    metadata={
        "tags": ["ipc", "incident", "timeout"],
        "runtime_dependencies": ["IPC Design Principle", "Scheduler"],
        "confidence": 0.9
    },
    use_policy=False               # True = Policy auto-infers type and confidence
)
```

**use_policy=True — auto-classification examples:**

```python
m1 = hmr.ingest("IPC backup caused timeouts — consumer threads insufficient",
                 use_policy=True)
print(m1.type)    # execution

m2 = hmr.ingest("Recommend async message queues for high-concurrency IPC",
                 use_policy=True)
print(m2.type)    # concept

m3 = hmr.ingest("Decided to use asyncio + priority heap approach",
                 use_policy=True)
print(m3.type)    # decision

m4 = hmr.ingest("Deadlock caused task blockage; root cause: circular wait",
                 use_policy=True)
print(m4.type)    # reflection
```

**What `ingest` triggers automatically:**
- Vector embedding generation
- SM-2 temporal state initialisation
- Memory Graph entity extraction
- Lifecycle check (async background)
- Cognitive graph (CWG) update

---

### 4.3 Recalling Memory

```python
result = hmr.recall(
    query="why does IPC latency cause Scheduler timeouts?",
    context={"active_goal": "Diagnose timeout", "pending_tasks": [...]},
    top_k=5,
    strategy="jit",     # force a strategy (optional — auto-selected by default)
    use_policy=True     # Policy assists scheduling (default: True)
)

print(result.recall_reasoning)    # "[JIT] JIT compiled 2 steps, ..."
for mem in result.memory_objects:
    score = result.relevance_scores[mem.id]
    print(f"[{score:.2f}] [{mem.type}] {mem.title}")
```

**Strategy options:**

| strategy | Best for | Characteristic |
|----------|---------|----------------|
| `"semantic"` | Simple similarity queries | Single vector search — fastest |
| `"temporal"` | Time-related ("recent", "last time") | Sorted by recency |
| `"jit"` | Complex reasoning ("why", "cause") | Multi-step — most accurate |
| `"hybrid"` | Active working goal present | Semantic + graph path combined |
| `"graph"` | Entity relationship queries | Graph path supplements candidates |
| `None` | General use (recommended) | Scheduler auto-decides |

**Return value — `RecallResult`:**

```python
result.memory_objects     # List[MemoryObject], sorted by relevance
result.recall_reasoning   # Strategy explanation and reasoning trace
result.relevance_scores   # Dict[memory_id, float]
result.predicted_need     # List[str] — what the system predicted you need
```

---

### 4.4 Runtime State

#### Save

```python
state = hmr.save_runtime_state(
    goal="Design async Scheduler",
    plan=["Research IPC ✓", "Design API ✓", "Implement", "Load test"],
    context={
        "current_focus": "implementation phase",
        "blockers": [],
        "confidence": 0.85
    }
)
print(state.runtime_id)   # rt_a1b2c3d4
```

#### Restore

```python
hmr2 = HMR(storage_path="./my_project")
state = hmr2.restore_runtime_state()              # latest state
state = hmr2.restore_runtime_state("rt_a1b2c3d4") # specific state

print(state.active_goal)    # "Design async Scheduler"
print(state.current_plan)   # ["Research IPC ✓", ...]
```

**Restoration auto-executes:**
1. SM-2 memory state recovery (per-memory review history)
2. Pre-loads memories most relevant to the current goal
3. Policy weights restored

---

### 4.5 Agent Workspaces

```python
# Get or create workspace (auto-persisted)
ws = hmr.get_workspace("agent_backend")

ws.active_goal = "Implement task queue"
ws.push_task({"name": "Design interface", "status": "todo"})
ws.push_task({"name": "Implement priority heap", "status": "todo"})
ws.temporary_thoughts.append("Consider heapq for the min-heap")

# Persist (or wait for next ingest to auto-save)
hmr.save_workspace("agent_backend")

# Complete a task (LIFO)
done = ws.pop_task()

# After restart — fully restored
hmr2 = HMR(storage_path="./my_project")
ws2 = hmr2.get_workspace("agent_backend", create=False)
print(ws2.active_goal)         # "Implement task queue"
print(len(ws2.task_stack))     # 1 (one task completed)
```

---

### 4.6 Memory Compression

```python
# Compress by type
compressed = hmr.compress_memories(
    memory_type="execution",
    max_memories=20
)

# Compress specific IDs
compressed = hmr.compress_memories(
    memory_ids=["mem_001", "mem_002", "mem_003"]
)

if compressed:
    print(compressed.title)    # "[Compressed] backup-record + incident"
    print(compressed.tags)     # [..., "compressed"]
```

Strategy: OpenAI LLM summarisation if API key present, else TF-IDF keyword extraction.

---

## 5. v2.0 New: ThoughtChain Engine

### Core Idea

```
Before v2.0: records *what happened* (execution memories)
v2.0:        records *why it thought that* (full reasoning chain)

Value:
  1. Traceability  — trace back the exact reasoning path
  2. Learning      — identify which judgements were wrong
  3. Handover      — hand off a task with full cognitive context
  4. Reuse         — successful chains guide future decisions
```

### API Reference

#### start_thinking — Create a chain

```python
chain = hmr.start_thinking(
    goal="Diagnose Scheduler IPC timeout root cause",
    expected_outcome="Identify root cause and resolve",  # optional
    agent_id="agent_backend"                              # optional
)
print(chain.chain_id)   # tc_a1b2c3d4
print(chain.status)     # ChainStatus.OPEN
```

#### think — Append a thought node

```python
from hmr.engines.thought_chain import ThoughtType

hmr.think(chain.chain_id,
          "Queue depth sustained >800; consume rate < produce rate",
          ThoughtType.OBSERVATION, confidence=0.95)

hmr.think(chain.chain_id,
          "Hypothesis: consumer thread count is insufficient",
          ThoughtType.HYPOTHESIS, confidence=0.7)

hmr.think(chain.chain_id,
          "Hypothesis: consumers preempted by CPU-intensive tasks",
          ThoughtType.HYPOTHESIS, confidence=0.8)

# Attach supporting memory IDs (trace the evidence)
recall_result = hmr.recall(query="IPC backpressure mechanism")
supporting = [m.id for m in recall_result.memory_objects[:2]]

hmr.think(chain.chain_id,
          "Decision: scale consumers to x3 + raise thread priority",
          ThoughtType.DECISION, confidence=0.85, memory_ids=supporting)

hmr.think(chain.chain_id,
          "Deployed: consumers x3 + priority raised",
          ThoughtType.ACTION, confidence=1.0)
```

#### reflect_on — Trigger reflection

```python
result = hmr.reflect_on(
    chain_id=chain.chain_id,
    actual_outcome="Queue depth dropped 800 → 50; timeouts eliminated",
    rating=0.92     # 0–1; omit for auto-inference
)

print(result.accuracy)           # 0.75 (correct nodes / total nodes)
print(result.correct_nodes)      # IDs of correctly judged thoughts
print(result.wrong_nodes)        # IDs of incorrectly judged thoughts
print(result.key_mistakes)       # Descriptions of key errors
print(result.insights)           # Distilled insights
print(result.suggested_memory)   # Content auto-stored as a reflection memory
```

After reflection:
- Each thought node gets a `was_correct` flag (True / False / None)
- High-value insights auto-stored as `reflection` type memory
- Chain status becomes `CLOSED`

#### best_decision_for — Query historical best decision

```python
best = hmr.best_decision_for("IPC queue backup problem")
# → "[Historical ref, accuracy=90%] Scale consumer threads x3 + raise priority"
# → Returns None if no relevant historical chains exist
```

#### Inspect chains

```python
# Get a single chain
chain_obj = hmr.thought_chain.get_chain(chain.chain_id)
print(chain_obj.to_summary())   # human-readable summary

# Find similar historical chains
similar = hmr.thought_chain.find_similar_chains("IPC timeout", top_k=3)

# Statistics
stats = hmr.thought_chain.get_stats()
print(stats["total_chains"])              # total number of chains
print(stats["avg_reflection_accuracy"])  # average reflection accuracy
print(stats["active_chains"])            # chains still open/active
```

### Complete ThoughtChain Example

```python
from hmr.engines.thought_chain import ThoughtType

# Multi-day incident investigation
chain = hmr.start_thinking(
    goal="Scheduler high-load response timeout — root cause analysis",
    expected_outcome="p99 latency < 100ms"
)

# Day 1: gather observations
hmr.think(chain.chain_id, "p99 latency 1200ms, far above SLA of 100ms",
          ThoughtType.OBSERVATION)
hmr.think(chain.chain_id, "IPC queue depth sustained >1000",
          ThoughtType.OBSERVATION)
hmr.think(chain.chain_id, "CPU usage only 40% — not CPU-bound",
          ThoughtType.OBSERVATION)

# Hypotheses
hmr.think(chain.chain_id, "Hypothesis: consumer thread count too low",
          ThoughtType.HYPOTHESIS, 0.7)
hmr.think(chain.chain_id, "Hypothesis: IO blocking stalls consumers",
          ThoughtType.HYPOTHESIS, 0.6)

# Day 2: validate and decide
hmr.think(chain.chain_id, "Confirmed: consumer threads waiting on sync IO",
          ThoughtType.OBSERVATION)
hmr.think(chain.chain_id, "Decision: switch to async IO + scale consumers",
          ThoughtType.DECISION, 0.9)
hmr.think(chain.chain_id, "Deployed: async IO refactor + consumer scaling",
          ThoughtType.ACTION)

# Post-execution reflection
ref = hmr.reflect_on(
    chain.chain_id,
    "p99 dropped to 45ms — better than SLA target",
    rating=0.95
)
print(ref.insights)
print(hmr.thought_chain.get_chain(chain.chain_id).to_summary())
```

---

## 6. v2.0 New: Memory Policy Engine

### Core Idea

```
v1.x: store/recall/forget strategies are all hard-coded
v2.0: learns from feedback — policy weights updated dynamically

Three sub-policies:
  IngestPolicy  → what to store, which type, what confidence?
  RecallPolicy  → which strategy, how many results (top_k)?
  ForgetPolicy  → how fast to decay, when to delete?
```

### feedback — Policy Feedback (Core)

```python
# Recall result was useful
hmr.feedback(
    event_type="recall_hit",
    memory_ids=[m.id for m in result.memory_objects[:2]],
    signal=0.85,             # positive = good
    query="IPC timeout cause",
    strategy="jit"
)

# Recall result was useless
hmr.feedback(
    event_type="recall_miss",
    memory_ids=[m.id for m in unused_results],
    signal=-0.5
)

# Task succeeded
hmr.feedback(
    event_type="task_success",
    memory_ids=related_memory_ids,
    signal=0.9,
    context={"memory_type": "execution"}
)

# Task failed
hmr.feedback(
    event_type="task_failure",
    memory_ids=related_memory_ids,
    signal=-0.7
)

# Compression improved recall quality
hmr.feedback(
    event_type="compress_gain",
    memory_ids=[compressed_memory.id],
    signal=0.6
)
```

**event_type reference:**

| Event | Signal range | Description |
|-------|------------|-------------|
| `recall_hit` | 0.5 – 1.0 | Recalled memories were actually used |
| `recall_miss` | -1.0 – -0.1 | Recalled memories were entirely unused |
| `task_success` | 0.5 – 1.0 | Full task succeeded |
| `task_failure` | -1.0 – -0.1 | Task failed |
| `compress_gain` | 0.3 – 0.8 | Compression improved recall quality |

### Policy-assisted ingest / recall

```python
# Auto-classify on ingest
mem = hmr.ingest(content, use_policy=True)
# Works for both English and Chinese via character-level matching

# Policy assists recall scheduling
result = hmr.recall(query, use_policy=True)   # default: True
# Adjusts strategy and top_k based on historical hit rate
```

### Inspect Policy state

```python
stats = hmr.policy.get_stats()
print(stats["total_feedback"])      # total feedback events
print(stats["positive_feedback"])   # positive signals
print(stats["positive_ratio"])      # higher = policy is working well
print(stats["recall_hit_rate"])     # recall hit rate
print(stats["policy_updates"])      # number of weight updates

# Current weight biases (for debugging)
weights = hmr.policy.get_policy_weights_summary()
print(weights["ingest_type_bias"])       # per-type classification lean
print(weights["recall_strategy_bias"])  # per-strategy usage lean
```

### Policy Best Practices

```python
# 1. Provide feedback after every recall
result = hmr.recall(query="...")
used = result.memory_objects[:1]
hmr.feedback("recall_hit", [m.id for m in used], signal=0.8,
             query="...", strategy="jit")

# 2. Summarise feedback at task end
if task_succeeded:
    hmr.feedback("task_success", all_related_ids, signal=0.9)
else:
    hmr.feedback("task_failure", all_related_ids, signal=-0.6)

# 3. Use use_policy=True to let the system learn optimal ingestion
for log_entry in daily_logs:
    hmr.ingest(log_entry, use_policy=True)
    # Policy gradually learns the project's memory style
```

---

## 7. v2.0 New: Self-Evolution Engine

### Core Idea

```
Problem: memory base bloats over time with duplicates, redundancies, contradictions
Solution: Evolution Engine actively optimises memory structure

Three core operations:
  abstract: similar memories → abstract concept (knowledge distillation)
  resolve:  contradictory pair → keep high-confidence, lower the other
  suggest:  analyse usage → recommend optimal LifecycleConfig parameters
```

### evolve — Run Evolution

```python
# Preview first (dry_run=True — analyse only, no changes)
preview = hmr.evolve(dry_run=True)
print(preview["summary"])
for action in preview["actions"]:
    print(f"  {action}")
# Output:
# Evolution done: abstracted 2 clusters, resolved 1 contradiction
#   [Preview] Can abstract 5 [execution] memories
#   [Preview] Contradiction: 《IPC should be sync》vs《IPC should be async》

# Execute for real
report = hmr.evolve(dry_run=False)
print(report["summary"])
print(report["abstractions"])             # clusters abstracted
print(report["contradictions_resolved"])  # contradictions resolved
print(report["suggestions"])              # config recommendations
```

### Reading the Evolution Report

```python
report = hmr.evolve()

# summary: one-line overview
print(report["summary"])
# → "Evolution done: abstracted 2 clusters, resolved 1 contradiction, health: ✅ Healthy"

# actions: per-operation detail
for action in report["actions"]:
    print(action)
# → ✅ Abstracted 6 [execution] memories → 《[Abstract] backup-record + timeout》
# → 🔧 Resolved contradiction: 《IPC sync》vs《IPC async》(semantic opposites)
# → 💡 Suggestion: type count 120 > threshold; recommend lowering to 80

# suggestions: config recommendations
sugg = report["suggestions"]
print(sugg["suggested_config"])   # recommended LifecycleConfig params
print(sugg["reasons"])            # why
print(sugg["current_health"])     # system health summary
```

### When to Run Evolution

```python
# Option A: run manually after accumulating memories (recommended)
if hmr.memory_fs.get_statistics()["total_memories"] % 100 == 0:
    hmr.evolve()

# Option B: daily schedule
import schedule
schedule.every().day.at("02:00").do(lambda: hmr.evolve())

# Option C: after major task completion
hmr.evolve()
```

### Evolution Statistics

```python
evo_stats = hmr.evolution.get_stats()
print(evo_stats["total_operations"])   # total operations performed
print(evo_stats["by_operation"])       # breakdown: {"abstract": 5, "resolve": 2}
print(evo_stats["recent_operations"])  # last 5 operations
```

---

## 8. v1.5 Advanced Components Recap

### Memory Scheduler

```python
# Inspect a scheduling decision without executing recall
plan = hmr.scheduler.schedule(
    query="Why does IPC latency slow down the Scheduler?",
    context={"active_goal": "Optimise Scheduler"}
)
print(plan.strategy.value)   # "jit"
print(plan.use_jit)           # True
print(plan.top_k)             # 8
print(plan.reasoning)         # "Complex query — using JIT multi-step retrieval"

stats = hmr.scheduler.get_stats()
print(stats["strategy_counts"])    # call counts per strategy
print(stats["cache_hit_rate"])     # hot-cache hit rate
print(stats["dominant_strategy"]) # most-used strategy
```

### JIT Memory Compiler

```python
# Direct use (auto-triggered by recall for complex queries)
result = hmr.jit_compiler.compile(
    query="Why did IPC latency cause a Scheduler timeout cascade?",
    context={"active_goal": "Investigate incident"},
    top_k=5,
    max_steps=3
)

for step in result.steps:
    print(f"Step {step.step+1}: {step.query}")
    print(f"  Found {len(step.memories)}, confidence {step.confidence}")
    print(f"  Gaps: {step.gaps}")

print("Query trace:", result.query_trace)
```

### Memory Lifecycle Engine

```python
from hmr.engines.lifecycle import LifecycleConfig

config = LifecycleConfig(
    max_memories_per_type   = 80,
    prune_retrievability    = 0.05,
    prune_min_age_days      = 7,
    prune_require_zero_access = True,
    auto_enabled            = True,
    check_interval_ingests  = 10,
)
hmr = HMR(storage_path="./data", lifecycle_config=config)

# Manual trigger
report = hmr.lifecycle.check_now(memory_type="execution")
print(report.summary())   # "Checked 50; deleted 3; compressed 20 → 1"

lc_stats = hmr.lifecycle.get_lifecycle_stats()
print(lc_stats["by_state"])
# {"fresh": 5, "active": 30, "fading": 10, "dormant": 3}
```

### Memory Graph Layer

```python
# Graph auto-builds on every ingest
nodes = hmr.memory_graph.find_related("Scheduler", depth=2)
for n in nodes:
    print(f"[{n.node_type.value}] {n.label} ({len(n.memory_ids)} memories)")

# Causal chain
chain = hmr.memory_graph.get_causal_chain("deadlock")
for node, edge in chain:
    print(f"→({edge.edge_type.value})→ {node.label}")

clusters = hmr.memory_graph.auto_cluster()
print(hmr.memory_graph.get_stats())
```

---

## 9. Complete Workflow Examples

### Example 1: Multi-Day Incident Investigation

```python
from hmr.core.hmr import HMR
from hmr.engines.thought_chain import ThoughtType

# ═══ Day 1: Problem Discovery ═══════════════════════════════════
hmr = HMR(storage_path="./incident_project")

hmr.ingest(
    "Production Scheduler p99 latency spiked from 50ms to 1200ms — sustained 2 hours",
    memory_type="execution", title="Production Latency Alert",
    metadata={"tags": ["production", "alert", "p99"]}
)

chain = hmr.start_thinking(
    goal="Root cause: Scheduler p99 spike 50ms → 1200ms",
    expected_outcome="Root cause identified; p99 restored to <100ms"
)
hmr.think(chain.chain_id, "p99 1200ms; CPU usage only 40%", ThoughtType.OBSERVATION, 0.95)
hmr.think(chain.chain_id, "IPC queue depth sustained >1000",  ThoughtType.OBSERVATION, 0.95)
hmr.think(chain.chain_id, "Not CPU-bound — suspect IO blocking", ThoughtType.HYPOTHESIS, 0.7)

hmr.save_runtime_state(
    goal="Root cause: Scheduler p99 spike",
    plan=["Gather metrics ✓", "Hypothesise ✓", "Validate", "Fix", "Verify"],
    context={"active_chain": chain.chain_id, "confidence": 0.5}
)

# ═══ Day 2: Validate and Fix ═════════════════════════════════════
hmr2 = HMR(storage_path="./incident_project")
state = hmr2.restore_runtime_state()
active_chain_id = state.current_context.get("active_chain")

# Smart recall for relevant knowledge
result = hmr2.recall(
    query="IO blocking causing consumer thread stalls",
    context={"active_goal": state.active_goal}
)
hmr2.feedback("recall_hit", [result.memory_objects[0].id], 0.8,
              query="IO blocking consumers")

# Continue the reasoning chain
if active_chain_id:
    hmr2.think(active_chain_id, "Profiling confirmed: consumers waiting on sync IO",
               ThoughtType.OBSERVATION, 0.98)
    hmr2.think(active_chain_id, "Decision: async IO + scale consumers to x3",
               ThoughtType.DECISION, 0.9)
    hmr2.think(active_chain_id, "Deployed: async IO refactor + consumer scaling",
               ThoughtType.ACTION, 1.0)
    hmr2.think(active_chain_id, "p99 dropped to 45ms — below SLA target",
               ThoughtType.OUTCOME, 1.0)

    ref = hmr2.reflect_on(
        active_chain_id,
        "p99 restored: 1200ms → 45ms",
        rating=0.95
    )
    print(f"Reflection accuracy: {ref.accuracy:.0%}")
    print(f"Insights: {ref.insights}")

hmr2.ingest(
    "Root cause: sync IO blocking consumer threads causing IPC queue backup. "
    "Fix: async IO + consumer x3 scaling. Result: p99 1200ms → 45ms.",
    memory_type="reflection",
    title="IPC Latency Root Cause & Fix Summary",
    metadata={"tags": ["ipc", "latency", "best-practice"], "confidence": 0.95}
)

report = hmr2.evolve()
print(report["summary"])

best = hmr2.best_decision_for("IPC queue backup latency")
print(f"Best historical decision: {best[:60] if best else 'None'}")
```

### Example 2: Multi-Agent Collaboration

```python
hmr = HMR(storage_path="./team_project")

# ── Backend agent ──────────────────────────────────────────────
backend = hmr.get_workspace("agent_backend")
backend.active_goal = "Implement Scheduler core logic"
backend.push_task({"name": "Implement priority heap", "status": "in_progress"})

be_chain = hmr.start_thinking("Design task priority algorithm",
                               agent_id="agent_backend")
hmr.think(be_chain.chain_id, "Need priority 1-10; high priority executes first",
          ThoughtType.OBSERVATION)
hmr.think(be_chain.chain_id, "Min-heap efficiently implements priority queue",
          ThoughtType.DECISION, 0.9)

# Publish the API spec so the frontend agent can find it
hmr.ingest(
    "Scheduler API: submit(task, priority=1-10), cancel(task_id), status(task_id)",
    memory_type="decision", title="Scheduler API Design",
    metadata={"tags": ["api", "scheduler"]}
)
hmr.save_workspace("agent_backend")

# ── Frontend agent ─────────────────────────────────────────────
frontend = hmr.get_workspace("agent_frontend")
frontend.active_goal = "Build Scheduler management UI"

api_result = hmr.recall(query="Scheduler API interface spec", strategy="semantic")
if api_result.memory_objects:
    api_doc = api_result.memory_objects[0]
    hmr.feedback("recall_hit", [api_doc.id], 0.9)
    print(f"Frontend retrieved API: {api_doc.content[:80]}")

hmr.save_workspace("agent_frontend")

# After restart — both workspaces fully restored
hmr2 = HMR(storage_path="./team_project")
ws_be = hmr2.get_workspace("agent_backend",  create=False)
ws_fe = hmr2.get_workspace("agent_frontend", create=False)
print(f"Backend:  {ws_be.active_goal}")
print(f"Frontend: {ws_fe.active_goal}")
```

### Example 3: Continuous Learning System

```python
hmr = HMR(storage_path="./learning_system")

# Simulate 30 days of execution records
for day in range(30):
    for run in range(3):
        hmr.ingest(
            f"Day{day+1} Run{run+1}: Scheduler p99={50+day%20}ms, "
            f"IPC queue peak {run*100}, concurrency {200+day*10} RPS",
            use_policy=True,
            title=f"Daily Run Record Day{day+1}-{run+1}"
        )

    if (day + 1) % 10 == 0:
        memories = hmr.memory_fs.list_memories(memory_type="execution")
        hmr.feedback(
            "task_success",
            memory_ids=[m.id for m in memories[-5:]],
            signal=0.85
        )
        status = hmr.get_system_status()
        print(f"Day {day+1}: {status['memory_fs']['total_memories']} memories total")

# After 30 days: review what Policy learned
print(hmr.policy.get_stats())
print(hmr.policy.get_policy_weights_summary())

# Self-evolve: compress redundancy, distil patterns
report = hmr.evolve()
print(report["summary"])
# → "Evolution done: abstracted 3 clusters, resolved 0 contradictions, health: ✅ Healthy"

# Distilled patterns are directly retrievable
result = hmr.recall(query="Scheduler performance patterns", top_k=3)
for mem in result.memory_objects:
    print(f"[{mem.type}] {mem.title}")
```

---

## 10. Configuration Reference

### LifecycleConfig — Full Options

```python
from hmr.engines.lifecycle import LifecycleConfig

LifecycleConfig(
    # Auto-compression trigger
    max_memories_per_type    = 80,    # compress when per-type count exceeds this
    consolidation_batch      = 20,    # max memories per compression run
    consolidation_keep_ratio = 0.3,   # original memories' weight reduced to 30%

    # Auto-deletion conditions (ALL must be satisfied simultaneously)
    prune_retrievability     = 0.05,  # SM-2 retrievability threshold (5%)
    prune_min_age_days       = 7,     # minimum age in days
    prune_require_zero_access= True,  # only delete never-accessed memories

    # Scheduling
    auto_enabled             = True,  # enable automatic lifecycle management
    check_interval_ingests   = 10,    # check every N ingests
)
```

### Environment Variables

```bash
OPENAI_API_KEY=sk-...    # Used for embeddings and LLM summarisation
```

### Data Directory Layout

```
hmr_data/
├── memories/            per-type memory files
│   ├── concepts/
│   ├── executions/
│   ├── decisions/
│   └── ...
├── runtimes/            RuntimeState JSON files
├── workspaces/          AgentWorkspace JSON files
├── vector_store/        persisted vector index
│   ├── vectors.json
│   └── vector_metadata.json
├── memory_graph/        entity graph data
│   └── memory_graph.json
├── thought_chains/      thought chain files (v2.0)
│   └── tc_*.json
├── policy/              policy weights (v2.0)
│   └── policy.json
├── evolution/           evolution logs (v2.0)
│   └── evolution_logs.json
└── index/               index files
```

---

## 11. System Status Monitoring

```python
status = hmr.get_system_status()

# Core
print(status["version"])                     # "2.0.0"
print(status["memory_fs"]["total_memories"])
print(status["vector_store"]["total_vectors"])
print(status["synced"])                      # True = in sync

# v1.5 components
print(status["memory_graph"]["total_nodes"])
print(status["memory_graph"]["total_edges"])
print(status["scheduler"]["dominant_strategy"])
print(status["scheduler"]["cache_hit_rate"])
print(status["lifecycle"]["by_state"])
# {"fresh": 5, "active": 30, "fading": 10, "dormant": 3}

# v2.0 components
print(status["thought_chain"]["total_chains"])
print(status["thought_chain"]["avg_reflection_accuracy"])
print(status["thought_chain"]["active_chains"])

print(status["policy"]["total_feedback"])
print(status["policy"]["positive_ratio"])
print(status["policy"]["recall_hit_rate"])

print(status["evolution"]["total_operations"])
print(status["evolution"]["by_operation"])   # {"abstract": N, "resolve": M}

# General
print(status["overdue_reviews"])      # memories due for SM-2 review
print(status["active_workspaces"])   # number of active agents
print(status["embedding_provider"]) # openai/sentence_transformers/tfidf
```

---

## 12. Troubleshooting

### "Rebuilding vector index" on startup

```
[HMR] Rebuilding vector index (N memories)...
```

**Normal behaviour** — happens on first start or if `vector_store/` was deleted.
Completes automatically; won't appear again until the directory is removed.

---

### Policy classification is wrong

```python
# 1. Inspect the classification decision
d = hmr.policy.decide_ingest(content, title=title)
print(d)   # {"should_store": True, "memory_type": "...", "reasoning": "..."}

# 2. Correct via feedback — Policy will learn
m = hmr.ingest(content, memory_type="execution")  # manually specify correct type
hmr.feedback("task_success", [m.id], signal=0.9,
             context={"memory_type": "execution", "content": content})

# 3. Ensure content contains recognisable feature words:
# execution: fail/error/crash/timeout/backup/fault/blocked
# decision:  decided/chose/selected/determined/adopted
# reflection:because/cause/reason/root-cause/analysis
# concept:   recommend/pattern/principle/approach/design
```

---

### Recall results are not relevant

```python
# Check sync state
status = hmr.get_system_status()
print(status["synced"])              # should be True
print(status["embedding_provider"]) # check which embedding is active

# Rebuild vector index
hmr.vector_store.rebuild_from_memories(hmr.memory_fs.list_memories())

# Force JIT for complex queries
result = hmr.recall(query="...", strategy="jit")
```

---

### evolve() reports no operations

```python
# Reason: triggers not met (cluster size <3, or no contradictions found)
stats = hmr.memory_fs.get_statistics()
print(stats["memory_types"])   # check per-type counts

# Run evolution directly on the engine for detailed output
report = hmr.evolution.evolve(
    memories=hmr.memory_fs.list_memories(),
    vector_store=hmr.vector_store,
    memory_fs=hmr.memory_fs,
)
```

---

### Reflection insights not auto-stored

```python
# Verify ingest_fn is registered
print(hmr.thought_chain._ingest_fn is not None)  # should be True

# Manual fallback
ref = hmr.reflect_on(chain_id, actual_outcome)
if ref.suggested_memory:
    hmr.ingest(ref.suggested_memory, memory_type="reflection",
               title=f"[Chain insight] {goal[:30]}")
```

---

*HMR v2.0 — Making AI remember not just answers, but how to think.*
