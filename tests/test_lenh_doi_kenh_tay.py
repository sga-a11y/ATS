"""LENH DOI KENH TAY khi party DANG TRAIN - dung thu tu user chot 30/08:

    lead chay ra safe -> GIAI TAN party -> ca lu chuyen kenh yeu cau
    -> chuyen xong thi CHECK LAI da o safe chua -> o safe roi thi LAP LAI party train o kenh do

Su co 30/08 21:45:44-46 (party 6): bam doi kenh 4 khi ca party dang train ->
    21:45:44 leader giai tan party o (820,1000)
    21:45:46 [4 member] smart path map 23821: (2150, 1810) -> (940,1100)
    21:45:46 [4 member] SERVER NGAT KET NOI: di chuyen QUA XA (ma 14)   <- CA 4, cung mot giay
Trong party member TU DI THEO leader nen vi tri THAT cua no la cho leader dung; `self.pos` cua bot
van la so dead-reckoning tu lan cuoi TU no ra lenh di. Party tan -> lenh move dau tien tinh tu pos
cu = server thay nhay ca nghin don vi -> ma 14 -> dut ket noi.

`S:013-004 <玩家離開隊伍> +玩家ID(8) +坐標X(2) +坐標Y(2)` MANG SAN toa do that - bot vut di
(`PARTY: goi 0x0d sub=4 CHUA XU LY: 040013e8e44c838d0300 3403 e803` = dung (820,1000)).
"""
from __future__ import annotations

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402

TOI = b"\x11" * 8
AI_DO = b"\x22" * 8


def _goi_roi_doi(entity, x, y):
    body = b"\x0d" + b"\x04\x00" + entity + x.to_bytes(2, "little") + y.to_bytes(2, "little")
    return b"\xc0\x91" + (len(body) + 6).to_bytes(2, "little") + b"\x00\x00" + body


def _bot():
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.self_entity = TOI
    c.party_idx = 0
    c.party_leader = None
    c.party_members = []
    c.team_of = {}
    c.team_of_at = 0.0
    c.pos = (2150, 1810)
    c.current_map = 23821
    c._position_generation = 0
    c._pos_valid_for_map = None
    c.auto_accept_party = False
    c.state = type("S", (), {"my_atype": 0, "self_slot": 0})()
    return c


class TestResyncPosKhiRoiDoi(unittest.TestCase):
    def test_lay_toa_do_that_tu_goi_roi_doi(self):
        c = _bot()
        c._on_party(_goi_roi_doi(TOI, 820, 1000))
        self.assertEqual(c.pos, (820, 1000),
                         "khong lay -> lenh move dau tien nhay 1300 don vi -> ma 14 -> dut ket noi")

    def test_bao_cho_navigate_biet_toa_do_MOI(self):
        c = _bot()
        gen = c._position_generation
        c._on_party(_goi_roi_doi(TOI, 820, 1000))
        self.assertGreater(c._position_generation, gen)
        self.assertEqual(c._pos_valid_for_map, 23821)

    def test_KHONG_lay_toa_do_cua_NGUOI_KHAC(self):
        c = _bot()
        c._on_party(_goi_roi_doi(AI_DO, 820, 1000))
        self.assertEqual(c.pos, (2150, 1810))

    def test_toa_do_rac_thi_bo_qua(self):
        c = _bot()
        c._on_party(_goi_roi_doi(TOI, 0, 0))
        self.assertEqual(c.pos, (2150, 1810))


class TestKhongCoCachHoiViTri(unittest.TestCase):
    """DA DO BANG SO tren log 30/08: 184 goi `0x06` DA GUI, 0 goi `S:006-001` nhan ve mang entity
    cua chinh minh (45 goi nhan ve deu la cua NGUOI KHAC).

    Client that cung vay: `MoveController.SendMove` GUI toa do len (`C:006-001`), con
    `Role.player.position` la bien LOCAL. `protocolTable[6][1]` chi de ve NGUOI KHAC di.
    => KHONG co cach hoi vi tri hien tai. Dung di tim lai.
    """

    def test_KHONG_ap_goi_0x06_cho_chinh_minh(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertNotIn("VI TRI THAT do SERVER cap", s)
        self.assertNotIn('pkt[9:17] == self.self_entity', s,
                         "server khong echo move cua chinh minh - code do khong bao gio chay")

    def test_GHI_RO_cac_nguon_server_sua_pos(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("KHONG co cach hoi vi tri hien tai")
        self.assertGreater(i, 0, "phai ghi ro de lan sau khong di tim lai")
        khoi = s[i:i + 900]
        for nguon in ("S:007-000", "S:012-000", "S:013-004", "0x03"):
            self.assertIn(nguon, khoi, "thieu nguon: %s" % nguon)


class TestThuTuLenhDoiKenh(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find('if kind == "channel":')
        self.assertGreater(i, 0)
        self.than = re.sub(r"#.*", "", s[i:i + 8600])
        self.src = s

    def test_LEADER_giai_tan_party_TRUOC_khi_ca_lu_chuyen(self):
        i_tan = self.than.find("c.leave_party(); reset_party_joined(pidx)")
        i_doi = self.than.find("ok = c.switch_channel(ch)")
        self.assertGreater(i_tan, 0, "khong giai tan -> member con tu di theo leader")
        self.assertLess(i_tan, i_doi)
        self.assertIn("if is_leader:", self.than, "chi LEADER moi giai tan")

    def test_MEMBER_phai_CHO_leader_xong_moi_duoc_di(self):
        """Log 30/08 22:15:19-22: lenh luc 22:15:19, member bat dau di 22:15:21 va RUNG NGAY
        (ma 14), con leader mai 22:15:24 moi giai tan party. Di truoc = chet."""
        self.assertIn('st["cmd_leader_xong"].wait(', self.than,
                      "member khong cho -> di khi con dang follow leader -> ma 14")
        i_cho = self.than.find('st["cmd_leader_xong"].wait(')
        i_di = self.than.find("_ra_safe_truoc_khi_doi_kenh(")
        self.assertLess(i_cho, i_di, "cho SAU khi da di thi vo nghia")
        self.assertIn("elif has_leader:", self.than, "party khong co bot-leader thi khong cho ai")

    def test_LEADER_tha_member_di_SAU_khi_giai_tan(self):
        i_tan = self.than.find("c.leave_party(); reset_party_joined(pidx)")
        i_tha = self.than.find('st["cmd_leader_xong"].set()')
        self.assertGreater(i_tha, 0, "khong tha thi member cho het 90s roi tu di")
        self.assertLess(i_tan, i_tha)

    def test_cua_cho_leader_chot_theo_SO_LENH_khong_theo_Event(self):
        """Event dung chung con SOT tu lenh truoc: member doc co TRUOC khi leader kip clear ->
        qua cua ngay, di truoc leader.

        Log 31/08 party 8: lenh doi kenh 10:49:23; 10:49:25 lubbon in "CHO leader ra safe..." roi
        di luon (10:49:26 `Doi kenh OK -> 1`), leader lbumot 10:49:26 moi nhan lenh, 10:49:50 moi
        giai tan. Server tu choi ma 3 (DANG TO DOI) -> lubbon TU roi party giua bai quai.
        """
        self.assertIn('"cmd_leader_xong_gen": None,', self.src, "khong co moc theo so lenh")
        i = self.src.find("manual: CHO leader ra safe + giai tan party truoc khi")
        self.assertGreater(i, 0)
        khoi = re.sub(r"#.*", "", self.src[i:i + 1000])
        self.assertIn('while st.get("cmd_leader_xong_gen") != cmd_gen_handled:', khoi,
                      "van cho bang Event tran -> con dua nhau voi leader")
        self.assertNotIn('st["cmd_leader_xong"].wait(90)', khoi)

    def test_leader_DAT_moc_dung_luc_giai_tan_xong(self):
        i = self.src.find('st["cmd_leader_xong"].set()')
        self.assertGreater(i, 0)
        truoc = self.src[max(0, i - 700):i]
        self.assertIn('st["cmd_leader_xong_gen"] = cmd_gen_handled', truoc,
                      "set Event ma khong ghi so lenh -> member cho mai")
        self.assertIn("c.leave_party()", truoc, "tha member di TRUOC khi giai tan")

    def test_leader_XOA_moc_o_dau_lenh_moi(self):
        i = self.src.find('st["cmd_leader_xong"].clear()')
        self.assertGreater(i, 0)
        self.assertIn('st["cmd_leader_xong_gen"] = None', self.src[i:i + 200],
                      "khong xoa moc cu -> lenh sau member qua cua ngay")

    def test_GHIM_kenh_user_chon_picker_khong_duoc_tu_doi(self):
        """Doi kenh xong, pha sync kenh chay tiep va TU CHON "kenh it nguoi nhat" -> keo ca party
        sang kenh khac, phu dinh lenh tay.

        Log 31/08 (party 16): user chon kenh 1, 09:57:24 `Doi kenh OK -> 1`, roi 09:58:22
        `Kenh it nguoi MA DU CHO ca party (5): kenh 2 (15/20) -> chuyen sang` -> ca lu ve kenh 2.
        """
        i = self.src.find('if kind == "channel":')
        self.assertGreater(i, 0)
        self.assertIn('st["kenh_ghim"] = int(ch) if ch else None', self.src[i:i + 900],
                      "lenh tay khong ghim kenh -> picker tu doi lai")

        j = self.src.find("r = c.pick_best_channel(")
        self.assertGreater(j, 0)
        khoi = self.src[max(0, j - 1200):j]
        self.assertIn('_ghim = st.get("kenh_ghim")', khoi, "picker khong doc kenh ghim")
        self.assertIn("if _ghim:", khoi)
        self.assertIn("c.switch_channel(int(_ghim))", khoi,
                      "co ghim thi phai dung dung kenh do, khong goi pick_best_channel")

    def test_kenh_ghim_HONG_thi_BO_ghim(self):
        """Ghim ma kenh do hong (ca party cung so ma khong thay nhau) thi ghim mai = ket cung."""
        j = self.src.find("r = c.pick_best_channel(")
        khoi = self.src[max(0, j - 1200):j]
        self.assertIn("int(_ghim) in _tru", khoi, "khong kiem kenh ghim co bi danh dau hong")
        self.assertIn('st["kenh_ghim"] = None', khoi, "kenh ghim hong ma khong bo ghim")

    def test_KHONG_giai_tan_o_doan_CHUNG_truoc_khoi_doi_kenh(self):
        """Doan chung cua `_do_manual_cmd` giai tan party NGAY khi vua nhan lenh - truoc ca khi ra
        safe - nen thu tu rieng cua lenh doi kenh thanh vo nghia.

        Log 31/08 09:56:12 (party 19): `-> LENH THU CONG ('channel', 1)` roi NGAY dong sau la
        `Roi/giai tan party cu`, mai 09:56:13 moi toi khoi doi kenh va bao "VAN dang trong tran".
        """
        i = self.src.find("def _do_manual_cmd(cmd):")
        j = self.src.find('if kind == "channel":', i)
        self.assertTrue(0 < i < j)
        chung = re.sub(r"#.*", "", self.src[i:j])
        i_tan = chung.find("c.leave_party(); reset_party_joined(pidx)")
        self.assertGreater(i_tan, 0, "mat doan huy party cho lenh route/town")
        self.assertIn('kind != "channel" and (is_leader', chung,
                      "lenh doi kenh van bi giai tan o doan chung")
        self.assertIn('if kind != "channel":\n                c.flee_mode = True', chung,
                      "lenh doi kenh van bi bat bo chay o doan chung (party con DU)")

    def test_XOA_co_truoc_moi_lenh(self):
        """Khong xoa thi lenh sau member di luon theo co cua lenh truoc."""
        self.assertIn('st["cmd_leader_xong"].clear()', self.than)

    def test_CHUA_ra_safe_thi_KHONG_doi_kenh(self):
        i = self.than.find('if not _ra_safe_truoc_khi_doi_kenh("lenh doi kenh tay"):')
        self.assertGreater(i, 0, "van doi kenh du chua toi safe")
        self.assertIn("continue", self.than[i:i + 200])
        self.assertLess(i, self.than.find("ok = c.switch_channel(ch)"))

    def test_DOI_XONG_phai_CHECK_LAI_da_o_safe_chua(self):
        i = self.than.find("ok = c.switch_channel(ch)")
        khoi = self.than[i:i + 900]
        self.assertIn('_ra_safe_truoc_khi_doi_kenh("sau khi doi kenh', khoi,
                      "doi kenh giu nguyen toa do; kenh moi cho do co the day quai")

    def test_DANH_XONG_TRAN_roi_moi_di(self):
        """User chot 30/08: "phai danh xong tran roi moi di chuyen den safe chu"."""
        self.assertIn("c._wait_combat_clear(idle=2.0, cap=120.0)", self.than)

    def test_CHUA_giai_tan_party_thi_KHONG_BO_CHAY(self):
        """User chot 30/08: "ko can bo chay, da giai tan pt dau ma phai bo chay" - du party thi
        viec gi phai chay, dinh quai cu danh cho xong."""
        self.assertNotIn("c.flee_mode = True", self.than,
                         "party con du ma van bat bo chay")
        i = self.src.find("def _ra_safe_truoc_khi_doi_kenh(")
        than = re.sub(r"#.*", "", self.src[i:self.src.find("\n        def do_channel_sync", i)])
        self.assertIn("bo_chay=not _con_party", than)
        self.assertIn('_con_party = bool(getattr(c, "party_members", None))', than)

    def test_ham_ra_rally_nhan_co_bo_chay(self):
        i = self.src.find("def _ra_rally_gom_lai(")
        than = re.sub(r"#.*", "", self.src[i:self.src.find("\n        def _acc_da", i)])
        self.assertIn("def _ra_rally_gom_lai(ly_do=\"\", bo_chay=True):", than)
        self.assertIn("if bo_chay:", than, "van bat flee vo dieu kien")
        self.assertIn("flee=bo_chay", than, "navigate_to van flee vo dieu kien")

    def test_cho_MOC_KET_TRAN_THAT_chu_khong_chi_idle(self):
        """`in_combat()` co duong suy luan theo idle/SAFETY - ra khoi no khong co nghia tran da
        xong that. Moc that la `0x14 sub0700` -> `_genuine_end_seen`."""
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def _wait_combat_clear(")
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn("_genuine_end_seen", than)
        self.assertIn("WAIT_END_THAT_SEC", than)
        # Chot cho nay TUNG bi khoa sau `_team_dungeon_until` -> duong train thuong khong duoc
        # bao ve. Gio phai ap dung cho MOI caller.
        i_cho = than.find("self._genuine_end_seen < time.time() - 2.0")
        self.assertGreater(i_cho, 0)
        self.assertNotIn("_team_dungeon_until", than[max(0, i_cho - 200):i_cho],
                         "van khoa chot cho sau dieu kien pho ban to doi")

    def test_ra_safe_phai_XAC_NHAN_da_toi(self):
        """`navigate_to` tran khong xac nhan gi - phai di qua `_ra_rally_gom_lai` (doc lai toa do,
        thu lai 3 lan) va TRA KET QUA."""
        i = self.src.find("def _ra_safe_truoc_khi_doi_kenh(")
        than = re.sub(r"#.*", "", self.src[i:self.src.find("\n        def do_channel_sync", i)])
        self.assertIn("_ra_rally_gom_lai(", than)
        self.assertNotIn("c.navigate_to(", than, "navigate_to tran = khong biet da toi hay chua")
        self.assertIn("return _ok", than)


if __name__ == "__main__":
    unittest.main()
