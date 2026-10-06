package com.tsbot.android

import android.app.Activity
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.IBinder
import androidx.core.content.ContextCompat
import java.io.File
import org.json.JSONObject

/** Verification APK only. Fake core fixtures never open game connections. */
class CoreUpdateProbeActivity : Activity() {
    private lateinit var connection: ServiceConnection
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        check(BuildConfig.APPLICATION_ID.endsWith(".verification"))
        connection = object : ServiceConnection {
            override fun onServiceDisconnected(name: ComponentName?) = Unit
            override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
                val service = (binder as BotForegroundService.LocalBinder).getService()
                Thread {
                    try {
                        when (intent.getStringExtra("phase")) {
                            "report" -> File(filesDir, "probe_report").writeText(JSONObject()
                                .put("loaded", ApkUpdater.loadedCoreVersion.value)
                                .put("pid", android.os.Process.myPid()).toString())
                            "start" -> {
                                check(File(filesDir, "probe_loaded").isFile) { "Fake core not loaded" }
                                val server = Servers.ALL.entries.first()
                                val party = Party("probe", server.key, cityKey = "", accounts = listOf(
                                    Account("probe-active", "fake"), Account("probe-stopped", "fake")))
                                PartyStore(this@CoreUpdateProbeActivity).save(listOf(party))
                                service.startParty(0, party, server.value.ip, server.value.serverId)
                            }
                            "stop-one" -> service.stopAccount("probe-stopped")
                            else -> {
                                ApkUpdater.setAutoUpdate(this@CoreUpdateProbeActivity, false)
                                val version = intent.getStringExtra("version")!!
                                CoreUpdateRestart.activityVisible = intent.getBooleanExtra("show_ui", false)
                                if (intent.getBooleanExtra("cancel", false)) Thread {
                                    while (!CoreUpdateRestart.hasPending(this@CoreUpdateProbeActivity)) Thread.sleep(10)
                                    service.stopAll()
                                }.start()
                                val method = ApkUpdater::class.java.getDeclaredMethod("installBundleZip",
                                    Context::class.java, File::class.java, String::class.java)
                                method.isAccessible = true
                                method.invoke(ApkUpdater, this@CoreUpdateProbeActivity,
                                    File(filesDir, "probe.zip"), version)
                            }
                        }
                    } catch (e: Exception) { File(filesDir, "probe_error").writeText(e.stackTraceToString()) }
                    finally { runOnUiThread { finish() } }
                }.start()
            }
        }
        val service = Intent(this, BotForegroundService::class.java)
        ContextCompat.startForegroundService(this, service)
        bindService(service, connection, Context.BIND_AUTO_CREATE)
    }

    override fun onDestroy() { unbindService(connection); super.onDestroy() }
}
