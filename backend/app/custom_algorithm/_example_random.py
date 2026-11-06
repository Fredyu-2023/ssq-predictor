"""示例 1：纯随机选号。

文件名以下划线开头，加载器会跳过它；复制为 ``my_algo.py``（去掉下划线）后重启即可启用。
"""

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
