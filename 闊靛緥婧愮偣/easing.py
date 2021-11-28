from enum import Enum
from functools import partial
from math import pi, sin, cos

import numpy as np


def _easing_linear(start: tuple[float, float, float], end: tuple[float, float, float], t: float) -> tuple[
        float, float, float]:
    return tuple(np.array(np.mat((1 - t, t)) @ np.mat((start, end)))[0])


def _easing_cubic_bezier(start: tuple[float, float, float], end: tuple[float, float, float], t: float) -> tuple[
        float, float, float]:
    mult = np.eye(3) * (1 - t) * (1 + 2 * t)
    mult[1, 1] = 1.
    start = np.array(start) @ mult
    mult = np.eye(3) * t * (3 - 2 * t)
    mult[1, 1] = 1
    end = np.array(end) @ mult
    return _easing_linear(start, end, t)


def _easing_sinus(start: tuple[float, float, float], end: tuple[float, float, float], t: float, x: str,
                  z: str = None) -> tuple[float, float, float]:
    x0, y0, z0 = start
    x1, y1, z1 = end
    if x == 'si':
        sx = sin(t * pi / 2)
    elif x == 'so':
        sx = 1 - cos(t * pi / 2)
    else:
        raise RuntimeError(f'unknown easing type x = {x}')
    if z == 'si':
        sz = sin(t * pi / 2)
    elif z == 'so':
        sz = 1 - cos(t * pi / 2)
    else:
        sz = t
    return x0 + (x1 - x0) * sx, y0 + (y1 - y0) * t, z0 + (z1 - z0) * sz


class Easing(Enum):
    Linear = partial(_easing_linear)
    CubicBezier = partial(_easing_cubic_bezier)
    Si = partial(_easing_sinus, x='si')
    SiSi = partial(_easing_sinus, x='si', z='si')
    SiSo = partial(_easing_sinus, x='si', z='so')
    So = partial(_easing_sinus, x='so')
    SoSo = partial(_easing_sinus, x='so', z='so')
    SoSi = partial(_easing_sinus, x='so', z='si')


if __name__ == '__main__':
    print(_easing_linear((0, 1, 0), (1, 1, 0), 0.2))
    print(_easing_cubic_bezier((0, 0, 0), (1, 1, 0), 0.2))
    print(Easing.So.value((0, 1, 0), (1, 1, 0), 0.2))
    print(Easing.CubicBezier)
    print(Easing.SiSi)
