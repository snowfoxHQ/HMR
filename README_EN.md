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

## License

MIT License
