package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Assert.assertArrayEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PythonBridgeTest {

    @Before
    fun setUp() {
        if (!Python.isStarted()) {
            val ctx = InstrumentationRegistry.getInstrumentation().targetContext
            Python.start(AndroidPlatform(ctx))
        }
    }

    @Test
    fun pythonEncodeFrame_matchesNativeResult() {
        val py = Python.getInstance()
        val module = py.getModule("bot_native_bridge")
        val payload = byteArrayOf(0x01, 0x00, 0x03, 0x02, 0x01, 0x01, 0xe3.toByte(), 0x2e, 0x07, 0xa9.toByte())
        val fromPython = module.callAttr("encode_frame", 0x32, payload).toJava(ByteArray::class.java)
        val fromKotlin = ProtocolBridge.encodeFrame(0x32, payload)
        assertArrayEquals(fromKotlin, fromPython)
    }
}
