"""
HMR HTTP Service — 把 HMR 包成本地 HTTP 服务，供 OpenClaw 等外部 agent 调用

前提：
  1. 已安装 HMR：在 HMR 项目目录（含 pyproject.toml）运行过 pip install -e .
  2. 已装服务依赖：pip install fastapi uvicorn

启动：
    python server.py

默认监听 http://127.0.0.1:8077（只绑本机，不对外网开放）

可选环境变量：
    HMR_STORAGE_PATH   数据存储路径（默认 ./hmr_data）
    HMR_HOST           监听地址（默认 127.0.0.1）
    HMR_PORT           端口（默认 8077）
    HMR_TOKEN          访问令牌（默认空，不校验）
"""

import os
import sys
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

# HMR 通过 pip install -e . 安装后可直接导入，无需任何路径配置
try:
    from hmr.core.hmr import HMR
except ImportError:
    print(
        "[HMR Service] 错误：找不到 hmr 包。\n"
        "  请先在 HMR 项目目录（含 pyproject.toml 的那一层）运行：\n"
        "      pip install -e .\n",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from fastapi import FastAPI, HTTPException, Header
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print(
        "[HMR Service] 错误：缺少服务依赖。\n"
        "  请运行：pip install fastapi uvicorn\n",
        file=sys.stderr,
    )
    sys.exit(1)


# ── 配置（全部可用环境变量覆盖，无硬编码路径）─────────────────────────────
HMR_STORAGE_PATH = os.environ.get("HMR_STORAGE_PATH", "./hmr_data")
HMR_HOST = os.environ.get("HMR_HOST", "127.0.0.1")
HMR_PORT = int(os.environ.get("HMR_PORT", "8077"))
HMR_TOKEN = os.environ.get("HMR_TOKEN", "")

hmr: Optional[HMR] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global hmr
    print(f"[HMR Service] 初始化 HMR，存储路径: {HMR_STORAGE_PATH}")
    hmr = HMR(storage_path=HMR_STORAGE_PATH)
    print(f"[HMR Service] HMR v{hmr.VERSION} 就绪")
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
    return {"status": "ok", "version": hmr.VERSION if hmr else "not_ready"}


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
