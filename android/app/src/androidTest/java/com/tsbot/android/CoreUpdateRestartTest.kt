package com.tsbot.android

import android.content.Context
import android.content.ContextWrapper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import org.json.JSONObject

@RunWith(AndroidJUnit4::class)
class CoreUpdateRestartTest {
    private lateinit var root: File
    private lateinit var context: Context
    private var previousLoaded: String? = null

    @Before fun setup() {
        val base = InstrumentationRegistry.getInstrumentation().targetContext
        root = File(base.cacheDir, "core-test-${System.nanoTime()}").apply { mkdirs() }
        context = object : ContextWrapper(base) {
            override fun getFilesDir() = root
            override fun getSharedPreferences(name: String, mode: Int) =
                base.getSharedPreferences(root.name + name, mode)
        }
        previousLoaded = ApkUpdater.loadedCoreVersion.value
    }

    @After fun cleanup() {
        ApkUpdater.recordLoadedCoreVersion(previousLoaded)
        root.deleteRecursively()
    }

    private fun parties() = listOf(Party("probe", "probe", cityKey = "", accounts = listOf(
        Account("active", "fake"), Account("stopped", "fake", enabled = false))))

    private fun oldCore() {
        File(root, "bot_bundle/current").mkdirs()
        File(root, "bot_bundle/current/marker").writeText("old")
        File(root, "bot_bundle/version.txt").writeText("9.1.1.202610060001")
    }

    private fun installFixture() {
        File(root, "bot_bundle/current").renameTo(File(root, "bot_bundle/previous"))
        File(root, "bot_bundle/current").mkdirs()
        File(root, "bot_bundle/current/marker").writeText("new")
        File(root, "bot_bundle/version.txt").writeText("9.1.1.202610060002")
        CoreUpdateRestart.installed(context)
    }

    @Test fun cancelOneAndConsumeExactlyOnce() {
        oldCore()
        CoreUpdateRestart.prepare(context, "9.1.1.202610060002", parties())
        CoreUpdateRestart.cancelResume(context, "active")
        installFixture()
        ApkUpdater.recordLoadedCoreVersion("9.1.1.202610060002")
        val resumed = CoreUpdateRestart.consumeResume(context)
        assertTrue(resumed.flatMap { it.accounts }.none { it.enabled })
        assertFalse(CoreUpdateRestart.hasPending(context))
        assertTrue(CoreUpdateRestart.consumeResume(context).isEmpty())
        assertFalse(File(root, "bot_bundle/previous").exists())
    }

    @Test fun wrongLoadedVersionCannotConsumeResumePlan() {
        oldCore()
        CoreUpdateRestart.prepare(context, "9.1.1.202610060002", parties())
        installFixture()
        ApkUpdater.recordLoadedCoreVersion("9.1.1.202610060001")
        assertThrows(IllegalStateException::class.java) { CoreUpdateRestart.consumeResume(context) }
        assertTrue(CoreUpdateRestart.hasPending(context))
    }

    @Test fun failedLoadRestoresFilesAndPreventsRollbackLoop() {
        oldCore()
        CoreUpdateRestart.prepare(context, "9.1.1.202610060002", parties())
        installFixture()
        assertTrue(CoreUpdateRestart.rollback(context, "test import failure"))
        assertEquals("old", File(root, "bot_bundle/current/marker").readText())
        assertEquals("9.1.1.202610060001", File(root, "bot_bundle/version.txt").readText())
        assertFalse(CoreUpdateRestart.rollback(context, "second failure"))
        ApkUpdater.recordLoadedCoreVersion("9.1.1.202610060001")
        val resumed = CoreUpdateRestart.consumeResume(context).single()
        assertTrue(resumed.accounts[0].enabled)
        assertFalse(resumed.accounts[1].enabled)
    }

    @Test fun interruptedBeforeReplacementDoesNotDeleteWorkingCore() {
        oldCore()
        CoreUpdateRestart.prepare(context, "9.1.1.202610060002", parties())
        val journal = File(root, "core_update_restart.json")
        journal.writeText(JSONObject(journal.readText()).put("owner", -1).toString())
        CoreUpdateRestart.recoverInterruptedInstall(context)
        assertEquals("old", File(root, "bot_bundle/current/marker").readText())
        assertEquals("9.1.1.202610060001", File(root, "bot_bundle/version.txt").readText())
    }

    @Test fun activityRecreationCannotRollbackLiveUpdate() {
        oldCore()
        CoreUpdateRestart.prepare(context, "9.1.1.202610060002", parties())
        CoreUpdateRestart.recoverInterruptedInstall(context)
        val state = JSONObject(File(root, "core_update_restart.json").readText())
        assertFalse(state.optBoolean("restoring"))
        assertNull(CoreUpdateRestart.lastError(context))
    }

    @Test fun rollbackInterruptedAfterRenameRestoresVersionBeforeLoading() {
        oldCore()
        CoreUpdateRestart.prepare(context, "9.1.1.202610060002", parties())
        installFixture()
        val journal = File(root, "core_update_restart.json")
        journal.writeText(JSONObject(journal.readText()).put("restoring", true)
            .put("rollback_pending", true).put("installed", false).toString())
        File(root, "bot_bundle/current").deleteRecursively()
        File(root, "bot_bundle/previous").renameTo(File(root, "bot_bundle/current"))
        CoreUpdateRestart.recoverInterruptedInstall(context)
        assertEquals("old", File(root, "bot_bundle/current/marker").readText())
        assertEquals("9.1.1.202610060001", File(root, "bot_bundle/version.txt").readText())
        val state = JSONObject(journal.readText())
        assertFalse(state.getBoolean("rollback_pending"))
        assertTrue(state.getBoolean("installed"))
    }

    // Review #3: a bundle not newer than the APK is ignored by design, so the APK core is correct.
    @Test fun bundleNotNewerThanApkIsAcceptedAsLoaded() {
        val older = "1.0.202601010000"
        CoreUpdateRestart.prepare(context, older, parties())
        File(root, "bot_bundle/current").mkdirs()
        File(root, "bot_bundle/version.txt").writeText(older)
        CoreUpdateRestart.installed(context)
        ApkUpdater.recordLoadedCoreVersion(BuildConfig.VERSION_NAME)
        assertEquals(1, CoreUpdateRestart.consumeResume(context).size)
        assertFalse(CoreUpdateRestart.hasPending(context))
    }

    // Review #3: an unreadable resume plan must not make a good core look broken.
    @Test fun corruptResumePlanDoesNotFailLoad() {
        oldCore()
        CoreUpdateRestart.prepare(context, "9.1.1.202610060002", parties())
        installFixture()
        File(root, "core_update_resume.json").writeText("{broken")
        ApkUpdater.recordLoadedCoreVersion("9.1.1.202610060002")
        assertTrue(CoreUpdateRestart.consumeResume(context).isEmpty())
        assertFalse(CoreUpdateRestart.hasPending(context))
    }

    // Review #6a: no core directory before the update -> rollback must not keep the broken new one.
    @Test fun rollbackWithoutPreviousCoreRemovesBrokenCore() {
        File(root, "bot_bundle").mkdirs()
        File(root, "bot_bundle/version.txt").writeText("9.1.1.202610060001")
        CoreUpdateRestart.prepare(context, "9.1.1.202610060002", parties())
        File(root, "bot_bundle/current").mkdirs()
        File(root, "bot_bundle/current/marker").writeText("new")
        File(root, "bot_bundle/version.txt").writeText("9.1.1.202610060002")
        CoreUpdateRestart.installed(context)
        assertTrue(CoreUpdateRestart.rollback(context, "test import failure"))
        assertFalse(File(root, "bot_bundle/current").exists())
        assertFalse(File(root, "bot_bundle/version.txt").exists())
    }

    // Review #6b: a backup left over by an earlier update must never replace the working core.
    @Test fun staleBackupIsNeverRestored() {
        oldCore()
        File(root, "bot_bundle/previous").mkdirs()
        File(root, "bot_bundle/previous/marker").writeText("stale")
        CoreUpdateRestart.prepare(context, "9.1.1.202610060002", parties())
        val journal = File(root, "core_update_restart.json")
        journal.writeText(JSONObject(journal.readText()).put("owner", -1).toString())
        CoreUpdateRestart.recoverInterruptedInstall(context)
        assertEquals("old", File(root, "bot_bundle/current/marker").readText())
    }

    // Review #4: one failure must not disable updates forever; only the broken version is skipped.
    @Test fun loadFailureSkipsOnlyThatVersionUntilANewerCoreLoads() {
        oldCore()
        CoreUpdateRestart.prepare(context, "9.1.1.202610060002", parties())
        installFixture()
        assertTrue(CoreUpdateRestart.rollback(context, "import failure", loadFailed = true))
        assertEquals("9.1.1.202610060002", CoreUpdateRestart.failedVersion(context))
        CoreUpdateRestart.acknowledgeError(context)
        assertNull(CoreUpdateRestart.lastError(context))
        ApkUpdater.recordLoadedCoreVersion("9.1.1.202610060001")
        CoreUpdateRestart.consumeResume(context)
        assertEquals("9.1.1.202610060002", CoreUpdateRestart.failedVersion(context))

        CoreUpdateRestart.prepare(context, "9.1.1.202610060003", parties())
        File(root, "bot_bundle/current").renameTo(File(root, "bot_bundle/previous"))
        File(root, "bot_bundle/current").mkdirs()
        File(root, "bot_bundle/version.txt").writeText("9.1.1.202610060003")
        CoreUpdateRestart.installed(context)
        ApkUpdater.recordLoadedCoreVersion("9.1.1.202610060003")
        CoreUpdateRestart.consumeResume(context)
        assertNull(CoreUpdateRestart.failedVersion(context))
        assertNull(CoreUpdateRestart.lastError(context))
    }

    // Review #9: recovery runs first in onCreate; a failure there must not crash (crash loop).
    @Test fun recoveryNeverThrows() {
        oldCore()
        CoreUpdateRestart.prepare(context, "9.1.1.202610060002", parties())
        File(root, "core_update_restart.json").writeText("{broken")
        CoreUpdateRestart.recoverInterruptedInstall(context)
        assertNotNull(CoreUpdateRestart.lastError(context))
    }

    @Test fun javaExecWithExplicitGlobalsDoesNotCrash() {
        val base = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(base))
        val builtins = Python.getInstance().getModule("builtins")
        val globals = builtins.callAttr("dict")
        builtins.callAttr("exec", "value = 42", globals)
        assertEquals(42, globals!!.callAttr("get", "value")!!.toInt())
    }
}
