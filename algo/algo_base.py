# 指针规划算法的基类和一些实用类型、函数
from typing import Self, IO
from enum import Enum
from typing import NamedTuple
import math
import cmath
import json


from basis import Position, Vector


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


class ScreenUtil:
    width: int
    height: int

    flick_radius: float

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.flick_radius = width * 0.1

    def visible(self, pos: Position) -> bool:
        return (0 <= pos.real <= self.width) and (0 <= pos.imag <= self.height)

    def remap(self, position: Position, rotation: Vector) -> Position:
        if self.visible(position):
            return position

        # 重新计算note
        c = (position * rotation.conjugate()).real

        sumx = sumy = 0
        x1 = div(c, rotation.real)
        y1 = div(c, rotation.imag)
        x2 = div(c - self.height * rotation.imag, rotation.real)
        y2 = div(c - self.width * rotation.real, rotation.imag)
        if 0 < x1 < self.width:
            sumx += x1
        if 0 < y1 < self.height:
            sumy += y1
        if 0 < x2 < self.width:
            sumx += x2
            sumy += self.height
        if 0 < y2 < self.height:
            sumy += y2
            sumx += self.width
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

    def _map_to(self, x_offset: int, y_offset: int, x_scale: float, y_scale: float) -> TouchEvent:
        return TouchEvent(
            pos=(x_offset + round(self.pos.real * x_scale), y_offset + round(self.pos.imag * y_scale)),
            action=self.action,
            pointer=self.pointer,
        )


class WindowGeometry(NamedTuple):
    x: int
    y: int
    w: int
    h: int


def remap_events(
    screen: ScreenUtil, geometry: WindowGeometry, answer: dict[int, list[VirtualTouchEvent]]
) -> list[tuple[int, list[TouchEvent]]]:
    result = []
    x_scale = geometry.w / screen.width
    y_scale = geometry.h / screen.height
    for ts in sorted(answer.keys()):
        converted = []
        for event in answer[ts]:
            converted.append(
                TouchEvent(
                    (geometry.x + round(event.pos.real * x_scale), geometry.y + round(event.pos.imag * y_scale)),
                    event.action,
                    event.pointer,
                )
            )
        result.append((ts, converted))
    return result


def dump_to_json(screen: ScreenUtil, ans: dict[int, list[VirtualTouchEvent]]):
    return json.dumps(
        {
            'width': screen.width,
            'height': screen.height,
            'events': {timestamp: [event.to_serializable() for event in events] for timestamp, events in ans.items()},
        }
    )


def load_from_json(content: str) -> tuple[ScreenUtil, dict[int, list[VirtualTouchEvent]]]:
    dic = json.loads(content)
    return ScreenUtil(dic['width'], dic['height']), {
        int(ts): [VirtualTouchEvent.from_serializable(event) for event in events]
        for ts, events in dic['events'].items()
    }


__all__ = ['TouchAction', 'VirtualTouchEvent', 'TouchEvent', 'distance_of', 'ScreenUtil']
