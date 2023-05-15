from typing import Self
from judge_line import JudgeLine


class Chart:
    version: int
    offset: float
    judge_lines: list[JudgeLine]

    def __init__(self, version: int, offset: float, judge_lines: list[JudgeLine]) -> None:
        self.version = version
        self.offset = offset
        self.judge_lines = judge_lines

    @classmethod
    def from_dict(cls, d: dict) -> Self:
        version = d['formatVersion']
        if version == 1:
            return cls(version, d['offset'], [*map(JudgeLine.from_dict_v1, d['judgeLineList'])])
        else:
            return cls(version, d['offset'], [*map(JudgeLine.from_dict, d['judgeLineList'])])


__all__ = ['Chart']
