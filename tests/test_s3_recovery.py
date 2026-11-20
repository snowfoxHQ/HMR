"""阶段三回归：Pending 状态、重试、重启恢复与洞察补偿。"""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from hmr.core.hmr import HMR
from hmr.engines.thought_chain import ThoughtType
from hmr.storage.pending import is_retryable_error


class TestS3Recovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls._tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.case_path = self.base / self._testMethodName
        self.hmr = HMR(storage_path=str(self.case_path))

    def test_successful_ingest_clears_pending(self):
        self.hmr.ingest("正常写入", title="ok-case")
        active = [p for p in self.hmr.pending.all() if p.status != "persisted"]
        self.assertEqual(active, [])

    def test_failure_keeps_pending_with_backoff(self):
        with patch.object(self.hmr.semantic_engine, "store", side_effect=OSError("503 down")):
            with self.assertRaises(OSError):
                self.hmr.ingest("失败保留", title="fail-case")
        items = [p for p in self.hmr.pending.all() if p.status == "failed"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].attempts, 1)
        self.assertGreater(items[0].next_retry_at, time.time())
        self.assertIn("503", items[0].last_error)

    def test_non_retryable_error_is_pushed_far(self):
        with patch.object(self.hmr.semantic_engine, "store", side_effect=ValueError("bad arg")):
            with self.assertRaises(ValueError):
                self.hmr.ingest("不可重试", title="bad-case")
        items = [p for p in self.hmr.pending.all() if p.status == "failed"]
        self.assertGreater(items[0].next_retry_at, time.time() + 3600)

    def test_error_classification(self):
        self.assertTrue(is_retryable_error(OSError("connection reset")))
        self.assertTrue(is_retryable_error(RuntimeError("HTTP 503")))
        self.assertFalse(is_retryable_error(ValueError("invalid")))

    def test_retry_pending_replays_and_clears(self):
        with patch.object(self.hmr.semantic_engine, "store", side_effect=OSError("temporary")):
            with self.assertRaises(OSError):
                self.hmr.ingest("待重放内容", title="retry-case")

        stats = self.hmr.retry_pending(force=True)
        self.assertEqual(stats["succeeded"], 1)
        self.assertEqual(stats["failed"], 0)
        results = self.hmr.recall("待重放内容")
        self.assertTrue(any("待重放" in m.content for m in results.memory_objects))
        self.assertEqual(
            [p for p in self.hmr.pending.all() if p.status != "persisted"], []
        )

    def test_restart_recovers_pending(self):
        self.hmr.queue_pending(
            content="重启恢复内容", memory_type="concept", title="recover-case"
        )
        restarted = HMR(storage_path=str(self.case_path))
        results = restarted.recall("重启恢复内容")
        self.assertTrue(any("重启恢复内容" in m.content for m in results.memory_objects))

    def test_thought_chain_failure_queues_pending(self):
        with patch.object(
            self.hmr.thought_chain, "_ingest_fn", side_effect=RuntimeError("write down")
        ):
            chain = self.hmr.start_thinking("排查超时")
            self.hmr.think(chain.chain_id, "队列积压", ThoughtType.OBSERVATION)
            self.hmr.think(chain.chain_id, "扩容消费者", ThoughtType.DECISION)
            self.hmr.reflect_on(chain.chain_id, "延迟降低", rating=0.9)

        pending = [
            p for p in self.hmr.pending.all()
            if "thought_chain" in str(p.metadata.get("tags", ""))
        ]
        self.assertGreaterEqual(len(pending), 1)


if __name__ == "__main__":
    unittest.main()
