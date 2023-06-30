from typing import Self, NamedTuple
from functools import partial
from collections import defaultdict
from enum import Enum
import re
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from easing import EasingFunction, EASING_FUNCTIONS
from bamboo import Bamboo


class PecNoteType(Enum):
    TAP = 1
    HOLD = 2
    FLICK = 3
    DRAG = 4


@dataclass
class PecNote:
    type: PecNoteType
    time: float
    position_x: float
    speed: float
    scale: float
    above: bool
    end_time: float | None = None

    def sp(self, speed: float) -> Self:
        self.speed = speed
        return self

    def sc(self, scale: float) -> Self:
        self.scale = scale
        return self


@dataclass
class PecJudgeLine:
    notes: list[PecNote] = field(default_factory=list)
    speed: Bamboo[float] = field(default_factory=Bamboo)
    degree: Bamboo[float] = field(default_factory=Bamboo)
    position: Bamboo[npt.NDArray[np.float_]] = field(default_factory=Bamboo)


class PecBpsInfo(NamedTuple):
    time: float  # seconds
    beats: float  # how many beats have passed
    bps: float  # beats per second


RPE_EASING_FUNCS: list[EasingFunction] = [
    (lambda _: _),
    (lambda _: _),
    EASING_FUNCTIONS['sine_out'],
    EASING_FUNCTIONS['sine_in'],
    EASING_FUNCTIONS['sine_inout'],
    EASING_FUNCTIONS['quad_inout'],
    EASING_FUNCTIONS['cubic_out'],
    EASING_FUNCTIONS['cubic_in'],
    EASING_FUNCTIONS['quant_out'],
    EASING_FUNCTIONS['quant_in'],
    EASING_FUNCTIONS['cubic_inout'],
    EASING_FUNCTIONS['quant_inout'],
    EASING_FUNCTIONS['quint_out'],
    EASING_FUNCTIONS['quint_in'],
    EASING_FUNCTIONS['expo_out'],
    EASING_FUNCTIONS['expo_in'],
    EASING_FUNCTIONS['circ_out'],
    EASING_FUNCTIONS['circ_in'],
    EASING_FUNCTIONS['back_out'],
    EASING_FUNCTIONS['back_in'],
    EASING_FUNCTIONS['circ_inout'],
    EASING_FUNCTIONS['back_inout'],
    EASING_FUNCTIONS['elastic_out'],
    EASING_FUNCTIONS['elastic_in'],
    EASING_FUNCTIONS['bounce_out'],
    EASING_FUNCTIONS['bounce_in'],
    EASING_FUNCTIONS['bounce_inout'],
    EASING_FUNCTIONS['elastic_inout'],
]


@dataclass
class PecChart:
    offset: float
    bpss: list[PecBpsInfo]
    lines: defaultdict[int, PecJudgeLine]

    def __init__(self, content: str):
        self.offset = 0
        self.bpss = []
        self.lines = defaultdict(PecJudgeLine)

        # 将pec格式的内容转换为python代码，让python解释器帮助我们解析执行
        content = re.sub(r'''["'+eghijklnoqstuwxyzA-Z\-*/]''', '', content)  # 避免不必要的麻烦
        content = (
            '\n'.join(
                re.sub(r'\s+', ' ', line.strip()).replace(' ', '(', 1).replace(' ', ',') + ')'
                for line in content.splitlines()
            )
            .replace('\n#', '.sp')
            .replace('\n&', '.sc')
        )

        # 调用个exec来帮助我们解析转换完的pec格式
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

    def _note(self, note_type: int, line_number: int, *args) -> PecNote:
        # the tap note
        note_type_enum = PecNoteType(note_type)
        if note_type_enum == PecNoteType.HOLD:
            start_beats, end_beats, position_x, above, fake = args
            start = self._beats_to_seconds(start_beats)
            end = self._beats_to_seconds(end_beats)
        else:
            beats, position_x, above, fake = args
            start = self._beats_to_seconds(beats)
            end = None
        note = PecNote(note_type_enum, start, position_x / 1024, 1.0, 1.0, bool(above), end)
        if not fake:
            self.lines[line_number].notes.append(note)
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
        # 通常来讲，bpm事件列表的长度一般小于100
        # 所以理论上逆序遍历足够了
        # 应该没有必要设计高级的数据结构
        # 再说了，都用python了那还要啥自行车
        for seconds, beats_begin, bps in reversed(self.bpss):
            if beats >= beats_begin:
                return seconds + (beats - beats_begin) / bps
        raise RuntimeError('???')

    def _cv(self, line_number: int, beats: float, speed: float) -> None:
        # set velocity
        # TODO: find out why 5.85?
        seconds = self._beats_to_seconds(beats)
        self.lines[line_number].speed.cut(seconds, speed / 5.85)

    def _cp(self, line_number: int, beats: float, x: float, y: float) -> None:
        # set position
        seconds = self._beats_to_seconds(beats)
        self.lines[line_number].position.cut(seconds, np.array((x, y)))

    def _cd(self, line_number: int, beats: float, degree: float) -> None:
        # set degree
        seconds = self._beats_to_seconds(beats)
        self.lines[line_number].degree.cut(seconds, degree)

    def _ca(self, line_number: int, beats: float, opacity: float) -> None:
        # ignore opacity setting event
        pass

    def _cm(self, line_number: int, start_beats: float, end_beats: float, x: float, y: float, easing_type: int) -> None:
        # motion event
        seconds_start = self._beats_to_seconds(start_beats)
        seconds_end = self._beats_to_seconds(end_beats)
        self.lines[line_number].position.embed(
            seconds_start, seconds_end, np.array(0), np.array((x, y)), RPE_EASING_FUNCS[easing_type]
        )

    def _cr(self, line_number: int, start_beats: float, end_beats: float, end: float, easing_type: int) -> None:
        # rotate event
        seconds_start = self._beats_to_seconds(start_beats)
        seconds_end = self._beats_to_seconds(end_beats)
        line = self.lines[line_number]
        line.degree.embed(seconds_start, seconds_end, 0, end, RPE_EASING_FUNCS[easing_type])

    def _cf(self, line_number: int, start_beats: float, end_beats: float, end: float) -> None:
        # ignore opacity setting event
        pass


if __name__ == '__main__':
    pec = PecChart(open('../phira/489/Guitar&Lonely&Blue Planet.pec').read())
    print(pec.lines[0].speed.joints)
