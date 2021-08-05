package com.rabbithouse.svr

import java.util.*

class Size(val width: Int, val height: Int) {

    fun rotate(): Size {
        return Size(height, width)
    }

    override fun equals(other: Any?): Boolean {
        if (this === other) {
            return true
        }
        if (other == null || javaClass != other.javaClass) {
            return false
        }
        val size = other as Size
        return width == size.width && height == size.height
    }

    override fun hashCode(): Int {
        return Objects.hash(width, height)
    }

    override fun toString(): String {
        return "Size{width=$width, height=$height}"
    }

}