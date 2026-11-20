"""
test_service.py — 测试 HMR v2.0 服务是否正常（不需要 OpenClaw）
用法：先启动 server.py，再另开窗口运行 python test_service.py
"""
import urllib.request
import json

BASE = "http://127.0.0.1:8077"

def call(path, method="GET", data=None, params=None):
    url = BASE + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

print("=" * 55)
print(" HMR v2.0 服务连接测试")
print("=" * 55)

print("\n[1] 健康检查...")
h = call("/health")
print(f"    版本 {h['version']}  状态 {h['status']}")

print("\n[2] 存入记忆（普通模式）...")
r = call("/ingest", "POST", {"content": "用户喜欢用 Python 和简洁代码",
                              "memory_type": "concept", "title": "用户偏好"})
print(f"    已存《{r['title']}》")

print("\n[3] 存入记忆（Policy 模式）...")
r = call("/ingest", "POST", {"content": "IPC 队列积压导致调度器超时",
                              "title": "IPC超时问题", "use_policy": True})
print(f"    Policy 存储：类型={r['type']}  id={r['id'][:8]}...")

print("\n[4] 召回记忆...")
r = call("/recall", "POST", {"query": "用户喜欢什么", "top_k": 3})
print(f"    召回 {len(r['memories'])} 条")
for m in r["memories"]:
    print(f"      《{m['title']}》score={m['score']:.2f}")

print("\n[5] ThoughtChain（推理链+反思）...")
r = call("/think", "POST", {
    "goal": "排查 IPC 超时根因",
    "thoughts": [
        {"content": "队列深度持续 > 800", "type": "observation", "confidence": 0.9},
        {"content": "消费者线程可能不足", "type": "hypothesis", "confidence": 0.7},
        {"content": "扩容消费者线程 x3", "type": "decision", "confidence": 0.85},
    ],
    "actual_outcome": "延迟从 800ms 降至 50ms",
    "rating": 0.9
})
print(f"    链ID={r['chain_id'][:8]}...  洞察={len(r['insights'])} 条  已反思={r['reflected']}")

print("\n[6] 查询历史最优决策...")
r = call("/best_decision", params={"goal": "IPC 积压问题"})
print(f"    {r['best_decision'] or '（暂无历史）'}")

print("\n[7] Policy 反馈...")
r = call("/feedback", "POST", {
    "event_type": "task_success",
    "memory_ids": [],
    "signal": 0.8,
    "query": "IPC 超时"
})
print(f"    已记录: {r['event_type']}  signal={r['signal']}")

print("\n[8] 自我演化（预览）...")
r = call("/evolve", "POST", params={"dry_run": "true"})
print(f"    {r.get('summary', r.get('message', 'OK'))}")

print("\n[9] 保存状态...")
r = call("/save_state", "POST", {"goal": "测试v2.0对接", "plan": ["启动", "测试", "验证"]})
print(f"    已保存: {r['goal']}")

print("\n[10] 重建向量索引...")
r = call("/reindex", "POST")
print(f"    重建 {r['memory_count']} 条，provider={r['embedding_provider']}")

print("\n" + "=" * 55)
print(" ✅ HMR v2.0 服务工作正常，可接入 OpenClaw")
print("=" * 55)
