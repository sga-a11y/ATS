package com.tsbot.android

data class Party(
    val name: String,
    val serverKey: String,
    val runMode: String = RunModes.STAND_STILL,
    val cityKey: String = Cities.ALL.keys.first(),
    // Chi dung khi runMode == RunModes.DIGIOI: true = SOLO (moi acc doc lap, khong lap party,
    // khong dong bo kenh) | false = lap party that (leader moi, member accept). Mirror PC's
    // pcfg["digioi_mode"] == "solo" - 1 sub-option BEN TRONG mode "digioi", KHONG phai 2 mode
    // rieng biet o dropdown chinh.
    val digioiSolo: Boolean = false,
    // Chi dung khi runMode == RunModes.DIGIOI va digioiSolo == false (party that): true = "Khong
    // co chu PT" (khong account nao lam leader - moi account la member, dung yen cho leader
    // NGOAI/tay moi party that su, KHONG tu invite, KHONG tu dong reconnect khi rot). Mirror PC's
    // no_leader_var (gui.py) / has_leader = PARTY_LEADER_ACC.get(pidx) is not None.
    val noLeader: Boolean = false,
    val leaderWhitelist: List<String> = emptyList(),
    // Lam nhiem vu hang ngay (bingo 9 o: phó bản đơn, boss thế giới, gacha, hợp đồ... + nhan
    // thuong). Mirror PC's do_daily (gui.py). CHUA duoc noi vao logic chay nao (UI-only, se lam
    // sau) - gia tri mac dinh True khop PC's default.
    val doDaily: Boolean = true,
    // Nhan exp offline luc login. Mac dinh CO tick de giu hanh vi cu.
    val claimOfflineExp: Boolean = true,
    // Danh het luot World Boss luc login trong gio 12h-23h, truoc khi di pho ban doi.
    // Mac dinh CO tick. Neu tat, daily quest o2 van giu hanh vi cu: thieu thi danh 1 lan.
    val autoWorldBoss: Boolean = true,
    // Tu di pho ban doi. Mac dinh: 20/50/80 bat, 110 tat.
    val autoTeamDungeon: Boolean = true,
    val teamDungeons: Map<Int, Boolean> = mapOf(20 to true, 50 to true, 80 to true, 110 to false),
    // Chi dung khi runMode == RunModes.TRAIN: key trong config.TRAIN_MAPS (vd "12831").
    val trainMapKey: String = "",
    // Chi dung khi runMode == RunModes.TRAIN: index trong tm["mobs"] cua map do, -1 = "Bot tu chon"
    // (leader chon ngau nhien moi lan vao/reform). Mirror PC's mob_index (-1 mac dinh).
    val trainMobIndex: Int = -1,
    // Su dung Phuc Than (item nhom "phuc_than" trong use_items.json, dung/trang bi dinh ky 30p/lan
    // - xem use_phuc_than_items() client.py). Mirror PC's use_phuc_than_var (gui.py). Mac dinh
    // KHONG tick (giong PC).
    val usePhucThan: Boolean = false,
    // Dung Di Gioi Ho Phu (0xff8c) khi mode Di Gioi con <15 phut. Check luc login + moi 5p.
    // Mac dinh KHONG tick, mirror PC's use_digioi_ho_phu_var (gui.py).
    val useDigioiHoPhu: Boolean = false,
    // Danh boss QD (do_legion_boss). Mirror PC's fight_boss_var (gui.py). Mac dinh CO tick (giu
    // hanh vi cu - truoc gio luon danh).
    val fightLegionBoss: Boolean = true,
    // Van tieu (do_van_tieu: nhan qua escort + gui pet). Mirror PC's van_tieu_var (gui.py).
    // Mac dinh CO tick (giu hanh vi cu - truoc gio luon lam).
    val doVanTieu: Boolean = true,
    // Tu ban Noi Dat o NPC Nha buon Ng.Thanh khi pre-route random ve Ng.Thanh. Mac dinh CO tick.
    val autoSellNoiDat: Boolean = true,
    // "Tu don tui do" = CONG TONG cua 3 muc con (Noi Dat / item rac / cuon vo tuong rac).
    // Phan giai cuon mac dinh TAT: phan giai la MAT HAN cuon, user phai tu soat list truoc.
    val autoBagClean: Boolean = true,
    val autoDiscardJunk: Boolean = true,
    val autoDecomposeScrolls: Boolean = false,
    // tid_hex -> "keep"/"drop", CHI chua muc user doi khac mac dinh (vkcd = keep)
    val scrollModes: Map<String, String> = emptyMap(),
    // Tu dong gop nguyen lieu cho quan doan (mac dinh BAT). List edit duoc: mac dinh donate HET.
    val autoDonateMaterials: Boolean = true,
    // tid_hex -> "keep", CHI chua nguyen lieu user danh dau GIU (mac dinh donate)
    val materialModes: Map<String, String> = emptyMap(),
    // Mua shop (mac dinh TAT). Master autoBuyShop + list item ben duoi.
    // Ho Phu: mua 3/ngay. Thien Chau: mua 1/ngay. Bao Hop: mua 1/ngay khi xu > baoHopXuThreshold.
    val autoBuyShop: Boolean = false,
    val buyHoPhu: Boolean = false,
    val buyThienChau: Boolean = false,
    val buyBaoHop: Boolean = false,
    val baoHopXuThreshold: Int = 10000000,
    // Tu mua HP/SP (mac dinh TAT): login xong tinh tong HP/SP du tru tu item trong tui; neu <
    // nguong -> di Trac Quan mua Vien Hanh Khi (+62HP) / Thien Kim Du (+62SP), so luong theo *Qty
    // (mua toi da theo xu, 20 xu/cai). 1 lan/ngay/acc. Mirror PC's buy_hp/buy_sp (gui.py).
    val buyHp: Boolean = false,
    val hpQty: Int = 9999,
    val hpThresh: Int = 500000,
    val buySp: Boolean = false,
    val spQty: Int = 9999,
    val spThresh: Int = 500000,
    // Cap quai Di Gioi: idx 1..15 (goi 0x61 02 00 idx) -> cap 10..180. Mac dinh 2 = cap 25.
    val diGioiLevel: Int = 2,
    val accounts: List<Account> = emptyList(),
)

fun Party.copyAdvancedSettingsFrom(source: Party): Party = copy(
    doDaily = source.doDaily,
    claimOfflineExp = source.claimOfflineExp,
    autoWorldBoss = source.autoWorldBoss,
    autoTeamDungeon = source.autoTeamDungeon,
    teamDungeons = source.teamDungeons,
    usePhucThan = source.usePhucThan,
    useDigioiHoPhu = source.useDigioiHoPhu,
    fightLegionBoss = source.fightLegionBoss,
    doVanTieu = source.doVanTieu,
    autoSellNoiDat = source.autoSellNoiDat,
    autoBagClean = source.autoBagClean,
    autoDiscardJunk = source.autoDiscardJunk,
    autoDecomposeScrolls = source.autoDecomposeScrolls,
    scrollModes = source.scrollModes,
    autoDonateMaterials = source.autoDonateMaterials,
    materialModes = source.materialModes,
    autoBuyShop = source.autoBuyShop,
    buyHoPhu = source.buyHoPhu,
    buyThienChau = source.buyThienChau,
    buyBaoHop = source.buyBaoHop,
    baoHopXuThreshold = source.baoHopXuThreshold,
    buyHp = source.buyHp,
    hpQty = source.hpQty,
    hpThresh = source.hpThresh,
    buySp = source.buySp,
    spQty = source.spQty,
    spThresh = source.spThresh,
    // KHONG copy diGioiLevel: cap quai DG la setting RIENG tung party (o section mode Di Gioi),
    // khong duoc "ap dung cho party khac" de len cap cua party do.
)
