package com.tsbot.android

object ProtocolBridge {
    init {
        System.loadLibrary("tsbot_protocol")
    }

    private external fun nativeEncodeFrame(opcode: Int, payload: ByteArray): ByteArray
    private external fun nativeDecodeStream(wire: ByteArray): Array<ByteArray>

    fun encodeFrame(opcode: Int, payload: ByteArray): ByteArray = nativeEncodeFrame(opcode, payload)

    /** Returns Pair(list of complete frames, number of bytes consumed from start of wire). */
    fun decodeStream(wire: ByteArray): Pair<List<ByteArray>, Int> {
        val raw = nativeDecodeStream(wire)
        val consumedBytes = raw[0]
        val consumed = (consumedBytes[0].toInt() and 0xFF) or
            ((consumedBytes[1].toInt() and 0xFF) shl 8) or
            ((consumedBytes[2].toInt() and 0xFF) shl 16) or
            ((consumedBytes[3].toInt() and 0xFF) shl 24)
        val frames = raw.drop(1)
        return Pair(frames, consumed)
    }
}
