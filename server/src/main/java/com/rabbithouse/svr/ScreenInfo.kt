package com.rabbithouse.svr

import android.graphics.Rect

class ScreenInfo(
    /**
     * Device (physical) size, possibly cropped
     */
    val contentRect // device size, possibly cropped
    : Rect,
    /**
     * Video size, possibly smaller than the device size, already taking the device rotation and crop into account.
     *
     *
     * However, it does not include the locked video orientation.
     */
    val unlockedVideoSize: Size
) {

    /**
     * Return the video size as if locked video orientation was not set.
     *
     * @return the unlocked video size
     */

    /**
     * Return the actual video size if locked video orientation is set.
     *
     * @return the actual video size
     */
    val videoSize: Size
        get() = if (videoRotation % 2 == 0) {
            unlockedVideoSize
        } else unlockedVideoSize.rotate()

    /**
     * Return the rotation to apply to the device rotation to get the requested locked video orientation
     *
     * @return the rotation offset
     */
    private val videoRotation: Int
        get() = 0

    /**
     * Return the rotation to apply to the requested locked video orientation to get the device rotation
     *
     * @return the (reverse) rotation offset
     */
    val reverseVideoRotation: Int
        get() = 0

    companion object {
        fun computeScreenInfo(displayInfo: DisplayInfo): ScreenInfo {
            val deviceSize = displayInfo.size
            val contentRect = Rect(0, 0, deviceSize.width, deviceSize.height)
            val videoSize = computeVideoSize(contentRect.width(), contentRect.height())
            return ScreenInfo(contentRect, videoSize)
        }

        private fun computeVideoSize(w: Int, h: Int): Size {
            // Compute the video size and the padding of the content inside this video.
            // Principle:
            // - scale down the great side of the screen to maxSize (if necessary);
            // - scale down the other side so that the aspect ratio is preserved;
            // - round this value to the nearest multiple of 8 (H.264 only accepts multiples of 8)
            // in case it's not a multiple of 8
            return Size(w and 7.inv(), h and 7.inv())
        }

    }

}