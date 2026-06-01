"""基于 LLM 的提示词压缩器。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Awaitable


COMPRESSION_SYSTEM_PROMPT = """你是一名提示词优化专家。请将用户提供的系统提示词压缩为精华版。

压缩要求：
1. 保留所有关键约束和行为规则
2. 保留人格设定的核心特征和语气风格
3. 去除冗余修辞、重复表达、过渡语句和装饰性词汇
4. 用极简中文表达，严格控制在目标长度以内
5. 不要改变原意，不要添加原文没有的内容
6. 只输出压缩后的文本，不要任何解释和 markdown 标记"""


class PromptCompressor:
    """使用 LLM 压缩提示词以减少 token 消耗。"""

    def __init__(
        self,
        llm_func: Callable[[str, str, str], Awaitable[dict]],
        config: dict,
        data_dir: Path,
    ) -> None:
        self.llm_func = llm_func
        self.config = config
        self.data_dir = data_dir
        self._cache: dict[str, str] = {}
        self._cache_file = data_dir / "compressed_prompts.json"
        self._load_cache()

    def _load_cache(self) -> None:
        if not self._cache_file.exists():
            return
        try:
            text = self._cache_file.read_text(encoding="utf-8")
            data = json.loads(text) if text.strip() else {}
            if isinstance(data, dict):
                self._cache = data
        except (json.JSONDecodeError, OSError):
            self._cache = {}

    def _save_cache(self) -> None:
        try:
            self._cache_file.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def get(self, key: str, fallback: str = "") -> str:
        return self._cache.get(key, fallback)

    def is_cached(self, key: str) -> bool:
        return key in self._cache and bool(self._cache[key])

    async def compress_all(self) -> dict[str, str]:
        """压缩所有插件管理的提示词。"""
        ratio = self.config.get("prompt_compression_ratio", 30)
        results: dict[str, str] = {}

        anchor = self._build_raw_anchor()
        if anchor:
            compressed = await self._compress_one(anchor, ratio, "锚点提示词")
            if compressed:
                results["anchor"] = compressed

        phases = self.config.get("phases", {})
        for phase in ("menstrual", "follicular", "ovulatory", "luteal"):
            phase_cfg = phases.get(phase, {})
            for key in ("prompt", "time_morning", "time_afternoon", "time_night"):
                text = phase_cfg.get(key, "")
                if text:
                    cache_key = f"{phase}_{key}"
                    compressed = await self._compress_one(text, ratio, f"{phase}.{key}")
                    if compressed:
                        results[cache_key] = compressed

        self._cache.update(results)
        self._save_cache()
        return results

    async def _compress_one(self, text: str, ratio: int, label: str) -> str:
        target_len = max(20, int(len(text) * ratio / 100))
        user_prompt = (
            f"请将以下提示词压缩为精华版，目标长度约 {target_len} 字"
            f"（当前 {len(text)} 字的 {ratio}%）。\n\n"
            f"原文：\n{text}\n\n"
            f"请只输出压缩后的文本："
        )
        try:
            result = await self.llm_func(user_prompt, COMPRESSION_SYSTEM_PROMPT, "")
            output = (result.get("response", "")).strip()
            if output.startswith("```"):
                lines = output.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                output = "\n".join(lines).strip()
            return output
        except Exception:
            return ""

    def _build_raw_anchor(self) -> str:
        from .prompt import PromptBuilder
        return PromptBuilder.build_raw_anchor(self.config)
