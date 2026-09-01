package com.tsbot.android

import org.json.JSONObject

/**
 * Danh sach EVENT teleport (mode "Event") - DOC TU assets/train_bot_data/events.json
 * (dung CHUNG voi ban PC).
 *
 * TRUOC DAY day la map CHEP TAY va no DA LECH that: PC co 3 event (Nhi Kieu / 40 NPC /
 * **Loan dau**) con APK chi co 2 - them `loan_dau` vao events.json ma quen sua file nay, nen
 * ban APK khong he chon duoc Loan dau. Dung y bai hoc `Servers.kt` + muc "SHARED_ASSETS tung la
 * allowlist chep tay" trong CLAUDE.md -> nay khong chep nua.
 *
 * `motTranDuoc` = event nay co tick "Chi danh 1 tran" hay khong; neo theo DU LIEU
 * (`party_battle.kind == "chaos_vs"`) chu khong theo key, y het ban PC (`gui.py`).
 *
 * FALLBACK ben duoi CHI dung khi doc asset that bai (khong de UI trong).
 */
object Events {
    data class Info(val label: String, val motTranDuoc: Boolean = false)

    private var loaded: Map<String, Info>? = null

    /** Goi som (MainActivity.onCreate / BotForegroundService.onCreate) de nap tu assets. */
    fun init(context: android.content.Context) {
        if (loaded != null) return
        loaded = try {
            val bytes = context.assets.open("train_bot_data/events.json").readBytes()
            val root = JSONObject(String(bytes, Charsets.UTF_8))
            val evs = root.optJSONObject("events") ?: root
            val out = LinkedHashMap<String, Info>()
            for (key in evs.keys()) {
                val o = evs.optJSONObject(key) ?: continue
                val kind = o.optJSONObject("party_battle")?.optString("kind") ?: ""
                out[key] = Info(o.optString("label", key), kind == "chaos_vs")
            }
            out.takeIf { it.isNotEmpty() }
        } catch (e: Exception) {
            null
        }
    }

    val ALL: Map<String, Info> get() = loaded ?: FALLBACK

    private val FALLBACK: Map<String, Info> = linkedMapOf(
        "nhi_kieu" to Info("Nhị Kiều"),
        "npc_40" to Info("40 NPC"),
        "loan_dau" to Info("Loạn đấu", motTranDuoc = true),
    )
}
