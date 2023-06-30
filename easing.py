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
    return (
        f'({_in(expr).replace("x", "(2 * x)")}) / 2 if x < 0.5 else ({_out(expr).replace("x", "(2 * x - 1)")}) / 2 + 1'
    )


def _outin(expr: str) -> str:
    return (
        f'({_out(expr).replace("x", "(2 * x)")}) / 2 if x < 0.5 else ({_in(expr).replace("x", "(2 * x - 1)")}) / 2 + 1'
    )


_EASING_BASIC_FUNCTIONS = {
    'linear': 'x',
    'sine': 'sin(x * pi / 2)',
    'quad': 'x ** 2',
    'cubic': 'x ** 3',
    'quant': 'x ** 4',
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
    b + s.__name__: easing((b, fn), s)
    for s in _EASING_SUFFIXES
    for b, fn in _EASING_BASIC_FUNCTIONS.items()
}

LVALUE: EasingFunction = lambda _: 0
RVALUE: EasingFunction = lambda _: 1

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
