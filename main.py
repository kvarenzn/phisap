import configparser
import json
import os
import zipfile
from tkinter import ttk, messagebox, Tk, X, IntVar, StringVar, DoubleVar, filedialog, Toplevel
from typing import Iterator
from algo.algo_base import TouchEvent
from threading import Thread

from catalog import Catalog
from chart import Chart
from control import DeviceController
from extract import AssetsManager, TextAsset
from solve import load_from_json, export_to_json

from rich.console import Console
from rich.progress import track, Progress


def extract_apk(console: Console):
    apk_path = filedialog.askopenfilename(filetypes=[('安装包', '.apk')], title='请选择要解包的游戏安装包')
    if not apk_path:
        return
    popup = Toplevel()
    popup.title('正在解包，请稍候...')
    popup.minsize(300, 60)
    popup.resizable(False, False)
    popup.pack_slaves()
    popup.update()

    console.print('正在读取安装包...')
    apk_file = zipfile.ZipFile(apk_path)
    console.print('正在解析catalog.json...')
    catalog = Catalog(apk_file.open('assets/aa/catalog.json'))
    manager = AssetsManager()
    for file in track(apk_file.namelist(), description='正在加载文件...', console=console):
        if not file.startswith('assets/aa/Android'):
            continue
        with apk_file.open(file) as f:
            manager.load_file(f)
    popup.title('已加载安装包')
    popup.update()
    manager.read_assets(console)

    popup.title('正在解包，请稍候...')
    popup.update()
    for file in track(manager.asset_files, description='正在写入文件...', console=console):
        assert file.parent
        filepath = file.parent.reader.path
        if filepath.name not in catalog.fname_map:
            continue
        asset_name = catalog.fname_map[filepath.name]
        if not asset_name.startswith('Assets/'):
            continue
        basedir = os.path.dirname(asset_name)
        if basedir and not os.path.exists(basedir):
            os.makedirs(basedir)

        for obj in file.objects:
            if isinstance(obj, TextAsset):
                with open(asset_name, 'w') as out:
                    out.write(obj.text)

    popup.destroy()


def agreement():
    if os.path.exists('./cache'):
        return
    if not messagebox.askyesno(title='用户协定', message='您因使用或修改本程序发生的一切后果将由您自己承担而与程序原作者无关。\n' '您是否同意？'):
        exit(1)


class App(ttk.Frame):
    cache: configparser.ConfigParser | None
    running: bool
    start_time: float
    controller: DeviceController | None
    player_worker_thread: Thread | None
    console: Console

    def __init__(self, master: Tk):
        super().__init__(master)
        self.console = Console()
        self.controller = None
        self.player_worker_thread = None
        self.cache_path = None
        self.running = True
        self.start_time = 0.0
        self.cache = None
        self.pack()

        frm = ttk.Frame()
        frm.pack()
        self.extract_btn = ttk.Button(frm, text='解包Apk', command=lambda: extract_apk(self.console))
        self.extract_btn.pack()

        ttk.Separator(orient='horizontal').pack(fill=X)

        self.sync_mode = IntVar()
        self.sync_mode.set(0)

        frm = ttk.Frame()
        frm.pack()

        ttk.Label(frm, text='计时器同步方式：').grid(column=0, row=0)

        self.sync_mode1 = ttk.Radiobutton(
            frm, text='延时同步', variable=self.sync_mode, value=0, command=self.sync_mode_changed
        )
        self.sync_mode2 = ttk.Radiobutton(
            frm, text='手动同步', variable=self.sync_mode, value=1, command=self.sync_mode_changed
        )
        self.sync_mode1.grid(column=1, row=0)
        self.sync_mode2.grid(column=2, row=0)

        ttk.Separator(orient='horizontal').pack(fill=X)

        frm = ttk.Frame()
        frm.pack()

        ttk.Label(frm, text='曲目ID：').grid(column=0, row=0)

        self.song_id = StringVar()
        self.songs_select = ttk.Combobox(frm, state='readonly', values=[], textvariable=self.song_id)
        self.songs_select.grid(column=1, row=0)
        self.songs_select.bind('<<ComboboxSelected>>', self.song_selected)

        ttk.Label(frm, text='难度：').grid(column=0, row=1)

        self.difficulty = StringVar()
        self.difficulties_select = ttk.Combobox(frm, state='readonly', values=[], textvariable=self.difficulty)
        self.difficulties_select.grid(column=1, row=1)
        self.difficulties_select.bind('<<ComboboxSelected>>', self.difficulty_selected)

        ttk.Separator(orient='horizontal').pack(fill=X)

        frm = ttk.Frame()
        frm.pack()

        ttk.Label(frm, text='规划算法：').grid(column=0, row=0)

        self.algo = StringVar()
        self.algo_select = ttk.Combobox(frm, state='readonly', values=[], textvariable=self.algo)
        self.algo_select.grid(column=1, row=0)

        ttk.Separator(orient='horizontal').pack(fill=X)

        ttk.Label()

        frm = ttk.Frame()
        frm.pack()

        self.delay_lbl = ttk.Label(frm, text='延时时长：')
        self.delay_lbl.grid(column=0, row=0)

        self.delay = DoubleVar()
        self.delay_input = ttk.Spinbox(frm, increment=0.01, textvariable=self.delay, from_=-100, to=100)
        self.delay_input.grid(column=1, row=0)

        ttk.Label(frm, text='秒').grid(column=2, row=0)

        ttk.Separator(orient='horizontal').pack(fill=X)

        self.go = ttk.Button(text='开始!', command=self.run)
        self.go.pack(anchor='center', expand=1)

        ttk.Separator(orient='horizontal').pack(fill=X)

        self.info_label = ttk.Label(text='请开始游戏，再暂停游戏，然后再点击上面的开始按钮')
        self.info_label.pack()

        agreement()

    def sync_mode_changed(self):
        if self.sync_mode.get() == 0:  # delay
            self.info_label['text'] = '请开始游戏，再暂停游戏，然后再点击上面的开始按钮'
            self.delay_input['state'] = 'normal'
        else:  # tap
            self.info_label['text'] = ''
            self.delay_input['state'] = 'disabled'

    def load_songs(self):
        try:
            self.songs_select['values'] = sorted(os.listdir('./Assets/Tracks'))
            if not len(self.songs_select['values']):
                raise RuntimeError('no chart files')
        except Exception:
            messagebox.showinfo(
                '谱面库为空',
                'phisap需要依赖游戏的谱面文件才能工作，然而您当前的谱面库为空\n'
                'phisap支持从游戏安装包中解包并读取谱面文件，接下来请您选择游戏的安装包\n'
                '另外，每当游戏更新后，您都需要重新点击"解包Apk"按钮来更新谱面库',
            )
            extract_apk(self.console)
            self.load_songs()
        finally:
            return self

    def load_cache(self, cache_path):
        self.cache_path = cache_path
        cache = configparser.ConfigParser()

        if os.path.exists(cache_path):
            cache.read(cache_path)

        if not cache.has_section('cache'):
            cache.add_section('cache')

        try:
            self.song_id.set(cache.get('cache', 'songid'))
            difficulties = [
                file[6:-5]
                for file in os.listdir(os.path.join('./Assets/Tracks', self.song_id.get()))
                if 'ans' not in file
            ]
            self.difficulties_select['values'] = difficulties
        except configparser.NoOptionError:
            cache.set('cache', 'songid', '')

        try:
            self.difficulty.set(difficulty := cache.get('cache', 'difficulty'))
            algos = ['algo1', 'algo2']
            if os.path.exists(f'./Assets/Tracks/{self.song_id.get()}/Chart_{difficulty}.json.ans.json'):
                algos.insert(0, '不规划(使用缓存)')
            self.algo_select['values'] = algos
        except configparser.NoOptionError:
            cache.set('cache', 'difficulty', '')

        try:
            self.delay.set(cache.getfloat('cache', 'offset'))
        except configparser.NoOptionError:
            cache.set('cache', 'offset', '1.95')

        self.cache = cache

        return self

    def detect_adb_devices(self):
        return self

    def song_selected(self, event):
        songid = event.widget.get()
        difficulties = [file[6:-5] for file in os.listdir(os.path.join('./Assets/Tracks', songid)) if 'ans' not in file]
        self.difficulties_select['values'] = difficulties

    def difficulty_selected(self, event):
        difficulty = event.widget.get()
        algos = ['algo1', 'algo2']
        if os.path.exists(f'./Assets/Tracks/{self.song_id.get()}/Chart_{difficulty}.json.ans.json'):
            algos.insert(0, '不规划(使用缓存)')
        self.algo_select['values'] = algos

    def run(self):
        try:
            import time

            chart_path = f'./Assets/Tracks/{self.song_id.get()}/Chart_{self.difficulty.get()}.json'

            chart = Chart.from_dict(json.load(open(chart_path)))

            assert self.cache
            assert self.cache_path
            self.cache.set('cache', 'songid', self.song_id.get())
            self.cache.set('cache', 'difficulty', self.difficulty.get())
            self.cache.set('cache', 'offset', str(self.delay.get()))
            self.cache.write(open(self.cache_path, 'w'))

            algo_method = self.algo.get()
            ans: dict
            ans_file = chart_path + '.ans.json'
            if algo_method == '不规划(使用缓存)':
                ans = load_from_json(open(ans_file))
            elif algo_method == 'algo1':
                import algo.algo1

                ans = algo.algo1.solve(chart, self.console)
                export_to_json(ans, open(ans_file, 'w'))
            elif algo_method == 'algo2':
                import algo.algo2

                ans = algo.algo2.solve(chart, self.console)
                export_to_json(ans, open(ans_file, 'w'))
            else:
                raise RuntimeError(f'unknown algo_method: {algo_method}')

            if self.controller is None:
                self.controller = DeviceController()

            device_width = self.controller.device_width
            device_height = self.controller.device_height

            height = device_height
            width = height * 16 // 9
            xoffset = (device_width - width) >> 1
            yoffset = (device_height - height) >> 1
            scale_factor = height / 720

            adapted_ans = [
                (timestamp, [ev.map_to(xoffset, yoffset, scale_factor, scale_factor) for ev in ans[timestamp]])
                for timestamp in sorted(ans.keys())
            ]

            ans_iter = iter(adapted_ans)

            pre_info = self.info_label['text']
            pre_command = self.go['command']
            pre_text = self.go['text']
            pre_delay_lbl = self.delay_lbl['text']
            pre_delay_var = self.delay_input['textvariable']

            delay_offset = DoubleVar()
            delay_offset.set(0)

            if self.sync_mode.get() == 0:
                self.controller.tap(device_width >> 1, device_height >> 1)
                offset = self.delay.get()

                self.info_label['text'] = '准备就绪'

                def stop():
                    self.running = False

                self.go['command'] = stop
                self.go['text'] = '取消'

                self.delay_lbl['text'] = '微调(正为延后，负为提前)：'
                self.delay_input['state'] = 'normal'
                self.delay_input['textvariable'] = delay_offset

                def incremented(_):
                    self.start_time += 0.01

                def decremented(_):
                    self.start_time -= 0.01

                self.delay_input.bind('<<Increment>>', incremented)
                self.delay_input.bind('<<Decrement>>', decremented)

                self.start_time = time.time() + offset

                begin = False
                self.running = True

                timestamp, events = next(ans_iter)
                try:
                    while self.running:
                        self.update()
                        now = round((time.time() - self.start_time) * 1000)
                        if now >= timestamp:
                            if not begin:
                                self.info_label['text'] = '开始操作'
                                begin = True
                            for event in events:
                                self.controller.touch(*event.pos, event.action, pointer_id=event.pointer)
                            timestamp, events = next(ans_iter)
                except Exception:
                    pass
                finally:
                    self.console.print('[client] INFO: 自动打歌已结束')

                self.go['command'] = pre_command
                self.go['text'] = pre_text

                self.info_label['text'] = pre_info
                self.delay_lbl['text'] = pre_delay_lbl

                self.delay_input['textvariable'] = pre_delay_var

                self.delay_input.unbind('<<Increment>>')
                self.delay_input.unbind('<<Decrement>>')
            else:
                self.info_label['text'] = '准备就绪\n请在第一个音符快落到判定线时，再按下上面的按钮\n可以使用空格键触发'
                self.go['text'] = '开始操作'

                self.running = True

                def player_worker(ans_iter: Iterator[tuple[int, list[TouchEvent]]]) -> None:
                    """打歌线程"""
                    if self.controller:
                        timestamp, events = next(ans_iter)
                        self.start_time = time.time() - timestamp / 1000 - 0.01  # 0.01 for the delay time

                        try:
                            while self.running:
                                now = round((time.time() - self.start_time) * 1000)
                                if now >= timestamp:
                                    for event in events:
                                        self.controller.touch(*event.pos, event.action, pointer_id=event.pointer)
                                    timestamp, events = next(ans_iter)
                        except StopIteration:
                            pass
                        finally:
                            self.console.print('打歌完毕')
                    else:
                        self.console.print('self.controller == None')

                    self.go['command'] = pre_command
                    self.go['text'] = pre_text
                    self.info_label['text'] = pre_info
                    self.delay_lbl['text'] = pre_delay_lbl

                    self.delay_input['textvariable'] = pre_delay_var
                    self.delay_input['state'] = 'disabled'

                    self.delay_input.unbind('<<Increment>>')
                    self.delay_input.unbind('<<Decrement>>')

                self.player_worker_thread = Thread(target=player_worker, args=(ans_iter,), daemon=True)

                def go_now():
                    def stop():
                        self.running = False

                    if self.player_worker_thread is None:
                        return

                    self.player_worker_thread.start()
                    self.info_label['text'] = '正在操作'
                    self.go['command'] = stop
                    self.go['text'] = '停止操作'

                    self.delay_lbl['text'] = '微调(正为延后，负为提前)：'
                    self.delay_input['state'] = 'normal'
                    self.delay_input['textvariable'] = delay_offset

                    def incremented(_):
                        self.start_time += 0.01

                    def decremented(_):
                        self.start_time -= 0.01

                    self.delay_input.bind('<<Increment>>', incremented)
                    self.delay_input.bind('<<Decrement>>', decremented)

                self.go['command'] = go_now
                self.update()
        except Exception:
            self.console.print_exception(show_locals=True)


if __name__ == '__main__':
    tk = Tk()
    tk.title('phisap')
    App(tk).load_songs().load_cache('./cache').detect_adb_devices().mainloop()
