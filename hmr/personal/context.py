"""
个人记忆上下文构建与注入节奏。

借鉴 MemoraX Code：User Profile 首轮注入，Procedure 第 1/6/11 轮后每 5 轮提醒一次。
不依赖任何 IDE hook；由调用方在每轮开始时调用 build(turn=...)。
"""

from .profile import ProfileStorageError, UserProfileStore
from .procedure import ProcedureStore

DEFAULT_REMINDER_INTERVAL = 5


def is_reminder_due(turn: int, interval: int = DEFAULT_REMINDER_INTERVAL) -> bool:
    """turn=1,6,11,... 时返回 True（第 1 轮 + 之后每 interval 轮）。"""
    if turn < 1 or interval < 1:
        return False
    if turn == 1:
        return True
    return (turn - 1) % interval == 0


class PersonalMemoryContext:
    """把 User Profile 与 Procedure Memory 渲染为可注入的上下文文本。"""

    def __init__(self, home: str):
        self.home = home
        self.profile = UserProfileStore(home)
        self.procedure = ProcedureStore(home)

    def build(
        self,
        turn: int = 1,
        *,
        include_profile: bool = True,
        interval: int = DEFAULT_REMINDER_INTERVAL,
        profile_chars: int = 2000,
        procedure_chars: int = 4000,
    ) -> str:
        parts = []

        if include_profile:
            try:
                preferences = self.profile.read()
            except ProfileStorageError:
                preferences = []
            if preferences:
                lines = ["[User Profile]"]
                for pref in preferences:
                    lines.append(f"- ({pref.type}) {pref.description}")
                    if pref.applies_when not in ("", "-"):
                        lines.append(f"  Applies when: {pref.applies_when}")
                    if pref.do_not_apply_when not in ("", "-"):
                        lines.append(f"  Do not apply when: {pref.do_not_apply_when}")
                text = "\n".join(lines)
                if len(text) > profile_chars:
                    text = text[:profile_chars] + "\n[truncated]"
                parts.append(text)

        if is_reminder_due(turn, interval):
            procedure = self.procedure.build_context(procedure_chars)
            if procedure:
                parts.append("[Procedure Memory]\n" + procedure)

        return "\n\n".join(parts)

    def build_for_memory(self, memory) -> str:
        """按一条 MemoryObject 的边界选择注入内容（预留给 writeback 层）。"""
        boundary = getattr(memory, "boundary", "coding")
        if boundary == "user":
            return self.build(1, include_profile=True)
        if boundary == "procedure":
            return self.build(1, include_profile=False)
        return ""
