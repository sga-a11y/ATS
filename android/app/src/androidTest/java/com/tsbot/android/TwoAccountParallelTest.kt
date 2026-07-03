package com.tsbot.android

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.flow.first

/**
 * Test tich hop: 2 account chay song song that qua BotForegroundService.
 *
 * Test nay CAN 2 tai khoan game that hop le de chay - khong the tu dong hoa hoan toan
 * neu khong co credentials that. De tu chay test nay voi tai khoan cua ban:
 *
 * 1. Tao file: android/app/src/androidTest/assets/test_accounts.json
 *    Noi dung:
 *    {
 *      "acc1": { "username": "...", "password": "...", "server_key": "trieu_van" },
 *      "acc2": { "username": "...", "password": "...", "server_key": "trieu_van" }
 *    }
 *    (server_key phai la mot trong cac key trong Servers.ALL, xem Servers.kt)
 *
 * 2. File nay da duoc them vao .gitignore (khong commit mat khau that).
 *
 * 3. Chay: cd android && ./gradlew connectedDebugAndroidTest
 *
 * Neu file khong ton tai, test SKIP (Assume) thay vi FAIL.
 */
@RunWith(AndroidJUnit4::class)
class TwoAccountParallelTest {
    @Test
    fun twoAccountsRunConcurrentlyWithoutBlockingEachOther() {
        val ctx = InstrumentationRegistry.getInstrumentation().context
        val testAssets = try {
            JSONObject(ctx.assets.open("test_accounts.json").bufferedReader().readText())
        } catch (e: Exception) {
            null
        }
        assumeTrue(
            "Can file android/app/src/androidTest/assets/test_accounts.json (xem huong dan trong comment o dau file) de chay test nay",
            testAssets != null
        )

        val acc1 = Account(
            testAssets!!.getJSONObject("acc1").getString("username"),
            testAssets.getJSONObject("acc1").getString("password"),
        )
        val acc1ServerKey = testAssets.getJSONObject("acc1").getString("server_key")
        val acc2 = Account(
            testAssets.getJSONObject("acc2").getString("username"),
            testAssets.getJSONObject("acc2").getString("password"),
        )
        val acc2ServerKey = testAssets.getJSONObject("acc2").getString("server_key")

        val targetCtx = InstrumentationRegistry.getInstrumentation().targetContext
        val latch = CountDownLatch(1)
        var svc: BotForegroundService? = null
        val conn = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName, binder: IBinder) {
                svc = (binder as BotForegroundService.LocalBinder).getService()
                latch.countDown()
            }
            override fun onServiceDisconnected(name: ComponentName) {}
        }
        targetCtx.bindService(Intent(targetCtx, BotForegroundService::class.java), conn, Context.BIND_AUTO_CREATE)
        assertTrue("Service khong bind duoc trong 10s", latch.await(10, TimeUnit.SECONDS))

        val info1 = Servers.ALL[acc1ServerKey]!!
        val info2 = Servers.ALL[acc2ServerKey]!!
        try {
            svc!!.startAccount(acc1, info1.ip, info1.serverId, RunModes.STAND_STILL)
            svc!!.startAccount(acc2, info2.ip, info2.serverId, RunModes.STAND_STILL)

            // 30s: du cho 2 login HTTP that + ket noi TCP game song song (thuong ~10-15s/acc
            // theo quan sat thu cong), nhan doi lam bien do de tranh flaky tren mang cham.
            val deadline = System.currentTimeMillis() + 30000
            var bothRunning = false
            while (System.currentTimeMillis() < deadline) {
                val statusMap = runBlocking { svc!!.status.first() }
                if (statusMap[acc1.username]?.state == RunState.RUNNING &&
                    statusMap[acc2.username]?.state == RunState.RUNNING
                ) {
                    bothRunning = true
                    break
                }
                Thread.sleep(1000)
            }
            assertEquals(true, bothRunning)
        } finally {
            // LUON dung 2 account + unbind du test pass/fail/timeout - tranh de lai 2 ket noi
            // bot THAT chay ngam vo thoi han neu assertion o tren fail giua chung.
            svc?.stopAccount(acc1.username)
            svc?.stopAccount(acc2.username)
            targetCtx.unbindService(conn)
        }
    }
}
