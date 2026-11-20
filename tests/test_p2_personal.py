"""P2 回归：用户画像、流程记忆与注入节奏。"""

import tempfile
import unittest
from pathlib import Path

from hmr.core.hmr import HMR
from hmr.personal import (
    PersonalMemoryContext,
    ProfileStorageError,
    ProcedureStore,
    UserProfileStore,
    is_reminder_due,
)


class TestP2Personal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.profile = UserProfileStore(str(self.home))
        self.procedure = ProcedureStore(str(self.home))

    def tearDown(self):
        self._tmp.cleanup()

    def test_profile_add_duplicate_update_delete(self):
        status, pid = self.profile.add(
            "communication", "用中文回答，语气简洁", applies_when="所有任务"
        )
        self.assertEqual(status, "added")
        self.assertEqual(len(self.profile.read()), 1)

        status2, pid2 = self.profile.add(
            "communication", "用中文回答，语气简洁", applies_when="所有任务"
        )
        self.assertEqual((status2, pid2), ("duplicate", pid))

        self.assertEqual(self.profile.update(pid, description="用中文回答，先结论后细节"), "updated")
        self.assertEqual(self.profile.read()[0].description, "用中文回答，先结论后细节")

        self.assertEqual(self.profile.delete(pid), "deleted")
        self.assertEqual(self.profile.read(), [])

    def test_profile_strict_schema_rejects_corruption(self):
        self.profile.add("workflow", "先跑测试再提交")
        text = self.profile.path.read_text(encoding="utf-8")
        self.profile.path.write_text(
            text.replace("active_count: 1", "active_count: 99"), encoding="utf-8"
        )
        with self.assertRaises(ProfileStorageError):
            self.profile.read()

    def test_profile_atomic_write_path(self):
        self.profile.add("environment", "使用 Python 3.11")
        self.assertTrue(self.profile.path.exists())
        self.assertEqual(list(self.profile.path.parent.glob("*.tmp")), [])

    def test_procedure_topic_roundtrip(self):
        path = self.procedure.write_topic(
            "release-check",
            "发布前检查",
            "准备提交代码时",
            ["运行单元测试", "检查 CHANGELOG 倒序", "确认未提交密钥"],
            ["紧急热修可跳过第二项"],
        )
        self.assertTrue(path.exists())
        self.assertEqual(self.procedure.list_topics(), ["release-check"])
        text = self.procedure.read_topic("release-check")
        self.assertIn("## Procedure", text)
        self.assertIn("## Exceptions", text)
        self.assertIn("运行单元测试", text)
        self.assertIn("Use when: 准备提交代码时", text)

    def test_procedure_context_budget(self):
        self.procedure.write_topic("a-topic", "A", "when", ["step"])
        context = self.procedure.build_context(max_chars=50)
        self.assertLessEqual(len(context), 95)
        self.assertIn("[truncated]", context)
        # 预算过小时不产出无意义碎片
        self.assertEqual(self.procedure.build_context(max_chars=30), "")

    def test_cadence_rule(self):
        self.assertTrue(is_reminder_due(1))
        self.assertFalse(is_reminder_due(2))
        self.assertFalse(is_reminder_due(5))
        self.assertTrue(is_reminder_due(6))
        self.assertTrue(is_reminder_due(11))
        self.assertFalse(is_reminder_due(7))

    def test_context_injects_profile_first_then_procedure(self):
        self.profile.add("communication", "回答使用简体中文")
        self.procedure.write_topic("commit-rule", "提交规则", "完成阶段后", ["立即提交"])
        ctx = PersonalMemoryContext(str(self.home)).build(turn=1)
        self.assertIn("[User Profile]", ctx)
        self.assertIn("[Procedure Memory]", ctx)

        ctx_turn2 = PersonalMemoryContext(str(self.home)).build(turn=2)
        self.assertIn("[User Profile]", ctx_turn2)
        self.assertNotIn("[Procedure Memory]", ctx_turn2)

    def test_hmr_integration(self):
        hmr = HMR(
            storage_path=str(self.home / "hmr_data"),
            personal_home=str(self.home / "personal"),
        )
        hmr.personal.profile.add("communication", "先说结论")
        text = hmr.personal_context(turn=1)
        self.assertIn("先说结论", text)


if __name__ == "__main__":
    unittest.main()
