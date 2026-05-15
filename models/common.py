from __future__ import annotations

from dataclasses import field
from types import MappingProxyType
from typing import Any, Mapping


class AttrsMixin:
    """
    为模型类提供统一的 attrs 扩展属性能力。

    注意：
    attrs 字段由子类显式声明，避免 dataclass 继承字段顺序问题。
    """
    attrs: Mapping[str, Any] = field(default_factory=dict)

    def _freeze_attrs(self) -> None:
        """
        将 attrs 转成只读 Mapping，避免外部修改。
        frozen dataclass 中需要使用 object.__setattr__。
        """
        object.__setattr__(self, "attrs", MappingProxyType(dict(self.attrs)))

    def get_attr(self, name: str, default: Any = None) -> Any:
        """
        获取自定义属性。如果不存在，直接报错。
        """
        if name not in self.attrs:
            raise KeyError(f"Missing required custom attribute: {name}")

        return self.attrs.get(name, default)

    def has_attr(self, name: str) -> bool:
        return name in self.attrs
