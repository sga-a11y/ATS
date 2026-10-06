package com.tsbot.android

import android.content.Context
import android.content.Intent
import android.os.Process
import android.os.SystemClock
import android.util.AtomicFile
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileNotFoundException

/** Persistent handoff to a fresh Python process. Account configuration stays in app-private files. */
internal object CoreUpdateRestart {
    private const val RESUME = "core_update_resume.json"
    private const val PREFS = "core_restart"
    // CoreRestartService needs a few seconds; past this the old process exits by itself and the
    // sticky bot service is restarted by the system, finishing the handoff from the journal.
    private const val RESTART_WATCHDOG_MS = 30_000L
    @Volatile var scheduled = false
        private set
    @Volatile var activityVisible = false

    private fun journal(context: Context) = File(context.filesDir, "core_update_restart.json")
    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, 0)
    private fun read(context: Context): JSONObject? = journal(context).takeIf {
        it.isFile || File(it.path + ".bak").isFile
    }
        ?.let { JSONObject(AtomicFile(it).openRead().bufferedReader().use { reader -> reader.readText() }) }

    private fun write(file: File, text: String) {
        val atomic = AtomicFile(file)
        val output = atomic.startWrite()
        try { output.write(text.toByteArray(Charsets.UTF_8)); atomic.finishWrite(output) }
        catch (e: Exception) { atomic.failWrite(output); throw e }
    }

    fun hasPending(context: Context) = journal(context).exists() || File(journal(context).path + ".bak").exists()
    fun lastError(context: Context): String? = prefs(context).getString("error", null)
    /** Version whose code failed to load; automatic updates skip it until a newer one is published. */
    fun failedVersion(context: Context): String? = prefs(context).getString("failed_version", null)
    /** The user has seen the error: stop showing it (the failed version stays skipped). */
    fun acknowledgeError(context: Context) { prefs(context).edit().remove("error").commit() }

    @Synchronized
    fun prepare(context: Context, version: String, parties: List<Party>) {
        check(!hasPending(context)) { "Đang có một lần cập nhật core chưa hoàn tất" }
        val base = File(context.filesDir, "bot_bundle")
        // Nothing is pending, so any backup left here is stale: a rollback must never restore it.
        File(base, "previous").deleteRecursively()
        PartyStore(context, RESUME).save(parties)
        write(journal(context), JSONObject().put("target", version)
            .put("previous", ApkUpdater.installedBundleVersion(context))
            .put("had_current", File(base, "current").exists())
            .put("created", System.currentTimeMillis()).put("owner", Process.myPid())
            .put("installed", false).toString())
        prefs(context).edit().remove("error").commit()
    }

    @Synchronized
    fun installed(context: Context) {
        val state = checkNotNull(read(context))
        write(journal(context), state.put("installed", true).toString())
    }

    @Synchronized
    fun schedule(context: Context) {
        val state = checkNotNull(read(context)) { "Không có lần cập nhật core nào để áp dụng" }
        // A rollback reschedules from the new process before any activity resumes: keep the UI choice.
        val showUi = activityVisible || state.optBoolean("show_ui")
        if (showUi && !state.optBoolean("show_ui")) write(journal(context), state.put("show_ui", true).toString())
        scheduled = true
        try {
            ContextCompat.startForegroundService(context, Intent(context, CoreRestartService::class.java)
                .putExtra("old_pid", Process.myPid()).putExtra("show_ui", showUi))
        } catch (e: Exception) { scheduled = false; throw e }
        Thread({
            SystemClock.sleep(RESTART_WATCHDOG_MS)
            android.util.Log.e("aTSBot", "core restart did not replace this process; exiting")
            Process.killProcess(Process.myPid())
        }, "aTSBot-core-restart-watchdog").apply { isDaemon = true }.start()
    }

    @Synchronized
    fun cancelResume(context: Context, username: String? = null) {
        if (!hasPending(context)) return
        val file = File(context.filesDir, RESUME)
        val text = try { AtomicFile(file).openRead().bufferedReader().use { it.readText() } }
            catch (_: FileNotFoundException) { return }
        val parties = JSONArray(text)
        for (i in 0 until parties.length()) {
            val accounts = parties.getJSONObject(i).getJSONArray("accounts")
            for (j in 0 until accounts.length()) {
                val account = accounts.getJSONObject(j)
                if (username == null || account.getString("username") == username) account.put("enabled", false)
            }
        }
        write(file, parties.toString())
    }

    /** Restores the core from before the update. [loadFailed]: the new code itself is broken, so
     *  automatic updates skip that version. Returns false when there is nothing (more) to restore. */
    @Synchronized
    fun rollback(context: Context, message: String, loadFailed: Boolean = false): Boolean {
        val state = read(context) ?: return false
        if (state.optBoolean("restoring") && !state.optBoolean("rollback_pending")) return false
        state.put("restoring", true).put("rollback_pending", true).put("installed", false)
        write(journal(context), state.toString())
        val base = File(context.filesDir, "bot_bundle")
        val current = File(base, "current")
        val previous = File(base, "previous")
        val hadCurrent = state.optBoolean("had_current", true)
        if (previous.exists()) {
            current.deleteRecursively()
            check(previous.renameTo(current)) { "Không khôi phục được core cũ" }
        } else if (!hadCurrent) {
            current.deleteRecursively()
        }
        val version = File(base, "version.txt")
        // Without a core directory a version label would only make the ignored bundle look loaded.
        if (!hadCurrent || state.optString("previous").isEmpty()) version.delete()
        else version.writeText(state.getString("previous"))
        state.put("rollback_pending", false).put("installed", true)
        write(journal(context), state.toString())
        prefs(context).edit().putString("error", message).apply {
            if (loadFailed) putString("failed_version", state.getString("target"))
        }.commit()
        return true
    }

    /** Never throws: it runs first in onCreate, and a crash there would loop forever. */
    @Synchronized
    fun recoverInterruptedInstall(context: Context) {
        try {
            val state = read(context) ?: return
            if (state.optBoolean("rollback_pending") ||
                (!state.optBoolean("installed") && state.optInt("owner", -1) != Process.myPid())) {
                rollback(context, "Cập nhật bị gián đoạn; đã khôi phục core trước.")
            }
        } catch (e: Exception) {
            android.util.Log.e("aTSBot", "core update recovery failed", e)
            prefs(context).edit().putString("error", "Không khôi phục được core: ${e.message}").commit()
        }
    }

    @Synchronized
    fun consumeResume(context: Context): List<Party> {
        val state = read(context) ?: return emptyList()
        // What must be loaded given the files on disk: a bundle not newer than the APK is ignored
        // by design, and then the APK's own core is the correct one.
        val expected = ApkUpdater.effectiveVersion(context)
        check(ApkUpdater.loadedCoreVersion.value == expected) { "Core mới chưa nạp thành công" }
        val recent = System.currentTimeMillis() - state.getLong("created") in 0..300_000
        val parties = if (recent) loadResumePlan(context) else emptyList()
        // Backup first: once the journal is gone nothing may restore it over the working core.
        File(context.filesDir, "bot_bundle/previous").deleteRecursively()
        discard(context)
        if (!state.optBoolean("restoring")) prefs(context).edit().remove("error").remove("failed_version").commit()
        return parties
    }

    private fun loadResumePlan(context: Context): List<Party> = try {
        val file = File(context.filesDir, RESUME)
        AtomicFile(file).openRead().close()   // restores an interrupted write's backup, if any
        PartyStore(context, RESUME).load()
    } catch (e: Exception) {
        android.util.Log.w("aTSBot", "core update resume plan unreadable; accounts stay stopped", e)
        emptyList()
    }

    @Synchronized
    fun discard(context: Context) {
        AtomicFile(journal(context)).delete()
        AtomicFile(File(context.filesDir, RESUME)).delete()
    }
}
