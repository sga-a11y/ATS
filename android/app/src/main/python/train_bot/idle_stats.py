"""Thong ke treo may cho 1 acc - chep logic `MachineBox.Statistics` cua client
(`_lua_dec/Logic/MachineBox.lua:1049`).

Pham vi: tu luc Start party toi luc Stop (user chot 29/09). Chi giu trong RAM: Stop van xem duoc
tren GUI, tat app la mat. Start party lan sau -> tao moi.
"""
from __future__ import annotations

import threading
import time
import weakref

ITEM_HONG = 23024   # 損壞的 - client bo qua khong dem (MachineBox.lua:1088)


class IdleStats:
    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.end_time = None
        self.exp = {}          # ten (char/pet) -> exp, giu thu tu nhan
        self.exp_n = {}        # ten -> so lan nhan exp
        self.exp_last = {}     # ten -> exp lan cuoi
        self._client = None    # weakref GameClient dang chay -> doc daily quest / PB to doi
        self._daily = None     # trang thai daily lan cuoi doc duoc (giu lai khi Stop)
        self.fights = 0
        self.deaths = {"char": 0, "pet": 0}   # client chi dem char; bot dem ca pet
        self.logins = 0
        self.get_items = {}    # item_id -> [ten, so luong] (InsertItems: gop theo id, giu thu tu)
        self.use_items = {}

    def stop(self):
        if self.end_time is None:
            self.end_time = time.time()

    def resume(self):
        self.end_time = None

    def elapsed(self) -> int:
        return int((self.end_time or time.time()) - self.start_time)

    def add_exp(self, name, n: int):
        if n <= 0:
            return
        with self._lock:
            self.exp[name] = self.exp.get(name, 0) + n
            self.exp_n[name] = self.exp_n.get(name, 0) + 1
            self.exp_last[name] = n

    def bind_client(self, client):
        try:
            self._client = weakref.ref(client)
        except TypeError:          # object khong ho tro weakref (vd test) -> giu ref thuong
            self._client = lambda: client

    def _read_daily(self):
        c = self._client() if self._client else None
        if c is not None:
            try:
                self._daily = c.daily_status()
            except Exception:
                pass
        return self._daily

    def add_fight(self):
        with self._lock:
            self.fights += 1

    def add_death(self, who: str = "char"):
        with self._lock:
            self.deaths[who] = self.deaths.get(who, 0) + 1

    def add_login(self):
        with self._lock:
            self.logins += 1

    @staticmethod
    def _insert(t, item_id, name, quant):
        rec = t.get(item_id)
        if rec is None:
            t[item_id] = [name, quant]
        else:
            rec[1] += quant

    def add_get_item(self, item_id: int, name: str, quant: int):
        if quant <= 0 or item_id == ITEM_HONG:
            return
        with self._lock:
            self._insert(self.get_items, item_id, name, quant)

    def add_use_item(self, item_id: int, name: str, quant: int):
        if quant <= 0:
            return
        with self._lock:
            self._insert(self.use_items, item_id, name, quant)

    def snapshot(self) -> dict:
        daily = self._read_daily()
        with self._lock:
            return {
                "elapsed": self.elapsed(),
                "running": self.end_time is None,
                "exp": dict(self.exp),
                "exp_n": dict(self.exp_n),
                "exp_last": dict(self.exp_last),
                "daily": daily,
                "fights": self.fights,
                "deaths": dict(self.deaths),
                "logins": self.logins,
                "get_items": [(i, n, q) for i, (n, q) in self.get_items.items()],
                "use_items": [(i, n, q) for i, (n, q) in self.use_items.items()],
            }


def fmt_time(sec: int) -> str:
    h, r = divmod(max(0, int(sec)), 3600)
    m, s = divmod(r, 60)
    return "%02d:%02d:%02d" % (h, m, s)
