package com.tsbot.android

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class BotForegroundServiceTest {
    @Test
    fun invalidAccountReachesErrorState() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val latch = CountDownLatch(1)
        var boundService: BotForegroundService? = null
        val conn = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName, binder: IBinder) {
                boundService = (binder as BotForegroundService.LocalBinder).getService()
                latch.countDown()
            }
            override fun onServiceDisconnected(name: ComponentName) {}
        }
        val intent = Intent(ctx, BotForegroundService::class.java)
        ctx.bindService(intent, conn, Context.BIND_AUTO_CREATE)
        latch.await(10, TimeUnit.SECONDS)

        val svc = boundService!!
        svc.startAccount(Account("invalid_xyz", "wrong"), "103.82.28.98", 1)

        var finalState: RunState? = null
        val deadline = System.currentTimeMillis() + 20000
        while (System.currentTimeMillis() < deadline) {
            val s = runBlocking { svc.status.first() }["invalid_xyz"]
            if (s?.state == RunState.ERROR) { finalState = s.state; break }
            Thread.sleep(500)
        }
        assertEquals(RunState.ERROR, finalState)
        ctx.unbindService(conn)
    }
}
