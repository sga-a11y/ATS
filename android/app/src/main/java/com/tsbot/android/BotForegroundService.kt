package com.tsbot.android

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONArray
import java.io.File
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update

/**
 * Chay bot qua coordinator CHUNG voi ban PC: train_bot.run_party_digioi (dong bo tu bot PC bang
 * tools/sync_apk_python.py). Kotlin chi: populate config (setup_party_runtime) -> start_party(pidx)
 * -> POLL account_status() de cap nhat UI -> stop qua stop_party/stop_account. KHONG con logic
 * dieu phoi rieng ben Kotlin/train_runner (fix 1 lan an ca 2 ban).
 */
class BotForegroundService : Service() {

    private val binder = LocalBinder()

    // username -> pidx (party dang chay); dung de poll status + map lenh thu cong.
    private val userPidx = ConcurrentHashMap<String, Int>()
    private val runningPidx = ConcurrentHashMap.newKeySet<Int>()
    private val startingPidx = ConcurrentHashMap.newKeySet<Int>()

    private val _status = MutableStateFlow<Map<String, AccountStatus>>(emptyMap())
    val status: StateFlow<Map<String, AccountStatus>> = _status

    @Volatile private var startGeneration = 0
    @Volatile private var polling = false
    private var pollerThread: Thread? = null

    // Khong co WakeLock -> man hinh tat la CPU vao deep sleep, cac thread bot (ket noi TCP,
    // vong lap combat) bi treo/cham han du foreground service van "song" (foreground service
    // CHI chong bi HE THONG KILL, KHONG tu giu CPU thuc). PARTIAL_WAKE_LOCK giu CPU chay ngam
    // (man hinh van tat binh thuong, tiet kiem pin man hinh) suot thoi gian service song.
    private var wakeLock: PowerManager.WakeLock? = null

    inner class LocalBinder : Binder() {
        fun getService(): BotForegroundService = this@BotForegroundService
    }

    override fun onBind(intent: Intent): IBinder = binder

    override fun onCreate() {
        super.onCreate()
        Servers.init(applicationContext)   // danh sach server doc tu assets/servers.json
        materializeSmartNavAssets()
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        installPythonBundlePath()
        startForeground(1, buildNotification())
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "aTSBot:botService").apply {
            setReferenceCounted(false)
            acquire()
        }
    }

    private fun installPythonBundlePath(excludePidx: Int? = null) {
        val bundlePath = ApkUpdater.pythonBundlePath(this)
        if (!File(bundlePath, "train_bot/run_party_digioi.py").isFile) return
        try {
            // CORE UPDATE FIX: chi insert sys.path[0] la CHUA DU. 2 truong hop van chay code CU:
            //  1) UI (MainActivity) da import train_bot.config tu assets APK TRUOC khi service cam
            //     bundle path -> package train_bot bi cache trong sys.modules tro vao APK cu.
            //  2) Foreground service giu process song: user update core -> file bundle tren dia da
            //     moi nhung sys.modules van giu code cu (tat app cung khong chet process).
            // => sau khi cam path, PURGE moi module train_bot* dang nap tu noi KHAC bundle.
            //    (Chi purge khi bot chua chay account nao - dang chay thi de nguyen, lan Start sau se an.)
            val py = Python.getInstance()
            val p = bundlePath.absolutePath
            val purge = runningPidx.isEmpty() && startingPidx.all { it == excludePidx }
            val coreVer = try { ApkUpdater.installedBundleVersion(this) } catch (e: Exception) { "?" }
            // PURGE TAT CA module train_bot*, KHONG loc theo duong dan.
            // pythonBundlePath() la duong dan CO DINH (bot_bundle/current/android): update core chi
            // GHI DE file BEN TRONG, duong dan khong doi -> module cu van co __file__ bat dau bang
            // _p -> phep loc "khac duong dan" cu KHONG bao gio thay chung la cu -> process chay code
            // cu mai cho toi khi bi kill. Bug that: core v1.1.202608100031 tren dia nhung log boss
            // van thieu dong "Boss QD: tran ket thuc" cua ban do.
            val code = """
import sys, logging
_p = ${'"'}${'"'}${'"'}$p${'"'}${'"'}${'"'}
_ver = ${'"'}${'"'}${'"'}$coreVer${'"'}${'"'}${'"'}
_prev = getattr(sys, "__ats_core_loaded__", None)
if _p not in sys.path:
    sys.path.insert(0, _p)
if (not ${if (purge) "True" else "False"}) and _prev is not None and _prev != _ver:
    # Co core MOI tren dia nhung dang co acc chay -> KHONG dam purge (thread dang chay giu tham
    # chieu module cu; purge nua chung se thanh nua cu nua moi). Bao TO ra de user biet phai dung
    # het roi chay lai, khong thi cu tuong da cap nhat ma van chay code cu (bug that 00:50).
    logging.getLogger("bot").warning(
        "CORE MOI v%s DA TAI nhung dang co acc CHAY -> VAN chay code cu v%s. "
        "DUNG TAT CA roi chay lai de ap dung.", _ver, _prev)
if ${if (purge) "True" else "False"}:
    _stale = [_n for _n, _m in list(sys.modules.items())
              if _n == "train_bot" or _n.startswith("train_bot.")]
    for _n in _stale:
        del sys.modules[_n]
    if _stale:
        logging.getLogger("bot").warning("CORE RELOAD: bo %d module de nap lai tu bundle: %s",
                                         len(_stale), sorted(_stale))
import train_bot.client as _c
sys.__ats_core_loaded__ = _ver
logging.getLogger("bot").info("CORE LOAD: core=v%s client=%s", _ver, getattr(_c, "__file__", "?"))
""".trimIndent()
            py.getModule("builtins").callAttr("exec", code)
        } catch (e: Exception) {
            android.util.Log.w("aTSBot", "install bundle path failed: ${e.message}", e)
        }
    }

    private fun materializeSmartNavAssets() {
        val nav = File(filesDir, "world_nav.json")
        val ground = File(filesDir, "gamedata/Ground.mmg")
        val sceneFight = File(filesDir, "gamedata/SceneFight_C.dat")
        val itemData = File(filesDir, "items_gamedata.json")
        val prefs = getSharedPreferences("smart_nav_assets", Context.MODE_PRIVATE)
        val currentVersion = BuildConfig.VERSION_CODE
        if (prefs.getInt("version", -1) == currentVersion && nav.isFile && ground.isFile && sceneFight.isFile && itemData.isFile) {
            return
        }
        copyBundledAsset("world_nav.json", nav)
        copyBundledAsset("gamedata/Ground.mmg", ground)
        copyBundledAsset("gamedata/SceneFight_C.dat", sceneFight)
        copyBundledAsset("items_gamedata.json", itemData)
        prefs.edit().putInt("version", currentVersion).apply()
    }

    private fun copyBundledAsset(name: String, target: File) {
        target.parentFile?.mkdirs()
        val temporary = File(target.parentFile, ".${target.name}.tmp")
        assets.open("train_bot_data/$name").use { input ->
            temporary.outputStream().use { output -> input.copyTo(output) }
        }
        if (target.exists() && !target.delete()) {
            temporary.delete()
            error("Khong thay duoc asset cu: ${target.path}")
        }
        if (!temporary.renameTo(target)) {
            temporary.copyTo(target, overwrite = true)
            temporary.delete()
        }
    }

    private fun buildNotification(): Notification {
        val channelId = "tsbot_service"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(channelId, "aTSBot", NotificationManager.IMPORTANCE_LOW)
            (getSystemService(NotificationManager::class.java)).createNotificationChannel(channel)
        }
        return Notification.Builder(this, channelId)
            .setContentTitle("aTSBot dang chay")
            .setSmallIcon(android.R.drawable.ic_media_play)
            .build()
    }

    private fun rpd(): PyObject = Python.getInstance().getModule("train_bot.run_party_digioi")

    // --- map RunMode (UI) -> config mode/param cua ban PC ---
    private data class ModeCfg(
        val mode: String, val startCity: Int, val cityFlag: Int, val mobIndex: Int,
        val eventKey: String, val digioiMode: String, val hasLeader: Boolean,
    )

    private fun mapMode(party: Party): ModeCfg = when (party.runMode) {
        RunModes.STAND_STILL -> {   // ve thanh dung yen = PC "city"
            val c = Cities.ALL[party.cityKey]
            ModeCfg("city", c?.cityId ?: 0, c?.flag ?: 0, -1, "", "party", false)
        }
        RunModes.STAY_LOGIN -> ModeCfg("stand", 0, 0, -1, "", "party", false)   // login dung yen do
        RunModes.DIGIOI_TRAIN -> ModeCfg(
            "digioi_train", party.trainMapKey.toIntOrNull() ?: 0, 0, party.trainMobIndex,
            "", "party", !party.noLeader,
        )
        RunModes.TRAIN -> ModeCfg(
            "train", party.trainMapKey.toIntOrNull() ?: 0, 0, party.trainMobIndex,
            "", "party", !party.noLeader,
        )
        RunModes.DIGIOI -> ModeCfg(
            "digioi", 0, 0, -1, "",
            if (party.digioiSolo) "solo" else "party",
            if (party.digioiSolo) false else !party.noLeader,
        )
        RunModes.EVENT -> ModeCfg("event", 0, 0, -1, party.cityKey, "party", false)
        else -> ModeCfg("stand", 0, 0, -1, "", "party", false)
    }

    @Synchronized
    private fun startPartyNow(
        pidx: Int,
        party: Party,
        serverIp: String,
        serverId: Int,
        generation: Int,
    ) {
        val activeAccounts = party.accounts.filter { it.enabled }
        if (activeAccounts.isEmpty() || pidx in runningPidx || !startingPidx.add(pidx)) return
        // Moi lan Start: cam lai bundle + purge module cu (neu vua update core ma process chua chet)
        installPythonBundlePath(excludePidx = pidx)
        activeAccounts.forEach { account ->
            _status.update { it + (account.username to AccountStatus(RunState.CONNECTING)) }
        }
        try {
            if (generation != startGeneration) return
            val m = mapMode(party)
            // 1 CHUOI STRING duy nhat (KHONG phai List<String>/List<List<String>>) - da xac nhan qua
            // logcat that: ke ca List<String> PHANG, Chaquopy van khong convert dung thanh Python
            // list khi truyen qua callAttr ("TypeError: 'ArrayList' object is not iterable" ngay tai
            // list(accounts) phia Python). String thi luon convert dung -> join bang ky tu phan tach
            // hiem gap (U+0001), Python tu split() lai.
            val SEP = ""
            val accountsFlat = activeAccounts.joinToString(SEP) {
                "${it.username}$SEP${it.password}$SEP${it.battleJson}$SEP${it.heal.toRuntimeJson()}" +
                    "$SEP${it.furnace.toRuntimeJson()}"
            }
            val py = rpd()
            val leaders = party.leaderWhitelist.joinToString("\n")
            py.callAttr(
                "setup_party_runtime", pidx, m.mode, serverIp, serverId, accountsFlat,
                m.cityFlag, m.startCity, m.mobIndex, party.doDaily, m.digioiMode, m.eventKey,
                leaders, m.hasLeader, party.usePhucThan, party.useDigioiHoPhu,
                party.fightLegionBoss, party.doVanTieu,
                party.buyHoPhu, party.buyBaoHop, party.baoHopXuThreshold,
                party.diGioiLevel, party.autoSellNoiDat,
                party.buyHp, party.hpQty, party.hpThresh,
                party.buySp, party.spQty, party.spThresh,
                party.claimOfflineExp,
                party.autoTeamDungeon, teamDungeonsJson(party.teamDungeons),
                party.autoBuyShop, party.buyThienChau,
                party.autoWorldBoss,
                // THEM O CUOI signature Python (setup_party_runtime) - goi THEO VI TRI
                party.autoBagClean, party.autoDiscardJunk,
                party.autoDecomposeScrolls, party.scrollModes,
                party.autoDonateMaterials, party.materialModes,
                party.autoEventExchange, party.eventExchangeItems,
            )
            if (generation != startGeneration) return
            py.callAttr("start_party", pidx)
            if (generation == startGeneration) {
                runningPidx.add(pidx)
                activeAccounts.forEach { userPidx[it.username] = pidx }
                ensurePoller()
            }
        } catch (e: Exception) {
            android.util.Log.e("aTSBot", "startParty loi (pidx=$pidx): ${e.message}", e)
            activeAccounts.forEach { account ->
                _status.update { s ->
                    s + (account.username to AccountStatus(RunState.ERROR, message = e.message ?: "loi khoi dong"))
                }
            }
        } finally {
            startingPidx.remove(pidx)
        }
    }

    /** Khoi dong 1 PARTY (pidx = vi tri party trong danh sach app - on dinh trong phien). */
    fun startParty(pidx: Int, party: Party, serverIp: String, serverId: Int) {
        val generation = startGeneration
        Thread({
            startPartyNow(pidx, party, serverIp, serverId, generation)
        }).also {
            it.name = "aTSBot-start-party-$pidx"
            it.isDaemon = true
            it.start()
        }
    }

    /** Khoi dong lan luot de setup runtime cua cac party khong ghi de nhau. */
    fun startAll(parties: List<Party>) {
        val generation = startGeneration
        Thread({
            parties.forEachIndexed { pidx, party ->
                if (generation != startGeneration) return@Thread
                val server = Servers.ALL[party.serverKey] ?: return@forEachIndexed
                startPartyNow(pidx, party, server.ip, server.serverId, generation)
            }
        }).also {
            it.name = "aTSBot-start-all"
            it.isDaemon = true
            it.start()
        }
    }

    private fun ensurePoller() {
        if (polling) return
        polling = true
        pollerThread = Thread {
            while (polling) {
                try {
                    val py = rpd()
                    val runningNow = HashSet<Int>()
                    userPidx.keys.toList().forEach { u ->
                        val d = py.callAttr("account_status", u) ?: return@forEach
                        val st = statusFromPy(d)
                        _status.update { it + (u to st) }
                        if (st.state == RunState.RUNNING) userPidx[u]?.let { runningNow.add(it) }
                    }
                    // Tu lanh: acc tu thoat / bi Dung (stopAccount) khong xoa runningPidx ->
                    // guard "pidx in runningPidx" chan restart vinh vien (Chay tat ca ko tac dung).
                    // Doi chieu voi trang thai that: pidx nao khong con acc chay & khong dang start -> bo.
                    runningPidx.retainAll { it in runningNow || it in startingPidx }
                } catch (_: Exception) {
                }
                try { Thread.sleep(1500) } catch (_: InterruptedException) { }
            }
        }.also { it.isDaemon = true; it.start() }
    }

    private fun statusFromPy(d: PyObject): AccountStatus {
        // callAttr("get", k) tra ve PyObject (co the boc Python None) -> toInt()/toBoolean() tren None
        // nem exception -> boc try, None -> null.
        fun gInt(k: String): Int? = try { d.callAttr("get", k)?.toInt() } catch (_: Exception) { null }
        fun gBool(k: String): Boolean = try { d.callAttr("get", k)?.toBoolean() ?: false } catch (_: Exception) { false }
        fun gString(k: String): String = try { d.callAttr("get", k)?.toString() ?: "" } catch (_: Exception) { "" }
        val running = gBool("running")
        return AccountStatus(
            state = if (running) RunState.RUNNING else RunState.STOPPED,
            hp = gInt("hp"),
            sp = gInt("sp"),
            hpMax = gInt("hp_max"),
            spMax = gInt("sp_max"),
            charName = gString("char"),
            charLevel = gInt("char_level"),
            charAgi = gInt("char_agi"),
            petName = gString("pet_name"),
            petLevel = gInt("pet_level"),
            petAgi = gInt("pet_agi"),
            partyAvgLevel = gInt("party_avg_level"),
            mapId = gInt("map"),
            channel = gInt("channel"),
            message = "",
        )
    }

    // --- SOI LO: thong bao "Chu y" (item lo mode notify) ---
    /** [{user, tab, id, name, bag, slot, kind}] cua ca party. Du lieu THO, UI tu dung cau chu. */
    fun furnaceNotifyItems(pidx: Int): List<Map<String, String>> {
        return try {
            val lst = rpd().callAttr("furnace_notify_items", pidx)?.asList() ?: return emptyList()
            lst.mapNotNull { po ->
                try {
                    val m = HashMap<String, String>()
                    for (k in listOf("user", "tab", "id", "name", "bag", "slot", "kind", "new")) {
                        po.callAttr("get", k)?.let { m[k] = it.toString() }
                    }
                    m
                } catch (_: Exception) { null }
            }
        } catch (_: Exception) { emptyList() }
    }

    fun furnaceNotifyCount(pidx: Int): Int =
        try { rpd().callAttr("furnace_notify_count", pidx)?.toInt() ?: 0 } catch (_: Exception) { 0 }

    fun furnaceNotifyBuy(username: String, tid: Int): Boolean =
        try { rpd().callAttr("furnace_notify_buy", username, tid)?.toBoolean() ?: false }
        catch (_: Exception) { false }

    fun furnaceNotifySkip(username: String, tid: Int): Boolean =
        try { rpd().callAttr("furnace_notify_skip", username, tid)?.toBoolean() ?: false }
        catch (_: Exception) { false }

    fun stopParty(pidx: Int) {
        try { rpd().callAttr("stop_party", pidx) } catch (_: Exception) { }
        runningPidx.remove(pidx)
        userPidx.filterValues { it == pidx }.keys.forEach { userPidx.remove(it) }
    }

    fun stopAccount(username: String) {
        try { rpd().callAttr("stop_account", username) } catch (_: Exception) { }
    }

    fun stopAll() {
        startGeneration += 1
        // Dung lai CHINH flow stopParty da hoat dong on dinh. Snapshot truoc vi stopParty se
        // xoa runningPidx/userPidx trong luc lap.
        val partiesToStop = (
            runningPidx.toSet() + startingPidx.toSet() + userPidx.values.toSet()
        ).sorted()
        partiesToStop.forEach { stopParty(it) }
        startingPidx.clear()
        _status.update { current ->
            current.mapValues { AccountStatus(RunState.IDLE) }
        }
    }

    // --- lenh LIVE (doi kenh / teleport thanh / giftcode) - map username -> pidx ---
    private fun pidxSet(usernames: List<String>): List<Int> =
        usernames.mapNotNull { userPidx[it] }.distinct()

    fun sendChannel(usernames: List<String>, ch: Int) {
        pidxSet(usernames).forEach { try { rpd().callAttr("party_switch_channel", it, ch) } catch (_: Exception) {} }
    }

    fun sendChannelAuto(usernames: List<String>) {
        // -1 = tu chon kenh (run_party_digioi.party_switch_channel: ch<=0 -> pick_best)
        pidxSet(usernames).forEach { try { rpd().callAttr("party_switch_channel", it, 0) } catch (_: Exception) {} }
    }

    fun sendCity(usernames: List<String>, cityId: Int, flag: Int) {
        pidxSet(usernames).forEach { try { rpd().callAttr("party_teleport_city", it, cityId, flag) } catch (_: Exception) {} }
    }

    // Doi cap quai Di Gioi LIVE cho party (idx 1..15) - goi party_set_di_gioi_level (gui 0x61 02 00 idx).
    fun setDiGioiLevel(usernames: List<String>, idx: Int) {
        pidxSet(usernames).forEach { try { rpd().callAttr("party_set_di_gioi_level", it, idx) } catch (_: Exception) {} }
    }

    fun sendRouteMaps(usernames: List<String>, sourceMap: Int, destMap: Int) {
        pidxSet(usernames).forEach { try { rpd().callAttr("party_route_maps", it, sourceMap, destMap) } catch (_: Exception) {} }
    }

    fun sendGiftcode(usernames: List<String>, code: String) {
        pidxSet(usernames).forEach { try { rpd().callAttr("redeem_giftcode_party", it, code) } catch (_: Exception) {} }
    }

    /** Query danh sach kenh (BLOCKING - goi tu background). Tra [channel, so_nguoi, suc_chua]. */
    fun getChannels(username: String): List<Triple<Int, Int, Int>> {
        val pidx = userPidx[username] ?: return emptyList()
        return try {
            // get_channel_list tra DICT {ch: (cur, cap)}
            val res = rpd().callAttr("get_channel_list", pidx) ?: return emptyList()
            res.asMap().map { (k, v) ->
                val pair = v.asList()
                Triple(k.toInt(), pair[0].toInt(), pair[1].toInt())
            }.sortedBy { it.first }
        } catch (e: Exception) {
            emptyList()
        }
    }

    /** Kenh dang o cua account (tu account_status.channel). */
    fun currentChannel(username: String): Int? {
        return try {
            val d = rpd().callAttr("account_status", username) ?: return null
            d.callAttr("get", "channel")?.toInt()
        } catch (e: Exception) {
            null
        }
    }

    /** Skill set cua 1 pet mang theo - tab per-pet trong dialog Kich ban Skill. */
    data class PetSkillSet(val pid: Int, val name: String, val skills: List<SkillChoice>)
    data class AccountSkills(
        val char: List<SkillChoice>,
        val pet: List<SkillChoice>,
        val pets: List<PetSkillSet>,
        val activePid: Int,
    )

    fun accountSkills(username: String): AccountSkills {
        fun parseSkill(item: PyObject): SkillChoice? {
            return try {
                val parts = item.asList()
                val id = parts.getOrNull(0)?.toInt() ?: return null
                val name = parts.getOrNull(1)?.toString()
                    ?.takeIf { it.isNotBlank() && it != "None" }
                    ?: "Skill $id"
                val cost = parts.getOrNull(2)?.toString()?.toIntOrNull()
                val cat = parts.getOrNull(3)?.toString()?.toIntOrNull()
                SkillChoice(id, name, cost, cat)
            } catch (_: Exception) {
                try {
                    val id = item.toInt()
                    SkillChoice(id, "Skill $id")
                } catch (_: Exception) {
                    null
                }
            }
        }

        val empty = AccountSkills(emptyList(), emptyList(), emptyList(), 0)
        return try {
            val d = rpd().callAttr("account_skills", username) ?: return empty
            val charSkills = d.callAttr("get", "char")?.asList()?.mapNotNull { parseSkill(it) } ?: emptyList()
            val petSkills = d.callAttr("get", "pet")?.asList()?.mapNotNull { parseSkill(it) } ?: emptyList()
            val pets = d.callAttr("get", "pets")?.asList()?.mapNotNull { row ->
                try {
                    val parts = row.asList()
                    PetSkillSet(
                        parts[0].toInt(),
                        parts[1].toString(),
                        parts[2].asList().mapNotNull { parseSkill(it) },
                    )
                } catch (_: Exception) { null }
            } ?: emptyList()
            val active = try { d.callAttr("get", "active")?.toInt() ?: 0 } catch (_: Exception) { 0 }
            AccountSkills(charSkills, petSkills, pets, active)
        } catch (e: Exception) {
            empty
        }
    }

    fun applyAccountBattle(username: String, battleJson: String): Boolean {
        return try {
            rpd().callAttr("apply_account_battle", username, battleJson)?.toBoolean() ?: false
        } catch (e: Exception) {
            false
        }
    }

    fun dangerousNpcNames(): List<String> {
        return try {
            rpd().callAttr("dangerous_npc_names")
                ?.asList()
                ?.map { it.toString() }
                ?.filter { it.isNotBlank() }
                ?: emptyList()
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun saveDangerousNpcNames(names: List<String>): Boolean {
        return try {
            val arr = JSONArray()
            names.forEach { name ->
                val clean = name.trim()
                if (clean.isNotEmpty()) arr.put(clean)
            }
            rpd().callAttr("save_dangerous_npc_names", arr.toString())?.toBoolean() ?: false
        } catch (e: Exception) {
            false
        }
    }

    fun applyAccountHeal(username: String, healJson: String): Boolean {
        return try {
            rpd().callAttr("apply_account_heal", username, healJson)?.toBoolean() ?: false
        } catch (e: Exception) {
            false
        }
    }

    fun applyAccountFurnace(username: String, furnaceJson: String): Boolean {
        return try {
            rpd().callAttr("apply_account_furnace", username, furnaceJson)?.toBoolean() ?: false
        } catch (e: Exception) {
            false
        }
    }

    fun isRunning(username: String): Boolean {
        return try {
            rpd().callAttr("is_account_running", username)?.toBoolean() ?: false
        } catch (e: Exception) {
            userPidx.containsKey(username)
        }
    }

    /** Log rieng cua 1 acc (party.log loc theo username - xem get_account_log ben Python: loc
     * CA username LAN ten nhan vat hien tai, vi nhan log tu doi ten sau khi resolve xong). */
    fun getAccountLog(username: String, maxLines: Int = 500): String {
        return try {
            rpd().callAttr("get_account_log", username, maxLines)?.toString() ?: ""
        } catch (e: Exception) {
            "Loi doc log: ${e.message}"
        }
    }

    override fun onDestroy() {
        polling = false
        stopAll()
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
        super.onDestroy()
    }
}
