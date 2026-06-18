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
import shutil
import subprocess
import sys

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
             "vantieu_requests.json", "skills_db.json"]


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


def stage():
    """Copy source sach vao _stage. config.py = config.example.py (KHONG dung config that)."""
    os.makedirs(STAGE, exist_ok=True)
    shutil.copy(os.path.join(ROOT, "gui.py"), STAGE)
    shutil.copy(os.path.join(ROOT, "run_party_digioi.py"), STAGE)
    # bot package: copy het .py TRU config.py that -> dung config.example.py lam config.py
    bot_src = os.path.join(ROOT, "bot")
    bot_dst = os.path.join(STAGE, "bot")
    os.makedirs(bot_dst, exist_ok=True)
    for fn in os.listdir(bot_src):
        if not fn.endswith(".py"):
            continue
        if fn == "config.py":          # KHONG copy config that (credential)
            continue
        shutil.copy(os.path.join(bot_src, fn), bot_dst)
    # config.example.py -> config.py (rong, khong credential)
    shutil.copy(os.path.join(bot_src, "config.example.py"),
                os.path.join(bot_dst, "config.py"))
    print("staged source (config = example, KHONG co credential)")


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
           os.path.join(STAGE, "gui.py")]
    run(cmd)
    src = os.path.join(WORK, NAME + ".exe")
    shutil.copy(src, os.path.join(DIST, NAME + ".exe"))
    print("compiled (Nuitka native) -> %s\\%s.exe" % (DIST, NAME))


def copy_data():
    """Copy JSON config (sua duoc) + accounts.json MAU + README ra canh .exe."""
    import json
    for fn in DATA_JSON:
        src = os.path.join(ROOT, fn)
        if os.path.exists(src):
            shutil.copy(src, DIST)
    # accounts.json MAU: 1 party voi acc1/pass1, acc2/pass2, acc3/pass3 (placeholder) -> mo len
    # KHONG bi trong (do "lom"), nguoi nhan vao "Cau hinh" sua thanh acc that cua ho.
    sample = {
        "channel": 2,
        "parties": [{
            "server": "trieu_van", "mode": "stand", "start_city_id": 0,
            "mob_index": -1, "city_flag": 0, "do_dungeon": True, "leaders": [],
            "accounts": [
                {"u": "acc1", "p": "pass1", "on": True},
                {"u": "acc2", "p": "pass2", "on": True},
                {"u": "acc3", "p": "pass3", "on": True},
            ],
        }],
    }
    with open(os.path.join(DIST, "accounts.json"), "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)
    # version (doc tu bot/_version.py)
    ver = "?"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_v", os.path.join(ROOT, "bot", "_version.py"))
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
        "TÍNH NĂNG\n"
        "  - Quản lý nhiều party / nhiều acc, mỗi party 1 chế độ riêng\n"
        "  - 11 server. Chế độ: Train map / Train Dị Giới / Về thành / Đứng yên\n"
        "  - Tự động: lập party + mời + đồng bộ kênh, đánh daily dungeon, vận tiêu,\n"
        "    nhận quà online, nhận mail / quà sự kiện / exp offline, nhập giftcode\n"
        "  - Tự tìm đường tới bãi train, kéo cả party qua cổng\n"
        "  - Tự phục hồi khi kẹt bãi / có acc chết / hết giờ Dị Giới\n\n"
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
    print("copied data JSON + accounts.json mau + README (user-facing) ra %s" % DIST)


if __name__ == "__main__":
    print("=== BUILD PRODUCT (PyArmor + PyInstaller onefile) ===")
    clean()
    stage()
    package()
    copy_data()
    print("\n=== XONG. Gui ca thu muc: %s ===" % DIST)
