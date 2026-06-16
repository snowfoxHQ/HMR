# HMR v1.5 User Manual

**Hestia Memory Runtime — A Persistent Cognitive Runtime for Long-Running AI Systems**

Version: v1.5.0 | Language: English

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Core Concepts](#core-concepts)
4. [Core API](#core-api)
   - [Initialization](#initialization)
   - [Ingesting Memory](#ingesting-memory)
   - [Recalling Memory](#recalling-memory)
   - [Runtime State](#runtime-state)
   - [Agent Workspaces](#agent-workspaces)
   - [Memory Compression](#memory-compression)
   - [System Status](#system-status)
5. [Advanced Components](#advanced-components)
   - [Memory Scheduler](#memory-scheduler)
   - [JIT Memory Compiler](#jit-memory-compiler)
   - [Memory Lifecycle Engine](#memory-lifecycle-engine)
   - [Memory Graph Layer](#memory-graph-layer)
6. [Complete Workflow Examples](#complete-workflow-examples)
7. [Configuration Reference](#configuration-reference)
8. [Troubleshooting](#troubleshooting)
9. [Changelog](#changelog)

---

## Quick Start

```python
from hmr.core.hmr import HMR

# 1. Initialize
hmr = HMR(storage_path="./my_project")

# 2. Store a memory
hmr.ingest(
    "IPC should use async message queues to avoid blocking",
    memory_type="concept",
    title="IPC Design Principle"
)

# 3. Save your current working state
hmr.save_runtime_state(
    goal="Design the Scheduler",
    plan=["Research IPC", "Design API", "Implement"]
)

# 4. Days later — restart and restore
state = hmr.restore_runtime_state()
print(state.active_goal)   # "Design the Scheduler"

# 5. Smart recall of relevant memories
result = hmr.recall(query="Scheduler IPC design")
for mem in result.memory_objects:
    print(f"[{mem.type}] {mem.title}")
```

---

## Installation

> **Important note for Windows users**
> Do NOT place the project under `Documents`, `Desktop`, or `Pictures` —
> these are synced by OneDrive, which locks files during installation and
> causes `pip install -e .` to fail with
> `could not create 'hmr.egg-info': The system cannot find the file specified`.
> Use a non-synced path such as `C:\hmr` or `C:\projects\hmr`.

### Step 1: Install dependencies (always works)

```bash
pip install pydantic numpy
```

> These two packages are all you need — HMR runs fully with the built-in
> TF-IDF Embedding.

### Step 2: Install HMR

From the extracted directory containing `pyproject.toml`:

```bash
# Windows (PowerShell)
cd C:\hmr
pip install -e .

# Linux / macOS
cd /path/to/hmr
pip install -e .
```

Or use it **without installing** — add two lines at the top of your script:

```python
import sys
sys.path.insert(0, r"C:\hmr")   # change to your actual path
from hmr.core.hmr import HMR
```

### (Optional) Better semantic search

HMR works without either of these (it falls back to built-in TF-IDF).
Installing one improves quality:

```bash
# Option A: Local model (recommended — free, no API key, offline)
pip install sentence-transformers

# Option B: OpenAI Embeddings (best quality, requires API key)
pip install openai
```

#### Choosing a local model (Chinese / multilingual support)

Option A's local model defaults to `all-MiniLM-L6-v2` (~80MB, lightweight, good
for English but **weak on Chinese**). You can switch to a model better suited to
your language via the `HMR_ST_MODEL` environment variable — **no code change needed**.

| Model | Size | Best for |
|-------|------|----------|
| `all-MiniLM-L6-v2` (default) | ~80MB | English, lightweight |
| `BAAI/bge-small-zh-v1.5` | ~100MB | Chinese, lightweight |
| `BAAI/bge-base-zh-v1.5` | ~400MB | Chinese, higher quality |
| `BAAI/bge-m3` | ~2.2GB | **Strong in both Chinese & English**, best for mixed text |
| `paraphrase-multilingual-MiniLM-L12-v2` | ~120MB | 50+ languages, lightweight |

How to set (bge-m3 example):

```bash
# Windows (PowerShell) — temporary
$env:HMR_ST_MODEL="BAAI/bge-m3"

# Windows (PowerShell) — persistent
[System.Environment]::SetEnvironmentVariable("HMR_ST_MODEL", "BAAI/bge-m3", "User")

# Linux / macOS
export HMR_ST_MODEL="BAAI/bge-m3"
```

After setting, HMR logs the actual model loaded:
`[HMR Embedding] 使用 sentence-transformers (BAAI/bge-m3)`

> **Important:** After changing models, the old vector index is incompatible with
> the new model and must be rebuilt once. If using the HTTP service, call
> `POST /reindex` to rebuild automatically; if using the library directly, call
> `hmr.vector_store.rebuild_from_memories(hmr.memory_fs.list_memories())`.
> Skipping the rebuild will make semantic search inaccurate.

#### Option C: Ollama local models (recommended, great for Chinese)

If you already run models locally via [Ollama](https://ollama.com), HMR can call
it directly — **no model download by HMR needed**. Ideal for managing strong
Chinese models like bge-m3 through Ollama.

```bash
# 1. Pull the model with Ollama (once)
ollama pull bge-m3

# 2. Tell HMR to use Ollama
# Windows (PowerShell)
$env:HMR_OLLAMA_MODEL="bge-m3"

# Linux / macOS
export HMR_OLLAMA_MODEL="bge-m3"
```

Optional — if Ollama isn't at the default address, set `HMR_OLLAMA_HOST`:
```bash
$env:HMR_OLLAMA_HOST="http://localhost:11434"   # default, usually unnecessary
```

After setting, HMR logs:
`[HMR Embedding] 使用 Ollama (bge-m3, dim=1024)`

> Switching to Ollama also invalidates the old index — call `POST /reindex` once.

---

#### Embedding provider overview (HMR auto-selects by priority)

| Priority | Provider | Enabled when | Best for |
|----------|----------|--------------|----------|
| 1 | **OpenAI** (online) | `OPENAI_API_KEY` set | Best quality, needs internet + key |
| 2 | **Ollama** (local) | `HMR_OLLAMA_MODEL` set | Local, strong Chinese (bge-m3), offline |
| 3 | **sentence-transformers** (local) | package installed | Local, configurable via `HMR_ST_MODEL` |
| 4 | **TF-IDF** (fallback) | always available | No deps, dev/testing |

Mix freely: set OpenAI for online; use Ollama's bge-m3 for local Chinese;
set nothing to fall back to TF-IDF.

#### Filter recall by language (mixed-language scenarios)

Bilingual models (like bge-m3) map semantically similar Chinese and English
content to nearby vectors, so searching in Chinese may surface English results.
HMR can filter recall by language via the `HMR_LANG_FILTER` environment variable:

| Value | Behavior | Best for |
|-------|----------|----------|
| `off` (default) | No filtering, returns both | Mixed text, cross-language search |
| `auto` | Detects **query** language, returns same-language only | Chinese query → Chinese only |
| `zh` | Force Chinese results only | Fixed Chinese scenarios |
| `en` | Force English results only | Fixed English scenarios |

```bash
# Windows (PowerShell)
$env:HMR_LANG_FILTER="auto"

# Linux / macOS
export HMR_LANG_FILTER="auto"
```

> Default is `off`, preserving existing behavior. Language is auto-detected by
> Chinese-character ratio — no manual tagging needed. If filtering yields no
> results, it falls back to unfiltered (so you never get zero hits).
>
> **Recommendation:** Agent-conversation memories are naturally mixed-language
> (Chinese prose + English technical terms/code), where strict language filtering
> can backfire — **keep the default `off`**. This feature is better suited to
> **structured knowledge bases** with clear per-item language, where enabling
> `auto` or `zh`/`en` actually pays off.

If using Option B, set the `OPENAI_API_KEY` environment variable.
**Commands are listed per platform below — find your own system and use the
matching command. The commands are completely different across systems; using
the wrong one will fail.**

#### Windows — PowerShell

```powershell
# Temporary (current PowerShell window only; lost when closed)
$env:OPENAI_API_KEY="sk-..."

# Persistent (writes to user environment; reopen PowerShell to take effect)
[System.Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-...", "User")

# Verify it is set
echo $env:OPENAI_API_KEY
```

#### Windows — CMD (Command Prompt)

```cmd
:: Temporary (current CMD window only)
set OPENAI_API_KEY=sk-...

:: Persistent (writes to user environment; reopen CMD to take effect)
setx OPENAI_API_KEY "sk-..."

:: Verify it is set
echo %OPENAI_API_KEY%
```

#### Linux / macOS — Terminal

```bash
# Temporary (current terminal session only; lost when closed)
export OPENAI_API_KEY="sk-..."

# Persistent (writes to shell config; applies to all new terminals)
# bash users:
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.bashrc && source ~/.bashrc
# zsh users (macOS default):
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.zshrc && source ~/.zshrc

# Verify it is set
echo $OPENAI_API_KEY
```

> **Note:** Once set, HMR reads it automatically at startup — no need to put the
> key in your code. HMR auto-selects in the order
> OpenAI → sentence-transformers → TF-IDF, using whichever is installed and set.
>
> If you prefer not to set an environment variable, pass it in code instead:
> `HMR(storage_path="./data", llm_api_key="sk-...")`

### Step 3: Verify installation

Save the following as `verify.py` (**do NOT paste it into the terminal /
PowerShell — this is Python code and must be run with `python`**):

```python
from hmr.core.hmr import HMR

hmr = HMR(storage_path="./test_data")
print("Version:", hmr.VERSION)   # should print 1.5.0

status = hmr.get_system_status()
print("Embedding:", status["embedding_provider"])  # openai / sentence_transformers / tfidf
print("Synced:", status["synced"])                  # True
```

Then run:

```bash
python verify.py
```

Seeing `Version: 1.5.0` and `Synced: True` means installation succeeded.

---

## Core Concepts

### Design Philosophy

```
Traditional AI memory:  Memory = Storage   (you ask, it searches)
HMR:                   Memory = Persistent Cognitive Runtime
                        (the system predicts what you need and pre-loads it)
```

### Five Key Components

| Component | Responsibility | Analogy |
|-----------|---------------|---------|
| **MemoryObject** | Basic unit of memory — typed, summarised, time-weighted | A single memory in the brain |
| **RuntimeState** | Current cognitive state: goal, plan, context | Your mental state while working |
| **Memory Scheduler** | Decides which recall strategy to use | OS process scheduler |
| **JIT Compiler** | Multi-step reasoning retrieval, gap analysis, query rewriting | Compiler multi-pass optimisation |
| **Memory Graph** | Entity / causal / temporal structured network | Knowledge graph |

### Memory Types

| Type | Purpose | Example |
|------|---------|---------|
| `concept` | Abstract knowledge, design principles | "Async is better than sync" |
| `project` | Project context | "HMR v2 project goals" |
| `decision` | Decision + rationale | "Chose Chroma over Pinecone" |
| `execution` | Execution traces, failure records | "Deadlock occurred during load test" |
| `task` | Task definitions | "Implement priority queue" |
| `reflection` | Post-mortems and learnings | "Root cause of deadlock" |
| `agent_memory` | Agent-private memories | "agent_frontend UI decisions" |
| `workflow` | Process definitions | "Release process SOP" |

---

## Core API

### Initialization

```python
from hmr.core.hmr import HMR
from hmr.engines.lifecycle import LifecycleConfig

hmr = HMR(
    storage_path="./hmr_data",               # Data directory (default: ./hmr_data)
    embedding_model="text-embedding-3-small", # OpenAI embedding model
    llm_api_key="sk-...",                    # Optional; or set OPENAI_API_KEY env var
    lifecycle_config=LifecycleConfig(         # Optional custom lifecycle config
        max_memories_per_type=100,
        check_interval_ingests=10,
    )
)
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `storage_path` | `"./hmr_data"` | Root directory for all persistent data |
| `embedding_model` | `"text-embedding-3-small"` | OpenAI embedding model name |
| `llm_api_key` | `None` | OpenAI API key (optional) |
| `lifecycle_config` | Default config | Lifecycle engine settings |

---

### Ingesting Memory

Store new knowledge, events, or decisions into HMR.

```python
memory = hmr.ingest(
    content="Under high concurrency the IPC queue backed up; "
            "tasks waited >500 ms, causing downstream timeouts.",
    memory_type="execution",
    title="Load Test Failure #1",
    metadata={
        "tags": ["ipc", "load-test", "timeout"],
        "runtime_dependencies": ["IPC Design Principle", "Scheduler"],
        "confidence": 0.9
    }
)

print(memory.id)                # mem_a1b2c3d4
print(memory.semantic_summary)  # auto-generated summary
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | str | ✅ | Memory content (long text supported) |
| `memory_type` | str | No | Memory type, default `"concept"` |
| `title` | str | No | Title; auto-generated if omitted |
| `metadata` | dict | No | Contains `tags`, `runtime_dependencies`, `confidence` |

**What `ingest` triggers automatically:**
- Vector embedding generation
- SM-2 temporal state initialisation
- Memory Graph entity extraction
- Lifecycle check (every N ingests)
- Cognitive graph (CWG) update

---

### Recalling Memory

Intelligently recall relevant memories. The Memory Scheduler automatically
selects the best strategy.

```python
result = hmr.recall(
    query="Why does IPC latency cause Scheduler timeouts?",
    context={"active_goal": "Optimise Scheduler"},  # optional but improves results
    top_k=5,
    strategy="jit"   # optional — force a specific strategy
)

print(result.recall_reasoning)
# "[JIT] JIT compiled 2 steps, query trace: ..."

for mem in result.memory_objects:
    score = result.relevance_scores[mem.id]
    print(f"  [{score:.2f}] {mem.title}")
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | None | Query string |
| `context` | dict | None | Current context (containing `active_goal`, etc.) |
| `top_k` | int | 5 | Number of memories to return |
| `strategy` | str | None | Force a strategy; see table below |

**Strategy options:**

| Value | Best for | Characteristics |
|-------|---------|-----------------|
| `"semantic"` | Simple similarity queries | Single vector search — fastest |
| `"temporal"` | Time-related queries ("recent …", "last time …") | Sorted by recency weight |
| `"jit"` | Complex reasoning ("why …", "what caused …") | Multi-step retrieval — most accurate |
| `"hybrid"` | When there is an active working goal | Semantic + graph path combined |
| `"graph"` | When entity relationships matter | Graph path supplements candidates |

> When `strategy` is not specified, the Scheduler selects automatically based
> on query characteristics.

**Return value — `RecallResult`:**

```python
result.memory_objects    # List[MemoryObject], sorted by relevance
result.recall_reasoning  # str — strategy used and reasoning
result.relevance_scores  # Dict[str, float] — score per memory
result.predicted_need    # List[str] — what the system predicted you need
```

---

### Runtime State

Save and restore the AI's complete cognitive state across sessions.

#### Saving State

```python
state = hmr.save_runtime_state(
    goal="Design async Scheduler",
    plan=[
        "Research IPC protocol ✓",
        "Design task-queue API",
        "Implement priority scheduling",
        "Load-test validation"
    ],
    context={
        "current_focus": "Task-queue API design",
        "blockers": ["Need to confirm IPC protocol spec"],
        "confidence": 0.7
    }
)

print(state.runtime_id)   # rt_a1b2c3d4
```

#### Restoring State

```python
# After restart
hmr2 = HMR(storage_path="./my_project")

# Restore the latest state
state = hmr2.restore_runtime_state()

# Or restore a specific state
state = hmr2.restore_runtime_state(runtime_id="rt_a1b2c3d4")

if state:
    print(state.active_goal)      # "Design async Scheduler"
    print(state.current_plan)     # ["Research IPC protocol ✓", ...]
    print(state.current_context)  # {"current_focus": "Task-queue API design", ...}
```

**What restoration does automatically:**
1. Restores SM-2 memory states (review history for each memory)
2. Pre-loads memories most relevant to the current goal
3. Prints the pre-loading strategy used

---

### Agent Workspaces

Each agent has its own workspace, persisted to disk across restarts.

```python
# Get or create workspace
ws = hmr.get_workspace("agent_backend")

# Set goal and tasks
ws.active_goal = "Implement task queue"
ws.push_task({"name": "Design queue interface", "status": "todo", "priority": 1})
ws.push_task({"name": "Implement priority heap",  "status": "todo", "priority": 2})

# Record temporary thoughts (not stored in long-term memory)
ws.temporary_thoughts.append("Consider using heapq for the min-heap")

# Persist the workspace (auto-saved on ingest; can also be manual)
hmr.save_workspace("agent_backend")

# Mark a task done
completed = ws.pop_task()
print(completed["name"])   # "Implement priority heap" (LIFO)

# Multi-agent scenario
ws_frontend = hmr.get_workspace("agent_frontend")
ws_frontend.active_goal = "Build management UI"

# After restart — workspaces are fully restored
hmr2 = HMR(storage_path="./my_project")
ws_back = hmr2.get_workspace("agent_backend", create=False)
print(ws_back.active_goal)         # "Implement task queue"
print(len(ws_back.task_stack))     # 1 (one task already completed)
```

---

### Memory Compression

Compress multiple related memories into a single abstract piece of knowledge.

```python
# Compress all memories of a given type
compressed = hmr.compress_memories(
    memory_type="execution",   # compress all execution records
    max_memories=20            # process at most 20 at a time
)

# Compress specific memories by ID
compressed = hmr.compress_memories(
    memory_ids=["mem_001", "mem_002", "mem_003"]
)

if compressed:
    print(compressed.title)    # "[Compressed] failure-record + load-test"
    print(compressed.content)  # distilled abstract knowledge
    print(compressed.tags)     # [..., "compressed"]
```

**Compression strategy:**
- OpenAI API available → LLM extracts core patterns and rules
- No API key → TF-IDF keyword summarisation

**Automatic compression:**  
Set `LifecycleConfig.max_memories_per_type`; when the count for a type exceeds
that threshold the Lifecycle Engine triggers compression in the background
automatically — no manual call needed.

---

### System Status

```python
status = hmr.get_system_status()

print(f"Version:           {status['version']}")
print(f"Total memories:    {status['memory_fs']['total_memories']}")
print(f"Total vectors:     {status['vector_store']['total_vectors']}")
print(f"Data synced:       {status['synced']}")          # True/False
print(f"Embedding:         {status['embedding_provider']}")
print(f"Graph nodes:       {status['memory_graph']['total_nodes']}")
print(f"Graph edges:       {status['memory_graph']['total_edges']}")
print(f"Dominant strategy: {status['scheduler']['dominant_strategy']}")
print(f"Cache hit rate:    {status['scheduler']['cache_hit_rate']}")
print(f"Overdue reviews:   {status['overdue_reviews']}")
print(f"Active workspaces: {status['active_workspaces']}")

# Lifecycle breakdown
lc = status['lifecycle']
print(f"Fresh memories:    {lc['by_state']['fresh']}")
print(f"Active memories:   {lc['by_state']['active']}")
print(f"Fading memories:   {lc['by_state']['fading']}")
print(f"Dormant memories:  {lc['by_state']['dormant']}")
print(f"At-risk memories:  {len(lc['at_risk'])} (near auto-deletion)")
```

---

## Advanced Components

### Memory Scheduler

The Scheduler decides which recall strategy to use on every call — the key
step that turns HMR from a retrieval tool into a memory operating system.

```python
# View scheduling statistics
stats = hmr.scheduler.get_stats()
print(stats["strategy_counts"])    # call count per strategy
print(stats["cache_hit_rate"])     # hot-cache hit rate
print(stats["dominant_strategy"])  # most-used strategy

# Inspect a scheduling decision without executing a recall
plan = hmr.scheduler.schedule(
    query="Why does IPC latency cause Scheduler timeouts?",
    context={"active_goal": "Optimise Scheduler"}
)
print(plan.strategy.value)   # "hybrid"
print(plan.use_jit)          # True
print(plan.top_k)            # 6
print(plan.reasoning)
# "Active goal present (Optimise Scheduler), using hybrid strategy"

# Invalidate cache entries when a memory is updated
hmr.scheduler.invalidate_cache("mem_001")
```

**Hot-cache details:**

| Property | Default | Description |
|----------|---------|-------------|
| Capacity | 50 entries | LRU eviction when full |
| TTL | 300 s (5 min) | Entries expire automatically |
| Policy | LRU | Least-recently-used evicted first |
| Benefit | Same query → instant return | No re-retrieval cost |

---

### JIT Memory Compiler

Upgrades single-shot vector search to multi-step reasoning retrieval.
Best for complex questions.

```python
# Use directly (recall() calls this automatically for complex queries)
result = hmr.jit_compiler.compile(
    query="Why did IPC latency cause a cascade of Scheduler timeouts?",
    context={"active_goal": "Investigate production incident"},
    top_k=5,
    max_steps=3   # at most 3 retrieval rounds
)

# Inspect each retrieval step
for step in result.steps:
    print(f"Step {step.step + 1}: {step.query}")
    print(f"  Found:      {len(step.memories)} memories")
    print(f"  Confidence: {step.confidence}")
    print(f"  Gaps:       {step.gaps}")

# Query rewrite trace
print("Query trace:", result.query_trace)
# ["Why did IPC latency cause…", "IPC design principle timeout",
#  "Scheduler timeout cascading"]

print(result.reasoning)
# "JIT compiled 2 steps, trace: original → rewrite-1 → rewrite-2,
#  15 candidates → top 5 selected (confidence: 0.82)"
```

**When JIT is triggered automatically:**

| Query characteristic | Example | Auto-triggers JIT |
|---------------------|---------|-------------------|
| Reasoning keywords | "why", "cause", "reason", "为什么" | ✅ |
| Time-span keywords | "history", "trend", "evolution", "演化" | ✅ |
| Manual override | `recall(strategy="jit")` | ✅ |
| Pending tasks > 3 | Active runtime with many tasks | ✅ |

---

### Memory Lifecycle Engine

Memories naturally decay; low-value memories are cleaned up automatically.

```python
from hmr.engines.lifecycle import LifecycleConfig

config = LifecycleConfig(
    max_memories_per_type=80,       # auto-compress when count exceeds this
    prune_retrievability=0.05,      # delete if SM-2 retrievability < 5%
    prune_min_age_days=7,           # only consider deletion after 7 days
    prune_require_zero_access=True, # only delete never-accessed memories
    consolidation_batch=20,         # max memories per compression run
    auto_enabled=True,              # enable automatic lifecycle checks
    check_interval_ingests=10,      # check every N ingests
)

hmr = HMR(storage_path="./my_project", lifecycle_config=config)

# Manually trigger a full check
report = hmr.lifecycle.check_now(memory_type="execution")
print(report.summary())
# "Checked 50; deleted 3; compressed 20 → 1"
print(report.reasons)
# ["Deleted [execution] <Load Test #1> (retrievability=0.02, age=14d, 0 accesses)", ...]

# View lifecycle statistics
stats = hmr.lifecycle.get_lifecycle_stats()
print(stats["by_state"])
# {"fresh": 5, "active": 30, "fading": 10, "dormant": 3}
print(stats["at_risk"])    # memories approaching auto-deletion
```

**Memory lifecycle states:**

| State | Condition | Description |
|-------|-----------|-------------|
| `fresh` | Age < 1 day | Newly ingested |
| `active` | SM-2 retrievability > 0.7 | Recently accessed, memory clear |
| `fading` | Retrievability 0.3–0.7 | Fading, could benefit from review |
| `dormant` | Retrievability < 0.3 | Long unused, near forgotten |
| `pruned` | Retrievability < 0.05 + never accessed + age ≥ 7 days | Auto-deleted |

**SM-2 retrievability formula:**

```
R(t) = e^(-t / S)

where:
  t = days since last review
  S = stability (grows with each review)

After 5 reviews:  S ≈ 18 days  → memory lasts ~2 weeks without review
After 10 reviews: S ≈ 90 days  → memory lasts ~3 months without review
```

---

### Memory Graph Layer

Automatically extracts entities and relationships from memories to build a
structured cognitive network.

```python
# The graph is updated automatically on every ingest.
# You can also query it directly.

# Find all nodes related to an entity (2-hop traversal)
nodes = hmr.memory_graph.find_related("Scheduler", depth=2)
for node in nodes:
    print(f"[{node.node_type.value}] {node.label}  ({len(node.memory_ids)} memories)")

# Get the causal chain starting from an entity
chain = hmr.memory_graph.get_causal_chain("deadlock")
for node, edge in chain:
    print(f"  →({edge.edge_type.value})→ {node.label}")
# →(causal)→ queue backup →(causal)→ response timeout

# Graph-path recall — find all memory IDs related to a query
memory_ids = hmr.memory_graph.get_memory_ids_for_query("IPC timeout root cause")
print(f"Graph path found {len(memory_ids)} related memories")

# Automatic semantic clustering
clusters = hmr.memory_graph.auto_cluster()
for c in clusters:
    print(f"Cluster '{c.label}': {len(c.node_ids)} nodes")

# Graph statistics
stats = hmr.memory_graph.get_stats()
print(stats)
# {"total_nodes": 25, "total_edges": 38,
#  "node_types": {"entity": 15, "episode": 8, "concept": 2},
#  "edge_types": {"causal": 10, "temporal": 8, "semantic": 12, "part_of": 8}}
```

**Node types:**

| Type | Description | Source |
|------|-------------|--------|
| `entity` | System/component names (Scheduler, IPC, Agent) | CamelCase words + tech nouns |
| `episode` | Complete event episodes | `execution` / `reflection` memories |
| `concept` | Abstract concepts (async, deadlock, priority) | Technical keywords |

**Edge types:**

| Type | Meaning | Example |
|------|---------|---------|
| `causal` | A causes B | deadlock → timeout |
| `temporal` | A precedes B | queue full → message drop |
| `semantic` | A ≈ B (similar meaning) | IPC ≈ message queue |
| `part_of` | A is part of B | queue ∈ Scheduler |

---

## Complete Workflow Examples

### Scenario: Multi-day Development Project

```python
from hmr.core.hmr import HMR

# ═══ Day 1: Research Phase ══════════════════════════════════════

hmr = HMR(storage_path="./scheduler_project")

hmr.ingest(
    "IPC should use async message queues with backpressure control "
    "to prevent producers from overrunning consumers and causing OOM.",
    memory_type="concept",
    title="IPC Design Principle",
    metadata={"tags": ["ipc", "async", "backpressure"]}
)

hmr.ingest(
    "Attempted lock-based synchronous scheduling. "
    "Deadlock appeared at concurrency >50 — Task A waited for Task B's lock "
    "while Task B waited for Task A's lock, forming a circular wait.",
    memory_type="execution",
    title="Sync Scheduling Failure",
    metadata={"tags": ["failure", "deadlock"], "confidence": 0.95}
)

hmr.save_runtime_state(
    goal="Design async Scheduler",
    plan=["Research IPC ✓", "Study scheduling algorithms ✓",
          "Design API", "Implement", "Load test"],
    context={"current_phase": "design", "confidence": 0.6}
)
print("Day 1 complete — state saved.")

# ═══ Day 3: Continue Development ════════════════════════════════

hmr = HMR(storage_path="./scheduler_project")   # new process

state = hmr.restore_runtime_state()
print(f"Continuing: {state.active_goal}")
print(f"Plan:       {state.current_plan}")

# Complex query — JIT multi-step retrieval triggers automatically
result = hmr.recall(
    query="Why did the sync approach deadlock, and how does async fix it?",
    context={"active_goal": state.active_goal}
)
print(f"Recall strategy: {result.recall_reasoning[:60]}")

hmr.ingest(
    "Decision: use asyncio event loop + priority heap for the Scheduler. "
    "Eliminates all thread locks — coroutine switching replaces context switching.",
    memory_type="decision",
    title="Scheduler Tech Stack Decision",
    metadata={
        "tags": ["asyncio", "scheduler", "decision"],
        "runtime_dependencies": ["IPC Design Principle", "Sync Scheduling Failure"]
    }
)

hmr.save_runtime_state(
    goal="Design async Scheduler",
    plan=["Research IPC ✓", "Study scheduling algorithms ✓",
          "Design API ✓", "Implement", "Load test"],
    context={"current_phase": "implementation", "confidence": 0.85}
)
```

### Scenario: Multi-Agent Collaboration

```python
hmr = HMR(storage_path="./team_project")

# Agent A — Backend
backend = hmr.get_workspace("agent_backend")
backend.active_goal = "Implement Scheduler core logic"
backend.push_task({"name": "Implement priority heap", "status": "in_progress"})

hmr.ingest(
    "Scheduler API: scheduler.submit(task, priority=1–10), "
    "scheduler.cancel(task_id), scheduler.get_status(task_id)",
    memory_type="decision",
    title="Scheduler API Design",
    metadata={"tags": ["api", "scheduler"]}
)
hmr.save_workspace("agent_backend")

# Agent B — Frontend
frontend = hmr.get_workspace("agent_frontend")
frontend.active_goal = "Build Scheduler management UI"
frontend.push_task({"name": "Design task list page", "status": "todo"})

# Frontend retrieves the API design from shared memory
result = hmr.recall(query="Scheduler API interface", strategy="semantic")
api_doc = result.memory_objects[0] if result.memory_objects else None
print(f"Frontend retrieved API doc: {api_doc.title if api_doc else 'not found'}")

hmr.save_workspace("agent_frontend")

# After restart — both workspaces are fully restored
hmr2 = HMR(storage_path="./team_project")
ws_b = hmr2.get_workspace("agent_backend",  create=False)
ws_f = hmr2.get_workspace("agent_frontend", create=False)
print(f"Backend goal:  {ws_b.active_goal}")
print(f"Frontend goal: {ws_f.active_goal}")
```

### Scenario: Long-running Learning Loop

```python
hmr = HMR(storage_path="./learning_project")

# Accumulate execution traces over time
for run in range(30):
    hmr.ingest(
        f"Run {run}: Scheduler latency p99={80 + run % 20}ms under {100 + run * 10} RPS. "
        f"IPC queue depth peaked at {run % 5 * 100}.",
        memory_type="execution",
        title=f"Benchmark Run #{run}"
    )

# Auto-compression kicks in when count exceeds threshold.
# Or trigger manually:
compressed = hmr.compress_memories(memory_type="execution")
if compressed:
    print(f"Compressed to: {compressed.title}")
    print(f"Content: {compressed.content[:200]}")

# The compressed memory is now a reusable concept
result = hmr.recall(query="Scheduler benchmark performance patterns")
print(f"Top result: {result.memory_objects[0].title}")
```

---

## Configuration Reference

### LifecycleConfig — Full Options

```python
from hmr.engines.lifecycle import LifecycleConfig

LifecycleConfig(
    # Auto-compression trigger
    max_memories_per_type   = 80,    # compress when per-type count exceeds this
    consolidation_batch     = 20,    # max memories per compression run
    consolidation_keep_ratio= 0.3,   # original memories' weight reduced to 30%

    # Auto-deletion conditions (ALL must be met)
    prune_retrievability    = 0.05,  # SM-2 retrievability threshold (5%)
    prune_min_age_days      = 7,     # minimum age in days
    prune_require_zero_access = True,# only delete never-accessed memories

    # Scheduling
    auto_enabled            = True,  # enable automatic lifecycle management
    check_interval_ingests  = 10,    # check every N ingests
)
```

### Environment Variables

```bash
OPENAI_API_KEY=sk-...   # Used for Embedding and LLM summarisation
```

### Directory Layout

```
hmr_data/
├── memories/
│   ├── concepts/           # concept-type memories
│   ├── executions/         # execution-type memories
│   ├── decisions/          # decision-type memories
│   └── ...                 # one sub-dir per type
├── runtimes/               # RuntimeState JSON files
├── workspaces/             # AgentWorkspace JSON files
├── vector_store/
│   ├── vectors.json        # persisted embedding vectors
│   └── vector_metadata.json
├── memory_graph/
│   └── memory_graph.json   # persisted graph data
├── index/
│   ├── memory_index.json
│   └── runtime_index.json
└── schema_version.json
```

---

## Troubleshooting

### "Rebuilding vector index" on startup

```
[HMR] Empty vector index detected — rebuilding from MemoryFS (N memories)...
```

**This is normal.** It happens on first startup or if `vector_store/` was
deleted. Rebuilding completes automatically; it only runs once.

### Recall results are not relevant

```python
# 1. Check which embedding provider is active
status = hmr.get_system_status()
print(status["embedding_provider"])
# If "tfidf", consider installing a better embedding package.

# 2. Force JIT strategy for complex questions
result = hmr.recall(query="...", strategy="jit")

# 3. Check data sync
print(status["synced"])    # should be True

# 4. Rebuild vector index if synced is False
hmr.vector_store.rebuild_from_memories(hmr.memory_fs.list_memories())
```

### `compress_memories` returns None

```python
# Reason: fewer than 2 memories meet the compression criteria.
# Check how many low-weight memories exist:
memories = hmr.memory_fs.list_memories(memory_type="execution")
low = [m for m in memories if m.temporal_weight < 0.5]
print(f"Compressible: {len(low)}")

# Force-lower temporal weight to make them eligible:
for m in memories[:5]:
    m.temporal_weight = 0.3
    hmr.memory_fs.write_memory(m)
result = hmr.compress_memories(memory_type="execution")
```

### Memory Graph node count stays at 0

```python
# The rule-based extractor looks for CamelCase words and tech nouns.
# Make sure memory content contains recognisable entities.

# Good (entities will be extracted)
hmr.ingest("The Scheduler encountered IPC queue backup under high load.", ...)

# Poor (hard to extract entities from)
hmr.ingest("Something went wrong, it was slow.", ...)
```

### Workspace disappears after restart

```python
# Always call save_workspace after modifying a workspace.
ws = hmr.get_workspace("my_agent")
ws.active_goal = "..."
hmr.save_workspace("my_agent")   # ← required, or wait for next ingest
```

### SM-2 states not restored after restart

```python
# SM-2 states are stored inside RuntimeState.current_context.
# Make sure you call save_runtime_state() before shutting down.
hmr.save_runtime_state(goal=..., plan=...)
```

---

## Changelog

| Version | Highlights |
|---------|-----------|
| **v1.5.0** | Added JIT Compiler, Memory Scheduler, Lifecycle Engine, Memory Graph |
| **v1.1.0** | Fixed VectorStore persistence, real Embedding, SM-2 algorithm, Workspace persistence |
| **v1.0.0** | Initial release — basic memory storage and recall |

---

*HMR v1.5 — Making AI systems truly remember, not just retrieve.*
