from collections import defaultdict
from functools import partial
import math
import cmath
import re
from typing import TypedDict, NotRequired, NamedTuple, Generator, Any, Self
from enum import Enum
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from basis import Vector, Position, NoteType
from bamboo import Bamboo, BrokenBamboo, LivingBamboo

from rich.console import Console

from algo.base import TouchAction

from pec import PecBpsInfo, PecChart
from pgr import PgrChart
from rpe import RpeChart
from easing import LVALUE
from rpe import RPE_EASING_FUNCS


class VisualNoteItem(NamedTuple):
    type: NoteType
    bottom_middle: Position
    rotation: Vector
    height: float


class VisualLineItem(NamedTuple):
    center: Position
    rotation: Vector
    opacity: float


class VisualPointerItem(NamedTuple):
    center: Position
    opacity: float


class VisualNote(NamedTuple):
    type: NoteType
    time: float
    offset: Vector
    hold: float
    speed: float
    floor: float
    above: bool
    scale: float = 1
    fake: bool = False


class VisualJudgeLine(metaclass=ABCMeta):
    notes: list[VisualNote]
    position: Bamboo[Position]
    floor: Bamboo[float]
    rotation: Bamboo[float]
    opacity: Bamboo[float]


class VisualChart(metaclass=ABCMeta):
    offset: float
    lines: list[VisualJudgeLine]
    screen_size: Vector


class VisualPgrNoteDict(TypedDict):
    type: int
    time: int
    positionX: float
    holdTime: float
    speed: float
    floorPosition: float


class VisualPgrSpeedEventDict(TypedDict):
    startTime: float
    endTime: float
    value: float


class VisualPgrNormalEventDict(TypedDict):
    startTime: float
    endTime: float
    start: float
    end: float
    start2: NotRequired[float]
    end2: NotRequired[float]


class VisualPgrJudgeLineDict(TypedDict):
    bpm: float
    notesAbove: list[VisualPgrNoteDict]
    notesBelow: list[VisualPgrNoteDict]
    speedEvents: list[VisualPgrSpeedEventDict]
    judgeLineMoveEvents: list[VisualPgrNormalEventDict]
    judgeLineRotateEvents: list[VisualPgrNormalEventDict]
    judgeLineDisappearEvents: list[VisualPgrNormalEventDict]


class VisualPgrChartDict(TypedDict):
    formatVersion: int
    offset: float
    judgeLineList: list[VisualPgrJudgeLineDict]


class VisualPgrJudgeLine(VisualJudgeLine):
    _NOTE_TYPES = [NoteType.UNKNOWN, NoteType.TAP, NoteType.DRAG, NoteType.HOLD, NoteType.FLICK]

    def __init__(self, dic: VisualPgrJudgeLineDict, format_version: int) -> None:
        self.bpm = dic['bpm']
        beats_length = 1.875 / self.bpm
        self.notes = []
        note_factor = 0.9 if format_version == 3 else 40
        floor_factor = 5.4 if format_version == 3 else 260
        for note in dic['notesAbove']:
            self.notes.append(
                VisualNote(
                    self._NOTE_TYPES[note['type']],
                    note['time'] * beats_length,
                    note['positionX'] * note_factor,
                    note['holdTime'] * beats_length,
                    note['speed'] * floor_factor,
                    note['floorPosition'] * floor_factor,
                    True,
                )
            )
        for note in dic['notesBelow']:
            self.notes.append(
                VisualNote(
                    self._NOTE_TYPES[note['type']],
                    note['time'] * beats_length,
                    note['positionX'] * note_factor,
                    note['holdTime'] * beats_length,
                    note['speed'] * floor_factor,
                    note['floorPosition'] * floor_factor,
                    False,
                )
            )

        baseline = 0
        self.floor = BrokenBamboo[float]()
        for event in dic['speedEvents']:
            if event['startTime'] == event['endTime']:
                continue
            start = event['startTime'] * beats_length
            end = event['endTime'] * beats_length
            delta = (end - start) * event['value'] * floor_factor
            self.floor.cut(start, end, baseline, baseline + delta)
            baseline += delta

        self.position = BrokenBamboo[Position]()
        if format_version == 1:
            for event in dic['judgeLineMoveEvents']:
                sv = event['start']
                ev = event['end']
                self.position.cut(
                    event['startTime'] * beats_length,
                    event['endTime'] * beats_length,
                    Position(sv // 1000, sv % 1000),
                    Position(ev // 1000, ev % 1000),
                )
        elif format_version == 3:
            for event in dic['judgeLineMoveEvents']:
                assert 'start2' in event and 'end2' in event
                self.position.cut(
                    event['startTime'] * beats_length,
                    event['endTime'] * beats_length,
                    Position(event['start'] * 16, 9 * event['start2']),
                    Position(event['end'] * 16, 9 * event['end2']),
                )

        self.rotation = BrokenBamboo[float]()
        for event in dic['judgeLineRotateEvents']:
            self.rotation.cut(
                event['startTime'] * beats_length,
                event['endTime'] * beats_length,
                math.radians(event['start']),
                math.radians(event['end']),
            )

        self.opacity = BrokenBamboo[float]()
        for event in dic['judgeLineDisappearEvents']:
            self.opacity.cut(
                event['startTime'] * beats_length,
                event['endTime'] * beats_length,
                event['start'],
                event['end'],
            )


class VisualPgrChart(VisualChart):
    def __init__(self, dic: VisualPgrChartDict) -> None:
        format_version = dic['formatVersion']
        print(format_version)
        self.offset = dic['offset']
        self.lines = [VisualPgrJudgeLine(line, format_version) for line in dic['judgeLineList']]
        if format_version == 1:
            self.screen_size = Vector(880, 520)
        else:
            self.screen_size = Vector(16, 9)


@dataclass
class VisualPecNote:
    type: NoteType
    time: float
    offset: Position
    speed: float
    scale: float
    above: bool
    end_time: float | None = None
    fake: bool = False

    def sp(self, speed: float) -> Self:
        self.speed = speed
        return self

    def sc(self, scale: float) -> Self:
        self.scale = scale
        return self


class VisualPecJudgeLine(VisualJudgeLine):
    chart: 'VisualPecChart | None'
    rotation: LivingBamboo[float]
    position: LivingBamboo[Position]
    opacity: LivingBamboo[float]
    speed: LivingBamboo[float]
    floor: LivingBamboo[float]

    def __init__(self) -> None:
        self.notes = []
        self.rotation = LivingBamboo[float]()
        self.position = LivingBamboo[Position]()
        self.opacity = LivingBamboo[float]()
        self.speed = LivingBamboo[float]()
        self.floor = LivingBamboo[float]()
        self.chart = None

    def finish(self, notes: list[VisualPecNote]) -> None:
        floor = 0
        timestamp = 0
        seg = None
        velocity = 0
        for seg in self.speed.joints:
            delta = seg.timestamp - timestamp
            floor += delta * velocity
            self.floor.cut(seg.timestamp, floor, RPE_EASING_FUNCS[0])
            velocity = seg.value
            timestamp = seg.timestamp

        if seg:
            self.floor.cut(114514, (114514 - timestamp) * seg.value)
        for note in notes:
            self.notes.append(
                VisualNote(
                    note.type,
                    note.time,
                    note.offset,
                    0 if note.end_time is None else note.end_time - note.time,
                    note.speed * (self.speed @ note.time),
                    self.floor @ note.time,
                    note.above,
                    note.scale,
                    note.fake,
                )
            )


class VisualPecChart(VisualChart):
    _NOTE_TYPES = [NoteType.UNKNOWN, NoteType.TAP, NoteType.HOLD, NoteType.FLICK, NoteType.DRAG]
    _SPEED_FACTOR = 700 / 5.85
    bpss: list

    def __init__(self, content: str) -> None:
        self.screen_size = Vector(2048, 1400)
        self.offset = 0
        self.bpss = []
        self.notes = defaultdict(list)
        self.lines_map = defaultdict(VisualPecJudgeLine)

        content = re.sub(r'''["'+eghijkloqstuwxyzA-Z*/\\]''', '', content)
        content = (
            '\n'.join(
                re.sub(r'\s+', ' ', line.strip()).replace(' ', '(', 1).replace(' ', ',') + ')'
                for line in content.splitlines()
                if line
            )
            .replace('\n#', '.sp')
            .replace('\n&', '.sc')
        )

        global_vars = {
            name: getattr(self, '_' + name) for name in ['off', 'bp', 'cv', 'cp', 'cd', 'ca', 'cm', 'cr', 'cf']
        } | {'__builtins__': {}}
        for i in range(1, 5):
            global_vars[f'n{i}'] = partial(self._note, i)
        exec(
            'off(' + content,
            global_vars,
            {},
        )

        self.lines = []
        for line_id in sorted(self.lines_map.keys()):
            line = self.lines_map[line_id]
            line.finish(self.notes[line_id])
            self.lines.append(line)

    def _note(self, note_type: int, line_number: int, *args) -> VisualPecNote:
        # the tap note
        note_type_enum = self._NOTE_TYPES[note_type]
        if note_type_enum == NoteType.HOLD:
            start_beats, end_beats, position_x, above, fake = args
            start = self._beats_to_seconds(start_beats)
            end = self._beats_to_seconds(end_beats)
        else:
            beats, position_x, above, fake = args
            start = self._beats_to_seconds(beats)
            end = None
        note = VisualPecNote(note_type_enum, start, position_x, 1.0, 1.0, above == 1, end, fake=bool(fake))
        self.notes[line_number].append(note)
        return note

    def _off(self, offset: int) -> None:
        # TODO: why?
        self.offset = offset / 1000 - 0.15

    def _bp(self, beats: float, bpm: float) -> None:
        bps = bpm / 60
        if not self.bpss:
            self.bpss.append(PecBpsInfo(0, beats, bps))
            return
        seconds_passed, beats_passed, last_bps = self.bpss[-1]
        seconds_passed += (beats - beats_passed) / last_bps
        self.bpss.append(PecBpsInfo(seconds_passed, beats, bps))

    def _beats_to_seconds(self, beats: float) -> float:
        for seconds, beats_begin, bps in reversed(self.bpss):
            if beats >= beats_begin:
                return seconds + (beats - beats_begin) / bps
        raise RuntimeError('???')

    def _cv(self, line_number: int, beats: float, speed: float) -> None:
        # speed event
        seconds = self._beats_to_seconds(beats)
        self.lines_map[line_number].speed.cut(seconds, speed * self._SPEED_FACTOR)

    def _cp(self, line_number: int, beats: float, x: float, y: float) -> None:
        # set position
        seconds = self._beats_to_seconds(beats)
        self.lines_map[line_number].position.cut(seconds, complex(x, y))

    def _cd(self, line_number: int, beats: float, degree: float) -> None:
        # set degree
        seconds = self._beats_to_seconds(beats)
        self.lines_map[line_number].rotation.cut(seconds, -math.radians(degree))

    def _ca(self, line_number: int, beats: float, opacity: float) -> None:
        # set opacity
        seconds = self._beats_to_seconds(beats)
        self.lines_map[line_number].opacity.cut(seconds, opacity / 255)

    def _cm(self, line_number: int, start_beats: float, end_beats: float, x: float, y: float, easing_type: int) -> None:
        # motion event
        seconds_start = self._beats_to_seconds(start_beats)
        seconds_end = self._beats_to_seconds(end_beats)
        self.lines_map[line_number].position.embed(
            seconds_start, seconds_end, complex(x, y), RPE_EASING_FUNCS[easing_type]
        )

    def _cr(self, line_number: int, start_beats: float, end_beats: float, end: float, easing_type: int) -> None:
        # rotate event
        seconds_start = self._beats_to_seconds(start_beats)
        seconds_end = self._beats_to_seconds(end_beats)
        line = self.lines_map[line_number]
        line.rotation.embed(seconds_start, seconds_end, -math.radians(end), RPE_EASING_FUNCS[easing_type])

    def _cf(self, line_number: int, start_beats: float, end_beats: float, value: float) -> None:
        # opacity event
        start = self._beats_to_seconds(start_beats)
        end = self._beats_to_seconds(end_beats)
        self.lines_map[line_number].opacity.embed(start, end, value / 255, RPE_EASING_FUNCS[0])


if __name__ == '__main__':
    import pyglet
    from pyglet.window import key
    import time
    import json

    def render_chart(chart: VisualChart, time: float) -> Generator[VisualLineItem | VisualNoteItem, Any, None]:
        for line in chart.lines:
            position = line.position @ time
            line_rotation = line.rotation @ time
            rotation = cmath.exp(complex(imag=line_rotation))
            yield VisualLineItem(position, rotation, line.opacity @ time)
            for note in line.notes:
                if time > note.time + note.hold:
                    continue

                height = note.floor - line.floor @ time
                if not note.above:
                    height = -height

                if note.type == NoteType.HOLD:
                    # hold的rotation是float，而不是complex，因为我们在绘制hold时只需要偏转角度
                    if time <= note.time:
                        note_height = note.speed * note.hold
                        if not note.above:
                            note_height = -note_height
                        yield VisualNoteItem(
                            note.type, position + (note.offset + height * 1j) * rotation, line_rotation, note_height
                        )
                    else:
                        note_height = note.speed * (note.hold + note.time - time)
                        if not note.above:
                            note_height = -note_height
                        yield VisualNoteItem(
                            note.type,
                            position + note.offset * rotation,
                            line_rotation,
                            note_height,
                        )
                else:
                    yield VisualNoteItem(note.type, position + (note.offset + height * 1j) * rotation, rotation, 0)

    WINDOW_SIZE = (1280, 720)
    WINDOW_WIDTH, WINDOW_HEIGHT = WINDOW_SIZE

    window = pyglet.window.Window(width=WINDOW_WIDTH, height=WINDOW_HEIGHT)

    start = 0

    # chart = VisualPgrChart(json.load(open('Assets/Tracks/Burn.NceS.0/Chart_IN.json')))
    chart = VisualPgrChart(json.load(open('Assets/Tracks/Nhelv.Silentroom.0/Chart_IN.json')))
    # chart = VisualPgrChart(json.load(open('Assets/Tracks/Nhelv.Silentroom.0/Chart_IN.json')))
    # chrt = PgrChart(json.load(open('Assets/Tracks/DESTRUCTION321.Normal1zervsBrokenNerdz.0/Chart_AT.json')))
    # chrt = RpeChart(json.load(open('../phira/1837/volcanic (full version)(From Malody).json')))
    # chrt = PecChart(open('./98527886.json').read())
    # from algo.algo3 import solve
    # screen, ans = solve(chrt, {}, Console())
    # verify answer
    # ptrs = defaultdict(bool)
    # for ts, events in ans:
    #     assert ts % 8 == 0
    #     this_round = set()
    #     for event in events:
    #         if event.pointer_id in this_round:
    #             print(f'ts = {ts}, {events}')
    #         this_round.add(event.pointer_id)
    #         match event.action:
    #             case TouchAction.DOWN:
    #                 assert not ptrs[event.pointer_id], f'DOWN(ts={ts}, id={event.pointer_id})'
    #                 ptrs[event.pointer_id] = True
    #             case TouchAction.MOVE:
    #                 assert ptrs[event.pointer_id], f'MOVE(ts={ts}, id={event.pointer_id}, pos={event.pos})'
    #             case TouchAction.UP:
    #                 assert ptrs[event.pointer_id], f'UP(ts={ts}, id={event.pointer_id})'
    #                 ptrs[event.pointer_id] = False
    # assert not any(ptrs.values())
    # print('验证通过')
    # exit()
    # chart = VisualPecChart(open('./98527886.json').read())
    print(f'共计{len(chart.lines)}根判定线')
    scale = (WINDOW_WIDTH / chart.screen_size.real, WINDOW_HEIGHT / chart.screen_size.imag)

    colors = [
        (10, 195, 255),  # TAP
        (240, 237, 105),  # DRAG
        (0, 255, 255),  # HOLD
        (254, 67, 101),  # FLICK
    ]
    note_radius = 50
    line_radius = 10000
    paused = False

    label = pyglet.text.Label(font_name='Fira Code', font_size=20, x=0, y=0, anchor_x='left', anchor_y='bottom')

    @window.event
    def on_draw():
        window.clear()
        shapes = []
        batch = pyglet.graphics.Batch()
        now = start if paused else time.monotonic() - start
        label.text = f'{int(now // 60):02d}:{now % 60:06.3f}'
        label.draw()
        for item in render_chart(chart, now):
            match item:
                case VisualLineItem(center=center, rotation=rotation, opacity=opacity):
                    position = Position(center.real * scale[0], center.imag * scale[1])
                    left = position + rotation * line_radius
                    right = position - rotation * line_radius
                    line = pyglet.shapes.Line(left.real, left.imag, right.real, right.imag, 4, (255, 255, 255), batch)
                    line.opacity = int(255 * opacity)
                    shapes.append(line)
                case VisualNoteItem(type=NoteType.HOLD):
                    bottom_middle = Position(item.bottom_middle.real * scale[0], item.bottom_middle.imag * scale[1])
                    hold = pyglet.shapes.Rectangle(bottom_middle.real, bottom_middle.imag, note_radius * 2, item.height * scale[1], (10, 195, 255, 200), batch)
                    hold.anchor_position = (note_radius, 0)
                    hold.rotation = math.degrees(-item.rotation.real)
                    shapes.append(hold)
                case _:
                    position = Position(item.bottom_middle.real * scale[0], item.bottom_middle.imag * scale[1])
                    left = position + item.rotation * note_radius
                    right = position - item.rotation * note_radius
                    shapes.append(
                        pyglet.shapes.Line(
                            left.real, left.imag, right.real, right.imag, 10, colors[item.type.value], batch
                        )
                    )
        batch.draw()

    keys = {key.LEFT: False, key.RIGHT: False, key.COMMA: False, key.PERIOD: False, key.UP: False, key.DOWN: False}

    @window.event
    def on_key_press(symbol: int, modifiers):
        global paused, start
        match symbol:
            case key.SPACE:
                if paused:
                    paused = False
                    start = time.monotonic() - start
                else:
                    paused = True
                    start = time.monotonic() - start
            case key._0:
                if not paused:
                    paused = True
                start = 0
            case key.LEFT | key.RIGHT | key.COMMA | key.PERIOD | key.UP | key.DOWN:
                keys[symbol] = True
                if not paused:
                    paused = True
                    start = time.monotonic() - start

    @window.event
    def on_key_release(symbol: int, modifiers):
        match symbol:
            case key.LEFT | key.RIGHT | key.COMMA | key.PERIOD | key.UP | key.DOWN:
                keys[symbol] = False

    def update(_):
        global start
        if keys[key.UP]:
            start -= 0.1
        elif keys[key.DOWN]:
            start += 0.1
        elif keys[key.LEFT]:
            start -= 0.01
        elif keys[key.RIGHT]:
            start += 0.01
        elif keys[key.COMMA]:
            start -= 0.001
        elif keys[key.PERIOD]:
            start += 0.001
        if start < 0:
            start = 0

    pyglet.clock.schedule_interval(update, 1 / 60)

    start = time.monotonic()
    pyglet.app.run(1 / 30)
