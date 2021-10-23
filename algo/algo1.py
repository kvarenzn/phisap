import math
from typing import Any

from .algo_base import TouchAction, TouchEvent
from chart import Chart
from note import Note
from utils import distance_of


class Pointer:
    pid: int
    pos: tuple[float, float]
    timestamp: int
    occupied: int

    def __init__(self, pid: int, pos: tuple[float, float], timestamp: int):
        self.pid = pid
        self.pos = pos
        self.timestamp = timestamp
        self.occupied = 0

    def __repr__(self):
        return f'Pointer(pid={self.pid}, pos={self.pos}, timestamp={self.timestamp})'


class Pointers:
    max_pointer_id: int
    pointers: dict[int, Pointer]
    begin: int
    direction: int
    now: int

    recycled: set[int]
    unused: dict[int, Pointer]
    unused_now: dict[int, Pointer]
    mark_as_released: list[int]

    def __init__(self, begin: int, direction: int = 1):
        self.begin = begin
        self.max_pointer_id = begin
        self.pointers = {}
        self.recycled = set()
        self.unused = {}
        self.direction = direction
        self.unused_now = {}
        self.mark_as_released = []

    def _new(self) -> int:
        if not self.recycled:
            pid = self.max_pointer_id
            self.max_pointer_id += self.direction
            return pid
        return self.recycled.pop()

    def _del(self, pointer_id: int):
        self.recycled.add(pointer_id)
        if len(self.recycled) == (self.max_pointer_id - self.begin) / self.direction:
            self.max_pointer_id = self.begin
            self.recycled.clear()

    def acquire(self, note: dict[str, Any], new: bool = True) -> tuple[int, bool]:
        event_id = note['i']
        if event_id in self.pointers:
            ptr = self.pointers[event_id]
            ptr.timestamp = self.now
            ptr.pos = note['p']
            return ptr.pid, False
        if not new:
            nearest_distance = 200
            nearest_pid = None
            for pid, ptr in self.unused.items():
                if (d := distance_of(note['p'], ptr.pos)) < nearest_distance:
                    nearest_pid = ptr.pid
                    nearest_distance = d
            if nearest_pid is not None:
                ptr = self.unused[nearest_pid]
                del self.unused[nearest_pid]
                ptr.timestamp = self.now
                ptr.pos = note['p']
                ptr.occupied = 0
                self.pointers[event_id] = ptr
                return ptr.pid, False
        pid = self._new()
        self.pointers[event_id] = Pointer(pid, note['p'], self.now)
        return pid, True

    def release(self, note: dict[str, Any]):
        event_id = note['i']
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
                f'unused: {len(self.unused)} & pointers: {len(self.pointers)} are on screen @ {self.now}')

    def finish(self):
        for ptr in self.unused.values():
            yield ptr.pid, ptr.timestamp + 1, ptr.pos
        for ptr in self.unused_now.values():
            yield ptr.pid, ptr.timestamp + 1, ptr.pos
        for ptr in self.pointers.values():
            yield ptr.pid, ptr.timestamp + 1, ptr.pos


def solve(chart: Chart) -> dict[int, list[TouchEvent]]:
    flick_start = -30
    flick_end = 30
    flick_scale_factor = 100

    frames: dict[int, list] = {}
    result: dict[int, list[TouchEvent]] = {}

    def insert(milliseconds: int, event: dict):
        if milliseconds not in frames:
            frames[milliseconds] = []
        frames[milliseconds].append(event)

    def ins(milliseconds: int, event: TouchEvent):
        if milliseconds not in result:
            result[milliseconds] = []
        result[milliseconds].append(event)

    current_event_id = 0

    def flick_pos(px: float, py: float, offset: int) -> tuple[float, float]:
        return px + math.sin(offset * math.pi / 10) * flick_scale_factor * sa, py + math.sin(
            offset * math.pi / 10) * flick_scale_factor * ca

    print('正在统计帧...', end='')
    # 统计frames
    for line in chart.judge_lines:
        for note in line.notes_above + line.notes_below:
            ms = round(line.seconds(note.time) * 1000)
            off_x = note.x * 72
            x, y = line.pos(note.time)
            alpha = - line.angle(note.time) * math.pi / 180
            sa = math.sin(alpha)
            ca = math.cos(alpha)
            px, py = x + off_x * ca, y + off_x * sa
            # if not in_rect((px, py), border=0):
            #     continue
            if px < 0 or px > 1280 or py < 0 or py > 720:
                print(f'found: px = {px}, py = {py}')
                continue

            if note.typ == Note.TAP:
                insert(ms, {
                    'a': 'tap',
                    'p': (px, py),
                    'i': current_event_id
                })
            elif note.typ == Note.DRAG:
                insert(ms, {
                    'a': 'drag',
                    'p': (px, py),
                    'i': current_event_id
                })
            elif note.typ == Note.FLICK:
                insert(ms + flick_start, {
                    'a': 'flick_start',
                    # 'p': flick_pos(*line.pos_of(note, line.time(ms + flick_start) / 1000), flick_start),
                    'p': flick_pos(px, py, flick_start),
                    'i': current_event_id
                })
                for offset in range(flick_start + 1, flick_end):
                    insert(ms + offset, {
                        'a': 'flick',
                        # 'p': flick_pos(*line.pos_of(note, line.time(ms + offset) / 1000), offset),
                        'p': flick_pos(px, py, offset),
                        'i': current_event_id
                    })
                insert(ms + flick_end, {
                    'a': 'flick_end',
                    # 'p': flick_pos(*line.pos_of(note, line.time(ms + flick_end) / 1000), flick_end),
                    'p': flick_pos(px, py, flick_end),
                    'i': current_event_id
                })
            elif note.typ == Note.HOLD:
                hold_ms = math.ceil(line.seconds(note.hold) * 1000)
                insert(ms, {
                    'a': 'hold_start',
                    'p': (px, py),
                    'i': current_event_id
                })
                for offset in range(1, hold_ms):
                    insert(ms + offset, {
                        'a': 'hold',
                        'p': line.pos_of(note, line.time((ms + offset) / 1000)),
                        'i': current_event_id
                    })
                insert(ms + hold_ms, {
                    'a': 'hold_end',
                    'p': line.pos_of(note, line.time((ms + hold_ms) / 1000)),
                    'i': current_event_id
                })
            current_event_id += 1

    print(f'统计完毕，当前谱面共计{len(frames)}帧')

    pointers = Pointers(0)

    print('正在规划触控事件...', end='')
    for ms, frame in sorted(frames.items()):
        pointers.now = ms
        is_keyframe = False
        for note in frame:
            action = note['a']
            if action == 'tap':
                ins(ms, TouchEvent(note['p'], TouchAction.DOWN, pointers.acquire(note)[0]))
                pointers.release(note)
                is_keyframe = True

            elif action == 'drag':
                pid, new = pointers.acquire(note, new=False)
                act = TouchAction.DOWN if new else TouchAction.MOVE
                ins(ms, TouchEvent(note['p'], act, pid))
                pointers.release(note)
                # is_keyframe = True

            elif action == 'flick_start':
                pid, new = pointers.acquire(note, new=False)
                act = TouchAction.DOWN if new else TouchAction.MOVE
                ins(ms, TouchEvent(note['p'], act, pid))
            elif action == 'flick':
                ins(ms, TouchEvent(note['p'], TouchAction.MOVE, pointers.acquire(note)[0]))
            elif action == 'flick_end':
                ins(ms, TouchEvent(note['p'], TouchAction.MOVE, pointers.acquire(note)[0]))
                pointers.release(note)

            elif action == 'hold_start':
                ins(ms, TouchEvent(note['p'], TouchAction.DOWN, pointers.acquire(note)[0]))
                is_keyframe = True
            elif action == 'hold':
                ins(ms, TouchEvent(note['p'], TouchAction.MOVE, pointers.acquire(note)[0]))
            elif action == 'hold_end':
                ins(ms, TouchEvent(note['p'], TouchAction.MOVE, pointers.acquire(note)[0]))
                pointers.release(note)

        for pid, ts, pos in pointers.recycle(is_keyframe):
            ins(ts, TouchEvent(pos, TouchAction.UP, pid))

    for pid, ts, pos in pointers.finish():
        ins(ts, TouchEvent(pos, TouchAction.UP, pid))
    print('规划完毕.')
    return result
