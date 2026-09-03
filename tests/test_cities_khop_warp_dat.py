# -*- coding: utf-8 -*-
"""cities.json phai KHOP `Warp_C.dat` cua client.

Crack 03/09 (user hoi "Y chau co 2 thanh tele nao"): `flag` trong goi teleport
(C:068-001 = 0x44 sub01 + [sceneId u16][no u8]) CHINH LA CHI SO ban ghi (0-based) trong
`Warp_C.dat` - xem `UITeleport.SendUseWarp(sceneId, no)` va `SetupSkyPointData` (duyet
`warpDatas[i]`, giu `warp[idx].no = i`).

Bo cuc Warp_C.dat (Data_WarpData.lua WarpData.New) - 16 byte/ban ghi:
    name(u32 = id TextData) + scene(u16) + mark(u16 = bitId da mo thanh) + x(i32) + y(i32)

=> KHONG can capture de biet flag: doc thang file la ra. Test nay bat truong hop cities.json
lech so voi client (them thanh nham flag = bot tele sang thanh KHAC).

Y Chau co 2 thanh: Phien Ngu (26001, flag 19) va Y Chau (26011, flag 20) - them 03/09.
"""
import io
import json
import os
import struct
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WARP = os.path.join(ROOT, "gamedata", "Data", "Warp_C.dat")


def _doc_warp():
    """[(no, scene, mark)] theo dung thu tu file. None neu khong co file .dat (khong theo repo)."""
    if not os.path.exists(WARP):
        return None
    with open(WARP, "rb") as fh:
        d = fh.read()
    n = struct.unpack_from("<i", d, 0)[0]
    fmt, sz = "<IHHii", struct.calcsize("<IHHii")
    if (len(d) - 4) != n * sz:
        return None                      # bo cuc doi -> khong dam khang dinh, de test khac bat
    out = []
    for i in range(n):
        _name, scene, mark, _x, _y = struct.unpack_from(fmt, d, 4 + i * sz)
        out.append((i, scene, mark))
    return out


def _cities():
    with io.open(os.path.join(ROOT, "cities.json"), encoding="utf-8") as fh:
        return json.load(fh)["cities"]


class TestHaiThanhYChau(unittest.TestCase):
    def test_co_du_2_thanh(self):
        c = _cities()
        self.assertEqual(c["phien_ngu"]["city_id"], 26001)
        self.assertEqual(c["phien_ngu"]["flag"], 19)
        self.assertEqual(c["y_chau"]["city_id"], 26011)
        self.assertEqual(c["y_chau"]["flag"], 20)


class TestKhongTrungLap(unittest.TestCase):
    def test_city_id_va_flag_deu_duy_nhat(self):
        """Trung flag = 2 thanh cung mot 'no' -> chac chan mot cai tele sai."""
        c = _cities()
        ids = [v["city_id"] for v in c.values()]
        flags = [v["flag"] for v in c.values()]
        self.assertEqual(len(ids), len(set(ids)), "trung city_id")
        self.assertEqual(len(flags), len(set(flags)), "trung flag")


class TestKhopFileClient(unittest.TestCase):
    def test_moi_thanh_dung_flag_theo_Warp_C_dat(self):
        warp = _doc_warp()
        if warp is None:
            self.skipTest("khong co gamedata/Data/Warp_C.dat (file .dat khong theo repo)")
        theo_scene = {scene: no for no, scene, _mark in warp}
        lech = []
        for key, v in _cities().items():
            no = theo_scene.get(v["city_id"])
            if no is None:
                lech.append("%s (%d) KHONG co trong Warp_C.dat" % (key, v["city_id"]))
            elif no != v["flag"]:
                lech.append("%s (%d): cities.json flag=%d nhung file la %d"
                            % (key, v["city_id"], v["flag"], no))
        self.assertEqual(lech, [], "cities.json lech Warp_C.dat: %s" % lech)


if __name__ == "__main__":
    unittest.main()
