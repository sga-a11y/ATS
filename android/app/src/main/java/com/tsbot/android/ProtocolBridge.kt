package com.tsbot.android

/**
 * Ket qua decodeStream. Dung data class voi getter kieu Java (getFrames()/getConsumed())
 * thay vi kotlin.Pair - Chaquopy khong proxy .first()/.second() cua Pair on dinh, nhung
 * getter kieu Java (tu 'val' data class) thi luon truy cap duoc tu Python.
 */
data class DecodeStreamResult(val frames: List<ByteArray>, val consumed: Int)

object ProtocolBridge {
    init {
        System.loadLibrary("tsbot_protocol")
    }

    private external fun nativeEncodeFrame(opcode: Int, payload: ByteArray): ByteArray
    private external fun nativeDecodeStream(wire: ByteArray): Array<ByteArray>

    fun encodeFrame(opcode: Int, payload: ByteArray): ByteArray = nativeEncodeFrame(opcode, payload)

    /** Returns (list of complete frames, number of bytes consumed from start of wire). */
    fun decodeStream(wire: ByteArray): DecodeStreamResult {
        val raw = nativeDecodeStream(wire)
        val consumedBytes = raw[0]
        val consumed = (consumedBytes[0].toInt() and 0xFF) or
            ((consumedBytes[1].toInt() and 0xFF) shl 8) or
            ((consumedBytes[2].toInt() and 0xFF) shl 16) or
            ((consumedBytes[3].toInt() and 0xFF) shl 24)
        val frames = raw.drop(1)
        return DecodeStreamResult(frames, consumed)
    }
}
