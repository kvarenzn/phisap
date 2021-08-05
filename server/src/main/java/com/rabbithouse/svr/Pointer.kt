package com.rabbithouse.svr

class Pointer(
        /**
         * Pointer id as received from the client.
         */
        val id: Long,
        /**
         * Local pointer id, using the lowest possible values to fill the [PointerProperties][android.view.MotionEvent.PointerProperties].
         */
        val localId: Int) {

    var point: Point? = null
    var pressure = 0f
    var isUp = false

}