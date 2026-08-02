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

data class Account(
    val username: String,
    val password: String,
    val battleJson: String = "",
    val heal: HealSettings = HealSettings(),
    val enabled: Boolean = true,
)
