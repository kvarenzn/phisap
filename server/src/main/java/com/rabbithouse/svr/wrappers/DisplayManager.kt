package com.rabbithouse.svr.wrappers

import android.os.IInterface
import com.rabbithouse.svr.DisplayInfo
import com.rabbithouse.svr.Size

class DisplayManager(private val manager: IInterface) {
    fun getDisplayInfo(displayId: Int): DisplayInfo? {
        return try {
            val displayInfo = manager.javaClass.getMethod("getDisplayInfo", Int::class.javaPrimitiveType).invoke(manager, displayId)
                    ?: return null
            val cls: Class<*> = displayInfo.javaClass
            // width and height already take the rotation into account
            val width = cls.getDeclaredField("logicalWidth").getInt(displayInfo)
            val height = cls.getDeclaredField("logicalHeight").getInt(displayInfo)
            val rotation = cls.getDeclaredField("rotation").getInt(displayInfo)
            val layerStack = cls.getDeclaredField("layerStack").getInt(displayInfo)
            cls.getDeclaredField("flags").getInt(displayInfo)
            DisplayInfo(Size(width, height), rotation, layerStack)
        } catch (e: Exception) {
            throw AssertionError(e)
        }
    }

}