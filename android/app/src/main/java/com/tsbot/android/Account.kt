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

// --- VAN TIEU (dispatch): config per-acc, nam chung bang setting "Hoi HP/SP" cua acc. ---
// pets RONG = dung TAT CA pet trong nha tro (mac dinh, y het hanh vi cu truoc khi co tinh nang
// nay). Tick theo PET ID chu khong theo index nha tro: index xe dich khi them/bot pet.
data class VantieuConfig(
    val on: Boolean = true,          // mac dinh BAT
    val pets: List<Int> = emptyList(),
) {
    fun isDefault(): Boolean = on && pets.isEmpty()
}

fun vantieuFromJson(o: JSONObject?): VantieuConfig {
    if (o == null) return VantieuConfig()
    val arr = o.optJSONArray("pets")
    val ids = ArrayList<Int>()
    if (arr != null) for (i in 0 until arr.length()) ids.add(arr.optInt(i))
    return VantieuConfig(on = o.optBoolean("on", true), pets = ids.filter { it > 0 })
}

fun VantieuConfig.toJsonObject(): JSONObject = JSONObject().apply {
    put("on", on)
    put("pets", org.json.JSONArray().also { a -> pets.forEach { a.put(it) } })
}

// Van tieu di CHUNG heal_json: cung mot dialog, va duong heal_json da duoc noi san toi
// setup_party_runtime -> khong phai them tham so VI TRI moi (Kotlin goi theo vi tri).
fun HealSettings.toRuntimeJson(vantieu: VantieuConfig): String =
    toJsonObject().apply { put("vantieu", vantieu.toJsonObject()) }.toString()

fun HealSettings.toRuntimeJson(): String = toJsonObject().toString()

fun HealSettings.isDefault(): Boolean = this == HealSettings()

// --- SOI LO (furnace): config per-acc. 3 tab thuong; items = tid_hex -> "auto"/"notify". ---
data class FurnaceTab(val on: Boolean = true, val items: Map<String, String> = emptyMap())  // mac dinh TICK

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
    // Coi la rong CHI khi khong tab nao bat VA khong co items (truoc day chi xet items -> tab tick ON
    // ma chua mo List bi coi la rong -> mat tick khi luu + khong gui runtime).
    fun isEmpty(): Boolean = !voTuong.on && !trangBi.on && !chuyenSinh.on &&
        voTuong.items.isEmpty() && trangBi.items.isEmpty() && chuyenSinh.items.isEmpty()
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
    if (!on && items.isEmpty()) return null   // giu tab tick ON du chua co items (chua mo List)
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
    val vantieu: VantieuConfig = VantieuConfig(),
    val enabled: Boolean = true,
    // Bang TU CONG DIEM TIEM NANG (JSON): {"reserve": int, "rules":[{"stat","target"}]}.
    // Dat CUOI cung de cac cho dung tham so VI TRI (PartyStore) khong phai sua.
    val pointJson: String = "",
)
