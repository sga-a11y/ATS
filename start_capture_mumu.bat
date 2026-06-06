@echo off
title Capture TS Online - MuMu
echo ====================================
echo   Capture packet TCP port 6614 tren MuMu
echo   Dung skill trong game -> Ctrl+C de dung + lay file
echo ====================================
echo.

set ADB=C:\LDPlayer\LDPlayer9\adb.exe
set DEV=127.0.0.1:7555
set OUT=/sdcard/ts_capture.pcap

echo [0] Ket noi + root...
%ADB% connect %DEV%
%ADB% -s %DEV% root
timeout /t 2 /nobreak >nul

echo [1] Xoa file cu (neu co)...
%ADB% -s %DEV% shell "rm -f %OUT%"

echo [2] Bat dau capture port 6614...
echo     Hay dung skill trong game, xong nhan Ctrl+C o day.
echo.
%ADB% -s %DEV% shell "tcpdump -i any -w %OUT% port 6614"

echo.
echo [3] Keo file ve may tinh...
%ADB% -s %DEV% pull %OUT% E:\code\ATS\codeATS\ts_capture.pcap
echo.
echo === Xong! File: E:\code\ATS\codeATS\ts_capture.pcap ===
echo     Chay: python analyze_pcap.py ts_capture.pcap
pause
