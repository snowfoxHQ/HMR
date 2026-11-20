# HMR — Hestia Memory Runtime

> 中文版见 [README.md](README.md)

> **A Persistent Cognitive Runtime for Long-Running AI Systems**

[![version](https://img.shields.io/badge/version-2.0.0-blue)](https://github.com/hestia-os/hmr)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10+-brightgreen)](https://python.org)

---

## What is it?

Traditional AI memory systems do one thing: **store and retrieve**.

HMR does something different: **it makes AI think, learn, remember, and evolve like a human mind.**

```
Traditional:  Memory = Storage  (you ask, it searches)
HMR:          Memory = Persistent Cognitive Runtime
               ├── Remembers *how* it thought, not just *what* happened
               ├── Learns from every reflection — gets smarter over time
               ├── Fully restores cognitive state after restart
               └── Actively discovers redundant knowledge, self-evolves
```

---

## What's New in v2.0

Built on top of v1.5 (Scheduler / JIT / Lifecycle / MemoryGraph), v2.0 adds three cognitive intelligence layers:

| Engine | What it does | Core value |
|--------|-------------|------------|
| **ThoughtChain** | Explicit reasoning chains + reflection loops | AI can trace back *why* it made a decision |
| **Memory Policy** | Strategy learning (store / recall / forget) | Gets more accurate the more you use it |
| **Self-Evolution** | Pattern detection + knowledge abstraction + contradiction resolution | Memory base self-optimises, never bloats |

---

## 5-Minute Quick Start

```python
from hmr.core.hmr import HMR
from hmr.engines.thought_chain import ThoughtType

hmr = HMR(storage_path="./my_project")

# 1. Store memory (Policy auto-detects type)
hmr.ingest("IPC queue backup caused timeouts — consumer threads insufficient",
           use_policy=True)

# 2. Build an explicit reasoning chain
chain = hmr.start_thinking("Diagnose IPC timeout root cause")
hmr.think(chain.chain_id, "Queue depth sustained >800",     ThoughtType.OBSERVATION)
hmr.think(chain.chain_id, "Consumer threads may be too few", ThoughtType.HYPOTHESIS)
hmr.think(chain.chain_id, "Scale consumer threads to x3",   ThoughtType.DECISION)
hmr.think(chain.chain_id, "Deployment complete",             ThoughtType.ACTION)

# 3. Reflect: evaluate reasoning quality, auto-store insights
result = hmr.reflect_on(chain.chain_id,
                         "Latency dropped from 800ms to 50ms", rating=0.9)
print(result.insights)

# 4. Next time you hit a similar problem, fetch the best historical decision
best = hmr.best_decision_for("IPC queue backup")
print(best)
# [Historical ref, accuracy=90%] Scale consumer threads to x3 + raise priority

# 5. Save cognitive state — fully restored after restart
hmr.save_runtime_state(goal="Optimise IPC performance",
                        plan=["Analyse ✓", "Scale ✓", "Validate"])
# ↑ Vector index, SM-2 state, chains, Policy weights — all persisted

# 6. Self-evolve (finds duplicate knowledge, compresses + abstracts)
report = hmr.evolve()
print(report["summary"])
```

---

## Installation

```bash
# Minimal (built-in TF-IDF Embedding — always works)
pip install pydantic numpy

# Recommended (better semantic understanding)
pip install openai                  # Option A: OpenAI Embeddings
# or
pip install sentence-transformers   # Option B: local model, no API key needed

# Set key if using Option A
export OPENAI_API_KEY="sk-..."
```

---

## Architecture

```
HMR v2.0
│
├── core/
│   ├── models.py          Data structures (MemoryObject / RuntimeState / AgentWorkspace)
│   └── hmr.py             Main engine (all API entry points)
│
├── engines/
│   ├── semantic.py        Semantic retrieval engine            — v1.0
│   ├── runtime_state.py   Runtime state persistence            — v1.0
│   ├── recall.py          Active recall engine                 — v1.0
│   ├── temporal.py        SM-2 forgetting curve                — v1.1
│   ├── jit_compiler.py    Multi-step reasoning retrieval       — v1.5
│   ├── lifecycle.py       Auto-compress / prune                — v1.5
│   ├── scheduler.py       Strategy scheduling + hot-cache      — v1.5
│   ├── thought_chain.py   Reasoning chains + reflection loops  — v2.0 ★
│   ├── policy.py          Store/recall/forget strategy learning — v2.0 ★
│   └── evolution.py       Self-evolution engine                — v2.0 ★
│
├── storage/
│   ├── memory_fs.py       Filesystem storage (atomic writes)
│   └── vector_store.py    Vector index (persisted)
│
└── graph/
    ├── cwg.py             Cognitive workspace graph (runtime deps)
    └── memory_graph.py    Entity / causal / temporal graph      — v1.5
```

---

## Core API at a Glance

```python
hmr = HMR(storage_path="./data", llm_api_key="sk-...")

# ── Memory management ────────────────────────────────────────
hmr.ingest(content, memory_type, title, metadata, use_policy)
hmr.recall(query, context, top_k, strategy, use_policy)
hmr.compress_memories(memory_type, memory_ids, max_memories)

# ── Runtime state ────────────────────────────────────────────
hmr.save_runtime_state(goal, plan, context)
hmr.restore_runtime_state(runtime_id)

# ── Agent workspaces ─────────────────────────────────────────
hmr.get_workspace(agent_id)
hmr.save_workspace(agent_id)

# ── v2.0 ThoughtChain ────────────────────────────────────────
chain = hmr.start_thinking(goal, expected_outcome)
hmr.think(chain_id, content, thought_type, confidence)
hmr.reflect_on(chain_id, actual_outcome, rating)
hmr.best_decision_for(goal)

# ── v2.0 Policy ──────────────────────────────────────────────
hmr.feedback(event_type, memory_ids, signal, query, strategy)

# ── v2.0 Evolution ───────────────────────────────────────────
hmr.evolve(dry_run=False)

# ── System status ────────────────────────────────────────────
hmr.get_system_status()
```

---

## Changelog

| Version | Highlights |
|---------|-----------|
| **v2.0** | ThoughtChain / Policy / Evolution — three cognitive intelligence engines |
| **v1.5** | JIT Compiler / Scheduler / Lifecycle / Memory Graph |
| **v1.1** | VectorStore persistence / SM-2 forgetting curve / Workspace persistence |
| **v1.0** | Initial release: memory storage + semantic recall + RuntimeState |

---

## License

MIT License — free to use, modify, and deploy commercially.

---

*HMR: Making AI remember not just answers, but how to think.*
