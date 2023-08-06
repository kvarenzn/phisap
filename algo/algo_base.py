# 指针规划算法的基类和一些实用类型、函数
from collections import defaultdict
from typing import Any, Self
from enum import Enum
from typing import NamedTuple, TypeAlias, TypedDict
from io import BytesIO
import struct

from z3 import Int, Solver, unsat

from basis import Position, Vector, Chart, JudgeLine, Note

class NoteFeedback(Enum):
    PERFECT = 0
    GOOD = 1
    MISS = 2

class NoteRef(NamedTuple):
    ref: Note
    line: JudgeLine
    feedback: NoteFeedback = NoteFeedback.PERFECT


def calc_score(total: int, target_score: int, strict: bool) -> tuple[int, int, int, int] | None:
    perfect = Int('perfect')
    good = Int('good')
    miss = Int('miss')
    combo = Int('combo')
    solver = Solver()
    solver.add(perfect >= 0)
    solver.add(good >= 0)
    solver.add(miss >= 0)
    solver.add(combo >= 1)
    solver.add(perfect + good + miss == total)
    solver.add(combo <= perfect + good)
    solver.add(combo * (miss + 1) >= perfect + good)
    f: Any
    if strict:
        f = (perfect + 0.65 * good) / total * 1000000
    else:
        f = (perfect + 0.65 * good) / total * 900000 + combo / total * 100000  # type: ignore
    solver.add(f >= target_score)
    solver.add(f < target_score + 1)
    if solver.check() == unsat:
        return
    else:
        model = solver.model()
        return model[perfect].as_long(), model[good].as_long(), model[miss].as_long(), model[combo].as_long() # type: ignore


def preprocess(chart: Chart, target_score: int, strict: bool) -> Chart:
    if target_score == 0:
        chart.lines.clear()
        return chart
    elif target_score == 1000000:
        return chart
    linear_chart: defaultdict[float, list[NoteRef]] = defaultdict(list)
    total = 0
    for line in chart.lines:
        for note in line.notes:
            total += 1
            linear_chart[note.seconds].append(NoteRef(note, line))
    result = calc_score(total, target_score, strict)
    if result is None:
        print(f'failed: unable to gather the specified score {target_score}')
        for i in range(1, 500001):
            for fact in (-1, 1):
                delta = i * fact
                score = target_score + delta
                if not (0 <= score <= 1000000):
                    continue
                result = calc_score(total, target_score, strict)
                if result is not None:
                    print(f'found an approximate score that can be obtained: {score}')
                    break
    assert result is not None
    perfect, good, miss, combo = result
    not_bad = perfect + good
    return chart


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
    pointer_id: int


class VirtualTouchEvent(NamedTuple):
    pos: Position
    action: TouchAction
    pointer_id: int

    def __str__(self) -> str:
        return f'''TouchEvent<{self.pointer_id} {self.action.name} @ ({self.pos.real:4.2f}, {self.pos.imag:4.2f})>'''

    def to_serializable(self) -> bytes:
        return struct.pack('!BIdd', self.action.value, self.pointer_id, self.pos.real, self.pos.imag)

    @classmethod
    def from_serializable(cls, data: bytes) -> Self:
        action, pointer_id, x, y = struct.unpack('!BIdd', data)
        return VirtualTouchEvent(complex(x, y), TouchAction(action), pointer_id)

    def _map_to(self, x_offset: int, y_offset: int, x_scale: float, y_scale: float) -> TouchEvent:
        return TouchEvent(
            pos=(x_offset + round(self.pos.real * x_scale), y_offset + round(self.pos.imag * y_scale)),
            action=self.action,
            pointer_id=self.pointer_id,
        )


AnswerType: TypeAlias = list[tuple[int, list[TouchEvent]]]
RawAnswerType: TypeAlias = list[tuple[int, list[VirtualTouchEvent]]]


class WindowGeometry(NamedTuple):
    x: int
    y: int
    w: int
    h: int


def remap_events(screen: ScreenUtil, geometry: WindowGeometry, answer: RawAnswerType) -> AnswerType:
    x_scale = geometry.w / screen.width
    y_scale = geometry.h / screen.height
    return [
        (
            ts,
            [
                TouchEvent(
                    (geometry.x + round(event.pos.real * x_scale), geometry.y + round(event.pos.imag * y_scale)),
                    event.action,
                    event.pointer_id,
                )
                for event in events
            ],
        )
        for ts, events in answer
    ]


def dump_data(screen: ScreenUtil, ans: RawAnswerType) -> bytes:
    result = bytearray(b'PSAP' + struct.pack('!II', screen.width, screen.height))
    for ts, events in ans:
        result.extend(struct.pack('!iB', ts, len(events)))
        for event in events:
            result.extend(event.to_serializable())
    return result


def load_data(content: bytes) -> tuple[ScreenUtil, RawAnswerType]:
    reader = BytesIO(content)
    assert reader.read(4) == b'PSAP'
    width, height = struct.unpack('!II', reader.read(8))
    ans = []
    while True:
        ts_bytes = reader.read(4)
        if not ts_bytes:
            break
        (ts,) = struct.unpack('!i', ts_bytes)
        (length,) = struct.unpack('!b', reader.read(1))
        ans.append((ts, [VirtualTouchEvent.from_serializable(reader.read(21)) for _ in range(length)]))
    return ScreenUtil(width, height), ans


class AlgorithmConfigure(TypedDict):
    algo1_flick_start: int
    algo1_flick_end: int
    algo1_flick_direction: int
    algo1_sample_delay: int
    algo1_target_score: int
    algo1_strict_mode: bool
    algo2_flick_start: int
    algo2_flick_end: int
    algo2_flick_direction: int
    algo2_target_score: int
    algo2_strict_mode: bool
    algo2_continue_when_failed: bool


__all__ = ['TouchAction', 'VirtualTouchEvent', 'TouchEvent', 'distance_of', 'ScreenUtil']
