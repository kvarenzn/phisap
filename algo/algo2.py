# 较为激进的规划算法

import math
from typing import Iterator, NamedTuple
from dataclasses import dataclass
from collections import defaultdict

from chart import Chart
from note import NoteType
from .algo_base import TouchAction, VirtualTouchEvent, recalc_pos, in_screen


from rich.console import Console
from rich.progress import track


class PlainNote(NamedTuple):
    type: NoteType
    timestamp: int
    pos: tuple[float, float]
    angle: float


class Frame:
    """一帧长度为10ms"""

    timestamp: int
    unallocated: defaultdict[NoteType, list[PlainNote]]

    def __init__(self, timestamp: int) -> None:
        self.timestamp = timestamp
        self.unallocated = defaultdict(list)

    def add(self, note_type: NoteType, pos: tuple[float, float], angle: float) -> None:
        pos = recalc_pos(pos, math.sin(angle), math.cos(angle))
        self.unallocated[note_type].append(PlainNote(note_type, self.timestamp, pos, angle))

    def taps(self) -> Iterator[PlainNote]:
        taps = self.unallocated[NoteType.TAP]
        for tap in taps:
            yield tap
        taps.clear()

    def drags(self) -> Iterator[PlainNote]:
        drags = self.unallocated[NoteType.DRAG]
        for drag in drags:
            yield drag
        drags.clear()

    def flicks(self) -> Iterator[PlainNote]:
        flicks = self.unallocated[NoteType.FLICK]
        for flick in flicks:
            yield flick
        flicks.clear()


class Frames:
    frames: dict[int, Frame]

    def __init__(self) -> None:
        self.frames = {}

    def __getitem__(self, timestamp: int) -> Frame:
        if timestamp not in self.frames:
            self.frames[timestamp] = Frame(timestamp)
        return self.frames[timestamp]

    def __iter__(self) -> Iterator[Frame]:
        return iter(sorted(self.frames.values(), key=lambda f: f.timestamp))

    def __len__(self) -> int:
        return len(self.frames)


@dataclass
class Pointer:
    id: int  # 唯一id，用于发送指令
    note: PlainNote | None = None  # 和这个指针绑定的note
    age: int = 0  # 该指针在屏幕上存在的时间，负数表示该指针正在触发某个note


def distance_of(note1: PlainNote | None, note2: PlainNote | None) -> float:
    if note1 is None or note2 is None:
        return math.inf
    x1, y1 = note1.pos
    x2, y2 = note2.pos
    return (x2 - x1) ** 2 + (y2 - y1) ** 2


FLICK_START = -30
FLICK_END = 30
FLICK_DURATION = FLICK_END - FLICK_START
FLICK_RADIUS = 30


class PointerAllocator:
    pointers: list[Pointer]
    events: defaultdict[int, list[VirtualTouchEvent]]
    last_timestamp: int | None
    now: int

    def __init__(self, max_pointers_count: int = 10, begin_at: int = 1000):
        self.pointers = [Pointer(i + begin_at) for i in range(max_pointers_count)]
        self.events = defaultdict(list)
        self.last_timestamp = None

    def _find_available_pointers(self, note: PlainNote) -> Pointer | None:
        """查找当前屏幕上可以直接拿来用的指针
        查找条件：距离目标点100个单位之内的、已经被废弃的指针
        """
        ox, oy = note.pos
        ca, sa = math.cos(note.angle), math.sin(note.angle)
        for pointer in self.pointers:
            if pointer.note is None or pointer.age <= 0:  # 忽略闲置指针和正在FLICK的指针
                continue
            px, py = pointer.note.pos
            if abs((px - ox) * ca + (py - oy) * sa) < 100:
                return pointer
        return None

    def _alloc(self, note: PlainNote) -> Pointer:
        available_pointers = [p for p in self.pointers if p.note is None or p.age > 0]
        assert available_pointers
        return min(available_pointers, key=lambda p: distance_of(p.note, note))  # 优先使用废弃的Pointer

    def _insert(self, timestamp: int, event: VirtualTouchEvent) -> None:
        self.events[timestamp].append(event)

    def _tap(self, pointer: Pointer, note: PlainNote) -> None:
        if pointer.note is not None:
            # 如果分配的是"旧"指针，先抬起，再落下
            self._insert(self.now - pointer.age + 1, VirtualTouchEvent(pointer.note.pos, TouchAction.UP, pointer.id))
        pointer.note = note
        pointer.age = 0
        self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.DOWN, pointer.id))

    def _flick(self, pointer: Pointer, note: PlainNote) -> None:
        if pointer.note is None:
            self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.DOWN, pointer.id))
        else:
            self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.MOVE, pointer.id))
        alpha = note.angle
        sa, ca = math.sin(alpha), math.cos(alpha)
        px, py = recalc_pos(note.pos, sa, ca)  # 对于flick，需先判断是否在屏幕内判定，否则之后生成的一系列滑动事件将会被recalc_pos给映射到同一点，使得flick漏判
        x, y = recalc_pos(note.pos, sa, ca)
        for delta in range(FLICK_DURATION):
            rate = 1 - 2 * delta / FLICK_DURATION
            px, py = (x - rate * FLICK_RADIUS * sa, y + rate * FLICK_RADIUS * ca)
            self._insert(self.now + delta, VirtualTouchEvent((px, py), TouchAction.MOVE, pointer.id))
        pointer.note = note._replace(pos=(px, py))
        pointer.age = FLICK_START - FLICK_END

    def _drag(self, pointer: Pointer, note: PlainNote) -> None:
        if pointer.note is None:
            self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.DOWN, pointer.id))
        else:
            self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.MOVE, pointer.id))
        self._insert(self.now, VirtualTouchEvent(note.pos, TouchAction.MOVE, pointer.id))
        pointer.note = note
        pointer.age = 0

    def allocate(self, frame: Frame) -> None:
        # 更新pointer age
        self.now = frame.timestamp
        if self.last_timestamp is not None:
            for pointer in self.pointers:
                pointer.age += self.now - self.last_timestamp

        # 步骤1：分配tap
        for note in frame.taps():
            pointer = self._alloc(note)
            self._tap(pointer, note)

        # 步骤2: 分配flick
        for note in frame.flicks():
            pointer = self._alloc(note)
            self._flick(pointer, note)

        # 步骤3：分配drag
        for note in frame.drags():
            pointer = self._find_available_pointers(note)
            if pointer:
                pointer.age = 0
                continue
            pointer = self._alloc(note)
            self._drag(pointer, note)

        self.last_timestamp = frame.timestamp

    def withdraw(self) -> None:
        """收回在屏幕上的所有pointer"""
        if self.last_timestamp is None:
            return

        final = self.last_timestamp + 1
        for pointer in self.pointers:
            if pointer.note:
                self._insert(final, VirtualTouchEvent(pointer.note.pos, TouchAction.UP, pointer.id))

    def done(self) -> defaultdict[int, list[VirtualTouchEvent]]:
        self.withdraw()
        return self.events


def solve(chart: Chart, console: Console) -> defaultdict[int, list[VirtualTouchEvent]]:
    frames = Frames()

    # 统计frames
    for line in track(chart.judge_lines, description='统计操作帧...', console=console):
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
                    if not in_screen(pos):
                        # 这块的逻辑在algo1.py中有解释
                        px, py = pos
                        for dt in range(-3, 4):
                            new_time = note.time + dt
                            xx, yy = line.pos(new_time)
                            new_alpha = -line.angle(new_time) * math.pi / 180
                            new_sa = math.sin(new_alpha)
                            new_ca = math.cos(new_alpha)
                            pxx, pyy = xx + off_x * new_ca, yy + off_x * new_sa
                            if in_screen((pxx, pyy)):
                                console.print(f'[red]微调判定时间：flick(pos=({px, py}), time={note.time}) => flick(pos=({pxx}, {pyy}), time={new_time})[/red]')
                                alpha = new_alpha
                                pos = (pxx, pyy)
                                break

                    frames[ms + FLICK_START].add(NoteType.FLICK, pos, alpha)
                case _:
                    frames[ms].add(note.type, pos, alpha)

    console.print(f'统计完毕，当前谱面共计{len(frames)}帧')

    allocator = PointerAllocator()

    for frame in track(frames, description='规划触控事件...'):
        allocator.allocate(frame)

    return allocator.done()


__all__ = ['solve']
