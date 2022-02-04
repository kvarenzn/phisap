import socket
import struct
import subprocess
import threading
import time
import os

class DeviceController:
    video_socket: socket.socket
    control_socket: socket.socket
    server_process: subprocess.Popen
    garbage_collector: threading.Thread
    device_size: tuple[int, int]
    collector_running: bool

    def __init__(self, port: int = 27183, push_server: bool = True, server_dir: str = '.'):
        server_file = next(filter(lambda p: p.startswith('scrcpy-server-v'), os.listdir(server_dir)))
        server_file = os.path.join(server_dir, server_file)
        server_version = server_file.split('v')[-1]
        if push_server:
            subprocess.run(['adb', 'push', server_file, '/data/local/tmp/scrcpy-server.jar'])
        subprocess.run(['adb', 'reverse', 'localabstract:scrcpy', f'tcp:{port}'])
        skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        skt.bind(('localhost', port))
        skt.listen(1)
        self.server_process = subprocess.Popen(
            ['adb', 'shell', 'CLASSPATH=/data/local/tmp/scrcpy-server.jar', 'app_process', '/',
             'com.genymobile.scrcpy.Server',
             server_version,
             'log_level=warn',
             'bit_rate=8000000',
             'clipboard_autosync=false'
             ])
        self.video_socket, _ = skt.accept()
        self.control_socket, _ = skt.accept()
        subprocess.run(['adb', 'reverse', '--remove', 'localabstract:scrcpy'])  # 禁用adb tunnel

        self.collector_running = True

        def collector():
            '''垃圾收集器
            实际上我们并不需要scrcpy-server传来的视频数据，
            但如果我们不接收这些数据，server就会崩溃，所以这个线程专门用来接受这些数据，
            然后把它们丢到虚空'''
            while self.collector_running:
                header = self.video_socket.recv(12)
                pts, size = struct.unpack('!qI', header)
                self.video_socket.recv(size)

        def ctrlmsg_receiver():
            '''另一个垃圾收集器
            收集的是scrcpy-server传来的控制事件的信息，
            比如屏幕旋转事件等
            '''
            while self.collector_running:
                msg_type = self.control_socket.recv(1)
                size, = struct.unpack('!I', self.control_socket.recv(4))
                self.control_socket.recv(size)

        _device_name = self.video_socket.recv(64)
        width, height = struct.unpack('!HH', self.video_socket.recv(4))
        self.device_size = width, height

        self.garbage_collector = threading.Thread(target=collector, daemon=True)
        self.garbage_collector.start()

        self.control_collector = threading.Thread(target=ctrlmsg_receiver, daemon=True)
        self.control_collector.start()


    def touch(self, x: int, y: int, action: int, pressure: int = 0xffff, pointer_id: int = 0xffffffffffffffff):
        self.control_socket.send(
            struct.pack('!bbQiiHHHI', 2, action, pointer_id, x, y, *self.device_size, pressure, 1))

    def touch_down(self, x: int, y: int, pressure: int = 0xffff, pointer_id: int = 0xffffffffffffffff):
        self.control_socket.send(struct.pack('!bbQiiHHHI', 2, 0, pointer_id, x, y, *self.device_size, pressure, 1))

    def touch_move(self, x: int, y: int, pressure: int = 0xffff, pointer_id: int = 0xffffffffffffffff):
        self.control_socket.send(struct.pack('!bbQiiHHHI', 2, 2, pointer_id, x, y, *self.device_size, pressure, 1))

    def touch_up(self, x: int, y: int, pressure: int = 0xffff, pointer_id: int = 0xffffffffffffffff):
        self.control_socket.send(struct.pack('!bbQiiHHHI', 2, 1, pointer_id, x, y, *self.device_size, pressure, 1))

    def tap(self, x: int, y: int, pointer_id: int = 0xffffffffffffffff, pressure: int = 0xffff):
        self.touch_down(x, y, pressure, pointer_id)
        self.touch_up(x, y, pressure, pointer_id)


if __name__ == '__main__':
    ids = 0
    ctl = DeviceController()
    while True:
        print(f'tap {ids}')
        ctl.touch_down(200, 200, pointer_id=ids)
        ids += 1
        time.sleep(0.6)
