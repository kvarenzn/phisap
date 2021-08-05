package com.rabbithouse.svr

import kotlin.experimental.and

object StringUtils {
    fun getUtf8TruncationIndex(utf8: ByteArray, maxLength: Int): Int {
        var len = utf8.size
        if (len <= maxLength) {
            return len
        }
        len = maxLength
        // see UTF-8 encoding <https://en.wikipedia.org/wiki/UTF-8#Description>
        while (utf8[len] and 0x80.toByte() != 0.toByte() && utf8[len] and 0xc0.toByte() != 0xc0.toByte()) {
            // the next byte is not the start of a new UTF-8 codepoint
            // so if we would cut there, the character would be truncated
            len--
        }
        return len
    }
}