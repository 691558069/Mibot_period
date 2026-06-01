"""会话周期配置持久化（JSON + 原子写入）。"""

import copy
import json
import os
import asyncio
from pathlib import Path
from typing import Any


class CycleStore:
    """会话周期配置的持久化存储。"""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._data_dir / "cycles.json"
        self._lock = asyncio.Lock()
        self._cache: dict[str, dict[str, Any]] | None = None

    async def _load(self) -> dict[str, dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        if not self._file_path.exists():
            self._cache = {}
            return self._cache
        try:
            content = self._file_path.read_text(encoding="utf-8")
            data = json.loads(content) if content.strip() else {}
            if not isinstance(data, dict):
                data = {}
        except (json.JSONDecodeError, OSError):
            data = {}
        self._cache = data
        return self._cache

    async def _save(self, data: dict[str, dict[str, Any]]) -> None:
        self._cache = data
        tmp_path = self._file_path.with_suffix(".tmp")
        try:
            content = json.dumps(data, ensure_ascii=False, indent=2)
            tmp_path.write_text(content, encoding="utf-8")
            os.replace(str(tmp_path), str(self._file_path))
        except OSError:
            self._file_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    async def get(self, umo: str) -> dict[str, Any] | None:
        async with self._lock:
            data = await self._load()
            return data.get(umo)

    async def set(self, umo: str, data: dict[str, Any]) -> None:
        async with self._lock:
            all_data = await self._load()
            all_data[umo] = data
            await self._save(all_data)

    async def delete(self, umo: str) -> None:
        async with self._lock:
            all_data = await self._load()
            if umo in all_data:
                del all_data[umo]
                await self._save(all_data)

    async def get_all(self) -> dict[str, dict[str, Any]]:
        async with self._lock:
            return copy.deepcopy(await self._load())

    async def toggle(self, umo: str) -> bool:
        async with self._lock:
            all_data = await self._load()
            if umo not in all_data:
                all_data[umo] = {"enabled": True}
            else:
                current = all_data[umo].get("enabled", False)
                all_data[umo]["enabled"] = not current
            await self._save(all_data)
            return all_data[umo]["enabled"]
