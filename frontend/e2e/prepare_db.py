"""为 e2e 准备隔离开奖库。

用 SQLite 的 VACUUM INTO 把真实库复制到 frontend/e2e/.tmp/e2e.db：
WAL 中未落盘的数据也会一并写入，副本干净且可随意读写，不会污染真实库。

该脚本由 Playwright 的后端 webServer 命令在 uvicorn 启动前调用，
因此不会和运行中的后端抢文件锁。
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent.parent / "backend" / "data" / "ssq.db"
TMP_DIR = HERE / ".tmp"
TARGET = TMP_DIR / "e2e.db"


def main() -> int:
    if not SOURCE.exists():
        print(f"[e2e] 找不到开奖库：{SOURCE}", file=sys.stderr)
        return 1

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{TARGET}{suffix}")
        if path.exists():
            try:
                path.unlink()
            except PermissionError:
                print(
                    f"[e2e] 无法删除 {path}：可能仍有后端进程占用，请先停止 8000 端口的服务",
                    file=sys.stderr,
                )
                return 1

    source = sqlite3.connect(SOURCE)
    try:
        source.execute("VACUUM INTO ?", (str(TARGET),))
    finally:
        source.close()

    copy = sqlite3.connect(TARGET)
    try:
        total = copy.execute("select count(*) from draws").fetchone()[0]
        latest = copy.execute("select max(issue) from draws").fetchone()[0]
    finally:
        copy.close()
    print(f"[e2e] 开奖库已复制：{total} 期，最新期号 {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
