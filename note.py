from typing import TypedDict
from enum import IntEnum


class NoteDict(TypedDict):
    type: int
    time: int
    positionX: float
    holdTime: float
    speed: float
    floorPosition: float


class NoteType(IntEnum):
    TAP = 1
    DRAG = 2
    HOLD = 3
    FLICK = 4

    @property
    def name(self) -> str:
        return ['UNKNOWN', 'TAP', 'DRAG', 'HOLD', 'FLICK'][self.value]


class Note:
    type: NoteType
    time: int
    x: float
    hold: float
    speed: float
    floor: float

    def __init__(self, type: NoteType, time: int, x: float, hold: float, speed: float, floor: float):
        self.type = type
        self.time = time
        self.x = x
        self.hold = hold
        self.speed = speed
        self.floor = floor

    @classmethod
    def load(cls, d: NoteDict) -> 'Note':
        return cls(NoteType(d['type']), d['time'], d['positionX'], d['holdTime'], d['speed'], d['floorPosition'])

    def __repr__(self):
        return (
            f'''Note({self.type.name}, time={self.time}, x={self.x}, '''
            f'''hold={self.hold}, speed={self.speed}, floor={self.floor})'''
        )


__all__ = ['NoteDict', 'Note', 'NoteType']
