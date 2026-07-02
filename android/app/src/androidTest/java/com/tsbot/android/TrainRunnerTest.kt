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
class TrainRunnerTest {
    @Before
    fun setup() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(ctx))
    }

    /**
     * Chaquopy 16.0.0 khong ho tro goi truc tiep mot Java/Kotlin lambda tuy y qua cu phap
     * Python obj(...) (khong co proxy tu dong cho SAM interface thanh __call__). Vi vay test
     * nay goi ham thuan Python train_bot.train_runner.run_train_sync_for_test(), ham nay tu
     * tao callback bang Python roi goi run_train() thuc su - van di qua CHINH XAC code path
     * san xuat (login that bai -> on_status("error", ...) -> return), chi khac o cho callback
     * duoc dinh nghia phia Python thay vi proxy tu Kotlin.
     */
    @Test
    fun invalidLoginReportsErrorNotCrash() {
        val py = Python.getInstance()
        val mod = py.getModule("train_bot.train_runner")
        val result = mod.callAttr(
            "run_train_sync_for_test",
            "invalid_user_xyz", "wrong_pw", "1.2.3.4", 1
        )
        assertEquals("error", result.toString())
    }
}
