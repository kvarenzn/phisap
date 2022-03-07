import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

import ChapterModel

Item {
	signal chapterSelected(int index)

	FontLoader {
		id: pgrFont
		source: 'Assets/Source Han Sans & Saira Hybrid-Regular.ttf'
		property var fontName: status == FontLoader.Ready ? name : 'Sans Serif'
	}

	Image {
		id: blurredBackground
		anchors.fill: parent
		source: 'Assets/Tracks/%23ChapterCover/AllSongBlur.png'
		smooth: true
		mipmap: true
	}

	smooth: true
	antialiasing: true

	layer {
		enabled: true
		mipmap: true
		samples: 8
	}

	ListView {
		id: chaptersList
		currentIndex: -1
		anchors.fill: parent
		orientation: ListView.Horizontal
		snapMode: ListView.SnapOneItem
		spacing: - width / 9

		property real itemWidth: width / 4
		property real wideItemWidth: width / 2

		delegate: Item {
			id: chapterItem
			property real itemWidth: ListView.isCurrentItem ? chaptersList.wideItemWidth : chaptersList.itemWidth
			width: itemWidth + height * Math.tan(Math.PI / 12)
			height: chaptersList.height

			smooth: true
			antialiasing: true

			MouseArea {
				anchors.fill: parent
				onClicked: chaptersList.currentIndex = -1
			}

			Text {
				text: chapterName
				font.family: pgrFont.fontName
				font.pointSize: parent.height <= 0 ? 1 : parent.height / 18
				color: '#ccffffff'
				z: 0.1
				opacity: chapterItem.ListView.isCurrentItem ? 1.0 : 0.0
				visible: opacity > 0
				anchors.left: parent.left
				anchors.top: parent.top
				anchors.leftMargin: parent.height * Math.tan(Math.PI / 12) + parent.height / 18
				anchors.topMargin: parent.height / 7
				Behavior on opacity { PropertyAnimation {} }
			}

			Rectangle {
				width: parent.itemWidth * Math.cos(Math.PI / 12)
				height: parent.itemWidth * Math.sin(Math.PI / 12) + chaptersList.height / Math.cos(Math.PI / 12)
				y: chaptersList.y + chaptersList.height - height

				smooth: true
				antialiasing: true
				rotation: 15
				transformOrigin: Item.BottomLeft

				clip: true

				MouseArea {
					anchors.fill: parent
					onClicked: {
						blurredBackground.source = chapterBlurPath
						chaptersList.currentIndex = index
					}
				}

				Image {
					source: chapterImagePath
					smooth: true
					mipmap: true
					antialiasing: true
					width: sourceSize.width * height / sourceSize.height
					height: chaptersList.height
					anchors.centerIn: parent
					rotation: -15
				}

				Text {
					text: chapterShortName
					opacity: chapterItem.ListView.isCurrentItem ? 0.0 : 1.0
					anchors.left: parent.right
					anchors.bottom: parent.bottom
					anchors.bottomMargin: chapterItem.itemWidth * Math.sin(Math.PI / 12)
					color: '#bbffffff'
					rotation: -90
					transformOrigin: Item.BottomLeft
					font.family: pgrFont.fontName
					font.pointSize: chaptersList.itemWidth / 5
					Behavior on opacity { PropertyAnimation {} }
				}

				Rectangle {
					id: playButton
					opacity: chapterItem.ListView.isCurrentItem ? 1.0 : 0.0
					visible: opacity > 0
					anchors.centerIn: parent
					width: chapterItem.width
					height: chaptersList.height / 9
					rotation: -15
					color: '#ccffffff'
					Behavior on opacity { PropertyAnimation {} }
					Text {
						text: '▷   P   L   A   Y'
						font.family: pgrFont.fontName
						font.pointSize: playButton.height <= 0 ? 12 : playButton.height * 0.5
						anchors.centerIn: playButton
					}
					MouseArea {
						anchors.fill: parent
						onClicked: {
							chapterSelected(index)
						}
					}
				}

				Behavior on x { PropertyAnimation {} }
				Behavior on width { PropertyAnimation {} }
				Behavior on height { PropertyAnimation {} }
			}
		}

		model: ChaptersData
	}
}
