"""阶段二回归：来源身份、作用域绑定、脱敏与幂等去重。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hmr.core.hmr import HMR
from hmr.security.redaction import redact_content, redact_sensitive_text


class TestS2Trust(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.hmr = HMR(storage_path=str(Path(cls._tmp.name) / "hmr_data"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_redaction_categories_and_overlap(self):
        text = (
            "api_key: sk-abcdefghijklmnopqrstuvwxyz0123 "
            "Authorization: Bearer abcdefghijklmnopqrst "
            "password=hunter2secret keep=visible"
        )
        out = redact_sensitive_text(text)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz0123", out)
        self.assertNotIn("abcdefghijklmnopqrst", out)
        self.assertNotIn("hunter2secret", out)
        self.assertIn("keep=visible", out)

    def test_redaction_is_idempotent(self):
        once = redact_sensitive_text("token: abcdefghijklmnopqrstuvwxyz")
        twice = redact_sensitive_text(once)
        self.assertEqual(once, twice)

    def test_redaction_before_truncation(self):
        text = "x" * 90 + " sk-abcdefghijklmnopqrstuvwxyz0123 tail"
        out = redact_content(text, max_chars=100)
        self.assertNotIn("sk-abcde", out)
        self.assertIn("[truncated]", out)

    def test_source_identity_is_persisted(self):
        m = self.hmr.ingest(
            "来源身份测试",
            title="source-case",
            metadata={
                "source_client": "codebuddy",
                "source_session_id": "sess-1",
                "source_turn_id": "turn-1",
                "source_workspace": self.hmr.workspace_id,
            },
        )
        self.assertEqual(m.metadata["source_client"], "codebuddy")
        self.assertEqual(m.metadata["source_turn_id"], "turn-1")
        self.assertTrue(m.metadata["source_timestamp"])
        self.assertEqual(len(m.metadata["source_hash"]), 16)
        restored = self.hmr.memory_fs.read_memory(m.id)
        self.assertEqual(restored.metadata["source_turn_id"], "turn-1")

    def test_scope_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            self.hmr.ingest(
                "越界写入",
                metadata={"source_workspace": "another-workspace"},
            )

    def test_ingest_redacts_sensitive_content(self):
        m = self.hmr.ingest(
            "密钥 api_key: sk-abcdefghijklmnopqrstuvwxyz0123 不应落盘",
            title="redact-case",
        )
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz0123", m.content)
        self.assertIn("[REDACTED_API_KEY]", m.content)

    def test_idempotency_same_turn_returns_same_memory(self):
        meta = {"source_turn_id": "turn-idem-1", "source_client": "codebuddy"}
        first = self.hmr.ingest("幂等去重测试", title="idem", metadata=meta)
        second = self.hmr.ingest("幂等去重测试", title="idem", metadata=meta)
        self.assertEqual(first.id, second.id)

    def test_same_content_different_turn_is_not_duplicate(self):
        a = self.hmr.ingest("同一事实", metadata={"source_turn_id": "turn-a"})
        b = self.hmr.ingest("同一事实", metadata={"source_turn_id": "turn-b"})
        self.assertNotEqual(a.id, b.id)

    def test_write_failure_releases_idempotency_slot(self):
        meta = {"source_turn_id": "turn-retry-1"}
        with patch.object(self.hmr.semantic_engine, "store", side_effect=RuntimeError("down")):
            with self.assertRaises(RuntimeError):
                self.hmr.ingest("失败重试测试", metadata=meta)
        ok = self.hmr.ingest("失败重试测试", metadata=meta)
        self.assertTrue(ok.id)

    def test_trace_uses_same_redaction(self):
        self.hmr.trace.emit(
            "memory_ingest",
            request={"prompt": "api_key: sk-abcdefghijklmnopqrstuvwxyz0123"},
        )
        events = self.hmr.trace.read_events(limit=5)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz0123", str(events))


if __name__ == "__main__":
    unittest.main()
