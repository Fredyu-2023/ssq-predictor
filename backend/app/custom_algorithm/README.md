# 用户自有算法插件

把算法 `.py` 文件放进本目录（`backend/app/custom_algorithm/`），重启后端即自动注册；
前端「选号预测」页的策略下拉会多出一项（标记为「自定义」），`POST /api/predict` 可直接调用。

**不需要改任何核心代码。** 唯一要求：继承 `BaseStrategy` 并实现 `generate`。

## 1. 快速开始

```powershell
# 1) 复制示例并去掉下划线前缀（下划线开头的文件不会被加载）
Copy-Item backend/app/custom_algorithm/_example_random.py backend/app/custom_algorithm/my_algo.py

# 2) 改类名 / name / description，写自己的逻辑

# 3) 重启后端（或调用 registry.reload()）
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# 4) 查看是否注册成功
curl http://127.0.0.1:8000/api/strategies
```

## 2. 接口契约

```python
from app.strategies.base import BaseStrategy, ball_params

class MyAlgorithm(BaseStrategy):
    name = "my_algo"                      # 唯一标识，前端下拉与 API 参数用这个
    description = "我的独门算法"           # 前端展示的说明文字
    # source 由加载器自动写成 "custom"，不要自己设置

    def generate(self, history, count=1, **params):
        """返回 count 注号码。

        history: list[Draw]，按时间从旧到新排列，最多 500 期。
                 每条可用 draw.issue / draw.draw_date / draw.reds / draw.blue / draw.blues
        count:   本次要生成的注数（1-20）
        params:  由 API 注入的关键字参数，见下表

        返回:    list[list[int]]，每注 [r1, r2, ..., rN, b]，
                 红球必须升序、不重复，且在合法范围内。
        """
```

### 2.1 可用的 params

| 参数 | 说明 |
|------|------|
| `window` | 参考期数（1–500），默认 30；可用 `history[-window:]` 取近 N 期 |
| `red_count` / `red_min` / `red_max` | 当前彩种的红球数量与范围（双色球 6 / 1–33） |
| `blue_min` / `blue_max` | 蓝球范围（双色球 1–16） |
| `seed` | 仅在请求 `params` 里显式传入时存在，用于固定随机序列，便于复现 |

> 球号规则参数由服务端最后写入，**用户无法覆盖**。请用 `ball_params(params)` 读取，
> 这样以后接入其他彩种时算法无需改代码。

### 2.2 结果校验

所有返回结果都会经过 `validate_bets`：注数、长度、整数、红球不重复/升序/范围、蓝球范围。
不合法会抛 `ValueError`，API 返回 500 并在 `detail` 中带上完整堆栈——不会拖垮其他策略。

### 2.3 性能约定

`generate` 单次调用建议 < 5 秒。不要在里面发起网络请求或做长时间训练。

## 3. 示例一：纯随机

完整可运行文件：[`_example_random.py`](./_example_random.py)

```python
from __future__ import annotations

import random

from app.strategies.base import BaseStrategy, ball_params


class ExampleRandomStrategy(BaseStrategy):
    name = "example_random"
    description = "示例：按球号规则纯随机选号"

    def generate(self, history, count=1, **params):
        cfg = ball_params(params)
        rng = random.SystemRandom()
        bets = []
        for _ in range(count):
            reds = sorted(
                rng.sample(
                    range(cfg["red_min"], cfg["red_max"] + 1),
                    cfg["red_count"],
                )
            )
            bets.append([*reds, rng.randint(cfg["blue_min"], cfg["blue_max"])])
        return bets
```

## 4. 示例二：按历史频次加权

完整可运行文件：[`_example_freq.py`](./_example_freq.py)

```python
from __future__ import annotations

from collections import Counter

from app.strategies.base import BaseStrategy, ball_params


def _weighted_pick(rng, pool, weights, k):
    """不放回加权抽样（weights 全为 0 时退化为均匀抽样）。"""
    pool = list(pool)
    weights = [float(w) for w in weights]
    chosen = []
    for _ in range(k):
        total = sum(weights)
        if total <= 0:
            index = rng.randrange(len(pool))
        else:
            target = rng.random() * total
            acc = 0.0
            index = 0
            for i, w in enumerate(weights):
                acc += w
                if target <= acc:
                    index = i
                    break
        chosen.append(pool.pop(index))
        weights.pop(index)
    return chosen


class ExampleFreqStrategy(BaseStrategy):
    name = "example_freq"
    description = "示例：按近 window 期红球/蓝球频次加权选号"

    def generate(self, history, count=1, **params):
        cfg = ball_params(params)
        window = int(params.get("window", 30))
        recent = history[-window:] if window > 0 else history

        red_freq = Counter()
        blue_freq = Counter()
        for draw in recent:
            red_freq.update(draw.reds)
            blue_freq.update(draw.blues)

        rng = random.SystemRandom()
        red_pool = range(cfg["red_min"], cfg["red_max"] + 1)
        blue_pool = range(cfg["blue_min"], cfg["blue_max"] + 1)
        # +1 让没出现过的号码也有机会被选中
        red_weights = [red_freq.get(n, 0) + 1 for n in red_pool]
        blue_weights = [blue_freq.get(n, 0) + 1 for n in blue_pool]

        bets = []
        for _ in range(count):
            reds = sorted(_weighted_pick(rng, red_pool, red_weights, cfg["red_count"]))
            blues = _weighted_pick(rng, blue_pool, blue_weights, 1)
            bets.append([*reds, blues[0]])
        return bets
```

## 5. 加载规则

| 规则 | 行为 |
|------|------|
| 文件名 `_foo.py` | **跳过**（示例文件用下划线前缀，避免示例混进策略列表） |
| 一个文件多个策略类 | 每个 `BaseStrategy` 子类都会注册（仅限本模块内定义的类） |
| 重名 | 后加载的自定义策略覆盖同名内置策略 |
| 单个文件报错 | 记录到 `registry.load_errors()`，其余文件继续加载 |
| 修改代码后 | 重启后端生效；开发期也可调用 `app.strategies.registry.reload()` 热重载 |
