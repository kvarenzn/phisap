import io
from io import SEEK_CUR, SEEK_END
from typing import BinaryIO
from struct import unpack, calcsize


class BinaryReader:
    _KNOWN_TYPES = {
        'i32': 'i',
        'u32': 'I',
        'i16': 'h',
        'u16': 'H',
        'i8': 'b',
        'u8': 'B',
        'i64': 'q',
        'u64': 'Q',
        'f32': 'f',
        'f64': 'd'
    }

    _stream: BinaryIO
    _format_head: str
    _header_backup: str | None

    def __init__(self, stream: BinaryIO | bytes | bytearray, big_endian: bool = True):
        if isinstance(stream, (bytes, bytearray)):
            self._stream = io.BytesIO(stream)
        else:
            self._stream = stream
            self._stream.seek(0)
        self._format_head = '>' if big_endian else '<'
        self._header_backup = None

    @property
    def bool(self) -> bool:
        return bool(self._stream.read(1)[0])

    @property
    def pos(self) -> int:
        return self._stream.tell()

    @pos.setter
    def pos(self, new_pos: int):
        if new_pos >= 0:
            self._stream.seek(new_pos)
        else:
            self._stream.seek(-new_pos, SEEK_END)

    def __len__(self) -> int:
        pos = self._stream.tell()
        place = self._stream.seek(0, SEEK_END)
        self._stream.seek(pos)
        return place

    @property
    def big_endian(self) -> bool:
        return self._format_head == '>'

    @big_endian.setter
    def big_endian(self, big_endian: bool):
        self._format_head = '>' if big_endian else '<'

    def save_endian(self):
        self._header_backup = self._format_head

    def restore_endian(self):
        if self._header_backup is not None:
            self._format_head = self._header_backup

    def offset(self, offset: int) -> 'BinaryReader':
        self._stream.seek(offset)
        return self

    def skip(self, count: int):
        self._stream.seek(count, SEEK_CUR)

    def align(self, size: int) -> int:
        return self._stream.seek(-self._stream.tell() % size, SEEK_CUR)

    def read(self, count: int) -> bytes:
        return self._stream.read(count)

    def str(self, length: int, encoding: str = 'utf-8') -> str:
        return self._stream.read(length).decode(encoding=encoding)

    def bcstr(self) -> bytes:
        barr = bytearray()
        while (b := self._stream.read(1)) != b'\0':
            barr += b
        return bytes(barr)

    def cstr(self) -> str:
        barr = bytearray()
        while (b := self._stream.read(1)) != b'\0':
            barr += b
        return barr.decode()

    def bcstrl(self, max_size: int) -> str:
        barr = bytearray()
        counter = 0
        while (b := self._stream.read(1)) != b'\0' and counter < max_size:
            counter += 1
            barr.extend(b)
        return barr

    def aligned_string(self) -> str:
        res = self.str(self.i32)
        self.align(4)
        return res

    def __getattr__(self, name):
        if name in self._KNOWN_TYPES:
            fmt = self._KNOWN_TYPES[name]
            return unpack(self._format_head + fmt, self._stream.read(calcsize(fmt)))[0]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
