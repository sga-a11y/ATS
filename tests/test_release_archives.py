import os
import inspect
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import build_product


class TestReleaseArchives(unittest.TestCase):
    def test_nuitka_does_not_delete_locked_build_tree(self):
        source = inspect.getsource(build_product.package)

        self.assertNotIn("--remove-output", source)

    def test_drive_archive_is_ignored_by_git(self):
        with open(".gitignore", encoding="utf-8") as fh:
            ignored_paths = {line.strip() for line in fh if line.strip()}
        self.assertIn("aTSBot-drive.zip", ignored_paths)
        self.assertIn("aTSBot-bundle.zip", ignored_paths)

    def test_release_metadata_and_upload_include_android_apk(self):
        source = inspect.getsource(build_product)

        self.assertIn("APK_RELEASE_NAME", source)
        self.assertIn("BUNDLE_RELEASE_NAME", source)
        self.assertIn('"apk_url"', source)
        self.assertIn('"bundle_url"', source)
        self.assertIn('"pc_app_required_version"', source)
        self.assertIn('"apk_required_version"', source)
        self.assertIn("make_bundle(ver)", source)
        self.assertIn("build_android_apk(ver)", source)
        self.assertIn("os.path.join(ROOT, APK_RELEASE_NAME)", source)
        self.assertIn("os.path.join(ROOT, BUNDLE_RELEASE_NAME)", source)

    def test_android_gradle_accepts_shared_release_version(self):
        with open("android/app/build.gradle.kts", encoding="utf-8") as fh:
            gradle = fh.read()

        self.assertIn('providers.gradleProperty("atsVersion")', gradle)
        self.assertIn("ATS_BUILD_VERSION", gradle)
        self.assertIn("versionCodeFromVersion(buildVersionName)", gradle)

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
