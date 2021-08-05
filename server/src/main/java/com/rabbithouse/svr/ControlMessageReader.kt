package com.rabbithouse.svr

import java.io.EOFException
import java.io.IOException
import java.io.InputStream
import java.nio.ByteBuffer
import kotlin.experimental.and

class ControlMessageReader {
    private val rawBuffer = ByteArray(MESSAGE_MAX_SIZE)
    private val buffer = ByteBuffer.wrap(rawBuffer)
    private val isFull: Boolean
        get() = buffer.remaining() == rawBuffer.size

    @Throws(IOException::class)
    fun readFrom(input: InputStream) {
        check(!isFull) { "Buffer full, call next() to consume" }
        buffer.compact()
        val head = buffer.position()
        val r = input.read(rawBuffer, head, rawBuffer.size - head)
        if (r == -1) {
            throw EOFException("Controller socket closed")
        }
        buffer.position(head + r)
        buffer.flip()
    }

    operator fun next(): ControlMessage? {
        if (!buffer.hasRemaining()) {
            return null
        }
        val savedPosition = buffer.position()
        val msg: ControlMessage? = when (val type = buffer.get().toInt()) {
            ControlMessage.TYPE_INJECT_TOUCH_EVENT -> parseInjectTouchEvent()
            ControlMessage.TYPE_STOP_VIDEO_STREAMING -> ControlMessage.createEmpty(type)
            else -> {
                Ln.w("Unknown event type: $type")
                null
            }
        }
        if (msg == null) {
            // failure, reset savedPosition
            buffer.position(savedPosition)
        }
        return msg
    }

    private fun parseInjectTouchEvent(): ControlMessage? {
        if (buffer.remaining() < INJECT_TOUCH_EVENT_PAYLOAD_LENGTH) {
            return null
        }
        val action = toUnsigned(buffer.get())
        val pointerId = buffer.long
        val position = readPosition(buffer)
        // 16 bits fixed-point
        val pressureInt = toUnsigned(buffer.short)
        // convert it to a float between 0 and 1 (0x1p16f is 2^16 as float)
        val pressure = if (pressureInt == 0xffff) 1f else pressureInt / 65536f
        val buttons = buffer.int
        return ControlMessage.createInjectTouchEvent(action, pointerId, position, pressure, buttons)
    }

    companion object {
        const val INJECT_TOUCH_EVENT_PAYLOAD_LENGTH = 27
        private const val MESSAGE_MAX_SIZE = 1 shl 18 // 256k
        private fun readPosition(buffer: ByteBuffer): Position {
            val x = buffer.int
            val y = buffer.int
            val screenWidth = toUnsigned(buffer.short)
            val screenHeight = toUnsigned(buffer.short)
            return Position(x, y, screenWidth, screenHeight)
        }

        private fun toUnsigned(value: Short): Int {
            return (value and 0xffff.toShort()).toInt()
        }

        private fun toUnsigned(value: Byte): Int {
            return (value and 0xff.toByte()).toInt()
        }
    }

    init {
        // invariant: the buffer is always in "get" mode
        buffer.limit(0)
    }
}