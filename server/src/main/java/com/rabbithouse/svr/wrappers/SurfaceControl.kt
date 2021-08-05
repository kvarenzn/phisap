package com.rabbithouse.svr.wrappers

import android.annotation.SuppressLint
import android.graphics.Rect
import android.os.Build
import android.os.IBinder
import android.view.Surface
import com.rabbithouse.svr.Ln.e
import java.lang.reflect.InvocationTargetException
import java.lang.reflect.Method

@SuppressLint("PrivateApi")
object SurfaceControl {
    private val CLASS: Class<*> = try {
        Class.forName("android.view.SurfaceControl")
    } catch (e: ClassNotFoundException) {
        throw AssertionError(e)
    }

    fun createDisplay(name: String, secure: Boolean): IBinder {
        return (try {
            CLASS.getMethod("createDisplay", String::class.java, Boolean::class.javaPrimitiveType).invoke(null, name, secure)
        } catch (e: Exception) {
            throw AssertionError(e)
        }) as IBinder
    }

    fun destroyDisplay(display: IBinder) {
        try {
            CLASS.getMethod("destroyDisplay", IBinder::class.java).invoke(display)
        } catch (e: Exception) {
            throw AssertionError(e)
        }
    }

    fun openTransaction() {
        try {
            CLASS.getMethod("openTransaction").invoke(null)
        } catch (e: Exception) {
            e(e.stackTraceToString())
            throw AssertionError(e)
        }
    }

    fun setDisplaySurface(displayToken: IBinder, surface: Surface) {
        try {
            CLASS.getMethod("setDisplaySurface", IBinder::class.java, Surface::class.java).invoke(null, displayToken, surface)
        } catch (e: Exception) {
            throw AssertionError(e)
        }
    }

    fun setDisplayProjection(displayToken: IBinder, orientation: Int, layerStackRect: Rect, displayRect: Rect) {
        try {
            CLASS.getMethod("setDisplayProjection", IBinder::class.java, Int::class.javaPrimitiveType, Rect::class.java, Rect::class.java).invoke(null, displayToken, orientation, layerStackRect, displayRect)
        } catch (e: Exception) {
            throw AssertionError(e)
        }
    }

    fun setDisplayLayerStack(displayToken: IBinder, layerStack: Int) {
        try {
            CLASS.getMethod("setDisplayLayerStack", IBinder::class.java, Int::class.javaPrimitiveType).invoke(null, displayToken, layerStack)
        } catch (e: Exception) {
            throw AssertionError(e)
        }
    }

    fun closeTransaction() {
        try {
            CLASS.getMethod("closeTransaction").invoke(null)
        } catch (e: Exception) {
            throw AssertionError(e)
        }
    }
}