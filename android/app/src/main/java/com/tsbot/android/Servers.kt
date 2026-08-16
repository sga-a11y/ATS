package com.tsbot.android

import org.json.JSONObject

/**
 * Danh sach server - DOC TU assets/train_bot_data/servers.json (dung CHUNG voi ban PC).
 *
 * TRUOC DAY day la map CHEP TAY, va no da lech that: PC co 17 server con APK chi co 16
 * (thieu Truong Lieu id 18) vi khi them server moi chi sua servers.json ma quen sua file nay.
 * Dung bai hoc "SHARED_ASSETS tung la allowlist chep tay" trong CLAUDE.md -> nay khong chep nua.
 *
 * FALLBACK ben duoi CHI dung khi doc asset that bai (khong de UI trong). tools/sync_apk_python.py
 * co cong chan bat FALLBACK phai phu du key cua servers.json.
 */
object Servers {
    data class Info(val label: String, val ip: String, val serverId: Int)

    private var loaded: Map<String, Info>? = null

    /** Goi som (MainActivity.onCreate / BotForegroundService.onCreate) de nap tu assets. */
    fun init(context: android.content.Context) {
        if (loaded != null) return
        loaded = try {
            val bytes = context.assets.open("train_bot_data/servers.json").readBytes()
            val root = JSONObject(String(bytes, Charsets.UTF_8)).getJSONObject("servers")
            val out = LinkedHashMap<String, Info>()
            for (key in root.keys()) {
                val o = root.getJSONObject(key)
                out[key] = Info(o.getString("label"), o.getString("ip"), o.getInt("id"))
            }
            out.takeIf { it.isNotEmpty() }
        } catch (e: Exception) {
            null
        }
    }

    val ALL: Map<String, Info> get() = loaded ?: FALLBACK

    private val FALLBACK: Map<String, Info> = linkedMapOf(
        "trieu_van" to Info("Triệu Vân", "103.82.28.98", 1),
        "tao_thao" to Info("Tào Tháo", "103.82.28.99", 2),
        "lu_bo" to Info("Lữ Bố", "103.82.28.100", 3),
        "luu_bi" to Info("Lưu Bị", "103.82.28.126", 4),
        "ton_quyen" to Info("Tôn Quyền", "103.82.28.140", 5),
        "truong_phi" to Info("Trương Phi", "103.82.28.143", 6),
        "chu_du" to Info("Chu Du", "103.82.28.144", 7),
        "quan_vu" to Info("Quan Vũ", "103.82.28.146", 8),
        "dieu_thuyen" to Info("Điêu Thuyền", "103.190.202.43", 9),
        "gia_cat_luong" to Info("Gia Cát Lượng", "103.190.202.44", 10),
        "dai_kieu" to Info("Đại Kiều", "103.190.202.45", 11),
        "manh_hoach" to Info("Mạnh Hoạch", "103.190.202.46", 12),
        "hoang_trung" to Info("Hoàng Trung", "103.190.202.47", 13),
        "ma_sieu" to Info("Mã Siêu", "103.190.202.48", 14),
        "quach_gia" to Info("Quách Gia", "103.190.202.49", 15),
        // id 16 = Bang Thong DA DONG (loi ky thuat) -> nhay thang 17, khong phai thieu sot
        "dien_vi" to Info("Điển Vi", "103.190.202.60", 17),
        "truong_lieu" to Info("Trương Liêu", "103.190.202.61", 18),
    )
}
