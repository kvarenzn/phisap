import socket
import struct
import subprocess
import time


class DeviceController:
    streaming_socket: socket.socket
    controll_socket: socket.socket
    server_process: subprocess.Popen
    device_size: tuple[int, int]

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

        _device_name = self.controll_socket.recv(64)
        width, height = struct.unpack('!HH', self.controll_socket.recv(4))
        self.device_size = width, height

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
