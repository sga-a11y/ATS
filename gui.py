# -*- coding: utf-8 -*-
"""GUI quan ly bot TS Online (Tkinter - khong can cai them gi).

Tinh nang:
  - Moi PARTY = 1 tab. Trong tab: bang trang thai tung acc + Start/Stop tung acc + ca party.
  - Start/Stop toan bo.
  - Log truc tiep (cuon theo thoi gian thuc).
  - Sua cau hinh (party/acc, map train/DG) -> luu accounts.json.

Chay:  python gui.py
"""
import os, sys, json, re, queue, logging, threading, time, collections, importlib
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

_LABEL_RE = re.compile(r"^\d\d:\d\d:\d\d \[([^\]]+)\]")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_party_digioi as ctrl          # module dieu khien (da refactor)
from bot import config
from bot._appdir import app_dir as _app_dir   # thu muc goc (dev=project, frozen=canh .exe)

ACCOUNTS_JSON = os.path.join(_app_dir(), "accounts.json")

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


def _map_name(mid):
    if mid is None:
        return "-"
    if mid == getattr(config, "DIGIOI_MAP_ID", -1):
        return f"Dị Giới ({mid})"
    tm = getattr(config, "TRAIN_MAPS", {}).get(mid)
    if tm:
        return f"Train ({mid})"
    return str(mid)


# ---------------- App ----------------
class BotGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TS Online Bot Manager")
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
        self._build_toolbar()
        self._build_tabs()
        self._build_log()
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.after(1000, self._refresh)
        self.after(300, self._drain_log)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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

    # ---- toolbar ----
    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Button(bar, text="▶ START TẤT CẢ", command=self._start_all).pack(side="left", padx=3)
        ttk.Button(bar, text="■ STOP TẤT CẢ", command=self._stop_all).pack(side="left", padx=3)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(bar, text="🗑 Xóa log", command=self._clear_log).pack(side="left", padx=3)
        ttk.Button(bar, text="📋 Log: Tất cả", command=self._log_show_all).pack(side="left", padx=3)
        ttk.Button(bar, text="Mỗi party 1 chế độ → ⚙ Cấu hình",
                   command=self._open_config).pack(side="right", padx=8)

    # ---- che tai khoan/ten (BAM vao header cot "Tai khoan"/"Nhan vat" de doi) ----
    # Tranh bi soi khi quay/share man hinh. 3 trang thai: 0=hien full | 1=che giua (s***01) |
    # 2=an het (*****). Icon tren header bao trang thai. Mac dinh che giua.
    _privacy = 1
    _PRIV_ICON = ["👁", "👁‍🗨", "🙈"]   # 0 hien | 1 che giua | 2 an het

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

    def _mask(self, s):
        """Che tai khoan/ten theo trang thai con mat. 0=full | 1=s***01 | 2=*****."""
        if not s or s == "-":
            return s
        st = getattr(self, "_privacy", 0)
        if st == 0:
            return s
        if st == 2:
            return "*****"
        # 1 = che giua: ky tu dau + 3 sao + 2 ky tu cuoi (s***01). Ngan qua thi che gon.
        if len(s) <= 3:
            return s[0] + "***"
        return s[0] + "***" + s[-2:]

    def _char_cell(self, s):
        """Cot Nhan vat: 'tenNV_lvchar_tenPet_lvPet'. Privacy CHI che ten NV (lv + pet luon hien).
        Khong co pet -> 'tenNV_lvchar'. Chua load lv -> chi 'tenNV'."""
        parts = [self._mask(s.get("char") or "-")]
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
        lb = tk.Listbox(win, width=34, height=min(16, max(3, len(self.cities))), font=("", 10))
        lb.pack(fill="both", expand=True, padx=8)
        for (cid, f, n) in self.cities:
            lb.insert("end", n)
        def _go():
            sel = lb.curselection()
            if sel:
                cid, f, n = self.cities[sel[0]]
                threading.Thread(target=ctrl.party_teleport_city,
                                 args=(pidx, cid, f), daemon=True).start()
            win.destroy()
        ttk.Button(win, text="✔ Teleport về thành này", command=_go).pack(pady=8)

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
                "stand": "Đứng yên", "cleanbag": "Dọn túi"}.get(pmode, pmode)
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
                self.log_txt.insert("end", line + "\n")
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
            for (u, p, is_leader, is_picker) in ctrl.party_accounts(pidx):
                if not tree.exists(u):
                    continue
                p_total += 1
                s = ctrl.account_status(u)
                if s["running"]:
                    any_running = True
                    p_run += 1
                if s.get("strategist"):
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
                tree.item(u, values=(self._mask(u), self._char_cell(s), role, run, _map_name(s["map"]),
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
                self.log_txt.insert("end", line + "\n")
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
                        pc.get("mob_index"), pc.get("city_flag"), pc.get("do_dungeon"))
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
    ("cleanbag", "Dọn dẹp túi đồ (chưa làm)"),
]
_MODE_LABEL = dict(MODE_OPTIONS)
_LABEL_MODE = {v: k for k, v in MODE_OPTIONS}


class PartyConfigFrame(ttk.Frame):
    """1 tab cau hinh 1 party: mode (dropdown) + map/quai/thanh (dropdown) + acc."""
    def __init__(self, master, party, train_maps, cities, servers):
        super().__init__(master, padding=8)
        self.train_maps = train_maps   # list (map_id, name, mobs)
        self.cities = cities           # list (city_id, flag, name)
        self.servers = servers         # list (key, label)
        self._preset = party or {}

        srow = ttk.Frame(self); srow.pack(fill="x", pady=4)
        ttk.Label(srow, text="Server:", width=10).pack(side="left")
        self.server_var = tk.StringVar()
        cur_srv = self._preset.get("server", servers[0][0] if servers else "trieu_van")
        self.server_var.set(dict(servers).get(cur_srv, servers[0][1] if servers else cur_srv))
        ttk.Combobox(srow, textvariable=self.server_var, state="readonly", width=22,
                     values=[lbl for _, lbl in servers]).pack(side="left")

        row = ttk.Frame(self); row.pack(fill="x", pady=4)
        ttk.Label(row, text="Chế độ:", width=10).pack(side="left")
        self.mode_var = tk.StringVar(value=_MODE_LABEL.get(self._preset.get("mode", "digioi"),
                                                           "Train Dị Giới"))
        cb = ttk.Combobox(row, textvariable=self.mode_var, state="readonly", width=34,
                          values=[lbl for _, lbl in MODE_OPTIONS])
        cb.pack(side="left"); cb.bind("<<ComboboxSelected>>", lambda e: self._on_mode_change())

        self.dyn = ttk.Frame(self); self.dyn.pack(fill="x", pady=6)
        self.map_var = tk.StringVar(); self.mob_var = tk.StringVar(); self.city_var = tk.StringVar()
        self.map_cb = self.mob_cb = self.city_cb = None

        # KHONG co chu PT: slot 0 = ("","") -> member tu dung cho leader ngoai/tay moi.
        accs = self._preset.get("accounts", [])
        no_leader = bool(accs) and not (accs[0].get("u", "").strip())
        shown = accs[1:] if no_leader else accs
        # Hang: [Khong co chu PT] ... [White list rieng party nay]
        nlrow = ttk.Frame(self); nlrow.pack(fill="x", pady=(2, 0))
        self.no_leader_var = tk.BooleanVar(value=no_leader)
        ttk.Checkbutton(nlrow, text="Không có chủ PT (member tự đứng, chờ leader ngoài/tay mời)",
                        variable=self.no_leader_var).pack(side="left")
        wl = self._preset.get("leaders", [])
        ttk.Label(nlrow, text="  │  White list riêng:").pack(side="left")
        self.leaders_var = tk.StringVar(value=", ".join(wl) if isinstance(wl, list) else str(wl or ""))
        ttk.Entry(nlrow, textvariable=self.leaders_var).pack(side="left", fill="x", expand=True, padx=4)

        self.dungeon_var = tk.BooleanVar(value=self._preset.get("do_dungeon", True))
        ttk.Checkbutton(self, text="Đánh daily dungeon (lượt 1 free, lượt 2+ mua vàng)",
                        variable=self.dungeon_var).pack(anchor="w")

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
            self._add_acc_row(u, a.get("p", ""), on)
        ttk.Button(self, text="➕ Thêm dòng acc",
                   command=lambda: self._add_acc_row("", "", True)).pack(anchor="w", pady=(2, 0))
        self._render_dyn()

    def _add_acc_row(self, u="", p="", on=True):
        fr = ttk.Frame(self._acc_inner); fr.pack(fill="x", pady=1)
        on_var = tk.BooleanVar(value=bool(on))
        ttk.Checkbutton(fr, variable=on_var).pack(side="left")
        e_u = ttk.Entry(fr, width=16, font=("Consolas", 10)); e_u.pack(side="left", padx=(0, 4))
        e_u.insert(0, u)
        e_p = ttk.Entry(fr, width=14, font=("Consolas", 10)); e_p.pack(side="left", padx=(0, 4))
        e_p.insert(0, p)
        row = {"on": on_var, "u": e_u, "p": e_p, "frame": fr}
        ttk.Button(fr, text="✕", width=2, command=lambda: self._del_acc_row(row)).pack(side="left")
        self.acc_rows.append(row)

    def _del_acc_row(self, row):
        row["frame"].destroy()
        if row in self.acc_rows:
            self.acc_rows.remove(row)

    def _on_mode_change(self):
        # Khi DOI che do: tu set mac dinh "Khong co chu PT".
        #  - city (ve thanh) / stand (login dau dung yen): TICK (member tu dung, khong can chu PT).
        #  - train / digioi: BO TICK (can chu PT de keo party + lap tran).
        mode = _LABEL_MODE.get(self.mode_var.get(), "digioi")
        self.no_leader_var.set(mode in ("city", "stand"))
        self._render_dyn()

    def _render_dyn(self):
        for w in self.dyn.winfo_children():
            w.destroy()
        mode = _LABEL_MODE.get(self.mode_var.get(), "digioi")
        if mode == "train":
            ttk.Label(self.dyn, text="Map:", width=10).pack(side="left")
            names = [n for (_i, n, _m) in self.train_maps]
            self.map_cb = ttk.Combobox(self.dyn, textvariable=self.map_var, state="readonly",
                                       width=22, values=names)
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
                        if cid == self._preset.get("start_city_id")), 0)
            if names:
                self.city_var.set(names[idx])
        elif mode == "digioi":
            ttk.Label(self.dyn, text="→ START_CITY_ID = 49942 (Dị Giới, cố định)").pack(side="left")
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
        accs = []
        for r in self.acc_rows:
            u = r["u"].get().strip()
            if not u:
                continue
            accs.append({"u": u, "p": r["p"].get().strip(), "on": bool(r["on"].get())})
        if self.no_leader_var.get() and accs:
            accs = [{"u": "", "p": "", "on": True}] + accs   # slot 0 trong = KHONG co chu PT
        # server: label -> key
        srv = next((k for k, lbl in self.servers if lbl == self.server_var.get()),
                   self.servers[0][0] if self.servers else "trieu_van")
        leaders = [x.strip() for x in self.leaders_var.get().split(",") if x.strip()]
        return {"server": srv, "mode": mode, "start_city_id": sc, "mob_index": mob_index,
                "city_flag": city_flag, "do_dungeon": bool(self.dungeon_var.get()),
                "leaders": leaders, "accounts": accs}


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
        self.geometry("620x540")
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
        self.lb = tk.Listbox(left, width=26, height=20, exportselection=False)
        self.lb.pack(fill="y", expand=True)
        self.lb.bind("<<ListboxSelect>>", lambda e: self._on_select())
        b = ttk.Frame(left); b.pack(fill="x", pady=4)
        ttk.Button(b, text="+ Thêm", command=self._add).pack(side="left")
        ttk.Button(b, text="🗑 Xóa", command=self._del).pack(side="left", padx=4)
        b2 = ttk.Frame(left); b2.pack(fill="x")
        ttk.Button(b2, text="▲ Lên", command=lambda: self._move(-1)).pack(side="left")
        ttk.Button(b2, text="▼ Xuống", command=lambda: self._move(1)).pack(side="left", padx=4)

        right = ttk.Frame(self, padding=6); right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="Map ID (log 'MAP HIEN TAI'):").pack(anchor="w")
        self.id_var = tk.StringVar(); ttk.Entry(right, textvariable=self.id_var, width=16).pack(anchor="w")
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
        data = self._load()
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
        try:
            with open(ACCOUNTS_JSON, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"channel": 2, "parties": []}

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
            cfg = PartyConfigFrame(entry["holder"], entry["preset"],
                                   self.train_maps, self.cities, self.servers)
            cfg.pack(fill="both", expand=True)
            entry["cfg"] = cfg
        return entry["cfg"]

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
            # ghi ngay vao accounts.json (chi update party_leaders, giu cac key khac)
            d = self._load() or {}
            d["party_leaders"] = names
            try:
                with open(ACCOUNTS_JSON, "w", encoding="utf-8") as f:
                    json.dump(d, f, ensure_ascii=False, indent=2)
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
        with open(ACCOUNTS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
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
