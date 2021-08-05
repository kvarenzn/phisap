package com.rabbithouse.svr

import android.util.Log

/**
 * Log both to Android logger (so that logs are visible in "adb logcat") and standard output/error (so that they are visible in the terminal
 * directly).
 */
object Ln {
    private const val TAG = "phisap"
    private const val PREFIX = "[server] "
    private var threshold = Level.INFO

    /**
     * Initialize the log level.
     *
     *
     * Must be called before starting any new thread.
     *
     * @param level the log level
     */
    fun initLogLevel(level: Level) {
        threshold = level
    }

    private fun isEnabled(level: Level): Boolean {
        return level.ordinal >= threshold.ordinal
    }

    fun d(message: String) {
        if (isEnabled(Level.DEBUG)) {
            Log.d(TAG, message)
            println(PREFIX + "DEBUG: " + message)
        }
    }

    fun i(message: String) {
        if (isEnabled(Level.INFO)) {
            Log.i(TAG, message)
            println(PREFIX + "INFO: " + message)
        }
    }

    fun w(message: String) {
        if (isEnabled(Level.WARN)) {
            Log.w(TAG, message)
            println(PREFIX + "WARN: " + message)
        }
    }

    @kotlin.jvm.JvmStatic
    @JvmOverloads
    fun e(message: String, throwable: Throwable? = null) {
        if (isEnabled(Level.ERROR)) {
            Log.e(TAG, message, throwable)
            println(PREFIX + "ERROR: " + message)
            throwable?.printStackTrace()
        }
    }

    enum class Level {
        DEBUG, INFO, WARN, ERROR
    }
}