package com.tsbot.android

/** Danh sach EVENT teleport (mode "Event") - key khop voi events.json ben python
 * (train_bot_data/events.json). Mode Event: bot tele toi map event roi DUNG YEN cho nguoi
 * choi tay moi vao party. Moi nick tu di rieng (khong party/sync kenh). Them event moi =
 * them 1 dong o day + 1 entry trong events.json (label chi de hien UI, buoc di nam o json). */
object Events {
    data class Info(val label: String)

    val ALL: Map<String, Info> = linkedMapOf(
        "nhi_kieu" to Info("Nhị Kiều"),
    )
}
