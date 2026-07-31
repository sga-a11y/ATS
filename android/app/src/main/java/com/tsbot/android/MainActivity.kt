package com.tsbot.android

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.IBinder
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.KeyboardType
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

class MainActivity : ComponentActivity() {
    private var boundService by mutableStateOf<BotForegroundService?>(null)

    // KHONG stopService() o onDestroy: dich vu foreground PHAI song sau khi Activity dong
    // (nguoi dung tat man hinh nhung bot van chay nen) - chi unbindService de gia phong
    // ServiceConnection cua rieng Activity nay, KHONG dung lai Service.
    private var isBound = false

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            boundService = (service as BotForegroundService.LocalBinder).getService()
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            boundService = null
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val serviceIntent = Intent(this, BotForegroundService::class.java)
        ContextCompat.startForegroundService(this, serviceIntent)
        isBound = bindService(serviceIntent, connection, Context.BIND_AUTO_CREATE)

        setContent {
            TsBotTheme {
                Surface(color = MaterialTheme.colorScheme.background) {
                    TsBotApp(
                        boundServiceProvider = { boundService },
                        partyStore = PartyStore(this),
                    )
                }
            }
        }
    }

    override fun onDestroy() {
        // bindService() co the tra false (vd Service khong the start) - goi unbindService()
        // tren connection chua tung dang ky se nem IllegalArgumentException, lam crash
        // ca onDestroy. Chi unbind neu bindService() da thanh cong.
        if (isBound) {
            unbindService(connection)
            isBound = false
        }
        super.onDestroy()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TsBotApp(
    boundServiceProvider: () -> BotForegroundService?,
    partyStore: PartyStore,
) {
    var parties by remember { mutableStateOf(partyStore.load()) }
    var showAddPartyDialog by remember { mutableStateOf(false) }
    // Party dang mo dialog "them acc" (null = khong dialog nao dang mo)
    var addAccountForParty by remember { mutableStateOf<String?>(null) }
    // Party dang duoc sua (ten/server) - null = khong sua party nao
    var editingParty by remember { mutableStateOf<Party?>(null) }
    // (ten party, account) dang duoc sua (user/pass) - null = khong sua acc nao
    var editingAccount by remember { mutableStateOf<Pair<String, Account>?>(null) }
    // Tab party dang chon (moi party = 1 tab, giong ban PC)
    var selectedTab by remember { mutableStateOf(0) }

    val service = boundServiceProvider()
    val statusMap by (service?.status?.collectAsState() ?: remember { mutableStateOf(emptyMap()) })
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var updateInfo by remember { mutableStateOf<ApkUpdateInfo?>(null) }
    var updateBusyText by remember { mutableStateOf<String?>(null) }
    var updateMessage by remember { mutableStateOf<Pair<String, String>?>(null) }
    var pendingInstallApk by remember { mutableStateOf<File?>(null) }

    fun refresh() {
        parties = partyStore.load()
    }

    fun checkApkUpdate(manual: Boolean) {
        if (updateBusyText != null) return
        scope.launch {
            if (manual) updateBusyText = "Đang kiểm tra bản mới..."
            try {
                val info = withContext(Dispatchers.IO) {
                    ApkUpdater.checkUpdate(BuildConfig.VERSION_NAME)
                }
                if (info != null) {
                    updateInfo = info
                } else if (manual) {
                    updateMessage = "Update" to "Đang là bản mới nhất (${BuildConfig.VERSION_NAME})."
                }
            } catch (e: Exception) {
                if (manual) {
                    updateMessage = "Lỗi cập nhật" to
                        "Không kiểm tra được bản mới:\n${e.message ?: e.javaClass.simpleName}\n\nTải thủ công:\n${ApkUpdater.MANUAL_DOWNLOAD_URL}"
                }
            } finally {
                if (manual) updateBusyText = null
            }
        }
    }

    fun downloadAndInstall(info: ApkUpdateInfo) {
        if (updateBusyText != null) return
        updateInfo = null
        scope.launch {
            updateBusyText = "Đang tải APK v${info.version}..."
            try {
                val apk = withContext(Dispatchers.IO) {
                    ApkUpdater.downloadApk(context.applicationContext, info)
                }
                updateBusyText = null
                if (ApkUpdater.canInstallApk(context)) {
                    ApkUpdater.installApk(context, apk)
                } else {
                    pendingInstallApk = apk
                }
            } catch (e: Exception) {
                updateBusyText = null
                updateMessage = "Lỗi cập nhật" to
                    "Không tải/cài được APK:\n${e.message ?: e.javaClass.simpleName}\n\nTải thủ công:\n${ApkUpdater.MANUAL_DOWNLOAD_URL}"
            }
        }
    }

    LaunchedEffect(Unit) {
        delay(1500)
        checkApkUpdate(manual = false)
    }

    // Coordinator CHUNG (run_party_digioi): moi mode deu khoi dong theo PARTY (pidx = vi tri party
    // trong danh sach). Bam Start 1 account = khoi dong CA party (giong PC). Service tu map RunMode
    // -> config mode/param va goi setup_party_runtime + start_party.
    fun startPartyIn(party: Party) {
        val info = Servers.ALL[party.serverKey] ?: return
        val pidx = parties.indexOf(party)
        if (pidx >= 0) service?.startParty(pidx, party, info.ip, info.serverId)
    }

    fun startAccountIn(party: Party, account: Account) = startPartyIn(party)

    val runningCount = statusMap.values.count { it.state == RunState.RUNNING }
    val totalAccounts = parties.sumOf { it.accounts.size }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("aTSBot", fontWeight = FontWeight.Bold)
                        Spacer(Modifier.width(10.dp))
                        if (totalAccounts > 0) {
                            StatusDot(if (runningCount > 0) StatusRunning else StatusStopped)
                            Spacer(Modifier.width(6.dp))
                            Text(
                                "$runningCount/$totalAccounts đang chạy",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    titleContentColor = MaterialTheme.colorScheme.onSurface,
                ),
                actions = {
                    TextButton(
                        onClick = { checkApkUpdate(manual = true) },
                        enabled = updateBusyText == null,
                    ) { Text("Check Update") }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { showAddPartyDialog = true }) {
                Icon(Icons.Default.Add, contentDescription = "Thêm party")
            }
        },
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize()) {
            if (parties.isEmpty()) {
                Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
                    Text("Chưa có party nào", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(12.dp))
                    Button(onClick = { showAddPartyDialog = true }) {
                        Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(4.dp)); Text("Tạo party")
                    }
                }
            } else {
                // Moi party = 1 TAB (giong ban PC). Tab hien ten party + cham trang thai.
                val curTab = selectedTab.coerceIn(0, parties.size - 1)
                ScrollableTabRow(
                    selectedTabIndex = curTab,
                    containerColor = MaterialTheme.colorScheme.surface,
                    edgePadding = 8.dp,
                ) {
                    parties.forEachIndexed { i, p ->
                        val runningInP = p.accounts.count { statusMap[it.username]?.state == RunState.RUNNING }
                        Tab(
                            selected = i == curTab,
                            onClick = { selectedTab = i },
                            text = {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    StatusDot(if (runningInP > 0) StatusRunning else StatusStopped, 8)
                                    Spacer(Modifier.width(6.dp))
                                    Text(p.name)
                                }
                            },
                        )
                    }
                }

                val party = parties[curTab]
                Column(
                    modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(12.dp),
                ) {
                    PartyCard(
                        party = party,
                        statusMap = statusMap,
                        onAddAccount = { addAccountForParty = party.name },
                        onEditParty = { editingParty = party },
                        onEditAccount = { account -> editingAccount = party.name to account },
                        onRemoveAccount = { username ->
                            partyStore.removeAccountFromParty(party.name, username)
                            refresh()
                        },
                        onRemoveParty = {
                            partyStore.removeParty(party.name)
                            selectedTab = 0
                            refresh()
                        },
                        onStart = { account -> startAccountIn(party, account) },
                        onStop = { username -> service?.stopAccount(username) },
                        onStartParty = { startPartyIn(party) },
                        onStopParty = { party.accounts.forEach { service?.stopAccount(it.username) } },
                        onSendChannel = { ch -> service?.sendChannel(party.accounts.map { it.username }, ch) },
                        onSendChannelAuto = { service?.sendChannelAuto(party.accounts.map { it.username }) },
                        onSendCity = { id, flag -> service?.sendCity(party.accounts.map { it.username }, id, flag) },
                        onSendRouteMaps = { source, dest -> service?.sendRouteMaps(party.accounts.map { it.username }, source, dest) },
                        onSendGiftcode = { code -> service?.sendGiftcode(party.accounts.map { it.username }, code) },
                        onGetChannels = {
                            party.accounts.firstOrNull { service?.isRunning(it.username) == true }
                                ?.let { service?.getChannels(it.username) } ?: emptyList()
                        },
                        onCurrentChannel = {
                            party.accounts.firstOrNull { service?.isRunning(it.username) == true }
                                ?.let { service?.currentChannel(it.username) }
                        },
                        onGetLog = { username -> service?.getAccountLog(username) ?: "" },
                    )
                }
            }
        }
    }

    val busy = updateBusyText
    if (busy != null) {
        AlertDialog(
            onDismissRequest = {},
            title = { Text("Update") },
            text = { Text(busy) },
            confirmButton = {},
        )
    }

    val availableUpdate = updateInfo
    if (availableUpdate != null) {
        AlertDialog(
            onDismissRequest = { updateInfo = null },
            title = { Text("Có bản mới ${availableUpdate.version}") },
            text = {
                Column {
                    Text("Bản hiện tại: ${BuildConfig.VERSION_NAME}")
                    if (availableUpdate.notes.isNotBlank()) {
                        Spacer(Modifier.height(8.dp))
                        Text(availableUpdate.notes)
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { downloadAndInstall(availableUpdate) }) {
                    Text("Tải và cài")
                }
            },
            dismissButton = {
                TextButton(onClick = { updateInfo = null }) { Text("Để sau") }
            },
        )
    }

    val apkToInstall = pendingInstallApk
    if (apkToInstall != null) {
        AlertDialog(
            onDismissRequest = { pendingInstallApk = null },
            title = { Text("Cài APK mới") },
            text = {
                Text(
                    "Android cần quyền cài ứng dụng không rõ nguồn cho aTSBot. " +
                        "Nếu chưa bật quyền, bấm Tiếp tục để mở cài đặt, bật xong quay lại bấm Tiếp tục lần nữa."
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        if (ApkUpdater.canInstallApk(context)) {
                            pendingInstallApk = null
                            ApkUpdater.installApk(context, apkToInstall)
                        } else {
                            ApkUpdater.openInstallPermissionSettings(context)
                        }
                    },
                ) { Text("Tiếp tục") }
            },
            dismissButton = {
                TextButton(onClick = { pendingInstallApk = null }) { Text("Để sau") }
            },
        )
    }

    val message = updateMessage
    if (message != null) {
        AlertDialog(
            onDismissRequest = { updateMessage = null },
            title = { Text(message.first) },
            text = { Text(message.second) },
            confirmButton = {
                TextButton(onClick = { updateMessage = null }) { Text("Đóng") }
            },
        )
    }

    if (showAddPartyDialog) {
        AddPartyDialog(
            onDismiss = { showAddPartyDialog = false },
            onSave = { party ->
                partyStore.addParty(party)
                refresh()
                showAddPartyDialog = false
            },
        )
    }

    val partyNameForAdd = addAccountForParty
    if (partyNameForAdd != null) {
        AddAccountDialog(
            title = "Thêm tài khoản",
            onDismiss = { addAccountForParty = null },
            onSave = { account ->
                partyStore.addAccountToParty(partyNameForAdd, account)
                refresh()
                addAccountForParty = null
            },
        )
    }

    val partyBeingEdited = editingParty
    if (partyBeingEdited != null) {
        AddPartyDialog(
            title = "Sửa party",
            initialName = partyBeingEdited.name,
            initialServerKey = partyBeingEdited.serverKey,
            initialRunMode = partyBeingEdited.runMode,
            initialCityKey = partyBeingEdited.cityKey,
            initialDigioiSolo = partyBeingEdited.digioiSolo,
            initialNoLeader = partyBeingEdited.noLeader,
            initialLeaderWhitelist = partyBeingEdited.leaderWhitelist,
            initialDoDaily = partyBeingEdited.doDaily,
            initialTrainMapKey = partyBeingEdited.trainMapKey,
            initialTrainMobIndex = partyBeingEdited.trainMobIndex,
            initialUsePhucThan = partyBeingEdited.usePhucThan,
            initialUseDigioiHoPhu = partyBeingEdited.useDigioiHoPhu,
            initialFightLegionBoss = partyBeingEdited.fightLegionBoss,
            initialDoVanTieu = partyBeingEdited.doVanTieu,
            initialAutoSellNoiDat = partyBeingEdited.autoSellNoiDat,
            initialBuyHoPhu = partyBeingEdited.buyHoPhu,
            initialBuyBaoHop = partyBeingEdited.buyBaoHop,
            initialBaoHopXuThreshold = partyBeingEdited.baoHopXuThreshold,
            initialBuyHp = partyBeingEdited.buyHp,
            initialHpQty = partyBeingEdited.hpQty,
            initialHpThresh = partyBeingEdited.hpThresh,
            initialBuySp = partyBeingEdited.buySp,
            initialSpQty = partyBeingEdited.spQty,
            initialSpThresh = partyBeingEdited.spThresh,
            initialDiGioiLevel = partyBeingEdited.diGioiLevel,
            onApplyDiGioiLevel = { idx ->
                service?.setDiGioiLevel(partyBeingEdited.accounts.map { it.username }, idx)
            },
            onDismiss = { editingParty = null },
            onSave = { edited ->
                // Giu nguyen danh sach account, chi doi ten/server.
                partyStore.updateParty(partyBeingEdited.name, edited.copy(accounts = partyBeingEdited.accounts))
                refresh()
                editingParty = null
            },
            onApplyAdvancedToAll = { source ->
                val count = partyStore.applyAdvancedSettingsToOtherParties(partyBeingEdited.name, source)
                refresh()
                count
            },
        )
    }

    val accountBeingEdited = editingAccount
    if (accountBeingEdited != null) {
        val (partyName, account) = accountBeingEdited
        AddAccountDialog(
            title = "Sửa tài khoản",
            initialUsername = account.username,
            initialPassword = account.password,
            initialBattleJson = account.battleJson,
            initialHeal = account.heal,
            charSkills = service?.accountSkills(account.username)?.first ?: emptyList(),
            petSkills = service?.accountSkills(account.username)?.second ?: emptyList(),
            onDismiss = { editingAccount = null },
            onSave = { edited ->
                partyStore.updateAccountInParty(partyName, account.username, edited)
                service?.applyAccountBattle(edited.username, edited.battleJson)
                service?.applyAccountHeal(edited.username, edited.heal.toRuntimeJson())
                refresh()
                editingAccount = null
            },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PartyCard(
    party: Party,
    statusMap: Map<String, AccountStatus>,
    onAddAccount: () -> Unit,
    onEditParty: () -> Unit,
    onEditAccount: (Account) -> Unit,
    onRemoveAccount: (String) -> Unit,
    onRemoveParty: () -> Unit,
    onStart: (Account) -> Unit,
    onStop: (String) -> Unit,
    onStartParty: () -> Unit,
    onStopParty: () -> Unit,
    onSendChannel: (Int) -> Unit,
    onSendChannelAuto: () -> Unit,
    onSendCity: (Int, Int) -> Unit,
    onSendRouteMaps: (Int, Int) -> Unit,
    onSendGiftcode: (String) -> Unit,
    onGetChannels: () -> List<Triple<Int, Int, Int>>,
    onCurrentChannel: () -> Int?,
    onGetLog: (String) -> String = { "" },
) {
    val runningInParty = party.accounts.count { statusMap[it.username]?.state == RunState.RUNNING }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(16.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(party.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(2.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Pill(Servers.ALL[party.serverKey]?.label ?: party.serverKey)
                        Spacer(Modifier.width(6.dp))
                        Pill(RunModes.ALL[party.runMode] ?: party.runMode)
                    }
                }
                // Icon quan ly party (them acc / sua / xoa) o goc phai header - KHONG chung hang
                // voi nut Chay/Dung (truoc day chung hang -> nut bi bop hep, chu xuong dong 1 ky tu).
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onAddAccount, enabled = party.accounts.size < 5) {
                        Icon(Icons.Default.Add, contentDescription = "Thêm tài khoản")
                    }
                    IconButton(onClick = onEditParty) {
                        Icon(Icons.Default.Edit, contentDescription = "Sửa party", modifier = Modifier.size(20.dp))
                    }
                    IconButton(onClick = onRemoveParty) {
                        Icon(Icons.Default.Delete, contentDescription = "Xóa party",
                            tint = StatusError, modifier = Modifier.size(20.dp))
                    }
                }
            }

            if (party.accounts.isNotEmpty()) {
                Spacer(Modifier.height(4.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    StatusDot(if (runningInParty > 0) StatusRunning else StatusStopped)
                    Spacer(Modifier.width(6.dp))
                    Text(
                        "$runningInParty/${party.accounts.size} đang chạy",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Spacer(Modifier.height(10.dp))
            // Hang nut CHAY / DUNG ca party: 2 nut chia deu, KHONG chung hang voi icon -> du rong.
            Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                FilledTonalButton(
                    onClick = onStartParty,
                    enabled = party.accounts.isNotEmpty(),
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Default.PlayArrow, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Chạy party", maxLines = 1)
                }
                Spacer(Modifier.width(8.dp))
                OutlinedButton(
                    onClick = onStopParty,
                    enabled = party.accounts.isNotEmpty(),
                    modifier = Modifier.weight(1f),
                ) {
                    StopIcon(); Spacer(Modifier.width(4.dp)); Text("Dừng party", maxLines = 1)
                }
            }

            // ==== DIEU KHIEN LIVE (giong PC): kenh hien tai + doi kenh (list+so nguoi) + doi thanh ====
            var curChannel by remember { mutableStateOf<Int?>(null) }
            var showChannelDialog by remember { mutableStateOf(false) }
            var showCityDialog by remember { mutableStateOf(false) }
            var showGiftcodeDialog by remember { mutableStateOf(false) }
            // poll kenh hien tai moi 5s (chi khi party co acc)
            LaunchedEffect(party.accounts.firstOrNull()?.username) {
                while (party.accounts.isNotEmpty()) {
                    curChannel = withContext(Dispatchers.IO) { onCurrentChannel() }
                    delay(5000)
                }
            }
            if (party.accounts.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "Kênh: ${curChannel?.toString() ?: "—"}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.weight(1f))
                    OutlinedButton(onClick = { showChannelDialog = true }) { Text("Đổi kênh") }
                    Spacer(Modifier.width(6.dp))
                    OutlinedButton(onClick = { showCityDialog = true }) { Text("Đổi thành") }
                    Spacer(Modifier.width(6.dp))
                    OutlinedButton(onClick = { showGiftcodeDialog = true }) { Text("Giftcode") }
                }
            }
            if (showChannelDialog) {
                ChannelDialog(
                    onDismiss = { showChannelDialog = false },
                    onGetChannels = onGetChannels,
                    onPick = { ch -> onSendChannel(ch); curChannel = ch; showChannelDialog = false },
                    onAuto = { onSendChannelAuto(); showChannelDialog = false },
                )
            }
            if (showCityDialog) {
                CityDialog(
                    onDismiss = { showCityDialog = false },
                    allowRouteMaps = party.runMode == RunModes.STAND_STILL || party.runMode == RunModes.STAY_LOGIN,
                    onPick = { info -> onSendCity(info.cityId, info.flag); showCityDialog = false },
                    onRouteMaps = { source, dest -> onSendRouteMaps(source, dest); showCityDialog = false },
                )
            }
            if (showGiftcodeDialog) {
                GiftcodeDialog(
                    onDismiss = { showGiftcodeDialog = false },
                    onSave = { code -> onSendGiftcode(code); showGiftcodeDialog = false },
                )
            }

            if (party.accounts.isEmpty()) {
                Text("Chưa có tài khoản - bấm + để thêm")
            } else {
                var expandedLogUser by remember { mutableStateOf<String?>(null) }
                party.accounts.forEach { account ->
                    Spacer(Modifier.height(6.dp))
                    AccountRow(
                        account = account,
                        status = statusMap[account.username] ?: AccountStatus(),
                        onStart = { onStart(account) },
                        onStop = { onStop(account.username) },
                        onEdit = { onEditAccount(account) },
                        onDelete = { onRemoveAccount(account.username) },
                        expanded = expandedLogUser == account.username,
                        onToggleLog = {
                            expandedLogUser = if (expandedLogUser == account.username) null else account.username
                        },
                        onGetLog = { onGetLog(account.username) },
                    )
                }
            }
        }
    }
}

@Composable
fun AccountRow(
    account: Account,
    status: AccountStatus,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
    expanded: Boolean = false,
    onToggleLog: () -> Unit = {},
    onGetLog: () -> String = { "" },
) {
    val running = status.state == RunState.RUNNING
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth().clickable(onClick = onToggleLog),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                StatusDot(statusColor(status.state))
                Spacer(Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(account.username, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold)
                    val characterParts = buildList {
                        if (status.charName.isNotBlank()) add(status.charName)
                        status.charLevel?.let { add(it.toString()) }
                        if (status.petName.isNotBlank()) {
                            add(status.petName)
                            status.petLevel?.let { add(it.toString()) }
                        }
                    }
                    if (characterParts.isNotEmpty()) {
                        val average = status.partyAvgLevel?.let { " ($it)" } ?: ""
                        Text(
                            characterParts.joinToString("_") + average,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Text(
                        statusLabel(status.state),
                        style = MaterialTheme.typography.labelMedium,
                        color = statusColor(status.state),
                    )
                }
                // Start / Stop gon: dang chay -> hien nut Dung (do), nguoc lai -> nut Chay (xanh)
                if (running) {
                    OutlinedButton(onClick = onStop) { StopIcon(); Spacer(Modifier.width(4.dp)); Text("Dừng") }
                } else {
                    FilledTonalButton(onClick = onStart) {
                        Icon(Icons.Default.PlayArrow, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(4.dp)); Text("Chạy")
                    }
                }
                IconButton(onClick = onEdit) {
                    Icon(Icons.Default.Edit, contentDescription = "Sửa", modifier = Modifier.size(18.dp))
                }
                IconButton(onClick = onDelete) {
                    Icon(Icons.Default.Delete, contentDescription = "Xóa", tint = StatusError, modifier = Modifier.size(18.dp))
                }
            }

            // Thanh HP/SP truc quan (chi hien khi da co so lieu)
            if (status.hp != null && status.hpMax != null && status.hpMax > 0) {
                Spacer(Modifier.height(8.dp))
                StatBar("HP", status.hp, status.hpMax, HpColor)
            }
            if (status.sp != null && status.spMax != null && status.spMax > 0) {
                Spacer(Modifier.height(4.dp))
                StatBar("SP", status.sp, status.spMax, SpColor)
            }
            if (status.message.isNotBlank()) {
                Spacer(Modifier.height(6.dp))
                Text(
                    status.message,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            // Log rieng cua acc nay - bam vao dong tren (Row) de xo/thu gon. Chi doc log() khi
            // dang mo (remember(expanded) -> khong doc lien tuc moi lan recompose khi dong).
            if (expanded) {
                val clipboard = LocalClipboardManager.current
                val logText = remember(expanded) { onGetLog() }
                val logScroll = rememberScrollState()
                // Tu cuon xuong dong MOI NHAT ngay khi mo - KHONG bat nguoi dung tu keo xuong.
                LaunchedEffect(logText) { logScroll.scrollTo(logScroll.maxValue) }
                Spacer(Modifier.height(8.dp))
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(8.dp))
                        .padding(8.dp),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("Log của ${account.username}", style = MaterialTheme.typography.labelLarge)
                        TextButton(onClick = { clipboard.setText(AnnotatedString(logText)) }) {
                            Text("📋 Copy")
                        }
                    }
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(240.dp)
                            .verticalScroll(logScroll),
                    ) {
                        Text(
                            logText,
                            style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                        )
                    }
                }
            }
        }
    }
}

/** Cham tron mau trang thai. */
@Composable
fun StatusDot(color: Color, size: Int = 10) {
    Box(modifier = Modifier.size(size.dp).clip(CircleShape).background(color))
}

/** Nhan nho (server / mode) kieu "pill". */
@Composable
fun Pill(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier
            .clip(RoundedCornerShape(6.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(horizontal = 8.dp, vertical = 3.dp),
    )
}

/** Icon "dung" (Icons core khong co Stop -> ve o vuong bo tron). */
@Composable
fun StopIcon() {
    Box(modifier = Modifier.size(12.dp).clip(RoundedCornerShape(2.dp)).background(StatusError))
}

/** Thanh HP/SP: nhan + so + progress bar mau. */
@Composable
fun StatBar(label: String, cur: Int, max: Int, color: Color) {
    val frac = (cur.toFloat() / max.toFloat()).coerceIn(0f, 1f)
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.width(24.dp))
        LinearProgressIndicator(
            progress = { frac },
            color = color,
            trackColor = MaterialTheme.colorScheme.surface,
            modifier = Modifier.weight(1f).height(8.dp).clip(RoundedCornerShape(4.dp)),
        )
        Spacer(Modifier.width(8.dp))
        Text("$cur/$max", style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.width(72.dp))
    }
}

/** Doc TRAIN_MAPS tu Python de hien dropdown "Map train" - tra (key, ten map) GIU NGUYEN thu tu
 * trong train_maps.json (= thu tu ban PC) - KHONG sap xep lai theo alphabet. asMap() (khac
 * callAttr("keys").asList() - Chaquopy KHONG convert duoc dict_keys view sang PyList, nem
 * UnsupportedOperationException "dict_keys object has no attribute __getitem__", da xac nhan qua
 * crash log that) giu dung thu tu Python dict (json.loads tu Python 3.7+ giu insertion order). */
// Cap quai Di Gioi: idx 1..15 (goi 0x61 02 00 idx) -> cap hien thi. Xem KNOWLEDGE.md.
val DG_LEVELS = listOf(10, 25, 40, 55, 70, 85, 100, 110, 120, 130, 140, 150, 160, 170, 180)

// (key, ten hien thi, nhom). Nhom = field 'group' trong train_maps.json (mac dinh 'Chua phan nhom').
fun trainMapOptions(): List<Triple<String, String, String>> {
    val config = com.chaquo.python.Python.getInstance().getModule("train_bot.config")
    val maps = config.get("TRAIN_MAPS")!!
    return maps.asMap().entries.map { (k, v) ->
        val name = v.callAttr("get", "name")?.toString()
        val group = v.callAttr("get", "group")?.toString()?.ifBlank { "Chưa phân nhóm" } ?: "Chưa phân nhóm"
        Triple(k.toString(), if (name.isNullOrBlank()) k.toString() else name, group)
    }
}

/** Thu tu nhom hien thi: nhom co ten (theo xuat hien) TRUOC, 'Chua phan nhom' xuong CUOI. */
fun trainMapGroupOrder(opts: List<Triple<String, String, String>>): List<String> {
    val order = LinkedHashSet<String>()
    opts.forEach { if (it.third != "Chưa phân nhóm") order.add(it.third) }
    if (opts.any { it.third == "Chưa phân nhóm" }) order.add("Chưa phân nhóm")
    return order.toList()
}

/** Doc danh sach diem quai cua 1 map train tu Python de hien dropdown "Quái". Luon co "Bot tu chon"
 * (-1) o dau danh sach. */
fun trainMobOptions(mapKey: String): List<Pair<Int, String>> {
    val mapId = mapKey.toIntOrNull() ?: return listOf(-1 to "Bot tự chọn")
    val config = com.chaquo.python.Python.getInstance().getModule("train_bot.config")
    val maps = config.get("TRAIN_MAPS")!!
    val info = maps.callAttr("get", mapId) ?: return listOf(-1 to "Bot tự chọn")
    val mobs = info.callAttr("get", "mobs") ?: return listOf(-1 to "Bot tự chọn")
    val list = mutableListOf(-1 to "Bot tự chọn")
    mobs.asList().forEachIndexed { i, pt ->
        val coords = pt.asList()
        list.add(i to "Điểm ${i + 1} (${coords[0]}, ${coords[1]})")
    }
    return list
}

private fun parseLeaderWhitelist(text: String): List<String> =
    text.split('\n', '\r', ',')
        .map { it.trim() }
        .filter { it.isNotEmpty() }
        .distinctBy { it.lowercase() }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddPartyDialog(
    onDismiss: () -> Unit,
    onSave: (Party) -> Unit,
    title: String = "Tạo party",
    initialName: String = "",
    initialServerKey: String = Servers.ALL.keys.first(),
    initialRunMode: String = RunModes.STAND_STILL,
    initialCityKey: String = Cities.ALL.keys.first(),
    initialDigioiSolo: Boolean = false,
    initialNoLeader: Boolean = false,
    initialLeaderWhitelist: List<String> = emptyList(),
    initialDoDaily: Boolean = true,
    initialTrainMapKey: String = "",
    initialTrainMobIndex: Int = -1,
    initialUsePhucThan: Boolean = false,
    initialUseDigioiHoPhu: Boolean = false,
    initialFightLegionBoss: Boolean = true,
    initialDoVanTieu: Boolean = true,
    initialAutoSellNoiDat: Boolean = true,
    initialBuyHoPhu: Boolean = false,
    initialBuyBaoHop: Boolean = false,
    initialBaoHopXuThreshold: Int = 1000000,
    initialBuyHp: Boolean = false,
    initialHpQty: Int = 9999,
    initialHpThresh: Int = 500000,
    initialBuySp: Boolean = false,
    initialSpQty: Int = 9999,
    initialSpThresh: Int = 500000,
    initialDiGioiLevel: Int = 2,
    onApplyAdvancedToAll: ((Party) -> Int)? = null,
    onApplyDiGioiLevel: ((Int) -> Unit)? = null,
) {
    var name by remember { mutableStateOf(initialName) }
    var expanded by remember { mutableStateOf(false) }
    var selectedKey by remember { mutableStateOf(initialServerKey) }
    var modeExpanded by remember { mutableStateOf(false) }
    var selectedMode by remember { mutableStateOf(initialRunMode) }
    var cityExpanded by remember { mutableStateOf(false) }
    var selectedCity by remember { mutableStateOf(initialCityKey) }
    var digioiSolo by remember { mutableStateOf(initialDigioiSolo) }
    var noLeader by remember { mutableStateOf(initialNoLeader) }
    var leaderWhitelistText by remember { mutableStateOf(initialLeaderWhitelist.joinToString("\n")) }
    var doDaily by remember { mutableStateOf(initialDoDaily) }
    var trainMapKey by remember { mutableStateOf(initialTrainMapKey.ifEmpty { trainMapOptions().firstOrNull()?.first ?: "" }) }
    var trainMobExpanded by remember { mutableStateOf(false) }
    var trainMobIndex by remember { mutableStateOf(initialTrainMobIndex) }
    var trainMapExpanded by remember { mutableStateOf(false) }
    var usePhucThan by remember { mutableStateOf(initialUsePhucThan) }
    var useDigioiHoPhu by remember { mutableStateOf(initialUseDigioiHoPhu) }
    var fightLegionBoss by remember { mutableStateOf(initialFightLegionBoss) }
    var doVanTieu by remember { mutableStateOf(initialDoVanTieu) }
    var autoSellNoiDat by remember { mutableStateOf(initialAutoSellNoiDat) }
    var buyHoPhu by remember { mutableStateOf(initialBuyHoPhu) }
    var buyBaoHop by remember { mutableStateOf(initialBuyBaoHop) }
    var baoHopXuText by remember { mutableStateOf(initialBaoHopXuThreshold.toString()) }
    var buyHp by remember { mutableStateOf(initialBuyHp) }
    var hpQtyText by remember { mutableStateOf(initialHpQty.toString()) }
    var hpThreshText by remember { mutableStateOf(initialHpThresh.toString()) }
    var buySp by remember { mutableStateOf(initialBuySp) }
    var spQtyText by remember { mutableStateOf(initialSpQty.toString()) }
    var spThreshText by remember { mutableStateOf(initialSpThresh.toString()) }
    // Cap quai Di Gioi: idx 1..15 (1-based). UI hien theo cap 10..180.
    var diGioiLevel by remember { mutableStateOf(initialDiGioiLevel.coerceIn(1, DG_LEVELS.size)) }
    var diGioiExpandedMode by remember { mutableStateOf(false) }
    var showAdvanced by remember { mutableStateOf(false) }
    var advancedApplyMessage by remember { mutableStateOf("") }

    fun currentParty(): Party = Party(
        name = name.ifBlank { initialName.ifBlank { "Party" } },
        serverKey = selectedKey,
        runMode = selectedMode,
        cityKey = selectedCity,
        digioiSolo = digioiSolo,
        noLeader = noLeader,
        leaderWhitelist = parseLeaderWhitelist(leaderWhitelistText),
        doDaily = doDaily,
        trainMapKey = trainMapKey,
        trainMobIndex = trainMobIndex,
        usePhucThan = usePhucThan,
        useDigioiHoPhu = useDigioiHoPhu,
        fightLegionBoss = fightLegionBoss,
        doVanTieu = doVanTieu,
        autoSellNoiDat = autoSellNoiDat,
        buyHoPhu = buyHoPhu,
        buyBaoHop = buyBaoHop,
        baoHopXuThreshold = baoHopXuText.toIntOrNull() ?: 1000000,
        buyHp = buyHp,
        hpQty = hpQtyText.toIntOrNull() ?: 9999,
        hpThresh = hpThreshText.toIntOrNull() ?: 500000,
        buySp = buySp,
        spQty = spQtyText.toIntOrNull() ?: 9999,
        spThresh = spThreshText.toIntOrNull() ?: 500000,
        diGioiLevel = diGioiLevel,
    )

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            // Cuon duoc theo chieu doc - dialog nay co RAT NHIEU field (ten/server/mode/checkbox
            // Di Gioi+Train/dropdown Map+Quai/thanh...), khong scroll se tran ra ngoai vung hien
            // thi tren man hinh nho, khien cac field cuoi (vd dropdown "Quai") bi che/lech vi tri
            // popup - da xac nhan qua test thuc te tren emulator (chon Quai "khong thay hien thi
            // gi ca" vi popup tinh vi tri theo anchor da bi day ra ngoai).
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Tên party") },
                    singleLine = true,
                )
                Spacer(Modifier.height(8.dp))
                ExposedDropdownMenuBox(
                    expanded = expanded,
                    onExpandedChange = { expanded = it },
                ) {
                    OutlinedTextField(
                        value = Servers.ALL[selectedKey]?.label ?: selectedKey,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("Server") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                        // menuAnchor() BAT BUOC de ExposedDropdownMenuBox nhan dien tap vao
                        // TextField la yeu cau mo dropdown - thieu no thi bam vao khong phan ung.
                        modifier = Modifier.fillMaxWidth().menuAnchor(),
                    )
                    DropdownMenu(
                        expanded = expanded,
                        onDismissRequest = { expanded = false },
                    ) {
                        Servers.ALL.forEach { (key, info) ->
                            DropdownMenuItem(
                                text = { Text(info.label) },
                                onClick = {
                                    selectedKey = key
                                    expanded = false
                                },
                            )
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                ExposedDropdownMenuBox(
                    expanded = modeExpanded,
                    onExpandedChange = { modeExpanded = it },
                ) {
                    OutlinedTextField(
                        value = RunModes.ALL[selectedMode] ?: selectedMode,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("Chế độ chạy") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = modeExpanded) },
                        modifier = Modifier.fillMaxWidth().menuAnchor(),
                    )
                    DropdownMenu(
                        expanded = modeExpanded,
                        onDismissRequest = { modeExpanded = false },
                    ) {
                        RunModes.ALL.forEach { (key, label) ->
                            DropdownMenuItem(
                                text = { Text(label) },
                                onClick = {
                                    selectedMode = key
                                    modeExpanded = false
                                },
                            )
                        }
                    }
                }
                // Che do "SOLO (khong lap party)" CHI ap dung khi mode = Di Gioi - mirror
                // pcfg["digioi_mode"]=="solo" ben PC (1 sub-option BEN TRONG mode digioi).
                if (selectedMode == RunModes.DIGIOI || selectedMode == RunModes.DIGIOI_TRAIN) {
                    Spacer(Modifier.height(8.dp))
                    if (selectedMode == RunModes.DIGIOI) {   // DG+Train luon chay PARTY (cho ca party xong DG)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = digioiSolo, onCheckedChange = { digioiSolo = it })
                            Text("Chạy SOLO (mỗi account độc lập, không lập party thật)")
                        }
                    }
                    // Cap quai Di Gioi: chon ngay trong phan config mode (mirror PC's _render_dyn).
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Cấp quái:")
                        Box(modifier = Modifier.padding(start = 6.dp)) {
                            OutlinedButton(onClick = { diGioiExpandedMode = true }) {
                                Text(DG_LEVELS[diGioiLevel - 1].toString())
                            }
                            DropdownMenu(expanded = diGioiExpandedMode, onDismissRequest = { diGioiExpandedMode = false }) {
                                DG_LEVELS.forEachIndexed { i, lv ->
                                    DropdownMenuItem(text = { Text(lv.toString()) },
                                        onClick = { diGioiLevel = i + 1; diGioiExpandedMode = false })
                                }
                            }
                        }
                        if (onApplyDiGioiLevel != null) {
                            TextButton(onClick = { onApplyDiGioiLevel(diGioiLevel) },
                                modifier = Modifier.padding(start = 8.dp)) { Text("Áp dụng ngay") }
                        }
                    }
                }
                // Bot dung yen cho leader ngoai/tay moi: an khi Di Gioi + SOLO (khong lap party).
                // Chi khi bat moi hien o nhap whitelist leader.
                Spacer(Modifier.height(8.dp))
                if (!(selectedMode == RunModes.DIGIOI && digioiSolo)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = noLeader, onCheckedChange = { noLeader = it })
                        Text("Bot đứng yên, chờ nhận lời mời từ")
                    }
                    if (noLeader) {
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(
                            value = leaderWhitelistText,
                            onValueChange = { leaderWhitelistText = it },
                            label = { Text("Tên leader") },
                            supportingText = { Text("Mỗi dòng hoặc dấu phẩy = 1 tên nhân vật leader. Để trống = nhận lời mời từ mọi người.") },
                            minLines = 2,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
                // Cac setting IT KHI DOI gom vao "Cai dat nang cao" (mirror gui.py ben PC) - tranh
                // dialog nay (da rat nhieu field) bi day dai them moi lan them setting moi.
                TextButton(onClick = { showAdvanced = !showAdvanced }) {
                    Text(if (showAdvanced) "▲ Ẩn cài đặt nâng cao" else "⚙ Cài đặt nâng cao")
                }
                if (showAdvanced) {
                    Column(modifier = Modifier.background(MaterialTheme.colorScheme.surfaceVariant)
                        .padding(8.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = doDaily, onCheckedChange = { doDaily = it })
                            Text("Làm nhiệm vụ hàng ngày")
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = usePhucThan, onCheckedChange = { usePhucThan = it })
                            Text("Sử dụng Phúc Thần")
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = useDigioiHoPhu, onCheckedChange = { useDigioiHoPhu = it })
                            Text("Dùng Dị giới hộ phù")
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = fightLegionBoss, onCheckedChange = { fightLegionBoss = it })
                            Text("Đánh boss QD")
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = doVanTieu, onCheckedChange = { doVanTieu = it })
                            Text("Vận tiêu (nhận quà + gửi pet)")
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = autoSellNoiDat, onCheckedChange = { autoSellNoiDat = it })
                            Text("Tự bán Nồi đất")
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = buyHoPhu, onCheckedChange = { buyHoPhu = it })
                            Text("Mua Dị Giới Hộ Phù (3 cái/ngày)")
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = buyBaoHop, onCheckedChange = { buyBaoHop = it })
                            Text("Mua Triệu Gọi Bảo Hộp khi xu >")
                            OutlinedTextField(
                                value = baoHopXuText,
                                onValueChange = { baoHopXuText = it.filter { c -> c.isDigit() } },
                                singleLine = true,
                                modifier = Modifier.width(120.dp).padding(start = 6.dp),
                                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = KeyboardType.Number),
                            )
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = buyHp, onCheckedChange = { buyHp = it })
                            Text("Tự mua HP x")
                            OutlinedTextField(
                                value = hpQtyText,
                                onValueChange = { hpQtyText = it.filter { c -> c.isDigit() } },
                                singleLine = true,
                                modifier = Modifier.width(84.dp).padding(start = 6.dp),
                                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = KeyboardType.Number),
                            )
                            Text("  khi tổng HP có thể hồi từ item trong túi <", modifier = Modifier.padding(start = 6.dp))
                            OutlinedTextField(
                                value = hpThreshText,
                                onValueChange = { hpThreshText = it.filter { c -> c.isDigit() } },
                                singleLine = true,
                                modifier = Modifier.width(104.dp).padding(start = 6.dp),
                                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = KeyboardType.Number),
                            )
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = buySp, onCheckedChange = { buySp = it })
                            Text("Tự mua SP x")
                            OutlinedTextField(
                                value = spQtyText,
                                onValueChange = { spQtyText = it.filter { c -> c.isDigit() } },
                                singleLine = true,
                                modifier = Modifier.width(84.dp).padding(start = 6.dp),
                                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = KeyboardType.Number),
                            )
                            Text("  khi tổng SP có thể hồi từ item trong túi <", modifier = Modifier.padding(start = 6.dp))
                            OutlinedTextField(
                                value = spThreshText,
                                onValueChange = { spThreshText = it.filter { c -> c.isDigit() } },
                                singleLine = true,
                                modifier = Modifier.width(104.dp).padding(start = 6.dp),
                                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = KeyboardType.Number),
                            )
                        }
                        // (Cap quai Di Gioi da chuyen ra section mode Di Gioi ngoai - khong lap lai o day)
                        if (onApplyAdvancedToAll != null) {
                            Spacer(Modifier.height(8.dp))
                            OutlinedButton(
                                onClick = {
                                    val count = onApplyAdvancedToAll(currentParty())
                                    advancedApplyMessage = if (count > 0) {
                                        "Đã áp dụng cho $count party khác"
                                    } else {
                                        "Không có party khác"
                                    }
                                },
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text("Áp dụng cho tất cả")
                            }
                            if (advancedApplyMessage.isNotBlank()) {
                                Spacer(Modifier.height(4.dp))
                                Text(
                                    advancedApplyMessage,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
                // DG+Train cung can chon MAP TRAIN (pha 2 sau khi ca party xong Di Gioi).
                if (selectedMode == RunModes.TRAIN || selectedMode == RunModes.DIGIOI_TRAIN) {
                    Spacer(Modifier.height(8.dp))
                    val mapOptions = trainMapOptions()
                    ExposedDropdownMenuBox(expanded = trainMapExpanded, onExpandedChange = { trainMapExpanded = it }) {
                        OutlinedTextField(
                            value = mapOptions.find { it.first == trainMapKey }?.second ?: trainMapKey,
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("Map train") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = trainMapExpanded) },
                            modifier = Modifier.fillMaxWidth().menuAnchor(),
                        )
                        DropdownMenu(expanded = trainMapExpanded, onDismissRequest = { trainMapExpanded = false }) {
                            val groups = trainMapGroupOrder(mapOptions)
                            // Chua gom nhom (chi co 'Chua phan nhom') -> hien PHANG nhu cu, khong header thua.
                            val flat = groups.size <= 1 && groups.firstOrNull() == "Chưa phân nhóm"
                            if (flat) {
                                mapOptions.forEach { (key, mapName, _) ->
                                    DropdownMenuItem(text = { Text(mapName) }, onClick = {
                                        trainMapKey = key; trainMobIndex = -1; trainMapExpanded = false
                                    })
                                }
                            } else {
                                groups.forEach { g ->
                                    DropdownMenuItem(enabled = false, onClick = {},
                                        text = { Text("📁 $g") })
                                    mapOptions.filter { it.third == g }.forEach { (key, mapName, _) ->
                                        DropdownMenuItem(text = { Text("    $mapName") }, onClick = {
                                            trainMapKey = key; trainMobIndex = -1; trainMapExpanded = false
                                        })
                                    }
                                }
                            }
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    val mobOptions = trainMobOptions(trainMapKey)
                    ExposedDropdownMenuBox(expanded = trainMobExpanded, onExpandedChange = { trainMobExpanded = it }) {
                        OutlinedTextField(
                            value = mobOptions.find { it.first == trainMobIndex }?.second ?: "Bot tự chọn",
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("Quái") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = trainMobExpanded) },
                            modifier = Modifier.fillMaxWidth().menuAnchor(),
                        )
                        DropdownMenu(expanded = trainMobExpanded, onDismissRequest = { trainMobExpanded = false }) {
                            mobOptions.forEach { (idx, label) ->
                                DropdownMenuItem(text = { Text(label) }, onClick = {
                                    trainMobIndex = idx; trainMobExpanded = false
                                })
                            }
                        }
                    }
                }
                // Chon thanh CHI can khi mode = ve thanh dung yen. Mode "login o dau dung yen do"
                // (STAY_LOGIN) va "Di Gioi" (DIGIOI) khong teleport ve thanh nen an o chon thanh.
                if (selectedMode == RunModes.STAND_STILL) {
                    Spacer(Modifier.height(8.dp))
                    ExposedDropdownMenuBox(
                        expanded = cityExpanded,
                        onExpandedChange = { cityExpanded = it },
                    ) {
                        OutlinedTextField(
                            value = Cities.ALL[selectedCity]?.label ?: selectedCity,
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("Thành") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = cityExpanded) },
                            modifier = Modifier.fillMaxWidth().menuAnchor(),
                        )
                        DropdownMenu(
                            expanded = cityExpanded,
                            onDismissRequest = { cityExpanded = false },
                        ) {
                            Cities.ALL.forEach { (key, info) ->
                                DropdownMenuItem(
                                    text = { Text(info.label) },
                                    onClick = {
                                        selectedCity = key
                                        cityExpanded = false
                                    },
                                )
                            }
                        }
                    }
                }
                // Mode EVENT: chon event de tele toi (dung chung field cityKey lam event key -
                // run_train nhan runMode==event thi coi cityKey la event_key). Mac dinh event dau tien.
                if (selectedMode == RunModes.EVENT) {
                    Spacer(Modifier.height(8.dp))
                    ExposedDropdownMenuBox(
                        expanded = cityExpanded,
                        onExpandedChange = { cityExpanded = it },
                    ) {
                        OutlinedTextField(
                            value = Events.ALL[selectedCity]?.label ?: (Events.ALL.values.firstOrNull()?.label ?: ""),
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("Event") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = cityExpanded) },
                            modifier = Modifier.fillMaxWidth().menuAnchor(),
                        )
                        DropdownMenu(
                            expanded = cityExpanded,
                            onDismissRequest = { cityExpanded = false },
                        ) {
                            Events.ALL.forEach { (key, info) ->
                                DropdownMenuItem(
                                    text = { Text(info.label) },
                                    onClick = {
                                        selectedCity = key
                                        cityExpanded = false
                                    },
                                )
                            }
                        }
                    }
                }
                // De trong cuoi Column: cac dropdown gan cuoi (vd "Quai" khi mode Train) can CHO
                // BEN DUOI de DropdownMenu popup bung ra - dialog nay co RAT NHIEU field nen field
                // cuoi cung nam sat day vung hien thi, khong co cho -> popup bi coi la khong co
                // dien tich hien thi (xac nhan qua test thuc te: bam vao khong thay gi ca). Them
                // khoang trong lon o day de AlertDialog danh du cho ben duoi field cuoi cung.
                Spacer(Modifier.height(300.dp))
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (name.isNotBlank()) {
                        onSave(Party(
                            name = name,
                            serverKey = selectedKey,
                            runMode = selectedMode,
                            cityKey = selectedCity,
                            digioiSolo = digioiSolo,
                            noLeader = noLeader,
                            leaderWhitelist = parseLeaderWhitelist(leaderWhitelistText),
                            doDaily = doDaily,
                            trainMapKey = trainMapKey,
                            trainMobIndex = trainMobIndex,
                            usePhucThan = usePhucThan,
                            useDigioiHoPhu = useDigioiHoPhu,
                            fightLegionBoss = fightLegionBoss,
                            doVanTieu = doVanTieu,
                            autoSellNoiDat = autoSellNoiDat,
                            buyHoPhu = buyHoPhu,
                            buyBaoHop = buyBaoHop,
                            baoHopXuThreshold = baoHopXuText.toIntOrNull() ?: 1000000,
                            buyHp = buyHp,
                            hpQty = hpQtyText.toIntOrNull() ?: 9999,
                            hpThresh = hpThreshText.toIntOrNull() ?: 500000,
                            buySp = buySp,
                            spQty = spQtyText.toIntOrNull() ?: 9999,
                            spThresh = spThreshText.toIntOrNull() ?: 500000,
                            diGioiLevel = diGioiLevel,
                        ))
                    }
                },
            ) {
                Text("Lưu")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Hủy") }
        },
    )
}

private data class BattleRuleUi(
    val enabled: Boolean = true,
    val condition: String = "always",
    val op: String = "gte",
    val value: String = "",
    val skill: String = "auto",
    val target: String = "auto",
)

private val BattleConditionOptions = listOf(
    "always" to "Luôn luôn",
    "mob" to "Số quái",
    "block" to "Block quái",
    "sp" to "SP",
    "hp_pct" to "HP (%)",
    "ally_hp_pct" to "Có đồng đội HP < %",
    "ally_sp_pct" to "Có đồng đội SP < %",
    "sp_full" to "SP đầy",
    "boss" to "Đang boss / phó bản",
    "quest" to "Quest đông quái",
    "mineral" to "Quái khoáng",
    "ally_dead" to "Đồng đội chết",
)

private val BattleCompareOptions = listOf(
    "gte" to ">=",
    "lte" to "<=",
    "gt" to ">",
    "lt" to "<",
    "eq" to "=",
)

private val BattleNumericConditions = setOf("mob", "block", "sp", "hp_pct", "ally_hp_pct", "ally_sp_pct")
private val BattleFixedLessConditions = setOf("ally_hp_pct", "ally_sp_pct")

private val BattleActionOptions = listOf(
    "auto" to "Auto",
    "normal" to "Đánh thường",
    "defend" to "Phòng thủ",
    "flee" to "Bỏ chạy",
)

private val BattleTargetOptions = listOf(
    "auto" to "Auto",
    "block" to "Theo block",
    "enemy_low_hp" to "Quái ít HP nhất",
    "enemy_high_hp" to "Quái nhiều HP nhất",
    "enemy_first" to "Quái đầu",
    "enemy_last" to "Quái cuối",
    "ally_low_hp" to "Đồng đội ít HP nhất",
    "ally_high_hp" to "Đồng đội nhiều HP nhất",
    "ally_low_sp" to "Đồng đội ít SP nhất",
    "self" to "Bản thân",
)

private fun defaultConditionValue(condition: String): String = when (condition) {
    "mob" -> "1"
    "block" -> "2"
    "ally_hp_pct" -> "70"
    "ally_sp_pct" -> "50"
    "sp", "hp_pct" -> "50"
    else -> ""
}

private fun normalizeBattleCondition(raw: String, op: String, value: String): Triple<String, String, String> {
    val parts = raw.split("_")
    if (parts.size == 3 && parts[1] in setOf("gte", "lte") && parts[2].toIntOrNull() != null) {
        val condition = if (parts[0] == "hp") "hp_pct" else parts[0]
        if (condition in BattleNumericConditions) return Triple(condition, parts[1], parts[2])
    }
    return Triple(raw, op, value)
}

private fun isReviveSkill(skill: SkillChoice): Boolean =
    skill.cat == 8 || skill.name.contains("Hồi Sinh", ignoreCase = true)

private fun isReviveSkillId(skill: String, skills: List<SkillChoice>): Boolean {
    val id = skill.toIntOrNull() ?: return false
    return skills.any { it.id == id && isReviveSkill(it) }
}

private fun conditionOptions(skills: List<SkillChoice>, selected: String): List<Pair<String, String>> {
    val hasRevive = skills.any { isReviveSkill(it) }
    return BattleConditionOptions.filter { (key, _) -> key != "ally_dead" || hasRevive || selected == "ally_dead" }
}

private fun parseBattleRules(json: String, unit: String): List<BattleRuleUi> {
    if (json.isBlank()) return listOf(BattleRuleUi())
    return try {
        val obj = JSONObject(json)
        val arr = obj.optJSONArray(unit)
        if (arr == null || arr.length() == 0) return listOf(BattleRuleUi())
        (0 until arr.length()).mapNotNull { i ->
            val r = arr.optJSONObject(i) ?: return@mapNotNull null
            val rawSkill = r.opt("skill")
            val (condition, op, value) = normalizeBattleCondition(
                r.optString("condition", "always"),
                r.optString("op", "gte"),
                r.optString("value", ""),
            )
            val target = r.optString("target", "auto").let { if (it == "ally_high_sp") "auto" else it }
            BattleRuleUi(
                enabled = r.optBoolean("enabled", true),
                condition = condition,
                op = op,
                value = value,
                skill = when (rawSkill) {
                    is Number -> rawSkill.toInt().toString()
                    is String -> rawSkill
                    else -> "auto"
                },
                target = target,
            )
        }.ifEmpty { listOf(BattleRuleUi()) }
    } catch (_: Exception) {
        listOf(BattleRuleUi())
    }
}

private fun battleJson(charRules: List<BattleRuleUi>, petRules: List<BattleRuleUi>): String {
    val def = BattleRuleUi()
    val charClean = charRules.ifEmpty { listOf(def) }
    val petClean = petRules.ifEmpty { listOf(def) }
    if (charClean == listOf(def) && petClean == listOf(def)) return ""
    fun ruleObj(r: BattleRuleUi) = JSONObject().apply {
        val cleanValue = if (r.condition in BattleNumericConditions) {
            r.value.ifBlank { defaultConditionValue(r.condition) }
        } else {
            ""
        }
        val cleanOp = if (r.condition in BattleFixedLessConditions) "lt" else r.op
        put("enabled", r.enabled)
        put("condition", r.condition)
        put("op", cleanOp)
        put("value", cleanValue)
        val asInt = r.skill.toIntOrNull()
        if (asInt != null) put("skill", asInt) else put("skill", r.skill)
        put("target", if (r.condition == "ally_dead") "auto" else r.target)
    }
    return JSONObject()
        .put("char", JSONArray().also { arr -> charClean.forEach { arr.put(ruleObj(it)) } })
        .put("pet", JSONArray().also { arr -> petClean.forEach { arr.put(ruleObj(it)) } })
        .toString()
}

private fun skillOptions(
    skills: List<SkillChoice>,
    selected: String,
    reviveOnly: Boolean = false,
): List<Pair<String, String>> {
    fun label(s: SkillChoice): String {
        val name = s.name.ifBlank { "Skill ${s.id}" }
        return if (s.cost != null) "$name (${s.id}, SP ${s.cost})" else "$name (${s.id})"
    }

    val out = if (reviveOnly) mutableListOf() else BattleActionOptions.toMutableList()
    val shownSkills = if (reviveOnly) skills.filter { isReviveSkill(it) } else skills
    out += shownSkills.distinctBy { it.id }.sortedBy { it.id }.map { it.id.toString() to label(it) }
    val saved = selected.toIntOrNull()
    if (saved != null && shownSkills.none { it.id == saved }) out += selected to "Skill $selected (đã lưu)"
    return out
}

private fun skillAvailableOrOffline(skills: List<SkillChoice>, skillId: Int): Boolean =
    skills.isEmpty() || skills.any { it.id == skillId }

private fun pickTemplateSkill(skills: List<SkillChoice>, candidates: List<Int>): String? =
    candidates.firstOrNull { skillAvailableOrOffline(skills, it) }?.toString()

private fun pickTemplateAttack(skills: List<SkillChoice>, preferHighCost: Boolean): String? {
    val attacks = skills.filter { it.cat == 1 || it.cat == 2 }
    if (attacks.isEmpty()) return null
    val picked = if (preferHighCost) {
        attacks.maxByOrNull { it.cost ?: 0 }
    } else {
        attacks.minByOrNull { it.cost ?: 9999 }
    }
    return picked?.id?.toString()
}

private fun defaultBattleRules(skills: List<SkillChoice>): List<BattleRuleUi> {
    val out = mutableListOf<BattleRuleUi>()
    val revive = skills.firstOrNull { isReviveSkill(it) }?.id?.toString()
        ?: if (skills.isEmpty()) "11013" else null
    if (revive != null) {
        out += BattleRuleUi(condition = "ally_dead", skill = revive, target = "auto")
    }
    val heal = pickTemplateSkill(skills, listOf(11010, 11004))
    if (heal != null) {
        out += BattleRuleUi(condition = "ally_hp_pct", op = "lt", value = "70", skill = heal, target = "ally_low_hp")
    }
    val spRestore = skills.filter { it.cat == 6 }.maxByOrNull { it.cost ?: 0 }?.id?.toString()
    if (spRestore != null) {
        out += BattleRuleUi(condition = "ally_sp_pct", op = "lt", value = "50", skill = spRestore, target = "ally_low_sp")
    }
    out += BattleRuleUi(condition = "mineral", skill = "flee", target = "self")
    val boss = pickTemplateSkill(skills, listOf(12009, 12006, 13013, 12003, 10005))
        ?: pickTemplateAttack(skills, preferHighCost = true)
    if (boss != null) {
        out += BattleRuleUi(condition = "boss", skill = boss, target = "enemy_low_hp")
    }
    val allTarget = pickTemplateSkill(skills, listOf(12014, 10012))
    if (allTarget != null) {
        out += BattleRuleUi(condition = "quest", skill = allTarget, target = "block")
    }
    val combo = pickTemplateSkill(skills, listOf(12003, 10005, 13013))
        ?: pickTemplateAttack(skills, preferHighCost = false)
    if (combo != null) {
        val needBlock = if (combo == "13013") "3" else "2"
        out += BattleRuleUi(condition = "sp_full", skill = combo, target = "block")
        out += BattleRuleUi(condition = "block", op = "gte", value = needBlock, skill = combo, target = "block")
    }
    out += BattleRuleUi(condition = "always", skill = "normal", target = "auto")
    return out
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RuleDropdown(
    label: String,
    value: String,
    options: List<Pair<String, String>>,
    onValue: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val shown = options.firstOrNull { it.first == value }?.second ?: value
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = shown,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier.fillMaxWidth().menuAnchor(),
        )
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { (key, text) ->
                DropdownMenuItem(text = { Text(text) }, onClick = {
                    onValue(key)
                    expanded = false
                })
            }
        }
    }
}

@Composable
private fun BattleRuleUnitEditor(
    title: String,
    rules: List<BattleRuleUi>,
    skills: List<SkillChoice>,
    onRules: (List<BattleRuleUi>) -> Unit,
) {
    Text(title, style = MaterialTheme.typography.labelLarge)
    rules.forEachIndexed { index, rule ->
        val reviveSkills = skills.filter { isReviveSkill(it) }
        fun updateRule(next: BattleRuleUi) {
            onRules(rules.toMutableList().also { list -> list[index] = next })
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(
                    checked = rule.enabled,
                    onCheckedChange = {
                        onRules(rules.toMutableList().also { list -> list[index] = list[index].copy(enabled = it) })
                    },
                )
                Text("Rule ${index + 1}", modifier = Modifier.weight(1f), style = MaterialTheme.typography.labelSmall)
                TextButton(
                    enabled = index > 0,
                    onClick = {
                        onRules(rules.toMutableList().also { list ->
                            val moved = list.removeAt(index)
                            list.add(index - 1, moved)
                        })
                    },
                ) {
                    Text("↑")
                }
                TextButton(
                    enabled = index < rules.lastIndex,
                    onClick = {
                        onRules(rules.toMutableList().also { list ->
                            val moved = list.removeAt(index)
                            list.add(index + 1, moved)
                        })
                    },
                ) {
                    Text("↓")
                }
                if (rules.size > 1) {
                    TextButton(onClick = { onRules(rules.filterIndexed { i, _ -> i != index }) }) {
                        Text("Xóa")
                    }
                }
            }
            RuleDropdown("Điều kiện", rule.condition, conditionOptions(skills, rule.condition)) { condition ->
                var next = rule.copy(condition = condition)
                next = if (condition in BattleNumericConditions) {
                    next.copy(
                        op = if (condition in BattleFixedLessConditions) "lt" else next.op,
                        value = next.value.ifBlank { defaultConditionValue(condition) },
                    )
                } else {
                    next.copy(value = "")
                }
                if (condition == "ally_dead") {
                    val reviveId = reviveSkills.firstOrNull()?.id?.toString()
                    next = next.copy(
                        skill = if (reviveId != null && !isReviveSkillId(next.skill, skills)) reviveId else next.skill,
                        target = "auto",
                    )
                }
                updateRule(next)
            }
            if (rule.condition in BattleNumericConditions) {
                if (rule.condition in BattleFixedLessConditions) {
                    OutlinedTextField(
                        value = "<",
                        onValueChange = {},
                        enabled = false,
                        label = { Text("Dấu") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                } else {
                    RuleDropdown("Dấu", rule.op, BattleCompareOptions) {
                        updateRule(rule.copy(op = it))
                    }
                }
                OutlinedTextField(
                    value = rule.value,
                    onValueChange = { text -> updateRule(rule.copy(value = text.filter { it.isDigit() })) },
                    label = { Text("Số") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            RuleDropdown("Skill", rule.skill, skillOptions(skills, rule.skill, reviveOnly = rule.condition == "ally_dead")) {
                updateRule(rule.copy(skill = it))
            }
            if (rule.condition != "ally_dead") {
                RuleDropdown("Target", rule.target, BattleTargetOptions) {
                    updateRule(rule.copy(target = it))
                }
            }
        }
    }
    TextButton(onClick = { onRules(rules + BattleRuleUi()) }) { Text("+ Thêm rule") }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddAccountDialog(
    onDismiss: () -> Unit,
    onSave: (Account) -> Unit,
    title: String = "Thêm tài khoản",
    initialUsername: String = "",
    initialPassword: String = "",
    initialBattleJson: String = "",
    initialHeal: HealSettings = HealSettings(),
    charSkills: List<SkillChoice> = emptyList(),
    petSkills: List<SkillChoice> = emptyList(),
) {
    var username by remember { mutableStateOf(initialUsername) }
    var password by remember { mutableStateOf(initialPassword) }
    var hpCharText by remember(initialHeal) { mutableStateOf(initialHeal.hpChar.toString()) }
    var spCharText by remember(initialHeal) { mutableStateOf(initialHeal.spChar.toString()) }
    var hpPetText by remember(initialHeal) { mutableStateOf(initialHeal.hpPet.toString()) }
    var spPetText by remember(initialHeal) { mutableStateOf(initialHeal.spPet.toString()) }
    var charRules by remember(initialBattleJson) { mutableStateOf(parseBattleRules(initialBattleJson, "char")) }
    var petRules by remember(initialBattleJson) { mutableStateOf(parseBattleRules(initialBattleJson, "pet")) }
    var confirmDefault by remember { mutableStateOf(false) }

    fun pct(text: String, fallback: Int): Int = (text.toIntOrNull() ?: fallback).coerceIn(0, 100)
    fun currentHeal(): HealSettings = HealSettings(
        hpChar = pct(hpCharText, 40),
        spChar = pct(spCharText, 0),
        hpPet = pct(hpPetText, 40),
        spPet = pct(spPetText, 0),
    )

    fun saveDefaultRules() {
        val nextChar = defaultBattleRules(charSkills)
        val nextPet = defaultBattleRules(petSkills)
        charRules = nextChar
        petRules = nextPet
        if (username.isNotBlank() && password.isNotBlank()) {
            onSave(Account(username, password, battleJson(nextChar, nextPet), currentHeal()))
        }
    }

    if (confirmDefault) {
        AlertDialog(
            onDismissRequest = { confirmDefault = false },
            title = { Text("Nạp mẫu") },
            text = { Text("Nạp kịch bản skill mặc định và lưu áp dụng ngay?") },
            confirmButton = {
                TextButton(onClick = {
                    confirmDefault = false
                    saveDefaultRules()
                }) { Text("Đồng ý") }
            },
            dismissButton = {
                TextButton(onClick = { confirmDefault = false }) { Text("Hủy") }
            },
        )
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = username,
                    onValueChange = { username = it },
                    label = { Text("Tài khoản") },
                    singleLine = true,
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Mật khẩu") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                )
                Spacer(Modifier.height(12.dp))
                Text("Chiến đấu", style = MaterialTheme.typography.titleSmall)
                Text(
                    if (charSkills.isNotEmpty() || petSkills.isNotEmpty()) {
                        "Skill live lấy từ acc đang online"
                    } else {
                        "Muốn chọn skill đã học thì chạy acc trước"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                Text("Hồi HP/SP", style = MaterialTheme.typography.titleSmall)
                Text(
                    "Dùng item khi chỉ số tụt dưới ngưỡng (%)",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(6.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = hpCharText,
                        onValueChange = { hpCharText = it.filter { ch -> ch.isDigit() }.take(3) },
                        label = { Text("HP char") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = spCharText,
                        onValueChange = { spCharText = it.filter { ch -> ch.isDigit() }.take(3) },
                        label = { Text("SP char") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.weight(1f),
                    )
                }
                Spacer(Modifier.height(6.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = hpPetText,
                        onValueChange = { hpPetText = it.filter { ch -> ch.isDigit() }.take(3) },
                        label = { Text("HP pet") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = spPetText,
                        onValueChange = { spPetText = it.filter { ch -> ch.isDigit() }.take(3) },
                        label = { Text("SP pet") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.weight(1f),
                    )
                }
                TextButton(onClick = {
                    hpCharText = "40"
                    spCharText = "0"
                    hpPetText = "40"
                    spPetText = "0"
                }) { Text("Mặc định hồi máu") }
                Spacer(Modifier.height(12.dp))
                BattleRuleUnitEditor("Char", charRules, charSkills) { charRules = it }
                Spacer(Modifier.height(8.dp))
                BattleRuleUnitEditor("Pet", petRules, petSkills) { petRules = it }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (username.isNotBlank() && password.isNotBlank()) {
                        val bj = battleJson(charRules, petRules)
                        onSave(Account(username, password, bj, currentHeal()))
                    }
                },
            ) {
                Text("Lưu")
            }
        },
        dismissButton = {
            Row {
                TextButton(onClick = { confirmDefault = true }) { Text("Mặc định") }
                TextButton(onClick = onDismiss) { Text("Hủy") }
            }
        },
    )
}

@Composable
fun ChannelDialog(
    onDismiss: () -> Unit,
    onGetChannels: () -> List<Triple<Int, Int, Int>>,
    onPick: (Int) -> Unit,
    onAuto: () -> Unit,
) {
    var loading by remember { mutableStateOf(true) }
    var channels by remember { mutableStateOf<List<Triple<Int, Int, Int>>>(emptyList()) }
    LaunchedEffect(Unit) {
        channels = withContext(Dispatchers.IO) { onGetChannels() }
        loading = false
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Đổi kênh") },
        text = {
            Column {
                TextButton(onClick = onAuto) { Text("⭐ Tự chọn kênh vắng nhất") }
                Spacer(Modifier.height(4.dp))
                when {
                    loading -> Text("Đang lấy danh sách kênh...")
                    channels.isEmpty() -> Text("Không lấy được danh sách kênh (account chưa chạy?)")
                    else -> LazyColumn(modifier = Modifier.height(320.dp)) {
                        items(channels) { (ch, cur, cap) ->
                            TextButton(
                                onClick = { onPick(ch) },
                                modifier = Modifier.fillMaxWidth(),
                            ) { Text("Kênh $ch   —   $cur/$cap người") }
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Đóng") } },
    )
}

@Composable
fun CityDialog(
    onDismiss: () -> Unit,
    allowRouteMaps: Boolean,
    onPick: (Cities.Info) -> Unit,
    onRouteMaps: (Int, Int) -> Unit,
) {
    var showRoute by remember { mutableStateOf(false) }
    var sourceMap by remember { mutableStateOf("") }
    var destMap by remember { mutableStateOf("") }
    // Khi bam "Chon Thanh" trong che do di bo -> tap 1 thanh se dien cityId (= map id) vao o BBB
    // thay vi teleport. Giup user chon thanh dich ma khong phai nho so map.
    var pickForDest by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Đổi thành (teleport)") },
        text = {
            Column {
                if (allowRouteMaps) {
                    OutlinedButton(
                        onClick = { showRoute = !showRoute },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Đi bộ từ map AAA đến map BBB") }
                }
                if (allowRouteMaps && showRoute) {
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = sourceMap,
                        onValueChange = { sourceMap = it },
                        label = { Text("Map AAA (để trống = tự chọn)") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(6.dp))
                    OutlinedTextField(
                        value = destMap,
                        onValueChange = { destMap = it },
                        label = { Text("Map BBB") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(6.dp))
                    Button(
                        onClick = {
                            val source = sourceMap.trim().toIntOrNull() ?: 0
                            val dest = destMap.trim().toIntOrNull()
                            if (dest != null && dest > 0) onRouteMaps(source, dest)
                        },
                        enabled = (destMap.trim().toIntOrNull() ?: 0) > 0,
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Bắt đầu kéo map") }
                    Spacer(Modifier.height(6.dp))
                    OutlinedButton(
                        onClick = { pickForDest = !pickForDest },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text(if (pickForDest) "Đang chọn Thành cho ô BBB… (bấm để hủy)" else "Chọn Thành") }
                    Spacer(Modifier.height(10.dp))
                }
                LazyColumn(modifier = Modifier.height(320.dp)) {
                    // Map di-bo dac biet (khong teleport duoc) o DAU danh sach - chi hien khi dang
                    // chon Thanh cho o BBB.
                    if (pickForDest) {
                        item {
                            TextButton(
                                onClick = { destMap = "55002"; pickForDest = false },
                                modifier = Modifier.fillMaxWidth(),
                            ) { Text("Nhà Nam Tinh Quân") }
                        }
                    }
                    items(Cities.ALL.values.toList()) { info ->
                        TextButton(
                            onClick = {
                                if (pickForDest) {
                                    destMap = info.cityId.toString()
                                    pickForDest = false
                                } else {
                                    onPick(info)
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(info.label) }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Đóng") } },
    )
}

@Composable
fun GiftcodeDialog(
    onDismiss: () -> Unit,
    onSave: (String) -> Unit,
) {
    var code by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Nhập giftcode") },
        text = {
            OutlinedTextField(
                value = code,
                onValueChange = { code = it },
                label = { Text("Giftcode") },
                singleLine = true,
            )
        },
        confirmButton = {
            Button(onClick = { if (code.isNotBlank()) onSave(code.trim()) }) {
                Text("Lưu")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Hủy") }
        },
    )
}
