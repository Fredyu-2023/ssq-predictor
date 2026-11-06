"""历史开奖与彩种列表 API（分页，禁止一次性返回全量）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import db
from ..fetchers import get_fetcher, list_fetchers
from ..models import Draw, LotteryConfig
from ..schemas import DrawOut, HistoryPage, LotteryOut

router = APIRouter(tags=["history"])


@router.get("/lotteries", response_model=list[LotteryOut])
def lotteries(session: Session = Depends(db.get_db)) -> list[LotteryOut]:
    rows = {
        row.lottery_type: row
        for row in session.execute(select(LotteryConfig)).scalars().all()
    }
    items: list[LotteryOut] = []
    for cls in list_fetchers():
        row = rows.get(cls.lottery_type)
        cfg = cls.ball_config
        items.append(
            LotteryOut(
                type=cls.lottery_type,
                name=cls.name,
                red_count=cfg.red_count,
                red_min=cfg.red_min,
                red_max=cfg.red_max,
                blue_count=cfg.blue_count,
                blue_min=cfg.blue_min,
                blue_max=cfg.blue_max,
                enabled=bool(row.enabled) if row else True,
            )
        )
    return items


def _check_type(lottery_type: str) -> str:
    try:
        get_fetcher(lottery_type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return lottery_type


@router.get("/history", response_model=HistoryPage)
def history(
    type: str = Query(default="ssq"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=500),  # 上限 500：统计页走势矩阵「全部」档一次取 300 期
    q: str | None = Query(default=None, max_length=50, description="按期号或开奖日期搜索"),
    session: Session = Depends(db.get_db),
) -> HistoryPage:
    lottery_type = _check_type(type)
    keyword = (q or "").strip()
    conditions = [Draw.lottery_type == lottery_type]
    if keyword:
        like = f"%{keyword}%"
        conditions.append(
            or_(
                Draw.issue.ilike(like),
                func.strftime("%Y-%m-%d", Draw.draw_date).ilike(like),
            )
        )
    total = session.execute(
        select(func.count()).select_from(Draw).where(*conditions)
    ).scalar_one()
    rows = (
        session.execute(
            select(Draw)
            .where(*conditions)
            .order_by(Draw.issue.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    items = [
        DrawOut(
            lottery_type=row.lottery_type,
            issue=row.issue,
            draw_date=row.draw_date,
            reds=row.reds,
            blues=row.blues,
            sales_amount=row.sales_amount,
            pool_balance=row.pool_balance,
            prize1_count=row.prize1_count,
        )
        for row in rows
    ]
    return HistoryPage(total=int(total), page=page, size=size, items=items)


@router.get("/history/latest", response_model=DrawOut)
def latest(
    type: str = Query(default="ssq"), session: Session = Depends(db.get_db)
) -> DrawOut:
    lottery_type = _check_type(type)
    row = session.execute(
        select(Draw)
        .where(Draw.lottery_type == lottery_type)
        .order_by(Draw.issue.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="暂无开奖数据，请先同步")
    return DrawOut(
        lottery_type=row.lottery_type,
        issue=row.issue,
        draw_date=row.draw_date,
        reds=row.reds,
        blues=row.blues,
        sales_amount=row.sales_amount,
        pool_balance=row.pool_balance,
        prize1_count=row.prize1_count,
    )
