import io
from io import SEEK_CUR, SEEK_END
from typing import IO, Literal
from struct import unpack


class BinaryReader:
    _stream: IO[bytes]
    _format_head: str
    _big_endian: bool
    _byte_order: Literal['big'] | Literal['little']

    def __init__(self, stream: IO[bytes] | bytes | bytearray, big_endian: bool = True):
        if isinstance(stream, (bytes, bytearray)):
            self._stream = io.BytesIO(stream)
        else:
            self._stream = stream
            self._stream.seek(0)
        self.big_endian = big_endian

    @property
    def boolean(self) -> bool:
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
        return self._big_endian

    @big_endian.setter
    def big_endian(self, big_endian: bool):
        self._big_endian = big_endian
        if big_endian:
            self._format_head = '>'
            self._byte_order = 'big'
        else:
            self._format_head = '<'
            self._byte_order = 'little'

    def offset(self, offset: int) -> 'BinaryReader':
        self._stream.seek(offset)
        return self

    def skip(self, count: int):
        self._stream.seek(count, SEEK_CUR)

    def align(self, size: int) -> int:
        return self._stream.seek(-self._stream.tell() % size, SEEK_CUR)

    def read(self, count: int) -> bytes:
        return self._stream.read(count)

    def string(self, length: int, encoding: str = 'utf-8') -> str:
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

    def bcstrl(self, max_size: int) -> bytes:
        barr = bytearray()
        counter = 0
        while (b := self._stream.read(1)) != b'\0' and counter < max_size:
            counter += 1
            barr.extend(b)
        return barr

    def aligned_string(self) -> str:
        res = self.string(self.i32)
        self.align(4)
        return res

    @property
    def f32(self) -> float:
        return unpack(self._format_head + 'f', self._stream.read(4))[0]

    @property
    def f64(self) -> float:
        return unpack(self._format_head + 'd', self._stream.read(8))[0]

    @property
    def i8(self) -> int:
        return int.from_bytes(self._stream.read(1), self._byte_order, signed=True)

    @property
    def u8(self) -> int:
        return int.from_bytes(self._stream.read(1), self._byte_order)

    @property
    def i16(self) -> int:
        return int.from_bytes(self._stream.read(2), self._byte_order, signed=True)

    @property
    def u16(self) -> int:
        return int.from_bytes(self._stream.read(2), self._byte_order)

    @property
    def i32(self) -> int:
        return int.from_bytes(self._stream.read(4), self._byte_order, signed=True)

    @property
    def u32(self) -> int:
        return int.from_bytes(self._stream.read(4), self._byte_order)

    @property
    def i64(self) -> int:
        return int.from_bytes(self._stream.read(8), self._byte_order, signed=True)

    @property
    def u64(self) -> int:
        return int.from_bytes(self._stream.read(8), self._byte_order)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


__all__ = ['BinaryReader']
