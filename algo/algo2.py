import math
from sys import stdout
from typing import Optional, Iterator

from .algo_base import TouchAction, TouchEvent
from chart import Chart
from note import Note


class SimpleNote:
    note_type: int
    timestamp: int
    pos: tuple[float, float]
    angle: float

    def __init__(self, note_type: int, timestamp: int, pos: tuple[float, float], angle: float):
        self.note_type = note_type
        self.timestamp = timestamp
        self.pos = pos
        self.angle = angle


class Frame:
    timestamp: int

    unallocated: list[list[SimpleNote]]
    allocated: list[list[SimpleNote]]

    def __init__(self, timestamp: int):
        self.timestamp = timestamp

        self.unallocated = [[] for _ in range(4)]
        self.allocated = [[] for _ in range(4)]

    def add(self, note_type: int, pos: tuple[float, float], angle: float):
        self.unallocated[note_type - 1].append(SimpleNote(note_type, self.timestamp, pos, angle))

    def taps(self) -> Iterator[SimpleNote]:
        taps = self.unallocated[Note.TAP - 1]
        while taps:
            yield taps.pop(0)

    def drags(self) -> Iterator[SimpleNote]:
        drags = self.unallocated[Note.DRAG - 1]
        while drags:
            yield drags.pop(0)

    def flicks(self) -> Iterator[SimpleNote]:
        flicks = self.unallocated[Note.FLICK - 1]
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
    note: Optional[SimpleNote]
    age: int

    def __init__(self, pid: int, note: Optional[SimpleNote] = None, age: int = 0):
        self.id = pid
        self.note = note
        self.age = age


def distance_of(note1: Optional[SimpleNote], note2: SimpleNote) -> float:
    if note1 is None:
        return math.inf
    x1, y1 = note1.pos
    x2, y2 = note2.pos
    return (x2 - x1) ** 2 + (y2 - y1) ** 2


flick_start = -50
flick_end = 50
flick_scale_factor = 100


class PointerAllocator:
    pointers: list[Pointer]
    events: dict[int, list[TouchEvent]]
    last_timestamp: Optional[int]
    now: int

    def __init__(self, max_pointers_count: int = 10, begin_at: int = 1000):
        self.pointers = [Pointer(i + begin_at) for i in range(max_pointers_count)]
        self.events = {}
        self.last_timestamp = None

    def alloc(self, note: SimpleNote) -> Pointer:
        usable_pointers = [p for p in self.pointers if p.note is None or p.age > 0]
        assert usable_pointers
        return min(usable_pointers, key=lambda p: distance_of(p.note, note))  # 优先使用废弃的Pointer

    def check(self, note: SimpleNote) -> Optional[Pointer]:
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

    def _insert(self, timestamp: int, event: TouchEvent):
        if timestamp not in self.events:
            self.events[timestamp] = []
        self.events[timestamp].append(event)

    def _tap(self, pointer: Pointer, note: SimpleNote):
        if pointer.note is not None:
            self._insert(self.now - pointer.age + 1, TouchEvent(pointer.note.pos, TouchAction.UP, pointer.id))
        pointer.note = note
        pointer.age = 0
        self._insert(self.now, TouchEvent(note.pos, TouchAction.DOWN, pointer.id))

    def _flick(self, pointer: Pointer, note: SimpleNote):
        if pointer.note is None:
            self._insert(self.now, TouchEvent(note.pos, TouchAction.DOWN, pointer.id))
        else:
            self._insert(self.now, TouchEvent(note.pos, TouchAction.MOVE, pointer.id))
        alpha = note.angle
        sa, ca = math.sin(alpha), math.cos(alpha)
        px, py = note.pos
        for off in range(flick_end - flick_start):
            offset = off + flick_start
            px, py = note.pos[0] + math.sin(offset * math.pi / 10) * flick_scale_factor * sa, note.pos[1] + math.sin(
                offset * math.pi / 10) * flick_scale_factor * ca
            self._insert(self.now, TouchEvent((px, py), TouchAction.MOVE, pointer.id))
        note.pos = (px, py)
        pointer.note = note
        pointer.age = flick_start - flick_end

    def _drag(self, pointer: Pointer, note: SimpleNote):
        if pointer.note is None:
            self._insert(self.now, TouchEvent(note.pos, TouchAction.DOWN, pointer.id))
        else:
            self._insert(self.now, TouchEvent(note.pos, TouchAction.MOVE, pointer.id))
        self._insert(self.now, TouchEvent(note.pos, TouchAction.MOVE, pointer.id))
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


def solve(chart: Chart) -> dict[int, list[TouchEvent]]:
    frames = Frames()

    print('正在统计帧...', end='')
    stdout.flush()
    # 统计frames
    for line in chart.judge_lines:
        for note in line.notes_above + line.notes_below:
            ms = round(line.seconds(note.time) * 1000)
            off_x = note.x * 72
            x, y = line.pos(note.time)
            alpha = - line.angle(note.time) * math.pi / 180
            pos = x + off_x * math.cos(alpha), y + off_x * math.sin(alpha)
            if note.typ == Note.HOLD:
                hold_ms = math.ceil(line.seconds(note.hold) * 1000)
                frames[ms].add(Note.TAP, pos, alpha)
                for offset in range(1, hold_ms + 1):
                    frames[ms + offset].add(Note.DRAG,
                                            line.pos_of(note, line.time((ms + offset) / 1000)),
                                            alpha)
            elif note.typ == Note.FLICK:
                frames[ms + flick_start].add(Note.FLICK, pos, alpha)
            else:
                frames[ms].add(note.typ, pos, alpha)

    print(f'统计完毕，当前谱面共计{len(frames)}帧')

    allocator = PointerAllocator()

    print('正在规划触控事件...', end='')
    stdout.flush()

    for frame in frames:
        allocator.allocate(frame)

    print('规划完毕.')
    return allocator.done()
