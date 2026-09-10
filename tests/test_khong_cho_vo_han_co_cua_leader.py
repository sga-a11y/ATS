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


class TestMemberKhongCho(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        i = self.src.find("def _do_reform(to_spot=True):")
        self.assertGreater(i, 0)
        j = self.src.find("\n        def ", i + 10)
        self.than = self.src[i:j if j > i else len(self.src)]

    def test_KHONG_con_ham_cho_leader_keo(self):
        """Ham do la mot cho acc tu quyet - bo han, khong phai chinh han cho dai hon."""
        self.assertNotIn("_cho_leader_keo", self.src)
        self.assertNotIn("CHO_LEADER_KEO_SEC", self.src)

    def test_nhanh_member_KHONG_cho_co_nao(self):
        i = self.than.find("MEMBER KHONG CHO, KHONG BAO CAO")
        self.assertGreater(i, 0, "mat nhanh member trong _do_reform")
        khoi = _ma(self.than[i:i + 2500])
        for _co in ("route_party_ready", "route_done"):
            self.assertNotIn(_co, khoi, "member van doc co cua leader")
        self.assertNotIn("while", khoi, "member van co vong cho")
        self.assertNotIn("time.sleep", khoi, "member van ngoi doi")

    def test_nhanh_member_RA_LUON(self):
        """Ra khoi `_do_reform` = khong tu ve thanh, khong tu di route."""
        i = self.than.find("MEMBER KHONG CHO, KHONG BAO CAO")
        khoi = _ma(self.than[i:i + 2500])
        self.assertIn("return", khoi)


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
        i = self.src.find('while not st["invited"].is_set():')
        self.assertGreater(i, 0)
        self.assertIn("LEADER khong con chay", self.src[i:i + 1500])


class TestPhiaThiHanhDocLenhDieuPhoi(unittest.TestCase):
    """Thay cho vong cho: moi viec cap party deu bat nguon tu LENH cua dieu phoi."""

    def setUp(self):
        self.src = _src()

    def test_moi_party_THOI_khi_dieu_phoi_bao_GOM(self):
        """Chi `VIEC_GOM` moi la lenh doi huong.

        `VIEC_LAM` KHONG phai "cam moi" - no chi noi "khong co viec cap party phai lam", ma party
        chua du thi van phai moi. Toi tung xet `viec != VIEC_MOI` o day (10/09) va no giet party 1
        ngay trong dem: ke hoach dao dong moi 2 giay (`lam` -> `moi` -> `lam` -> `gom`), leader vao
        vong moi luc dang `lam` la thoi ngay -> khong bao gio moi duoc; bon member dung o thanh
        21011 con leader di route mot minh.
        """
        i = self.src.find("def _moi_theo_dieu_phoi(")
        self.assertGreater(i, 0)
        j = self.src.find("\n        def ", i + 10)
        than = self.src[i:j]
        self.assertIn('_kh.get("viec") == VIEC_GOM', than)
        self.assertNotIn('_kh.get("viec") != VIEC_MOI', than,
                         "dieu kien nay chan oan: ke hoach dao dong nen leader khong kip moi")

    def test_dieu_phoi_biet_mode_nao_khong_can_doi(self):
        self.assertIn("def _mode_can_lap_doi(", self.src)
        i = self.src.find('st["n_members"] = ')
        self.assertIn("_mode_can_lap_doi(pidx)", self.src[i:i + 300])


if __name__ == "__main__":
    unittest.main()
