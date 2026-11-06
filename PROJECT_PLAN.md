# 彩票开奖数据同步与分析系统 · 项目计划书

> 项目代号：`ssq-predictor`（首期落地双色球，架构预留多彩种扩展）
> 状态：待确认
> 日期：2026-11-06
>
> 📄 **配套文档**：
> - [页面设计书 PAGE_DESIGN.html](./PAGE_DESIGN.html)（页面分类、布局结构、组件清单、交互规范）
> - [可视化算法说明手册 ALGORITHM_GUIDE.html](./ALGORITHM_GUIDE.html)（A–R 算法大白话讲解 + 号码示例）

---

## 0. 免责声明（必须置顶）

**彩票开奖是真随机独立事件，不存在可预测规律。**

本系统定位是 **开奖数据同步 + 统计分析 + 策略选号工具**，不是"中奖预测器"。所有内置策略的长期收益率在数学上等价于纯随机。系统内置回测模块会**诚实展示这一事实**，不做任何中奖保证。

用户自有算法（见第 7 节）由用户自行实现，本系统只提供接入契约，不对其效果做任何背书。

---

## 1. 项目目标

1. **数据同步引擎**：从外部数据源拉取开奖结果，**存到本地 SQLite**。首期支持双色球，后续可扩展大乐透、排列3/5、快乐8、福彩3D 等其他玩法
2. 采集 2003 年至今全部双色球开奖数据（约 3000 期）
3. 提供多维度统计分析（频次、冷热、遗漏、奇偶、大小、区间、和值等）
4. 提供多种**选号策略**（随机/热号/冷号/均衡/混合），并暴露统一接口
5. 预留**用户自有算法插件位**——用户可把自己的算法以 Python 类形式放入指定目录，系统自动加载并暴露给 API/前端
6. 提供**回测引擎**：用历史数据滑动模拟各策略命中率，与随机基线对比，输出统计显著性
7. 提供 **Web 页面**：历史查询、统计图表、选号、回测结果可视化、**同步状态与手动触发**

**不做**：任何形式的"AI 预测中奖号"、"深度学习选号"、付费开奖号等噱头。

---

## 2. 双色球规则速查

| 项 | 规则 |
|---|---|
| 红球 | 6 个，从 **01–33** 中选，不重复 |
| 蓝球 | 1 个，从 **01–16** 中选 |
| 开奖频率 | 每周二、四、日 21:15（约 150 期/年） |
| 历史跨度 | 2003 年第 1 期至今，约 3000 期 |
| 期号格式 | `YYYYNNN`（如 `2024001`） |

---

## 2.1 数据同步引擎（新增，支持多彩种扩展）

### 设计目标

- **统一入库**：所有彩种的开奖结果存到同一张 `draws` 表，用 `lottery_type` 字段区分
- **适配器模式**：每个彩种实现一个 `Fetcher` 类，负责"从外部源拉取 → 解析成统一结构"
- **增量同步**：只拉取本地缺失的期号，不重复全量拉取
- **启动自动 + 手动触发**：应用（后端）启动时自动同步一次全部已注册彩种；前端「数据同步」页随时可手动触发；定时任务（可选，P2 之后）
- **可追溯**：记录每次同步的时间、新增条数、失败信息

### 同步流程

```
┌──────────────────────────────────────────────────────┐
│  SyncEngine (统一调度)                                │
│                                                      │
│  1. 读取目标彩种最后一期号 (DB)                        │
│  2. 找到对应 Fetcher 适配器                            │
│  3. 调用 fetcher.fetch(since=last_issue)              │
│  4. 校验每条记录 (红球范围/不重复/蓝球范围)            │
│  5. UPSERT 到 draws 表 (按 lottery_type+issue 去重)   │
│  6. 记录 sync_log                                     │
└──────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ SSQFetcher       │  │ DLTFetcher       │  │ ...Fetcher       │
│ (双色球-体彩网)   │  │ (大乐透-待实现)   │  │ (新彩种只需继承)  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Fetcher 基类契约

```python
class BaseFetcher(ABC):
    lottery_type: str              # 彩种唯一标识，如 "ssq", "dlt"
    name: str                      # 中文名，如 "双色球"
    ball_config: BallConfig        # 红球范围/个数、蓝球范围/个数

    @abstractmethod
    def fetch(self, since: str | None = None) -> list[RawDraw]:
        """拉取 since 期号之后的所有开奖记录"""

    @abstractmethod
    def fetch_latest(self) -> RawDraw | None:
        """拉取最新一期（用于快速校验数据源是否可用）"""
```

### 统一数据结构 `RawDraw`

```python
@dataclass
class RawDraw:
    lottery_type: str       # "ssq"
    issue: str              # "2024001"
    draw_date: date
    reds: list[int]         # [3, 11, 17, 22, 28, 33]
    blues: list[int]        # [9]          （多蓝球彩种支持多个）
    sales_amount: int | None
    pool_balance: int | None
    prize_details: dict | None   # 各奖级注数/奖金
```

### 扩展新彩种的步骤（用户/开发者）

1. 在 `app/fetchers/` 下新建 `xxx_fetcher.py`
2. 继承 `BaseFetcher`，实现 `fetch` 和 `fetch_latest`
3. 在 `fetchers/__init__.py` 注册
4. （可选）在 `BallConfig` 里配置球号规则
5. 前端无需改动——`/api/sync/status` 和 `/api/sync/run` 自动支持

### 同步状态记录表 `sync_log`

| 字段 | 说明 |
|------|------|
| id | 主键 |
| lottery_type | 彩种 |
| started_at | 同步开始时间 |
| finished_at | 结束时间 |
| status | success / failed / partial |
| fetched_count | 拉取条数 |
| inserted_count | 新增入库条数 |
| error_msg | 失败信息（若有） |

### 数据同步相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sync/status` | 各彩种同步状态（最新期号、总条数、上次同步时间） |
| POST | `/api/sync/run?type=ssq` | 手动触发指定彩种同步（不传则同步全部已注册彩种） |
| GET | `/api/sync/logs?type=ssq&limit=20` | 同步历史日志 |

### 启动自动同步（P1 必做）

- 后端在 FastAPI `startup` 事件里触发一次后台同步：`asyncio.create_task(sync_all())`
- 不阻塞启动：接口先可用，同步在后台跑，前端「数据同步」页轮询状态即可看到进度
- 开关：环境变量 `AUTO_SYNC_ON_STARTUP=true|false`（默认 true）
- 失败处理：启动同步失败只写 `sync_log`，不让应用启动失败；用户可手动重试
- 幂等：与手动同步共用同一把「彩种级互斥锁」，避免启动同步与手动同步并发写库

### 定时同步（可选，P2 之后）

- 用 `APScheduler` 或简单 `threading.Timer`
- 双色球每周二/四/日 21:30 自动拉取最新一期
- 可通过配置开关启用/禁用

---

## 3. 技术架构

```
┌─────────────────────────────────────────────────┐
│  浏览器  (React + TS + Vite)                     │
│  历史 / 统计 / 选号 / 回测  四个页面              │
└───────────────────────┬─────────────────────────┘
                        │  REST API (JSON)
┌───────────────────────▼─────────────────────────┐
│  后端  (Python + FastAPI)                        │
│  ┌──────────┬──────────┬──────────┬──────────┐   │
│  │ history  │ stats    │ predict  │ backtest │   │
│  │ 历史查询  │ 统计分析  │ 选号策略  │ 回测引擎  │   │
│  └──────────┴──────────┴──────────┴──────────┘   │
│  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ strategies/      │  │ custom_algorithm/    │  │
│  │ 内置策略（5种）   │  │ 用户自有算法（插件位） │  │
│  └──────────────────┘  └──────────────────────┘  │
└───────────────────────┬─────────────────────────┘
                        │  SQLAlchemy
┌───────────────────────▼─────────────────────────┐
│  SQLite  (data/ssq.db)                           │
│  表: draws (期号, 日期, 红球1-6, 蓝球, 销售额…)  │
└─────────────────────────────────────────────────┘
```

**选型理由**：
- **FastAPI**：异步、自带 Swagger 文档、Pydantic 校验，适合快速开发数据接口
- **SQLite**：数据量小（3000 行），零运维，单文件便携
- **React + Vite**：项目所在环境已有成熟 Vite 工具链（参考 k8sTest/frontend），上手快
- **Python 插件**：用户自有算法用 Python 写最自然，动态加载成本低

---

## 4. 目录结构

```
ssq-predictor/
├── PROJECT_PLAN.md              ← 本文档
├── README.md                    ← 项目说明（实施后写）
├── .gitignore
│
├── backend/
│   ├── main.py                  ← FastAPI 入口
│   ├── requirements.txt
│   ├── run.ps1 / run.sh         ← 一键启动脚本
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py            ← 配置（数据源、DB 路径、端口）
│   │   ├── db.py                ← SQLAlchemy 引擎 + Session
│   │   ├── models.py            ← Draw / SyncLog ORM 模型
│   │   ├── schemas.py           ← Pydantic 请求/响应模型
│   │   │
│   │   ├── sync_engine.py       ← ★ 同步引擎（统一调度 + 校验 + UPSERT）★
│   │   ├── fetchers/            ← ★ 各彩种数据适配器 ★
│   │   │   ├── __init__.py      ← Fetcher 注册表
│   │   │   ├── base.py          ← BaseFetcher 抽象基类 + RawDraw + BallConfig
│   │   │   ├── ssq_fetcher.py   ← 双色球（体彩网）
│   │   │   └── dlt_fetcher.py   ← 大乐透（预留，可空实现）
│   │   │
│   │   ├── fetch_history.py     ← 旧名保留，内部委托给 sync_engine
│   │   ├── analyzer.py          ← 统计分析（频次/冷热/遗漏/奇偶…）
│   │   ├── backtest.py          ← 回测引擎
│   │   │
│   │   ├── strategies/          ← 内置选号策略
│   │   │   ├── __init__.py
│   │   │   ├── base.py          ← BaseStrategy 抽象基类
│   │   │   ├── random_strategy.py
│   │   │   ├── hot_strategy.py
│   │   │   ├── cold_strategy.py
│   │   │   ├── balanced_strategy.py
│   │   │   ├── mixed_strategy.py
│   │   │   └── registry.py      ← 策略注册表（自动发现）
│   │   │
│   │   ├── custom_algorithm/    ← ★ 用户自有算法插件位 ★
│   │   │   ├── __init__.py
│   │   │   └── README.md        ← 接口契约 + 示例（用户在这里放算法）
│   │   │
│   │   ├── visualizers/         ← ★ 形态分析可视化引擎（全部后补）★
│   │   │   ├── __init__.py
│   │   │   ├── base.py          ← BaseVisualizer + VisualizationData
│   │   │   ├── registry.py      ← 自动注册（含 A-R 全部占位）
│   │   │   └── *_visualizer.py  ← 逐个按需实现（G/J/Q/M…）
│   │   │
│   │   └── api/                 ← 路由层
│   │       ├── __init__.py
│   │       ├── history.py
│   │       ├── stats.py
│   │       ├── predict.py
│   │       ├── backtest.py
│   │       ├── visualizers.py   ← 可视化算法列表/运行/特征
│   │       └── sync.py            ← 同步状态/触发/日志
│   │
│   ├── data/
│   │   └── ssq.db               ← SQLite 数据文件（gitignore）
│   │
│   └── tests/
│       ├── test_fetch.py
│       ├── test_sync_engine.py
│       ├── test_analyzer.py
│       ├── test_strategies.py
│       ├── test_visualizers.py
│       └── test_backtest.py
│
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/
        │   └── client.ts         ← axios 封装
        ├── pages/
        │   ├── HistoryPage.tsx   ← 历史开奖列表 + 球号
        │   ├── StatsPage.tsx     ← 统计图表
        │   ├── PredictPage.tsx   ← 选号 + 策略选择
        │   ├── BacktestPage.tsx  ← 回测结果可视化
        │   └── SyncPage.tsx      ← 数据同步状态 + 手动触发 + 日志
        │   └── VisualizerPage.tsx ← 形态分析（算法清单+2D/3D渲染+特征导出）
        ├── components/
        │   ├── Ball.tsx          ← 单个球号组件
        │   ├── NumberMatrix.tsx  ← 33×16 球盘
        │   └── ...
        └── styles/
```

---

## 5. 核心模块详细设计

### 5.1 数据同步引擎 (`sync_engine.py` + `fetchers/`)

> `fetch_history.py` 保留为兼容入口，内部委托给 `SyncEngine`。

**双色球数据源**：中国体彩网公开接口

```
GET https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry
    ?gameNo=85          # 85 = 双色球
    &provinceId=0
    &pageSize=100
    &isVerify=1
    &pageNo={n}
```

返回 JSON，字段含：`lotteryDrawNum`(期号)、`lotteryDrawTime`(日期)、`lotteryDrawResult`(红球蓝球空格分隔)、`lotterySaleAmount`(销售额)、`poolBalanceAfterdraw`(奖池)、`prizeLevelList`(各奖级)。

**SyncEngine 统一流程**（对所有彩种一致）：
1. 读 DB 中该彩种最后一期号 → 作为增量起点；空表则 `since=None` 全量拉取
2. 从 `fetchers` 注册表拿到对应 `Fetcher`，调用 `fetcher.fetch(since=last_issue)`
3. 对每条 `RawDraw` 做**球号合法性校验**（红球范围/不重复/个数、蓝球范围/个数）—— 不合法则跳过并记录
4. `UPSERT` 到 `draws` 表（按 `lottery_type + issue` 联合主键去重，**绝不 DROP 表**）
5. 写 `sync_log`：开始/结束时间、拉取条数、入库条数、状态、错误信息
6. 返回统计：新增 N 期，最新期号 xxx

**采集规范**：
- 分页拉取，每页 100 条，请求间隔 ≥ 0.5s（礼貌爬取）
- 失败重试 3 次，记录失败页号到 `sync_log.error_msg`
- 校验失败的单条记录不影响其他记录入库

### 5.2 统计分析 (`analyzer.py`)

输入：近期开奖记录列表（可指定窗口 N=30/100/全部）

输出维度：

| 维度 | 说明 |
|------|------|
| 红球频次 | 01–33 各出现次数 |
| 蓝球频次 | 01–16 各出现次数 |
| 冷热号 | 近 N 期频次降序 Top/Bottom |
| 遗漏值 | 每个号距上次出现的期数 |
| 连号 | 相邻号同现的次数（如 01-02, 07-08） |
| 奇偶比 | 每期红球奇偶比分布（如 3:3, 4:2） |
| 大小比 | 红球 ≤16 为小、>16 为大 |
| 和值 | 6 个红球之和的分布区间 |
| 区间比 | 三区间 (1-11 / 12-22 / 23-33) 个数比 |
| AC 值 | 算术复杂度（号码复杂度指标） |

所有统计输出标准化 JSON，供前端图表渲染。

### 5.3 选号策略 (`strategies/`)

**基类 `BaseStrategy`**：

```python
class BaseStrategy(ABC):
    name: str          # 策略唯一标识
    description: str   # 前端展示说明

    @abstractmethod
    def generate(self, history: list[Draw], count: int = 1, **params) -> list[list[int]]:
        """返回 count 注号码，每注为 [r1,r2,r3,r4,r5,r6, b]，红球升序"""
```

**内置策略**：

| 策略 | 逻辑 |
|------|------|
| `random` | 纯随机（基线） |
| `hot` | 按近 N 期频次加权抽样红球/蓝球 |
| `cold` | 按遗漏值加权（遗漏越久权重越高） |
| `balanced` | 强制奇偶 3:3、大小 3:3、区间 2:2:2，再随机 |
| `mixed` | 以上策略各出一部分再合并去重 |

所有策略保证：红球 6 个不重复升序，蓝球 1 个，结果合法。

### 5.4 形态分析可视化引擎 (`visualizers/`)

> 把往期号码作为数学变换的输入参数，生成非常规 2D/3D 图形，再从图形特征反推号码规律。
> **所有算法均为"后补插件"**：首期只搭框架 + 页面标记"待实现"，逐个按需落地。
> 能用 3D（Three.js）就用 3D，图形特征按需对接用户自定义算法。

#### 5.4.1 架构

```python
class BaseVisualizer(ABC):
    name: str              # 唯一标识
    title: str             # 中文名（前端展示）
    category: str          # "spiral" | "collapse" | "expand" | "combo"
    dimension: int         # 2 or 3
    status: str            # "implemented" | "planned"（页面据此标记）
    description: str

    @abstractmethod
    def render(self, draws: list[Draw], **params) -> VisualizationData:
        """输入若干期开奖，输出图形数据"""

    def extract_features(self, data: VisualizationData) -> dict:
        """从图形中提取特征（面积/质心/收敛点等），可喂给自定义算法。
        默认返回 {}，子类按需覆盖。"""
        return {}
```

**统一数据结构 `VisualizationData`**：
```python
@dataclass
class VisualizationData:
    type: str          # "curve_2d" | "points_3d" | "mesh" | "graph" | "trajectory"
    data: dict         # 具体几何数据（点坐标、边、面等）
    metadata: dict     # 渲染参数（颜色映射、动画配置等）
```

前端「形态分析」页：
- 列出所有 visualizer，已实现的可点击运行，**待实现的显示"开发中"标记**
- 运行后展示图形（2D Canvas / 3D Three.js）
- 显示提取到的图形特征，可一键复制为自定义算法的输入参数

#### 5.4.2 可视化算法清单（全部后补，按需实现）

| 编号 | 名称 | 类别 | 维度 | 核心映射 | 状态 |
|------|------|------|------|----------|------|
| A | 傅里叶闭合曲线 | 频域 | 2D | 红球=谐波振幅，蓝球=相位 | 待实现 |
| B | Lissajous 图形 | 频域 | 2D | 红球两两配对为 x/y 频率 | 待实现 |
| C | 3D 时空轨迹 | 轨迹 | 3D | 6红球→3个3D点，蓝球=颜色 | 待实现 |
| D | 球面调和变形球 | 频域 | 3D | 红球=球谐系数 | 待实现 |
| E | 混沌吸引子 | 动力系统 | 3D | 号码=初值，迭代洛伦兹等 | 待实现 |
| F | 共现网络图 | 图论 | 2D | 号码=节点，同现=边 | 待实现 |
| G | 螺旋骨架傅里叶 | 螺旋 | 2D/3D | 红球=螺旋上谐波振幅，蓝球=紧密度 | 待实现 |
| H | 极坐标傅里叶玫瑰 | 螺旋 | 2D | 红球=r(θ)傅里叶系数 | 待实现 |
| I | 斐波那契螺旋点阵 | 螺旋 | 2D/3D | 号码=黄金角分布的径向距离 | 待实现 |
| J | 引力坍缩轨迹 | 塌陷 | 2D/3D | 红球=质点质量，蓝球=引力常数 | 待实现 |
| K | 吸引子盆地塌缩 | 塌陷 | 3D | 号码=动力系统初值，看塌缩路径 | 待实现 |
| L | 多边形塌缩 | 塌陷 | 2D | 红球=六边形顶点半径，蓝球=衰减系数 | 待实现 |
| M | 呼吸球面 | 伸展收缩 | 3D | 红球=球谐系数，球面周期膨胀收缩 | 待实现 |
| N | 形态渐变(Homotopy) | 伸展收缩 | 2D/3D | 从上期形状连续形变为本期 | 待实现 |
| O | 形态学膨胀/腐蚀 | 伸展收缩 | 2D | 号码=二值点集，迭代膨胀腐蚀 | 待实现 |
| P | 螺旋呼吸叠加 | 组合 | 2D/3D | 多期螺旋波叠加干涉 | 待实现 |
| Q | 螺旋塌缩吸引子 | 组合 | 3D | 螺旋骨架+动力系统，收敛点可作算法输入 | 待实现 |
| R | 呼吸螺旋点云 | 组合 | 3D | 斐波那契点阵+呼吸缩放 | 待实现 |

#### 5.4.3 图形特征 → 自定义算法（按需打通）

每个 visualizer 的 `extract_features()` 可输出结构化特征，例如：

| 算法 | 可提取特征 | 可作自定义算法输入 |
|------|------------|-------------------|
| G 螺旋傅里叶 | 曲线面积、质心、自交点数、振幅包络 | ✅ |
| J 引力坍缩 | 坍缩时间、收敛点坐标、残余角动量 | ✅ 收敛点 |
| K 吸引子盆地 | 盆地编号、收敛耗时、螺旋圈数 | ✅ 盆地编号 |
| Q 螺旋塌缩 | 收敛点坐标、收缩速率、螺旋圈数 | ✅ 收敛点 |
| M 呼吸球面 | 呼吸振幅、对称破缺方向 | ✅ |

前端提供"导出特征 JSON"按钮，用户可直接粘进自定义算法。

#### 5.4.4 Three.js 实现约束（来自经验）

- 优先**本地 three.module.js + importmap**，避免 CDN/控制器依赖导致 404
- 控制器缺失时自实现球坐标相机（theta/phi/distance）完成拖拽旋转+滚轮缩放
- 默认**静态立体 + 轻交互**（拖拽/点按），不加粒子/自动旋转等动效，除非确认
- 保留 2D Canvas 回退开关（容器切换），3D 不认可可快速回退

---

### 5.5 回测引擎 (`backtest.py`)

**方法**：滑动窗口

```
for i in range(window, len(history)):
    train = history[i-window : i]      # 训练窗口
    actual = history[i]                 # 实际开奖
    preds = strategy.generate(train, count=1)
    score = compare(preds[0], actual)   # 中红球数、是否中蓝球
```

**输出指标**：
- 命中红球数分布（0–6 的频次）
- 命中蓝球概率
- 各奖级理论命中率 vs 实际
- 与 `random` 基线的**卡方检验 p-value**（若 p > 0.05，证明该策略与随机无显著差异——这正是诚实展示的核心）

**诚实性硬约束**：回测页必须显示 p-value 结论，不允许隐藏"策略≈随机"的事实。

### 5.6 API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/lotteries` | 已注册彩种列表（含球号规则） |
| GET | `/api/history?type=ssq&page=1&size=50` | 历史开奖（分页，按期号降序） |
| GET | `/api/history/latest?type=ssq` | 最新一期 |
| GET | `/api/stats?type=ssq&range=30` | 统计数据（range=30/100/all） |
| GET | `/api/strategies` | 可用策略列表（含用户自有） |
| POST | `/api/predict` | 选号：`{strategy, count, params}` |
| POST | `/api/backtest` | 回测：`{strategy, window, periods}` |
| **GET** | **`/api/sync/status`** | **各彩种同步状态（最新期号、总条数、上次同步时间）** |
| **POST** | **`/api/sync/run?type=ssq`** | **手动触发同步（不传 type 则同步全部已注册彩种）** |
| **GET** | **`/api/sync/logs?type=ssq&limit=20`** | **同步历史日志** |
| GET | `/api/visualizers` | 可视化算法清单（含 status: implemented/planned） |
| POST | `/api/visualizers/{name}/render` | 运行指定可视化算法，输入若干期号范围，返回图形数据 |
| POST | `/api/visualizers/{name}/features` | 运行并提取图形特征（可作自定义算法输入） |

> 所有涉及彩种的接口都带 `type` 参数，默认 `ssq`。旧的 `/api/fetch` 保留为 `/api/sync/run?type=ssq` 的别名。

**选号响应示例**：
```json
{
  "strategy": "balanced",
  "count": 5,
  "numbers": [
    {"red": [3, 11, 17, 22, 28, 33], "blue": 9},
    ...
  ],
  "disclaimer": "本结果为统计选号，中奖概率与纯随机等价"
}
```

**同步状态响应示例**：
```json
{
  "lotteries": [
    {
      "type": "ssq",
      "name": "双色球",
      "latest_issue": "2024120",
      "latest_date": "2024-10-15",
      "total_count": 3120,
      "last_sync_at": "2024-10-15T21:35:02",
      "last_sync_status": "success"
    }
  ]
}
```

### 5.7 前端页面

| 页面 | 内容 |
|------|------|
| **历史开奖** | 表格 + 每期红球蓝球可视化球号；支持按期号/日期搜索；顶部彩种切换下拉 |
| **统计分析** | 频次柱状图、遗漏热力图、奇偶/大小/区间饼图；可选 30/100/全部窗口 |
| **选号预测** | 策略下拉（含用户自有算法）→ 生成 N 注 → 球号展示 + 冷热标记；显眼免责声明 |
| **回测** | 策略对比柱状图 + p-value 结论 + "策略与随机无显著差异"提示 |
| **形态分析** | 可视化算法清单（已实现/待实现标记）→ 运行展示 2D/3D 图形 → 提取图形特征 → 可导出为自定义算法输入 |
| **数据同步** | 各彩种同步状态卡片（最新期号/总条数/上次同步时间）+ 手动同步按钮 + 最近同步日志表格 |

视觉风格沿用项目现有暗色主题（参考 k8sTest 的 CSS 变量体系），保持一致性。

---

## 6. 用户自有算法插件接口（重点）

用户将算法实现放在 `backend/app/custom_algorithm/` 目录下。

### 6.1 接口契约

用户只需创建一个 `.py` 文件，继承 `BaseStrategy` 并实现 `generate`：

```python
# backend/app/custom_algorithm/my_algo.py
from app.strategies.base import BaseStrategy
from app.models import Draw

class MyAlgorithm(BaseStrategy):
    name = "my_algo"
    description = "我的独门算法（用户自实现）"

    def generate(self, history: list[Draw], count: int = 1, **params):
        # 用户在这里写自己的逻辑
        # history 是历史开奖记录，每条含 reds:list[int], blue:int
        # 返回 list[list[int]]，每注 [r1..r6, b]，红球升序不重复
        ...
        return [[1, 2, 3, 4, 5, 6, 7]]
```

### 6.2 自动加载机制

- 应用启动时，`registry.py` 扫描 `custom_algorithm/` 下所有 `.py` 文件
- 用 `importlib` 动态导入，发现所有 `BaseStrategy` 子类
- 自动注册到策略表，前端 `/api/strategies` 可看到，`/api/predict?strategy=my_algo` 可调用
- 用户改完算法文件，重启后端即生效（或提供热重载开关）

### 6.3 隔离与安全

- 用户算法与内置策略**同基类、同校验**：返回结果必须通过红球/蓝球合法性校验，否则报错不崩溃
- 用户算法异常被 try/except 捕获，返回 500 + 堆栈给前端，不影响其他策略
- 不限制用户算法的复杂度，但约定 `generate` 单次调用 < 5s（前端有超时）

### 6.4 我会交付的内容

- `custom_algorithm/__init__.py`（空）
- `custom_algorithm/README.md`：完整接口文档 + 两个示例（随机示例、基于历史频次的简单示例）
- 自动加载 + 校验逻辑
- 用户**不需要**我改任何核心代码，只需往里放 `.py` 文件

---

## 7. 数据模型 (`models.py`)

### 7.1 开奖结果表 `draws`（支持多彩种）

```python
class Draw(Base):
    __tablename__ = "draws"
    # 联合主键：彩种 + 期号（不同彩种期号可能重复）
    lottery_type = Column(String(10), primary_key=True)   # "ssq" / "dlt" / ...
    issue        = Column(String(20), primary_key=True)   # 期号 2024001
    draw_date    = Column(Date, index=True)
    red1..red6   = Column(Integer)                         # 红球（最多 6 个，多余彩种可留空）
    blue         = Column(Integer)                         # 蓝球（单蓝球彩种）
    # 多蓝球彩种（如大乐透后区 2 个）用 JSON 字段扩展
    extra_blues  = Column(JSON, nullable=True)             # 多蓝球时存 [b1, b2]
    sales_amount = Column(BigInteger, nullable=True)       # 销售额
    pool_balance = Column(BigInteger, nullable=True)       # 奖池
    prize1_count = Column(Integer, nullable=True)          # 一等奖注数
    prize_details= Column(JSON, nullable=True)             # 各奖级明细
    created_at   = Column(DateTime, default=datetime.utcnow)
```

### 7.2 同步日志表 `sync_log`

```python
class SyncLog(Base):
    __tablename__ = "sync_log"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    lottery_type  = Column(String(10), index=True)
    started_at    = Column(DateTime, default=datetime.utcnow)
    finished_at   = Column(DateTime, nullable=True)
    status        = Column(String(20))    # success / failed / partial
    fetched_count = Column(Integer, default=0)
    inserted_count= Column(Integer, default=0)
    error_msg     = Column(Text, nullable=True)
```

### 7.3 彩种配置表 `lottery_config`（可选）

存各彩种的球号规则，前端可动态读取（不硬编码双色球规则）：

```python
class LotteryConfig(Base):
    __tablename__ = "lottery_config"
    lottery_type = Column(String(10), primary_key=True)
    name         = Column(String(50))      # "双色球"
    red_count    = Column(Integer)         # 6
    red_min      = Column(Integer)         # 1
    red_max      = Column(Integer)         # 33
    blue_count   = Column(Integer)         # 1
    blue_min     = Column(Integer)         # 1
    blue_max     = Column(Integer)         # 16
    enabled      = Column(Boolean, default=True)
```

---

## 8. 实施步骤

| 阶段 | 内容 | 预计 |
|------|------|------|
| **P1** | 后端骨架 + DB + **同步引擎 + 双色球 Fetcher**（跑通 3000 期入库） | — |
| **P2** | 统计分析模块 + API + 前端历史/统计页 + 同步状态页 | — |
| **P3** | 选号策略 + 自动注册 + 前端选号页 | — |
| **P4** | 用户自有算法插件位 + 接口文档 + 示例 | — |
| **P5** | 回测引擎 + 前端回测页（含 p-value 展示） | — |
| **P6** | **可视化引擎框架**：BaseVisualizer + 注册表（A–R 全部占位为 planned）+ 前端形态分析页（清单展示，全部标记"待实现"） | — |
| **P7** | 测试、启动脚本、README、联调收尾 | — |
| **后续** | 按需逐个实现 visualizer（G/J/Q/M…），每实现一个跑通正确性测试再标记 implemented | — |

---

## 9. 性能与视觉优化原则

> 优先级：**性能 > 精确性/准确度 > 精致视觉**。三者都要，不牺牲前者换后者。

### 9.1 后端性能

| 优化项 | 措施 |
|--------|------|
| DB 查询 | `draws` 表按 `lottery_type + issue` 建联合主键索引；`draw_date` 建索引；统计查询用聚合 SQL 而非 Python 全量扫描 |
| 统计缓存 | 频次/遗漏等统计结果按 `(lottery_type, range)` 缓存到内存（LRU），开奖更新时失效，避免每次请求重算 3000 期 |
| 分页 | 历史列表强制分页（默认 50 条/页），禁止一次返回全量 |
| 异步 | 数据同步、回测等长耗时操作用 FastAPI `BackgroundTasks` 或独立线程，不阻塞 API |
| 连接池 | SQLAlchemy `QueuePool`，避免每次请求新建连接 |

### 9.2 前端性能

| 优化项 | 措施 |
|--------|------|
| 按需加载 | 可视化页面懒加载 Three.js（仅进入「形态分析」页时引入），首屏不加载 3D 库 |
| DPR 钳制 | Three.js `renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))`，高 DPR 设备不放大像素填充成本 |
| LOD | 3D 场景中几何体按距离切换细分精度（近处精细、远处简化） |
| 视锥剔除 | Three.js 默认开启 `frustumCulled`，不可见对象不渲染 |
| Draw Call | 合并相同材质几何体（`BufferGeometryUtils.mergeGeometries`），减少 draw call |
| 动画节流 | 渲染循环用 `requestAnimationFrame`；非交互时暂停渲染（`needsRender` 标志），不持续空转 |
| FPS 监控 | 开发模式显示 FPS / Draw Call / DPR，便于针对性降级 |
| 虚拟化 | 历史开奖长列表用虚拟滚动（react-window），3000 期不一次性渲染 DOM |

### 9.3 精确性与数值稳定性

- 所有浮点计算统一用 `numpy`（底层 BLAS，精度与性能兼顾）
- 累加类计算（如频次、面积）用 `math.fsum` 或 Kahan 求和，减少浮点误差累积
- 可视化算法的数值范围做归一化，避免大数相乘导致精度丢失
- 详见 §11 算法正确性验证

### 9.4 视觉表现（精致但克制）

**整体风格**：暗色主题（沿用 k8sTest 色系），玻璃拟态卡片，柔和渐变，统一间距与圆角。

**3D 视觉**：
- PBR 材质（`MeshStandardMaterial`）+ 正确色彩空间（`THREE.SRGBColorSpace`）
- 环境光 + 主方向光 + 半球光的标准三点布光，避免死黑或过曝
- 抗锯齿（`antialias: true`），仅在必要对象开阴影（控制 shadow map 尺寸 1024~2048）
- 背景用渐变天空盒或纯色，不堆砌粒子/滤镜
- 默认**静态立体 + 轻交互**（OrbitControls 拖拽旋转 + 滚轮缩放 + 阻尼），不加自动旋转/粒子特效

**2D 视觉**：
- Canvas 2D 用 `devicePixelRatio` 适配高分屏，线条抗锯齿
- 球号用径向渐变模拟立体感，红蓝双色区分
- 图表（ECharts / Chart.js）配色与主题统一，动画克制

**排版**：
- 字号梯度清晰（标题 20-32px / 正文 13-15px / 辅助 12px）
- 代码/期号用等宽字体
- 所有交互元素有 hover / active 状态反馈

**加载态**：
- 骨架屏替代空白加载
- 数据同步、可视化渲染等长操作显示进度条

---

## 10. 待确认事项

### ✅ 已确认

- **可视化算法**：A–R 全部为"后补插件"，首期只搭框架 + 页面标记"待实现"，逐个按需落地
- **图形特征对接自定义算法**：按需打通（visualizer 的 `extract_features()` 输出结构化特征）
- **2D/3D**：能用 3D（Three.js）就用 3D，默认静态立体 + 轻交互，不加粒子/自动旋转

### ❓ 待确认

1. **数据源**：双色球用体彩网 `webapi.sporttery.cn` 接口（推荐，返回 JSON 好解析）。是否接受？或你有其他数据源？
2. **后续彩种数据源**：大乐透/排列3/5/快乐8 等，是否也走体彩网接口（gameNo 不同），还是你有指定的其他源？
3. ~~**定时同步**~~ **已明确**：后端启动时自动同步一次全部彩种（不阻塞启动）+ 前端手动触发；定时任务（每周 21:30）放 P2 之后
4. **前端端口**：默认 Vite `5173`，后端 FastAPI `8000`，是否 OK？
5. ~~**启动方式**~~ **已明确**：只用 `run.ps1`/`run.sh` 一键启动，**不做 Docker 化**
6. **用户自有算法**：是否需要我在交付时预埋一个**可运行的示例算法**供你参考改写？还是只给空目录 + 文档？
7. **回测默认窗口**：默认用近 100 期做训练、回测最近 500 期，是否合适？
8. **暗色主题**：是否沿用 k8sTest 的暗色风格，还是换亮色？

---

## 11. 算法正确性验证（硬约束，不允许出错）

> 本项目中所有数学变换、统计计算、可视化算法，**必须通过可证伪的自动化测试**才能合入。不允许"看起来对"、"肉眼验证"、"大概差不多"。

### 11.1 验证原则

1. **每个算法配 `known-good` 用例**：用解析解或第三方权威库（numpy/scipy/sympy）作为基准，逐数值比对
2. **属性测试（property-based）**：验证数学恒等式（如傅里叶正逆变换互逆、螺旋半径公式单调）
3. **边界用例**：全 0、全相同号码、最大/最小边界值、空输入
4. **数值容差**：浮点比对使用 `np.isclose`（rtol=1e-9, atol=1e-12），不做模糊判断
5. **CI 强制**：所有 `tests/` 用例在提交前必须全绿，否则禁止合入

### 11.2 各模块验证清单

#### 数据同步与解析

| 测试项 | 验证方法 |
|--------|----------|
| 期号解析 | 固定 JSON → 断言期号、日期、红篮球完全匹配 |
| 球号合法性校验 | 构造红球重复/越界/个数错误、蓝球越界 → 断言被拒绝 |
| UPSERT 去重 | 同一条记录插入两次 → DB 中只有一条 |
| 增量同步 | 模拟已有 N 期 → 再次 fetch → 断言只拉取 N+1 期之后 |

#### 统计分析

| 测试项 | 验证方法 |
|--------|----------|
| 频次统计 | 手造 5 期数据 → 频次和 = 5×6 = 30 |
| 遗漏值 | 已知序列 → 逐期断言遗漏值（含首次出现=0） |
| 奇偶/大小比 | 固定号码 → 断言比值精确 |
| 空数据兜底 | 空列表 → 不崩溃，返回全 0 / 默认值 |

#### 选号策略

| 测试项 | 验证方法 |
|--------|----------|
| 输出合法性 | 任意策略输出 → 红球 6 个不重复且 1–33、升序；蓝球 1 个且 1–16 |
| 随机基线均匀性 | 跑 10000 次 → 各号出现频次服从均匀分布（卡方检验 p > 0.01） |
| 均衡策略约束 | 输出必须奇偶 3:3、大小 3:3、区间 2:2:2 |

#### 回测引擎

| 测试项 | 验证方法 |
|--------|----------|
| 滑动窗口不越界 | window > 数据长度 → 报错或跳过，不越界 |
| 中奖判定 | 固定 pred + actual → 中红球数精确 |
| 卡方 p-value | 用 numpy/scipy 的 `chisquare` 交叉验证 |
| 回测期数一致 | 输入 N 期 → 输出恰好 N-window 条记录 |

#### 可视化算法（重点）

每个 visualizer 必须有独立测试，验证数学变换本身的正确性：

| 算法 | 验证用例 | 基准来源 |
|------|----------|----------|
| **傅里叶级数** | 输入 `[1,0,0,0,0,0]` → 输出应为纯余弦曲线；正变换后逆变换恢复原系数 | `numpy.fft` / 手算解析解 |
| **螺旋（阿基米德/对数）** | `θ=0` 时半径 = 初始值；`θ` 增大半径单调递增（对数螺旋） | 公式 `r = a·e^(bθ)` 逐点验证 |
| **黄金角分布** | N 个点 → 相邻夹角 = 137.5°，半径 = √(序号) 的单调函数 | 数学定义逐项比对 |
| **引力坍缩** | 两体问题 → 轨迹符合开普勒/解析解；动量守恒（系统总动量误差 < 1e-9） | 两体解析解 + 守恒律 |
| **Lissajous** | 频率比 1:1 相位 0 → 直线；1:2 → 经典双环 | 参数方程逐点验证 |
| **球谐（如做 3D）** | l=0,m=0 → 球面；l=1,m=0 → 两极凸起 | 球谐函数表 |
| **形态学膨胀/腐蚀** | 单点膨胀 N 次 → 面积 = π·N²（离散近似） | 几何公式 |

**每个 visualizer 的测试必须包含**：
- 至少 1 个 `known-good` 数值用例（与 numpy/scipy 或解析解比对）
- 1 个边界用例（全 0、全相同号、极端值）
- 1 个属性测试（变换的数学恒等式，如可逆性、单调性、守恒律）

### 11.3 验证流程（强制）

```
实现算法 → 写测试（known-good + 边界 + 属性）→ 跑测试全绿
         ↓
   用真实开奖数据跑一遍 → 抽样手算核对 3-5 个点
         ↓
   数值稳定性检查（输入微扰 → 输出不爆炸）
         ↓
   合入
```

**禁止**：未写测试就提交算法代码；测试只测 happy path 不测边界；用 `print` 肉眼比对代替断言。

### 11.4 验证工具栈

- `pytest` 为主测试框架
- `numpy` / `scipy` 作为数值计算基准（不重复造轮子，且本身经过验证）
- `hypothesis` 做 property-based 测试（可选）
- 浮点断言统一用 `np.testing.assert_allclose`

---

## 12. 诚实性承诺

本项目所有面向用户的页面都会包含类似提示：

> ⚠️ 彩票为独立随机事件，历史数据不影响未来开奖。本系统仅作统计分析与选号参考，所有策略的长期命中率与纯随机无统计学差异。请理性购彩，量力而行。

回测模块会**主动证明**这一点（p-value 展示），而不是回避。
