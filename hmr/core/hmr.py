"""
HMR v1.5 - Hestia Memory Runtime
持续认知运行时

核心组件：
  - SemanticMemoryEngine   语义记忆引擎
  - TemporalEngine          SM-2 遗忘曲线
  - RuntimeStateEngine      认知状态持久化
  - ActiveRecallEngine      主动召回
  - JITMemoryCompiler       多步推理检索
  - MemoryLifecycleEngine   生命周期自动管理
  - MemoryScheduler         策略调度 + 热缓存
  - MemoryGraph             实体/因果/时序图
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from .models import (
    MemoryObject, RuntimeState, AgentWorkspace, CognitiveNode, RecallResult
)
from ..engines.semantic       import SemanticMemoryEngine
from ..engines.runtime_state  import RuntimeStateEngine
from ..engines.recall         import ActiveRecallEngine
from ..engines.temporal       import TemporalEngine
from ..engines.jit_compiler   import JITMemoryCompiler, CompileResult
from ..engines.lifecycle      import MemoryLifecycleEngine, LifecycleConfig
from ..engines.scheduler      import MemoryScheduler, RecallStrategy
from ..storage.memory_fs      import MemoryFS
from ..storage.vector_store   import VectorStore
from ..graph.cwg              import CognitiveWorkspaceGraph
from ..graph.memory_graph     import MemoryGraph


class HMR:
    """
    Hestia Memory Runtime v1.5

    基础用法：
        hmr = HMR(storage_path="./my_data")
        hmr.ingest("IPC 设计原则", memory_type="concept")
        hmr.save_runtime_state(goal="设计调度器", plan=["研究", "设计", "实现"])

        # 重启后恢复
        hmr2 = HMR(storage_path="./my_data")
        state = hmr2.restore_runtime_state()
        result = hmr2.recall(query="调度器设计")
    """

    VERSION = "1.5.0"

    def __init__(
        self,
        storage_path: str = "./hmr_data",
        embedding_model: str = "text-embedding-3-small",
        llm_api_key: Optional[str] = None,
        lifecycle_config: Optional[LifecycleConfig] = None,
    ):
        self.storage_path = storage_path
        self._llm_api_key = llm_api_key

        # 存储层
        self.memory_fs = MemoryFS(storage_path)
        self.vector_store = VectorStore(
            embedding_model=embedding_model,
            storage_path=f"{storage_path}/vector_store"
        )

        # 核心引擎
        self.semantic_engine = SemanticMemoryEngine(
            vector_store=self.vector_store,
            memory_fs=self.memory_fs
        )
        self.temporal_engine  = TemporalEngine(memory_fs=self.memory_fs)
        self.runtime_engine   = RuntimeStateEngine(memory_fs=self.memory_fs)
        self.recall_engine    = ActiveRecallEngine(
            semantic_engine=self.semantic_engine,
            runtime_engine=self.runtime_engine,
            temporal_engine=self.temporal_engine
        )
        self.jit_compiler = JITMemoryCompiler(
            semantic_engine=self.semantic_engine,
            temporal_engine=self.temporal_engine
        )
        self.scheduler = MemoryScheduler(
            temporal_engine=self.temporal_engine,
            memory_fs=self.memory_fs
        )
        self.lifecycle = MemoryLifecycleEngine(
            memory_fs=self.memory_fs,
            temporal_engine=self.temporal_engine,
            config=lifecycle_config or LifecycleConfig()
        )
        self.lifecycle.register_compress_fn(self.compress_memories)

        # 图层
        self.cwg          = CognitiveWorkspaceGraph(memory_fs=self.memory_fs)
        self.memory_graph = MemoryGraph(
            storage_path=f"{storage_path}/memory_graph"
        )

        # 代理工作区
        self.workspaces: Dict[str, AgentWorkspace] = {}
        self._load_workspaces()

        self.current_runtime: Optional[RuntimeState] = None

        # 启动同步
        self._sync_vector_store()

    # =========================================================================
    # 启动同步
    # =========================================================================

    def _sync_vector_store(self):
        all_memories = self.memory_fs.list_memories()
        vs_count = len(self.vector_store.vectors)
        if all_memories and vs_count == 0:
            print(f"[HMR] 检测到向量为空，重建索引（{len(all_memories)} 条）...")
            self.vector_store.rebuild_from_memories(all_memories)
            for m in all_memories:
                self.temporal_engine.create_temporal_state(m)
        elif all_memories:
            missing = [m for m in all_memories if m.id not in self.vector_store.vectors]
            if missing:
                self.vector_store.rebuild_from_memories(missing)

    def _load_workspaces(self):
        for ws in self.memory_fs.list_workspaces():
            self.workspaces[ws.agent_id] = ws

    # =========================================================================
    # ingest
    # =========================================================================

    def ingest(
        self,
        content: str,
        memory_type: str = "concept",
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryObject:
        """摄入新记忆，自动触发图更新和生命周期检查"""
        summary = self._generate_summary(content, title)
        memory = MemoryObject(
            type=memory_type,
            title=title or f"{memory_type.title()} {datetime.utcnow().strftime('%H:%M')}",
            content=content,
            semantic_summary=summary,
        )
        if metadata:
            for key in ["tags", "runtime_dependencies", "linked_memories", "confidence"]:
                if key in metadata:
                    setattr(memory, key, metadata[key])

        self.semantic_engine.store(memory)
        self.temporal_engine.create_temporal_state(memory)

        if self.current_runtime:
            self._update_cwg_for_memory(memory)

        try:
            self.memory_graph.add_from_memory(memory)
        except Exception:
            pass

        self.lifecycle.on_ingest(memory)
        return memory

    # =========================================================================
    # recall
    # =========================================================================

    def recall(
        self,
        query: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        strategy: Optional[str] = None
    ) -> RecallResult:
        """
        智能召回。Scheduler 自动决定策略：
          semantic / temporal / jit / hybrid / graph
        可通过 strategy 参数手动指定。
        """
        context = context or self._get_current_context()
        plan    = self.scheduler.schedule(query, context, hint=strategy)

        cache_key = f"{query}|{context.get('active_goal','')}|{plan.top_k}"
        cached = self.scheduler.get_from_cache(cache_key)
        if cached:
            return RecallResult(
                memory_objects=cached,
                recall_reasoning=f"[Cache] {plan.reasoning}",
                predicted_need=[query or ""],
                relevance_scores={m.id: 1.0 for m in cached}
            )

        if plan.use_jit:
            cr: CompileResult = self.jit_compiler.compile(
                query=query or context.get("active_goal", ""),
                context=context, top_k=plan.top_k,
                max_steps=plan.jit_max_steps
            )
            memories, scores = cr.memories, cr.relevance_scores
            reasoning = f"[{plan.strategy.value.upper()}] {cr.reasoning}"
        else:
            r = self.recall_engine.recall(
                query=query, context=context, top_k=plan.top_k
            )
            memories, scores = r.memory_objects, r.relevance_scores
            reasoning = f"[{plan.strategy.value.upper()}] {r.recall_reasoning}"

        # Graph 增强
        if plan.strategy in (RecallStrategy.GRAPH, RecallStrategy.HYBRID):
            graph_ids = self.memory_graph.get_memory_ids_for_query(
                query or context.get("active_goal", "")
            )
            seen = {m.id for m in memories}
            for mid in graph_ids:
                if mid not in seen and len(memories) < plan.top_k * 2:
                    mem = self.memory_fs.read_memory(mid)
                    if mem:
                        memories.append(mem)
                        scores[mid] = 0.5
                        seen.add(mid)
            memories.sort(key=lambda m: scores.get(m.id, 0), reverse=True)
            memories = memories[:plan.top_k]

        if plan.cache_result:
            self.scheduler.put_to_cache(cache_key, memories)

        return RecallResult(
            memory_objects=memories,
            recall_reasoning=reasoning,
            predicted_need=[query or ""] + list(context.get("focus_areas", [])),
            relevance_scores=scores
        )

    # =========================================================================
    # Runtime State
    # =========================================================================

    def save_runtime_state(
        self,
        goal: Optional[str] = None,
        plan: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> RuntimeState:
        """保存当前认知运行时状态（含 SM-2）"""
        state = RuntimeState(
            active_goal=goal, current_plan=plan or [],
            current_context=context or {},
            active_agents=list(self.workspaces.keys()),
        )
        state.current_context["__sm2_states__"] = \
            self.temporal_engine.export_sm2_states()
        self.runtime_engine.save_state(state)
        self.current_runtime = state
        return state

    def restore_runtime_state(
        self, runtime_id: Optional[str] = None
    ) -> Optional[RuntimeState]:
        """恢复认知运行时状态，自动预加载相关记忆"""
        state = self.runtime_engine.restore_state(runtime_id)
        if state:
            self.current_runtime = state
            sm2 = state.current_context.pop("__sm2_states__", {})
            if sm2:
                self.temporal_engine.import_sm2_states(sm2)
            self._preload_runtime_memories(state)
        return state

    # =========================================================================
    # Agent Workspace
    # =========================================================================

    def get_workspace(
        self, agent_id: str, create: bool = True
    ) -> Optional[AgentWorkspace]:
        """获取或创建代理工作区（自动持久化）"""
        if agent_id not in self.workspaces:
            if not create:
                return None
            ws = AgentWorkspace(agent_id=agent_id)
            self.workspaces[agent_id] = ws
            self.memory_fs.write_workspace(ws)
        return self.workspaces.get(agent_id)

    def save_workspace(self, agent_id: str):
        ws = self.workspaces.get(agent_id)
        if ws:
            self.memory_fs.write_workspace(ws)

    # =========================================================================
    # Snapshot
    # =========================================================================

    def snapshot(self) -> Dict[str, Any]:
        return {
            "version": self.VERSION,
            "current_runtime": self.current_runtime.snapshot() if self.current_runtime else None,
            "workspaces": {aid: ws.model_dump() for aid, ws in self.workspaces.items()},
            "sm2_states": self.temporal_engine.export_sm2_states(),
            "timestamp": datetime.utcnow().isoformat()
        }

    def restore_snapshot(self, snapshot: Dict[str, Any]):
        if snapshot.get("current_runtime"):
            self.current_runtime = RuntimeState.restore(snapshot["current_runtime"])
        for agent_id, ws_data in snapshot.get("workspaces", {}).items():
            ws = AgentWorkspace(**ws_data)
            self.workspaces[agent_id] = ws
            self.memory_fs.write_workspace(ws)
        if snapshot.get("sm2_states"):
            self.temporal_engine.import_sm2_states(snapshot["sm2_states"])

    # =========================================================================
    # compress_memories
    # =========================================================================

    def compress_memories(
        self,
        memory_ids: Optional[List[str]] = None,
        memory_type: Optional[str] = None,
        max_memories: int = 20
    ) -> Optional[MemoryObject]:
        """压缩多条记忆为一条抽象知识（LLM 摘要 or TF-IDF 降级）"""
        if memory_ids:
            memories = [self.memory_fs.read_memory(mid) for mid in memory_ids]
            memories = [m for m in memories if m]
        elif memory_type:
            memories = self.memory_fs.list_memories(memory_type)
        else:
            memories = self.memory_fs.list_memories()

        memories = [
            m for m in memories
            if m.temporal_weight < 0.5 or m.access_count > 5
        ][:max_memories]

        if len(memories) < 2:
            return None

        combined = "\n\n---\n\n".join([
            f"[{m.type}] {m.title}:\n{m.content[:300]}" for m in memories
        ])
        abstract = (
            self._compress_with_llm(combined, memories)
            or self._compress_with_tfidf(memories)
        )
        all_tags = list(set(t for m in memories for t in m.tags))
        all_deps = list(set(d for m in memories for d in m.runtime_dependencies))

        compressed = self.ingest(
            content=abstract,
            memory_type="concept",
            title=f"[压缩] {self._extract_topic(memories)}",
            metadata={
                "tags": all_tags[:10] + ["compressed"],
                "runtime_dependencies": all_deps[:5],
                "confidence": 0.85
            }
        )
        for m in memories:
            m.confidence = max(0.1, m.confidence * 0.5)
            if "compressed_source" not in m.tags:
                m.tags.append("compressed_source")
            self.memory_fs.write_memory(m)

        print(f"[HMR] 压缩完成：{len(memories)} 条 → 《{compressed.title}》")
        return compressed

    # =========================================================================
    # 系统状态
    # =========================================================================

    def get_system_status(self) -> Dict[str, Any]:
        fs_stats        = self.memory_fs.get_statistics()
        vs_stats        = self.vector_store.get_stats()
        lc_stats        = self.lifecycle.get_lifecycle_stats()
        graph_stats     = self.memory_graph.get_stats()
        scheduler_stats = self.scheduler.get_stats()
        overdue         = self.temporal_engine.get_forgetting_schedule()

        return {
            "version":           self.VERSION,
            "memory_fs":         fs_stats,
            "vector_store":      vs_stats,
            "synced":            fs_stats["total_memories"] <= vs_stats["total_vectors"],
            "lifecycle":         lc_stats,
            "memory_graph":      graph_stats,
            "scheduler":         scheduler_stats,
            "active_runtime":    self.current_runtime.runtime_id if self.current_runtime else None,
            "active_workspaces": len(self.workspaces),
            "overdue_reviews":   len([x for x in overdue if x["overdue_days"] > 0]),
            "embedding_provider":vs_stats.get("embedding_provider", "unknown"),
        }

    # =========================================================================
    # 内部辅助
    # =========================================================================

    def _get_current_context(self) -> Dict[str, Any]:
        return {
            "runtime_id":    self.current_runtime.runtime_id if self.current_runtime else None,
            "active_goal":   self.current_runtime.active_goal if self.current_runtime else None,
            "focus_areas":   self.current_runtime.focus_areas if self.current_runtime else [],
            "pending_tasks": self.current_runtime.pending_tasks if self.current_runtime else [],
            "active_agents": list(self.workspaces.keys()),
        }

    def _update_cwg_for_memory(self, memory: MemoryObject):
        node = CognitiveNode(
            type="memory", content=memory.title,
            metadata={"memory_id": memory.id, "memory_type": memory.type}
        )
        self.cwg.add_node(node)
        if self.current_runtime:
            self.cwg.link_to_runtime(node.node_id, self.current_runtime.runtime_id)

    def _preload_runtime_memories(self, state: RuntimeState):
        if state.active_goal:
            result = self.recall(
                query=state.active_goal,
                context={
                    "active_goal":   state.active_goal,
                    "focus_areas":   state.focus_areas,
                    "pending_tasks": state.pending_tasks,
                }
            )
            state.active_memory_ids = [m.id for m in result.memory_objects]
            print(f"[HMR] 预加载 {len(result.memory_objects)} 条相关记忆")

    def _generate_summary(self, content: str, title: Optional[str] = None) -> str:
        if len(content) > 200:
            s = self._summarize_with_llm(content)
            if s:
                return s
        return self._summarize_with_keywords(content, title)

    def _summarize_with_llm(self, content: str) -> Optional[str]:
        try:
            import openai, os
            key = self._llm_api_key or os.environ.get("OPENAI_API_KEY", "")
            if not key:
                return None
            client = openai.OpenAI(api_key=key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user",
                           "content": f"用一句话（30字以内）概括核心要点：\n\n{content[:1000]}"}],
                max_tokens=60
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return None

    def _summarize_with_keywords(self, content: str, title: Optional[str] = None) -> str:
        import re
        from collections import Counter
        stop = {"的","了","是","在","我","有","和","就","不","人","都",
                "a","an","the","is","are","to","of","and","in","for","that","this"}
        words = re.findall(r'\b\w{2,}\b', content.lower())
        kws   = [w for w in words if w not in stop]
        top   = [w for w, _ in Counter(kws).most_common(8)]
        prefix    = f"[{title}] " if title else ""
        candidate = f"{prefix}核心：{', '.join(top)}" if top else content[:80]
        return candidate if len(candidate) < len(content) else content[:80] + "..."

    def _compress_with_llm(self, combined: str, memories) -> Optional[str]:
        try:
            import openai, os
            key = self._llm_api_key or os.environ.get("OPENAI_API_KEY", "")
            if not key:
                return None
            client = openai.OpenAI(api_key=key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user",
                           "content": f"从以下{len(memories)}条记忆中提取核心规律（200字以内）：\n{combined[:3000]}"}],
                max_tokens=300
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return None

    def _compress_with_tfidf(self, memories) -> str:
        import re
        from collections import Counter
        stop  = {"的","了","是","在","a","an","the","is","to","of","and","in","for"}
        text  = " ".join(m.content for m in memories)
        words = re.findall(r'\b\w{2,}\b', text.lower())
        top   = [w for w, _ in Counter([w for w in words if w not in stop]).most_common(15)]
        types = list(set(m.type for m in memories))
        return (
            f"涵盖 {len(memories)} 条记忆（类型：{', '.join(types)}）。\n"
            f"核心关键词：{', '.join(top)}。"
        )

    def _extract_topic(self, memories) -> str:
        import re
        from collections import Counter
        words = [w for m in memories for w in re.findall(r'\b\w{3,}\b', m.title)]
        return " + ".join(w for w, _ in Counter(words).most_common(2)) if words else "混合记忆"


def create_hmr(
    storage_path: str = "./hmr_data",
    llm_api_key: Optional[str] = None
) -> HMR:
    """便捷工厂函数"""
    return HMR(storage_path=storage_path, llm_api_key=llm_api_key)
