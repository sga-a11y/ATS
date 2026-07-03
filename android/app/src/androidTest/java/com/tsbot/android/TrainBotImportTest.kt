package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertNotNull

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
}
