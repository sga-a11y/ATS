@echo off
title Frida Server - MuMu
echo ====================================
echo   Frida Server cho MuMu (127.0.0.1:7555)
echo   Giu cua so nay mo trong luc chay hook_skill.py
echo ====================================
echo.

set ADB=C:\LDPlayer\LDPlayer9\adb.exe

echo [1] Ket noi MuMu...
%ADB% connect 127.0.0.1:7555

echo [2] Port forward 27042...
%ADB% -s 127.0.0.1:7555 forward tcp:27042 tcp:27042

echo [3] Set adbd root...
%ADB% -s 127.0.0.1:7555 root
timeout /t 2 /nobreak >nul

echo [4] Khoi dong frida-server tren MuMu...
echo     (Giu cua so nay mo - Ctrl+C de dung)
echo.
%ADB% -s 127.0.0.1:7555 shell /data/local/tmp/frida-server-16

echo.
echo === Frida server da dung ===
pause
