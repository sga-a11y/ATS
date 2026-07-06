package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue

@RunWith(AndroidJUnit4::class)
class TrainBotImportTest {
    @Before
    fun setup() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(ctx))
    }

    @Test
    fun importAllModulesNoError() {
        val py = Python.getInstance()
        assertNotNull(py.getModule("train_bot.config"))
        assertNotNull(py.getModule("train_bot.auth"))
        assertNotNull(py.getModule("train_bot.login"))
        assertNotNull(py.getModule("train_bot.state"))
        assertNotNull(py.getModule("train_bot.combat"))
        assertNotNull(py.getModule("train_bot.client"))
    }

    @Test
    fun vantieuRequestsLoadsNonEmpty() {
        val py = Python.getInstance()
        val config = py.getModule("train_bot.config")
        val enabled = config.get("VANTIEU_ENABLE")!!.toBoolean()
        assertTrue("VANTIEU_ENABLE phai la True (khop bot/config.py)", enabled)
        val requests = config.get("VANTIEU_REQUESTS")!!
        assertTrue("VANTIEU_REQUESTS phai load duoc du lieu that (khong rong)", requests.callAttr("__len__").toInt() > 0)
    }
}
