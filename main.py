import configparser
import json
import os
from typing import Callable

from prompt_toolkit import prompt
from prompt_toolkit.completion import FuzzyWordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.lexers import Lexer

from chart import Chart
from control import DeviceController
from solve import solve, load_from_json, export_to_json


def run(chart_path: str, advance: float):
    import time

    chart = Chart.from_dict(json.load(open(chart_path)))

    ans_file = chart_path + '.ans.json'
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

    ctl.tap(device_size[0] // 2, device_size[1] // 2)

    ctl.lock.acquire()
    ctl.stop_streaming()
    print('[client] INFO: 自动打歌已启动')

    start_time = time.time() - advance
    ans_iter = iter(sorted(ans.items()))

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
        time.sleep(0.5)


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
    print('''欢迎使用phisap - PHIgros Semi-Auto Player
    
    注意：由于一些限制，目前并不能保证任意一首曲目在每次由本程序
    自动完成时都能达到φ(100%)的成绩。同样也不能保证将来版本的程序
    满足上述要求。
    
    使用方法:

    1. 将运行本程序的计算机连接您的安卓设备，并打开设备上的USB调试功能。
    2. 启动设备上的Phigros，选择您要打的曲目，曲目开始后双击屏幕左上角的
        暂停按钮暂停游戏。
    3. 在下方输入您选择的曲目和难度。以后的版本可能会加入自动识别的功能。
    4. 输入曲目的延时（单位：秒）。由于本程序无法精确获知曲目的开始时机，
        所以需要一个延时来同步本程序和Phigros的时间。如果您感觉每次程序
        击打note的时刻均在其到达判定线之前，请减小这个值，否则增大这个值。
        注意：这个值没有大小的限制，且可以为负。可能需要多尝试几次来达到
        最佳效果。
    5. 之后程序会自动解除设备上的暂停并完成这首曲目。如果设备上弹出USB授权
        对话框，请确认授权，并且重新运行本程序。如果您发现设备上的暂停一直
        未解除，也请尝试重新运行本程序。若仍未成功，则表明本程序不支持您的
        设备。注意：您可以随时按下Ctrl+C终止本程序。
    ''')


if __name__ == '__main__':
    welcome()
    cache = configparser.ConfigParser()
    cache_path = './cache'

    if os.path.exists(cache_path):
        cache.read(cache_path)

    if not cache.has_section('cache'):
        cache.add_section('cache')

    try:
        cache.getfloat('cache', 'offset')
    except configparser.NoOptionError:
        cache.set('cache', 'offset', '0.22')

    last_offset = cache.getfloat('cache', 'offset')
    select_chart = ask_for_chart()
    offset = input(f'负时延({last_offset})? ')
    try:
        offset = float(offset)
        cache.set('cache', 'offset', str(offset))
        cache.write(open(cache_path, 'w'))
    except ValueError:
        offset = last_offset
    run(select_chart, offset)
