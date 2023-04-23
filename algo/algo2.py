"""激进的指针规划算法
这种算法把hold拆分成一个tap和若干个drag，各自规划
"""
import math
from sys import stdout
from typing import Iterator
from dataclasses import dataclass
from collections import defaultdict

from chart import Chart
from note import NoteType
from utils import recalc_pos
from .algo_base import TouchAction, VirtualTouchEvent


@dataclass
class PlainNote:
    note_type: int
    timestamp: int
    pos: tuple[float, float]
    angle: float


class Frame:
    timestamp: int
    unallocated: defaultdict[NoteType, list[PlainNote]]

    def __init__(self, timestamp: int):
        self.timestamp = timestamp
        self.unallocated = defaultdict(list)

    def add(self, note_type: NoteType, pos: tuple[float, float], angle: float):
        pos = recalc_pos(pos, math.sin(angle), math.cos(angle))
        self.unallocated[note_type].append(PlainNote(note_type, self.timestamp, pos, angle))

    def taps(self) -> Iterator[PlainNote]:
        taps = self.unallocated[NoteType.TAP]
        while taps:
            yield taps.pop(0)

    def drags(self) -> Iterator[PlainNote]:
        drags = self.unallocated[NoteType.DRAG]
        while drags:
            yield drags.pop(0)

    def flicks(self) -> Iterator[PlainNote]:
        flicks = self.unallocated[NoteType.FLICK]
        while flicks:
            yield flicks.pop(0)


class Frames:
    frames: dict[int, Frame]

    def __init__(self):
        self.frames = {}

    def __getitem__(self, timestamp: int) -> Frame:
        if timestamp not in self.frames:
            self.frames[timestamp] = Frame(timestamp)
        return self.frames[timestamp]

    def __iter__(self) -> Iterator[Frame]:
        return iter(sorted(self.frames.values(), key=lambda f: f.timestamp))

    def __len__(self) -> int:
        return len(self.frames)


class Pointer:
    id: int
    note: PlainNote | None
    age: int

    def __init__(self, pid: int, note: PlainNote | None = None, age: int = 0):
        self.id = pid
        self.note = note
        self.age = age


def distance_of(note1: PlainNote | None, note2: PlainNote | None) -> float:
    if note1 is None or note2 is None:
        return math.inf
    x1, y1 = note1.pos
    x2, y2 = note2.pos
    return (x2 - x1) ** 2 + (y2 - y1) ** 2


FLICK_START = -50
FLICK_END = 50
FLICK_SCALE_FACTOR = 100


class PointerAllocator:
    pointers: list[Pointer]
    events: dict[int, list[VirtualTouchEvent]]
    last_timestamp: int | None
    now: int

    def __init__(self, max_pointers_count: int = 10, begin_at: int = 1000):
        self.pointers = [Pointer(i + begin_at) for i in range(max_pointers_count)]
        self.events = {}
        self.last_timestamp = None

    def alloc(self, note: PlainNote) -> Pointer:
        available_pointers = [p for p in self.pointers if p.note is None or p.age > 0]
        assert available_pointers
        return min(available_pointers, key=lambda p: distance_of(p.note, note))  # 优先使用废弃的Pointer

    def check(self, note: PlainNote) -> Pointer | None:
        ox, oy = note.pos
        ca, sa = math.cos(note.angle), math.sin(note.angle)
        for pointer in self.pointers:
            if pointer.note is None:  # 闲置指针
                continue
            # TODO: 考虑flick在移动时的影响
            px, py = pointer.note.pos
            if abs((px - ox) * ca + (py - oy) * sa) < 100:
                return pointer
        return None

    def _insert(self, timestamp: int, event: VirtualTouchEvent):
        if timestamp not in self.events:
            self.events[timestamp] = []
        self.events[timestamp].append(event)

    def _tap(self, pointer: Pointer, note: PlainNote):
        if pointer.note is not None:
            self._insert(self.now - pointer.age + 1, VirtualTouchEvent(pointer.note.pos, TouchAction.UP, pointer.id))
        pointer.note = note
        pointer.age = 0
        self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.DOWN, pointer.id))

    def _flick(self, pointer: Pointer, note: PlainNote):
        if pointer.note is None:
            self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.DOWN, pointer.id))
        else:
            self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.MOVE, pointer.id))
        alpha = note.angle
        sa, ca = math.sin(alpha), math.cos(alpha)
        px, py = note.pos
        for off in range(FLICK_END - FLICK_START):
            offset = off + FLICK_START
            px, py = (
                note.pos[0] + math.sin(offset * math.pi / 10) * FLICK_SCALE_FACTOR * sa,
                note.pos[1] + math.sin(offset * math.pi / 10) * FLICK_SCALE_FACTOR * ca,
            )
            self._insert(self.now, VirtualTouchEvent((px, py), TouchAction.MOVE, pointer.id))
        note.pos = (px, py)
        pointer.note = note
        pointer.age = FLICK_START - FLICK_END

    def _drag(self, pointer: Pointer, note: PlainNote):
        if pointer.note is None:
            self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.DOWN, pointer.id))
        else:
            self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.MOVE, pointer.id))
        self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.MOVE, pointer.id))
        pointer.note = note
        pointer.age = 0

    def allocate(self, frame: Frame):
        # 更新pointer age
        self.now = frame.timestamp
        if self.last_timestamp is not None:
            for pointer in self.pointers:
                pointer.age += self.now - self.last_timestamp

        # 步骤1：分配tap
        for note in frame.taps():
            pointer = self.alloc(note)
            self._tap(pointer, note)

        # 步骤2: 分配flick
        for note in frame.flicks():
            pointer = self.alloc(note)
            self._flick(pointer, note)

        # 步骤3：分配drag
        for note in frame.drags():
            pointer = self.check(note)
            if pointer:
                pointer.age = 0
                continue
            pointer = self.alloc(note)
            self._drag(pointer, note)

        self.last_timestamp = frame.timestamp

    def done(self):
        return self.events


def solve(chart: Chart) -> dict[int, list[VirtualTouchEvent]]:
    frames = Frames()

    print('正在统计帧...', end='')
    stdout.flush()
    # 统计frames
    for line in chart.judge_lines:
        for note in line.notes_above + line.notes_below:
            ms = round(line.seconds(note.time) * 1000)
            off_x = note.x * 72
            x, y = line.pos(note.time)
            alpha = -line.angle(note.time) * math.pi / 180
            pos = x + off_x * math.cos(alpha), y + off_x * math.sin(alpha)
            match note.type:
                case NoteType.HOLD:
                    hold_ms = math.ceil(line.seconds(note.hold) * 1000)
                    frames[ms].add(NoteType.TAP, pos, alpha)
                    for offset in range(1, hold_ms + 1):
                        alpha = -line.angle(line.time((ms + offset) / 1000)) * math.pi / 180
                        frames[ms + offset].add(
                            NoteType.DRAG, line.pos_of(note, line.time((ms + offset) / 1000)), alpha
                        )
                case NoteType.FLICK:
                    frames[ms + FLICK_START].add(NoteType.FLICK, pos, alpha)
                case _:
                    frames[ms].add(note.type, pos, alpha)

    print(f'统计完毕，当前谱面共计{len(frames)}帧')

    allocator = PointerAllocator()

    print('正在规划触控事件...', end='')
    stdout.flush()

    for frame in frames:
        allocator.allocate(frame)

    print('规划完毕.')
    return allocator.done()
