"""SQLAlchemy 引擎与 Session 管理。

设计要点：
- 引擎可重建（便于测试注入临时数据库路径）
- SQLite 使用 check_same_thread=False，因为同步任务跑在后台线程里
- 所有表通过 Base.metadata.create_all 创建，绝不 DROP 已有表
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def _enable_sqlite_pragmas(engine_: Engine) -> None:
    """开启 WAL，提升并发读写稳定性。"""

    @event.listens_for(engine_, "connect")
    def _set_pragma(dbapi_conn, _record):  # pragma: no cover - 依赖真实连接
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def init_engine(db_path: Path | str | None = None, echo: bool = False) -> Engine:
    """（重建）初始化引擎与 Session 工厂。传 ":memory:" 可用于测试。"""
    global engine, SessionLocal

    path = str(db_path or config.DB_PATH)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{path}"
    else:
        url = "sqlite://"

    engine = create_engine(
        url,
        echo=echo,
        future=True,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
    )
    _enable_sqlite_pragmas(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine


def init_db() -> None:
    """建表（幂等）。不删除任何已有数据。"""
    from . import models  # noqa: F401  确保模型已注册到 Base.metadata

    if engine is None:
        init_engine()
    assert engine is not None
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """获取一个新 Session（调用方负责关闭，建议用 with 语法）。"""
    if SessionLocal is None:
        init_db()
    assert SessionLocal is not None
    return SessionLocal()


def get_db() -> Iterator[Session]:
    """FastAPI 依赖注入用的 Session 生成器。"""
    session = get_session()
    try:
        yield session
    finally:
        session.close()
