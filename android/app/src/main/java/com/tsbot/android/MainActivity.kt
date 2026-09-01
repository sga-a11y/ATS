package com.tsbot.android

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.net.Uri
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
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
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
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.produceState
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Switch
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.window.PopupProperties
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
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

    private fun startAndBindBotService() {
        if (isBound) return
        val serviceIntent = Intent(this, BotForegroundService::class.java)
        ContextCompat.startForegroundService(this, serviceIntent)
        isBound = bindService(serviceIntent, connection, Context.BIND_AUTO_CREATE)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Servers.init(applicationContext)   // danh sach server doc tu assets/servers.json

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

        lifecycleScope.launch {
            withContext(Dispatchers.IO) {
                runCatching { ApkUpdater.updateBundleIfNeeded(applicationContext) }
                    .onFailure { android.util.Log.w("aTSBot", "bundle update failed: ${it.message}", it) }
            }
            startAndBindBotService()
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

fun partyStatusColor(party: Party, statusMap: Map<String, AccountStatus>): Color {
    val enabledAccounts = party.accounts.filter { it.enabled }
    if (enabledAccounts.isEmpty()) return StatusStopped
    val states = enabledAccounts.map { statusMap[it.username]?.state ?: RunState.IDLE }
    val running = states.count { it == RunState.RUNNING }
    val connecting = states.any { it == RunState.CONNECTING }
    return when {
        running == enabledAccounts.size -> StatusRunning
        running > 0 || connecting -> StatusConnecting
        else -> StatusStopped
    }
}

private const val PRIVACY_FULL = 0
private const val PRIVACY_MASK = 1
private const val PRIVACY_ORDINAL = 2
private val TeamDungeonLevels = listOf(20, 50, 80, 110)

private data class UpdateDialogLink(val label: String, val url: String)

private data class UpdateDialogMessage(
    val title: String,
    val body: String,
    val links: List<UpdateDialogLink> = emptyList(),
)

private fun defaultTeamDungeons(src: Map<Int, Boolean> = emptyMap()): Map<Int, Boolean> =
    linkedMapOf(
        20 to (src[20] ?: true),
        50 to (src[50] ?: true),
        80 to (src[80] ?: true),
        110 to (src[110] ?: false),
    )

fun teamDungeonsJson(value: Map<Int, Boolean>): String = JSONObject().apply {
    TeamDungeonLevels.forEach { put(it.toString(), value[it] ?: false) }
}.toString()

fun accountOrdinalMap(parties: List<Party>): Map<String, String> {
    var index = 1
    val out = linkedMapOf<String, String>()
    parties.forEach { party ->
        party.accounts.forEach { account ->
            if (account.username.isNotBlank() && !out.containsKey(account.username)) {
                out[account.username] = "acc${index++}"
            }
        }
    }
    return out
}

fun maskPart(value: String): String {
    if (value.isBlank() || value == "—") return value
    if (value.length <= 3) return value.take(1) + "***"
    return value.take(1) + "***" + value.takeLast(2)
}

fun maskUsername(username: String, mode: Int, ordinals: Map<String, String>): String = when (mode) {
    PRIVACY_FULL -> username
    PRIVACY_ORDINAL -> ordinals[username] ?: maskPart(username)
    else -> maskPart(username)
}

fun maskCharacterName(name: String, username: String, mode: Int, ordinals: Map<String, String>): String = when (mode) {
    PRIVACY_FULL -> name
    PRIVACY_ORDINAL -> ordinals[username] ?: maskPart(name)
    else -> maskPart(name)
}

fun maskAccountLog(
    logText: String,
    username: String,
    charName: String,
    mode: Int,
    ordinals: Map<String, String>,
): String {
    if (mode == PRIVACY_FULL) return logText
    var out = logText.replace("[$username]", "[${maskUsername(username, mode, ordinals)}]")
    if (charName.isNotBlank()) {
        out = out.replace("[$charName]", "[${maskCharacterName(charName, username, mode, ordinals)}]")
    }
    return out
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
    var editingHealAccount by remember { mutableStateOf<Pair<String, Account>?>(null) }
    // XOA phai HOI TRUOC (user: bam phat xoa luon -> bam nham la khoc).
    // (ten party, username) dang cho xac nhan xoa acc | ten party dang cho xac nhan xoa party.
    var confirmDeleteAccount by remember { mutableStateOf<Pair<String, String>?>(null) }
    var confirmDeleteParty by remember { mutableStateOf<String?>(null) }
    var editingSkillAccount by remember { mutableStateOf<Pair<String, Account>?>(null) }
    var editingPointAccount by remember { mutableStateOf<Pair<String, Account>?>(null) }
    // Tab party dang chon (moi party = 1 tab, giong ban PC)
    var selectedTab by remember { mutableStateOf(0) }
    var privacyMode by rememberSaveable { mutableStateOf(PRIVACY_MASK) }

    val service = boundServiceProvider()
    val statusMap by (service?.status?.collectAsState() ?: remember { mutableStateOf(emptyMap()) })
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val privacyOrdinals = remember(parties) { accountOrdinalMap(parties) }
    var currentCoreVersion by remember { mutableStateOf(ApkUpdater.effectiveVersion(context)) }
    var updateInfo by remember { mutableStateOf<ApkUpdateInfo?>(null) }
    var updateBusyText by remember { mutableStateOf<String?>(null) }
    var updateMessage by remember { mutableStateOf<UpdateDialogMessage?>(null) }
    var pendingInstallApk by remember { mutableStateOf<File?>(null) }

    fun manualUpdateMessage(title: String, body: String): UpdateDialogMessage =
        UpdateDialogMessage(
            title = title,
            body = body,
            links = listOf(
                UpdateDialogLink("GitHub APK", ApkUpdater.GITHUB_APK_DOWNLOAD_URL),
                UpdateDialogLink("Google Drive", ApkUpdater.MANUAL_DOWNLOAD_URL),
            ),
        )

    fun openExternalUrl(url: String) {
        runCatching {
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        }
    }

    fun refresh() {
        parties = partyStore.load()
    }

    fun checkApkUpdate(manual: Boolean) {
        if (updateBusyText != null) return
        scope.launch {
            if (manual) updateBusyText = "Đang kiểm tra bản mới..."
            try {
                if (manual) {
                    val bundleUpdated = withContext(Dispatchers.IO) {
                        ApkUpdater.updateBundleIfNeeded(context.applicationContext)
                    }
                    if (bundleUpdated) {
                        currentCoreVersion = ApkUpdater.effectiveVersion(context)
                    }
                } else {
                    currentCoreVersion = ApkUpdater.effectiveVersion(context)
                }
                val info = withContext(Dispatchers.IO) {
                    ApkUpdater.checkUpdate(BuildConfig.VERSION_NAME)
                }
                currentCoreVersion = ApkUpdater.effectiveVersion(context)
                if (info != null) {
                    updateInfo = info
                } else if (manual) {
                    updateMessage = UpdateDialogMessage(
                        "Update",
                        "Đang là bản mới nhất: core v$currentCoreVersion\nAPK: v${BuildConfig.VERSION_NAME}",
                    )
                }
            } catch (e: Exception) {
                if (manual) {
                    updateMessage = manualUpdateMessage(
                        "Lỗi cập nhật",
                        "Không kiểm tra được bản mới:\n${e.message ?: e.javaClass.simpleName}",
                    )
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
                updateMessage = manualUpdateMessage(
                    "Lỗi cập nhật",
                    "Không tải/cài được APK:\n${e.message ?: e.javaClass.simpleName}",
                )
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

    fun startAccountIn(party: Party, account: Account) {
        if (account.enabled) startPartyIn(party)
    }

    fun startAllParties() {
        service?.startAll(parties)
    }

    fun stopAllParties() {
        scope.launch(Dispatchers.IO) { service?.stopAll() }
    }

    val runningCount = statusMap.values.count { it.state == RunState.RUNNING }
    val totalAccounts = parties.sumOf { party -> party.accounts.count { it.enabled } }
    val anyConnecting = parties.any { party ->
        party.accounts.any { account ->
            account.enabled && statusMap[account.username]?.state == RunState.CONNECTING
        }
    }
    val allPartiesColor = when {
        totalAccounts > 0 && runningCount == totalAccounts -> StatusRunning
        runningCount > 0 || anyConnecting -> StatusConnecting
        else -> StatusStopped
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("aTSBot", fontWeight = FontWeight.Bold)
                        Spacer(Modifier.width(6.dp))
                        Text(
                            "v$currentCoreVersion",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.width(10.dp))
                        if (totalAccounts > 0) {
                            StatusDot(allPartiesColor)
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
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    FilledTonalButton(
                        onClick = ::startAllParties,
                        enabled = service != null && totalAccounts > 0,
                        modifier = Modifier.weight(1f),
                    ) {
                        Icon(Icons.Default.PlayArrow, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Chạy tất cả", maxLines = 1)
                    }
                    Spacer(Modifier.width(8.dp))
                    OutlinedButton(
                        onClick = ::stopAllParties,
                        enabled = service != null,
                        modifier = Modifier.weight(1f),
                    ) {
                        StopIcon()
                        Spacer(Modifier.width(4.dp))
                        Text("Dừng tất cả", maxLines = 1)
                    }
                }

                // Moi party = 1 TAB (giong ban PC). Tab hien ten party + cham trang thai.
                val curTab = selectedTab.coerceIn(0, parties.size - 1)
                ScrollableTabRow(
                    selectedTabIndex = curTab,
                    containerColor = MaterialTheme.colorScheme.surface,
                    edgePadding = 8.dp,
                ) {
                    parties.forEachIndexed { i, p ->
                        Tab(
                            selected = i == curTab,
                            onClick = { selectedTab = i },
                            text = {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    StatusDot(partyStatusColor(p, statusMap), 8)
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
                        privacyMode = privacyMode,
                        privacyOrdinals = privacyOrdinals,
                        onTogglePrivacy = { privacyMode = (privacyMode + 1) % 3 },
                        onAddAccount = { addAccountForParty = party.name },
                        onEditParty = { editingParty = party },
                        onEditAccount = { account -> editingAccount = party.name to account },
                        onEditHeal = { account -> editingHealAccount = party.name to account },
                        onEditSkill = { account -> editingSkillAccount = party.name to account },
                        onEditPoint = { account -> editingPointAccount = party.name to account },
                        onEnabledChange = { account, enabled ->
                            partyStore.updateAccountInParty(
                                party.name,
                                account.username,
                                account.copy(enabled = enabled),
                            )
                            refresh()
                        },
                        onRemoveAccount = { username ->
                            confirmDeleteAccount = party.name to username   // hoi truoc khi xoa
                        },
                        onRemoveParty = {
                            confirmDeleteParty = party.name                 // hoi truoc khi xoa
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
                        onFurnaceNotify = {
                            // pidx suy tu vi tri party trong list (giong startPartyIn)
                            val _pi = parties.indexOf(party)
                            // THU TU giong GUI PC: BA DAU -> QUAN DOAN -> DU DIEM -> LO.
                            // Ba Dau len dau vi no la viec CO HAN GIO (het la mat quyen loi hoi
                            // day HP/SP), con lai luc nao lam cung duoc.
                            if (_pi >= 0)
                                (service?.baDauNotifyItems(_pi) ?: emptyList()) +
                                    (service?.legionNotifyItems(_pi) ?: emptyList()) +
                                    (service?.diemDuNotifyItems(_pi) ?: emptyList()) +
                                    (service?.furnaceNotifyItems(_pi) ?: emptyList())
                            else emptyList()
                        },
                        onFurnaceBuy = { u, tid -> service?.furnaceNotifyBuy(u, tid) ?: false },
                        onFurnaceSkip = { u, tid -> service?.furnaceNotifySkip(u, tid) ?: false },
                        onLegionSkip = { u -> service?.legionNotifySkip(u) ?: false },
                        onBaDauSkip = { u -> service?.baDauNotifySkip(u) ?: false },
                        onDiemDuSkip = { u -> service?.diemDuNotifySkip(u) ?: false },
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
            title = { Text(message.title) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(message.body)
                    if (message.links.isNotEmpty()) {
                        Spacer(Modifier.height(4.dp))
                        Text("Tải thủ công:", fontWeight = FontWeight.SemiBold)
                        message.links.forEach { link ->
                            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text(link.label, style = MaterialTheme.typography.bodySmall)
                                Text(
                                    link.url,
                                    color = MaterialTheme.colorScheme.primary,
                                    style = MaterialTheme.typography.bodySmall,
                                    modifier = Modifier.clickable { openExternalUrl(link.url) },
                                )
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { updateMessage = null }) { Text("Đóng") }
            },
        )
    }

    if (showAddPartyDialog) {
        AddPartyDialog(
            onDismiss = { showAddPartyDialog = false },
            onSave = { party ->
                val saved = partyStore.addParty(party)
                if (saved) {
                    refresh()
                    showAddPartyDialog = false
                }
                saved
            },
            // Party moi: mac dinh mode Train map + bai "Rung Noi Huynh" (TRAIN_MAPS key 12831).
            initialRunMode = RunModes.TRAIN,
            initialTrainMapKey = "12831",
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

    // ---- XAC NHAN XOA (user: bam phat xoa luon -> bam nham la khoc) ----
    val delAcc = confirmDeleteAccount
    if (delAcc != null) {
        val (pName, uName) = delAcc
        AlertDialog(
            onDismissRequest = { confirmDeleteAccount = null },
            title = { Text("Xóa tài khoản?") },
            text = { Text("Xóa '" + uName + "' khỏi party '" + pName + "'?\nKhông khôi phục lại được.") },
            confirmButton = {
                Button(
                    onClick = {
                        confirmDeleteAccount = null
                        partyStore.removeAccountFromParty(pName, uName)
                        refresh()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = StatusError),
                ) { Text("Xóa") }
            },
            dismissButton = { TextButton(onClick = { confirmDeleteAccount = null }) { Text("Hủy") } },
        )
    }
    val delParty = confirmDeleteParty
    if (delParty != null) {
        val nAcc = parties.firstOrNull { it.name == delParty }?.accounts?.size ?: 0
        AlertDialog(
            onDismissRequest = { confirmDeleteParty = null },
            title = { Text("Xóa party?") },
            text = { Text("Xóa party '" + delParty + "' và " + nAcc + " tài khoản trong đó?\nKhông khôi phục lại được.") },
            confirmButton = {
                Button(
                    onClick = {
                        confirmDeleteParty = null
                        partyStore.removeParty(delParty)
                        selectedTab = 0
                        refresh()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = StatusError),
                ) { Text("Xóa") }
            },
            dismissButton = { TextButton(onClick = { confirmDeleteParty = null }) { Text("Hủy") } },
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
            initialClaimOfflineExp = partyBeingEdited.claimOfflineExp,
            initialAutoWorldBoss = partyBeingEdited.autoWorldBoss,
            initialAutoTeamDungeon = partyBeingEdited.autoTeamDungeon,
            initialTeamDungeons = partyBeingEdited.teamDungeons,
            initialTrainMapKey = partyBeingEdited.trainMapKey,
            initialTrainMobIndex = partyBeingEdited.trainMobIndex,
            initialTrainPick = partyBeingEdited.trainPick,
            initialMobMin = partyBeingEdited.mobMin,
            initialMobMax = partyBeingEdited.mobMax,
            initialMobElements = partyBeingEdited.mobElements,
            initialUsePhucThan = partyBeingEdited.usePhucThan,
            initialUseDigioiHoPhu = partyBeingEdited.useDigioiHoPhu,
            initialFightLegionBoss = partyBeingEdited.fightLegionBoss,
            initialDoVanTieu = partyBeingEdited.doVanTieu,
            initialAutoSellNoiDat = partyBeingEdited.autoSellNoiDat,
            initialDeathReturnTown = partyBeingEdited.deathReturnTown,
            initialPetDeathReturnTown = partyBeingEdited.petDeathReturnTown,
            initialAutoBagClean = partyBeingEdited.autoBagClean,
            initialAutoDiscardJunk = partyBeingEdited.autoDiscardJunk,
            initialAutoDecomposeScrolls = partyBeingEdited.autoDecomposeScrolls,
            initialScrollModes = partyBeingEdited.scrollModes,
            initialAutoDonateMaterials = partyBeingEdited.autoDonateMaterials,
            initialMaterialModes = partyBeingEdited.materialModes,
            initialAutoEventExchange = partyBeingEdited.autoEventExchange,
            initialEventExchangeItems = partyBeingEdited.eventExchangeItems,
            initialAutoBuyShop = partyBeingEdited.autoBuyShop,
            initialBuyHoPhu = partyBeingEdited.buyHoPhu,
            initialBuyThienChau = partyBeingEdited.buyThienChau,
            initialBuyBaoHop = partyBeingEdited.buyBaoHop,
            initialBaoHopXuThreshold = partyBeingEdited.baoHopXuThreshold,
            initialBuyHp = partyBeingEdited.buyHp,
            initialHpQty = partyBeingEdited.hpQty,
            initialHpThresh = partyBeingEdited.hpThresh,
            initialBuySp = partyBeingEdited.buySp,
            initialSpQty = partyBeingEdited.spQty,
            initialSpThresh = partyBeingEdited.spThresh,
            initialDiGioiLevel = partyBeingEdited.diGioiLevel,
            initialDiGioiPick = partyBeingEdited.diGioiPick,
            onApplyDiGioiLevel = { idx ->
                service?.setDiGioiLevel(partyBeingEdited.accounts.map { it.username }, idx)
            },
            onDismiss = { editingParty = null },
            onSave = { edited ->
                // Cuon vua chuyen sang PHAN GIAI -> tat Bi Cap/K.Toa/T.Tinh/Me ben lo cua MOI
                // account trong party (config lo la cua TUNG account, list phan giai la cua party
                // -> khong quet het thi acc khac van mua roi bi pha).
                val dropped = newlyDroppedScrolls(
                    context, partyBeingEdited.scrollModes, edited.scrollModes)
                var syncedFurnace = 0
                val accs = partyBeingEdited.accounts.map { acc ->
                    val (f, n) = furnaceWithScrollsSkipped(context, acc.furnace, dropped)
                    syncedFurnace += n
                    if (n > 0) acc.copy(furnace = f) else acc
                }
                // Giu nguyen danh sach account, chi doi ten/server.
                val saved = partyStore.updateParty(
                    partyBeingEdited.name,
                    edited.copy(accounts = accs),
                )
                if (saved && syncedFurnace > 0) {
                    accs.forEach { service?.applyAccountFurnace(it.username, it.furnace.toRuntimeJson()) }
                    android.widget.Toast.makeText(
                        context,
                        "Đã chuyển $syncedFurnace mục bên lò sang \"Bỏ qua\"",
                        android.widget.Toast.LENGTH_LONG,
                    ).show()
                }
                if (saved) {
                    refresh()
                    editingParty = null
                }
                saved
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
            initialFurnace = account.furnace,
            initialVantieu = account.vantieu,   // giu config van tieu khi sua thong tin dang nhap
            initialEnabled = account.enabled,
            onDismiss = { editingAccount = null },
            onSave = { edited ->
                // Item lo vua thoat "Bo qua" -> cuon so huu no ve "Giu lai" (khong thi vua
                // mua vua phan giai). scrollModes la cua PARTY nen ghi vao party dang sua.
                run {
                    val un = furnaceUnskippedTids(context, account.furnace, edited.furnace)
                    val party = parties.firstOrNull { it.name == partyName }
                    if (party != null && un.isNotEmpty()) {
                        val (m, n) = scrollModesAfterUnskip(context, party.scrollModes, un)
                        if (n > 0) {
                            partyStore.updateParty(party.name, party.copy(scrollModes = m))
                            android.widget.Toast.makeText(
                                context,
                                "Đã chuyển $n cuộn sang \"Giữ lại\"",
                                android.widget.Toast.LENGTH_LONG,
                            ).show()
                        }
                    }
                }
                partyStore.updateAccountInParty(partyName, account.username, edited)
                service?.applyAccountBattle(edited.username, edited.battleJson)
                service?.applyAccountHeal(edited.username, edited.heal.toRuntimeJson(edited.vantieu))
                service?.applyAccountFurnace(edited.username, edited.furnace.toRuntimeJson())
                refresh()
                editingAccount = null
            },
        )
    }

    val healAccount = editingHealAccount
    if (healAccount != null) {
        val (partyName, account) = healAccount
        HealSettingsDialog(
            initialHeal = account.heal,
            initialFurnace = account.furnace,
            initialVantieu = account.vantieu,
            innPets = service?.accountInnPets(account.username) ?: emptyList(),
            onDismiss = { editingHealAccount = null },
            onApplyToAll = { heal, furnace, vantieuOn ->
                val count = partyStore.applyHealToAllAccounts(heal)
                partyStore.applyFurnaceToAllAccounts(furnace)
                // VAN TIEU: chi dong bo O TICK, KHONG dong bo list pet - pet nha tro moi acc mot
                // khac (id khac han nhau) nen ap list cua acc nay sang acc khac la vo nghia.
                partyStore.applyVantieuOnToAllAccounts(vantieuOn)
                partyStore.load().flatMap { it.accounts }.forEach {
                    service?.applyAccountHeal(it.username, heal.toRuntimeJson(it.vantieu))
                    service?.applyAccountFurnace(it.username, furnace.toRuntimeJson())
                }
                refresh()
                count
            },
            onSave = { editedHeal, editedFurnace, editedVantieu ->
                // Item lo vua thoat "Bo qua" -> cuon so huu no ve "Giu lai" (khong thi vua
                // mua vua phan giai). scrollModes la cua PARTY nen ghi vao party dang sua.
                run {
                    val un = furnaceUnskippedTids(context, account.furnace, editedFurnace)
                    val party = parties.firstOrNull { it.name == partyName }
                    if (party != null && un.isNotEmpty()) {
                        val (m, n) = scrollModesAfterUnskip(context, party.scrollModes, un)
                        if (n > 0) {
                            partyStore.updateParty(party.name, party.copy(scrollModes = m))
                            android.widget.Toast.makeText(
                                context,
                                "Đã chuyển $n cuộn sang \"Giữ lại\"",
                                android.widget.Toast.LENGTH_LONG,
                            ).show()
                        }
                    }
                }
                partyStore.updateAccountInParty(
                    partyName,
                    account.username,
                    account.copy(heal = editedHeal, furnace = editedFurnace,
                                 vantieu = editedVantieu),
                )
                service?.applyAccountHeal(account.username, editedHeal.toRuntimeJson(editedVantieu))
                service?.applyAccountFurnace(account.username, editedFurnace.toRuntimeJson())
                refresh()
                editingHealAccount = null
            },
        )
    }

    val pointAccount = editingPointAccount
    if (pointAccount != null) {
        val (partyName, account) = pointAccount
        PointSettingsDialog(
            username = account.username,
            initialPointJson = account.pointJson,
            onLoadInfo = { service?.pointInfoJson(account.username) ?: "" },
            onAddPoint = { key, add -> service?.addPoint(account.username, key, add) ?: "False" },
            onDismiss = { editingPointAccount = null },
            onSave = { json ->
                partyStore.updateAccountInParty(
                    partyName, account.username, account.copy(pointJson = json))
                service?.applyPointConfig(account.username, json)
                refresh()
                editingPointAccount = null
            },
        )
    }

    val skillAccount = editingSkillAccount
    if (skillAccount != null) {
        val (partyName, account) = skillAccount
        val skills = service?.accountSkills(account.username)
            ?: BotForegroundService.AccountSkills(emptyList(), emptyList(), emptyList(), 0)
        SkillSettingsDialog(
            initialBattleJson = account.battleJson,
            charSkills = skills.char,
            petSkills = skills.pet,
            pets = skills.pets,
            activePid = skills.activePid,
            dangerousNpcNames = {
                service?.dangerousNpcNames()?.takeIf { it.isNotEmpty() } ?: DefaultDangerousNpcNames
            },
            onSaveDangerousNpcNames = { names ->
                service?.saveDangerousNpcNames(names)
            },
            onDismiss = { editingSkillAccount = null },
            onSave = { editedBattleJson ->
                partyStore.updateAccountInParty(
                    partyName,
                    account.username,
                    account.copy(battleJson = editedBattleJson),
                )
                service?.applyAccountBattle(account.username, editedBattleJson)
                refresh()
                editingSkillAccount = null
            },
        )
    }
}

fun loadStatusMapNames(context: Context): Map<Int, String> = buildMap {
    Cities.ALL.values.forEach { put(it.cityId, it.label) }

    fun readMapAsset(name: String): JSONObject {
        val bundled = ApkUpdater.bundleDataFile(context, name)
        val text = if (bundled.isFile) {
            bundled.readText(Charsets.UTF_8)
        } else {
            context.assets
                .open("train_bot_data/$name")
                .bufferedReader(Charsets.UTF_8)
                .use { it.readText() }
        }
        return JSONObject(text)
    }

    fun JSONObject.forEachObject(block: (String, JSONObject) -> Unit) {
        val iterator = keys()
        while (iterator.hasNext()) {
            val key = iterator.next()
            optJSONObject(key)?.let { block(key, it) }
        }
    }

    runCatching {
        val root = readMapAsset("train_maps.json")
        (root.optJSONObject("maps") ?: root).forEachObject { key, info ->
            key.toIntOrNull()?.let { put(it, info.optString("name", key)) }
        }
    }
    runCatching {
        val root = readMapAsset("cities.json")
        (root.optJSONObject("cities") ?: root).forEachObject { key, info ->
            val mapId = info.optInt("city_id", 0)
            if (mapId > 0) put(mapId, info.optString("name", key))
        }
    }
    runCatching {
        val root = readMapAsset("events.json")
        (root.optJSONObject("events") ?: root).forEachObject { key, info ->
            val mapId = info.optInt("dest_map", 0)
            if (mapId > 0) put(mapId, info.optString("label", key))
        }
    }
    runCatching {
        val root = readMapAsset("train_routes.json")
        (root.optJSONObject("routes") ?: root).forEachObject { key, info ->
            val mapId = info.optInt("dest_map", key.toIntOrNull() ?: 0)
            if (mapId > 0 && mapId !in this) put(mapId, info.optString("name", key))
        }
    }

    put(49942, "Dị Giới")
    put(10991, "40 NPC")
    put(55002, "Nhà Nam Tinh Quân")

    // TEN THEO GAME cho MOI map con lai (scene_names.json - boc tu Data/TextData_C.dat bang
    // tools/crack_scene_names.py). Dat CUOI + dung putIfAbsent de cac ten gõ tay o tren van
    // thang. Thieu buoc nay: map ngoai cac bang tren hien SO THO (vd tang thap 2K "12931").
    runCatching {
        val root = readMapAsset("scene_names.json")
        root.keys().forEach { k ->
            val mapId = k.toIntOrNull() ?: return@forEach
            if (mapId !in this) put(mapId, root.optString(k, k))
        }
    }
    // Thap event (2K): 12924..12938 deu ten "Thang Thap" -> them SO TANG cho biet dang o dau.
    runCatching {
        val root = readMapAsset("events.json")
        (root.optJSONObject("events") ?: root).forEachObject { _, info ->
            val pb = info.optJSONObject("party_battle") ?: return@forEachObject
            if (pb.optString("kind") != "floor_crawl") return@forEachObject
            val base = pb.optInt("floor_base", 0)
            val top = pb.optInt("top_map", 0)
            if (base <= 0 || top <= 0) return@forEachObject
            for (mid in (base + 1)..top) {
                val nm = this[mid] ?: continue
                if (nm.firstOrNull()?.isDigit() == false) put(mid, "$nm ${mid - base}")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PartyCard(
    party: Party,
    statusMap: Map<String, AccountStatus>,
    privacyMode: Int,
    privacyOrdinals: Map<String, String>,
    onTogglePrivacy: () -> Unit,
    onAddAccount: () -> Unit,
    onEditParty: () -> Unit,
    onEditAccount: (Account) -> Unit,
    onEditHeal: (Account) -> Unit,
    onEditSkill: (Account) -> Unit,
    onEditPoint: (Account) -> Unit = {},
    onEnabledChange: (Account, Boolean) -> Unit,
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
    // SOI LO - thong bao "Chu y": lay danh sach / mua / bo qua (goi xuong Python qua service)
    onFurnaceNotify: () -> List<Map<String, String>> = { emptyList() },
    onFurnaceBuy: (String, Int) -> Boolean = { _, _ -> false },
    onFurnaceSkip: (String, Int) -> Boolean = { _, _ -> false },
    onLegionSkip: (String) -> Boolean = { _ -> false },
    onBaDauSkip: (String) -> Boolean = { _ -> false },
    onDiemDuSkip: (String) -> Boolean = { _ -> false },
    onCurrentChannel: () -> Int?,
    onGetLog: (String) -> String = { "" },
) {
    val runningInParty = party.accounts.count { statusMap[it.username]?.state == RunState.RUNNING }
    val enabledInParty = party.accounts.count { it.enabled }
    val context = LocalContext.current
    val statusMapNames = remember(context) { loadStatusMapNames(context) }
    val agiValues = party.accounts.flatMap { account ->
        val status = statusMap[account.username]
        buildList {
            status?.charAgi?.let(::add)
            if (!status?.petName.isNullOrBlank()) status?.petAgi?.let(::add)
        }
    }
    val agiSpread = if (agiValues.isEmpty()) null else
        agiValues.maxOrNull()!! - agiValues.minOrNull()!!
    val agiWarning = agiSpread != null && agiSpread > 10

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
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.clickable(onClick = onTogglePrivacy),
                    ) {
                        Text("👁", style = MaterialTheme.typography.bodyMedium)
                        Spacer(Modifier.width(6.dp))
                        Text(party.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    }
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
                    StatusDot(partyStatusColor(party, statusMap))
                    Spacer(Modifier.width(6.dp))
                    Text(
                        "$runningInParty/$enabledInParty đang chạy",
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
                    enabled = party.accounts.any { it.enabled },
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
            var showAgiDialog by remember { mutableStateOf(false) }
            var showNotifyDialog by remember { mutableStateOf(false) }
            var notifyCount by remember { mutableStateOf(0) }
            var notifyItems by remember { mutableStateOf<List<Map<String, String>>>(emptyList()) }
            // poll kenh hien tai + so thong bao lo moi 5s (chi khi party co acc)
            LaunchedEffect(party.accounts.firstOrNull()?.username) {
                while (party.accounts.isNotEmpty()) {
                    curChannel = withContext(Dispatchers.IO) { onCurrentChannel() }
                    val n = withContext(Dispatchers.IO) { onFurnaceNotify() }
                    notifyItems = n
                    notifyCount = n.size
                    delay(5000)
                }
            }
            if (party.accounts.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    "Kênh hiện tại: ${curChannel?.toString() ?: "—"}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    OutlinedButton(
                        onClick = { showChannelDialog = true },
                        modifier = Modifier.weight(1f).height(60.dp),
                    ) { Text("Đổi kênh", maxLines = 2) }
                    OutlinedButton(
                        onClick = { showCityDialog = true },
                        modifier = Modifier.weight(1f).height(60.dp),
                    ) { Text("Đổi thành", maxLines = 2) }
                    OutlinedButton(
                        onClick = { showGiftcodeDialog = true },
                        modifier = Modifier.weight(1f).height(60.dp),
                    ) { Text("Giftcode", maxLines = 2) }
                }
                Spacer(Modifier.height(6.dp))
                // Check AGI THU GON (weight) de nhuong cho nut "Chu y" cung hang. Nut Chu y chi
                // hien khi CO thong bao (giong PC: an mac dinh, pack khi co).
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    OutlinedButton(
                        onClick = { showAgiDialog = true },
                        modifier = Modifier.weight(1f),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 6.dp),
                        colors = ButtonDefaults.outlinedButtonColors(
                            containerColor = if (agiWarning) Color(0xFFFFB74D) else Color.Transparent,
                            contentColor = if (agiWarning) Color(0xFF3E2723) else MaterialTheme.colorScheme.primary,
                        ),
                    ) {
                        Text(if (agiWarning) "⚠ AGI (lệch $agiSpread)" else "⚡ Check AGI",
                            maxLines = 1, style = MaterialTheme.typography.labelLarge,
                            fontWeight = if (agiWarning) FontWeight.Bold else FontWeight.Medium)
                    }
                    if (notifyCount > 0) {
                        // CAM = co viec CAN CHU Y NGAY (hien tai: Ba Dau sap het han) - cung mau
                        // voi nut "Check AGI" luc lech, de nhin luot qua la thay. Con lai vang nhat.
                        val gapNotify = notifyItems.any { it["kind"] == "ba_dau" }
                        OutlinedButton(
                            onClick = { showNotifyDialog = true },
                            modifier = Modifier.weight(1f),
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 6.dp),
                            colors = ButtonDefaults.outlinedButtonColors(
                                containerColor = if (gapNotify) StatusConnecting else Color(0xFFFFF3CD),
                                contentColor = if (gapNotify) Color(0xFF3B2500) else Color(0xFF8A6D00),
                            ),
                        ) {
                            Text("⚠ Chú ý ($notifyCount)", maxLines = 1,
                                style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
                        }
                    }
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
            if (showNotifyDialog) {
                FurnaceNotifyDialog(
                    items = notifyItems,
                    onDismiss = { showNotifyDialog = false },
                    onBuy = { u, tid -> onFurnaceBuy(u, tid) },
                    onSkip = { u, tid -> onFurnaceSkip(u, tid) },
                    onLegionSkip = { u -> onLegionSkip(u) },
                    onBaDauSkip = { u -> onBaDauSkip(u) },
                    onDiemDuSkip = { u -> onDiemDuSkip(u) },
                    onRefresh = {
                        val n = onFurnaceNotify(); notifyItems = n; notifyCount = n.size
                    },
                )
            }
            if (showAgiDialog) {
                PartyAgiDialog(
                    party = party,
                    statusMap = statusMap,
                    privacyMode = privacyMode,
                    privacyOrdinals = privacyOrdinals,
                    onDismiss = { showAgiDialog = false },
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
                        mapLabel = statusMap[account.username]?.mapId?.let { statusMapNames[it] ?: it.toString() } ?: "—",
                        privacyMode = privacyMode,
                        privacyOrdinals = privacyOrdinals,
                        onStart = { onStart(account) },
                        onStop = { onStop(account.username) },
                        onEdit = { onEditAccount(account) },
                        onEditHeal = { onEditHeal(account) },
                        onEditSkill = { onEditSkill(account) },
                        onEditPoint = { onEditPoint(account) },
                        onEnabledChange = { enabled -> onEnabledChange(account, enabled) },
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
    mapLabel: String = "—",
    privacyMode: Int,
    privacyOrdinals: Map<String, String>,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onEdit: () -> Unit,
    onEditHeal: () -> Unit,
    onEditSkill: () -> Unit,
    onEditPoint: () -> Unit,
    onEnabledChange: (Boolean) -> Unit,
    onDelete: () -> Unit,
    expanded: Boolean = false,
    onToggleLog: () -> Unit = {},
    onGetLog: () -> String = { "" },
) {
    val running = status.state == RunState.RUNNING
    val displayUsername = maskUsername(account.username, privacyMode, privacyOrdinals)
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
                Checkbox(
                    checked = account.enabled,
                    onCheckedChange = onEnabledChange,
                    modifier = Modifier.size(36.dp),
                )
                Spacer(Modifier.width(4.dp))
                StatusDot(statusColor(status.state))
                Spacer(Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(displayUsername, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold)
                    val characterParts = buildList {
                        if (status.charName.isNotBlank()) {
                            add(maskCharacterName(status.charName, account.username, privacyMode, privacyOrdinals))
                        }
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
                    if (status.mapId != null || status.channel != null) {
                        val channelLabel = status.channel?.toString() ?: "—"
                        Text(
                            "Map: $mapLabel  •  Kênh: $channelLabel",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Text(
                        statusLabel(status.state),
                        style = MaterialTheme.typography.labelMedium,
                        color = statusColor(status.state),
                    )
                }
            }
            Spacer(Modifier.height(6.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                // Tach hang nut xuong duoi de ten acc/char khong bi bop khi co them HP/SP + Skill.
                if (running) {
                    OutlinedButton(onClick = onStop) { StopIcon(); Spacer(Modifier.width(4.dp)); Text("Dừng") }
                } else {
                    FilledTonalButton(onClick = onStart, enabled = account.enabled) {
                        Icon(Icons.Default.PlayArrow, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(4.dp)); Text("Chạy")
                    }
                }
                IconButton(onClick = onEdit) {
                    Icon(Icons.Default.Edit, contentDescription = "Sửa tài khoản", modifier = Modifier.size(18.dp))
                }
                IconButton(onClick = onEditHeal) {
                    Icon(Icons.Default.Settings, contentDescription = "Hồi HP SP", modifier = Modifier.size(18.dp))
                }
                TextButton(onClick = onEditSkill) {
                    Text("Battle", maxLines = 1)
                }
                TextButton(onClick = onEditPoint) {
                    Text("Point", maxLines = 1)
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
                // Doc log (get_account_log quet ca file + loc + mask regex) CHAY OFF-THREAD:
                // truoc day goi tren MAIN thread trong remember{} -> mo log lag/suyt ANR khi log to.
                // Doc off-thread + TU REFRESH moi 2s khi dang mo (live nhu PC). produceState huy
                // vong lap khi thu gon log (roi khoi if(expanded)) hoac doi acc/charname.
                val logText by produceState(
                    initialValue = "Đang tải log...",
                    expanded, account.username, status.logLabel.ifBlank { status.charName },
                    privacyMode, privacyOrdinals,
                ) {
                    while (true) {
                        value = withContext(Dispatchers.IO) {
                            // Mask theo NHAN LOG (co the la "ten~username" khi trung ten voi acc
                            // khac), khong theo charName tran - trung ten la mask nham acc khac.
                            maskAccountLog(onGetLog(), account.username,
                                status.logLabel.ifBlank { status.charName },
                                privacyMode, privacyOrdinals)
                        }
                        delay(2000)
                    }
                }
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
                        Text("Log của $displayUsername", style = MaterialTheme.typography.labelLarge)
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
val DG_LEVELS: List<Int> by lazy {
    try {
        pyTrainPick().get("DG_LEVELS")!!.asList().map { it.toInt() }
    } catch (e: Exception) {
        listOf(10, 25, 40, 55, 70, 85, 100, 110, 120, 130, 140, 150, 160, 170, 180)
    }
}

/** 5 muc tu chon CAP QUAI DG: (khoa, nhan NGAN). Lay tu Python train_pick.PICK_MODES[i][2]. */
fun dgPickOptions(): List<Pair<String, String>> =
    pyTrainPick().get("PICK_MODES")!!.asList().map { row ->
        val r = row.asList()
        r[0].toString() to r[2].toString()
    }

// (key, ten hien thi, nhom). Nhom = field 'group' trong train_maps.json (mac dinh 'Chua phan nhom').
/** Tien to khoa cua 5 muc "bot tu chon map" trong dropdown Map. */
const val PICK_PREFIX = "pick:"
const val PICK_GROUP = "\u2605 Bot tự chọn map"

private fun pyTrainPick() =
    com.chaquo.python.Python.getInstance().getModule("train_bot.train_pick")

/** 5 muc tu chon map: (khoa "pick:avg-25", nhan, nhom). Nhan LAY TU PYTHON train_pick.PICK_MODES. */
fun trainPickOptions(): List<Triple<String, String, String>> =
    pyTrainPick().get("PICK_MODES")!!.asList().map { row ->
        val pair = row.asList()
        Triple(PICK_PREFIX + pair[0].toString(), pair[1].toString(), PICK_GROUP)
    }

/** 8 he: 7 he cua game + Vo he. (id, ten) - lay tu Python train_pick.ELEMENTS. */
fun elementList(): List<Pair<Int, String>> =
    pyTrainPick().get("ELEMENTS")!!.asList().map { row ->
        val pair = row.asList()
        pair[0].toInt() to pair[1].toString()
    }

fun allElementIds(): List<Int> = elementList().map { it.first }

fun trainMapOptions(): List<Triple<String, String, String>> {
    val config = com.chaquo.python.Python.getInstance().getModule("train_bot.config")
    val maps = config.get("TRAIN_MAPS")!!
    return trainPickOptions() + maps.asMap().entries.map { (k, v) ->
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

fun filterTrainMapOptions(
    opts: List<Triple<String, String, String>>,
    query: String,
): List<Triple<String, String, String>> {
    val q = query.trim().lowercase()
    if (q.isBlank()) return opts
    return opts.filter { (key, mapName, group) ->
        key.lowercase().contains(q) || mapName.lowercase().contains(q) || group.lowercase().contains(q)
    }
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
    onSave: (Party) -> Boolean,
    title: String = "Tạo party",
    initialName: String = "",
    initialServerKey: String = Servers.ALL.keys.first(),
    initialRunMode: String = RunModes.STAND_STILL,
    initialCityKey: String = Cities.ALL.keys.first(),
    initialDigioiSolo: Boolean = false,
    initialNoLeader: Boolean = false,
    initialLeaderWhitelist: List<String> = emptyList(),
    initialDoDaily: Boolean = true,
    initialClaimOfflineExp: Boolean = true,
    initialAutoWorldBoss: Boolean = true,
    initialAutoTeamDungeon: Boolean = true,
    initialTeamDungeons: Map<Int, Boolean> = defaultTeamDungeons(),
    initialTrainMapKey: String = "",
    initialTrainMobIndex: Int = -1,
    initialTrainPick: String = "",
    initialMobMin: Int = 3,
    initialMobMax: Int = 4,
    initialMobElements: List<Int> = listOf(0, 1, 2, 3, 4, 5, 7, 8),
    initialUsePhucThan: Boolean = false,
    initialUseDigioiHoPhu: Boolean = false,
    initialFightLegionBoss: Boolean = true,
    initialDoVanTieu: Boolean = true,
    initialAutoSellNoiDat: Boolean = true,
    initialDeathReturnTown: Boolean = true,
    initialPetDeathReturnTown: Boolean = true,
    initialAutoBagClean: Boolean = true,
    initialAutoDiscardJunk: Boolean = true,
    initialAutoDecomposeScrolls: Boolean = false,
    initialScrollModes: Map<String, String> = emptyMap(),
    initialAutoDonateMaterials: Boolean = true,
    initialMaterialModes: Map<String, String> = emptyMap(),
    initialAutoEventExchange: Boolean = false,
    initialEventExchangeItems: List<String> = emptyList(),
    initialAutoBuyShop: Boolean = false,
    initialBuyHoPhu: Boolean = false,
    initialBuyThienChau: Boolean = false,
    initialBuyBaoHop: Boolean = false,
    initialBaoHopXuThreshold: Int = 10000000,
    initialBuyHp: Boolean = false,
    initialHpQty: Int = 9999,
    initialHpThresh: Int = 500000,
    initialBuySp: Boolean = false,
    initialSpQty: Int = 9999,
    initialSpThresh: Int = 500000,
    initialDiGioiLevel: Int = 2,
    initialDiGioiPick: String = "",
    onApplyAdvancedToAll: ((Party) -> Int)? = null,
    onApplyDiGioiLevel: ((Int) -> Unit)? = null,
) {
    var name by remember { mutableStateOf(initialName) }
    var nameError by remember { mutableStateOf<String?>(null) }
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
    var claimOfflineExp by remember { mutableStateOf(initialClaimOfflineExp) }
    var autoWorldBoss by remember { mutableStateOf(initialAutoWorldBoss) }
    var autoTeamDungeon by remember { mutableStateOf(initialAutoTeamDungeon) }
    var teamDungeons by remember { mutableStateOf(defaultTeamDungeons(initialTeamDungeons)) }
    var showTeamDungeonList by remember { mutableStateOf(false) }
    val initialTrainMapOptions = remember { trainMapOptions() }
    var trainMapKey by remember {
        mutableStateOf(
            if (initialTrainPick.isNotEmpty()) PICK_PREFIX + initialTrainPick
            else initialTrainMapKey.ifEmpty { initialTrainMapOptions.firstOrNull()?.first ?: "" },
        )
    }
    var trainMapText by remember {
        val initialMapName = initialTrainMapOptions.find { it.first == trainMapKey }?.second ?: trainMapKey
        mutableStateOf(TextFieldValue(initialMapName))
    }
    var trainMobExpanded by remember { mutableStateOf(false) }
    var trainMobIndex by remember { mutableStateOf(initialTrainMobIndex) }
    var mobMin by remember { mutableStateOf(initialMobMin.toString()) }
    var mobMax by remember { mutableStateOf(initialMobMax.toString()) }
    var mobElements by remember { mutableStateOf(initialMobElements.toSet()) }
    var showElementList by remember { mutableStateOf(false) }
    val allElems = remember { allElementIds() }
    val isPickMode = trainMapKey.startsWith(PICK_PREFIX)
    var trainMapExpanded by remember { mutableStateOf(false) }
    var collapsedTrainMapGroups by remember { mutableStateOf(emptySet<String>()) }
    var usePhucThan by remember { mutableStateOf(initialUsePhucThan) }
    var useDigioiHoPhu by remember { mutableStateOf(initialUseDigioiHoPhu) }
    var fightLegionBoss by remember { mutableStateOf(initialFightLegionBoss) }
    var doVanTieu by remember { mutableStateOf(initialDoVanTieu) }
    var autoSellNoiDat by remember { mutableStateOf(initialAutoSellNoiDat) }
    var deathReturnTown by remember { mutableStateOf(initialDeathReturnTown) }
    var petDeathReturnTown by remember { mutableStateOf(initialPetDeathReturnTown) }
    var autoBagClean by remember { mutableStateOf(initialAutoBagClean) }
    var autoDiscardJunk by remember { mutableStateOf(initialAutoDiscardJunk) }
    var autoDecomposeScrolls by remember { mutableStateOf(initialAutoDecomposeScrolls) }
    var scrollModes by remember { mutableStateOf(initialScrollModes) }
    var autoDonateMaterials by remember { mutableStateOf(initialAutoDonateMaterials) }
    var materialModes by remember { mutableStateOf(initialMaterialModes) }
    var showMaterialList by remember { mutableStateOf(false) }
    var autoEventExchange by remember { mutableStateOf(initialAutoEventExchange) }
    var eventExchangeItems by remember { mutableStateOf(initialEventExchangeItems) }
    var showEventExchange by remember { mutableStateOf(false) }
    var showBagClean by remember { mutableStateOf(false) }
    var showScrollList by remember { mutableStateOf(false) }
    var autoBuyShop by remember { mutableStateOf(initialAutoBuyShop) }
    var buyHoPhu by remember { mutableStateOf(initialBuyHoPhu) }
    var buyThienChau by remember { mutableStateOf(initialBuyThienChau) }
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
    var diGioiPick by remember { mutableStateOf(initialDiGioiPick) }
    val dgPicks = remember { try { dgPickOptions() } catch (e: Exception) { emptyList() } }
    var diGioiExpandedMode by remember { mutableStateOf(false) }
    var showAdvanced by remember { mutableStateOf(false) }
    var showShopList by remember { mutableStateOf(false) }
    var advancedApplyMessage by remember { mutableStateOf("") }

    fun toggleTrainMapGroup(group: String) {
        collapsedTrainMapGroups = if (group in collapsedTrainMapGroups) {
            collapsedTrainMapGroups - group
        } else {
            collapsedTrainMapGroups + group
        }
    }

    fun currentParty(): Party = Party(
        name = name.ifBlank { initialName.ifBlank { "Party" } },
        serverKey = selectedKey,
        runMode = selectedMode,
        cityKey = selectedCity,
        digioiSolo = digioiSolo,
        noLeader = noLeader,
        leaderWhitelist = parseLeaderWhitelist(leaderWhitelistText),
        doDaily = doDaily,
        claimOfflineExp = claimOfflineExp,
        autoWorldBoss = autoWorldBoss,
        autoTeamDungeon = autoTeamDungeon,
        teamDungeons = teamDungeons,
        trainMapKey = if (isPickMode) "" else trainMapKey,
        trainMobIndex = if (isPickMode) -1 else trainMobIndex,
        trainPick = if (isPickMode) trainMapKey.removePrefix(PICK_PREFIX) else "",
        mobMin = mobMin.toIntOrNull()?.coerceIn(1, 6) ?: 3,
        mobMax = mobMax.toIntOrNull()?.coerceIn(1, 6) ?: 4,
        mobElements = (if (mobElements.isEmpty()) allElems.toSet() else mobElements).sorted(),
        usePhucThan = usePhucThan,
        useDigioiHoPhu = useDigioiHoPhu,
        fightLegionBoss = fightLegionBoss,
        doVanTieu = doVanTieu,
        autoSellNoiDat = autoSellNoiDat,
        deathReturnTown = deathReturnTown,
        petDeathReturnTown = petDeathReturnTown,
        autoBagClean = autoBagClean,
        autoDiscardJunk = autoDiscardJunk,
        autoDecomposeScrolls = autoDecomposeScrolls,
        scrollModes = scrollModes,
        autoDonateMaterials = autoDonateMaterials,
        materialModes = materialModes,
        autoBuyShop = autoBuyShop,
        buyHoPhu = buyHoPhu,
        buyThienChau = buyThienChau,
        buyBaoHop = buyBaoHop,
        baoHopXuThreshold = baoHopXuText.toIntOrNull() ?: 10000000,
        buyHp = buyHp,
        hpQty = hpQtyText.toIntOrNull() ?: 9999,
        hpThresh = hpThreshText.toIntOrNull() ?: 500000,
        buySp = buySp,
        spQty = spQtyText.toIntOrNull() ?: 9999,
        spThresh = spThreshText.toIntOrNull() ?: 500000,
        diGioiLevel = diGioiLevel,
        diGioiPick = diGioiPick,
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
                    onValueChange = {
                        name = it
                        nameError = null
                    },
                    label = { Text("Tên party") },
                    singleLine = true,
                    isError = nameError != null,
                    supportingText = {
                        nameError?.let { Text(it) }
                    },
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
                                Text(
                                    dgPicks.find { it.first == diGioiPick }?.second
                                        ?: DG_LEVELS[diGioiLevel - 1].toString(),
                                )
                            }
                            DropdownMenu(expanded = diGioiExpandedMode, onDismissRequest = { diGioiExpandedMode = false }) {
                                dgPicks.forEach { (key, label) ->
                                    DropdownMenuItem(text = { Text(label) },
                                        onClick = { diGioiPick = key; diGioiExpandedMode = false })
                                }
                                DG_LEVELS.forEachIndexed { i, lv ->
                                    DropdownMenuItem(text = { Text(lv.toString()) },
                                        onClick = {
                                            diGioiLevel = i + 1; diGioiPick = ""
                                            diGioiExpandedMode = false
                                        })
                                }
                            }
                        }
                        // Dang TU CHON thi khong ap ngay duoc: moc quai chi tinh duoc luc chay (can
                        // level ca party), bam nut se ap NHAM cap dang hien.
                        if (onApplyDiGioiLevel != null && diGioiPick.isEmpty()) {
                            TextButton(onClick = { onApplyDiGioiLevel(diGioiLevel) },
                                modifier = Modifier.padding(start = 8.dp)) { Text("Áp dụng ngay") }
                        }
                    }
                }
                // Whitelist co 2 nghia:
                // - Bat: bot dung yen va accept leader ngoai.
                // - Tat: bot-leader moi them acc ngoai sau khi du bot member.
                Spacer(Modifier.height(8.dp))
                if (!(selectedMode == RunModes.DIGIOI && digioiSolo)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = noLeader, onCheckedChange = { noLeader = it })
                        Text("Bot đứng yên, chờ nhận lời mời từ")
                    }
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = leaderWhitelistText,
                        onValueChange = { leaderWhitelistText = it },
                        label = { Text(if (noLeader) "Tên leader" else "Mời thêm acc ngoài party") },
                        supportingText = {
                            Text(
                                if (noLeader)
                                    "Mỗi dòng hoặc dấu phẩy = 1 tên nhân vật leader. Để trống = nhận lời mời từ mọi người."
                                else
                                    "Khi train, bot mời các tên đang đứng xung quanh trước rồi mới mời acc bot. Acc ngoài vào hay không không ảnh hưởng flow."
                            )
                        },
                        minLines = 2,
                        modifier = Modifier.fillMaxWidth(),
                    )
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
                            Checkbox(checked = claimOfflineExp, onCheckedChange = { claimOfflineExp = it })
                            Text("Nhận exp offline")
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = autoWorldBoss, onCheckedChange = { autoWorldBoss = it })
                            Text("Đánh hết lượt World Boss")
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = autoTeamDungeon, onCheckedChange = { autoTeamDungeon = it })
                            Text("Tự đi phó bản")
                            OutlinedButton(
                                onClick = { showTeamDungeonList = true },
                                modifier = Modifier.padding(start = 8.dp),
                            ) { Text("List phó bản") }
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
                        // VAN TIEU da CHUYEN sang bang setting "Hoi HP SP" CUA TUNG ACC (kem nut
                        // List chon rieng pet nao duoc di van tieu -> don EXP cho vai con). Bo o
                        // tick CHUNG o day de khong co 2 noi dieu khien cung mot thu.
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = autoBagClean, onCheckedChange = { autoBagClean = it })
                            Text("Tự dọn túi đồ")
                            OutlinedButton(
                                onClick = { showBagClean = true },
                                modifier = Modifier.padding(start = 8.dp),
                            ) { Text("Chi tiết") }
                        }
                        // "Tu doi qua event" thuoc CAI DAT NANG CAO (giong gui.py, ngay sau "Tu don
                        // tui do"). Truoc day bi dat NHAM trong dialog "Don dep tui do" -> user mo
                        // Cai dat nang cao khong thay dau, tuong ban APK thieu tinh nang.
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = autoEventExchange, onCheckedChange = { autoEventExchange = it })
                            Text("Tự đổi quà event")
                            OutlinedButton(
                                onClick = { showEventExchange = true },
                                modifier = Modifier.padding(start = 8.dp),
                            ) { Text("List quà") }
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = autoBuyShop, onCheckedChange = { autoBuyShop = it })
                            Text("Tự mua shop")
                            OutlinedButton(
                                onClick = { showShopList = true },
                                modifier = Modifier.padding(start = 8.dp),
                            ) { Text("List shop") }
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
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = deathReturnTown,
                                onCheckedChange = { deathReturnTown = it })
                            Text("Char chết về thành")
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = petDeathReturnTown,
                                onCheckedChange = { petDeathReturnTown = it })
                            Text("Pet chết về thành")
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
                    fun selectedTrainMapName(): String =
                        mapOptions.find { it.first == trainMapKey }?.second ?: trainMapKey

                    fun selectedTrainMapTextValue(): TextFieldValue {
                        val mapName = selectedTrainMapName()
                        return TextFieldValue(
                            text = mapName,
                            selection = TextRange(0, mapName.length),
                        )
                    }

                    fun pickTrainMap(key: String, mapName: String) {
                        trainMapKey = key
                        trainMapText = TextFieldValue(
                            text = mapName,
                            selection = TextRange(0, mapName.length),
                        )
                        trainMobIndex = -1
                        trainMapExpanded = false
                    }

                    fun closeTrainMapDropdown(snapToFirst: Boolean = false) {
                        if (snapToFirst && trainMapText.text.isNotBlank()) {
                            filterTrainMapOptions(mapOptions, trainMapText.text).firstOrNull()?.let { (key, mapName, _) ->
                                pickTrainMap(key, mapName)
                                return
                            }
                        }
                        trainMapText = selectedTrainMapTextValue()
                        trainMapExpanded = false
                    }

                    LaunchedEffect(trainMapExpanded, trainMapKey) {
                        if (trainMapExpanded && trainMapText.text == selectedTrainMapName()) {
                            trainMapText = selectedTrainMapTextValue()
                        }
                    }

                    Box {
                        OutlinedTextField(
                            value = trainMapText,
                            onValueChange = {
                                trainMapText = it
                                trainMapExpanded = true
                            },
                            singleLine = true,
                            label = { Text("Map train") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = trainMapExpanded) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .onFocusChanged { focusState ->
                                    if (focusState.isFocused && !trainMapExpanded) {
                                        trainMapText = selectedTrainMapTextValue()
                                        trainMapExpanded = true
                                    }
                                },
                        )
                        DropdownMenu(
                            expanded = trainMapExpanded,
                            onDismissRequest = { closeTrainMapDropdown(snapToFirst = true) },
                            properties = PopupProperties(focusable = false),
                        ) {
                            val selectedAll = trainMapText.selection.start == 0 &&
                                trainMapText.selection.end == trainMapText.text.length &&
                                trainMapText.text == selectedTrainMapName()
                            val trainMapQuery = if (selectedAll) "" else trainMapText.text
                            val shownMapOptions = filterTrainMapOptions(mapOptions, trainMapQuery)
                            val searchingMap = trainMapQuery.trim().isNotEmpty()
                            val groups = trainMapGroupOrder(shownMapOptions)
                            // Chua gom nhom (chi co 'Chua phan nhom') -> hien PHANG nhu cu, khong header thua.
                            val flat = groups.size <= 1 && groups.firstOrNull() == "Chưa phân nhóm"
                            if (shownMapOptions.isEmpty()) {
                                DropdownMenuItem(
                                    text = { Text("Không tìm thấy map") },
                                    onClick = {},
                                    enabled = false,
                                )
                            } else if (flat) {
                                shownMapOptions.forEach { (key, mapName, _) ->
                                    DropdownMenuItem(text = { Text(mapName) }, onClick = {
                                        pickTrainMap(key, mapName)
                                    })
                                }
                            } else {
                                groups.forEach { g ->
                                    val collapsed = !searchingMap && g in collapsedTrainMapGroups
                                    DropdownMenuItem(
                                        onClick = { toggleTrainMapGroup(g) },
                                        text = { Text(if (collapsed) "▶ 📁 $g" else "▼ 📂 $g") },
                                    )
                                    if (!collapsed) {
                                        shownMapOptions.filter { it.third == g }.forEach { (key, mapName, _) ->
                                            DropdownMenuItem(text = { Text("    $mapName") }, onClick = {
                                                pickTrainMap(key, mapName)
                                            })
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    if (isPickMode) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(
                                value = mobMin,
                                onValueChange = { v -> mobMin = v.filter { it.isDigit() }.take(1) },
                                label = { Text("Quái min") }, singleLine = true,
                                modifier = Modifier.weight(1f),
                            )
                            Spacer(Modifier.width(8.dp))
                            OutlinedTextField(
                                value = mobMax,
                                onValueChange = { v -> mobMax = v.filter { it.isDigit() }.take(1) },
                                label = { Text("Quái max") }, singleLine = true,
                                modifier = Modifier.weight(1f),
                            )
                            Spacer(Modifier.width(8.dp))
                            OutlinedButton(onClick = { showElementList = true }) {
                                Text("Hệ (" + mobElements.size + "/" + allElems.size + ")")
                            }
                        }
                        if (showElementList) {
                            AlertDialog(
                                onDismissRequest = { showElementList = false },
                                confirmButton = {
                                    TextButton(onClick = { showElementList = false }) { Text("Xong") }
                                },
                                title = { Text("Hệ quái muốn đánh") },
                                text = {
                                    Column {
                                        Text("Tick hết hoặc không tick gì = đánh tất cả các hệ.")
                                        elementList().forEach { (eid, name) ->
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                Checkbox(
                                                    checked = eid in mobElements,
                                                    onCheckedChange = { on ->
                                                        mobElements =
                                                            if (on) mobElements + eid else mobElements - eid
                                                    },
                                                )
                                                Text(name)
                                            }
                                        }
                                    }
                                },
                            )
                        }
                    } else {
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
                    if (name.isBlank()) {
                        nameError = "Vui lòng nhập tên party"
                    } else {
                        val saved = onSave(Party(
                            name = name.trim(),
                            serverKey = selectedKey,
                            runMode = selectedMode,
                            cityKey = selectedCity,
                            digioiSolo = digioiSolo,
                            noLeader = noLeader,
                            leaderWhitelist = parseLeaderWhitelist(leaderWhitelistText),
                            doDaily = doDaily,
                            claimOfflineExp = claimOfflineExp,
                            autoWorldBoss = autoWorldBoss,
                            autoTeamDungeon = autoTeamDungeon,
                            teamDungeons = teamDungeons,
                            trainMapKey = if (isPickMode) "" else trainMapKey,
                            trainMobIndex = if (isPickMode) -1 else trainMobIndex,
                            trainPick = if (isPickMode) trainMapKey.removePrefix(PICK_PREFIX) else "",
                            mobMin = mobMin.toIntOrNull()?.coerceIn(1, 6) ?: 3,
                            mobMax = mobMax.toIntOrNull()?.coerceIn(1, 6) ?: 4,
                            mobElements = (if (mobElements.isEmpty()) allElems.toSet() else mobElements).sorted(),
                            usePhucThan = usePhucThan,
                            useDigioiHoPhu = useDigioiHoPhu,
                            fightLegionBoss = fightLegionBoss,
                            doVanTieu = doVanTieu,
                            autoSellNoiDat = autoSellNoiDat,
                            deathReturnTown = deathReturnTown,
                            petDeathReturnTown = petDeathReturnTown,
                            autoBagClean = autoBagClean,
                            autoDiscardJunk = autoDiscardJunk,
                            autoDecomposeScrolls = autoDecomposeScrolls,
                            scrollModes = scrollModes,
                            autoDonateMaterials = autoDonateMaterials,
                            materialModes = materialModes,
                            autoEventExchange = autoEventExchange,
                            eventExchangeItems = eventExchangeItems,
                            eventExchangeSig = if (eventExchangeItems.isEmpty()) ""
                                               else PartyStore.eventSigNow(),
                            autoBuyShop = autoBuyShop,
                            buyHoPhu = buyHoPhu,
                            buyThienChau = buyThienChau,
                            buyBaoHop = buyBaoHop,
                            baoHopXuThreshold = baoHopXuText.toIntOrNull() ?: 10000000,
                            buyHp = buyHp,
                            hpQty = hpQtyText.toIntOrNull() ?: 9999,
                            hpThresh = hpThreshText.toIntOrNull() ?: 500000,
                            buySp = buySp,
                            spQty = spQtyText.toIntOrNull() ?: 9999,
                            spThresh = spThreshText.toIntOrNull() ?: 500000,
                            diGioiLevel = diGioiLevel,
                            diGioiPick = diGioiPick,
                        ))
                        if (!saved) nameError = "Tên party đã tồn tại"
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
    if (showBagClean) {
        AlertDialog(
            onDismissRequest = { showBagClean = false },
            title = { Text("Dọn dẹp túi đồ") },
            text = {
                Column {
                    Text("Các việc bot làm khi bật \"Tự dọn túi đồ\":")
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = autoSellNoiDat, onCheckedChange = { autoSellNoiDat = it })
                        Text("Tự bán Nồi đất")
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = autoDiscardJunk, onCheckedChange = { autoDiscardJunk = it })
                        Text("Tự vứt item rác (Ngọc Hư)")
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = autoDonateMaterials, onCheckedChange = { autoDonateMaterials = it })
                        Text("Tự đóng góp nguyên liệu cho quân đoàn")
                        OutlinedButton(
                            onClick = { showMaterialList = true },
                            modifier = Modifier.padding(start = 8.dp),
                        ) { Text("List") }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = autoDecomposeScrolls, onCheckedChange = { autoDecomposeScrolls = it })
                        Text("Tự phân giải cuộn võ tướng rác")
                        OutlinedButton(
                            onClick = { showScrollList = true },
                            modifier = Modifier.padding(start = 8.dp),
                        ) { Text("List") }
                    }
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Lưu ý: phân giải là MẤT HẲN cuộn. Mặc định giữ lại cuộn của tướng có vũ " +
                            "khí chuyên dụng, còn lại phân giải — nên soát List trước khi bật.",
                        color = androidx.compose.ui.graphics.Color(0xFFAA0000),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = { showBagClean = false }) { Text("Đóng") }
            },
        )
    }

    if (showScrollList) {
        ScrollListDialog(
            modes = scrollModes,
            onDismiss = { showScrollList = false },
            onSave = { scrollModes = it; showScrollList = false },
        )
    }

    if (showEventExchange) {
        EventExchangeDialog(
            picked = eventExchangeItems,
            onDismiss = { showEventExchange = false },
            onSave = { eventExchangeItems = it; showEventExchange = false },
        )
    }

    if (showMaterialList) {
        MaterialListDialog(
            modes = materialModes,
            onDismiss = { showMaterialList = false },
            onSave = { materialModes = it; showMaterialList = false },
        )
    }

    if (showShopList) {
        AlertDialog(
            onDismissRequest = { showShopList = false },
            title = { Text("List shop") },
            text = {
                Column {
                    Text("Chọn vật phẩm shop bot sẽ tự mua:")
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = buyHoPhu, onCheckedChange = { buyHoPhu = it })
                        Text("Dị Giới hộ phù")
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = buyThienChau, onCheckedChange = { buyThienChau = it })
                        Text("Hộp Thiên Châu")
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = buyBaoHop, onCheckedChange = { buyBaoHop = it })
                        Text("Triệu gọi bảo hộp khi xu >")
                        OutlinedTextField(
                            value = baoHopXuText,
                            onValueChange = { baoHopXuText = it.filter { c -> c.isDigit() } },
                            singleLine = true,
                            modifier = Modifier.width(140.dp).padding(start = 6.dp),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showShopList = false }) { Text("Đóng") }
            },
        )
    }
    if (showTeamDungeonList) {
        AlertDialog(
            onDismissRequest = { showTeamDungeonList = false },
            title = { Text("List phó bản") },
            text = {
                Column {
                    Text("Chọn phó bản đội bot sẽ tự đi:")
                    Spacer(Modifier.height(8.dp))
                    TeamDungeonLevels.forEach { level ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(
                                checked = teamDungeons[level] ?: false,
                                onCheckedChange = { checked ->
                                    teamDungeons = defaultTeamDungeons(teamDungeons + (level to checked))
                                },
                            )
                            Text("Phó bản $level")
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showTeamDungeonList = false }) { Text("Đóng") }
            },
        )
    }
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
    "dangerous_npc" to "NPC nguy hiểm",
    "enemy_low_hp" to "Quái ít HP nhất",
    "enemy_high_hp" to "Quái nhiều HP nhất",
    "enemy_first" to "Quái đầu",
    "enemy_last" to "Quái cuối",
    "ally_low_hp" to "Đồng đội ít HP nhất",
    "ally_high_hp" to "Đồng đội nhiều HP nhất",
    "ally_low_sp" to "Đồng đội ít SP nhất",
    "ally_revive_skill" to "Đồng đội có skill Hồi sinh",
    "ally_protect_skill" to "Đồng đội có skill bảo vệ",
    "self" to "Bản thân",
)

private val DefaultDangerousNpcNames = listOf(
    "Chu Công",
    "Hằng Nga",
    "Gia Cát Lượng",
    "Tư Mã Ý",
    "Lục Tốn",
    "Bàng Thống",
    "Lữ Bố",
    "Trần Cung",
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
        // unit "pets/<pid>" = mang nam trong object "pets" (format per-pet moi)
        val arr = if (unit.startsWith("pets/")) {
            obj.optJSONObject("pets")?.optJSONArray(unit.substringAfter("/"))
        } else {
            obj.optJSONArray(unit)
        }
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

/** Vai tro pet: {"train"/"boss"/"quest": pet_id}. Nam TRONG battleJson nen di theo duong config
 *  san co, khong phai them tham so cho service. */
// "pb_don" tach khoi "boss": PB don cho nhieu EXP nen user muon danh rieng mot con de don exp.
// Nhan "quest" ghi ro la PB DOI de khong lan voi PB don.
val PetRoleLabels = listOf(
    "train" to "Train", "boss" to "Boss",
    "quest" to "Quest/PB đội/Event", "pb_don" to "PB đơn",
)

private fun parsePetRoles(json: String): Map<String, Int> {
    if (json.isBlank()) return emptyMap()
    return try {
        val o = JSONObject(json).optJSONObject("pet_roles") ?: return emptyMap()
        o.keys().asSequence().mapNotNull { k -> o.optInt(k, 0).takeIf { it > 0 }?.let { k to it } }.toMap()
    } catch (_: Exception) {
        emptyMap()
    }
}

/** Rule cua 1 pet: uu tien "pets"[pid]; config CU chi co "pet" -> gan cho pet DANG DUNG. */
private fun parsePetRules(json: String, pid: Int, activePid: Int): List<BattleRuleUi> {
    if (json.isBlank()) return listOf(BattleRuleUi())
    return try {
        val root = JSONObject(json)
        val petsObj = root.optJSONObject("pets")
        if (petsObj != null) {
            if (petsObj.has(pid.toString())) parseBattleRules(json, "pets/$pid")
            else listOf(BattleRuleUi())
        } else if (root.has("pet") && (pid == activePid || activePid == 0)) {
            parseBattleRules(json, "pet")
        } else {
            listOf(BattleRuleUi())
        }
    } catch (_: Exception) {
        listOf(BattleRuleUi())
    }
}

/** battleJson format MOI: {"char":[...], "pets":{"<pid>":[...]}} - tab default khong luu. */
private fun battleJsonPets(
    charRules: List<BattleRuleUi>,
    petsMap: Map<Int, List<BattleRuleUi>>,
    petRoles: Map<String, Int> = emptyMap(),
): String {
    val def = BattleRuleUi()
    val charClean = charRules.ifEmpty { listOf(def) }
    val petsClean = petsMap.filterValues { it.isNotEmpty() && it != listOf(def) }
    if (charClean == listOf(def) && petsClean.isEmpty() && petRoles.isEmpty()) return ""
    return JSONObject()
        .apply {
            if (petRoles.isNotEmpty()) {
                put("pet_roles", JSONObject().apply { petRoles.forEach { (r, p) -> put(r, p) } })
            }
        }
        .put("char", JSONArray().also { arr -> charClean.forEach { arr.put(battleRuleObj(it)) } })
        .put("pets", JSONObject().apply {
            petsClean.forEach { (pid, rules) ->
                put(pid.toString(), JSONArray().also { arr -> rules.forEach { arr.put(battleRuleObj(it)) } })
            }
        })
        .toString()
}

private fun battleRuleObj(r: BattleRuleUi) = JSONObject().apply {
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

private fun battleJson(charRules: List<BattleRuleUi>, petRules: List<BattleRuleUi>): String {
    val def = BattleRuleUi()
    val charClean = charRules.ifEmpty { listOf(def) }
    val petClean = petRules.ifEmpty { listOf(def) }
    if (charClean == listOf(def) && petClean == listOf(def)) return ""
    return JSONObject()
        .put("char", JSONArray().also { arr -> charClean.forEach { arr.put(battleRuleObj(it)) } })
        .put("pet", JSONArray().also { arr -> petClean.forEach { arr.put(battleRuleObj(it)) } })
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
    onEditDangerousNpcs: () -> Unit,
    onRules: (List<BattleRuleUi>) -> Unit,
) {
    val isCharacter = title.equals("Char", ignoreCase = true)
    val sectionLabel = if (isCharacter) "NHÂN VẬT (CHAR)" else "PET ĐANG DÙNG"
    val sectionColor = if (isCharacter) {
        MaterialTheme.colorScheme.primaryContainer
    } else {
        MaterialTheme.colorScheme.tertiaryContainer
    }
    val sectionTextColor = if (isCharacter) {
        MaterialTheme.colorScheme.onPrimaryContainer
    } else {
        MaterialTheme.colorScheme.onTertiaryContainer
    }
    Surface(
        color = sectionColor.copy(alpha = 0.14f),
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(8.dp)) {
    Surface(
        color = sectionColor,
        contentColor = sectionTextColor,
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            sectionLabel,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
        )
    }
    Spacer(Modifier.height(4.dp))
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
                if (rule.target == "dangerous_npc") {
                    TextButton(onClick = onEditDangerousNpcs) {
                        Text("Danh sách NPC")
                    }
                }
            }
        }
    }
    TextButton(onClick = { onRules(rules + BattleRuleUi()) }) { Text("+ Thêm rule") }
        }
    }
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
    initialFurnace: FurnaceConfig = FurnaceConfig(),
    initialVantieu: VantieuConfig = VantieuConfig(),
    initialEnabled: Boolean = true,
) {
    var username by remember { mutableStateOf(initialUsername) }
    var password by remember { mutableStateOf(initialPassword) }

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
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (username.isNotBlank() && password.isNotBlank()) {
                        onSave(Account(
                            username = username,
                            password = password,
                            battleJson = initialBattleJson,
                            heal = initialHeal,
                            furnace = initialFurnace,
                            vantieu = initialVantieu,
                            enabled = initialEnabled,
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

// tab furnace: key config -> (pool name trong furnace_pool.json, nhan hien thi)
val FURNACE_TABS = listOf(
    Triple("vo_tuong", "Vo Tuong", "Võ Tướng thường"),
    Triple("trang_bi", "Trang Bi", "Trang Bị thường"),
    Triple("chuyen_sinh", "Chuyen Sinh", "Chuyển Sinh thường"),
)

@Composable
fun HealSettingsDialog(
    initialHeal: HealSettings,
    onDismiss: () -> Unit,
    onSave: (HealSettings, FurnaceConfig, VantieuConfig) -> Unit,
    initialFurnace: FurnaceConfig = FurnaceConfig(),
    initialVantieu: VantieuConfig = VantieuConfig(),
    innPets: List<Pair<Int, String>> = emptyList(),   // (pet_id, ten) trong nha tro; rong = chua biet
    onApplyToAll: ((HealSettings, FurnaceConfig, Boolean) -> Int)? = null,
) {
    var hpCharText by remember(initialHeal) { mutableStateOf(initialHeal.hpChar.toString()) }
    var spCharText by remember(initialHeal) { mutableStateOf(initialHeal.spChar.toString()) }
    var hpPetText by remember(initialHeal) { mutableStateOf(initialHeal.hpPet.toString()) }
    var spPetText by remember(initialHeal) { mutableStateOf(initialHeal.spPet.toString()) }
    var applyMessage by remember { mutableStateOf("") }
    var furnace by remember(initialFurnace) { mutableStateOf(initialFurnace) }
    var pickerTab by remember { mutableStateOf<Triple<String, String, String>?>(null) }
    var vantieu by remember(initialVantieu) { mutableStateOf(initialVantieu) }
    var showVantieuPets by remember { mutableStateOf(false) }

    fun pct(text: String, fallback: Int): Int = (text.toIntOrNull() ?: fallback).coerceIn(0, 100)
    fun currentHeal() = HealSettings(
        hpChar = pct(hpCharText, 40),
        spChar = pct(spCharText, 0),
        hpPet = pct(hpPetText, 40),
        spPet = pct(spPetText, 0),
    )

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Hồi HP/SP + Soi lò") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                Text(
                    "Dùng item khi chỉ số tụt dưới ngưỡng (%)",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    HealPercentField("HP char", hpCharText, { hpCharText = it }, Modifier.weight(1f))
                    HealPercentField("SP char", spCharText, { spCharText = it }, Modifier.weight(1f))
                }
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    HealPercentField("HP pet", hpPetText, { hpPetText = it }, Modifier.weight(1f))
                    HealPercentField("SP pet", spPetText, { spPetText = it }, Modifier.weight(1f))
                }
                TextButton(onClick = {
                    hpCharText = "40"; spCharText = "0"; hpPetText = "40"; spPetText = "0"
                    furnace = FurnaceConfig()   // reset lo ve mac dinh: 3 tab on, xoa config List
                }) { Text("Mặc định") }
                HorizontalDivider(Modifier.padding(vertical = 4.dp))
                Text("Soi lò (mua item theo list):", style = MaterialTheme.typography.bodySmall)
                FURNACE_TABS.forEach { tab ->
                    val t = furnace.tab(tab.first)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Switch(checked = t.on, onCheckedChange = {
                            furnace = furnace.withTab(tab.first, t.copy(on = it))
                        })
                        Spacer(Modifier.width(6.dp))
                        Text(tab.third, modifier = Modifier.weight(1f), maxLines = 1)
                        TextButton(onClick = { pickerTab = tab }) {
                            Text("📋 List (${t.items.size})", maxLines = 1)
                        }
                    }
                }
                // --- VAN TIEU: tick bat + nut List chon rieng pet nao duoc di ---
                // Chuyen tu Cai dat nang cao ve day: van tieu CO EXP nen user muon don exp cho
                // vai con thay vi dan deu ca nha tro.
                Spacer(Modifier.height(8.dp))
                HorizontalDivider()
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = vantieu.on,
                        onCheckedChange = { vantieu = vantieu.copy(on = it) })
                    Text("Vận tiêu", modifier = Modifier.weight(1f), maxLines = 1)
                    TextButton(onClick = { showVantieuPets = true }) {
                        Text(if (vantieu.pets.isEmpty()) "📋 List (tất cả)"
                             else "📋 List (${vantieu.pets.size})", maxLines = 1)
                    }
                }
                if (onApplyToAll != null) {
                    OutlinedButton(
                        onClick = {
                            val count = onApplyToAll(currentHeal(), furnace, vantieu.on)
                            applyMessage = "Đã áp dụng cho $count acc"
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Áp dụng cho tất cả acc") }
                    if (applyMessage.isNotBlank()) {
                        Spacer(Modifier.height(6.dp))
                        Text(applyMessage, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = { onSave(currentHeal(), furnace, vantieu) }) { Text("Lưu") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Hủy") }
        },
    )

    if (showVantieuPets) {
        // Chon rieng pet nao duoc di VAN TIEU. Tick theo PET ID (index nha tro xe dich khi
        // them/bot pet). KHONG tick con nao = dung TAT CA (mac dinh, y het hanh vi cu).
        // Pet MOI (chua co trong list da luu) mac dinh KHONG tick.
        val chon = remember(vantieu) { mutableStateListOf<Int>().also { it.addAll(vantieu.pets) } }
        AlertDialog(
            onDismissRequest = { showVantieuPets = false },
            title = { Text("Pet vận tiêu") },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    if (innPets.isEmpty()) {
                        Text("Chưa biết pet trong nhà trọ của acc này. " +
                             "List pet do server gửi lúc login. Chạy acc một lần rồi mở lại là " +
                             "có, sau đó chỉnh được cả khi acc đang tắt.")
                    } else {
                        Text("Không tick con nào = dùng TẤT CẢ (như cũ).",
                            style = MaterialTheme.typography.bodySmall)
                        Spacer(Modifier.height(6.dp))
                        innPets.forEach { (pid, ten) ->
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Checkbox(
                                    checked = chon.contains(pid),
                                    onCheckedChange = {
                                        if (it) { if (!chon.contains(pid)) chon.add(pid) }
                                        else chon.remove(pid)
                                    },
                                )
                                Text(ten, maxLines = 1)
                            }
                        }
                    }
                }
            },
            confirmButton = {
                Button(onClick = {
                    // Tick HET => luu RONG: "tat ca" va "khong con nao" cho ket qua giong nhau;
                    // luu rong thi them pet ve sau khong bi ket vao dien "tick le" ngoai y muon.
                    vantieu = vantieu.copy(
                        pets = if (innPets.isNotEmpty() && chon.size == innPets.size) emptyList()
                               else chon.sorted())
                    showVantieuPets = false
                }) { Text("Lưu") }
            },
            dismissButton = {
                TextButton(onClick = { showVantieuPets = false }) { Text("Hủy") }
            },
        )
    }

    val pt = pickerTab
    if (pt != null) {
        FurnacePickerDialog(
            poolName = pt.second,
            title = pt.third,
            initialItems = furnace.tab(pt.first).items,
            onDismiss = { pickerTab = null },
            onSave = { items ->
                val old = furnace.tab(pt.first)
                furnace = furnace.withTab(pt.first, old.copy(items = items))
                pickerTab = null
            },
        )
    }
}

/** 1 cuon goi vo tuong trong pet_scrolls.json. vkcd = tuong co vu khi chuyen dung. */
data class PetScroll(
    val tid: String, val name: String, val npc: String, val vkcd: Boolean,
    val lv: Int = 0, val rare: String = "", val extra: List<String> = emptyList(),
) {
    /** "ten cuon — ten tuong · Lv### · hang hiem" (+ ★ neu mac dinh giu).
     *  Hien Lv/hang de user tu quyet: khong truong nao trong data phan loai duoc xin/rac. */
    fun label(): String {
        val extra = listOf(
            if (npc.isNotEmpty() && !name.contains(npc)) npc else "",
            if (lv > 0) "Lv$lv" else "",
            rare,
        ).filter { it.isNotEmpty() }
        val nm = if (extra.isEmpty()) name else "$name — " + extra.joinToString(" · ")
        return if (vkcd) "$nm ★" else nm
    }
}

/** Doc pet_scrolls.json tu assets -> list TAT CA cuon goi vo tuong (cache).
 *  Sinh boi tools/crack_pet_scrolls.py. */
private var _petScrollsCache: List<PetScroll>? = null

fun loadPetScrolls(context: android.content.Context): List<PetScroll> {
    if (_petScrollsCache == null) {
        _petScrollsCache = try {
            val bytes = context.assets.open("train_bot_data/pet_scrolls.json").readBytes()
            val root = JSONObject(String(bytes, Charsets.UTF_8))
            val out = ArrayList<PetScroll>()
            for (tid in root.keys()) {
                val o = root.getJSONObject(tid)
                out.add(PetScroll(tid, o.optString("name", ""), o.optString("npc", ""),
                                  o.optBoolean("vkcd", false),
                                  o.optInt("lv", 0), o.optString("rare", ""),
                                  o.optJSONArray("extra")?.let { arr ->
                                      (0 until arr.length()).map { arr.optString(it) }
                                  } ?: emptyList()))
            }
            out
        } catch (e: Exception) {
            emptyList()
        }
    }
    return _petScrollsCache ?: emptyList()
}

/* ---- Dong bo LIST PHAN GIAI <-> SOI LO (mirror gui.py, chi chay luc an Luu) --------------
 * Hai cau hinh de da nhau: lo "tu mua" K.Toa/Me khi tui trong -> phan giai xoa di -> vong lo
 * sau lai mua. Engine chi mua khi tui CHUA CO nen vong dot tien nay LAP VINH VIEN.
 * PHAM VI: config lo theo TUNG ACCOUNT, list phan giai theo PARTY -> phai quet MOI account. */
private val FURNACE_SCROLL_TABS = mapOf("vo_tuong" to "Vo Tuong", "chuyen_sinh" to "Chuyen Sinh")

/** {tid mon do -> tid cuon so huu}, gom ca chinh cuon lan K.Toa/T.Tinh/Me cua no. */
fun scrollOwnerMap(context: android.content.Context): Map<String, String> {
    val out = HashMap<String, String>()
    for (sc in loadPetScrolls(context)) {
        out[sc.tid] = sc.tid
        for (e in sc.extra) out.putIfAbsent(e, sc.tid)
    }
    return out
}

/** Cuon vua chuyen sang PHAN GIAI -> dat "skip" cho Bi Cap + K.Toa/T.Tinh/Me cua no. */
fun furnaceWithScrollsSkipped(
    context: android.content.Context,
    furnace: FurnaceConfig,
    droppedScrolls: Set<String>,
): Pair<FurnaceConfig, Int> {
    if (droppedScrolls.isEmpty()) return furnace to 0
    val byTid = loadPetScrolls(context).associateBy { it.tid }
    val want = HashSet<String>()
    for (t in droppedScrolls) {
        want.add(t)
        byTid[t]?.extra?.let { want.addAll(it) }
    }
    var out = furnace
    var n = 0
    for ((tabKey, poolName) in FURNACE_SCROLL_TABS) {
        val pool = loadFurnacePool(context, poolName).map { it.first }.toSet()
        val old = out.tab(tabKey)
        val items = HashMap(old.items)
        for (t in want.intersect(pool)) {
            // "skip" TUONG MINH: item mac dinh Thong bao ma xoa key thi lan sau lai ve notify
            if (items[t] != "skip") { items[t] = "skip"; n++ }
        }
        if (n > 0) out = out.withTab(tabKey, old.copy(items = items))
    }
    return out to n
}

/** Che do HIEU LUC cua 1 item lo: config cua acc de len mac dinh (vkcd -> "notify"). */
private fun furnaceEffectiveMode(
    items: Map<String, String>, tid: String, dfltNotify: Set<String>,
): String {
    val m = items[tid]
    if (m == "skip") return ""
    if (!m.isNullOrEmpty()) return m
    return if (tid in dfltNotify) "notify" else ""
}

/** Tid vua thoat khoi "Bo qua" (skip -> tu mua/thong bao) khi so 2 ban config lo. */
fun furnaceUnskippedTids(
    context: android.content.Context, old: FurnaceConfig, new: FurnaceConfig,
): List<String> {
    val out = ArrayList<String>()
    for ((tabKey, poolName) in FURNACE_SCROLL_TABS) {
        val dflt = loadFurnaceDefaultNotify(context, poolName)
        val o = old.tab(tabKey).items
        val n = new.tab(tabKey).items
        for (tid in loadFurnacePool(context, poolName).map { it.first }) {
            if (furnaceEffectiveMode(o, tid, dflt).isEmpty() &&
                furnaceEffectiveMode(n, tid, dflt).isNotEmpty()
            ) out.add(tid)
        }
    }
    return out
}

/** Cuon vua chuyen sang PHAN GIAI khi so 2 ban scrollModes (mac dinh = vkcd -> giu). */
fun newlyDroppedScrolls(
    context: android.content.Context, old: Map<String, String>, new: Map<String, String>,
): Set<String> {
    val out = HashSet<String>()
    for (sc in loadPetScrolls(context)) {
        val dflt = if (sc.vkcd) "keep" else "drop"
        val before = old[sc.tid] ?: dflt
        val after = new[sc.tid] ?: dflt
        if (after == "drop" && before != "drop") out.add(sc.tid)
    }
    return out
}

/** Item lo chuyen BO QUA -> Tu mua/Thong bao => cuon so huu no ve "Giu lai". */
fun scrollModesAfterUnskip(
    context: android.content.Context,
    modes: Map<String, String>,
    unskipped: List<String>,
): Pair<Map<String, String>, Int> {
    if (unskipped.isEmpty()) return modes to 0
    val owner = scrollOwnerMap(context)
    val byTid = loadPetScrolls(context).associateBy { it.tid }
    val out = HashMap(modes)
    var n = 0
    for (t in unskipped) {
        val sc = owner[t] ?: continue   // mon do khong thuoc cuon nao (vd tab Trang Bi)
        // modes chi luu muc KHAC mac dinh -> mac dinh da la "giu" thi XOA key di
        if (byTid[sc]?.vkcd == true) {
            if (out.remove(sc) == "drop") n++
        } else if (out[sc] != "keep") {
            out[sc] = "keep"; n++
        }
    }
    return out to n
}

/** List cuon vo tuong: bam 1 dong de doi GIU LAI <-> PHAN GIAI (mirror gui.py _open_scroll_list).
 *  modes CHI luu muc DOI KHAC mac dinh (vkcd = giu lai) -> cuon moi cua game tu theo mac dinh. */
@Composable
fun ScrollListDialog(
    modes: Map<String, String>,
    onDismiss: () -> Unit,
    onSave: (Map<String, String>) -> Unit,
) {
    val context = LocalContext.current
    val all = remember { loadPetScrolls(context) }
    val state = remember {
        mutableStateMapOf<String, String>().apply {
            all.forEach { put(it.tid, modes[it.tid] ?: if (it.vkcd) "keep" else "drop") }
        }
    }
    var query by remember { mutableStateOf("") }
    // "Phan giai" len TRUOC de user soat cai se bi MAT truoc tien
    val shown = all.filter { query.isBlank() || it.label().contains(query, ignoreCase = true) }
        .sortedWith(compareBy({ state[it.tid] != "drop" }, { -it.lv }, { it.label() }))

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Cuộn võ tướng (${all.size})") },
        text = {
            Column {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    singleLine = true,
                    label = { Text("Tìm") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(6.dp))
                Text("Bấm 1 dòng để đổi trạng thái.", style = MaterialTheme.typography.bodySmall)
                LazyColumn(modifier = Modifier.heightIn(max = 360.dp)) {
                    items(shown.size) { i ->
                        val sc = shown[i]
                        val drop = state[sc.tid] == "drop"
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.fillMaxWidth()
                                .clickable { state[sc.tid] = if (drop) "keep" else "drop" }
                                .padding(vertical = 6.dp),
                        ) {
                            Text(sc.label(), modifier = Modifier.weight(1f))
                            Text(
                                if (drop) "Phân giải" else "Giữ lại",
                                color = if (drop) androidx.compose.ui.graphics.Color(0xFFAA0000)
                                        else androidx.compose.ui.graphics.Color(0xFF007700),
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = {
                // chi luu phan KHAC mac dinh -> file config gon, va mac dinh sua sau van co hieu luc
                onSave(all.filter { state[it.tid] != (if (it.vkcd) "keep" else "drop") }
                    .associate { it.tid to (state[it.tid] ?: "drop") })
            }) { Text("Lưu") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Hủy") } },
    )
}

/** 1 nguyen lieu donate quan doan trong donate_materials.json. Sinh boi crack_donate_materials.py. */
data class DonateMaterial(val tid: String, val name: String, val kind: Int, val lv: Int) {
    fun label(): String {
        val cat = MAT_KIND_NAME[kind] ?: ""
        val extra = listOf(cat, if (lv > 0) "Lv$lv" else "").filter { it.isNotEmpty() }
        return if (extra.isEmpty()) name else "$name — " + extra.joinToString(" · ")
    }
}
private val MAT_KIND_NAME = mapOf(
    24 to "Sành", 25 to "Gỗ", 26 to "Vỏ", 27 to "Xương", 28 to "Ngọc Sa", 29 to "Đá quý",
    30 to "Da", 31 to "Vải", 32 to "Giấy", 33 to "Trúc", 34 to "Thảo mộc", 35 to "Hạt Đá",
    36 to "Băng", 40 to "Kim Sa", 41 to "Ngân Phấn", 42 to "Bột Đồng", 43 to "Thiết",
    44 to "Thiếc", 45 to "Tử Tinh", 46 to "Hồng Tinh")
private var _donateMaterialsCache: List<DonateMaterial>? = null

fun loadDonateMaterials(context: android.content.Context): List<DonateMaterial> {
    if (_donateMaterialsCache == null) {
        _donateMaterialsCache = try {
            val bytes = context.assets.open("train_bot_data/donate_materials.json").readBytes()
            val root = JSONObject(String(bytes, Charsets.UTF_8)).getJSONObject("items")
            val out = ArrayList<DonateMaterial>()
            for (tid in root.keys()) {
                val o = root.getJSONObject(tid)
                out.add(DonateMaterial(tid, o.optString("name", ""), o.optInt("kind", 0), o.optInt("lv", 0)))
            }
            out
        } catch (e: Exception) {
            emptyList()
        }
    }
    return _donateMaterialsCache ?: emptyList()
}

@Composable
fun EventExchangeDialog(
    picked: List<String>,
    onDismiss: () -> Unit,
    onSave: (List<String>) -> Unit,
) {
    // Danh sach do PYTHON tinh (bot/event_exchange.py: options_from_cache) tu file cache bot ghi
    // luc dang nhap -> KHONG chep tay sang Kotlin, khong the lech voi ban PC.
    val rows = remember {
        try {
            com.chaquo.python.Python.getInstance()
                .getModule("train_bot.event_exchange")
                .callAttr("options_from_cache")
                .asList()
                .mapNotNull { line ->
                    val t = line.toString().split("\t", limit = 2)
                    if (t.size == 2) t[0] to t[1] else null
                }
        } catch (e: Exception) {
            emptyList()
        }
    }
    val state = remember { mutableStateMapOf<String, Boolean>().apply { picked.forEach { put(it, true) } } }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Quà event (${rows.size})") },
        text = {
            Column {
                if (rows.isEmpty()) {
                    Text(
                        "Chưa có dữ liệu đổi thưởng.\n\nDanh sách này do BOT ghi lại khi đăng " +
                            "nhập (server gửi). Chạy bot 1 lần rồi mở lại.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                } else {
                    Text(
                        "Chỉ hiện QUÀ CUỐI. Bot tự truy ngược chuỗi nguyên liệu và CHỈ đổi khi đủ " +
                            "toàn bộ chuỗi (tránh đổi ra nguyên liệu trung gian chiếm túi).",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    LazyColumn(modifier = Modifier.heightIn(max = 360.dp)) {
                        items(rows.size) { i ->
                            val (key, label) = rows[i]
                            val on = state[key] == true
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.fillMaxWidth()
                                    .clickable { state[key] = !on }
                                    .padding(vertical = 6.dp),
                            ) {
                                Checkbox(checked = on, onCheckedChange = { state[key] = it })
                                Text(label, modifier = Modifier.weight(1f))
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = { onSave(state.filterValues { it }.keys.toList()) }) { Text("Lưu") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Hủy") } },
    )
}

@Composable
fun MaterialListDialog(
    modes: Map<String, String>,
    onDismiss: () -> Unit,
    onSave: (Map<String, String>) -> Unit,
) {
    val context = LocalContext.current
    val all = remember { loadDonateMaterials(context) }
    val state = remember {
        mutableStateMapOf<String, String>().apply {
            all.forEach { put(it.tid, if (modes[it.tid] == "keep") "keep" else "donate") }
        }
    }
    var query by remember { mutableStateOf("") }
    // "Dong gop" (se MAT) len TRUOC, Lv cao len tren de soat nguyen lieu quy
    val shown = all.filter { query.isBlank() || it.label().contains(query, ignoreCase = true) }
        .sortedWith(compareBy({ state[it.tid] != "donate" }, { -it.lv }, { it.label() }))
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Nguyên liệu (${all.size})") },
        text = {
            Column {
                OutlinedTextField(
                    value = query, onValueChange = { query = it }, singleLine = true,
                    label = { Text("Tìm") }, modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(6.dp))
                Text("Bấm 1 dòng để đổi trạng thái. Mặc định ĐÓNG GÓP hết.",
                     style = MaterialTheme.typography.bodySmall)
                LazyColumn(modifier = Modifier.heightIn(max = 360.dp)) {
                    items(shown.size) { i ->
                        val m = shown[i]
                        val donate = state[m.tid] != "keep"
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.fillMaxWidth()
                                .clickable { state[m.tid] = if (donate) "keep" else "donate" }
                                .padding(vertical = 6.dp),
                        ) {
                            Text(m.label(), modifier = Modifier.weight(1f))
                            Text(
                                if (donate) "Đóng góp" else "Giữ lại",
                                color = if (donate) androidx.compose.ui.graphics.Color(0xFFAA0000)
                                        else androidx.compose.ui.graphics.Color(0xFF007700),
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = {
                // chi luu muc GIU (khac mac dinh donate) -> nguyen lieu moi tu donate theo mac dinh
                onSave(all.filter { state[it.tid] == "keep" }.associate { it.tid to "keep" })
            }) { Text("Lưu") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Hủy") } },
    )
}

/** Doc furnace_default_notify.json tu assets -> {poolName: set(tid_hex)} (cache).
 *  Item cua vo tuong CO VU KHI CHUYEN DUNG -> mac dinh "Thong bao" thay vi "Bo qua".
 *  Sinh boi tools/crack_furnace_notify.py. */
private var _furnaceNotifyCache: Map<String, Set<String>>? = null

fun loadFurnaceDefaultNotify(context: android.content.Context, poolName: String): Set<String> {
    if (_furnaceNotifyCache == null) {
        _furnaceNotifyCache = try {
            val bytes = context.assets.open("train_bot_data/furnace_default_notify.json").readBytes()
            val root = JSONObject(String(bytes, Charsets.UTF_8))
            val out = LinkedHashMap<String, Set<String>>()
            for (k in root.keys()) {
                val o = root.getJSONObject(k)
                val s = LinkedHashSet<String>()
                for (tid in o.keys()) s.add(tid)
                out[k] = s
            }
            out
        } catch (e: Exception) {
            emptyMap()
        }
    }
    return _furnaceNotifyCache?.get(poolName) ?: emptySet()
}

/** Doc furnace_pool.json tu assets -> {poolName: [(tid_hex, ten)]} (cache). */
private var _furnacePoolCache: Map<String, List<Pair<String, String>>>? = null

fun loadFurnacePool(context: android.content.Context, poolName: String): List<Pair<String, String>> {
    if (_furnacePoolCache == null) {
        try {
            val bytes = context.assets.open("train_bot_data/furnace_pool.json").readBytes()
            val root = JSONObject(String(bytes, Charsets.UTF_8))
            val out = LinkedHashMap<String, List<Pair<String, String>>>()
            for (k in root.keys()) {
                val o = root.getJSONObject(k)
                val lst = ArrayList<Pair<String, String>>()
                for (tid in o.keys()) lst.add(tid to o.optString(tid, tid))
                out[k] = lst
            }
            _furnacePoolCache = out
        } catch (e: Exception) {
            _furnacePoolCache = emptyMap()
        }
    }
    return _furnacePoolCache?.get(poolName) ?: emptyList()
}

/** Chi so trang bi (equip_stats.json): {tid_hex: EquipStat}. Value dang goc-100 (bonus that = val-100). */
data class EquipStat(val lv: Int, val q: Int, val e: Int, val ev: Int, val fit: Int, val attrs: List<Pair<Int, Int>>)
private var _equipStatCache: Map<String, EquipStat>? = null
private val EQ_ATTR = mapOf(207 to "hp", 208 to "sp", 210 to "atk", 211 to "def", 212 to "int",
    214 to "agi", 218 to "tc", 219 to "nl")
private val EQ_ELEM = mapOf(1 to "địa", 2 to "thủy", 3 to "hỏa", 4 to "phong", 5 to "tâm", 7 to "quang", 8 to "ám")
private val EQ_QUAL = mapOf(0 to "trắng", 1 to "xanh", 2 to "lam", 3 to "tím", 4 to "đỏ")
private val EQ_FIT = mapOf(1 to "Đầu", 2 to "Thân", 3 to "Vũ khí", 4 to "Tay", 5 to "Chân", 6 to "Đặc biệt", 100 to "Choàng")

fun loadEquipStats(context: android.content.Context): Map<String, EquipStat> {
    if (_equipStatCache == null) {
        try {
            val bytes = context.assets.open("train_bot_data/equip_stats.json").readBytes()
            val root = JSONObject(String(bytes, Charsets.UTF_8))
            val out = HashMap<String, EquipStat>()
            for (k in root.keys()) {
                val o = root.getJSONObject(k)
                val a = o.optJSONArray("a")
                val attrs = ArrayList<Pair<Int, Int>>()
                if (a != null) for (i in 0 until a.length()) {
                    val pr = a.getJSONArray(i); attrs.add(pr.getInt(0) to pr.getInt(1))
                }
                out[k] = EquipStat(o.optInt("lv"), o.optInt("q"), o.optInt("e"), o.optInt("ev", 100), o.optInt("fit"), attrs)
            }
            _equipStatCache = out
        } catch (e: Exception) { _equipStatCache = emptyMap() }
    }
    return _equipStatCache ?: emptyMap()
}

private fun sgn(x: Int) = (if (x >= 0) "+" else "") + x

fun equipMaxBonus(s: EquipStat?): Int = s?.attrs?.maxOfOrNull { it.second - 100 } ?: -999

fun equipDisplay(s: EquipStat?, name: String): String {
    if (s == null) return name
    val sb = StringBuilder(name)
    if (s.fit != 0) sb.append("_").append(EQ_FIT[s.fit] ?: "?")   // vi tri: Dau/Than/Vu khi/Tay/Chan
    sb.append("_Lv").append(s.lv)
    for ((k, v) in s.attrs) sb.append("_").append(EQ_ATTR[k] ?: "#$k").append(" ").append(sgn(v - 100))
    if (s.e != 0) sb.append("_").append(EQ_ELEM[s.e] ?: "?").append(" ").append(sgn(s.ev - 100))
    sb.append("_").append(EQ_QUAL[s.q] ?: "?")
    return sb.toString()
}

/** Cau chu thong bao lo - giong ban PC (_furnace_notify_line trong gui.py).
 *  Rieng tab trang_bi hien TEN DAI kem chi so (equipDisplay) de quyet dinh mua hay khong. */
private fun furnaceNotifyLine(context: android.content.Context, it: Map<String, String>): String {
    val u = it["user"] ?: "?"
    val tab = it["tab"] ?: ""
    var nm = (it["name"] ?: "?").trim()
    // ITEM LA = id khong co trong furnace_pool.json (game update them item moi) - engine danh dau
    // "new"; phai neu ro chu khong de nhin y het item thuong.
    val nw = if (it["new"]?.lowercase() in listOf("true", "1")) " ⚠ ITEM LẠ (ngoài danh sách đã biết)" else ""
    return when (tab) {
        "trang_bi" -> {
            val tid = it["id"]?.toIntOrNull()
            if (tid != null) {
                nm = equipDisplay(loadEquipStats(context)[String.format("0x%04x", tid)], nm)
            }
            "$u soi lò trang bị thường có \"$nm\" - trong túi đang có ${it["bag"] ?: 0} món$nw"
        }
        "vo_tuong" -> "$u soi lò võ tướng thường có \"$nm\"$nw"
        "chuyen_sinh" -> "$u soi lò chuyển sinh thường có \"$nm\"$nw"
        else -> "$u: lò có \"$nm\"$nw"
    }
}

@Composable
fun FurnaceNotifyDialog(
    items: List<Map<String, String>>,
    onDismiss: () -> Unit,
    onBuy: (String, Int) -> Boolean,
    onSkip: (String, Int) -> Boolean,
    onLegionSkip: (String) -> Boolean = { _ -> false },
    onBaDauSkip: (String) -> Boolean = { _ -> false },
    onDiemDuSkip: (String) -> Boolean = { _ -> false },
    onRefresh: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Chú ý") },
        text = {
            if (items.isEmpty()) {
                Text("(không có thông báo)")
            } else {
                LazyColumn(modifier = Modifier.fillMaxWidth().heightIn(max = 380.dp)) {
                    items(items, key = { (it["user"] ?: "") + (it["kind"] ?: "") + (it["id"] ?: "") }) { it0 ->
                        val u = it0["user"] ?: return@items
                        if (it0["kind"] == "ba_dau") {
                            Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                                Text("$u: Ba Đậu Yêu sẽ hết hạn vào lúc ${it0["luc"]}",
                                     style = MaterialTheme.typography.bodySmall,
                                     fontWeight = FontWeight.Bold,
                                     color = StatusConnecting)
                                Row(horizontalArrangement = Arrangement.End,
                                    modifier = Modifier.fillMaxWidth()) {
                                    TextButton(onClick = {
                                        scope.launch {
                                            withContext(Dispatchers.IO) { onBaDauSkip(u) }
                                            onRefresh()
                                        }
                                    }) { Text("Bỏ qua") }
                                }
                                HorizontalDivider()
                            }
                            return@items
                        }
                        if (it0["kind"] == "diem_du") {
                            Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                                Text("$u còn dư ${it0["diem"]} điểm chưa dùng — bảng tự cộng đã " +
                                     "duyệt hết mà vẫn thừa (mở nút Point để thêm dòng)",
                                     style = MaterialTheme.typography.bodySmall)
                                Row(horizontalArrangement = Arrangement.End,
                                    modifier = Modifier.fillMaxWidth()) {
                                    TextButton(onClick = {
                                        scope.launch {
                                            withContext(Dispatchers.IO) { onDiemDuSkip(u) }
                                            onRefresh()
                                        }
                                    }) { Text("Bỏ qua") }
                                }
                                HorizontalDivider()
                            }
                            return@items
                        }
                        if (it0["kind"] == "legion") {
                            Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                                Text("$u KHÔNG có quân đoàn — mất phần donate quân đoàn, " +
                                     "boss quân đoàn và các quyền lợi đi kèm",
                                     style = MaterialTheme.typography.bodySmall)
                                Row(horizontalArrangement = Arrangement.End,
                                    modifier = Modifier.fillMaxWidth()) {
                                    TextButton(onClick = {
                                        scope.launch {
                                            withContext(Dispatchers.IO) { onLegionSkip(u) }
                                            onRefresh()
                                        }
                                    }) { Text("Bỏ qua") }
                                }
                                HorizontalDivider()
                            }
                            return@items
                        }
                        val tid = it0["id"]?.toIntOrNull() ?: return@items
                        Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                            Text(furnaceNotifyLine(context, it0),
                                style = MaterialTheme.typography.bodySmall)
                            Row(horizontalArrangement = Arrangement.End,
                                modifier = Modifier.fillMaxWidth()) {
                                TextButton(onClick = {
                                    scope.launch {
                                        withContext(Dispatchers.IO) { onSkip(u, tid) }
                                        onRefresh()
                                    }
                                }) { Text("Bỏ qua") }
                                TextButton(onClick = {
                                    scope.launch {
                                        val ok = withContext(Dispatchers.IO) { onBuy(u, tid) }
                                        onRefresh()
                                        android.widget.Toast.makeText(context,
                                            if (ok) "Đã mua" else "Mua không thành công (acc tắt / hết chips / lò đã đổi)",
                                            android.widget.Toast.LENGTH_SHORT).show()
                                    }
                                }) { Text("Mua") }
                            }
                            HorizontalDivider()
                        }
                    }
                }
            }
        },
        confirmButton = {
            Row {
                TextButton(onClick = onDismiss) { Text("Đóng") }
                // "Bo qua tat ca": bo qua MOI dong dang hien roi dong bang (mirror gui.py).
                TextButton(onClick = {
                    val all = items.toList()
                    scope.launch {
                        withContext(Dispatchers.IO) {
                            for (row in all) {
                                val u = row["user"] ?: continue
                                val tid = row["id"]?.toIntOrNull() ?: continue
                                try {
                                    onSkip(u, tid)
                                } catch (e: Exception) {
                                    android.util.Log.w("tsbot", "bo qua tat ca: loi 1 dong", e)
                                }
                            }
                        }
                        onRefresh()
                        onDismiss()
                    }
                }) { Text("Bỏ qua tất cả") }
            }
        },
    )
}

@Composable
fun FurnacePickerDialog(
    poolName: String,
    title: String,
    initialItems: Map<String, String>,
    onDismiss: () -> Unit,
    onSave: (Map<String, String>) -> Unit,
) {
    val context = LocalContext.current
    val pool = remember(poolName) { loadFurnacePool(context, poolName) }
    val dfltNotify = remember(poolName) { loadFurnaceDefaultNotify(context, poolName) }
    val modes = remember(initialItems) { mutableStateMapOf<String, String>().apply { putAll(initialItems) } }
    // Config cua acc DE LEN mac dinh. Chua chon gi -> "Thong bao" neu la item cua vo tuong CO
    // VU KHI CHUYEN DUNG, con lai -> "Bo qua".
    val modeOf = { tid: String ->
        val m = modes[tid]
        when {
            m == "skip" -> ""                                   // bo qua TUONG MINH
            m != null -> m
            dfltNotify.contains(tid) -> "notify"                // mac dinh cho item vo tuong co vkcd
            else -> ""
        }
    }
    var query by remember { mutableStateOf("") }
    val rank = { m: String? -> when (m) { "auto" -> 0; "notify" -> 1; else -> 2 } }
    // Sort theo che do luc MO dialog (snapshot) -> doi che do KHONG re-sort live (item khong nhay cho).
    // Chi sort lai khi tim/mo lai ("luc luu moi can sort" -> lan mo sau da sap xep san).
    val sortModes = remember { modes.toMap() }
    val modeOfSort = { tid: String ->
        val m = sortModes[tid]
        when { m == "skip" -> ""; m != null -> m; dfltNotify.contains(tid) -> "notify"; else -> "" }
    }
    // Tab Trang Bi: hien ten + Lv + chi so + pham, sort theo CHI SO (+bonus) giam dan.
    val isEquip = poolName == "Trang Bi"
    val equipStats = remember(poolName) { if (isEquip) loadEquipStats(context) else emptyMap() }
    val disp = { tid: String, name: String -> if (isEquip) equipDisplay(equipStats[tid], name) else name }
    val filtered = remember(query, pool) {
        val kw = query.trim().lowercase()
        val f = pool.filter { kw.isEmpty() || disp(it.first, it.second).lowercase().contains(kw) || it.first.contains(kw) }
        if (isEquip) f.sortedWith(compareBy({ rank(modeOfSort(it.first)) }, { -equipMaxBonus(equipStats[it.first]) }, { it.second }))
        else f.sortedWith(compareBy({ rank(modeOfSort(it.first)) }, { it.second }))
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Lò $title", maxLines = 1) },
        text = {
            Column {
                OutlinedTextField(query, { query = it }, label = { Text("Tìm theo tên") },
                    singleLine = true, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(6.dp))
                LazyColumn(modifier = Modifier.fillMaxWidth().heightIn(max = 380.dp)) {
                    items(filtered, key = { it.first }) { (tid, name) ->
                        val m = modeOf(tid)
                        Row(verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.fillMaxWidth().padding(vertical = 1.dp)) {
                            Text(disp(tid, name), modifier = Modifier.weight(1f),
                                maxLines = if (isEquip) 2 else 1,
                                style = MaterialTheme.typography.bodySmall)
                            listOf("" to "Bỏ qua", "auto" to "Tự mua", "notify" to "Thông báo").forEach { (mv, lbl) ->
                                val sel = m == mv
                                TextButton(onClick = {
                                    if (mv.isEmpty()) {
                                        // Item MAC DINH thong bao: phai luu "skip" moi tat duoc,
                                        // xoa key la lan sau lai ve mac dinh notify.
                                        if (dfltNotify.contains(tid)) modes[tid] = "skip"
                                        else modes.remove(tid)
                                    } else modes[tid] = mv
                                }, contentPadding = androidx.compose.foundation.layout.PaddingValues(4.dp)) {
                                    Text(lbl, style = MaterialTheme.typography.labelSmall,
                                        color = if (sel) MaterialTheme.colorScheme.primary
                                                else MaterialTheme.colorScheme.onSurfaceVariant,
                                        fontWeight = if (sel) FontWeight.Bold else FontWeight.Normal)
                                }
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = {
                onSave(modes.filterValues { it == "auto" || it == "notify" || it == "skip" }.toMap())
            }) { Text("Lưu") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Hủy") } },
    )
}

@Composable
private fun HealPercentField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    OutlinedTextField(
        value = value,
        onValueChange = { onValueChange(it.filter(Char::isDigit).take(3)) },
        label = { Text(label) },
        suffix = { Text("%") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        modifier = modifier,
    )
}

/** 6 chi so cong diem duoc, DUNG THU TU o tren UI cua client (Logic/Status.lua:399-412):
 *  o 4/5 la Hpx/Spx, o 6 moi la Agi - KHONG lien mach 27..32. Xem KNOWLEDGE.md muc 7o. */
private val PointStats = listOf(
    "int" to "INT", "atk" to "ATK", "def" to "DEF",
    "hpx" to "HPx", "spx" to "SPx", "agi" to "AGI",
)

private data class PointRule(val stat: String, val target: Int)

private fun parsePointRules(json: String): Pair<Int, List<PointRule>> {
    if (json.isBlank()) return 999 to emptyList()
    return try {
        val o = org.json.JSONObject(json)
        val arr = o.optJSONArray("rules")
        val rules = mutableListOf<PointRule>()
        for (i in 0 until (arr?.length() ?: 0)) {
            val r = arr!!.optJSONObject(i) ?: continue
            val t = r.optInt("target", 0)
            if (t > 0) rules.add(PointRule(r.optString("stat", "int"), t))
        }
        o.optInt("reserve", 999) to rules
    } catch (_: Exception) { 999 to emptyList() }
}

private fun buildPointJson(reserve: Int, rules: List<PointRule>): String {
    val arr = org.json.JSONArray()
    rules.forEach { arr.put(org.json.JSONObject().put("stat", it.stat).put("target", it.target)) }
    return org.json.JSONObject().put("reserve", reserve).put("rules", arr).toString()
}

/**
 * DIEM TIEM NANG cua NHAN VAT (khong quan tam pet). Ban Kotlin cua PointDialog ben PC - cung mot
 * luat, cung mot ham core (`point_info` / `add_point` / `apply_point_config`).
 *
 *  1. Bang 6 chi so: GOC (thu ma cong diem tac dong toi) va TONG (da gom trang bi/thu cuoi/the).
 *  2. Cong TAY: dang trong tran -> XEP HANG, het tran bot tu gui.
 *  3. Bang TU CONG: dong dau CO DINH "Point de danh", cac dong sau la muc dich tung chi so,
 *     duyet TU TREN XUONG. Rule chot theo diem GOC.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PointSettingsDialog(
    username: String,
    initialPointJson: String,
    onLoadInfo: () -> String,
    onAddPoint: (String, Int) -> String,
    onDismiss: () -> Unit,
    onSave: (String) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val (initReserve, initRules) = remember(initialPointJson) { parsePointRules(initialPointJson) }
    var reserve by remember { mutableStateOf(initReserve.toString()) }
    val rules = remember { mutableStateListOf<PointRule>().apply { addAll(initRules) } }
    var infoJson by remember { mutableStateOf("") }
    val adds = remember { mutableStateMapOf<String, String>() }

    suspend fun nap() {
        infoJson = withContext(Dispatchers.IO) { onLoadInfo() }
    }
    LaunchedEffect(username) { nap() }

    val info = remember(infoJson) {
        try { if (infoJson.isBlank()) null else org.json.JSONObject(infoJson) } catch (_: Exception) { null }
    }
    val goc = remember(info) {
        val m = mutableMapOf<String, Pair<Int, Int>>()
        val arr = info?.optJSONArray("stats")
        for (i in 0 until (arr?.length() ?: 0)) {
            val st = arr!!.optJSONObject(i) ?: continue
            m[st.optString("key")] = st.optInt("goc") to st.optInt("tong")
        }
        m
    }
    val tuCache = info?.optBoolean("cache") == true

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Point: $username") },
        text = {
            Column(modifier = Modifier.fillMaxWidth().heightIn(max = 460.dp)
                .verticalScroll(rememberScrollState())) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text("Chỉ số", Modifier.weight(1f), style = MaterialTheme.typography.labelMedium)
                    Text("Gốc", Modifier.weight(1f), style = MaterialTheme.typography.labelMedium)
                    Text("Tổng", Modifier.weight(1f), style = MaterialTheme.typography.labelMedium)
                    Text("Cộng", Modifier.weight(1.4f), style = MaterialTheme.typography.labelMedium)
                }
                PointStats.forEach { (key, ten) ->
                    val gt = goc[key]
                    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Text(ten, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                        Text(gt?.first?.toString() ?: "?", Modifier.weight(1f),
                            style = MaterialTheme.typography.bodySmall)
                        Text(gt?.second?.toString() ?: "?", Modifier.weight(1f),
                            style = MaterialTheme.typography.bodySmall)
                        OutlinedTextField(
                            value = adds[key] ?: "0",
                            onValueChange = { adds[key] = it.filter { c -> c.isDigit() } },
                            singleLine = true,
                            modifier = Modifier.weight(1.4f),
                            textStyle = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
                Spacer(Modifier.height(6.dp))
                val left = info?.opt("left")?.toString()?.takeIf { it != "null" } ?: "?"
                Text("Điểm dư: $left", fontWeight = FontWeight.Bold)
                // Acc TAT -> so doc tu cache (chi de XEM). Noi RO keo user bam cong mai khong an.
                Text(
                    if (info == null) "(acc chưa chạy và chưa có số đã lưu)"
                    else if (tuCache) "(acc đang TẮT — số đã lưu, bật acc mới cộng được)"
                    else "(số đọc trực tiếp từ acc đang chạy)",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = { scope.launch { nap() } }) { Text("Đọc lại") }
                    TextButton(onClick = {
                        scope.launch {
                            val cho = mutableListOf<String>()
                            var loi: String? = null
                            withContext(Dispatchers.IO) {
                                for ((key, ten) in PointStats) {
                                    val add = (adds[key] ?: "0").toIntOrNull() ?: 0
                                    if (add <= 0) continue
                                    when (onAddPoint(key, add)) {
                                        "queued" -> { cho.add("$ten +$add"); adds[key] = "0" }
                                        "True" -> adds[key] = "0"
                                        else -> { loi = "Không cộng được $add vào $ten"; break }
                                    }
                                }
                            }
                            if (loi != null) {
                                android.widget.Toast.makeText(context,
                                    "$loi — acc phải đang chạy và còn đủ điểm dư",
                                    android.widget.Toast.LENGTH_LONG).show()
                            } else if (cho.isNotEmpty()) {
                                android.widget.Toast.makeText(context,
                                    "Đang trong trận — đã xếp hàng, đánh xong bot tự cộng: " +
                                        cho.joinToString(", "),
                                    android.widget.Toast.LENGTH_LONG).show()
                            }
                            nap()
                        }
                    }) { Text("Cộng ngay") }
                }

                HorizontalDivider(Modifier.padding(vertical = 6.dp))
                Text("Tự cộng Điểm (duyệt từ trên xuống)", fontWeight = FontWeight.SemiBold)
                Row(Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Text("Point để dành:", Modifier.weight(1.4f),
                        style = MaterialTheme.typography.bodySmall)
                    OutlinedTextField(
                        value = reserve,
                        onValueChange = { reserve = it.filter { c -> c.isDigit() } },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                        textStyle = MaterialTheme.typography.bodySmall,
                    )
                }
                Text("(luôn giữ lại; dư hơn số này mới cộng cho các dòng dưới)",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                rules.forEachIndexed { idx, r ->
                    var mo by remember(idx) { mutableStateOf(false) }
                    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.weight(1f)) {
                            TextButton(onClick = { mo = true }) {
                                Text(PointStats.firstOrNull { it.first == r.stat }?.second ?: r.stat)
                            }
                            DropdownMenu(expanded = mo, onDismissRequest = { mo = false }) {
                                PointStats.forEach { (k, t) ->
                                    DropdownMenuItem(text = { Text(t) }, onClick = {
                                        rules[idx] = r.copy(stat = k); mo = false
                                    })
                                }
                            }
                        }
                        OutlinedTextField(
                            value = r.target.toString(),
                            onValueChange = { v ->
                                rules[idx] = r.copy(target = v.filter { it.isDigit() }.toIntOrNull() ?: 0)
                            },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            textStyle = MaterialTheme.typography.bodySmall,
                        )
                        IconButton(onClick = { rules.removeAt(idx) }) {
                            Icon(Icons.Default.Delete, contentDescription = "Xóa dòng",
                                tint = StatusError, modifier = Modifier.size(18.dp))
                        }
                    }
                }
                TextButton(onClick = { rules.add(PointRule("int", 0)) }) { Text("+ Thêm dòng") }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                onSave(buildPointJson(reserve.toIntOrNull() ?: 999,
                    rules.filter { it.target > 0 }))
            }) { Text("Lưu") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Đóng") } },
    )
}

@Composable
fun SkillSettingsDialog(
    initialBattleJson: String,
    charSkills: List<SkillChoice>,
    petSkills: List<SkillChoice>,
    dangerousNpcNames: () -> List<String>,
    onSaveDangerousNpcNames: (List<String>) -> Unit,
    onDismiss: () -> Unit,
    onSave: (String) -> Unit,
    pets: List<BotForegroundService.PetSkillSet> = emptyList(),
    activePid: Int = 0,
) {
    var charRules by remember(initialBattleJson) {
        mutableStateOf(parseBattleRules(initialBattleJson, "char"))
    }
    // Acc OFFLINE (pets rong): giu editor "Pet" chung cu - luu lai nguyen key "pet".
    var petRules by remember(initialBattleJson) {
        mutableStateOf(parseBattleRules(initialBattleJson, "pet"))
    }
    // Acc ONLINE: TAB rieng tung pet (mirror PC + client MachineBox.fightSettings per npcId).
    // Config "pet" chung cu -> gan cho pet DANG DUNG (activePid), pet khac auto (chot voi user).
    var petTab by remember { mutableStateOf(0) }
    var petRulesMap by remember(initialBattleJson, pets) {
        mutableStateOf(pets.associate { it.pid to parsePetRules(initialBattleJson, it.pid, activePid) })
    }
    // Vai tro pet: 1 vai chi 1 pet -> tick vai o pet nay thi cac pet khac tu nha vai do.
    var petRoles by remember(initialBattleJson) { mutableStateOf(parsePetRoles(initialBattleJson)) }
    var confirmDefault by remember { mutableStateOf(false) }
    var editDangerousNpc by remember { mutableStateOf(false) }
    var dangerousNpcText by remember { mutableStateOf("") }

    fun openDangerousNpcEditor() {
        dangerousNpcText = dangerousNpcNames().joinToString("\n")
        editDangerousNpc = true
    }

    if (confirmDefault) {
        AlertDialog(
            onDismissRequest = { confirmDefault = false },
            title = { Text("Nạp mẫu") },
            text = { Text("Nạp kịch bản skill mặc định và lưu áp dụng ngay?") },
            confirmButton = {
                TextButton(onClick = {
                    confirmDefault = false
                    val nextChar = defaultBattleRules(charSkills)
                    if (pets.isEmpty()) {
                        onSave(battleJson(nextChar, defaultBattleRules(petSkills)))
                    } else {
                        onSave(battleJsonPets(nextChar,
                            pets.associate { it.pid to defaultBattleRules(it.skills) }, petRoles))
                    }
                }) { Text("Đồng ý") }
            },
            dismissButton = {
                TextButton(onClick = { confirmDefault = false }) { Text("Hủy") }
            },
        )
    }

    if (editDangerousNpc) {
        AlertDialog(
            onDismissRequest = { editDangerousNpc = false },
            title = { Text("NPC nguy hiểm") },
            text = {
                Column {
                    Text("Mỗi dòng là một tên NPC, thứ tự trên trước.")
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = dangerousNpcText,
                        onValueChange = { dangerousNpcText = it },
                        minLines = 8,
                        maxLines = 12,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val names = dangerousNpcText
                        .lines()
                        .map { it.trim() }
                        .filter { it.isNotEmpty() }
                        .distinct()
                    onSaveDangerousNpcNames(names)
                    editDangerousNpc = false
                }) { Text("Lưu") }
            },
            dismissButton = {
                TextButton(onClick = { editDangerousNpc = false }) { Text("Hủy") }
            },
        )
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Kịch bản Battle") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
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
                BattleRuleUnitEditor("Char", charRules, charSkills, ::openDangerousNpcEditor) { charRules = it }
                Spacer(Modifier.height(8.dp))
                if (pets.isEmpty()) {
                    BattleRuleUnitEditor("Pet", petRules, petSkills, ::openDangerousNpcEditor) { petRules = it }
                } else {
                    Text("Pet (rule riêng từng pet)", style = MaterialTheme.typography.titleSmall)
                    ScrollableTabRow(selectedTabIndex = petTab, edgePadding = 0.dp) {
                        pets.forEachIndexed { i, ps ->
                            Tab(selected = petTab == i, onClick = { petTab = i },
                                text = { Text(ps.name) })
                        }
                    }
                    Spacer(Modifier.height(4.dp))
                    val cur = pets[petTab]
                    Text("Dùng pet này khi:", style = MaterialTheme.typography.bodySmall)
                    // 4 vai (them "PB don") + nhan dai hon -> mot Row co dinh la TRAN NGANG tren
                    // dien thoai. Xep 2 vai/hang de doc duoc o man hinh hep.
                    PetRoleLabels.chunked(2).forEach { hang ->
                        Row {
                            hang.forEach { (role, label) ->
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Checkbox(
                                        checked = petRoles[role] == cur.pid,
                                        onCheckedChange = { on ->
                                            petRoles = petRoles.toMutableMap().apply {
                                                if (on) put(role, cur.pid) else remove(role)
                                            }
                                        },
                                    )
                                    Text(label, style = MaterialTheme.typography.bodySmall,
                                        maxLines = 2)
                                }
                            }
                        }
                    }
                    Text(
                        "Vai không tick pet nào → giữ nguyên pet đang dùng.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    BattleRuleUnitEditor("", petRulesMap[cur.pid] ?: listOf(BattleRuleUi()),
                        cur.skills, ::openDangerousNpcEditor) {
                        petRulesMap = petRulesMap.toMutableMap().apply { put(cur.pid, it) }
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = {
                if (pets.isEmpty()) onSave(battleJson(charRules, petRules))
                else onSave(battleJsonPets(charRules, petRulesMap, petRoles))
            }) { Text("Lưu") }
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

@Composable
fun PartyAgiDialog(
    party: Party,
    statusMap: Map<String, AccountStatus>,
    privacyMode: Int,
    privacyOrdinals: Map<String, String>,
    onDismiss: () -> Unit,
) {
    val values = party.accounts.flatMap { account ->
        val status = statusMap[account.username]
        buildList {
            status?.charAgi?.let(::add)
            if (!status?.petName.isNullOrBlank()) status?.petAgi?.let(::add)
        }
    }
    val low = values.minOrNull()
    val high = values.maxOrNull()
    val spread = if (low != null && high != null) high - low else null
    val warning = spread != null && spread > 10
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Check AGI - ${party.name}") },
        text = {
            Column(modifier = Modifier.height(360.dp).verticalScroll(rememberScrollState())) {
                Text(
                    when {
                        spread == null -> "Chưa có dữ liệu AGI. Hãy chạy party và chờ login xong."
                        warning -> "Thấp nhất $low · Cao nhất $high · Lệch $spread\n⚠ Lệch AGI quá 10, khó combo"
                        else -> "Thấp nhất $low · Cao nhất $high · Lệch $spread"
                    },
                    color = if (warning) Color(0xFFF59E0B) else MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(Modifier.height(12.dp))
                party.accounts.forEach { account ->
                    val status = statusMap[account.username]
                    val charName = status?.charName?.takeIf { it.isNotBlank() }
                    val displayName = if (charName != null) {
                        maskCharacterName(charName, account.username, privacyMode, privacyOrdinals)
                    } else {
                        maskUsername(account.username, privacyMode, privacyOrdinals)
                    }
                    Text(displayName, fontWeight = FontWeight.Bold)
                    Text("AGI char: ${status?.charAgi ?: "—"}")
                    Text(if (status?.petName.isNullOrBlank()) "Pet đang dùng: —" else
                        "Pet đang dùng: ${status?.petName}  ·  AGI ${status?.petAgi ?: "—"}")
                    Spacer(Modifier.height(10.dp))
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Đóng") } },
    )
}
