package com.rabbithouse.svr

import android.annotation.TargetApi
import android.graphics.Rect
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.os.Build
import android.os.Looper
import com.rabbithouse.svr.wrappers.SurfaceControl
import java.nio.ByteBuffer

class VideoStreamer(private val connection: DesktopConnection?, private val device: Device, crop: Rect = Rect()) {
    private var startStreaming = true

    private val headerBuffer = ByteBuffer.allocate(12)
    private var ptsOrigin: Long = 0

    private val crop = if (crop.isEmpty) {
        Size(device.screenInfo.videoSize.width, device.screenInfo.videoSize.height)
    } else {
        Size(crop.width(), crop.height())
    }.run {
        Rect(crop.left, crop.top, crop.left + (width and 7.inv()), crop.top + (height and 7.inv()))
    }

    @TargetApi(Build.VERSION_CODES.O)
    fun loop() {
//        Looper.prepareMainLooper()
        var running: Boolean
        do {
            val screenInfo = device.screenInfo
            val size = screenInfo.videoSize

            val display = SurfaceControl.createDisplay("phisap", true)

            val codec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
            val format = MediaFormat.createVideoFormat("video/avc", crop.width(), crop.height())
            format.setInteger(MediaFormat.KEY_BIT_RATE, 8000000)
            format.setString(MediaFormat.KEY_MIME, MediaFormat.MIMETYPE_VIDEO_AVC)
            format.setInteger(MediaFormat.KEY_FRAME_RATE, 60)
            format.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface)
            format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 10)
            format.setLong(MediaFormat.KEY_REPEAT_PREVIOUS_FRAME_AFTER, 100000) // µs

            codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)

            val surface = codec.createInputSurface()

            SurfaceControl.openTransaction()
            SurfaceControl.setDisplaySurface(display, surface)
            SurfaceControl.setDisplayProjection(display, 0, crop, Rect(0, 0, size.width, size.height))
            SurfaceControl.setDisplayLayerStack(display, device.layerStack)
            SurfaceControl.closeTransaction()

            codec.start()
            try {
                val bufferInfo = MediaCodec.BufferInfo()
                var eof = false
                while (!eof && startStreaming) {
                    val outputBufferId = codec.dequeueOutputBuffer(bufferInfo, -1)
                    eof = (bufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0
                    try {
                        if (outputBufferId >= 0) {
                            val codecBuffer = codec.getOutputBuffer(outputBufferId)!!
                            headerBuffer.clear()

                            val pts = if ((bufferInfo.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) {
                                -1
                            } else {
                                bufferInfo.presentationTimeUs - if (ptsOrigin == 0.toLong()) {
                                    ptsOrigin = bufferInfo.presentationTimeUs
                                    ptsOrigin
                                } else {
                                    ptsOrigin
                                }
                            }
                            headerBuffer.putLong(pts)
                            headerBuffer.putInt(codecBuffer.remaining())
                            headerBuffer.flip()
                            connection!!.controlFd.also {
                                IO.writeFully(it, headerBuffer)
                                IO.writeFully(it, codecBuffer)
                            }
                        }
                    } finally {
                        if (outputBufferId >= 0) {
                            codec.releaseOutputBuffer(outputBufferId, false)
                        }
                    }
                }
                running = !eof
            } finally {
                SurfaceControl.destroyDisplay(display)
                codec.release()
                surface.release()
            }

        } while (running && startStreaming)

        while (true) {
            Thread.sleep(1000)
        }
    }
}