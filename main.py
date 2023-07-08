import os
import time
import json
import typing
import zipfile
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QLayout,
    QPushButton,
    QTabWidget,
    QLineEdit,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QSpinBox,
    QFileDialog,
    QProgressDialog,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject

from rich.console import Console

from control import DeviceController
from catalog import Catalog
from extract import AssetsManager, TextAsset, ObjectReader, ClassID
from algo.algo_base import ScreenUtil, dump_to_json, load_from_json, WindowGeometry, remap_events, TouchEvent
from basis import Chart
from cache_manager import CacheManager
from control import DeviceController

from pgr import PgrChart
from pec import PecChart
from rpe import RpeChart

PHISAP_VERSION = '0.6'


class ExtractPackageWorker(QThread):
    processUpdate: pyqtSignal
    packagePath: str

    def run(self) -> None:
        package = zipfile.ZipFile(self.packagePath)
        try:
            catalog = Catalog(package.open('assets/aa/catalog.json'))
        except KeyError:
            # TODO: alert
            print('???')
            return

        manager = AssetsManager()
        files = package.namelist()
        dialog = QProgressDialog(self.tr('Loading...'), self.tr('Cancel'), 0, len(files))
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        for index, file in enumerate(files):
            dialog.setValue(index)
            if dialog.wasCanceled():
                return
            if not file.startswith('assets/aa/Android'):
                continue
            with package.open(file) as f:
                manager.load_file(f)
        dialog.setValue(len(files))

        files = manager.asset_files
        dialog = QProgressDialog(self.tr('Processing...'), self.tr('Cancel'), 0, len(files))
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        for index, file in enumerate(files):
            dialog.setValue(index)
            if dialog.wasCanceled():
                return
            for object_info in file.object_infos:
                with ObjectReader(file.reader, file, object_info) as obj_reader:
                    if obj_reader.class_id == ClassID.TEXT_ASSET:
                        file.add_object(TextAsset(obj_reader))
        dialog.setValue(len(files))

        dialog = QProgressDialog(self.tr('Extracting...'), self.tr('Cancel'), 0, len(manager.asset_files))
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        for index, file in enumerate(manager.asset_files):
            dialog.setValue(index)
            if dialog.wasCanceled():
                return
            assert file.parent
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
        dialog.setValue(len(manager.asset_files))

    def __init__(self, packagePath: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.packagePath = packagePath
        self.processUpdate = pyqtSignal(int)


class AutoplayWorker(QThread):
    controller: DeviceController
    ansIter: typing.Iterator[tuple[int, list[TouchEvent]]]
    startTime: float
    running: bool
    delayMs: int
    defaultOffset: int

    def __init__(
        self, ansIter: typing.Iterator[tuple[int, list[TouchEvent]]], defaultOffset: int, parent: 'MainWindow'
    ) -> None:
        super().__init__(parent)
        self.ansIter = ansIter
        self.delayMs = 0
        self.defaultOffset = defaultOffset

        assert parent.controller
        self.controller = parent.controller

    def run(self) -> None:
        self.running = True
        timestamp, events = next(self.ansIter)
        self.startTime = round(time.time() * 1000) + self.defaultOffset
        try:
            while self.running:
                now = round(time.time() * 1000) - self.startTime + self.delayMs
                if now >= timestamp:
                    for event in events:
                        self.controller.touch(*event.pos, event.action, event.pointer)
                    timestamp, events = next(self.ansIter)
        except StopIteration:
            pass
        finally:
            pass

    def onDelayChanged(self, delay: int) -> None:
        self.delayMs = delay

    def stop(self) -> None:
        self.running = False


class MainWindow(QWidget):
    console: Console
    extractedCharts: Path
    cacheManager: CacheManager

    controller: DeviceController | None
    running: bool
    autoplayWorker: AutoplayWorker | None

    mainLayout: QLayout
    deviceSerialSelector: QComboBox
    refreshDeviceButton: QPushButton
    chartSelectTabs: QTabWidget
    songIdSelector: QComboBox
    extractButton: QPushButton
    difficultySelector: QComboBox
    customChartPath: QLineEdit
    customSelectButton: QPushButton
    algorithmSelector: QButtonGroup
    preferCache: QCheckBox
    mainModeSelectTabs: QTabWidget
    syncModeSelector: QButtonGroup
    aspectRatioSelector: QButtonGroup
    delayLabel: QLabel
    delayInput: QSpinBox
    autoplayView: QWidget
    goButton: QPushButton
    saveResult: QCheckBox
    testButton: QPushButton
    lastDelayValue: int

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.console = Console()
        self.extractedCharts = Path('./Assets/Tracks')
        self.cacheManager = CacheManager()
        self.autoplayWorker = None
        self.controller = None

        self.setMinimumWidth(300)

        self.setWindowTitle(f'phisap v{PHISAP_VERSION}')
        self.mainLayout = QVBoxLayout()

        self.deviceSerialSelector = QComboBox()
        self.deviceSerialSelector.currentTextChanged.connect(self.onSelectedDeviceChanged)
        self.refreshDeviceButton = QPushButton(text=self.tr('Refresh'))
        self.refreshDeviceButton.clicked.connect(self.refreshDevices)

        deviceSelection = QHBoxLayout()
        self.mainLayout.addLayout(deviceSelection)
        deviceSelection.addWidget(QLabel(text=self.tr('Device serial:')))
        deviceSelection.addWidget(self.deviceSerialSelector)
        deviceSelection.addWidget(self.refreshDeviceButton)

        self.chartSelectTabs = QTabWidget()
        self.mainLayout.addWidget(self.chartSelectTabs)

        selectExtractedView = QWidget()
        selectExtractedViewLayout = QVBoxLayout()
        selectExtractedView.setLayout(selectExtractedViewLayout)
        self.songIdSelector = QComboBox()
        self.extractButton = QPushButton(text=self.tr('Extract'))
        self.extractButton.clicked.connect(self.extractPackage)
        line1 = QHBoxLayout()
        selectExtractedViewLayout.addLayout(line1)
        line1.addWidget(QLabel(text=self.tr('Song:')))
        line1.addWidget(self.songIdSelector)
        line1.addWidget(self.extractButton)
        line2 = QHBoxLayout()
        selectExtractedViewLayout.addLayout(line2)
        self.difficultySelector = QComboBox()
        line2.addWidget(QLabel(text=self.tr('Difficulty:')))
        line2.addWidget(self.difficultySelector)
        self.songIdSelector.setDisabled(True)
        self.songIdSelector.currentTextChanged.connect(self.onSongIdChanged)
        self.difficultySelector.setDisabled(True)

        selectCustomView = QWidget()
        selectCustomViewLayout = QHBoxLayout()
        selectCustomView.setLayout(selectCustomViewLayout)
        selectCustomViewLayout.addWidget(QLabel(text=self.tr('Path:')))
        self.customChartPath = QLineEdit()
        self.customSelectButton = QPushButton(self.tr('Choose'))
        self.customSelectButton.clicked.connect(self.askCustomChart)
        selectCustomViewLayout.addWidget(self.customChartPath)
        selectCustomViewLayout.addWidget(self.customSelectButton)

        self.chartSelectTabs.addTab(selectExtractedView, self.tr('Choose Extracted'))
        self.chartSelectTabs.addTab(selectCustomView, self.tr('Load Custom'))

        self.algorithmSelector = QButtonGroup()
        algo1Radio = QRadioButton(text=self.tr('Conservative'))
        algo1Radio.setChecked(True)
        algo2Radio = QRadioButton(text=self.tr('Radical'))
        algorithmSelectionLayout = QHBoxLayout()
        algorithmSelectionLayout.addWidget(QLabel(text=self.tr('Algorithm:')))
        algorithmSelectionLayout.addWidget(algo1Radio)
        algorithmSelectionLayout.addWidget(algo2Radio)
        self.algorithmSelector.addButton(algo1Radio, id=0)
        self.algorithmSelector.addButton(algo2Radio, id=1)
        self.mainLayout.addLayout(algorithmSelectionLayout)

        self.mainModeSelectTabs = QTabWidget()
        self.mainLayout.addWidget(self.mainModeSelectTabs)
        self.autoplayView = QWidget()
        autoplayViewLayout = QVBoxLayout()
        self.autoplayView.setLayout(autoplayViewLayout)
        line0 = QHBoxLayout()
        autoplayViewLayout.addLayout(line0)
        self.preferCache = QCheckBox(text=self.tr('Prefer to use the cache if it exists'))
        self.preferCache.setChecked(True)
        line0.addWidget(self.preferCache)
        line1 = QHBoxLayout()
        autoplayViewLayout.addLayout(line1)
        line1.addWidget(QLabel(text=self.tr('Sync mode:')))
        self.syncModeSelector = QButtonGroup()
        syncMode1 = QRadioButton(text=self.tr('Manual'))
        syncMode1.setChecked(True)
        syncMode2 = QRadioButton(text=self.tr('Delay'))
        line1.addWidget(syncMode1)
        line1.addWidget(syncMode2)
        self.syncModeSelector.addButton(syncMode1, id=0)
        self.syncModeSelector.addButton(syncMode2, id=1)
        self.syncModeSelector.idClicked.connect(self.onSyncModeChanged)
        self.mainModeSelectTabs.addTab(self.autoplayView, self.tr('Autoplay'))
        line2 = QHBoxLayout()
        self.delayLabel = QLabel(text=self.tr('Delay:'))
        line2.addWidget(self.delayLabel)
        self.delayInput = QSpinBox()
        self.delayInput.setRange(-1145141919, 1145141919)
        self.delayInput.setDisabled(True)
        line2.addWidget(self.delayInput)
        line2.addWidget(QLabel(text=self.tr('ms')))
        autoplayViewLayout.addLayout(line2)
        line3 = QHBoxLayout()
        line3.addWidget(QLabel(text=self.tr('Aspect ratio:')))
        r16x9 = QRadioButton(text='16:9')
        r16x9.setChecked(True)
        r4x3 = QRadioButton(text='4:3')
        line3.addWidget(r16x9)
        line3.addWidget(r4x3)
        self.aspectRatioSelector = QButtonGroup()
        self.aspectRatioSelector.addButton(r16x9, id=0)
        self.aspectRatioSelector.addButton(r4x3, id=1)
        autoplayViewLayout.addLayout(line3)
        self.goButton = QPushButton(text=self.tr('Prepare'))
        self.goButton.clicked.connect(self.autoplay)
        autoplayViewLayout.addWidget(self.goButton)
        testAlgorithmView = QWidget()
        testAlgorithmViewLayout = QVBoxLayout()
        testAlgorithmView.setLayout(testAlgorithmViewLayout)
        self.saveResult = QCheckBox(text=self.tr('Save generated result'))
        testAlgorithmViewLayout.addWidget(self.saveResult)
        self.testButton = QPushButton(text=self.tr('Execute'))
        self.testButton.clicked.connect(self.process)
        testAlgorithmViewLayout.addWidget(self.testButton)
        self.mainModeSelectTabs.addTab(testAlgorithmView, self.tr('Test algorithm'))
        self.setLayout(self.mainLayout)

        self.loadSongs()
        self.refreshDevices()

    def askCustomChart(self) -> None:
        filepath, sel = QFileDialog.getOpenFileName(
            self, self.tr('Choose custom chart file'), '.', self.tr('JSON Charts (*.json);;PEC Charts (*.pec)')
        )
        if not sel:
            return
        self.customChartPath.setText(filepath)

    def extractPackage(self) -> None:
        filepath, sel = QFileDialog.getOpenFileName(
            self, self.tr('Choose package file'), '.', self.tr('Android Package (*.apk);;Opaque Binary Blob (*.obb)')
        )
        if not sel:
            return
        self.extractButton.setDisabled(True)
        worker = ExtractPackageWorker(filepath, self)
        worker.finished.connect(self.onExtractFinished)
        worker.start()

    def onExtractFinished(self):
        self.extractButton.setDisabled(False)
        box = QMessageBox()
        box.setText(self.tr('Extract finished'))
        box.exec()

    def loadSongs(self) -> None:
        try:
            for folderPath in sorted(self.extractedCharts.iterdir()):
                folder = folderPath.name
                if folder.startswith('#'):
                    continue
                if '.' in folder:
                    title, artist, version = folder.split('.')
                    version = '' if version == '0' else f' (ver.{version})'
                    self.songIdSelector.addItem(f'{title} - {artist}{version}', folder)
                else:
                    self.songIdSelector.addItem(folder, folder)
            if self.songIdSelector.count() == 0:
                raise RuntimeError(self.tr('no charts found'))
            self.songIdSelector.setDisabled(False)
        except Exception as e:
            print(e.with_traceback(None))

    def onSongIdChanged(self, _: str) -> None:
        # update difficultySelector
        songIdDir = Path(self.extractedCharts / self.songIdSelector.currentData())
        self.difficultySelector.clear()
        for file in songIdDir.glob('Chart_*.json'):
            name = file.name
            self.difficultySelector.addItem(name[6:-5], file.name)
        if not self.difficultySelector.isEnabled():
            self.difficultySelector.setDisabled(False)

    def onSyncModeChanged(self, buttonId: int) -> None:
        if buttonId == 0:
            # manual
            self.delayInput.setDisabled(True)
            self.goButton.setText(self.tr('Prepare'))
        else:
            self.delayInput.setDisabled(False)
            self.goButton.setText(self.tr('Go!'))

    def getSelectedPath(self) -> tuple[int, Path]:
        selectedIndex = self.chartSelectTabs.currentIndex()
        if selectedIndex == 0:
            return (
                selectedIndex,
                self.extractedCharts / self.songIdSelector.currentData() / self.difficultySelector.currentData(),
            )
        else:
            return selectedIndex, Path(self.customChartPath.text())

    def loadChart(self) -> tuple[str, Chart]:
        selection, chartPath = self.getSelectedPath()
        content = chartPath.open().read()
        chart: Chart
        if selection == 0:
            chart = PgrChart(json.loads(content))
        else:
            try:
                if chartPath.name.endswith('.pec'):
                    raise json.decoder.JSONDecodeError('Not a json file', '<>', 0)
                j = json.loads(content)
                chart = RpeChart(j) if 'META' in j else PgrChart(j)
            except json.decoder.JSONDecodeError:
                chart = PecChart(content)
        return content, chart

    def process(self) -> None:
        self.testButton.setDisabled(True)
        try:
            algoIndex = self.algorithmSelector.checkedId()
            content, chart = self.loadChart()
            screen: ScreenUtil
            ans: dict
            if algoIndex == 0:
                import algo.algo1 as algo
            else:
                import algo.algo2 as algo
            screen, ans = algo.solve(chart, self.console)
            if self.saveResult.isChecked():
                self.cacheManager.write_cache_of_content(content, dump_to_json(screen, ans))
            box = QMessageBox(self)
            box.setText(self.tr('Done.'))
            box.exec()
        except Exception:
            self.console.print_exception(show_locals=False)
        finally:
            self.testButton.setDisabled(False)

    def refreshDevices(self) -> None:
        self.deviceSerialSelector.clear()
        try:
            devices = DeviceController.get_devices()
            if not devices:
                self.deviceSerialSelector.addItem(self.tr('No device found'))
                if self.mainModeSelectTabs.count() == 2:
                    self.mainModeSelectTabs.removeTab(0)
            else:
                self.deviceSerialSelector.addItems(devices)
                if self.mainModeSelectTabs.count() <= 1:
                    self.mainModeSelectTabs.insertTab(0, self.autoplayView, self.tr('Autoplay'))
        except Exception:
            pass
    
    def onSelectedDeviceChanged(self, serial: str) -> None:
        if not serial:
            return

        if self.controller and self.controller.serial != serial:
            self.controller = None

        if serial == self.tr('No device found'):
            return
        
        self.controller = DeviceController(serial)
        

    def autoplay(self) -> None:
        content, chart = self.loadChart()
        algoIndex = self.algorithmSelector.checkedId()
        ans: dict
        screen: ScreenUtil
        ansJson: str | None = None

        if ansJson is not None:
            screen, ans = load_from_json(ansJson)
        else:
            if algoIndex == 0:
                import algo.algo1 as algo
            else:
                import algo.algo2 as algo
            screen, ans = algo.solve(chart, self.console)
            self.cacheManager.write_cache_of_content(content, dump_to_json(screen, ans))

        assert self.controller is not None

        deviceWidth = self.controller.device_width
        deviceHeight = self.controller.device_height

        width: int
        height: int
        if self.aspectRatioSelector.checkedId() == 0:
            # 16:9
            height = deviceHeight
            width = height * 16 // 9

        else:
            # 4:3
            height = deviceHeight
            width = height * 4 // 3

        geometry = WindowGeometry((deviceWidth - width) >> 1, (deviceHeight - height) >> 1, width, height)

        adaptedAns = remap_events(screen, geometry, ans)
        ansIter = iter(adaptedAns)

        self.delayLabel.setText(self.tr('Offset:'))
        if self.syncModeSelector.checkedId() == 0:
            # Manual
            self.autoplayWorker = AutoplayWorker(ansIter, -adaptedAns[0][0] - 10, self)  # -10 for the reaction delay
            self.lastDelayValue = self.delayInput.value()

            def waitForBegin():
                if not self.autoplayWorker:
                    return
                self.prepareBeforeAutoplay()

            self.goButton.setText(self.tr('Go!'))
            self.goButton.clicked.disconnect(self.autoplay)
            self.goButton.clicked.connect(waitForBegin)
        else:
            # Delay
            self.lastDelayValue = self.delayInput.value()
            self.autoplayWorker = AutoplayWorker(ansIter, self.lastDelayValue, self)
            self.controller.tap(deviceWidth >> 1, deviceHeight >> 1)
            self.prepareBeforeAutoplay()

    def prepareBeforeAutoplay(self) -> None:
        assert self.autoplayWorker is not None
        self.autoplayWorker.start()
        self.autoplayWorker.finished.connect(self.cleanAfterAutoplay)

        self.goButton.clicked.disconnect()
        self.goButton.clicked.connect(self.autoplayWorker.stop)
        self.goButton.setText(self.tr('Stop'))

        self.delayInput.setValue(0)
        self.delayInput.setDisabled(False)
        self.delayInput.valueChanged.connect(self.autoplayWorker.onDelayChanged)

    def cleanAfterAutoplay(self) -> None:
        self.goButton.clicked.disconnect()
        self.goButton.clicked.connect(self.autoplay)
        self.onSyncModeChanged(self.syncModeSelector.checkedId())
        self.delayInput.setValue(self.lastDelayValue)
        self.delayInput.valueChanged.disconnect()
        self.autoplayWorker = None
        self.delayLabel.setText(self.tr('Delay:'))


if __name__ == '__main__':
    from PyQt5.QtCore import QTranslator, QLocale
    import sys

    app = QApplication(sys.argv)
    trans = QTranslator()
    trans.load(QLocale(), 'phisap', '-', './i18n/', '.qm')
    app.installTranslator(trans)
    window = MainWindow()
    window.show()
    app.exec()
