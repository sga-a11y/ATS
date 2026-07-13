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
import urllib.request

# URL co dinh tro ban moi nhat (repo release PUBLIC rieng -> khong lo source, khong can token).
UPDATE_URL = "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/version.json"
_FALLBACK_EXE_URL = "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/aTSBot.exe"


def running_exe() -> str:
    """Duong dan exe dang chay (Nuitka onefile: sys.executable = aTSBot.exe)."""
    return os.path.abspath(sys.executable)


def is_frozen() -> bool:
    """True neu dang chay BAN BUILD (exe), False khi dev chay 'python gui.py' (python.exe)."""
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
            return ver, (d.get("url") or _FALLBACK_EXE_URL), str(d.get("notes", ""))
    except Exception:
        pass
    return None


def download_and_swap(url: str, on_progress=None):
    """Tai exe moi ve canh exe hien tai -> viet _update.bat -> chay bat (detached) -> thoat app NGAY.
    on_progress(done, total) de cap nhat thanh tien trinh (total=0 neu server ko bao Content-Length)."""
    exe = running_exe()
    d = os.path.dirname(exe)
    exe_name = os.path.basename(exe)
    new = os.path.join(d, "aTSBot_new.exe")

    req = urllib.request.Request(url, headers={"User-Agent": "atsbot-updater"})
    with urllib.request.urlopen(req, timeout=30) as r, open(new, "wb") as f:
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

    bat = os.path.join(d, "_update.bat")
    with open(bat, "w", encoding="ascii") as f:
        f.write(
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            ":wait\r\n"
            'tasklist /fi "imagename eq %s" 2>nul | find /i "%s" >nul && (timeout /t 1 /nobreak >nul & goto wait)\r\n'
            'move /y "aTSBot_new.exe" "%s" >nul\r\n'
            'start "" "%s"\r\n'
            'del "%%~f0"\r\n' % (exe_name, exe_name, exe_name, exe_name)
        )
    # DETACHED_PROCESS (0x8) | CREATE_NO_WINDOW (0x08000000): bat chay ngam, song sau khi app thoat
    subprocess.Popen(["cmd", "/c", bat], cwd=d,
                     creationflags=0x00000008 | 0x08000000, close_fds=True)
    os._exit(0)
