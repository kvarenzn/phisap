from json import load, dump
from typing import IO

from algo.algo_base import TouchEvent


def export_to_json(ans: dict[int, list[TouchEvent]], out_file: IO):
    dump(
        {
            timestamp: [event.to_serializable() for event in events]
            for timestamp, events in ans.items()
        },
        out_file,
    )


def load_from_json(in_file: IO) -> dict[int, list[TouchEvent]]:
    return {
        int(ts): [TouchEvent.from_serializable(event) for event in events]
        for ts, events in load(in_file).items()
    }
