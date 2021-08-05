package com.rabbithouse.svr

import android.os.Build
import android.view.*
import com.rabbithouse.svr.wrappers.InputManager
import com.rabbithouse.svr.wrappers.ServiceManager

class Device {

    @get:Synchronized
    var screenInfo: ScreenInfo

    /**
     * The surface flinger layer stack associated with this logical display
     */
    val layerStack: Int

    fun getPhysicalPoint(position: Position?): Point? {
        // it hides the field on purpose, to read it with a lock
        val screenInfo = screenInfo // read with synchronization

        // ignore the locked video orientation, the events will apply in coordinates considered in the physical device orientation
        val unlockedVideoSize = screenInfo.unlockedVideoSize
        val reverseVideoRotation = screenInfo.reverseVideoRotation
        // reverse the video rotation to apply the events
        val devicePosition = position!!.rotate(reverseVideoRotation)
        val clientVideoSize = devicePosition.screenSize
        if (unlockedVideoSize != clientVideoSize) {
            // The client sends a click relative to a video with wrong dimensions,
            // the device may have been rotated since the event was generated, so ignore the event
            return null
        }
        val contentRect = screenInfo.contentRect
        val point = devicePosition.point
        val convertedX = contentRect.left + point.x * contentRect.width() / unlockedVideoSize.width
        val convertedY = contentRect.top + point.y * contentRect.height() / unlockedVideoSize.height
        return Point(convertedX, convertedY)
    }

    fun supportsInputEvents(): Boolean {
        return true
    }

    private fun injectEvent(inputEvent: InputEvent?, mode: Int): Boolean {
        return SERVICE_MANAGER.inputManager!!.injectInputEvent(inputEvent, mode)
    }

    fun injectEvent(event: InputEvent?): Boolean {
        return injectEvent(event, InputManager.INJECT_INPUT_EVENT_MODE_ASYNC)
    }

    companion object {
        private val SERVICE_MANAGER = ServiceManager()
        val deviceName: String
            get() = Build.MODEL

    }

    init {
        val displayInfo = SERVICE_MANAGER.displayManager!!.getDisplayInfo(0)
            ?: throw InvalidDisplayIdException(0)
        screenInfo = ScreenInfo.computeScreenInfo(displayInfo)
        val screenSize = screenInfo.unlockedVideoSize
        Ln.i("屏幕尺寸: " + screenSize.width + "x" + screenSize.height)
        layerStack = displayInfo.layerStack
    }
}