"""ORM 模型：draws（开奖结果，多彩种共用）与 sync_log（同步日志）。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Draw(Base):
    """开奖结果。联合主键 (lottery_type, issue)，不同彩种期号可重复。"""

    __tablename__ = "draws"

    lottery_type: Mapped[str] = mapped_column(String(10), primary_key=True)
    issue: Mapped[str] = mapped_column(String(20), primary_key=True)
    draw_date: Mapped[date] = mapped_column(Date, index=True)

    red1: Mapped[int] = mapped_column(Integer)
    red2: Mapped[int] = mapped_column(Integer)
    red3: Mapped[int] = mapped_column(Integer)
    red4: Mapped[int] = mapped_column(Integer)
    red5: Mapped[int] = mapped_column(Integer)
    red6: Mapped[int] = mapped_column(Integer)
    blue: Mapped[int] = mapped_column(Integer)
    # 多蓝球彩种（如大乐透后区 2 个）用 JSON 扩展
    extra_blues: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    sales_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pool_balance: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prize1_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prize_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("ix_draws_type_date", "lottery_type", "draw_date"),
    )

    @property
    def reds(self) -> list[int]:
        return [self.red1, self.red2, self.red3, self.red4, self.red5, self.red6]

    @property
    def blues(self) -> list[int]:
        if self.extra_blues:
            return [self.blue, *self.extra_blues]
        return [self.blue]


class SyncLog(Base):
    """每次同步一条记录，用于前端展示同步历史与失败原因。"""

    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lottery_type: Mapped[str] = mapped_column(String(10), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # success/failed/partial
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)


class LotteryConfig(Base):
    """彩种球号规则。由各 Fetcher 在初始化时写入，前端无需硬编码规则。"""

    __tablename__ = "lottery_config"

    lottery_type: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    red_count: Mapped[int] = mapped_column(Integer)
    red_min: Mapped[int] = mapped_column(Integer)
    red_max: Mapped[int] = mapped_column(Integer)
    blue_count: Mapped[int] = mapped_column(Integer)
    blue_min: Mapped[int] = mapped_column(Integer)
    blue_max: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
