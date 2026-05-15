from dataclasses import dataclass, field
from typing import Any, Mapping

from .common import AttrsMixin


@dataclass(slots=True, frozen=True)
class Flow(AttrsMixin):
    id: int
    src: int
    dst: int
    rate: int
    duration: float

    attrs: Mapping[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return (f"Flow(id={self.id}, src={self.src}, dst={self.dst}, "
                f"rate={self.rate}, duration={self.duration}, attrs={self.attrs})")

    def __post_init__(self):
        # 把 self.attrs 变成只读、不可修改的字典（冻结保护），外部无法篡改，保护数据安全。
        self._freeze_attrs()

    def get_attr(self, name: str, default: Any = None) -> Any:
        """
        获取自定义属性。如果不存在，直接报错。
        """
        if name not in self.attrs:
            raise KeyError(f"Flow {self.id} missing required custom attribute: {name}")

        return self.attrs.get(name, default)
