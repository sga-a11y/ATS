@echo off
echo ====================================
echo   TS Online - Bat dau capture traffic
echo ====================================
echo.
echo Hay choi game binh thuong, traffic se tu dong luu vao traffic/traffic_raw.log
echo Nhan Ctrl+C de dung.
echo.
python -m mitmproxy.tools.main --web-host 127.0.0.1 --web-port 8081 --listen-port 8080 -s capture.py
