from io import SEEK_CUR
from typing import IO
from struct import unpack, calcsize


class BinaryReader:
    KNOWN_TYPES = {
        'i32': 'i',
        'u32': 'I',
        'i16': 'h',
        'u16': 'H',
        'i8': 'b',
        'u8': 'B',
        'i64': 'q',
        'u64': 'Q',
    }

    _stream: IO
    anchor: int

    def __init__(self, stream: IO):
        self._stream = stream
        self._stream.seek(0)
        self.anchor = 0

    @property
    def pos(self) -> int:
        return self._stream.tell()

    @pos.setter
    def pos(self, new_pos: int):
        self._stream.seek(new_pos)

    def offset(self, offset: int) -> 'BinaryReader':
        self._stream.seek(offset)
        return self

    def suboffset(self, offset: int) -> 'BinaryReader':
        self._stream.seek(self.anchor + offset)
        return self

    def skip(self, count: int):
        self._stream.seek(count, SEEK_CUR)

    def bytes(self, count: int) -> bytes:
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

    def __getattr__(self, name):
        if name in self.KNOWN_TYPES:
            format_ = self.KNOWN_TYPES[name]
            return unpack(format_, self._stream.read(calcsize(format_)))[0]
