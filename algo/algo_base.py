# 指针规划算法的基类和一些实用类型、函数
from enum import Enum
from typing import NamedTuple


class TouchAction(Enum):
    DOWN = 0
    UP = 1
    MOVE = 2
    CANCEL = 3
    OUTSIDE = 4
    POINTER_DOWN = 5
    POINTER_UP = 6
    HOVER_MOVE = 7


class VirtualTouchEvent(NamedTuple):
    pos: tuple[float, float]
    action: TouchAction
    pointer: int

    def __str__(self):
        x, y = self.pos
        return f'''TouchEvent<{self.pointer} {self.action.name} @ ({x:4.2f}, {y:4.2f})>'''

    def to_serializable(self):
        return {'pos': self.pos, 'action': self.action.value, 'pointer': self.pointer}

    @classmethod
    def from_serializable(cls, obj: dict) -> 'VirtualTouchEvent':
        return VirtualTouchEvent(obj['pos'], TouchAction(obj['action']), obj['pointer'])

    def map_to(self, x_offset: int, y_offset: int, x_scale: float, y_scale: float) -> 'TouchEvent':
        x_orig, y_orig = self.pos
        return TouchEvent(
            pos=(x_offset + round(x_orig * x_scale), y_offset + round(y_orig * y_scale)),
            action=self.action,
            pointer=self.pointer,
        )


class TouchEvent(NamedTuple):
    pos: tuple[int, int]
    action: TouchAction
    pointer: int
