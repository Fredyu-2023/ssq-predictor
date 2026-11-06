"""FastAPI 入口：建表 → 启动自动同步（后台线程，不阻塞启动）→ 挂载路由。"""

from __future__ import annotations

import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app import config, db, sync_engine
from app.api import backtest, history, predict, stats, sync, visualizers
from app.models import Draw
from app.schemas import HealthOut

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # 每页请求日志太吵
logger = logging.getLogger("ssq")


def _startup_sync() -> None:
    """启动同步：失败只写 sync_log，绝不影响应用可用性。"""
    logger.info("启动自动同步开始")
    try:
        results = sync_engine.sync_all(wait=True, full=True)
        for r in results:
            logger.info(
                "同步 %s：%s，拉取 %d 条，新增 %d 条，最新期号 %s，耗时 %dms",
                r.lottery_type,
                r.status,
                r.fetched_count,
                r.inserted_count,
                r.latest_issue,
                r.elapsed_ms,
            )
    except Exception:  # pragma: no cover - 兜底，避免线程异常刷屏
        logger.exception("启动自动同步异常")


def _bootstrap() -> None:
    db.init_db()
    with db.get_session() as session:
        sync_engine.sync_lottery_configs(session)
        stale = sync_engine.cleanup_stale_logs(session)
    if stale:
        logger.info("清理了 %d 条上次中断的同步日志", stale)
    if config.AUTO_SYNC_ON_STARTUP:
        threading.Thread(target=_startup_sync, name="startup-sync", daemon=True).start()
    else:
        logger.info("AUTO_SYNC_ON_STARTUP=false，跳过启动同步")


app = FastAPI(
    title="双色球开奖数据同步与分析系统",
    version="0.1.0",
    description="仅本机/局域网使用；彩票为独立随机事件，本系统仅作统计分析与选号参考。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 仅内网使用
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    _bootstrap()


@app.get(f"{config.API_PREFIX}/health", response_model=HealthOut, tags=["health"])
def health() -> HealthOut:
    with db.get_session() as session:
        count = session.execute(select(func.count()).select_from(Draw)).scalar_one()
    return HealthOut(db=str(config.DB_PATH), draws=int(count))


app.include_router(sync.router, prefix=config.API_PREFIX)
app.include_router(history.router, prefix=config.API_PREFIX)
app.include_router(stats.router, prefix=config.API_PREFIX)
app.include_router(predict.router, prefix=config.API_PREFIX)
app.include_router(backtest.router, prefix=config.API_PREFIX)
app.include_router(visualizers.router, prefix=config.API_PREFIX)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
