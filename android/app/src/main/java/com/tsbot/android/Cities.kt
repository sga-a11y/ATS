package com.tsbot.android

/** Danh sach thanh de teleport ve (opcode 0x44) - copy tu cities.json (goc du lieu that,
 * xem E:\Claude\ATS\cities.json), dung cho mode "Dung yen tai thanh": nguoi dung chon 1
 * thanh, bot se ve va dung yen tai do. city_id/flag phai dung cap (server tu choi neu sai). */
object Cities {
    data class Info(val label: String, val cityId: Int, val flag: Int)

    val ALL: Map<String, Info> = linkedMapOf(
        // Sap theo flag tang dan (thu tu hien trong list chon thanh).
        "trac_quan" to Info("Trác Quận", 12001, 0),
        "bac_hai" to Info("Bắc Hải", 11011, 1),
        "ng_thanh" to Info("Nghiệp Thành", 12061, 2),
        "cu_loc" to Info("Cự Lộc", 12011, 3),
        "lac_duong" to Info("Lạc Dương", 13001, 4),
        "hua_xuong" to Info("Hứa Xương", 13011, 5),
        "truong_an" to Info("Trường An", 14001, 6),
        "tu_chau" to Info("Từ Châu", 15001, 7),
        "tho_xuan" to Info("Thọ Xuân", 15021, 8),
        "kien_nghiep" to Info("Kiến Nghiệp", 18001, 9),
        "hoi_ke" to Info("Hội Kê", 18021, 10),
        "tuong_binh" to Info("Tương Bình", 19001, 11),
        "thuong_dang" to Info("Thượng Đảng", 20001, 12),
        "tuong_duong" to Info("Tương Dương", 21001, 13),
        "giang_lang" to Info("Giang Lăng", 21011, 14),
        "lau_bo" to Info("Lâu Bò", 56001, 15),
        // 3 thanh MOI mo (22/07). Xac nhan tu capture goi 0x44 (thanh_moi_/tamadai_20260722.pcap).
        // LUU Y: Ta Ma Dai teleport city_id = 57001, KHONG phai 61041 (61041 la ma ban do hien
        // trong game, goi 0x44 dung 57001).
        "ta_ma_dai" to Info("Tả Mã Đài", 57001, 16),
        "truong_sa" to Info("Trường Sa", 23001, 17),
        "linh_lang" to Info("Linh Lăng", 23011, 18),
    )

    /** Nha Nam Tinh Quan (55002) KHONG phai thanh: bot ve Bac Hai roi keo party di bo len (Python
     * `_ve_thanh_tap_trung` / `party_teleport_city`). Chi nam trong list chon cua mode ve thanh +
     * popup teleport, dat TRUOC Trac Quan - KHONG nam trong ALL (ALL.keys.first() la mac dinh). */
    const val NHA_NAM_TINH_KEY = "nha_nam_tinh"
    val NHA_NAM_TINH = Info("Nhà Nam Tinh Quân", 55002, 1)

    /** List chon cua mode "Ve thanh dung yen": Nha Nam Tinh Quan + cac thanh. */
    val CHOICES: Map<String, Info> = linkedMapOf(NHA_NAM_TINH_KEY to NHA_NAM_TINH) + ALL
}
