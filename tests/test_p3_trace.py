"""P3 回归：本地 trace、脱敏、去重与失败隔离。"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from hmr.core.hmr import HMR
from hmr.observability import TraceStore, sanitize_trace_value


class TestP3Trace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "traces"
        self.store = TraceStore(str(self.base))

    def tearDown(self):
        self._tmp.cleanup()

    def test_sanitize_modes(self):
        self.assertEqual(sanitize_trace_value("secret", False), "[redacted]")
        value = sanitize_trace_value(
            {"api_key": "sk-abc", "query": "hello", "nested": {"token": "t"}}, True
        )
        self.assertEqual(value["api_key"], "[redacted]")
        self.assertEqual(value["nested"]["token"], "[redacted]")
        self.assertEqual(value["query"], "hello")
        long_text = sanitize_trace_value("x" * 100, True, max_chars=20)
        self.assertIn("[truncated]", long_text)

    def test_emit_read_and_event_id_dedupe(self):
        first = self.store.emit(
            "memory_ingest", event_id="evt_fixed",
            request={"title": "测试"}, response={"id": "mem_1"},
        )
        second = self.store.emit("memory_ingest", event_id="evt_fixed")
        self.assertEqual(first, "evt_fixed")
        self.assertIsNone(second)
        events = self.store.read_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_id"], "evt_fixed")
        self.assertEqual(events[0]["schema_version"], "hmr_trace.v1")
        self.assertEqual(events[0]["request"]["title"], "测试")

    def test_retention_prunes_old_files(self):
        old = self.base / "events-2020-01-01.jsonl"
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text("{}\n", encoding="utf-8")
        old_time = time.time() - 30 * 24 * 3600
        os.utime(old, (old_time, old_time))

        self.store.emit("memory_ingest")
        self.assertFalse(old.exists())

    def test_disabled_store_is_noop(self):
        path = self.base / "disabled"
        store = TraceStore(str(path), enabled=False)
        self.assertIsNone(store.emit("memory_ingest"))
        self.assertEqual(store.read_events(), [])
        self.assertFalse(path.exists())

    def test_hmr_emits_trace_without_breaking_recall(self):
        hmr = HMR(storage_path=str(Path(self._tmp.name) / "hmr_data"))
        m = hmr.ingest("trace 测试记忆", title="trace-case")
        result = hmr.recall("trace 测试")
        events = hmr.trace.read_events()
        operations = {e["operation"] for e in events}
        self.assertIn("memory_ingest", operations)
        self.assertIn("memory_retrieve", operations)
        self.assertTrue(result.memory_objects)
        self.assertEqual(hmr.get_system_status()["trace"]["enabled"], True)
        self.assertGreater(hmr.get_system_status()["trace"]["events"], 0)

    def test_bad_trace_config_does_not_break_hmr(self):
        hmr = HMR(
            storage_path=str(Path(self._tmp.name) / "hmr_data2"),
            trace_config={"unexpected_key": 1},
        )
        self.assertIsNotNone(hmr.memory_fs)
        self.assertFalse(hmr.trace.enabled)


if __name__ == "__main__":
    unittest.main()
