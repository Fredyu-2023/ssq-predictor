"""G. 螺旋骨架傅里叶（可视化算法实现）。

原理（一句话）：先画一条阿基米德螺旋当「骨架」，再把 6 段余弦波按红球决定的振幅
叠加到骨架上，得到一条「边旋转边起伏」的开口曲线。

映射规则（与 ALGORITHM_GUIDE.html 中的 G 节一致）：
- 红球 r_n（n = 1..6，按升序对应第 n 阶谐波）→ 该阶谐波的振幅；
  振幅按红球上限归一化后再换算成权重，6 个红球的权重之和恒为 1
- 蓝球 b → 螺旋紧密度：蓝球越大，螺距 pitch 越小，同样半径内的圈数越多（收得更紧）

计算流程：
1. 取传入序列的最新一期，读出 reds / blue（期数由 API 层决定，本算法只用最新一期）
2. 由蓝球算出 tightness → pitch → 总圈数 turns
3. 沿 θ = 0..turns·2π 均匀采样：r(θ) = 骨架半径 × (1 + gain × Σ w_n cos(nθ))
4. 转成直角坐标 (r cosθ, r sinθ)，整体归一化到单位圆内（最大半径 = 1）
5. 输出 points / 谐波清单 / 参数，供前端用 SVG 绘制

可调参数（经 render(**params) 传入，均有默认值与钳位范围）：
- samples：采样点数，默认 1440，钳位 [240, 6000]；越多曲线越顺滑
- gain：谐波总振幅（相对局部半径），默认 0.28，钳位 [0, 0.6]；越大起伏越明显
- pitch：基准螺距（每圈半径增量），默认 0.26，钳位 [0.05, 0.5]；
  实际螺距 = pitch × (1 - 0.6 × tightness)，蓝球越大收得越紧
- red_max / blue_max：号码上限，默认 33 / 16，用于归一化

注意：该算法只把号码映射成几何形状，不具备任何预测含义。
"""

from __future__ import annotations

import math

from .base import BaseVisualizer, VisualizationData

TAU = 2 * math.pi

DEFAULT_SAMPLES = 1440  # 采样点数，越多曲线越顺滑
DEFAULT_GAIN = 0.28  # 谐波总振幅（相对局部半径，0~0.6）
DEFAULT_PITCH = 0.26  # 蓝球最小时的螺距（每圈半径增量）
DEFAULT_INNER_RADIUS = 0.10  # 螺旋起点半径（归一化前）
DEFAULT_RED_MAX = 33  # 双色球红球上限
DEFAULT_BLUE_MAX = 16  # 双色球蓝球上限


def _clamp(value: float, low: float, high: float) -> float:
    """把 value 钳位到 [low, high]，防止非法参数让图形退化或发散。"""
    return max(low, min(high, value))


class SpiralFourierVisualizer(BaseVisualizer):
    """螺旋骨架 + 6 阶余弦谐波。

    类属性即算法元数据（编号 / 标题 / 类别 / 维度 / 状态），注册表直接读取。
    render() 只使用最新一期数据；extract_features() 从渲染结果中提取 14 项几何特征。
    """

    name = "spiral_fourier"
    code = "G"
    title = "螺旋骨架傅里叶"
    category = "螺旋"
    dimension = "2D/3D"
    status = "implemented"
    description = "红球按升序对应 6 阶谐波振幅，蓝球决定螺距与圈数；在螺旋骨架上叠加余弦波。"
    mapping = "红球=螺旋上谐波振幅，蓝球=紧密度"

    # ---------- 渲染 ----------

    def render(self, draws: list, **params) -> VisualizationData:
        if not draws:
            raise ValueError("螺旋骨架傅里叶至少需要一期开奖数据")

        # 只取最新一期：几何形态由单期号码决定（期数裁剪在 API 层完成）
        draw = draws[-1]
        reds = [int(value) for value in draw.reds]
        blue = int(draw.blues[0])

        red_max = float(params.get("red_max", DEFAULT_RED_MAX))
        blue_max = float(params.get("blue_max", DEFAULT_BLUE_MAX))
        if red_max <= 0 or blue_max <= 0:
            raise ValueError("red_max / blue_max 必须为正数")

        samples = int(_clamp(float(params.get("samples", DEFAULT_SAMPLES)), 240, 6000))
        gain = _clamp(float(params.get("gain", DEFAULT_GAIN)), 0.0, 0.6)
        base_pitch = _clamp(float(params.get("pitch", DEFAULT_PITCH)), 0.05, 0.5)

        # 蓝球 → 紧密度 → 螺距。蓝球越大紧密度越高，螺距越小、圈数越多。
        tightness = _clamp(blue / blue_max, 0.0, 1.0)
        pitch = base_pitch * (1.0 - 0.6 * tightness)
        turns = (1.0 - DEFAULT_INNER_RADIUS) / pitch
        total_angle = turns * TAU

        # 红球 → 振幅 → 归一化权重：权重之和为 1，保证波形幅度不超过 gain。
        amplitudes = [value / red_max for value in reds]
        amplitude_sum = math.fsum(amplitudes)
        weights = [value / amplitude_sum for value in amplitudes]

        # ---- 采样循环：θ 从 0 匀速转到 turns·2π，逐点算半径并转直角坐标 ----
        points: list[list[float]] = []
        raw: list[tuple[float, float]] = []
        for index in range(samples):
            progress = index / (samples - 1)  # 0→1 的归一化进度
            theta = total_angle * progress  # 当前极角
            skeleton = DEFAULT_INNER_RADIUS + (1.0 - DEFAULT_INNER_RADIUS) * progress  # 骨架半径：线性外扩
            wave = math.fsum(
                weights[order] * math.cos((order + 1) * theta) for order in range(len(weights))
            )
            radius = skeleton * (1.0 + gain * wave)  # 骨架 × (1 + 增益 × 波形)：边旋转边起伏
            raw.append((radius * math.cos(theta), radius * math.sin(theta)))

        # 归一化：以最大半径（波峰）为 1，保证图形始终落在单位圆内，前端可直接等比缩放。
        scale = max(math.hypot(x, y) for x, y in raw)
        for x, y in raw:
            points.append([round(x / scale, 6), round(y / scale, 6)])

        # 谐波清单：阶数 / 对应红球 / 原始振幅 / 归一化权重，供前端画权重条
        harmonics = [
            {
                "order": index + 1,
                "number": reds[index],
                "amplitude": round(amplitudes[index], 6),
                "weight": round(weights[index], 6),
            }
            for index in range(len(reds))
        ]

        return VisualizationData(
            type="spiral_fourier",
            data={
                "points": points,
                "normalized": True,
                "scale": scale,
                "turns": round(turns, 6),
                "tightness": round(tightness, 6),
                "pitch": round(pitch, 6),
                "gain": round(gain, 6),
                "inner_radius": DEFAULT_INNER_RADIUS,
                "harmonics": harmonics,
                "reds": reds,
                "blue": blue,
                "red_max": red_max,
                "blue_max": blue_max,
                "issue": draw.issue,
            },
            metadata={
                "code": self.code,
                "name": self.name,
                "title": self.title,
                "algorithm": "阿基米德螺旋骨架 + 6 阶余弦谐波叠加",
                "issue": draw.issue,
                "draw_date": str(draw.draw_date),
            },
        )

    # ---------- 特征 ----------

    def extract_features(self, data: VisualizationData) -> dict:
        payload = data.data
        points = payload.get("points") or []
        if not points:
            return {}

        # 逐点极坐标：半径用于长度/振幅统计，角度用于累计转角
        radii = [math.hypot(x, y) for x, y in points]
        angles = [math.atan2(y, x) for x, y in points]
        count = len(points)

        # 弧长：相邻点欧氏距离求和（弦长逼近弧长，1440 个采样点足够精确）
        arc_length = math.fsum(
            math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
            for i in range(1, count)
        )

        # 累计转角：用 sin/cos 规避 ±π 处的角度跳变，等价于曲线总弯曲量。
        turning = math.fsum(
            abs(
                math.atan2(
                    math.sin(angles[i] - angles[i - 1]),
                    math.cos(angles[i] - angles[i - 1]),
                )
            )
            for i in range(1, count)
        )

        turns = float(payload.get("turns", 0.0))
        inner = float(payload.get("inner_radius", 0.0))
        scale = float(payload.get("scale", 1.0))
        # 归一化把整条曲线同比例缩小了 scale 倍，骨架半径也要除以同一系数才能相除。
        skeletons = [
            (inner + (1.0 - inner) * (i / (count - 1))) / scale for i in range(count)
        ]
        modulations = [radii[i] / skeletons[i] - 1.0 for i in range(count)]

        # 谐波质心：Σ(阶数 × 权重)，值越大说明高阶（对应大号码红球）越主导
        harmonics = payload.get("harmonics") or []
        weighted = [item["weight"] for item in harmonics]
        dominant = max(harmonics, key=lambda item: item["weight"]) if harmonics else None
        centroid = math.fsum(
            (index + 1) * weight for index, weight in enumerate(weighted)
        )

        # 半径统计与终点方位角（归一化到 [0, 360)）
        mean_radius = math.fsum(radii) / count
        variance = math.fsum((value - mean_radius) ** 2 for value in radii) / count
        end_angle = math.degrees(angles[-1]) % 360.0

        # 14 项特征：形态参数回显 + 派生几何量，供下游比对/聚类使用
        return {
            "turns": round(turns, 6),
            "tightness": round(float(payload.get("tightness", 0.0)), 6),
            "pitch": round(float(payload.get("pitch", 0.0)), 6),
            "gain": round(float(payload.get("gain", 0.0)), 6),
            "harmonic_centroid": round(centroid, 6),
            "dominant_harmonic": dominant["order"] if dominant else 0,
            "mean_radius": round(mean_radius, 6),
            "radius_std": round(math.sqrt(variance), 6),
            "arc_length": round(arc_length, 6),
            "curvature_energy": round(turning, 6),
            "wave_amplitude": round(max(abs(value) for value in modulations), 6),
            "wave_energy": round(math.fsum(value ** 2 for value in modulations) / count, 6),
            "end_radius": round(radii[-1], 6),
            "end_angle_deg": round(end_angle, 6),
        }
