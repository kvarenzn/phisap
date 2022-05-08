import QtQuick
import QtQuick.Controls
import QtQuick.Shapes

Item {
	signal songSelected(int index)
	signal backPressed

	id: songSelect

	width: 1280
	height: 720

	FontLoader {
		id: pgrFont
		source: 'Assets/Source Han Sans & Saira Hybrid-Regular.ttf'
		property var fontName: status == FontLoader.Ready ? name : 'Sans Serif'
	}

	ListView {
		id: songsList
		currentIndex: 1
		anchors.fill: parent
		orientation: ListView.Vertical
		snapMode: ListView.SnapOneItem

		delegate: Item {
			id: songItem
			width: songSelect.width
			height: songSelect.height

			smooth: true
			antialiasing: true

			Image {
				anchors.fill: parent
				source: `Assets/Tracks/${modelData}/Illustration.png`
				smooth: true
				mipmap: true
			}
		}

		ScrollIndicator.vertical: ScrollIndicator {
			id: indicator
			visible: false
		}

		model: [
			'Aleph0.LeaF.0',
			'Burn.NceS.0',
			'Credits.Frums.0',
			'CROSSSOUL.HyuNfeatSyepias.0'
		]
	}

	Item {
		anchors.fill: parent
		opacity: !indicator.active
		visible: opacity > 0
		Behavior on opacity { PropertyAnimation { duration: 100 } }

		layer.enabled: true
		layer.mipmap: true
		layer.samples: 8

		Shape {
			id: backBtn
			width: height * (2.5 + Math.tan(Math.PI / 12))
			height: parent.height / 10
			clip: true
			ShapePath {
				strokeWidth: 0
				strokeColor: 'transparent'
				fillColor: '#77777777'
				startX: 0; startY: 0
				PathLine { x: 0; y: backBtn.height }
				PathLine { x: backBtn.height * 2.5; y: backBtn.height }
				PathLine { x: backBtn.height * (2.5 + Math.tan(Math.PI / 12)); y: 0 }
				PathLine { x: 0; y: 0 }
			}
			ShapePath {
				strokeWidth: 7
				strokeColor: 'white'
				fillColor: 'transparent'
				startX: backBtn.height * (2.5 + Math.tan(Math.PI / 12)) - 3.5
				startY: 0
				PathLine { x: backBtn.height * 2.5 - 3.5; y: backBtn.height }
			}

			Text {
				id: leftArrow
				text: '←'
				color: 'white'
				font.pointSize: parent.height > 0 ? parent.height / 3 : 1
				anchors.verticalCenter: parent.verticalCenter
				anchors.horizontalCenter: parent.horizontalCenter
				anchors.horizontalCenterOffset: - parent.height * 0.8
			}

			Text {
				text: '返回'
				color: 'white'
				font.pointSize: parent.height > 0 ? parent.height / 3 : 1
				anchors.left: leftArrow.right
				anchors.leftMargin: parent.height / 2.7
				anchors.verticalCenter: parent.verticalCenter
			}

			MouseArea {
				anchors.fill: parent
				onClicked: {
					backPressed()
				}
			}
		}

		Rectangle {
			y: parent.height / 8
			width: parent.width / 3
			height: parent.height / 3.5

			Rectangle {
				x: parent.height / 8
				width: parent.height / 20
				anchors.top: parent.top
				anchors.bottom: titleText.bottom
				color: 'white'
			}

			Text {
				id: titleText
				text: 'Burn'
				font.pointSize: parent.height > 0 ? parent.height / 5 : 1
				font.bold: true
				anchors.left: parent.left
				anchors.leftMargin: parent.height / 4
				anchors.top: parent.top
				color: 'white'
			}

			Text {
				id: artistText
				text: 'NceS'
				font.pointSize: parent.height > 0 ? parent.height / 10 : 1
				font.bold: true
				anchors.left: titleText.left
				anchors.top: titleText.bottom
				color: 'white'
			}

			gradient: Gradient {
				orientation: Gradient.Horizontal
				GradientStop { position: 0; color: '#aa000000' }
				GradientStop { position: 1; color: 'transparent' }
			}
		}
	}
}
