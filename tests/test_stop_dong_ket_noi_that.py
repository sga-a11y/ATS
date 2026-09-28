"""STOP phai DONG socket that khi thread acc thoat (ca 28/09: 124/145 acc van online sau Stop).

stop_account hoan dong socket khi acc o bai train; watchdog chi dong neu thread con song. Engine
moi tra thread som -> finally cua run_account la cho cuoi cung phai dong.
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    os.path.join(ROOT, "run_party_digioi.py"),
    os.path.join(ROOT, "android", "app", "src", "main", "python", "train_bot", "run_party_digioi.py"),
]


class TestStopDongKetNoiThat(unittest.TestCase):
    def test_finally_run_account_dong_client_khi_stop(self):
        for f in FILES:
            src = open(f, encoding="utf-8").read()
            i = src.index("def run_account(")
            j = src.index("account_clients.pop(username, None)", i)
            k = src.rfind("finally:", i, j)
            self.assertGreater(k, 0, f)
            khoi = src[k:j]
            self.assertIn("if _stopped() and c is not None:", khoi, f)
            self.assertIn("c.close()", khoi, f)


if __name__ == "__main__":
    unittest.main()
