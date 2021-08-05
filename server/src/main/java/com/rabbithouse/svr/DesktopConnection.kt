package com.rabbithouse.svr

import android.net.LocalSocket
import android.net.LocalSocketAddress
import java.io.*
import java.nio.charset.StandardCharsets

class DesktopConnection private constructor(private val controlSocket: LocalSocket) : Closeable {
    private val controlInputStream: InputStream = controlSocket.inputStream
    val controlFd: FileDescriptor
        get() = controlSocket.fileDescriptor
    private val reader = ControlMessageReader()

    @Throws(IOException::class)
    override fun close() {
        controlSocket.shutdownInput()
        controlSocket.shutdownOutput()
        controlSocket.close()
    }

    @Throws(IOException::class)
    private fun send(deviceName: String, width: Int, height: Int) {
        val buffer = ByteArray(DEVICE_NAME_FIELD_LENGTH + 4)
        val deviceNameBytes = deviceName.toByteArray(StandardCharsets.UTF_8)
        val len = StringUtils.getUtf8TruncationIndex(deviceNameBytes, DEVICE_NAME_FIELD_LENGTH - 1)
        System.arraycopy(deviceNameBytes, 0, buffer, 0, len)

        buffer[DEVICE_NAME_FIELD_LENGTH] = (width shr 8).toByte()
        buffer[DEVICE_NAME_FIELD_LENGTH + 1] = width.toByte()
        buffer[DEVICE_NAME_FIELD_LENGTH + 2] = (height shr 8).toByte()
        buffer[DEVICE_NAME_FIELD_LENGTH + 3] = height.toByte()
        IO.writeFully(controlFd, buffer, 0, buffer.size)
    }

    @Throws(IOException::class)
    fun receiveControlMessage(): ControlMessage {
        var msg = reader.next()
        while (msg == null) {
            reader.readFrom(controlInputStream)
            msg = reader.next()
        }
        return msg
    }

    companion object {
        private const val DEVICE_NAME_FIELD_LENGTH = 64
        private const val SOCKET_NAME = "phisap"

        @Throws(IOException::class)
        private fun connect(): LocalSocket {
            val localSocket = LocalSocket()
            localSocket.connect(LocalSocketAddress(SOCKET_NAME))
            return localSocket
        }

        @Throws(IOException::class)
        fun open(device: Device): DesktopConnection {
            val controlSocket: LocalSocket = try {
                connect()
            } catch (e: IOException) {
                throw e
            } catch (e: RuntimeException) {
                throw e
            }
            val connection = DesktopConnection(controlSocket)
            val videoSize = device.screenInfo.videoSize
            connection.send(Device.deviceName, videoSize.width, videoSize.height)
            return connection
        }
    }

}