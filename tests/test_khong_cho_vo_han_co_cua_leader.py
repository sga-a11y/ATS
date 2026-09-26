"""MEMBER KHONG CHO, KHONG BAO CAO, KHONG TU DI DAU. Dieu phoi quyet het (L1/L2).

User 10/09: "da bao dieu phoi quyet het, acc deo cho deo bao cao gi het" -> "rule dat ca tuan roi
ma m van code ngu vay".

BA DOI THIET KE O CUNG MOT CHO, hai lan dau deu sai:

  1. (cu)      `while not st["route_party_ready"].is_set():`  - CHO VO HAN co cua leader.
     Party 50, 10/09: leader qua cong mot minh roi vao vong reform moi -> `clear()` co; ba member
     nam cho 6 phut, khong ca dong keepalive. py-spy chi dung dong cho do. Dieu phoi luc ay BIET
     "party dang o 2 MAP khac nhau [18000, 18021]" va ra lenh gom - khong ai nghe duoc.

  2. (sang 10/09, TOI SUA - VAN SAI) `_cho_leader_keo(...)` co HAN CUNG 120s.
     Bo duoc cho-vo-han, nhung do sai thu: mot chuyen route qua nhieu cong dai hon 2 phut la binh
     thuong. Party 1, 22:50 cung ngay:
         22:50:40 [xGAx]   qua cong idx=1 -> map 21521       <- leader VAN DANG KEO
         22:50:52 [chihao] THOI CHO leader keo (route_done) sau 120s
         22:50:57 [chihao] pre-route: tele trung gian ve thanh 12001 truoc
         22:50:57 [chihao] Teleport: dang o to doi -> ROI DOI truoc
         22:51:10 [party 1] viec=gom - party dang o 3 MAP khac nhau   <- HAU QUA, khong phai nguyen nhan
     Bon member het han giua chuyen di, chay tiep flow "di train", phai ROI DOI de teleport ->
     party tan giua duong.

  3. (dung) MEMBER KHONG CHO GI CA. Trong party, member bi leader keo theo tu dong - co che cua
     chinh client (`Logic/Team.lua` AddMember -> `Teleport(leader.position)`). Viec duy nhat member
     phai lam la DUNG TU Y LAM VIEC KHAC. Leader hong thi DIEU PHOI thay (no doc map ca party moi
     2 giay) va ra lenh - mot cho quyet.

Bai hoc: them mot vong cho la them mot cho acc TU QUYET. Han dai hay ngan khong phai van de - van
de la co vong cho.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _ma(s):
    """Bo docstring + comment - chi xet MA CHAY."""
    s = re.sub(r'"""[\s\S]*?"""', "", s)
    return re.sub(r"#.*", "", s)




class TestKhongConBarrierChoVoHan(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_moi_barrier_deu_co_LOI_THOAT(self):
        """Barrier cho co cua leader phai co it nhat MOT loi thoat khong phu thuoc leader:
        nghe duoc lenh dieu phoi, hoac thoat khi leader tat.
        """
        ma = _ma(self.src)
        for m in re.finditer(r'while not st\[\s*"([a-z_]+)"\s*\]\.is_set\(\):', ma):
            ten = m.group(1)
            than = ma[m.end():m.end() + 2000]
            co_loi_thoat = ("_nghe_lenh_kenh()" in than or "khong con chay" in than)
            self.assertTrue(co_loi_thoat,
                            "barrier `%s` cho vo han ma khong co loi thoat nao" % ten)

    def test_barrier_moi_loi_thoat_khi_leader_tat(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        anh = snapshot([account(song=False), account("b")], thieu_acc_song=True)
        result = E.quyet_dinh(anh)
        self.assertNotEqual(result.get("b"), E.VIEC_TRAIN)
        self.assertNotIn('while not st["invited"].is_set():', inspect.getsource(R.run_account))




if __name__ == "__main__":
    unittest.main()
