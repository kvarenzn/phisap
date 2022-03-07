import QtQuick
import QtQuick.Shapes
import Qt5Compat.GraphicalEffects

Rectangle {
	width: 1280
	height: 720
	color: 'black'

	property real shortSide: Math.min(width, height)
	property real outerSide: shortSide / 6
	property real innerSide: outerSide / (Math.cos(Math.PI / 30) + Math.sin(Math.PI / 30))
	property real arcWidth: 6
	Rectangle {
		width: outerSide
		height: outerSide
		anchors.centerIn: parent
		color: 'transparent'
		border.width: 3
		border.color: 'white'

		RotationAnimation on rotation {
			loops: Animation.Infinite
			duration: 5000
			from: 0
			to: 360
		}
	}

	Rectangle {
		width: innerSide
		height: innerSide
		anchors.centerIn: parent
		color: 'transparent'
		border.width: 2
		border.color: '#aaffffff'

		RotationAnimation on rotation {
			loops: Animation.Infinite
			duration: 5000
			from: 360
			to: 0
		}
	}

	Shape {
		width: innerSide
		height: innerSide

		anchors.centerIn: parent
		ShapePath {
			strokeWidth: arcWidth
			strokeColor: 'white'
			fillColor: 'transparent'

			startX: innerSide / 2 - arcWidth / 2; startY: arcWidth / 2
			PathArc {
				x: innerSide - arcWidth; y: innerSide / 2 - arcWidth / 2
				radiusX: innerSide / 2 - arcWidth / 2
				radiusY: innerSide / 2 - arcWidth / 2
			}
		}

		ShapePath {
			strokeWidth: arcWidth
			strokeColor: 'white'
			fillColor: 'transparent'

			startX: innerSide / 2 - arcWidth / 2; startY: innerSide - arcWidth
			PathArc {
				x: arcWidth / 2; y: innerSide / 2 - arcWidth / 2
				radiusX: innerSide / 2 - arcWidth / 2
				radiusY: innerSide / 2 - arcWidth / 2
			}
		}

		RotationAnimation on rotation {
			loops: Animation.Infinite
			duration: 2500
			from: 360
			to: 0
		}
	}

	Text {
		id: loadingText
		text: 'Loading'
		anchors.centerIn: parent
		font.pointSize: shortSide / 30
		font.bold: true
		leftPadding: height / 2
		rightPadding: height / 2
		color: 'white'
		visible: false
	}

	Rectangle {
		id: textBackground
		color: 'white'
		anchors.fill: loadingText
		visible: false
	}

	OpacityMask {
		id: inversedText
		invert: true
		anchors.fill: textBackground
		source: textBackground
		maskSource: loadingText
		visible: false
	}

	Shape {
		id: maskSource
		anchors.fill: textBackground
		visible: false

		property real leftFactor: 0
		property real rightFactor: 0
		property real leftX: leftFactor * textBackground.width
		property real rightX: rightFactor * textBackground.width

		ShapePath {
			strokeWidth: 0
			strokeColor: 'transparent'
			fillColor: 'white'
			startX: maskSource.leftX; startY: 0
			PathLine { x: maskSource.leftX; y: textBackground.height }
			PathLine { x: maskSource.rightX; y: textBackground.height }
			PathLine { x: maskSource.rightX; y: 0 }
			PathLine { x: maskSource.leftX; y: 0 }
		}

		SequentialAnimation {
			running: true
			loops: Animation.Infinite
			NumberAnimation {
				target: maskSource
				properties: 'rightFactor'
				from: 0
				to: 1
				duration: 500
				easing.type: Easing.InExpo
			}
			PauseAnimation { duration: 100 }
			NumberAnimation {
				target: maskSource
				properties: 'leftFactor'
				from: 0
				to: 1
				duration: 500
				easing.type: Easing.InExpo
			}
			NumberAnimation {
				target: maskSource
				properties: 'leftFactor,rightFactor'
				to: 0
				duration: 100
			}
		}
	}

	OpacityMask {
		id: mask1
		anchors.fill: textBackground
		source: inversedText
		maskSource: maskSource
	}

	OpacityMask {
		id: mask2
		invert: !mask1.invert
		anchors.fill: textBackground
		source: loadingText
		maskSource: maskSource
	}

	Shape {
		id: boxBorder
		property real margin: 5
		property real leftFactor: 0
		property real rightFactor: 0.5
		property bool displayII: rightFactor == 1 && leftFactor != 1
		property real leftX: leftFactor * width
		property real rightX: rightFactor * width
		anchors.fill: textBackground
		anchors.leftMargin: - margin
		anchors.rightMargin: - margin
		anchors.topMargin: - margin
		anchors.bottomMargin: - margin

		ShapePath {
			strokeWidth: 2
			strokeColor: 'white'
			fillColor: 'transparent'
			startX: boxBorder.leftX; startY: boxBorder.height
			PathLine { x: boxBorder.rightX; y: boxBorder.height }
			PathLine { x: boxBorder.rightX; y: boxBorder.displayII ? 0 : boxBorder.height }
		}

		ShapePath {
			strokeWidth: 2
			strokeColor: 'white'
			fillColor: 'transparent'
			startX: boxBorder.width - boxBorder.leftX; startY: 0
			PathLine { x: boxBorder.width - boxBorder.rightX; y: 0 }
			PathLine { x: boxBorder.width - boxBorder.rightX; y: boxBorder.displayII ? boxBorder.height : 0 }
		}

		SequentialAnimation {
			running: true
			loops: Animation.Infinite
			NumberAnimation {
				target: boxBorder
				properties: 'rightFactor'
				from: 0
				to: 1
				duration: 500
				easing.type: Easing.InExpo
			}
			PauseAnimation { duration: 100 }
			NumberAnimation {
				target: boxBorder
				properties: 'leftFactor'
				from: 0
				to: 1
				duration: 500
				easing.type: Easing.InExpo
			}
			NumberAnimation {
				target: boxBorder
				properties: 'leftFactor,rightFactor'
				to: 0
				duration: 100
			}
		}
	}

	layer.enabled: true
	layer.mipmap: true
	layer.samples: 8
}
