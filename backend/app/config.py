"""全局配置：路径、端口、同步参数。所有可调项都可用环境变量覆盖。"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = BASE_DIR / "data"

DB_PATH = Path(os.getenv("SSQ_DB_PATH", str(DATA_DIR / "ssq.db")))

# 启动时是否自动同步一次全部已注册彩种
AUTO_SYNC_ON_STARTUP = os.getenv("AUTO_SYNC_ON_STARTUP", "true").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# 同步参数：每页条数、请求间隔（秒，礼貌爬取）、失败重试次数、超时（秒）
SYNC_PAGE_SIZE = int(os.getenv("SSQ_SYNC_PAGE_SIZE", "100"))
SYNC_REQUEST_INTERVAL = float(os.getenv("SSQ_SYNC_INTERVAL", "0.5"))
SYNC_MAX_RETRIES = int(os.getenv("SSQ_SYNC_MAX_RETRIES", "3"))
HTTP_TIMEOUT = float(os.getenv("SSQ_HTTP_TIMEOUT", "20"))

# 手动同步等待启动同步释放锁的最长秒数
SYNC_LOCK_WAIT = float(os.getenv("SSQ_SYNC_LOCK_WAIT", "5"))

API_PREFIX = "/api"
