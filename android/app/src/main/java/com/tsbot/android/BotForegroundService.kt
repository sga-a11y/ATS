package com.tsbot.android

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.IBinder
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update

/**
 * Chay nhieu account train song song, moi account 1 thread rieng goi vao
 * train_bot.train_runner.run_train qua Chaquopy. Trang thai tung account duoc
 * publish qua StateFlow de UI observe.
 */
class BotForegroundService : Service() {
    private val binder = LocalBinder()

    // THREAD-SAFETY: startAccount()/stopAccount() duoc goi tu main/UI thread, trong khi
    // shouldStop.call() (doc stopFlags) chay tren tung account-thread rieng, va finally
    // block (xoa runningThreads) cung chay tren account-thread do. Vay la ghi tu UI thread
    // + doc/ghi tu N account-thread cung luc -> mutableMapOf thuong KHONG an toan (co the
    // ConcurrentModificationException hoac lost update khi nhieu account start/stop gan
    // nhau). Dung ConcurrentHashMap thay vi Collections.synchronizedMap vi day chi la cac
    // thao tac put/remove/get don le (khong can lock ca map cho compound action), va
    // ConcurrentHashMap cho doc khong block (phu hop voi shouldStop.call() bi poll lien tuc
    // trong vong lap train_runner).
    private val runningThreads = ConcurrentHashMap<String, Thread>()
    private val stopFlags = ConcurrentHashMap<String, Boolean>()

    private val _status = MutableStateFlow<Map<String, AccountStatus>>(emptyMap())
    val status: StateFlow<Map<String, AccountStatus>> = _status

    inner class LocalBinder : Binder() {
        fun getService(): BotForegroundService = this@BotForegroundService
    }

    override fun onBind(intent: Intent): IBinder = binder

    override fun onCreate() {
        super.onCreate()
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        startForeground(1, buildNotification())
    }

    private fun buildNotification(): Notification {
        val channelId = "tsbot_service"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(channelId, "aTSBot", NotificationManager.IMPORTANCE_LOW)
            (getSystemService(NotificationManager::class.java)).createNotificationChannel(channel)
        }
        return Notification.Builder(this, channelId)
            .setContentTitle("aTSBot dang chay")
            .setSmallIcon(android.R.drawable.ic_media_play)
            .build()
    }

    fun startAccount(account: Account, serverIp: String, serverId: Int, runMode: String, cityKey: String) {
        // TOCTOU: KHONG dung "if containsKey(...) return" roi put rieng - 2 lan goi
        // startAccount() gan nhau (vd double-tap nut Start tren UI) co the ca 2 deu
        // qua check TRUOC khi ben nao kip put, tao 2 Thread cung chay cho 1 username,
        // de len stopFlags/runningThreads cua nhau. putIfAbsent la atomic: tao Thread
        // TRUOC nhung CHI .start() neu putIfAbsent tra ve null (chua co ai giu cho slot
        // nay); neu da co (tra ve non-null) -> bo qua, khong start them.
        stopFlags[account.username] = false
        val thread = Thread {
            try {
                val module = Python.getInstance().getModule("train_bot.train_runner")
                val shouldStop = PyObject.fromJava(object {
                    fun call(): Boolean = stopFlags[account.username] == true
                })
                val onStatus = PyObject.fromJava(object {
                    fun call(state: String, hp: PyObject?, sp: PyObject?, hpMax: PyObject?, spMax: PyObject?, msg: String) {
                        _status.update {
                            it + (account.username to AccountStatus(
                                state = RunState.valueOf(state.uppercase()),
                                hp = hp?.toInt(),
                                sp = sp?.toInt(),
                                hpMax = hpMax?.toInt(),
                                spMax = spMax?.toInt(),
                                message = msg,
                            ))
                        }
                    }
                })
                module.callAttr(
                    "run_train", account.username, account.password, serverIp, serverId,
                    runMode, cityKey, shouldStop, onStatus,
                )
            } catch (e: Exception) {
                _status.update {
                    it + (account.username to AccountStatus(RunState.ERROR, message = e.message ?: "loi khong ro"))
                }
            } finally {
                runningThreads.remove(account.username)
                stopFlags.remove(account.username)
            }
        }
        if (runningThreads.putIfAbsent(account.username, thread) != null) return
        thread.start()
    }

    fun stopAccount(username: String) {
        stopFlags[username] = true
    }

    fun stopAll() {
        runningThreads.keys.toList().forEach { stopFlags[it] = true }
    }

    override fun onDestroy() {
        stopAll()
        super.onDestroy()
    }
}
