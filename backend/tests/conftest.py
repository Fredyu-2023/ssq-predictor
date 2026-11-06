"""测试公共夹具：每个用例一个独立临时 SQLite 文件。"""

from __future__ import annotations

import pytest

from app import db


@pytest.fixture()
def session(tmp_path):
    db.init_engine(tmp_path / "test.db")
    db.init_db()
    with db.get_session() as s:
        yield s
