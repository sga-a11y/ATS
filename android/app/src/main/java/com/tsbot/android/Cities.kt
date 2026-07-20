package com.tsbot.android

/** Danh sach thanh de teleport ve (opcode 0x44) - copy tu cities.json (goc du lieu that,
 * xem E:\Claude\ATS\cities.json), dung cho mode "Dung yen tai thanh": nguoi dung chon 1
 * thanh, bot se ve va dung yen tai do. city_id/flag phai dung cap (server tu choi neu sai). */
object Cities {
    data class Info(val label: String, val cityId: Int, val flag: Int)

    val ALL: Map<String, Info> = linkedMapOf(
        "trac_quan" to Info("Trác Quận", 12001, 0),
        "ng_thanh" to Info("Nghiệp Thành", 12061, 2),
        "cu_loc" to Info("Cự Lộc", 12011, 3),
        "bac_hai" to Info("Bắc Hải", 11011, 1),
        "kien_nghiep" to Info("Kiến Nghiệp", 18001, 9),
        "tuong_binh" to Info("Tương Bình", 19001, 11),
        "hoi_ke" to Info("Hội Kê", 18021, 10),
        "lac_duong" to Info("Lạc Dương", 13001, 4),
        "hua_xuong" to Info("Hứa Xương", 13011, 5),
        "truong_an" to Info("Trường An", 14001, 6),
        "tu_chau" to Info("Từ Châu", 15001, 7),
        "tho_xuan" to Info("Thọ Xuân", 15021, 8),
        "thuong_dang" to Info("Thượng Đảng", 20001, 12),
        "lau_bo" to Info("Lâu Bò", 56001, 15),
        "tuong_duong" to Info("Tương Dương", 21001, 13),
        "giang_lang" to Info("Giang Lăng", 21011, 14),
    )
}
