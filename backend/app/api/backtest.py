"""回测 API：滑动窗口模拟指定策略，返回命中分布与卡方 p-value。"""

from __future__ import annotations

import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import backtest, db
from ..fetchers import get_fetcher
from ..models import Draw
from ..schemas import BacktestOut, BacktestRequest
from ..strategies import get_strategy

router = APIRouter(tags=["backtest"])


@router.post("/backtest", response_model=BacktestOut)
def run(request: BacktestRequest, session: Session = Depends(db.get_db)) -> BacktestOut:
    try:
        fetcher = get_fetcher(request.type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        strategy = get_strategy(request.strategy)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    seed = request.params.get("seed")
    if seed is not None:
        try:
            seed = int(seed)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="seed 必须是整数") from exc

    limit = request.window + request.periods
    rows = list(
        session.execute(
            select(Draw)
            .where(Draw.lottery_type == request.type)
            .order_by(Draw.issue.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    rows.reverse()
    if not rows:
        raise HTTPException(status_code=400, detail="暂无历史开奖数据，请先同步")

    cfg = fetcher.ball_config
    try:
        result = backtest.run_backtest(
            rows,
            strategy,
            window=request.window,
            periods=request.periods,
            red_count=cfg.red_count,
            red_min=cfg.red_min,
            red_max=cfg.red_max,
            blue_min=cfg.blue_min,
            blue_max=cfg.blue_max,
            seed=seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"策略 {request.strategy} 回测失败：\n{traceback.format_exc()}",
        ) from None

    return BacktestOut(**result)
