# 双色球开奖数据同步与分析系统

本机 / 局域网使用的彩票数据分析工具：自动同步开奖数据 → 统计分析 → 策略选号 → 回测验证 → 形态可视化。
**不做 Docker、不对外网开放；彩票为独立随机事件，系统只做统计观察，不具备预测能力。**

## 功能

| 页面 | 内容 |
|------|------|
| 历史开奖 | 彩种切换、按期号/日期搜索、分页表格、红蓝球可视化 |
| 统计分析 | 红/蓝频次、当前遗漏热力图、冷热号、连号、奇偶/大小/三区比、和值与 AC 分布（30 / 100 / 全部） |
| 选号预测 | 5 个内置策略 + 自定义算法，生成 1–20 注，热号/冷号标记，一键复制 |
| 策略回测 | 滑动窗口回测全部策略，红球命中分布、奖级实际 vs 理论期望、卡方 p-value 结论 |
| 形态分析 | A–R 共 18 种几何映射算法清单（框架已就绪，均标记「开发中」） |
| 数据同步 | 各彩种状态卡片、手动同步、最近同步日志 |

## 技术栈

- 后端：Python 3.11+、FastAPI、SQLAlchemy 2.x、SQLite（WAL）、Pydantic v2、httpx、numpy
- 前端：React 18 + Vite 5 + TypeScript（strict），纯 CSS/SVG 图表，暗色主题，hash 路由

## 快速开始

前置：Python 3.11+、Node.js 18+。

```powershell
# Windows
.\run.ps1                 # 仅本机
.\run.ps1 -Lan            # 局域网可访问（0.0.0.0）
.\run.ps1 -NoBrowser      # 不自动打开浏览器
```

```bash
# Linux / macOS
chmod +x run.sh
./run.sh                  # 仅本机
LAN=1 ./run.sh            # 局域网可访问
```

脚本会自动安装依赖并启动：

- 前端 http://127.0.0.1:5173
- 后端 http://127.0.0.1:8000/api/health
- 接口文档 http://127.0.0.1:8000/docs
- 日志 `.run/backend.log`、`.run/frontend.log`，Ctrl+C 停止

手动启动（可选）：

```bash
cd backend && pip install -r requirements.txt && python -m uvicorn main:app --host 127.0.0.1 --port 8000
cd frontend && npm install && npm run dev
```

后端启动时会**自动同步一次全部彩种**（约几十秒，失败只记日志不影响使用）；也可在「数据同步」页手动触发。

## 配置（环境变量）

| 变量 | 默认 | 说明 |
|------|------|------|
| `SSQ_DB_PATH` | `backend/data/ssq.db` | SQLite 路径 |
| `AUTO_SYNC_ON_STARTUP` | `true` | 启动时是否自动同步 |
| `SSQ_SYNC_PAGE_SIZE` | `100` | 每页拉取条数 |
| `SSQ_SYNC_INTERVAL` | `0.5` | 请求间隔（秒，礼貌爬取） |
| `SSQ_SYNC_MAX_RETRIES` | `3` | 失败重试次数 |
| `SSQ_HTTP_TIMEOUT` | `20` | 单请求超时（秒） |

端口可用 `run.ps1 -BackendPort` / `-FrontendPort` 或 `BACKEND_PORT` / `FRONTEND_PORT` 覆盖。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查（库路径 + 条数） |
| GET | `/api/lotteries` | 彩种与球号规则 |
| GET | `/api/history?type=ssq&page=1&size=20&q=` | 历史开奖（`q` 支持期号/日期模糊搜索） |
| GET | `/api/history/latest?type=ssq` | 最新一期 |
| GET | `/api/status` | 各彩种同步状态 |
| POST | `/api/run` | 手动同步（可指定彩种） |
| GET | `/api/logs` | 最近同步日志 |
| GET | `/api/stats?type=ssq&range=30\|100\|all` | 统计分析 |
| GET | `/api/strategies` | 策略清单（内置 + 自定义） |
| POST | `/api/predict` | 生成号码：`{strategy,count,params}` |
| POST | `/api/backtest` | 回测：`{strategy,window,periods}` |
| GET | `/api/visualizers` | 可视化算法清单 |
| POST | `/api/visualizers/{name}/render` | 渲染图形（未实现返回 501） |
| POST | `/api/visualizers/{name}/features` | 提取图形特征（未实现返回 501） |

统一约定：未知彩种/策略 → 404；参数越界 → 400/422；算法内部异常 → 500 并附堆栈。

## 自定义算法

把 `.py` 文件放进 `backend/app/custom_algorithm/` 即可自动注册（下划线开头的文件会被跳过）。
完整接口文档与两个可运行示例见 [backend/app/custom_algorithm/README.md](backend/app/custom_algorithm/README.md)。

```python
from app.strategies.base import BaseStrategy, ball_params

class MyAlgorithm(BaseStrategy):
    name = "my_algo"
    description = "我的算法"

    def generate(self, history, count=1, **params):
        cfg = ball_params(params)
        ...
        return [[*reds, blue] for _ in range(count)]  # 每注 [r1..r6, b]
```

## 测试

```bash
cd backend
python -m pytest -p no:terminal        # 全部后端测试
cd ../frontend
npm run build                          # tsc --noEmit + vite build
npm run test:e2e                       # Playwright 端到端（首次需先执行 npx playwright install chromium）
```

e2e 说明：`frontend/playwright.config.ts` 会自动启动后端（8000）与前端（5173）。
后端使用由真实库复制出的隔离副本 `frontend/e2e/.tmp/e2e.db`，并关闭启动自动同步，
不访问外网、不改动真实开奖库；覆盖 6 个页面渲染、历史搜索/翻页、选号、回测、
形态清单、API 契约与 375px 移动端溢出检查。

## 目录结构

```
backend/
  main.py                  FastAPI 入口（启动自动同步）
  app/
    config.py  db.py  models.py  schemas.py
    sync_engine.py         同步引擎（校验 + UPSERT + 日志）
    fetchers/              各彩种数据适配器
    analyzer.py            统计（频次/遗漏/冷热/结构/和值/AC）
    backtest.py            滑动窗口回测 + 卡方检验
    strategies/            内置策略 + 自动注册（base/registry/builtin）
    visualizers/           可视化框架（A–R 占位）
    custom_algorithm/      用户自有算法目录（README + 两个示例）
    api/                   health/history/sync/stats/predict/backtest/visualizers
  tests/                   79+ 项单元测试
frontend/
  src/pages/               History / Stats / Predict / Backtest / Visualizer / Sync
  src/components/          Ball / BarChart / Heatmap / DistributionBars
run.ps1  run.sh
```

## 说明与限制

- 数据源为公开开奖信息，同步失败不影响已有数据；建议低频同步。
- 目前实抓彩种为双色球，大乐透适配器为预留实现。
- 形态分析 A–R 为后补插件，当前仅提供框架与清单（`planned`），前端显示「开发中」。
- **免责声明**：本系统仅用于统计分析与算法实验，不构成购彩建议；任何选号策略的中奖概率都与纯随机等价。
