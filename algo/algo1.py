# 保守的指针规划算法

# 将每个note视作一个整体进行处理，几押就分配几个pointer
# 将flick拆分为FLICK_START, 数个FLICK和一个FLICK_END，共用一个pointer_id
# 将hold拆分为HOLD_START，数个HOLD和一个HOLD_END，同样共用一个pointer_id

import math
import cmath
from typing import NamedTuple, Iterable
from itertools import chain
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
    occupied_pointers: dict[int, Pointer]  # event_id => Pointer
    begin: int
    delta: int
    now: int

    idle_pointers: set[int]
    unused: dict[int, Pointer]
    mark_as_released: set[int]
    inserted_liftup_events: list[tuple[int, int, Position]]

    def __init__(self, pointer_ids: Iterable[int]) -> None:
        self.occupied_pointers = {}
        self.idle_pointers = set(pointer_ids)
        self.unused = {}
        self.inserted_liftup_events = []
        self.mark_as_released = set()

    def acquire(self, event: FrameEvent, new: bool = True) -> tuple[int, bool]:
        event_id = event.id

        # 如果event.action in (FLICK, FLICK_END, HOLD, HOLD_END)
        # 忽略，直接让它们使用之前的pointer id即可
        if event_id in self.occupied_pointers:
            ptr = self.occupied_pointers[event_id]
            ptr.timestamp = self.now
            ptr.pos = event.point
            return ptr.pid, False

        # 如果不需要发送"DOWN"事件，即不需要“新的”指针
        # 那么直接将屏幕上现有的指针移动过来就行
        if not new:
            nearest_distance = float('inf')
            nearest_pid = None
            # 移动一个离目标最近的指针
            for pid, ptr in self.unused.items():
                if (d := distance_of(event.point, ptr.pos)) < nearest_distance:
                    nearest_pid = ptr.pid
                    nearest_distance = d
            # 如果找到了，更新信息并返回
            if nearest_pid is not None:
                ptr = self.unused[nearest_pid]
                del self.unused[nearest_pid]
                ptr.timestamp = self.now
                ptr.pos = event.point
                self.occupied_pointers[event_id] = ptr
                return ptr.pid, False

        # 需要分配一个新的指针
        if self.idle_pointers:
            pid = self.idle_pointers.pop()
            self.occupied_pointers[event_id] = Pointer(pid, event.point, self.now)
            return pid, True
        else:
            nearest_distance = math.inf
            nearest_pid = None
            for pid, ptr in self.unused.items():
                if (d := distance_of(event.point, ptr.pos)) < nearest_distance:
                    nearest_pid = ptr.pid
                    nearest_distance = d
            if nearest_pid is not None:
                ptr = self.unused[nearest_pid]
                del self.unused[nearest_pid]
                self.inserted_liftup_events.append((ptr.pid, ptr.timestamp + 1, ptr.pos))
                ptr.timestamp = self.now
                ptr.pos = event.point
                self.occupied_pointers[event_id] = ptr
                return ptr.pid, True
        raise RuntimeError('no free pointers!')

    def release(self, event: FrameEvent) -> None:
        event_id = event.id

        if event_id not in self.occupied_pointers:
            return

        # 指针已经完成了它的使命，不过先不要抬起
        # 现在屏幕上放着，只标记它“已经没有用了”
        self.mark_as_released.add(event_id)

    def recycle(self) -> None:
        # 在击打note完毕后，回收所有已经没有用的pointer
        # 即将它们从屏幕上移除(抬起)
        for event_id in self.mark_as_released:
            ptr = self.occupied_pointers[event_id]
            self.unused[ptr.pid] = ptr
            del self.occupied_pointers[event_id]
        self.mark_as_released.clear()

    def force_liftup_unused(self) -> list[tuple[int, int, Position]]:
        result = []
        for ptr in self.unused.values():
            result.append((ptr.pid, ptr.timestamp + 1, ptr.pos))
            self.idle_pointers.add(ptr.pid)
        self.unused.clear()
        return result

    def finish(self):
        # 回收所有还在屏幕上的指针
        for ptr in chain(self.unused.values(), self.occupied_pointers.values()):
            yield ptr.pid, ptr.timestamp + 1, ptr.pos


def solve(chart: Chart, console: Console) -> tuple[ScreenUtil, dict[int, list[VirtualTouchEvent]]]:
    # 获得虚拟屏幕的尺寸数据
    screen = ScreenUtil(chart.screen_width, chart.screen_height)

    # 定义flick的触发手法
    # 如果滑键在时刻t判定，那么在时刻t+flick_start开始滑，滑到时刻t+flick_end
    # 一共滑flick_duration毫秒
    flick_start = -30
    flick_end = 30
    flick_duration = flick_end - flick_start

    # 帧数据，每一帧都是note被击打时的快照
    # 保存当时所有(比如多押的时候)被击打note的必要数据，如类型，位置，方向等
    frames: defaultdict[int, list[FrameEvent]] = defaultdict(list)

    # 工具函数，向帧中添加一个note
    def add_frame_event(milliseconds: int, action: FrameEventAction, point: Position, id: int):
        frames[milliseconds].append(FrameEvent(action, point, id))

    # 每个note分配一个自增id，起始为0
    # 主要用于标记和处理flick和hold(因为这两种note是被拆分处理的)
    # 对于同一个flick(或hold)，FLICK_START, FLICK和FLICK_END(或HOLD_START, HOLD和HOLD_END)有相同的id
    current_note_id = 0

    # 滑键手势函数，目前定义为平行于滑键的方向滑动
    def flick_pos(pos: Position, offset: int, rot_vec: Vector) -> Position:
        rate = 1 - 2 * (offset - flick_start) / flick_duration
        return pos - rot_vec.conjugate() * screen.flick_radius * rate

    # 统计帧数据
    for line in track(chart.lines, description='正在统计帧...', console=console):
        for note in line.notes:
            ms = round(note.seconds * 1000)
            line_pos = line.position @ note.seconds
            delta = note.offset
            alpha = line.angle @ note.seconds
            rotation: Vector = cmath.exp(alpha * 1j)
            note_pos = line_pos + rotation * delta

            match note.type:
                case NoteType.TAP:
                    add_frame_event(ms, FrameEventAction.TAP, screen.remap(note_pos, rotation), current_note_id)
                case NoteType.DRAG:
                    add_frame_event(ms, FrameEventAction.DRAG, screen.remap(note_pos, rotation), current_note_id)
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
                        for dt in range(1, 10):  # 查找的范围为[event.time - 10, event.time + 10]
                            new_time = note.seconds + dt * line.beat_duration(note.seconds)
                            new_line_pos = line.position @ new_time
                            new_alpha = line.angle @ new_time
                            new_rot_vec = cmath.exp(new_alpha * 1j)
                            new_note_pos = new_line_pos + new_rot_vec * delta
                            if screen.visible(new_note_pos):
                                found = True
                                console.print(
                                    f'[yellow]微调判定时间：flick(pos=({(note_pos.real, note_pos.imag)}), time={note.seconds}) => flick(pos=({(new_note_pos.real, new_note_pos.imag)}), time={new_time})[/yellow]'
                                )
                                rotation = new_rot_vec
                                note_pos = new_note_pos
                                break

                        if not found:
                            # 对于另外一些情况，我们没有找到这个时间戳
                            # 这是我们假设此处使用了垂直判定机制，使用recalc_pos找到一个屏幕内的可行判定点
                            note_pos = screen.remap(note_pos, rotation)
                            console.print(
                                f'[yellow]微调失败，采取备用方案 => flick(pos=({(note_pos.real, note_pos.imag)})[/yellow]'
                            )

                    add_frame_event(
                        ms + flick_start,
                        FrameEventAction.FLICK_START,
                        screen.remap(flick_pos(note_pos, flick_start, rotation), rotation),
                        current_note_id,
                    )
                    for offset in range(flick_start + 1, flick_end):
                        add_frame_event(
                            ms + offset,
                            FrameEventAction.FLICK,
                            screen.remap(flick_pos(note_pos, offset, rotation), rotation),
                            current_note_id,
                        )
                    add_frame_event(
                        ms + flick_end,
                        FrameEventAction.FLICK_END,
                        screen.remap(flick_pos(note_pos, flick_end, rotation), rotation),
                        current_note_id,
                    )
                case NoteType.HOLD:
                    hold_ms = math.ceil(note.hold * 1000)
                    add_frame_event(ms, FrameEventAction.HOLD_START, screen.remap(note_pos, rotation), current_note_id)
                    for offset in range(1, hold_ms):
                        new_time = (ms + offset) / 1000
                        angle = line.angle @ new_time
                        add_frame_event(
                            ms + offset,
                            FrameEventAction.HOLD,
                            screen.remap(line.pos(new_time, note.offset), cmath.exp(angle * 1j)),
                            current_note_id,
                        )
                    new_time = (ms + hold_ms) / 1000
                    angle = line.angle @ new_time
                    add_frame_event(
                        ms + hold_ms,
                        FrameEventAction.HOLD_END,
                        screen.remap(line.pos(new_time, note.offset), cmath.exp(angle * 1j)),
                        current_note_id,
                    )
            current_note_id += 1

    pointers_count = max(len(frame) for _, frame in frames.items())
    console.print(f'统计完毕，当前谱面共计{len(frames)}帧，最多需要{pointers_count}押')
    if pointers_count > 10:
        console.print('[red]规划失败，请使用激进算法[/red]')
        raise RuntimeError('planning failed')

    pointers = PointerManager(range(1000, 1001 + pointers_count))  # pointer id从1000到1010，共计10个

    # 规划结果
    result: defaultdict[int, list[VirtualTouchEvent]] = defaultdict(list)

    # 向规划结果中添加事件
    def add_touch_event(milliseconds: int, pos: Position, action: TouchAction, pointer_id: int):
        result[milliseconds].append(VirtualTouchEvent(pos, action, pointer_id))

    # 根据统计得到的关键帧数据进行规划
    for ms, frame in track(sorted(frames.items()), description='正在规划触控事件...', console=console):
        pointers.now = ms
        for note in frame:
            match note.action:
                case FrameEventAction.TAP:
                    add_touch_event(ms, note.point, TouchAction.DOWN, pointers.acquire(note)[0])
                    pointers.release(note)
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
        pointers.recycle()

        for pid, ts, line_pos in pointers.inserted_liftup_events:
            add_touch_event(ts, line_pos, TouchAction.UP, pid)

        pointers.inserted_liftup_events.clear()

    for pid, ts, line_pos in pointers.finish():
        add_touch_event(ts, line_pos, TouchAction.UP, pid)
    console.print('规划完毕.')
    return screen, result


__all__ = ['solve']

if __name__ == '__main__':
    from pgr import PgrChart
    import json

    console = Console()
    chart = PgrChart(json.load(open('../Assets/Tracks/Rrharil.TeamGrimoire.0/Chart_AT.json')))
    for i in range(100):
        try:
            # solve(chart, console, i / 10)
            print('ok, scope =', i / 10)
        except RuntimeError:
            pass
