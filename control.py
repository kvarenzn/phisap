import socket
import struct
import subprocess
import threading
import time
import random
import os

from algo.algo_base import TouchAction


class DeviceController:
    session_id: str
    video_socket: socket.socket
    control_socket: socket.socket
    server_process: subprocess.Popen
    garbage_collector: threading.Thread
    device_width: int
    device_height: int
    collector_running: bool

    def __init__(self, port: int = 27188, push_server: bool = True, server_dir: str = '.'):
        self.session_id = format(random.randint(0, 0x7FFFFFFF), '08x')
        server_file = next(filter(lambda p: p.startswith('scrcpy-server-v'), os.listdir(server_dir)))
        server_file = os.path.join(server_dir, server_file)
        server_version = server_file.split('v')[-1]
        if push_server:
            subprocess.run(['adb', 'push', server_file, '/data/local/tmp/scrcpy-server.jar'])
        subprocess.run(['adb', 'reverse', f'localabstract:scrcpy_{self.session_id}', f'tcp:{port}'])
        skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        skt.bind(('localhost', port))
        skt.listen(1)
        command_line = [
            'adb',
            'shell',
            'CLASSPATH=/data/local/tmp/scrcpy-server.jar',
            'app_process',
            '/',
            'com.genymobile.scrcpy.Server',
            server_version,
            f'scid={self.session_id}',
            'log_level=info',
            'audio=false',
            'clipboard_autosync=false',
        ]
        self.server_process = subprocess.Popen(command_line)
        # 由于我们指定了audio=false，所以这只有两个socket
        # 其实本来audio streaming可以用于对齐时钟，不过可惜只支持Android 11及以上
        self.video_socket, _ = skt.accept()
        self.control_socket, _ = skt.accept()
        subprocess.run(
            ['adb', 'reverse', '--remove', f'localabstract:scrcpy_{self.session_id}']
        )  # 移除创建的adb tunnel，我们不再需要它了

        # 读取服务端发送的dummy byte，确认连接成功

        self.collector_running = True

        def collector():
            '''垃圾收集器
            实际上我们并不需要scrcpy-server传来的视频数据，
            但如果我们不接收这些数据，server就会崩溃，所以这个线程专门用来接受这些数据，
            然后把它们丢到虚空'''
            try:
                while self.collector_running:
                    _pts = self.video_socket.recv(8)  # unused
                    size = int.from_bytes(self.video_socket.recv(4), 'big')
                    self.video_socket.recv(size)
            except Exception as e:
                print(e.with_traceback(None))
                self.collector_running = False

        def ctrlmsg_receiver():
            '''另一个垃圾收集器
            收集的是scrcpy-server传来的控制事件的信息，
            比如屏幕旋转事件等'''
            try:
                while self.collector_running:
                    _msg_type = self.control_socket.recv(1)
                    size = int.from_bytes(self.control_socket.recv(4), 'big')
                    self.control_socket.recv(size)
            except Exception as e:
                print(e.with_traceback(None))
                self.collector_running = False

        _device_name = self.video_socket.recv(64)  # sendDeviceMeta

        # streamer.writeVideoHeader(device.getScreenInfo().getVideoSize())
        _codec_id = self.video_socket.recv(4).decode()
        self.device_width = int.from_bytes(self.video_socket.recv(4), 'big')
        self.device_height = int.from_bytes(self.video_socket.recv(4), 'big')

        print('[client]', f'device_size = {self.device_width}x{self.device_height}, codec_id = {_codec_id}')

        self.garbage_collector = threading.Thread(target=collector, daemon=True)
        self.garbage_collector.start()

        self.control_collector = threading.Thread(target=ctrlmsg_receiver, daemon=True)
        self.control_collector.start()

    def touch(self, x: int, y: int, action: TouchAction, pointer_id: int = 0xFFFFFFFFFFFFFFFF):
        self.control_socket.send(
            struct.pack(
                '!bbQiiHHHII',
                2,
                action.value,
                pointer_id,
                x,
                y,
                self.device_width,
                self.device_height,
                0xFFFF,  # pressure
                1,  # action_button
                1,  # buttons
            )
        )

    def tap(self, x: int, y: int, pointer_id: int = 0xFFFFFFFFFFFFFFFF):
        self.touch(x, y, TouchAction.DOWN, pointer_id)
        self.touch(x, y, TouchAction.UP, pointer_id)


if __name__ == '__main__':
    pointer_id = 114514
    ctl = DeviceController()
    ctl.touch(0, 0, TouchAction.DOWN, pointer_id)
    for i in range(ctl.device_width):
        time.sleep(0.01)
        ctl.touch(i, i, TouchAction.MOVE, pointer_id)
    ctl.touch(ctl.device_height, ctl.device_height, TouchAction.MOVE, pointer_id)
