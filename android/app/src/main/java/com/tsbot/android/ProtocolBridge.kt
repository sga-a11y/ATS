package com.tsbot.android

object ProtocolBridge {
    init {
        System.loadLibrary("tsbot_protocol")
    }

    private external fun nativeEncodeFrame(opcode: Int, payload: ByteArray): ByteArray
    private external fun nativeDecodeStream(wire: ByteArray): Array<ByteArray>

    fun encodeFrame(opcode: Int, payload: ByteArray): ByteArray = nativeEncodeFrame(opcode, payload)
    fun decodeStream(wire: ByteArray): List<ByteArray> = nativeDecodeStream(wire).toList()
}
