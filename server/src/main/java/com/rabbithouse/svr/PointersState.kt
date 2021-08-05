package com.rabbithouse.svr

import android.view.MotionEvent.PointerCoords
import android.view.MotionEvent.PointerProperties
import java.util.*

class PointersState {
    private val pointers: MutableList<Pointer> = ArrayList()
    private fun indexOf(id: Long): Int {
        for (i in pointers.indices) {
            val pointer = pointers[i]
            if (pointer.id == id) {
                return i
            }
        }
        return -1
    }

    private fun isLocalIdAvailable(localId: Int): Boolean {
        for (i in pointers.indices) {
            val pointer = pointers[i]
            if (pointer.localId == localId) {
                return false
            }
        }
        return true
    }

    private fun nextUnusedLocalId(): Int {
        for (localId in 0 until MAX_POINTERS) {
            if (isLocalIdAvailable(localId)) {
                return localId
            }
        }
        return -1
    }

    operator fun get(index: Int): Pointer {
        return pointers[index]
    }

    fun getPointerIndex(id: Long): Int {
        val index = indexOf(id)
        if (index != -1) {
            // already exists, return it
            return index
        }
        if (pointers.size >= MAX_POINTERS) {
            // it's full
            return -1
        }
        // id 0 is reserved for mouse events
        val localId = nextUnusedLocalId()
        if (localId == -1) {
            throw AssertionError("pointers.size() < maxFingers implies that a local id is available")
        }
        val pointer = Pointer(id, localId)
        pointers.add(pointer)
        // return the index of the pointer
        return pointers.size - 1
    }

    /**
     * Initialize the motion event parameters.
     *
     * @param props  the pointer properties
     * @param coords the pointer coordinates
     * @return The number of items initialized (the number of pointers).
     */
    fun update(props: Array<PointerProperties?>, coords: Array<PointerCoords?>): Int {
        val count = pointers.size
        for (i in 0 until count) {
            val pointer = pointers[i]

            // id 0 is reserved for mouse events
            props[i]!!.id = pointer.localId
            val point = pointer.point!!
            coords[i]!!.x = point.x.toFloat()
            coords[i]!!.y = point.y.toFloat()
            coords[i]!!.pressure = pointer.pressure
        }
        cleanUp()
        return count
    }

    /**
     * Remove all pointers which are UP.
     */
    private fun cleanUp() {
        for (i in pointers.indices.reversed()) {
            val pointer = pointers[i]
            if (pointer.isUp) {
                pointers.removeAt(i)
            }
        }
    }

    companion object {
        const val MAX_POINTERS = 10
    }
}