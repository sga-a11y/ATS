package com.tsbot.android

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** Luu/doc parties.json - moi Party co 1 server rieng (chon 1 lan luc tao Party), cac
 * account trong Party chi can username/password (khong hoi server tung acc nua). */
class PartyStore(private val context: Context) {
    private val file = File(context.filesDir, "parties.json")

    fun load(): List<Party> {
        if (!file.exists()) return emptyList()
        val arr = JSONArray(file.readText())
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            val accArr = o.getJSONArray("accounts")
            val accounts = (0 until accArr.length()).map { j ->
                val a = accArr.getJSONObject(j)
                Account(a.getString("username"), a.getString("password"))
            }
            Party(o.getString("name"), o.getString("server_key"), accounts)
        }
    }

    fun save(parties: List<Party>) {
        val arr = JSONArray()
        parties.forEach { p ->
            val o = JSONObject()
            o.put("name", p.name)
            o.put("server_key", p.serverKey)
            val accArr = JSONArray()
            p.accounts.forEach { a ->
                val ao = JSONObject()
                ao.put("username", a.username)
                ao.put("password", a.password)
                accArr.put(ao)
            }
            o.put("accounts", accArr)
            arr.put(o)
        }
        file.writeText(arr.toString())
    }

    fun addParty(party: Party) {
        val current = load().filterNot { it.name == party.name }
        save(current + party)
    }

    fun removeParty(name: String) {
        save(load().filterNot { it.name == name })
    }

    fun addAccountToParty(partyName: String, account: Account) {
        val updated = load().map { p ->
            if (p.name == partyName) {
                p.copy(accounts = p.accounts.filterNot { it.username == account.username } + account)
            } else p
        }
        save(updated)
    }

    fun removeAccountFromParty(partyName: String, username: String) {
        val updated = load().map { p ->
            if (p.name == partyName) {
                p.copy(accounts = p.accounts.filterNot { it.username == username })
            } else p
        }
        save(updated)
    }
}
