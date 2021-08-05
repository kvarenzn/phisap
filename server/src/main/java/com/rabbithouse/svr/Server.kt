package com.rabbithouse.svr

import android.graphics.Rect
import java.io.IOException
import kotlin.math.min
import kotlin.math.max

object Server {

    private lateinit var streamingThread: Thread

    @Throws(Exception::class)
    @JvmStatic
    fun main(args: Array<String>) {
        Ln.initLogLevel(Ln.Level.INFO)
        val device = Device()
        val deviceHeight = device.screenInfo.videoSize.height
        val deviceWidth = device.screenInfo.videoSize.width
        try {
            DesktopConnection.open(device).use { connection ->
                val controller = Controller(device, connection)
                val width = 88
                val left = (deviceWidth - (deviceHeight / 9 * 16)) / 2 + 3
                val top = deviceHeight / 216
                val videoStreamer =
                    VideoStreamer(connection, device, Rect(left, top, left + width, top + width))
                streamingThread = startStreaming(videoStreamer)
                try {
                    Ln.i("主控制进程已启动")
                    controller.control()
                } catch (e: IOException) {
                    Ln.i("主控制进程已终止")
                } finally {
                    if (!streamingThread.isInterrupted) {
                        streamingThread.interrupt()
                    }
                }
            }
        } catch (e: Exception) {
            Ln.d(e.toString())
        }
    }

    fun stopStreaming() {
        streamingThread.interrupt()
        Ln.i("流式传输已终止")
    }

    private fun startStreaming(streamer: VideoStreamer): Thread {
        val thread = Thread {
            try {
                Ln.i("流式传输已启动")
                streamer.loop()
            } catch (e: Exception) {
                Ln.e("流式传输意外终止")
                Ln.e(e.stackTraceToString())
            }
        }
        thread.start()
        return thread
    }

}
