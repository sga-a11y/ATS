"""DIEU PHOI phai TU GUI lenh doi kenh, khong ghi co roi cho acc di ngang qua diem nghe.

Ca that 09/09 party 3 (user: "sao dieu phoi vo dung vai lon" / "thong bao cai lon, viet 1 dong
rule the ma chi la thong bao a"):

    12:40:16 [party 3] CHOT kenh dich = 16 (kenh IT NGUOI NHAT ma du cho ca team)
    12:40:33 [nanam]   Boss the gioi: DA VAO TRAN -> danh CHO HET TRAN
    12:41:03 [party 3] kenh dich 16 qua 45s van chua gom xong ({2: 1, 8: 2, 10: 2}) -> chot lai
    12:41:49 ... 12:42:34 ... 12:49:30   (14 nhip, phan bo kenh KHONG NHUC NHICH mot li)

Suot 9 phut do khong co MOT dong `Doi kenh` nao cua ca nam acc: lenh chua he duoc gui di. Nguoi
gui la `_nghe_lenh_kenh()` trong `run_account`, chi chay khi acc di ngang qua mot trong chin diem
nghe - ma ca nam dang trong vong boss the gioi nam han trong `bot/client.py`.

Bang chung co che van dung, chi la khong duoc chay: 13:08:59 luc acc ranh, bon member doi kenh
xong trong MOT giay.

13 luat o `RULE_DIEU_PHOI.md` deu noi CHON kenh nao cho khon; khong luat nao bat phai GUI lenh.
Ghi co len client cung la bao cao - van la bat acc tu lam (L2).
"""
from __future__ import annotations

import io
import os
import sys
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class _State:
    """Client gia - chi cac truong duong doi kenh doc."""

    def __init__(self, in_battle=False):
        self.in_battle = in_battle


class _C:
    def __init__(self, kenh=2, running=True, in_battle=False, in_combat=False, grace=False):
        self.running = running
        self.current_channel = kenh
        self.state = _State(in_battle)
        self._in_combat = in_combat
        self._grace = grace
        self._label = "acc%s" % kenh
        self.da_gui = []          # cac kenh da duoc ra lenh doi sang
        self._chan_switch_result = None

    def in_combat(self):
        return self._in_combat

    def _in_battle_end_grace(self):
        return self._grace

    def switch_channel(self, ch, wait=None, retries=None, theo_lenh=False):
        self.da_gui.append(int(ch))
        self.current_channel = int(ch)
        self._chan_switch_result = 0
        return True


def _cho_xong(cs, han=3.0):
    """Lenh gui trong thread rieng -> cho no chay xong roi moi doi chieu."""
    het = time.time() + han
    while time.time() < het:
        if not any(getattr(c, "_dp_gui_kenh_dang_chay", False) for c in cs):
            return
        time.sleep(0.01)


class TestDieuPhoiTuGuiLenh(unittest.TestCase):
    def setUp(self):
        self.st = {"lock": threading.RLock(), "event_battle_active": False}

    def test_acc_lech_kenh_thi_DIEU_PHOI_GUI_lenh(self):
        a, b = _C(kenh=2), _C(kenh=10)
        song = [("u1", a), ("u2", b)]
        n = R._dieu_phoi_thi_hanh_kenh(0, self.st, song, 16)
        self.assertEqual(n, 2)
        _cho_xong([a, b])
        self.assertEqual(a.da_gui, [16])
        self.assertEqual(b.da_gui, [16])

    def test_acc_DANG_BAN_vong_dai_van_nhan_duoc_lenh(self):
        """Cot loi cua ca party 3: acc dang trong mot vong dai cua `client.py` khong he goi
        `_nghe_lenh_kenh`, nhung dieu phoi khong hoi acc nen van gui duoc."""
        bandai = _C(kenh=2)          # khong co ai goi `_nghe_lenh_kenh` cho no ca
        R._dieu_phoi_thi_hanh_kenh(0, self.st, [("u1", bandai)], 16)
        _cho_xong([bandai])
        self.assertEqual(bandai.da_gui, [16])

    def test_dang_o_dung_kenh_thi_KHONG_gui(self):
        c = _C(kenh=16)
        self.assertEqual(R._dieu_phoi_thi_hanh_kenh(0, self.st, [("u", c)], 16), 0)
        self.assertEqual(c.da_gui, [])

    def test_chua_chot_dich_thi_khong_gui_gi(self):
        c = _C(kenh=2)
        self.assertEqual(R._dieu_phoi_thi_hanh_kenh(0, self.st, [("u", c)], None), 0)
        self.assertEqual(c.da_gui, [])

    def test_KHONG_gui_chong_len_nhau(self):
        """Vong dieu phoi chay moi 2 giay; `switch_channel` cho ack toi vai giay."""
        c = _C(kenh=2)
        R._dieu_phoi_thi_hanh_kenh(0, self.st, [("u", c)], 16)
        _cho_xong([c])
        c.current_channel = 2                     # gia bo chua sang duoc
        self.assertEqual(R._dieu_phoi_thi_hanh_kenh(0, self.st, [("u", c)], 16), 0,
                         "gui lai ngay lap tuc -> chong goi len nhau, khong nhanh hon")

    def test_gui_LAI_duoc_sau_khi_qua_han(self):
        c = _C(kenh=2)
        R._dieu_phoi_thi_hanh_kenh(0, self.st, [("u", c)], 16)
        _cho_xong([c])
        c.current_channel = 2
        c._dp_gui_kenh_luc = time.time() - R.DIEU_PHOI_GUI_LAI_KENH_SEC - 1
        self.assertEqual(R._dieu_phoi_thi_hanh_kenh(0, self.st, [("u", c)], 16), 1,
                         "khong gui lai bao gio = acc truot mot lan la ket vinh vien")


class TestKhongGuiKhiNguyHIEM(unittest.TestCase):
    """Doi kenh giua tran/event -> `S:000-000` ma 47 `<戰鬥未結束事件先結束>` -> DUT KET NOI."""

    def setUp(self):
        self.st = {"lock": threading.RLock(), "event_battle_active": False}

    def _khong_gui(self, c, st=None):
        self.assertEqual(R._dieu_phoi_thi_hanh_kenh(0, st or self.st, [("u", c)], 16), 0)
        self.assertEqual(c.da_gui, [])

    def test_dang_trong_tran(self):
        self._khong_gui(_C(kenh=2, in_battle=True))

    def test_grace_ket_tran(self):
        self._khong_gui(_C(kenh=2, grace=True))

    def test_in_combat(self):
        self._khong_gui(_C(kenh=2, in_combat=True))

    def test_party_dang_danh_event(self):
        st = {"lock": threading.RLock(), "event_battle_active": True}
        self._khong_gui(_C(kenh=2), st)

    def test_acc_da_tat(self):
        self._khong_gui(_C(kenh=2, running=False))


class TestNoiVaoVongDieuPhoi(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_vong_dieu_phoi_co_goi_thi_hanh(self):
        """Chot xong ma khong goi thi hanh = quay lai dung cai bang thong bao."""
        i = self.src.find("_dieu_phoi_chot_kenh(pidx, st, song")
        self.assertGreater(i, 0)
        self.assertIn("_dieu_phoi_thi_hanh_kenh(", self.src[i:i + 400])

    def test_dung_CHUNG_ham_kiem_an_toan(self):
        """Hai ban sao dieu kien an toan thi som muon lech nhau."""
        i = self.src.find("def _nghe_lenh_kenh():")
        j = self.src.find("\n    has_leader =", i)
        self.assertGreater(j, i)
        khoi = self.src[i:j]
        self.assertIn("_kenh_doi_duoc_ngay(", khoi)


class TestLenhDieuPhoiThiHanhTuyetDoi(unittest.TestCase):
    """User 09/09: "lenh cua dieu phoi phai thi hanh tuyet doi".

    Viec rieng cua acc (boss the gioi) la vong nhieu tran lien tiep nam han trong `client.py`.
    Dang gom party ma lao vao do = party lac nhau ca tieng de doi lay vai luot boss.
    """

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.cli = fh.read()

    def test_boss_the_gioi_KHONG_con_hoan_theo_lenh(self):
        """User chot 14/09 (huong 3): bo cua hoan cho boss the gioi / PB don.

        Cua hoan cu dat dung vao THOI DIEM LUON DANG GOM - hai viec nay chi chay o login chores,
        ma luc moi login thi 250 acc dung o 250 cho khac nhau -> dieu phoi ra lenh gom -> HOAN ->
        va vi chi chay MOT LAN, mat luot CA NGAY. Restart bao nhieu lan cung the.

        Do tren log 14/09, sau restart 251 acc luc 22:31:46:
            PB don : 109 acc bi HOAN |  2 acc danh duoc luot
            WB     : 162 acc bi HOAN | 51 acc vao danh
        Ca ngay: 2739 lan `Boss the gioi: HOAN`, 3224 lan `Dungeon: HOAN`; o 1 (PB don) chi
        14/152 acc sang duoc -> 96% acc khong xong nhiem vu ngay.

        An toan hon truoc vi hai viec nay bao pha `PHASE_LOGIN_CHORE`: dieu phoi KHONG tinh acc
        dang viec vat vao phep do lech map/kenh, va loi moi party duoc GIU lai den khi xong viec.
        """
        i = self.src.find("def _maybe_auto_world_boss(reason: str):")
        self.assertGreater(i, 0)
        khoi = self.src[i:i + 2000]
        self.assertNotIn("_cam = _dieu_phoi_dang_ra_lenh()", khoi,
                         "cua hoan song lai -> boss the gioi lai mat luot ca ngay")
        self.assertIn("c.do_world_boss_all()", khoi)

    def test_PB_don_KHONG_con_hoan_theo_lenh(self):
        self.assertNotIn("c.do_daily_dungeon(cho_phep=", self.src,
                         "cua hoan song lai -> PB don lai mat luot ca ngay")
        self.assertIn("c.do_daily_dungeon()", self.src)

    def test_dieu_phoi_KHONG_QUAY_RAY_acc_dang_lam(self):
        """User 14/09: "khi dang danh PB don va daily quest thi dieu phoi tam thoi ko quay ray"."""
        i = self.src.find("ACC DANG LAM VIEC VAT -> KHONG QUAY RAY")
        self.assertGreater(i, 0, "dieu phoi van gui lenh doi kenh cho acc dang danh PB don")
        khoi = self.src[i:i + 1200]
        self.assertIn("_ban = set(_ai_dang_lam_viec_le(song))", khoi)
        self.assertIn("if _u in _ban:", khoi)

    def test_client_co_cua_de_dung_giua_chung(self):
        i = self.cli.find("def do_world_boss_all(")
        self.assertGreater(i, 0)
        self.assertIn("cho_phep", self.cli[i:i + 200])
        j = self.cli.find("while self.running and loops < max_loops:", i)
        self.assertGreater(j, i)
        self.assertIn("cho_phep()", self.cli[j:j + 400],
                      "phai kiem MOI vong, khong phai chi mot lan luc vao")

    def test_van_danh_dau_wb_done_khi_hoan(self):
        """Leader cho co `wb_done` truoc khi lap pho ban - hoan ma khong danh dau thi party treo."""
        i = self.src.find("def _maybe_auto_world_boss(reason: str):")
        j = self.src.find("def _ket_thuc_pha_dg():", i)
        khoi = self.src[i:j]
        self.assertIn("finally:", khoi)
        self.assertIn('st.setdefault("wb_done", set()).add(username)', khoi)


if __name__ == "__main__":
    unittest.main()
