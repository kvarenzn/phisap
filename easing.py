from typing import Callable
from types import CodeType, FunctionType
from enum import Enum
from functools import partial
from math import pi, sin, cos, sqrt

import numpy as np


def _easing_linear(
    start: tuple[float, float, float], end: tuple[float, float, float], t: float
) -> tuple[float, float, float]:
    return tuple(np.array(np.mat((1 - t, t)) @ np.mat((start, end)))[0])


def _easing_cubic_bezier(
    start: tuple[float, float, float], end: tuple[float, float, float], t: float
) -> tuple[float, float, float]:
    mult = np.eye(3) * (1 - t) * (1 + 2 * t)
    mult[1, 1] = 1.0
    start = (np.array(start) @ mult).tolist()
    mult = np.eye(3) * t * (3 - 2 * t)
    mult[1, 1] = 1
    end = (np.array(end) @ mult).tolist()
    return _easing_linear(start, end, t)


def _easing_sinus(
    start: tuple[float, float, float], end: tuple[float, float, float], t: float, x: str, z: str | None = None
) -> tuple[float, float, float]:
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


def _in(expr: str) -> str:
    return f'1 - ({expr.replace("x", "(1 - x)")})'


def _out(expr: str) -> str:
    return expr


def _inout(expr: str) -> str:
    return f'({_in(expr).replace("x", "(2 * x)")}) / 2 if x < 0.5 else (1 + ({_out(expr).replace("x", "(2 * x - 1)")})) / 2'


def _outin(expr: str) -> str:
    return f'({_out(expr).replace("x", "(2 * x)")}) / 2 if x < 0.5 else (1 + ({_in(expr).replace("x", "(2 * x - 1)")})) / 2'


_EASING_BASIC_FUNCTIONS = {
    'linear': 'x',
    'sine': 'sin(x * pi / 2)',
    'quad': 'x ** 2',
    'cubic': 'x ** 3',
    'quart': 'x ** 4',
    'quint': 'x ** 5',
    'circ': '1 - sqrt(1 - x * x)',
    'expo': '2. ** (10 * x - 10)',
    'back': '(2.70158 * x - 1.70158) * x ** 2',
    'elastic': f'-(2 ** (10 * x - 10) * sin({2 * pi / 3} * (x * 10. - 10.75)))',
    'bounce': f'A * x ** 2 if x < {1 / 2.75} else (A * (x - {1.5 / 2.75}) ** 2 + 0.75 if x < {2 / 2.75} else (A * (x - {2.25 / 2.75}) ** 2 + 0.9375 if x < {2.5 / 2.75} else A * (x - {2.625 / 2.75}) ** 2 + 0.984375))'.replace(
        'A', str(7.5625)
    ),
}

_EASING_SUFFIXES = [_in, _out, _inout, _outin]


def easing(easing_basic: tuple[str, str], suffix: Callable[[str], str]) -> Callable[[float], float]:
    name, expr = easing_basic
    name += suffix.__name__
    f = compile('lambda x:' + suffix(expr), '<string>', 'eval')
    code = [c for c in f.co_consts if isinstance(c, CodeType)][0]
    return FunctionType(code, globals())


EasingFunction = Callable[[float], float]

EASING_FUNCTIONS: dict[str, EasingFunction] = {
    b + s.__name__: easing((b, fn), s) for s in _EASING_SUFFIXES for b, fn in _EASING_BASIC_FUNCTIONS.items()
}

LVALUE: EasingFunction = lambda _: 0
RVALUE: EasingFunction = lambda _: 1


def easing_with_range(f: EasingFunction, left: float, right: float) -> EasingFunction:
    fl = f(left)
    fr = f(right)
    d = fr - fl
    return lambda t: (f(left + (right - left) * t) - fl) / d


_BEZIER_SAMPLES_COUNT = 21
_BEZIER_SAMPLE_STEP = 1 / (_BEZIER_SAMPLES_COUNT - 1)
_NEWTON_MIN_STEP = 1e-3
_NEWTON_STOP = 4
_SUBDIVISION_PREC = 1e-7
_SUBDIVISION_STOP = 10
_SLOPE_EPS = 1e-7


def cubic_rev_bezier(x1: float, y1: float, x2: float, y2: float) -> EasingFunction:
    f = lambda a, b: ((a - b) * 3 + 1, b * 3 - a * 6, a * 3)
    a1, a2, a3 = f(y1, y2)
    b1, b2, b3 = f(x1, x2)

    sample_table = [
        (((b1 * i + b2) * i) + b3) * i for i in (j * _BEZIER_SAMPLE_STEP for j in range(_BEZIER_SAMPLES_COUNT))
    ]

    def inner(t: float) -> float:
        if t == 0 or t == 1:
            return ((a1 * t + a2) * t + a3) * t
        i = min(int(t / _BEZIER_SAMPLE_STEP), _BEZIER_SAMPLES_COUNT - 1)
        dist = (t - sample_table[i]) / (sample_table[i + 1] - sample_table[i])
        tt = (i + dist) * _BEZIER_SAMPLE_STEP
        slp = (b1 * 3 * tt + b2 * 2) * tt + b3
        if slp <= _SLOPE_EPS:
            pass
        elif slp >= _NEWTON_MIN_STEP:
            # newton iteration
            for _ in range(_NEWTON_STOP):
                diff = ((b1 * tt + b2) * tt + b3) * tt - t
                tt -= diff / slp
                slp = (b1 * 3 * tt + b2 * 2) * tt + b3
                if slp <= _SLOPE_EPS:
                    break
        else:
            # bisect
            l, r = _BEZIER_SAMPLE_STEP * i, _BEZIER_SAMPLE_STEP * (i + 1)
            tt = (l + r) / 2
            for _ in range(_SUBDIVISION_STOP):
                diff = ((b1 * tt + b2) * tt + b3) * tt - t
                if abs(diff) <= _SUBDIVISION_PREC:
                    break
                if diff > 0:
                    r = tt
                else:
                    l = tt
                tt = (l + r) / 2
        return ((a1 * tt + a2) * tt + a3) * tt

    return inner


class Easing3D(Enum):
    Linear = partial(_easing_linear)
    CubicBezier = partial(_easing_cubic_bezier)
    Si = partial(_easing_sinus, x='si')
    SiSi = partial(_easing_sinus, x='si', z='si')
    SiSo = partial(_easing_sinus, x='si', z='so')
    So = partial(_easing_sinus, x='so')
    SoSo = partial(_easing_sinus, x='so', z='so')
    SoSi = partial(_easing_sinus, x='so', z='si')


if __name__ == '__main__':
    # import matplotlib.pyplot as plt
    #
    # x = [i / 1000 for i in range(1001)]
    # circ_in = EASING_FUNCTIONS['circ_in']
    # y = [circ_in(i) for i in x]
    # fig, ax = plt.subplots()
    # ax.plot(x, y)
    # plt.show()
    pass
