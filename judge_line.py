from typing import Self
from note import Note
import math


class SpeedEvent:
    start_time: float
    end_time: float
    floor: float
    value: float

    def __init__(self, start_time: float, end_time: float, floor: float, value: float) -> None:
        self.start_time = start_time
        self.end_time = end_time
        self.floor = floor
        self.value = value

    @classmethod
    def from_dict(cls, d: dict) -> Self:
        return cls(d['startTime'], d['endTime'], d.get('floorPosition', 0.0), d['value'])

    def __repr__(self) -> str:
        return f'''SpeedEvent(start={self.start_time}, end={self.end_time}, floor={self.floor}, value={self.value})'''


class NormalEvent:
    start_time: float
    end_time: float
    start: float
    end: float
    start2: float
    end2: float

    def __init__(self, start_time: float, end_time: float, start: float, end: float, start2: float, end2: float) -> None:
        self.start_time = start_time
        self.end_time = end_time
        self.start = start
        self.end = end
        self.start2 = start2
        self.end2 = end2

    @classmethod
    def from_dict(cls, d: dict) -> Self:
        return cls(d['startTime'], d['endTime'], d['start'], d['end'], d.get('start2', 0.0), d.get('end2', 0.0))

    @classmethod
    def from_dict_v1(cls, d: dict) -> Self:
        start = d['start']
        end = d['end']
        return cls(
            d['startTime'],
            d['endTime'],
            (start // 1000) / 880,
            (end // 1000) / 880,
            (start % 1000) / 520,
            (end % 1000) / 520,
        )


class JudgeLine:
    notes_above: list[Note]
    notes_below: list[Note]
    bpm: float
    speed_events: list[SpeedEvent]
    disappear_events: list[NormalEvent]
    move_events: list[NormalEvent]
    rotate_events: list[NormalEvent]

    def __init__(
        self,
        notes_above: list[Note],
        notes_below: list[Note],
        bpm: float,
        speed_events: list[SpeedEvent],
        disappear_events: list[NormalEvent],
        move_events: list[NormalEvent],
        rotate_events: list[NormalEvent],
    ) -> None:
        self.notes_above = notes_above
        self.notes_below = notes_below
        self.bpm = bpm
        self.speed_events = speed_events
        self.disappear_events = disappear_events
        self.move_events = move_events
        self.rotate_events = rotate_events

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            [*map(Note.load, d['notesAbove'])],
            [*map(Note.load, d['notesBelow'])],
            d['bpm'],
            [*map(SpeedEvent.from_dict, d['speedEvents'])],
            [*map(NormalEvent.from_dict, d['judgeLineDisappearEvents'])],
            [*map(NormalEvent.from_dict, d['judgeLineMoveEvents'])],
            [*map(NormalEvent.from_dict, d['judgeLineRotateEvents'])],
        )

    @classmethod
    def from_dict_v1(cls, d: dict) -> Self:
        speed_events = d['speedEvents']
        current_floor = 0.0
        for ev in speed_events:
            if 'floorPosition' not in ev:
                ev['floorPosition'] = current_floor
                current_floor += 1.875 * (ev['endTime'] - ev['startTime']) * ev['value'] / d['bpm']

        return cls(
            [*map(Note.load, d['notesAbove'])],
            [*map(Note.load, d['notesBelow'])],
            d['bpm'],
            [*map(SpeedEvent.from_dict, d['speedEvents'])],
            [*map(NormalEvent.from_dict, d['judgeLineDisappearEvents'])],
            [*map(NormalEvent.from_dict_v1, d['judgeLineMoveEvents'])],
            [*map(NormalEvent.from_dict, d['judgeLineRotateEvents'])],
        )

    def floor(self, t: float) -> float:
        for e in self.speed_events:
            if e.start_time <= t <= e.end_time:
                return self.seconds((t - e.start_time) * e.value) + e.floor
        raise RuntimeError(f'floorPosition not found: time = {t}')

    def seconds(self, t: float) -> float:
        return t * 1.875 / self.bpm

    def time(self, second: float) -> float:
        return second * self.bpm / 1.875

    def opacity(self, t: float) -> float:
        for e in self.disappear_events:
            if e.start_time <= t <= e.end_time:
                return e.start + (e.end - e.start) * (t - e.start_time) / (e.end_time - e.start_time)
        return 1.0

    def pos(self, t: float) -> tuple[float, float]:
        for e in self.move_events:
            if e.start_time <= t <= e.end_time:
                return (
                    (e.start + (e.end - e.start) * (t - e.start_time) / (e.end_time - e.start_time)) * 1280,
                    720 - (e.start2 + (e.end2 - e.start2) * (t - e.start_time) / (e.end_time - e.start_time)) * 720,
                )
        return 0, 0

    def angle(self, t: float) -> float:
        for e in self.rotate_events:
            if e.start_time <= t <= e.end_time:
                return e.start + (e.end - e.start) * (t - e.start_time) / (e.end_time - e.start_time)
        return 0.0

    @property
    def notes(self) -> list[Note]:
        return self.notes_above + self.notes_below

    def pos_of(self, note: Note, time: int | float | None = None) -> tuple[float, float]:
        t = time if time is not None else note.time
        off_x = note.x * 72
        x, y = self.pos(t)
        a = -self.angle(t) * math.pi / 180
        return x + off_x * math.cos(a), y + off_x * math.sin(a)
