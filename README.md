# HMR — Hestia Memory Runtime

> English version: [README_EN.md](README_EN.md)

> **持续认知运行时，为长期运行的 AI 系统而生**

[![版本](https://img.shields.io/badge/version-2.0.0-blue)](https://github.com/snowfoxHQ/HMR)
[![许可证](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-brightgreen)](https://python.org)

---

## 这是什么

传统 AI 记忆系统只做一件事：**存和查**。

HMR 做的是另一件事：**让 AI 像人一样思考、学习、记忆和演化。**

```
传统:   记忆 = 存储（你问，我搜）
HMR:    记忆 = 持续认知运行时
         ├── 记住"怎么想的"，不只是"发生了什么"
         ├── 从每次反思中学习，越用越准
         ├── 重启后完整恢复认知状态
         └── 主动发现重复知识，自我演化
```

---

## v2.0 新增了什么

在 v1.5（Scheduler / JIT / Lifecycle / MemoryGraph）的基础上，v2.0 新增三个认知智能层：

| 引擎 | 做什么 | 核心价值 |
|------|--------|---------|
| **ThoughtChain** | 显式推理链 + 反思循环 | AI 能回溯"当时为什么这样决策" |
| **Memory Policy** | 策略学习（存/取/忘） | 越用越准，中英文均适用 |
| **Self-Evolution** | 模式识别 + 知识抽象 + 矛盾解决 | 记忆库自我优化，不再无限膨胀 |

---

## 5 分钟快速开始

```python
from hmr.core.hmr import HMR
from hmr.engines.thought_chain import ThoughtType

hmr = HMR(storage_path="./my_project")

# 1. 存入记忆（Policy 自动判断类型）
hmr.ingest("IPC 队列积压导致超时，消费者线程不足", use_policy=True)

# 2. 显式推理链
chain = hmr.start_thinking("排查 IPC 超时根因")
hmr.think(chain.chain_id, "队列深度持续 > 800", ThoughtType.OBSERVATION)
hmr.think(chain.chain_id, "消费者线程可能不足", ThoughtType.HYPOTHESIS)
hmr.think(chain.chain_id, "扩容消费者线程 x3", ThoughtType.DECISION)
hmr.think(chain.chain_id, "已完成部署",          ThoughtType.ACTION)

# 3. 反思：评估推理质量，自动存储洞察
result = hmr.reflect_on(chain.chain_id, "延迟从 800ms 降至 50ms", rating=0.9)
print(result.insights)

# 4. 下次遇到类似问题，直接查历史最优决策
best = hmr.best_decision_for("IPC 积压问题")
print(best)   # [历史参考 准确率=90%] 扩容消费者线程 x3 + 提升优先级

# 5. 保存认知状态，重启后完整恢复
hmr.save_runtime_state(goal="优化 IPC 性能", plan=["分析 ✓", "扩容 ✓", "验证"])
# ↑ 向量索引、SM-2 状态、推理链、Policy 权重——全部持久化

# 6. 自我演化（发现重复知识，自动压缩抽象）
report = hmr.evolve()
print(report["summary"])
```

---

## 安装

```bash
# 基础（内置 TF-IDF Embedding，始终可用）
pip install pydantic numpy

# 推荐（更好的语义理解）
pip install openai              # 方案A：OpenAI Embedding
# 或
pip install sentence-transformers  # 方案B：本地模型，无需 API Key

# 设置 OpenAI Key（如使用方案A）
export OPENAI_API_KEY="sk-..."
```

---

## 系统架构

```
HMR v2.0
│
├── core/
│   ├── models.py          数据结构（MemoryObject / RuntimeState / AgentWorkspace）
│   └── hmr.py             主引擎（所有 API 入口）
│
├── engines/
│   ├── semantic.py        语义检索引擎           ─ v1.0
│   ├── runtime_state.py   运行时状态持久化         ─ v1.0
│   ├── recall.py          主动召回引擎             ─ v1.0
│   ├── temporal.py        SM-2 遗忘曲线           ─ v1.1
│   ├── jit_compiler.py    多步推理检索             ─ v1.5
│   ├── lifecycle.py       自动压缩 / 剪枝          ─ v1.5
│   ├── scheduler.py       策略调度 + 热缓存        ─ v1.5
│   ├── thought_chain.py   推理链 + 反思循环        ─ v2.0 ★
│   ├── policy.py          存/取/忘策略学习         ─ v2.0 ★
│   └── evolution.py       自我演化引擎             ─ v2.0 ★
│
├── storage/
│   ├── memory_fs.py       文件系统存储（原子写入）
│   └── vector_store.py    向量索引（持久化）
│
└── graph/
    ├── cwg.py             认知工作图（运行时依赖）
    └── memory_graph.py    实体 / 因果 / 时序图    ─ v1.5
```

---

## 核心 API 速览

```python
hmr = HMR(storage_path="./data", llm_api_key="sk-...")

# ── 记忆管理 ─────────────────────────────────────────────────
hmr.ingest(content, memory_type, title, metadata, use_policy)
hmr.recall(query, context, top_k, strategy, use_policy)
hmr.compress_memories(memory_type, memory_ids, max_memories)

# ── 运行时状态 ───────────────────────────────────────────────
hmr.save_runtime_state(goal, plan, context)
hmr.restore_runtime_state(runtime_id)

# ── 代理工作区 ───────────────────────────────────────────────
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

# ── 系统状态 ─────────────────────────────────────────────────
hmr.get_system_status()
```

---

## 版本历史

| 版本 | 核心内容 |
|------|---------|
| **v2.0** | ThoughtChain / Policy / Evolution 三大认知引擎 |
| **v1.5** | JIT Compiler / Scheduler / Lifecycle / Memory Graph |
| **v1.1** | VectorStore 持久化 / SM-2 遗忘曲线 / Workspace 持久化 |
| **v1.0** | 初始版本：记忆存储 + 语义召回 + RuntimeState |

---

## 许可证

MIT License — 自由使用、修改、商业应用。

---

*HMR: 让 AI 不只记住答案，而是记住如何思考。*
