"""EVENT LIEN SERVER (無界 - "vo gioi"): loan dau THU 7 nam tren MOT MAY KHAC.

SU CO 05/09 21:20 (party 11, 5 acc ca buoi 0 tran):
    go_to_event 'Loan dau' -> staging 0, dest 54901
    go_to_event 'Loan dau' xong: map=23882 (dich 54901) -> CHUA TOI
Bot gui `0x4d 03005a00`, server tra ve lenh CHUYEN MAY, bot BO QUA -> dung im o map train.

Capture `captures/loandau_t7_20260905.pcap` co 4 luong TCP tren 2 IP:
    103.190.202.46:6614   0.0s -> 19.5s     (may dang choi)
    103.190.202.65:6614  21.7s -> het       (may cua map 54901)

Cau truc lay THANG tu client, KHONG doan:
    protocal.lua:563  S:001-020 <通知連無界伺服器> ServerId(2)+L(1)+IP(L)+port(2)+SN(4)
    protocal.lua:577  S:001-021 <通知連回原SERVER> GSID(2)
    Network.lua:428   C:001-000 +版本編號(2)+伺服器ID(2)+連線碼(4)+登入方式(1)
                      登入方式 255 (ELogin.Unbounded): +L(1)+帳號 +L(1)+密碼 +RoleID(8)+SN(4)
"""
from __future__ import annotations

import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import auth  # noqa: E402
from bot.protocol import xor  # noqa: E402

# Goi THAT tu capture (than sau opcode, ke ca 2 byte sub).
BAO_CHUYEN = bytes.fromhex(
    "1400ff001c3100300033002e003100390030002e003200300032002e0036003500d61901000000")


class TestDocGoiBaoChuyen(unittest.TestCase):
    def test_doc_dung_goi_that(self):
        d = auth.parse_bao_chuyen_vo_gioi(BAO_CHUYEN)
        self.assertEqual(d, {"server_id": 255, "host": "103.190.202.65",
                             "port": 6614, "sn": 1})

    def test_goi_khac_thi_tra_None(self):
        self.assertIsNone(auth.parse_bao_chuyen_vo_gioi(bytes.fromhex("10000102030405060708")))
        self.assertIsNone(auth.parse_bao_chuyen_vo_gioi(b"\x14\x00"))      # cut ngan

    def test_khong_no_khi_goi_cut_giua_chuoi_IP(self):
        self.assertIsNone(auth.parse_bao_chuyen_vo_gioi(BAO_CHUYEN[:12]))


class TestGoiAuthVoGioi(unittest.TestCase):
    """Sai mot trong ba diem duoi la server tu choi -> mat ca buoi event."""

    ACC, PWD = "1623035726@vtc", "DKC8A3798N"
    ENT = bytes.fromhex("b241273a191b0700")

    def _than(self, **kw):
        g = auth.build_unbounded_auth_packet(self.ACC, self.PWD, self.ENT, 255, 1, **kw)
        return xor(g)[7:]      # bo header, tra than (xor la phep tu nghich)

    def test_dung_y_HET_goi_client(self):
        """Doi chieu tung byte voi goi client that trong capture (bo connectCode - xem test rieng)."""
        than = self._than(connect_code=0x000019b9)
        self.assertEqual(than.hex(), "00000201ff00b9190000ff1c"
                         + self.ACC.encode("utf-16-le").hex()
                         + "14" + self.PWD.encode("utf-16-le").hex()
                         + self.ENT.hex() + "01000000")

    def test_loginKind_la_255_khong_phai_25(self):
        """25 = ELogin.VNSDK (goi thuong). Vo gioi la 255 = ELogin.Unbounded."""
        self.assertEqual(auth.LOGIN_VO_GIOI, 0xFF)
        self.assertEqual(self._than()[10], 0xFF)

    def test_do_dai_chuoi_la_MOT_byte(self):
        """Vo gioi dung `WriteStringWithByteL`; goi thuong dung `WriteStringWithWordL` (2 byte).
        Dung nham 2 byte -> server doc lech ca goi."""
        than = self._than()
        self.assertEqual(than[11], len(self.ACC.encode("utf-16-le")))   # 0x1c = 28, KHONG phai 1c00
        sau_acc = 12 + 28
        self.assertEqual(than[sau_acc], len(self.PWD.encode("utf-16-le")))

    def test_co_RoleID_va_SN(self):
        """Hai truong goi auth thuong KHONG co."""
        than = self._than()
        self.assertTrue(than.endswith(self.ENT + struct.pack("<I", 1)))

    def test_serverId_lay_tu_goi_bao_chuyen(self):
        d = auth.parse_bao_chuyen_vo_gioi(BAO_CHUYEN)
        than = auth.build_unbounded_auth_packet(self.ACC, self.PWD, self.ENT,
                                                d["server_id"], d["sn"])
        self.assertEqual(struct.unpack_from("<H", xor(than)[7:], 4)[0], 255)

    def test_chan_du_lieu_hong(self):
        with self.assertRaises(ValueError):
            auth.build_unbounded_auth_packet(self.ACC, self.PWD, b"\x01\x02", 255, 1)
        with self.assertRaises(ValueError):
            auth.build_unbounded_auth_packet("x" * 200, self.PWD, self.ENT, 255, 1)


class TestClientNoiDay(unittest.TestCase):
    def _src(self):
        import io
        return io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8").read()

    def test_bat_goi_bao_chuyen_va_goi_ve(self):
        s = self._src()
        self.assertIn(r'pkt[7:9] == b"\x14\x00"', s, "khong bat S:001-020 -> dung im o may cu")
        self.assertIn(r'pkt[7:9] == b"\x15\x00"', s, "khong bat S:001-021 (ve may cu)")

    def test_go_to_event_CHUYEN_MAY_chu_khong_cho_suong(self):
        s = self._src()
        i = s.find("def go_to_event(")
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn("chuyen_server_vo_gioi()", than,
                      "chi cho ma khong doi may -> map event khong nam tren may nay, cho mai")

    def test_that_bai_thi_KHONG_di_tiep(self):
        s = self._src()
        i = s.find("def chuyen_server_vo_gioi(")
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn("self.server_closed = True", than,
                      "chuyen hong ma khong bao -> acc treo, supervisor khong login lai may cu")
        self.assertIn("self._host_goc", than, "khong nho may goc thi khong biet duong ve")



class TestKhongCanChayRaCONG(unittest.TestCase):
    """User chot 05/09 sau khi chay that: san vo gioi nam tren MAY KHAC, ma login lan sau LUON
    vao MAY GOC -> tat acc la ra khoi map event luon. Khong can chay ra NPC.

    Khac han thu 3 (map 10991 CUNG may): o do khong ra thi lan sau bot khoi dong tu map event.
    Bo buoc chay ra = bot mot cho co the hong (dialog tren map la, giua luc member con danh do).
    """

    def _than(self):
        import io as _io
        s = _io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8").read()
        i = s.find("def _loandau_ra_khoi_map(")
        return s[i:s.find("\ndef ", i + 10)]

    def test_o_san_vo_gioi_thi_KHONG_lam_gi_them(self):
        than = self._than()
        i = than.find('getattr(c, "tren_vo_gioi", False)')
        self.assertGreater(i, 0, "khong phan biet san vo gioi")
        self.assertLess(i, than.find("c.exit_event(ev)"), "phai xet vo gioi TRUOC khi tele 12003")
        self.assertNotIn("roi_san_vo_gioi", than, "van chay ra NPC - user da bao khong can")

    def test_thu_3_VAN_phai_ra_khoi_map(self):
        """Map 10991 cung may goc: khong ra thi lan sau bot khoi dong tu map event."""
        self.assertIn("c.exit_event(ev)", self._than())

    def test_da_bo_han_ham_chay_ra(self):
        import io as _io
        s = _io.open(os.path.join(ROOT, "bot", "loandau.py"), encoding="utf-8").read()
        self.assertNotIn("def roi_san_vo_gioi", s, "de lai ham chet")
        self.assertNotIn("RA_MO_NPC", s)


class TestHongThiPhaiVE_MAY_GOC(unittest.TestCase):
    """BUG THAT 05/09 21:57 - party 11 "vang game".

        SERVER BAO CHUYEN (vo gioi): 103.190.202.65:6614 serverId=255 SN=1
        CHUYEN SANG SERVER VO GIOI 103.190.202.65:6614 ...
        (het log - acc chet)

    Ban dau gan `self.host = <ip vo gioi>` NGAY khi mo socket. Auth hong -> supervisor login
    lai bang `self.host` = dam vao chinh may vua tu choi -> vong lap chet, khong bao gio ve
    duoc may cu. Moi duong that bai PHAI tra host ve may goc.
    """

    def _than(self):
        import io as _io
        s = _io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8").read()
        i = s.find("def chuyen_server_vo_gioi(")
        return s[i:s.find("\n    def ", i + 10)]

    def test_moi_duong_hong_deu_tra_host_ve_may_goc(self):
        than = self._than()
        self.assertIn("self.host = self._host_goc", than,
                      "khong tra host ve -> supervisor dam mai vao may vo gioi")
        # SAU khi da tro host sang may vo gioi thi KHONG duoc con duong `return False` tran nao
        # (truoc do thi duoc: luc ay host van la may goc, chua doi gi).
        i = than.find('self.host = bc["host"]')
        self.assertGreater(i, 0)
        for dong in than[i:].splitlines():
            self.assertNotEqual(dong.strip(), "return False",
                                "con duong thoat SAU khi doi host ma khong tra host ve may goc")

    def test_boc_loi_cua_login_setup(self):
        """`_login_setup` gui hang loat goi; auth bi tu choi = socket dong = OSError."""
        than = self._than()
        i = than.find("self._login_setup()")
        self.assertGreater(i, 0)
        self.assertIn("try:", than[max(0, i - 120):i], "_login_setup khong duoc boc try")

    def test_khong_thay_spawn_cung_tinh_la_hong(self):
        than = self._than()
        self.assertIn("KHONG thay spawn", than,
                      "auth xong ma khong vao duoc thi van phai ve may goc, khong duoc treo")

    def test_xoa_co_tren_vo_gioi_khi_hong(self):
        """Con co `tren_vo_gioi` la luc ra se goi NPC vo gioi tren may goc -> vo nghia."""
        than = self._than()
        self.assertIn("self.tren_vo_gioi = False", than)


# Goi THAT tu `captures/loandau_t7_login_20260905.pcap`.
LOGIN_OK = bytes.fromhex(
    "02000001000800b32d3145918d03003898ea78dd97e640001c31003600320033003000320031003900330030"
    "004000760074006300143300370051004800380052003300410034003900" "00")
GOI_001_013 = bytes.fromhex("0d000d3f0000")


class TestCapAccPwdChoVoGioi(unittest.TestCase):
    """MANH CON THIEU khien lan chay 05/09 21:57 that bai (log dung ngay sau
    "CHUYEN SANG SERVER VO GIOI", server tu choi auth).

    Bot gui user_id (chuoi so) + access_token (51 ky tu) cua rieng no. Nhung server vo gioi doi
    CAP MA SERVER GOC VUA PHAT LAI luc login qua S:001-002:
        acc = "<user_id>@vtc"   pwd = ve 10 ky tu (KHAC access_token)
    """

    def test_doc_dung_cap_tu_goi_login(self):
        self.assertEqual(auth.parse_ket_qua_login(LOGIN_OK), ("1623021930@vtc", "37QH8R3A49"))

    def test_goi_khac_thi_None(self):
        self.assertIsNone(auth.parse_ket_qua_login(GOI_001_013))
        self.assertIsNone(auth.parse_ket_qua_login(LOGIN_OK[:20]))

    def test_doc_connect_code(self):
        self.assertEqual(auth.parse_connect_code(GOI_001_013), 16141)
        self.assertIsNone(auth.parse_connect_code(LOGIN_OK))

    def test_client_luu_ca_ba_thu(self):
        import io as _io
        s = _io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8").read()
        self.assertIn(r'pkt[7:9] == b"\x02\x00"', s, "khong bat S:001-002 -> khong co acc/pwd")
        self.assertIn(r'pkt[7:9] == b"\x0d\x00"', s, "khong bat S:001-013 -> connectCode luon 0")

    def test_KHONG_dung_user_id_access_token_nua(self):
        import io as _io
        s = _io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8").read()
        i = s.find("def chuyen_server_vo_gioi(")
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn("self._vg_acc", than)
        self.assertNotIn("self.user_id", than,
                         "van gui user_id -> server vo gioi tu choi (da mac 05/09 21:57)")

    def test_chua_co_cap_thi_KHONG_DI(self):
        import io as _io
        s = _io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8").read()
        i = s.find("def chuyen_server_vo_gioi(")
        than = s[i:s.find("\n    def ", i + 10)]
        j = than.find("if not self._vg_acc or not self._vg_pwd:")
        self.assertGreater(j, 0, "khong co cap ma van di = chac chan bi tu choi")
        self.assertLess(j, than.find("_open_game_socket"), "phai kiem TRUOC khi dong socket cu")


if __name__ == "__main__":
    unittest.main()
