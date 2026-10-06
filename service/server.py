"""
HMR HTTP Service v2.0 - wraps HMR as a local HTTP service for external agents (OpenClaw etc.)

Prerequisites:
  1. HMR installed: run 'pip install -e .' in the HMR project dir (with pyproject.toml)
  2. Service deps installed: pip install fastapi uvicorn

Start: python server.py
Default: http://127.0.0.1:8077 (localhost only)

Optional env vars:
    HMR_STORAGE_PATH / HMR_HOST / HMR_PORT / HMR_TOKEN
    OLLAMA_HOST / HMR_VISION_MODEL / HMR_VISION_PROMPT  (for /ingest_image)

/ingest_image: use local Ollama vision model to caption an image, then store in HMR
    Requires: ollama pull qwen2.5vl:7b
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

try:
    from hmr.core.hmr import HMR
except ImportError:
    print("[HMR Service] ERROR: hmr package not found. Run 'pip install -e .' in the HMR project dir.",
          file=sys.stderr)
    sys.exit(1)

try:
    from fastapi import FastAPI, HTTPException, Header
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("[HMR Service] ERROR: missing deps. Run 'pip install fastapi uvicorn'.",
          file=sys.stderr)
    sys.exit(1)


HMR_STORAGE_PATH = os.environ.get("HMR_STORAGE_PATH", "./hmr_data")
HMR_HOST = os.environ.get("HMR_HOST", "127.0.0.1")
HMR_PORT = int(os.environ.get("HMR_PORT", "8077"))
HMR_TOKEN = os.environ.get("HMR_TOKEN", "")

# Vision model config (for /ingest_image)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
HMR_VISION_MODEL = os.environ.get("HMR_VISION_MODEL", "qwen2.5vl:7b")
VISION_PROMPT = os.environ.get(
    "HMR_VISION_PROMPT",
    "describe this image in detail in Chinese.if it is a chart, diagram or UI screenshot, "
    "explain key elements, structure and text.be specific, for later search."
)

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
    print(f"[HMR Service] Init HMR, storage path: {HMR_STORAGE_PATH}")
    hmr = HMR(storage_path=HMR_STORAGE_PATH)

    current = hmr.get_system_status().get("embedding_provider", "unknown")
    last = _read_last_provider()

    if last and last != current:
        provider_mismatch = {"from": last, "to": current}
        print("=" * 64, file=sys.stderr)
        print(f"[HMR Service] [!]  Embedding provider changed: {last} -> {current}",
              file=sys.stderr)
        print("    old vector index does not match current provider, semantic search may fail.", file=sys.stderr)
        print("    fix: curl -X POST http://127.0.0.1:8077/reindex", file=sys.stderr)
        print("=" * 64, file=sys.stderr)
    else:
        provider_mismatch = None

    _write_provider(current)
    print(f"[HMR Service] HMR v{hmr.VERSION} ready (Embedding: {current})")
    yield
    print("[HMR Service] close")


app = FastAPI(title="HMR Memory Service", lifespan=lifespan)


def check_token(x_hmr_token: Optional[str]):
    if HMR_TOKEN and x_hmr_token != HMR_TOKEN:
        raise HTTPException(status_code=401, detail="invalid HMR token")


class IngestRequest(BaseModel):
    content: str
    memory_type: str = "concept"
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    confidence: Optional[float] = None
    use_policy: bool = False

class RecallRequest(BaseModel):
    query: str
    top_k: int = 5
    strategy: Optional[str] = None
    use_policy: bool = True

class SaveStateRequest(BaseModel):
    goal: Optional[str] = None
    plan: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None

class ThinkRequest(BaseModel):
    goal: str
    thoughts: Optional[List[Dict[str, Any]]] = None  # [{content, type, confidence}]
    actual_outcome: Optional[str] = None
    rating: Optional[float] = None

class FeedbackRequest(BaseModel):
    event_type: str   # recall_hit / recall_miss / task_success / task_failure
    memory_ids: List[str]
    signal: float     # -1.0 ~ 1.0
    query: Optional[str] = None
    strategy: Optional[str] = None


class IngestImageRequest(BaseModel):
    # (one of): image_path (local path accessible by server)or image_base64 (raw image content)
    image_path: Optional[str] = None
    image_base64: Optional[str] = None
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    prompt: Optional[str] = None      # custom prompt, default if omitted
    model: Optional[str] = None       # custom vision model, default: HMR_VISION_MODEL
    memory_type: str = "concept"


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
            f"Embedding provider from {provider_mismatch['from']} to "
            f"{provider_mismatch['to']}, vector index needs rebuild.please POST /reindex fix."
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
        "message": f"using {current} rebuild {len(memories)} memory vectors reindexed",
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
                     title=req.title, metadata=metadata or None,
                     use_policy=req.use_policy)
    return {"id": mem.id, "type": mem.type, "title": mem.title,
            "summary": mem.semantic_summary}


@app.post("/recall")
def recall(req: RecallRequest, x_hmr_token: Optional[str] = Header(None)):
    check_token(x_hmr_token)
    if provider_mismatch:
        raise HTTPException(
            status_code=409,
            detail=(f"vector index does not match current embedding provider"
                    f" (index built with {provider_mismatch['from']}, current "
                    f"{provider_mismatch['to']}).please POST /reindex to rebuild."),
        )
    result = hmr.recall(query=req.query, top_k=req.top_k, strategy=req.strategy,
                        use_policy=req.use_policy)
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
    print(f"[HMR Service] listening on http://{HMR_HOST}:{HMR_PORT}")
    if HMR_TOKEN:
        print("[HMR Service] enabled token auth")
    uvicorn.run(app, host=HMR_HOST, port=HMR_PORT)


# =============================================================================
# v2.0 new endpoints
# =============================================================================

@app.post("/think")
def think(req: ThinkRequest, x_hmr_token: Optional[str] = Header(None)):
    """
    run a thought chain and reflect.
    pass goal + thoughts; auto-create chain, append thoughts, reflect.
    """
    check_token(x_hmr_token)
    from hmr.engines.thought_chain import ThoughtType

    chain = hmr.start_thinking(req.goal)

    for t in (req.thoughts or []):
        tt_str = t.get("type", "observation").lower()
        tt_map = {
            "observation": ThoughtType.OBSERVATION,
            "hypothesis":  ThoughtType.HYPOTHESIS,
            "decision":    ThoughtType.DECISION,
            "action":      ThoughtType.ACTION,
            "insight":     ThoughtType.INSIGHT,
        }
        tt = tt_map.get(tt_str, ThoughtType.OBSERVATION)
        hmr.think(chain.chain_id, t.get("content", ""), tt,
                  confidence=t.get("confidence", 0.7))

    result = None
    if req.actual_outcome:
        result = hmr.reflect_on(chain.chain_id, req.actual_outcome, req.rating)

    return {
        "chain_id": chain.chain_id,
        "goal": chain.goal,
        "thought_count": len(chain.thoughts),
        "reflected": result is not None,
        "insights": result.insights if result else [],
        "suggested_memory": result.suggested_memory if result else None,
    }


@app.get("/best_decision")
def best_decision(goal: str, x_hmr_token: Optional[str] = Header(None)):
    """query best decision from past successful chains for a similar goal"""
    check_token(x_hmr_token)
    decision = hmr.best_decision_for(goal)
    return {"goal": goal, "best_decision": decision}


@app.post("/feedback")
def feedback(req: FeedbackRequest, x_hmr_token: Optional[str] = Header(None)):
    """send feedback to the policy engine to drive learning"""
    check_token(x_hmr_token)
    hmr.feedback(
        event_type=req.event_type,
        memory_ids=req.memory_ids,
        signal=req.signal,
        query=req.query,
        strategy=req.strategy,
    )
    return {"recorded": True, "event_type": req.event_type, "signal": req.signal}


@app.post("/evolve")
def evolve(dry_run: bool = False, x_hmr_token: Optional[str] = Header(None)):
    """
    run a self-evolution cycle.
    dry_run=true analyze only, no changes (preview mode).
    """
    check_token(x_hmr_token)
    report = hmr.evolve(dry_run=dry_run)
    return report


# =============================================================================
# Image ingestion (/ingest_image): local Ollama vision model captions -> store in HMR
# =============================================================================

def _describe_image_with_ollama(img_b64: str, model: str, prompt: str) -> str:
    """Call local Ollama vision model, return a text description of the image"""
    import urllib.request
    import json as _json

    payload = _json.dumps({
        "model": model,
        "prompt": prompt,
        "images": [img_b64],
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # vision inference is slow, use a generous timeout
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = _json.loads(resp.read())
    return data.get("response", "").strip()


@app.post("/ingest_image")
def ingest_image(req: IngestImageRequest, x_hmr_token: Optional[str] = Header(None)):
    """
    Image ingestion: caption an image with the local vision model, then store in HMR.
    The image itself is NOT stored in HMR; only the description (plus origin path if image_path given).

    Provide either image_path (local path accessible by the server) or image_base64.

    Example:
        curl -X POST http://127.0.0.1:8077/ingest_image \
             -H "Content-Type: application/json" \
             -d '{"image_path": "I:/imgs/arch.png", "title": "diagram"}'
    """
    check_token(x_hmr_token)

    import base64

    # 1. get image base64
    origin_path = None
    if req.image_base64:
        img_b64 = req.image_base64
    elif req.image_path:
        p = Path(req.image_path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Image not found: {req.image_path}")
        if not p.is_file():
            raise HTTPException(status_code=400, detail=f"Not a file: {req.image_path}")
        try:
            with open(p, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read image: {e}")
        origin_path = str(p.resolve())
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either image_path or image_base64"
        )

    # 2. vision model generates description
    model = req.model or HMR_VISION_MODEL
    prompt = req.prompt or VISION_PROMPT
    try:
        desc = _describe_image_with_ollama(img_b64, model, prompt)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=(f"Vision model call failed ({e}). Check Ollama is running "
                    f"and model {model} is pulled (ollama pull {model}).")
        )

    if not desc:
        raise HTTPException(status_code=502, detail="Vision model returned empty description")

    # 3. store in HMR (append origin path to the description for later lookup)
    content = desc
    if origin_path:
        content = f"{desc}\n\n[origin] {origin_path}"

    title = req.title or (Path(req.image_path).stem if req.image_path else "image description")
    tags = (req.tags or []) + ["image", "vision_description"]

    mem = hmr.ingest(
        content=content,
        memory_type=req.memory_type,
        title=title,
        metadata={"tags": tags},
    )

    return {
        "id": mem.id,
        "title": mem.title,
        "description": desc,
        "origin_path": origin_path,
        "model": model,
    }
