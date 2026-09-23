# -*- coding: utf-8 -*-
"""`setup_party_runtime` phai IN RA cac tick vua nhan.

CHI BAN APK di qua ham nay - ban PC doc thang `config.py`. Nen day la CUA SO DUY NHAT de biet
dien thoai that su gui gi, va bug dang "tick khong co tac dung" chi hien o APK.

Truoc 23/09 ham nay nhan xong ghi thang vao `PARTY_CONFIG` roi thoi, KHONG mot dong log. User bao:
    "khong tick danh boss QD ma no van danh"
    "khong tick mua HP SP ma van di mua"
ma khong cach nao biet tick do co toi Python khong.

Phia Kotlin goi ham nay THEO VI TRI voi 58 doi so; doi chieu tung cap thi khop (58 <-> 58), nhung
"khop tren giay" khong phai bang chung ve GIA TRI THAT luc chay. APK co man hinh log trong app nen
user doc duoc dong nay ma khong can logcat.
"""
from __future__ import annotations

import ast
import io
import logging
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

# Tick nao cung phai doc duoc tu dong log. Ten hien thi -> ten tham so cua ham.
TICK_PHAI_IN = {
    "boss_QD": "fight_legion_boss",
    "boss_TG": "auto_world_boss",
    "PB_doi": "auto_team_dungeon",
    "daily": "do_daily",
    "van_tieu": "do_van_tieu",
    "mua_HP": "buy_hp",
    "mua_SP": "buy_sp",
    "phuc_than": "use_phuc_than",
    "ho_phu_DG": "use_digioi_ho_phu",
    "doi_qua_event": "auto_event_exchange",
    "mo_ruong": "auto_open_boxes",
    "cat_do": "auto_cat_do",
    "ban_noi_dat": "auto_sell_noi_dat",
    "don_tui": "auto_bag_clean",
    "vut_rac": "auto_discard_junk",
    "phan_giai_cuon": "auto_decompose_scrolls",
    "donate": "auto_donate_materials",
}


class _Bat(logging.Handler):
    def __init__(self):
        super().__init__()
        self.dong = []

    def emit(self, rec):
        try:
            self.dong.append(rec.getMessage())
        except Exception:
            pass


def _chay(**kw):
    """Goi `setup_party_runtime` va tra dong log SETUP."""
    bat = _Bat()
    log = logging.getLogger("partydg")   # ten logger cua run_party_digioi
    log.addHandler(bat)
    _cu = log.level
    log.setLevel(logging.INFO)
    try:
        R.setup_party_runtime(0, "train", "1.2.3.4", 9, "u1\x01p1\x01\x01\x01", **kw)
    finally:
        log.removeHandler(bat)
        log.setLevel(_cu)
    _d = [d for d in bat.dong if "SETUP:" in d]
    assert _d, "khong in dong SETUP nao"
    return _d[-1]


class TestCoDongLogSetup(unittest.TestCase):
    def test_in_du_moi_tick(self):
        dong = _chay()
        for nhan in TICK_PHAI_IN:
            self.assertIn(nhan + "=", dong, "dong SETUP thieu tick %r" % nhan)

    def test_in_DUNG_gia_tri_khi_TAT(self):
        """Quan trong nhat: user BO TICK thi dong log phai noi False."""
        dong = _chay(fight_legion_boss=False, auto_world_boss=False, buy_hp=False, buy_sp=False,
                     do_van_tieu=False, auto_team_dungeon=False)
        for nhan in ("boss_QD", "boss_TG", "PB_doi", "van_tieu", "mua_HP", "mua_SP"):
            self.assertIn("%s=False" % nhan, dong, "%s TAT ma log khong noi False" % nhan)

    def test_in_DUNG_gia_tri_khi_BAT(self):
        dong = _chay(fight_legion_boss=True, buy_hp=True, use_phuc_than=True)
        for nhan in ("boss_QD", "mua_HP", "phuc_than"):
            self.assertIn("%s=True" % nhan, dong, "%s BAT ma log khong noi True" % nhan)

    def test_in_ca_SO_LUONG_qua_event(self):
        """Tick bat ma danh sach rong thi bot khong doi gi - phai phan biet duoc hai ca do."""
        dong = _chay(auto_event_exchange=True, event_exchange_items="qua1\nqua2")
        self.assertIn("doi_qua_event=True(2 mon)", dong)
        dong = _chay(auto_event_exchange=True, event_exchange_items="")
        self.assertIn("doi_qua_event=True(0 mon)", dong)

    def test_in_ca_NGUONG_mua_HP_SP(self):
        dong = _chay(buy_hp=True, hp_qty=123, hp_thresh=456)
        self.assertIn("mua_HP=True(123/456)", dong)

    def test_co_so_party_de_biet_dong_nay_cua_ai(self):
        self.assertIn("PARTY 1 SETUP", _chay())


class TestKhongLamHongHam(unittest.TestCase):
    def test_van_ghi_config_nhu_cu(self):
        _chay(fight_legion_boss=False)
        from bot import config
        self.assertIs(config.PARTY_CONFIG[0]["fight_legion_boss"], False)

    def test_log_nam_o_CUOI_ham(self):
        """In truoc khi ghi xong config thi doc phai gia tri nua voi."""
        src = io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8").read()
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "setup_party_runtime")
        than = ast.get_source_segment(src, fn)
        i_cfg = than.find("config.PARTY_CONFIG[pidx] = {")
        i_log = than.find("SETUP: mode=")
        self.assertGreater(i_cfg, 0)
        self.assertGreater(i_log, i_cfg, "in log TRUOC khi ghi config")


if __name__ == "__main__":
    unittest.main()
