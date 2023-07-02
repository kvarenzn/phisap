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


def det(a: Position, b: Position) -> float:
    return (a * b.conjugate() * 1j).real


def intersect(line1: tuple[Position, Position], line2: tuple[Position, Position]) -> Position | None:
    dl1 = line1[0] - line1[1]
    dl2 = line2[0] - line2[1]
    xd = complex(dl1.real, dl2.real)
    yd = complex(dl1.imag, dl2.imag)
    di = det(xd, yd)
    if di == 0:
        return None
    d = complex(det(*line1), det(*line2))
    return complex(det(d, xd) / di, det(d, yd) / di)


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

    def remap(self, p: Position, rotation: Vector) -> Position:
        if self.visible(p):
            return p

        # 在直线上取一个新点q
        q = p + rotation * 1j

        # 依次求与四条边所在直线的交点
        j1 = intersect((p, q), (0, self.width))  # (0, 0) -> (W, 0)
        j2 = intersect((p, q), (0, self.height * 1j))  # (0, 0) -> (0, H)
        j3 = intersect((p, q), (self.width, complex(self.width, self.height)))  # (W, 0) -> (W, H)
        j4 = intersect((p, q), (self.height * 1j, complex(self.width, self.height)))  # (0, H) -> (W, H)

        s = 0
        cnt = 0
        if j1 is not None and (0 <= j1.real <= self.width):
            s += j1
            cnt += 1
        if j2 is not None and (0 <= j2.imag <= self.height):
            s += j2
            cnt += 1
        if j3 is not None and (0 <= j3.imag <= self.height):
            s += j3
            cnt += 1
        if j4 is not None and (0 <= j4.real <= self.width):
            s += j4
            cnt += 1

        if s == 0:
            return complex(self.width, self.height) / 2
        return s / cnt


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
