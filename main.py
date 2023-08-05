import os
import time
import json
import typing
import zipfile
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication,
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
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QSettings

from rich.console import Console

from control import DeviceController
from catalog import Catalog
from extract import AssetsManager, TextAsset, ObjectReader, ClassID
from algo.algo_base import (
    AlgorithmConfigure,
    ScreenUtil,
    dump_data,
    load_data,
    WindowGeometry,
    remap_events,
    TouchEvent,
    RawAnswerType,
)
from basis import Chart
from cache_manager import CacheManager
from control import DeviceController

from pgr import PgrChart
from pec import PecChart
from rpe import RpeChart

PHISAP_VERSION = '0.14'


class ExtractPackageWorker(QThread):
    processUpdate = pyqtSignal(int, int, int)  # phase, current, max
    packagePath: str
    running: bool

    def run(self) -> None:
        self.running = True
        package = zipfile.ZipFile(self.packagePath)
        try:
            catalog = Catalog(package.open('assets/aa/catalog.json'))
        except KeyError:
            # TODO: alert
            print('???')
            return

        manager = AssetsManager()
        files = package.namelist()
        for index, file in enumerate(files):
            self.processUpdate.emit(0, index, len(files))
            if not self.running:
                return
            if not file.startswith('assets/aa/Android'):
                continue
            with package.open(file) as f:
                manager.load_file(f)

        files = manager.asset_files
        for index, file in enumerate(files):
            self.processUpdate.emit(1, index, len(files))
            if not self.running:
                return
            for object_info in file.object_infos:
                with ObjectReader(file.reader, file, object_info) as obj_reader:
                    if obj_reader.class_id == ClassID.TEXT_ASSET:
                        file.add_object(TextAsset(obj_reader))

        files = manager.asset_files
        for index, file in enumerate(files):
            self.processUpdate.emit(2, index, len(files))
            if not self.running:
                return
            assert file.parent
            filepath = file.parent.reader.path
            if filepath.name not in catalog.fname_map:
                continue
            asset_name = catalog.fname_map[filepath.name]
            if not asset_name.startswith('Assets/'):
                continue

            for obj in file.objects:
                if isinstance(obj, TextAsset):
                    basedir = os.path.dirname(asset_name)
                    if basedir and not os.path.exists(basedir):
                        os.makedirs(basedir)
                    with open(asset_name, 'w') as out:
                        out.write(obj.text)

    def cancel(self) -> None:
        self.running = False

    def __init__(self, packagePath: str, parent: QObject) -> None:
        super().__init__(parent)
        self.packagePath = packagePath


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
        self.startTime = round(time.monotonic() * 1000) + self.defaultOffset
        try:
            while self.running:
                now = round(time.monotonic() * 1000) - self.startTime + self.delayMs
                if now >= timestamp:
                    for event in events:
                        self.controller.touch(*event.pos, event.action, event.pointer_id)
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
    extractPackageWorker: ExtractPackageWorker | None
    extractProgressDialog: QProgressDialog | None

    mainLayout: QLayout
    deviceSerialSelector: QComboBox
    refreshDeviceButton: QPushButton
    chartSelectTabs: QTabWidget
    songIdSelector: QComboBox
    extractButton: QPushButton
    difficultySelector: QComboBox
    customChartPath: QLineEdit
    customSelectButton: QPushButton
    algorithmSelectorTabs: QTabWidget

    algo1FlickStart: QSpinBox
    algo1FlickEnd: QSpinBox
    algo1FlickDirection: QButtonGroup
    algo1SampleDelay: QSpinBox
    algo1TargetScore: QSpinBox
    algo1StrictMode: QCheckBox
    algo2FlickStart: QSpinBox
    algo2FlickEnd: QSpinBox
    algo2FlickDirection: QButtonGroup
    algo2TargetScore: QSpinBox
    algo2StrictMode: QCheckBox

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

    settings: QSettings

    SETTINGS: dict[str, tuple[str, typing.Any] | int | float | bool | str] = {
        'songId': ('songIdSelector', None),
        'difficulty': ('difficultySelector', None),
        'algorithm': ('algorithmSelectorTabs', 0),
        'algo1FlickStart': -17,
        'algo1FlickEnd': 17,
        'algo1FlickDirection': 0,
        'algo1SampleDelay': 1,
        'algo1TargetScore': 1000000,
        'algo1StrictMode': False,
        'algo2FlickStart': -17,
        'algo2FlickEnd': 17,
        'algo2FlickDirection': 1,
        'algo2TargetScore': 1000000,
        'algo2StrictMode': False,
        'customChartPath': '',
        'preferCache': True,
        'syncMode': ('syncModeSelector', 0),
        'delay': ('delayInput', 0),
        'aspectRatio': ('aspectRatioSelector', 0),
        'saveCache': ('saveResult', False),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.console = Console()
        self.extractedCharts = Path('./Assets/Tracks')
        self.cacheManager = CacheManager()
        self.autoplayWorker = None
        self.extractPackageWorker = None
        self.extractProgressDialog = None
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
        selectExtractedViewLayout.addWidget(self.extractButton)
        line1 = QHBoxLayout()
        selectExtractedViewLayout.addLayout(line1)
        line1.addWidget(QLabel(text=self.tr('Song:')))
        line1.addWidget(self.songIdSelector)
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

        self.algorithmSelectorTabs = QTabWidget()
        self.mainLayout.addWidget(self.algorithmSelectorTabs)
        algo1ConfigView = QWidget()
        self.algorithmSelectorTabs.addTab(algo1ConfigView, self.tr('Conserv algo'))
        algo1ConfigViewLayout = QVBoxLayout()
        algo1ConfigView.setLayout(algo1ConfigViewLayout)
        line1 = QHBoxLayout()
        algo1ConfigViewLayout.addLayout(line1)
        line1.addWidget(QLabel(text=self.tr('Flick start at:')))
        self.algo1FlickStart = QSpinBox()
        self.algo1FlickStart.setRange(-1145141919, 1145141919)
        line1.addWidget(self.algo1FlickStart)
        line1.addWidget(QLabel(text=self.tr('ms')))
        line2 = QHBoxLayout()
        algo1ConfigViewLayout.addLayout(line2)
        line2.addWidget(QLabel(text=self.tr('Flick end at:')))
        self.algo1FlickEnd = QSpinBox()
        self.algo1FlickEnd.setRange(-1145141919, 1145141919)
        line2.addWidget(self.algo1FlickEnd)
        line2.addWidget(QLabel(text=self.tr('ms')))
        line3 = QHBoxLayout()
        algo1ConfigViewLayout.addLayout(line3)
        self.algo1FlickDirection = QButtonGroup()
        line3.addWidget(QLabel(text=self.tr('Flick direction:')))
        direc1 = QRadioButton(text=self.tr('Perpend. to'))
        direc2 = QRadioButton(text=self.tr('Parallel to'))
        line3.addWidget(direc1)
        line3.addWidget(direc2)
        self.algo1FlickDirection.addButton(direc1, id=0)
        self.algo1FlickDirection.addButton(direc2, id=1)
        direc1.setChecked(True)
        line31 = QHBoxLayout()
        algo1ConfigViewLayout.addLayout(line31)
        line31.addWidget(QLabel(text=self.tr('Sample delay:')))
        self.algo1SampleDelay = QSpinBox()
        self.algo1SampleDelay.setRange(1, 17)
        line31.addWidget(self.algo1SampleDelay)
        line31.addWidget(QLabel(text=self.tr('ms')))
        line4 = QHBoxLayout()
        algo1ConfigViewLayout.addLayout(line4)
        self.algo1TargetScore = QSpinBox()
        self.algo1TargetScore.setRange(0, 1000000)
        self.algo1TargetScore.setDisabled(True)
        line4.addWidget(QLabel(text=self.tr('Target score:')))
        line4.addWidget(self.algo1TargetScore)
        self.algo1StrictMode = QCheckBox(text=self.tr('Strict'))
        self.algo1StrictMode.setDisabled(True)
        line4.addWidget(self.algo1StrictMode)

        algo2ConfigView = QWidget()
        self.algorithmSelectorTabs.addTab(algo2ConfigView, self.tr('Radical algo'))
        algo2ConfigViewLayout = QVBoxLayout()
        algo2ConfigView.setLayout(algo2ConfigViewLayout)
        line1 = QHBoxLayout()
        algo2ConfigViewLayout.addLayout(line1)
        line1.addWidget(QLabel(text=self.tr('Flick start at:')))
        self.algo2FlickStart = QSpinBox()
        self.algo2FlickStart.setRange(-1145141919, 1145141919)
        line1.addWidget(self.algo2FlickStart)
        line1.addWidget(QLabel(text=self.tr('ms')))
        line2 = QHBoxLayout()
        algo2ConfigViewLayout.addLayout(line2)
        line2.addWidget(QLabel(text=self.tr('Flick end at:')))
        self.algo2FlickEnd = QSpinBox()
        self.algo2FlickEnd.setRange(-1145141919, 1145141919)
        line2.addWidget(self.algo2FlickEnd)
        line2.addWidget(QLabel(text=self.tr('ms')))
        line3 = QHBoxLayout()
        algo2ConfigViewLayout.addLayout(line3)
        self.algo2FlickDirection = QButtonGroup()
        line3.addWidget(QLabel(text=self.tr('Flick direction:')))
        direc1 = QRadioButton(text=self.tr('Perpend. to'))
        direc2 = QRadioButton(text=self.tr('Parallel to'))
        line3.addWidget(direc1)
        line3.addWidget(direc2)
        self.algo2FlickDirection.addButton(direc1, id=0)
        self.algo2FlickDirection.addButton(direc2, id=1)
        direc1.setChecked(True)
        line4 = QHBoxLayout()
        algo2ConfigViewLayout.addLayout(line4)
        self.algo2TargetScore = QSpinBox()
        self.algo2TargetScore.setRange(0, 1000000)
        self.algo2TargetScore.setDisabled(True)
        line4.addWidget(QLabel(text=self.tr('Target score:')))
        line4.addWidget(self.algo2TargetScore)
        self.algo2StrictMode = QCheckBox(text=self.tr('Strict'))
        self.algo2StrictMode.setDisabled(True)
        line4.addWidget(self.algo2StrictMode)

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

        self.settings = QSettings('./.settings.ini', QSettings.Format.IniFormat)
        self.loadSettings()

    def loadSettings(self) -> None:
        for key, info in self.SETTINGS.items():
            if isinstance(info, tuple):
                widgetName, defaultValue = info
            else:
                widgetName = key
                defaultValue = info
            widget = getattr(self, widgetName)
            match widget:
                case QComboBox():
                    if widget.count() > 1:
                        widget.setCurrentText(self.settings.value(key, defaultValue or widget.currentText(), str))
                case QTabWidget():
                    widget.setCurrentIndex(self.settings.value(key, defaultValue, type(defaultValue)))
                case QSpinBox():
                    widget.setValue(self.settings.value(key, defaultValue, type(defaultValue)))
                case QButtonGroup():
                    widget.button(self.settings.value(key, defaultValue, type(defaultValue))).setChecked(True)
                case QLineEdit():
                    widget.setText(self.settings.value(key, defaultValue, type(defaultValue)))
                case QCheckBox():
                    widget.setChecked(self.settings.value(key, defaultValue, type(defaultValue)))

    def saveSettings(self) -> None:
        for key, info in self.SETTINGS.items():
            if isinstance(info, tuple):
                widgetName = info[0]
            else:
                widgetName = key
            widget = getattr(self, widgetName)
            match widget:
                case QComboBox():
                    if widget.count() > 1:
                        self.settings.setValue(key, widget.currentText())
                case QTabWidget():
                    self.settings.setValue(key, widget.currentIndex())
                case QSpinBox():
                    self.settings.setValue(key, widget.value())
                case QButtonGroup():
                    self.settings.setValue(key, widget.checkedId())
                case QLineEdit():
                    self.settings.setValue(key, widget.text())
                case QCheckBox():
                    self.settings.setValue(key, widget.isChecked())

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
        self.extractPackageWorker = ExtractPackageWorker(filepath, self)
        self.extractProgressDialog = QProgressDialog(self)
        self.extractProgressDialog.canceled.connect(self.extractPackageWorker.cancel)
        self.extractPackageWorker.finished.connect(self.onExtractFinished)
        self.extractPackageWorker.processUpdate.connect(self.onExtractProgressUpdated)
        self.extractPackageWorker.start()

    def onExtractProgressUpdated(self, phase: int, current: int, maxValue: int) -> None:
        if self.extractProgressDialog is None:
            return

        hint = [self.tr('Loading...'), self.tr('Processing...'), self.tr('Extracting...')]
        self.extractProgressDialog.setLabelText(hint[phase])
        self.extractProgressDialog.setMaximum(maxValue)
        self.extractProgressDialog.setValue(current)

    def onExtractFinished(self):
        if self.extractProgressDialog:
            self.extractProgressDialog.close()
            self.extractProgressDialog = None
        self.extractButton.setDisabled(False)
        box = QMessageBox()
        box.setText(self.tr('Extract finished'))
        box.exec()
        self.loadSongs()

    def loadSongs(self) -> None:
        try:
            if not self.extractedCharts.exists() or not self.extractedCharts.is_dir():
                return
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
        content = chartPath.open(encoding='utf-8').read()
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

    def getAlgorithmConfigureDict(self) -> AlgorithmConfigure:
        return AlgorithmConfigure(
            algo1_flick_start=self.algo1FlickStart.value(),
            algo1_flick_end=self.algo1FlickEnd.value(),
            algo1_flick_direction=self.algo1FlickDirection.checkedId(),
            algo1_sample_delay=self.algo1SampleDelay.value(),
            algo1_target_score=self.algo1TargetScore.value(),
            algo1_strict_mode=self.algo1StrictMode.isChecked(),
            algo2_flick_start=self.algo2FlickStart.value(),
            algo2_flick_end=self.algo2FlickEnd.value(),
            algo2_flick_direction=self.algo2FlickDirection.checkedId(),
            algo2_target_score=self.algo2TargetScore.value(),
            algo2_strict_mode=self.algo2StrictMode.isChecked()
        )

    def process(self) -> None:
        self.saveSettings()
        self.testButton.setDisabled(True)
        try:
            algoIndex = self.algorithmSelectorTabs.currentIndex()
            content, chart = self.loadChart()
            screen: ScreenUtil
            ans: RawAnswerType
            if algoIndex == 0:
                import algo.algo1 as algo
            else:
                import algo.algo3 as algo
            screen, ans = algo.solve(chart, self.getAlgorithmConfigureDict(), self.console)
            if self.saveResult.isChecked():
                self.cacheManager.write_cache_of_content(content, dump_data(screen, ans))
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
        self.saveSettings()
        content, chart = self.loadChart()
        algoIndex = self.algorithmSelectorTabs.currentIndex()
        ans: RawAnswerType
        screen: ScreenUtil
        cacheData: bytes | None = None

        if self.preferCache.isChecked():
            cacheData = self.cacheManager.find_cache_for_content(content)

        if cacheData is not None:
            screen, ans = load_data(cacheData)
        else:
            if algoIndex == 0:
                import algo.algo1 as algo
            else:
                import algo.algo3 as algo
            screen, ans = algo.solve(chart, self.getAlgorithmConfigureDict(), self.console)
            self.cacheManager.write_cache_of_content(content, dump_data(screen, ans))

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
            self.autoplayWorker = AutoplayWorker(ansIter, -adaptedAns[0][0], self)
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
