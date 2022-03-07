import zipfile
import os
from extract import AssetsManager, Texture2D, TextAsset
from catalog import Catalog

if __name__ == '__main__':
    # apk_path = input('安装包路径: ')
    apk_path = '/home/chino/base.apk'
    apk_file = zipfile.ZipFile(apk_path)
    catalog = Catalog(apk_file.open('assets/aa/catalog.json'))
    manager = AssetsManager()
    for file in apk_file.namelist():
        if not file.startswith('assets/aa/Android'):
            continue
        with apk_file.open(file) as f:
            manager.load_file(f)
    manager.read_assets()
    for file in manager.asset_files:
        filepath = file.parent.reader.path
        if filepath.name not in catalog.fname_map:
            continue
        asset_name = catalog.fname_map[filepath.name]
        if not asset_name.startswith('Assets/'):
            continue
        basedir = os.path.dirname(asset_name)
        if basedir and not os.path.exists(basedir):
            os.makedirs(basedir)

        for obj in file.objects:
            if isinstance(obj, TextAsset):
                with open(asset_name, 'w') as out:
                    out.write(obj.text)
            elif isinstance(obj, Texture2D):
                obj.get_image().save(asset_name)
