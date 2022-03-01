from json import load, loads
from io import BytesIO
from base64 import b64decode
from typing import IO
from binary_reader import BinaryReader


class Catalog:
    buckets: list[dict]
    keys: list
    entries: list[dict]
    fname_map: dict[str, str]

    def __init__(self, file: IO):
        data = load(file)

        self.buckets = []
        bds = data['m_BucketDataString']
        reader = BinaryReader(BytesIO(b64decode(bds)), False)
        bucket_count = reader.u32
        for _ in range(bucket_count):
            self.buckets.append({
                'offset': reader.i32,
                'entries': [reader.i32 for __ in range(reader.i32)]
            })

        self.keys = []
        kds = data['m_KeyDataString']
        reader = BinaryReader(BytesIO(b64decode(kds)), False)
        key_count = reader.u32
        for _ in range(key_count):
            self.keys.append(self.read_object(reader))

        eds = BinaryReader(BytesIO(b64decode(data['m_EntryDataString'])), False)
        xds = BinaryReader(BytesIO(b64decode(data['m_ExtraDataString'])), False)
        entry_count = eds.u32
        self.entries = []
        iids = data['m_InternalIds']
        pids = data['m_ProviderIds']
        rtps = data['m_resourceTypes']
        for _ in range(entry_count):
            internal_id = eds.i32
            provider_index = eds.i32
            dependency_key_index = eds.i32
            dep_hash = eds.i32
            data_index = eds.i32
            primary_key = eds.i32
            resource_type = eds.i32
            obj = None
            if data_index >= 0:
                xds.pos = data_index
                obj = self.read_object(xds)
            self.entries.append({
                'internalId': iids[internal_id],
                'provider': pids[provider_index],
                'dependencyKey': None if dependency_key_index < 0 else self.keys[dependency_key_index],
                'depHash': dep_hash,
                'primaryKey': self.keys[primary_key],
                'resourceType': rtps[resource_type],
                'data': obj,
                'keys': []
            })

        for b, k in zip(self.buckets, self.keys):
            for e in b['entries']:
                self.entries[e]['keys'].append(k)

        self.fname_map = {}
        for e in self.entries:
            if isinstance(e['primaryKey'], str) and isinstance(e['dependencyKey'], str):
                self.fname_map[e['dependencyKey']] = e['primaryKey']

    @classmethod
    def read_object(cls, reader: BinaryReader):
        obj_type = reader.u8
        if obj_type == 0:  # ascii string
            return reader.str(reader.u32)
        elif obj_type == 1:  # unicode(16) string
            return reader.str(reader.u32, 'utf-16')
        elif obj_type == 2:  # u16
            return reader.u16
        elif obj_type == 3:  # u32
            return reader.u32
        elif obj_type == 4:  # i32
            return reader.i32
        elif obj_type == 7:  # json object
            return {
                'assembly_name': reader.str(reader.u8),
                'class_name': reader.str(reader.u8),
                'json': loads(reader.str(reader.i32, 'utf-16'))
            }
        else:
            raise RuntimeError(f'type {obj_type} not supported now.')


__all__ = ['Catalog']
