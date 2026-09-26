"""An unresolved regroup stays actionable without repeatedly cancelling one worker task."""
from __future__ import annotations

import unittest

from bot import party_engine as PE


class TestLenhGomKhongMat(unittest.TestCase):
    def _snapshot(self, member_map):
        accs = [PE.AnhAcc("leader", la_leader=True, map_id=12001, kenh=1,
                           so_member=1),
                PE.AnhAcc("member", map_id=member_map, kenh=1, so_member=1)]
        return PE.AnhParty(0, accs, can_bao_nhieu=1, thanh_dich=12001,
                           dp_viec=PE.DP_GOM)

    def test_con_lech_thi_nhip_sau_van_giao_gom(self):
        first = PE.quyet_dinh(self._snapshot(21001))
        second = PE.quyet_dinh(self._snapshot(21001))
        self.assertEqual(first["member"], PE.VIEC_VE_THANH)
        self.assertEqual(second["member"], PE.VIEC_VE_THANH)

    def test_da_ve_toi_diem_gom_thi_khong_tele_lai(self):
        jobs = PE.quyet_dinh(self._snapshot(12001))
        self.assertNotEqual(jobs.get("member"), PE.VIEC_VE_THANH)

    def test_cung_viec_dang_chay_khong_bi_huy_moi_nhip(self):
        worker = PE.AccWorker("member", object(), lambda *_: None)
        self.assertTrue(worker.giao(PE.VIEC_VE_THANH))
        worker._huy.clear()
        self.assertFalse(worker.giao(PE.VIEC_VE_THANH))
        self.assertFalse(worker._huy.is_set())

    def test_viec_chay_xong_nhung_van_lech_duoc_thu_lai(self):
        worker = PE.AccWorker("member", object(), lambda *_: None)
        worker.giao(PE.VIEC_VE_THANH)
        with worker._lock:
            worker._viec_moi = None
            worker._viec = PE.VIEC_NGHI
        self.assertTrue(worker.giao(PE.VIEC_VE_THANH))


if __name__ == "__main__":
    unittest.main()
