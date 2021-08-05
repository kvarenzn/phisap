package com.rabbithouse.svr.wrappers

import android.annotation.SuppressLint
import android.os.IBinder
import android.os.IInterface
import java.lang.reflect.Method

@SuppressLint("PrivateApi,DiscouragedPrivateApi")
class ServiceManager {
    private var getServiceMethod: Method? = null
    var displayManager: DisplayManager? = null
        get() {
            if (field == null) {
                field = DisplayManager(
                    getService(
                        "display",
                        "android.hardware.display.IDisplayManager"
                    )
                )
            }
            return field
        }
        private set

    var inputManager: InputManager? = null
        get() {
            if (field == null) {
                field = InputManager(getService("input", "android.hardware.input.IInputManager"))
            }
            return field
        }
        private set


    private fun getService(service: String, type: String): IInterface {
        return try {
            val binder = getServiceMethod!!.invoke(null, service) as IBinder
            val asInterfaceMethod =
                Class.forName("$type\$Stub").getMethod("asInterface", IBinder::class.java)
            asInterfaceMethod.invoke(null, binder) as IInterface
        } catch (e: Exception) {
            throw AssertionError(e)
        }
    }

    companion object {
        const val PACKAGE_NAME = "com.android.shell"
        const val USER_ID = 0
    }

    init {
        getServiceMethod = try {
            Class.forName("android.os.ServiceManager")
                .getDeclaredMethod("getService", String::class.java)
        } catch (e: Exception) {
            throw AssertionError(e)
        }
    }
}