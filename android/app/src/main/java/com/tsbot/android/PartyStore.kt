package com.tsbot.android

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** Luu/doc parties.json - moi Party co 1 server rieng (chon 1 lan luc tao Party), cac
 * account trong Party chi can username/password (khong hoi server tung acc nua). */
class PartyStore(private val context: Context) {
    private val file = File(context.filesDir, "parties.json")

    private fun stringList(o: JSONObject, key: String): List<String> {
        val arr = o.optJSONArray(key) ?: return emptyList()
        return (0 until arr.length()).mapNotNull { i ->
            arr.optString(i, "").trim().takeIf { it.isNotEmpty() }
        }
    }

    private fun teamDungeons(o: JSONObject): Map<Int, Boolean> {
        val defaults = linkedMapOf(20 to true, 50 to true, 80 to true, 110 to false)
        val obj = o.optJSONObject("team_dungeons") ?: return defaults
        defaults.keys.toList().forEach { level ->
            if (obj.has(level.toString())) defaults[level] = obj.optBoolean(level.toString(), defaults[level] == true)
        }
        return defaults
    }

    companion object {
        /** Chu ky su kien doi thuong DANG MO (tap key qua cuoi). Rong = chua doc duoc.
         *  Dung CHUNG ham Python voi ban PC (bot/event_exchange.py: cache_signature) de khong
         *  lech. Khong can context nen de o companion -> UI goi PartyStore.eventSigNow(). */
        fun eventSigNow(): String = try {
            com.chaquo.python.Python.getInstance()
                .getModule("train_bot.event_exchange")
                .callAttr("cache_signature")
                .toString()
        } catch (e: Exception) {
            ""
        }
    }

    fun load(): List<Party> {
        if (!file.exists()) return emptyList()
        val arr = JSONArray(file.readText())
        val curSig = eventSigNow()
        val loaded = (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            val accArr = o.getJSONArray("accounts")
            val accounts = (0 until accArr.length()).map { j ->
                val a = accArr.getJSONObject(j)
                Account(
                    a.getString("username"),
                    a.getString("password"),
                    a.optString("battle", ""),
                    healSettingsFromJson(a.optJSONObject("heal")),
                    furnaceConfigFromJson(a.optJSONObject("furnace")),
                    vantieuFromJson(a.optJSONObject("vantieu")),
                    a.optBoolean("enabled", true),
                    a.optString("point", ""),
                )
            }
            val shopItems = o.optJSONObject("shop_items")
            val legacyBuyHoPhu = o.optBoolean("buy_ho_phu", false)
            val legacyBuyThienChau = o.optBoolean("buy_thien_chau", false)
            val legacyBuyBaoHop = o.optBoolean("buy_bao_hop", false)
            val buyHoPhu = shopItems?.optBoolean("ho_phu", legacyBuyHoPhu) ?: legacyBuyHoPhu
            val buyThienChau = shopItems?.optBoolean("thien_chau", legacyBuyThienChau) ?: legacyBuyThienChau
            val buyBaoHop = shopItems?.optBoolean("bao_hop", legacyBuyBaoHop) ?: legacyBuyBaoHop
            Party(
                name = o.getString("name"),
                serverKey = o.getString("server_key"),
                // optString co default: file cu (truoc khi them run_mode/city_key) van doc
                // duoc, tu dong coi la mac dinh - khong can migrate du lieu cu thu cong.
                runMode = o.optString("run_mode", RunModes.STAND_STILL),
                cityKey = o.optString("city_key", Cities.ALL.keys.first()),
                digioiSolo = o.optBoolean("digioi_solo", false),
                noLeader = o.optBoolean("no_leader", false),
                leaderWhitelist = stringList(o, "leaders"),
                doDaily = o.optBoolean("do_daily", true),
                claimOfflineExp = o.optBoolean("claim_offline_exp", true),
                autoWorldBoss = o.optBoolean("auto_world_boss", true),
                autoTeamDungeon = o.optBoolean("auto_team_dungeon", true),
                teamDungeons = teamDungeons(o),
                trainMapKey = o.optString("train_map_key", ""),
                trainMobIndex = o.optInt("train_mob_index", -1),
                trainPick = o.optString("train_pick", ""),
                diGioiPick = o.optString("di_gioi_pick", ""),
                loanDauMotTran = o.optBoolean("loandau_mot_tran", false),
                mobMin = o.optInt("mob_min", 3),
                mobMax = o.optInt("mob_max", 4),
                mobElements = o.optJSONArray("mob_elements")?.let { arr ->
                    (0 until arr.length()).map { arr.getInt(it) }
                } ?: listOf(0, 1, 2, 3, 4, 5, 7, 8),
                usePhucThan = o.optBoolean("use_phuc_than", false),
                useDigioiHoPhu = o.optBoolean("use_digioi_ho_phu", false),
                fightLegionBoss = o.optBoolean("fight_legion_boss", true),
                doVanTieu = o.optBoolean("do_van_tieu", true),
                autoSellNoiDat = o.optBoolean("auto_sell_noi_dat", true),
                deathReturnTown = o.optBoolean("death_return_town", true),
                petDeathReturnTown = o.optBoolean("pet_death_return_town", true),
                autoBagClean = o.optBoolean("auto_bag_clean", true),
                autoDiscardJunk = o.optBoolean("auto_discard_junk", true),
                autoDecomposeScrolls = o.optBoolean("auto_decompose_scrolls", false),
                scrollModes = o.optJSONObject("scroll_modes")?.let { m ->
                    m.keys().asSequence().mapNotNull { k -> m.optString(k, "").takeIf { it.isNotEmpty() }?.let { k to it } }.toMap()
                } ?: emptyMap(),
                autoDonateMaterials = o.optBoolean("auto_donate_materials", true),
                materialModes = o.optJSONObject("material_modes")?.let { m ->
                    m.keys().asSequence().mapNotNull { k -> m.optString(k, "").takeIf { it.isNotEmpty() }?.let { k to it } }.toMap()
                } ?: emptyMap(),
                autoEventExchange = o.optBoolean("auto_event_exchange", false),
                eventExchangeItems = o.optJSONArray("event_exchange_items")?.let { a ->
                    (0 until a.length()).mapNotNull { a.optString(it, "").takeIf { s -> s.isNotEmpty() } }
                } ?: emptyList(),
                eventExchangeSig = o.optString("event_exchange_sig", ""),
                autoBuyShop = o.optBoolean("auto_buy_shop", buyHoPhu || buyThienChau || buyBaoHop),
                buyHoPhu = buyHoPhu,
                buyThienChau = buyThienChau,
                buyBaoHop = buyBaoHop,
                baoHopXuThreshold = o.optInt("bao_hop_xu_threshold", 10000000),
                buyHp = o.optBoolean("buy_hp", false),
                hpQty = o.optInt("hp_qty", 9999),
                hpThresh = o.optInt("hp_thresh", 500000),
                buySp = o.optBoolean("buy_sp", false),
                spQty = o.optInt("sp_qty", 9999),
                spThresh = o.optInt("sp_thresh", 500000),
                diGioiLevel = o.optInt("di_gioi_level", 2),
                accounts = accounts,
            )
        }
        if (curSig.isEmpty()) return loaded    // chua doc duoc su kien -> khong dung vao config
        // Chu ky luc user tick KHAC chu ky hien tai = su kien da doi -> xoa tick (ke ca khi mon
        // do van con o su kien moi: nguyen lieu da khac han, phai bat chon lai).
        // Config cu chua co truong sig -> khong biet thuoc event nao -> cung xoa 1 lan.
        val reset = loaded.map {
            if ((it.autoEventExchange || it.eventExchangeItems.isNotEmpty()) &&
                it.eventExchangeSig != curSig)
                it.copy(autoEventExchange = false, eventExchangeItems = emptyList(),
                        eventExchangeSig = "")
            else it
        }
        if (reset != loaded) save(reset)
        return reset
    }

    fun save(parties: List<Party>) {
        val arr = JSONArray()
        parties.forEach { p ->
            val o = JSONObject()
            o.put("name", p.name)
            o.put("server_key", p.serverKey)
            o.put("run_mode", p.runMode)
            o.put("city_key", p.cityKey)
            o.put("digioi_solo", p.digioiSolo)
            o.put("no_leader", p.noLeader)
            o.put("leaders", JSONArray().apply { p.leaderWhitelist.forEach { put(it) } })
            o.put("do_daily", p.doDaily)
            o.put("claim_offline_exp", p.claimOfflineExp)
            o.put("auto_world_boss", p.autoWorldBoss)
            o.put("auto_team_dungeon", p.autoTeamDungeon)
            o.put("team_dungeons", JSONObject().apply {
                listOf(20, 50, 80, 110).forEach { put(it.toString(), p.teamDungeons[it] ?: false) }
            })
            o.put("train_map_key", p.trainMapKey)
            o.put("train_mob_index", p.trainMobIndex)
            o.put("train_pick", p.trainPick)
            o.put("di_gioi_pick", p.diGioiPick)
            o.put("loandau_mot_tran", p.loanDauMotTran)
            o.put("mob_min", p.mobMin)
            o.put("mob_max", p.mobMax)
            o.put("mob_elements", JSONArray().also { a -> p.mobElements.forEach { a.put(it) } })
            o.put("use_phuc_than", p.usePhucThan)
            o.put("use_digioi_ho_phu", p.useDigioiHoPhu)
            o.put("fight_legion_boss", p.fightLegionBoss)
            o.put("do_van_tieu", p.doVanTieu)
            o.put("auto_sell_noi_dat", p.autoSellNoiDat)
            o.put("death_return_town", p.deathReturnTown)
            o.put("pet_death_return_town", p.petDeathReturnTown)
            o.put("auto_bag_clean", p.autoBagClean)
            o.put("auto_discard_junk", p.autoDiscardJunk)
            o.put("auto_decompose_scrolls", p.autoDecomposeScrolls)
            o.put("scroll_modes", JSONObject().apply { p.scrollModes.forEach { (k, v) -> put(k, v) } })
            o.put("auto_donate_materials", p.autoDonateMaterials)
            o.put("material_modes", JSONObject().apply { p.materialModes.forEach { (k, v) -> put(k, v) } })
            o.put("auto_event_exchange", p.autoEventExchange)
            o.put("event_exchange_items", JSONArray().apply { p.eventExchangeItems.forEach { put(it) } })
            o.put("event_exchange_sig", p.eventExchangeSig)
            o.put("auto_buy_shop", p.autoBuyShop)
            o.put("shop_items", JSONObject().apply {
                put("ho_phu", p.buyHoPhu)
                put("thien_chau", p.buyThienChau)
                put("bao_hop", p.buyBaoHop)
            })
            o.put("buy_ho_phu", p.buyHoPhu)
            o.put("buy_thien_chau", p.buyThienChau)
            o.put("buy_bao_hop", p.buyBaoHop)
            o.put("bao_hop_xu_threshold", p.baoHopXuThreshold)
            o.put("buy_hp", p.buyHp)
            o.put("hp_qty", p.hpQty)
            o.put("hp_thresh", p.hpThresh)
            o.put("buy_sp", p.buySp)
            o.put("sp_qty", p.spQty)
            o.put("sp_thresh", p.spThresh)
            o.put("di_gioi_level", p.diGioiLevel)
            val accArr = JSONArray()
            p.accounts.forEach { a ->
                val ao = JSONObject()
                ao.put("username", a.username)
                ao.put("password", a.password)
                ao.put("enabled", a.enabled)
                if (a.battleJson.isNotBlank()) ao.put("battle", a.battleJson)
                if (a.pointJson.isNotBlank()) ao.put("point", a.pointJson)
                if (!a.heal.isDefault()) ao.put("heal", a.heal.toJsonObject())
                if (!a.furnace.isEmpty()) ao.put("furnace", a.furnace.toJsonObject())
                if (!a.vantieu.isDefault()) ao.put("vantieu", a.vantieu.toJsonObject())
                accArr.put(ao)
            }
            o.put("accounts", accArr)
            arr.put(o)
        }
        file.writeText(arr.toString())
    }

    fun addParty(party: Party): Boolean {
        val current = load()
        if (current.any { it.name.equals(party.name.trim(), ignoreCase = true) }) return false
        save(current + party.copy(name = party.name.trim()))
        return true
    }

    fun removeParty(name: String) {
        save(load().filterNot { it.name == name })
    }

    /** Sua ten/server cua 1 Party (giu nguyen danh sach account ben trong). oldName khac
     * newParty.name khi nguoi dung doi ten Party. */
    fun updateParty(oldName: String, newParty: Party): Boolean {
        val current = load()
        val trimmedName = newParty.name.trim()
        if (current.any {
                it.name != oldName && it.name.equals(trimmedName, ignoreCase = true)
            }
        ) return false
        val updated = current.map { p ->
            if (p.name == oldName) newParty.copy(name = trimmedName) else p
        }
        save(updated)
        return true
    }

    fun applyAdvancedSettingsToOtherParties(sourceName: String, source: Party): Int {
        var count = 0
        val updated = load().map { p ->
            if (p.name == sourceName) {
                p
            } else {
                count += 1
                p.copyAdvancedSettingsFrom(source)
            }
        }
        save(updated)
        return count
    }

    fun applyHealToAllAccounts(heal: HealSettings): Int {
        var count = 0
        val updated = load().map { party ->
            party.copy(accounts = party.accounts.map {
                count += 1
                it.copy(heal = heal)
            })
        }
        save(updated)
        return count
    }

    /** Dong bo O TICK van tieu cho MOI acc. KHONG dong bo list pet: pet nha tro moi acc mot
     *  khac (pet id khac han nhau) nen ap list cua acc nay sang acc khac la vo nghia. */
    fun applyVantieuOnToAllAccounts(on: Boolean): Int {
        var count = 0
        val updated = load().map { party ->
            party.copy(accounts = party.accounts.map {
                count += 1
                it.copy(vantieu = it.vantieu.copy(on = on))
            })
        }
        save(updated)
        return count
    }

    fun applyFurnaceToAllAccounts(furnace: FurnaceConfig): Int {
        var count = 0
        val updated = load().map { party ->
            party.copy(accounts = party.accounts.map {
                count += 1
                it.copy(furnace = furnace)
            })
        }
        save(updated)
        return count
    }

    /** Them/sua acc. Tra false neu party da du 5 acc va day la acc MOI (gioi han 5 acc/party). */
    fun addAccountToParty(partyName: String, account: Account): Boolean {
        val party = load().find { it.name == partyName } ?: return false
        val exists = party.accounts.any { it.username == account.username }
        if (!exists && party.accounts.size >= 5) return false   // GIOI HAN 5 acc / party
        val updated = load().map { p ->
            if (p.name == partyName) {
                p.copy(accounts = p.accounts.filterNot { it.username == account.username } + account)
            } else p
        }
        save(updated)
        return true
    }

    fun removeAccountFromParty(partyName: String, username: String) {
        val updated = load().map { p ->
            if (p.name == partyName) {
                p.copy(accounts = p.accounts.filterNot { it.username == username })
            } else p
        }
        save(updated)
    }

    /** Sua username/password cua 1 account trong Party. oldUsername khac newAccount.username
     * khi nguoi dung doi ten dang nhap. */
    fun updateAccountInParty(partyName: String, oldUsername: String, newAccount: Account) {
        val updated = load().map { p ->
            if (p.name == partyName) {
                p.copy(accounts = p.accounts.map { if (it.username == oldUsername) newAccount else it })
            } else p
        }
        save(updated)
    }
}
