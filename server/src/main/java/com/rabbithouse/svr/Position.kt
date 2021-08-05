package com.rabbithouse.svr

import java.util.*

class Position(val point: Point, val screenSize: Size?) {

    constructor(x: Int, y: Int, screenWidth: Int, screenHeight: Int) : this(Point(x, y), Size(screenWidth, screenHeight))

    fun rotate(rotation: Int): Position {
        screenSize!!
        return when (rotation) {
            1 -> Position(Point(screenSize.height - point.y, point.x), screenSize.rotate())
            2 -> Position(Point(screenSize.width - point.x, screenSize.height - point.y), screenSize)
            3 -> Position(Point(point.y, screenSize.width - point.x), screenSize.rotate())
            else -> this
        }
    }

    override fun equals(other: Any?): Boolean {
        if (this === other) {
            return true
        }
        if (other == null || javaClass != other.javaClass) {
            return false
        }
        val position = other as Position
        return point == position.point && screenSize == position.screenSize
    }

    override fun hashCode(): Int {
        return Objects.hash(point, screenSize)
    }

    override fun toString(): String {
        return "Position{point=$point, screenSize=$screenSize}"
    }

}