"""Fetcher 抽象基类：球号规则、统一数据结构 RawDraw、合法性校验。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class BallConfig:
    """球号规则。校验逻辑集中在 validate()，所有彩种共用。"""

    red_count: int
    red_min: int
    red_max: int
    blue_count: int
    blue_min: int
    blue_max: int
    # 允许的蓝球个数上限（默认等于 blue_count）。双色球在少数派奖期会出现「幸运蓝球」，
    # 此时蓝球为 2 个：主蓝球照常统计，第二个存入 extra_blues。
    blue_count_max: int | None = None

    def _blue_expected(self) -> str:
        if self.blue_count_max and self.blue_count_max != self.blue_count:
            return f"{self.blue_count}-{self.blue_count_max}"
        return str(self.blue_count)

    def validate(self, reds: list[int], blues: list[int]) -> None:
        """校验红球/蓝球是否合法，不合法抛 ValueError（含具体原因）。"""
        if len(reds) != self.red_count:
            raise ValueError(f"红球个数应为 {self.red_count}，实际 {len(reds)}")
        if len(set(reds)) != len(reds):
            raise ValueError(f"红球存在重复：{reds}")
        for n in reds:
            if not isinstance(n, int) or not (self.red_min <= n <= self.red_max):
                raise ValueError(f"红球 {n} 超出范围 {self.red_min}-{self.red_max}")

        blue_upper = self.blue_count_max or self.blue_count
        if not (self.blue_count <= len(blues) <= blue_upper):
            raise ValueError(f"蓝球个数应为 {self._blue_expected()}，实际 {len(blues)}")
        if len(set(blues)) != len(blues):
            raise ValueError(f"蓝球存在重复：{blues}")
        for n in blues:
            if not isinstance(n, int) or not (self.blue_min <= n <= self.blue_max):
                raise ValueError(f"蓝球 {n} 超出范围 {self.blue_min}-{self.blue_max}")

    def as_dict(self) -> dict:
        data = {
            "red_count": self.red_count,
            "red_min": self.red_min,
            "red_max": self.red_max,
            "blue_count": self.blue_count,
            "blue_min": self.blue_min,
            "blue_max": self.blue_max,
        }
        if self.blue_count_max is not None:
            data["blue_count_max"] = self.blue_count_max
        return data


@dataclass
class RawDraw:
    """Fetcher 输出的统一数据结构，尚未入库。"""

    lottery_type: str
    issue: str
    draw_date: date
    reds: list[int]
    blues: list[int]
    sales_amount: int | None = None
    pool_balance: int | None = None
    prize_details: dict | None = None
    prize1_count: int | None = None
    skipped_reason: str | None = field(default=None, compare=False)


class BaseFetcher(ABC):
    """彩种数据适配器契约：从外部源拉取 → 解析成 RawDraw。"""

    lottery_type: str
    name: str
    ball_config: BallConfig

    @abstractmethod
    def fetch(self, since: str | None = None) -> list[RawDraw]:
        """拉取 since 期号之后（不含）的所有开奖记录，按期号升序返回。"""

    @abstractmethod
    def fetch_latest(self) -> RawDraw | None:
        """拉取最新一期，用于快速校验数据源可用性。"""
