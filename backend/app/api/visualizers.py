"""可视化 API：清单 + 渲染 / 特征提取（未实现算法统一返回 501）。"""

from __future__ import annotations

import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import db
from ..fetchers import get_fetcher
from ..models import Draw
from ..schemas import (
    VisualizerFeaturesOut,
    VisualizerOut,
    VisualizerRequest,
    VisualizationOut,
)
from ..visualizers import BaseVisualizer, get_visualizer, list_visualizers

router = APIRouter(tags=["visualizers"])


def _resolve(name: str) -> BaseVisualizer:
    try:
        return get_visualizer(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _ensure_implemented(visualizer: BaseVisualizer) -> None:
    if visualizer.status != "implemented":
        raise HTTPException(
            status_code=501,
            detail=f"{visualizer.title}（{visualizer.code}）仍在开发中，当前仅提供框架与占位清单",
        )


def _load_draws(session: Session, lottery_type: str, periods: int) -> list[Draw]:
    try:
        get_fetcher(lottery_type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rows = list(
        session.execute(
            select(Draw)
            .where(Draw.lottery_type == lottery_type)
            .order_by(Draw.issue.desc())
            .limit(periods)
        )
        .scalars()
        .all()
    )
    rows.reverse()
    if not rows:
        raise HTTPException(status_code=400, detail="暂无历史开奖数据，请先同步")
    return rows


@router.get("/visualizers", response_model=list[VisualizerOut])
def list_all() -> list[VisualizerOut]:
    return [VisualizerOut(**item) for item in list_visualizers()]


@router.post("/visualizers/{name}/render", response_model=VisualizationOut)
def render(
    name: str,
    request: VisualizerRequest,
    session: Session = Depends(db.get_db),
) -> VisualizationOut:
    visualizer = _resolve(name)
    _ensure_implemented(visualizer)
    rows = _load_draws(session, request.type, request.periods)
    try:
        data = visualizer.render(rows, **request.params)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"{name} 渲染失败：\n{traceback.format_exc()}",
        ) from None
    return VisualizationOut(type=data.type, data=data.data, metadata=data.metadata)


@router.post("/visualizers/{name}/features", response_model=VisualizerFeaturesOut)
def features(
    name: str,
    request: VisualizerRequest,
    session: Session = Depends(db.get_db),
) -> VisualizerFeaturesOut:
    visualizer = _resolve(name)
    _ensure_implemented(visualizer)
    rows = _load_draws(session, request.type, request.periods)
    try:
        data = visualizer.render(rows, **request.params)
        extracted = visualizer.extract_features(data)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"{name} 特征提取失败：\n{traceback.format_exc()}",
        ) from None
    return VisualizerFeaturesOut(code=visualizer.code, name=visualizer.name, features=extracted)
