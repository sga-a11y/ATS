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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.KeyboardType
import androidx.core.content.ContextCompat

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

    fun refresh() {
        parties = partyStore.load()
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
            initialDoDaily = partyBeingEdited.doDaily,
            initialTrainMapKey = partyBeingEdited.trainMapKey,
            initialTrainMobIndex = partyBeingEdited.trainMobIndex,
            onDismiss = { editingParty = null },
            onSave = { edited ->
                // Giu nguyen danh sach account, chi doi ten/server.
                partyStore.updateParty(partyBeingEdited.name, edited.copy(accounts = partyBeingEdited.accounts))
                refresh()
                editingParty = null
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
            onDismiss = { editingAccount = null },
            onSave = { edited ->
                partyStore.updateAccountInParty(partyName, account.username, edited)
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
                    onPick = { info -> onSendCity(info.cityId, info.flag); showCityDialog = false },
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
                            .verticalScroll(rememberScrollState()),
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
fun trainMapOptions(): List<Pair<String, String>> {
    val config = com.chaquo.python.Python.getInstance().getModule("train_bot.config")
    val maps = config.get("TRAIN_MAPS")!!
    return maps.asMap().entries.map { (k, v) ->
        k.toString() to (v.callAttr("get", "name")?.toString() ?: k.toString())
    }
}

/** Doc danh sach diem quai cua 1 map train tu Python de hien dropdown "Quái". Luon co "Bot tu chon"
 * (-1) o dau danh sach. */
fun trainMobOptions(mapKey: String): List<Pair<Int, String>> {
    val config = com.chaquo.python.Python.getInstance().getModule("train_bot.config")
    val maps = config.get("TRAIN_MAPS")!!
    val info = maps.callAttr("get", mapKey) ?: return listOf(-1 to "Bot tự chọn")
    val mobs = info.callAttr("get", "mobs") ?: return listOf(-1 to "Bot tự chọn")
    val list = mutableListOf(-1 to "Bot tự chọn")
    mobs.asList().forEachIndexed { i, pt ->
        val coords = pt.asList()
        list.add(i to "Điểm ${i + 1} (${coords[0]}, ${coords[1]})")
    }
    return list
}

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
    initialDoDaily: Boolean = true,
    initialTrainMapKey: String = "",
    initialTrainMobIndex: Int = -1,
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
    var doDaily by remember { mutableStateOf(initialDoDaily) }
    var trainMapKey by remember { mutableStateOf(initialTrainMapKey.ifEmpty { trainMapOptions().firstOrNull()?.first ?: "" }) }
    var trainMobExpanded by remember { mutableStateOf(false) }
    var trainMobIndex by remember { mutableStateOf(initialTrainMobIndex) }
    var trainMapExpanded by remember { mutableStateOf(false) }

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
                if (selectedMode == RunModes.DIGIOI) {
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = digioiSolo, onCheckedChange = { digioiSolo = it })
                        Text("Chạy SOLO (mỗi account độc lập, không lập party thật)")
                    }
                }
                // "Khong co chu PT" va "Lam nhiem vu hang ngay": MOI mode deu co (mirror PC -
                // gui.py hien 2 checkbox nay cho tat ca train/city/stand/digioi, KHONG rieng
                // Di Gioi), CHI an "Khong co chu PT" khi dang o Di Gioi + SOLO (khong lap party
                // that -> "chu PT" vo nghia, mirror _update_no_leader_visibility ben PC).
                Spacer(Modifier.height(8.dp))
                if (!(selectedMode == RunModes.DIGIOI && digioiSolo)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = noLeader, onCheckedChange = { noLeader = it })
                        Text("Không có chủ PT (member tự đứng, chờ leader ngoài/tay mời)")
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = doDaily, onCheckedChange = { doDaily = it })
                    Text("Làm nhiệm vụ hàng ngày")
                }
                if (selectedMode == RunModes.TRAIN) {
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
                            mapOptions.forEach { (key, mapName) ->
                                DropdownMenuItem(text = { Text(mapName) }, onClick = {
                                    trainMapKey = key; trainMobIndex = -1; trainMapExpanded = false
                                })
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
                        onSave(Party(name, selectedKey, selectedMode, selectedCity, digioiSolo, noLeader, doDaily, trainMapKey, trainMobIndex))
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

@Composable
fun AddAccountDialog(
    onDismiss: () -> Unit,
    onSave: (Account) -> Unit,
    title: String = "Thêm tài khoản",
    initialUsername: String = "",
    initialPassword: String = "",
) {
    var username by remember { mutableStateOf(initialUsername) }
    var password by remember { mutableStateOf(initialPassword) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column {
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
                        onSave(Account(username, password))
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
    onPick: (Cities.Info) -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Đổi thành (teleport)") },
        text = {
            LazyColumn(modifier = Modifier.height(380.dp)) {
                items(Cities.ALL.values.toList()) { info ->
                    TextButton(
                        onClick = { onPick(info) },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text(info.label) }
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
