"""
HMR HTTP Service — 把 HMR 包成本地 HTTP 服务，供 OpenClaw 等外部 agent 调用

前提：
  1. 已安装 HMR：在 HMR 项目目录（含 pyproject.toml）运行过 pip install -e .
  2. 已装服务依赖：pip install fastapi uvicorn

启动：python server.py
默认监听 http://127.0.0.1:8077（只绑本机）

可选环境变量：
    HMR_STORAGE_PATH / HMR_HOST / HMR_PORT / HMR_TOKEN
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

try:
    from hmr.core.hmr import HMR
except ImportError:
    print("[HMR Service] 错误：找不到 hmr 包。请在 HMR 项目目录运行 pip install -e .",
          file=sys.stderr)
    sys.exit(1)

try:
    from fastapi import FastAPI, HTTPException, Header
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("[HMR Service] 错误：缺少依赖。请运行 pip install fastapi uvicorn",
          file=sys.stderr)
    sys.exit(1)


HMR_STORAGE_PATH = os.environ.get("HMR_STORAGE_PATH", "./hmr_data")
HMR_HOST = os.environ.get("HMR_HOST", "127.0.0.1")
HMR_PORT = int(os.environ.get("HMR_PORT", "8077"))
HMR_TOKEN = os.environ.get("HMR_TOKEN", "")

_PROVIDER_MARKER = Path(HMR_STORAGE_PATH) / ".embedding_provider"

hmr: Optional[HMR] = None
provider_mismatch: Optional[Dict[str, str]] = None


def _read_last_provider() -> Optional[str]:
    try:
        if _PROVIDER_MARKER.exists():
            return _PROVIDER_MARKER.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return None


def _write_provider(provider: str):
    try:
        _PROVIDER_MARKER.parent.mkdir(parents=True, exist_ok=True)
        _PROVIDER_MARKER.write_text(provider, encoding="utf-8")
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global hmr, provider_mismatch
    print(f"[HMR Service] 初始化 HMR，存储路径: {HMR_STORAGE_PATH}")
    hmr = HMR(storage_path=HMR_STORAGE_PATH)

    current = hmr.get_system_status().get("embedding_provider", "unknown")
    last = _read_last_provider()

    if last and last != current:
        provider_mismatch = {"from": last, "to": current}
        print("=" * 64, file=sys.stderr)
        print(f"[HMR Service] ⚠️  检测到 Embedding 提供者切换：{last} → {current}",
              file=sys.stderr)
        print("    旧向量索引与当前提供者不匹配，语义搜索可能失效。", file=sys.stderr)
        print("    修复：curl -X POST http://127.0.0.1:8077/reindex", file=sys.stderr)
        print("=" * 64, file=sys.stderr)
    else:
        provider_mismatch = None

    _write_provider(current)
    print(f"[HMR Service] HMR v{hmr.VERSION} 就绪（Embedding: {current}）")
    yield
    print("[HMR Service] 关闭")


app = FastAPI(title="HMR Memory Service", lifespan=lifespan)


def check_token(x_hmr_token: Optional[str]):
    if HMR_TOKEN and x_hmr_token != HMR_TOKEN:
        raise HTTPException(status_code=401, detail="无效的 HMR token")


class IngestRequest(BaseModel):
    content: str
    memory_type: str = "concept"
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    confidence: Optional[float] = None

class RecallRequest(BaseModel):
    query: str
    top_k: int = 5
    strategy: Optional[str] = None

class SaveStateRequest(BaseModel):
    goal: Optional[str] = None
    plan: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None


@app.get("/health")
def health():
    if not hmr:
        return {"status": "starting", "version": "not_ready"}
    s = hmr.get_system_status()
    result = {
        "status": "ok",
        "version": hmr.VERSION,
        "embedding_provider": s.get("embedding_provider"),
        "total_memories": s.get("memory_fs", {}).get("total_memories", 0),
        "synced": s.get("synced", False),
    }
    if provider_mismatch:
        result["status"] = "degraded"
        result["warning"] = (
            f"Embedding 提供者从 {provider_mismatch['from']} 切换为 "
            f"{provider_mismatch['to']}，向量索引需重建。请 POST /reindex 修复。"
        )
    return result


@app.post("/reindex")
def reindex(x_hmr_token: Optional[str] = Header(None)):
    global provider_mismatch
    check_token(x_hmr_token)
    memories = hmr.memory_fs.list_memories()
    hmr.vector_store.rebuild_from_memories(memories)
    current = hmr.get_system_status().get("embedding_provider", "unknown")
    _write_provider(current)
    provider_mismatch = None
    return {
        "reindexed": True,
        "memory_count": len(memories),
        "embedding_provider": current,
        "message": f"已用 {current} 重建 {len(memories)} 条记忆的向量索引",
    }


@app.post("/ingest")
def ingest(req: IngestRequest, x_hmr_token: Optional[str] = Header(None)):
    check_token(x_hmr_token)
    metadata = {}
    if req.tags:
        metadata["tags"] = req.tags
    if req.confidence is not None:
        metadata["confidence"] = req.confidence
    mem = hmr.ingest(content=req.content, memory_type=req.memory_type,
                     title=req.title, metadata=metadata or None)
    return {"id": mem.id, "type": mem.type, "title": mem.title,
            "summary": mem.semantic_summary}


@app.post("/recall")
def recall(req: RecallRequest, x_hmr_token: Optional[str] = Header(None)):
    check_token(x_hmr_token)
    if provider_mismatch:
        raise HTTPException(
            status_code=409,
            detail=(f"向量索引与当前 Embedding 提供者不匹配"
                    f"（索引建于 {provider_mismatch['from']}，当前 "
                    f"{provider_mismatch['to']}）。请先 POST /reindex 重建。"),
        )
    result = hmr.recall(query=req.query, top_k=req.top_k, strategy=req.strategy)
    return {
        "reasoning": result.recall_reasoning,
        "memories": [
            {"id": m.id, "type": m.type, "title": m.title,
             "content": m.content, "summary": m.semantic_summary,
             "score": result.relevance_scores.get(m.id, 0.0)}
            for m in result.memory_objects
        ],
    }


@app.post("/save_state")
def save_state(req: SaveStateRequest, x_hmr_token: Optional[str] = Header(None)):
    check_token(x_hmr_token)
    state = hmr.save_runtime_state(goal=req.goal, plan=req.plan, context=req.context)
    return {"runtime_id": state.runtime_id, "goal": state.active_goal}


@app.get("/restore_state")
def restore_state(x_hmr_token: Optional[str] = Header(None)):
    check_token(x_hmr_token)
    state = hmr.restore_runtime_state()
    if not state:
        return {"restored": False}
    return {"restored": True, "runtime_id": state.runtime_id,
            "goal": state.active_goal, "plan": state.current_plan,
            "context": state.current_context}


@app.get("/status")
def status(x_hmr_token: Optional[str] = Header(None)):
    check_token(x_hmr_token)
    return hmr.get_system_status()


if __name__ == "__main__":
    print(f"[HMR Service] 启动于 http://{HMR_HOST}:{HMR_PORT}")
    if HMR_TOKEN:
        print("[HMR Service] 已启用 token 鉴权")
    uvicorn.run(app, host=HMR_HOST, port=HMR_PORT)
