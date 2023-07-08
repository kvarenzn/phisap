from typing import TypedDict, NamedTuple, Callable
import math
import cmath

from basis import Note, NoteType, JudgeLine, Chart, Position
from bamboo import TwinBamboo, LivingBamboo, BambooGrove, Bamboo, BambooShoot, _Interpable
from easing import EasingFunction, EASING_FUNCTIONS, easing_with_range, cubic_rev_bezier, LVALUE

RPE_EASING_FUNCS: list[EasingFunction] = [
    (lambda _: _),  # 0
    (lambda _: _),  # 1
    EASING_FUNCTIONS['sine_out'],  # 2
    EASING_FUNCTIONS['sine_in'],  # 3
    EASING_FUNCTIONS['quad_in'],  # 4
    EASING_FUNCTIONS['quad_out'],  # 5
    EASING_FUNCTIONS['sine_outin'],  # 6
    EASING_FUNCTIONS['quad_outin'],  # 7
    EASING_FUNCTIONS['cubic_in'],  # 8
    EASING_FUNCTIONS['cubic_out'],  # 9
    EASING_FUNCTIONS['quart_in'],  # 10
    EASING_FUNCTIONS['quart_out'],  # 11
    EASING_FUNCTIONS['cubic_outin'],  # 12
    EASING_FUNCTIONS['quart_outin'],  # 13
    EASING_FUNCTIONS['quint_in'],  # 14
    EASING_FUNCTIONS['quint_out'],  # 15
    EASING_FUNCTIONS['expo_in'],  # 16
    EASING_FUNCTIONS['expo_out'],  # 17
    EASING_FUNCTIONS['circ_in'],  # 18
    EASING_FUNCTIONS['circ_out'],  # 19
    EASING_FUNCTIONS['back_in'],  # 20
    EASING_FUNCTIONS['back_out'],  # 21
    EASING_FUNCTIONS['circ_outin'],  # 22
    EASING_FUNCTIONS['back_outin'],  # 23
    EASING_FUNCTIONS['elastic_in'],  # 24
    EASING_FUNCTIONS['elastic_out'],  # 25
    EASING_FUNCTIONS['bounce_in'],  # 26
    EASING_FUNCTIONS['bounce_out'],  # 27
    EASING_FUNCTIONS['bounce_outin'],  # 28
    EASING_FUNCTIONS['elastic_outin'],  # 29
]


class RpeBeats(NamedTuple):
    add: float
    num: float
    deno: float

    def beats(self) -> float:
        return self.add + self.num / self.deno


class RpeBPMInfoDict(TypedDict):
    bpm: float
    startTime: RpeBeats


class RpeMetaInfoDict(TypedDict):
    RPEVersion: int
    offset: int


class RpeBezierControl(NamedTuple):
    x1: float
    y1: float
    x2: float
    y2: float


class RpeEventDict(TypedDict):
    bezier: int
    bezierPoints: RpeBezierControl
    easingLeft: float
    easingRight: float
    easingType: int
    start: float
    end: float
    startTime: RpeBeats
    endTime: RpeBeats
    linkgroup: int


class RpeEventLayerDict(TypedDict, total=False):
    moveXEvents: list[RpeEventDict]
    moveYEvents: list[RpeEventDict]
    rotateEvents: list[RpeEventDict]


class RpeExtendedEventsDict(TypedDict, total=False):
    scaleXEvents: list[RpeEventDict]
    scaleYEvents: list[RpeEventDict]
    inclineEvents: list[RpeEventDict]


RPE_NOTE_TYPES = [NoteType.UNKNOWN, NoteType.TAP, NoteType.HOLD, NoteType.FLICK, NoteType.DRAG]

class RpeNoteDict(TypedDict):
    type: int
    above: int
    startTime: RpeBeats
    endTime: RpeBeats
    positionX: float
    yOffset: float
    alpha: int
    size: float
    speed: float
    isFake: int
    visibleTime: float


class RpeYControlDict(TypedDict):
    easing: int
    x: float
    y: float


class RpeSkewControlDict(TypedDict):
    easing: int
    x: float
    skew: float


class RpePosControlDict(TypedDict):
    easing: int
    pos: float
    x: float


class RpeJudgeLineDict(TypedDict):
    Group: int
    Name: str
    bpmfactor: float
    eventLayers: list[RpeEventLayerDict]
    extended: RpeExtendedEventsDict
    father: int
    notes: list[RpeNoteDict]
    skewControl: list[RpeSkewControlDict]
    posControl: list[RpePosControlDict]
    yControl: list[RpeYControlDict]


class RpeChartDict(TypedDict):
    META: RpeMetaInfoDict
    BPMList: list[RpeBPMInfoDict]
    judgeLineGroup: list[str]
    judgeLineList: list[RpeJudgeLineDict]


class RpeBpsInfo(NamedTuple):
    seconds: float
    beats: float
    bps: float


class RpeJudgeLine(JudgeLine):
    chart: 'RpeChart'

    scale_x: Bamboo[float]
    scale_y: Bamboo[float]
    incline: Bamboo[float]


    pos_control: LivingBamboo[float]
    skew_control: LivingBamboo[float]
    y_control: LivingBamboo[float]

    def __init__(self, dic: RpeJudgeLineDict, chart: 'RpeChart') -> None:
        super().__init__()

        self.chart = chart

        # control events
        self.pos_control = LivingBamboo[float]()
        if 'posControl' in dic:
            for event in dic['posControl']:
                self.pos_control.cut(event['x'], event['pos'], RPE_EASING_FUNCS[event['easing']])
        self.skew_control = LivingBamboo[float]()
        if 'skewControl' in dic:
            for event in dic['skewControl']:
                self.skew_control.cut(event['x'], event['skew'], RPE_EASING_FUNCS[event['easing']])
        self.y_control = LivingBamboo[float]()
        if 'yControl' in dic:
            for event in dic['yControl']:
                self.y_control.cut(event['x'], event['y'], RPE_EASING_FUNCS[event['easing']])

        def get_easing(event: RpeEventDict) -> EasingFunction:
            if 'bezier' in event and event['bezier'] != 0:
                return cubic_rev_bezier(*event['bezierPoints'])
            else:
                # not bezier
                easing_type = event['easingType']
                easing_func: EasingFunction
                if easing_type > len(RPE_EASING_FUNCS) - 1:
                    print(f'unsupported easing type: {easing_type}')
                    easing_func = LVALUE
                else:
                    easing_func = RPE_EASING_FUNCS[event['easingType']]

                if math.isclose(event['easingLeft'], 0) and math.isclose(event['easingRight'], 1):
                    return easing_func
                else:
                    return easing_with_range(easing_func, event['easingLeft'], event['easingRight'])
        
        def convert_events(events: list[RpeEventDict], convert: Callable[[float], float] | None = None) -> Bamboo[float]:
            b = LivingBamboo[float]()
            if not convert:
                for event in events:
                    b.cut(self.chart._beats_to_seconds(RpeBeats(*event['startTime']).beats()), event['start'], get_easing(event))
                    b.cut(self.chart._beats_to_seconds(RpeBeats(*event['endTime']).beats()), event['end'], LVALUE)
            else:
                for event in events:
                    b.cut(self.chart._beats_to_seconds(RpeBeats(*event['startTime']).beats()), convert(event['start']), get_easing(event))
                    b.cut(self.chart._beats_to_seconds(RpeBeats(*event['endTime']).beats()), convert(event['end']), LVALUE)
            return b

        xss: list[Bamboo[float]] = []
        yss: list[Bamboo[float]] = []
        alphas: list[Bamboo[float]] = []
        for layers in dic['eventLayers']:
            if not isinstance(layers, dict):
                continue
            if 'moveXEvents' in layers:
                xss.append(convert_events(layers['moveXEvents']))
            if 'moveYEvents' in layers:
                yss.append(convert_events(layers['moveYEvents'], lambda y: -y))
            if 'rotateEvents' in layers:
                alphas.append(convert_events(layers['rotateEvents'], math.radians))
        self.position = TwinBamboo(BambooGrove(xss, 0), BambooGrove(yss, 0), lambda pos: pos + complex(self.chart.screen_width, self.chart.screen_height) / 2)
        self.angle = BambooGrove(alphas, 0)

        extended_dict = dic['extended']

        self.incline = convert_events(extended_dict['inclineEvents']) if 'inclineEvents' in extended_dict else BambooShoot(0)
        self.scale_x = convert_events(extended_dict['scaleXEvents']) if 'scaleXEvents' in extended_dict else BambooShoot(1)
        self.scale_y = convert_events(extended_dict['scaleYEvents']) if 'scaleYEvents' in extended_dict else BambooShoot(1)

        self.notes = []
        for note in dic['notes']:
            if note['isFake']:
                continue
            note_type = RPE_NOTE_TYPES[note['type']]
            start_time = self.chart._beats_to_seconds(RpeBeats(*note['startTime']).beats())
            end_time = self.chart._beats_to_seconds(RpeBeats(*note['endTime']).beats())
            self.notes.append(Note(note_type, start_time, end_time - start_time, complex(note['positionX'], note['yOffset'] * note['speed'])))
    
    def pos(self, seconds: float, offset: Position) -> Position:
        angle = self.angle[seconds]
        pos = self.position[seconds]
        return pos + cmath.exp(angle * 1j) * offset

    def beat_duration(self, seconds: float) -> float:
        for time_start, _, bps in reversed(self.chart.bpss):
            if time_start <= seconds:
                return 1 / bps
        return 1.875 / 175


class RpeChart(Chart):
    bpss: list[RpeBpsInfo]

    def __init__(self, dic: RpeChartDict) -> None:
        super().__init__()
        self.screen_width = 1350
        self.screen_height = 900

        self.bpss = []
        for item in dic['BPMList']:
            bps = item['bpm'] / 60
            beats = RpeBeats(*item['startTime']).beats()
            if not self.bpss:
                self.bpss.append(RpeBpsInfo(0, beats, bps))
                continue
            seconds_passed, beats_passed, last_bps = self.bpss[-1]
            seconds_passed += (beats - beats_passed) / last_bps
            self.bpss.append(RpeBpsInfo(seconds_passed, beats, bps))
        
        self.lines = []
        for line in dic['judgeLineList']:
            if 'notes' not in line:
                continue
            self.lines.append(RpeJudgeLine(line, self))

    def _beats_to_seconds(self, beats: float) -> float:
        # 跟pec.py的函数完全一样
        for seconds, beats_begin, bps in reversed(self.bpss):
            if beats >= beats_begin:
                return seconds + (beats - beats_begin) / bps
        raise RuntimeError('???')

if __name__ == '__main__':
    # tests
    import json
    rpe = RpeChart(json.load(open('../../test/phira/1000/AT15.json')))
    import pygame

    pygame.init()
    screen = pygame.display.set_mode((1350, 900))
    clock = pygame.time.Clock()
    running = True

    seconds = 0

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill('black')
        pos = rpe.lines[0].position[seconds]
        angle = cmath.exp(rpe.lines[0].angle[seconds] * 1j)
        left = pos + angle * 3500
        right = pos - angle * 3500
        pygame.draw.circle(screen, 'white', (pos.real, pos.imag), 10)
        pygame.draw.line(screen, 'white', (left.real, left.imag), (right.real, right.imag), 4)
        pygame.display.flip()
        seconds += clock.tick(60) / 1000
    pygame.quit()
