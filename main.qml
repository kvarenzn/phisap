import QtQuick
import QtQuick.Controls

import phisap.utils

Item {
	width: 1280
	height: 720

	Utils {
		id: utils
	}

	StackView {
		id: stack
		anchors.fill: parent

		replaceEnter: Transition {
			PropertyAnimation {
				property: 'opacity'
				from: 0
				to: 1
				duration: 200
			}
		}

		replaceExit: Transition {
			PropertyAnimation {
				property: 'opacity'
				from: 1
				to: 0
				duration: 200
			}
		}

		Component.onCompleted: {
			push(welcomePage)
		}
	}

	Component {
		id: welcomePage
		Welcome {
			stackView: stack
			onSwitchView: {
				stack.replace(chapterSelectPage)
			}
		}
	}

	Component {
		id: chapterSelectPage
		ChapterSelect {
		}
	}

	Component {
		id: songSelectPage
		SongSelect {
			onBackPressed: {
				stack.pop()
			}
		}
	}
}
