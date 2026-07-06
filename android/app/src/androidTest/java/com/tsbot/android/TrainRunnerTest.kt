package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.chaquo.python.Python
import com.chaquo.python.PyObject
import com.chaquo.python.android.AndroidPlatform
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import java.util.concurrent.atomic.AtomicReference

/** Doi tuong Kotlin THAT dung phuong thuc "call" - dung day de kiem tra Chaquopy that su
 * proxy va Python goi duoc .call(...) tren no, KHONG chi gia lap bang Python (xem
 * train_runner.py module docstring ve quy uoc nay). */
class KotlinStatusCallback(private val ref: AtomicReference<String>) {
    fun call(state: String, hp: PyObject?, sp: PyObject?, hpMax: PyObject?, spMax: PyObject?, message: String) {
        ref.set(state)
    }
}

class KotlinShouldStopCallback {
    fun call(): Boolean = true
}

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

    /** Xac nhan THAT rang phia Kotlin co the truyen 1 doi tuong that vao Python va Python
     * goi duoc .call(...) tren no dung nhu quy uoc train_runner.py yeu cau - day la dieu
     * kien tien quyet de BotForegroundService (task sau) noi Kotlin<->Python that. */
    @Test
    fun kotlinCallbackObjectIsCallableFromPython() {
        val py = Python.getInstance()
        val mod = py.getModule("train_bot.train_runner")
        val lastState = AtomicReference<String>()
        val onStatus = PyObject.fromJava(KotlinStatusCallback(lastState))
        val shouldStop = PyObject.fromJava(KotlinShouldStopCallback())
        mod.callAttr(
            "run_train", "invalid_user_xyz", "wrong_pw", "1.2.3.4", 1,
            RunModes.STAND_STILL, Cities.ALL.keys.first(), shouldStop, onStatus,
        )
        assertEquals("error", lastState.get())
    }

    /**
     * claim_mail/claim_online_gifts/do_van_tieu (train_bot/client.py) luu trang thai vao
     * gift_state.json/daily_state.json/vantieu_state.json bang DUONG DAN TUONG DOI (khong
     * prefix thu muc) - xac nhan CWD cua tien trinh Python (Chaquopy) tren Android thuc su
     * ghi duoc, de cac ham nay luu "da nhan" ben ngoai session hien tai.
     */
    @Test
    fun cwdIsWritableOnAndroid() {
        val py = Python.getInstance()
        val os = py.getModule("os")
        val cwd = os.callAttr("getcwd").toString()
        val testFile = java.io.File(cwd, "cwd_write_test.tmp")
        testFile.writeText("test")
        assertTrue("CWD ($cwd) phai ghi duoc de claim_mail/claim_online_gifts/do_van_tieu luu trang thai dung", testFile.exists())
        testFile.delete()
    }

    /**
     * Xac nhan _apply_cmd dinh tuyen dung lenh "giftcode" toi GameClient.redeem_giftcode()
     * (khong can ket noi mang that) - qua ham test-only apply_giftcode_cmd_for_test() dung
     * _FakeClientForTest trong train_runner.py.
     */
    @Test
    fun applyGiftcodeCommandCallsRedeemGiftcode() {
        val py = Python.getInstance()
        val mod = py.getModule("train_bot.train_runner")
        val result = mod.callAttr("apply_giftcode_cmd_for_test", "TESTCODE123").toString()
        assertTrue("Message phai chua ma giftcode da nhap", result.contains("TESTCODE123"))
    }
}
