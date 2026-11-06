"""选号策略基类与输出合法性校验。

所有策略（内置 + 用户自定义）都返回 list[list[int]]，每注形如
[r1, r2, ..., rN, b]，红球必须升序且不重复。
"""

from __future__ import annotations

import numbers
from abc import ABC, abstractmethod

DISCLAIMER = "本结果为统计选号，中奖概率与纯随机等价"

# 双色球默认球号规则（后续多彩种由 API 通过 params 覆盖）
DEFAULT_BALLS = {
    "red_count": 6,
    "red_min": 1,
    "red_max": 33,
    "blue_min": 1,
    "blue_max": 16,
}


class BaseStrategy(ABC):
    """策略契约：generate(history, count, **params) -> count 注号码。"""

    name: str = ""
    description: str = ""
    source: str = "builtin"

    @abstractmethod
    def generate(self, history: list, count: int = 1, **params) -> list[list[int]]:
        raise NotImplementedError


def ball_params(params: dict) -> dict:
    """合并球号规则参数，用户传入的同名键不得覆盖球号配置。"""
    result = dict(DEFAULT_BALLS)
    for key in DEFAULT_BALLS:
        if key in params:
            result[key] = int(params[key])
    return result


def _as_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise ValueError(f"{label} 必须是整数，实际为 {value!r}")
    return int(value)


def validate_bets(
    bets: list[list[int]],
    *,
    expected_count: int,
    red_count: int = 6,
    red_min: int = 1,
    red_max: int = 33,
    blue_min: int = 1,
    blue_max: int = 16,
) -> list[list[int]]:
    """校验并归一化为纯 int 列表；不合法抛 ValueError（含具体原因）。"""
    if not isinstance(bets, list):
        raise ValueError(f"策略返回值必须是 list，实际为 {type(bets).__name__}")
    if len(bets) != expected_count:
        raise ValueError(f"应返回 {expected_count} 注，实际 {len(bets)} 注")

    normalized: list[list[int]] = []
    for index, bet in enumerate(bets):
        if not isinstance(bet, (list, tuple)):
            raise ValueError(f"第 {index + 1} 注必须是 list，实际为 {type(bet).__name__}")
        if len(bet) != red_count + 1:
            raise ValueError(f"第 {index + 1} 注长度应为 {red_count + 1}，实际 {len(bet)}")
        reds = [_as_int(n, f"第 {index + 1} 注红球") for n in bet[:red_count]]
        blue = _as_int(bet[-1], f"第 {index + 1} 注蓝球")

        if len(set(reds)) != red_count:
            raise ValueError(f"第 {index + 1} 注红球存在重复：{reds}")
        for n in reds:
            if not (red_min <= n <= red_max):
                raise ValueError(f"第 {index + 1} 注红球 {n} 超出范围 {red_min}-{red_max}")
        if reds != sorted(reds):
            raise ValueError(f"第 {index + 1} 注红球未升序：{reds}")
        if not (blue_min <= blue <= blue_max):
            raise ValueError(f"第 {index + 1} 注蓝球 {blue} 超出范围 {blue_min}-{blue_max}")
        normalized.append([*reds, blue])
    return normalized
