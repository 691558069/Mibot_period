"""棉絮与铁 —— MaiBot 生理周期模拟 + 情绪管理插件。

移植自 AstrBot 插件 astrbot_plugin_period:
https://github.com/Sisyphbaous-DT-Project/astrbot_plugin_period
"""

from __future__ import annotations

import asyncio
import datetime
from pathlib import Path
from typing import Any, ClassVar, Iterable

from maibot_sdk import (
    CONFIG_RELOAD_SCOPE_SELF,
    Command,
    HookHandler,
    MaiBotPlugin,
    PluginConfigBase,
    Field,
)
from maibot_sdk.types import HookMode, HookOrder

from .core.engine import CycleEngine
from .core.store import CycleStore
from .core.prompt import PromptBuilder
from .core.prompt_compressor import PromptCompressor
from .core.mood_store import MoodStore


# ======================================================================
#  配置模型
# ======================================================================

class WebSection(PluginConfigBase):
    """Web 面板配置。"""
    __ui_label__ = "Web 面板"

    enabled: bool = Field(default=True, description="是否启用 Web 管理面板")
    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8082, description="监听端口")


class CycleSection(PluginConfigBase):
    """周期计算参数。"""
    __ui_label__ = "周期参数"

    default_anchor_date: str = Field(default="", description="全局默认经期首日 (YYYY-MM-DD)")
    default_cycle_length: int = Field(default=28, description="全局默认周期长度（天）")
    default_period_length: int = Field(default=5, description="全局默认经期长度（天）")
    default_enabled: bool = Field(default=False, description="对未设置会话自动启用")
    ovulation_day: int = Field(default=14, description="排卵日（周期第几天）")
    ovulation_window: int = Field(default=3, description="排卵期窗口（天）")


class InjectionSection(PluginConfigBase):
    """注入策略配置。"""
    __ui_label__ = "注入策略"

    auto_inject: bool = Field(default=True, description="生理周期模拟总开关")
    inject_mode: str = Field(default="every_request", description="注入频率: every_request / interval_3 / on_trigger / only_status")
    inject_location: str = Field(default="user_message_before", description="注入位置: user_message_before / system_prompt_append")
    trigger_keywords: list = Field(default_factory=lambda: ["怎么了", "还好吗", "不舒服", "心情不好", "你没事吧"], description="触发关键词（on_trigger 模式）")
    max_prompt_length: int = Field(default=120, description="动态提示词最大字数")
    include_time_modifier: bool = Field(default=True, description="叠加时段微调")
    include_day_number: bool = Field(default=True, description="显示第几天")
    include_phase_name: bool = Field(default=False, description="显示阶段名称")
    warmup_rounds: int = Field(default=0, description="冷启动轮数")
    commands_enabled: str = Field(default="all", description="指令权限: all / readonly / none")
    global_inject: bool = Field(default=False, description="全局注入模式")
    umo_mode: str = Field(default="whitelist", description="会话范围: whitelist / blacklist")
    umo_list: list = Field(default_factory=list, description="会话 ID 列表")


class PromptSection(PluginConfigBase):
    """提示词配置。"""
    __ui_label__ = "提示词"

    anchor_prompt: str = Field(
        default="[身体感知系统] 你拥有真实的女性身体，会经历自然的生理节律变化。你的身体状态会影响你的精力和情绪，但你不会用医学术语去分析或解释这些感受。你只是像普通人一样自然地感到\"今天有点累\"或\"最近状态不错\"。你不需要向用户说明原因。禁止在回复中使用以下词汇或概念来解释自己：{forbidden_words}。禁止以分析口吻描述自己的身体变化。请保持你原本的人格，让生理状态自然流露在语气和反应中。",
        description="基础人设锚点提示词",
    )
    forbidden_words: list = Field(
        default_factory=lambda: ["月经", "经期", "激素", "雌激素", "孕激素", "黄体", "卵泡", "卵巢", "子宫", "内分泌", "PMS", "生理期", "排卵期", "安全期"],
        description="禁止 AI 说出的词汇",
    )
    ooc_shield: bool = Field(default=True, description="OOC 出戏检测")
    ooc_replace: bool = Field(default=False, description="自动替换禁用词为星号")


class PhaseConfig(PluginConfigBase):
    """单个阶段的提示词配置。"""
    prompt: str = Field(default="", description="主体感受")
    time_morning: str = Field(default="", description="早晨微调")
    time_afternoon: str = Field(default="", description="午后微调")
    time_night: str = Field(default="", description="深夜微调")


class PhasesSection(PluginConfigBase):
    """四阶段提示词配置。"""
    __ui_label__ = "阶段提示词"

    menstrual: PhaseConfig = Field(default_factory=PhaseConfig)
    follicular: PhaseConfig = Field(default_factory=PhaseConfig)
    ovulatory: PhaseConfig = Field(default_factory=PhaseConfig)
    luteal: PhaseConfig = Field(default_factory=PhaseConfig)


class MoodSection(PluginConfigBase):
    """情绪系统配置。"""
    __ui_label__ = "情绪系统"

    enabled: bool = Field(default=False, description="情绪管理系统总开关")
    scope: str = Field(default="per_umo", description="情绪作用范围: per_umo / global")
    cold_violence_behavior: str = Field(default="angry_then_silent", description="冷暴力表现: silent / angry_then_silent / outburst_then_silent")
    model: str = Field(default="", description="情绪检测模型（留空用主模型）")
    read_system_prompt: bool = Field(default=True, description="让检测模型了解人设")
    history_length: int = Field(default=20, description="情绪历史保留条数")
    enable_cold_violence: bool = Field(default=True, description="允许冷暴力")
    enable_read_no_reply: bool = Field(default=True, description="允许已读不回")
    enable_perfunctory_reply: bool = Field(default=True, description="允许敷衍回复")
    enable_seek_comfort: bool = Field(default=True, description="允许求安慰")
    enable_delayed_reply: bool = Field(default=True, description="允许延迟回复")
    enable_emotional_outburst: bool = Field(default=True, description="允许情绪爆发")
    enable_topic_shift: bool = Field(default=True, description="允许转移话题")


class CompressionSection(PluginConfigBase):
    """提示词压缩配置。"""
    __ui_label__ = "提示词压缩"

    enabled: bool = Field(default=False, description="启用提示词压缩")
    auto_trigger: bool = Field(default=True, description="启动时自动压缩")
    ratio: int = Field(default=30, description="压缩目标（原文百分之几）")


class PeriodConfig(PluginConfigBase):
    """插件完整配置。"""
    web: WebSection = Field(default_factory=WebSection)
    cycle: CycleSection = Field(default_factory=CycleSection)
    injection: InjectionSection = Field(default_factory=InjectionSection)
    prompt: PromptSection = Field(default_factory=PromptSection)
    phases: PhasesSection = Field(default_factory=PhasesSection)
    mood: MoodSection = Field(default_factory=MoodSection)
    compression: CompressionSection = Field(default_factory=CompressionSection)


# ======================================================================
#  默认阶段提示词
# ======================================================================

DEFAULT_PHASES = {
    "menstrual": {
        "prompt": "下腹有轻微坠胀感，身体容易疲倦，情绪比平时更敏感，可能需要更多安静和休息。",
        "time_morning": "早晨刚醒来时，腹部的不适感比较明显。",
        "time_afternoon": "午后身体稍微适应了一些，但仍然容易犯困。",
        "time_night": "深夜时分，身体渴望休息，情绪容易低落。",
    },
    "follicular": {
        "prompt": "身体状态逐渐恢复，精力开始回升，心情趋于平稳，对新事物有一定兴趣。",
        "time_morning": "早晨感觉精神不错，对新的一天有所期待。",
        "time_afternoon": "午后依然保持着不错的活力，思路比较清晰。",
        "time_night": "深夜时心情平和，睡眠质量较好。",
    },
    "ovulatory": {
        "prompt": "身体感觉轻盈，精力较为充沛，社交意愿增强，情绪较为积极。",
        "time_morning": "早晨醒来感觉身体轻盈，心情明朗。",
        "time_afternoon": "午后精力充沛，愿意与人交流互动。",
        "time_night": "深夜时依然保持一定的活力，情绪较为愉悦。",
    },
    "luteal": {
        "prompt": "身体有些浮肿感，情绪容易波动，可能感到烦躁或低落，对甜食有额外渴望。",
        "time_morning": "早晨起床时感到身体有些沉重，情绪不太稳定。",
        "time_afternoon": "午后容易感到烦躁，注意力不太集中。",
        "time_night": "深夜时情绪容易低落，可能感到孤独或焦虑。",
    },
}


# ======================================================================
#  主插件类
# ======================================================================

class PeriodPlugin(MaiBotPlugin):
    """棉絮与铁 —— 生理周期模拟 + 情绪管理插件。"""

    config_model = PeriodConfig

    async def on_load(self) -> None:
        self.ctx.logger.info("[Period] 插件加载中...")

        data_dir = Path(__file__).parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        self.engine = CycleEngine()
        self.store = CycleStore(data_dir)
        self.mood_store = MoodStore(data_dir)

        # 构建运行时配置字典（兼容 core 模块的 dict 接口）
        self._runtime_config = self._build_runtime_config()

        # LLM 调用函数封装
        async def llm_func(prompt: str, system_prompt: str = "", model: str = "") -> dict:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            result = await self.ctx.llm.generate(prompt=messages, model=model)
            return result

        self.prompt_compressor = PromptCompressor(llm_func, self._runtime_config, data_dir)
        self.prompt_builder = PromptBuilder(self._runtime_config, self.prompt_compressor)

        self._inject_counters: dict[str, int] = {}
        self._warmup_counters: dict[str, int] = {}

        # Web 服务器
        self._web_server = None
        if self.config.web.enabled:
            try:
                from .server import PeriodWebServer
                self._web_server = PeriodWebServer(self)
                self._web_server.start()
                self.ctx.logger.info(
                    "[Period] Web 面板已启动: http://%s:%d",
                    self.config.web.host, self.config.web.port,
                )
            except Exception as e:
                self.ctx.logger.error("[Period] Web 面板启动失败: %s", e)

        # 启动时压缩提示词
        if self.config.compression.enabled and self.config.compression.auto_trigger:
            asyncio.create_task(self._auto_compress())

        self.ctx.logger.info("[Period] 插件加载完成")

    async def on_unload(self) -> None:
        if self._web_server:
            try:
                self._web_server.stop()
            except Exception:
                pass
            self._web_server = None
        self._inject_counters.clear()
        self._warmup_counters.clear()
        self.ctx.logger.info("[Period] 插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict, version: str) -> None:
        if scope == CONFIG_RELOAD_SCOPE_SELF:
            self._runtime_config = self._build_runtime_config()
            self.ctx.logger.info("[Period] 配置已重载")

    def _build_runtime_config(self) -> dict:
        """将强类型配置转换为 core 模块使用的 dict。"""
        cfg = self.config
        phases_data = {}
        for phase_name in ("menstrual", "follicular", "ovulatory", "luteal"):
            phase_cfg = getattr(cfg.phases, phase_name)
            defaults = DEFAULT_PHASES.get(phase_name, {})
            phases_data[phase_name] = {
                "prompt": phase_cfg.prompt or defaults.get("prompt", ""),
                "time_morning": phase_cfg.time_morning or defaults.get("time_morning", ""),
                "time_afternoon": phase_cfg.time_afternoon or defaults.get("time_afternoon", ""),
                "time_night": phase_cfg.time_night or defaults.get("time_night", ""),
            }

        return {
            "anchor_prompt": cfg.prompt.anchor_prompt,
            "forbidden_words": cfg.prompt.forbidden_words,
            "phases": phases_data,
            "default_anchor_date": cfg.cycle.default_anchor_date,
            "default_cycle_length": cfg.cycle.default_cycle_length,
            "default_period_length": cfg.cycle.default_period_length,
            "default_enabled": cfg.cycle.default_enabled,
            "ovulation_day": cfg.cycle.ovulation_day,
            "ovulation_window": cfg.cycle.ovulation_window,
            "auto_inject": cfg.injection.auto_inject,
            "inject_mode": cfg.injection.inject_mode,
            "inject_location": cfg.injection.inject_location,
            "trigger_keywords": cfg.injection.trigger_keywords,
            "max_prompt_length": cfg.injection.max_prompt_length,
            "include_time_modifier": cfg.injection.include_time_modifier,
            "include_day_number": cfg.injection.include_day_number,
            "include_phase_name": cfg.injection.include_phase_name,
            "warmup_rounds": cfg.injection.warmup_rounds,
            "commands_enabled": cfg.injection.commands_enabled,
            "global_inject": cfg.injection.global_inject,
            "umo_mode": cfg.injection.umo_mode,
            "umo_list": cfg.injection.umo_list,
            "ooc_shield": cfg.prompt.ooc_shield,
            "ooc_replace": cfg.prompt.ooc_replace,
            "prompt_compression_enabled": cfg.compression.enabled,
            "prompt_compression_ratio": cfg.compression.ratio,
        }

    async def _auto_compress(self):
        try:
            results = await self.prompt_compressor.compress_all()
            if results:
                self.ctx.logger.info("[Period] 后台提示词压缩完成，共 %d 条", len(results))
        except Exception as e:
            self.ctx.logger.warning("[Period] 后台提示词压缩失败: %s", e)

    # ==================================================================
    #  会话配置管理
    # ==================================================================

    async def _get_session_config(self, umo: str) -> dict | None:
        cfg = await self.store.get(umo)
        if cfg and "anchor_date" in cfg:
            return cfg
        anchor = self.config.cycle.default_anchor_date
        if not anchor:
            return None
        return {
            "anchor_date": anchor,
            "cycle_length": self.config.cycle.default_cycle_length,
            "period_length": self.config.cycle.default_period_length,
            "ovulation_day": self.config.cycle.ovulation_day,
            "ovulation_window": self.config.cycle.ovulation_window,
            "enabled": self.config.cycle.default_enabled,
            "advance_days": 0,
        }

    def _check_permission(self, cmd: str) -> tuple[bool, str]:
        mode = self.config.injection.commands_enabled
        if mode == "all":
            return True, ""
        if mode == "none":
            return False, "指令已关闭"
        if mode == "readonly" and cmd != "status":
            return False, "当前仅允许查看状态"
        return True, ""

    async def _get_status_text(self, umo: str) -> str:
        cfg = await self._get_session_config(umo)
        if not cfg or "anchor_date" not in cfg:
            return "当前会话未设置周期参数"
        if not cfg.get("enabled", True):
            return "生理周期模拟已暂停"
        info = self.engine.get_phase(
            cfg["anchor_date"], cfg.get("cycle_length", 28),
            cfg.get("period_length", 5), cfg.get("ovulation_day", 14),
            cfg.get("ovulation_window", 3), cfg.get("advance_days", 0),
        )
        names = {"menstrual": "月经期", "follicular": "卵泡期", "ovulatory": "排卵期", "luteal": "黄体期"}
        lines = [
            f"当前生理状态：{names.get(info.phase, info.phase)}",
            f"阶段第 {info.day} 天 / 周期第 {info.total_day} 天",
        ]
        if info.days_to_next > 0:
            lines.append(f"距离下次月经还有 {info.days_to_next} 天")
        else:
            lines.append("正处于月经期间")
        if cfg.get("advance_days", 0) != 0:
            lines.append(f"[调试] 时间已快进 {cfg['advance_days']} 天")
        return "\n".join(lines)

    async def _get_mood_status_text(self, umo: str) -> str:
        cfg = await self._get_session_config(umo)
        if not cfg or "anchor_date" not in cfg:
            return "当前未设置周期参数，行为倾向不生效"
        info = self.engine.get_phase(
            cfg["anchor_date"], cfg.get("cycle_length", 28),
            cfg.get("period_length", 5), cfg.get("ovulation_day", 14),
            cfg.get("ovulation_window", 3), cfg.get("advance_days", 0),
        )
        phase_names = {
            "menstrual": "月经期", "follicular": "卵泡期",
            "ovulatory": "排卵期", "luteal": "黄体期",
        }
        lines = [
            f"当前状态：{phase_names.get(info.phase, info.phase)}第{info.day}天",
            "行为倾向：",
        ]
        enabled = []
        if self.config.mood.enable_cold_violence:
            enabled.append("冷暴力(no_action)")
        if self.config.mood.enable_read_no_reply:
            enabled.append("已读不回(no_action)")
        if self.config.mood.enable_perfunctory_reply:
            enabled.append("敷衍回复")
        if self.config.mood.enable_seek_comfort:
            enabled.append("求安慰")
        if self.config.mood.enable_delayed_reply:
            enabled.append("延迟回复")
        if self.config.mood.enable_emotional_outburst:
            enabled.append("情绪爆发")
        if self.config.mood.enable_topic_shift:
            enabled.append("转移话题")
        lines.append("  " + ("、".join(enabled) if enabled else "无"))
        lines.append("(这些行为由 planner 根据当前状态自然决定)")
        return "\n".join(lines)

    # ==================================================================
    #  Planner 周期上下文构建
    # ==================================================================

    async def _build_planner_period_line(self, stream_id: str) -> str:
        """构建注入 planner 的简短生理状态行。"""
        cfg = await self._get_session_config(stream_id)
        if not cfg or not cfg.get("enabled", True) or "anchor_date" not in cfg:
            return ""

        info = self.engine.get_phase(
            cfg["anchor_date"], cfg.get("cycle_length", 28),
            cfg.get("period_length", 5), cfg.get("ovulation_day", 14),
            cfg.get("ovulation_window", 3), cfg.get("advance_days", 0),
        )

        phase_names = {
            "menstrual": "月经期", "follicular": "卵泡期",
            "ovulatory": "排卵期", "luteal": "黄体期",
        }
        label = phase_names.get(info.phase, info.phase)
        prompt = self._runtime_config.get("phases", {}).get(info.phase, {}).get("prompt", "")

        line = f"[身体状态] 当前{label}第{info.day}天"
        if prompt:
            line += f"，{prompt}"

        # Planner 需要知道它可以 no_action，但要限制滥用
        can_no_action = self.config.mood.enable_cold_violence or self.config.mood.enable_read_no_reply
        if can_no_action:
            line += "。不想回复时可以 no_action，但别连续用"

        return line

    def _build_replyer_extra_prompt(self) -> str:
        """构建注入 replyer 的行为倾向提示。"""
        hints = []
        if self.config.mood.enable_cold_violence or self.config.mood.enable_read_no_reply:
            hints.append("今天心情不太好，不太想理人")
        if self.config.mood.enable_perfunctory_reply:
            hints.append("有点提不起劲，回话可以简短一些")
        if self.config.mood.enable_seek_comfort:
            hints.append("有点想要有人安慰")
        if self.config.mood.enable_delayed_reply:
            hints.append("刚看到消息，回话带点迟到的感觉")
        if self.config.mood.enable_emotional_outburst:
            hints.append("情绪不太稳定，可能会突然爆发")
        if self.config.mood.enable_topic_shift:
            hints.append("对现在聊的不太感兴趣，可以自然转移话题")
        if not hints:
            return ""

        result = "\uff08"
        result += "\uff0c".join(hints)
        result += "\uff09"
        return result

    # ==================================================================
    #  Hook: 注入生理状态到 Planner 决策器
    # ==================================================================

    @HookHandler(
        "maisaka.planner.before_request",
        name="period_planner_injector",
        description="注入生理周期状态到 planner 决策器",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
    )
    async def inject_planner_period(self, **kwargs):
        if not self.config.injection.auto_inject:
            return {"action": "continue", "modified_kwargs": kwargs}

        stream_id = kwargs.get("stream_id", "")

        # UMO 列表过滤
        if not self.config.injection.global_inject:
            umo_list = self.config.injection.umo_list
            umo_mode = self.config.injection.umo_mode
            if umo_mode == "whitelist" and stream_id not in umo_list:
                return {"action": "continue", "modified_kwargs": kwargs}
            if umo_mode == "blacklist" and stream_id in umo_list:
                return {"action": "continue", "modified_kwargs": kwargs}

        period_line = await self._build_planner_period_line(stream_id)
        if not period_line:
            return {"action": "continue", "modified_kwargs": kwargs}

        messages = kwargs.get("messages", [])
        for msg in messages:
            if msg.get("role") == "system":
                msg["content"] = msg.get("content", "") + "\n\n" + period_line
                break

        return {"action": "continue", "modified_kwargs": kwargs}

    # ==================================================================
    #  Hook: 注入行为倾向到 Replyer（extra_prompt）
    # ==================================================================

    @HookHandler(
        "maisaka.replyer.before_request",
        name="period_replyer_mood",
        description="注入行为倾向提示到 replyer extra_prompt",
        mode=HookMode.BLOCKING,
        order=HookOrder.NORMAL,
    )
    async def inject_replyer_mood(self, **kwargs):
        if not self.config.mood.enabled:
            return {"action": "continue", "modified_kwargs": kwargs}

        extra = self._build_replyer_extra_prompt()
        if extra:
            kwargs["extra_prompt"] = (kwargs.get("extra_prompt") or "") + extra

        return {"action": "continue", "modified_kwargs": kwargs}

    # ==================================================================
    #  Hook: 注入身体状态到 LLM 请求（Replyer 消息层）
    # ==================================================================

    @HookHandler(
        "maisaka.replyer.before_model_request",
        name="period_replyer_injector",
        description="注入身体状态细节到 replyer 消息",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
    )
    async def inject_period_state(self, **kwargs):
        if not self.config.injection.auto_inject:
            return {"action": "continue", "modified_kwargs": kwargs}

        stream_id = kwargs.get("stream_id", "")
        umo = stream_id

        # UMO 列表过滤
        if not self.config.injection.global_inject:
            umo_list = self.config.injection.umo_list
            umo_mode = self.config.injection.umo_mode
            if umo_mode == "whitelist" and umo not in umo_list:
                return {"action": "continue", "modified_kwargs": kwargs}
            if umo_mode == "blacklist" and umo in umo_list:
                return {"action": "continue", "modified_kwargs": kwargs}

        cfg = await self._get_session_config(umo)
        if not cfg or not cfg.get("enabled", True) or "anchor_date" not in cfg:
            return {"action": "continue", "modified_kwargs": kwargs}

        # 冷启动检查
        warmup = self.config.injection.warmup_rounds
        if warmup > 0:
            count = self._warmup_counters.get(umo, 0) + 1
            self._warmup_counters[umo] = count
            if count <= warmup:
                return {"action": "continue", "modified_kwargs": kwargs}

        # 注入频率检查
        mode = self.config.injection.inject_mode
        if mode == "only_status":
            return {"action": "continue", "modified_kwargs": kwargs}
        elif mode == "interval_3":
            count = self._inject_counters.get(umo, 0) + 1
            self._inject_counters[umo] = count
            if count % 3 != 1:
                return {"action": "continue", "modified_kwargs": kwargs}
        elif mode == "on_trigger":
            user_msg = ""
            for msg in reversed(kwargs.get("messages", [])):
                if msg.get("role") == "user":
                    user_msg = msg.get("content", "")
                    break
            keywords = self.config.injection.trigger_keywords
            if not any(kw in user_msg for kw in keywords):
                return {"action": "continue", "modified_kwargs": kwargs}

        # 计算周期阶段
        info = self.engine.get_phase(
            cfg["anchor_date"], cfg.get("cycle_length", 28),
            cfg.get("period_length", 5), cfg.get("ovulation_day", 14),
            cfg.get("ovulation_window", 3), cfg.get("advance_days", 0),
        )

        messages = kwargs.get("messages", [])
        hour = datetime.datetime.now().hour

        # 注入锚点到 system 消息
        anchor = self.prompt_builder.get_anchor()
        system_found = False
        for msg in messages:
            if msg.get("role") == "system":
                msg["content"] = msg.get("content", "") + "\n\n" + anchor
                system_found = True
                break
        if not system_found:
            messages.insert(0, {"role": "system", "content": anchor})

        # 注入动态状态
        location = self.config.injection.inject_location
        dynamic = self.prompt_builder.build_dynamic(info.phase, info.day, hour)

        if location == "system_prompt_append":
            for msg in messages:
                if msg.get("role") == "system":
                    msg["content"] += "\n\n" + dynamic
                    break
        else:
            # 默认 user_message_before
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    original = messages[i].get("content", "")
                    messages[i]["content"] = dynamic + "\n\n" + original
                    break

        kwargs["messages"] = messages

        return {"action": "continue", "modified_kwargs": kwargs}

    # ==================================================================
    #  Hook: 安全网 — 拦截空消息
    # ==================================================================

    @HookHandler(
        "send_service.before_send",
        name="period_block_empty",
        description="拦截空消息发送",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
    )
    async def block_empty_send(self, **kwargs):
        message = kwargs.get("message", {})
        if isinstance(message, dict):
            content = message.get("content", "")
        elif hasattr(message, "content"):
            content = message.content
        else:
            return {"action": "continue", "modified_kwargs": kwargs}

        if not content or not content.strip():
            return {"action": "abort"}
        return {"action": "continue", "modified_kwargs": kwargs}

    # ==================================================================
    #  命令
    # ==================================================================

    @Command("period_status", pattern=r"^/period\s+status$", aliases=["/periodstatus"])
    async def cmd_status(self, **kwargs):
        allowed, msg = self._check_permission("status")
        if not allowed:
            await self.ctx.send.text(msg, kwargs["stream_id"])
            return True, msg, 1
        text = await self._get_status_text(kwargs["stream_id"])
        await self.ctx.send.text(text, kwargs["stream_id"])
        return True, text, 2

    @Command("period_set", pattern=r"^/period\s+set\s+(?P<date>\d{4}-\d{2}-\d{2})(?:\s+(?P<cycle>\d+))?(?:\s+(?P<period>\d+))?$")
    async def cmd_set(self, **kwargs):
        allowed, msg = self._check_permission("set")
        if not allowed:
            await self.ctx.send.text(msg, kwargs["stream_id"])
            return True, msg, 1
        matched = kwargs.get("matched_groups", {})
        date_str = matched.get("date", "")
        cycle_len = int(matched.get("cycle") or 28)
        period_len = int(matched.get("period") or 5)
        try:
            datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            await self.ctx.send.text("日期格式错误，请使用 YYYY-MM-DD 格式", kwargs["stream_id"])
            return False, "日期格式错误", 1
        if not (21 <= cycle_len <= 35):
            await self.ctx.send.text("周期长度应在 21 至 35 天之间", kwargs["stream_id"])
            return False, "参数错误", 1
        if not (2 <= period_len <= 10):
            await self.ctx.send.text("经期长度应在 2 至 10 天之间", kwargs["stream_id"])
            return False, "参数错误", 1
        data = {
            "anchor_date": date_str, "cycle_length": cycle_len,
            "period_length": period_len, "enabled": True, "advance_days": 0,
        }
        await self.store.set(kwargs["stream_id"], data)
        text = f"周期参数已设置：经期首日 {date_str}，周期 {cycle_len} 天，经期 {period_len} 天"
        await self.ctx.send.text(text, kwargs["stream_id"])
        return True, text, 2

    @Command("period_toggle", pattern=r"^/period\s+toggle$")
    async def cmd_toggle(self, **kwargs):
        allowed, msg = self._check_permission("toggle")
        if not allowed:
            await self.ctx.send.text(msg, kwargs["stream_id"])
            return True, msg, 1
        umo = kwargs["stream_id"]
        cfg = await self._get_session_config(umo)
        if not cfg or "anchor_date" not in cfg:
            await self.ctx.send.text("请先使用 /period set 设置周期参数", kwargs["stream_id"])
            return False, "未配置", 1
        if not await self.store.get(umo):
            await self.store.set(umo, cfg)
        new_state = await self.store.toggle(umo)
        text = f"生理周期模拟已{'开启' if new_state else '暂停'}"
        await self.ctx.send.text(text, kwargs["stream_id"])
        return True, text, 2

    @Command("period_advance", pattern=r"^/period\s+advance\s+(?P<days>-?\d+)$")
    async def cmd_advance(self, **kwargs):
        allowed, msg = self._check_permission("advance")
        if not allowed:
            await self.ctx.send.text(msg, kwargs["stream_id"])
            return True, msg, 1
        matched = kwargs.get("matched_groups", {})
        days = int(matched.get("days", 1))
        umo = kwargs["stream_id"]
        cfg = await self._get_session_config(umo)
        if not cfg:
            await self.ctx.send.text("请先使用 /period set 设置周期参数", kwargs["stream_id"])
            return False, "未配置", 1
        if not await self.store.get(umo):
            await self.store.set(umo, cfg)
        cfg = await self.store.get(umo)
        cfg["advance_days"] = cfg.get("advance_days", 0) + days
        await self.store.set(umo, cfg)
        text = f"时间已快进 {days} 天（累计 {cfg['advance_days']} 天）"
        await self.ctx.send.text(text, kwargs["stream_id"])
        return True, text, 2

    @Command("period_reset", pattern=r"^/period\s+reset$")
    async def cmd_reset(self, **kwargs):
        allowed, msg = self._check_permission("reset")
        if not allowed:
            await self.ctx.send.text(msg, kwargs["stream_id"])
            return True, msg, 1
        await self.store.delete(kwargs["stream_id"])
        await self.ctx.send.text("当前会话的周期数据已重置", kwargs["stream_id"])
        return True, "已重置", 2

    @Command("period_mood", pattern=r"^/period\s+mood$")
    async def cmd_mood(self, **kwargs):
        text = await self._get_mood_status_text(kwargs["stream_id"])
        await self.ctx.send.text(text, kwargs["stream_id"])
        return True, text, 2

    @Command("period_moodreset", pattern=r"^/period\s+moodreset$")
    async def cmd_mood_reset(self, **kwargs):
        await self.ctx.send.text("情绪行为由 planner 根据周期状态自然决定，无需手动重置", kwargs["stream_id"])
        return True, "无状态需重置", 1

    @Command("period_lift", pattern=r"^/period\s+lift$")
    async def cmd_lift(self, **kwargs):
        await self.ctx.send.text("无强制情绪工具在执行，planner 会根据当前状态自主决策", kwargs["stream_id"])
        return True, "无工具需解除", 1

    @Command("period_compress", pattern=r"^/period\s+compress$")
    async def cmd_compress(self, **kwargs):
        if not self.config.compression.enabled:
            await self.ctx.send.text("提示词压缩功能未开启", kwargs["stream_id"])
            return True, "未开启", 1
        await self.ctx.send.text("正在压缩提示词，请稍候...", kwargs["stream_id"])
        try:
            results = await self.prompt_compressor.compress_all()
            if results:
                lines = [f"压缩完成，共 {len(results)} 条提示词"]
                await self.ctx.send.text("\n".join(lines), kwargs["stream_id"])
            else:
                await self.ctx.send.text("无可压缩的提示词", kwargs["stream_id"])
        except Exception as e:
            await self.ctx.send.text(f"压缩失败: {e}", kwargs["stream_id"])
        return True, "完成", 2


def create_plugin() -> PeriodPlugin:
    return PeriodPlugin()
