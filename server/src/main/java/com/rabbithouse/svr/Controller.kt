package com.rabbithouse.svr

import android.os.SystemClock
import android.view.InputDevice
import android.view.MotionEvent
import android.view.MotionEvent.PointerCoords
import android.view.MotionEvent.PointerProperties
import java.io.IOException

class Controller(private val device: Device, private val connection: DesktopConnection) {
    private var lastTouchDown: Long = 0
    private val pointersState = PointersState()
    private val pointerProperties = arrayOfNulls<PointerProperties>(PointersState.MAX_POINTERS)
    private val pointerCoords = arrayOfNulls<PointerCoords>(PointersState.MAX_POINTERS)
    private fun initPointers() {
        for (i in 0 until PointersState.MAX_POINTERS) {
            val props = PointerProperties()
            props.toolType = MotionEvent.TOOL_TYPE_FINGER
            val coords = PointerCoords()
            coords.orientation = 0f
            coords.size = 1f
            pointerProperties[i] = props
            pointerCoords[i] = coords
        }
    }

    @Throws(IOException::class)
    fun control() {
        while (true) {
            handleEvent()
        }
    }

    @Throws(IOException::class)
    private fun handleEvent() {
        val msg = connection.receiveControlMessage()
        when (msg.type) {
            ControlMessage.TYPE_INJECT_TOUCH_EVENT -> if (device.supportsInputEvents()) {
                injectTouch(msg.action, msg.pointerId, msg.position, msg.pressure, msg.buttons)
            }
            ControlMessage.TYPE_STOP_VIDEO_STREAMING -> Server.stopStreaming()
            else -> {
            }
        }
    }

    private fun injectTouch(
        actionCode: Int,
        pointerId: Long,
        position: Position?,
        pressure: Float,
        buttons: Int
    ): Boolean {
        var action = actionCode
        val now = SystemClock.uptimeMillis()
        val point = device.getPhysicalPoint(position)
        if (point == null) {
            Ln.w("Ignore touch event, it was generated for a different device size")
            return false
        }
        val pointerIndex = pointersState.getPointerIndex(pointerId)
        if (pointerIndex == -1) {
            Ln.w("Too many pointers for touch event")
            return false
        }
        val pointer = pointersState[pointerIndex]
        pointer.point = point
        pointer.pressure = pressure
        pointer.isUp = action == MotionEvent.ACTION_UP
        val pointerCount = pointersState.update(pointerProperties, pointerCoords)
        if (pointerCount == 1) {
            if (action == MotionEvent.ACTION_DOWN) {
                lastTouchDown = now
            }
        } else {
            // secondary pointers must use ACTION_POINTER_* ORed with the pointerIndex
            if (action == MotionEvent.ACTION_UP) {
                action =
                    MotionEvent.ACTION_POINTER_UP or (pointerIndex shl MotionEvent.ACTION_POINTER_INDEX_SHIFT)
            } else if (action == MotionEvent.ACTION_DOWN) {
                action =
                    MotionEvent.ACTION_POINTER_DOWN or (pointerIndex shl MotionEvent.ACTION_POINTER_INDEX_SHIFT)
            }
        }

        // Right-click and middle-click only work if the source is a mouse
        val nonPrimaryButtonPressed = buttons and MotionEvent.BUTTON_PRIMARY.inv() != 0
        val source =
            if (nonPrimaryButtonPressed) InputDevice.SOURCE_MOUSE else InputDevice.SOURCE_TOUCHSCREEN
        val event = MotionEvent
            .obtain(
                lastTouchDown,
                now,
                action,
                pointerCount,
                pointerProperties,
                pointerCoords,
                0,
                buttons,
                1f,
                1f,
                DEVICE_ID_VIRTUAL,
                0,
                source,
                0
            )
        return device.injectEvent(event)
    }

    companion object {
        private const val DEVICE_ID_VIRTUAL = -1

    }

    init {
        initPointers()
    }
}