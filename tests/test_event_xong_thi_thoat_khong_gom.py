"""EVENT XONG -> di doi thuong roi THOAT. Dieu phoi khong duoc ra lenh gom/moi nua.

User 14/09: "p6 p7, danh xong 40NPC no ve Nghiep thanh lam gi the" -> "event thi danh xong out,
train deo gi o day".

`_ket_thuc` (bot/npc40.py) set `client._npc40_done = True` khi het gio / thua 2 tran / thua sach.
Tu do chi con MOT viec SOLO: toi NPC map 12003 doi qua roi thoat game. Nhung dieu phoi khong he
biet, van ra lenh gom party -> acc bi keo vao vong reform va KHONG BAO GIO quay lai duoc nhanh doc
co do.

CA THAT party 7, 14/09:
    21:12:36 [ttsau] 40NPC: thua sach (khong co prompt) -> THOAT LUON        <- `_npc40_done`
    21:18:59 [party 7] REFORM gen -> 6 - chung kenh roi ma doi khong du      <- dieu phoi gom
    21:19:09 [ttsau] (LEADER) reform: 4/4 member join lai -> KEO qua cong ra train map
    21:19:10 [ttsau] loi reform (bo qua): 'NoneType' object has no attribute 'get'
    21:20:12 [ttbay] PARTY: ... ROI doi -> roster con 3 -> 2 ...
Ca lu quay vong o Nghiep Thanh (12061) thay vi di doi thuong.

DOI CHIEU party 22 cung luc - khong bi dieu phoi chen vao thi lam DUNG:
    21:15:46 [gclmot] (LEADER) 40NPC xong -> di doi thuong + thoat game
    21:16:52 [gclmot] doi thuong 40NPC: da doi qua chien dau o NPC map 12003
    21:17:39 >>> PARTY 22 DA THOAT HET

Loi thu hai trong cung chuoi: `route2.get("steps", [])` khong duoc bao ve. Mode event thi
`TRAIN_ROUTES.get(sc)` = None -> NoneType, va loi bi `except Exception` nuot thanh mot dong
"loi reform (bo qua)" nen khong ai biet reform chet giua chung.
"""
from __future__ import annotations

from tests.party_controller_helpers import quyet_party

import io
import os
import sys
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class _C:
    def __init__(self, map_id=12061, ch=1, npc40_done=False):
        self.current_map = map_id
        self.current_channel = ch
        self.running = True
        self.party_members = []
        self._npc40_done = npc40_done

    def kenh_dang_chac(self):
        return True


class _Nen(unittest.TestCase):
    PARTY = 80

    def setUp(self):
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)
        self.st["n_members"] = 4
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "event"}}
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [("u%d" % i, "p", i == 0, i == 0) for i in range(5)]
        self._gt = R.get_account_task
        R.get_account_task = lambda u: {"phase": "event"}

    def tearDown(self):
        R.get_account_task = self._gt
        R.party_accounts = self._pa
        R.config.PARTY_CONFIG = self._pc
        R._party_state.pop(self.PARTY, None)

    def _song(self, done_idx=()):
        return [("u%d" % i, _C(npc40_done=(i in done_idx))) for i in range(5)]


class TestEventXongThiKhongGom(_Nen):
    def test_leader_bao_xong_thi_dieu_phoi_IM(self):
        kh, ly_do, _lt = quyet_party(R, self.PARTY, self.st, self._song({0}), None)
        self.assertEqual(kh["viec"], R.VIEC_LAM, ly_do)
        self.assertIn("DA XONG", ly_do)

    def test_go_claim_set_thi_dieu_phoi_IM(self):
        self.st["go_claim"].set()
        kh, ly_do, _lt = quyet_party(R, self.PARTY, self.st, self._song(), None)
        self.assertEqual(kh["viec"], R.VIEC_LAM, ly_do)
        self.assertIn("DA XONG", ly_do)

    def test_CHUA_xong_thi_van_dieu_phoi_binh_thuong(self):
        """Khong duoc im khi event con dang chay - luc do party van phai du."""
        kh, ly_do, _lt = quyet_party(R, self.PARTY, self.st, self._song(), None)
        self.assertNotIn("DA XONG", ly_do)


class TestKhongCanRouteTrainChoEvent(unittest.TestCase):
    """Event work is assigned directly even when there is no train route."""

    def test_chua_vao_event_thi_giao_vao_event(self):
        from bot import party_engine as PE
        accs = [PE.AnhAcc("leader", la_leader=True, map_id=12061, kenh=1),
                PE.AnhAcc("member", map_id=12061, kenh=1)]
        anh = PE.AnhParty(0, accs, can_bao_nhieu=1, pha=PE.PHA_EVENT, map_dich=None)
        self.assertEqual(PE.quyet_dinh(anh),
                         {"leader": PE.VIEC_VAO_EVENT, "member": PE.VIEC_VAO_EVENT})

    def test_event_xong_thi_doi_thuong_khong_di_train(self):
        from bot import party_engine as PE
        accs = [PE.AnhAcc("leader", la_leader=True, map_id=12061, kenh=1),
                PE.AnhAcc("member", map_id=12061, kenh=1)]
        anh = PE.AnhParty(0, accs, can_bao_nhieu=1, pha=PE.PHA_EVENT,
                          map_dich=None, event_xong=True)
        jobs = PE.quyet_dinh(anh)
        self.assertEqual(set(jobs.values()), {PE.VIEC_DOI_THUONG})



if __name__ == "__main__":
    unittest.main()
