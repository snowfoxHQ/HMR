from hmr.core.hmr import HMR

hmr = HMR(storage_path="./test_data")
print("版本:", hmr.VERSION)   # 应输出 1.5.0

status = hmr.get_system_status()
print("Embedding 方案:", status["embedding_provider"])  # openai / sentence_transformers / tfidf
print("数据同步:", status["synced"])                     # True