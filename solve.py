from json import load, dump
from typing import IO

from algo.algo1 import solve as algo1
from algo.algo2 import solve as algo2
from algo.algo_base import TouchEvent
from chart import Chart


def solve(chart: Chart) -> dict[int, list[TouchEvent]]:
    try:
        res = algo1(chart)
        print('使用算法: algo1')
        return res
    except RuntimeError:
        print('使用算法: algo2')
        return algo2(chart)


def export_to_json(ans: dict[int, list[TouchEvent]], out_file: IO):
    dump({timestamp: [event.to_serializable() for event in events] for timestamp, events in ans.items()}, out_file)


def load_from_json(in_file: IO) -> dict[int, list[TouchEvent]]:
    return {int(ts): [TouchEvent.from_serializable(event) for event in events] for ts, events in load(in_file).items()}
