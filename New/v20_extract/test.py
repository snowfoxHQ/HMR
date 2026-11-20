from hmr.core.hmr import HMR

hmr = HMR(storage_path="./test_data")
print("版本:", hmr.VERSION)

hmr.ingest("IPC 应使用异步消息队列", memory_type="concept", title="IPC 原则")
hmr.save_runtime_state(goal="设计调度器", plan=["研究", "设计", "实现"])

result = hmr.recall(query="调度器 IPC")
print("召回", len(result.memory_objects), "条")

status = hmr.get_system_status()
print("Embedding 方案:", status["embedding_provider"])
print("数据同步:", status["synced"])
