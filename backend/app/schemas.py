"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class DrawOut(BaseModel):
    lottery_type: str
    issue: str
    draw_date: date
    reds: list[int]
    blues: list[int]
    sales_amount: int | None = None
    pool_balance: int | None = None
    prize1_count: int | None = None

    model_config = {"from_attributes": True}


class HistoryPage(BaseModel):
    total: int
    page: int
    size: int
    items: list[DrawOut]


class LotteryOut(BaseModel):
    type: str
    name: str
    red_count: int
    red_min: int
    red_max: int
    blue_count: int
    blue_min: int
    blue_max: int
    enabled: bool = True


class SyncStatusItem(BaseModel):
    type: str
    name: str
    latest_issue: str | None = None
    latest_date: date | None = None
    total_count: int = 0
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    syncing: bool = False


class SyncStatusResponse(BaseModel):
    lotteries: list[SyncStatusItem]


class SyncRunResult(BaseModel):
    lottery_type: str
    status: str  # success / failed / partial / busy
    fetched_count: int = 0
    inserted_count: int = 0
    skipped_count: int = 0
    latest_issue: str | None = None
    error_msg: str | None = None
    elapsed_ms: int = 0


class SyncLogOut(BaseModel):
    id: int
    lottery_type: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    fetched_count: int
    inserted_count: int
    error_msg: str | None = None

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str = Field(default="ok")
    db: str
    draws: int


# ---------------- 统计 ----------------


class NumberCount(BaseModel):
    number: int
    count: int


class NumberOmission(BaseModel):
    number: int
    omission: int


class PairCount(BaseModel):
    pair: str
    count: int
    parts: list[int]


class DistributionItem(BaseModel):
    label: str
    count: int
    parts: list[int] | None = None


class SumStats(BaseModel):
    min: int
    max: int
    mean: float


class StatsOut(BaseModel):
    lottery_type: str
    range: str
    window: int
    draws_total: int
    first_issue: str | None = None
    last_issue: str | None = None
    red_freq: list[NumberCount]
    blue_freq: list[NumberCount]
    red_omission: list[NumberOmission]
    blue_omission: list[NumberOmission]
    hot_red: list[NumberCount]
    cold_red: list[NumberCount]
    hot_blue: list[NumberCount]
    cold_blue: list[NumberCount]
    consecutive: list[PairCount]
    odd_even: list[DistributionItem]
    big_small: list[DistributionItem]
    zone_ratio: list[DistributionItem]
    sum_distribution: list[DistributionItem]
    sum_stats: SumStats
    ac_distribution: list[DistributionItem]
    ac_avg: float


# ---------------- 选号策略 ----------------


class StrategyOut(BaseModel):
    name: str
    description: str
    source: str


class PredictRequest(BaseModel):
    strategy: str = "random"
    type: str = "ssq"
    count: int = Field(default=1, ge=1, le=20)
    params: dict[str, Any] = Field(default_factory=dict)


class BetOut(BaseModel):
    red: list[int]
    blue: int


class PredictOut(BaseModel):
    strategy: str
    count: int
    numbers: list[BetOut]
    disclaimer: str


# ---------------- 回测 ----------------


class BacktestRequest(BaseModel):
    strategy: str = "random"
    type: str = "ssq"
    window: int = Field(default=100, ge=1, le=500)
    periods: int = Field(default=100, ge=1, le=500)
    params: dict[str, Any] = Field(default_factory=dict)


class RedHitItem(BaseModel):
    hits: int
    count: int
    ratio: float


class PrizeLevelItem(BaseModel):
    level: int
    name: str
    condition: str
    actual: int
    expected: float
    probability: float


class ChiSquareBucket(BaseModel):
    label: str
    observed: int
    expected: float


class ChiSquareOut(BaseModel):
    statistic: float
    df: int
    p_value: float
    buckets: list[ChiSquareBucket]
    conclusion: str


class BacktestOut(BaseModel):
    strategy: str
    window: int
    periods: int
    samples: int
    from_issue: str
    to_issue: str
    red_hits: list[RedHitItem]
    avg_red_hits: float
    blue_hits: int
    blue_hit_rate: float
    blue_expected_rate: float
    prize_levels: list[PrizeLevelItem]
    chi_square: ChiSquareOut
    disclaimer: str


# ---------------- 可视化 ----------------


class VisualizerOut(BaseModel):
    code: str
    name: str
    title: str
    category: str
    dimension: str
    status: str
    description: str
    mapping: str


class VisualizerRequest(BaseModel):
    type: str = "ssq"
    periods: int = Field(default=30, ge=1, le=200)
    params: dict[str, Any] = Field(default_factory=dict)


class VisualizationOut(BaseModel):
    type: str
    data: dict[str, Any]
    metadata: dict[str, Any]


class VisualizerFeaturesOut(BaseModel):
    code: str
    name: str
    features: dict[str, Any]
