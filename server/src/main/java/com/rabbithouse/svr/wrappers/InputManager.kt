package com.rabbithouse.svr.wrappers

import android.os.IInterface
import android.view.InputEvent
import com.rabbithouse.svr.Ln.e
import java.lang.reflect.InvocationTargetException
import java.lang.reflect.Method

class InputManager(private val manager: IInterface) {
    @get:Throws(NoSuchMethodException::class)
    private var injectInputEventMethod: Method? = null
        get() {
            if (field == null) {
                field = manager.javaClass.getMethod("injectInputEvent", InputEvent::class.java, Int::class.javaPrimitiveType)
            }
            return field
        }

    fun injectInputEvent(inputEvent: InputEvent?, mode: Int): Boolean {
        return try {
            val method = injectInputEventMethod
            method!!.invoke(manager, inputEvent, mode) as Boolean
        } catch (e: InvocationTargetException) {
            e("Could not invoke method", e)
            false
        } catch (e: IllegalAccessException) {
            e("Could not invoke method", e)
            false
        } catch (e: NoSuchMethodException) {
            e("Could not invoke method", e)
            false
        }
    }

    companion object {
        const val INJECT_INPUT_EVENT_MODE_ASYNC = 0

    }
}