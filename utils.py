import math


def distance_of(p1: tuple[float, float], p2: tuple[float, float]):
    p1x, p1y = p1
    p2x, p2y = p2
    return math.sqrt((p2x - p1x) ** 2 + (p2y - p1y) ** 2)


def div(x: float, y: float) -> float:
    """自动处理除零异常"""
    try:
        return x / y
    except ZeroDivisionError:
        return math.nan


def recalc_pos(position: tuple[float, float], sa: float, ca: float) -> tuple[float, float]:
    """重新计算坐标
    一些情况下，note会在屏幕的外侧判定。点名批评Nhelv。
    也就是说，此时横坐标会在[0, 1280]的范围外，或者纵坐标会在[0, 720]的范围外。
    这是我们需要重新规划击打的位置，让该位置落在屏幕内。
    我们利用屁股肉的垂直判定区域特性来解决这个问题。
    也就是说，在高垂直于判定线且长度不限，同时宽平行且与note等长的矩形范围内点击任意位置均视为判定成功。
    为了简化这个问题，我们将矩形视作一条线，这条线过矩形的终点且与矩形的两高平行。
    这条线必与屏幕对应的矩形相交，且绝大部分情况下有两个交点。
    我们取这两个交点的中心点作为我们操作note的位置。
    :param position: 坐标
    :param sa: sin(angle) 判定线偏移角度的正弦值
    :param ca: cos(angle) 判定线偏移角度的余弦值
    :return: 重新计算后的坐标
    """
    px, py = position

    if px < 0 or px > 1280 or py < 0 or py > 720:
        # 重新计算note
        sumx = sumy = 0
        x1 = px + py * div(sa, ca)
        y1 = py + px * div(ca, sa)
        x2 = px - (720 - py) * div(sa, ca)
        y2 = py - (1280 - px) * div(ca, sa)
        if 0 < x1 < 1280:
            sumx += x1
        if 0 < y1 < 720:
            sumy += y1
        if 0 < x2 < 1280:
            sumx += x2
            sumy += 720
        if 0 < y2 < 720:
            sumy += y2
            sumx += 1280
        return sumx / 2, sumy / 2
    else:
        return px, py
