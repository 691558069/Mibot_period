"""棉絮与铁 Web 管理面板服务器。

基于 FastAPI + uvicorn，在独立守护线程中运行。
参考 A_memorix 的 Web 服务器实现。
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


class AnchorUpdate(BaseModel):
    date: str


class AdvanceRequest(BaseModel):
    days: int = 1


class PeriodWebServer:
    """Period 插件的 Web 管理面板。"""

    def __init__(self, plugin) -> None:
        self.plugin = plugin
        self.host = plugin.config.web.host
        self.port = plugin.config.web.port
        self.app = FastAPI(title="棉絮与铁 - 周期管理面板")
        self._server = None
        self._thread: threading.Thread | None = None

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self._setup_routes()

    def _setup_routes(self) -> None:
        app = self.app

        # ---- 页面路由 ----

        @app.get("/")
        async def index():
            html_path = Path(__file__).parent / "web" / "index.html"
            if html_path.exists():
                return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
            return HTMLResponse(content="<h1>面板文件未找到</h1>")

        # ---- API 路由 ----

        @app.get("/api/sessions")
        async def list_sessions():
            all_data = await self.plugin.store.get_all()
            sessions = []
            for umo, cfg in all_data.items():
                if not cfg or "anchor_date" not in cfg:
                    continue
                try:
                    info = self.plugin.engine.get_phase(
                        cfg["anchor_date"], cfg.get("cycle_length", 28),
                        cfg.get("period_length", 5), cfg.get("ovulation_day", 14),
                        cfg.get("ovulation_window", 3), cfg.get("advance_days", 0),
                    )
                except Exception:
                    continue
                phase_labels = {
                    "menstrual": "月经期", "follicular": "卵泡期",
                    "ovulatory": "排卵期", "luteal": "黄体期",
                }
                sessions.append({
                    "umo": umo,
                    "enabled": cfg.get("enabled", True),
                    "anchor_date": cfg["anchor_date"],
                    "cycle_length": cfg.get("cycle_length", 28),
                    "period_length": cfg.get("period_length", 5),
                    "advance_days": cfg.get("advance_days", 0),
                    "phase": info.phase,
                    "phase_day": info.day,
                    "total_day": info.total_day,
                    "days_to_next": info.days_to_next,
                    "phase_label": phase_labels.get(info.phase, info.phase),
                })
            return {"status": "ok", "data": {"sessions": sessions, "count": len(sessions)}}

        @app.get("/api/config")
        async def get_config():
            cfg = self.plugin.config
            return {
                "status": "ok",
                "data": {
                    "default_anchor_date": cfg.cycle.default_anchor_date,
                    "default_enabled": cfg.cycle.default_enabled,
                    "default_cycle_length": cfg.cycle.default_cycle_length,
                    "default_period_length": cfg.cycle.default_period_length,
                    "ovulation_day": cfg.cycle.ovulation_day,
                    "ovulation_window": cfg.cycle.ovulation_window,
                },
            }

        @app.post("/api/sessions/{umo}/toggle")
        async def toggle_session(umo: str):
            cfg = await self.plugin._get_session_config(umo)
            if not cfg or "anchor_date" not in cfg:
                raise HTTPException(status_code=404, detail="会话未配置")
            if not await self.plugin.store.get(umo):
                await self.plugin.store.set(umo, cfg)
            new_state = await self.plugin.store.toggle(umo)
            cfg = await self.plugin.store.get(umo)
            return {"status": "ok", "data": {"enabled": new_state}}

        @app.post("/api/sessions/{umo}/advance")
        async def advance_session(umo: str, body: AdvanceRequest):
            if not (-365 <= body.days <= 365):
                raise HTTPException(status_code=400, detail="days 范围为 -365 ~ 365")
            cfg = await self.plugin._get_session_config(umo)
            if not cfg:
                raise HTTPException(status_code=404, detail="会话未配置")
            if not await self.plugin.store.get(umo):
                await self.plugin.store.set(umo, cfg)
            cfg = await self.plugin.store.get(umo)
            cfg["advance_days"] = cfg.get("advance_days", 0) + body.days
            await self.plugin.store.set(umo, cfg)
            return {"status": "ok", "data": {"advance_days": cfg["advance_days"]}}

        @app.post("/api/sessions/{umo}/anchor")
        async def set_anchor(umo: str, body: AnchorUpdate):
            try:
                import datetime
                datetime.datetime.strptime(body.date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")
            cfg = await self.plugin._get_session_config(umo)
            if not cfg:
                raise HTTPException(status_code=404, detail="会话未配置")
            if not await self.plugin.store.get(umo):
                await self.plugin.store.set(umo, cfg)
            cfg = await self.plugin.store.get(umo)
            cfg["anchor_date"] = body.date
            cfg["advance_days"] = 0
            await self.plugin.store.set(umo, cfg)
            return {"status": "ok"}

        @app.post("/api/sessions/{umo}/delete")
        async def delete_session(umo: str):
            if not await self.plugin.store.get(umo):
                raise HTTPException(status_code=404, detail="会话不存在")
            await self.plugin.store.delete(umo)
            return {"status": "ok", "data": {"umo": umo, "deleted": True}}

    def run(self):
        import uvicorn
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info")
        self._server = uvicorn.Server(config)
        self._server.run()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=2)
