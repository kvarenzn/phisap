# 将谱面划分为不同的帧，帧与帧之间相互独立（即上一帧不会影响到下一帧）
# 每帧只包含将（比如TAP和DRAG）或者正在（比如FLICK）判定的note的数据，如位置和偏转角度，其余note均不关心
# 采用125Hz作为基准采样率，即每一帧包含8ms内的所有要判定的note
# 在分配时，我们按顺序从头至尾过一遍所有的帧
# 每个指针理论上有三个状态：
# 空闲：该指针当前不在屏幕上
# 受雇：该指针正在被用于触发某个note的判定
# 休息：该指针当前没有被用于触发任何判定，不过仍然在屏幕上，没有抬起
# 我们的规划遵循使用尽量少的指针的原则，使用贪心算法，优先使用“休息”的指针，实在没辙了再使用“空闲”的指针
# 为了区分这三个状态，我们使用了两个变量用于标记
# on_screen: 布尔值，表明该指针目前是否在屏幕上，用于区分“空闲”状态和其他状态。
# 在实现时，on_screen以一个set代替，如果指针在set内，则表明指针在屏幕上
# expire: 整数，表明该指针被“解雇”的时期。需要跟当前时刻进行比对，如果小于等于当前时刻，则正在”休息“，反之则”受雇“
# 使用“休息”和“空闲”的指针之间的区别还是比较大的。
# 如果使用“休息”的指针，我们只需要发送一个"MOVE"事件就能把它移动到我们期望的位置
# 而使用“空闲”的指针，我们需要发送一个"DOWN"事件，先告知系统屏幕上现在多了个触点。如果只发送"MOVE"在某些系统上是无效的

# 我们在开始时并没有帧的数据，我们需要将谱面转换为帧的列表
# 我们遍历每条判定线上的每个note，根据note的`time`属性（表明该note何时被判定）将他们放到不同的帧内
# 除此之外，我们需要拆分hold（这个想法继承自algo2）
# 根据我的一些实验，hold可能不需要一直按着，中途可以换手，只要一直有指针在判定区内即可
# 也就是说hold可以看成是一个tap + 一系列的drag
# 这样我们就能省不少事

# 每一帧的具体流程分三部分：
# 0. 计算所有在屏幕上的指针的寿命
# 1. 规划flick
# 我搜集并阅读了一些资料，发现flick在判定时是从note落到判定线处开始的
# 也就是说我们不需要在flick落到判定线之前就先在判定区内滑动
# 这样flick实际上可以类比为一个开头不需要tap的hold（因为phigros只检测“滑动”这个动作）
# 与hold不同的是，它要求一直使用相同的指针（因为要追踪指针的移动）
# 所以某种程度来说，flick的要求是最严格的
# 分配时尽量使用“休息”的指针
# 绑定给flick后，我们直接往最后的规划结果里添加全部的滑动事件。并设定该指针的寿命为滑动持续的时间+1
# 2. 规划tap和drag
# 我们这次规划时将利用phigros的垂直判定机制
# 先计算出这一帧中每个tap和drag的判定区。之后我们就不再管具体的“note”了，我们需要的是往每个判定区内分配一个指针
# 为了减少指针的使用，我们求解判定区之间的交集，并使用交集区域代替原有的判定区
# 如果某个交集属于的判定区中的任意一个来自于tap，那么我们标记该区域为“tap区”，否则标记为“drag”区。
# 为了能尽可能多地抵消tap，我们先计算tap的判定区之间的交集，再计算drag，最后合并
# 之后，我们取这个区域的中心点作为我们的触控点
# 与algo2的思路不同的是，到这一步后，我们先考虑drag区，同样是优先选择分配“休息”的指针
# 完事后再考虑"tap"区。这时，能直接MOVE过去的指针都已经分配得差不多了。此时如果屏幕上还有指针，那么也先分配给tap区
# 只不过需要先发送"UP"，再发送"DOWN"


import math
import cmath
from typing import Callable, Iterable, Iterator, NamedTuple
from dataclasses import dataclass
from collections import defaultdict
from shapely import (
    Polygon,
    LineString,
    clip_by_rect,
    buffer,
    Point,
    distance,
    centroid,
    intersects,
    intersection,
    contains,
)

from basis import Chart, NoteType, Position, Vector
from .algo_base import TouchAction, VirtualTouchEvent, ScreenUtil, RawAnswerType, AlgorithmConfigure


from rich.console import Console
from rich.progress import track


# 计算几何辅助类
class CompGeoHelper:
    width: float
    height: float
    diag_length: float
    judge_area_width: float

    @staticmethod
    def _det(a: Position, b: Position) -> float:
        return (a * b.conjugate() * 1j).real

    @staticmethod
    def _line_x_line(line1: tuple[Position, Position], line2: tuple[Position, Position]) -> Position | None:
        dl1 = line1[0] - line1[1]
        dl2 = line2[0] - line2[1]
        xd = Position(dl1.real, dl2.real)
        yd = Position(dl1.imag, dl2.imag)
        di = CompGeoHelper._det(xd, yd)
        if di == 0:
            return None
        d = Position(CompGeoHelper._det(*line1), CompGeoHelper._det(*line2))
        return Position(CompGeoHelper._det(d, xd) / di, CompGeoHelper._det(d, yd) / di)

    @staticmethod
    def _point_in_segment(point: Position, segment: tuple[Position, Position]) -> bool:
        # 如果点point已经在线段segment所在直线上了，判断point是否在线段segment内
        xs = (segment[0].real, segment[1].real)
        ys = (segment[0].imag, segment[1].imag)
        return (min(xs) <= point.real <= max(xs)) and (min(ys) <= point.imag <= max(ys))


    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.judge_area_width = width / 10  # TODO: 验证这个值
        self.height = height
        self.diag_length = abs(complex(width, height))

    def _line_x_screen(self, line: tuple[Position, Position]) -> None | Position | tuple[Position, Position]:
        # 求解直线与屏幕边缘的交点，共三种情况：没有交点，只有一个交点，有两个交点
        # 如果直线与屏幕的一边重合，则认为直线与该边没有交点，共计两个交点

        points = set()
        p = self._line_x_line(line, (Position(0, self.height), Position(self.width, self.height)))
        if p is not None and (0 <= p.real <= self.width):
            points.add(p)
        p = self._line_x_line(line, (Position(0, 0), Position(self.width, 0)))
        if p is not None and (0 <= p.real <= self.width):
            points.add(p)
        p = self._line_x_line(line, (Position(0, 0), Position(0, self.height)))
        if p is not None and (0 <= p.imag <= self.height):
            points.add(p)
        p = self._line_x_line(line, (Position(self.width, 0), Position(self.width, self.height)))
        if p is not None and (0 <= p.imag <= self.height):
            points.add(p)

        if not points:
            return None
        elif len(points) == 1:
            return points.pop()
        else:
            return tuple(points)

    def _calc_judge_norm(self, point: Position, rotation: Vector) -> None | tuple[Position, Position]:
        # 计算过note中心，垂直于note偏转方向，且两端点均在屏幕外的线段
        # 该线段将被用于计算note判定区
        line = (point, point + rotation * 1j)
        res = self._line_x_screen(line)
        if not isinstance(res, tuple):
            return None
        a, b = res
        d = b - a
        d /= abs(d)
        d *= self.diag_length
        return (a - d, b + d)

    def judge_area(self, point: Position, rotation: Vector) -> None | Polygon:
        # 根据中心位置和旋转向量计算note的判定区
        norm = self._calc_judge_norm(point, rotation)
        if norm is None:
            return None
        a, b = norm
        segment = LineString(((a.real, a.imag), (b.real, b.imag)))
        return clip_by_rect(buffer(segment, self.judge_area_width / 2), 0, 0, self.width, self.height)


class PlainNote(NamedTuple):
    timestamp: int
    pos: Position
    angle: Vector


class Frame(NamedTuple):
    """一帧长度为8ms"""

    taps: list[PlainNote]
    drags: list[PlainNote]
    flicks: list[PlainNote]


@dataclass
class Pointer:
    id: int  # 唯一id，用于发送指令
    position: Position  # 指针当前所在位置
    expire: int


def distance_of(note1: PlainNote | None, note2: PlainNote | None) -> float:
    if note1 is None or note2 is None:
        return math.inf
    return abs(note2.pos - note1.pos)


class PointerAllocator:
    flick_duration: int
    flick_rotate_factor: complex
    screen: ScreenUtil
    cghelper: CompGeoHelper
    note_width: float
    pointers: set[int]
    on_screen: list[Pointer]
    events: defaultdict[int, list[VirtualTouchEvent]]
    ts2ms: Callable[[int], int]
    now: int

    def __init__(
        self,
        screen: ScreenUtil,
        cghelper: CompGeoHelper,
        flick_duration: int,
        flick_direction: int,
        pointers: Iterable[int],
        ts2ms: Callable[[int], int],
    ):
        self.screen = screen
        self.cghelper = cghelper
        self.flick_duration = flick_duration
        self.flick_rotate_factor = 1j if flick_direction == 0 else 1
        self.pointers = set(pointers)
        self.on_screen = []
        self.events = defaultdict(list)
        self.ts2ms = ts2ms

    def _alloc(self, judge_area: Polygon, prefer_new: bool) -> Pointer | int:
        # 如果返回Pointer，表明这是“休息”的指针
        # 否则，表明这是“空闲”的指针
        if not prefer_new:
            # 优先使用"休息"的pointer
            on_screen_pointers = [p for p in self.on_screen if p.expire < self.now]
            if on_screen_pointers:
                return min(
                    on_screen_pointers, key=lambda p: distance(Point(p.position.real, p.position.imag), judge_area)
                )
            # 没有，则使用"空闲"的pointer
            if self.pointers:
                return self.pointers.pop()
            # 都没有，寄！
            raise RuntimeError(f'no free pointers @ {self.now}')
        else:
            # 优先使用"空闲"的pointer
            if self.pointers:
                return self.pointers.pop()
            # 没有了，强制使用屏幕上已有的pointer
            on_screen_pointers = [p for p in self.on_screen if p.expire <= self.now]
            if on_screen_pointers:
                return min(
                    on_screen_pointers, key=lambda p: distance(Point(p.position.real, p.position.imag), judge_area)
                )
            # 还是没有，寄！
            raise RuntimeError(f'no free pointers @ {self.now}')

    def _bind(self, pointer: int | Pointer, position: Position, age: int) -> Pointer:
        if isinstance(pointer, int):
            ptr = Pointer(pointer, position, self.now + age)
            self.on_screen.append(ptr)
            return ptr
        else:
            pointer.expire = self.now + age
            pointer.position = position
            return pointer

    def _insert(self, timestamp: int, event: VirtualTouchEvent) -> None:
        self.events[timestamp].append(event)

    def allocate(self, timestamp: int, frame: Frame) -> None:
        # 更新pointer age
        self.now = timestamp

        # 步骤1：分配flick
        for note in frame.flicks:
            rotation = note.angle
            area = self.cghelper.judge_area(note.pos, rotation)
            assert area is not None, note
            pointer = self._alloc(area, prefer_new=False)
            center: Point = centroid(area)
            pos = Position(center.x, center.y)
            if isinstance(pointer, int):
                self._insert(self.now, VirtualTouchEvent(pos, TouchAction.DOWN, pointer))
            else:
                self._insert(self.now, VirtualTouchEvent(pos, TouchAction.MOVE, pointer.id))
            pointer = self._bind(pointer, pos, self.flick_duration + 1)
            note_pos = 0
            for delta in range(1, self.flick_duration + 1):
                rate = 1 - 2 * delta / self.flick_duration
                note_pos = pos + rotation * self.flick_rotate_factor * rate * self.screen.flick_radius
                self._insert(self.now + delta, VirtualTouchEvent(note_pos, TouchAction.MOVE, pointer.id))
            pointer.position = note_pos

        # 步骤2：计算并合并drag和tap的判定区
        taps_area = []
        drags_area = []

        ## 先合并taps
        ## 这时drags_area恒为空
        for note in frame.taps:
            judge_area = self.cghelper.judge_area(note.pos, note.angle)
            assert judge_area is not None, note
            for index, area in enumerate(taps_area):
                if intersects(area, judge_area):
                    taps_area[index] = intersection(area, judge_area)
                    break
            else:
                taps_area.append(judge_area)

        ## 再合并drags
        for note in frame.drags:
            judge_area = self.cghelper.judge_area(note.pos, note.angle)
            assert judge_area is not None, note
            # 如果目前在屏幕上的指针有谁在drag的判定区内，那么视作已经判定成功
            ignore = False
            for pointer in self.on_screen:
                if pointer.expire > timestamp and contains(judge_area, Point(pointer.position.real, pointer.position.imag)):
                    ignore = True
                    break
            if ignore:
                continue
            # 尽量往drags里合并
            for index, area in enumerate(drags_area):
                if intersects(area, judge_area):
                    drags_area[index] = intersection(area, judge_area)
                    break
            else:
                # 如果都没有重合的，那么再往taps里合并
                for index, area in enumerate(taps_area):
                    if intersects(area, judge_area):
                        taps_area[index] = intersection(area, judge_area)
                        break
                else:
                    # 如果还不行，那么就单开一片区域
                    drags_area.append(judge_area)

        # 步骤3：分配指针
        ## 先分配drag
        for area in drags_area:
            pointer = self._alloc(area, prefer_new=False)
            position = centroid(area)
            position = Position(position.x, position.y)
            if isinstance(pointer, int):
                self._insert(self.now, VirtualTouchEvent(position, TouchAction.DOWN, pointer))
            else:
                self._insert(self.now, VirtualTouchEvent(position, TouchAction.MOVE, pointer.id))
            self._bind(pointer, position, 1)

        ## 再分配tap
        for area in taps_area:
            pointer = self._alloc(area, prefer_new=False)
            position = centroid(area)
            position = Position(position.x, position.y)
            if isinstance(pointer, Pointer):
                # 如果分配的是"旧"指针，先抬起，再落下
                self._insert(pointer.expire, VirtualTouchEvent(pointer.position, TouchAction.UP, pointer.id, f'expire = {pointer.expire}'))
            pointer = self._bind(pointer, position, 1)
            self._insert(self.now, VirtualTouchEvent(position, TouchAction.DOWN, pointer.id, f'now = {self.now}'))

        # 步骤4：清理剩余指针
        # 既然已经不需要这些指针了，那就抬起来呗
        rest_pointers = [p for p in self.on_screen if p.expire < timestamp]
        for pointer in rest_pointers:
            self._insert(pointer.expire, VirtualTouchEvent(pointer.position, TouchAction.UP, pointer.id))
            self.on_screen.remove(pointer)
            self.pointers.add(pointer.id)

    def withdraw(self) -> None:
        """收回在屏幕上的所有pointer"""
        for pointer in self.on_screen:
            self._insert(
                pointer.expire, VirtualTouchEvent(pointer.position, TouchAction.UP, pointer.id)
            )

    def done(self) -> RawAnswerType:
        self.withdraw()
        return [(self.ts2ms(ts), events) for ts, events in sorted(self.events.items())]


def solve(chart: Chart, _: AlgorithmConfigure, console: Console) -> tuple[ScreenUtil, RawAnswerType]:
    flick_duration = 3
    flick_direction = 0
    screen = ScreenUtil(chart.screen_width, chart.screen_height)
    cghelper = CompGeoHelper(chart.screen_width, chart.screen_height)
    frames: defaultdict[int, Frame] = defaultdict(lambda: Frame(list(), list(), list()))
    ms2ts = lambda ms: ms >> 3
    ts2ms = lambda ts: ts << 3
    ts2s = lambda ts: ts / 125

    # 统计frames
    for line in track(chart.lines, description='统计操作帧...', console=console):
        for note in line.notes:
            ms = round(note.seconds * 1000)
            timestamp = ms2ts(ms)
            rotation = cmath.exp(line.angle @ note.seconds * 1j)
            pos = line.position @ note.seconds + rotation * note.offset
            match note.type:
                case NoteType.HOLD:
                    frames[timestamp].taps.append(PlainNote(timestamp, pos, rotation))
                    end_timestamp = ms2ts(ms + math.ceil(note.hold * 1000)) + 1
                    for offset in range(timestamp + 1, end_timestamp):
                        time = ts2s(offset)
                        frames[offset].drags.append(
                            PlainNote(offset, line.pos(time, note.offset), cmath.exp(line.angle @ time * 1j))
                        )
                    # TODO: 确认是否需要对从hold中拆出来的每个tap或drag都应用下边的操作(微调偏移，寻找在屏幕内的坐标)
                case _:
                    if not screen.visible(pos) and cghelper.judge_area(pos, rotation) is None:
                        # 这块的逻辑在algo1.py中有解释
                        # 现在对所有的note都应用同样的操作
                        for dt in range(1, 10):
                            for sign in (-1, 1):
                                new_time = note.seconds + dt * sign * line.beat_duration(note.seconds)
                                new_line_pos = line.position @ new_time
                                new_rotation = cmath.exp(line.angle @ new_time * 1j)
                                new_note_pos = new_line_pos + rotation * note.offset
                                if screen.visible(new_note_pos) or cghelper.judge_area(pos, rotation) is not None:
                                    console.print(
                                        f'[yellow]Note(type={note.type}, pos=({(pos.real, pos.imag)}), time={note.seconds}s) => Note(type={note.type}, pos=({(new_note_pos.real, new_note_pos.imag)}), time={new_time}s)[/yellow]'
                                    )
                                    rotation = new_rotation
                                    pos = new_note_pos
                                    break
                            else:
                                continue
                            break
                        else:
                            console.print(
                                f'[yellow]为Note(type={note.type}, pos=({(pos.real, pos.imag)}), time={note.seconds}s)调整偏移失败，将导致不可预测的错误[/yellow]'
                            )
                    plain_note = PlainNote(timestamp, pos, rotation)
                    frame = frames[timestamp]
                    match note.type:
                        case NoteType.FLICK:
                            frame.flicks.append(plain_note)
                        case NoteType.TAP:
                            frame.taps.append(plain_note)
                        case NoteType.DRAG:
                            frame.drags.append(plain_note)

    console.print(f'统计完毕，当前谱面共计{len(frames)}帧')

    allocator = PointerAllocator(screen, cghelper, flick_duration, flick_direction, range(1000, 1011), ts2ms)

    for timestamp, frame in track(sorted(frames.items()), description='规划触控事件...'):
        allocator.allocate(timestamp, frame)

    console.print('规划完毕.')

    return screen, allocator.done()


__all__ = ['solve']
