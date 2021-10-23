import configparser
import json
import os
import sys
from typing import Callable

from prompt_toolkit import prompt
from prompt_toolkit.completion import FuzzyWordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.lexers import Lexer

from chart import Chart
from control import DeviceController
from solve import solve, load_from_json, export_to_json


class BinomialLexer(Lexer):
    correct_word_list: list[str]
    correct_style: str
    wrong_style: str

    def __init__(self, correct_word_list: list[str], correct_style: str = '#00ff00 bold', wrong_style: str = '#ff0000'):
        self.correct_word_list = correct_word_list
        self.correct_style = correct_style
        self.wrong_style = wrong_style

    def lex_document(self, document: Document) -> Callable[[int], StyleAndTextTuples]:

        def get_line(linenum: int) -> StyleAndTextTuples:
            try:
                line = document.lines[linenum]
                if line.strip() in self.correct_word_list:
                    return [(self.correct_style, line)]
                else:
                    return [(self.wrong_style, line)]
            except IndexError:
                return []

        return get_line


def ask_for_chart() -> str:
    # load databases
    songs = os.listdir('./Assets/Tracks')
    songs_completer = FuzzyWordCompleter(songs)
    songname_lexer = BinomialLexer(songs)
    first = True
    while True:
        selected_song = prompt('歌曲ID(可输入曲名或作者进行模糊搜索)? ' if first else '歌曲ID? ', completer=songs_completer,
                               lexer=songname_lexer)
        if selected_song in songs:
            break
        first = False
        print('歌曲ID不存在，请重新输入')
    difficulties = [file[6:-5] for file in os.listdir(os.path.join('./Assets/Tracks', selected_song)) if
                    'ans' not in file]
    difficulty_completer = FuzzyWordCompleter(difficulties)
    difficulty_lexer = BinomialLexer(difficulties)
    while True:
        selected_difficulty = prompt(f'难度({difficulties})? ', completer=difficulty_completer, lexer=difficulty_lexer)
        if selected_difficulty in difficulties:
            break
        print('难度不存在，请重新输入')
    return os.path.join('./Assets/Tracks', selected_song, f'Chart_{selected_difficulty}.json')


def welcome():
    # 如果您修改本程序或本程序的源代码，则默认您同意下面的协定：
    print('您因使用或修改本程序发生的一切后果将由您自己承担而与程序原作者无关。')
    print('您是否同意这个协定？')
    accept = input('如果同意，请输入"同意"并回车，否则输入其他一切的内容将被视为不同意: ')
    if accept != '同意':
        exit()
    print('tips: \033[0;31m适度游戏益脑，沉迷游戏伤身。合理安排时间，享受健康生活\033[0m')

    print(f'''欢迎使用phisap - PHIgros Semi-Auto Player
    
    注意：由于一些限制，目前并不能保证任意一首曲目在每次由本程序
    自动完成时都能达到φ(100%)的成绩。同样也不能保证将来版本的程序
    满足上述要求。
    ''')


def detect_time_limit():
    # 希望您能严格遵守新规定，如果您擅自修改或去掉这部分代码，
    # 请您自行承担相关责任
    import datetime
    now = datetime.datetime.now()
    if now.weekday() >= 4 and (datetime.time(20, 0, 0, 0) <= now.time() <= datetime.time(21, 0, 0, 0)):
        return
    print('\033[0;31m现在在规定时间之外，本程序将被禁止继续运行。请您严格遵守相关限制！\033[0m')
    print('规定时间为：每周的五、六、日三天的20:00至21:00')
    exit()


if __name__ == '__main__':
    # 您要是实在嫌麻烦，就注释掉/删掉这下面两个函数的调用
    detect_time_limit()
    welcome()

    adjusting_method = 'delay'
    if len(sys.argv) > 1:
        param = sys.argv[1]
        if param in ['delay', 'tap']:
            adjusting_method = param

    if adjusting_method == 'delay':
        cache = configparser.ConfigParser()
        cache_path = './cache'

        if os.path.exists(cache_path):
            cache.read(cache_path)

        if not cache.has_section('cache'):
            cache.add_section('cache')

        try:
            cache.getfloat('cache', 'offset')
        except configparser.NoOptionError:
            cache.set('cache', 'offset', '1.95')

        print('请您在游戏设备上选择游玩的曲目，开始游戏后请将游戏暂停，然后在这里继续')

    print('确保您已允许USB调试，如果游戏设备上弹出询问授权的对话框，请允许授权。')

    select_chart = ask_for_chart()

    if adjusting_method == 'delay':
        last_offset = cache.getfloat('cache', 'offset')
        offset = input(f'时延({last_offset})? ')
        try:
            offset = float(offset)
            cache.set('cache', 'offset', str(offset))
            cache.write(open(cache_path, 'w'))
        except ValueError:
            offset = last_offset

    import time

    chart = Chart.from_dict(json.load(open(select_chart)))

    ans_file = select_chart + '.ans.json'
    if os.path.exists(ans_file):
        print('使用缓存')
        ans = load_from_json(open(ans_file))
    else:
        ans = solve(chart)
        export_to_json(ans, open(ans_file, 'w'))

    ctl = DeviceController()
    device_size = ctl.device_size

    height = device_size[1]
    width = height * 16 // 9
    xoffset = (device_size[0] - width) // 2
    yoffset = (device_size[1] - height) // 2
    scale_factor = height / 720

    for evs in ans.values():
        for i in range(len(evs)):
            ev = evs[i]
            x, y = ev.pos
            x = xoffset + round(x * scale_factor)
            y = yoffset + round(y * scale_factor)
            evs[i] = ev._replace(pos=(x, y))

    ans_iter = iter(sorted(ans.items()))

    if adjusting_method == 'delay':
        ctl.tap(device_size[0] // 2, device_size[1] // 2)
        print('[client] INFO: 自动打歌已启动')
        print(f'[client] INFO: {"提前" if offset < 0 else "等待"}{abs(offset)}秒')

        start_time = time.time() + offset

        begin = False

        ce_ms, ces = next(ans_iter)
        try:
            while True:
                now = round((time.time() - start_time) * 1000)
                if now >= ce_ms:
                    if not begin:
                        print('[client] INFO: 开始操作')
                        begin = True
                    for ev in ces:
                        ctl.touch(*ev.pos, ev.action.value, pointer_id=ev.pointer)
                        # print(ev)
                    ce_ms, ces = next(ans_iter)
        except StopIteration:
            print('[client] INFO: 自动打歌已结束')
            time.sleep(0.5)  # 等待server退出

    elif adjusting_method == 'tap':
        print('[client] INFO: 自动打歌已就绪，等待您的指示')
        print('[client] INFO: 请开始游戏，并在第一个音符快落到判定线时，在这里输入两次回车')
        input()
        print('[client] INFO: 自动打歌已启动')
        ce_ms, ces = next(ans_iter)
        start_time = time.time() - ce_ms / 1000 - 0.01

        for ev in ces:
            ctl.touch(*ev.pos, ev.action.value, pointer_id=ev.pointer)
        ce_ms, ces = next(ans_iter)

        try:
            while True:
                now = round((time.time() - start_time) * 1000)
                if now >= ce_ms:
                    for ev in ces:
                        ctl.touch(*ev.pos, ev.action.value, pointer_id=ev.pointer)
                        # print(ev)
                    ce_ms, ces = next(ans_iter)
        except StopIteration:
            print('[client] INFO: 自动打歌已结束')
            time.sleep(0.5)  # 等待server退出
