import struct
import time

import usb.core

from algo.base import RawAnswerType, ScreenUtil, TouchAction, TouchEvent


GranularAnswerItem = tuple[int, list[TouchEvent]]


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
        0x09, 0x32,        #     Usage (In Range)
        0x25, 0x01,        #     Logical Maximum (1)
        0x81, 0x02,        #     Input (Data, Variable, Absolute)
        0x75, 0x02,        #     Report Size (2)
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
        return bytes([(id & 0b1111) | (on_screen * 0b110000)]) + struct.pack('HH', x, y)

    @staticmethod
    def _gen_event_data(fingers: dict[int, tuple[int, int]]) -> bytes:
        res = bytes()
        for i in range(10):
            if i in fingers:
                x, y = fingers[i]
                res += HIDController._finger_event(i, True, x, y)
            else:
                res += HIDController._finger_event(i, False, 0, 0)
        return res

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
        # 动态分配指针ID
        pointer_id_map = {}
        ids = set(range(10))
        for timestamp, events in answer:
            operated = set()
            for event in events:
                if event.pointer_id not in pointer_id_map:
                    pointer_id_map[event.pointer_id] = ids.pop()
                pointer_id = pointer_id_map[event.pointer_id]
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
    controller = HIDController((2340, 1080), HIDController.get_devices()[0])
    device_width = controller.device_width
    device_height = controller.device_height

    controller.tap_center()
