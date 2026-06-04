# TS Online Bot - Auto Setup Script
# Chay bang PowerShell: Right-click -> Run with PowerShell

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "    [ERR] $msg" -ForegroundColor Red }

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "   TS Online Bot - Setup Tool" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

# ---- Buoc 1: Kiem tra Python ----
Write-Step "Kiem tra Python..."
try {
    $pyVer = python --version 2>&1
    Write-Ok $pyVer
} catch {
    Write-Err "Chua co Python! Tai tai: https://python.org"
    Start-Process "https://python.org/downloads"
    Read-Host "Sau khi cai xong nhan Enter de tiep tuc"
}

# ---- Buoc 2: Cai mitmproxy ----
Write-Step "Cai mitmproxy..."
pip install mitmproxy --quiet
# Them Scripts vao PATH de dung mitmweb/mitmdump
$pythonScripts = python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
if ($pythonScripts -and ($env:PATH -notlike "*$pythonScripts*")) {
    $env:PATH = "$pythonScripts;$env:PATH"
    Write-Ok "Da them $pythonScripts vao PATH"
}
Write-Ok "mitmproxy da san sang"

# ---- Buoc 3: Ket noi ADB toi MuMu ----
Write-Step "Ket noi ADB toi MuMu Emulator..."

# Tim adb.exe trong thu muc MuMu
$mumuPaths = @(
    "$env:LOCALAPPDATA\MuMuPlayer\12.0\shell\adb.exe",
    "C:\Program Files\MuMuPlayer\12.0\shell\adb.exe",
    "C:\Program Files (x86)\MuMu\emulator\nemu\vmonitor\bin\adb_server.exe",
    "$env:LOCALAPPDATA\Netease\MuMuPlayerGlobal-12.0\shell\adb.exe"
)

$adb = $null
foreach ($p in $mumuPaths) {
    if (Test-Path $p) { $adb = $p; break }
}

if (-not $adb) {
    # Thu dung adb trong PATH
    try {
        adb version | Out-Null
        $adb = "adb"
        Write-Ok "Dung adb trong PATH"
    } catch {
        Write-Err "Khong tim thay ADB. Tim thu cong trong thu muc MuMu cua Anh."
        $adb = Read-Host "Nhap duong dan toi adb.exe (vi du: C:\MuMu\shell\adb.exe)"
    }
}

Write-Ok "ADB: $adb"

# Cac port MuMu pho bien
$mumuPorts = @(7555, 16384, 16416, 5554, 5556)
$connected = $false

foreach ($port in $mumuPorts) {
    Write-Host "    Thu ket noi port $port..." -ForegroundColor Gray
    $result = (& $adb connect "127.0.0.1:$port") | Out-String
    if ($result -match "connected") {
        Write-Ok "Ket noi thanh cong qua port $port"
        $script:adbPort = $port
        $connected = $true
        break
    }
}

if (-not $connected) {
    Write-Err "Khong ket noi duoc MuMu. Kiem tra MuMu dang chay va bat ADB Debug."
    Write-Host "    MuMu -> Settings -> Other -> ADB Debug: ON" -ForegroundColor Yellow
    Read-Host "Bat ADB xong nhan Enter"
    & $adb connect "127.0.0.1:7555"
}

# ---- Buoc 4: Cau hinh proxy tren MuMu ----
Write-Step "Cau hinh proxy tren MuMu (10.0.2.2:8080)..."
& $adb -s "127.0.0.1:$adbPort" shell settings put global http_proxy "10.0.2.2:8080"
& $adb -s "127.0.0.1:$adbPort" shell settings put global https_proxy "10.0.2.2:8080"
Write-Ok "Proxy da set"

# ---- Buoc 5: Cai mitmproxy cert ----
Write-Step "Tao thu muc luu traffic..."
New-Item -ItemType Directory -Force -Path ".\traffic" | Out-Null
New-Item -ItemType Directory -Force -Path ".\certs"   | Out-Null

# Chay mitmdump lan dau de tao cert
Write-Step "Tao mitmproxy certificate..."
$certJob = Start-Job -ScriptBlock { python -m mitmproxy.tools.main --listen-port 18080 }
Start-Sleep -Seconds 4
Stop-Job -Job $certJob -ErrorAction SilentlyContinue
Remove-Job -Job $certJob -ErrorAction SilentlyContinue

$certSrc = "$env:USERPROFILE\.mitmproxy\mitmproxy-ca-cert.cer"
if (Test-Path $certSrc) {
    Copy-Item $certSrc ".\certs\mitmproxy-ca-cert.cer"
    # Push cert len MuMu
    & $adb -s "127.0.0.1:$adbPort" push $certSrc "/sdcard/mitmproxy-ca-cert.cer"
    Write-Ok "Da copy cert len MuMu tai /sdcard/mitmproxy-ca-cert.cer"
    Write-Host ""
    Write-Host "  BUOC MANUAL: Trong MuMu, vao Settings -> Security -> Install Certificate" -ForegroundColor Yellow
    Write-Host "  Chon file '/sdcard/mitmproxy-ca-cert.cer'" -ForegroundColor Yellow
} else {
    Write-Err "Chua tao duoc cert. Thu lai sau."
}

# ---- Buoc 6: Tao script bat traffic ----
Write-Step "Tao script capture traffic..."

$captureScript = @'
import mitmproxy.http
from mitmproxy import ctx
import json, time, os

LOG_FILE = "traffic/traffic_raw.log"
os.makedirs("traffic", exist_ok=True)

class TSOnlineCapture:
    def __init__(self):
        self.count = 0
        ctx.log.info("=== TS Online Traffic Capture Started ===")

    def request(self, flow: mitmproxy.http.HTTPFlow):
        entry = {
            "time": time.time(),
            "type": "REQUEST",
            "method": flow.request.method,
            "url": flow.request.pretty_url,
            "host": flow.request.host,
            "headers": dict(flow.request.headers),
            "body_hex": flow.request.content.hex() if flow.request.content else "",
            "body_text": flow.request.text if flow.request.content else ""
        }
        self._log(entry)

    def response(self, flow: mitmproxy.http.HTTPFlow):
        entry = {
            "time": time.time(),
            "type": "RESPONSE",
            "url": flow.request.pretty_url,
            "status": flow.response.status_code,
            "headers": dict(flow.response.headers),
            "body_hex": flow.response.content.hex() if flow.response.content else "",
            "body_text": flow.response.text if flow.response.content else ""
        }
        self._log(entry)
        self.count += 1
        if self.count % 10 == 0:
            ctx.log.info(f"Captured {self.count} responses so far...")

    def _log(self, entry):
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

addons = [TSOnlineCapture()]
'@

$captureScript | Out-File -FilePath ".\capture.py" -Encoding utf8
Write-Ok "Da tao capture.py"

# ---- Buoc 7: Tao file chay capture ----
@"
@echo off
echo ====================================
echo   TS Online - Bat dau capture traffic
echo ====================================
echo.
echo Hay choi game binh thuong, traffic se tu dong luu vao traffic/traffic_raw.log
echo Nhan Ctrl+C de dung.
echo.
mitmweb --listen-port 8080 -s capture.py
"@ | Out-File -FilePath ".\start_capture.bat" -Encoding ascii

Write-Ok "Da tao start_capture.bat"

# ---- Ket qua ----
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   SETUP HOAN THANH!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "BUOC TIEP THEO:" -ForegroundColor Yellow
Write-Host "1. Trong MuMu: Settings -> Security -> Install Certificate" -ForegroundColor White
Write-Host "   Chon: /sdcard/mitmproxy-ca-cert.cer" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Chay: .\start_capture.bat" -ForegroundColor White
Write-Host ""
Write-Host "3. Mo game TS Online trong MuMu va choi binh thuong" -ForegroundColor White
Write-Host ""
Write-Host "4. Traffic se luu tai: .\traffic\traffic_raw.log" -ForegroundColor White
Write-Host ""
Read-Host "Nhan Enter de thoat"
