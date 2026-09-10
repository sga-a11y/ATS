"""KHAC MAP THI GOM MAP - khong bọc thêm hai lớp trì hoãn.

User 09/09: "p1 biet khac map ma deo gom map, cai dieu phoi m viet ngu den the a" -> "di train thi
don gian la khac map thi gom map, khac kenh thi gom kenh, du thi di train, m long vong mai van loi
la sao".

Cai "long vong" la hai lop TOI tu them, chong len nhau thanh mot cai khoa:

  1. AN HAN 60 GIAY dung chung cho ca lech map lan lech kenh. 60 giay la han cua mot CHUYEN GOM
     dang chay (ve thanh trung gian -> thanh tap ket, tung acc lech nhip); lay no lam han PHAT
     HIEN lech thi party lech ca phut van chua duoc ra lenh. Teleport chuyen tiep chi mat vai giay.

  2. DONG HO RESET VE 0 khi thay cung map MOT nhip. Party lech NGAT QUANG thi dong ho khong bao
     gio chay du han -> khong bao gio duoc gom, du dieu phoi in "con lech map" ba chuc lan.

Ca that 09/09 party 1 - `brub` bi dump ra 21011 luc 13:08:28 va dung do; bon acc kia ra/vao pho
ban solo lien tuc nen tap map chop tat giua {21011} va {21011, 62001}:

    13:08:16 gen 23: viec=lam - con lech map [21011, 62001] -> chua lap party, cho gom xong
    13:08:42 gen 25: viec=moi - cung map/kenh nhung DOI chua du        <- dong ho RESET
    13:08:52 gen 26: viec=lam - con lech map [21011, 62001]            <- dem lai tu dau
    13:09:22 gen 29: viec=moi - cung map/kenh                          <- RESET lan nua
    13:11:33 gen 33: viec=gom - party dang o 2 MAP khac nhau           <- ba phut sau

Ba phut cho mot viec dieu phoi DA BIET tu giay dau tien.
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

from bot import config


class _C:
    def __init__(self, map_id=None, channel=1, roster=0):
        self.current_map = map_id
        self.current_channel = channel
        self.running = True
        self.party_members = [b"x" * 8] * roster

    def digioi_minutes_live(self):
        return float(R.DIGIOI_LIMIT)      # het gio DG -> pha train, dung duong dang xet


class _Nen(unittest.TestCase):
    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._accounts = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "a1", u == "a1") for u in self.ACCS]
        self._jmc = R.joined_member_count
        R.joined_member_count = lambda pidx: len(self.ACCS) - 1
        self._clients = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self._pcfg = dict(getattr(config, "PARTY_CONFIG", {}))
        config.PARTY_CONFIG = {self.PARTY: {"mode": "train"}}

    def tearDown(self):
        R.party_accounts = self._accounts
        R.joined_member_count = self._jmc
        R.account_clients.clear(); R.account_clients.update(self._clients)
        R._party_state.pop(self.PARTY, None)
        config.PARTY_CONFIG = self._pcfg

    def _dat(self, **kw):
        for u, c in kw.items():
            R.account_clients[u] = c

    def _quyet(self, lech_tu=None):
        return R._dieu_phoi_quyet(self.PARTY, R._pstate(self.PARTY),
                                  R._acc_song(self.PARTY), lech_tu)


class TestLechMapAnHanNgan(_Nen):
    def test_lech_map_an_han_NGAN_hon_lech_kenh(self):
        self.assertLess(R.LECH_MAP_AN_HAN_SEC, R.KE_HOACH_LECH_MAP_SEC,
                        "khac map thi gom map - khong phai viec phai can nhac mot phut")

    def test_lech_map_qua_an_han_thi_RA_LENH_GOM(self):
        self._dat(a1=_C(21011), a2=_C(62001), a3=_C(62001))
        kh, ly_do, _ = self._quyet(lech_tu=time.time() - R.LECH_MAP_AN_HAN_SEC - 1)
        self.assertEqual(kh["viec"], R.VIEC_GOM, ly_do)

    def test_lech_map_THOANG_QUA_thi_chua_gom(self):
        """Acc dang teleport chuyen tiep - lech vai giay la binh thuong."""
        self._dat(a1=_C(21011), a2=_C(62001), a3=_C(62001))
        kh, _l, _ = self._quyet(lech_tu=time.time() - 1)
        self.assertNotEqual(kh["viec"], R.VIEC_GOM)

    def test_KHONG_phai_doi_du_han_cua_lech_kenh(self):
        """Cot loi: lech map ma bat cho het han cua lech kenh la sai loai han."""
        self._dat(a1=_C(21011), a2=_C(62001), a3=_C(62001))
        _tu = time.time() - (R.LECH_MAP_AN_HAN_SEC + R.KE_HOACH_LECH_MAP_SEC) / 2.0
        kh, ly_do, _ = self._quyet(lech_tu=_tu)
        self.assertEqual(kh["viec"], R.VIEC_GOM, ly_do)


class TestDongHoLechKhongBiRESET(_Nen):
    """Lech NGAT QUANG van la lech - mot nhip cung map khong xoa duoc tuoi cua no."""

    def test_mot_nhip_cung_map_KHONG_xoa_dong_ho(self):
        self._dat(a1=_C(21011), a2=_C(21011), a3=_C(21011))
        _kh, _l, lech_tu = self._quyet(lech_tu=time.time() - 100)
        self.assertIsNotNone(lech_tu, "reset ngay -> lech ngat quang khong bao gio dat han")

    def test_het_lech_DU_LAU_thi_moi_xoa(self):
        self._dat(a1=_C(21011), a2=_C(21011), a3=_C(21011))
        _kh, _l, lech_tu = self._quyet(lech_tu=time.time() - 100)
        R._pstate(self.PARTY)["het_lech_tu"] = time.time() - R.HET_LECH_CHAC_SEC - 1
        _kh, _l, lech_tu = self._quyet(lech_tu=lech_tu)
        self.assertIsNone(lech_tu)

    def test_lech_lai_thi_dong_ho_GIU_NGUYEN_tuoi(self):
        """Day dung la ca party 1: chop tat {21011} <-> {21011, 62001}. Lan lech thu hai phai
        THUA KE tuoi cua lan dau, khong dem lai tu dau."""
        _tu = time.time() - R.LECH_MAP_AN_HAN_SEC - 1
        self._dat(a1=_C(21011), a2=_C(21011), a3=_C(21011))
        _kh, _l, lech_tu = self._quyet(lech_tu=_tu)          # thoang cung map
        self._dat(a2=_C(62001))                              # roi lech lai ngay
        kh, ly_do, _ = self._quyet(lech_tu=lech_tu)
        self.assertEqual(kh["viec"], R.VIEC_GOM, ly_do)

    def test_party_LANH_thi_khong_ra_lenh_du_dong_ho_con_treo(self):
        """Dong ho giu qua nhieu la de khong mat tuoi - KHONG phai de ra lenh cho party dang lanh."""
        self._dat(a1=_C(21011), a2=_C(21011), a3=_C(21011))
        kh, _l, _ = self._quyet(lech_tu=time.time() - 100)
        self.assertNotIn(kh["viec"], (R.VIEC_GOM, R.VIEC_DONG_BO))


class TestViecRiengKhongDuocDE_RA_LECH_MAP(unittest.TestCase):
    """Pho ban solo `leave_party()` roi vao mot map rieng: no VUA pha doi VUA lam lech map - dung
    hai thu dieu phoi dang co gang sua. Dang gom ma vao day = tu tay pha viec cua chinh minh.

    LUOT DANG CHAY VAN CHAY NOT (user: "dang lam viec vat thi lam not chu") - cua chan nam o DAU
    moi luot, truoc `buy_dungeon_ticket()`, nen khong mat ve mat luot.
    """

    def setUp(self):
        import io
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.cli = fh.read()

    def test_moi_cho_goi_dungeon_deu_hoi_dieu_phoi(self):
        self.assertNotIn("c.do_daily_dungeon()", self.src,
                         "con mot cho goi tran -> acc do van vao pho ban giua luc party dang gom")
        self.assertGreater(self.src.count("c.do_daily_dungeon(cho_phep=_dieu_phoi_dang_ra_lenh)"), 0)

    def test_dungeon_chan_TRUOC_khi_mua_ve(self):
        i = self.cli.find("def do_daily_dungeon(")
        j = self.cli.find("while self.running and done_runs < runs_target:", i)
        self.assertGreater(j, i)
        k = self.cli.find("buy_dungeon_ticket()", j)
        self.assertGreater(k, j)
        self.assertIn("cho_phep()", self.cli[j:k],
                      "chan sau khi mua ve = mat ve")

    def test_luot_dang_chay_van_chay_NOT(self):
        """Cua chan o DAU vong lap, khong cat ngang `_run_one_dungeon`."""
        i = self.cli.find("def do_daily_dungeon(")
        j = self.cli.find("while self.running and done_runs < runs_target:", i)
        k = self.cli.find("_run_one_dungeon(", j)
        khoi = self.cli[j:k]
        self.assertIn("break", khoi)          # thoat o dau vong, truoc khi vao luot moi
        self.assertNotIn("return", khoi.split("cho_phep()")[-1].split("break")[0])

    def test_ke_hoach_GOM_la_du_de_hoan_viec_rieng(self):
        """Khong doi den luc co `kenh_dich`/`gom_dich` cu the moi hoan - ke hoach noi truoc."""
        i = self.src.find("def _dieu_phoi_dang_ra_lenh():")
        self.assertGreater(i, 0)
        khoi = self.src[i:i + 1400]
        self.assertIn("VIEC_GOM", khoi)
        self.assertIn("VIEC_DONG_BO", khoi)


if __name__ == "__main__":
    unittest.main()
