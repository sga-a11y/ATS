@echo off
title Party Train Di Gioi Bot
cd /d "%~dp0"
REM Auto party-train Di Gioi: login -> vao DG -> dong bo kenh -> moi theo entity
REM -> set quan su -> chay long vong + ca party danh chung. Chay VO HAN (khong tham so).
python run_party_digioi.py
echo.
echo === Bot da dung. Nhan phim bat ky de dong. ===
pause >nul
