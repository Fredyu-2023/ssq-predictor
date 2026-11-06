"""选号 API：策略清单与选号生成。"""

from __future__ import annotations

import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import db
from ..fetchers import get_fetcher
from ..models import Draw
from ..schemas import BetOut, PredictOut, PredictRequest, StrategyOut
from ..strategies import (
    DISCLAIMER,
    get_strategy,
    list_strategies,
    validate_bets,
)

router = APIRouter(tags=["predict"])

MAX_HISTORY = 500


def _load_history(session: Session, lottery_type: str) -> list[Draw]:
    rows = list(
        session.execute(
            select(Draw)
            .where(Draw.lottery_type == lottery_type)
            .order_by(Draw.issue.desc())
            .limit(MAX_HISTORY)
        )
        .scalars()
        .all()
    )
    rows.reverse()
    return rows


@router.get("/strategies", response_model=list[StrategyOut])
def strategies() -> list[StrategyOut]:
    return [StrategyOut(**item) for item in list_strategies()]


@router.post("/predict", response_model=PredictOut)
def predict(request: PredictRequest, session: Session = Depends(db.get_db)) -> PredictOut:
    try:
        fetcher = get_fetcher(request.type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        strategy = get_strategy(request.strategy)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    cfg = fetcher.ball_config
    params = dict(request.params)
    try:
        window = int(params.get("window", 30))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="window 必须是整数") from exc
    if not 1 <= window <= MAX_HISTORY:
        raise HTTPException(status_code=400, detail=f"window 需在 1-{MAX_HISTORY} 之间")
    params["window"] = window
    # 球号规则最后写入，用户参数不得覆盖
    params.update(cfg.as_dict())

    history = _load_history(session, request.type)
    if not history:
        raise HTTPException(status_code=400, detail="暂无历史开奖数据，请先同步")

    try:
        raw = strategy.generate(history, request.count, **params)
        bets = validate_bets(
            raw,
            expected_count=request.count,
            red_count=cfg.red_count,
            red_min=cfg.red_min,
            red_max=cfg.red_max,
            blue_min=cfg.blue_min,
            blue_max=cfg.blue_max,
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"策略 {request.strategy} 执行或校验失败：\n{traceback.format_exc()}",
        ) from None

    numbers = [
        BetOut(red=bet[: cfg.red_count], blue=bet[-1]) for bet in bets
    ]
    return PredictOut(
        strategy=request.strategy,
        count=request.count,
        numbers=numbers,
        disclaimer=DISCLAIMER,
    )
