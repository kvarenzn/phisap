from collections import defaultdict
import socket
import struct
import subprocess
import threading
import time
import random
import os
from typing import Iterable

import usb.core
import av

from algo.base import RawAnswerType, ScreenUtil, TouchAction, TouchEvent


GranularAnswerItem = tuple[int, list[TouchEvent]]


class ScrcpyController:
    serial: str | None
    port: int
    session_id: str
    skt: socket.socket
    video_socket: socket.socket
    control_socket: socket.socket
    server_process: subprocess.Popen
    streaming_collector: threading.Thread
    control_collector: threading.Thread
    device_width: int
    device_height: int
    collector_running: bool

    def __init__(
        self, serial: str | None = None, port: int = 27188, push_server: bool = True, server_dir: str = '.'
    ) -> None:
        self.serial = serial
        self.port = port
        adb = ('adb',) if serial is None else ('adb', '-s', serial)
        self.session_id = format(random.randint(0, 0x7FFFFFFF), '08x')
        server_file = next(filter(lambda p: p.startswith('scrcpy-server-v'), os.listdir(server_dir)))
        server_file = os.path.join(server_dir, server_file)
        server_version = server_file.split('v')[-1]
        if push_server:
            subprocess.run([*adb, 'push', server_file, '/data/local/tmp/scrcpy-server.jar'])
        self.skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        while True:
            try:
                self.skt.bind(('localhost', self.port))
                break
            except OSError as e:
                if e.errno == 98:  # Address already in use
                    self.port += 1
                else:
                    raise e
        self.skt.listen(1)
        subprocess.run([*adb, 'reverse', f'localabstract:scrcpy_{self.session_id}', f'tcp:{self.port}'])
        command_line = [
            *adb,
            'shell',
            'CLASSPATH=/data/local/tmp/scrcpy-server.jar',
            'app_process',
            '/',
            'com.genymobile.scrcpy.Server',
            server_version,
            f'scid={self.session_id}',
            'log_level=info',
            # 'video_codec=h264',  # TODO: 主界面加入相关设置
            'audio=false',
            # 'video_encoder=OMX.google.h264.encoder',
            'clipboard_autosync=false',
        ]
        self.server_process = subprocess.Popen(command_line)
        # 由于我们指定了audio=false，所以这只有两个socket
        # 其实本来audio streaming可以用于对齐时钟，不过可惜只支持Android 11及以上
        self.video_socket, _ = self.skt.accept()
        self.control_socket, _ = self.skt.accept()
        subprocess.run(
            [*adb, 'reverse', '--remove', f'localabstract:scrcpy_{self.session_id}']
        )  # 移除创建的adb tunnel，我们不再需要它了

        self.collector_running = True

        def streaming_decoder():
            '''解码手机端传回的视频数据，得到视频的尺寸'''
            codec = av.CodecContext.create('h264', 'r')
            try:
                while self.collector_running:
                    _pts = self.video_socket.recv(8)  # unused
                    size = int.from_bytes(self.video_socket.recv(4), 'big')
                    packets = codec.parse(self.video_socket.recv(size))
                    for packet in packets:
                        frames = codec.decode(packet)
                        for frame in frames:
                            if self.device_width != frame.width or self.device_height != frame.height:
                                print(
                                    '[client]',
                                    f'device_size: {self.device_width}x{self.device_height} -> {frame.width}x{frame.height}',
                                )
                                self.device_width = frame.width
                                self.device_height = frame.height
                            break
                        break
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
        codec_id = self.video_socket.recv(4).decode()
        self.device_width = int.from_bytes(self.video_socket.recv(4), 'big')
        self.device_height = int.from_bytes(self.video_socket.recv(4), 'big')

        print('[client]', f'device_size = {self.device_width}x{self.device_height}, codec_id = {codec_id}')

        self.streaming_collector = threading.Thread(target=streaming_decoder, daemon=True)
        self.streaming_collector.start()

        self.control_collector = threading.Thread(target=ctrlmsg_receiver, daemon=True)
        self.control_collector.start()

    def touch(self, x: int, y: int, action: TouchAction, pointer_id: int) -> None:
        self.control_socket.send(
            struct.pack(
                '!bbQiiHHHII',
                2,  # type: SC_CONTROL_MSG_TYPE_INJECT_TOUCH_EVENT
                action.value,
                pointer_id,
                x,
                y,
                self.device_width,
                self.device_height,
                0xFFFF,  # pressure
                1,  # action_button: AMOTION_EVENT_BUTTON_PRIMARY
                1,  # buttons: AMOTION_EVENT_BUTTON_PRIMARY
            )
        )

    def tap_center(self, pointer_id: int = 1000, delay: float = 0.1) -> None:
        self.touch(self.device_width >> 1, self.device_height >> 1, TouchAction.DOWN, pointer_id)
        time.sleep(delay)
        self.touch(self.device_width >> 1, self.device_height >> 1, TouchAction.UP, pointer_id)

    def clean(self) -> None:
        self.collector_running = False
        self.server_process.kill()
        self.video_socket.close()
        self.control_socket.close()
        self.skt.close()

    def preprocess(self, screen: ScreenUtil, answer: RawAnswerType) -> list[GranularAnswerItem]:
        height = self.device_height
        width = self.device_width * screen.width // screen.height
        offset_x = (self.device_width - width) >> 1
        offset_y = (self.device_height - height) >> 1
        x_scale = width / screen.width
        y_scale = height / screen.height
        return [
            (
                ts,
                [
                    TouchEvent(
                        (offset_x + round(event.pos.real * x_scale), offset_y + round(event.pos.imag * y_scale)),
                        event.action,
                        event.pointer_id,
                    )
                    for event in events
                ],
            )
            for ts, events in answer
        ]

    def connect(self) -> None:
        pass

    @staticmethod
    def get_devices() -> list[str]:
        ret, output = subprocess.getstatusoutput('adb devices')
        if ret != 0:
            return []
        return [
            serial
            for serial, status in (
                line.split('\t')
                for line in output.splitlines()
                if not line.startswith('*') and line != 'List of devices attached'
            )
            if status == 'device'
        ]


ViscousAnswerItem = tuple[int, bytes]


class HIDController:
    _REPORT_DESCRIPTION_HEAD = bytes([
        0x05, 0x0d,        # Usage Page (Digitalizers)
        0x09, 0x04,        # Usage (Touch Screen)
        0xa1, 0x01,        # Collection (Application)
        0x15, 0x00,        #   Logical Minimum (0)
    ])  # fmt: skip
    _REPORT_DESCRIPTION_BODY_P1 = bytes([
        0x09, 0x22,        #   Usage (Finger)
        0xa1, 0x02,        #   Collection (Logical),
        0x09, 0x51,        #     Usage (Contact Identifier)
        0x75, 0x04,        #     Report Size (4)
        0x95, 0x01,        #     Report Count (1)
        0x25, 0x09,        #     Logical Maximum (9)
        0x81, 0x02,        #     Input (Data, Variable, Absolute)
        0x09, 0x42,        #     Usage (Tip Switch)
        0x25, 0x01,        #     Logical Maximum (1)
        0x75, 0x01,        #     Report Size (1)
        0x81, 0x02,        #     Input (Data, Variable, Absolute)
        0x75, 0x03,        #     Report Size (3)
        0x81, 0x01,        #     Input (Constant)
        0x05, 0x01,        #     Usage Page (Generic Desktop Page)
        0x09, 0x30,        #     Usage (X)
        0x26,              #     Logical Maximum (Currently Unknown)
    ])  # fmt: skip
    _REPORT_DESCRIPTION_BODY_P2 = bytes([
        0x75, 0x10,        #     Report Size (16)
        0x81, 0x02,        #     Input (Data, Variable, Absolute)
        0x09, 0x31,        #     Usage (Y)
        0x26,              #     Logical Maximum (Currently Unknown)
    ])  # fmt: skip
    _REPORT_DESCRIPTION_BODY_P3 = bytes([
        0x81, 0x02,        #     Input (Data, Variable, Absolute)
        0x05, 0x0d,        #     Usage Page (Digitalizers)
        0xc0,              #   End Collection
    ])  # fmt: skip
    _REPORT_DESCRIPTION_TAIL = bytes([
        0x09, 0x54,        #   Usage (Contact Count)
        0x25, 0x10,        #   Logical Maximum (16)
        0x75, 0x04,        #   Report Size (4)
        0x81, 0x02,        #   Input (Data, Variable, Absolute)
        0x09, 0x55,        #   Usage (Contact Count Maximum)
        0x81, 0x01,        #   Input (Constant)
        0xc0,              # End Collection
    ])  # fmt: skip

    accessory_id: int
    serial: str
    device_width: int
    device_height: int
    _device: usb.core.Device
    _report_description: bytes

    def __init__(self, device_size: tuple[int, int], serial: str) -> None:
        self.serial = serial
        width, height = device_size
        self.device_width = width
        self.device_height = height
        desc_body = (
            self._REPORT_DESCRIPTION_BODY_P1
            + struct.pack('H', width)
            + self._REPORT_DESCRIPTION_BODY_P2
            + struct.pack('H', height)
            + self._REPORT_DESCRIPTION_BODY_P3
        )
        self._report_description = self._REPORT_DESCRIPTION_HEAD + desc_body * 10 + self._REPORT_DESCRIPTION_TAIL
        self.accessory_id = 114514
        self._find_device(serial)

    def _find_device(self, serial: str) -> None:
        devices = usb.core.find(find_all=True)
        if not devices:
            return
        for device in devices:
            try:
                if serial == device.serial_number:
                    self._device = device
                    break
            except ValueError:
                pass

    def clean(self) -> None:
        self.disconnect()

    def connect(self) -> None:
        self._register_hid()
        self._set_hid_report_description()

    def disconnect(self) -> None:
        self._unregister_hid()

    @staticmethod
    def _finger_event(id: int, on_screen: bool, x: int, y: int) -> bytes:
        return bytes([(id & 0b1111) | (on_screen << 4)]) + struct.pack('HH', x, y)

    @staticmethod
    def _gen_event_data_1(fingers: Iterable[tuple[int, int, int]]) -> bytes:
        res = bytes()
        count = 0
        ids = set(range(10))
        for id, x, y in fingers:
            res += HIDController._finger_event(id, True, x, y)
            count += 1
            ids.remove(id)
        for _ in range(10 - count):
            res += HIDController._finger_event(ids.pop(), False, 0, 0)
        return res + bytes([0b10100000 | (count & 0b1111)])
    
    @staticmethod
    def _gen_event_data(fingers: dict[int, tuple[int, int]]) -> bytes:
        res = bytes()
        count = 0
        for i in range(10):
            if i in fingers:
                res += HIDController._finger_event(i, True, fingers[i][0], fingers[i][1])
            else:
                res += HIDController._finger_event(i, False, 0, 0)
        return res + bytes([0b10100000 | (count & 0b1111)])

    def _register_hid(self):
        self._device.ctrl_transfer(
            64,  # ENDPOINT_OUT | REQUEST_TYPE_VENDOR
            54,  # ACCESSORY_REGISTER_HID
            self.accessory_id,
            len(self._report_description),
        )  # fmt: skip

    def _unregister_hid(self):
        self._device.ctrl_transfer(
            64,  # ENDPOINT_OUT | REQUEST_TYPE_VENDOR
            55,  # ACCESSORY_UNREGISTER_ID
            self.accessory_id, 0
        )  # fmt: skip

    def _set_hid_report_description(self):
        self._device.ctrl_transfer(
            64,  # ENDPOINT_OUT | REQUEST_TYPE_VENDOR
            56,  # ACCESSORY_SET_HID_REPORT_DESC
            self.accessory_id,
            0,
            self._report_description,
        )  # fmt: skip

    def _send_hid_event(self, event: bytes):
        self._device.ctrl_transfer(
            64,  # ENDPOINT_OUT | REQUEST_TYPE_VENDOR
            57,  # ACCESSORY_SEND_HID_EVENT
            self.accessory_id, 0, event
        )  # fmt: skip

    def send(self, event: bytes):
        self._send_hid_event(event)

    def preprocess(self, screen: ScreenUtil, answer: RawAnswerType) -> list[ViscousAnswerItem]:
        res = []
        current_fingers: dict[int, tuple[int, int]] = {}
        short_edge = min(self.device_width, self.device_height)
        long_edge = max(self.device_width, self.device_height)
        medium_edge = short_edge // screen.height * screen.width
        offset_x = (long_edge - medium_edge) >> 1
        offset_y = 0
        scale_x = medium_edge // screen.width
        scale_y = short_edge // screen.height
        for timestamp, events in answer:
            operated = set()
            for event in events:
                pointer_id = event.pointer_id - 1000
                x = round(event.pos.real * scale_x) + offset_x
                y = round(event.pos.imag * scale_y) + offset_y
                x, y = self.device_width - y, x
                assert pointer_id not in operated
                operated.add(pointer_id)
                match event.action:
                    case TouchAction.DOWN:
                        assert pointer_id not in current_fingers
                        current_fingers[pointer_id] = (x, y)
                    case TouchAction.MOVE:
                        assert pointer_id in current_fingers
                        current_fingers[pointer_id] = (x, y)
                    case TouchAction.UP:
                        assert pointer_id in current_fingers
                        del current_fingers[pointer_id]
            res.append((timestamp, self._gen_event_data(current_fingers)))
        return res

    def tap_center(self, delay: float = 0.1) -> None:
        self._send_hid_event(self._gen_event_data({0: (self.device_width >> 1, self.device_height >> 1)}))
        time.sleep(delay)
        self._send_hid_event(self._gen_event_data({}))

    @staticmethod
    def get_devices() -> list[str]:
        res = []
        devices = usb.core.find(find_all=True)
        if devices is None:
            return res
        for device in devices:
            try:
                serial_number = device.serial_number
                if isinstance(serial_number, str):
                    res.append(serial_number)
            except ValueError:
                pass
        return res


if __name__ == '__main__':
    print(ScrcpyController.get_devices())
    controller = ScrcpyController()
    device_width = controller.device_width
    device_height = controller.device_height

    controller.tap_center()
