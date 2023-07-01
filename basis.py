from abc import ABCMeta, abstractmethod
from enum import IntEnum
from bamboo import Bamboo
from typing import TypeAlias, NamedTuple

# 屏幕长为16个单位，宽为9个单位
# 所有的时间单位统一为秒

VIRTUAL_WIDTH = 16
VIRTUAL_HEIGHT = 9


class NoteType(IntEnum):
    UNKNOWN = -1
    TAP = 0
    DRAG = 1
    HOLD = 2
    FLICK = 3


class Note(NamedTuple):
    type: NoteType
    seconds: float
    hold: float
    x: float


Position: TypeAlias = complex
Vector: TypeAlias = complex


class JudgeLine(metaclass=ABCMeta):
    notes: list[Note]
    position: Bamboo[Position]
    angle: Bamboo[float]

    @abstractmethod
    def pos(self, seconds: float, position_x: float) -> Position:
        ...

    @abstractmethod
    def beat_duration(self) -> float: ...


class Chart(metaclass=ABCMeta):
    offset: float
    judge_lines: list[JudgeLine]
