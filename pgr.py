from typing import TypedDict, Required
import math
from basis import NoteType, Note, JudgeLine, Position, Chart
from bamboo import BrokenBamboo
import itertools
import cmath


class PgrNoteDict(TypedDict):
    type: int
    time: int
    positionX: float
    holdTime: float
    speed: float
    floorPosition: float


class PgrNormalEventDict(TypedDict, total=False):
    startTime: Required[float]
    endTime: Required[float]
    start: Required[float]
    end: Required[float]
    start2: float
    end2: float


class PgrJudgeLineDict(TypedDict):
    bpm: float
    notesAbove: list[PgrNoteDict]
    notesBelow: list[PgrNoteDict]
    judgeLineMoveEvents: list[PgrNormalEventDict]
    judgeLineRotateEvents: list[PgrNormalEventDict]


class PgrChartDict(TypedDict):
    formatVersion: int
    offset: float
    judgeLineList: list[PgrJudgeLineDict]


PGR_NOTE_TYPES: list[NoteType] = [NoteType.UNKNOWN, NoteType.TAP, NoteType.DRAG, NoteType.HOLD, NoteType.FLICK]


class PgrJudgeLine(JudgeLine):
    bpm: float
    notes: list[Note]
    position: BrokenBamboo[Position]
    angle: BrokenBamboo[float]

    def __init__(self, dic: PgrJudgeLineDict, format_version: int, ratio: tuple[int, int]) -> None:
        self.bpm = dic['bpm']
        beats_length = 1.875 / self.bpm
        self.notes = [
            Note(
                PGR_NOTE_TYPES[n['type']],
                n['time'] * beats_length,
                n.get('holdTime', 0) * beats_length,
                n['positionX'] * 0.9,
            )
            for n in itertools.chain(dic['notesAbove'], dic['notesBelow'])
        ]
        self.angle = BrokenBamboo[float]()
        for event in dic['judgeLineRotateEvents']:
            self.angle.cut(
                event['startTime'] * beats_length,
                event['endTime'] * beats_length,
                -math.radians(event['start']),
                -math.radians(event['end']),
            )
        w, h = ratio
        self.position = BrokenBamboo[Position]()
        if format_version == 1:
            for event in dic['judgeLineMoveEvents']:
                sv = event['start']
                ev = event['end']
                self.position.cut(
                    event['startTime'] * beats_length,
                    event['endTime'] * beats_length,
                    complex((sv // 1000) / 880 * w, h - (sv % 1000) / 520 * h),
                    complex((ev // 1000) / 880 * w, h - (ev % 1000) / 520 * h),
                )
        else:
            for event in dic['judgeLineMoveEvents']:
                assert 'start2' in event and 'end2' in event
                self.position.cut(
                    event['startTime'] * beats_length,
                    event['endTime'] * beats_length,
                    complex(event['start'] * w, h * (1 - event['start2'])),
                    complex(event['end'] * w, h * (1 - event['end2'])),
                )

    def pos(self, seconds: float, offset: Position) -> Position:
        angle = self.angle @ seconds
        pos = self.position @ seconds
        return pos + cmath.exp(angle * 1j) * offset

    def beat_duration(self, _: float) -> float:
        return 1.875 / self.bpm


class PgrChart(Chart):
    offset: float
    lines: list[PgrJudgeLine]
    _CHART_SIZE_V1 = (880, 520)
    _CHART_SIZE_V3 = (16, 9)

    def __init__(self, dic: PgrChartDict, ratio: tuple[int, int]) -> None:
        self.width, self.height = ratio
        version = dic['formatVersion']
        self.offset = dic['offset']
        self.lines = [PgrJudgeLine(line, version, ratio) for line in dic['judgeLineList']]
