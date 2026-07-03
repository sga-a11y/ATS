package com.tsbot.android

/**
 * Danh sach server, tuong duong SERVERS dict trong
 * android/app/src/main/python/smoke_login.py. Copy nguyen gia tri, KHONG doan.
 */
object Servers {
    data class Info(val label: String, val ip: String, val serverId: Int)

    val ALL: Map<String, Info> = linkedMapOf(
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
    )
}
