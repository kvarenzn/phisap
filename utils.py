import math
from typing import Union, IO


def distance_of(p1: tuple[float, float], p2: tuple[float, float]):
    p1x, p1y = p1
    p2x, p2y = p2
    return math.sqrt((p2x - p1x) ** 2 + (p2y - p1y) ** 2)


def in_rect(point: tuple, border: Union[float, int] = 48) -> bool:
    x, y = point
    return (-border <= x <= 1280 + border) and (-border <= y <= 720 + border)


def read_string_end_with_nil(f: IO) -> str:
    res = bytearray()
    while (c := f.read(1)) != b'\0':
        res += c
    return res.decode()


def intersection(p0: tuple[float, float], angle: float, width: float = 1280, height: float = 720) -> \
        tuple[tuple[float, float], tuple[float, float]]:
    angle %= 360.
    x0, y0 = p0
    if angle == 0:
        return (0, y0), (width, y0)
    elif angle == 90:
        return (x0, height), (x0, 0)
    elif angle == 180:
        return (width, y0), (0, y0)
    elif angle == 270:
        return (x0, 0), (x0, height)
