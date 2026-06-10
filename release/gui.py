# -*- coding: utf-8 -*-
"""GUI quan ly bot TS Online (Tkinter - khong can cai them gi).

Tinh nang:
  - Moi PARTY = 1 tab. Trong tab: bang trang thai tung acc + Start/Stop tung acc + ca party.
  - Start/Stop toan bo.
  - Log truc tiep (cuon theo thoi gian thuc).
  - Sua cau hinh (party/acc, map train/DG) -> luu accounts.json.

Chay:  python gui.py
"""
import os, sys, json, re, queue, logging, threading, time, collections
import tkinter as tk
from tkinter import ttk, messagebox

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
    h = _QueueHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
    logging.getLogger().addHandler(h)


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
        sc = getattr(config, "START_CITY_ID", 0)
        mode = "Dị Giới" if sc == getattr(config, "DIGIOI_MAP_ID", -1) else \
               (f"Map-train {sc}" if config.TRAIN_MAPS.get(sc) else f"Đứng yên ({sc})")
        self._mode_lbl = ttk.Label(bar, text=f"Chế độ: {mode}", font=("", 10, "bold"))
        self._mode_lbl.pack(side="right", padx=8)

    # ---- tabs per party ----
    def _build_tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=4)
        self.party_trees = {}   # pidx -> Treeview
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
            self.nb.add(frame, text=f"Party {pidx + 1} ({len(accs)})")
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
            tree = ttk.Treeview(frame, columns=cols, show="headings", height=8)
            for c in cols:
                tree.heading(c, text=heads[c]); tree.column(c, width=widths[c], anchor="center")
            tree.column("acc", anchor="w"); tree.column("char", anchor="w")
            tree.tag_configure("on", foreground="#0a0")
            tree.tag_configure("off", foreground="#999")
            tree.bind("<<TreeviewSelect>>", lambda e, p=pidx: self._on_acc_select(p))
            tree.pack(fill="both", expand=True)
            for (u, p, is_leader, is_picker) in accs:
                role = "LEADER" if is_leader else ("picker" if is_picker else "member")
                tree.insert("", "end", iid=u, values=(u, "", role, "Tắt", "-", "-", "-", "-", "-"),
                            tags=("off",))
            self.party_trees[pidx] = tree

    # ---- log panel ----
    def _build_log(self):
        self._log_frame = ttk.LabelFrame(self, text="Log — Tất cả", padding=4)
        self._log_frame.pack(fill="both", expand=False, padx=6, pady=(0, 6))
        self.log_txt = tk.Text(self._log_frame, height=12, wrap="none", bg="#111", fg="#ddd",
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
            for (u, p, is_leader, is_picker) in ctrl.party_accounts(pidx):
                if not tree.exists(u):
                    continue
                s = ctrl.account_status(u)
                role = "LEADER" if is_leader else ("picker" if is_picker else "member")
                run = "● CHẠY" if s["running"] else "Tắt"
                dg = f"{s['dg_remain']}p" if s["dg_remain"] is not None else "-"
                tree.item(u, values=(u, s["char"] or "-", role, run, _map_name(s["map"]),
                                     s["channel"] if s["channel"] else "-",
                                     "✔" if s["in_party"] else "-", dg,
                                     "⚔" if s["combat"] else "-"),
                          tags=("on" if s["running"] else "off",))
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
    def _open_config(self):
        ConfigDialog(self)

    def _on_close(self):
        if messagebox.askokcancel("Thoát", "Dừng tất cả acc và thoát?"):
            try: ctrl.stop_all()
            except Exception: pass
            self.destroy()


# ---------------- Config dialog ----------------
class ConfigDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Cấu hình - accounts.json")
        self.geometry("640x560")
        self.transient(master); self.grab_set()
        data = self._load()
        top = ttk.Frame(self, padding=6); top.pack(fill="x")
        ttk.Label(top, text="START_CITY_ID (12831=map train, 49942=Dị Giới, 0=đứng yên):").pack(side="left")
        self.sc_var = tk.StringVar(value=str(data.get("start_city_id", 0)))
        ttk.Entry(top, textvariable=self.sc_var, width=10).pack(side="left", padx=4)
        ttk.Label(top, text="Kênh:").pack(side="left", padx=(10, 0))
        self.ch_var = tk.StringVar(value=str(data.get("channel", 1)))
        ttk.Entry(top, textvariable=self.ch_var, width=6).pack(side="left", padx=4)

        ttk.Label(self, text="Mỗi dòng 1 acc: user,pass  | dòng trống ngăn cách các party "
                  "(slot đầu mỗi party = chủ PT)", padding=6).pack(fill="x")
        self.txt = tk.Text(self, wrap="none", font=("Consolas", 10))
        self.txt.pack(fill="both", expand=True, padx=6)
        self.txt.insert("1.0", self._parties_to_text(data.get("parties", [])))

        bar = ttk.Frame(self, padding=6); bar.pack(fill="x")
        ttk.Button(bar, text="💾 Lưu", command=self._save).pack(side="right", padx=3)
        ttk.Button(bar, text="Hủy", command=self.destroy).pack(side="right", padx=3)

    def _load(self):
        try:
            with open(ACCOUNTS_JSON, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"start_city_id": 0, "channel": 1, "parties": []}

    def _parties_to_text(self, parties):
        blocks = []
        for party in parties:
            lines = [f"{a.get('u','')},{a.get('p','')}" for a in party.get("accounts", [])]
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def _text_to_parties(self):
        raw = self.txt.get("1.0", "end").strip("\n")
        parties = []
        for block in raw.split("\n\n"):
            accs = []
            for line in block.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [x.strip() for x in line.split(",")]
                u = parts[0]; p = parts[1] if len(parts) > 1 else ""
                accs.append({"u": u, "p": p})
            if accs:
                parties.append({"accounts": accs})
        return parties

    def _save(self):
        try:
            data = {
                "start_city_id": int(self.sc_var.get().strip() or 0),
                "channel": int(self.ch_var.get().strip() or 1),
                "parties": self._text_to_parties(),
            }
        except ValueError:
            messagebox.showerror("Lỗi", "START_CITY_ID / Kênh phải là số."); return
        with open(ACCOUNTS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Đã lưu", "Đã lưu accounts.json.\nKhởi động lại app để áp dụng cấu hình mới.")
        self.destroy()


if __name__ == "__main__":
    _setup_log_capture()
    BotGUI().mainloop()
