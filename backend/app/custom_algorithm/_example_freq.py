"""示例 2：按近 window 期红球/蓝球频次加权选号。

文件名以下划线开头，加载器会跳过它；复制为 ``my_algo.py``（去掉下划线）后重启即可启用。
"""

from __future__ import annotations

import random
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
