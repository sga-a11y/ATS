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

    fun load(): List<Party> {
        if (!file.exists()) return emptyList()
        val arr = JSONArray(file.readText())
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            val accArr = o.getJSONArray("accounts")
            val accounts = (0 until accArr.length()).map { j ->
                val a = accArr.getJSONObject(j)
                Account(
                    a.getString("username"),
                    a.getString("password"),
                    a.optString("battle", ""),
                    healSettingsFromJson(a.optJSONObject("heal")),
                    a.optBoolean("enabled", true),
                )
            }
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
                trainMapKey = o.optString("train_map_key", ""),
                trainMobIndex = o.optInt("train_mob_index", -1),
                usePhucThan = o.optBoolean("use_phuc_than", false),
                useDigioiHoPhu = o.optBoolean("use_digioi_ho_phu", false),
                fightLegionBoss = o.optBoolean("fight_legion_boss", true),
                doVanTieu = o.optBoolean("do_van_tieu", true),
                autoSellNoiDat = o.optBoolean("auto_sell_noi_dat", true),
                buyHoPhu = o.optBoolean("buy_ho_phu", false),
                buyBaoHop = o.optBoolean("buy_bao_hop", false),
                baoHopXuThreshold = o.optInt("bao_hop_xu_threshold", 1000000),
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
            o.put("train_map_key", p.trainMapKey)
            o.put("train_mob_index", p.trainMobIndex)
            o.put("use_phuc_than", p.usePhucThan)
            o.put("use_digioi_ho_phu", p.useDigioiHoPhu)
            o.put("fight_legion_boss", p.fightLegionBoss)
            o.put("do_van_tieu", p.doVanTieu)
            o.put("auto_sell_noi_dat", p.autoSellNoiDat)
            o.put("buy_ho_phu", p.buyHoPhu)
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
                if (!a.heal.isDefault()) ao.put("heal", a.heal.toJsonObject())
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
