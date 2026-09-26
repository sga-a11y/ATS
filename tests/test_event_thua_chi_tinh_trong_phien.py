"""Quyet dinh "thua 2 tran -> thoat" CHI co gia tri trong lan login do.

User chot 02/09: "may pt log vao xong out luon, m cache so tran thua lai a? t chi muon 2 lan thua
thi out o lan login do thoi, login lai thi danh lai cho den khi thua 2 tran lien tiep".

Hai co song trong `_party_state[pidx]` (state theo TIEN TRINH, khong theo lan login):
  - `go_claim`      : truoc day KHONG duoc xoa o BAT KY dau -> set mot lan la moi acc login sau do
                      deu doc thay -> "40NPC xong -> di doi thuong + thoat" ngay khi vua vao game.
  - `event_battle_done`: co xoa nhung chi o nhanh reconnect VA con gac sau `event_battle_active`,
                      ma `_on_npc40_loss` da ha co do xuong False truoc -> thuc te khong bao gio xoa.

`consec_loss` thi von da dung: no la bien CUC BO trong `npc40.run_loop`, chet theo thread.
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rpd():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _npc40():
    with io.open(os.path.join(ROOT, "bot", "npc40.py"), encoding="utf-8") as fh:
        return fh.read()


class TestSoTranThuaKhongBiCache(unittest.TestCase):
    def test_consec_loss_la_bien_CUC_BO(self):
        """Dem so tran thua phai chet theo thread, khong duoc treo len client/party state."""
        src = _npc40()
        self.assertIn("    consec_loss = 0", src)
        self.assertNotIn("_consec_loss", src, "dem so tran thua bi luu ra ngoai -> song qua login")
        self.assertNotIn("client.consec_loss", src)

    def test_khong_ghi_so_tran_thua_ra_file(self):
        self.assertNotIn("consec_loss", _rpd(),
                         "coordinator khong duoc giu so tran thua giua cac lan login")




class TestStartPartyCungXoa(unittest.TestCase):
    def test_hai_co_nam_trong_danh_sach_reset_phien_moi(self):
        src = _rpd()
        i = src.find('for k in ("leader_ok", "leader_bad", "leader_gone"')
        self.assertGreater(i, 0)
        khoi = src[i:src.find("st[k].clear()", i)]
        self.assertIn('"go_claim"', khoi)
        self.assertIn('"event_battle_done"', khoi)


class TestVanThoatDuocKhiThuaThat(unittest.TestCase):
    """Xoa co khong duoc lam hong duong thoat binh thuong."""

    def test_van_con_duong_set_go_claim(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot

        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R, "_event_cua_party", return_value={"party_battle": {"kind": "npc_repeat"}}):
            R._pstate(0)["go_claim"].set()
            self.assertTrue(R._event_xong_engine_moi(0))

    def test_thoat_co_y_thi_KHONG_relogin(self):
        """Thoat vi thua 2 tran khong duoc tinh la 'rot' -> khong duoc tu login lai roi danh tiep."""
        src = _rpd()
        i = src.find("reconnectable = (not _stopped()")
        khoi = re.sub(r"#.*", "", src[i:i + 420])
        for dk in ("_forced_reconnect", "_login_failed", "_unexpected_error", "server_closed"):
            self.assertIn(dk, khoi)
        self.assertNotIn("_npc40_done", khoi)


if __name__ == "__main__":
    unittest.main()
