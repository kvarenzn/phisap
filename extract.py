import io
import os
from enum import Enum
from math import ceil
from struct import unpack
from typing import IO, NamedTuple, TypeVar, Generic, Any

import lz4.block
import lz4.frame
import lz4.stream

import zipfile

from utils import read_string_end_with_nil

from catalog import Catalog

COMMON_STRINGS = {
    0: 'AABB',
    5: 'AnimationClip',
    19: 'AnimationCurve',
    34: 'AnimationState',
    49: 'Array',
    55: 'Base',
    60: 'BitField',
    69: 'bitset',
    76: 'bool',
    81: 'char',
    86: 'ColorRGBA',
    96: 'Component',
    106: 'data',
    111: 'deque',
    117: 'double',
    124: 'dynamic_array',
    138: 'FastPropertyName',
    155: 'first',
    161: 'float',
    167: 'Font',
    172: 'GameObject',
    183: 'Generic Mono',
    196: 'GradientNEW',
    208: 'GUID',
    213: 'GUIStyle',
    222: 'int',
    226: 'list',
    231: 'long long',
    241: 'map',
    245: 'Matrix4x4f',
    256: 'MdFour',
    263: 'MonoBehaviour',
    277: 'MonoScript',
    288: 'm_ByteSize',
    299: 'm_Curve',
    307: 'm_EditorClassIdentifier',
    331: 'm_EditorHideFlags',
    349: 'm_Enabled',
    359: 'm_ExtensionPtr',
    374: 'm_GameObject',
    387: 'm_Index',
    395: 'm_IsArray',
    405: 'm_IsStatic',
    416: 'm_MetaFlag',
    427: 'm_Name',
    434: 'm_ObjectHideFlags',
    452: 'm_PrefabInternal',
    469: 'm_PrefabParentObject',
    490: 'm_Script',
    499: 'm_StaticEditorFlags',
    519: 'm_Type',
    526: 'm_Version',
    536: 'Object',
    543: 'pair',
    548: 'PPtr<Component>',
    564: 'PPtr<GameObject>',
    581: 'PPtr<Material>',
    596: 'PPtr<MonoBehaviour>',
    616: 'PPtr<MonoScript>',
    633: 'PPtr<Object>',
    646: 'PPtr<Prefab>',
    659: 'PPtr<Sprite>',
    672: 'PPtr<TextAsset>',
    688: 'PPtr<Texture>',
    702: 'PPtr<Texture2D>',
    718: 'PPtr<Transform>',
    734: 'Prefab',
    741: 'Quaternionf',
    753: 'Rectf',
    759: 'RectInt',
    767: 'RectOffset',
    778: 'second',
    785: 'set',
    789: 'short',
    795: 'size',
    800: 'SInt16',
    807: 'SInt32',
    814: 'SInt64',
    821: 'SInt8',
    827: 'staticvector',
    840: 'string',
    847: 'TextAsset',
    857: 'TextMesh',
    866: 'Texture',
    874: 'Texture2D',
    884: 'Transform',
    894: 'TypelessData',
    907: 'UInt16',
    914: 'UInt32',
    921: 'UInt64',
    928: 'UInt8',
    934: 'unsigned int',
    947: 'unsigned long long',
    966: 'unsigned short',
    981: 'vector',
    988: 'Vector2f',
    997: 'Vector3f',
    1006: 'Vector4f',
    1015: 'm_ScriptingClassIdentifier',
    1042: 'Gradient',
    1051: 'Type*',
    1057: 'int2_storage',
    1070: 'int3_storage',
    1083: 'BoundsInt',
    1093: 'm_CorrespondingSourceObject',
    1121: 'm_PrefabInstance',
    1138: 'm_PrefabAsset',
    1152: 'FileSize',
    1161: 'Hash128'
}


class StorageBlock(NamedTuple):
    uncompressed_size: int
    compressed_size: int
    flags: int


class Node(NamedTuple):
    offset: int
    size: int
    flags: int
    path: str


class TypeTreeNode:
    type_: str
    name: str
    byte_size: int
    index: int
    is_array: bool
    version: int
    meta_flag: int
    level: int
    type_str_offset: int
    name_str_offset: int
    ref_type_hash: int


class ClassID(Enum):
    OBJECT = 0
    TEXTURE_2D = 28
    TEXT_ASSET = 49
    AUDIO_CLIP = 83
    MONO_BEHAVIOUR = 114
    ASSET_BUNDLE = 142
    SPRITE = 213


class SerializedType:
    class_id: ClassID
    is_stripped_type: bool
    script_type_index: int
    nodes: list[TypeTreeNode]
    script_id: bytes
    old_type_hash: bytes
    type_dependencies: list[int]

    def __init__(self, reader: IO):
        class_id, self.is_stripped_type, self.script_type_index = unpack('<ibh', reader.read(7))
        self.class_id = ClassID(class_id)
        if self.class_id == ClassID.MONO_BEHAVIOUR:
            self.script_id = reader.read(16)
        self.old_type_hash = reader.read(16)
        number_of_nodes, string_buffer_size = unpack('<ii', reader.read(8))
        self.nodes = []
        for _ in range(number_of_nodes):
            node = TypeTreeNode()
            node.version, node.level, node.is_array, \
            node.type_str_offset, node.name_str_offset, \
            node.byte_size, node.index, node.meta_flag, \
            node.ref_type_hash = unpack('<HbbIIiiiQ', reader.read(32))
            self.nodes.append(node)
        string_buf = io.BytesIO(reader.read(string_buffer_size))

        def read_string(offset: int) -> str:
            if offset & 0x80000000 == 0:
                string_buf.seek(offset)
                return read_string_end_with_nil(string_buf)
            offset = offset & 0x7fffffff;
            return COMMON_STRINGS.get(offset, str(offset))

        for node in self.nodes:
            node.type_ = read_string(node.type_str_offset)
            node.name = read_string(node.name_str_offset)

        type_dependencies_len, = unpack('<I', reader.read(4))
        self.type_dependencies = []
        for i in range(type_dependencies_len):
            self.type_dependencies.append(*unpack('<i', reader.read(4)))


class ObjectInfo:
    byte_start: int
    byte_size: int
    type_id: int
    class_id: ClassID
    path_id: int
    serialized_type: SerializedType


class LocalSerializedObjectIdentifier:
    local_serializerd_file_index: int
    local_identifier_in_file: int


class FileIdentifier:
    guid: bytes
    type: int
    path_name: str


class SerializedFile:
    metadata_size: int
    file_size: int
    version: int
    data_offset: int
    big_endian: bool
    unity_version: str
    target_platform: int
    enable_type_tree: bool
    types: list[SerializedType]
    object_infos: list[ObjectInfo]
    script_types: list[LocalSerializedObjectIdentifier]
    externals: list[FileIdentifier]
    ref_types: list[SerializedType]
    reader: IO

    @classmethod
    def is_serialized_file(cls, content: bytes) -> bool:
        if len(content) < 20:
            return False
        reader = io.BytesIO(content)

        _, file_size, version, data_offset = unpack('!IIII', reader.read(16))
        reader.seek(4, io.SEEK_CUR)  # skip endianess and reversed
        if version >= 22:
            if file_size < 48:
                return False
            _, file_size, data_offset = unpack('<IQQ', reader.read(20))
        if file_size != len(content) or data_offset > file_size:
            return False

        return True

    def __init__(self, content: bytes):
        reader = io.BytesIO(content)

        self.metadata_size, self.file_size, self.version, self.data_offset = unpack('!IIII', reader.read(16))
        self.big_endian = bool(reader.read(1)[0])
        reader.seek(3, 1)  # reserved
        self.unity_version = read_string_end_with_nil(reader)
        self.target_platform, self.enable_type_tree = unpack('<ib', reader.read(5))
        self.enable_type_tree = bool(self.enable_type_tree)

        type_count, = unpack('i', reader.read(4))
        self.types = []
        for _ in range(type_count):
            self.types.append(SerializedType(reader))

        # read objects
        object_count, = unpack('<i', reader.read(4))
        self.object_infos = []
        for _ in range(object_count):
            obj_info = ObjectInfo()

            reader.seek(ceil(reader.tell() / 4) * 4)  # align stream with alignment 4
            obj_info.path_id, obj_info.byte_start, obj_info.byte_size, obj_info.type_id = unpack('<qIIi',
                                                                                                 reader.read(20))
            obj_info.byte_start += self.data_offset
            obj_info.serialized_type = self.types[obj_info.type_id]
            obj_info.class_id = obj_info.serialized_type.class_id

            self.object_infos.append(obj_info)

        # read scripts
        script_count, = unpack('<i', reader.read(4))
        self.script_types = []
        for _ in range(script_count):
            script_type = LocalSerializedObjectIdentifier()
            script_type.local_serializerd_file_index, = unpack('<i', reader.read(4))

            reader.seek(ceil(reader.tell() / 4) * 4)  # align stream with alignment
            script_type.local_identifier_in_file, = unpack('<q', reader.read(8))

            self.script_types.append(script_type)

        # externals
        external_count, = unpack('<i', reader.read(4))
        self.externals = []
        for _ in range(external_count):
            external = FileIdentifier()
            read_string_end_with_nil(reader)
            external.guid = reader.read(16)
            external.type, = unpack('<i', reader.read(4))
            external.path_name = read_string_end_with_nil(reader)
            self.externals.append(external)

        # ref types
        ref_type_count, = unpack('<i', reader.read(4))
        self.ref_types = [SerializedType(reader) for _ in range(ref_type_count)]

        self.reader = reader


class NamedObject:
    name: str

    def __init__(self, reader: IO):
        self.name = reader.read(unpack('<i', reader.read(4))[0]).decode()
        reader.seek(ceil(reader.tell() / 4) * 4)


T = TypeVar('T')


class PPtr(Generic[T]):
    file_id: int
    path_id: int

    assets_file: SerializedFile
    index: int

    def __init__(self, reader: IO):
        self.file_id, self.path_id = unpack('<iq', reader.read(12))


class TextAsset(NamedObject):
    text: str

    def __init__(self, reader: IO):
        super().__init__(reader)
        length, = unpack('<i', reader.read(4))
        self.text = reader.read(length).decode()

    def __repr__(self):
        return f'TextAsset(text={repr(self.text)})'


class AssetInfo:
    preload_index: int
    preload_size: int
    asset: PPtr[Any]

    def __init__(self, reader: IO):
        self.preload_index, self.preload_size = unpack('<ii', reader.read(8))
        self.asset = PPtr(reader)


class AssetBundle(NamedObject):
    preload_table: list[PPtr[Any]]
    container: dict[str, AssetInfo]

    def __init__(self, reader: IO):
        super().__init__(reader)
        # preload table
        size, = unpack('<i', reader.read(4))
        self.preload_table = []
        for _ in range(size):
            self.preload_table.append(PPtr(reader))

        # container
        size, = unpack('<i', reader.read(4))
        self.container = {}
        for _ in range(size):
            key = reader.read(unpack('<i', reader.read(4))[0]).decode()
            reader.seek(ceil(reader.tell() / 4) * 4)
            self.container[key] = AssetInfo(reader)


class RectF:
    x: float
    y: float
    width: float
    height: float

    def __init__(self, reader: IO):
        self.x, self.y, self.width, self.height = unpack('<ffff', reader.read(16))


class Sprite(NamedObject):
    rect: RectF

    def __init__(self, reader: IO):
        super().__init__(reader)
        self.rect = RectF(reader)


class BundleFile:
    signature: str
    version: int
    unity_version: str
    unity_revision: str

    size: int
    compressed_blocks_info_size: int
    uncompressed_blocks_info_size: int
    flags: int

    blocks_info: list[StorageBlock]
    directory_info: list[Node]
    files: list[SerializedFile]

    objects: list[NamedObject]

    def __init__(self, f: IO):
        self.signature = read_string_end_with_nil(f)
        self.version, = unpack('!I', f.read(4))
        self.unity_version = read_string_end_with_nil(f)
        self.unity_revision = read_string_end_with_nil(f)

        self.size, self.compressed_blocks_info_size, self.uncompressed_blocks_info_size, self.flags = unpack('!qIII',
                                                                                                             f.read(20))
        compressed_data = f.read(self.compressed_blocks_info_size)
        compression_type = self.flags & 0x3f
        binfo_reader = lz4.block.decompress(compressed_data, uncompressed_size=self.uncompressed_blocks_info_size)
        binfo_reader = io.BytesIO(binfo_reader)
        uncompressed_data_hash = binfo_reader.read(16)

        blocks_info_count, = unpack('!i', binfo_reader.read(4))
        self.blocks_info = [StorageBlock(*unpack('!IIH', binfo_reader.read(10))) for _ in range(blocks_info_count)]

        nodes_count, = unpack('!i', binfo_reader.read(4))
        self.directory_info = [Node(*unpack('!qqI', binfo_reader.read(20)), read_string_end_with_nil(binfo_reader)) for
                               _ in range(nodes_count)]

        blocks = bytes()
        for block in self.blocks_info:
            compress_method = block.flags & 0x3f
            if compress_method == 0:  # raw data without compression
                blocks += f.read(block.compressed_size)
            elif compress_method == 1:  # 7zip
                print(f'7zip compression method not supported now, file {f.name} used this method')
            elif compress_method in (2, 3):  # LZ4 or LZMA
                blocks += lz4.block.decompress(f.read(block.compressed_size), uncompressed_size=block.uncompressed_size)
            else:
                print(f'unknown compression method: {compress_method} in file {f.name}')
        block_stream = io.BytesIO(blocks)

        self.files = []
        for node in self.directory_info:
            block_stream.seek(node.offset)
            content = block_stream.read(node.size)
            if SerializedFile.is_serialized_file(content):
                self.files.append(SerializedFile(content))
            else:
                pass

        self.objects = []
        for file in self.files:
            reader = file.reader
            for obj_info in file.object_infos:
                reader.seek(obj_info.byte_start)
                if obj_info.class_id == ClassID.OBJECT:
                    pass
                elif obj_info.class_id == ClassID.ASSET_BUNDLE:
                    self.objects.append(AssetBundle(io.BytesIO(reader.read())))
                elif obj_info.class_id == ClassID.TEXT_ASSET:
                    self.objects.append(TextAsset(io.BytesIO(reader.read())))


def load_apk(apk_path: str):
    apk_file = zipfile.ZipFile(apk_path)
    catalog = Catalog(apk_file.open('assets/aa/catalog.json'))
    print(catalog)
    for file in apk_file.namelist():
        if not file.startswith('assets/aa/Android'):
            continue
        b = BundleFile(apk_file.open(file))
        basename = file[18:]
        if len(b.objects) == 2 and any(isinstance(obj, TextAsset) for obj in b.objects):
            container = next(filter(lambda o: isinstance(o, AssetBundle), b.objects))
            text = next(filter(lambda o: isinstance(o, TextAsset), b.objects))
            filename = next(iter(container.container.keys()))
            if not filename.startswith('Assets/'):
                filename = catalog.fname_map[basename]
            basedir = os.path.dirname(filename)
            if basedir and not os.path.exists(basedir):
                os.makedirs(basedir)
            with open(filename, 'w') as out:
                out.write(text.text)


if __name__ == '__main__':
    apk_path = input('path: ')
    load_apk(apk_path)
