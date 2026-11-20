"""
HMR v2.0 - 核心运行时引擎

v1.0  基础记忆存储
v1.1  持久化修复（VectorStore / SM-2 / 文件锁）
v1.5  记忆操作系统（Scheduler / JIT / Lifecycle / MemoryGraph）
v2.0  认知智能层：
        + ThoughtChain Engine  — 显式推理链 + 反思循环
        + Memory Policy Engine — 策略学习（存/取/忘）
        + Self-Evolution Engine — 模式识别 + 知识抽象 + 矛盾解决
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import hashlib
import os
import time

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
from ..engines.thought_chain  import ThoughtChainEngine, ThoughtType, ThoughtChain
from ..engines.policy         import MemoryPolicyEngine
from ..engines.memory_card    import MemoryCardEngine
from ..engines.evolution      import SelfEvolutionEngine
from ..storage.memory_fs      import MemoryFS
from ..storage.vector_store   import VectorStore
from ..storage.idempotency    import IdempotencyStore
from ..storage.pending        import PendingStore, is_retryable_error
from ..security.redaction     import redact_content
from ..personal               import PersonalMemoryContext
from ..observability          import TraceStore
from ..graph.cwg              import CognitiveWorkspaceGraph
from ..graph.memory_graph     import MemoryGraph


def detect_lang(text: str) -> str:
    """简单语言检测：按中文字符占比判断。>=15% 判 zh，否则 en。无额外依赖。"""
    if not text:
        return "en"
    zh = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    total = sum(1 for ch in text if ch.strip())
    if total == 0:
        return "en"
    return "zh" if (zh / total) >= 0.15 else "en"


class HMR:
    """
    Hestia Memory Runtime v2.0

    v2.0 新增：
        self.thought_chain  → 推理链引擎
        self.policy         → 策略学习引擎
        self.evolution      → 自我演化引擎
    """

    VERSION = "2.0.0"

    def __init__(
        self,
        storage_path: str = "./hmr_data",
        embedding_model: str = "text-embedding-3-small",
        llm_api_key: Optional[str] = None,
        lifecycle_config: Optional[LifecycleConfig] = None,
        personal_home: Optional[str] = None,
        trace_enabled: bool = True,
        trace_config: Optional[Dict[str, Any]] = None,
        workspace_id: Optional[str] = None,
        redact_on_ingest: bool = True,
    ):
        self.storage_path = storage_path
        self._llm_api_key = llm_api_key
        self.workspace_id = workspace_id or Path(storage_path).name
        self.redact_on_ingest = redact_on_ingest

        # v2.1 P2：个人记忆层，默认随 storage_path 落盘，不污染用户主目录
        self.personal = PersonalMemoryContext(
            personal_home or str(Path(storage_path) / "personal-memory")
        )

        # v2.1 P3：本地 trace；初始化失败不能阻断运行时
        try:
            self.trace = TraceStore(
                str(Path(storage_path) / "traces"),
                enabled=trace_enabled,
                **(trace_config or {}),
            )
        except Exception:
            self.trace = TraceStore(
                str(Path(storage_path) / "traces"), enabled=False
            )

        # v2.2 S2：写入幂等（单 Runtime / 单进程边界）
        self.idempotency = IdempotencyStore(storage_path)
        self.pending = PendingStore(storage_path)

        # ── 存储层 ────────────────────────────────────────────────────────────
        self.memory_fs = MemoryFS(storage_path)
        self.vector_store = VectorStore(
            embedding_model=embedding_model,
            storage_path=f"{storage_path}/vector_store"
        )

        # ── v1.x 核心引擎 ─────────────────────────────────────────────────────
        self.semantic_engine = SemanticMemoryEngine(
            vector_store=self.vector_store, memory_fs=self.memory_fs
        )
        self.temporal_engine  = TemporalEngine(memory_fs=self.memory_fs)
        self.runtime_engine   = RuntimeStateEngine(memory_fs=self.memory_fs)
        self.recall_engine    = ActiveRecallEngine(
            semantic_engine=self.semantic_engine,
            runtime_engine=self.runtime_engine,
            temporal_engine=self.temporal_engine
        )
        self.jit_compiler  = JITMemoryCompiler(
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
        self.lifecycle.register_delete_fn(self.delete_memory)

        # ── 图层 ──────────────────────────────────────────────────────────────
        self.cwg          = CognitiveWorkspaceGraph(memory_fs=self.memory_fs)
        self.memory_graph = MemoryGraph(storage_path=f"{storage_path}/memory_graph")

        # ── v2.0 新增认知引擎 ─────────────────────────────────────────────────
        self.thought_chain = ThoughtChainEngine(
            storage_path=f"{storage_path}/thought_chains"
        )
        self.thought_chain.register_ingest_fn(self.ingest)
        self.thought_chain.register_pending_fn(self.queue_pending)

        self.policy = MemoryPolicyEngine(
            storage_path=f"{storage_path}/policy"
        )

        self.evolution = SelfEvolutionEngine(
            storage_path=f"{storage_path}/evolution"
        )
        self.evolution.register_ingest_fn(self.ingest)
        self.evolution.register_llm_fn(self._summarize_with_llm)

        # v2.1 新增：结构化记忆卡引擎（MemoraX 借鉴 P1）
        self.memory_card = MemoryCardEngine()

        # ── 代理工作区 ────────────────────────────────────────────────────────
        self.workspaces: Dict[str, AgentWorkspace] = {}
        self._load_workspaces()

        # ── 当前运行时 ────────────────────────────────────────────────────────
        self.current_runtime: Optional[RuntimeState] = None

        # ── 启动同步 ──────────────────────────────────────────────────────────
        self._sync_vector_store()
        self._recover_pending()

    # =========================================================================
    # 启动同步
    # =========================================================================

    def _sync_vector_store(self):
        all_memories = self.memory_fs.list_memories()
        vs_count = len(self.vector_store.vectors)
        if all_memories and vs_count == 0:
            print(f"[HMR] 重建向量索引（{len(all_memories)} 条）...")
            self.vector_store.rebuild_from_memories(all_memories)
            for mem in all_memories:
                self.temporal_engine.create_temporal_state(mem)
        elif all_memories:
            missing = [m for m in all_memories if m.id not in self.vector_store.vectors]
            if missing:
                self.vector_store.rebuild_from_memories(missing)

        # 反向对账：向量存在但记忆文件已不存在，清理孤儿向量
        valid_ids = {m.id for m in all_memories}
        orphans = [vid for vid in self.vector_store.vectors if vid not in valid_ids]
        for vid in orphans:
            self.vector_store.delete(vid)
        if orphans:
            print(f"[HMR] 清理孤儿向量 {len(orphans)} 条")

    def _load_workspaces(self):
        for ws in self.memory_fs.list_workspaces():
            self.workspaces[ws.agent_id] = ws

    # =========================================================================
    # ingest（v2.0：Policy 驱动）
    # =========================================================================

    def ingest(
        self,
        content: str,
        memory_type: str = "concept",
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        use_policy: bool = False,   # 是否用 Policy 自动决定类型和置信度
        boundary: Optional[str] = None,
        scope: Optional[str] = None,
        _pending_id: Optional[str] = None,
    ) -> MemoryObject:
        """
        摄入记忆。

        v2.0 新增：
        - use_policy=True 时，Policy 自动推断 memory_type 和 confidence
        v2.1 新增（MemoraX 借鉴 P0）：
        - 完整保留 metadata，不再丢弃未知字段
        - boundary/scope/status/evidence/source 结构化落盘
        """
        meta = dict(metadata or {})

        # v2.1 P1：CODE_AGENT_MEMORY 自动识别与验证门槛
        if self.memory_card.is_card(content):
            card = self.memory_card.parse(content)
            if card is None:
                raise ValueError("CODE_AGENT_MEMORY 卡片格式无法解析")
            card_check = self.memory_card.validate(card)
            if not card_check.ok:
                raise ValueError(
                    "CODE_AGENT_MEMORY 校验失败: " + "; ".join(card_check.errors)
                )
            card_kwargs = self.memory_card.to_memory_kwargs(card)
            content = card_kwargs["content"]
            title = title or card_kwargs["title"]
            if memory_type == "concept":
                memory_type = card_kwargs["memory_type"]
            boundary = boundary or card_kwargs["boundary"]
            # 卡片的 status/evidence 优先，调用方无法通过 metadata 绕过验证门槛
            meta = {**meta, **card_kwargs["metadata"]}

        # v2.2 S2：写入前脱敏（先脱敏再计算指纹，落盘内容不含敏感片段）
        if self.redact_on_ingest:
            content = redact_content(content)
            if title:
                title = redact_content(title)

        # v2.2 S2：来源身份与工作区作用域绑定
        for key in (
            "source_client", "source_session_id",
            "source_turn_id", "source_workspace",
        ):
            if key in meta and meta[key] is not None:
                meta[key] = str(meta[key])
        meta.setdefault("source_timestamp", datetime.utcnow().isoformat())
        if meta.get("source_workspace") and meta["source_workspace"] != self.workspace_id:
            raise ValueError(
                f"来源工作区不匹配：{meta['source_workspace']!r} != {self.workspace_id!r}"
            )
        meta["source_hash"] = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()[:16]

        # v2.2 S2：幂等占位，命中时直接返回已存在的记忆
        idem_key = self.idempotency.make_key(meta.get("source_turn_id", ""), content)
        duplicate_id = self.idempotency.check_and_reserve(idem_key)
        if duplicate_id:
            existing = self.memory_fs.read_memory(duplicate_id)
            if existing is not None:
                return existing
            # 占位记录指向的记忆已不存在，释放后正常重写
            self.idempotency.release(idem_key)

        # v2.3 S3：先登记 accepted 状态，失败后仍可恢复
        if _pending_id is None:
            _pending_id = self.pending.add(
                content=content,
                memory_type=memory_type,
                title=title or "",
                metadata=meta,
                idem_key=idem_key,
            )

        # Policy 驱动模式
        if use_policy:
            ctx = {
                "title": title,
                "tags": meta.get("tags", []),
                "runtime_dependencies": meta.get("runtime_dependencies", []),
                "existing_memory_count": len(self.vector_store.vectors),
            }
            policy_decision = self.policy.decide_ingest(
                content, title, ctx["tags"], ctx["runtime_dependencies"],
                ctx["existing_memory_count"]
            )
            if not policy_decision["should_store"]:
                # Policy 认为不值得存：释放占位并撤销 pending
                self.idempotency.release(idem_key)
                if _pending_id:
                    self.pending.remove(_pending_id)
                return MemoryObject(
                    type="concept", title=title or "跳过", content=content,
                    semantic_summary=f"[Policy跳过] {policy_decision['reasoning']}"
                )
            memory_type = (
                memory_type if memory_type != "concept"
                else policy_decision["memory_type"]
            )
            meta.setdefault("confidence", policy_decision["confidence"])

        # 边界路由：显式参数 > metadata > 规则推断
        bd = boundary or meta.get("boundary")
        sc = scope or meta.get("scope")
        if bd is None or sc is None:
            boundary_decision = self.policy.decide_boundary(
                content, title, memory_type, meta.get("tags")
            )
            bd = bd or boundary_decision["boundary"]
            sc = sc or boundary_decision["scope"]
        if bd not in ("coding", "repo", "user", "procedure"):
            bd = "coding"
        if sc not in ("project", "user", "global"):
            sc = "project"
        status = meta.get("status", "active")
        if status not in ("active", "candidate", "verified", "superseded", "deleted"):
            status = "active"

        # 语言检测提前到写盘前，确保 lang 真正持久化（旧版是死代码）
        lang = detect_lang((title or "") + " " + content)
        meta.setdefault("lang", lang)
        evidence = meta.get("evidence", []) or []
        if isinstance(evidence, str):
            evidence = [evidence]

        summary = self._generate_summary(content, title)
        memory = MemoryObject(
            type=memory_type,
            title=title or f"{memory_type.title()} {datetime.utcnow().strftime('%H:%M')}",
            content=content,
            semantic_summary=summary,
            boundary=bd,
            scope=sc,
            status=status,
            source=str(meta.get("source", "agent")),
            evidence=list(evidence),
            metadata=meta,
        )

        for key in ["tags", "runtime_dependencies", "linked_memories", "confidence"]:
            if key in meta:
                setattr(memory, key, meta[key])

        self._mem_lang = getattr(self, "_mem_lang", {})
        self._mem_lang[memory.id] = lang

        try:
            self.semantic_engine.store(memory)
        except Exception as exc:
            self.idempotency.release(idem_key)
            if _pending_id:
                attempts = self.pending.get(_pending_id).attempts if self.pending.get(_pending_id) else 0
                # 不可重试错误推到很远的将来，避免启动恢复时无限重放
                delay = min(60, 2 ** attempts) if is_retryable_error(exc) else 86400
                self.pending.mark_failed(
                    _pending_id, str(exc), time.time() + delay
                )
            raise
        self.temporal_engine.create_temporal_state(memory)

        if self.current_runtime:
            self._update_cwg_for_memory(memory)

        try:
            self.memory_graph.add_from_memory(memory)
        except Exception:
            pass

        # v2.0：通知 Policy 记录这次摄入
        self.lifecycle.on_ingest(memory)

        # v2.1 P3：trace（失败不影响主链路）
        try:
            self.trace.emit(
                "memory_ingest",
                ok=True,
                outcome=memory.id,
                trace=str(meta.get("trace_id", "")),
                request={"title": memory.title, "type": memory_type, "boundary": bd},
                response={"id": memory.id, "status": memory.status},
                related_turns=list(meta.get("related_turns", []) or []),
            )
        except Exception:
            pass

        if _pending_id:
            self.pending.mark_persisted(_pending_id)
        self.idempotency.mark(idem_key, memory.id)
        return memory

    # =========================================================================
    # ingest_card（v2.1：结构化记忆卡）
    # =========================================================================

    def ingest_card(
        self,
        card_text: str,
        *,
        strict: bool = True,
        memory_type: Optional[str] = None,
        use_policy: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> MemoryObject:
        """
        摄入一张 CODE_AGENT_MEMORY 卡片。

        strict=True（默认）时，未验证的正面经验会被拒绝，
        这是从 MemoraX 借鉴的核心写入纪律。
        """
        card = self.memory_card.parse(card_text)
        if card is None:
            raise ValueError("不是合法的 CODE_AGENT_MEMORY 卡片")
        result = self.memory_card.validate(card)
        if not result.ok:
            if strict:
                raise ValueError(
                    "CODE_AGENT_MEMORY 校验失败: " + "; ".join(result.errors)
                )
            # 宽松模式：降级为 candidate，避免未验证经验伪装成 verified
            card.status = "candidate"
        options = self.memory_card.to_memory_kwargs(card)
        if memory_type:
            options["memory_type"] = memory_type
        if metadata:
            options["metadata"] = {**options["metadata"], **metadata}
        options.update(kwargs)
        return self.ingest(use_policy=use_policy, **options)

    # =========================================================================
    # delete_memory（存储一致性统一入口）
    # =========================================================================

    def delete_memory(self, memory_id: str) -> bool:
        """同时删除记忆文件、memory_index 条目与向量索引。"""
        if not self.memory_fs.delete_memory(memory_id):
            return False
        try:
            self.vector_store.delete(memory_id)
        except Exception:
            # 向量删除失败会由启动对账兜底，不影响文件删除语义
            pass
        self.semantic_engine.memory_cache.pop(memory_id, None)
        getattr(self, "_mem_lang", {}).pop(memory_id, None)
        return True

    # =========================================================================
    # Pending 恢复（v2.3 S3）
    # =========================================================================

    def queue_pending(
        self,
        content: str,
        memory_type: str = "reflection",
        title: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """登记一条延后写入，供 ThoughtChain 等失败补偿路径使用。"""
        return self.pending.add(
            content=content,
            memory_type=memory_type,
            title=title or "",
            metadata=dict(metadata or {}),
            idem_key="",
        )

    def retry_pending(self, force: bool = False, max_items: int = 20) -> Dict[str, Any]:
        """重放到期的 Pending 写入，返回统计字典。"""
        items = (
            [i for i in self.pending.all() if i.status != "persisted"]
            if force
            else self.pending.list_retryable()
        )
        stats = {"attempted": 0, "succeeded": 0, "failed": 0}
        for item in items[:max_items]:
            stats["attempted"] += 1
            try:
                self.ingest(
                    content=item.content,
                    memory_type=item.memory_type,
                    title=item.title or None,
                    metadata=item.metadata,
                    _pending_id=item.pending_id,
                )
                stats["succeeded"] += 1
            except Exception:
                stats["failed"] += 1
        return stats

    def drain_pending(self, max_items: int = 20) -> Dict[str, Any]:
        """退出前尽力刷新全部待处理写入。"""
        return self.retry_pending(force=True, max_items=max_items)

    def _recover_pending(self):
        stats = self.retry_pending()
        if stats["attempted"]:
            print(f"[HMR] Pending 恢复：{stats}")

    # =========================================================================
    # personal_context（v2.1：个人记忆注入）
    # =========================================================================

    def personal_context(self, turn: int = 1, **kwargs) -> str:
        """构建可注入的个人记忆上下文（首轮画像 + cadence 流程提醒）。"""
        return self.personal.build(turn, **kwargs)

    # =========================================================================
    # recall（v2.0：Policy 融合）
    # =========================================================================

    def recall(
        self,
        query: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        strategy: Optional[str] = None,
        use_policy: bool = True,    # 是否用 Policy 辅助调度决策
        boundaries: Optional[List[str]] = None,  # 按记忆边界过滤
    ) -> RecallResult:
        """
        召回记忆。

        v2.0 新增：
        - use_policy=True 时，Policy 辅助 Scheduler 做策略决策
        - 召回结果自动通知 Policy 记录（用于策略学习）
        """
        context = context or self._get_current_context()

        # Policy 辅助决策
        if use_policy and not strategy:
            policy_ctx = {
                **context,
                "total_memories": len(self.vector_store.vectors),
            }
            pd = self.policy.decide_recall(query or "", policy_ctx, base_top_k=top_k)
            if not strategy:
                strategy = pd["strategy"]
            top_k = pd["top_k"]

        plan = self.scheduler.schedule(query, context, hint=strategy)

        cache_key = (
            f"{query}|{context.get('active_goal', '')}|{plan.top_k}"
            f"|{','.join(sorted(boundaries or []))}"
        )
        cached = self.scheduler.get_from_cache(cache_key)
        if cached:
            cached = self._filter_by_boundary(cached, boundaries)
            try:
                self.trace.emit(
                    "memory_retrieve", ok=True, outcome="cache",
                    trace=str((context or {}).get("trace_id", "")),
                    request={"query": query, "top_k": top_k, "boundaries": boundaries},
                    response={"count": len(cached)},
                )
            except Exception:
                pass
            return RecallResult(
                memory_objects=cached,
                recall_reasoning=f"[Cache] {plan.reasoning}",
                predicted_need=[query or ""],
                relevance_scores={m.id: 1.0 for m in cached}
            )

        if plan.use_jit:
            cr: CompileResult = self.jit_compiler.compile(
                query=query or context.get("active_goal", ""),
                context=context, top_k=plan.top_k, max_steps=plan.jit_max_steps
            )
            memories, scores = cr.memories, cr.relevance_scores
            reasoning = f"[{plan.strategy.value.upper()}] {cr.reasoning}"
        else:
            r = self.recall_engine.recall(query=query, context=context, top_k=plan.top_k)
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

        memories = self._apply_lang_filter(query, memories)
        memories = self._filter_by_boundary(memories, boundaries)

        try:
            self.trace.emit(
                "memory_retrieve", ok=True, outcome=str(plan.strategy.value),
                trace=str((context or {}).get("trace_id", "")),
                request={"query": query, "top_k": top_k, "boundaries": boundaries},
                response={"count": len(memories), "ids": [m.id for m in memories]},
            )
        except Exception:
            pass

        return RecallResult(
            memory_objects=memories,
            recall_reasoning=reasoning,
            predicted_need=[query or ""] + list(context.get("focus_areas", [])),
            relevance_scores=scores
        )

    # =========================================================================
    # v2.0 新增：ThoughtChain API
    # =========================================================================

    def start_thinking(
        self,
        goal: str,
        agent_id: Optional[str] = None,
        expected_outcome: Optional[str] = None,
    ) -> ThoughtChain:
        """
        开始一条新的思维链。

        示例：
            chain = hmr.start_thinking("为什么调度器超时")
            hmr.think(chain.chain_id, "IPC 队列深度 > 1000", ThoughtType.OBSERVATION)
            hmr.think(chain.chain_id, "可能是消费者速度不够", ThoughtType.HYPOTHESIS)
            hmr.think(chain.chain_id, "增加消费者线程", ThoughtType.DECISION)
            hmr.think(chain.chain_id, "已部署 3 个消费者", ThoughtType.ACTION)
            result = hmr.reflect_on(chain.chain_id, "延迟降低 80%", rating=0.9)
        """
        runtime_id = self.current_runtime.runtime_id if self.current_runtime else None
        return self.thought_chain.create_chain(
            goal=goal, agent_id=agent_id,
            runtime_id=runtime_id, expected_outcome=expected_outcome
        )

    def think(
        self,
        chain_id: str,
        content: str,
        thought_type: ThoughtType,
        confidence: float = 0.7,
        memory_ids: Optional[List[str]] = None,
    ):
        """向思维链追加一个思维节点"""
        return self.thought_chain.add_thought(
            chain_id=chain_id, content=content,
            thought_type=thought_type, confidence=confidence,
            memory_ids=memory_ids or []
        )

    def reflect_on(
        self,
        chain_id: str,
        actual_outcome: str,
        rating: Optional[float] = None,
    ):
        """
        对思维链执行反思，自动评估推理质量并存储洞察。
        rating: 0-1，1=完全成功，0=完全失败（不传则自动推断）
        """
        return self.thought_chain.reflect(chain_id, actual_outcome, rating)

    def best_decision_for(self, goal: str) -> Optional[str]:
        """从历史成功链中查找同类问题的最优决策"""
        return self.thought_chain.get_best_decision_for(goal)

    # =========================================================================
    # v2.0 新增：Policy Feedback API
    # =========================================================================

    def feedback(
        self,
        event_type: str,
        memory_ids: List[str],
        signal: float,
        context: Optional[Dict[str, Any]] = None,
        query: Optional[str] = None,
        strategy: Optional[str] = None,
    ):
        """
        向策略引擎提供反馈，让系统从结果中学习。

        event_type:
            "recall_hit"    — 召回结果有用（signal > 0）
            "recall_miss"   — 召回结果无用（signal < 0）
            "task_success"  — 任务成功（signal 0.5~1.0）
            "task_failure"  — 任务失败（signal -0.5~-1.0）
            "compress_gain" — 压缩提升了召回质量（signal > 0）

        示例：
            result = hmr.recall(query="调度器超时原因")
            # ... 使用召回结果 ...
            hmr.feedback(
                "recall_hit",
                memory_ids=[m.id for m in result.memory_objects[:2]],
                signal=0.8,
                query="调度器超时原因",
                strategy="jit"
            )
        """
        self.policy.record_feedback(
            event_type=event_type,
            memory_ids=memory_ids,
            signal=signal,
            context=context or {},
            query=query,
            strategy=strategy,
        )

    # =========================================================================
    # v2.0 新增：Self-Evolution API
    # =========================================================================

    def evolve(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        运行一次自我演化周期。

        dry_run=True：只分析，不修改（先预览再决定）

        示例：
            # 先预览
            report = hmr.evolve(dry_run=True)
            print(report["summary"])
            for action in report["actions"]:
                print(f"  {action}")

            # 确认后执行
            hmr.evolve(dry_run=False)
        """
        system_stats = self.get_system_status()
        return self.evolution.evolve(
            memories=self.memory_fs.list_memories(),
            vector_store=self.vector_store,
            memory_fs=self.memory_fs,
            system_stats=system_stats,
            dry_run=dry_run,
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
        state = RuntimeState(
            active_goal=goal, current_plan=plan or [],
            current_context=context or {},
            active_agents=list(self.workspaces.keys()),
        )
        sm2_data = self.temporal_engine.export_sm2_states()
        state.current_context["__sm2_states__"] = sm2_data
        self.runtime_engine.save_state(state)
        self.current_runtime = state
        return state

    def restore_runtime_state(self, runtime_id: Optional[str] = None) -> Optional[RuntimeState]:
        state = self.runtime_engine.restore_state(runtime_id)
        if state:
            self.current_runtime = state
            sm2_data = state.current_context.pop("__sm2_states__", {})
            if sm2_data:
                self.temporal_engine.import_sm2_states(sm2_data)
            self._preload_runtime_memories(state)
        return state

    # =========================================================================
    # Workspace
    # =========================================================================

    def get_workspace(self, agent_id: str, create: bool = True) -> Optional[AgentWorkspace]:
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
        if memory_ids:
            memories = [self.memory_fs.read_memory(mid) for mid in memory_ids]
            memories = [m for m in memories if m]
        elif memory_type:
            memories = self.memory_fs.list_memories(memory_type)
        else:
            memories = self.memory_fs.list_memories()

        memories = [m for m in memories if m.temporal_weight < 0.5 or m.access_count > 5][:max_memories]
        if len(memories) < 2:
            return None

        combined = "\n\n---\n\n".join([
            f"[{m.type}] {m.title}:\n{m.content[:300]}" for m in memories
        ])
        abstract = self._compress_with_llm(combined, memories) or self._compress_with_tfidf(memories)
        all_tags = list(set(t for m in memories for t in m.tags))
        all_deps = list(set(d for m in memories for d in m.runtime_dependencies))

        compressed = self.ingest(
            content=abstract, memory_type="concept",
            title=f"[压缩] {self._extract_topic(memories)}",
            metadata={"tags": all_tags[:10] + ["compressed"], "runtime_dependencies": all_deps[:5], "confidence": 0.85}
        )

        for m in memories:
            m.confidence = max(0.1, m.confidence * 0.5)
            if "compressed_source" not in m.tags:
                m.tags.append("compressed_source")
            self.memory_fs.write_memory(m)

        # 通知 Policy
        self.policy.record_feedback("compress_gain", [compressed.id], 0.6)
        return compressed

    # =========================================================================
    # 系统状态（v2.0 扩展）
    # =========================================================================

    def get_system_status(self) -> Dict[str, Any]:
        fs_stats        = self.memory_fs.get_statistics()
        vs_stats        = self.vector_store.get_stats()
        lc_stats        = self.lifecycle.get_lifecycle_stats()
        graph_stats     = self.memory_graph.get_stats()
        scheduler_stats = self.scheduler.get_stats()
        overdue         = self.temporal_engine.get_forgetting_schedule()
        try:
            trace_stats = self.trace.stats()
        except Exception:
            trace_stats = {"enabled": False, "events": 0}

        return {
            "version":          self.VERSION,
            "memory_fs":        fs_stats,
            "vector_store":     vs_stats,
            "synced":           fs_stats["total_memories"] <= vs_stats["total_vectors"],
            "lifecycle":        lc_stats,
            "memory_graph":     graph_stats,
            "scheduler":        scheduler_stats,
            # v2.0 新增
            "thought_chain":    self.thought_chain.get_stats(),
            "policy":           self.policy.get_stats(),
            "evolution":        self.evolution.get_stats(),
            # v2.1 新增
            "trace":            trace_stats,
            # 通用
            "active_runtime":   self.current_runtime.runtime_id if self.current_runtime else None,
            "active_workspaces":len(self.workspaces),
            "overdue_reviews":  len([x for x in overdue if x["overdue_days"] > 0]),
            "embedding_provider": vs_stats.get("embedding_provider", "unknown"),
        }

    # =========================================================================
    # 辅助方法
    # =========================================================================

    @staticmethod
    def _filter_by_boundary(memories, boundaries):
        """按四类记忆边界过滤；旧记忆缺省 boundary=coding。"""
        if not boundaries:
            return memories
        allowed = set(boundaries)
        return [m for m in memories if getattr(m, "boundary", "coding") in allowed]

    def _apply_lang_filter(self, query, memories):
        """按 HMR_LANG_FILTER 过滤召回语言。off(默认)=不过滤；auto=按查询语言；zh/en=强制。"""
        mode = os.environ.get("HMR_LANG_FILTER", "off").lower()
        if mode == "off" or not memories:
            return memories
        if mode == "auto":
            target = detect_lang(query or "")
        elif mode in ("zh", "en"):
            target = mode
        else:
            return memories

        def mem_lang(m):
            # 直接实时检测记忆内容的语言（标题+正文），可靠且不依赖持久化
            return detect_lang((getattr(m, "title", "") or "") + " " +
                               (getattr(m, "content", "") or ""))

        filtered = [m for m in memories if mem_lang(m) == target]
        return filtered if filtered else memories

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
            result = self.recall(query=state.active_goal, context={
                "active_goal": state.active_goal,
                "focus_areas": state.focus_areas,
                "pending_tasks": state.pending_tasks
            })
            state.active_memory_ids = [m.id for m in result.memory_objects]

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
                messages=[{"role": "user", "content": f"用一句话（30字以内）概括核心要点：\n\n{content[:1000]}"}],
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
        prefix = f"[{title}] " if title else ""
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
                messages=[{"role": "user", "content":
                    f"从以下{len(memories)}条记忆中提取核心规律（200字以内）：\n{combined[:3000]}"}],
                max_tokens=300
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return None

    def _compress_with_tfidf(self, memories) -> str:
        import re
        from collections import Counter
        stop = {"的","了","是","在","a","an","the","is","to","of","and","in","for"}
        all_text = " ".join(m.content for m in memories)
        words = re.findall(r'\b\w{2,}\b', all_text.lower())
        kws = [w for w in words if w not in stop]
        top = [w for w, _ in Counter(kws).most_common(15)]
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


def create_hmr(storage_path: str = "./hmr_data", llm_api_key: Optional[str] = None) -> HMR:
    return HMR(storage_path=storage_path, llm_api_key=llm_api_key)
