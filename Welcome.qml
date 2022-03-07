import QtQuick
import QtQuick.Particles
import QtQuick.Controls
import QtQuick.Dialogs
import Qt5Compat.GraphicalEffects

import phisap.extractor
import phisap.utils

Item {
	required property var stackView

	signal screenClicked
	signal switchView

	Utils {
		id: utils
	}

	FontLoader {
		id: pgrFont
		source: 'Assets/Source Han Sans & Saira Hybrid-Regular.ttf'
		property var fontName: status == FontLoader.Ready ? name : 'Sans Serif'
	}

	Loader {
		id: extractor
		active: false
		sourceComponent: extractWorker
	}

	Component {
		id: extractWorker
		ExtractWorker {}
	}

	Rectangle {
		anchors.fill: parent
		color: 'black'
	}

	ParticleSystem {
		id: particles
	}

	ImageParticle {
		system: particles
		alpha: 0.5
		alphaVariation: 0.5
		source: 'qrc:///particleresources/fuzzydot.png'
	}

	Emitter {
		system: particles
		emitRate: 2
		lifeSpan: 8000
		lifeSpanVariation: 5000
		velocity: PointDirection {
			y: -10; yVariation: 5
			x: 0; xVariation: 5
		}
		acceleration: PointDirection { y: 0 }
		size: 40
		endSize: -1
		sizeVariation: 20
		width: parent.width
		height: parent.height
	}

	MouseArea {
		id: screenArea
		anchors.fill: parent
		onClicked: {
			screenClicked()
		}
	}

	Text {
		id: programTitle
		text: 'phisap'
		color: 'white'
		font.family: pgrFont.fontName
		font.pointSize: 50

		anchors.horizontalCenter: parent.horizontalCenter
		anchors.verticalCenter: parent.verticalCenter
		anchors.verticalCenterOffset: -this.height / 2

		smooth: true
	}

	Glow {
		anchors.fill: programTitle
		radius: 20
		color: 'cyan'
		source: programTitle
	}

	Text {
		id: welcomeText

		font.family: pgrFont.fontName
		font.pointSize: 12
		smooth: true

		anchors.horizontalCenter: parent.horizontalCenter
		anchors.verticalCenter: parent.verticalCenter
		anchors.verticalCenterOffset: parent.height / 6

		color: 'white'
	}

	Glow {
		anchors.fill: welcomeText
		color: 'white'
		radius: 30
		source: welcomeText

		SequentialAnimation on radius {
			loops: Animation.Infinite

			NumberAnimation {
				from: 0; to: 30
				easing.type: Easing.InExpo; duration: 1400
			}

			PauseAnimation {
				duration: 300
			}

			NumberAnimation {
				from: 30; to: 0
				easing.type: Easing.OutExpo; duration: 1400
			}
		}
	}

	Rectangle {
		id: progressbar
		visible: false
		width: parent.width / 2
		height: 5
		anchors.horizontalCenter: parent.horizontalCenter
		anchors.top: welcomeText.bottom
		anchors.topMargin: 20

		color: 'transparent'

		property real value: -1

		Rectangle {
			id: runningBar
			visible: parent.value < 0 && parent.visible
			anchors.top: parent.top
			anchors.bottom: parent.bottom
			anchors.left: parent.left
			anchors.right: parent.right
			anchors.leftMargin: 0
			anchors.rightMargin: parent.width
			color: 'white'

			property int duration: 400
			ParallelAnimation {
				loops: Animation.Infinite
				running: runningBar.visible
				SequentialAnimation {
					PauseAnimation { duration: runningBar.duration }
					NumberAnimation {
						target: runningBar
						property: 'anchors.leftMargin'
						to: progressbar.width
						duration: runningBar.duration
					}
					PauseAnimation { duration: runningBar.duration }
					NumberAnimation {
						target: runningBar
						property: 'anchors.leftMargin'
						to: 0
						duration: runningBar.duration
					}
				}
				SequentialAnimation {
					NumberAnimation {
						target: runningBar
						property: 'anchors.rightMargin'
						to: 0
						duration: runningBar.duration
					}
					PauseAnimation { duration: runningBar.duration }
					NumberAnimation {
						target: runningBar
						property: 'anchors.rightMargin'
						to: progressbar.width
						duration: runningBar.duration
					}
					PauseAnimation { duration: runningBar.duration }
				}
			}
		}

		Rectangle {
			id: innerBar
			visible: parent.value >= 0 && parent.visible
			height: parent.height
			width: parent.width * parent.value
			anchors.top: parent.top
			anchors.left: parent.left
			anchors.bottom: parent.bottom
			color: 'white'
			Behavior on width { PropertyAnimation {} }
		}

		Text {
			text: Math.round(parent.value * 100) + '%'
			font.family: pgrFont.fontName
			visible: innerBar.visible
			anchors.top: parent.bottom
			anchors.topMargin: 3
			anchors.horizontalCenter: innerBar.right
			color: 'white'
			Behavior on x { PropertyAnimation {}  }
		}
	}

	Component.onCompleted: {
		let needExtract = !utils.database_available()
		welcomeText.text = '点 击 屏 幕 以 ' + (needExtract ? '解 包 游 戏' : '开 始')
		if (needExtract) {
			extractor.active = true
			extractor.item.update_progress.connect(updateProgress)
			extractor.item.done_extract.connect(doneExtract)
			screenClicked.connect(() => {
				let path = utils.ask_apk_path()
				if (path) {
					extractor.item.apkPath = path
					extractor.item.start()
				}
			})
		} else {
			screenClicked.connect(() => {
				switchView()
			})
		}
	}

    function setWelcomeText(text) {
        welcomeText.text = text
    }

	function updateProgress(value) {
		if (!progressbar.visible) {
			progressbar.visible = true
		}
		if (progressbar.value < 0) {
			welcomeText.text = '正 在 读 取 安 装 包 ...'
		} else {
			welcomeText.text = '正 在 写 入 解 包 结 果 ...'
		}
		progressbar.value = value
	}

	function doneExtract() {
		progressbar.visible = false
		switchView()
	}
}
