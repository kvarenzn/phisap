import sys
from time import time

from chart import Chart
from solve import solve, CoordConv

if __name__ == '__main__':
    print('请开启游戏，测量并输入下面四个点的屏幕坐标(以"x, y"的格式输入)：')
    bottom_left = tuple(map(int, input('底部轨道最左下角：').split(',')))
    top_left = tuple(map(int, input('天空线的最左端：').split(',')))
    top_right = tuple(map(int, input('天空线的最右端：').split(',')))
    bottom_right = tuple(map(int, input('底部轨道最右下角：').split(',')))
    print()
    chart_path = input('谱面文件路径: ')

    delay = float(input('延时(从暂停界面重开游戏所需时间(秒))：'))
    chart = Chart.loads(open(chart_path).read())
    conv = CoordConv(bottom_left, top_left, top_right, bottom_right)
    ans = solve(chart, conv)
    ans_iter = iter(sorted(ans.items()))
    ms, evs = next(ans_iter)
    sys.path.append('..')
    from control import DeviceController

    ctl = DeviceController()
    w, h = ctl.device_size
    ctl.tap(w // 2, h // 2)
    start = time() + delay
    print('[client] INFO: 自动打歌已启动')
    try:
        while True:
            now = round((time() - start) * 1000)
            if now >= ms:
                for ev in evs:
                    ctl.touch(ev.action.value, *ev.pos, ev.pointer)
                ms, evs = next(ans_iter)
    except StopIteration:
        print('[client] INFO: 自动打歌已终止')
