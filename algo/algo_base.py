# 指针规划算法的基类和一些实用类型、函数
from typing import Self, IO
from enum import Enum
from typing import NamedTuple
import math
import cmath
import json


from basis import VIRTUAL_WIDTH, VIRTUAL_HEIGHT, Position, Vector


def distance_of(p1: Position, p2: Position) -> float:
    return abs(p1 - p2)

def unit_mul(p1: complex, p2: complex) -> complex:
    return complex(p1.real * p2.real, p1.imag * p2.imag)


def div(x: float, y: float) -> float:
    """自动处理除零异常"""
    try:
        return x / y
    except ZeroDivisionError:
        return math.nan


def in_screen(pos: Position) -> bool:
    return (0 <= pos.real <= VIRTUAL_WIDTH) and (0 <= pos.imag <= VIRTUAL_HEIGHT)


def recalc_pos(position: Position, rot_vec: Vector) -> Position:
    """重新计算坐标
    :param position: 坐标
    :param sa: sin(angle) 判定线偏移角度的正弦值
    :param ca: cos(angle) 判定线偏移角度的余弦值
    :return: 重新计算后的坐标
    """
    if in_screen(position):
        return position

    # 重新计算note
    c = (position * rot_vec.conjugate()).real

    sumx = sumy = 0
    x1 = div(c, rot_vec.real)
    y1 = div(c, rot_vec.imag)
    x2 = div(c - VIRTUAL_HEIGHT * rot_vec.imag, rot_vec.real)
    y2 = div(c - VIRTUAL_WIDTH * rot_vec.real, rot_vec.imag)
    if 0 < x1 < VIRTUAL_WIDTH:
        sumx += x1
    if 0 < y1 < VIRTUAL_HEIGHT:
        sumy += y1
    if 0 < x2 < VIRTUAL_WIDTH:
        sumx += x2
        sumy += VIRTUAL_HEIGHT
    if 0 < y2 < VIRTUAL_HEIGHT:
        sumy += y2
        sumx += VIRTUAL_WIDTH
    return complex(sumx / 2, sumy / 2)


class TouchAction(Enum):
    DOWN = 0
    UP = 1
    MOVE = 2
    CANCEL = 3
    OUTSIDE = 4
    POINTER_DOWN = 5
    POINTER_UP = 6
    HOVER_MOVE = 7


class TouchEvent(NamedTuple):
    pos: tuple[int, int]
    action: TouchAction
    pointer: int


class VirtualTouchEvent(NamedTuple):
    pos: Position
    action: TouchAction
    pointer: int

    def __str__(self) -> str:
        return f'''TouchEvent<{self.pointer} {self.action.name} @ ({self.pos.real:4.2f}, {self.pos.imag:4.2f})>'''

    def to_serializable(self) -> dict:
        return {'pos': [self.pos.real, self.pos.imag], 'action': self.action.value, 'pointer': self.pointer}

    @classmethod
    def from_serializable(cls, obj: dict) -> Self:
        x, y = obj['pos']
        return VirtualTouchEvent(complex(x, y), TouchAction(obj['action']), obj['pointer'])

    def map_to(self, x_offset: int, y_offset: int, x_scale: float, y_scale: float) -> TouchEvent:
        return TouchEvent(
            pos=(x_offset + round(self.pos.real * x_scale), y_offset + round(self.pos.imag * y_scale)),
            action=self.action,
            pointer=self.pointer,
        )


def export_to_json(ans: dict[int, list[VirtualTouchEvent]], out_file: IO):
    json.dump(
        {timestamp: [event.to_serializable() for event in events] for timestamp, events in ans.items()},
        out_file,
    )


def load_from_json(in_file: IO) -> dict[int, list[VirtualTouchEvent]]:
    return {
        int(ts): [VirtualTouchEvent.from_serializable(event) for event in events]
        for ts, events in json.load(in_file).items()
    }


__all__ = ['TouchAction', 'VirtualTouchEvent', 'TouchEvent', 'distance_of', 'recalc_pos', 'in_screen']
