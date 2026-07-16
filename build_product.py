"""Build ban PRODUCT (.exe) gui cho nguoi khac:
 - KHONG nhung tai khoan/credential cua minh (dung config.example.py -> config.py rong).
 - Bao ve code: NUITKA bien dich Python -> C -> .exe native (KHONG con bytecode de decompile)
   + anti-debug guard (bot/_guard.py).
 - Nuitka onefile -> 1 file TSBot.exe (khong can cai Python).
 - File JSON config de NGOAI canh .exe (nguoi nhan sua duoc): servers/cities/train_maps/...
   + accounts.json RONG (nguoi nhan tu nhap acc qua GUI).

Chay:  python build_product.py
Output: dist_product/  (gui ca thu muc nay cho nguoi khac)
"""
import os
import json
import shutil
import subprocess
import sys
import urllib.request

RELEASE_REPO = "sgagamee-oss/atsbot-release"   # repo PUBLIC phat hanh (upload exe + version.json)

ROOT = os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.join(ROOT, "_stage")        # source sach (config.example -> config)
WORK = os.path.join(ROOT, "_work")          # Nuitka build temp
DIST = os.path.join(ROOT, "aTSBot")         # output cuoi cung (thu muc gui di)
NAME = "aTSBot"

# Nuitka cache PHAI o thu muc THUONG (khong sandbox). Mac dinh %LOCALAPPDATA%\Nuitka co the bi
# ao hoa duoi sandbox app -> gcc doc file MinGW khong nhat quan (loi 'structuredquerycondition.h
# No such file' du file co that). Dat cache ve goc o cung de tranh.
os.environ.setdefault("NUITKA_CACHE_DIR",
                      os.path.join(os.path.splitdrive(ROOT)[0] + os.sep, "_nk"))


# --- file CODE (.py) se obfuscate + dong goi vao exe ---
PY_SOURCES = ["gui.py", "run_party_digioi.py", "bot"]

# --- file JSON DATA: de NGOAI canh .exe (nguoi nhan sua). config.py KHONG o day (la code). ---
DATA_JSON = ["servers.json", "cities.json", "train_maps.json", "train_routes.json",
             "mob_paths.json", "map_gates.json", "pets.json", "pet_hedoanh.json",
             "vantieu_requests.json", "skills_db.json", "junk_scrolls.json", "skills_data.json",
             "items_gamedata.json", "donate_items.json", "use_items.json", "events.json",
             "train_block_stats.json"]


def run(cmd, **kw):
    print(">>", " ".join(cmd))
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        print("LOI: lenh tren that bai (exit %d)" % r.returncode)
        sys.exit(1)


def clean():
    for d in (STAGE, WORK, DIST):
        shutil.rmtree(d, ignore_errors=True)
    for f in (NAME + ".spec",):
        if os.path.exists(os.path.join(ROOT, f)):
            os.remove(os.path.join(ROOT, f))


VERSION_PREFIX = "1.1"   # tang khi doi tinh nang lon; hau to timestamp tu sinh moi lan build


def _build_version():
    """1.1.YYYYMMDDHHMM - tu sinh theo thoi diem build, de user nhin duoc dang xai ban nao
    (truoc day version co dinh "1.0.0" khong phan biet duoc cac lan build khac nhau)."""
    import datetime
    return VERSION_PREFIX + "." + datetime.datetime.now().strftime("%Y%m%d%H%M")


def stage():
    """Copy source sach vao _stage. config.py = file TRACKED (placeholder credential; account that o
    accounts.json - gitignored, KHONG nhung vao build)."""
    os.makedirs(STAGE, exist_ok=True)
    shutil.copy(os.path.join(ROOT, "gui.py"), STAGE)
    shutil.copy(os.path.join(ROOT, "run_party_digioi.py"), STAGE)
    # bot package: copy het .py (config.py la file tracked placeholder, copy binh thuong)
    bot_src = os.path.join(ROOT, "bot")
    bot_dst = os.path.join(STAGE, "bot")
    os.makedirs(bot_dst, exist_ok=True)
    for fn in os.listdir(bot_src):
        if not fn.endswith(".py"):
            continue
        shutil.copy(os.path.join(bot_src, fn), bot_dst)
    ver = _build_version()
    with open(os.path.join(bot_dst, "_version.py"), "w", encoding="utf-8") as f:
        f.write('"""Phien ban app - TU SINH luc build (build_product.py), KHONG sua tay."""\n')
        f.write('VERSION = "%s"\n' % ver)
    print("staged source (config.py placeholder, account that o accounts.json) - version=%s" % ver)


def package():
    """NUITKA bien dich _stage/gui.py -> .exe native onefile (chong dich nguoc)."""
    os.makedirs(DIST, exist_ok=True)
    cmd = [sys.executable, "-m", "nuitka",
           "--onefile",                       # 1 file .exe
           "--standalone",
           "--assume-yes-for-downloads",      # tu tai C-compiler neu thieu (khong hoi)
           "--windows-console-mode=disable",  # app GUI: khong hien console
           "--enable-plugin=tk-inter",        # ho tro tkinter
           "--include-package=bot",           # bao dam package bot vao binary
           "--follow-imports",
           "--output-dir=" + WORK,
           "--output-filename=" + NAME + ".exe",
           "--remove-output",                 # don file trung gian sau build
           "gui.py"]                          # CHAY TU cwd=STAGE -> bot = _stage/bot (config example),
    #                                           KHONG lay nham bot THAT o ROOT (tranh lo credential).
    # Buoc nen onefile (zstd) chay NHIEU worker theo so CPU, moi worker ngon RAM lon -> may dang
    # chay nhieu MuMu/bot de OOM ("zstd compress error: not enough memory", xac nhan thuc te
    # 15/07). Fail lan dau -> tu build lai KHONG NEN (--onefile-no-compression): exe to hon
    # (~35MB thay vi ~10MB) nhung luon thanh cong; zip ben ngoai van nen bot lai duoc mot phan.
    r = subprocess.run(cmd, cwd=STAGE)
    if r.returncode != 0:
        print("!! Nuitka fail (kha nang OOM buoc nen) -> thu lai voi --onefile-no-compression")
        run(cmd[:-1] + ["--onefile-no-compression", "gui.py"], cwd=STAGE)
    src = os.path.join(WORK, NAME + ".exe")
    shutil.copy(src, os.path.join(DIST, NAME + ".exe"))
    print("compiled (Nuitka native) -> %s\\%s.exe" % (DIST, NAME))


def copy_data():
    """Copy JSON config (sua duoc) + README ra canh .exe. KHONG copy accounts.json: ban gui di
    KHONG co accounts.json de nguoi nhan COPY DE ban moi (update) len ban cu ma KHONG mat cau hinh
    acc da luu. Lan dau chay, gui.py tu tao accounts.json mac dinh neu chua co (_load_profiles)."""
    for fn in DATA_JSON:
        src = os.path.join(ROOT, fn)
        if os.path.exists(src):
            shutil.copy(src, DIST)
    # version: doc tu _stage/bot/_version.py (BAN TIMESTAMP that da nhung vao exe), KHONG doc
    # ROOT/bot/_version.py (="1.1.dev" fallback dev) -> neu doc ROOT thi version.json/tag release
    # LECH voi version trong exe -> auto-update loan.
    ver = "?"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_v", os.path.join(STAGE, "bot", "_version.py"))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        ver = m.VERSION
    except Exception:
        pass
    # README user-facing (BO doan bao ve code - user doc ky cuc). Chi tinh nang + cach dung.
    note = (
        f"TS Online Bot  v{ver}\n"
        "============================\n\n"
        "CÁCH DÙNG\n"
        "  1. Chạy aTSBot.exe\n"
        "  2. Bấm 'Cấu hình' -> nhập tài khoản + chọn chế độ cho từng party -> Lưu\n"
        "  3. Bấm START\n\n"
        "CHẾ ĐỘ PARTY (chọn khi Cấu hình)\n"
        "  - Train map: đưa cả party ra bãi luyện quái đã chọn, tự lập party, tự tìm đường\n"
        "    (kéo qua cổng/an toàn), tự đánh, tự phục hồi khi kẹt bãi / acc chết / văng map\n"
        "  - Train Dị Giới: vào Dị Giới, chạy vòng quanh đánh tới hết giờ trong ngày\n"
        "  - Tập trung về thành (đứng yên): cả party về 1 thành cấu hình sẵn, đứng yên\n"
        "  - Login đâu đứng yên đó: không di chuyển, chỉ tự làm việc vặt (xem dưới)\n\n"
        "TỰ ĐỘNG LÀM (mọi chế độ, không cần bấm gì thêm)\n"
        "  - Nhiệm vụ hằng ngày (9 ô) + claim thưởng hàng/cột/tổng kết\n"
        "  - Phó bản tổ đội (nhiệm vụ ô 5): cả party CÙNG chưa xong thì tự lập đội đánh hộ,\n"
        "    xong claim nốt thưởng; có 1 acc đã xong thì bỏ qua (không phá đội hình đang chạy)\n"
        "  - Dungeon ngày (solo), vận tiêu, quà online/mail/sự kiện/exp offline, giftcode\n"
        "  - Đồng bộ kênh cả party (kiểm tra đủ chỗ trước khi chuyển, tránh kẹt kênh đầy)\n\n"
        "MẸO GIAO DIỆN\n"
        "  - Bấm tiêu đề cột 'Kênh' -> đổi kênh cả party | cột 'Map' -> teleport về thành\n"
        "  - Bấm cột 'Tài khoản' / 'Nhân vật' -> che thông tin (tránh lộ khi share màn hình)\n"
        "  - Chấm trạng thái: xanh = đủ acc chạy | vàng = chạy một phần | xám = tắt\n\n"
        "GHI CHÚ\n"
        "  - Các file .json cạnh exe là cấu hình (server / map / thành) - có thể sửa\n"
        "  - accounts.json lưu tài khoản của bạn (GUI tự ghi khi bấm Lưu)\n")
    # utf-8-sig (co BOM) -> Notepad Windows hien dung dau tieng Viet
    with open(os.path.join(DIST, "README.txt"), "w", encoding="utf-8-sig") as f:
        f.write(note)
    # version.json cho AUTO-UPDATE: upload FILE NAY + aTSBot.exe len GitHub release 'atsbot-release'.
    # App (bot/updater.py) tai file nay tu URL 'latest' co dinh -> so version -> hoi cap nhat.
    # Sua "notes" thanh mo ta thay doi truoc khi up (user se thay trong popup cap nhat).
    vj = {
        "version": ver,
        # CA FOLDER (exe + JSON config) -> them server/map/route moi (nam trong JSON) den duoc user cu.
        "url": "https://github.com/sgagamee-oss/atsbot-release/releases/latest/download/aTSBot.zip",
        "notes": "Bản cập nhật mới.",
    }
    with open(os.path.join(DIST, "version.json"), "w", encoding="utf-8") as f:
        json.dump(vj, f, ensure_ascii=False, indent=2)
    print("copied data JSON + accounts.json mau + README + version.json ra %s" % DIST)


def make_zip():
    """Dong goi noi dung folder DIST (exe + json + README + version.json) -> ROOT/aTSBot.zip
    (FLAT: file o goc zip -> giai nen la GHI DE thang vao folder app). accounts.json KHONG co
    trong DIST -> khong vao zip -> update KHONG ghi de cau hinh acc cua user."""
    import zipfile
    zpath = os.path.join(ROOT, NAME + ".zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(DIST):
            for fn in files:
                full = os.path.join(root, fn)
                z.write(full, os.path.relpath(full, DIST))   # arcname = tuong doi voi DIST (flat)
    print("dong goi -> %s (%.1f MB)" % (zpath, os.path.getsize(zpath) / 1e6))


def _release_token():
    """Lay token GitHub: uu tien env GH_TOKEN/GITHUB_TOKEN, roi den git credential store (chinh
    token dang push - account sga-a11y, da duoc them collaborator write vao RELEASE_REPO)."""
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok:
        return tok.strip()
    try:
        r = subprocess.run(["git", "credential", "fill"],
                           input="protocol=https\nhost=github.com\n\n",
                           capture_output=True, text=True, timeout=15)
        for line in r.stdout.splitlines():
            if line.startswith("password="):
                return line[len("password="):].strip()
    except Exception:
        pass
    return None


def _gh_post(url, token, data=None, ctype="application/json"):
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "User-Agent": "atsbot-build"}
    if data is not None:
        headers["Content-Type"] = ctype
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def upload_release():
    """Tao GitHub release (tag = version) + upload aTSBot.exe + version.json. Token lay tu
    git credential (tai dung token dang push). Loi -> in huong dan up thu cong, KHONG fail build."""
    token = _release_token()
    if not token:
        print("!! Khong lay duoc token (GH_TOKEN / git credential) -> BO QUA upload. Up thu cong:")
        print("   gh release create v<version> %s\\aTSBot.exe %s\\version.json -R %s"
              % (DIST, DIST, RELEASE_REPO))
        return
    vj = json.load(open(os.path.join(DIST, "version.json"), encoding="utf-8"))
    tag = "v" + vj["version"]
    try:
        rel = _gh_post("https://api.github.com/repos/%s/releases" % RELEASE_REPO, token,
                       json.dumps({"tag_name": tag, "name": tag,
                                   "body": vj.get("notes", "")}).encode("utf-8"))
    except Exception as e:
        print("!! Tao release loi (tag trung? khong quyen?): %s" % e)
        return
    rid = rel["id"]
    for path in (os.path.join(ROOT, NAME + ".zip"), os.path.join(DIST, NAME + ".exe"),
                 os.path.join(DIST, "version.json")):
        if not os.path.exists(path):
            continue
        name = os.path.basename(path)
        up = ("https://uploads.github.com/repos/%s/releases/%d/assets?name=%s"
              % (RELEASE_REPO, rid, name))
        try:
            _gh_post(up, token, open(path, "rb").read(), ctype="application/octet-stream")
            print("   uploaded %s" % name)
        except Exception as e:
            print("!! Upload %s loi: %s" % (name, e))
    print("=== Release %s da len https://github.com/%s/releases/latest ===" % (tag, RELEASE_REPO))


if __name__ == "__main__":
    print("=== BUILD PRODUCT (PyArmor + PyInstaller onefile) ===")
    clean()
    stage()
    package()
    copy_data()
    make_zip()
    if "--no-upload" in sys.argv:
        print("\n(--no-upload) BO QUA upload release.")
    else:
        print("\n=== Upload release len %s ===" % RELEASE_REPO)
        upload_release()
    print("\n=== XONG. Gui ca thu muc: %s ===" % DIST)
