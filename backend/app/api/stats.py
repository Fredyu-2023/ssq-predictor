"""统计分析 API：GET /api/stats?type=ssq&range=30|100|all

缓存策略：key 含 (彩种, 窗口, 总条数, 最新期号)，同步后由 sync_engine 主动失效。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import analyzer, db
from ..fetchers import get_fetcher
from ..models import Draw
from ..schemas import StatsOut

router = APIRouter(tags=["stats"])

VALID_RANGES = {"30", "100", "all"}


def _check_type(lottery_type: str) -> str:
    try:
        get_fetcher(lottery_type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return lottery_type


def _to_stat_draw(row: Draw) -> analyzer.StatDraw:
    return analyzer.StatDraw(
        issue=row.issue,
        reds=tuple(row.reds),
        blue=row.blue,
        draw_date=row.draw_date,
    )


def _compute(session: Session, lottery_type: str, range_str: str) -> dict:
    total = int(
        session.execute(
            select(func.count()).select_from(Draw).where(Draw.lottery_type == lottery_type)
        ).scalar_one()
    )
    latest = session.execute(
        select(Draw.issue)
        .where(Draw.lottery_type == lottery_type)
        .order_by(Draw.issue.desc())
        .limit(1)
    ).scalar_one_or_none()

    cache_key = (lottery_type, range_str, total, latest)
    cached = analyzer.cache_get(cache_key)
    if cached is not None:
        return cached

    stmt = (
        select(Draw)
        .where(Draw.lottery_type == lottery_type)
        .order_by(Draw.issue.desc())
    )
    if range_str != "all":
        stmt = stmt.limit(int(range_str))
    rows = list(session.execute(stmt).scalars().all())
    rows.reverse()  # 统计按旧 → 新顺序计算遗漏值

    cfg = get_fetcher(lottery_type).ball_config
    payload = analyzer.analyze(
        [_to_stat_draw(row) for row in rows],
        red_count=cfg.red_count,
        red_min=cfg.red_min,
        red_max=cfg.red_max,
        blue_min=cfg.blue_min,
        blue_max=cfg.blue_max,
    )
    payload["lottery_type"] = lottery_type
    payload["range"] = range_str
    payload["draws_total"] = total
    analyzer.cache_put(cache_key, payload)
    return payload


@router.get("/stats", response_model=StatsOut)
def stats(
    type: str = Query(default="ssq"),
    range_: str = Query(default="30", alias="range", description="统计窗口：30 / 100 / all"),
    session: Session = Depends(db.get_db),
) -> StatsOut:
    lottery_type = _check_type(type)
    if range_ not in VALID_RANGES:
        raise HTTPException(
            status_code=400, detail=f"range 仅支持 {'/'.join(sorted(VALID_RANGES))}"
        )
    return StatsOut(**_compute(session, lottery_type, range_))
