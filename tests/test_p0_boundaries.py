"""P0 回归：记忆边界、metadata 保留与旧数据兼容。"""

import json
import tempfile
import unittest
from pathlib import Path

from hmr.core.hmr import HMR
from hmr.core.models import MemoryObject


class TestP0Boundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.hmr = HMR(storage_path=str(Path(cls._tmp.name) / "hmr_data"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_boundary_routing(self):
        cases = [
            ("请始终用中文回答，语气简洁", "user"),
            ("每次先检查测试再提交，按顺序执行验证", "procedure"),
            ("本仓库的入口文件是 server.py，模块划分见架构文档", "repo"),
            ("修复了 IPC 超时：根因是消费者不足，测试通过", "coding"),
        ]
        for content, expected in cases:
            with self.subTest(expected=expected):
                d = self.hmr.policy.decide_boundary(content)
                self.assertEqual(d["boundary"], expected)

    def test_metadata_fully_preserved(self):
        m = self.hmr.ingest(
            "测试 metadata 保留",
            title="metadata-case",
            memory_type="concept",
            metadata={
                "custom_key": "kept",
                "source": "codebuddy",
                "evidence": ["pytest passed", "CI green"],
                "status": "verified",
            },
            boundary="coding",
        )
        self.assertEqual(m.metadata["custom_key"], "kept")
        self.assertEqual(m.boundary, "coding")
        self.assertEqual(m.scope, "project")
        self.assertEqual(m.status, "verified")
        self.assertEqual(m.evidence, ["pytest passed", "CI green"])
        self.assertIn("lang", m.metadata)
        restored = self.hmr.memory_fs.read_memory(m.id)
        self.assertEqual(restored.metadata["custom_key"], "kept")
        self.assertEqual(restored.evidence, ["pytest passed", "CI green"])
        self.assertIn("lang", restored.metadata)

    def test_explicit_boundary_overrides_inference(self):
        m = self.hmr.ingest(
            "我喜欢简洁回复",
            title="override",
            metadata={"boundary": "user", "scope": "user"},
        )
        self.assertEqual(m.boundary, "user")
        self.assertEqual(m.scope, "user")

    def test_legacy_record_loads_without_migration(self):
        legacy = {
            "id": "mem_legacy01",
            "type": "concept",
            "title": "旧记忆",
            "content": "旧格式无边界字段",
            "semantic_summary": "旧格式无边界字段",
            "linked_memories": [],
            "runtime_dependencies": [],
            "tags": [],
            "confidence": 1.0,
            "temporal_weight": 1.0,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "last_accessed": None,
            "access_count": 0,
            "embedding": None,
        }
        obj = MemoryObject(**legacy)
        self.assertEqual(obj.boundary, "coding")
        self.assertEqual(obj.scope, "project")
        self.assertEqual(obj.metadata, {})

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "legacy.json"
            p.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")

    def test_filter_by_boundary(self):
        items = [
            MemoryObject(type="concept", title="a", content="a", semantic_summary="a", boundary="user"),
            MemoryObject(type="concept", title="b", content="b", semantic_summary="b", boundary="coding"),
        ]
        out = self.hmr._filter_by_boundary(items, ["user"])
        self.assertEqual([m.title for m in out], ["a"])
        self.assertEqual(len(self.hmr._filter_by_boundary(items, None)), 2)


if __name__ == "__main__":
    unittest.main()
