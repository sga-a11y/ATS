@echo off
title Capture TS Online - MuMu 12 Cong ty
echo ====================================
echo   Capture packet TCP port 6614 tren MuMu 12 - may cong ty
echo   Device co dinh: 127.0.0.1:7555
echo   Vao pho ban / thao tac trong game -> Ctrl+C de dung + lay file
echo ====================================
echo.

set ADB=adb
where adb >nul 2>&1 || set "ADB=%LOCALAPPDATA%\MuMuPlayer\12.0\shell\adb.exe"
if not exist "%ADB%" set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"

set DEV=127.0.0.1:7555
set OUT=/sdcard/ts_capture_mumu12_congty.pcap
set LOCAL_OUT=%~dp0ts_capture_mumu12_congty.pcap

echo [0] Ket noi + root...
%ADB% connect %DEV%
%ADB% -s %DEV% root
timeout /t 2 /nobreak >nul

echo [1] Xoa file cu (neu co)...
%ADB% -s %DEV% shell "rm -f %OUT%"

echo [2] Bat dau capture port 6614...
echo     Hay thao tac trong game, xong nhan Ctrl+C o day.
echo.
%ADB% -s %DEV% shell "tcpdump -i any -w %OUT% port 6614"

echo.
echo [3] Keo file ve may tinh...
%ADB% -s %DEV% pull %OUT% "%LOCAL_OUT%"
echo.
echo === Xong! File: %LOCAL_OUT% ===
echo     Chay: python analyze_pcap.py "%LOCAL_OUT%"
pause
