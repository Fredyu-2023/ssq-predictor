"""策略注册表：内置策略 + 用户 custom_algorithm 目录自动扫描。"""

from __future__ import annotations

import importlib
import pkgutil
import sys
import threading
from collections import OrderedDict
from pathlib import Path

from .base import BaseStrategy
from .builtin import BUILTIN_STRATEGIES

_lock = threading.Lock()
_strategies: "OrderedDict[str, tuple[BaseStrategy, str]]" = OrderedDict()
_errors: list[str] = []

CUSTOM_DIR = Path(__file__).resolve().parents[1] / "custom_algorithm"


def _scan_custom(found: "OrderedDict[str, tuple[BaseStrategy, str]]", errors: list[str]) -> None:
    if not CUSTOM_DIR.is_dir():
        return
    for info in pkgutil.iter_modules([str(CUSTOM_DIR)]):
        if info.name.startswith("_"):
            continue
        module_name = f"app.custom_algorithm.{info.name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # 单个算法文件失败不影响其他策略
            errors.append(f"{module_name}: {exc.__class__.__name__}: {exc}")
            continue

        for attr in vars(module).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseStrategy)
                and attr is not BaseStrategy
                and attr.__module__ == module.__name__
            ):
                if not getattr(attr, "name", ""):
                    errors.append(f"{module_name}.{attr.__name__}: name 不能为空")
                    continue
                try:
                    instance = attr()
                except Exception as exc:
                    errors.append(f"{module_name}.{attr.__name__}: 实例化失败：{exc}")
                    continue
                found[instance.name] = (instance, "custom")


def reload() -> None:
    """重新扫描内置策略与 custom_algorithm（用户改代码后调用即可生效）。"""
    with _lock:
        for name in list(sys.modules):
            if name.startswith("app.custom_algorithm.") and name != "app.custom_algorithm":
                sys.modules.pop(name, None)
        importlib.invalidate_caches()

        found: "OrderedDict[str, tuple[BaseStrategy, str]]" = OrderedDict(
            (strategy.name, (strategy, "builtin")) for strategy in BUILTIN_STRATEGIES
        )
        errors: list[str] = []
        _scan_custom(found, errors)

        _strategies.clear()
        _strategies.update(found)
        _errors.clear()
        _errors.extend(errors)


def ensure_loaded() -> None:
    if not _strategies:
        reload()


def list_strategies() -> list[dict]:
    ensure_loaded()
    with _lock:
        return [
            {"name": instance.name, "description": instance.description, "source": source}
            for instance, source in _strategies.values()
        ]


def get_strategy(name: str) -> BaseStrategy:
    ensure_loaded()
    with _lock:
        entry = _strategies.get(name)
    if entry is None:
        raise KeyError(f"未找到策略：{name}")
    return entry[0]


def load_errors() -> list[str]:
    ensure_loaded()
    with _lock:
        return list(_errors)
