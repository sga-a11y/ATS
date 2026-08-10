package com.tsbot.android

import kotlin.math.roundToInt
import org.json.JSONObject

data class HealSettings(
    val hpChar: Int = 40,
    val spChar: Int = 0,
    val hpPet: Int = 40,
    val spPet: Int = 0,
)

private fun healPct(o: JSONObject, key: String, defaultValue: Int): Int {
    val raw = o.opt(key) ?: return defaultValue
    val value = when (raw) {
        is Number -> raw.toDouble()
        is String -> raw.toDoubleOrNull() ?: return defaultValue
        else -> return defaultValue
    }
    val pct = if (value <= 1.0) value * 100.0 else value
    return pct.roundToInt().coerceIn(0, 100)
}

fun healSettingsFromJson(o: JSONObject?): HealSettings {
    if (o == null) return HealSettings()
    return HealSettings(
        hpChar = healPct(o, "hp_char", 40),
        spChar = healPct(o, "sp_char", 0),
        hpPet = healPct(o, "hp_pet", 40),
        spPet = healPct(o, "sp_pet", 0),
    )
}

fun HealSettings.toJsonObject(): JSONObject = JSONObject().apply {
    put("hp_char", hpChar.coerceIn(0, 100) / 100.0)
    put("sp_char", spChar.coerceIn(0, 100) / 100.0)
    put("hp_pet", hpPet.coerceIn(0, 100) / 100.0)
    put("sp_pet", spPet.coerceIn(0, 100) / 100.0)
}

fun HealSettings.toRuntimeJson(): String = toJsonObject().toString()

fun HealSettings.isDefault(): Boolean = this == HealSettings()

// --- SOI LO (furnace): config per-acc. 3 tab thuong; items = tid_hex -> "auto"/"notify". ---
data class FurnaceTab(val on: Boolean = false, val items: Map<String, String> = emptyMap())

data class FurnaceConfig(
    val voTuong: FurnaceTab = FurnaceTab(),
    val trangBi: FurnaceTab = FurnaceTab(),
    val chuyenSinh: FurnaceTab = FurnaceTab(),
) {
    fun tab(key: String): FurnaceTab = when (key) {
        "vo_tuong" -> voTuong; "trang_bi" -> trangBi; else -> chuyenSinh
    }
    fun withTab(key: String, t: FurnaceTab): FurnaceConfig = when (key) {
        "vo_tuong" -> copy(voTuong = t); "trang_bi" -> copy(trangBi = t); else -> copy(chuyenSinh = t)
    }
    fun isEmpty(): Boolean = voTuong.items.isEmpty() && trangBi.items.isEmpty() && chuyenSinh.items.isEmpty()
}

private fun furnaceTabFromJson(o: JSONObject?): FurnaceTab {
    if (o == null) return FurnaceTab()
    val items = LinkedHashMap<String, String>()
    val io = o.optJSONObject("items")
    if (io != null) for (k in io.keys()) {
        val v = io.optString(k)
        if (v == "auto" || v == "notify") items[k] = v
    }
    return FurnaceTab(on = o.optBoolean("on", true), items = items)
}

fun furnaceConfigFromJson(o: JSONObject?): FurnaceConfig {
    if (o == null) return FurnaceConfig()
    return FurnaceConfig(
        voTuong = furnaceTabFromJson(o.optJSONObject("vo_tuong")),
        trangBi = furnaceTabFromJson(o.optJSONObject("trang_bi")),
        chuyenSinh = furnaceTabFromJson(o.optJSONObject("chuyen_sinh")),
    )
}

private fun FurnaceTab.toJsonOrNull(): JSONObject? {
    if (items.isEmpty()) return null
    val io = JSONObject(); for ((k, v) in items) io.put(k, v)
    return JSONObject().apply { put("on", on); put("items", io) }
}

fun FurnaceConfig.toJsonObject(): JSONObject = JSONObject().apply {
    voTuong.toJsonOrNull()?.let { put("vo_tuong", it) }
    trangBi.toJsonOrNull()?.let { put("trang_bi", it) }
    chuyenSinh.toJsonOrNull()?.let { put("chuyen_sinh", it) }
}

fun FurnaceConfig.toRuntimeJson(): String = if (isEmpty()) "" else toJsonObject().toString()

data class Account(
    val username: String,
    val password: String,
    val battleJson: String = "",
    val heal: HealSettings = HealSettings(),
    val furnace: FurnaceConfig = FurnaceConfig(),
    val enabled: Boolean = true,
)
