@echo off
setlocal EnableExtensions
title Capture TS Online - MuMu 12 Cong ty
echo ====================================
echo   Capture packet all traffic tren MuMu 12 - may cong ty
echo   Device co dinh: 127.0.0.1:16768
echo   Vao pho ban / thao tac trong game -> Ctrl+C de dung + lay file
echo ====================================
echo.

set "ADB="
for %%A in (
  "E:\MuMuPlayerGlobal\nx_main\adb.exe"
  "%LOCALAPPDATA%\MuMuPlayer\12.0\shell\adb.exe"
  "%LOCALAPPDATA%\Netease\MuMuPlayerGlobal-12.0\shell\adb.exe"
  "C:\Program Files\MuMuPlayer\12.0\shell\adb.exe"
  "C:\Program Files\Netease\MuMuPlayerGlobal-12.0\shell\adb.exe"
  "C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe"
  "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
) do (
  if exist "%%~A" (
    set "ADB=%%~A"
    goto adb_found
  )
)
for /f "delims=" %%A in ('where adb 2^>nul') do (
  set "ADB=%%A"
  goto adb_found
)

:adb_found
if not defined ADB (
  echo [ERR] Khong tim thay adb.exe.
  echo       Kiem tra MuMu 12 da cai/chay chua, hoac sua bien ADB trong file nay.
  pause
  exit /b 1
)

set DEV=127.0.0.1:16768
set OUT=/sdcard/ts_capture_mumu12_congty.pcap
set LOCAL_OUT=%~dp0ts_capture_mumu12_congty.pcap

echo [0] ADB: %ADB%
echo [0] Ket noi + root...
"%ADB%" connect %DEV%
"%ADB%" -s %DEV% root
"%ADB%" -s %DEV% wait-for-device
timeout /t 1 /nobreak >nul

echo [1] Xoa file cu (neu co)...
"%ADB%" -s %DEV% shell "rm -f %OUT%"

echo [2] Bat dau capture all traffic (bo qua ADB port 5555)...
echo     Hay thao tac trong game, xong nhan Ctrl+C o day.
echo.
"%ADB%" -s %DEV% shell "tcpdump -i any -w %OUT% not port 5555"

echo.
echo [3] Keo file ve may tinh...
"%ADB%" -s %DEV% pull %OUT% "%LOCAL_OUT%"
echo.
echo === Xong! File: %LOCAL_OUT% ===
echo     Chay: python analyze_pcap.py "%LOCAL_OUT%"
pause
