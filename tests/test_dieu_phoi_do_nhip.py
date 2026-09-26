"""Each party has one decision loop; a failed tick cannot stop another party."""
from __future__ import annotations

import threading
import unittest
from unittest import mock

from bot import party_engine as PE


class _Client:
    running = True
    current_map = 12001
    current_channel = 1
    party_members = ()


class TestMotLuongMoiParty(unittest.TestCase):
    def setUp(self):
        self.client = _Client()
        self.engines = []

    def tearDown(self):
        for engine in self.engines:
            engine.stop()
            if engine._th is not None:
                engine._th.join(timeout=2)

    def _engine(self, pidx):
        engine = PE.PartyEngine(pidx, lambda: [("a", self.client, True)])
        self.engines.append(engine)
        return engine

    def test_start_lai_khong_tao_luong_quyet_dinh_thu_hai(self):
        engine = self._engine(0)
        with mock.patch.object(engine, "nhip", return_value={}):
            engine.start()
            first = engine._th
            engine.start()
            self.assertIs(engine._th, first)
            self.assertTrue(first.is_alive())
            self.assertEqual(first.name, "engine-p1")

    def test_moi_party_co_luong_rieng(self):
        first, second = self._engine(0), self._engine(1)
        with mock.patch.object(first, "nhip", return_value={}), \
             mock.patch.object(second, "nhip", return_value={}):
            first.start()
            second.start()
            self.assertIsNot(first._th, second._th)
            self.assertTrue(first._th.is_alive())
            self.assertTrue(second._th.is_alive())

    def test_nhip_loi_duoc_thu_lai_o_chinh_party(self):
        engine = self._engine(0)
        retried = threading.Event()
        calls = []

        def tick():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("tick failed")
            retried.set()
            return {}

        with mock.patch.object(engine, "nhip", side_effect=tick):
            engine.start()
            self.assertTrue(retried.wait(2), "one failed tick stopped the party controller")
            self.assertGreaterEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
