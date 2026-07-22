# -*- coding: utf-8 -*-
"""GUI quan ly bot TS Online (Tkinter - khong can cai them gi).

Tinh nang:
  - Moi PARTY = 1 tab. Trong tab: bang trang thai tung acc + Start/Stop tung acc + ca party.
  - Start/Stop toan bo.
  - Log truc tiep (cuon theo thoi gian thuc).
  - Sua cau hinh (party/acc, map train/DG) -> luu accounts.json.

Chay:  python gui.py
"""
import os, sys, json, re, queue, logging, threading, time, collections, importlib, webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

_LABEL_RE = re.compile(r"^\d\d:\d\d:\d\d \[([^\]]+)\]")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_party_digioi as ctrl          # module dieu khien (da refactor)
from bot import config
from bot._appdir import app_dir as _app_dir   # thu muc goc (dev=project, frozen=canh .exe)

log = logging.getLogger("bot")   # -> hien o panel log GUI (qua _QueueHandler tren root)

ACCOUNTS_JSON = os.path.join(_app_dir(), "accounts.json")
DONATE_CHAT_URL = "https://zalo.me/g/qiy6aflscqbh6v4tivej"
# Cap quai Di Gioi: idx 1..15 (gói 0x61 02 00 idx) -> cap hien thi. Xem KNOWLEDGE.md.
_DG_LEVELS = [10, 25, 40, 55, 70, 85, 100, 110, 120, 130, 140, 150, 160, 170, 180]

def _dg_level_to_idx(level_val, default=2):
    try:
        return _DG_LEVELS.index(int(level_val)) + 1
    except (ValueError, TypeError):
        return default

BATTLE_CONDITION_TYPE_LABELS = {
    "always": "Luôn luôn",
    "mob": "Số quái",
    "block": "Block quái",
    "sp": "SP",
    "hp_pct": "HP (%)",
    "ally_hp_pct": "Có đồng đội HP < %",
    "ally_sp_pct": "Có đồng đội SP < %",
    "sp_full": "SP đầy",
    "boss": "Đang boss / phó bản",
    "quest": "Quest đông quái",
    "ally_dead": "Đồng đội chết",
}
LABEL_BATTLE_CONDITION_TYPES = {v: k for k, v in BATTLE_CONDITION_TYPE_LABELS.items()}
BATTLE_COMPARE_LABELS = {"gte": ">=", "lte": "<=", "gt": ">", "lt": "<", "eq": "="}
LABEL_BATTLE_COMPARE = {v: k for k, v in BATTLE_COMPARE_LABELS.items()}
BATTLE_NUMERIC_CONDITIONS = {"mob", "block", "sp", "hp_pct", "ally_hp_pct", "ally_sp_pct"}
BATTLE_FIXED_LT_CONDITIONS = {"ally_hp_pct", "ally_sp_pct"}
BATTLE_ACTION_LABELS = {
    "auto": "Auto",
    "normal": "Đánh thường",
    "defend": "Phòng thủ",
    "flee": "Bỏ chạy",
}
LABEL_BATTLE_ACTIONS = {v: k for k, v in BATTLE_ACTION_LABELS.items()}
BATTLE_TARGET_LABELS = {
    "auto": "Auto",
    "block": "Theo block",
    "enemy_low_hp": "Quái ít HP nhất",
    "enemy_high_hp": "Quái nhiều HP nhất",
    "enemy_first": "Quái đầu",
    "enemy_last": "Quái cuối",
    "ally_low_hp": "Đồng đội ít HP nhất",
    "ally_high_hp": "Đồng đội nhiều HP nhất",
    "ally_low_sp": "Đồng đội ít SP nhất",
    "self": "Bản thân",
}
LABEL_BATTLE_TARGETS = {v: k for k, v in BATTLE_TARGET_LABELS.items()}


def _load_donate_qr_image():
    from bot.donate_qr_data import DONATE_QR_PNG_B64
    return tk.PhotoImage(data=DONATE_QR_PNG_B64)


# Party MAU cho profile moi (placeholder de user thay = acc that)
_DEFAULT_PARTY = {"server": "trieu_van", "mode": "stand", "start_city_id": 0, "mob_index": -1,
                  "city_flag": 0, "do_daily": True, "leaders": [],
                  "accounts": [{"u": "acc1", "p": "pass1", "on": True},
                               {"u": "acc2", "p": "pass2", "on": True},
                               {"u": "acc3", "p": "pass3", "on": True}]}


def _load_profiles():
    """Doc accounts.json -> {active, profiles:{ten:{channel,party_leaders,parties}}}.
    Dang FLAT cu {channel,parties} -> MIGRATE: 'Cau hinh 1' = config HIEN TAI cua user (active),
    'Cau hinh 2' = template mac dinh (1 party placeholder) de user tu dien thanh bo khac."""
    import copy
    _missing = not os.path.exists(ACCOUNTS_JSON)   # ban gui di KHONG kem accounts.json -> lan dau thieu
    if _missing:
        # Chua co accounts.json (may moi / copy de update) -> TAO NGAY file mac dinh, CA 2 cau hinh
        # deu co party mau (acc1/pass1, acc2/pass2, acc3/pass3) de user mo Setting la thay ngay, khoi
        # bi trong o Cau hinh 1 (dang active).
        prof = {"active": "Cấu hình 1",
                "profiles": {"Cấu hình 1": {"channel": 2, "parties": [copy.deepcopy(_DEFAULT_PARTY)]},
                             "Cấu hình 2": {"channel": 2, "parties": [copy.deepcopy(_DEFAULT_PARTY)]}}}
        try: _save_profiles(prof)
        except Exception: pass
        return prof
    try:
        with open(ACCOUNTS_JSON, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {"channel": 2, "parties": []}
    if isinstance(d, dict) and isinstance(d.get("profiles"), dict) and d["profiles"]:
        return d
    # FLAT cu {channel,parties} -> MIGRATE: Cau hinh 1 = config THAT cua user (giu nguyen), Cau hinh 2
    # = template mau.
    ch = d.get("channel", 2) if isinstance(d, dict) else 2
    return {"active": "Cấu hình 1",
            "profiles": {"Cấu hình 1": d,
                         "Cấu hình 2": {"channel": ch, "parties": [copy.deepcopy(_DEFAULT_PARTY)]}}}


def _save_profiles(prof):
    """Ghi {active, profiles} vao accounts.json (bot tu rut profile active qua config._load_accounts_json)."""
    with open(ACCOUNTS_JSON, "w", encoding="utf-8") as f:
        json.dump(prof, f, ensure_ascii=False, indent=2)

# ---------------- Log -> queue (de GUI hien) ----------------
_log_queue = queue.Queue()


class _QueueHandler(logging.Handler):
    def emit(self, record):
        try:
            _log_queue.put_nowait(self.format(record))
        except Exception:
            pass


def _setup_log_capture():
    root = logging.getLogger()
    # Bo StreamHandler (in log ra console Windows) - GUI da hien log roi.
    # Giu FileHandler (party.log) - FileHandler la con cua StreamHandler nen loai tru rieng.
    for h in list(root.handlers):
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            root.removeHandler(h)
    qh = _QueueHandler()
    qh.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
    root.addHandler(qh)


_MAP_NAMES: dict = {}

def _map_name(mid):
    if mid is None:
        return "-"
    if mid == getattr(config, "DIGIOI_MAP_ID", -1):
        return "Dị Giới"
    if not _MAP_NAMES:
        # map train (train_maps.json)
        for k, v in _load_json("train_maps.json").get("maps", {}).items():
            try:
                _MAP_NAMES[int(k)] = v.get("name", k)
            except ValueError:
                pass
        # thanh (cities.json): city_id -> ten thanh (map_id thanh thuong = city_id)
        for k, v in _load_json("cities.json").get("cities", {}).items():
            try:
                _MAP_NAMES.setdefault(int(v.get("city_id")), v.get("name", k))
            except (ValueError, TypeError):
                pass
        # map event (events.json): dest_map -> label (bo qua dest=0)
        for k, v in _load_json("events.json").get("events", {}).items():
            try:
                dm = int(v.get("dest_map", 0))
                if dm:
                    _MAP_NAMES.setdefault(dm, v.get("label", k))
            except (ValueError, TypeError):
                pass
        _MAP_NAMES.setdefault(10991, "40 NPC")   # map event 40 NPC (dest chua bat duoc qua capture)
    return _MAP_NAMES.get(mid, str(mid))


# ---------------- App ----------------
class BotGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        try:
            from bot._version import VERSION as _VER
        except Exception:
            _VER = "?"
        self._version = _VER
        self.title(f"TS Online Bot Manager v{_VER}")
        self.geometry("1100x720")
        self.minsize(900, 560)
        self._setup_style()
        self._dot_on = self._make_dot("#16c60c")    # xanh la: DU acc dang chay
        self._dot_warn = self._make_dot("#f0c000")  # vang: chay MOT PHAN (thieu acc - chet/rot)
        self._dot_off = self._make_dot("#888888")   # xam: khong co acc nao chay
        # list thanh (cho popup teleport khi bam header Map). Doc tu cities.json giong ConfigDialog.
        ct_raw = _load_json("cities.json").get("cities", {})
        self.cities = [(v["city_id"], v.get("flag", 0), v.get("name", k)) for k, v in ct_raw.items()]
        # --- log filter state ---
        self.log_buffer = collections.deque(maxlen=4000)   # (line, label)
        self.log_filter = None         # None = tat ca; hoac set(username) duoc hien
        self._char2user = {}           # ten nhan vat -> username (cap nhat khi acc resolve)
        self._all_usernames = set(u for pidx in range(len(config.PARTIES))
                                  for (u, *_ ) in ctrl.party_accounts(pidx))
        self._build_ordinal()
        self._build_toolbar()
        self._build_tabs()
        self._build_log()
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.after(1000, self._refresh)
        self.after(300, self._drain_log)
        self.after(1500, self._check_update)   # tu kiem tra ban moi (chi khi chay ban build)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- tu dong cap nhat ----
    def _check_update(self, manual=False):
        """Chay ban build -> check version.json tren host; co ban moi -> hoi + tai + restart."""
        try:
            from bot import updater
        except Exception as e:
            log.warning("update: khong load duoc updater: %s", e)
            if manual:
                messagebox.showerror("Update", f"Khong load duoc updater:\n{e}", parent=self)
            return
        if not updater.is_frozen():
            if manual:
                messagebox.showinfo("Update", "Ban dang chay source/dev nen khong tu update.", parent=self)
            return   # dev chay 'python gui.py' -> khong tu update
        if manual:
            log.info("update: dang kiem tra thu cong...")
        def worker():
            try:
                info = updater.check_update(self._version)
            except Exception as e:
                # KHONG goi duoc server cap nhat (mang / GitHub CDN githubusercontent bi chan o VN /
                # SSL / timeout). Log RO de khong tuong nham "da moi nhat" (bug cu nuot exception).
                msg = ("Khong ket noi duoc server cap nhat. May nay co the bi chan GitHub/CDN, "
                       "loi DNS/proxy/cert, hoac antivirus/firewall chan download.\n\n"
                       f"Chi tiet: {e}")
                log.warning("update: KHONG KET NOI DUOC SERVER CAP NHAT: %s", e)
                if manual:
                    self.after(0, lambda m=msg: self._show_update_error("Update", m))
                return
            if info:
                log.info("update: CO BAN MOI v%s (dang hien %s) -> hoi user", info[0], self._version)
                self.after(0, lambda: self._prompt_update(*info))
            else:
                log.info("update: dang la ban moi nhat (v%s)", self._version)
                if manual:
                    self.after(0, lambda: messagebox.showinfo(
                        "Update", f"Dang la ban moi nhat: v{self._version}", parent=self))
        threading.Thread(target=worker, daemon=True).start()

    def _show_update_error(self, title, msg):
        try:
            from bot import updater
            manual_url = getattr(updater, "MANUAL_DOWNLOAD_URL", "")
        except Exception:
            manual_url = ""
        if not manual_url:
            messagebox.showerror(title, msg, parent=self)
            return
        top = tk.Toplevel(self)
        top.title(title)
        top.transient(self)
        top.resizable(False, False)
        box = ttk.Frame(top, padding=14)
        box.pack(fill="both", expand=True)
        tk.Label(box, text=msg, justify="left", wraplength=520).pack(anchor="w", pady=(0, 12))
        bar = ttk.Frame(box)
        bar.pack(fill="x")
        ttk.Button(bar, text="Mở Google Drive", command=lambda: webbrowser.open(manual_url, new=2)).pack(side="left")
        ttk.Button(bar, text="Đóng", command=top.destroy).pack(side="right")
        top.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - top.winfo_width()) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - top.winfo_height()) // 2)
        top.geometry(f"+{x}+{y}")
        top.grab_set()

    def _prompt_update(self, ver, url, notes):
        from tkinter import messagebox
        from bot import updater
        msg = f"Có bản mới: v{ver}\n\n{notes}\n\nCập nhật ngay? App sẽ tải bản mới rồi tự khởi động lại."
        if not messagebox.askyesno("Có bản cập nhật", msg, parent=self):
            return
        # cua so tien trinh nho
        top = tk.Toplevel(self); top.title("Đang cập nhật")
        top.geometry("360x90"); top.transient(self); top.resizable(False, False)
        lbl = tk.Label(top, text="Đang tải bản mới..."); lbl.pack(pady=14)
        bar = ttk.Progressbar(top, length=320, mode="determinate"); bar.pack()
        def on_prog(done, total):
            if total:
                self.after(0, lambda: (bar.config(value=done * 100 / total),
                                       lbl.config(text=f"Đang tải: {done//1024//1024}/{total//1024//1024} MB")))
        def dl():
            try:
                updater.download_and_swap(url, on_prog)   # ham nay tu thoat app khi xong
            except Exception as e:
                self.after(0, lambda: (top.destroy(),
                                       self._show_update_error("Lỗi cập nhật",
                                            f"Không tải được bản mới:\n{e}\n\nTải thủ công giúp.")))
        threading.Thread(target=dl, daemon=True).start()

    def _open_donate(self):
        top = tk.Toplevel(self)
        top.title("Donate")
        top.transient(self)
        top.resizable(False, False)
        box = ttk.Frame(top, padding=16)
        box.pack(fill="both", expand=True)

        ttk.Label(box, text="Nếu bạn happy với bot, bạn có thể donate ít xiền cafe ủng hộ bot",
                  wraplength=420, justify="center").pack(pady=(0, 10))

        try:
            img = _load_donate_qr_image()
            scale = max(1, (max(img.width(), img.height()) + 339) // 340)
            if scale > 1:
                img = img.subsample(scale, scale)
            top._donate_qr_img = img
            ttk.Label(box, image=img).pack(pady=(0, 12))
        except Exception as e:
            ttk.Label(box, text=f"Không mở được ảnh QR: {e}",
                      foreground="#b00020", wraplength=420).pack(pady=(0, 12))

        ttk.Label(box, text="Nếu bạn không happy với bot, bạn hãy join nhóm chat để chửi bot:",
                  wraplength=420, justify="center").pack()
        link = tk.Label(box, text=DONATE_CHAT_URL, fg="#0563c1", cursor="hand2")
        link.pack(pady=(4, 12))
        link.bind("<Button-1>", lambda _e: webbrowser.open(DONATE_CHAT_URL, new=2))
        try:
            link.configure(font=(link.cget("font"), 9, "underline"))
        except Exception:
            pass

        ttk.Button(box, text="Đóng", command=top.destroy).pack()
        top.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - top.winfo_width()) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - top.winfo_height()) // 2)
        top.geometry(f"+{x}+{y}")
        top.grab_set()

    # ---- cham tron trang thai (anh) cho tab party ----
    def _make_dot(self, color, size=13):
        img = tk.PhotoImage(width=size, height=size)   # nen trong suot
        cx = cy = (size - 1) / 2.0
        r = size / 2.0 - 1.5
        for y in range(size):
            for x in range(size):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    img.put(color, (x, y))
        return img

    # ---- style: lam tab party dang chon NOI BAT ----
    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")   # theme cho phep to mau tab (vista bo qua)
        except Exception:
            pass
        style.configure("TNotebook", background="#cfd4da", borderwidth=0)
        style.configure("TNotebook.Tab", padding=[16, 8], font=("", 10),
                        background="#c2c8d0", foreground="#445")
        style.map("TNotebook.Tab",
                  background=[("selected", "#1565c0"), ("active", "#9fb6d4")],
                  foreground=[("selected", "#ffffff"), ("active", "#102")],
                  font=[("selected", ("", 10, "bold"))],
                  expand=[("selected", [1, 3, 1, 0])])   # tab chon phinh to hon
        self._setup_check_indicator(style)

    def _setup_check_indicator(self, style):
        """Theme clam ve tick checkbox la dau 'X' -> de hieu nham la 'bo'. Doi sang dau 'v' (✓)
        bang anh indicator tu ve (o vuong + dau check xanh khi tick)."""
        try:
            pad = "#dcdad5"; box = "#ffffff"; border = "#6f6f6f"; ck = "#1565c0"
            W, H = 18, 14
            def base():
                img = tk.PhotoImage(width=W, height=H)
                img.put(pad, to=(0, 0, W, H))
                img.put(box, to=(0, 0, 14, 14))
                for x in range(14):
                    img.put(border, (x, 0)); img.put(border, (x, 13))
                for y in range(14):
                    img.put(border, (0, y)); img.put(border, (13, y))
                return img
            self._img_unchk = base()
            self._img_chk = base()
            pts = [(3, 7), (4, 8), (5, 9), (6, 10), (7, 8), (8, 6), (9, 5), (10, 4), (11, 3)]
            for (x, y) in pts:
                self._img_chk.put(ck, (x, y)); self._img_chk.put(ck, (x, y + 1))
                self._img_chk.put(ck, (x + 1, y))
            style.element_create("vchk.indicator", "image", self._img_unchk,
                                 ("selected", self._img_chk), sticky="")
            style.layout("TCheckbutton", [
                ("Checkbutton.padding", {"sticky": "nswe", "children": [
                    ("vchk.indicator", {"side": "left", "sticky": ""}),
                    ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                        ("Checkbutton.label", {"sticky": "nswe"})]})
                ]})
            ])
        except Exception:
            pass   # loi tao anh/style -> giu indicator mac dinh (X), khong crash GUI

    # ---- toolbar ----
    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Button(bar, text="▶ START TẤT CẢ", command=self._start_all).pack(side="left", padx=3)
        ttk.Button(bar, text="■ STOP TẤT CẢ", command=self._stop_all).pack(side="left", padx=3)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(bar, text="🗑 Xóa log", command=self._clear_log).pack(side="left", padx=3)
        ttk.Button(bar, text="📋 Log: Tất cả", command=self._log_show_all).pack(side="left", padx=3)
        ttk.Button(bar, text="Check Update", command=lambda: self._check_update(manual=True)).pack(side="left", padx=3)
        ttk.Button(bar, text="Mỗi party 1 chế độ → ⚙ Cấu hình",
                   command=self._open_config).pack(side="right", padx=8)
        ttk.Button(bar, text="Donate", command=self._open_donate).pack(side="right", padx=3)

    # ---- che tai khoan/ten (BAM vao header cot "Tai khoan"/"Nhan vat" de doi) ----
    # Tranh bi soi khi quay/share man hinh. 3 trang thai (ap dung CA bang LAN log moi):
    #   0=hien full | 1=che giua (s***01) | 2=an het -> doi ten theo THU TU acc (acc1, acc2,...)
    # Icon tren header bao trang thai. Mac dinh che giua.
    _privacy = 1
    _PRIV_ICON = ["👁", "👁‍🗨", "🙈"]   # 0 hien | 1 che giua | 2 doi so thu tu

    def _priv_head(self, col):
        return f"{self._HEADS[col]} {self._PRIV_ICON[getattr(self, '_privacy', 1)]}"

    def _toggle_privacy(self):
        self._privacy = (getattr(self, "_privacy", 1) + 1) % 3
        for tree in self.party_trees.values():
            try:
                tree.heading("acc", text=self._priv_head("acc"))
                tree.heading("char", text=self._priv_head("char"))
            except Exception:
                pass

    def _build_ordinal(self):
        """Map username -> ten thu tu acc1, acc2,... (theo thu tu party/acc) cho che do an het."""
        ordered = [u for pidx in range(len(config.PARTIES))
                   for (u, *_ ) in ctrl.party_accounts(pidx) if u and u.strip()]
        self._ordinal = {u: f"acc{i + 1}" for i, u in enumerate(ordered)}

    @staticmethod
    def _part(s):
        """Che giua: ky tu dau + 3 sao + 2 ky tu cuoi (s***01). Ngan qua -> che gon."""
        if len(s) <= 3:
            return s[0] + "***"
        return s[0] + "***" + s[-2:]

    def _mask_user(self, u):
        """Che USERNAME theo trang thai. 0=full | 1=s***01 | 2=ten thu tu (acc1, acc2,...)."""
        if not u or u == "-":
            return u
        st = getattr(self, "_privacy", 0)
        if st == 0:
            return u
        if st == 1:
            return self._part(u)
        return self._ordinal.get(u, self._part(u))   # 2 = so thu tu acc

    def _mask_char(self, c):
        """Che TEN NHAN VAT. 0=full | 1=s***01 | 2=so thu tu cua acc tuong ung (qua _char2user)."""
        if not c or c == "-":
            return c
        st = getattr(self, "_privacy", 0)
        if st == 0:
            return c
        if st == 1:
            return self._part(c)
        u = self._char2user.get(c)
        return self._ordinal.get(u, self._part(c)) if u else self._part(c)

    def _mask_label(self, label):
        """Che 1 label trong log (username hoac ten nhan vat)."""
        if label in getattr(self, "_ordinal", {}):
            return self._mask_user(label)
        if label in self._char2user:
            return self._mask_char(label)
        return self._mask_user(label)

    def _mask_log_line(self, line, label):
        """Doi [label] dau dong log theo trang thai privacy (chi cho dong MOI luc hien)."""
        if getattr(self, "_privacy", 0) == 0 or not label:
            return line
        return line.replace(f"[{label}]", f"[{self._mask_label(label)}]", 1)

    def _char_cell(self, s):
        """Cot Nhan vat: 'tenNV_lvchar_tenPet_lvPet'. Privacy CHI che ten NV (lv + pet luon hien).
        Khong co pet -> 'tenNV_lvchar'. Chua load lv -> chi 'tenNV'."""
        parts = [self._mask_char(s.get("char") or "-")]
        if s.get("char_level"):
            parts.append(str(s["char_level"]))
        if s.get("pet_name"):
            parts.append(s["pet_name"])
            if s.get("pet_level"):
                parts.append(str(s["pet_level"]))
        return "_".join(parts)

    # ---- BAM header Kenh -> doi kenh ca party | BAM header Map -> teleport thanh ----
    def _popup_channels(self, pidx):
        import tkinter.messagebox as mb
        # hoi server list kenh (~3s) trong thread -> roi mo popup tren main thread (tranh treo GUI)
        def _work():
            chans = ctrl.get_channel_list(pidx)
            self.after(0, lambda: self._show_channel_popup(pidx, chans))
        threading.Thread(target=_work, daemon=True).start()

    def _show_channel_popup(self, pidx, chans):
        import tkinter.messagebox as mb
        if not chans:
            mb.showwarning("Đổi kênh", "Không lấy được danh sách kênh.")
            return
        win = tk.Toplevel(self); win.title(f"P{pidx + 1} · Đổi kênh")
        win.transient(self); win.grab_set()
        ttk.Label(win, text="Chọn kênh — cả party sẽ HỦY PARTY + chuyển kênh rồi tiếp tục chạy như trong setting:",
                  padding=8).pack(anchor="w")
        items = sorted(chans.items(), key=lambda kv: kv[1][0])   # it nguoi nhat truoc
        lb = tk.Listbox(win, width=34, height=min(14, max(3, len(items))), font=("Consolas", 10))
        lb.pack(fill="both", expand=True, padx=8)
        for ch, (cur, cap) in items:
            lb.insert("end", f"Kênh {ch:>3}   —   {cur}/{cap} người")
        def _go():
            sel = lb.curselection()
            if sel:
                threading.Thread(target=ctrl.party_switch_channel,
                                 args=(pidx, items[sel[0]][0]), daemon=True).start()
            win.destroy()
        ttk.Button(win, text="✔ Chuyển sang kênh này", command=_go).pack(pady=8)

    def _popup_cities(self, pidx):
        import tkinter.messagebox as mb
        if not self.cities:
            mb.showwarning("Teleport thành", "Không có danh sách thành.")
            return
        win = tk.Toplevel(self); win.title(f"P{pidx + 1} · Teleport về thành")
        win.transient(self); win.grab_set()
        ttk.Label(win, text="Chọn thành — cả party sẽ HỦY PARTY + teleport rồi tiếp tục chạy như trong setting:",
                  padding=8).pack(anchor="w")
        mode = config.PARTY_CONFIG.get(pidx, {}).get("mode")
        allow_route = mode in ("city", "stand")
        extra_rows = 1 if allow_route else 0
        lb = tk.Listbox(win, width=38, height=min(17, max(4, len(self.cities) + extra_rows)), font=("", 10))
        lb.pack(fill="both", expand=True, padx=8)
        if allow_route:
            lb.insert("end", "Đi từ map AAA đến map BBB")
        for (cid, f, n) in self.cities:
            lb.insert("end", n)
        def _go():
            sel = lb.curselection()
            if sel:
                offset = 1 if allow_route else 0
                if allow_route and sel[0] == 0:
                    win.destroy()
                    self._popup_route_maps(pidx)
                    return
                cid, f, n = self.cities[sel[0] - offset]
                threading.Thread(target=ctrl.party_teleport_city,
                                 args=(pidx, cid, f), daemon=True).start()
            win.destroy()
        lb.bind("<Double-1>", lambda _e: _go())
        ttk.Button(win, text="Chọn", command=_go).pack(pady=8)

    def _popup_route_maps(self, pidx):
        import tkinter.messagebox as mb
        win = tk.Toplevel(self); win.title(f"P{pidx + 1} · Đi map")
        win.transient(self); win.grab_set()
        box = ttk.Frame(win, padding=12)
        box.pack(fill="both", expand=True)
        ttk.Label(
            box,
            text="AAA để trống = tự chọn thành gần BBB nhất.",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(box, text="Map AAA:").grid(row=1, column=0, sticky="e", padx=(0, 6), pady=4)
        src_var = tk.StringVar()
        dst_var = tk.StringVar()
        ttk.Entry(box, textvariable=src_var, width=18).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(box, text="Map BBB:").grid(row=2, column=0, sticky="e", padx=(0, 6), pady=4)
        dst_entry = ttk.Entry(box, textvariable=dst_var, width=18)
        dst_entry.grid(row=2, column=1, sticky="w", pady=4)

        def _start():
            try:
                src = int(src_var.get().strip()) if src_var.get().strip() else 0
                dst = int(dst_var.get().strip())
            except ValueError:
                mb.showerror("Đi map", "Map AAA/BBB phải là số. AAA có thể để trống.", parent=win)
                return
            if dst <= 0:
                mb.showerror("Đi map", "Map BBB không hợp lệ.", parent=win)
                return
            threading.Thread(target=ctrl.party_route_maps,
                             args=(pidx, src, dst), daemon=True).start()
            win.destroy()

        row = ttk.Frame(box)
        row.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(row, text="Bắt đầu kéo map", command=_start).pack(side="left", padx=4)
        ttk.Button(row, text="Hủy", command=win.destroy).pack(side="left", padx=4)
        dst_entry.focus_set()

    # ---- tabs per party ----
    def _build_tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="x", expand=False, padx=6, pady=4)   # bang gon -> log chiem phan lon
        self.nb.bind("<Double-1>", self._on_tab_dblclick)      # double-click tab -> mo Setting party do
        self.party_trees = {}   # pidx -> Treeview
        self._populate_tabs()

    _COLS = ("acc", "char", "role", "run", "map", "ch", "party", "dg", "combat")
    _HEADS = {"acc": "Tài khoản", "char": "Nhân vật", "role": "Vai trò", "run": "Trạng thái",
              "map": "Map", "ch": "Kênh", "party": "Trong PT", "dg": "DG còn", "combat": "Đánh"}
    _WIDTHS = {"acc": 70, "char": 190, "role": 70, "run": 90, "map": 130, "ch": 50,
               "party": 70, "dg": 70, "combat": 55}
    PARTIES_PER_GROUP = 10   # 1-10 party = 1 tab; 11-20 = 2 tab; ... 91-100 = 10 tab

    def _populate_tabs(self):
        import math
        for tab in self.nb.tabs():
            self.nb.forget(tab)
        self.party_trees = {}       # pidx -> Treeview
        self.party_subframes = {}   # pidx -> sub-tab frame (cham trang thai party qua sub_nb.tab)
        self.group_nb = {}          # gidx -> sub-Notebook (chua cac party tab)
        self.group_frames = {}      # gidx -> group tab frame (cham trang thai group)
        self.group_members = {}     # gidx -> [pidx,...] (thu tu party trong group)
        self.group_of = {}          # pidx -> gidx
        self.group_first = {}       # gidx -> pidx dau (double-click mo config)
        eligible = [p for p in range(len(config.PARTIES)) if ctrl.party_accounts(p)]
        n = len(eligible)
        if n == 0:
            return
        n_groups = max(1, math.ceil(n / self.PARTIES_PER_GROUP))
        gsize = math.ceil(n / n_groups)   # chia DEU cac party vao group
        for gidx in range(n_groups):
            members = eligible[gidx * gsize:(gidx + 1) * gsize]
            if not members:
                continue
            gtab = ttk.Frame(self.nb)
            self.nb.add(gtab, text=f"Nhóm {gidx + 1} (P{members[0] + 1}-P{members[-1] + 1})",
                        image=self._dot_off, compound="left")
            self.group_frames[gidx] = gtab
            self.group_first[gidx] = members[0]
            self.group_members[gidx] = members
            # SUB-NOTEBOOK: moi party = 1 sub-tab (nhu cu) -> khong xep doc, khong lag
            sub = ttk.Notebook(gtab)
            sub.pack(fill="both", expand=True, pady=(2, 0))
            sub.bind("<<NotebookTabChanged>>", self._on_party_tab)
            sub.bind("<Double-1>", self._on_party_dblclick)   # double-click sub-tab -> config party
            self.group_nb[gidx] = sub
            for pidx in members:
                self.group_of[pidx] = gidx
                self._build_party_tab(sub, pidx)

    def _build_party_tab(self, sub_nb, pidx):
        accs = ctrl.party_accounts(pidx)
        pmode = config.PARTY_CONFIG.get(pidx, {}).get("mode", "?")
        mlbl = {"digioi": "Dị Giới", "train": "Train map", "city": "Về thành",
                "stand": "Đứng yên", "event": "Event", "cleanbag": "Dọn túi"}.get(pmode, pmode)
        frame = ttk.Frame(sub_nb, padding=4)
        sub_nb.add(frame, text=f"P{pidx + 1} · {mlbl} ({len(accs)})",
                   image=self._dot_off, compound="left")
        self.party_subframes[pidx] = frame
        btns = ttk.Frame(frame); btns.pack(fill="x", pady=(0, 4))
        ttk.Button(btns, text="▶ Start party",
                   command=lambda p=pidx: self._start_party(p)).pack(side="left", padx=2)
        ttk.Button(btns, text="■ Stop party",
                   command=lambda p=pidx: self._stop_party(p)).pack(side="left", padx=2)
        ttk.Separator(btns, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(btns, text="▶ Start acc chọn",
                   command=lambda p=pidx: self._start_sel(p)).pack(side="left", padx=2)
        ttk.Button(btns, text="■ Stop acc chọn",
                   command=lambda p=pidx: self._stop_sel(p)).pack(side="left", padx=2)
        ttk.Separator(btns, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(btns, text="🎟 Nhập giftcode",
                   command=lambda p=pidx: self._redeem_giftcode(p)).pack(side="left", padx=2)
        tree = ttk.Treeview(frame, columns=self._COLS, show="headings", height=max(len(accs), 3))
        for col in self._COLS:
            if col in ("acc", "char"):   # BAM header de che/hien tai khoan + ten (3 trang thai)
                tree.heading(col, text=self._priv_head(col), command=self._toggle_privacy)
            elif col == "ch":            # BAM header Kenh -> doi kenh ca party
                tree.heading(col, text=self._HEADS[col] + " ↧",
                             command=lambda p=pidx: self._popup_channels(p))
            elif col == "map":           # BAM header Map -> teleport ca party ve thanh
                tree.heading(col, text=self._HEADS[col] + " ↧",
                             command=lambda p=pidx: self._popup_cities(p))
            else:
                tree.heading(col, text=self._HEADS[col])
            tree.column(col, width=self._WIDTHS[col], anchor="center")
        tree.column("acc", anchor="w"); tree.column("char", anchor="w")
        tree.tag_configure("on", foreground="#0a0")
        tree.tag_configure("off", foreground="#999")
        tree.tag_configure("qs", foreground="#c25e00")
        tree.bind("<<TreeviewSelect>>", lambda e, p=pidx: self._on_acc_select(p))
        tree.pack(fill="x", expand=False)
        for (u, p, is_leader, is_picker) in accs:
            role = "LEADER" if is_leader else ("picker" if is_picker else "member")
            tree.insert("", "end", iid=u, values=(u, "", role, "Tắt", "-", "-", "-", "-", "-"),
                        tags=("off",))
        self.party_trees[pidx] = tree

    def _on_party_tab(self, event):
        # doi sub-tab party -> loc log party do
        sub = event.widget
        for gidx, nb in self.group_nb.items():
            if str(nb) == str(sub):
                members = self.group_members.get(gidx, [])
                try:
                    i = nb.index(nb.select())
                except Exception:
                    return
                if 0 <= i < len(members):
                    self._filter_party(members[i])
                return

    def _filter_party(self, pidx):
        users = set(u for (u, *_ ) in ctrl.party_accounts(pidx))
        self._set_log_filter(users, f"Party {pidx + 1}")

    def _filter_party(self, pidx):
        users = set(u for (u, *_ ) in ctrl.party_accounts(pidx))
        self._set_log_filter(users, f"Party {pidx + 1}")

    # ---- log panel ----
    def _build_log(self):
        self._log_frame = ttk.LabelFrame(self, text="Log — Tất cả", padding=4)
        self._log_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))   # chiem phan lon
        self.log_txt = tk.Text(self._log_frame, height=20, wrap="none", bg="#111", fg="#ddd",
                               font=("Consolas", 9))
        sb = ttk.Scrollbar(self._log_frame, command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.log_txt.pack(side="left", fill="both", expand=True)

    # ---- log filter ----
    def _label_to_user(self, label):
        """Tu label [xxx] trong log -> username. label co the la username hoac ten nhan vat."""
        if label is None:
            return None
        if label in self._all_usernames:
            return label
        return self._char2user.get(label)

    def _line_visible(self, label):
        if self.log_filter is None:
            return True
        if label is None:        # dong he thong (vd ">>> PARTY N DA THOAT HET...") -> LUON hien
            return True
        u = self._label_to_user(label)
        return u is not None and u in self.log_filter

    def _set_log_filter(self, users, title):
        self.log_filter = users
        self._log_frame.configure(text=f"Log — {title}")
        self._rerender_log()

    def _rerender_log(self):
        self.log_txt.delete("1.0", "end")
        for line, label in self.log_buffer:
            if self._line_visible(label):
                self.log_txt.insert("end", self._mask_log_line(line, label) + "\n")
        self.log_txt.see("end")

    def _log_show_all(self):
        self._set_log_filter(None, "Tất cả")

    def _clear_log(self):
        self.log_buffer.clear()
        self.log_txt.delete("1.0", "end")

    def _on_tab_changed(self, _e=None):
        # doi GROUP tab -> loc log theo party DANG CHON trong group do
        try:
            gidx = self.nb.index(self.nb.select())
        except Exception:
            return
        sub = self.group_nb.get(gidx)
        members = self.group_members.get(gidx, [])
        if sub is not None and members:
            try:
                i = sub.index(sub.select())
                if 0 <= i < len(members):
                    self._filter_party(members[i])
            except Exception:
                pass

    def _on_acc_select(self, pidx):
        tree = self.party_trees.get(pidx)
        if not tree:
            return
        sel = tree.selection()
        if not sel:
            return
        u = sel[0]
        char = ""
        c = ctrl.account_clients.get(u)
        if c is not None and c.char_name:
            char = f" / {c.char_name}"
        self._set_log_filter({u}, f"{u}{char}")

    # ---- actions ----
    def _start_all(self):
        threading.Thread(target=ctrl.start_all, daemon=True).start()

    def _stop_all(self):
        threading.Thread(target=ctrl.stop_all, daemon=True).start()

    def _start_party(self, pidx):
        threading.Thread(target=ctrl.start_party, args=(pidx,), daemon=True).start()

    def _stop_party(self, pidx):
        threading.Thread(target=ctrl.stop_party, args=(pidx,), daemon=True).start()

    def _redeem_giftcode(self, pidx):
        # dem so acc dang chay cua party de bao cho nguoi dung
        running = [u for (u, _p, _l, _pk) in ctrl.party_accounts(pidx)
                   if ctrl.is_account_running(u)]
        if not running:
            messagebox.showwarning("Giftcode",
                                   f"Party {pidx + 1} chưa có acc nào đang chạy.\n"
                                   "Hãy Start party trước rồi mới nhập giftcode.")
            return
        code = simpledialog.askstring(
            "Nhập giftcode",
            f"Nhập giftcode cho Party {pidx + 1} ({len(running)} acc đang chạy):",
            parent=self)
        if not code or not code.strip():
            return
        code = code.strip()
        threading.Thread(target=ctrl.redeem_giftcode_party, args=(pidx, code),
                         daemon=True).start()
        messagebox.showinfo("Giftcode",
                            f"Đang nhập '{code}' cho {len(running)} acc của Party {pidx + 1}.\n"
                            "Quà về qua mail → bot tự nhận. Xem log để biết kết quả.")

    def _start_sel(self, pidx):
        tree = self.party_trees[pidx]
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Chọn acc", "Hãy chọn 1 dòng acc trước."); return
        accs = {u: (p, lead, pick) for (u, p, lead, pick) in ctrl.party_accounts(pidx)}
        for u in sel:
            if u in accs:
                p, lead, pick = accs[u]
                threading.Thread(target=ctrl.start_account, args=(u, p, pidx, lead, pick),
                                 daemon=True).start()

    def _stop_sel(self, pidx):
        tree = self.party_trees[pidx]
        for u in tree.selection():
            threading.Thread(target=ctrl.stop_account, args=(u,), daemon=True).start()

    # ---- refresh status ----
    def _refresh(self):
        # cap nhat map ten nhan vat -> username (de loc log theo acc/party)
        for u, c in list(ctrl.account_clients.items()):
            if c is not None and c.char_name:
                self._char2user[c.char_name] = u
        group_run = {}    # gidx -> so acc dang chay
        group_total = {}  # gidx -> tong so acc
        for pidx, tree in self.party_trees.items():
            any_running = False
            p_total = 0; p_run = 0   # dem acc cua party de quyet dinh mau cham
            # Di Gioi SOLO: khong co khai niem leader/member/quan su that (moi acc chay doc lap) ->
            # hien "solo" cho de hieu, tranh hieu lam la co lap party/phu thuoc leader.
            pcfg_gui = config.PARTY_CONFIG.get(pidx, {})
            is_digioi_solo = (pcfg_gui.get("mode") == "digioi" and pcfg_gui.get("digioi_mode") == "solo")
            for (u, p, is_leader, is_picker) in ctrl.party_accounts(pidx):
                if not tree.exists(u):
                    continue
                p_total += 1
                s = ctrl.account_status(u)
                if s["running"]:
                    any_running = True
                    p_run += 1
                if is_digioi_solo:
                    role = "solo"
                elif s.get("strategist"):
                    role = "Quân sư"
                elif is_leader:
                    role = "LEADER"
                elif is_picker:
                    role = "picker"
                else:
                    role = "member"
                run = "● CHẠY" if s["running"] else "Tắt"
                dg = f"{s['dg_remain']}p" if s["dg_remain"] is not None else "-"
                tag = "qs" if (s["running"] and s.get("strategist")) else \
                      ("on" if s["running"] else "off")
                tree.item(u, values=(self._mask_user(u), self._char_cell(s), role, run, _map_name(s["map"]),
                                     s["channel"] if s["channel"] else "-",
                                     "✔" if s["in_party"] else "-", dg,
                                     "⚔" if s["combat"] else "-"),
                          tags=(tag,))
            # cham trang thai TUNG PARTY (sub-tab trong group):
            #   xanh = DU acc chay | vang = chay MOT PHAN (thieu) | xam = tat het
            gidx = self.group_of.get(pidx)
            subf = self.party_subframes.get(pidx)
            sub = self.group_nb.get(gidx)
            p_dot = (self._dot_off if p_run == 0 else
                     (self._dot_on if p_run >= p_total and p_total > 0 else self._dot_warn))
            if sub is not None and subf is not None:
                try:
                    sub.tab(subf, image=p_dot)
                except Exception:
                    pass
            group_run[gidx] = group_run.get(gidx, 0) + p_run
            group_total[gidx] = group_total.get(gidx, 0) + p_total
        # cham trang thai TUNG GROUP TAB: xanh = du | vang = mot phan | xam = tat
        for gidx, gframe in self.group_frames.items():
            gr = group_run.get(gidx, 0); gt = group_total.get(gidx, 0)
            g_dot = (self._dot_off if gr == 0 else
                     (self._dot_on if gr >= gt and gt > 0 else self._dot_warn))
            try:
                self.nb.tab(gframe, image=g_dot)
            except Exception:
                pass
        self.after(1500, self._refresh)

    def _drain_log(self):
        n = 0
        while n < 300:
            try:
                line = _log_queue.get_nowait()
            except queue.Empty:
                break
            m = _LABEL_RE.match(line)
            label = m.group(1) if m else None
            self.log_buffer.append((line, label))
            if self._line_visible(label):
                self.log_txt.insert("end", self._mask_log_line(line, label) + "\n")
            n += 1
        if n:
            cnt = int(self.log_txt.index("end-1c").split(".")[0])
            if cnt > 2000:
                self.log_txt.delete("1.0", f"{cnt - 2000}.0")
            self.log_txt.see("end")
        self.after(300, self._drain_log)

    # ---- config editor ----
    def _group_cur_party(self, gidx):
        """pidx cua party DANG CHON trong group gidx (fallback party dau)."""
        sub = self.group_nb.get(gidx)
        members = self.group_members.get(gidx, [])
        if sub is not None and members:
            try:
                i = sub.index(sub.select())
                if 0 <= i < len(members):
                    return members[i]
            except Exception:
                pass
        return self.group_first.get(gidx, 0)

    def _on_tab_dblclick(self, event):
        # double-click GROUP tab -> mo Setting o party DANG CHON cua group do
        try:
            gidx = self.nb.index("@%d,%d" % (event.x, event.y))
        except Exception:
            return   # double-click ngoai vung tab header -> bo qua
        ConfigDialog(self, open_pidx=self._group_cur_party(gidx))

    def _on_party_dblclick(self, event):
        # double-click PARTY sub-tab -> mo Setting cua party do
        sub = event.widget
        for gidx, nb in self.group_nb.items():
            if str(nb) == str(sub):
                try:
                    i = nb.index("@%d,%d" % (event.x, event.y))
                except Exception:
                    return
                members = self.group_members.get(gidx, [])
                if 0 <= i < len(members):
                    ConfigDialog(self, open_pidx=members[i])
                return

    def _open_config(self):
        # mo Setting o party DANG CHON cua group dang chon
        try:
            gidx = self.nb.index(self.nb.select())
        except Exception:
            gidx = 0
        ConfigDialog(self, open_pidx=self._group_cur_party(gidx))

    def reload_config(self):
        """Nap lai accounts.json + dung lai tab. TU STOP acc nao config (mode/map) bi DOI
        (khong tu Start - de Anh chu dong Start lai khi muon)."""
        def _sigs():
            s = {}
            for u, pidx in config.ACCOUNT_PARTY.items():
                pc = config.PARTY_CONFIG.get(pidx, {})
                s[u] = (pc.get("server"), pc.get("mode"), pc.get("start_city_id"),
                        pc.get("mob_index"), pc.get("city_flag"), pc.get("do_daily", pc.get("do_dungeon")),
                        pc.get("use_phuc_than"), pc.get("use_digioi_ho_phu"))
            return s
        old = _sigs()
        importlib.reload(config)   # doc lai accounts.json -> PARTIES/PARTY_CONFIG moi
        new = _sigs()
        # acc dang chay ma config doi (hoac bi xoa khoi config) -> STOP
        changed = [u for u in list(ctrl.account_clients)
                   if ctrl.is_account_running(u) and old.get(u) != new.get(u)]
        for u in changed:
            ctrl.stop_account(u)
        self._all_usernames = set(u for pidx in range(len(config.PARTIES))
                                  for (u, *_ ) in ctrl.party_accounts(pidx))
        self._build_ordinal()
        self._populate_tabs()
        if changed:
            messagebox.showinfo("Đã nạp lại",
                                "Đã áp dụng cấu hình mới.\nĐÃ STOP %d acc bị đổi config — "
                                "bấm Start lại khi muốn chạy theo cấu hình mới." % len(changed))

    def _on_close(self):
        if messagebox.askokcancel("Thoát", "Dừng tất cả acc và thoát?"):
            try: ctrl.stop_all()
            except Exception: pass
            self.destroy()


# ---------------- Config dialog (per-party, dropdown) ----------------
_BASE = _app_dir()   # dev=project root | frozen=thu muc canh .exe (JSON config sua duoc)


def _load_json(name):
    try:
        with open(os.path.join(_BASE, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


MODE_OPTIONS = [
    ("digioi", "Train Dị Giới"),
    ("train", "Train map"),
    ("city", "Tập trung về thành (đứng yên)"),
    ("stand", "Login đâu đứng yên đó"),
    ("event", "Event (tele tới map event, đứng yên chờ mời tay)"),
    ("cleanbag", "Dọn dẹp túi đồ (chưa làm)"),
]
_MODE_LABEL = dict(MODE_OPTIONS)
_LABEL_MODE = {v: k for k, v in MODE_OPTIONS}


class PartyConfigFrame(ttk.Frame):
    """1 tab cau hinh 1 party: mode (dropdown) + map/quai/thanh (dropdown) + acc."""
    _PW_MASK = "******"   # placeholder pass da luu (giau pass that khi mo lai Settings)
    def __init__(self, master, party, train_maps, cities, servers, on_apply_advanced_to_all=None,
                 on_apply_di_gioi_level=None):
        super().__init__(master, padding=8)
        self.train_maps = train_maps   # list (map_id, name, mobs)
        self.cities = cities           # list (city_id, flag, name)
        self.servers = servers         # list (key, label)
        self.on_apply_advanced_to_all = on_apply_advanced_to_all
        self.on_apply_di_gioi_level = on_apply_di_gioi_level
        self._preset = party or {}

        srow = ttk.Frame(self); srow.pack(fill="x", pady=4)
        ttk.Label(srow, text="Server:", width=10).pack(side="left")
        self.server_var = tk.StringVar()
        cur_srv = self._preset.get("server", servers[0][0] if servers else "trieu_van")
        self.server_var.set(dict(servers).get(cur_srv, servers[0][1] if servers else cur_srv))
        ttk.Combobox(srow, textvariable=self.server_var, state="readonly", width=22,
                     values=[lbl for _, lbl in servers]).pack(side="left")
        ttk.Button(srow, text="⚙ Cài đặt nâng cao",
                   command=self._open_advanced_settings).pack(side="right")

        row = ttk.Frame(self); row.pack(fill="x", pady=4)
        ttk.Label(row, text="Chế độ:", width=10).pack(side="left")
        self.mode_var = tk.StringVar(value=_MODE_LABEL.get(self._preset.get("mode", "digioi"),
                                                           "Train Dị Giới"))
        cb = ttk.Combobox(row, textvariable=self.mode_var, state="readonly", width=34,
                          values=[lbl for _, lbl in MODE_OPTIONS])
        cb.pack(side="left"); cb.bind("<<ComboboxSelected>>", lambda e: self._on_mode_change())
        # "Kieu chay" (Di Gioi: Party/Solo) - dat NGANG HANG voi Che do (ben phai), CHI hien khi
        # mode=digioi (an/hien qua pack/pack_forget trong _render_dyn, KHONG tao lai trong dyn frame
        # rieng vi user muon o SAME ROW voi Che do, khong phai xuong dong duoi).
        self.digioi_kind_lbl = ttk.Label(row, text="  │  Kiểu chạy:")
        self.digioi_kind_var = tk.StringVar()
        self.digioi_kind_cb = ttk.Combobox(row, textvariable=self.digioi_kind_var, state="readonly",
                                           width=24, values=["Party (lập đội chung)", "Solo (mỗi acc chạy riêng)"])
        def _on_digioi_kind_change(_e=None):
            self.digioi_solo_var.set(self.digioi_kind_var.get().startswith("Solo"))
            self._update_no_leader_visibility()
        self.digioi_kind_cb.bind("<<ComboboxSelected>>", _on_digioi_kind_change)

        self.dyn = ttk.Frame(self); self.dyn.pack(fill="x", pady=6)
        self.map_var = tk.StringVar(); self.mob_var = tk.StringVar(); self.city_var = tk.StringVar()
        self.map_cb = self.mob_cb = self.city_cb = None
        # EVENT: list (key, label) tu events.json -> picker khi mode=event
        self.events = [(k, v.get("label", k)) for k, v in (getattr(config, "EVENTS", {}) or {}).items()]
        self.event_var = tk.StringVar(); self.event_cb = None
        # Di Gioi: party (mac dinh, giu nguyen hanh vi cu - lap party chung, dong bo kenh) vs solo
        # (moi acc chay rieng le, khong lap party, khong dong bo kenh - dung khi acc khong can/khong
        # muon gop chung, vd khac nick khong lien quan nhau).
        self.digioi_solo_var = tk.BooleanVar(value=(self._preset.get("digioi_mode") == "solo"))

        # KHONG co chu PT: slot 0 = ("","") -> member tu dung cho leader ngoai/tay moi.
        accs = self._preset.get("accounts", [])
        no_leader = bool(accs) and not (accs[0].get("u", "").strip())
        shown = accs[1:] if no_leader else accs
        # Hang: [Khong co chu PT] ... [White list rieng party nay]
        nlrow = ttk.Frame(self); nlrow.pack(fill="x", pady=(2, 0))
        self.no_leader_var = tk.BooleanVar(value=no_leader)
        # Di Gioi SOLO: khong lap party that -> "chu PT" khong co y nghia gi, an checkbox nay cho
        # gon (xem _update_no_leader_visibility, goi lai moi khi doi "Kieu chay").
        self.no_leader_cb = ttk.Checkbutton(
            nlrow, text="Không có chủ PT (member tự đứng, chờ leader ngoài/tay mời)",
            variable=self.no_leader_var)
        self.no_leader_cb.pack(side="left")
        wl = self._preset.get("leaders", [])
        self.wl_lbl = ttk.Label(nlrow, text="  │  White list riêng:")
        self.wl_lbl.pack(side="left")
        self.leaders_var = tk.StringVar(value=", ".join(wl) if isinstance(wl, list) else str(wl or ""))
        self.wl_entry = ttk.Entry(nlrow, textvariable=self.leaders_var)
        self.wl_entry.pack(side="left", fill="x", expand=True, padx=4)

        # Cac setting IT KHI DOI (vd daily quest) gom vao dialog "Cai dat nang cao" (nut o hang
        # Server) thay vi 1 checkbox rieng ngay day - tranh bang cau hinh party bi day dai/roi
        # khi sau nay them setting moi. Bien van giu o day de _save()/_gather doc binh thuong.
        self.daily_var = tk.BooleanVar(value=self._preset.get("do_daily", self._preset.get("do_dungeon", True)))
        # Su dung Phuc Than: mac dinh KHONG tick (user tu bat khi can) - logic dung item nay
        # se lam sau, hien tai chi luu setting.
        self.use_phuc_than_var = tk.BooleanVar(value=bool(self._preset.get("use_phuc_than", False)))
        # Di Gioi Ho Phu: mac dinh KHONG tick. Khi bat, chi mode Di Gioi moi dung va chi
        # khi timer con <15 phut (run_party_digioi.py check luc login + moi 10p).
        self.use_digioi_ho_phu_var = tk.BooleanVar(value=bool(self._preset.get("use_digioi_ho_phu", False)))
        # Danh boss QD: mac dinh CO tick (giu hanh vi cu - truoc gio luon danh). User tat khi
        # khong muon acc nay danh boss quan doan.
        self.fight_boss_var = tk.BooleanVar(value=bool(self._preset.get("fight_legion_boss", True)))
        # Van tieu: mac dinh CO tick (giu hanh vi cu - truoc gio luon lam). Tat -> khong nhan qua
        # escort + khong gui pet van tieu + khong hen gio check lai.
        self.van_tieu_var = tk.BooleanVar(value=bool(self._preset.get("do_van_tieu", True)))
        # Mua shop (mac dinh TAT): Di Gioi Ho Phu (mua 3/ngay), Trieu Goi Bao Hop (mua 1/ngay khi
        # xu > nguong). 1 lan/ngay/acc (luu ben shop_state.json).
        self.buy_ho_phu_var = tk.BooleanVar(value=bool(self._preset.get("buy_ho_phu", False)))
        self.buy_bao_hop_var = tk.BooleanVar(value=bool(self._preset.get("buy_bao_hop", False)))
        self.bao_hop_xu_var = tk.StringVar(value=str(self._preset.get("bao_hop_xu_threshold", 1000000)))
        # Cap quai Di Gioi: luu idx 1..15; UI hien theo cap (10..180). Mac dinh idx 2 = cap 25.
        _dg_idx = int(self._preset.get("di_gioi_level", 2))
        self.di_gioi_level_var = tk.StringVar(value=str(_DG_LEVELS[_dg_idx - 1] if 1 <= _dg_idx <= 15 else 25))

        ttk.Label(self, text="Acc (TICK = dùng, BỎ TICK = bỏ qua). Dòng đầu đã tick = chủ PT "
                  "(trừ khi tick ô trên). TỐI ĐA 5 acc/party:").pack(anchor="w")
        # vung CUON chua cac dong acc (checkbox + user + pass + nut xoa)
        _wrap = ttk.Frame(self); _wrap.pack(fill="both", expand=True)
        self._acc_canvas = tk.Canvas(_wrap, height=160, highlightthickness=0)
        _sb = ttk.Scrollbar(_wrap, orient="vertical", command=self._acc_canvas.yview)
        self._acc_inner = ttk.Frame(self._acc_canvas)
        self._acc_inner.bind("<Configure>",
                             lambda e: self._acc_canvas.configure(scrollregion=self._acc_canvas.bbox("all")))
        self._acc_canvas.create_window((0, 0), window=self._acc_inner, anchor="nw")
        self._acc_canvas.configure(yscrollcommand=_sb.set)
        self._acc_canvas.pack(side="left", fill="both", expand=True)
        _sb.pack(side="right", fill="y")
        self.acc_rows = []
        for a in shown:
            u = a.get("u", ""); on = a.get("on", True)
            if u.lstrip().startswith("#"):   # tuong thich co che '#' cu -> bo tick
                on = False; u = u.lstrip().lstrip("#").strip()
            self._add_acc_row(u, a.get("p", ""), on, a.get("heal"), a.get("settings"))
        ttk.Button(self, text="➕ Thêm dòng acc",
                   command=lambda: self._add_acc_row("", "", True)).pack(anchor="w", pady=(2, 0))
        self._render_dyn()

    def _add_acc_row(self, u="", p="", on=True, heal=None, settings=None):
        fr = ttk.Frame(self._acc_inner); fr.pack(fill="x", pady=1)
        on_var = tk.BooleanVar(value=bool(on))
        ttk.Checkbutton(fr, variable=on_var).pack(side="left")
        e_u = ttk.Entry(fr, width=16, font=("Consolas", 10)); e_u.pack(side="left", padx=(0, 4))
        e_u.insert(0, u)
        e_p = ttk.Entry(fr, width=14, font=("Consolas", 10)); e_p.pack(side="left", padx=(0, 4))
        # heal: {hp_char,sp_char,hp_pet,sp_pet} (0-1). None/thieu key -> dung nguong chung.
        # settings: config rieng khac cua acc (battle rules, legacy flags...).
        row = {"on": on_var, "u": e_u, "p": e_p, "frame": fr, "_realp": p,
               "heal": dict(heal) if isinstance(heal, dict) else {},
               "settings": dict(settings) if isinstance(settings, dict) else {}}
        # Pass DA LUU -> hien placeholder '******' (giau pass that). Bam vao go thi xoa placeholder;
        # de trong khong go -> khoi phuc '******' (giu pass cu). Pass MOI (chua co) -> o trong, go ro.
        if p:
            e_p.insert(0, self._PW_MASK)
            def _fin(_e, ent=e_p):
                if ent.get() == self._PW_MASK:
                    ent.delete(0, "end")
            def _fout(_e, ent=e_p, rr=row):
                if not ent.get() and rr.get("_realp"):
                    ent.insert(0, self._PW_MASK)
            e_p.bind("<FocusIn>", _fin)
            e_p.bind("<FocusOut>", _fout)
        ttk.Button(fr, text="⚙", width=2, command=lambda: self._open_heal_dialog(row)).pack(side="left")
        ttk.Button(fr, text="Skill", width=5, command=lambda: self._open_skill_dialog(row)).pack(side="left")
        ttk.Button(fr, text="✕", width=2, command=lambda: self._del_acc_row(row)).pack(side="left")
        self.acc_rows.append(row)

    def _open_heal_dialog(self, row):
        """Popup chinh nguong hoi mau rieng acc: 4 % (HP char / SP char / HP pet / SP pet).
        Acc dang online -> hien so tuyet doi tuong ung (= round(% * max))."""
        uname = row["u"].get().strip()
        if not uname:
            messagebox.showinfo("Thiếu acc", "Nhập username trước đã."); return
        glob_hp = getattr(config, "HP_THRESHOLD", 0.4)
        glob_sp = getattr(config, "SP_THRESHOLD", 0.0)
        c = ctrl.account_clients.get(uname)
        st = c.state if (c is not None and getattr(c, "state", None)) else None
        # max tuong ung (0 = offline/chua biet)
        maxv = {
            "hp_char": st.char.hp_max if st else 0, "sp_char": st.char.sp_max if st else 0,
            "hp_pet": st.pet.hp_max if st else 0,  "sp_pet": st.pet.sp_max if st else 0,
        }
        win = tk.Toplevel(self); win.title(f"Hồi máu: {uname}"); win.resizable(False, False)
        win.transient(self.winfo_toplevel()); win.grab_set()
        rows = [("hp_char", "HP char", glob_hp), ("sp_char", "SP char", glob_sp),
                ("hp_pet", "HP pet", glob_hp),  ("sp_pet", "SP pet", glob_sp)]
        vars_ = {}
        ttk.Label(win, text="Hồi khi chỉ số TỤT DƯỚI ngưỡng %:").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 4))
        for i, (key, lbl, gdef) in enumerate(rows, start=1):
            ttk.Label(win, text=lbl + ":", width=9).grid(row=i, column=0, sticky="w", padx=(8, 2), pady=2)
            cur = row["heal"].get(key, gdef)
            v = tk.IntVar(value=int(round(cur * 100)))
            vars_[key] = v
            sp = tk.Spinbox(win, from_=0, to=100, width=5, textvariable=v)
            sp.grid(row=i, column=1, padx=2, pady=2)
            abs_lbl = ttk.Label(win, text="", width=14, foreground="#0a0")
            abs_lbl.grid(row=i, column=2, sticky="w", padx=(4, 8))
            def _upd(*_a, k=key, vv=v, l=abs_lbl):
                m = maxv[k]
                l.configure(text=(f"= {round(vv.get() / 100 * m)}" if m else "(offline)"))
            v.trace_add("write", _upd); _upd()
        def _save():
            row["heal"] = {k: max(0, min(100, vv.get())) / 100.0 for k, vv in vars_.items()}
            row["settings"].pop("char_defend", None)
            win.destroy()
        def _reset():
            for k, vv in vars_.items():
                vv.set(int(round((glob_hp if k.startswith("hp") else glob_sp) * 100)))
        bb = ttk.Frame(win); bb.grid(row=len(rows) + 1, column=0, columnspan=3, pady=8)
        ttk.Button(bb, text="↺ Mặc định chung", command=_reset).pack(side="left", padx=4)
        ttk.Button(bb, text="💾 Lưu", command=_save).pack(side="left", padx=4)
        ttk.Button(bb, text="Hủy", command=win.destroy).pack(side="left", padx=4)

    def _open_skill_dialog(self, row):
        """Popup rule battle rieng tung acc: Dieu kien -> Skill/action -> Target."""
        uname = row["u"].get().strip()
        if not uname:
            messagebox.showinfo("Thiếu acc", "Nhập username trước đã."); return
        settings = row.setdefault("settings", {})
        battle = settings.get("battle") if isinstance(settings.get("battle"), dict) else {}

        c = ctrl.account_clients.get(uname)
        st = c.state if (c is not None and getattr(c, "state", None)) else None
        live_skills = {
            "char": sorted(getattr(st, "skills_char", []) or []) if st else [],
            "pet": sorted(getattr(st, "pet_skills", []) or []) if st else [],
        }
        online = st is not None

        def _skill_label(skill_id):
            info = getattr(config, "SKILL_INFO", {}).get(skill_id, {}) or {}
            name = info.get("name")
            cost = info.get("cost")
            base = f"{name} ({skill_id}" if name else f"Skill {skill_id}"
            if cost is not None:
                return f"{base}, SP {cost})" if name else f"{base} (SP {cost})"
            return f"{base})" if name else base

        def _skill_values(unit, saved=None):
            vals = list(BATTLE_ACTION_LABELS.values())
            learned = live_skills[unit]
            if learned:
                vals.extend(_skill_label(s) for s in learned)
            elif saved:
                for s in saved:
                    if isinstance(s, int) and s > 0:
                        vals.append(_skill_label(s) + " (đã lưu)")
            return vals

        def _skill_to_label(v, unit):
            if isinstance(v, str) and v in BATTLE_ACTION_LABELS:
                return BATTLE_ACTION_LABELS[v]
            try:
                sid = int(v)
            except Exception:
                return BATTLE_ACTION_LABELS["auto"]
            return _skill_label(sid) if sid in live_skills[unit] else _skill_label(sid) + " (đã lưu)"

        def _label_to_skill(label):
            if label in LABEL_BATTLE_ACTIONS:
                return LABEL_BATTLE_ACTIONS[label]
            m = re.search(r"\b(\d{4,5})\b", label or "")
            return int(m.group(1)) if m else "auto"

        def _is_revive_skill(skill_id):
            try:
                info = getattr(config, "SKILL_INFO", {}).get(int(skill_id), {}) or {}
            except Exception:
                return False
            return info.get("cat") == 8 or "Hồi Sinh" in str(info.get("name") or "")

        def _revive_skills(unit, saved=None):
            ids = [s for s in live_skills[unit] if _is_revive_skill(s)]
            for s in saved or []:
                try:
                    sid = int(s)
                except Exception:
                    continue
                if sid not in ids and _is_revive_skill(sid):
                    ids.append(sid)
            return sorted(ids)

        def _condition_parts(rule):
            cond = rule.get("condition", "always") if isinstance(rule, dict) else "always"
            op = rule.get("op", "gte") if isinstance(rule, dict) else "gte"
            val = rule.get("value", "") if isinstance(rule, dict) else ""
            old = re.match(r"^(mob|sp|hp)_(gte|lte)_(\d+)$", str(cond))
            if old:
                kind, op, val = old.groups()
                cond = "hp_pct" if kind == "hp" else kind
            return cond, op, "" if val is None else str(val)

        def _condition_label(rule):
            cond, _op, _val = _condition_parts(rule)
            return BATTLE_CONDITION_TYPE_LABELS.get(cond, "Luôn luôn")

        def _condition_values(unit, saved_cond=None):
            vals = [v for k, v in BATTLE_CONDITION_TYPE_LABELS.items() if k != "ally_dead"]
            if _revive_skills(unit) or saved_cond == "ally_dead":
                vals.append(BATTLE_CONDITION_TYPE_LABELS["ally_dead"])
            return vals

        def _default_condition_value(cond):
            if cond == "mob":
                return "1"
            if cond == "block":
                return "2"
            if cond == "ally_hp_pct":
                return "70"
            if cond == "ally_sp_pct":
                return "50"
            if cond == "hp_pct":
                return "50"
            if cond == "sp":
                return "50"
            return ""

        def _normalize_rules(unit):
            raw = battle.get(unit)
            if isinstance(raw, list):
                out = []
                for r in raw:
                    if isinstance(r, dict):
                        cond, op, val = _condition_parts(r)
                        out.append({
                            "enabled": r.get("enabled", True) is not False,
                            "condition": cond,
                            "op": op,
                            "value": val,
                            "skill": r.get("skill", "auto"),
                            "target": r.get("target", "auto"),
                        })
                return out
            # Tuong thich ban dang lam do dang truoc khi doi sang rule list.
            if isinstance(raw, dict):
                mode = raw.get("mode", "auto")
                skill = "auto"
                if mode == "normal":
                    skill = "normal"
                elif mode == "defend":
                    skill = "defend"
                elif mode == "skill":
                    skill = int(raw.get("train_skill") or raw.get("boss_skill") or 0) or "auto"
                return [{"enabled": True, "condition": "always", "op": "gte", "value": "",
                         "skill": skill, "target": raw.get("target", "auto")}]
            if unit == "char" and settings.get("char_defend"):
                return [{"enabled": True, "condition": "always", "op": "gte", "value": "",
                         "skill": "defend", "target": "self"}]
            return [{"enabled": True, "condition": "always", "op": "gte", "value": "",
                     "skill": "auto", "target": "auto"}]

        def _skill_info(skill_id):
            try:
                return getattr(config, "SKILL_INFO", {}).get(int(skill_id), {}) or {}
            except Exception:
                return {}

        def _skill_cat(skill_id):
            return _skill_info(skill_id).get("cat", 1)

        def _skill_splash(skill_id):
            return _skill_info(skill_id).get("splash", 1)

        def _skill_cost(skill_id):
            return _skill_info(skill_id).get("cost", 0)

        def _is_attack_skill(skill_id):
            return _skill_cat(skill_id) in (1, 2)

        def _has_or_offline(unit, skill_id):
            learned = live_skills[unit]
            return (not learned) or int(skill_id) in learned

        def _pick_first(unit, candidates):
            for sid in candidates:
                if sid and _has_or_offline(unit, sid):
                    return sid
            return None

        def _pick_combo(unit):
            learned = live_skills[unit]
            cands = [s for s in learned if _is_attack_skill(s) and _skill_cat(s) == 1
                     and _skill_splash(s) in (2, 3, 4)]
            if cands:
                return min(cands, key=_skill_cost)
            return _pick_first(unit, [getattr(config, "SKILL_FIRE", 12003),
                                      getattr(config, "SKILL_ROCK", 10005), 13013])

        def _pick_boss(unit):
            learned = live_skills[unit]
            cands = [s for s in learned if _is_attack_skill(s) and _skill_splash(s) in (4, 1)]
            if cands:
                rank = {4: 2, 1: 1}
                return max(cands, key=lambda s: (rank.get(_skill_splash(s), 0), _skill_cost(s)))
            return _pick_first(unit, [12009, 12006, 13013, getattr(config, "SKILL_FIRE", 12003),
                                      getattr(config, "SKILL_ROCK", 10005)])

        def _pick_alltarget(unit):
            learned = live_skills[unit]
            cands = [s for s in learned if _is_attack_skill(s) and _skill_splash(s) == 8]
            if cands:
                return min(cands, key=_skill_cost)
            return _pick_first(unit, [12014, 10012])

        def _pick_sp_restore(unit):
            learned = live_skills[unit]
            cands = [s for s in learned if _skill_cat(s) == 6]
            if cands:
                return max(cands, key=_skill_cost)
            return None

        def _default_rule_template(unit):
            rules = []
            revs = _revive_skills(unit)
            if not revs and not live_skills[unit] and _is_revive_skill(11013):
                revs = [11013]
            if revs:
                rules.append({"enabled": True, "condition": "ally_dead", "op": "gte", "value": "",
                              "skill": revs[0], "target": "auto"})
            heal = _pick_first(unit, [getattr(config, "SKILL_HEAL_ALL", 11010),
                                      getattr(config, "SKILL_HEAL_ONE", 11004)])
            if heal:
                rules.append({"enabled": True, "condition": "ally_hp_pct", "op": "lt", "value": "70",
                              "skill": heal, "target": "ally_low_hp"})
            spr = _pick_sp_restore(unit)
            if spr:
                rules.append({"enabled": True, "condition": "ally_sp_pct", "op": "lt", "value": "50",
                              "skill": spr, "target": "ally_low_sp"})
            boss = _pick_boss(unit)
            if boss:
                rules.append({"enabled": True, "condition": "boss", "op": "gte", "value": "",
                              "skill": boss, "target": "enemy_low_hp"})
            alltarget = _pick_alltarget(unit)
            if alltarget:
                rules.append({"enabled": True, "condition": "quest", "op": "gte", "value": "",
                              "skill": alltarget, "target": "block"})
            combo = _pick_combo(unit)
            if combo:
                need_block = "3" if _skill_splash(combo) == 4 else "2"
                rules.append({"enabled": True, "condition": "sp_full", "op": "gte", "value": "",
                              "skill": combo, "target": "block"})
                rules.append({"enabled": True, "condition": "block", "op": "gte", "value": need_block,
                              "skill": combo, "target": "block"})
            rules.append({"enabled": True, "condition": "always", "op": "gte", "value": "",
                          "skill": "normal", "target": "auto"})
            return rules

        win = tk.Toplevel(self); win.title(f"Skill: {uname}"); win.resizable(False, False)
        win.transient(self.winfo_toplevel()); win.grab_set()
        frm = ttk.Frame(win, padding=10); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=("Acc đang online: có thể chọn skill đã học."
                             if online else
                             "Acc đang offline: muốn chọn skill đã học thì Start acc trước."),
                  foreground=("#0a0" if online else "#a60")).pack(anchor="w", pady=(0, 8))

        rule_rows = {"char": [], "pet": []}

        def _build_unit(parent, unit, title):
            box = ttk.LabelFrame(parent, text=title, padding=8)
            box.pack(fill="x", pady=(0, 8))
            hdr = ttk.Frame(box); hdr.pack(fill="x")
            ttk.Label(hdr, text="Bật", width=4).pack(side="left", padx=(0, 4))
            ttk.Label(hdr, text="Điều kiện", width=20).pack(side="left", padx=(0, 4))
            ttk.Label(hdr, text="Dấu", width=4, anchor="center").pack(side="left", padx=(0, 4))
            ttk.Label(hdr, text="Số", width=6, anchor="center").pack(side="left", padx=(0, 4))
            ttk.Label(hdr, text="Skill", width=24, anchor="center").pack(side="left", padx=(0, 4))
            ttk.Label(hdr, text="Target", width=22, anchor="center").pack(side="left", padx=(0, 4))
            list_fr = ttk.Frame(box); list_fr.pack(fill="x")

            def _refresh_order(unit_name):
                for rec in rule_rows[unit_name]:
                    rec["frame"].pack_forget()
                    rec["frame"].pack(fill="x", pady=1)

            def _move_rule(unit_name, rec, delta):
                rows = rule_rows[unit_name]
                try:
                    i = rows.index(rec)
                except ValueError:
                    return
                j = max(0, min(len(rows) - 1, i + delta))
                if i == j:
                    return
                rows[i], rows[j] = rows[j], rows[i]
                _refresh_order(unit_name)

            def _add_rule(rule=None):
                rule = rule or {"enabled": True, "condition": "always", "op": "gte", "value": "",
                                "skill": "auto", "target": "auto"}
                cond_key, op_key, value = _condition_parts(rule)
                fr = ttk.Frame(list_fr); fr.pack(fill="x", pady=1)
                enabled_var = tk.BooleanVar(value=rule.get("enabled", True) is not False)
                cond_var = tk.StringVar(value=_condition_label(rule))
                op_var = tk.StringVar(value=BATTLE_COMPARE_LABELS.get(op_key, ">="))
                value_var = tk.StringVar(value=value)
                saved_skill = rule.get("skill")
                skill_var = tk.StringVar(value=_skill_to_label(saved_skill, unit))
                target_var = tk.StringVar(value=BATTLE_TARGET_LABELS.get(rule.get("target"), "Auto"))
                ttk.Checkbutton(fr, variable=enabled_var).pack(side="left", padx=(0, 4))
                cond_cb = ttk.Combobox(fr, textvariable=cond_var, state="readonly", width=20,
                                       values=_condition_values(unit, cond_key))
                cond_cb.pack(side="left", padx=(0, 4))
                num_fr = ttk.Frame(fr)
                num_fr.pack(side="left", padx=(0, 4))
                op_cb = ttk.Combobox(num_fr, textvariable=op_var, state="readonly", width=4,
                                     values=list(BATTLE_COMPARE_LABELS.values()))
                op_cb.pack(side="left", padx=(0, 4))
                value_entry = ttk.Entry(num_fr, textvariable=value_var, width=6)
                value_entry.pack(side="left")
                num_fr.update_idletasks()
                num_fr.configure(width=num_fr.winfo_reqwidth(), height=num_fr.winfo_reqheight())
                num_fr.pack_propagate(False)
                skill_cb = ttk.Combobox(fr, textvariable=skill_var, state="readonly", width=24,
                                        values=_skill_values(unit, [saved_skill]))
                skill_cb.pack(side="left", padx=(0, 4))
                target_cb = ttk.Combobox(fr, textvariable=target_var, state="readonly", width=22,
                                         values=list(BATTLE_TARGET_LABELS.values()))
                target_cb.pack(side="left", padx=(0, 4))
                rec = {"frame": fr, "enabled": enabled_var, "condition": cond_var,
                       "op": op_var, "value": value_var, "skill": skill_var, "target": target_var}

                def _sync_condition(*_a):
                    ckey = LABEL_BATTLE_CONDITION_TYPES.get(cond_var.get(), "always")
                    is_num = ckey in BATTLE_NUMERIC_CONDITIONS
                    if ckey in BATTLE_FIXED_LT_CONDITIONS:
                        op_var.set("<")
                    if is_num:
                        if not op_cb.winfo_ismapped():
                            op_cb.pack(side="left", padx=(0, 4))
                        if not value_entry.winfo_ismapped():
                            value_entry.pack(side="left")
                        op_cb.configure(state=("readonly" if ckey not in BATTLE_FIXED_LT_CONDITIONS else "disabled"))
                        value_entry.configure(state="normal")
                    else:
                        op_cb.pack_forget()
                        value_entry.pack_forget()
                    if is_num and not value_var.get().strip():
                        value_var.set(_default_condition_value(ckey))
                    if not is_num and value_var.get().strip():
                        value_var.set("")
                    if ckey == "ally_dead":
                        revs = _revive_skills(unit, [_label_to_skill(skill_var.get())])
                        skill_cb.configure(values=[_skill_label(s) for s in revs],
                                           state=("readonly" if revs else "disabled"))
                        if revs and _label_to_skill(skill_var.get()) not in revs:
                            skill_var.set(_skill_label(revs[0]))
                        target_var.set("Auto")
                        target_cb.configure(state="disabled")
                    else:
                        skill_cb.configure(values=_skill_values(unit, [_label_to_skill(skill_var.get())]),
                                           state="readonly")
                        target_cb.configure(state="readonly")

                cond_var.trace_add("write", _sync_condition)
                _sync_condition()
                ttk.Button(fr, text="↑", width=2,
                           command=lambda r=rec: _move_rule(unit, r, -1)).pack(side="left", padx=(0, 2))
                ttk.Button(fr, text="↓", width=2,
                           command=lambda r=rec: _move_rule(unit, r, 1)).pack(side="left", padx=(0, 2))
                ttk.Button(fr, text="X", width=2,
                           command=lambda r=rec: _remove_rule(unit, r)).pack(side="left")
                rule_rows[unit].append(rec)

            def _remove_rule(unit_name, rec):
                rec["frame"].destroy()
                if rec in rule_rows[unit_name]:
                    rule_rows[unit_name].remove(rec)

            for rule in _normalize_rules(unit):
                _add_rule(rule)
            ttk.Button(box, text="+ Thêm rule",
                       command=lambda: _add_rule()).pack(anchor="w", pady=(4, 0))

        _build_unit(frm, "char", "Char")
        _build_unit(frm, "pet", "Pet")

        def _read_rules(unit):
            out = []
            for r in rule_rows[unit]:
                cond = LABEL_BATTLE_CONDITION_TYPES.get(r["condition"].get(), "always")
                skill = _label_to_skill(r["skill"].get())
                target = LABEL_BATTLE_TARGETS.get(r["target"].get(), "auto")
                value = r["value"].get().strip()
                if cond in BATTLE_NUMERIC_CONDITIONS and not value.isdigit():
                    value = _default_condition_value(cond)
                if cond == "ally_dead":
                    revs = _revive_skills(unit, [skill])
                    if not _is_revive_skill(skill) and revs:
                        skill = revs[0]
                    target = "auto"
                out.append({
                    "enabled": bool(r["enabled"].get()),
                    "condition": cond,
                    "op": "lt" if cond in BATTLE_FIXED_LT_CONDITIONS else LABEL_BATTLE_COMPARE.get(r["op"].get(), "gte"),
                    "value": value,
                    "skill": skill,
                    "target": target,
                })
            return out

        def _is_default(data):
            default = [{"enabled": True, "condition": "always", "op": "gte", "value": "",
                        "skill": "auto", "target": "auto"}]
            return data.get("char") == default and data.get("pet") == default

        def _save():
            data = {"char": _read_rules("char"), "pet": _read_rules("pet")}
            if _is_default(data):
                settings.pop("battle", None)
                live_cfg = {}
            else:
                settings["battle"] = data
                live_cfg = data
            settings.pop("char_defend", None)
            row["settings"] = settings
            try:
                ctrl.apply_account_battle(uname, live_cfg)
            except Exception as e:
                log.warning("[%s] apply live cau hinh skill loi: %s", uname, e)
            win.destroy()

        def _reset():
            if not messagebox.askyesno(
                    "Xác nhận nạp mẫu",
                    f"Nạp kịch bản skill mặc định cho acc '{uname}' và lưu áp dụng ngay?",
                    parent=win):
                return
            data = {"char": _default_rule_template("char"), "pet": _default_rule_template("pet")}
            settings["battle"] = data
            settings.pop("char_defend", None)
            row["settings"] = settings
            try:
                ctrl.apply_account_battle(uname, data)
            except Exception as e:
                log.warning("[%s] apply live kich ban skill mac dinh loi: %s", uname, e)
            win.destroy()

        bb = ttk.Frame(frm); bb.pack(fill="x", pady=(2, 0))
        ttk.Button(bb, text="Mặc định", command=_reset).pack(side="left", padx=4)
        ttk.Button(bb, text="Lưu", command=_save).pack(side="left", padx=4)
        ttk.Button(bb, text="Hủy", command=win.destroy).pack(side="left", padx=4)

    def _del_acc_row(self, row):
        row["frame"].destroy()
        if row in self.acc_rows:
            self.acc_rows.remove(row)

    def _open_advanced_settings(self):
        """Dialog gom cac setting IT KHI DOI cua party (hien tai: daily quest) - tach khoi bang
        chinh de tranh bi day dai/roi khi sau nay them setting moi (xem ghi chu o self.daily_var)."""
        win = tk.Toplevel(self); win.title("Cài đặt nâng cao"); win.transient(self); win.grab_set()
        win.resizable(False, False)
        frm = ttk.Frame(win, padding=12); frm.pack(fill="both", expand=True)
        ttk.Checkbutton(frm, text="Làm nhiệm vụ hàng ngày (bingo 9 ô: phó bản đơn, boss thế giới, "
                        "gacha, hợp đồ... + nhận thưởng)",
                        variable=self.daily_var).pack(anchor="w")
        ttk.Checkbutton(frm, text="Sử dụng Phúc Thần",
                        variable=self.use_phuc_than_var).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(frm, text="Dùng Dị giới hộ phù",
                        variable=self.use_digioi_ho_phu_var).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(frm, text="Đánh boss QD",
                        variable=self.fight_boss_var).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(frm, text="Vận tiêu (nhận quà + gửi pet)",
                        variable=self.van_tieu_var).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(frm, text="Mua Dị Giới Hộ Phù (3 cái/ngày)",
                        variable=self.buy_ho_phu_var).pack(anchor="w", pady=(4, 0))
        _bh = ttk.Frame(frm); _bh.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Checkbutton(_bh, text="Mua Triệu Gọi Bảo Hộp khi xu nhiều hơn",
                        variable=self.buy_bao_hop_var).pack(side="left")
        ttk.Entry(_bh, textvariable=self.bao_hop_xu_var, width=10).pack(side="left", padx=(4, 0))
        # (Cap quai Di Gioi da chuyen ra setting mode Di Gioi ngoai - khong lap lai o day)
        bar = ttk.Frame(frm); bar.pack(fill="x", pady=(12, 0))
        if self.on_apply_advanced_to_all:
            ttk.Button(bar, text="Áp dụng cho các party khác",
                       command=lambda: self.on_apply_advanced_to_all(self._advanced_settings_data())
                       ).pack(side="left")
        ttk.Button(bar, text="Đóng", command=win.destroy).pack(side="right")

    def _advanced_settings_data(self):
        return {
            "do_daily": bool(self.daily_var.get()),
            "use_phuc_than": bool(self.use_phuc_than_var.get()),
            "use_digioi_ho_phu": bool(self.use_digioi_ho_phu_var.get()),
            "fight_legion_boss": bool(self.fight_boss_var.get()),
            "do_van_tieu": bool(self.van_tieu_var.get()),
            "buy_ho_phu": bool(self.buy_ho_phu_var.get()),
            "buy_bao_hop": bool(self.buy_bao_hop_var.get()),
            "bao_hop_xu_threshold": _parse_int(self.bao_hop_xu_var.get(), 1000000),
            "di_gioi_level": _dg_level_to_idx(self.di_gioi_level_var.get()),
        }

    def apply_advanced_settings(self, data):
        self.daily_var.set(bool(data.get("do_daily", True)))
        self.use_phuc_than_var.set(bool(data.get("use_phuc_than", False)))
        self.use_digioi_ho_phu_var.set(bool(data.get("use_digioi_ho_phu", False)))
        self.fight_boss_var.set(bool(data.get("fight_legion_boss", True)))
        self.van_tieu_var.set(bool(data.get("do_van_tieu", True)))
        self.buy_ho_phu_var.set(bool(data.get("buy_ho_phu", False)))
        self.buy_bao_hop_var.set(bool(data.get("buy_bao_hop", False)))
        self.bao_hop_xu_var.set(str(_parse_int(data.get("bao_hop_xu_threshold", 1000000), 1000000)))
        _idx = int(data.get("di_gioi_level", 2))
        self.di_gioi_level_var.set(str(_DG_LEVELS[_idx - 1] if 1 <= _idx <= 15 else 25))

    def _on_mode_change(self):
        # Khi DOI che do: tu set mac dinh "Khong co chu PT".
        #  - city / stand / event: TICK (moi nick tu dung/tele rieng, khong can chu PT).
        #  - train / digioi: BO TICK (can chu PT de keo party + lap tran).
        mode = _LABEL_MODE.get(self.mode_var.get(), "digioi")
        self.no_leader_var.set(mode in ("city", "stand", "event"))
        self._render_dyn()

    def _update_no_leader_visibility(self):
        """Di Gioi SOLO: khong lap party that -> checkbox 'Khong co chu PT' VA 'White list rieng'
        (dung de loc loi moi party) deu vo nghia -> an ca 2 cho gon (theo yeu cau). Cac mode khac
        (train/city/stand/Di Gioi party) van hien binh thuong."""
        mode = _LABEL_MODE.get(self.mode_var.get(), "digioi")
        hide = (mode == "digioi" and self.digioi_solo_var.get())
        if hide:
            self.no_leader_cb.pack_forget()
            self.wl_lbl.pack_forget()
            self.wl_entry.pack_forget()
        else:
            self.no_leader_cb.pack(side="left")
            self.wl_lbl.pack(side="left")
            self.wl_entry.pack(side="left", fill="x", expand=True, padx=4)

    def _render_dyn(self):
        for w in self.dyn.winfo_children():
            w.destroy()
        mode = _LABEL_MODE.get(self.mode_var.get(), "digioi")
        # "Kieu chay" (Party/Solo) chi hien khi mode=digioi, nam CUNG HANG voi "Che do" (ben phai).
        if mode == "digioi":
            self.digioi_kind_var.set("Solo (mỗi acc chạy riêng)" if self.digioi_solo_var.get()
                                     else "Party (lập đội chung)")
            self.digioi_kind_lbl.pack(side="left")
            self.digioi_kind_cb.pack(side="left")
        else:
            self.digioi_kind_lbl.pack_forget()
            self.digioi_kind_cb.pack_forget()
        self._update_no_leader_visibility()
        if mode == "train":
            ttk.Label(self.dyn, text="Map:", width=10).pack(side="left")
            names = [n for (_i, n, _m) in self.train_maps]
            self.map_cb = ttk.Combobox(self.dyn, textvariable=self.map_var, state="readonly",
                                       width=32, values=names)
            self.map_cb.pack(side="left")
            self.map_cb.bind("<<ComboboxSelected>>", lambda e: self._fill_mobs())
            ttk.Label(self.dyn, text="Quái:", width=6).pack(side="left", padx=(10, 0))
            self.mob_cb = ttk.Combobox(self.dyn, textvariable=self.mob_var, state="readonly", width=22)
            self.mob_cb.pack(side="left")
            ttk.Button(self.dyn, text="✎ Sửa map", command=self._edit_maps).pack(side="left", padx=(8, 0))
            idx = next((i for i, (mid, _n, _m) in enumerate(self.train_maps)
                        if mid == self._preset.get("start_city_id")), 0)
            if names:
                self.map_var.set(names[idx])
            # Chi dung mob_index DA LUU neu preset von la 'train'. Doi tu mode khac sang train
            # -> mac dinh "Bot tu chon" (-1), KHONG lay mob_index=0 (rac) cua mode khac.
            pmob = self._preset.get("mob_index", -1) if self._preset.get("mode") == "train" else -1
            self._fill_mobs(pmob)
        elif mode == "city":
            ttk.Label(self.dyn, text="Thành:", width=10).pack(side="left")
            names = [n for (_i, _f, n) in self.cities]
            self.city_cb = ttk.Combobox(self.dyn, textvariable=self.city_var, state="readonly",
                                        width=24, values=names)
            self.city_cb.pack(side="left")
            idx = next((i for i, (cid, _f, _n) in enumerate(self.cities)
                        if cid == self._preset.get("start_city_id")), None)
            if idx is None:   # chua co preset (vd vua doi tu mode khac sang) -> mac dinh Ng.Thanh (12061)
                idx = next((i for i, (cid, _f, _n) in enumerate(self.cities) if cid == 12061), 0)
            if names:
                self.city_var.set(names[idx])
        elif mode == "event":
            ttk.Label(self.dyn, text="Event:", width=10).pack(side="left")
            labels = [lbl for _k, lbl in self.events]
            self.event_cb = ttk.Combobox(self.dyn, textvariable=self.event_var, state="readonly",
                                          width=32, values=labels)
            self.event_cb.pack(side="left")
            # chon lai event da luu (theo event_key), mac dinh cai dau tien
            cur = self._preset.get("event_key")
            idx = next((i for i, (k, _l) in enumerate(self.events) if k == cur), 0)
            if labels:
                self.event_var.set(labels[idx])
            ttk.Label(self.dyn, text="  (tele tới map event, đứng yên chờ mời tay)").pack(side="left")
        elif mode == "digioi":
            ttk.Label(self.dyn, text="Cấp quái:", width=10).pack(side="left")
            ttk.Combobox(self.dyn, textvariable=self.di_gioi_level_var, width=6, state="readonly",
                         values=[str(v) for v in _DG_LEVELS]).pack(side="left")
            if getattr(self, "on_apply_di_gioi_level", None):
                ttk.Button(self.dyn, text="Áp dụng ngay",
                           command=lambda: self.on_apply_di_gioi_level(
                               _dg_level_to_idx(self.di_gioi_level_var.get()))
                           ).pack(side="left", padx=(8, 0))
            ttk.Label(self.dyn, text="  (Dị Giới, START_CITY_ID=49942)").pack(side="left")
        elif mode == "stand":
            ttk.Label(self.dyn, text="→ Login ở đâu đứng yên đó (START_CITY_ID = 0)").pack(side="left")
        else:
            ttk.Label(self.dyn, text="→ Dọn dẹp túi đồ (chưa làm — placeholder)").pack(side="left")

    def _fill_mobs(self, preset_index=None):
        sel = self.map_var.get()
        mobs = next((m for (_i, n, m) in self.train_maps if n == sel), [])
        # Index 0 = "Bot tu chon" (ngau nhien). Index 1.. = diem cu the.
        opts = ["🎲 Bot tự chọn (ngẫu nhiên)"] + [f"Điểm {i + 1} {tuple(xy)}"
                                                  for i, xy in enumerate(mobs)]
        if self.mob_cb:
            self.mob_cb.configure(values=opts)
            # preset_index: -1 (hoac None) -> auto (0); >=0 -> diem do (+1)
            ci = (preset_index + 1) if (preset_index is not None and preset_index >= 0) else 0
            ci = min(ci, len(opts) - 1)
            self.mob_var.set(opts[ci])

    def _edit_maps(self):
        TrainMapEditor(self, on_save=self._reload_maps)

    def _reload_maps(self):
        # nap lai train_maps.json -> cap nhat list (chia se) + ve lai dropdown
        tm_raw = _load_json("train_maps.json").get("maps", {})
        self.train_maps[:] = [(int(k), v.get("name", k), v.get("mobs", [])) for k, v in tm_raw.items()]
        self._render_dyn()

    def get_data(self):
        mode = _LABEL_MODE.get(self.mode_var.get(), "digioi")
        sc, mob_index, city_flag = 0, 0, 0
        event_key = ""
        if mode == "digioi":
            sc = 49942
        elif mode == "train":
            sc = next((mid for (mid, n, _m) in self.train_maps if n == self.map_var.get()), 0)
            cur = self.mob_cb.current() if self.mob_cb else 0
            mob_index = (cur - 1) if cur >= 1 else -1   # 0 = "Bot tu chon" -> -1; k -> diem k-1
        elif mode == "city":
            for (cid, f, n) in self.cities:
                if n == self.city_var.get():
                    sc = cid; city_flag = f; break
        elif mode == "event":
            event_key = next((k for k, lbl in self.events if lbl == self.event_var.get()), "")
        accs = []
        for r in self.acc_rows:
            u = r["u"].get().strip()
            if not u:
                continue
            pw = r["p"].get().strip()
            if pw == self._PW_MASK:    # khong doi -> giu pass cu (da luu)
                pw = r.get("_realp", "")
            acc = {"u": u, "p": pw, "on": bool(r["on"].get())}
            if r.get("heal"):
                acc["heal"] = r["heal"]
            if r.get("settings"):
                acc["settings"] = r["settings"]
            accs.append(acc)
        if self.no_leader_var.get() and accs:
            accs = [{"u": "", "p": "", "on": True}] + accs   # slot 0 trong = KHONG co chu PT
        # server: label -> key
        srv = next((k for k, lbl in self.servers if lbl == self.server_var.get()),
                   self.servers[0][0] if self.servers else "trieu_van")
        leaders = [x.strip() for x in self.leaders_var.get().split(",") if x.strip()]
        data = {"server": srv, "mode": mode, "start_city_id": sc, "mob_index": mob_index,
                "city_flag": city_flag, "do_daily": bool(self.daily_var.get()),
                "use_phuc_than": bool(self.use_phuc_than_var.get()),
                "use_digioi_ho_phu": bool(self.use_digioi_ho_phu_var.get()),
                "fight_legion_boss": bool(self.fight_boss_var.get()),
                "do_van_tieu": bool(self.van_tieu_var.get()),
                "buy_ho_phu": bool(self.buy_ho_phu_var.get()),
                "buy_bao_hop": bool(self.buy_bao_hop_var.get()),
                "bao_hop_xu_threshold": _parse_int(self.bao_hop_xu_var.get(), 1000000),
                "di_gioi_level": _dg_level_to_idx(self.di_gioi_level_var.get()),
                "leaders": leaders, "accounts": accs}
        if mode == "digioi":
            data["digioi_mode"] = "solo" if self.digioi_solo_var.get() else "party"
        if mode == "event":
            data["event_key"] = event_key
        return data


def _parse_int(s, default):
    """Doc so nguyen tu text field; rong/loi -> default (tranh crash khi user go chu)."""
    try:
        return int(str(s).strip().replace(",", "").replace(".", "") or default)
    except Exception:
        return default


def _safe_points(safe):
    """Chuan hoa safe ve list [x,y]: nhan ca [[x,y],...] (moi) lan [x,y] (cu)."""
    if not safe:
        return []
    if isinstance(safe[0], (list, tuple)):
        return [list(p) for p in safe]
    return [list(safe)]


class TrainMapEditor(tk.Toplevel):
    """Sua train_maps.json: them/xoa map, sua safe point + mob point."""
    TM_PATH = os.path.join(_BASE, "train_maps.json")

    def __init__(self, master, on_save=None):
        super().__init__(master)
        self.title("Sửa map train (train_maps.json)")
        self.geometry("760x540")
        self.transient(master); self.grab_set()
        self.on_save = on_save
        raw = _load_json("train_maps.json").get("maps", {})
        # list dict: {id, name, safe:[[x,y]], mobs:[[x,y]]}
        self.maps = [{"id": k, "name": v.get("name", k),
                      "safe": _safe_points(v.get("safe", [])),
                      "mobs": [list(p) for p in v.get("mobs", [])]} for k, v in raw.items()]
        self._cur = None

        # Pack BAR (Luu/Huy) o DAY truoc -> giu cho duoi cung (left/right pack sau khong de len)
        bar = ttk.Frame(self, padding=6); bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="💾 Lưu", command=self._save).pack(side="right")
        ttk.Button(bar, text="Hủy", command=self.destroy).pack(side="right", padx=4)

        left = ttk.Frame(self, padding=6); left.pack(side="left", fill="y")
        ttk.Label(left, text="Danh sách map:").pack(anchor="w")
        self.lb = tk.Listbox(left, width=42, height=20, exportselection=False)
        self.lb.pack(fill="y", expand=True)
        self.lb.bind("<<ListboxSelect>>", lambda e: self._on_select())
        b = ttk.Frame(left); b.pack(fill="x", pady=4)
        ttk.Button(b, text="+ Thêm", command=self._add).pack(side="left")
        ttk.Button(b, text="🗑 Xóa", command=self._del).pack(side="left", padx=4)
        b2 = ttk.Frame(left); b2.pack(fill="x")
        ttk.Button(b2, text="▲ Lên", command=lambda: self._move(-1)).pack(side="left")
        ttk.Button(b2, text="▼ Xuống", command=lambda: self._move(1)).pack(side="left", padx=4)

        right = ttk.Frame(self, padding=6); right.pack(side="left", fill="both", expand=True)
        mapid_row = ttk.Frame(right); mapid_row.pack(anchor="w", fill="x")
        ttk.Label(mapid_row, text="Map ID (log 'MAP HIEN TAI'):").pack(side="left")
        self.id_var = tk.StringVar()
        ttk.Entry(mapid_row, textvariable=self.id_var, width=16).pack(side="left", padx=(8, 8))
        ttk.Button(mapid_row, text="Thống kê block",
                   command=self._show_block_stats).pack(side="left")
        ttk.Label(right, text="Tên:").pack(anchor="w", pady=(6, 0))
        self.name_var = tk.StringVar(); ttk.Entry(right, textvariable=self.name_var, width=34).pack(anchor="w")
        ttk.Label(right, text="Safe point (mỗi dòng: x,y — dòng đầu = điểm tập kết/lập party):"
                  ).pack(anchor="w", pady=(8, 0))
        self.safe_txt = tk.Text(right, height=6, font=("Consolas", 10)); self.safe_txt.pack(fill="x")
        ttk.Label(right, text="Mob point (mỗi dòng: x,y — leader ra đứng cây):").pack(anchor="w", pady=(8, 0))
        self.mob_txt = tk.Text(right, height=6, font=("Consolas", 10)); self.mob_txt.pack(fill="x")

        self._reload_list()
        if self.maps:
            self.lb.selection_set(0); self._on_select()

    def _reload_list(self):
        self.lb.delete(0, "end")
        for m in self.maps:
            self.lb.insert("end", f"{m['name']} ({m['id']})")

    def _pts_to_text(self, pts):
        return "\n".join(f"{p[0]},{p[1]}" for p in pts)

    def _text_to_pts(self, txt):
        out = []
        for line in txt.splitlines():
            line = line.strip().replace(" ", "")
            if not line:
                continue
            try:
                x, y = line.split(",")[:2]
                out.append([int(x), int(y)])
            except Exception:
                pass
        return out

    def _show_block_stats(self):
        self._commit()
        if self._cur is None or self._cur >= len(self.maps):
            messagebox.showinfo("Thống kê block", "Chưa chọn map.")
            return
        m = self.maps[self._cur]
        mid = str(m.get("id", "")).strip()
        if not mid.isdigit():
            messagebox.showerror("Thống kê block", "Map ID phải là số.")
            return
        try:
            from bot import train_block_stats
        except Exception as e:
            messagebox.showerror("Thống kê block", f"Không mở được thống kê:\n{e}")
            return

        top = tk.Toplevel(self)
        top.title(f"Thống kê block - {m.get('name', mid)}")
        top.transient(self)
        top.geometry("760x420")
        box = ttk.Frame(top, padding=8)
        box.pack(fill="both", expand=True)

        cols = ("idx", "spot", "total", "patterns")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=14)
        tree.heading("idx", text="#")
        tree.heading("spot", text="Điểm train")
        tree.heading("total", text="Số trận")
        tree.heading("patterns", text="Block xuất hiện")
        tree.column("idx", width=48, anchor="center")
        tree.column("spot", width=120, anchor="center")
        tree.column("total", width=80, anchor="center")
        tree.column("patterns", width=480, anchor="w")
        tree.pack(fill="both", expand=True)

        mobs = m.get("mobs") or []
        if not mobs:
            tree.insert("", "end", values=("-", "-", 0, "Map này chưa có mob point."))
        for i, spot in enumerate(mobs, 1):
            summary = train_block_stats.get_spot_summary(int(mid), spot)
            patterns = train_block_stats.format_patterns(summary.get("patterns", {}))
            tree.insert("", "end", values=(i, train_block_stats.spot_key(spot),
                                           int(summary.get("total", 0)), patterns or "-"))

        ttk.Label(box, text="Bot chỉ cộng thống kê từ danh sách quái ở đầu trận train map."
                  ).pack(anchor="w", pady=(8, 0))
        ttk.Button(box, text="Đóng", command=top.destroy).pack(anchor="e", pady=(8, 0))

    def _commit(self):
        """Luu field hien tai vao self.maps[self._cur]."""
        if self._cur is None or self._cur >= len(self.maps):
            return
        m = self.maps[self._cur]
        m["id"] = self.id_var.get().strip() or m["id"]
        m["name"] = self.name_var.get().strip() or m["id"]
        m["safe"] = self._text_to_pts(self.safe_txt.get("1.0", "end"))
        m["mobs"] = self._text_to_pts(self.mob_txt.get("1.0", "end"))

    def _on_select(self):
        self._commit()
        sel = self.lb.curselection()
        if not sel:
            return
        self._cur = sel[0]
        m = self.maps[self._cur]
        self.id_var.set(m["id"]); self.name_var.set(m["name"])
        self.safe_txt.delete("1.0", "end"); self.safe_txt.insert("1.0", self._pts_to_text(m["safe"]))
        self.mob_txt.delete("1.0", "end"); self.mob_txt.insert("1.0", self._pts_to_text(m["mobs"]))

    def _add(self):
        self._commit()
        self.maps.append({"id": "0", "name": "Map moi", "safe": [], "mobs": []})
        self._reload_list()
        self.lb.selection_clear(0, "end"); self.lb.selection_set("end")
        self._cur = None; self._on_select()

    def _del(self):
        sel = self.lb.curselection()
        if not sel or len(self.maps) == 0:
            return
        del self.maps[sel[0]]
        self._cur = None
        self._reload_list()
        if self.maps:
            self.lb.selection_set(0); self._on_select()
        else:
            for w in (self.id_var, self.name_var):
                w.set("")
            self.safe_txt.delete("1.0", "end"); self.mob_txt.delete("1.0", "end")

    def _move(self, delta):
        self._commit()
        sel = self.lb.curselection()
        if not sel:
            return
        i = sel[0]; j = i + delta
        if j < 0 or j >= len(self.maps):
            return
        self.maps[i], self.maps[j] = self.maps[j], self.maps[i]   # doi cho
        self._cur = j                      # cap nhat TRUOC khi doi selection (tranh commit nham)
        self._reload_list()
        self.lb.selection_clear(0, "end"); self.lb.selection_set(j); self.lb.see(j)
        self._on_select_no_commit(j)

    def _on_select_no_commit(self, idx):
        m = self.maps[idx]
        self.id_var.set(m["id"]); self.name_var.set(m["name"])
        self.safe_txt.delete("1.0", "end"); self.safe_txt.insert("1.0", self._pts_to_text(m["safe"]))
        self.mob_txt.delete("1.0", "end"); self.mob_txt.insert("1.0", self._pts_to_text(m["mobs"]))

    def _save(self):
        self._commit()
        data = {"_note": "Data map party-train. safe=[[x,y],...] (diem dau=tap ket). mobs=[[x,y],...].",
                "maps": {}}
        for m in self.maps:
            mid = m["id"].strip()
            if not mid or not mid.isdigit():
                messagebox.showerror("Lỗi", f"Map ID phải là số (map '{m['name']}')."); return
            data["maps"][mid] = {"name": m["name"], "safe": m["safe"], "mobs": m["mobs"]}
        with open(self.TM_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if self.on_save:
            self.on_save()
        messagebox.showinfo("Đã lưu", "Đã lưu train_maps.json.")
        self.destroy()


class ConfigDialog(tk.Toplevel):
    def __init__(self, master, open_pidx=0):
        super().__init__(master)
        self.title("Cấu hình party")
        self.geometry("640x600")
        self.transient(master); self.grab_set()
        # PROFILES: nhieu bo cau hinh, doi 1 phat. active = bo dang dung (= accounts.json).
        self._prof = _load_profiles()
        self._active = self._prof.get("active") or next(iter(self._prof["profiles"]))
        if self._active not in self._prof["profiles"]:
            self._active = next(iter(self._prof["profiles"]))
        self._orig_active = self._active
        data = self._prof["profiles"].get(self._active) or self._load()
        tm_raw = _load_json("train_maps.json").get("maps", {})
        self.train_maps = [(int(k), v.get("name", k), v.get("mobs", [])) for k, v in tm_raw.items()]
        ct_raw = _load_json("cities.json").get("cities", {})
        self.cities = [(v["city_id"], v.get("flag", 0), v.get("name", k)) for k, v in ct_raw.items()]
        sv_raw = _load_json("servers.json").get("servers", {})
        self.servers = [(k, v.get("label", k)) for k, v in sv_raw.items()] or [("trieu_van", "Triệu Vân")]

        top = ttk.Frame(self, padding=6); top.pack(fill="x")
        ttk.Label(top, text="Kênh chung:").pack(side="left")
        self.ch_var = tk.StringVar(value=str(data.get("channel", 2)))
        ttk.Entry(top, textvariable=self.ch_var, width=6).pack(side="left", padx=4)
        ttk.Button(top, text="➕ Thêm party", command=self._add_party).pack(side="left", padx=8)
        ttk.Button(top, text="🗑 Xóa party này", command=self._del_party).pack(side="left")

        # White list CHUNG (ap moi party): nut mo popup edit danh sach leader.
        _gl = data.get("party_leaders", [])
        self.gleaders_var = tk.StringVar(value=", ".join(_gl) if isinstance(_gl, list) else str(_gl or ""))
        self.gl_btn = ttk.Button(top, command=self._edit_global_leaders)
        self.gl_btn.pack(side="left", padx=8)
        self._update_gl_btn()

        # PROFILE switcher (ben phai white-list): doi 1 phat ca bo party giua cac cau hinh.
        self.prof_var = tk.StringVar(value=self._active)
        self.prof_cb = ttk.Combobox(top, textvariable=self.prof_var, width=14, state="readonly",
                                    values=list(self._prof["profiles"].keys()))
        self.prof_cb.pack(side="left", padx=(8, 0))
        self.prof_cb.bind("<<ComboboxSelected>>", self._on_profile_switch)
        ttk.Button(top, text="➕", width=3, command=self._add_profile).pack(side="left", padx=(2, 0))
        ttk.Button(top, text="🗑", width=3, command=self._del_profile).pack(side="left")

        self.nb = ttk.Notebook(self); self.nb.pack(fill="both", expand=True, padx=6, pady=4)
        self.nb.bind("<<NotebookTabChanged>>", self._on_cfg_group_tab)
        self.frames = []           # entries (theo thu tu pidx): {holder, preset, cfg, sub, gidx}
        self.cfg_group_nb = {}     # gidx -> sub-Notebook
        # GROUP -> party sub-tab (dong nhat voi GUI chinh). LAZY: party dung khi bam vao.
        self._build_groups(data.get("parties") or [{}], open_pidx)

        bar = ttk.Frame(self, padding=6); bar.pack(fill="x")
        ttk.Button(bar, text="💾 Lưu", command=self._save).pack(side="right", padx=3)
        ttk.Button(bar, text="Hủy", command=self.destroy).pack(side="right", padx=3)

    def _load(self):
        """Bo cau hinh DANG CHON (rut tu accounts.json dang profiles, hoac flat cu)."""
        try:
            with open(ACCOUNTS_JSON, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            return {"channel": 2, "parties": []}
        if isinstance(d, dict) and isinstance(d.get("profiles"), dict):
            return d["profiles"].get(d.get("active")) or {"channel": 2, "parties": []}
        return d

    PARTIES_PER_GROUP = 10

    def _build_groups(self, parties, focus_pidx=0):
        import math
        for t in self.nb.tabs():
            self.nb.forget(t)
        self.frames = []
        self.cfg_group_nb = {}
        n = len(parties)
        n_groups = max(1, math.ceil(n / self.PARTIES_PER_GROUP))
        gsize = math.ceil(n / n_groups)
        for gidx in range(n_groups):
            members = list(range(gidx * gsize, min((gidx + 1) * gsize, n)))
            if not members:
                continue
            gtab = ttk.Frame(self.nb)
            self.nb.add(gtab, text=f"Nhóm {gidx + 1} (P{members[0] + 1}-P{members[-1] + 1})")
            sub = ttk.Notebook(gtab); sub.pack(fill="both", expand=True)
            sub.bind("<<NotebookTabChanged>>", self._on_cfg_party_tab)
            self.cfg_group_nb[gidx] = sub
            for pidx in members:
                holder = ttk.Frame(sub)
                sub.add(holder, text=f"P{pidx + 1}")
                self.frames.append({"holder": holder, "preset": parties[pidx] or {}, "cfg": None,
                                    "sub": sub, "gidx": gidx})
        if self.frames:
            fp = min(max(focus_pidx, 0), len(self.frames) - 1)
            e = self.frames[fp]
            self.nb.select(e["gidx"])
            e["sub"].select(e["holder"])
            self._build_entry(e)

    def _build_entry(self, entry):
        if entry["cfg"] is None:
            on_apply = lambda data, e=entry: self._apply_advanced_to_all(e, data)
            _pidx = self.frames.index(entry)   # entries append theo dung thu tu pidx
            on_apply_dg = lambda idx, p=_pidx: threading.Thread(
                target=ctrl.party_set_di_gioi_level, args=(p, idx), daemon=True).start()
            cfg = PartyConfigFrame(entry["holder"], entry["preset"],
                                   self.train_maps, self.cities, self.servers,
                                   on_apply_advanced_to_all=on_apply,
                                   on_apply_di_gioi_level=on_apply_dg)
            cfg.pack(fill="both", expand=True)
            entry["cfg"] = cfg
        return entry["cfg"]

    def _apply_advanced_to_all(self, source_entry, data):
        count = 0
        for entry in self.frames:
            if entry is source_entry:
                continue
            if entry["cfg"] is not None:
                entry["cfg"].apply_advanced_settings(data)
            else:
                preset = dict(entry["preset"] or {})
                preset.update(data)
                entry["preset"] = preset
            count += 1
        if count:
            messagebox.showinfo("Đã áp dụng",
                                f"Đã áp dụng cài đặt nâng cao cho {count} party khác.\n"
                                "Bấm Lưu để ghi vào cấu hình.")
        else:
            messagebox.showinfo("Không có party khác", "Hiện chỉ có 1 party.")

    def _entry_of_sub(self, sub):
        """entry cua party DANG CHON trong sub-Notebook sub (theo holder dang select)."""
        try:
            cur = sub.select()
        except Exception:
            return None
        for e in self.frames:
            if e["sub"] is sub and str(e["holder"]) == str(cur):
                return e
        return None

    def _on_cfg_party_tab(self, event=None):
        e = self._entry_of_sub(event.widget)
        if e is not None:
            self._build_entry(e)

    def _on_cfg_group_tab(self, event=None):
        try:
            gidx = self.nb.index(self.nb.select())
        except Exception:
            return
        sub = self.cfg_group_nb.get(gidx)
        if sub is not None:
            e = self._entry_of_sub(sub)
            if e is not None:
                self._build_entry(e)

    def _snapshot(self):
        """Lay data hien tai cua tat ca party (built -> get_data; chua mo -> preset)."""
        return [e["cfg"].get_data() if e["cfg"] is not None else e["preset"] for e in self.frames]

    def _cur_party_index(self):
        try:
            gidx = self.nb.index(self.nb.select())
            sub = self.cfg_group_nb.get(gidx)
            e = self._entry_of_sub(sub)
            if e is not None:
                return self.frames.index(e)
        except Exception:
            pass
        return 0

    def _add_party(self):
        parties = self._snapshot() + [{}]
        self._build_groups(parties, len(parties) - 1)

    def _del_party(self):
        if len(self.frames) <= 1:
            return
        cur = self._cur_party_index()
        parties = self._snapshot()
        del parties[cur]
        self._build_groups(parties, min(cur, len(parties) - 1))

    # ---------- PROFILES (nhieu bo cau hinh, doi 1 phat) ----------
    def _collect_data(self):
        """Gom state UI hien tai -> {channel, party_leaders, parties} (bo party rong)."""
        try:
            ch = int(self.ch_var.get().strip() or 2)
        except ValueError:
            ch = 2
        parties = [p for p in self._snapshot() if p.get("accounts")]
        gleaders = [x.strip() for x in self.gleaders_var.get().split(",") if x.strip()]
        return {"channel": ch, "party_leaders": gleaders, "parties": parties}

    def _apply_data_to_ui(self, d):
        """Nap 1 bo cau hinh vao UI (kenh + white-list + rebuild tab party)."""
        self.ch_var.set(str(d.get("channel", 2)))
        gl = d.get("party_leaders", [])
        self.gleaders_var.set(", ".join(gl) if isinstance(gl, list) else str(gl or ""))
        self._update_gl_btn()
        self._build_groups(d.get("parties") or [{}], 0)

    def _on_profile_switch(self, event=None):
        """Doi profile trong dropdown: luu state hien tai vao profile cu (in-memory) -> nap profile moi."""
        new = self.prof_var.get()
        if new == self._active:
            return
        self._prof["profiles"][self._active] = self._collect_data()   # giu sua chua luu
        self._active = new
        self._apply_data_to_ui(self._prof["profiles"].get(new, {"channel": 2, "parties": []}))

    def _add_profile(self):
        name = simpledialog.askstring("Thêm cấu hình", "Tên cấu hình mới:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in self._prof["profiles"]:
            messagebox.showerror("Lỗi", "Tên cấu hình đã tồn tại."); return
        import copy
        self._prof["profiles"][self._active] = self._collect_data()       # luu profile dang sua
        self._prof["profiles"][name] = copy.deepcopy(self._collect_data())  # bo moi = copy hien tai
        self._active = name
        self.prof_cb.configure(values=list(self._prof["profiles"].keys()))
        self.prof_var.set(name)
        # state giu nguyen (la copy) -> khong rebuild

    def _del_profile(self):
        if len(self._prof["profiles"]) <= 1:
            messagebox.showinfo("Không xóa được", "Phải còn ít nhất 1 cấu hình."); return
        if not messagebox.askyesno("Xóa cấu hình", f"Xóa cấu hình '{self._active}'?"):
            return
        del self._prof["profiles"][self._active]
        self._active = next(iter(self._prof["profiles"]))
        self.prof_cb.configure(values=list(self._prof["profiles"].keys()))
        self.prof_var.set(self._active)
        self._apply_data_to_ui(self._prof["profiles"][self._active])

    def _update_gl_btn(self):
        n = len([x for x in self.gleaders_var.get().split(",") if x.strip()])
        self.gl_btn.configure(text=f"🛡 White list Leader ({n})")

    def _edit_global_leaders(self):
        """Popup edit white list CHUNG: moi dong 1 ten leader (ap dung MOI party).
        Bam Luu -> ghi THANG party_leaders vao accounts.json (giu nguyen cac key khac)."""
        win = tk.Toplevel(self); win.title("White list Leader (chung)")
        win.transient(self); win.grab_set(); win.geometry("320x360")
        ttk.Label(win, text="Mỗi dòng 1 tên leader (áp dụng MỌI party):").pack(anchor="w", padx=8, pady=(8, 2))
        # Pack BAR (nut) xuong DAY TRUOC -> luon hien, roi Text fill phan con lai.
        bar = ttk.Frame(win); bar.pack(side="bottom", fill="x", padx=8, pady=6)
        txt = tk.Text(win, font=("Consolas", 10)); txt.pack(side="top", fill="both", expand=True, padx=8)
        cur = [x.strip() for x in self.gleaders_var.get().split(",") if x.strip()]
        txt.insert("1.0", "\n".join(cur))
        def _save_gl():
            names = [ln.strip() for ln in txt.get("1.0", "end").splitlines() if ln.strip()]
            self.gleaders_var.set(", ".join(names))
            # ghi ngay vao accounts.json: chi update party_leaders cua profile DANG CHON, giu cac key khac
            try:
                d = _load_profiles()
                prof = d["profiles"].setdefault(self._active, {"channel": 2, "parties": []})
                prof["party_leaders"] = names
                d["active"] = self._active
                _save_profiles(d)
                self._prof = d
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không lưu được: {e}"); return
            self._update_gl_btn()
            win.destroy()
        ttk.Button(bar, text="💾 Lưu", command=_save_gl).pack(side="right")
        ttk.Button(bar, text="Hủy", command=win.destroy).pack(side="right", padx=4)

    def _save(self):
        try:
            ch = int(self.ch_var.get().strip() or 2)
        except ValueError:
            messagebox.showerror("Lỗi", "Kênh phải là số."); return
        # party DANG SUA -> de quay ve dung tab do o GUI chinh sau khi luu
        cur_pidx = self._cur_party_index()
        # tab DA mo (cfg dung) -> lay tu UI; tab CHUA mo -> giu nguyen preset (khong sua)
        parties = [p for p in self._snapshot() if p.get("accounts")]   # bo party rong
        # CAP 5: party game toi da 5 (1 leader + 4 member). Dem acc DANG TICK (on) co user.
        for i, p in enumerate(parties):
            n_on = sum(1 for a in p["accounts"] if a.get("on", True) and a.get("u", "").strip())
            if n_on > 5:
                messagebox.showerror("Lỗi", f"Party {i + 1} đang có nhiều hơn 5 thành viên "
                                     f"({n_on}). Bỏ tick bớt cho còn tối đa 5.")
                return
        gleaders = [x.strip() for x in self.gleaders_var.get().split(",") if x.strip()]
        data = {"channel": ch, "party_leaders": gleaders, "parties": parties}
        # CANH BAO: doi profile (active != luc mo dialog) khi DANG CHAY -> stop het acc thay doi.
        switching = (self._active != self._orig_active)
        running = bool(getattr(ctrl, "account_clients", {}))
        if switching and running:
            if not messagebox.askyesno("Đổi cấu hình",
                    f"Đang chạy. Đổi sang cấu hình '{self._active}' sẽ STOP các acc bị thay đổi "
                    "rồi áp dụng. Tiếp tục?"):
                return
        # luu vao profile dang chon -> ghi ca {active, profiles} vao accounts.json (bot tu rut active)
        self._prof["profiles"][self._active] = data
        self._prof["active"] = self._active
        _save_profiles(self._prof)
        master = self.master
        self.destroy()
        if hasattr(master, "reload_config"):
            master.reload_config()   # tu nap lai - khong can dong app
        # chuyen GUI chinh ve dung party (group + sub-tab) vua sua
        try:
            gidx = master.group_of.get(cur_pidx)
            if gidx is not None:
                master.nb.select(master.group_frames[gidx])
                sub = master.group_nb.get(gidx)
                subf = master.party_subframes.get(cur_pidx)
                if sub is not None and subf is not None:
                    sub.select(subf)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        try:   # anti-debug guard (no-op khi khong co debugger / khi ATS_NO_GUARD=1)
            from bot import _guard
            _guard.check_debugger(); _guard.start_watch()
        except Exception:
            pass
        _setup_log_capture()
        BotGUI().mainloop()
    except Exception as e:
        import traceback
        try:
            with open("gui_error.log", "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showerror("Loi GUI", f"{e}\n\nXem gui_error.log")
        except Exception:
            pass
