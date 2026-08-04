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
    private const val VERSION_URL =
        "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/version.json"
    private const val GOOGLE_DRIVE_VERSION_URL =
        "https://drive.google.com/file/d/1e3MlVufze1iag8X51IoyCYTf5RfzxCR5/view?usp=drive_link"
    private const val FALLBACK_APK_URL =
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
        val currentVersion = installedBundleVersion(context).ifBlank { BuildConfig.VERSION_NAME }
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

    fun updateBundleIfNeeded(context: Context): Boolean {
        val info = checkBundleUpdate(context) ?: return false
        downloadAndInstallBundle(context, info)
        return true
    }

    fun pythonBundlePath(context: Context): File =
        File(context.filesDir, "bot_bundle/current/android")

    fun bundleDataFile(context: Context, name: String): File =
        File(context.filesDir, "bot_bundle/current/data/$name")

    private fun installedBundleVersion(context: Context): String {
        return try {
            File(context.filesDir, "bot_bundle/version.txt").readText(Charsets.UTF_8).trim()
        } catch (_: Exception) {
            ""
        }
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
                errors += "${normalizeDownloadUrl(rawUrl)}: ${e.message ?: e.javaClass.simpleName}"
            }
        }
        throw RuntimeException("Không tải được core bundle từ mirror nào:\n" + errors.joinToString("\n"))
    }

    private fun installBundleZip(context: Context, zip: File, version: String) {
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
        current.deleteRecursively()
        if (!stage.renameTo(current)) {
            stage.copyRecursively(current, overwrite = true)
            stage.deleteRecursively()
        }
        File(base, "version.txt").writeText(version, Charsets.UTF_8)
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

    private fun isNewerVersion(remoteVersion: String, currentVersion: String): Boolean {
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
        if (out.isEmpty()) out += FALLBACK_APK_URL
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
