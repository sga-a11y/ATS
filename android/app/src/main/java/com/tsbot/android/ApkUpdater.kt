package com.tsbot.android

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.zip.ZipInputStream
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

data class ApkUpdateInfo(
    val version: String,
    val urls: List<String>,
    val notes: String,
)

data class BundleUpdateInfo(
    val version: String,
    val urls: List<String>,
    val notes: String,
)

object ApkUpdater {
    @Volatile internal var activateBundle: ((String, () -> Unit) -> Unit)? = null
    /** Set by the bot service; null means no service in this process, hence nothing running. */
    @Volatile internal var hasActiveAccounts: (() -> Boolean)? = null
    private val _deferredCoreVersion = MutableStateFlow<String?>(null)
    /** Newer core known but not applied because accounts are running; only the user may apply it. */
    val deferredCoreVersion = _deferredCoreVersion.asStateFlow()
    private val _coreUpdateStatus = MutableStateFlow<String?>(null)
    val coreUpdateStatus = _coreUpdateStatus.asStateFlow()

    internal fun reportCoreUpdate(message: String?) { _coreUpdateStatus.value = message }

    private class CoreActivationException(cause: Exception) : RuntimeException(cause.message, cause)
    private val _loadedCoreVersion = MutableStateFlow<String?>(null)
    val loadedCoreVersion = _loadedCoreVersion.asStateFlow()
    private val _availableCoreVersion = MutableStateFlow(BuildConfig.VERSION_NAME)
    val availableCoreVersion = _availableCoreVersion.asStateFlow()

    internal fun recordLoadedCoreVersion(version: String?) {
        _loadedCoreVersion.value = version
    }

    private const val VERSION_URL =
        "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/version.json"
    private const val GOOGLE_DRIVE_VERSION_URL =
        "https://drive.google.com/file/d/1e3MlVufze1iag8X51IoyCYTf5RfzxCR5/view?usp=drive_link"
    const val GITHUB_APK_DOWNLOAD_URL =
        "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/aTSBot.apk"
    const val MANUAL_DOWNLOAD_URL =
        "https://drive.google.com/drive/folders/1Cm2Suv7aFaq3-v9uq5G7iQ1aNHRoiirv"

    private const val FALLBACK_BUNDLE_URL =
        "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/aTSBot-bundle.zip"

    fun checkUpdate(currentVersion: String = BuildConfig.VERSION_NAME): ApkUpdateInfo? {
        val sources = listOf(VERSION_URL, GOOGLE_DRIVE_VERSION_URL)
        val errors = mutableListOf<String>()
        var sawSource = false
        var best: ApkUpdateInfo? = null
        for (source in sources) {
            try {
                val json = fetchJson(source)
                sawSource = true
                val legacy = !json.has("bundle_version") && !json.has("apk_version")
                val version = json.optString("apk_version", json.optString("version")).trim()
                val requiredVersion = json.optString("apk_required_version").trim()
                val apkRequired = if (requiredVersion.isNotBlank()) {
                    isNewerVersion(requiredVersion, currentVersion)
                } else {
                    json.optBoolean("apk_required", legacy)
                }
                if (apkRequired && isNewerVersion(version, currentVersion)) {
                    val info = ApkUpdateInfo(
                        version = version,
                        urls = apkUrlsFromVersion(json),
                        notes = json.optString("notes").trim(),
                    )
                    val currentBest = best
                    if (currentBest == null || info.version > currentBest.version) {
                        best = info
                    }
                }
            } catch (e: Exception) {
                errors += "$source: ${e.message ?: e.javaClass.simpleName}"
            }
        }
        if (best != null) return best
        if (sawSource) return null
        throw RuntimeException(errors.joinToString("; ").ifBlank { "Không có nguồn update nào" })
    }

    fun checkBundleUpdate(context: Context): BundleUpdateInfo? {
        // Compare with the core that actually runs: a bundle not newer than the APK is never loaded,
        // so applying it would restart every account for nothing.
        val currentVersion = effectiveVersion(context)
        val sources = listOf(VERSION_URL, GOOGLE_DRIVE_VERSION_URL)
        val errors = mutableListOf<String>()
        var sawSource = false
        var best: BundleUpdateInfo? = null
        for (source in sources) {
            try {
                val json = fetchJson(source, connectTimeout = 5_000, readTimeout = 10_000)
                sawSource = true
                val version = json.optString("bundle_version").trim()
                if (isNewerVersion(version, currentVersion)) {
                    val info = BundleUpdateInfo(
                        version = version,
                        urls = bundleUrlsFromVersion(json),
                        notes = json.optString("notes").trim(),
                    )
                    val currentBest = best
                    if (currentBest == null || info.version > currentBest.version) {
                        best = info
                    }
                }
            } catch (e: Exception) {
                errors += "$source: ${e.message ?: e.javaClass.simpleName}"
            }
        }
        if (best != null) return best
        if (sawSource) return null
        throw RuntimeException(errors.joinToString("; ").ifBlank { "Không có nguồn update nào" })
    }

    // ---- TU DONG UPDATE / CHAY CORE CU (giong PC, xem documents/CHAY_BAN_CU.md) ----
    // Version APK nam cung trong BuildConfig -> khong gia duoc -> tat update APK bang CO trong prefs.
    // Core bundle thi ghim nhu PC: version.txt = "9.<ban that>" -> so chuoi luon moi hon moi ban
    // server (khong tu update) VA moi hon VERSION_NAME (qua cua chan bundle cu o BotForegroundService).
    const val PIN_PREFIX = "9."
    private const val RELEASE_REPO = "sgagamee-oss/atsbot-release"
    private const val PREFS = "updater"
    private const val KEY_AUTO = "auto_update"
    // Kotlin goi ~50 ham Python, ham moi them lien tuc -> core qua cu thi nhieu tinh nang hong.
    // Bang PC: installed_app_version co tu 07/08.
    private const val MIN_PIN_VERSION = "1.1.202608080000"

    fun realVersion(version: String): String =
        version.trim().let { if (it.startsWith(PIN_PREFIX)) it.substring(PIN_PREFIX.length) else it }

    fun isAutoUpdate(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY_AUTO, true)

    fun setAutoUpdate(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY_AUTO, enabled).apply()
        val file = File(context.filesDir, "bot_bundle/version.txt")
        if (enabled && file.isFile) {
            // Tick lai: bo ghim de lan check sau thay ban moi hon.
            file.writeText(realVersion(file.readText(Charsets.UTF_8)), Charsets.UTF_8)
        }
    }

    // Danh sach chon ban cu: 100 ban gan nhat (giong PC RELEASE_LIMIT). Khong loc theo ngay: ngung
    // build thi danh sach van con ban de chon.
    // Doc releases.json truoc (build_product.py sinh, tai qua CDN - khong gioi han luot); loi moi
    // lui ve api.github.com (khong token chi 60 luot/gio/IP -> "403 rate limit exceeded").
    fun listReleases(): List<Pair<String, String>> {
        val text = try {
            openConnection("https://github.com/$RELEASE_REPO/releases/latest/download/releases.json")
                .inputStream.use { it.bufferedReader(Charsets.UTF_8).readText() }
        } catch (_: Exception) {
            openConnection("https://api.github.com/repos/$RELEASE_REPO/releases?per_page=100")
                .inputStream.use { it.bufferedReader(Charsets.UTF_8).readText() }
        }
        val arr = JSONArray(text)
        val out = mutableListOf<Pair<String, String>>()
        for (i in 0 until arr.length()) {
            val rel = arr.getJSONObject(i)
            val ver = rel.optString("tag_name").trim().removePrefix("v")
            if (ver.isBlank() || ver < MIN_PIN_VERSION || rel.optBoolean("draft")) continue
            val assets = rel.optJSONArray("assets") ?: continue
            val hasBundle = (0 until assets.length()).any {
                assets.getJSONObject(it).optString("name") == "aTSBot-bundle.zip"
            }
            if (hasBundle) out += ver to rel.optString("published_at").take(10)
        }
        return out.sortedByDescending { it.first }
    }

    /** Tai, tu nap core cua tag v<version>, ghim "9.<version>" va tat tu dong update. */
    @Synchronized
    fun installOldBundle(context: Context, version: String) {
        val ver = realVersion(version)
        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        val target = File(dir, "aTSBot-bundle-old-$ver.zip")
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val wasAuto = prefs.getBoolean(KEY_AUTO, true)
        try {
            downloadToFile("https://github.com/$RELEASE_REPO/releases/download/v$ver/aTSBot-bundle.zip", target)
            if (!looksLikeZip(target)) throw RuntimeException("File tải về không phải ZIP")
            // Saved before activating: this process is killed shortly after a successful install.
            prefs.edit().putBoolean(KEY_AUTO, false).commit()
            installBundleZip(context, target, PIN_PREFIX + ver)
        } catch (e: Exception) {
            prefs.edit().putBoolean(KEY_AUTO, wasAuto).commit()
            throw e
        } finally {
            target.delete()
        }
    }

    /** Applying restarts the bot process, so with accounts running (dungeon, boss...) it waits for
     *  the user's "Áp dụng ngay" ([applyWhileRunning] = true) instead of cutting them off. */
    @Synchronized
    fun updateBundleIfNeeded(context: Context, applyWhileRunning: Boolean = false): Boolean {
        if (!isAutoUpdate(context)) return false
        val info = checkBundleUpdate(context)
        if (info == null) {
            _deferredCoreVersion.value = null
            return false
        }
        // Its code already failed to load here (rolled back): wait for the next release.
        if (!applyWhileRunning && info.version == CoreUpdateRestart.failedVersion(context)) return false
        if (!applyWhileRunning && hasActiveAccounts?.invoke() == true) {
            _deferredCoreVersion.value = info.version
            return false
        }
        downloadAndInstallBundle(context, info)
        _deferredCoreVersion.value = null
        return true
    }

    fun pythonBundlePath(context: Context): File =
        File(context.filesDir, "bot_bundle/current/android")

    fun bundleDataFile(context: Context, name: String): File =
        File(context.filesDir, "bot_bundle/current/data/$name")

    fun installedBundleVersion(context: Context): String {
        return try {
            File(context.filesDir, "bot_bundle/version.txt").readText(Charsets.UTF_8).trim()
        } catch (_: Exception) {
            ""
        }
    }

    fun effectiveVersion(context: Context): String {
        val bundle = installedBundleVersion(context)
        val apk = BuildConfig.VERSION_NAME
        val available = if (isNewerVersion(bundle, apk)) bundle else apk
        _availableCoreVersion.value = available
        return available
    }

    private fun downloadAndInstallBundle(context: Context, info: BundleUpdateInfo) {
        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        val target = File(dir, "aTSBot-bundle-${info.version}.zip")
        val errors = mutableListOf<String>()
        for (rawUrl in info.urls) {
            try {
                downloadToFile(rawUrl, target)
                if (!looksLikeZip(target)) {
                    target.delete()
                    throw RuntimeException("File tải về không phải ZIP")
                }
                installBundleZip(context, target, info.version)
                target.delete()
                return
            } catch (e: Exception) {
                target.delete()
                if (e is CoreActivationException) throw e
                errors += "${normalizeDownloadUrl(rawUrl)}: ${e.message ?: e.javaClass.simpleName}"
            }
        }
        throw RuntimeException("Không tải được core bundle từ mirror nào:\n" + errors.joinToString("\n"))
    }

    private fun installBundleZip(context: Context, zip: File, version: String) {
        if (CoreUpdateRestart.hasPending(context)) {
            throw CoreActivationException(IllegalStateException("Một lần cập nhật core đang hoàn tất"))
        }
        val base = File(context.filesDir, "bot_bundle").apply { mkdirs() }
        val stage = File(base, "stage")
        val current = File(base, "current")
        stage.deleteRecursively()
        stage.mkdirs()
        unzipSafe(zip, stage)
        if (!File(stage, "android/train_bot/run_party_digioi.py").isFile) {
            throw RuntimeException("Bundle thiếu android/train_bot/run_party_digioi.py")
        }
        if (!File(stage, "android/train_bot/config.py").isFile) {
            throw RuntimeException("Bundle thiếu android/train_bot/config.py")
        }
        val backup = File(base, "previous")
        val versionFile = File(base, "version.txt")
        val install = {
            backup.deleteRecursively()
            check(!current.exists() || current.renameTo(backup)) { "Không sao lưu được core cũ" }
            check(stage.renameTo(current)) { "Không cài được core mới" }
            versionFile.writeText(version, Charsets.UTF_8)
            effectiveVersion(context)
            Unit
        }
        try {
            val activate = activateBundle
            // The service owns recovery once it has prepared the journal (restore + restart accounts).
            if (activate != null) activate(version, install) else {
                CoreUpdateRestart.prepare(context, version, emptyList())
                try {
                    install()
                    CoreUpdateRestart.installed(context)
                    CoreUpdateRestart.schedule(context)
                } catch (e: Exception) {
                    // No service, so no account to resume: restore the files and drop the journal.
                    runCatching { CoreUpdateRestart.rollback(context, "Cập nhật core lỗi: ${e.message}") }
                        .onFailure { e.addSuppressed(it) }
                    CoreUpdateRestart.discard(context)
                    effectiveVersion(context)
                    throw e
                }
            }
        } catch (e: Exception) {
            throw if (e is CoreActivationException) e else CoreActivationException(e)
        } finally {
            stage.deleteRecursively()
        }
    }

    private fun unzipSafe(zip: File, dest: File) {
        val base = dest.canonicalFile
        ZipInputStream(zip.inputStream()).use { input ->
            while (true) {
                val entry = input.nextEntry ?: break
                val outFile = File(dest, entry.name).canonicalFile
                if (outFile != base && !outFile.path.startsWith(base.path + File.separator)) {
                    throw RuntimeException("Zip bundle có đường dẫn không hợp lệ: ${entry.name}")
                }
                if (entry.isDirectory) {
                    outFile.mkdirs()
                } else {
                    outFile.parentFile?.mkdirs()
                    outFile.outputStream().use { output -> input.copyTo(output) }
                }
                input.closeEntry()
            }
        }
    }

    fun downloadApk(context: Context, info: ApkUpdateInfo): File {
        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        val target = File(dir, "aTSBot-${info.version}.apk")
        val errors = mutableListOf<String>()
        for (rawUrl in info.urls) {
            try {
                downloadToFile(rawUrl, target)
                if (!looksLikeApk(target)) {
                    target.delete()
                    throw RuntimeException("File tải về không phải APK")
                }
                return target
            } catch (e: Exception) {
                target.delete()
                errors += "${normalizeDownloadUrl(rawUrl)}: ${e.message ?: e.javaClass.simpleName}"
            }
        }
        throw RuntimeException("Không tải được APK từ mirror nào:\n" + errors.joinToString("\n"))
    }

    fun canInstallApk(context: Context): Boolean {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.O ||
            context.packageManager.canRequestPackageInstalls()
    }

    fun openInstallPermissionSettings(context: Context) {
        val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${context.packageName}"),
            )
        } else {
            Intent(Settings.ACTION_SECURITY_SETTINGS)
        }
        context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    fun installApk(context: Context, apk: File) {
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            apk,
        )
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    private fun fetchJson(
        url: String,
        connectTimeout: Int = 20_000,
        readTimeout: Int = 60_000,
    ): JSONObject {
        val text = openConnection(url, connectTimeout, readTimeout).inputStream.use { input ->
            input.bufferedReader(Charsets.UTF_8).readText()
        }
        return JSONObject(text)
    }

    private fun downloadToFile(url: String, target: File) {
        openConnection(url).inputStream.use { input ->
            target.outputStream().use { output ->
                input.copyTo(output)
            }
        }
        if (target.length() <= 0L) {
            throw RuntimeException("File rỗng")
        }
    }

    private fun openConnection(
        url: String,
        connectTimeoutMs: Int = 20_000,
        readTimeoutMs: Int = 60_000,
    ): HttpURLConnection {
        val conn = URL(normalizeDownloadUrl(url)).openConnection() as HttpURLConnection
        conn.instanceFollowRedirects = true
        conn.connectTimeout = connectTimeoutMs
        conn.readTimeout = readTimeoutMs
        conn.setRequestProperty("User-Agent", "atsbot-android-updater")
        val code = conn.responseCode
        if (code !in 200..299) {
            conn.disconnect()
            throw RuntimeException("HTTP $code")
        }
        return conn
    }

    // internal (khong con private): BotForegroundService dung de BO QUA bundle cu hon APK -
    // bundle duoc cam vao sys.path[0] nen no LUON thang module trong APK, ke ca khi da lac hau.
    internal fun isNewerVersion(remoteVersion: String, currentVersion: String): Boolean {
        if (remoteVersion.isBlank()) return false
        val current = currentVersion.trim()
        if (current.isBlank() || current.endsWith(".dev")) return true
        return remoteVersion > current
    }

    private fun apkUrlsFromVersion(json: JSONObject): List<String> {
        val out = mutableListOf<String>()
        collectUrls(json, "apk_urls", out)
        collectUrls(json, "apk_mirrors", out)
        collectUrls(json, "apk_url", out)
        collectUrls(json, "android_url", out)
        if (out.isEmpty()) out += GITHUB_APK_DOWNLOAD_URL
        return out.map { normalizeDownloadUrl(it) }.distinct()
    }

    private fun bundleUrlsFromVersion(json: JSONObject): List<String> {
        val out = mutableListOf<String>()
        collectUrls(json, "bundle_urls", out)
        collectUrls(json, "bundle_mirrors", out)
        collectUrls(json, "bundle_url", out)
        if (out.isEmpty()) out += FALLBACK_BUNDLE_URL
        return out.map { normalizeDownloadUrl(it) }.distinct()
    }

    private fun collectUrls(json: JSONObject, key: String, out: MutableList<String>) {
        when (val value = json.opt(key)) {
            is JSONArray -> {
                for (i in 0 until value.length()) {
                    value.optString(i).trim().takeIf { it.isNotBlank() }?.let(out::add)
                }
            }
            is String -> value.trim().takeIf { it.isNotBlank() }?.let(out::add)
        }
    }

    private fun normalizeDownloadUrl(url: String): String {
        val trimmed = url.trim()
        if (!trimmed.contains("drive.google.com", ignoreCase = true)) return trimmed
        val queryId = Regex("""[?&]id=([^&]+)""").find(trimmed)?.groupValues?.getOrNull(1)
        val pathId = Regex("""/file/d/([^/]+)""").find(trimmed)?.groupValues?.getOrNull(1)
        val fileId = queryId ?: pathId ?: return trimmed
        return "https://drive.google.com/uc?export=download&id=" +
            URLEncoder.encode(fileId, Charsets.UTF_8.name())
    }

    private fun looksLikeApk(file: File): Boolean = looksLikeZip(file)

    private fun looksLikeZip(file: File): Boolean {
        if (!file.isFile || file.length() < 4L) return false
        file.inputStream().use { input ->
            val b0 = input.read()
            val b1 = input.read()
            return b0 == 0x50 && b1 == 0x4b
        }
    }
}
