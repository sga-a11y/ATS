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
import ssl
import re
import urllib.parse
import urllib.request

# URL co dinh tro ban moi nhat (repo release PUBLIC rieng -> khong lo source, khong can token).
UPDATE_URL = "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/version.json"
# Mirror Google Drive: dien link public cua file version.json vao day khi co. Chap nhan ca dang
# share "https://drive.google.com/file/d/<id>/view?usp=sharing" hoac direct uc?id=<id>.
GOOGLE_DRIVE_VERSION_URL = "https://drive.google.com/file/d/1e3MlVufze1iag8X51IoyCYTf5RfzxCR5/view?usp=drive_link"
# Link public cua file aTSBot.zip tren Google Drive. Neu GitHub check duoc version nhung tai zip
# GitHub fail, updater se thu tiep URL nay.
GOOGLE_DRIVE_ZIP_URL = ""
MANUAL_DOWNLOAD_URL = "https://drive.google.com/drive/folders/1Cm2Suv7aFaq3-v9uq5G7iQ1aNHRoiirv"
UPDATE_SOURCES = [("GitHub", UPDATE_URL)]
if GOOGLE_DRIVE_VERSION_URL.strip():
    UPDATE_SOURCES.append(("Google Drive", GOOGLE_DRIVE_VERSION_URL.strip()))
EXTRA_ZIP_URLS = [u.strip() for u in (GOOGLE_DRIVE_ZIP_URL,) if u.strip()]
# Cap nhat = TAI CA FOLDER (exe + JSON config: server/map/route...) chu KHONG chi exe -> them
# server/map moi (nam trong JSON) moi den duoc user cu. Release chua aTSBot.zip = noi dung folder.
_FALLBACK_ZIP_URL = "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/aTSBot.zip"
_FALLBACK_BUNDLE_URL = "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/aTSBot-bundle.zip"


def running_exe() -> str:
    """Duong dan exe dang chay. BUG THAT da gap (xac nhan qua test thuc te): voi build Nuitka
    onefile hien tai, 'sys.executable' co the tra ve duong dan python.exe HE THONG (KHONG phai
    chinh file aTSBot.exe) - khien _update.bat viet 'start "" "python.exe"' (khong tham so) sau
    khi cap nhat xong, mo ra 1 REPL Python rong thay vi mo lai app. 'sys.argv[0]' dang tin cay
    hon cho truong hop nay (tro dung file exe nguoi dung da chay) - uu tien no neu KHONG chua
    'python' trong ten; fallback sys.executable neu argv[0] bat thuong."""
    cand = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    if cand and "python" not in os.path.basename(cand).lower() and os.path.isfile(cand):
        return cand
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
    cand = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    if cand.lower().endswith(".py"):
        return False
    exe = running_exe()
    return "python" not in os.path.basename(exe).lower() and not exe.lower().endswith(".py")


def _looks_like_ssl_error(exc) -> bool:
    seen = set()
    cur = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, ssl.SSLError):
            return True
        reason = getattr(cur, "reason", None)
        if isinstance(reason, ssl.SSLError):
            return True
        text = repr(cur).lower()
        if "ssl" in text or "certificate" in text or "cert" in text:
            return True
        cur = getattr(cur, "__cause__", None) or getattr(cur, "__context__", None)
    return False


def _urlopen_with_ssl_fallback(req, timeout: float):
    """Open URL normally first. Some user machines have broken/old Windows cert stores or
    TLS-inspecting antivirus: urllib then fails while Chrome still opens GitHub. Retry without
    certificate verification only for SSL/cert-looking errors; other network errors stay visible."""
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except Exception as e:
        if not _looks_like_ssl_error(e):
            raise
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def _google_drive_download_url(url: str) -> str:
    if "drive.google.com" not in str(url).lower():
        return url
    parsed = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(parsed.query)
    file_id = (q.get("id") or [""])[0]
    if not file_id:
        m = re.search(r"/file/d/([^/]+)", parsed.path)
        if m:
            file_id = m.group(1)
    if not file_id:
        return url
    return "https://drive.google.com/uc?export=download&id=" + urllib.parse.quote(file_id)


def _normalize_download_url(url: str) -> str:
    return _google_drive_download_url(str(url or "").strip())


def _fetch_version_json(url: str, timeout: float):
    """Tai version.json. Thu SSL verify binh thuong TRUOC; loi cert (exe thieu cert store Windows
    -> browser OK ma urllib fail) thi thu lai voi SSL KHONG verify. Nem exception neu ca 2 fail
    (goi ben ngoai bat de log ro - KHONG nuot am tham nhu truoc)."""
    req = urllib.request.Request(_normalize_download_url(url), headers={"User-Agent": "atsbot-updater"})
    with _urlopen_with_ssl_fallback(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _is_newer_version(remote_version: str, current_version: str) -> bool:
    remote = str(remote_version or "").strip()
    current = str(current_version or "").strip()
    if not remote:
        return False
    # Ban build that phai co timestamp. Neu bi mat _version.py trong exe thi coi nhu ban cu de
    # van hoi update, thay vi im lang vi so sanh chuoi "1.1...." > "?" bi sai.
    if not current or current == "?" or current.endswith(".dev"):
        return True
    return remote > current


def _unique_urls(urls, fallback=None):
    out = []
    seen = set()
    for u in urls:
        u = _normalize_download_url(u)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    if not out and fallback:
        out.append(_normalize_download_url(fallback))
    return out


def _collect_urls(data: dict, keys):
    urls = []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            urls.extend(str(u).strip() for u in value if str(u).strip())
        else:
            u = str(value or "").strip()
            if u:
                urls.append(u)
    return urls


def _download_urls_from_version(data: dict):
    urls = _collect_urls(data, ("pc_app_urls", "pc_app_mirrors", "pc_app_url", "urls", "mirrors", "url", "zip_url"))
    urls.extend(EXTRA_ZIP_URLS)
    return _unique_urls(urls, _FALLBACK_ZIP_URL)


def _bundle_urls_from_version(data: dict):
    urls = _collect_urls(data, ("bundle_urls", "bundle_mirrors", "bundle_url"))
    return _unique_urls(urls, _FALLBACK_BUNDLE_URL)


def check_update(current_version: str):
    """Tra (version, url, notes) neu host co ban MOI HON current_version.
    None = DA moi nhat (goi duoc server, ver <= current).
    RAISE = KHONG kiem tra duoc (mang/CDN githubusercontent bi chan/SSL/timeout) -> caller log RO
    'khong ket noi duoc server cap nhat' thay vi bao nham 'da moi nhat' (bug cu: nuot exception ->
    None -> user tuong bot on trong khi that ra mang chan github CDN).
    So sanh chuoi: format '1.1.YYYYMMDDHHMM' rong co dinh -> so chuoi = so thu tu thoi gian."""
    errors = []
    saw_source = False
    best = None
    for name, url in UPDATE_SOURCES:
        try:
            d = _fetch_version_json(url, timeout=20)   # 8->20s: CDN githubusercontent cham o VN
            saw_source = True
        except Exception as e:
            errors.append("%s: %s" % (name, e))
            continue
        legacy = "bundle_version" not in d and "pc_app_version" not in d
        ver = str(d.get("pc_app_version") or d.get("version") or "").strip()
        required_ver = str(d.get("pc_app_required_version") or "").strip()
        if required_ver:
            app_required = _is_newer_version(required_ver, current_version)
        else:
            app_required = bool(d.get("pc_app_required", legacy))
        if app_required and _is_newer_version(ver, current_version):
            cand = (ver, _download_urls_from_version(d), str(d.get("notes", "")))
            if best is None or ver > best[0]:
                best = cand
    if best:
        return best
    if saw_source:
        return None
    raise RuntimeError("; ".join(errors) if errors else "khong co nguon update nao")


def _app_root_dir() -> str:
    return os.path.dirname(running_exe())


def installed_app_version(fallback_version: str = "") -> str:
    """Version cua app shell/exe dang cai. Bundle update khong ghi de file nay."""
    try:
        with open(os.path.join(_app_root_dir(), "version.json"), encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("pc_app_version") or data.get("version") or fallback_version or "").strip()
    except Exception:
        return str(fallback_version or "").strip()


def _bundle_root() -> str:
    return os.path.join(_app_root_dir(), "bot_bundle")


def installed_bundle_version(fallback_version: str = "") -> str:
    try:
        with open(os.path.join(_bundle_root(), "version.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return str(fallback_version or "").strip()


def effective_version(fallback_version: str = "") -> str:
    app_ver = installed_app_version(fallback_version)
    bundle_ver = installed_bundle_version("")
    if bundle_ver and _is_newer_version(bundle_ver, app_ver):
        return bundle_ver
    return app_ver or bundle_ver or str(fallback_version or "").strip()


def check_bundle_update(current_app_version: str):
    """Tra (bundle_version, urls, notes) neu co core/data bundle moi.
    Bundle update la silent-update: app tai file zip va chay core moi, KHONG can user cai lai exe."""
    current_bundle = installed_bundle_version(current_app_version)
    errors = []
    saw_source = False
    best = None
    for name, url in UPDATE_SOURCES:
        try:
            d = _fetch_version_json(url, timeout=20)
            saw_source = True
        except Exception as e:
            errors.append("%s: %s" % (name, e))
            continue
        ver = str(d.get("bundle_version") or "").strip()
        if ver and _is_newer_version(ver, current_bundle):
            cand = (ver, _bundle_urls_from_version(d), str(d.get("notes", "")))
            if best is None or ver > best[0]:
                best = cand
    if best:
        return best
    if saw_source:
        return None
    raise RuntimeError("; ".join(errors) if errors else "khong co nguon update nao")


def _safe_extract_zip(zip_path: str, dest_dir: str):
    base = os.path.realpath(dest_dir)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            target = os.path.realpath(os.path.join(dest_dir, info.filename))
            if target != base and not target.startswith(base + os.sep):
                raise RuntimeError("Zip bundle co duong dan khong hop le: %s" % info.filename)
        z.extractall(dest_dir)


def _copy_tree_contents(src_dir: str, dst_dir: str):
    for root, dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        target_root = dst_dir if rel == "." else os.path.join(dst_dir, rel)
        os.makedirs(target_root, exist_ok=True)
        for dname in dirs:
            os.makedirs(os.path.join(target_root, dname), exist_ok=True)
        for fname in files:
            shutil.copy2(os.path.join(root, fname), os.path.join(target_root, fname))


def download_and_apply_bundle(urls, version: str, on_progress=None):
    """Tai aTSBot-bundle.zip -> bot_bundle/current + copy data ra canh exe.
    Code moi co hieu luc sau khi app restart (gui.py chen bot_bundle/current/pc vao sys.path luc boot)."""
    root = _app_root_dir()
    bundle_root = _bundle_root()
    zip_path = os.path.join(root, "aTSBot_bundle_update.zip")
    stage = os.path.join(bundle_root, "stage")
    current = os.path.join(bundle_root, "current")
    errors = []
    for one_url in _as_url_list(urls):
        try:
            req = urllib.request.Request(one_url, headers={"User-Agent": "atsbot-updater"})
            with _urlopen_with_ssl_fallback(req, timeout=60) as r, open(zip_path, "wb") as f:
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
            break
        except Exception as e:
            errors.append("%s: %s" % (one_url, e))
            try:
                os.remove(zip_path)
            except Exception:
                pass
    else:
        raise RuntimeError("Khong tai duoc core bundle tu mirror nao:\n" + "\n".join(errors))

    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)
    _safe_extract_zip(zip_path, stage)
    if not os.path.isfile(os.path.join(stage, "pc", "run_party_digioi.py")):
        raise RuntimeError("Bundle thieu pc/run_party_digioi.py")
    if not os.path.isfile(os.path.join(stage, "pc", "bot", "config.py")):
        raise RuntimeError("Bundle thieu pc/bot/config.py")

    data_dir = os.path.join(stage, "data")
    if os.path.isdir(data_dir):
        _merge_user_config(root, data_dir)
        _copy_tree_contents(data_dir, root)

    shutil.rmtree(current, ignore_errors=True)
    os.makedirs(bundle_root, exist_ok=True)
    os.replace(stage, current)
    with open(os.path.join(bundle_root, "version.txt"), "w", encoding="utf-8") as f:
        f.write(str(version))
    try:
        os.remove(zip_path)
    except Exception:
        pass


def restart_app():
    exe = running_exe()
    subprocess.Popen([exe], cwd=os.path.dirname(exe), close_fds=True)
    os._exit(0)


def _as_url_list(urls):
    if isinstance(urls, (list, tuple)):
        return [_normalize_download_url(u) for u in urls if str(u or "").strip()]
    return [_normalize_download_url(urls)]


def _merge_user_config(live_dir: str, stage_dir: str):
    """DU LIEU MAP LA CUA DEV - ban tai ve LUON DE len ban cua user (user 13/09: "luon tai file
    moi ve de file cu cua user").

    Truoc day `train_maps.json` / `train_routes.json` gop kieu user-wins: key nao may user DA CO
    thi giu ban user, chi them key MOI. Hai file nay lai chinh la noi dev sua safe / diem quai /
    route sau khi boc lai pcap -> may user da tung chay map do thi VINH VIEN ket ban cu, va bug
    duong di da sua o dev khong bao gio den duoc user. Nen gio KHONG gop nua: de nguyen ban
    staging cho xcopy ghi de.

    (`train_block_stats.json` von khong nam trong ham nay - no da bi ghi de binh thuong.)

    Con lai o day: `dangerous_npcs.json` - danh sach NPC nguy hiem user TU them tay, khong phai
    du lieu boc tu game -> van gop (union), khong de mat."""
    live_p = os.path.join(live_dir, "dangerous_npcs.json")
    stage_p = os.path.join(stage_dir, "dangerous_npcs.json")
    if os.path.exists(live_p) and os.path.exists(stage_p):
        try:
            with open(live_p, encoding="utf-8") as f:
                live = json.load(f)
            with open(stage_p, encoding="utf-8") as f:
                stage = json.load(f)
            live_names = live.get("names", []) if isinstance(live, dict) else []
            stage_names = stage.get("names", []) if isinstance(stage, dict) else []
            merged = []
            for name in list(stage_names or []) + list(live_names or []):
                text = str(name or "").strip()
                if text and text not in merged:
                    merged.append(text)
            if isinstance(stage, dict):
                stage["names"] = merged
                with open(stage_p, "w", encoding="utf-8") as f:
                    json.dump(stage, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def download_and_swap(url: str, on_progress=None):
    """Tai aTSBot.zip (CA FOLDER: exe + JSON config) ve -> giai nen ra _update_stage -> viet
    _update.bat: cho app thoat -> xcopy stage GHI DE folder (exe + json moi) -> chay lai -> don.
    accounts.json KHONG co trong zip (build khong ship) -> KHONG bi ghi de -> giu cau hinh user.
    on_progress(done, total) cap nhat thanh tien trinh (total=0 neu server ko bao Content-Length)."""
    exe = running_exe()
    d = os.path.dirname(exe)
    exe_name = os.path.basename(exe)
    # An toan: neu van nham ra python.exe/python3.exe (bug that da gap - xem ghi chu running_exe())
    # -> HUY update thay vi viet _update.bat khoi dong lai sai (mo REPL rong thay vi app that).
    if exe_name.lower().startswith("python"):
        raise RuntimeError(
            f"Khong xac dinh duoc file exe that su (nham ra '{exe_name}') - huy cap nhat de "
            "tranh khoi dong lai sai. Vui long tai ban moi thu cong.")
    zip_path = os.path.join(d, "aTSBot_update.zip")
    stage = os.path.join(d, "_update_stage")

    # 1) tai zip: version.json co the tra 1 URL hoac list mirror URLs. Thu lan luot toi khi duoc.
    errors = []
    for one_url in _as_url_list(url):
        try:
            req = urllib.request.Request(one_url, headers={"User-Agent": "atsbot-updater"})
            with _urlopen_with_ssl_fallback(req, timeout=60) as r, open(zip_path, "wb") as f:
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
            break
        except Exception as e:
            errors.append("%s: %s" % (one_url, e))
            try:
                os.remove(zip_path)
            except Exception:
                pass
    else:
        raise RuntimeError("Khong tai duoc ban update tu mirror nao:\n" + "\n".join(errors))

    # 2) giai nen ra staging (xoa staging cu neu con)
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(stage)

    # 2b) Gop DANH SACH NPC NGUY HIEM user tu them tay vao ban staging. Du lieu map/route thi
    # KHONG gop - ban tai ve de thang len ban cu (xem `_merge_user_config`).
    _merge_user_config(d, stage)

    # 3) bat: TASKKILL exe (bootstrap onefile khong tu chet bang os._exit -> giu khoa file) -> xcopy
    # stage GHI DE folder, RETRY toi khi het khoa -> chay lai. KHONG cho theo PID/ten process nua
    # (Nuitka onefile co process cha giu khoa, PID payload chet nhung khoa van con -> treo).
    # taskkill BO QUA neu exe_name la python* (dev) -> khong lo dinh python khac.
    _kill = "" if "python" in exe_name.lower() else \
        'taskkill /f /im "%s" >nul 2>&1\r\n' % exe_name
    bat = os.path.join(d, "_update.bat")
    with open(bat, "w", encoding="ascii") as f:
        f.write(
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "timeout /t 2 /nobreak >nul\r\n"   # cho app kip dong cua so
            + _kill +                          # kill exe -> nha khoa file (neu la ban build)
            ":copy\r\n"
            "timeout /t 1 /nobreak >nul\r\n"
            'xcopy /e /y /q /i "_update_stage\\*" "." >nul\r\n'
            'if errorlevel 1 goto copy\r\n'    # exe con khoa (chua kill xong) -> thu lai toi khi duoc
            'rmdir /s /q "_update_stage"\r\n'
            'del /q "aTSBot_update.zip"\r\n'
            'start "" "%s"\r\n'
            'del "%%~f0"\r\n' % exe_name
        )
    # DETACHED_PROCESS (0x8) | CREATE_NO_WINDOW (0x08000000): bat chay ngam, song sau khi app thoat
    subprocess.Popen(["cmd", "/c", bat], cwd=d,
                     creationflags=0x00000008 | 0x08000000, close_fds=True)
    os._exit(0)
