# 较为激进的规划算法

# 在保守算法的基础上，尽量合并note的判定区，即判定区有重叠部分的多个note视作一个note
# 这样就可以用单个事件触发多个note的判定
# 此外，尽量最小幅度地移动指针

# 将flick视作一堆drag，将hold视作tap+一堆drag

import math
import cmath
from typing import Iterator, NamedTuple
from dataclasses import dataclass
from collections import defaultdict

from basis import Chart, NoteType, Position, Vector
from .algo_base import TouchAction, VirtualTouchEvent, ScreenUtil, RawAnswerType, AlgorithmConfigure


from rich.console import Console
from rich.progress import track


class PlainNote(NamedTuple):
    type: NoteType
    timestamp: int
    pos: Position
    angle: Vector


class Frame:
    """一帧长度为1ms"""

    screen: ScreenUtil
    timestamp: int
    unallocated: defaultdict[NoteType, list[PlainNote]]

    def __init__(self, screen: ScreenUtil, timestamp: int) -> None:
        self.screen = screen
        self.timestamp = timestamp
        self.unallocated = defaultdict(list)

    def add(self, note_type: NoteType, pos: Position, angle: Vector) -> None:
        pos = self.screen.remap(pos, cmath.exp(angle * 1j))
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
    screen: ScreenUtil
    frames: dict[int, Frame]

    def __init__(self, screen: ScreenUtil) -> None:
        self.screen = screen
        self.frames = {}

    def __getitem__(self, timestamp: int) -> Frame:
        if timestamp not in self.frames:
            self.frames[timestamp] = Frame(self.screen, timestamp)
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
    return abs(note2.pos - note1.pos)


class PointerAllocator:
    flick_start: int
    flick_end: int
    flick_duration: int
    flick_rotate_factor: complex
    screen: ScreenUtil
    pointers: list[Pointer]
    events: defaultdict[int, list[VirtualTouchEvent]]
    last_timestamp: int | None
    now: int

    def __init__(self, screen: ScreenUtil, flick_start: int, flick_end: int, flick_direction: int, max_pointers_count: int = 10, begin_at: int = 1000):
        self.screen = screen
        self.flick_start = flick_start
        self.flick_end = flick_end
        self.flick_duration = self.flick_end - self.flick_start
        self.flick_rotate_factor = 1j if flick_direction == 0 else 1
        self.recycle_scope = (screen.width + screen.height) / 20
        self.pointers = [Pointer(i + begin_at) for i in range(max_pointers_count)]
        self.events = defaultdict(list)
        self.last_timestamp = None

    def _find_available_pointers(self, note: PlainNote) -> Pointer | None:
        """查找当前屏幕上可以直接拿来用的指针
        查找条件：距离目标点RECYCLE_SCOPE个单位之内的、已经被废弃的指针
        """
        angle = note.angle
        for pointer in self.pointers:
            if pointer.note is None or pointer.age <= 0:  # 忽略闲置指针和正在FLICK的指针
                continue
            if abs(((pointer.note.pos - note.pos) * angle.conjugate()).real) < self.recycle_scope:
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
        angle = note.angle
        note_pos = 0j
        pos = self.screen.remap(note.pos, angle)
        for delta in range(self.flick_duration):
            rate = 1 - 2 * delta / self.flick_duration
            note_pos = pos + angle * self.flick_rotate_factor * rate * self.screen.flick_radius
            self._insert(self.now + delta, VirtualTouchEvent(note_pos, TouchAction.MOVE, pointer.id))
        pointer.note = note._replace(pos=note_pos)
        pointer.age = -self.flick_duration

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

    def done(self) -> RawAnswerType:
        self.withdraw()
        return [(ts, events) for ts, events in sorted(self.events.items())]


def solve(chart: Chart, config: AlgorithmConfigure, console: Console) -> tuple[ScreenUtil, RawAnswerType]:
    flick_start = config['algo2_flick_start']
    flick_end = config['algo2_flick_end']
    flick_direction = config['algo2_flick_direction']
    screen = ScreenUtil(chart.screen_width, chart.screen_height)
    frames = Frames(screen)

    # 统计frames
    for line in track(chart.lines, description='统计操作帧...', console=console):
        for note in line.notes:
            ms = round(note.seconds * 1000)
            angle = cmath.exp(line.angle @ note.seconds * 1j)
            pos = line.position @ note.seconds + angle * note.offset
            match note.type:
                case NoteType.HOLD:
                    hold_ms = math.ceil(note.hold * 1000)
                    frames[ms].add(NoteType.TAP, pos, angle)
                    for offset in range(1, hold_ms + 1):
                        time = (ms + offset) / 1000
                        angle = cmath.exp(line.angle @ time * 1j)
                        frames[ms + offset].add(NoteType.DRAG, line.pos(time, note.offset), angle)
                case NoteType.FLICK:
                    if not screen.visible(pos):
                        # 这块的逻辑在algo1.py中有解释
                        for dt in range(1, 10):
                            new_time = note.seconds + dt * line.beat_duration(note.seconds)
                            new_line_pos = line.position @ new_time
                            new_angle = cmath.exp(line.angle @ new_time * 1j)
                            new_note_pos = new_line_pos + angle * note.offset
                            if screen.visible(new_note_pos):
                                console.print(
                                    f'[yellow]微调判定时间：flick(pos=({(pos.real, pos.imag)}), time={note.seconds}s) => flick(pos=({(new_note_pos.real, new_note_pos.imag)}), time={new_time}s)[/yellow]'
                                )
                                angle = new_angle
                                pos = new_note_pos
                                break
                            new_time = note.seconds - dt * line.beat_duration(note.seconds)
                            new_line_pos = line.position @ new_time
                            new_angle = cmath.exp(line.angle @ new_time * 1j)
                            new_note_pos = new_line_pos + angle * note.offset
                            if screen.visible(new_note_pos):
                                console.print(
                                    f'[yellow]微调判定时间：flick(pos=({(pos.real, pos.imag)}), time={note.seconds}s) => flick(pos=({(new_note_pos.real, new_note_pos.imag)}), time={new_time}s)[/yellow]'
                                )
                                angle = new_angle
                                pos = new_note_pos
                                break

                    frames[ms + flick_start].add(NoteType.FLICK, pos, angle)
                case _:
                    frames[ms].add(note.type, pos, angle)

    console.print(f'统计完毕，当前谱面共计{len(frames)}帧')

    allocator = PointerAllocator(screen, flick_start, flick_end, flick_direction)

    for frame in track(frames, description='规划触控事件...'):
        allocator.allocate(frame)

    console.print('规划完毕.')

    return screen, allocator.done()


__all__ = ['solve']
