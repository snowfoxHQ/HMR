# Changelog

## v1.5.0
- 新增 JIT Memory Compiler（多步推理检索）
- 新增 Memory Scheduler（调度策略 + 热缓存 LRU）
- 新增 Memory Lifecycle Engine（自动压缩/剪枝，后台异步）
- 新增 Memory Graph（实体/因果/时序图，持久化）

## v1.1.0
- 修复 VectorStore 持久化（重启不再丢失向量）
- 接入真实 Embedding（OpenAI → sentence-transformers → TF-IDF 三层 fallback）
- 实现真正的 SM-2 遗忘曲线（替代伪 Ebbinghaus）
- AgentWorkspace 持久化到磁盘
- 文件原子写入 + 线程锁（并发安全）
- compress_memories() 真实实现
- list_memories type_map 修复

## v1.0.0
- 初始版本
