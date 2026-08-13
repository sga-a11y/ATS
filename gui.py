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
import importlib.util   # can cho _BundleFirstFinder (spec_from_file_location)
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

_LABEL_RE = re.compile(r"^\d\d:\d\d:\d\d \[([^\]]+)\]")

class _BundleFirstFinder:
    """Ep code bot lay tu CORE BUNDLE thay vi ban da bien dich san trong .exe.

    BUG THAT (08/08): exe build bang Nuitka voi "--include-package=bot --follow-imports" nen
    gui.py, run_party_digioi.py VA bot/*.py deu nam CUNG trong binary. Nuitka nap module compiled
    qua sys.meta_path, ma sys.meta_path duoc xet TRUOC sys.path -> viec chen bundle vao sys.path
    (o duoi) KHONG bao gio thang duoc => core bundle moi tai ve bi bo qua, user chay code cu
    (xac nhan thuc te: exe 07/08 van chay client.py cu du core da la ban 08/08).

    Finder nay cam o sys.meta_path[0] nen duoc hoi TRUOC Nuitka: co file trong bundle thi dung
    bundle, khong co thi tra None -> tu dong roi ve ban compiled (exe chay duoc khi chua co bundle).
    Nho vay sua bot/*.py CHI CAN core update, khong phai cai lai exe (dung y do thiet ke 04/08).
    """

    _TOP_LEVEL = ("bot", "run_party_digioi")

    def __init__(self, root):
        self._root = root

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] not in self._TOP_LEVEL:
            return None
        rel = fullname.replace(".", os.sep)
        pkg_dir = os.path.join(self._root, rel)
        pkg_init = os.path.join(pkg_dir, "__init__.py")
        mod_py = os.path.join(self._root, rel + ".py")
        try:
            if os.path.isfile(pkg_init):
                return importlib.util.spec_from_file_location(
                    fullname, pkg_init, submodule_search_locations=[pkg_dir])
            if os.path.isfile(mod_py):
                return importlib.util.spec_from_file_location(fullname, mod_py)
        except Exception:
            return None
        return None


def _bootstrap_bundle_path():
    cand = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    if cand and "python" not in os.path.basename(cand).lower() and os.path.isfile(cand):
        base = os.path.dirname(cand)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    bundle_pc = os.path.join(base, "bot_bundle", "current", "pc")
    if (os.path.isfile(os.path.join(bundle_pc, "run_party_digioi.py"))
            and os.path.isfile(os.path.join(bundle_pc, "bot", "config.py"))):
        sys.path.insert(0, bundle_pc)
        # Chen TRUOC importer cua Nuitka (xem _BundleFirstFinder) - bat buoc, neu khong bundle
        # chi nam trong sys.path va khong bao gio duoc dung.
        try:
            if not any(isinstance(f, _BundleFirstFinder) for f in sys.meta_path):
                sys.meta_path.insert(0, _BundleFirstFinder(bundle_pc))
        except Exception:
            pass   # loi cam finder -> van chay duoc bang code compiled trong exe


_bootstrap_bundle_path()
_gui_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1 if sys.path and os.path.basename(sys.path[0]) == "pc" else 0, _gui_dir)
import run_party_digioi as ctrl          # module dieu khien (da refactor)
from bot import config
from bot._appdir import app_dir as _app_dir   # thu muc goc (dev=project, frozen=canh .exe)

log = logging.getLogger("bot")   # -> hien o panel log GUI (qua _QueueHandler tren root)

ACCOUNTS_JSON = os.path.join(_app_dir(), "accounts.json")
DONATE_CHAT_URL = "https://zalo.me/g/qiy6aflscqbh6v4tivej"
TEAM_DUNGEON_LEVELS = (20, 50, 80, 110)
DEFAULT_TEAM_DUNGEONS = {20: True, 50: True, 80: True, 110: False}
SHOP_ITEM_KEYS = ("ho_phu", "thien_chau", "bao_hop")
DEFAULT_SHOP_ITEMS = {"ho_phu": False, "thien_chau": False, "bao_hop": False}


def _normalize_team_dungeons(value):
    out = dict(DEFAULT_TEAM_DUNGEONS)
    if isinstance(value, dict):
        for lv in TEAM_DUNGEON_LEVELS:
            if str(lv) in value:
                out[lv] = bool(value.get(str(lv)))
            elif lv in value:
                out[lv] = bool(value.get(lv))
    elif isinstance(value, (list, tuple, set)):
        enabled = {int(x) for x in value if str(x).isdigit()}
        for lv in TEAM_DUNGEON_LEVELS:
            out[lv] = lv in enabled
    return out


def _team_dungeons_json(value):
    norm = _normalize_team_dungeons(value)
    return {str(lv): bool(norm.get(lv, False)) for lv in TEAM_DUNGEON_LEVELS}


def _normalize_shop_items(value, legacy=None):
    out = dict(DEFAULT_SHOP_ITEMS)
    if isinstance(legacy, dict):
        for key in SHOP_ITEM_KEYS:
            if key in legacy:
                out[key] = bool(legacy.get(key))
    if isinstance(value, dict):
        for key in SHOP_ITEM_KEYS:
            if key in value:
                out[key] = bool(value.get(key))
    elif isinstance(value, (list, tuple, set)):
        enabled = {str(x) for x in value}
        for key in SHOP_ITEM_KEYS:
            out[key] = key in enabled
    return out


def _shop_items_json(value):
    norm = _normalize_shop_items(value)
    return {key: bool(norm.get(key, False)) for key in SHOP_ITEM_KEYS}


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
    "mineral": "Quái khoáng",
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
    "dangerous_npc": "NPC nguy hiểm",
    "enemy_low_hp": "Quái ít HP nhất",
    "enemy_high_hp": "Quái nhiều HP nhất",
    "enemy_first": "Quái đầu",
    "enemy_last": "Quái cuối",
    "ally_low_hp": "Đồng đội ít HP nhất",
    "ally_high_hp": "Đồng đội nhiều HP nhất",
    "ally_low_sp": "Đồng đội ít SP nhất",
    "ally_revive_skill": "Đồng đội có skill Hồi sinh",
    "ally_protect_skill": "Đồng đội có skill bảo vệ",
    "self": "Bản thân",
}
LABEL_BATTLE_TARGETS = {v: k for k, v in BATTLE_TARGET_LABELS.items()}


def _load_donate_qr_image():
    from bot.donate_qr_data import DONATE_QR_PNG_B64
    return tk.PhotoImage(data=DONATE_QR_PNG_B64)


def _load_group_qr_image():
    from bot.group_qr_data import GROUP_QR_PNG_B64
    return tk.PhotoImage(data=GROUP_QR_PNG_B64)


# Party MAU cho profile moi (placeholder de user thay = acc that)
# Mac dinh mode TRAIN map Rung Noi Huynh (12831) - nhieu user tao acc xong KHONG chon che do,
# de "stand" (dung yen) thi bot khong lam gi -> tuong bot loi. Train Noi Huynh chay duoc ngay.
_DEFAULT_PARTY = {"server": "trieu_van", "mode": "train", "start_city_id": 12831, "mob_index": -1,
                  "city_flag": 0, "do_daily": True, "claim_offline_exp": True,
                  "auto_world_boss": True,
                  "auto_team_dungeon": True, "team_dungeons": _team_dungeons_json(DEFAULT_TEAM_DUNGEONS),
                  "auto_sell_noi_dat": True, "auto_bag_clean": True,
                  "auto_discard_junk": True, "auto_decompose_scrolls": False,
                  "auto_donate_materials": True,
                  "auto_buy_shop": False,
                  "shop_items": _shop_items_json(DEFAULT_SHOP_ITEMS), "leaders": [],
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
        _MAP_NAMES.setdefault(55002, "Nhà Nam Tinh Quân")   # map di-bo dac biet (khong teleport)
    nm = _MAP_NAMES.get(mid)
    if nm:
        return nm
    # Khong nam trong cac bang gõ tay o tren -> lay TEN THEO GAME (scene_names.json, boc tu
    # Data/TextData_C.dat). Truoc day rot thang ve str(mid) nen cac tang thap 2K hien so tho
    # (12931...). config.map_display_name them ca so tang cho thap event.
    try:
        return config.map_display_name(mid)
    except Exception:
        return str(mid)


_DEFAULT_GROUP = "Chưa phân nhóm"   # nhom mac dinh cho map chua gan group


class ComboSearch:
    """Autocomplete cho ttk.Combobox editable: GO TEXT -> popup listbox loc theo (ten/id/nhom) bung
    NGAY duoi combobox, KHONG cuop focus (van go tiep). Xuong/Len di chuyen (bo qua dong header
    nhom), Enter/click chon, Esc dong. Roi o ma text khong khop -> snap ve map dau.
      key_fn   : record -> chuoi de MATCH (vd 'ten id nhom')
      label_fn : record -> chuoi HIEN THI = gia tri set vao combobox
      group_fn : record -> ten nhom (None = khong gom nhom, list phang)."""
    def __init__(self, combo, items, key_fn, label_fn, on_pick, group_fn=None):
        self.combo = combo; self.items = items
        self.key_fn = key_fn; self.label_fn = label_fn; self.on_pick = on_pick
        self.group_fn = group_fn
        self.top = None; self.lb = None
        self._rows = []                # [(is_map, label, group)] song song listbox
        self._collapsed = set()        # ten nhom dang THU GON (click header de mo/thu)
        self._q = ""                   # query loc HIEN TAI (go -> text; click browse -> "" = hien het)
        combo.configure(values=[label_fn(r) for r in items])
        combo.bind("<KeyRelease>", self._on_key)
        combo.bind("<FocusOut>", lambda e: combo.after(160, self._maybe_hide))
        combo.bind("<Down>", self._nav); combo.bind("<Up>", self._nav)
        combo.bind("<Return>", self._enter); combo.bind("<Escape>", lambda e: self.hide())
        # Click vao combobox (ke ca tam giac ▼) -> hien popup NHOM cua ta (khong phai dropdown native
        # phang). 'break' chan native dropdown mo dong thoi. Click lai -> dong.
        combo.bind("<Button-1>", self._on_click)

    def _matched(self, q):
        return list(self.items) if not q else [r for r in self.items if q in self.key_fn(r).lower()]

    def _group_order(self):
        order = []
        for r in self.items:
            g = self.group_fn(r)
            if g != _DEFAULT_GROUP and g not in order:
                order.append(g)
        if any(self.group_fn(r) == _DEFAULT_GROUP for r in self.items):
            order.append(_DEFAULT_GROUP)
        return order

    def _build_rows(self, q):
        matched = self._matched(q)
        if not self.group_fn:
            return [(True, self.label_fn(r), None) for r in matched]
        shown_groups = [g for g in self._group_order()
                        if any(self.group_fn(r) == g for r in matched)]
        # chua gom nhom (chi 'Chua phan nhom') -> list phang, khong header thua
        if len(shown_groups) <= 1 and shown_groups and shown_groups[0] == _DEFAULT_GROUP:
            return [(True, self.label_fn(r), None) for r in matched]
        rows = []
        for g in shown_groups:
            # dang GO TIM (q) -> mo het de thay ket qua; chi DUYET (q rong) moi ton trong thu gon.
            collapsed = (not q) and (g in self._collapsed)
            rows.append((False, ("▶ " if collapsed else "▼ ") + g, g))
            if not collapsed:
                for r in matched:
                    if self.group_fn(r) == g:
                        rows.append((True, "    " + self.label_fn(r), None))
        return rows

    def _on_key(self, e):
        if e.keysym in ("Up", "Down", "Return", "Escape", "Left", "Right", "Tab"):
            return
        self._q = self.combo.get().strip().lower()   # GO -> loc theo text
        self.combo["values"] = [self.label_fn(r) for r in self._matched(self._q)]
        self.show()

    def show(self):
        rows = self._build_rows(self._q)
        if not rows:
            self.hide(); return
        self._rows = rows
        if self.top is None or not self.top.winfo_exists():
            self.top = tk.Toplevel(self.combo); self.top.wm_overrideredirect(True)
            try:
                self.top.attributes("-topmost", True)
            except Exception:
                pass
            self.lb = tk.Listbox(self.top, exportselection=False, activestyle="dotbox")
            self.lb.pack()
            self.lb.bind("<ButtonRelease-1>", self._click)
        self.lb.delete(0, "end")
        for i, (is_map, label, _g) in enumerate(rows):
            self.lb.insert("end", label)
            if not is_map:
                self.lb.itemconfig(i, foreground="#0a6")   # header nhom mau khac
        self.lb.configure(height=min(14, len(rows)),
                          width=max(20, int(self.combo.cget("width"))))
        x = self.combo.winfo_rootx()
        y = self.combo.winfo_rooty() + self.combo.winfo_height()
        self.top.wm_geometry("+%d+%d" % (x, y))
        self.top.deiconify(); self.top.lift()

    def hide(self):
        if self.top is not None and self.top.winfo_exists():
            self.top.withdraw()

    def _shown(self):
        return self.top is not None and self.top.winfo_exists() and self.top.winfo_ismapped()

    def _map_rows(self):
        return [i for i, row in enumerate(self._rows) if row[0]]

    def _maybe_hide(self):
        try:
            if self.combo.focus_get() is self.lb:
                return
        except Exception:
            pass
        self.hide()
        cur = self.combo.get()
        labels = [self.label_fn(r) for r in self.items]
        if cur not in labels:                       # go do dang -> snap ve map khop dau
            hit = self._matched(cur.strip().lower())
            if hit:
                self.combo.set(self.label_fn(hit[0])); self.on_pick()

    def _nav(self, e):
        if not self._shown():
            self.show()
        maps = self._map_rows()
        if not maps:
            return "break"
        cur = self.lb.curselection()
        ci = cur[0] if cur else -1
        # tim dong MAP ke tiep/truoc (bo qua header)
        if e.keysym == "Down":
            nxt = next((i for i in maps if i > ci), maps[0])
        else:
            nxt = next((i for i in reversed(maps) if i < ci), maps[-1])
        self.lb.selection_clear(0, "end"); self.lb.selection_set(nxt); self.lb.see(nxt)
        return "break"

    def _enter(self, e):
        if self._shown():
            cur = self.lb.curselection()
            i = cur[0] if cur else (self._map_rows()[0] if self._map_rows() else None)
            if i is not None:
                self._choose_row(i)
            return "break"

    def _on_click(self, e):
        self.combo.focus_set()
        # Boi den HET text dang co -> go ky tu dau la TU THAY (khoi phai Ctrl+A xoa map cu).
        self.combo.after(1, lambda: self.combo.selection_range(0, "end"))
        if self._shown():
            self.hide()
        else:
            self._q = ""                     # click browse -> hien HET nhom (khong loc theo map dang chon)
            self.combo.after(1, self.show)   # sau 1ms de combobox xu ly click xong
        return "break"                       # chan dropdown native (phang) mo cung luc

    def _click(self, e):
        cur = self.lb.curselection()
        if cur:
            self._choose_row(cur[0])

    def _choose_row(self, i):
        if not (0 <= i < len(self._rows)):
            return
        is_map, label, group = self._rows[i]
        if is_map:                                             # dong MAP -> chon
            self._choose(label.strip())
        elif group is not None:                                # HEADER nhom -> thu gon / mo lai
            if group in self._collapsed:
                self._collapsed.discard(group)
            else:
                self._collapsed.add(group)
            self.show()   # dung lai popup theo trang thai moi. KHONG focus_set(combo) -> tranh
            # _maybe_hide (FocusOut) an popup + snap ve map dau (bug "click nhom chon map dau").

    def _choose(self, label):
        self.combo.set(label); self.hide(); self.on_pick()


# ---------------- App ----------------
class BotGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        try:
            from bot._version import VERSION as _VER
        except Exception:
            _VER = "?"
        self._app_version = _VER
        self._version = _VER
        try:
            from bot import updater as _updater
            if _updater.is_frozen():
                self._app_version = _updater.installed_app_version(_VER)
                self._version = _updater.effective_version(_VER)
        except Exception:
            pass
        self.title(f"TS Online Bot Manager v{self._version}")
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
                bundle_info = updater.check_bundle_update(self._app_version)
                if bundle_info:
                    bver, burl, _bnotes = bundle_info
                    log.info("update: CO CORE BUNDLE MOI v%s -> tu tai va ap dung", bver)
                    updater.download_and_apply_bundle(burl, bver)
                    self.after(0, lambda v=bver: self._restart_after_bundle_update(v))
                    return
                info = updater.check_update(self._app_version)
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
                log.info("update: CO BAN MOI v%s (app %s, core %s) -> hoi user",
                         info[0], self._app_version, self._version)
                self.after(0, lambda: self._prompt_update(*info))
            else:
                log.info("update: dang la ban moi nhat (core v%s, app v%s)",
                         self._version, self._app_version)
                if manual:
                    self.after(0, lambda: messagebox.showinfo(
                        "Update",
                        f"Dang la ban moi nhat: core v{self._version}\nApp: v{self._app_version}",
                        parent=self))
        threading.Thread(target=worker, daemon=True).start()

    def _restart_after_bundle_update(self, ver):
        self._version = str(ver)
        self.title(f"TS Online Bot Manager v{self._version}")
        if bool(getattr(ctrl, "account_clients", {})):
            messagebox.showinfo(
                "Update",
                f"Da cap nhat core v{ver}. Dung bot va mo lai app de ap dung.",
                parent=self,
            )
            return
        log.info("update: da cap nhat core v%s -> khoi dong lai app de ap dung", ver)
        try:
            from bot import updater
            updater.restart_app()
        except Exception as e:
            messagebox.showinfo(
                "Update",
                f"Da cap nhat core v{ver}. Hay dong/mo lai app de ap dung.\n\nChi tiet: {e}",
                parent=self,
            )

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
        try:
            gimg = _load_group_qr_image()
            gscale = max(1, (max(gimg.width(), gimg.height()) + 219) // 220)
            if gscale > 1:
                gimg = gimg.subsample(gscale, gscale)
            top._group_qr_img = gimg
            ttk.Label(box, image=gimg).pack(pady=(8, 4))
        except Exception:
            pass
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
        text = "_".join(parts)
        if s.get("party_avg_level"):
            text += f" ({s['party_avg_level']})"
        return text

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

    def _force_resync(self, pidx):
        """BAM header 'Vai tro' -> EP DONG BO ca party theo leader (uu tien cao nhat): moi acc thoat
        hanh dong/vong cho hien tai + relogin bam leader. Dung khi party bi lech/ket barrier."""
        import tkinter.messagebox as mb
        if not mb.askyesno("Ép đồng bộ",
                           f"P{pidx + 1}: ÉP CẢ PARTY đồng bộ lại theo leader?\n\n"
                           "Mọi acc sẽ THOÁT hành động hiện tại + relogin bám leader.\n"
                           "Dùng khi party bị lệch nhịp / kẹt chờ vô hạn."):
            return
        threading.Thread(target=ctrl.request_party_resync, args=(pidx, "GUI"), daemon=True).start()

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
            lb.insert("end", "Đi bộ từ map AAA đến map BBB")
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
        # Mac dinh AAA = MAP DANG DUNG cua party (lay tu acc dang chay dau tien co current_map).
        # User muon di tu cho khac thi tu sua lai / xoa trong de bot tu chon thanh gan BBB.
        _cur = ""
        try:
            for (_u, _p, _lead, _pick) in ctrl.party_accounts(pidx):
                _c = ctrl.account_clients.get(_u)
                _m = getattr(_c, "current_map", None) if _c is not None else None
                if _m:
                    _cur = str(int(_m)); break
        except Exception:
            _cur = ""
        src_var = tk.StringVar(value=_cur)
        dst_var = tk.StringVar()
        ttk.Entry(box, textvariable=src_var, width=18).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(box, text="Map BBB:").grid(row=2, column=0, sticky="e", padx=(0, 6), pady=4)
        dst_entry = ttk.Entry(box, textvariable=dst_var, width=18)
        dst_entry.grid(row=2, column=1, sticky="w", pady=4)

        def _pick_city():
            # Popup list thanh da mo -> chon 1 thanh thi dien city_id (= map id) vao o BBB.
            # Them cac map di-bo dac biet (khong teleport duoc) o DAU danh sach.
            extra = [("Nhà Nam Tinh Quân", 55002)]
            choices = extra + [(_n, _cid) for (_cid, _f, _n) in self.cities]
            pick = tk.Toplevel(win); pick.title("Chọn Thành đích")
            pick.transient(win); pick.grab_set()
            lb2 = tk.Listbox(pick, width=28, height=min(20, max(4, len(choices))), font=("", 10))
            lb2.pack(fill="both", expand=True, padx=8, pady=8)
            for (_n, _cid) in choices:
                lb2.insert("end", _n)
            def _choose():
                s = lb2.curselection()
                if s:
                    dst_var.set(str(choices[s[0]][1]))
                pick.destroy()
            lb2.bind("<Double-1>", lambda _e: _choose())
            ttk.Button(pick, text="Chọn", command=_choose).pack(pady=(0, 8))
        ttk.Button(box, text="Chọn Thành", command=_pick_city).grid(
            row=2, column=2, sticky="w", padx=(6, 0), pady=4)

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
        self.party_agi_buttons = {} # pidx -> nut Check AGI/canh bao do lech
        self.party_notify_buttons = {}  # pidx -> nut "Chu y" (an neu party khong co thong bao)
        self._bag_notify_dismissed = set()  # username da bam "Bo qua" thong bao tui day (an phien nay)
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
        mlbl = {"digioi": "Dị Giới", "train": "Train map", "digioi_train": "DG + Train",
                "city": "Về thành",
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
        # (Bo nut "Start acc chon" - user moi hay bam nham thay vi Start party. Thay bang
        #  DOUBLE-CLICK 1 dong acc de start rieng acc do - xem tree.bind <Double-1> ben duoi.)
        ttk.Button(btns, text="■ Stop acc chọn",
                   command=lambda p=pidx: self._stop_sel(p)).pack(side="left", padx=2)
        ttk.Separator(btns, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(btns, text="🎟 Nhập giftcode",
                   command=lambda p=pidx: self._redeem_giftcode(p)).pack(side="left", padx=2)
        agi_btn = tk.Button(btns, text="⚡ Check AGI", relief="raised", padx=8,
                            command=lambda p=pidx: self._show_party_agi(p))
        agi_btn.pack(side="left", padx=2)
        self.party_agi_buttons[pidx] = agi_btn
        # Nut "Chu y": AN mac dinh (pack luc co thong bao). Party co nick can thong bao (vd item lo
        # de "Thong bao") -> hien nut; click -> dialog danh sach thong bao (mua ho / bo qua).
        notify_btn = tk.Button(btns, text="⚠ Chú ý", relief="raised", padx=8,
                               bg="#fff3cd", fg="#8a6d00", activebackground="#ffe69c",
                               command=lambda p=pidx: self._show_party_notify(p))
        self.party_notify_buttons[pidx] = notify_btn   # chua pack -> an; _update_notify_buttons se hien
        tree = ttk.Treeview(frame, columns=self._COLS, show="headings", height=max(len(accs), 3))
        for col in self._COLS:
            if col in ("acc", "char"):   # BAM header de che/hien tai khoan + ten (3 trang thai)
                tree.heading(col, text=self._priv_head(col), command=self._toggle_privacy)
            elif col == "role":          # BAM header Vai tro -> EP DONG BO ca party theo leader
                tree.heading(col, text=self._HEADS[col] + " ↧",
                             command=lambda p=pidx: self._force_resync(p))
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
        tree.bind("<Double-1>", lambda e, p=pidx: self._on_acc_dblclick(p, e))
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
        threading.Thread(target=ctrl.stop_all, args=("GUI Stop tat ca",), daemon=True).start()

    def _start_party(self, pidx):
        threading.Thread(target=ctrl.start_party, args=(pidx,), daemon=True).start()

    def _stop_party(self, pidx):
        threading.Thread(target=ctrl.stop_party, args=(pidx, "GUI Stop party"), daemon=True).start()

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

    def _show_party_agi(self, pidx):
        report = ctrl.party_agi_report(pidx)
        win = tk.Toplevel(self)
        win.title(f"Check AGI - Party {pidx + 1}")
        win.transient(self)
        rows = report["rows"]
        win.geometry("520x320")
        spread = report["spread"]
        if spread is None:
            summary = "Chưa có dữ liệu AGI. Hãy chạy party và chờ các acc login xong."
            color = "#666666"
        else:
            summary = (f"Thấp nhất: {report['min']}    Cao nhất: {report['max']}    "
                       f"Chênh lệch: {spread}")
            if report["warning"]:
                summary += "  ⚠ Lệch AGI quá 10, khó combo"
            color = "#b45309" if report["warning"] else "#166534"
        tk.Label(win, text=summary, fg=color, font=("", 10, "bold"),
                 anchor="w").pack(fill="x", padx=10, pady=(10, 6))
        columns = (("char", "Nhân vật", 150), ("char_agi", "AGI char", 75),
                   ("pet", "Pet đang dùng", 150), ("pet_agi", "AGI pet", 75))
        tree = ttk.Treeview(win, columns=tuple(key for key, _title, _width in columns),
                            show="headings", height=8)
        for key, title, width in columns:
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="center")
        for row in rows:
            char = row.get("char") or row.get("username") or "-"
            if char and char != "-" and char != row.get("username"):
                self._char2user[char] = row.get("username")
            if char == row.get("username"):
                char = self._mask_user(char)
            else:
                char = self._mask_char(char)
            tree.insert("", "end", values=(char,
                        row["char_agi"] if row["char_agi"] is not None else "—",
                        row["pet"] or "—",
                        row["pet_agi"] if row["pet_agi"] is not None else "—"))
        tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        ttk.Button(win, text="Đóng", command=win.destroy).pack(pady=(0, 10))

    def _on_acc_dblclick(self, pidx, event):
        # Double-click 1 dong acc -> start RIENG acc do (thay cho nut "Start acc chon" cu, tranh
        # user moi bam nham thay vi Start party).
        tree = self.party_trees[pidx]
        u = tree.identify_row(event.y)
        if not u:
            return
        accs = {a: (p, lead, pick) for (a, p, lead, pick) in ctrl.party_accounts(pidx)}
        if u in accs:
            p, lead, pick = accs[u]
            threading.Thread(target=ctrl.start_account, args=(u, p, pidx, lead, pick),
                             daemon=True).start()

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
            threading.Thread(target=ctrl.stop_account, args=(u, "GUI Stop acc chon"), daemon=True).start()

    # ---- refresh status ----
    # ---- THONG BAO PARTY (hien tai: lo; sau nay them tui day / het thuoc...) ----
    def _party_bag_notify(self, pidx):
        """List (username, {_bag}) cho acc co slot tui trong <=5 (chua bam Bo qua). Tui LEN DAU."""
        out = []
        try:
            accs = ctrl.party_accounts(pidx)
        except Exception:
            return out
        for (u, _p, _l, _pk) in accs:
            if u in self._bag_notify_dismissed:
                continue
            c = ctrl.account_clients.get(u)
            if c is None or not getattr(c, "running", False):
                continue
            try:
                if not getattr(c, "bag_slots", None):   # chua co snapshot tui -> chua tinh duoc
                    continue
                free = c.bag_free_slots()
                if free > 5:
                    continue
                out.append((u, {"_bag": True, "used": c.bag_used_slots(),
                                "cap": c.bag_capacity(), "free": free, "maxed": c.bag_slot_maxed()}))
            except Exception:
                continue
        return out

    def _party_notify_items(self, pidx):
        """List (username, item): thong bao TUI (len dau) + thong bao LO (account_furnace_notify)."""
        out = list(self._party_bag_notify(pidx))
        try:
            accs = ctrl.party_accounts(pidx)
        except Exception:
            return out
        notify = getattr(ctrl, "account_furnace_notify", {}) or {}
        for (u, _p, _l, _pk) in accs:
            for it in list(notify.get(u) or []):
                out.append((u, it))
        return out

    def _party_notify_count(self, pidx):
        return len(self._party_notify_items(pidx))

    def _furnace_notify_line(self, username, it):
        _u = self._mask_user(username)
        tab = it.get("tab"); nm = (it.get("name") or "?").strip()
        # ITEM LA = id KHONG co trong furnace_pool.json (game update them item moi). Engine da danh
        # dau "new" tu lau nhung UI chua dung -> nhin y het item thuong. Phai neu ro de user chu y.
        _new = " ⚠ ITEM LẠ (ngoài danh sách đã biết)" if it.get("new") else ""
        if tab == "trang_bi":
            # Ten DAI kem chi so (giong hien thi trong list) - chi co ten thi khong quyet dinh
            # duoc co dang mua hay khong.
            _tid = it.get("id")
            if _tid:
                nm = PartyConfigFrame._equip_display("0x%04x" % int(_tid), nm)
            return f'{_u} soi lò trang bị thường có "{nm}" - trong túi đang có {it.get("bag", 0)} món{_new}'
        if tab == "vo_tuong":
            return f'{_u} soi lò võ tướng thường có "{nm}"{_new}'
        if tab == "chuyen_sinh":
            return f'{_u} soi lò chuyển sinh thường có "{nm}"{_new}'
        return f'{_u}: lò có "{nm}"{_new}'

    def _furnace_buy_for(self, username, it):
        c = ctrl.account_clients.get(username)
        if c is None or not getattr(c, "running", False):
            return False
        try:
            return bool(c.buy_furnace_item(it["kind"], it["slot"], it["id"]))
        except Exception:
            return False

    def _remove_notify(self, username, it):
        lst = (getattr(ctrl, "account_furnace_notify", {}) or {}).get(username)
        if lst:
            try:
                lst.remove(it)
            except ValueError:
                pass

    def _show_party_notify(self, pidx):
        items = self._party_notify_items(pidx)
        win = tk.Toplevel(self); win.title(f"Chú ý - Party {pidx + 1}")
        win.transient(self.winfo_toplevel()); win.grab_set(); win.geometry("580x430")
        ttk.Label(win, text="Thông báo của party (hiện tại: lò):",
                  font=(None, 10, "bold")).pack(anchor="w", padx=10, pady=(8, 4))
        _cv = tk.Frame(win); _cv.pack(fill="both", expand=True, padx=8, pady=4)
        canvas = tk.Canvas(_cv, highlightthickness=0)
        sb = ttk.Scrollbar(_cv, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)

        def _add_row(u, it):
            rowf = ttk.Frame(inner); rowf.pack(fill="x", pady=2)
            # --- THONG BAO TUI DAY (len dau) ---
            if it.get("_bag"):
                used, cap, maxed = it["used"], it["cap"], it["maxed"]
                ttk.Button(rowf, text="Bỏ qua", width=7,
                           command=lambda: (self._bag_notify_dismissed.add(u), rowf.destroy())).pack(side="right", padx=2)
                if not maxed:
                    buybtn = tk.Button(rowf, text="Mua slot\n(đang xem giá...)", justify="center")
                    def _buy_slot():
                        buybtn.configure(state="disabled")
                        import threading as _t
                        def _do():
                            c = ctrl.account_clients.get(u)
                            try: ok = bool(c and c.buy_bag_slot())
                            except Exception: ok = False
                            def _done():
                                if ok:
                                    rowf.destroy()   # +5 slot -> bo dong nay
                                elif buybtn.winfo_exists():
                                    buybtn.configure(state="normal")
                                    messagebox.showwarning("Mua slot",
                                        "Mua slot không thành công (acc tắt / hết vàng / đã tối đa).", parent=win)
                            self.after(0, _done)
                        _t.Thread(target=_do, daemon=True).start()
                    buybtn.configure(command=_buy_slot); buybtn.pack(side="right", padx=2)
                    import threading as _t2
                    def _price():
                        c = ctrl.account_clients.get(u)
                        try: pr = c and c.query_bag_slot_price()
                        except Exception: pr = None
                        _txt = f"Mua slot\n{pr[0]} vàng" if pr else "Mua slot\n(?)"
                        self.after(0, lambda: buybtn.winfo_exists() and buybtn.configure(text=_txt))
                    _t2.Thread(target=_price, daemon=True).start()
                    _line = f'{self._mask_user(u)} túi đồ sắp đầy {used}/{cap}'
                else:
                    _line = f'{self._mask_user(u)} túi đồ ĐẦY {used}/{cap} (đã tối đa slot, không mua thêm được)'
                ttk.Label(rowf, text=_line, wraplength=380, justify="left").pack(side="left", fill="x", expand=True)
                return
            # --- THONG BAO LO ---
            ttk.Button(rowf, text="Bỏ qua", width=7,
                       command=lambda: (self._remove_notify(u, it), rowf.destroy())).pack(side="right", padx=2)

            def _buy():
                self._remove_notify(u, it); rowf.destroy()   # optimistic: xoa nut ngay
                import threading as _t
                def _do():
                    ok = self._furnace_buy_for(u, it)
                    if not ok:
                        self.after(0, lambda: messagebox.showwarning(
                            "Mua", "Mua không thành công (acc tắt / hết chips / lò đã đổi).", parent=win))
                _t.Thread(target=_do, daemon=True).start()
            ttk.Button(rowf, text="Mua", width=6, command=_buy).pack(side="right", padx=2)
            ttk.Label(rowf, text=self._furnace_notify_line(u, it), wraplength=400,
                      justify="left").pack(side="left", fill="x", expand=True)

        if not items:
            ttk.Label(inner, text="(không có thông báo)").pack(anchor="w", padx=4, pady=6)
        for u, it in items:
            _add_row(u, it)
        ttk.Button(win, text="Đóng", command=win.destroy).pack(pady=6)

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
            agi_report = ctrl.party_agi_report(pidx)
            agi_btn = self.party_agi_buttons.get(pidx)
            if agi_btn is not None:
                if agi_report["warning"]:
                    agi_btn.configure(text=f"⚠ Check AGI ({agi_report['spread']})",
                                      bg="#f59e0b", fg="#3b2500", activebackground="#d97706")
                else:
                    agi_btn.configure(text="⚡ Check AGI", bg="#e9ecef", fg="#111111",
                                      activebackground="#d9dde1")
            # Nut "Chu y": hien khi party CO thong bao (item lo mode notify), an neu khong.
            nbtn = self.party_notify_buttons.get(pidx)
            if nbtn is not None:
                _ncnt = self._party_notify_count(pidx)
                if _ncnt > 0:
                    nbtn.configure(text=f"⚠ Chú ý ({_ncnt})")
                    if not nbtn.winfo_ismapped():
                        nbtn.pack(side="left", padx=2)
                elif nbtn.winfo_ismapped():
                    nbtn.pack_forget()
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
                        pc.get("claim_offline_exp"), pc.get("auto_world_boss"),
                        pc.get("auto_team_dungeon"), pc.get("team_dungeons"),
                        pc.get("use_phuc_than"), pc.get("use_digioi_ho_phu"),
                        pc.get("fight_legion_boss"), pc.get("do_van_tieu"), pc.get("auto_sell_noi_dat"),
                        pc.get("auto_buy_shop"), pc.get("shop_items"),
                        pc.get("buy_ho_phu"), pc.get("buy_thien_chau"),
                        pc.get("buy_bao_hop"), pc.get("bao_hop_xu_threshold"),
                        pc.get("buy_hp"), pc.get("hp_qty"), pc.get("hp_thresh"),
                        pc.get("buy_sp"), pc.get("sp_qty"), pc.get("sp_thresh"))
            return s
        old = _sigs()
        importlib.reload(config)   # doc lai accounts.json -> PARTIES/PARTY_CONFIG moi
        new = _sigs()
        # acc dang chay ma config doi (hoac bi xoa khoi config) -> STOP
        changed = [u for u in list(ctrl.account_clients)
                   if ctrl.is_account_running(u) and old.get(u) != new.get(u)]
        for u in changed:
            ctrl.stop_account(u, reason="GUI reload config: account/party setting changed")
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
            try: ctrl.stop_all(reason="GUI dong app")
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
    ("digioi_train", "Dị Giới + Train map (hết giờ DG → cả party đi train)"),
    ("city", "Tập trung về thành (đứng yên)"),
    ("stand", "Login đâu đứng yên đó"),
    ("event", "Event"),
    ("cleanbag", "Dọn dẹp túi đồ (chưa làm)"),
]
_MODE_LABEL = dict(MODE_OPTIONS)
_LABEL_MODE = {v: k for k, v in MODE_OPTIONS}


class PartyConfigFrame(ttk.Frame):
    """1 tab cau hinh 1 party: mode (dropdown) + map/quai/thanh (dropdown) + acc."""
    _PW_MASK = "******"   # placeholder pass da luu (giau pass that khi mo lai Settings)
    def __init__(self, master, party, train_maps, cities, servers, on_apply_advanced_to_all=None,
                 on_apply_di_gioi_level=None, on_apply_heal_all=None, on_apply_furnace_all=None):
        super().__init__(master, padding=8)
        self.train_maps = train_maps   # list (map_id, name, mobs)
        self.cities = cities           # list (city_id, flag, name)
        self.servers = servers         # list (key, label)
        self.on_apply_advanced_to_all = on_apply_advanced_to_all
        self.on_apply_di_gioi_level = on_apply_di_gioi_level
        self.on_apply_heal_all = on_apply_heal_all   # ap nguong hoi mau cho MOI acc MOI party
        self.on_apply_furnace_all = on_apply_furnace_all  # ap config lo cho MOI acc MOI party
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
        # "Cap quai DG" cung NGANG HANG voi Che do (gon hon la de xuong hang dyn cung Map/Quai).
        # Hien khi mode = digioi / digioi_train (pack/pack_forget trong _render_dyn).
        # Cap quai Di Gioi: luu idx 1..15; UI hien theo cap (10..180). Mac dinh idx 2 = cap 25.
        _dg_idx = int(self._preset.get("di_gioi_level", 2))
        self.di_gioi_level_var = tk.StringVar(
            value=str(_DG_LEVELS[_dg_idx - 1] if 1 <= _dg_idx <= 15 else 25))
        self.dg_lvl_lbl = ttk.Label(row, text="  │  Cấp quái DG:")
        self.dg_lvl_cb = ttk.Combobox(row, textvariable=self.di_gioi_level_var, width=6,
                                      state="readonly", values=[str(v) for v in _DG_LEVELS])
        self.dg_apply_btn = ttk.Button(
            row, text="Áp dụng ngay",
            command=lambda: (self.on_apply_di_gioi_level(
                _dg_level_to_idx(self.di_gioi_level_var.get()))
                if getattr(self, "on_apply_di_gioi_level", None) else None))

        self.dyn = ttk.Frame(self); self.dyn.pack(fill="x", pady=6)
        self.map_var = tk.StringVar(); self.mob_var = tk.StringVar(); self.city_var = tk.StringVar()
        self.map_cb = self.mob_cb = self.city_cb = None
        # EVENT: list (key, label) tu events.json -> picker khi mode=event. Bo qua event co
        # "hidden": true (an tam - chua lam xong; giu data, bo co de hien lai).
        self.events = [(k, v.get("label", k)) for k, v in (getattr(config, "EVENTS", {}) or {}).items()
                       if not v.get("hidden")]
        self.event_var = tk.StringVar(); self.event_cb = None
        # Di Gioi: party (mac dinh, giu nguyen hanh vi cu - lap party chung, dong bo kenh) vs solo
        # (moi acc chay rieng le, khong lap party, khong dong bo kenh - dung khi acc khong can/khong
        # muon gop chung, vd khac nick khong lien quan nhau).
        self.digioi_solo_var = tk.BooleanVar(value=(self._preset.get("digioi_mode") == "solo"))

        # Bot dung yen cho leader ngoai/tay moi: slot 0 = ("","") -> khong co bot-leader.
        accs = self._preset.get("accounts", [])
        no_leader = bool(accs) and not (accs[0].get("u", "").strip())
        shown = accs[1:] if no_leader else accs
        # Hang: tick -> dung yen/accept whitelist; khong tick -> bot-leader moi them whitelist.
        nlrow = ttk.Frame(self); nlrow.pack(fill="x", pady=(2, 0))
        self.no_leader_var = tk.BooleanVar(value=no_leader)
        # Di Gioi SOLO: khong lap party that -> "chu PT" khong co y nghia gi, an checkbox nay cho
        # gon (xem _update_no_leader_visibility, goi lai moi khi doi "Kieu chay").
        self.no_leader_cb = ttk.Checkbutton(
            nlrow, text="Bot đứng yên, chờ nhận lời mời từ",
            variable=self.no_leader_var, command=self._update_no_leader_visibility)
        self.no_leader_cb.pack(side="left")
        wl = self._preset.get("leaders", [])
        self.wl_lbl = ttk.Label(nlrow, text="")
        self.wl_lbl.pack(side="left")
        self.leaders_var = tk.StringVar(value=", ".join(wl) if isinstance(wl, list) else str(wl or ""))
        self.wl_entry = ttk.Entry(nlrow, textvariable=self.leaders_var)
        self.wl_entry.pack(side="left", fill="x", expand=True, padx=4)

        # Cac setting IT KHI DOI (vd daily quest) gom vao dialog "Cai dat nang cao" (nut o hang
        # Server) thay vi 1 checkbox rieng ngay day - tranh bang cau hinh party bi day dai/roi
        # khi sau nay them setting moi. Bien van giu o day de _save()/_gather doc binh thuong.
        self.daily_var = tk.BooleanVar(value=self._preset.get("do_daily", self._preset.get("do_dungeon", True)))
        self.claim_offline_exp_var = tk.BooleanVar(value=bool(self._preset.get("claim_offline_exp", True)))
        self.auto_world_boss_var = tk.BooleanVar(value=bool(self._preset.get("auto_world_boss", True)))
        self.auto_team_dungeon_var = tk.BooleanVar(value=bool(self._preset.get("auto_team_dungeon", True)))
        self.team_dungeons = _normalize_team_dungeons(self._preset.get("team_dungeons"))
        # Su dung Phuc Than: mac dinh KHONG tick (user tu bat khi can) - logic dung item nay
        # se lam sau, hien tai chi luu setting.
        self.use_phuc_than_var = tk.BooleanVar(value=bool(self._preset.get("use_phuc_than", False)))
        # Di Gioi Ho Phu: mac dinh KHONG tick. Khi bat, chi mode Di Gioi moi dung va chi
        # khi timer con <15 phut (run_party_digioi.py check luc login + moi 5p).
        self.use_digioi_ho_phu_var = tk.BooleanVar(value=bool(self._preset.get("use_digioi_ho_phu", False)))
        # Danh boss QD: mac dinh CO tick (giu hanh vi cu - truoc gio luon danh). User tat khi
        # khong muon acc nay danh boss quan doan.
        self.fight_boss_var = tk.BooleanVar(value=bool(self._preset.get("fight_legion_boss", True)))
        # Van tieu: mac dinh CO tick (giu hanh vi cu - truoc gio luon lam). Tat -> khong nhan qua
        # escort + khong gui pet van tieu + khong hen gio check lai.
        self.van_tieu_var = tk.BooleanVar(value=bool(self._preset.get("do_van_tieu", True)))
        # Tu ban Noi Dat: mac dinh CO tick. Chi co tac dung khi bot tele trung gian ve Ng.Thanh
        # trong mode train/city; tat -> bo qua hoan toan.
        self.auto_sell_noi_dat_var = tk.BooleanVar(value=bool(self._preset.get("auto_sell_noi_dat", True)))
        # "Tu don tui do" = cong tong cua 3 muc con (Noi Dat / item rac / cuon vo tuong rac).
        # Phan giai cuon mac dinh TAT: phan giai la MAT HAN cuon, user phai tu soat list truoc.
        self.auto_bag_clean_var = tk.BooleanVar(value=bool(self._preset.get("auto_bag_clean", True)))
        self.auto_discard_junk_var = tk.BooleanVar(value=bool(self._preset.get("auto_discard_junk", True)))
        self.auto_decompose_scrolls_var = tk.BooleanVar(
            value=bool(self._preset.get("auto_decompose_scrolls", False)))
        self.scroll_modes = dict(self._preset.get("scroll_modes") or {})
        self.auto_donate_materials_var = tk.BooleanVar(
            value=bool(self._preset.get("auto_donate_materials", True)))   # mac dinh BAT
        self.material_modes = dict(self._preset.get("material_modes") or {})   # {tid:'keep'} - nguyen lieu GIU
        # Mua shop (mac dinh TAT): master "Tu mua shop" + list vat pham. Key cu van doc de
        # account.json doi cu update len khong bi mat setting.
        self.shop_items = _normalize_shop_items(self._preset.get("shop_items"), {
            "ho_phu": self._preset.get("buy_ho_phu", False),
            "thien_chau": self._preset.get("buy_thien_chau", False),
            "bao_hop": self._preset.get("buy_bao_hop", False),
        })
        self.auto_buy_shop_var = tk.BooleanVar(
            value=bool(self._preset.get("auto_buy_shop", any(self.shop_items.values())))
        )
        self.buy_ho_phu_var = tk.BooleanVar(value=bool(self.shop_items.get("ho_phu", False)))
        self.buy_thien_chau_var = tk.BooleanVar(value=bool(self.shop_items.get("thien_chau", False)))
        self.buy_bao_hop_var = tk.BooleanVar(value=bool(self.shop_items.get("bao_hop", False)))
        self.bao_hop_xu_var = tk.StringVar(value=str(self._preset.get("bao_hop_xu_threshold", 10000000)))
        # Tu mua HP/SP (mac dinh TAT): login xong tinh tong HP/SP du tru tu item trong tui;
        # neu < nguong -> di Trac Quan mua Vien Hanh Khi (+62HP) / Thien Kim Du (+62SP), so luong
        # theo o text (mua toi da theo xu, 20 xu/cai). 1 lan/ngay/acc.
        self.buy_hp_var = tk.BooleanVar(value=bool(self._preset.get("buy_hp", False)))
        self.hp_qty_var = tk.StringVar(value=str(self._preset.get("hp_qty", 9999)))
        self.hp_thresh_var = tk.StringVar(value=str(self._preset.get("hp_thresh", 500000)))
        self.buy_sp_var = tk.BooleanVar(value=bool(self._preset.get("buy_sp", False)))
        self.sp_qty_var = tk.StringVar(value=str(self._preset.get("sp_qty", 9999)))
        self.sp_thresh_var = tk.StringVar(value=str(self._preset.get("sp_thresh", 500000)))

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
            self._add_acc_row(u, a.get("p", ""), on, a.get("heal"), a.get("settings"), a.get("furnace"))
        ttk.Button(self, text="➕ Thêm dòng acc",
                   command=lambda: self._add_acc_row("", "", True)).pack(anchor="w", pady=(2, 0))
        self._render_dyn()

    def _add_acc_row(self, u="", p="", on=True, heal=None, settings=None, furnace=None):
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
               "furnace": dict(furnace) if isinstance(furnace, dict) else {},
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
        # --- SOI LO: 3 tab (tick bat + nut List chon item) ---
        furn = row.setdefault("furnace", {})
        furn_on = {}
        _fr = len(rows) + 1
        ttk.Separator(win, orient="horizontal").grid(row=_fr, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 2))
        ttk.Label(win, text="Soi lò (mua item theo list):").grid(
            row=_fr + 1, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 2))
        for j, (tab_key, pool_name, tab_label) in enumerate(self.FURNACE_TABS):
            bon = tk.BooleanVar(value=bool((furn.get(tab_key) or {}).get("on", True)))  # mac dinh TICK
            furn_on[tab_key] = bon
            ttk.Checkbutton(win, text=tab_label, variable=bon).grid(
                row=_fr + 2 + j, column=0, columnspan=2, sticky="w", padx=(8, 2), pady=1)
            ttk.Button(win, text="📋 List", width=8,
                       command=lambda tk_=tab_key, pn=pool_name, tl=tab_label:
                           self._open_furnace_list_dialog(row, tk_, pn, tl)).grid(
                row=_fr + 2 + j, column=2, sticky="w", padx=(4, 8), pady=1)
        def _save_furnace():
            # setdefault: tao entry KE CA khi chua mo List (truoc day chi luu neu tab_key da co trong
            # furn -> tick o ma chua mo List thi mat tick). Entry {"on": True} khong items van hop le
            # (engine: on=True, wl rong -> item ngoai pool van Thong bao).
            for tab_key, bon in furn_on.items():
                furn.setdefault(tab_key, {})["on"] = bool(bon.get())
        def _save():
            row["heal"] = {k: max(0, min(100, vv.get())) / 100.0 for k, vv in vars_.items()}
            row["settings"].pop("char_defend", None)
            _save_furnace()
            win.destroy()
        def _reset():
            # "Mac dinh chung": chi RESET cac o TAI CHO (khong ap dung cho ai, khong dong dialog).
            # User xem lai roi tu bam Luu / Ap dung cho tat ca.
            for k, vv in vars_.items():
                vv.set(int(round((glob_hp if k.startswith("hp") else glob_sp) * 100)))
            # Reset SOI LO ve mac dinh: tick 3 tab ON + XOA het config List (item ve default:
            # VKCD/chi so>=+40 -> Thong bao, con lai -> Bo qua). Xoa furn -> mo List thay mac dinh.
            for _bk, _bon in furn_on.items():
                _bon.set(True)
            furn.clear()
            _save_furnace()
        def _apply_all():
            # Ap NGUONG DANG CHINH + CONFIG LO (tick + LIST) cho MOI acc o MOI PARTY.
            _save_furnace()
            vals = {k: max(0, min(100, vv.get())) / 100.0 for k, vv in vars_.items()}
            import copy as _copy
            furn_snapshot = _copy.deepcopy(furn)
            if self.on_apply_heal_all:
                n = self.on_apply_heal_all(vals)
                # config lo (tick + LIST) cho MOI acc MOI party (truoc day apply_furnace_all chi ap
                # party NAY -> party khac khong sync list; tick nhin tuong sync vi mac dinh True).
                if self.on_apply_furnace_all:
                    self.on_apply_furnace_all(furn_snapshot)
                else:
                    self.apply_furnace_all(furn_snapshot)
                messagebox.showinfo("Áp dụng cho tất cả",
                                    f"Đã áp ngưỡng hồi máu + config lò cho {n} acc (tất cả party).\n"
                                    "Bấm Lưu để ghi vào cấu hình.", parent=win)
            else:   # fallback: chi party nay (khi mo doc lap, khong co callback)
                n = self.apply_heal_all(vals)
                self.apply_furnace_all(furn_snapshot)
                messagebox.showinfo("Áp dụng cho tất cả",
                                    f"Đã áp ngưỡng hồi máu + config lò cho {n} acc.", parent=win)
            win.destroy()
        bb = ttk.Frame(win); bb.grid(row=len(rows) + 6, column=0, columnspan=3, pady=(8, 2))
        ttk.Button(bb, text="↺ Mặc định chung", command=_reset).pack(side="left", padx=4)
        ttk.Button(bb, text="💾 Lưu", command=_save).pack(side="left", padx=4)
        ttk.Button(bb, text="Hủy", command=win.destroy).pack(side="left", padx=4)
        ttk.Button(win, text="📋 Áp dụng cho TẤT CẢ acc", command=_apply_all).grid(
            row=len(rows) + 7, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))

    # ---- SOI LO: pool + dialog chon item ----
    _furnace_default_notify_cache = None

    @classmethod
    def _load_furnace_default_notify(cls):
        """{pool_tab: {tid_hex: ten}} - item MAC DINH "Thong bao" (xem tools/crack_furnace_notify.py)."""
        if PartyConfigFrame._furnace_default_notify_cache is None:
            import json as _json, os as _os
            PartyConfigFrame._furnace_default_notify_cache = {}
            for p in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                    "furnace_default_notify.json"),
                      "furnace_default_notify.json"):
                try:
                    with open(p, encoding="utf-8") as fh:
                        PartyConfigFrame._furnace_default_notify_cache = _json.load(fh)
                        break
                except Exception:
                    pass
        return PartyConfigFrame._furnace_default_notify_cache

    _furnace_pool_cache = None
    FURNACE_TABS = [("vo_tuong", "Vo Tuong", "Võ Tướng thường"),
                    ("trang_bi", "Trang Bi", "Trang Bị thường"),
                    ("chuyen_sinh", "Chuyen Sinh", "Chuyển Sinh thường")]

    def _load_furnace_pool(self):
        """{pool_tab_name: {tid_hex: ten}} tu furnace_pool.json."""
        if PartyConfigFrame._furnace_pool_cache is None:
            import json as _json, os as _os
            PartyConfigFrame._furnace_pool_cache = {}
            for p in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "furnace_pool.json"),
                      "furnace_pool.json"):
                try:
                    with open(p, encoding="utf-8") as fh:
                        PartyConfigFrame._furnace_pool_cache = _json.load(fh); break
                except Exception:
                    pass
        return PartyConfigFrame._furnace_pool_cache

    _furnace_equip_cache = None
    _EQ_ATTR = {207: "hp", 208: "sp", 210: "atk", 211: "def", 212: "int",
                214: "agi", 218: "tc", 219: "nl"}
    _EQ_ELEM = {1: "địa", 2: "thủy", 3: "hỏa", 4: "phong", 5: "tâm", 7: "quang", 8: "ám"}
    _EQ_QUAL = {0: "trắng", 1: "xanh", 2: "lam", 3: "tím", 4: "đỏ"}
    _EQ_FIT = {1: "Đầu", 2: "Thân", 3: "Vũ khí", 4: "Tay", 5: "Chân", 6: "Đặc biệt", 100: "Choàng"}

    @classmethod
    def _load_equip_stats(cls):
        """{tid_hex: {n,lv,q,e,ev,a:[[kind,val]...]}} tu equip_stats.json (chi so trang bi)."""
        if PartyConfigFrame._furnace_equip_cache is None:
            import json as _json, os as _os
            PartyConfigFrame._furnace_equip_cache = {}
            for p in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "equip_stats.json"),
                      "equip_stats.json"):
                try:
                    with open(p, encoding="utf-8") as fh:
                        PartyConfigFrame._furnace_equip_cache = _json.load(fh); break
                except Exception:
                    pass
        return PartyConfigFrame._furnace_equip_cache

    def _equip_maxbonus(self, tid_hex):
        v = self._load_equip_stats().get(tid_hex)
        return max([val - 100 for _k, val in v["a"]] or [0]) if v else -999

    @classmethod
    def _equip_display(cls, tid_hex, name):
        """ten_Lv_chiso1_chiso2_..._he_pham (vd 'Kiem Ngo Vuong_Lv40_atk +10_agi +1_tím').

        classmethod: BotGUI._furnace_notify_line dung lai de THONG BAO lo trang bi hien du chi so
        (chi co ten thi khong quyet dinh duoc mua hay khong). Item lo vo tuong / chuyen sinh KHONG
        co trong equip_stats.json -> tra ve nguyen ten.
        """
        v = cls._load_equip_stats().get(tid_hex)
        if not v:
            return name
        parts = [name]
        if v.get("fit"):
            parts.append(cls._EQ_FIT.get(v["fit"], "?"))   # vi tri: Dau/Than/Vu khi/Tay/Chan
        parts.append("Lv%d" % v["lv"])
        for k, val in v["a"]:
            parts.append("%s %+d" % (cls._EQ_ATTR.get(k, "#%d" % k), val - 100))
        if v.get("e"):
            parts.append("%s %+d" % (cls._EQ_ELEM.get(v["e"], "?"), v.get("ev", 100) - 100))
        parts.append(cls._EQ_QUAL.get(v.get("q", 0), "?"))
        return "_".join(parts)

    # ---- Dong bo LIST PHAN GIAI <-> SOI LO (chi chay luc an Luu) -------------------------
    # Hai cau hinh nay de da nhau: lo "tu mua" K.Toa/Me khi tui trong -> phan giai xoa di ->
    # vong lo sau lai mua. Engine chi mua khi tui CHUA CO nen vong dot tien nay LAP VINH VIEN.
    # Luu y PHAM VI: config lo theo TUNG ACCOUNT, con list phan giai theo PARTY -> dong bo phai
    # quet MOI account trong party (neu khong, acc khac van mua roi bi pha).
    _SCROLL_TAB = {"vo_tuong": "Vo Tuong", "chuyen_sinh": "Chuyen Sinh"}

    def _scroll_owner_map(self):
        """{tid_hex mon do -> tid_hex cuon so huu}. Gom ca chinh cuon lan K.Toa/T.Tinh/Me cua no."""
        out = {}
        for tid, v in self._load_pet_scrolls().items():
            out[tid] = tid
            for e in (v.get("extra") or ()):
                out.setdefault(e, tid)
        return out

    def _sync_furnace_from_scrolls(self, newly_drop):
        """Cuon chuyen GIU -> PHAN GIAI: dat "Bo qua" cho Bi Cap + K.Toa/T.Tinh/Me cua no o lo
        cua MOI account trong party. Tra ve so muc da doi.

        Chieu nguoc lai (phan giai -> giu) KHONG lam gi: giu cuon thi mua/bao ben lo van hop ly.
        """
        data = self._load_pet_scrolls()
        want = set()
        for tid in newly_drop:
            want.add(tid)
            want.update(data.get(tid, {}).get("extra") or ())
        if not want:
            return 0
        n = 0
        for r in self.acc_rows:
            if not r["u"].get().strip():
                continue
            furn = r.setdefault("furnace", {})
            for tab_key, pool_name in self._SCROLL_TAB.items():
                pool = self._load_furnace_pool().get(pool_name, {})
                tab = furn.get(tab_key) or {}
                items = dict(tab.get("items") or {})
                for t in want & set(pool):
                    # "skip" TUONG MINH: item mac dinh Thong bao ma xoa key thi lan sau ve notify
                    if items.get(t) != "skip":
                        items[t] = "skip"
                        n += 1
                if items:
                    furn[tab_key] = {"on": tab.get("on", True), "items": items}
        return n

    def _sync_scrolls_from_furnace(self, unskipped):
        """Item lo chuyen BO QUA -> Tu mua/Thong bao: cuon so huu no ve "Giu lai".
        `unskipped` = list tid_hex. Tra ve so cuon da doi."""
        owner = self._scroll_owner_map()
        data = self._load_pet_scrolls()
        n = 0
        for t in unskipped:
            sc = owner.get(t)
            if not sc:
                continue    # mon do khong thuoc cuon nao trong list (vd tab Trang Bi)
            # scroll_modes chi luu muc KHAC mac dinh -> mac dinh da la "giu" thi xoa key di
            if data.get(sc, {}).get("vkcd"):
                if self.scroll_modes.pop(sc, None) == "drop":
                    n += 1
            elif self.scroll_modes.get(sc) != "keep":
                self.scroll_modes[sc] = "keep"
                n += 1
        return n

    def _open_furnace_list_dialog(self, row, tab_key, pool_name, tab_label):
        """Chon item lo tab `tab_key`: Treeview (ten + che do), search, moi item dropdown
        Bo/Tu mua/Bao. Sort Tu mua -> Bao -> Bo. Luu vao row['furnace'][tab_key]['items'].
        Rieng tab Trang Bi: hien ten + Lv + chi so + pham, sort theo CHI SO giam dan."""
        pool = self._load_furnace_pool().get(pool_name, {})
        if not pool:
            messagebox.showinfo("Thiếu pool", "Không đọc được furnace_pool.json."); return
        furn = row.setdefault("furnace", {})
        cur = dict((furn.get(tab_key) or {}).get("items") or {})   # {tid_hex: mode}
        MODE_TXT = {"auto": "Tự mua", "notify": "Thông báo", "": "Bỏ qua"}
        RANK = {"auto": 0, "notify": 1, "": 2}
        # state {tid_hex: mode}. cur co the co key hex ("0x..") HOAC int-string ("23456") tuy JSON.
        dflt_notify = self._load_furnace_default_notify().get(pool_name, {})

        def _cur_mode(tid_hex):
            # Config cua acc DE LEN mac dinh. Chua chon gi -> "Thong bao" neu item thuoc vo tuong
            # CO VU KHI CHUYEN DUNG (furnace_default_notify.json), con lai -> "Bo qua".
            m = cur.get(tid_hex) or cur.get(str(int(tid_hex, 16))) or cur.get(int(tid_hex, 16))
            if m == "skip":     # bo qua TUONG MINH (xem save()) -> UI hien "Bo qua"
                return ""
            if m:
                return m
            return "notify" if tid_hex in dflt_notify else ""
        state = {tid_hex: _cur_mode(tid_hex) for tid_hex in pool}
        _mode0 = dict(state)     # trang thai LUC MO -> biet muc nao vua thoat "Bo qua"

        win = tk.Toplevel(self); win.title(f"Lò {tab_label}: {row['u'].get().strip()}")
        win.transient(self.winfo_toplevel()); win.grab_set()
        win.geometry("640x560" if pool_name == "Trang Bi" else "460x520")
        top = ttk.Frame(win); top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="Tìm:").pack(side="left")
        q = tk.StringVar()
        ttk.Entry(top, textvariable=q).pack(side="left", fill="x", expand=True, padx=4)
        _tvf = ttk.Frame(win); _tvf.pack(fill="both", expand=True, padx=8)
        tv = ttk.Treeview(_tvf, columns=("mode",), show="tree headings", height=18)
        tv.heading("#0", text="Item"); tv.heading("mode", text="Chế độ")
        tv.column("#0", width=(510 if pool_name == "Trang Bi" else 330)); tv.column("mode", width=90, anchor="center")
        _vsb = ttk.Scrollbar(_tvf, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=_vsb.set)
        _vsb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)

        _is_equip = (pool_name == "Trang Bi")
        def refresh():
            kw = q.get().strip().lower()
            tv.delete(*tv.get_children())
            rows_ = []
            for tid_hex, nm in pool.items():
                disp = self._equip_display(tid_hex, nm or tid_hex) if _is_equip else (nm or tid_hex)
                if kw and kw not in disp.lower() and kw not in tid_hex:
                    continue
                rows_.append((tid_hex, disp))
            if _is_equip:
                # Trang Bi: nhom theo che do, trong moi nhom sort CHI SO (+bonus) giam dan.
                rows_.sort(key=lambda x: (RANK[state[x[0]]], -self._equip_maxbonus(x[0]), x[1]))
            else:
                rows_.sort(key=lambda x: (RANK[state[x[0]]], x[1]))   # Tu mua -> Bao -> Bo
            for tid_hex, disp in rows_:
                tv.insert("", "end", iid=tid_hex, text=disp, values=(MODE_TXT[state[tid_hex]],))
        q.trace_add("write", lambda *_a: refresh()); refresh()

        def set_mode(m):
            # Cap nhat che do TAI CHO (khong re-sort) -> item KHONG nhay cho khi dang chinh. Sort chi
            # chay khi mo/tim (refresh) -> lan mo sau da sap xep san ("luc luu moi can sort").
            for iid in tv.selection():
                state[iid] = m
                if tv.exists(iid):
                    tv.set(iid, "mode", MODE_TXT[m])
        bb = ttk.Frame(win); bb.pack(fill="x", padx=8, pady=6)
        ttk.Button(bb, text="Tự mua", command=lambda: set_mode("auto")).pack(side="left", padx=3)
        ttk.Button(bb, text="Thông báo", command=lambda: set_mode("notify")).pack(side="left", padx=3)
        ttk.Button(bb, text="Bỏ qua", command=lambda: set_mode("")).pack(side="left", padx=3)
        # Vong doi che do khi double-click: Thong bao -> Tu mua -> Bo qua -> Thong bao...
        # (truoc day: Tu mua -> Thong bao -> Bo qua)
        _NEXT_MODE = {"notify": "auto", "auto": "", "": "notify"}
        tv.bind("<Double-1>", lambda _e: set_mode(_NEXT_MODE[state.get(tv.focus(), "")]))

        def save():
            # Luu "skip" cho item MAC DINH thong bao ma user chon "Bo qua" - khong luu thi lan sau
            # lai ve mac dinh notify (khong tat duoc). Item khac van khong can luu khi bo qua.
            items = {}
            for t, m in state.items():
                if m in ("auto", "notify"):
                    items[t] = m
                elif not m and t in dflt_notify:
                    items[t] = "skip"
            # Item chuyen BO QUA -> Tu mua/Thong bao thi cuon so huu no phai ve "Giu lai",
            # khong thi vua mua vua phan giai. So voi trang thai LUC MO dialog (_mode0).
            _unskipped = [t for t, m in state.items() if m in ("auto", "notify") and not _mode0.get(t)]
            if items:
                on = (furn.get(tab_key) or {}).get("on", True)
                furn[tab_key] = {"on": on, "items": items}
            else:
                furn.pop(tab_key, None)
            _n = self._sync_scrolls_from_furnace(_unskipped) if tab_key in self._SCROLL_TAB else 0
            win.destroy()
            if _n:
                messagebox.showinfo("Đồng bộ phân giải",
                                    f"Đã chuyển {_n} cuộn sang \"Giữ lại\" "
                                    "(vì mục của chúng bên lò không còn Bỏ qua).",
                                    parent=self.winfo_toplevel())
        ttk.Button(bb, text="💾 Lưu", command=save).pack(side="right", padx=3)
        ttk.Button(bb, text="Hủy", command=win.destroy).pack(side="right", padx=3)

    def apply_heal_all(self, vals):
        """Ap nguong hoi mau `vals` cho moi acc (co username) trong party NAY. Tra so acc da ap."""
        n = 0
        for r in self.acc_rows:
            if not r["u"].get().strip():
                continue
            r["heal"] = dict(vals)
            n += 1
        return n

    def apply_furnace_all(self, furn_cfg):
        """Ap config SOI LO `furn_cfg` cho moi acc (co username) trong party NAY."""
        import copy as _copy
        n = 0
        for r in self.acc_rows:
            if not r["u"].get().strip():
                continue
            r["furnace"] = _copy.deepcopy(furn_cfg)
            n += 1
        return n

    def _open_skill_dialog(self, row):
        """Popup rule battle rieng tung acc: Dieu kien -> Skill/action -> Target."""
        uname = row["u"].get().strip()
        if not uname:
            messagebox.showinfo("Thiếu acc", "Nhập username trước đã."); return
        settings = row.setdefault("settings", {})
        battle = settings.get("battle") if isinstance(settings.get("battle"), dict) else {}

        c = ctrl.account_clients.get(uname)
        st = c.state if (c is not None and getattr(c, "state", None)) else None

        def _live_skill_ids(unit):
            if st is None:
                return []
            if unit == "char":
                return sorted(getattr(st, "skills_char", []) or [])
            skills = list(getattr(st, "pet_skills", []) or [])
            if not skills:
                skills = list(getattr(st, "skills_pet", []) or [])
            return sorted({int(s) for s in skills if isinstance(s, int) or str(s).isdigit()})

        live_skills = {
            "char": _live_skill_ids("char"),
            "pet": _live_skill_ids("pet"),
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
            rules.append({"enabled": True, "condition": "mineral", "op": "gte", "value": "",
                          "skill": "flee", "target": "self"})
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

        def _open_dangerous_npcs_editor():
            top = tk.Toplevel(win)
            top.title("NPC nguy hiểm")
            top.resizable(False, False)
            top.transient(win)
            top.grab_set()
            body = ttk.Frame(top, padding=10)
            body.pack(fill="both", expand=True)
            ttk.Label(body, text="Mỗi dòng là một tên NPC, thứ tự trên trước.").pack(anchor="w", pady=(0, 6))
            txt = tk.Text(body, width=36, height=12)
            txt.pack(fill="both", expand=True)
            txt.insert("1.0", "\n".join(getattr(config, "DANGEROUS_NPC_NAMES", []) or []))
            btns = ttk.Frame(body)
            btns.pack(fill="x", pady=(8, 0))

            def _save():
                names = [line.strip() for line in txt.get("1.0", "end").splitlines() if line.strip()]
                ok = False
                try:
                    ok = bool(ctrl.save_dangerous_npc_names(names))
                except Exception:
                    ok = False
                if not ok:
                    try:
                        config.save_dangerous_npc_names(names)
                    except Exception as e:
                        messagebox.showerror("NPC nguy hiểm", f"Không lưu được danh sách:\n{e}", parent=top)
                        return
                top.destroy()

            ttk.Button(btns, text="Lưu", command=_save).pack(side="left")
            ttk.Button(btns, text="Hủy", command=top.destroy).pack(side="left", padx=(8, 0))

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
                npc_btn = ttk.Button(fr, text="DS", width=3, command=_open_dangerous_npcs_editor)
                rec = {"frame": fr, "enabled": enabled_var, "condition": cond_var,
                       "op": op_var, "value": value_var, "skill": skill_var, "target": target_var}

                def _sync_target_button(*_a):
                    target_key = LABEL_BATTLE_TARGETS.get(target_var.get(), "auto")
                    if target_key == "dangerous_npc":
                        if not npc_btn.winfo_ismapped():
                            npc_btn.pack(side="left", padx=(0, 4), before=up_btn)
                    else:
                        npc_btn.pack_forget()

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
                        npc_btn.pack_forget()
                    else:
                        skill_cb.configure(values=_skill_values(unit, [_label_to_skill(skill_var.get())]),
                                           state="readonly")
                        target_cb.configure(state="readonly")
                        _sync_target_button()

                up_btn = ttk.Button(fr, text="↑", width=2,
                                    command=lambda r=rec: _move_rule(unit, r, -1))
                up_btn.pack(side="left", padx=(0, 2))
                down_btn = ttk.Button(fr, text="↓", width=2,
                                      command=lambda r=rec: _move_rule(unit, r, 1))
                down_btn.pack(side="left", padx=(0, 2))
                del_btn = ttk.Button(fr, text="X", width=2,
                                     command=lambda r=rec: _remove_rule(unit, r))
                del_btn.pack(side="left")
                cond_var.trace_add("write", _sync_condition)
                target_var.trace_add("write", _sync_target_button)
                _sync_condition()
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

    _pet_scrolls_cache = None

    @classmethod
    def _load_pet_scrolls(cls):
        """{tid_hex: {name,npc,vkcd}} tu pet_scrolls.json - TAT CA cuon goi vo tuong trong game."""
        if PartyConfigFrame._pet_scrolls_cache is None:
            import json as _json, os as _os
            PartyConfigFrame._pet_scrolls_cache = {}
            for p in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "pet_scrolls.json"),
                      "pet_scrolls.json"):
                try:
                    with open(p, encoding="utf-8") as fh:
                        PartyConfigFrame._pet_scrolls_cache = _json.load(fh); break
                except Exception:
                    pass
        return PartyConfigFrame._pet_scrolls_cache

    _donate_materials_cache = None
    _MAT_KIND = {24: "Sành", 25: "Gỗ", 26: "Vỏ", 27: "Xương", 28: "Ngọc Sa", 29: "Đá quý",
                 30: "Da", 31: "Vải", 32: "Giấy", 33: "Trúc", 34: "Thảo mộc", 35: "Hạt Đá",
                 36: "Băng", 40: "Kim Sa", 41: "Ngân Phấn", 42: "Bột Đồng", 43: "Thiết",
                 44: "Thiếc", 45: "Tử Tinh", 46: "Hồng Tinh"}

    @classmethod
    def _load_donate_materials(cls):
        """{tid_hex: {name,kind,lv}} tu donate_materials.json - TAT CA nguyen lieu donate duoc."""
        if PartyConfigFrame._donate_materials_cache is None:
            import json as _json, os as _os
            PartyConfigFrame._donate_materials_cache = {}
            for p in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "donate_materials.json"),
                      "donate_materials.json"):
                try:
                    with open(p, encoding="utf-8") as fh:
                        PartyConfigFrame._donate_materials_cache = _json.load(fh).get("items", {}); break
                except Exception:
                    pass
        return PartyConfigFrame._donate_materials_cache

    def _open_bag_clean_detail(self):
        """Bang chi tiet cua "Tu don tui do": 3 muc con. Bo tick o tong -> ca 3 ngung."""
        win = tk.Toplevel(self); win.title("Dọn dẹp túi đồ"); win.transient(self); win.grab_set()
        win.resizable(False, False)
        frm = ttk.Frame(win, padding=12); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text='Các việc bot làm khi bật "Tự dọn túi đồ":').pack(anchor="w")
        ttk.Checkbutton(frm, text="Tự bán Nồi đất (ở Nhà buôn Ng.Thành)",
                        variable=self.auto_sell_noi_dat_var).pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(frm, text="Tự vứt item rác (Ngọc Hư)",
                        variable=self.auto_discard_junk_var).pack(anchor="w", pady=(4, 0))
        _mt = ttk.Frame(frm); _mt.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Checkbutton(_mt, text="Tự đóng góp nguyên liệu cho quân đoàn",
                        variable=self.auto_donate_materials_var).pack(side="left")
        ttk.Button(_mt, text="List", command=self._open_material_list).pack(side="left", padx=(8, 0))
        _sc = ttk.Frame(frm); _sc.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Checkbutton(_sc, text="Tự phân giải cuộn võ tướng rác",
                        variable=self.auto_decompose_scrolls_var).pack(side="left")
        ttk.Button(_sc, text="List", command=self._open_scroll_list).pack(side="left", padx=(8, 0))
        ttk.Label(frm, foreground="#a00", wraplength=420, justify="left",
                  text="Lưu ý: phân giải là MẤT HẲN cuộn. Mặc định cuộn của tướng có vũ khí "
                       "chuyên dụng được giữ lại, còn lại phân giải — nên soát List trước khi bật."
                  ).pack(anchor="w", pady=(8, 0))
        ttk.Button(frm, text="Đóng", command=win.destroy).pack(anchor="e", pady=(12, 0))

    def _open_scroll_list(self):
        """List TAT CA cuon goi vo tuong: double-click doi GIU LAI <-> PHAN GIAI.

        self.scroll_modes CHI luu muc DOI KHAC mac dinh (mac dinh: co vkcd = giu lai) -> cuon moi
        cua game tu theo mac dinh, va bang mac dinh sua lai sau nay van co hieu luc.
        """
        data = self._load_pet_scrolls()
        if not data:
            messagebox.showwarning("List cuộn", "Không đọc được pet_scrolls.json")
            return
        win = tk.Toplevel(self); win.title("Cuộn võ tướng"); win.transient(self); win.grab_set()
        frm = ttk.Frame(win, padding=10); frm.pack(fill="both", expand=True)
        top = ttk.Frame(frm); top.pack(fill="x")
        ttk.Label(top, text="Double-click để đổi trạng thái. Tìm:").pack(side="left")
        q_var = tk.StringVar()
        ttk.Entry(top, textvariable=q_var, width=24).pack(side="left", padx=(4, 0))
        # Thanh nut phai pack TRUOC widget expand, khong thi bi bop mat khi cua so nho lai
        bar = ttk.Frame(frm); bar.pack(side="bottom", fill="x", pady=(10, 0))
        mid = ttk.Frame(frm); mid.pack(fill="both", expand=True)
        tv = ttk.Treeview(mid, columns=("st",), show="tree headings", height=20)
        tv.heading("#0", text="Cuộn"); tv.heading("st", text="Trạng thái")
        tv.column("#0", width=320); tv.column("st", width=110, anchor="center")
        sb = ttk.Scrollbar(mid, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True, pady=(8, 0))
        sb.pack(side="right", fill="y", pady=(8, 0))
        # state: tid_hex -> "keep"/"drop" (day du MOI cuon, luc Luu moi loc ra phan khac mac dinh)
        state = {tid: self.scroll_modes.get(tid, "keep" if v.get("vkcd") else "drop")
                 for tid, v in data.items()}

        def _label(tid):
            """ten cuon — ten tuong · Lv### · hang hiem (+ ★ neu mac dinh giu).

            Hien Lv/hang de user tu quyet: KHONG co truong nao trong data phan loai duoc
            xin/rac (da doi chieu - 'rare' lan 'level' deu khong tach sach), nen bang phai
            dua du thong tin thay vi bat user tin mac dinh.
            """
            v = data[tid]
            nm = v.get("name", "")
            extra = [x for x in (v.get("npc") if v.get("npc") not in nm else "",
                                 "Lv%s" % v["lv"] if v.get("lv") else "",
                                 v.get("rare", "")) if x]
            if extra:
                nm = "%s — %s" % (nm, " · ".join(extra))
            return nm + (" ★" if v.get("vkcd") else "")

        def _fill():
            q = q_var.get().strip().lower()
            tv.delete(*tv.get_children())
            # "Phan giai" len TRUOC de user soat cai se bi mat truoc tien
            for tid in sorted(data, key=lambda t: (state[t] != "drop",
                                                  -int(data[t].get("lv") or 0), _label(t))):
                if q and q not in _label(tid).lower():
                    continue
                tv.insert("", "end", iid=tid, text=_label(tid),
                          values=("Phân giải" if state[tid] == "drop" else "Giữ lại",))

        def _toggle(_e=None):
            tid = tv.focus()
            if not tid:
                return
            state[tid] = "keep" if state[tid] == "drop" else "drop"
            tv.item(tid, values=("Phân giải" if state[tid] == "drop" else "Giữ lại",))

        def _save():
            _was_drop = {t for t in data
                         if (self.scroll_modes.get(t) or ("keep" if data[t].get("vkcd") else "drop"))
                         == "drop"}
            self.scroll_modes = {
                tid: m for tid, m in state.items()
                if m != ("keep" if data[tid].get("vkcd") else "drop")}
            # Chi cac cuon VUA chuyen sang phan giai moi phai tat ben lo (chieu nguoc lai khong
            # can lam gi). Quet MOI account trong party vi config lo la cua tung account.
            _now_drop = {t for t, m in state.items() if m == "drop"}
            _n = self._sync_furnace_from_scrolls(_now_drop - _was_drop)
            win.destroy()
            if _n:
                messagebox.showinfo("Đồng bộ soi lò",
                                    f"Đã chuyển {_n} mục bên lò sang \"Bỏ qua\" "
                                    "(Bí Cấp / K.Toả / T.Tinh / Mê của cuộn vừa đặt Phân giải).",
                                    parent=self.winfo_toplevel())

        tv.bind("<Double-1>", _toggle)
        q_var.trace_add("write", lambda *_a: _fill())
        _fill()
        ttk.Label(bar, text="★ = mặc định giữ (tướng có vũ khí chuyên dụng / bản đặc biệt)").pack(side="left")
        ttk.Button(bar, text="Hủy", command=win.destroy).pack(side="right")
        ttk.Button(bar, text="Lưu", command=_save).pack(side="right", padx=(0, 8))

    def _open_material_list(self):
        """List TAT CA nguyen lieu donate duoc: double-click doi DONATE <-> GIU LAI.
        MAC DINH donate HET -> self.material_modes CHI luu muc user danh dau GIU (mac dinh khong luu)."""
        data = self._load_donate_materials()
        if not data:
            messagebox.showwarning("List nguyên liệu", "Không đọc được donate_materials.json")
            return
        win = tk.Toplevel(self); win.title("Nguyên liệu (đóng góp quân đoàn)")
        win.transient(self); win.grab_set()
        frm = ttk.Frame(win, padding=10); frm.pack(fill="both", expand=True)
        top = ttk.Frame(frm); top.pack(fill="x")
        ttk.Label(top, text="Double-click để đổi trạng thái. Tìm:").pack(side="left")
        q_var = tk.StringVar()
        ttk.Entry(top, textvariable=q_var, width=24).pack(side="left", padx=(4, 0))
        bar = ttk.Frame(frm); bar.pack(side="bottom", fill="x", pady=(10, 0))
        mid = ttk.Frame(frm); mid.pack(fill="both", expand=True)
        tv = ttk.Treeview(mid, columns=("st",), show="tree headings", height=20)
        tv.heading("#0", text="Nguyên liệu"); tv.heading("st", text="Trạng thái")
        tv.column("#0", width=340); tv.column("st", width=110, anchor="center")
        sb = ttk.Scrollbar(mid, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True, pady=(8, 0))
        sb.pack(side="right", fill="y", pady=(8, 0))
        # state: tid_hex -> "keep"/"donate"; MAC DINH donate (chi keep neu material_modes danh dau)
        state = {tid: ("keep" if self.material_modes.get(tid) == "keep" else "donate")
                 for tid in data}

        def _label(tid):
            v = data[tid]
            cat = self._MAT_KIND.get(v.get("kind"), "")
            extra = [x for x in (cat, "Lv%s" % v["lv"] if v.get("lv") else "") if x]
            nm = v.get("name", "")
            return "%s — %s" % (nm, " · ".join(extra)) if extra else nm

        def _fill():
            q = q_var.get().strip().lower()
            tv.delete(*tv.get_children())
            # "Donate" (se MAT) len TRUOC, roi theo Lv giam dan de soat mon quy tier cao
            for tid in sorted(data, key=lambda t: (state[t] != "donate",
                                                   -int(data[t].get("lv") or 0), _label(t))):
                if q and q not in _label(tid).lower():
                    continue
                tv.insert("", "end", iid=tid, text=_label(tid),
                          values=("Đóng góp" if state[tid] == "donate" else "Giữ lại",))

        def _toggle(_e=None):
            tid = tv.focus()
            if not tid:
                return
            state[tid] = "keep" if state[tid] == "donate" else "donate"
            tv.item(tid, values=("Đóng góp" if state[tid] == "donate" else "Giữ lại",))

        def _save():
            # CHI luu muc GIU (khac mac dinh donate) -> nguyen lieu moi cua game tu donate theo mac dinh
            self.material_modes = {tid: "keep" for tid, m in state.items() if m == "keep"}
            win.destroy()

        tv.bind("<Double-1>", _toggle)
        q_var.trace_add("write", lambda *_a: _fill())
        _fill()
        ttk.Label(bar, text="Mặc định ĐÓNG GÓP hết — đánh dấu Giữ lại nguyên liệu quý").pack(side="left")
        ttk.Button(bar, text="Hủy", command=win.destroy).pack(side="right")
        ttk.Button(bar, text="Lưu", command=_save).pack(side="right", padx=(0, 8))

    def _open_team_dungeon_list(self):
        win = tk.Toplevel(self)
        win.title("List phó bản")
        win.transient(self)
        win.grab_set()
        win.resizable(False, False)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Chọn phó bản tổ đội bot sẽ tự đi:").pack(anchor="w")
        vars_by_level = {}
        for lv in TEAM_DUNGEON_LEVELS:
            v = tk.BooleanVar(value=bool(self.team_dungeons.get(lv, False)))
            vars_by_level[lv] = v
            ttk.Checkbutton(frm, text=f"Phó bản {lv}", variable=v).pack(anchor="w", pady=(6, 0))

        def _save():
            self.team_dungeons = {lv: bool(vars_by_level[lv].get()) for lv in TEAM_DUNGEON_LEVELS}
            win.destroy()

        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(12, 0))
        ttk.Button(bar, text="Lưu", command=_save).pack(side="left")
        ttk.Button(bar, text="Hủy", command=win.destroy).pack(side="left", padx=(8, 0))

    def _open_shop_list(self):
        win = tk.Toplevel(self); win.title("List shop"); win.transient(self); win.grab_set()
        win.resizable(False, False)
        frm = ttk.Frame(win, padding=12); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Chọn vật phẩm shop bot sẽ tự mua:").pack(anchor="w", pady=(0, 6))
        vars_by_key = {
            "ho_phu": tk.BooleanVar(value=bool(self.buy_ho_phu_var.get())),
            "thien_chau": tk.BooleanVar(value=bool(self.buy_thien_chau_var.get())),
            "bao_hop": tk.BooleanVar(value=bool(self.buy_bao_hop_var.get())),
        }
        bao_hop_xu_var = tk.StringVar(value=str(_parse_int(self.bao_hop_xu_var.get(), 10000000)))
        ttk.Checkbutton(frm, text="Dị Giới hộ phù", variable=vars_by_key["ho_phu"]).pack(anchor="w")
        ttk.Checkbutton(frm, text="Hộp Thiên Châu", variable=vars_by_key["thien_chau"]).pack(anchor="w", pady=(4, 0))
        _bh = ttk.Frame(frm); _bh.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Checkbutton(_bh, text="Triệu gọi bảo hộp khi xu >",
                        variable=vars_by_key["bao_hop"]).pack(side="left")
        ttk.Entry(_bh, textvariable=bao_hop_xu_var, width=10).pack(side="left", padx=(4, 0))

        def _save():
            self.buy_ho_phu_var.set(bool(vars_by_key["ho_phu"].get()))
            self.buy_thien_chau_var.set(bool(vars_by_key["thien_chau"].get()))
            self.buy_bao_hop_var.set(bool(vars_by_key["bao_hop"].get()))
            self.bao_hop_xu_var.set(str(_parse_int(bao_hop_xu_var.get(), 10000000)))
            win.destroy()

        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(12, 0))
        ttk.Button(bar, text="Lưu", command=_save).pack(side="left")
        ttk.Button(bar, text="Hủy", command=win.destroy).pack(side="left", padx=(8, 0))

    def _open_advanced_settings(self):
        """Dialog gom cac setting IT KHI DOI cua party (hien tai: daily quest) - tach khoi bang
        chinh de tranh bi day dai/roi khi sau nay them setting moi (xem ghi chu o self.daily_var)."""
        win = tk.Toplevel(self); win.title("Cài đặt nâng cao"); win.transient(self); win.grab_set()
        win.resizable(False, False)
        frm = ttk.Frame(win, padding=12); frm.pack(fill="both", expand=True)
        ttk.Checkbutton(frm, text="Làm nhiệm vụ hàng ngày (bingo 9 ô: phó bản đơn, boss thế giới, "
                        "gacha, hợp đồ... + nhận thưởng)",
                        variable=self.daily_var).pack(anchor="w")
        ttk.Checkbutton(frm, text="Nhận exp offline",
                        variable=self.claim_offline_exp_var).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(frm, text="Đánh hết lượt World Boss",
                        variable=self.auto_world_boss_var).pack(anchor="w", pady=(4, 0))
        _td = ttk.Frame(frm); _td.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Checkbutton(_td, text="Tự đi phó bản",
                        variable=self.auto_team_dungeon_var).pack(side="left")
        ttk.Button(_td, text="List phó bản",
                   command=self._open_team_dungeon_list).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(frm, text="Sử dụng Phúc Thần",
                        variable=self.use_phuc_than_var).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(frm, text="Dùng Dị giới hộ phù",
                        variable=self.use_digioi_ho_phu_var).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(frm, text="Đánh boss QD",
                        variable=self.fight_boss_var).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(frm, text="Vận tiêu (nhận quà + gửi pet)",
                        variable=self.van_tieu_var).pack(anchor="w", pady=(4, 0))
        _bag = ttk.Frame(frm); _bag.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Checkbutton(_bag, text="Tự dọn túi đồ",
                        variable=self.auto_bag_clean_var).pack(side="left")
        ttk.Button(_bag, text="Chi tiết",
                   command=self._open_bag_clean_detail).pack(side="left", padx=(8, 0))
        _shop = ttk.Frame(frm); _shop.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Checkbutton(_shop, text="Tự mua shop",
                        variable=self.auto_buy_shop_var).pack(side="left")
        ttk.Button(_shop, text="List shop",
                   command=self._open_shop_list).pack(side="left", padx=(8, 0))
        # Tu mua HP/SP o Trac Quan (Loi Dai Huong Dung) khi du tru trong tui thap hon nguong.
        _hp = ttk.Frame(frm); _hp.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Checkbutton(_hp, text="Tự mua HP (Viên Hành Khí +62), số lượng",
                        variable=self.buy_hp_var).pack(side="left")
        ttk.Entry(_hp, textvariable=self.hp_qty_var, width=7).pack(side="left", padx=(4, 0))
        ttk.Label(_hp, text="khi tổng HP có thể hồi từ item trong túi <").pack(side="left", padx=(6, 0))
        ttk.Entry(_hp, textvariable=self.hp_thresh_var, width=9).pack(side="left", padx=(4, 0))
        _sp = ttk.Frame(frm); _sp.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Checkbutton(_sp, text="Tự mua SP (Thiên Kim Du +62), số lượng",
                        variable=self.buy_sp_var).pack(side="left")
        ttk.Entry(_sp, textvariable=self.sp_qty_var, width=7).pack(side="left", padx=(4, 0))
        ttk.Label(_sp, text="khi tổng SP có thể hồi từ item trong túi <").pack(side="left", padx=(6, 0))
        ttk.Entry(_sp, textvariable=self.sp_thresh_var, width=9).pack(side="left", padx=(4, 0))
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
            "claim_offline_exp": bool(self.claim_offline_exp_var.get()),
            "auto_world_boss": bool(self.auto_world_boss_var.get()),
            "auto_team_dungeon": bool(self.auto_team_dungeon_var.get()),
            "team_dungeons": _team_dungeons_json(self.team_dungeons),
            "use_phuc_than": bool(self.use_phuc_than_var.get()),
            "use_digioi_ho_phu": bool(self.use_digioi_ho_phu_var.get()),
            "fight_legion_boss": bool(self.fight_boss_var.get()),
            "do_van_tieu": bool(self.van_tieu_var.get()),
            "auto_sell_noi_dat": bool(self.auto_sell_noi_dat_var.get()),
            "auto_bag_clean": bool(self.auto_bag_clean_var.get()),
            "auto_discard_junk": bool(self.auto_discard_junk_var.get()),
            "auto_decompose_scrolls": bool(self.auto_decompose_scrolls_var.get()),
            "scroll_modes": dict(self.scroll_modes),
            "auto_donate_materials": bool(self.auto_donate_materials_var.get()),
            "material_modes": dict(self.material_modes),
            "auto_buy_shop": bool(self.auto_buy_shop_var.get()),
            "shop_items": _shop_items_json({
                "ho_phu": self.buy_ho_phu_var.get(),
                "thien_chau": self.buy_thien_chau_var.get(),
                "bao_hop": self.buy_bao_hop_var.get(),
            }),
            "buy_ho_phu": bool(self.buy_ho_phu_var.get()),
            "buy_thien_chau": bool(self.buy_thien_chau_var.get()),
            "buy_bao_hop": bool(self.buy_bao_hop_var.get()),
            "bao_hop_xu_threshold": _parse_int(self.bao_hop_xu_var.get(), 10000000),
            "buy_hp": bool(self.buy_hp_var.get()),
            "hp_qty": _parse_int(self.hp_qty_var.get(), 9999),
            "hp_thresh": _parse_int(self.hp_thresh_var.get(), 500000),
            "buy_sp": bool(self.buy_sp_var.get()),
            "sp_qty": _parse_int(self.sp_qty_var.get(), 9999),
            "sp_thresh": _parse_int(self.sp_thresh_var.get(), 500000),
            # KHONG co di_gioi_level o day: cap quai DG la setting RIENG tung party (o section
            # mode Di Gioi), khong duoc "ap dung cho party khac" de len cap cua party do.
        }

    def apply_advanced_settings(self, data):
        self.daily_var.set(bool(data.get("do_daily", True)))
        self.claim_offline_exp_var.set(bool(data.get("claim_offline_exp", True)))
        self.auto_world_boss_var.set(bool(data.get("auto_world_boss", True)))
        self.auto_team_dungeon_var.set(bool(data.get("auto_team_dungeon", True)))
        self.team_dungeons = _normalize_team_dungeons(data.get("team_dungeons"))
        self.use_phuc_than_var.set(bool(data.get("use_phuc_than", False)))
        self.use_digioi_ho_phu_var.set(bool(data.get("use_digioi_ho_phu", False)))
        self.fight_boss_var.set(bool(data.get("fight_legion_boss", True)))
        self.van_tieu_var.set(bool(data.get("do_van_tieu", True)))
        self.auto_sell_noi_dat_var.set(bool(data.get("auto_sell_noi_dat", True)))
        self.auto_bag_clean_var.set(bool(data.get("auto_bag_clean", True)))
        self.auto_discard_junk_var.set(bool(data.get("auto_discard_junk", True)))
        self.auto_decompose_scrolls_var.set(bool(data.get("auto_decompose_scrolls", False)))
        self.scroll_modes = dict(data.get("scroll_modes") or {})
        shop_items = _normalize_shop_items(data.get("shop_items"), {
            "ho_phu": data.get("buy_ho_phu", False),
            "thien_chau": data.get("buy_thien_chau", False),
            "bao_hop": data.get("buy_bao_hop", False),
        })
        self.auto_buy_shop_var.set(bool(data.get("auto_buy_shop", any(shop_items.values()))))
        self.buy_ho_phu_var.set(bool(shop_items.get("ho_phu", False)))
        self.buy_thien_chau_var.set(bool(shop_items.get("thien_chau", False)))
        self.buy_bao_hop_var.set(bool(shop_items.get("bao_hop", False)))
        self.bao_hop_xu_var.set(str(_parse_int(data.get("bao_hop_xu_threshold", 10000000), 10000000)))
        self.buy_hp_var.set(bool(data.get("buy_hp", False)))
        self.hp_qty_var.set(str(_parse_int(data.get("hp_qty", 9999), 9999)))
        self.hp_thresh_var.set(str(_parse_int(data.get("hp_thresh", 500000), 500000)))
        self.buy_sp_var.set(bool(data.get("buy_sp", False)))
        self.sp_qty_var.set(str(_parse_int(data.get("sp_qty", 9999), 9999)))
        self.sp_thresh_var.set(str(_parse_int(data.get("sp_thresh", 500000), 500000)))
        # KHONG dung di_gioi_level (setting rieng tung party, xem _advanced_settings_data)

    def _on_mode_change(self):
        # Khi DOI che do: tu set mac dinh "Khong co chu PT".
        #  - city / stand / event: TICK (moi nick tu dung/tele rieng, khong can chu PT).
        #  - train / digioi: BO TICK (can chu PT de keo party + lap tran).
        mode = _LABEL_MODE.get(self.mode_var.get(), "digioi")
        self.no_leader_var.set(mode in ("city", "stand"))
        self._render_dyn()

    def _update_no_leader_visibility(self):
        """Whitelist co 2 nghia: tick = accept leader ngoai; khong tick = moi them acc ngoai.
        Di Gioi SOLO: khong lap party that -> an ca checkbox lan whitelist cho gon."""
        mode = _LABEL_MODE.get(self.mode_var.get(), "digioi")
        hide = (mode == "digioi" and self.digioi_solo_var.get())
        if hide:
            self.no_leader_cb.pack_forget()
            self.wl_lbl.pack_forget()
            self.wl_entry.pack_forget()
        else:
            self.no_leader_cb.pack(side="left")
            if self.no_leader_var.get():
                self.wl_lbl.configure(text="")
                self.wl_lbl.pack(side="left")
            else:
                self.wl_lbl.configure(text="Mời thêm:")
                self.wl_lbl.pack(side="left", padx=(8, 0))
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
        # "Cap quai DG" ngang hang Che do - CHI o mode DG+Train (hang dyn con phai chua Map/Quai).
        # Mode "digioi" thuan van de cap quai o hang dyn nhu cu.
        if mode == "digioi_train":
            self.dg_lvl_lbl.pack(side="left")
            self.dg_lvl_cb.pack(side="left")
            if getattr(self, "on_apply_di_gioi_level", None):
                self.dg_apply_btn.pack(side="left", padx=(6, 0))
        else:
            self.dg_lvl_lbl.pack_forget()
            self.dg_lvl_cb.pack_forget()
            self.dg_apply_btn.pack_forget()
        self._update_no_leader_visibility()
        if mode in ("train", "digioi_train"):
            # (Cap quai DG da nam NGANG HANG voi Che do o tren - khong lap lai o day.)
            ttk.Label(self.dyn, text="Map:", width=10).pack(side="left")
            names = [n for (_i, n, _m, _g) in self.train_maps]
            # Combobox GO DUOC de tim nhanh (list map dai): go ID hoac TEN -> loc values + mo dropdown.
            self.map_cb = ttk.Combobox(self.dyn, textvariable=self.map_var, state="normal",
                                       width=32, values=names)
            self.map_cb.pack(side="left")
            self.map_cb.bind("<<ComboboxSelected>>", lambda e: self._fill_mobs())
            # Autocomplete: go ten HOAC id -> popup loc bung ngay duoi, van go tiep duoc; ↓ so dropdown.
            ComboSearch(self.map_cb, self.train_maps,
                        key_fn=lambda r: f"{r[1]} {r[0]} {r[3]}",   # match ten + id + nhom
                        label_fn=lambda r: r[1],                    # hien thi = ten map
                        group_fn=lambda r: r[3],                    # gom theo nhom trong popup
                        on_pick=self._fill_mobs)
            ttk.Label(self.dyn, text="Quái:", width=6).pack(side="left", padx=(10, 0))
            self.mob_cb = ttk.Combobox(self.dyn, textvariable=self.mob_var, state="readonly", width=22)
            self.mob_cb.pack(side="left")
            ttk.Button(self.dyn, text="✎ Sửa map", command=self._edit_maps).pack(side="left", padx=(8, 0))
            idx = next((i for i, (mid, _n, _m, _g) in enumerate(self.train_maps)
                        if mid == self._preset.get("start_city_id")), 0)
            if names:
                self.map_var.set(names[idx])
            # Chi dung mob_index DA LUU neu preset von la 'train'/'digioi_train'. Doi tu mode khac
            # sang -> mac dinh "Bot tu chon" (-1), KHONG lay mob_index=0 (rac) cua mode khac.
            pmob = (self._preset.get("mob_index", -1)
                    if self._preset.get("mode") in ("train", "digioi_train") else -1)
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
        mobs = next((m for (_i, n, m, _g) in self.train_maps if n == sel), [])
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
        # Mo editor chon SAN map dang train (theo dropdown Map) cho tien sua ngay.
        cur_id = next((mid for (mid, n, _m, _g) in self.train_maps
                       if n == self.map_var.get()), None)
        TrainMapEditor(self, on_save=self._reload_maps, select_map=cur_id)

    def _reload_maps(self):
        # nap lai train_maps.json -> cap nhat list (chia se) + ve lai dropdown
        tm_raw = _load_json("train_maps.json").get("maps", {})
        self.train_maps[:] = [(int(k), v.get("name", k), v.get("mobs", []), (v.get("group") or _DEFAULT_GROUP)) for k, v in tm_raw.items()]
        self._render_dyn()

    def get_data(self):
        mode = _LABEL_MODE.get(self.mode_var.get(), "digioi")
        sc, mob_index, city_flag = 0, 0, 0
        event_key = ""
        if mode == "digioi":
            sc = 49942
        elif mode in ("train", "digioi_train"):
            # digioi_train: start_city_id = MAP TRAIN (pha 2). Pha 1 (DG) dung DIGIOI_MAP_ID co dinh
            # trong runner, khong luu o day.
            sc = next((mid for (mid, n, _m, _g) in self.train_maps if n == self.map_var.get()), 0)
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
            if r.get("furnace"):
                acc["furnace"] = r["furnace"]
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
                "claim_offline_exp": bool(self.claim_offline_exp_var.get()),
                "auto_world_boss": bool(self.auto_world_boss_var.get()),
                "auto_team_dungeon": bool(self.auto_team_dungeon_var.get()),
                "team_dungeons": _team_dungeons_json(self.team_dungeons),
                "use_phuc_than": bool(self.use_phuc_than_var.get()),
                "use_digioi_ho_phu": bool(self.use_digioi_ho_phu_var.get()),
                "fight_legion_boss": bool(self.fight_boss_var.get()),
                "do_van_tieu": bool(self.van_tieu_var.get()),
                "auto_sell_noi_dat": bool(self.auto_sell_noi_dat_var.get()),
                "auto_bag_clean": bool(self.auto_bag_clean_var.get()),
                "auto_discard_junk": bool(self.auto_discard_junk_var.get()),
                "auto_decompose_scrolls": bool(self.auto_decompose_scrolls_var.get()),
                "scroll_modes": dict(self.scroll_modes),
                "auto_donate_materials": bool(self.auto_donate_materials_var.get()),
                "material_modes": dict(self.material_modes),
                "auto_buy_shop": bool(self.auto_buy_shop_var.get()),
                "shop_items": _shop_items_json({
                    "ho_phu": self.buy_ho_phu_var.get(),
                    "thien_chau": self.buy_thien_chau_var.get(),
                    "bao_hop": self.buy_bao_hop_var.get(),
                }),
                "buy_ho_phu": bool(self.buy_ho_phu_var.get()),
                "buy_thien_chau": bool(self.buy_thien_chau_var.get()),
                "buy_bao_hop": bool(self.buy_bao_hop_var.get()),
                "bao_hop_xu_threshold": _parse_int(self.bao_hop_xu_var.get(), 10000000),
                "buy_hp": bool(self.buy_hp_var.get()),
                "hp_qty": _parse_int(self.hp_qty_var.get(), 9999),
                "hp_thresh": _parse_int(self.hp_thresh_var.get(), 500000),
                "buy_sp": bool(self.buy_sp_var.get()),
                "sp_qty": _parse_int(self.sp_qty_var.get(), 9999),
                "sp_thresh": _parse_int(self.sp_thresh_var.get(), 500000),
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

    def __init__(self, master, on_save=None, select_map=None):
        super().__init__(master)
        self.title("Sửa map train (train_maps.json)")
        self.geometry("760x540")
        self.transient(master); self.grab_set()
        self.on_save = on_save
        raw = _load_json("train_maps.json").get("maps", {})
        # list dict: {id, name, group, safe:[[x,y]], mobs:[[x,y]]}. 'group' = nhom (cay 1 tang).
        self.maps = [{"id": k, "name": v.get("name", k),
                      "group": (v.get("group") or _DEFAULT_GROUP),
                      "safe": _safe_points(v.get("safe", [])),
                      "mobs": [list(p) for p in v.get("mobs", [])]} for k, v in raw.items()]
        # Map nao luc MO editor da RONG (chua co bai). Khi luu: neu 1 map van rong (user khong tu
        # nhap) NHUNG file tren dia da co bai (bot AUTO-LEARN trong luc editor dang mo) -> GIU data
        # dia, khong de snapshot cu de len (bug: auto-learn 21833 xong, bam Luu -> mat data).
        self._orig_empty = {k for k, v in raw.items()
                            if not v.get("mobs") and not v.get("safe")}
        self._cur = None

        # Pack BAR (Luu/Huy) o DAY truoc -> giu cho duoi cung (left/right pack sau khong de len)
        bar = ttk.Frame(self, padding=6); bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="💾 Lưu", command=self._save).pack(side="right")
        ttk.Button(bar, text="Hủy", command=self.destroy).pack(side="right", padx=4)

        left = ttk.Frame(self, padding=6); left.pack(side="left", fill="y")
        ttk.Label(left, text="Danh sách map (theo nhóm):").pack(anchor="w")
        # O TIM KIEM (theo ID hoac TEN) - loc nhanh khi list dai.
        frow = ttk.Frame(left); frow.pack(fill="x", pady=(0, 2))
        ttk.Label(frow, text="🔍").pack(side="left")
        self.filter_var = tk.StringVar()
        fent = ttk.Entry(frow, textvariable=self.filter_var)
        fent.pack(side="left", fill="x", expand=True)
        self.filter_var.trace_add("write", lambda *_: self._reload_list())
        ttk.Button(frow, text="✕", width=2,
                   command=lambda: self.filter_var.set("")).pack(side="left")
        # CAY 1 TANG: nhom (parent, gap/mo) -> map (child). Child iid = str(index trong self.maps),
        # group iid = 'g::'+ten nhom. Chuot phai vao map -> "Chuyen sang nhom".
        self._open_group = None      # accordion: CHI 1 nhom mo cung luc
        self._sel_guard = False      # tranh de quy khi enforce selection
        # NUT pack side=bottom TRUOC -> luon giu cho o duoi (khong bi tree expand day khuat).
        b2 = ttk.Frame(left); b2.pack(side="bottom", fill="x", pady=(2, 0))
        ttk.Button(b2, text="▲ Lên", command=lambda: self._move(-1)).pack(side="left")
        ttk.Button(b2, text="▼ Xuống", command=lambda: self._move(1)).pack(side="left", padx=4)
        b = ttk.Frame(left); b.pack(side="bottom", fill="x", pady=4)
        ttk.Button(b, text="+ Thêm", command=self._add).pack(side="left")
        ttk.Button(b, text="🗑 Xóa", command=self._del).pack(side="left", padx=4)
        ttk.Button(b, text="⇄ Nhóm…", command=self._popup_group_menu).pack(side="left", padx=4)
        # CAY 1 TANG: nhom (parent, gap/mo) -> map (child). Child iid = str(index trong self.maps).
        self.tree = ttk.Treeview(left, show="tree", selectmode="extended", height=18)
        self.tree.pack(side="top", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        self.tree.bind("<<TreeviewOpen>>", self._on_open)
        self.tree.bind("<Button-3>", self._popup_group_menu)

        right = ttk.Frame(self, padding=6); right.pack(side="left", fill="both", expand=True)
        mapid_row = ttk.Frame(right); mapid_row.pack(anchor="w", fill="x")
        ttk.Label(mapid_row, text="Map ID (log 'MAP HIEN TAI'):").pack(side="left")
        self.id_var = tk.StringVar()
        ttk.Entry(mapid_row, textvariable=self.id_var, width=16).pack(side="left", padx=(8, 8))
        ttk.Button(mapid_row, text="Thống kê block",
                   command=self._show_block_stats).pack(side="left")
        ttk.Label(right, text="Tên:").pack(anchor="w", pady=(6, 0))
        self.name_var = tk.StringVar(); ttk.Entry(right, textvariable=self.name_var, width=34).pack(anchor="w")
        grow = ttk.Frame(right); grow.pack(anchor="w", fill="x", pady=(6, 0))
        ttk.Label(grow, text="Nhóm:").pack(side="left")
        self.group_lbl = ttk.Label(grow, text="—", foreground="#0a6")
        self.group_lbl.pack(side="left", padx=(6, 8))
        ttk.Label(grow, text="(chuột phải map ở danh sách để chuyển nhóm)",
                  foreground="#888").pack(side="left")
        ttk.Label(right, text="Safe point (mỗi dòng: x,y — dòng đầu = điểm tập kết/lập party):"
                  ).pack(anchor="w", pady=(8, 0))
        self.safe_txt = tk.Text(right, height=6, font=("Consolas", 10)); self.safe_txt.pack(fill="x")
        ttk.Label(right, text="Mob point (mỗi dòng: x,y — leader ra đứng cây):").pack(anchor="w", pady=(8, 0))
        self.mob_txt = tk.Text(right, height=6, font=("Consolas", 10)); self.mob_txt.pack(fill="x")

        self._reload_list()
        sel_iid = None
        if select_map is not None:   # chon SAN map dang train (mo dung nhom cua no)
            idx = next((i for i, m in enumerate(self.maps)
                        if str(m["id"]) == str(select_map)), None)
            if idx is not None:
                self._open_group = "g:" + (self.maps[idx].get("group") or _DEFAULT_GROUP)
                self._reload_list()   # rebuild de nhom cua map do MO ra
                if self.tree.exists(str(idx)):
                    sel_iid = str(idx)
        if sel_iid is None:           # fallback: map dau nhom dau
            first = self.tree.get_children("")
            if first:
                kids = self.tree.get_children(first[0])
                if kids:
                    sel_iid = kids[0]
        if sel_iid is not None:
            self.tree.selection_set(sel_iid); self.tree.see(sel_iid); self._on_select()

    def _group_names(self):
        """Ten cac nhom theo thu tu XUAT HIEN dau tien; nhom mac dinh (chua phan nhom) XUONG CUOI."""
        out = []
        for m in self.maps:
            g = m.get("group") or _DEFAULT_GROUP
            if g != _DEFAULT_GROUP and g not in out:
                out.append(g)
        if any((m.get("group") or _DEFAULT_GROUP) == _DEFAULT_GROUP for m in self.maps):
            out.append(_DEFAULT_GROUP)          # map khong nhom luon o duoi cung
        return out

    def _reload_list(self):
        q = self.filter_var.get().strip().lower() if hasattr(self, "filter_var") else ""
        self.tree.delete(*self.tree.get_children(""))
        # gom index theo nhom (giu thu tu xuat hien)
        groups = self._group_names()
        gidx = {g: [] for g in groups}
        for i, m in enumerate(self.maps):
            gidx[m.get("group") or _DEFAULT_GROUP].append(i)
        # accordion: neu chua co nhom mo -> mo nhom dau
        if self._open_group not in ("g:" + g for g in groups):
            self._open_group = ("g:" + groups[0]) if groups else None
        for g in groups:
            all_i = gidx[g]
            show_i = [i for i in all_i
                      if not q or q in self.maps[i]["name"].lower() or q in str(self.maps[i]["id"]).lower()]
            if q and not show_i:
                continue                       # loc: an nhom khong co map khop
            gid = "g:" + g
            # dang loc -> mo het cho de thay; binh thuong -> CHI nhom _open_group mo (accordion)
            opened = True if q else (gid == self._open_group)
            self.tree.insert("", "end", iid=gid, open=opened,
                             text=f"📁 {g}  ({len(all_i)})")
            for i in show_i:
                m = self.maps[i]
                self.tree.insert(gid, "end", iid=str(i), text=f"{m['name']} ({m['id']})")

    def _selected_map_indices(self):
        return sorted(int(iid) for iid in self.tree.selection() if not iid.startswith("g:"))

    def _reselect(self, moved_objs, delta=0):
        """Chon lai cac map (theo object id) sau khi rebuild. Mo NHOM cha (accordion: chi nhom do)."""
        rows = [i for i, m in enumerate(self.maps) if id(m) in moved_objs]
        if rows:
            # cac map moved cung 1 nhom (rang buoc chon) -> accordion mo dung nhom do
            self._open_group = "g:" + (self.maps[rows[0]].get("group") or _DEFAULT_GROUP)
            self._reload_list()
        self.tree.selection_remove(*self.tree.selection())
        for i in rows:
            iid = str(i)
            if self.tree.exists(iid):
                self.tree.selection_add(iid)
        if rows:
            last = str(rows[-1] if delta >= 0 else rows[0])
            if self.tree.exists(last):
                self.tree.see(last)
        if len(rows) == 1:
            self._cur = rows[0]; self._on_select_no_commit(rows[0])
        else:
            self._cur = None

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
        """Luu field hien tai vao self.maps[self._cur] (group doi qua menu, khong dung o day)."""
        if self._cur is None or self._cur >= len(self.maps):
            return
        m = self.maps[self._cur]
        m["id"] = self.id_var.get().strip() or m["id"]
        m["name"] = self.name_var.get().strip() or m["id"]
        m["safe"] = self._text_to_pts(self.safe_txt.get("1.0", "end"))
        m["mobs"] = self._text_to_pts(self.mob_txt.get("1.0", "end"))

    def _load_fields(self, idx):
        m = self.maps[idx]
        self.id_var.set(m["id"]); self.name_var.set(m["name"])
        self.group_lbl.configure(text=m.get("group") or _DEFAULT_GROUP)
        self.safe_txt.delete("1.0", "end"); self.safe_txt.insert("1.0", self._pts_to_text(m["safe"]))
        self.mob_txt.delete("1.0", "end"); self.mob_txt.insert("1.0", self._pts_to_text(m["mobs"]))

    def _on_select_no_commit(self, idx):
        self._load_fields(idx)

    def _on_open(self, e):
        # ACCORDION: mo 1 nhom -> tu thu gon cac nhom khac.
        opened = self.tree.focus()
        if not opened or not opened.startswith("g:"):
            return
        self._open_group = opened
        for gid in self.tree.get_children(""):
            if gid != opened:
                self.tree.item(gid, open=False)

    def _enforce_selection(self):
        """Rang buoc chon: KHONG lan nhom+map, KHONG lan map o 2 nhom khac nhau. Anchor = item vua
        thao tac (tree.focus). Cat bo phan khong hop le."""
        sel = list(self.tree.selection())
        if len(sel) <= 1:
            return
        focus = self.tree.focus() or sel[-1]
        if focus.startswith("g:"):
            keep = [focus]                 # chon nhom -> chi rieng nhom do
        else:
            g = self.maps[int(focus)].get("group") or _DEFAULT_GROUP
            keep = [iid for iid in sel if not iid.startswith("g:")
                    and (self.maps[int(iid)].get("group") or _DEFAULT_GROUP) == g]
        if set(keep) != set(sel):
            self._sel_guard = True
            self.tree.selection_set(keep)
            self._sel_guard = False

    def _on_select(self):
        if self._sel_guard:
            return
        self._enforce_selection()
        self._commit()
        sel = self._selected_map_indices()
        if len(sel) != 1:
            self._cur = None
            return
        self._cur = sel[0]
        self._load_fields(self._cur)

    def _add(self):
        self._commit()
        self.filter_var.set("")               # xoa loc de map moi chac chan hien
        # them vao NHOM dang chon (neu dang chon 1 map/nhom), khong thi 'chua phan nhom'
        g = _DEFAULT_GROUP
        selg = [iid for iid in self.tree.selection() if iid.startswith("g:")]
        selm = self._selected_map_indices()
        if selg:
            g = selg[0][2:]
        elif selm:
            g = self.maps[selm[0]].get("group") or _DEFAULT_GROUP
        newmap = {"id": "0", "name": "Map moi", "group": g, "safe": [], "mobs": []}
        self.maps.append(newmap)
        self._reload_list()
        self._reselect({id(newmap)})

    def _del(self):
        sel = self._selected_map_indices()
        if not sel:
            return
        for i in sorted(sel, reverse=True):
            del self.maps[i]
        self._cur = None
        self._reload_list()
        for w in (self.id_var, self.name_var):
            w.set("")
        self.group_lbl.configure(text="—")
        self.safe_txt.delete("1.0", "end"); self.mob_txt.delete("1.0", "end")

    def _move_group(self, gid, delta):
        """Move CA NHOM len/xuong giua cac nhom CO TEN. 'Chua phan nhom' luon o duoi cung -> nhom
        co ten khong the xuong duoi no."""
        g = gid[2:]
        named = [x for x in self._group_names() if x != _DEFAULT_GROUP]
        if g not in named:
            return
        i = named.index(g); j = i + delta
        if j < 0 or j >= len(named):
            return
        named[i], named[j] = named[j], named[i]
        has_default = any((m.get("group") or _DEFAULT_GROUP) == _DEFAULT_GROUP for m in self.maps)
        order = named + ([_DEFAULT_GROUP] if has_default else [])
        buckets = {x: [] for x in order}
        for m in self.maps:
            buckets[m.get("group") or _DEFAULT_GROUP].append(m)
        self.maps = [m for x in order for m in buckets[x]]
        self._open_group = gid
        self._reload_list()
        self.tree.selection_set(gid); self.tree.see(gid)

    def _move(self, delta):
        self._commit()
        # NHOM dang chon (header) -> move ca nhom
        selg = [iid for iid in self.tree.selection() if iid.startswith("g:")]
        if selg:
            self._move_group(selg[0], delta)
            return
        sel = self._selected_map_indices()
        if not sel:
            return
        moved = {id(self.maps[i]) for i in sel}
        # Reorder TRONG TUNG NHOM: swap voi map cung nhom lien ke theo thu tu flat. Map khac nhom
        # giu nguyen. (Dang loc thi map bi an van tinh la "cung nhom" -> van doi cho hop ly.)
        from collections import defaultdict
        bygroup = defaultdict(list)
        for i in sel:
            bygroup[self.maps[i].get("group") or _DEFAULT_GROUP].append(i)
        for g, sidx in bygroup.items():
            order_full = [i for i, m in enumerate(self.maps)
                          if (m.get("group") or _DEFAULT_GROUP) == g]
            pos = {idx: p for p, idx in enumerate(order_full)}
            n = len(order_full)
            selpos = set(pos[i] for i in sidx)
            if delta < 0 and min(selpos) <= 0:
                continue
            if delta > 0 and max(selpos) >= n - 1:
                continue
            rng = range(n) if delta < 0 else range(n - 1, -1, -1)
            for p in rng:
                q = p + delta
                if p in selpos and 0 <= q < n and q not in selpos:
                    a, b = order_full[p], order_full[q]
                    self.maps[a], self.maps[b] = self.maps[b], self.maps[a]
                    selpos.discard(p); selpos.add(q)
        self._cur = None
        self._reload_list()
        self._reselect(moved, delta)

    # ---- NHOM: chuot phai ----
    def _popup_group_menu(self, event=None):
        # neu bam phai vao 1 dong chua chon -> chon dong do truoc
        if event is not None:
            iid = self.tree.identify_row(event.y)
            if iid and iid not in self.tree.selection():
                self.tree.selection_set(iid)
        sel_groups = [iid for iid in self.tree.selection() if iid.startswith("g:")]
        sel_maps = self._selected_map_indices()
        menu = tk.Menu(self, tearoff=0)
        if sel_groups and not sel_maps:
            g = sel_groups[0][2:]
            menu.add_command(label=f"✎ Đổi tên nhóm '{g}'…", command=lambda: self._rename_group(g))
            if g != _DEFAULT_GROUP:
                menu.add_command(label="🗑 Xoá nhóm (map → chưa phân nhóm)",
                                 command=lambda: self._delete_group(g))
        elif sel_maps:
            menu.add_command(label=f"Chuyển {len(sel_maps)} map sang nhóm:", state="disabled")
            menu.add_separator()
            cur_groups = [x for x in self._group_names()]
            for g in cur_groups:
                menu.add_command(label=f"   📁 {g}",
                                 command=lambda gg=g: self._assign_group(sel_maps, gg))
            menu.add_separator()
            menu.add_command(label="➕ Nhóm mới…", command=lambda: self._assign_group_new(sel_maps))
        else:
            return
        x = event.x_root if event is not None else self.tree.winfo_rootx() + 30
        y = event.y_root if event is not None else self.tree.winfo_rooty() + 30
        menu.tk_popup(x, y)

    def _assign_group(self, indices, group):
        moved = {id(self.maps[i]) for i in indices}
        for i in indices:
            self.maps[i]["group"] = group
        self._cur = None
        self._reload_list()
        self._reselect(moved)

    def _assign_group_new(self, indices):
        import tkinter.simpledialog as sd
        name = sd.askstring("Nhóm mới", "Tên nhóm mới:", parent=self)
        name = (name or "").strip()
        if name:
            self._assign_group(indices, name)

    def _rename_group(self, group):
        import tkinter.simpledialog as sd
        new = sd.askstring("Đổi tên nhóm", "Tên mới:", initialvalue=group, parent=self)
        new = (new or "").strip()
        if not new or new == group:
            return
        for m in self.maps:
            if (m.get("group") or _DEFAULT_GROUP) == group:
                m["group"] = new
        self._reload_list()

    def _delete_group(self, group):
        # KHONG xoa map - chi go nhom (map -> chua phan nhom, xuong duoi cung)
        for m in self.maps:
            if (m.get("group") or _DEFAULT_GROUP) == group:
                m["group"] = _DEFAULT_GROUP
        self._reload_list()

    def _save(self):
        self._commit()
        # DOC LAI file tren dia (co the da co bai AUTO-LEARN moi trong luc editor mo) de MERGE,
        # tranh snapshot cu de len mat data auto-learn.
        disk = _load_json("train_maps.json").get("maps", {})
        data = {"_note": "Data map party-train. safe=[[x,y],...] (diem dau=tap ket). mobs=[[x,y],...].",
                "maps": {}}
        for m in self.maps:
            mid = m["id"].strip()
            if not mid or not mid.isdigit():
                messagebox.showerror("Lỗi", f"Map ID phải là số (map '{m['name']}')."); return
            safe, mobs = m["safe"], m["mobs"]
            # Map van rong + luc mo cung rong (user khong dong) + dia da co bai -> GIU data dia.
            if (not safe and not mobs and mid in self._orig_empty
                    and disk.get(mid, {}).get("mobs")):
                d = disk[mid]
                safe = _safe_points(d.get("safe", []))
                mobs = [list(p) for p in d.get("mobs", [])]
            entry = {"name": m["name"], "safe": safe, "mobs": mobs}
            g = m.get("group") or _DEFAULT_GROUP
            if g != _DEFAULT_GROUP:            # chua-phan-nhom thi khong ghi field cho gon
                entry["group"] = g
            data["maps"][mid] = entry
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
        self.train_maps = [(int(k), v.get("name", k), v.get("mobs", []), (v.get("group") or _DEFAULT_GROUP)) for k, v in tm_raw.items()]
        ct_raw = _load_json("cities.json").get("cities", {})
        self.cities = [(v["city_id"], v.get("flag", 0), v.get("name", k)) for k, v in ct_raw.items()]
        sv_raw = _load_json("servers.json").get("servers", {})
        self.servers = [(k, v.get("label", k)) for k, v in sv_raw.items()] or [("trieu_van", "Triệu Vân")]

        top = ttk.Frame(self, padding=6); top.pack(fill="x")
        # Kenh chung cu khong con can user cau hinh: bot tu sync/chon kenh theo party.
        # Van giu bien an de accounts.json cu/tac vu migrate doc ghi khong doi format.
        self.ch_var = tk.StringVar(value=str(data.get("channel", 2)))
        ttk.Button(top, text="➕ Thêm party", command=self._add_party).pack(side="left")
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
            try:
                self.nametowidget(t).destroy()   # DESTROY (khong chi forget) -> giai phong widget cu
            except Exception:
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
                                   on_apply_di_gioi_level=on_apply_dg,
                                   on_apply_heal_all=self._apply_heal_to_all,
                                   on_apply_furnace_all=self._apply_furnace_to_all)
            cfg.pack(fill="both", expand=True)
            entry["cfg"] = cfg
        self._free_other_built_frames(entry)
        return entry["cfg"]

    def _free_other_built_frames(self, keep):
        """CHI giu 1 PartyConfigFrame song (dang xem). Cac frame party khac da mo: FLUSH data hien
        tai -> preset roi DESTROY. Bug that: _build_entry dung frame moi cho moi tab party ma KHONG
        huy -> bam qua 30 party = 30 bang nang (5 acc x nhieu widget) song cung luc -> can GDI/USER
        handle Windows -> DO (user 39 party). Data round-trip qua preset nen Save/apply-all van du
        (get_data == serialize luc Save)."""
        for e in self.frames:
            if e is keep or e.get("cfg") is None:
                continue
            try:
                e["preset"] = e["cfg"].get_data()
            except Exception:
                pass
            try:
                e["cfg"].destroy()
            except Exception:
                pass
            e["cfg"] = None

    def _apply_heal_to_all(self, vals):
        """Ap nguong hoi mau cho MOI acc o MOI party. Party da mo (cfg) -> set thang vao acc_rows;
        party CHUA mo -> ghi vao preset['accounts'] de khi mo/luu van co. Tra tong so acc."""
        total = 0
        for entry in self.frames:
            if entry["cfg"] is not None:
                total += entry["cfg"].apply_heal_all(vals)
            else:
                preset = dict(entry["preset"] or {})
                accs = [dict(a) for a in (preset.get("accounts") or [])]
                for a in accs:
                    if not str(a.get("u", "")).strip():
                        continue           # slot 0 rong (khong co chu PT) -> bo qua
                    a["heal"] = dict(vals)
                    total += 1
                preset["accounts"] = accs
                entry["preset"] = preset
        return total

    def _apply_furnace_to_all(self, furn_cfg):
        """Ap config SOI LO (tick + LIST) cho MOI acc o MOI party (giong _apply_heal_to_all)."""
        import copy as _copy
        total = 0
        for entry in self.frames:
            if entry["cfg"] is not None:
                total += entry["cfg"].apply_furnace_all(furn_cfg)
            else:
                preset = dict(entry["preset"] or {})
                accs = [dict(a) for a in (preset.get("accounts") or [])]
                for a in accs:
                    if not str(a.get("u", "")).strip():
                        continue
                    a["furnace"] = _copy.deepcopy(furn_cfg)
                    total += 1
                preset["accounts"] = accs
                entry["preset"] = preset
        return total

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
