package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertEquals

@RunWith(AndroidJUnit4::class)
class TrainBotProtocolTest {
    @Before
    fun setup() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(ctx))
    }

    @Test
    fun encodeDecodeRoundTripThroughShim() {
        val py = Python.getInstance()
        val mod = py.getModule("train_bot.protocol")
        val encoded = mod.callAttr("encode", 0x32, "AB".toByteArray())
        val wire = encoded.toJava(ByteArray::class.java)
        val result = mod.callAttr("parse_stream", wire)
        val list = result.asList()
        val frames = list[0].asList()
        val consumed = list[1].toInt()
        assertEquals(1, frames.size)
        assertEquals(wire.size, consumed)
        val opcode = frames[0].asList()[0].toInt()
        assertEquals(0x32, opcode)
    }
}
