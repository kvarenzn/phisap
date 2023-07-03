"""保守的指针规划算法"""

import math
import cmath
from typing import NamedTuple
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from .algo_base import TouchAction, VirtualTouchEvent, distance_of, ScreenUtil
from basis import Chart, NoteType, Position, Vector

from rich.console import Console
from rich.progress import track


@dataclass
class Pointer:
    pid: int
    pos: Position
    timestamp: int
    occupied: int = 0


class FrameEventAction(Enum):
    TAP = 0
    DRAG = 1
    FLICK_START = 2
    FLICK = 3
    FLICK_END = 4
    HOLD_START = 5
    HOLD = 6
    HOLD_END = 7


class FrameEvent(NamedTuple):
    action: FrameEventAction
    point: Position
    id: int


class PointerManager:
    max_pointer_id: int
    pointers: dict[int, Pointer]
    begin: int
    delta: int
    now: int

    recycle_scope: float

    recycled: set[int]
    unused: dict[int, Pointer]
    unused_now: dict[int, Pointer]
    mark_as_released: list[int]

    def __init__(self, recycle_scope: float, begin: int, delta: int = 1) -> None:
        self.recycle_scope = recycle_scope
        self.begin = begin
        self.max_pointer_id = begin
        self.pointers = {}
        self.recycled = set()
        self.unused = {}
        self.delta = delta
        self.unused_now = {}
        self.mark_as_released = []

    def _new(self) -> int:
        if not self.recycled:
            pid = self.max_pointer_id
            self.max_pointer_id += self.delta
            return pid
        return self.recycled.pop()

    def _del(self, pointer_id: int) -> None:
        self.recycled.add(pointer_id)
        if len(self.recycled) == (self.max_pointer_id - self.begin) / self.delta:
            self.max_pointer_id = self.begin
            self.recycled.clear()

    def acquire(self, event: FrameEvent, new: bool = True) -> tuple[int, bool]:
        event_id = event.id
        if event_id in self.pointers:
            ptr = self.pointers[event_id]
            ptr.timestamp = self.now
            ptr.pos = event.point
            return ptr.pid, False
        if not new:
            nearest_distance = self.recycle_scope
            nearest_pid = None
            for pid, ptr in self.unused.items():
                if (d := distance_of(event.point, ptr.pos)) < nearest_distance:
                    nearest_pid = ptr.pid
                    nearest_distance = d
            if nearest_pid is not None:
                ptr = self.unused[nearest_pid]
                del self.unused[nearest_pid]
                ptr.timestamp = self.now
                ptr.pos = event.point
                ptr.occupied = 0
                self.pointers[event_id] = ptr
                return ptr.pid, False
        pid = self._new()
        self.pointers[event_id] = Pointer(pid, event.point, self.now)
        return pid, True

    def release(self, event: FrameEvent) -> None:
        event_id = event.id
        if event_id in self.pointers:
            ptr = self.pointers[event_id]
            self.unused_now[ptr.pid] = ptr
            self.mark_as_released.append(event_id)

    def recycle(self, is_keyframe: bool):
        marked = []
        for event_id in self.mark_as_released:
            del self.pointers[event_id]
        self.mark_as_released = []
        if is_keyframe:
            for ptr in self.unused.values():
                ptr.occupied += 1
                if ptr.occupied > 0:
                    yield ptr.pid, ptr.timestamp + 1, ptr.pos
                    self._del(ptr.pid)
                    marked.append(ptr.pid)
        for pid in marked:
            del self.unused[pid]
        self.unused |= self.unused_now
        self.unused_now = {}

        if len(self.unused) + len(self.pointers) > 10:
            raise RuntimeError(
                f'unused: {len(self.unused)} & pointers: {len(self.pointers)} are on screen @ {self.now}'
            )

    def finish(self):
        for ptr in self.unused.values():
            yield ptr.pid, ptr.timestamp + 1, ptr.pos
        for ptr in self.unused_now.values():
            yield ptr.pid, ptr.timestamp + 1, ptr.pos
        for ptr in self.pointers.values():
            yield ptr.pid, ptr.timestamp + 1, ptr.pos


def solve(chart: Chart, console: Console) -> tuple[ScreenUtil, dict[int, list[VirtualTouchEvent]]]:
    screen = ScreenUtil(chart.screen_width, chart.screen_height)

    flick_start = -30
    flick_end = 30
    flick_duration = flick_end - flick_start

    frames: defaultdict[int, list[FrameEvent]] = defaultdict(list)

    def add_frame_event(milliseconds: int, action: FrameEventAction, point: Position, id: int):
        frames[milliseconds].append(FrameEvent(action, point, id))

    current_event_id = 0

    def flick_pos(pos: Position, offset: int, rot_vec: Vector) -> Position:
        rate = 1 - 2 * (offset - flick_start) / flick_duration
        return pos - rot_vec.conjugate() * screen.flick_radius * rate

    console.print('开始规划')

    # 统计frames
    for line in track(chart.judge_lines, description='正在统计帧...', console=console):
        for note in line.notes:
            ms = round(note.seconds * 1000)
            line_pos = line.position[note.seconds]
            delta = note.offset
            alpha = line.angle[note.seconds]
            rotation: Vector = cmath.exp(alpha * 1j)
            note_pos = line_pos + rotation * delta

            match note.type:
                case NoteType.TAP:
                    add_frame_event(ms, FrameEventAction.TAP, screen.remap(note_pos, rotation), current_event_id)
                case NoteType.DRAG:
                    add_frame_event(ms, FrameEventAction.DRAG, screen.remap(note_pos, rotation), current_event_id)
                case NoteType.FLICK:
                    if not screen.visible(note_pos):
                        # 给DESTRUCTION 3,2,1打个补丁
                        # 这首歌的IN难度的最后一个flick是在屏幕外判定的，你敢信？
                        # 这个flick的触发时刻为26752，然而它所在的判定线在26752时刻时的位置在(w/2, -h/2)
                        # 然而人类是可以正常触发这个flick的判定的
                        # 这是因为这个flick在(w/2, h/2)的位置闪了几下
                        # 根据Phigros的判定机制，相当于这个flick可以同时在(w/2, h/2)和(w/2, -h/2)判定
                        # 然而(w/2, -h/2)的位置不可能达到，所以相当于是在(w/2, h/2)判定了
                        # 但是phisap是不知道这个机制的
                        # 它遇到了(w/2, -h/2)这个flick，只会尝试使用recalc_pos在屏幕内找一个判定点
                        # 然而这是不可能做到的，因为这个flick的偏转角度是90度，也就是说是平行于屏幕宽边的
                        # 因此recalc_pos的算法便失效了，因为不可能计算出一个屏幕内的判定点
                        # 为了应对这种情况，我们需要微调flick触发时间
                        # 尝试在稍靠前或稍靠后的时间戳中找到一个判定点在屏幕内的时间戳
                        # 对于DESTRUCTION 3,2,1，在之后的一个时间戳(26753)，判定点的位置便是(w/2, h/2)
                        # 也就是在屏幕的中心
                        found = False
                        for dt in range(-10, 10):  # 查找的范围为[event.time - 3, event.time + 3]
                            new_time = note.seconds + dt * line.beat_duration(note.seconds)
                            new_line_pos = line.position[new_time]
                            new_alpha = line.angle[new_time]
                            new_rot_vec = cmath.exp(new_alpha * 1j)
                            new_note_pos = new_line_pos + new_rot_vec * delta
                            if screen.visible(new_note_pos):
                                found = True
                                console.print(
                                    f'[red]微调判定时间：flick(pos=({(note_pos.real, note_pos.imag)}), time={note.seconds}) => flick(pos=({(new_note_pos.real, new_note_pos.imag)}), time={new_time})[/red]'
                                )
                                rotation = new_rot_vec
                                note_pos = new_note_pos
                                break

                        if not found:
                            # 对于另外一些情况，我们没有找到这个时间戳
                            # 这是我们假设此处使用了垂直判定机制，使用recalc_pos找到一个屏幕内的可行判定点
                            note_pos = screen.remap(note_pos, rotation)
                            console.print(f'[red]微调失败，采取备用方案 => flick(pos=({(note_pos.real, note_pos.imag)})[/red]')

                    add_frame_event(
                        ms + flick_start,
                        FrameEventAction.FLICK_START,
                        screen.remap(flick_pos(note_pos, flick_start, rotation), rotation),
                        current_event_id,
                    )
                    for offset in range(flick_start + 1, flick_end):
                        add_frame_event(
                            ms + offset,
                            FrameEventAction.FLICK,
                            screen.remap(flick_pos(note_pos, offset, rotation), rotation),
                            current_event_id,
                        )
                    add_frame_event(
                        ms + flick_end,
                        FrameEventAction.FLICK_END,
                        screen.remap(flick_pos(note_pos, flick_end, rotation), rotation),
                        current_event_id,
                    )
                case NoteType.HOLD:
                    hold_ms = math.ceil(note.hold * 1000)
                    add_frame_event(ms, FrameEventAction.HOLD_START, screen.remap(note_pos, rotation), current_event_id)
                    for offset in range(1, hold_ms):
                        new_time = (ms + offset) / 1000
                        angle = line.angle[new_time]
                        add_frame_event(
                            ms + offset,
                            FrameEventAction.HOLD,
                            screen.remap(line.pos(new_time, note.offset), cmath.exp(angle * 1j)),
                            current_event_id,
                        )
                    new_time = (ms + hold_ms) / 1000
                    angle = line.angle[new_time]
                    add_frame_event(
                        ms + hold_ms,
                        FrameEventAction.HOLD_END,
                        screen.remap(line.pos(new_time, note.offset), cmath.exp(angle * 1j)),
                        current_event_id,
                    )
            current_event_id += 1

    console.print(f'统计完毕，当前谱面共计{len(frames)}帧')

    pointers = PointerManager((chart.screen_width + chart.screen_height) / 10, 1000)

    result: defaultdict[int, list[VirtualTouchEvent]] = defaultdict(list)

    def add_touch_event(milliseconds: int, pos: Position, action: TouchAction, pointer_id: int):
        result[milliseconds].append(VirtualTouchEvent(pos, action, pointer_id))

    for ms, frame in track(sorted(frames.items()), description='正在规划触控事件...', console=console):
        pointers.now = ms
        is_keyframe = False
        for note in frame:
            match note.action:
                case FrameEventAction.TAP:
                    add_touch_event(ms, note.point, TouchAction.DOWN, pointers.acquire(note)[0])
                    pointers.release(note)
                    is_keyframe = True
                case FrameEventAction.DRAG:
                    pid, new = pointers.acquire(note, new=False)
                    act = TouchAction.DOWN if new else TouchAction.MOVE
                    add_touch_event(ms, note.point, act, pid)
                    pointers.release(note)
                case FrameEventAction.FLICK_START:
                    pid, new = pointers.acquire(note, new=False)
                    act = TouchAction.DOWN if new else TouchAction.MOVE
                    add_touch_event(ms, note.point, act, pid)
                case FrameEventAction.FLICK | FrameEventAction.HOLD:
                    add_touch_event(ms, note.point, TouchAction.MOVE, pointers.acquire(note)[0])
                case FrameEventAction.FLICK_END | FrameEventAction.HOLD_END:
                    add_touch_event(ms, note.point, TouchAction.MOVE, pointers.acquire(note)[0])
                    pointers.release(note)
                case FrameEventAction.HOLD_START:
                    add_touch_event(ms, note.point, TouchAction.DOWN, pointers.acquire(note)[0])
                    is_keyframe = True

        for pid, ts, line_pos in pointers.recycle(is_keyframe):
            add_touch_event(ts, line_pos, TouchAction.UP, pid)

    for pid, ts, line_pos in pointers.finish():
        add_touch_event(ts, line_pos, TouchAction.UP, pid)
    console.print('规划完毕.')
    return screen, result
