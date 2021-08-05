from enum import Enum
from typing import NamedTuple


class TouchAction(Enum):
    DOWN = 0
    UP = 1
    MOVE = 2

    @classmethod
    def from_str(cls, string: str) -> 'TouchAction':
        return cls._member_map_[string]


class TouchEvent(NamedTuple):
    pos: tuple[float, float]
    action: TouchAction
    pointer: int

    def __str__(self):
        x, y = self.pos
        return f'''TouchEvent<{self.pointer} {self.action.name} @ ({x:4.2f}, {y:4.2f})>'''

    def to_serializable(self):
        return {
            'pos': self.pos,
            'action': self.action.name,
            'pointer': self.pointer
        }

    @classmethod
    def from_serializable(cls, obj: dict) -> 'TouchEvent':
        return TouchEvent(obj['pos'], TouchAction.from_str(obj['action']), obj['pointer'])