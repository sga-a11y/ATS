package com.tsbot.android

import android.app.ActivityManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.os.Process
import android.os.SystemClock
import androidx.core.content.ContextCompat
import java.util.concurrent.Executors

/** Runs outside the bot process, so no old Python threads survive the handoff. */
class CoreRestartService : Service() {
    private val executor = Executors.newSingleThreadExecutor()
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val channel = "core_restart"
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(channel, "Cập nhật core", NotificationManager.IMPORTANCE_LOW))
        startForeground(2, Notification.Builder(this, channel)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle("aTSBot đang tự áp dụng core mới").build())
        val oldPid = intent?.getIntExtra("old_pid", -1) ?: -1
        val showUi = intent?.getBooleanExtra("show_ui", false) ?: false
        executor.execute {
            try {
                val manager = getSystemService(ActivityManager::class.java)
                val old = manager.runningAppProcesses?.firstOrNull {
                    it.pid == oldPid && it.uid == Process.myUid() && it.processName == packageName
                }
                check(oldPid != Process.myPid()) { "Không xác định được tiến trình bot cũ" }
                // Old process already gone (crash/system kill): nothing to kill, the bot must still restart.
                if (old != null) {
                    SystemClock.sleep(500)
                    Process.killProcess(oldPid)
                    val deadline = SystemClock.elapsedRealtime() + 5000
                    while (manager.runningAppProcesses?.any { it.pid == oldPid } == true &&
                        SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(50)
                    check(manager.runningAppProcesses?.none { it.pid == oldPid } != false)
                }
                ContextCompat.startForegroundService(this, Intent(this, BotForegroundService::class.java))
                // Newer Android may refuse to open an activity from here; the bot runs regardless
                // and its notification still opens the app.
                if (showUi) try {
                    startActivity(Intent(this, MainActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
                } catch (e: Exception) { android.util.Log.w("aTSBot", "could not reopen the app", e) }
            } catch (e: Exception) {
                android.util.Log.e("aTSBot", "core process restart failed", e)
            } finally {
                if (stopSelfResult(startId)) stopForeground(STOP_FOREGROUND_REMOVE)
            }
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() { executor.shutdown(); super.onDestroy() }
}
