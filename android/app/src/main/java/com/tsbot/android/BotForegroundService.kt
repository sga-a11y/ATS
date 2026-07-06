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
    // LENH LIVE cho tung account (doi kenh / teleport thanh) - UI ghi qua sendCommand(),
    // account-thread doc + xoa qua getCmd.call() (mirror cmd_gen ben PC). ConcurrentHashMap vi
    // ghi tu UI thread + doc/remove tu N account-thread.
    private val pendingCmd = ConcurrentHashMap<String, Array<Any>>()

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
                val getCmd = PyObject.fromJava(object {
                    // tra lenh dang cho (roi XOA - moi lenh chi thuc thi 1 lan) hoac null
                    fun call(): Array<Any>? = pendingCmd.remove(account.username)
                })
                module.callAttr(
                    "run_train", account.username, account.password, serverIp, serverId,
                    runMode, cityKey, shouldStop, onStatus, getCmd,
                )
            } catch (e: Exception) {
                _status.update {
                    it + (account.username to AccountStatus(RunState.ERROR, message = e.message ?: "loi khong ro"))
                }
            } finally {
                runningThreads.remove(account.username)
                stopFlags.remove(account.username)
                pendingCmd.remove(account.username)
            }
        }
        if (runningThreads.putIfAbsent(account.username, thread) != null) return
        thread.start()
    }

    /** Khoi dong CA Party o che do Di Gioi THAT (party trong game). Neu !party.noLeader: account
     * dau tien = leader (khop PC's is_leader duoc khai bao san theo account). Neu party.noLeader
     * (mirror PC's "Khong co chu PT"): KHONG account nao la leader - moi account la member, dung
     * yen cho leader NGOAI/tay moi that su; account dau tien van lam "picker" (chon kenh chung)
     * giong PC (picker_acc = leader_acc if leader_acc else valid[0][0]). Goi 1 LAN cho ca Party
     * (khac startAccount tung acc rieng le) vi n_members phai duoc set TRUOC khi bat ky thread
     * nao bat dau vong keepalive. */
    fun startPartyDigioi(party: Party, serverIp: String, serverId: Int) {
        if (party.accounts.isEmpty()) return
        val partyModule = Python.getInstance().getModule("train_bot.party_state")
        val hasLeader = !party.noLeader
        val nMembers = if (hasLeader) party.accounts.size - 1 else party.accounts.size
        partyModule.callAttr("set_n_members", party.name, nMembers)
        val picker = party.accounts.first()
        party.accounts.forEach { account ->
            val isLeader = hasLeader && account.username == picker.username
            val isPicker = account.username == picker.username
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
                                    hp = hp?.toInt(), sp = sp?.toInt(),
                                    hpMax = hpMax?.toInt(), spMax = spMax?.toInt(), message = msg,
                                ))
                            }
                        }
                    })
                    module.callAttr(
                        "run_party_digioi", account.username, account.password, serverIp, serverId,
                        party.name, isLeader, isPicker, hasLeader, shouldStop, onStatus,
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
            if (runningThreads.putIfAbsent(account.username, thread) == null) thread.start()
        }
    }

    /** Di Gioi SOLO: moi account doc lap hoan toan, khong lap party/dong bo kenh. */
    fun startAccountDigioiSolo(account: Account, serverIp: String, serverId: Int) {
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
                                hp = hp?.toInt(), sp = sp?.toInt(),
                                hpMax = hpMax?.toInt(), spMax = spMax?.toInt(), message = msg,
                            ))
                        }
                    }
                })
                module.callAttr("run_digioi_solo", account.username, account.password, serverIp, serverId,
                    shouldStop, onStatus)
            } catch (e: Exception) {
                _status.update {
                    it + (account.username to AccountStatus(RunState.ERROR, message = e.message ?: "loi khong ro"))
                }
            } finally {
                runningThreads.remove(account.username)
                stopFlags.remove(account.username)
            }
        }
        if (runningThreads.putIfAbsent(account.username, thread) == null) thread.start()
    }

    fun stopAccount(username: String) {
        stopFlags[username] = true
    }

    fun stopAll() {
        runningThreads.keys.toList().forEach { stopFlags[it] = true }
    }

    /** Gui lenh LIVE (doi kenh / teleport thanh) cho cac account CHI DINH (dang chay) - giong
     * lenh thu cong per-party ben PC. cmd: ["channel", ch] | ["channel_auto"] | ["city", id, flag]. */
    fun sendCommand(usernames: List<String>, cmd: Array<Any>) {
        usernames.forEach { if (runningThreads.containsKey(it)) pendingCmd[it] = cmd }
    }

    fun sendChannel(usernames: List<String>, ch: Int) = sendCommand(usernames, arrayOf<Any>("channel", ch))
    fun sendChannelAuto(usernames: List<String>) = sendCommand(usernames, arrayOf<Any>("channel_auto"))
    fun sendCity(usernames: List<String>, cityId: Int, flag: Int) = sendCommand(usernames, arrayOf<Any>("city", cityId, flag))
    fun sendGiftcode(usernames: List<String>, code: String) = sendCommand(usernames, arrayOf<Any>("giftcode", code))

    /** Query danh sach kenh (BLOCKING ~3s - goi tu background thread/coroutine, KHONG main thread).
     * Tra list [channel, so_nguoi, suc_chua] sap xep theo channel; rong neu khong lay duoc. */
    fun getChannels(username: String): List<Triple<Int, Int, Int>> {
        return try {
            val res = Python.getInstance().getModule("train_bot.train_runner")
                .callAttr("get_channels", username) ?: return emptyList()
            val chans = res.callAttr("get", "channels") ?: return emptyList()
            chans.asList().map {
                val r = it.asList()
                Triple(r[0].toInt(), r[1].toInt(), r[2].toInt())
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    /** Kenh dang o cua 1 account (null neu chua switch / chua chay). */
    fun currentChannel(username: String): Int? {
        return try {
            Python.getInstance().getModule("train_bot.train_runner")
                .callAttr("current_channel", username)?.toInt()
        } catch (e: Exception) {
            null
        }
    }

    fun isRunning(username: String): Boolean = runningThreads.containsKey(username)

    override fun onDestroy() {
        stopAll()
        super.onDestroy()
    }
}
