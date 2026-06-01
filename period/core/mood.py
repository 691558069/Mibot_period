"""情绪状态模型 —— 仅跟踪活跃工具和交互历史，无数值分数。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MoodState:
    """情绪状态。"""

    active_tools: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    last_interaction: str = ""

    @classmethod
    def from_dict(cls, data: dict | None) -> "MoodState":
        if not data:
            return cls()
        return cls(
            active_tools=list(data.get("active_tools", [])),
            history=list(data.get("history", [])),
            last_interaction=data.get("last_interaction", ""),
        )

    def to_dict(self) -> dict:
        return {
            "active_tools": list(self.active_tools),
            "history": list(self.history),
            "last_interaction": self.last_interaction,
        }

    def is_tool_active(self, name: str) -> bool:
        return any(t.get("name") == name for t in self.active_tools)

    def expire_tools(self, now_iso: str) -> list[dict]:
        expired = []
        remaining = []
        for tool in self.active_tools:
            exp = tool.get("expires_at")
            if exp and isinstance(exp, str) and exp <= now_iso:
                expired.append(tool)
            else:
                remaining.append(tool)
        self.active_tools = remaining
        return expired

    def add_tool(
        self,
        name: str,
        params: dict,
        *,
        expires_at: str | None = None,
        rounds_left: int | None = None,
        initiated: bool = False,
    ) -> None:
        self.remove_tool(name)
        self.active_tools.append({
            "name": name,
            "params": dict(params),
            "expires_at": expires_at,
            "rounds_left": rounds_left,
            "initiated": initiated,
        })

    def remove_tool(self, name: str) -> bool:
        original_len = len(self.active_tools)
        self.active_tools = [t for t in self.active_tools if t.get("name") != name]
        return len(self.active_tools) < original_len

    def add_history(
        self,
        event: str,
        reasoning: str,
        user_message: str,
        max_length: int = 20,
    ) -> None:
        from datetime import datetime, timezone
        self.history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "reasoning": reasoning,
            "user_message": user_message,
        })
        if len(self.history) > max_length:
            self.history = self.history[-max_length:]
