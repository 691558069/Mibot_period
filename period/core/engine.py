"""周期计算引擎（纯函数，无平台依赖）。"""

from dataclasses import dataclass
from typing import Literal
from datetime import datetime, timedelta


@dataclass
class PhaseInfo:
    """当前周期阶段信息。"""
    phase: Literal["menstrual", "follicular", "ovulatory", "luteal"]
    day: int
    days_to_next: int
    total_day: int


class CycleEngine:
    """生理周期阶段计算引擎。"""

    @staticmethod
    def get_phase(
        anchor_date: str,
        cycle_length: int = 28,
        period_length: int = 5,
        ovulation_day: int = 14,
        ovulation_window: int = 3,
        advance_days: int = 0,
    ) -> PhaseInfo:
        """根据锚点日期计算当前周期阶段。

        Args:
            anchor_date: 经期首日，格式 "YYYY-MM-DD"。
            cycle_length: 完整周期天数（默认 28）。
            period_length: 经期持续天数（默认 5）。
            ovulation_day: 排卵日（周期第几天，默认 14）。
            ovulation_window: 排卵期窗口天数（默认 3）。
            advance_days: 调试用快进天数（默认 0）。

        Returns:
            PhaseInfo 当前阶段详情。
        """
        anchor = datetime.strptime(anchor_date, "%Y-%m-%d").date()
        today = datetime.now().date()
        effective_today = today + timedelta(days=advance_days)
        days_diff = (effective_today - anchor).days

        if days_diff < 0:
            cycles_back = (-days_diff // cycle_length) + 1
            days_diff += cycles_back * cycle_length

        total_day = (days_diff % cycle_length) + 1

        ovulation_half = (ovulation_window - 1) // 2
        ovulation_start = ovulation_day - ovulation_half
        ovulation_end = ovulation_start + ovulation_window - 1

        if total_day <= period_length:
            phase = "menstrual"
            day = total_day
        elif total_day < ovulation_start:
            phase = "follicular"
            day = total_day - period_length
        elif ovulation_start <= total_day <= ovulation_end:
            phase = "ovulatory"
            day = total_day - ovulation_start + 1
        else:
            phase = "luteal"
            day = total_day - ovulation_end

        if total_day <= period_length:
            days_to_next = 0
        else:
            days_to_next = cycle_length - total_day + 1

        return PhaseInfo(
            phase=phase,
            day=day,
            days_to_next=days_to_next,
            total_day=total_day,
        )
