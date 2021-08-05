import socket
import struct
import subprocess
import threading
import time

import av


class DeviceController:
    streaming_socket: socket.socket
    controll_socket: socket.socket
    server_process: subprocess.Popen
    garbage_collector: threading.Thread
    device_size: tuple[int, int]
    lock: threading.Lock

    def __init__(self, port: int = 27183, push_server: bool = True):
        if push_server:
            subprocess.run(['adb', 'push', './server/phisap-server', '/data/local/tmp/phisap-server.jar'])
        subprocess.run(['adb', 'reverse', 'localabstract:phisap', f'tcp:{port}'])
        skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        skt.bind(('localhost', port))
        skt.listen(1)
        self.server_process = subprocess.Popen(
            ['adb', 'shell', 'CLASSPATH=/data/local/tmp/phisap-server.jar', 'app_process', '/',
             'com.rabbithouse.svr.Server'])
        self.controll_socket, _anydata = skt.accept()
        subprocess.run(['adb', 'reverse', '--remove', 'localabstract:phisap'])

        self.lock = threading.Lock()

        self.collector_running = True

        def collector(lock: threading.Lock):
            codec = av.CodecContext.create('h264', 'r')
            last_pixel = None
            lock.acquire()
            done = False
            while self.collector_running:
                header = self.controll_socket.recv(12)
                pts, size = struct.unpack('!qI', header)
                data = self.controll_socket.recv(size)
                if not done:
                    packets = codec.parse(data)
                    for packet in packets:
                        try:
                            frames = codec.decode(packet)
                            for frame in frames:
                                arr = frame.to_rgb().to_ndarray()
                                color = arr[0, 0]
                                if last_pixel is None or (color - last_pixel).all():
                                    if last_pixel is None:
                                        last_pixel = color
                                        continue
                                    if (color > 230).all():
                                        lock.release()
                                        done = True
                                    last_pixel = color
                        finally:
                            pass

        _device_name = self.controll_socket.recv(64)
        width, height = struct.unpack('!HH', self.controll_socket.recv(4))
        self.garbage_collector = threading.Thread(target=collector, args=(self.lock,), daemon=True)
        self.garbage_collector.start()
        self.device_size = width, height

    def stop_streaming(self):
        self.controll_socket.send(struct.pack('!b', 11))
        self.collector_running = False

    def touch(self, x: int, y: int, action: int, pressure: int = 0xffff, pointer_id: int = 0xffffffffffffffff):
        self.controll_socket.send(
            struct.pack('!bbQiiHHHI', 2, action, pointer_id, x, y, *self.device_size, pressure, 1))

    def touch_down(self, x: int, y: int, pressure: int = 0xffff, pointer_id: int = 0xffffffffffffffff):
        self.controll_socket.send(struct.pack('!bbQiiHHHI', 2, 0, pointer_id, x, y, *self.device_size, pressure, 1))

    def touch_move(self, x: int, y: int, pressure: int = 0xffff, pointer_id: int = 0xffffffffffffffff):
        self.controll_socket.send(struct.pack('!bbQiiHHHI', 2, 2, pointer_id, x, y, *self.device_size, pressure, 1))

    def touch_up(self, x: int, y: int, pressure: int = 0xffff, pointer_id: int = 0xffffffffffffffff):
        self.controll_socket.send(struct.pack('!bbQiiHHHI', 2, 1, pointer_id, x, y, *self.device_size, pressure, 1))

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
