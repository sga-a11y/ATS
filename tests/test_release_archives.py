import os
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import build_product


class TestReleaseArchives(unittest.TestCase):
    def test_drive_archive_is_ignored_by_git(self):
        with open(".gitignore", encoding="utf-8") as fh:
            ignored_paths = {line.strip() for line in fh if line.strip()}
        self.assertIn("aTSBot-drive.zip", ignored_paths)

    def test_make_zip_creates_plain_and_password_protected_archives(self):
        with tempfile.TemporaryDirectory() as root:
            dist = os.path.join(root, "aTSBot")
            nested = os.path.join(dist, "gamedata")
            os.makedirs(nested)
            with open(os.path.join(dist, "aTSBot.exe"), "wb") as fh:
                fh.write(b"desktop-binary")
            with open(os.path.join(nested, "Ground.mmg"), "wb") as fh:
                fh.write(b"navigation-data")

            with patch.object(build_product, "ROOT", root), patch.object(
                build_product, "DIST", dist
            ):
                build_product.make_zip()

            plain_path = os.path.join(root, "aTSBot.zip")
            drive_path = os.path.join(root, "aTSBot-drive.zip")
            expected_names = {"aTSBot.exe", "gamedata/Ground.mmg"}

            self.assertTrue(os.path.isfile(plain_path))
            self.assertTrue(os.path.isfile(drive_path))

            with zipfile.ZipFile(plain_path) as plain:
                self.assertEqual(set(plain.namelist()), expected_names)
                self.assertEqual(plain.read("aTSBot.exe"), b"desktop-binary")
                self.assertFalse(any(info.flag_bits & 1 for info in plain.infolist()))

            with zipfile.ZipFile(drive_path) as drive:
                self.assertEqual(set(drive.namelist()), expected_names)
                self.assertTrue(all(info.flag_bits & 1 for info in drive.infolist()))
                with self.assertRaises(RuntimeError):
                    drive.read("aTSBot.exe")
                with self.assertRaises(RuntimeError):
                    drive.read("aTSBot.exe", pwd=b"aTSbot")
                self.assertEqual(
                    drive.read("aTSBot.exe", pwd=b"aTSBot"), b"desktop-binary"
                )
                self.assertEqual(
                    drive.read("gamedata/Ground.mmg", pwd=b"aTSBot"),
                    b"navigation-data",
                )


if __name__ == "__main__":
    unittest.main()
