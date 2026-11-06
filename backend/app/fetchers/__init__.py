"""Fetcher 注册表。新增彩种只需在这里登记，同步引擎/API 自动支持。"""

from __future__ import annotations

from .base import BallConfig, BaseFetcher, RawDraw
from .ssq_fetcher import SSQFetcher

# 已注册（启用）的彩种适配器
FETCHERS: dict[str, type[BaseFetcher]] = {
    SSQFetcher.lottery_type: SSQFetcher,
}


def get_fetcher(lottery_type: str) -> BaseFetcher:
    cls = FETCHERS.get(lottery_type)
    if cls is None:
        raise KeyError(f"未注册的彩种：{lottery_type}")
    return cls()


def list_fetchers() -> list[type[BaseFetcher]]:
    return list(FETCHERS.values())


__all__ = [
    "BaseFetcher",
    "BallConfig",
    "RawDraw",
    "FETCHERS",
    "get_fetcher",
    "list_fetchers",
    "SSQFetcher",
]
