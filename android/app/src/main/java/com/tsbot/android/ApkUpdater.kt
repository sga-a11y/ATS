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

data class ApkUpdateInfo(
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

    fun checkUpdate(currentVersion: String = BuildConfig.VERSION_NAME): ApkUpdateInfo? {
        val sources = listOf(VERSION_URL, GOOGLE_DRIVE_VERSION_URL)
        val errors = mutableListOf<String>()
        var sawSource = false
        var best: ApkUpdateInfo? = null
        for (source in sources) {
            try {
                val json = fetchJson(source)
                sawSource = true
                val version = json.optString("version").trim()
                if (isNewerVersion(version, currentVersion)) {
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

    private fun fetchJson(url: String): JSONObject {
        val text = openConnection(url).inputStream.use { input ->
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

    private fun openConnection(url: String): HttpURLConnection {
        val conn = URL(normalizeDownloadUrl(url)).openConnection() as HttpURLConnection
        conn.instanceFollowRedirects = true
        conn.connectTimeout = 20_000
        conn.readTimeout = 60_000
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

    private fun looksLikeApk(file: File): Boolean {
        if (!file.isFile || file.length() < 4L) return false
        file.inputStream().use { input ->
            val b0 = input.read()
            val b1 = input.read()
            return b0 == 0x50 && b1 == 0x4b
        }
    }
}
