# HMR v1.5 — Hestia Memory Runtime

> 中文版见 [README.md](README.md)

A persistent cognitive runtime for long-running AI systems.

## Installation

```bash
pip install pydantic numpy

# Recommended (better semantic understanding — pick one)
pip install openai                  # OpenAI Embedding
pip install sentence-transformers   # local model, no API key needed
```

## Quick Start

```python
from hmr.core.hmr import HMR

hmr = HMR(storage_path="./my_project")

hmr.ingest("IPC should use async message queues",
           memory_type="concept", title="IPC Design Principle")
hmr.save_runtime_state(goal="Design Scheduler",
                       plan=["Research", "Design", "Implement"])

# Fully restored after restart
hmr2 = HMR(storage_path="./my_project")
state  = hmr2.restore_runtime_state()
result = hmr2.recall(query="Scheduler IPC design")
```

## Directory Structure

```
hmr/
├── core/
│   ├── models.py          Data structures
│   └── hmr.py             Main engine
├── engines/
│   ├── semantic.py        Semantic retrieval
│   ├── runtime_state.py   Runtime state persistence
│   ├── recall.py          Active recall
│   ├── temporal.py        SM-2 forgetting curve
│   ├── jit_compiler.py    Multi-step reasoning retrieval
│   ├── lifecycle.py       Auto-compress / prune
│   └── scheduler.py       Strategy scheduling + hot-cache
├── storage/
│   ├── memory_fs.py       Filesystem storage
│   └── vector_store.py    Vector index (persisted)
└── graph/
    ├── cwg.py             Cognitive workspace graph
    └── memory_graph.py    Entity / causal graph
```

## Documentation

See the `docs/` directory:
- `USER_MANUAL_EN.md`       — English User Manual
- `USER_MANUAL_CN.md`       — 中文操作手册
- `BUGFIX_CN.md`            — v1.1 fix notes
- `HESTIA_INTEGRATION_EN.md`— Hestia OS integration guide

## OpenClaw Integration

HMR can serve as a persistent memory backend for [OpenClaw](https://openclaw.ai) agents, giving them cross-session memory.

```
OpenClaw agent  ──HTTP──▶  HMR service (service/server.py)  ──▶  HMR
   hmr-memory skill            127.0.0.1:8077
```

Three steps:

1. Start the HMR memory service:
   ```bash
   pip install fastapi uvicorn
   cd service
   python server.py
   ```
   See [service/README.md](service/README.md).

2. Install the OpenClaw skill (published on ClawHub):
   ```bash
   openclaw skills install hmr-memory
   ```

3. Test:
   ```bash
   openclaw agent --message "Remember I prefer Python"
   openclaw agent --message "What languages do I like?"
   ```
   If it answers Python, the integration works.

Skill source: [hmr-memory-skill](https://github.com/snowfoxHQ/hmr-memory-skill)

## License

MIT License
