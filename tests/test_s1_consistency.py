"""阶段一回归：文件、索引与向量三处存储一致性。"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hmr.core.hmr import HMR
from hmr.core.models import MemoryObject


class TestS1Consistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.hmr = HMR(storage_path=str(Path(cls._tmp.name) / "hmr_data"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _index(self):
        path = Path(self.hmr.storage_path) / "index" / "memory_index.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def test_vector_failure_rolls_back_file(self):
        m = MemoryObject(type="concept", title="回滚", content="内容", semantic_summary="内容")
        with patch.object(self.hmr.vector_store, "add", side_effect=RuntimeError("vector down")):
            with self.assertRaises(RuntimeError):
                self.hmr.semantic_engine.store(m)
        self.assertIsNone(self.hmr.memory_fs.read_memory(m.id))
        self.assertNotIn(m.id, self._index())

    def test_orphan_vector_is_skipped_and_cleaned(self):
        m = self.hmr.ingest("孤儿向量测试", title="orphan-source")
        self.hmr.memory_fs.delete_memory(m.id)
        self.assertIn(m.id, self.hmr.vector_store.vectors)

        self.hmr.semantic_engine.memory_cache.clear()
        results = self.hmr.semantic_engine.retrieve("孤儿向量测试", top_k=10)
        self.assertNotIn(m.id, [item.id for item in results])
        self.assertNotIn(m.id, self.hmr.vector_store.vectors)

    def test_delete_memory_syncs_all_three_stores(self):
        m = self.hmr.ingest("三处同步删除", title="delete-source")
        self.assertIn(m.id, self._index())
        self.assertIn(m.id, self.hmr.vector_store.vectors)

        self.assertTrue(self.hmr.delete_memory(m.id))
        self.assertIsNone(self.hmr.memory_fs.read_memory(m.id))
        self.assertNotIn(m.id, self._index())
        self.assertNotIn(m.id, self.hmr.vector_store.vectors)
        self.assertNotIn(m.id, self.hmr.semantic_engine.memory_cache)

    def test_delete_missing_memory_returns_false(self):
        self.assertFalse(self.hmr.delete_memory("mem_does_not_exist"))

    def test_lifecycle_prune_uses_unified_delete(self):
        config = self.hmr.lifecycle.config
        old_age, old_r = config.prune_min_age_days, config.prune_retrievability
        try:
            config.prune_min_age_days = 0
            config.prune_retrievability = 2.0
            m = self.hmr.ingest("剪枝同步测试", title="prune-source")
            report = self.hmr.lifecycle.check_now("concept")
            self.assertGreaterEqual(report.pruned_count, 1)
            self.assertNotIn(m.id, self.hmr.vector_store.vectors)
            self.assertNotIn(m.id, self._index())
        finally:
            config.prune_min_age_days = old_age
            config.prune_retrievability = old_r

    def test_startup_reconciliation_removes_orphans(self):
        m = self.hmr.ingest("启动对账", title="reconcile-source")
        self.hmr.memory_fs.delete_memory(m.id)
        self.assertIn(m.id, self.hmr.vector_store.vectors)

        self.hmr._sync_vector_store()
        self.assertNotIn(m.id, self.hmr.vector_store.vectors)


if __name__ == "__main__":
    unittest.main()
