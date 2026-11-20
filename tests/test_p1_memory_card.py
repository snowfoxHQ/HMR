"""P1 回归：CODE_AGENT_MEMORY 卡片解析、验证门槛与入库。"""

import tempfile
import unittest
from pathlib import Path

from hmr.core.hmr import HMR
from hmr.engines.memory_card import MemoryCard, MemoryCardEngine


VALID_CARD = """CODE_AGENT_MEMORY
repo: hestia-os/hmr
scope: hmr/core/hmr.py::ingest
status: verified
signal: focused test passed
problem: ingest 丢弃未知 metadata
technical_context: MemoryObject 字段需向后兼容
surfaces: ingest -> semantic_engine.store
failed_shape: 只透传四个白名单字段
validation: python -m unittest tests/test_p1_memory_card.py
principle: 结构化字段需要落盘而非临时对象
anchors: hmr/core/models.py, hmr/core/hmr.py"""

UNVERIFIED_CARD = """CODE_AGENT_MEMORY
repo: hestia-os/hmr
status: verified
signal: unknown
problem: 未经实测的修复
principle: 应验证后再存"""


class TestP1MemoryCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.hmr = HMR(storage_path=str(Path(cls._tmp.name) / "hmr_data"))
        cls.engine = cls.hmr.memory_card

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_engine_is_standalone(self):
        self.assertIsInstance(MemoryCardEngine(), MemoryCardEngine)

    def test_parse_roundtrip(self):
        card = self.engine.parse(VALID_CARD)
        self.assertIsNotNone(card)
        self.assertEqual(card.status, "verified")
        self.assertEqual(card.repo, "hestia-os/hmr")
        self.assertIn("CODE_AGENT_MEMORY", self.engine.render(card))
        self.assertTrue(self.engine.validate(card).ok)

    def test_verified_requires_validation_and_signal(self):
        card = self.engine.parse(UNVERIFIED_CARD)
        result = self.engine.validate(card)
        self.assertFalse(result.ok)
        self.assertTrue(any("validation" in e for e in result.errors))
        self.assertTrue(any("signal" in e for e in result.errors))

    def test_failed_attempt_requires_failed_shape(self):
        card = MemoryCard(
            status="failed_attempt", problem="修复失败", failed_shape="",
            validation="n/a",
        )
        result = self.engine.validate(card)
        self.assertFalse(result.ok)
        self.assertTrue(any("failed_shape" in e for e in result.errors))

    def test_ingest_card_stores_structure(self):
        m = self.hmr.ingest_card(VALID_CARD)
        self.assertEqual(m.boundary, "coding")
        self.assertEqual(m.metadata["status"], "verified")
        self.assertEqual(m.metadata["card"]["repo"], "hestia-os/hmr")
        self.assertTrue(m.evidence)
        self.assertEqual(m.metadata["source"], "code_agent_card")
        restored = self.hmr.memory_fs.read_memory(m.id)
        self.assertEqual(restored.metadata["card"]["signal"], "focused test passed")

    def test_strict_rejects_unverified(self):
        with self.assertRaises(ValueError):
            self.hmr.ingest_card(UNVERIFIED_CARD)

    def test_lenient_downgrades_to_candidate(self):
        m = self.hmr.ingest_card(UNVERIFIED_CARD, strict=False)
        self.assertEqual(m.metadata["status"], "candidate")

    def test_ingest_auto_detects_card(self):
        m = self.hmr.ingest(VALID_CARD, title="auto-detected")
        self.assertEqual(m.metadata["source"], "code_agent_card")
        self.assertEqual(m.title, "auto-detected")


if __name__ == "__main__":
    unittest.main()
