import os.path
import pathlib
from enum import Enum, auto
from typing import TypeVar, Generic, IO, Optional

import lz4.block
from rich.console import Console
from PIL import Image

from binary_reader import BinaryReader

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
    1161: 'Hash128',
}


class TypeTreeNode:
    type_: str
    name: str
    byte_size: int
    index: int
    type_flags: int
    version: int
    meta_flag: int
    level: int
    type_str_offset: int
    name_str_offset: int
    ref_type_hash: int


class TypeTree:
    nodes: list[TypeTreeNode]
    string_buffer: bytes


class ClassID(Enum):
    UNKNOWN = -1
    OBJECT = 0
    GAME_OBJECT = 1
    TRANSFORM = 4
    MATERIAL = 21
    TEXTURE_2D = 28
    MESH = 43
    SHADER = 48
    TEXT_ASSET = 49
    ANIMATION_CLIP = 74
    AUDIO_SOURCE = 82
    AUDIO_CLIP = 83
    ANIMATOR_CONTROLLER = 91
    ANIMATOR = 95
    MONO_BEHAVIOUR = 114
    MONO_SCRIPT = 115
    FONT = 128
    ASSET_BUNDLE = 142
    PARTICLE_SYSTEM = 198
    PARTICLE_SYSTEM_RENDERER = 199
    SHADER_VARIANT_COLLECTION = 200
    SPRITE_RENDERER = 212
    SPRITE = 213
    CANVAS_RENDERER = 222
    CANVAS = 223
    RECT_TRANSFORM = 224
    CANVAS_GROUP = 225

    @classmethod
    def from_int(cls, id: int) -> 'ClassID':
        try:
            return cls(id)
        except ValueError:
            print('未知的ClassID:', id)
            return ClassID.UNKNOWN


class SerializedType:
    class_id: ClassID
    is_stripped_type: bool
    script_type_index: int
    type_tree: TypeTree
    script_id: bytes
    old_type_hash: bytes
    type_dependencies: list[int]
    class_name: str
    namespace: str
    asm_name: str


class ObjectInfo:
    byte_start: int
    byte_size: int
    type_id: int
    class_id: ClassID
    path_id: int
    serialized_type: SerializedType | None = None
    is_destroyed: int
    stripped: bool


class LocalSerializedObjectIdentifier:
    local_serializerd_file_index: int
    local_identifier_in_file: int


class FileIdentifier:
    guid: bytes
    type: int
    path_name: str


class SerializedFile:
    class FileHeader:
        metadata_size: int
        file_size: int
        version: int
        data_offset: int
        big_endian: bool
        reserved_bytes: bytes

    assets_manager: 'AssetsManager'
    original_path: pathlib.Path
    path: pathlib.Path
    file_header: FileHeader
    file_big_endian: bool
    unity_version: str
    version: list[int]
    target_platform: int
    enable_type_tree: bool
    types: list[SerializedType]
    big_id_enabled: bool
    object_infos: list[ObjectInfo]
    script_types: list[LocalSerializedObjectIdentifier]
    externals: list[FileIdentifier]
    ref_types: list[SerializedType]
    user_information: str
    objects: list['Object']
    object_map: dict[int, 'Object']
    parent: Optional['BundleFile']

    def __init__(self, reader: 'FileReader', assets_manager: 'AssetsManager', parent: Optional['BundleFile'] = None):
        self.assets_manager = assets_manager
        self.reader = reader
        self.path = reader.path
        self.parent = parent
        self.file_header = self.FileHeader()
        self.file_header.metadata_size = reader.u32
        self.file_header.file_size = reader.u32
        self.file_header.version = reader.u32
        self.file_header.data_offset = reader.u32

        # header
        if self.file_header.version >= 9:
            self.file_header.big_endian = reader.boolean
            self.file_header.reserved_bytes = reader.read(3)
            self.file_big_endian = self.file_header.big_endian
        else:
            reader.pos = self.file_header.file_size - self.file_header.metadata_size
            self.file_big_endian = reader.boolean

        if self.file_header.version >= 22:
            self.file_header.metadata_size = reader.u32
            self.file_header.file_size = reader.u64
            self.file_header.data_offset = reader.u64
            reader.skip(8)

        # metadata
        if not self.file_big_endian:
            reader.big_endian = False

        if self.file_header.version >= 7:
            self.unity_version = reader.cstr()
            self.set_version(self.unity_version)

        if self.file_header.version >= 8:
            self.target_platform = reader.i32

        self.enable_type_tree = True
        if self.file_header.version >= 13:
            self.enable_type_tree = reader.boolean

        # types
        types_count = reader.i32
        self.types = []
        for _ in range(types_count):
            self.types.append(self._read_serialized_type(reader, False))

        self.big_id_enabled = False
        if 7 <= self.file_header.version < 14:
            self.big_id_enabled = bool(reader.i32)

        # objects
        object_count = reader.i32
        self.object_infos = []
        for _ in range(object_count):
            obj_info = ObjectInfo()

            if self.big_id_enabled:
                obj_info.path_id = reader.i64
            elif self.file_header.version < 14:
                obj_info.path_id = reader.i32
            else:
                reader.align(4)
                obj_info.path_id = reader.i64

            if self.file_header.version >= 22:
                obj_info.byte_start = reader.i64
            else:
                obj_info.byte_start = reader.u32

            obj_info.byte_start += self.file_header.data_offset
            obj_info.byte_size = reader.u32
            obj_info.type_id = reader.i32

            if self.file_header.version < 16:
                obj_info.class_id = ClassID(reader.u16)
                obj_info.serialized_type = next(
                    filter(lambda x: x and x.class_id.value == obj_info.type_id, self.types)
                )
            else:
                t = self.types[obj_info.type_id]
                obj_info.serialized_type = t
                obj_info.class_id = t.class_id

            if self.file_header.version < 11:
                obj_info.is_destroyed = reader.u16

            if 11 <= self.file_header.version < 17:
                script_type_index = reader.i16
                if obj_info.serialized_type is not None:
                    obj_info.serialized_type.script_type_index = script_type_index

            if self.file_header.version == 15 or self.file_header.version == 16:
                obj_info.stripped = reader.boolean

            self.object_infos.append(obj_info)

        # scripts
        if self.file_header.version >= 11:
            script_count = reader.i32
            self.script_types = []

            for _ in range(script_count):
                script_type = LocalSerializedObjectIdentifier()
                script_type.local_serializerd_file_index = reader.i32

                if self.file_header.version < 14:
                    script_type.local_identifier_in_file = reader.i32
                else:
                    reader.align(4)
                    script_type.local_identifier_in_file = reader.i64

                self.script_types.append(script_type)

        # externals
        external_count = reader.i32
        self.externals = []
        for _ in range(external_count):
            external = FileIdentifier()
            if self.file_header.version >= 6:
                reader.cstr()

            if self.file_header.version >= 5:
                external.guid = reader.read(16)
                external.type = reader.i32

            external.path_name = reader.cstr()
            self.externals.append(external)

        # ref types
        if self.file_header.version >= 20:
            self.ref_types = [self._read_serialized_type(reader, True) for _ in range(reader.i32)]

        if self.file_header.version >= 5:
            self.user_information = reader.cstr()

        self.objects = []
        self.object_map = {}

        self.reader = reader

    def _read_serialized_type(self, reader: BinaryReader, is_ref_type: bool) -> SerializedType:
        t = SerializedType()
        t.class_id = ClassID.from_int(reader.i32)

        version = self.file_header.version
        if version >= 16:
            t.is_stripped_type = reader.boolean

        if version >= 17:
            t.script_type_index = reader.u16

        if version >= 13:
            if is_ref_type and t.script_type_index >= 0:
                t.script_id = reader.read(16)
            elif (version < 16 and t.class_id.value < 0) or (
                version >= 16 and t.class_id == t.class_id == ClassID.MONO_BEHAVIOUR
            ):
                t.script_id = reader.read(16)
            t.old_type_hash = reader.read(16)

        if self.enable_type_tree:
            t.type_tree = TypeTree()
            t.type_tree.nodes = []
            if version >= 12 or version == 10:
                nodes_count = reader.i32
                length = reader.i32

                for _ in range(nodes_count):
                    node = TypeTreeNode()
                    node.version = reader.u16
                    node.level = reader.u8
                    node.type_flags = reader.u8
                    node.type_str_offset = reader.u32
                    node.name_str_offset = reader.u32
                    node.byte_size = reader.i32
                    node.index = reader.i32
                    node.meta_flag = reader.i32

                    if version >= 19:
                        node.ref_type_hash = reader.u64
                    t.type_tree.nodes.append(node)

                t.type_tree.string_buffer = reader.read(length)

                with BinaryReader(t.type_tree.string_buffer) as buf_reader:

                    def read_string(offset: int) -> str:
                        if offset & 0x80000000 == 0:
                            buf_reader.pos = offset
                            return buf_reader.cstr()
                        offset = offset & 0x7FFFFFFF
                        return COMMON_STRINGS.get(offset, str(offset))

                    for node in t.type_tree.nodes:
                        node.type_ = read_string(node.type_str_offset)
                        node.name = read_string(node.name_str_offset)

            else:
                nodes = t.type_tree.nodes

                def read_type_tree(level: int = 0):
                    nd = TypeTreeNode()
                    nodes.append(nd)
                    nd.level = level
                    nd.type_ = reader.cstr()
                    nd.name = reader.cstr()
                    nd.byte_size = reader.i32

                    if version == 2:
                        reader.skip(4)

                    if version == 3:
                        nd.index = reader.i32

                    nd.type_flags = reader.i32
                    nd.version = reader.i32

                    if version != 3:
                        nd.meta_flag = reader.i32

                    for _ in range(reader.i32):
                        read_type_tree(level + 1)

                read_type_tree(0)

            if version >= 21:
                if is_ref_type:
                    t.class_name = reader.cstr()
                    t.namespace = reader.cstr()
                    t.asm_name = reader.cstr()
                else:
                    t.type_dependencies = [reader.i32 for _ in range(reader.u32)]

        return t

    def add_object(self, obj: 'Object'):
        self.objects.append(obj)
        self.object_map[obj.path_id] = obj

    def set_version(self, unity_version: str):
        self.version = []
        for sp in unity_version.split('.'):
            try:
                self.version.append(int(sp))
            except ValueError:
                pass


class ResourceReader:
    need_search: bool
    path: str
    asset_file: SerializedFile
    offset: int
    size: int
    reader: BinaryReader

    def __init__(self, reader: BinaryReader, offset: int, size: int):
        self.reader = reader
        self.offset = offset
        self.size = size

    @classmethod
    def search(cls, path: str, asset_file: SerializedFile, offset: int, size: int) -> 'ResourceReader':
        resource_file_name = pathlib.Path(path).name
        if resource_file_name in asset_file.assets_manager.resource_file_readers:
            return ResourceReader(asset_file.assets_manager.resource_file_readers[resource_file_name], offset, size)
        assets_file_directory = asset_file.path.parent
        resource_file_path = assets_file_directory / resource_file_name
        if not resource_file_path.exists():
            raise RuntimeError(f'{resource_file_path} not exists')
        if resource_file_path.exists():
            raise RuntimeError(f'{resource_file_path} exists')
        raise RuntimeError('unimplemented')

    def get(self) -> bytes:
        self.reader.pos = self.offset
        return self.reader.read(self.size)


class ObjectReader(BinaryReader):
    asset_file: SerializedFile
    path_id: int
    byte_start: int
    byte_size: int
    class_id: ClassID
    serialized_type: SerializedType | None
    version: list[int]
    platform: int
    format_version: int

    def __init__(self, reader: BinaryReader, asset_file: SerializedFile, object_info: ObjectInfo):
        super().__init__(reader._stream)
        self.big_endian = reader.big_endian
        self.asset_file = asset_file
        self.path_id = object_info.path_id
        self.byte_start = object_info.byte_start
        self.byte_size = object_info.byte_size
        self.class_id = object_info.class_id
        self.serialized_type = object_info.serialized_type
        self.platform = asset_file.target_platform
        self.version = asset_file.version
        self.format_version = asset_file.file_header.version


class Object:
    asset_file: SerializedFile
    reader: ObjectReader
    path_id: int
    version: list[int]
    platform: int
    class_id: ClassID
    serialized_type: SerializedType | None
    byte_size: int

    def __init__(self, reader: ObjectReader):
        self.reader = reader
        reader.pos = reader.byte_start
        self.asset_file = reader.asset_file
        self.class_id = reader.class_id
        self.path_id = reader.path_id
        self.version = reader.version
        self.platform = reader.platform
        self.serialized_type = reader.serialized_type
        self.byte_size = reader.byte_size

        if self.platform == -2:
            _object_hide_flags = reader.u32


class EditorExtension(Object):
    def __init__(self, reader: ObjectReader):
        super().__init__(reader)
        if self.platform == -2:
            _prefab_parent_object = PPtr[EditorExtension](reader)
            _prefab_internal = PPtr[Object](reader)


class NamedObject(EditorExtension):
    name: str

    def __init__(self, reader: ObjectReader):
        super().__init__(reader)
        self.name = reader.aligned_string()


T = TypeVar('T')


class PPtr(Generic[T]):
    file_id: int
    path_id: int

    asset_file: SerializedFile
    index: int = -2

    def __init__(self, reader: ObjectReader):
        self.file_id = reader.i32
        self.path_id = reader.i32 if reader.format_version < 14 else reader.i64
        self.asset_file = reader.asset_file


class TextAsset(NamedObject):
    text: str

    def __init__(self, reader: ObjectReader):
        super().__init__(reader)
        self.text = reader.string(reader.i32)


class AssetInfo:
    preload_index: int
    preload_size: int
    asset: PPtr[Object]

    def __init__(self, reader: ObjectReader):
        self.preload_index = reader.i32
        self.preload_size = reader.i32
        self.asset = PPtr[Object](reader)


class AssetBundle(NamedObject):
    preload_table: list[PPtr[Object]]
    container: dict[str, AssetInfo]

    def __init__(self, reader: ObjectReader):
        super().__init__(reader)
        # preload table
        self.preload_table = [PPtr[Object](reader) for _ in range(reader.i32)]

        # container
        self.container = {reader.aligned_string(): AssetInfo(reader) for _ in range(reader.i32)}


class RectF:
    x: float
    y: float
    width: float
    height: float

    def __init__(self, reader: BinaryReader):
        self.x = reader.f32
        self.y = reader.f32
        self.width = reader.f32
        self.height = reader.f32


class Texture(NamedObject):
    def __init__(self, reader: ObjectReader):
        super().__init__(reader)
        version = reader.version
        if version >= [2017, 3]:
            _forced_fallback_format = reader.i32
            _downscale_fallback = reader.boolean
            if version >= [2020, 2]:
                _is_alpha_channel_optional = reader.boolean
            reader.align(4)


class Texture2D(Texture):
    class TextureFormat(Enum):
        Alpha8 = 1
        ARGB4444 = auto()
        RGB24 = auto()
        RGBA32 = auto()
        ARGB32 = auto()
        RGB565 = 7
        R16 = 9
        DXT1 = auto()
        DXT5 = 12
        RGBA4444 = auto()
        BGRA32 = auto()
        RHalf = auto()
        RGHalf = auto()
        RGBAHalf = auto()
        RFloat = auto()
        RGFloat = auto()
        RGBAFloat = auto()
        YUY2 = auto()
        RGB9e5Float = auto()
        BC4 = 26
        BC5 = auto()
        BC6H = 24
        BC7 = auto()
        DXT1Crunched = 28
        DXT5Crunched = auto()
        PVRTC_RGB2 = auto()
        PVRTC_RGBA2 = auto()
        PVRTC_RGB4 = auto()
        PVRTC_RGBA4 = auto()
        ETC_RGB4 = auto()
        ATC_RGB4 = auto()
        ATC_RGBA8 = auto()
        EAC_R = 41
        EAC_R_SIGNED = auto()
        EAC_RG = auto()
        EAC_RG_SIGNED = auto()
        ETC2_RGB = auto()
        ETC2_RGBA1 = auto()
        ETC2_RGBA8 = auto()
        ASTC_RGB_4x4 = auto()
        ASTC_RGB_5x5 = auto()
        ASTC_RGB_6x6 = auto()
        ASTC_RGB_8x8 = auto()
        ASTC_RGB_10x10 = auto()
        ASTC_RGB_12x12 = auto()
        ASTC_RGBA_4x4 = auto()
        ASTC_RGBA_5x5 = auto()
        ASTC_RGBA_6x6 = auto()
        ASTC_RGBA_8x8 = auto()
        ASTC_RGBA_10x10 = auto()
        ASTC_RGBA_12x12 = auto()
        ETC_RGB4_3DS = auto()
        ETC_RGBA8_3DS = auto()
        RG16 = auto()
        R8 = auto()
        ETC_RGB4Crunched = auto()
        ETC2_RGBA8Crunched = auto()
        ASTC_HDR_4x4 = auto()
        ASTC_HDR_5x5 = auto()
        ASTC_HDR_6x6 = auto()
        ASTC_HDR_8x8 = auto()
        ASTC_HDR_10x10 = auto()
        ASTC_HDR_12x12 = auto()
        RG32 = auto()
        RGB48 = auto()
        RGBA64 = auto()

    class StreamingInfo:
        offset: int
        size: int
        path: str

        def __init__(self, reader: ObjectReader):
            version = reader.version
            if version >= [2020]:
                self.offset = reader.i64
            else:
                self.offset = reader.u32
            self.size = reader.u32
            self.path = reader.aligned_string()

    class GLTextureSettings:
        filter_mode: int
        aniso: int
        mip_bias: float
        wrap_mode: int

        def __init__(self, reader: ObjectReader):
            version = reader.version
            self.filter_mode = reader.i32
            self.aniso = reader.i32
            self.mip_bias = reader.f32
            if version >= [2017]:
                self.wrap_mode = reader.i32
                _wrap_v = reader.i32
                _wrap_w = reader.i32
            else:
                self.wrap_mode = reader.i32

    width: int
    height: int
    texture_format: TextureFormat
    mipmap: bool
    mip_count: int
    texture_settings: GLTextureSettings
    image_data: bytes
    stream_data: StreamingInfo | None

    def __init__(self, reader: ObjectReader):
        super().__init__(reader)
        version = reader.version
        self.width = reader.i32
        self.height = reader.i32
        _complete_image_size = reader.i32
        if version >= [2020]:
            _mips_stripped = reader.i32

        self.texture_format = self.TextureFormat(reader.i32)

        if version <= [5, 2]:
            self.mipmap = reader.boolean
        else:
            self.mip_count = reader.i32

        if version >= [2, 6]:
            _is_readable = reader.boolean

        if version >= [2020]:
            _is_pre_processed = reader.boolean

        if version >= [2019, 3]:
            _ignore_master_texture_limit = reader.boolean

        if [3] <= version <= [5, 4]:
            _read_allowed = reader.boolean

        if version >= [2018, 2]:
            _streaming_mipmaps = reader.boolean
        reader.align(4)
        if version >= [2018, 2]:
            _streaming_mipmaps_priority = reader.i32

        _image_count = reader.i32
        _texture_dimension = reader.i32

        self.texture_settings = self.GLTextureSettings(reader)

        if version >= [3]:
            _lightmap_format = reader.i32

        if version >= [3, 5]:
            _colorspace = reader.i32

        if version >= [2020, 2]:
            _platform_blob = reader.read(reader.i32)
            reader.align(4)

        image_data_size = reader.i32
        self.stream_data = None
        if image_data_size == 0 and version >= [5, 3]:
            self.stream_data = self.StreamingInfo(reader)

        if self.stream_data and self.stream_data.path:
            self.image_data = ResourceReader.search(
                self.stream_data.path, self.asset_file, self.stream_data.offset, self.stream_data.size
            ).get()
        else:
            self.image_data = reader.read(image_data_size)

    def get_image(self) -> Image.Image | None:
        match self.texture_format:
            case self.TextureFormat.RGB24:
                return Image.frombytes('RGB', (self.width, self.height), self.image_data).transpose(1)
            case self.TextureFormat.RGBA32:
                return Image.frombytes('RGBA', (self.width, self.height), self.image_data).transpose(1)


class Font(NamedObject):
    font_data: bytes

    def __init__(self, reader: ObjectReader):
        super().__init__(reader)

        if self.version >= [5, 5]:
            _line_spacing = reader.f32
            _default_material = PPtr[Object](reader)
            _font_size = reader.f32
            _texture = PPtr[Texture](reader)
            _ascii_start_offset = reader.i32
            _tracking = reader.f32
            _character_spacing = reader.i32
            _character_padding = reader.i32
            _convert_case = reader.i32
            _character_rects_size = reader.i32

            reader.skip(44 * _character_rects_size)
            _kerning_values_size = reader.i32
            reader.skip(8 * _kerning_values_size)
            _pixel_scale = reader.f32
            _font_data_size = reader.i32

            if _font_data_size > 0:
                self.font_data = reader.read(_font_data_size)
        else:
            _ascii_start_offset = reader.i32

            if self.version <= [3]:
                _font_count_x = reader.i32
                _font_count_y = reader.i32

            _kerning = reader.f32
            _line_spacing = reader.f32

            if self.version <= [3]:
                for _ in range(reader.i32):
                    _first = reader.i32
                    _second = reader.f32
            else:
                _character_spacing = reader.i32
                _character_padding = reader.i32

            _convert_case = reader.i32
            _default_material = PPtr[Object](reader)

            for _ in range(reader.i32):
                _index = reader.i32

                _uvx = reader.f32
                _uvy = reader.f32
                _uvwidth = reader.f32
                _uvheight = reader.f32

                _vertx = reader.f32
                _verty = reader.f32
                _vertwidth = reader.f32
                _vertheight = reader.f32
                _width = reader.f32

                if self.version >= [4]:
                    _flipped = reader.boolean
                    reader.align(4)

            _texture = PPtr[Texture](reader)

            for _ in range(reader.i32):
                _pair_first = reader.u16
                _pair_second = reader.u16
                _second = reader.f32

            if self.version <= [3]:
                _grid_font = reader.boolean
                reader.align(4)
            else:
                _pixel_scale = reader.f32

            _font_data_size = reader.i32
            if _font_data_size > 0:
                self.font_data = reader.read(_font_data_size)


class Vector2:
    x: float
    y: float

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    @classmethod
    def read(cls, reader: BinaryReader) -> 'Vector2':
        return cls(reader.f32, reader.f32)


class Vector4:
    x: float
    y: float
    z: float
    w: float

    def __init__(self, x: float, y: float, z: float, w: float):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

    @classmethod
    def read(cls, reader: BinaryReader) -> 'Vector4':
        return cls(reader.f32, reader.f32, reader.f32, reader.f32)


class StreamFile:
    path: str
    stream: bytes


class FileReader(BinaryReader):
    GZIP_MAGIC = b'\x1f\x8b'
    BROTLI_MAGIC = b'brotli'
    ZIP_MAGIC = b'PK\x03\x04'
    ZIP_SPANNED_MAGIC = b'PK\x07\x08'

    class FileType(Enum):
        BundleFile = 0
        WebFile = 1
        GZipFile = 2
        BrotliFile = 3
        AssetsFile = 4
        ZipFile = 5
        ResourceFile = 6

    path: pathlib.Path
    file_type: FileType

    def __init__(self, stream: IO[bytes] | bytes | bytearray, path: str | pathlib.Path):
        super().__init__(stream)
        self.path = pathlib.Path(path)
        self.file_type = self.check_file_type()

    def check_file_type(self) -> FileType:
        signature = self.bcstrl(20)
        self.pos = 0
        match signature:
            case b'UnityWeb' | b'UnityRaw' | b'UnityArchive' | b'UnityFS':
                return self.FileType.BundleFile
            case b'UnityWebData1.0':
                return self.FileType.WebFile
            case _:
                magic = self.read(2)
                if magic == self.GZIP_MAGIC:
                    return self.FileType.GZipFile
                self.pos = 0x20
                magic = self.read(6)
                if magic == self.BROTLI_MAGIC:
                    return self.FileType.BrotliFile
                self.pos = 0
                if self.is_serialized_file():
                    return self.FileType.AssetsFile
                self.pos = 0
                magic = self.read(4)
                if magic == self.ZIP_MAGIC or magic == self.ZIP_SPANNED_MAGIC:
                    return self.FileType.ZipFile
                return self.FileType.ResourceFile

    def is_serialized_file(self) -> bool:
        length = len(self)

        if length < 20:
            return False

        self.skip(4)
        file_size = self.u32
        version = self.u32
        data_offset = self.u32

        self.skip(4)

        if version >= 22:
            if file_size < 48:
                return False
            self.skip(4)
            file_size = self.u64
            data_offset = self.u64

        if file_size != length or data_offset > file_size:
            return False

        return True


class BundleFile:
    class Header:
        signature: str
        version: int
        unity_version: str
        unity_revision: str
        size: int
        compressed_blocks_info_size: int
        uncompressed_blocks_info_size: int
        flags: int

    class StorageBlock:
        compressed_size: int
        uncompressed_size: int
        flags: int

    class Node:
        offset: int
        size: int
        flags: int
        path: str

    header: Header
    blocks_info: list[StorageBlock]
    directory_info: list[Node]
    files: list[StreamFile]
    reader: FileReader

    def __init__(self, reader: FileReader):
        self.reader = reader
        self.header = self.Header()
        self.header.signature = reader.cstr()
        self.header.version = reader.u32
        self.header.unity_version = reader.cstr()
        self.header.unity_revision = reader.cstr()

        signature = self.header.signature

        if signature == 'UnityArchive':
            raise RuntimeError('not supported')
        elif signature in ['UnityWeb', 'UnityRaw'] and self.header.version != 6:
            raise RuntimeError('not supported')
        elif signature == 'UnityFS' or (signature in ['UnityWeb', 'UnityRaw'] and self.header.version == 6):
            self.header.size = reader.i64
            self.header.compressed_blocks_info_size = reader.u32
            self.header.uncompressed_blocks_info_size = reader.u32
            self.header.flags = reader.u32
            if signature != 'UnityFS':
                reader.skip(1)

            if self.header.version >= 7:
                reader.align(16)

            if self.header.flags & 0x80:
                position = reader.pos
                reader.pos = -self.header.compressed_blocks_info_size
                block_info_bytes = reader.read(self.header.compressed_blocks_info_size)
                reader.pos = position
            else:
                block_info_bytes = reader.read(self.header.compressed_blocks_info_size)

            uncompressed_size = self.header.uncompressed_blocks_info_size

            match self.header.flags & 0x3F:
                case 1:  # LZMA
                    raise RuntimeError('sorry, dont support LZMA compress')
                case 2 | 3:  # LZ4 | LZ4HC
                    uncompressed_data = lz4.block.decompress(block_info_bytes, uncompressed_size=uncompressed_size)
                    if len(uncompressed_data) != uncompressed_size:
                        raise RuntimeError('lz4 decompression error: size not correct')
                case _:
                    uncompressed_data = bytes(block_info_bytes)

            with BinaryReader(uncompressed_data) as uc_reader:
                _uncompressed_data_hash = uc_reader.read(16)
                self.blocks_info = []
                for _ in range(uc_reader.i32):
                    block = self.StorageBlock()
                    block.uncompressed_size = uc_reader.u32
                    block.compressed_size = uc_reader.u32
                    block.flags = uc_reader.u16
                    self.blocks_info.append(block)

                self.directory_info = []
                for _ in range(uc_reader.i32):
                    node = self.Node()
                    node.offset = uc_reader.i64
                    node.size = uc_reader.i64
                    node.flags = uc_reader.u32
                    node.path = uc_reader.cstr()
                    self.directory_info.append(node)

            block_stream = bytearray()

            for block in self.blocks_info:
                match block.flags & 0x3F:
                    case 1:  # LZMA
                        raise RuntimeError('LZMA unsupported')
                    case 2 | 3:  # LZ4 | LZ4HC
                        block_stream.extend(
                            lz4.block.decompress(
                                reader.read(block.compressed_size), uncompressed_size=block.uncompressed_size
                            )
                        )
                    case _:  # raw
                        block_stream.extend(reader.read(block.compressed_size))

            with BinaryReader(block_stream) as s_reader:
                self.files = []
                for node in self.directory_info:
                    file = StreamFile()
                    file.path = node.path
                    s_reader.pos = node.offset
                    file.stream = s_reader.read(node.size)
                    self.files.append(file)


class AssetsManager:
    asset_files: list[SerializedFile]
    asset_file_hashes: list[str]
    resource_file_readers: dict[str, BinaryReader]
    asset_file_index_cache: dict[str, int]

    def __init__(self):
        self.asset_files = []
        self.asset_file_hashes = []
        self.resource_file_readers = {}
        self.asset_file_index_cache = {}

    def load_file(self, file: IO[bytes] | FileReader):
        if not isinstance(file, FileReader):
            file = FileReader(file, file.name)
        if file.file_type == FileReader.FileType.BundleFile:
            self.load_bundle(file)

    def load_bundle(self, reader: FileReader, original_path: pathlib.Path | None = None):
        bundle_file = BundleFile(reader)
        for file in bundle_file.files:
            subreader = FileReader(file.stream, reader.path.parent / pathlib.Path(file.path).name)
            subreader.pos = 0
            if subreader.file_type == FileReader.FileType.AssetsFile:
                self.load_assets(
                    subreader, original_path or reader.path, bundle_file.header.unity_revision, bundle_file
                )
            else:
                self.resource_file_readers[os.path.basename(file.path)] = subreader

    def load_assets(self, reader: FileReader, original_path: pathlib.Path, unity_version: str, bundle_file: BundleFile):
        if reader.path.name not in self.asset_file_hashes:
            asset_file = SerializedFile(reader, self, bundle_file)
            asset_file.original_path = original_path
            if not unity_version and asset_file.file_header.version < 7:
                asset_file.set_version(unity_version)
            self.asset_files.append(asset_file)
            self.asset_file_hashes.append(asset_file.path.name)

    def read_assets(self, console: Console | None = None):
        files = self.asset_files
        if console:
            from rich.progress import track

            files = track(files, description='正在解析文件...', console=console)

        for asset_file in files:
            for object_info in asset_file.object_infos:
                with ObjectReader(asset_file.reader, asset_file, object_info) as obj_reader:
                    obj = None
                    match obj_reader.class_id:
                        case ClassID.ASSET_BUNDLE:
                            obj = AssetBundle(obj_reader)
                        case ClassID.TEXT_ASSET:
                            obj = TextAsset(obj_reader)
                        case ClassID.TEXTURE_2D:
                            obj = Texture2D(obj_reader)
                        case ClassID.FONT:
                            obj = Font(obj_reader)
                        case _:
                            obj = Object(obj_reader)
                    if obj:
                        asset_file.add_object(obj)


if __name__ == '__main__':
    pass
