package com.tsbot.android

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.IBinder
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
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
            MaterialTheme {
                Surface {
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

    val service = boundServiceProvider()
    val statusMap by (service?.status?.collectAsState() ?: remember { mutableStateOf(emptyMap()) })

    fun refresh() {
        parties = partyStore.load()
    }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("TS Bot") })
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { showAddPartyDialog = true }) {
                Text("+")
            }
        },
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize().padding(12.dp)) {
            if (parties.isEmpty()) {
                Text("Chưa có party nào")
                Spacer(Modifier.height(12.dp))
                Button(onClick = { showAddPartyDialog = true }) {
                    Text("Tạo party")
                }
            } else {
                LazyColumn {
                    items(parties, key = { it.name }) { party ->
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
                                refresh()
                            },
                            onStart = { account ->
                                val info = Servers.ALL[party.serverKey]
                                if (info != null) {
                                    service?.startAccount(account, info.ip, info.serverId)
                                }
                            },
                            onStop = { username -> service?.stopAccount(username) },
                        )
                        Spacer(Modifier.height(8.dp))
                    }
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
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column {
                    Text(party.name, style = MaterialTheme.typography.titleMedium)
                    Text(Servers.ALL[party.serverKey]?.label ?: party.serverKey)
                }
                Row {
                    IconButton(onClick = onAddAccount) { Text("+") }
                    IconButton(onClick = onEditParty) { Text("✎") }
                    IconButton(onClick = onRemoveParty) { Text("✕") }
                }
            }

            if (party.accounts.isEmpty()) {
                Text("Chưa có tài khoản - bấm + để thêm")
            } else {
                party.accounts.forEach { account ->
                    Spacer(Modifier.height(6.dp))
                    AccountRow(
                        account = account,
                        status = statusMap[account.username] ?: AccountStatus(),
                        onStart = { onStart(account) },
                        onStop = { onStop(account.username) },
                        onEdit = { onEditAccount(account) },
                        onDelete = { onRemoveAccount(account.username) },
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
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(account.username, style = MaterialTheme.typography.bodyLarge)
                Row {
                    IconButton(onClick = onEdit) { Text("✎") }
                    IconButton(onClick = onDelete) { Text("✕") }
                }
            }

            val hpSp = if (status.hp != null && status.sp != null) {
                "HP ${status.hp}/${status.hpMax ?: "?"}  SP ${status.sp}/${status.spMax ?: "?"}"
            } else null

            Text("Trạng thái: ${status.state}")
            if (hpSp != null) Text(hpSp)
            if (status.message.isNotBlank()) Text(status.message)

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                TextButton(onClick = onStart) { Text("Start") }
                Spacer(Modifier.width(8.dp))
                TextButton(onClick = onStop) { Text("Stop") }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddPartyDialog(
    onDismiss: () -> Unit,
    onSave: (Party) -> Unit,
    title: String = "Tạo party",
    initialName: String = "",
    initialServerKey: String = Servers.ALL.keys.first(),
) {
    var name by remember { mutableStateOf(initialName) }
    var expanded by remember { mutableStateOf(false) }
    var selectedKey by remember { mutableStateOf(initialServerKey) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column {
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
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (name.isNotBlank()) {
                        onSave(Party(name, selectedKey))
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
