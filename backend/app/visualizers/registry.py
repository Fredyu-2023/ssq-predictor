"""可视化注册表：内置 A–R 清单，其中 G 螺旋骨架傅里叶已实现，其余为 planned。"""

from __future__ import annotations

from collections import OrderedDict

from .base import BaseVisualizer, VisualizationData
from .spiral_fourier import SpiralFourierVisualizer

PLANNED_SPECS = [
    ("A", "fourier_curve", "傅里叶闭合曲线", "频域", "2D", "红球=谐波振幅，蓝球=相位"),
    ("B", "lissajous", "Lissajous 图形", "频域", "2D", "红球两两配对为 x/y 频率"),
    ("C", "space_time_track", "3D 时空轨迹", "轨迹", "3D", "6 个红球 → 3 个 3D 点，蓝球=颜色"),
    ("D", "spherical_harmonics", "球面调和变形球", "频域", "3D", "红球=球谐系数"),
    ("E", "chaotic_attractor", "混沌吸引子", "动力系统", "3D", "号码=初值，迭代洛伦兹等"),
    ("F", "cooccurrence_network", "共现网络图", "图论", "2D", "号码=节点，同现=边"),
    ("G", "spiral_fourier", "螺旋骨架傅里叶", "螺旋", "2D/3D", "红球=螺旋上谐波振幅，蓝球=紧密度"),
    ("H", "polar_rose", "极坐标傅里叶玫瑰", "螺旋", "2D", "红球=r(θ) 的傅里叶系数"),
    ("I", "fibonacci_spiral", "斐波那契螺旋点阵", "螺旋", "2D/3D", "号码=黄金角分布的径向距离"),
    ("J", "gravity_collapse", "引力坍缩轨迹", "塌陷", "2D/3D", "红球=质点质量，蓝球=引力常数"),
    ("K", "basin_collapse", "吸引子盆地塌缩", "塌陷", "3D", "号码=动力系统初值，观察塌缩路径"),
    ("L", "polygon_collapse", "多边形塌缩", "塌陷", "2D", "红球=六边形顶点半径，蓝球=衰减系数"),
    ("M", "breathing_sphere", "呼吸球面", "伸展收缩", "3D", "红球=球谐系数，球面周期膨胀收缩"),
    ("N", "homotopy_morph", "形态渐变（Homotopy）", "伸展收缩", "2D/3D", "从上期形状连续形变为本期"),
    ("O", "morphological_dilate", "形态学膨胀/腐蚀", "伸展收缩", "2D", "号码=二值点集，迭代膨胀腐蚀"),
    ("P", "spiral_breathing", "螺旋呼吸叠加", "组合", "2D/3D", "多期螺旋波叠加干涉"),
    ("Q", "spiral_collapse", "螺旋塌缩吸引子", "组合", "3D", "螺旋骨架 + 动力系统，收敛点可作算法输入"),
    ("R", "breathing_pointcloud", "呼吸螺旋点云", "组合", "3D", "斐波那契点阵 + 呼吸缩放"),
]


class PlannedVisualizer(BaseVisualizer):
    """占位实现：可被 /api/visualizers 列出，但 render 明确抛出「开发中」。"""

    def __init__(self, code: str, name: str, title: str, category: str, dimension: str, mapping: str) -> None:
        self.code = code
        self.name = name
        self.title = title
        self.category = category
        self.dimension = dimension
        self.mapping = mapping
        self.status = "planned"
        self.description = f"{mapping}（算法框架已预留，具体实现开发中）"

    def render(self, draws: list, **params) -> VisualizationData:
        raise NotImplementedError(f"{self.title} 仍在开发中")


_REGISTRY: OrderedDict[str, BaseVisualizer] = OrderedDict(
    (spec[1], PlannedVisualizer(*spec)) for spec in PLANNED_SPECS
)
# G. 螺旋骨架傅里叶已有具体实现，用实现类覆盖同名的占位项（保持原有排序）。
_REGISTRY["spiral_fourier"] = SpiralFourierVisualizer()


def register(visualizer: BaseVisualizer) -> None:
    """登记一个具体实现（供后续插件调用）。"""
    if not visualizer.name:
        raise ValueError("visualizer 必须有 name")
    _REGISTRY[visualizer.name] = visualizer


def list_visualizers() -> list[dict]:
    return [item.to_dict() for item in _REGISTRY.values()]


def get_visualizer(name: str) -> BaseVisualizer:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"未知可视化算法：{name}") from exc
