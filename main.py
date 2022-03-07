import sys
import os
import zipfile
import json
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QObject, Slot, Property, QAbstractListModel, QByteArray
from PySide6.QtQml import QmlElement, qmlRegisterSingletonType
from PySide6.QtQuick import QQuickView
from PySide6.QtWidgets import QFileDialog, QWidget, QApplication

from catalog import Catalog
from extract import AssetsManager, Texture2D, TextAsset, Font

import time

QML_IMPORT_NAME = 'phisap.extractor'
QML_IMPORT_MAJOR_VERSION = 1


@QmlElement
class ExtractWorker(QThread):
    filepath: str

    update_progress = Signal(float)
    done_extract = Signal()

    def __init__(self, filepath: str = ''):
        super().__init__()
        self.filepath = filepath

    @Property(str)
    def apkPath(self):
        return self.filepath

    @apkPath.setter
    def apkPath(self, path):
        self.filepath = path

    def run(self):
        self.update_progress.emit(-1)
        apk_file = zipfile.ZipFile(self.filepath)
        catalog = Catalog(apk_file.open('assets/aa/catalog.json'))
        manager = AssetsManager()
        for file in apk_file.namelist():
            if not file.startswith('assets/aa/Android'):
                continue
            with apk_file.open(file) as f:
                manager.load_file(f)
        manager.read_assets()
        objects = []
        for file in manager.asset_files:
            filepath = file.parent.reader.path

            if filepath.name not in catalog.fname_map:
                continue
            asset_name = catalog.fname_map[filepath.name]
            if not asset_name.startswith('Assets/'):
                for obj in file.objects:
                    if isinstance(obj, Font):
                        objects.append(('Assets/' + obj.name + '.ttf', obj))
                continue
            basedir = os.path.dirname(asset_name)
            if basedir and not os.path.exists(basedir):
                os.makedirs(basedir)

            for obj in file.objects:
                if isinstance(obj, (TextAsset, Texture2D)):
                    objects.append((asset_name, obj))
        objects_count = len(objects)
        for i, (asset_name, obj) in enumerate(objects):
            if isinstance(obj, TextAsset):
                with open(asset_name, 'w') as out:
                    out.write(obj.text)
            elif isinstance(obj, Texture2D):
                obj.get_image().save(asset_name)
            elif isinstance(obj, Font):
                with open(asset_name, 'wb') as out:
                    out.write(obj.font_data)
            self.update_progress.emit(i / objects_count)
        self.done_extract.emit()


QML_IMPORT_NAME = 'phisap.utils'
QML_IMPORT_MAJOR_VERSION = 1


@QmlElement
class Utils(QObject):
    folder: Path

    def __init__(self):
        super().__init__()
        self.folder = Path(__file__).resolve().parent

    @Slot(result=str)
    def ask_apk_path(self):
        filepath, _ = QFileDialog.getOpenFileName(QWidget(), '选取安装包', '.', 'Phigros安装包 (*.apk)')
        return filepath

    @Slot(result=bool)
    def database_available(self):
        database = self.folder / 'Assets' / 'Tracks'
        if database.exists():
            return True
        return False


class ChapterModel(QAbstractListModel):
    ChapterIDRole = Qt.UserRole + 1
    ChapterNameRole = Qt.UserRole + 2
    ChapterShortNameRole = Qt.UserRole + 3
    ChapterImagePath = Qt.UserRole + 4
    ChapterBlurPath = Qt.UserRole + 5

    def __init__(self, parent=None):
        QAbstractListModel.__init__(self, parent)
        self._data = []

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.ChapterIDRole: QByteArray(b'chapterID'),
            self.ChapterNameRole: QByteArray(b'chapterName'),
            self.ChapterShortNameRole: QByteArray(b'chapterShortName'),
            self.ChapterImagePath: QByteArray(b'chapterImagePath'),
            self.ChapterBlurPath: QByteArray(b'chapterBlurPath')
        }

    def rowCount(self, index):
        return len(self._data)

    def data(self, index, role):
        d = self._data[index.row()]

        if role == self.ChapterIDRole:
            return d['id']
        elif role == self.ChapterNameRole:
            return d['name']
        elif role == self.ChapterShortNameRole:
            return d['short']
        elif role == self.ChapterImagePath:
            return d['path']
        elif role == self.ChapterBlurPath:
            return d['blur_path']

        return None

    def add(self, item):
        self._data.append(item)

    @Slot()
    def load_chapters(self):
        chapters = json.load(open('metadata.json'))['chapters']
        chapters = [{
            'id': 'AllSong',
            'name': '全部歌曲',
            'short': 'Phigros'
        }] + chapters
        covers = Path('Assets/Tracks/#ChapterCover')
        for chapter in chapters:
            chapter_id = chapter['id']
            if (path := covers / (chapter_id + '.png')).exists() and (
                    blur_path := covers / (chapter_id + 'Blur.png')).exists():
                self.add({
                    'id': chapter_id,
                    'name': chapter['name'],
                    'short': chapter['short'],
                    'path': path.as_posix().replace('#', '%23'),
                    'blur_path': blur_path.as_posix().replace('#', '%23')
                })


def chapters_model_callback(_engine):
    my_model = ChapterModel()
    my_model.load_chapters()
    return my_model


QML_IMPORT_NAME = 'phisap.models'
QML_IMPORT_MAJOR_VERSION = 1


@QmlElement
class SongModel(QAbstractListModel):
    SongIDRole = Qt.UserRole + 1
    TitlePartRole = Qt.UserRole + 2
    AuthorPartRole = Qt.UserRole + 3
    SongImagePath = Qt.UserRole + 4
    SongBlurPath = Qt.UserRole + 5

    def __init__(self, parent=None):
        QAbstractListModel.__init__(self, parent)
        self._data = []
        self._chapterID = 'Phigros'

    @Property(str)
    def chapterID(self):
        return self._chapterID

    @chapterID.setter
    def chapterID(self, new_id):
        self._chapterID = new_id

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.SongIDRole: QByteArray(b'songID'),
            self.TitlePartRole: QByteArray(b'title'),
            self.AuthorPartRole: QByteArray(b'author'),
            self.SongImagePath: QByteArray(b'songImagePath'),
            self.SongBlurPath: QByteArray(b'songBlurPath')
        }

    def rowCount(self, index):
        return len(self._data)

    def data(self, index, role):
        d = self._data[index.row()]

        if role == self.SongIDRole:
            return d['id']
        elif role == self.TitlePartRole:
            return d['title']
        elif role == self.AuthorPartRole:
            return d['author']
        elif role == self.SongImagePath:
            return d['path']
        elif role == self.SongBlurPath:
            return d['path_blur']

        return None

    def add(self, item):
        self._data.append(item)

    @Slot()
    def load_songs(self):
        chapters = json.load(open('metadata.json'))['chapters']
        paths = Path('Assets/Tracks')
        if self._chapterID == 'Phigros':
            for chapter in chapters:
                for song in chapter['songs']:
                    if (path := paths / song).exists():
                        title, author, _ = song.split('.')
                        self.add({
                            'id': song,
                            'title': title,
                            'author': author,
                            'path': (path / 'Illustration.png').as_posix(),
                            'path_blur': (path / 'IllustrationBlur.png').as_posix()
                        })
        else:
            songs = chapters[self._chapterID]['songs']
            for song in songs:
                if (path := paths / song).exists():
                    title, author, _ = song.split('.')
                    self.add({
                        'id': song,
                        'title': title,
                        'author': author,
                        'path': (path / 'Illustration.png').as_posix(),
                        'path_blur': (path / 'IllustrationBlur.png').as_posix()
                    })


if __name__ == '__main__':
    app = QApplication(sys.argv)
    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    qmlRegisterSingletonType(ChapterModel, 'ChapterModel', 1, 0, 'ChaptersData', chapters_model_callback)
    view.setSource('main.qml')
    if view.status() == QQuickView.Error:
        sys.exit(-1)
    view.show()
    sys.exit(app.exec())
