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

ACCOUNTS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.json")

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
        self._dot_on = self._make_dot("#16c60c")    # xanh la: co acc dang chay
        self._dot_off = self._make_dot("#888888")   # xam: khong co acc nao chay
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
        ttk.Button(bar, text="⚙ Cấu hình", command=self._open_config).pack(side="left", padx=3)
        ttk.Button(bar, text="🗑 Xóa log", command=self._clear_log).pack(side="left", padx=3)
        ttk.Button(bar, text="📋 Log: Tất cả", command=self._log_show_all).pack(side="left", padx=3)
        ttk.Label(bar, text="Mỗi party 1 chế độ → ⚙ Cấu hình", font=("", 10, "bold")
                  ).pack(side="right", padx=8)

    # ---- tabs per party ----
    def _build_tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="x", expand=False, padx=6, pady=4)   # bang gon -> log chiem phan lon
        self.nb.bind("<Double-1>", self._on_tab_dblclick)      # double-click tab -> mo Setting party do
        self.party_trees = {}   # pidx -> Treeview
        self._populate_tabs()

    def _populate_tabs(self):
        # xoa tab cu (dung khi reload config) roi dung lai theo config moi
        for tab in self.nb.tabs():
            self.nb.forget(tab)
        self.party_trees = {}
        self.party_frames = {}   # pidx -> frame (de cap nhat cham trang thai)
        cols = ("acc", "char", "role", "run", "map", "ch", "party", "dg", "combat")
        heads = {"acc": "Tài khoản", "char": "Nhân vật", "role": "Vai trò", "run": "Trạng thái",
                 "map": "Map", "ch": "Kênh", "party": "Trong PT", "dg": "DG còn", "combat": "Đánh"}
        widths = {"acc": 90, "char": 110, "role": 70, "run": 90, "map": 130, "ch": 50,
                  "party": 70, "dg": 70, "combat": 55}
        for pidx in range(len(config.PARTIES)):
            accs = ctrl.party_accounts(pidx)
            if not accs:
                continue
            frame = ttk.Frame(self.nb, padding=4)
            pmode = config.PARTY_CONFIG.get(pidx, {}).get("mode", "?")
            mlbl = {"digioi": "Dị Giới", "train": "Train map", "city": "Về thành",
                    "stand": "Đứng yên", "cleanbag": "Dọn túi"}.get(pmode, pmode)
            self.nb.add(frame, text=f"P{pidx + 1} · {mlbl} ({len(accs)})",
                        image=self._dot_off, compound="left")   # cham trang thai (xam/xanh)
            self.party_frames[pidx] = frame
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
            tree = ttk.Treeview(frame, columns=cols, show="headings", height=max(len(accs), 3))
            for c in cols:
                tree.heading(c, text=heads[c]); tree.column(c, width=widths[c], anchor="center")
            tree.column("acc", anchor="w"); tree.column("char", anchor="w")
            tree.tag_configure("on", foreground="#0a0")
            tree.tag_configure("off", foreground="#999")
            tree.tag_configure("qs", foreground="#c25e00")   # quan su - cam noi bat
            tree.bind("<<TreeviewSelect>>", lambda e, p=pidx: self._on_acc_select(p))
            tree.pack(fill="x", expand=False)
            for (u, p, is_leader, is_picker) in accs:
                role = "LEADER" if is_leader else ("picker" if is_picker else "member")
                tree.insert("", "end", iid=u, values=(u, "", role, "Tắt", "-", "-", "-", "-", "-"),
                            tags=("off",))
            self.party_trees[pidx] = tree

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
        try:
            pidx = self.nb.index(self.nb.select())
        except Exception:
            return
        users = set(u for (u, *_ ) in ctrl.party_accounts(pidx))
        self._set_log_filter(users, f"Party {pidx + 1}")

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
        for pidx, tree in self.party_trees.items():
            any_running = False
            for (u, p, is_leader, is_picker) in ctrl.party_accounts(pidx):
                if not tree.exists(u):
                    continue
                s = ctrl.account_status(u)
                if s["running"]:
                    any_running = True
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
                tree.item(u, values=(u, s["char"] or "-", role, run, _map_name(s["map"]),
                                     s["channel"] if s["channel"] else "-",
                                     "✔" if s["in_party"] else "-", dg,
                                     "⚔" if s["combat"] else "-"),
                          tags=(tag,))
            # cap nhat cham trang thai tab: xanh neu co >=1 acc chay, xam neu khong
            frame = self.party_frames.get(pidx)
            if frame is not None:
                try:
                    self.nb.tab(frame, image=self._dot_on if any_running else self._dot_off)
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
    def _on_tab_dblclick(self, event):
        # double-click LEN TAB nao -> mo Setting cua party do luon
        try:
            idx = self.nb.index("@%d,%d" % (event.x, event.y))
        except Exception:
            return   # double-click ngoai vung tab header -> bo qua
        ConfigDialog(self, open_pidx=idx)

    def _open_config(self):
        # mo Setting o dung tab party DANG CHON (thay vi mac dinh party 1)
        try:
            cur = self.nb.index(self.nb.select())
        except Exception:
            cur = 0
        ConfigDialog(self, open_pidx=cur)

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
_BASE = os.path.dirname(os.path.abspath(__file__))


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
        cb.pack(side="left"); cb.bind("<<ComboboxSelected>>", lambda e: self._render_dyn())

        self.dyn = ttk.Frame(self); self.dyn.pack(fill="x", pady=6)
        self.map_var = tk.StringVar(); self.mob_var = tk.StringVar(); self.city_var = tk.StringVar()
        self.map_cb = self.mob_cb = self.city_cb = None

        # KHONG co chu PT: slot 0 = ("","") -> member tu dung cho leader ngoai/tay moi.
        accs = self._preset.get("accounts", [])
        no_leader = bool(accs) and not (accs[0].get("u", "").strip())
        shown = accs[1:] if no_leader else accs
        self.no_leader_var = tk.BooleanVar(value=no_leader)
        ttk.Checkbutton(self, text="Không có chủ PT (member tự đứng, chờ leader ngoài/tay mời)",
                        variable=self.no_leader_var).pack(anchor="w", pady=(2, 0))
        self.dungeon_var = tk.BooleanVar(value=self._preset.get("do_dungeon", True))
        ttk.Checkbutton(self, text="Đánh daily dungeon (lượt 1 free, lượt 2+ mua vàng)",
                        variable=self.dungeon_var).pack(anchor="w")

        ttk.Label(self, text="Acc (mỗi dòng: user,pass — DÒNG ĐẦU = chủ PT trừ khi tick ô trên; "
                  "thêm # đầu dòng để BỎ QUA acc đó):").pack(anchor="w")
        self.txt = tk.Text(self, height=7, font=("Consolas", 10))
        self.txt.pack(fill="both", expand=True)
        self.txt.insert("1.0", "\n".join(f"{a.get('u','')},{a.get('p','')}" for a in shown))
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
            self._fill_mobs(self._preset.get("mob_index", -1))   # mac dinh = Bot tu chon (auto)
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
        for line in self.txt.get("1.0", "end").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [x.strip() for x in line.split(",")]
            accs.append({"u": parts[0], "p": parts[1] if len(parts) > 1 else ""})
        if self.no_leader_var.get() and accs:
            accs = [{"u": "", "p": ""}] + accs   # slot 0 trong = KHONG co chu PT
        # server: label -> key
        srv = next((k for k, lbl in self.servers if lbl == self.server_var.get()),
                   self.servers[0][0] if self.servers else "trieu_van")
        return {"server": srv, "mode": mode, "start_city_id": sc, "mob_index": mob_index,
                "city_flag": city_flag, "do_dungeon": bool(self.dungeon_var.get()), "accounts": accs}


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

        self.nb = ttk.Notebook(self); self.nb.pack(fill="both", expand=True, padx=6, pady=4)
        self.frames = []
        for party in (data.get("parties") or [{}]):
            self._add_tab(party)
        # mo dung tab party dang chon ben ngoai
        if self.frames:
            self.nb.select(min(max(open_pidx, 0), len(self.frames) - 1))

        bar = ttk.Frame(self, padding=6); bar.pack(fill="x")
        ttk.Button(bar, text="💾 Lưu", command=self._save).pack(side="right", padx=3)
        ttk.Button(bar, text="Hủy", command=self.destroy).pack(side="right", padx=3)

    def _load(self):
        try:
            with open(ACCOUNTS_JSON, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"channel": 2, "parties": []}

    def _add_tab(self, party):
        f = PartyConfigFrame(self.nb, party, self.train_maps, self.cities, self.servers)
        self.nb.add(f, text=f"Party {len(self.frames) + 1}")
        self.frames.append(f)

    def _add_party(self):
        self._add_tab({})
        self.nb.select(len(self.frames) - 1)

    def _del_party(self):
        if len(self.frames) <= 1:
            return
        i = self.nb.index(self.nb.select())
        self.nb.forget(i); self.frames.pop(i)
        for j, f in enumerate(self.frames):
            self.nb.tab(f, text=f"Party {j + 1}")

    def _save(self):
        try:
            ch = int(self.ch_var.get().strip() or 2)
        except ValueError:
            messagebox.showerror("Lỗi", "Kênh phải là số."); return
        # tab party DANG SUA trong dialog -> de quay ve dung tab do o GUI chinh sau khi luu
        try:
            cur_pidx = self.nb.index(self.nb.select())
        except Exception:
            cur_pidx = 0
        parties = [f.get_data() for f in self.frames]
        parties = [p for p in parties if p["accounts"]]   # bo party rong
        data = {"channel": ch, "parties": parties}
        with open(ACCOUNTS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        master = self.master
        self.destroy()
        if hasattr(master, "reload_config"):
            master.reload_config()   # tu nap lai - khong can dong app
        # chuyen GUI chinh ve tab party vua sua
        try:
            tabs = master.nb.tabs()
            if tabs:
                master.nb.select(min(max(cur_pidx, 0), len(tabs) - 1))
        except Exception:
            pass


if __name__ == "__main__":
    try:
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
