"""可视化框架：把开奖号码映射为几何形态。

说明：A–R 全部算法为后补插件，当前只提供框架与占位清单（status = planned）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VisualizationData:
    """前端渲染所需的统一数据结构。"""

    type: str
    data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class BaseVisualizer(ABC):
    """可视化算法基类。

    子类至少实现 ``render``；如需把图形特征喂给选号算法，再覆盖 ``extract_features``。
    """

    name: str = ""
    code: str = ""
    title: str = ""
    category: str = ""
    dimension: str = "2D"
    status: str = "planned"
    description: str = ""
    mapping: str = ""

    @abstractmethod
    def render(self, draws: list, **params) -> VisualizationData:
        """输入若干期开奖，输出图形几何数据。"""

    def extract_features(self, data: VisualizationData) -> dict:
        """从图形中提取特征（面积/质心/收敛点等），默认无。"""
        return {}

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "title": self.title,
            "category": self.category,
            "dimension": self.dimension,
            "status": self.status,
            "description": self.description,
            "mapping": self.mapping,
        }
