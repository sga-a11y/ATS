"""Tu dong cap nhat bản build (exe). Check version.json tren host cong khai -> neu co ban moi
hon -> hoi user -> tai exe moi -> _update.bat thay & khoi dong lai.

version.json (host tren GitHub Releases public 'atsbot-release', URL 'latest' co dinh):
  {"version": "1.1.YYYYMMDDHHMM", "url": "https://.../aTSBot.exe", "notes": "..."}

Windows KHONG cho ghi de exe dang chay -> phai qua _update.bat trung gian: cho app thoat ->
move exe moi de -> chay lai -> tu xoa bat.
"""
import os
import sys
import json
import subprocess
import shutil
import zipfile
import urllib.request

# URL co dinh tro ban moi nhat (repo release PUBLIC rieng -> khong lo source, khong can token).
UPDATE_URL = "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/version.json"
# Cap nhat = TAI CA FOLDER (exe + JSON config: server/map/route...) chu KHONG chi exe -> them
# server/map moi (nam trong JSON) moi den duoc user cu. Release chua aTSBot.zip = noi dung folder.
_FALLBACK_ZIP_URL = "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/aTSBot.zip"


def running_exe() -> str:
    """Duong dan exe dang chay (Nuitka onefile: sys.executable = aTSBot.exe)."""
    return os.path.abspath(sys.executable)


def is_frozen() -> bool:
    """True neu dang chay BAN BUILD (exe), False khi dev chay 'python gui.py' (python.exe).
    Nuitka dat bien global '__compiled__' trong MOI module da bien dich -> tin hieu CHAC CHAN nhat
    (truoc chi dua vao sys.executable name - voi Nuitka onefile co the tro vao temp/khac -> sai ->
    is_frozen=False -> BO QUA check update, dung canh 'chay exe ma khong hoi update')."""
    if "__compiled__" in globals():
        return True
    if getattr(sys, "frozen", False):   # PyInstaller/cx_Freeze fallback
        return True
    return "python" not in os.path.basename(sys.executable).lower()


def check_update(current_version: str):
    """Tra (version, url, notes) neu host co ban MOI HON current_version; None neu khong/loi.
    So sanh chuoi: format '1.1.YYYYMMDDHHMM' rong co dinh -> so chuoi = so thu tu thoi gian."""
    try:
        req = urllib.request.Request(UPDATE_URL, headers={"User-Agent": "atsbot-updater"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode("utf-8"))
        ver = str(d.get("version", "")).strip()
        if ver and ver > str(current_version):
            return ver, (d.get("url") or _FALLBACK_ZIP_URL), str(d.get("notes", ""))
    except Exception:
        pass
    return None


def download_and_swap(url: str, on_progress=None):
    """Tai aTSBot.zip (CA FOLDER: exe + JSON config) ve -> giai nen ra _update_stage -> viet
    _update.bat: cho app thoat -> xcopy stage GHI DE folder (exe + json moi) -> chay lai -> don.
    accounts.json KHONG co trong zip (build khong ship) -> KHONG bi ghi de -> giu cau hinh user.
    on_progress(done, total) cap nhat thanh tien trinh (total=0 neu server ko bao Content-Length)."""
    exe = running_exe()
    d = os.path.dirname(exe)
    exe_name = os.path.basename(exe)
    zip_path = os.path.join(d, "aTSBot_update.zip")
    stage = os.path.join(d, "_update_stage")

    # 1) tai zip
    req = urllib.request.Request(url, headers={"User-Agent": "atsbot-updater"})
    with urllib.request.urlopen(req, timeout=60) as r, open(zip_path, "wb") as f:
        total = int(r.headers.get("Content-Length", 0) or 0)
        done = 0
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if on_progress:
                on_progress(done, total)

    # 2) giai nen ra staging (xoa staging cu neu con)
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(stage)

    # 3) bat: cho app thoat -> xcopy stage GHI DE folder (exe + json), don rac -> chay lai
    bat = os.path.join(d, "_update.bat")
    with open(bat, "w", encoding="ascii") as f:
        f.write(
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            ":wait\r\n"
            'tasklist /fi "imagename eq %s" 2>nul | find /i "%s" >nul && (timeout /t 1 /nobreak >nul & goto wait)\r\n'
            'xcopy /e /y /q /i "_update_stage\\*" "." >nul\r\n'
            'rmdir /s /q "_update_stage"\r\n'
            'del /q "aTSBot_update.zip"\r\n'
            'start "" "%s"\r\n'
            'del "%%~f0"\r\n' % (exe_name, exe_name, exe_name)
        )
    # DETACHED_PROCESS (0x8) | CREATE_NO_WINDOW (0x08000000): bat chay ngam, song sau khi app thoat
    subprocess.Popen(["cmd", "/c", bat], cwd=d,
                     creationflags=0x00000008 | 0x08000000, close_fds=True)
    os._exit(0)
