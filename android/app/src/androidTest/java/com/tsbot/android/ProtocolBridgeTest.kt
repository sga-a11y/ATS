package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProtocolBridgeTest {

    private val wireBytes = byteArrayOf(
        0x6d.toByte(), 0x3c, 0xbc.toByte(), 0xad.toByte(), 0xad.toByte(), 0xad.toByte(),
        0x9f.toByte(), 0xac.toByte(), 0xad.toByte(), 0xae.toByte(), 0xaf.toByte(),
        0xac.toByte(), 0xac.toByte(), 0x4e, 0x83.toByte(), 0xaa.toByte(), 0x04
    )
    private val plaintext = byteArrayOf(
        0xc0.toByte(), 0x91.toByte(), 0x11, 0x00, 0x00, 0x00, 0x32, 0x01,
        0x00, 0x03, 0x02, 0x01, 0x01, 0xe3.toByte(), 0x2e, 0x07, 0xa9.toByte()
    )

    @Test
    fun decodeStream_parsesSingleFrame() {
        val result = ProtocolBridge.decodeStream(wireBytes)
        assertArrayEquals(
            arrayOf(plaintext.toList()),
            result.frames.map { it.toList() }.toTypedArray()
        )
        assertEquals(wireBytes.size, result.consumed)
    }

    @Test
    fun encodeFrame_matchesKnownWireBytes() {
        val payload = plaintext.copyOfRange(7, plaintext.size)
        val encoded = ProtocolBridge.encodeFrame(0x32, payload)
        assertArrayEquals(wireBytes, encoded)
    }
}
