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
    def _khoi_picker(self):
        """Khoi `if/elif/else` quyet dinh picker lay kenh nao.

        Neo theo NHANH LENH chu khong theo so ky tu truoc `pick_best_channel`: cua so co dinh
        truot ngay khi them mot nhanh (08/09: them nhanh "dieu phoi da chot -> theo" thi hai dong
        `_ghim` bi day ra khoi cua so 1200 ky tu, test do trong khi hanh vi khong doi).
        """
        i = self.src.find('_tru = set(st.get("kenh_hong_set")')
        if i < 0:
            i = self.src.find('_ghim = st.get("kenh_ghim")')
        self.assertGreater(i, 0, "khong tim thay dau khoi chon kenh cua picker")
        j = self.src.find("r = c.pick_best_channel(", i)
        self.assertGreater(j, i)
        return self.src[i:j]

    def setUp(self):
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        # 21/09: khoi nay DA TACH khoi `run_account` thanh ham module-level
        # `doi_kenh_theo_lenh_tay` de ENGINE MOI dung chung (truoc do engine moi khong co duong
        # nao doi kenh -> nut doi kenh chet khi moi party chuyen sang engine moi).
        # Neo theo TEN HAM, khong theo `if kind == "channel":` (chuoi do con o ca hai engine).
        i = s.find("def doi_kenh_theo_lenh_tay(")
        self.assertGreater(i, 0, "mat ham chung `doi_kenh_theo_lenh_tay`")
        self.than = re.sub(r"#.*", "", s[i:s.find("\ndef ", i + 10)])
        self.src = s

    def test_LEADER_giai_tan_party_TRUOC_khi_ca_lu_chuyen(self):
        i_tan = self.than.find("c.leave_party(); reset_party_joined(pidx)")
        i_doi = self.than.find("ok = c.switch_channel(ch,")
        self.assertGreater(i_tan, 0, "khong giai tan -> member con tu di theo leader")
        self.assertLess(i_tan, i_doi)
        self.assertIn("if is_leader:", self.than, "chi LEADER moi giai tan")

    def test_MEMBER_phai_CHO_leader_xong_moi_duoc_di(self):
        """Log 30/08 22:15:19-22: lenh luc 22:15:19, member bat dau di 22:15:21 va RUNG NGAY
        (ma 14), con leader mai 22:15:24 moi giai tan party. Di truoc = chet."""
        self.assertIn('st["cmd_leader_xong"].wait(', self.than,
                      "member khong cho -> di khi con dang follow leader -> ma 14")
        i_cho = self.than.find('st["cmd_leader_xong"].wait(')
        i_di = self.than.find("_safe(\"lenh doi kenh tay\")")
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
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        from tests.test_chon_kenh_it_nguoi_du_cho import _C
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R, "_mode_can_lap_doi", return_value=True), \
                mock.patch.object(R, "_party_40npc_ngoai_gio", return_value=False):
            st = R._pstate(0)
            st["kenh_ghim"] = 3
            c = _C(1, {2: (0, 20), 3: (20, 20)})
            c._chan_switch_target = 3
            c._chan_switch_result = 4
            self.assertEqual(R._engine_chot_kenh(0, st, [("a", c)]), 3)
            self.assertEqual(st["kenh_ghim"], 3)

    def test_KHONG_tu_bo_ghim_vi_cho_la_kenh_HONG(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        from tests.test_chon_kenh_it_nguoi_du_cho import _C
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R, "_mode_can_lap_doi", return_value=True), \
                mock.patch.object(R, "_party_40npc_ngoai_gio", return_value=False):
            st = R._pstate(0)
            st["kenh_ghim"] = 3
            c = _C(1, {2: (0, 20), 3: (20, 20)})
            c._chan_switch_target = 3
            c._chan_switch_result = 4
            self.assertEqual(R._engine_chot_kenh(0, st, [("a", c)]), 3)
            self.assertEqual(st["kenh_ghim"], 3)

    def test_KHONG_giai_tan_o_doan_CHUNG_truoc_khoi_doi_kenh(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        source = inspect.getsource(R._lenh_tay_engine_moi)
        branch = source.index('if kind == "channel":')
        self.assertNotIn("c.leave_party()", source[:branch])
        self.assertNotIn("c.flee_mode = True", source[:branch])
        self.assertIn("doi_kenh_theo_lenh_tay(", source[branch:])

    def test_XOA_co_truoc_moi_lenh(self):
        """Khong xoa thi lenh sau member di luon theo co cua lenh truoc."""
        self.assertIn('st["cmd_leader_xong"].clear()', self.than)

    def test_CHUA_ra_safe_thi_KHONG_doi_kenh(self):
        i = self.than.find('if not _safe("lenh doi kenh tay"):')
        self.assertGreater(i, 0, "van doi kenh du chua toi safe")
        self.assertIn("continue", self.than[i:i + 200])
        self.assertLess(i, self.than.find("ok = c.switch_channel(ch,"))

    def test_DOI_XONG_phai_CHECK_LAI_da_o_safe_chua(self):
        i = self.than.find("ok = c.switch_channel(ch,")
        khoi = self.than[i:i + 900]
        self.assertIn('_safe("sau khi doi kenh', khoi,
                      "doi kenh giu nguyen toa do; kenh moi cho do co the day quai")

    def test_DANH_XONG_TRAN_roi_moi_di(self):
        """User chot 30/08: "phai danh xong tran roi moi di chuyen den safe chu"."""
        self.assertIn("c._wait_combat_clear(idle=2.0, cap=120.0)", self.than)

    def test_CHUA_giai_tan_party_thi_KHONG_BO_CHAY(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        client = mock.Mock(current_map=100, pos=(1000, 1000), party_members=[1])
        client.navigate_to.side_effect = lambda *a, **k: setattr(client, "pos", (20, 30))
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.object(R, "_safe_map_dich_engine_moi", return_value=[(20, 30)]):
            self.assertTrue(R._ra_safe_engine_moi(client, 0))
        self.assertEqual(client.navigate_to.call_args.kwargs["flee"], False)
        client.leave_party.assert_not_called()

    def test_ham_ra_rally_nhan_co_bo_chay(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        client = mock.Mock(current_map=100, pos=(1000, 1000), party_members=[])
        client.navigate_to.side_effect = lambda *a, **k: setattr(client, "pos", (20, 30))
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.object(R, "_safe_map_dich_engine_moi", return_value=[(20, 30)]):
            self.assertTrue(R._ra_safe_engine_moi(client, 0))
        self.assertEqual(client.navigate_to.call_args.kwargs["flee"], True)
        client.leave_party.assert_not_called()

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
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        client = mock.Mock(current_map=100, pos=(1000, 1000), party_members=[])
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.object(R, "_safe_map_dich_engine_moi", return_value=[(20, 30)]):
            self.assertFalse(R._ra_safe_engine_moi(client, 0))
        client.navigate_to.assert_called_once()


if __name__ == "__main__":
    unittest.main()
