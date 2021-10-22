package com.rabbithouse.svr

import java.io.IOException

object Server {

    @Throws(Exception::class)
    @JvmStatic
    fun main(args: Array<String>) {
        Ln.initLogLevel(Ln.Level.INFO)
        val device = Device()
        try {
            DesktopConnection.open(device).use { connection ->
                val controller = Controller(device, connection)
                try {
                    Ln.i("主控制进程已启动")
                    controller.control()
                } catch (e: IOException) {
                    Ln.i("主控制进程已终止")
                }
            }
        } catch (e: Exception) {
            Ln.d(e.toString())
        }
    }
}
