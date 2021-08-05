package com.rabbithouse.svr

/**
 * Union of all supported event types, identified by their `type`.
 */
class ControlMessage private constructor() {
    var type = 0
        private set
    var text: String? = null
        private set
    var action: Int = 0 // KeyEvent.ACTION_* or MotionEvent.ACTION_* or POWER_MODE_* = 0
        private set
    var buttons: Int = 0 // MotionEvent.BUTTON_* = 0
        private set
    var pointerId: Long = 0
        private set
    var pressure = 0f
        private set
    var position: Position? = null
        private set

    companion object {
        const val TYPE_INJECT_TOUCH_EVENT = 2
        const val TYPE_STOP_VIDEO_STREAMING = 11

        fun createInjectTouchEvent(action: Int, pointerId: Long, position: Position?, pressure: Float, buttons: Int): ControlMessage {
            val msg = ControlMessage()
            msg.type = TYPE_INJECT_TOUCH_EVENT
            msg.action = action
            msg.pointerId = pointerId
            msg.pressure = pressure
            msg.position = position
            msg.buttons = buttons
            return msg
        }

        fun createEmpty(type: Int): ControlMessage {
            val msg = ControlMessage()
            msg.type = type
            return msg
        }
    }
}