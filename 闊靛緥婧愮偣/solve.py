import numpy as np

from .chart import Chart, Arc, Tap, Hold
from ..algo.algo_base import TouchAction, TouchEvent


class CoordConv:
    trans_mat: np.ndarray

    def __init__(
        self, dl: tuple[float, float], ul: tuple[float, float], ur: tuple[float, float], dr: tuple[float, float]
    ):
        x0, y0 = dl
        x1, y1 = ul
        x2, y2 = ur
        x3, y3 = dr
        a, b, c = x3 - x2, x1 - x2, x1 + x3 - x0 - x2
        d, e, f = y3 - y2, y1 - y2, y1 + y3 - y0 - y2

        g = b * d - a * e
        h = (a * f - c * d) / g
        g = (c * e - b * f) / g

        c, f = x0, y0
        a = (g + 1) * x3 - c
        b = (h + 1) * x1 - c
        d = (g + 1) * y3 - f
        e = (h + 1) * y1 - f

        self.trans_mat = np.array(((a, b, c), (d, e, f), (g, h, 1))).T

    def __call__(self, x: float, y: float) -> tuple[float, float]:
        x_, y_, z_ = np.array((x, y, 1)) @ self.trans_mat
        return x_ / z_, y_ / z_


def solve(chart: Chart, converter: CoordConv) -> dict[int, list[TouchEvent]]:
    result = {}

    def ins(ms: int, ev: TouchEvent):
        if ms not in result:
            result[ms] = []
        result[ms].append(ev)

    current_arctap_id = 1000

    arc_search_range = 5

    for note in chart.notes:
        if isinstance(note, Arc):
            start = (note.start_x, note.start_y, 1)
            end = (note.end_x, note.end_y, 1)
            delta = note.end - note.start
            if note.trace_arc:
                for tap in note.taps:
                    t = (tap.tick - note.start) / delta
                    px, py, _ = note.easing.value(start, end, t)
                    px, py = converter(px, py)
                    ins(tap.tick, TouchEvent((round(px), round(py)), TouchAction.DOWN, current_arctap_id))
                    ins(tap.tick + 2, TouchEvent((round(px), round(py)), TouchAction.UP, current_arctap_id))
                    current_arctap_id += 1
                    if current_arctap_id > 2000:
                        current_arctap_id = 1000
            else:
                px, py, _ = note.easing.value(start, end, 0)
                px, py = converter(px, py)
                ins(note.start, TouchEvent((round(px), round(py)), TouchAction.DOWN, note.color + 5))
                # 链接两个挨得很近的arc
                for tck in range(note.start - arc_search_range, note.start + arc_search_range + 1):
                    if tck not in result:
                        continue
                    for index, ev in enumerate(result[tck]):
                        if ev.pointer == note.color + 5 and ev.action == TouchAction.UP:
                            result[tck].pop(index)
                            result[note.start].pop(-1)
                            ins(note.start, TouchEvent((round(px), round(py)), TouchAction.MOVE, note.color + 5))
                            break
                    else:
                        continue
                    break

                for tick in range(note.start + 1, note.end):
                    t = (tick - note.start) / delta
                    px, py, _ = note.easing.value(start, end, t)
                    px, py = converter(px, py)
                    ins(tick, TouchEvent((round(px), round(py)), TouchAction.MOVE, note.color + 5))
                px, py, _ = note.easing.value(start, end, 1)
                px, py = converter(px, py)
                ins(note.end, TouchEvent((round(px), round(py)), TouchAction.UP, note.color + 5))
                # 链接两个相邻的arc
                for tck in range(note.end - arc_search_range, note.end + arc_search_range + 1):
                    if tck not in result:
                        continue
                    for index, ev in enumerate(result[tck]):
                        if ev.pointer == note.color + 5 and ev.action == TouchAction.DOWN:
                            result[tck].pop(index)
                            result[note.end].pop(-1)
                            ins(tck, TouchEvent((round(px), round(py)), TouchAction.MOVE, note.color + 5))
                            break
                    else:
                        continue
                    break
        elif isinstance(note, Tap):
            px, py = converter(-0.75 + note.track * 0.5, 0)
            ins(note.tick, TouchEvent((round(px), round(py)), TouchAction.DOWN, note.track))
            ins(note.tick + 20, TouchEvent((round(px), round(py)), TouchAction.UP, note.track))
        elif isinstance(note, Hold):
            px, py = converter(-0.75 + note.track * 0.5, 0)
            ins(note.start, TouchEvent((round(px), round(py)), TouchAction.DOWN, note.track))
            ins(note.end, TouchEvent((round(px), round(py)), TouchAction.UP, note.track))
    return result


if __name__ == '__main__':
    conv = CoordConv((760, 920), (650, 340), (1690, 340), (1580, 920))
    print(conv(0, 0))
    print(conv(0.5, 0))
    print(conv(0.5, 0.5))
    print(conv(1, 1))
    print(conv(-0.5, 0))
    print(conv(1.5, 0))
