package com.rabbithouse.svr

import java.util.*

class Point(val x: Int, val y: Int) {

    override fun equals(other: Any?): Boolean {
        if (this === other) {
            return true
        }
        if (other == null || javaClass != other.javaClass) {
            return false
        }
        val point = other as Point
        return x == point.x && y == point.y
    }

    override fun hashCode(): Int {
        return Objects.hash(x, y)
    }

    override fun toString(): String {
        return "Point{x=$x, y=$y}"
    }

}