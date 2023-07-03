from abc import ABCMeta, abstractmethod
from enum import IntEnum
from bamboo import Bamboo
from typing import TypeAlias, NamedTuple


Position: TypeAlias = complex
Vector: TypeAlias = complex


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
    offset: Position


class JudgeLine(metaclass=ABCMeta):
    notes: list[Note]
    position: Bamboo[Position]
    angle: Bamboo[float]

    @abstractmethod
    def pos(self, seconds: float, offset: Position) -> Position:
        ...

    @abstractmethod
    def beat_duration(self, seconds: float) -> float:
        ...


class Chart(metaclass=ABCMeta):
    screen_width: int
    screen_height: int
    offset: float
    lines: list[JudgeLine]
