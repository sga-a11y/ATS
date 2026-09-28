"""Chay ban cu = ghi version.json local thanh '9.<ban that>' -> ban cu (khong sua code gi) tu thay
minh moi nhat va KHONG tu update. Test giu dung co che so sanh ma ban cu dang dung."""
import json
import os
import tempfile
import unittest

from bot import updater


class GhimVersionTest(unittest.TestCase):
    def test_ban_ghim_luon_moi_hon_moi_ban_server(self):
        fake = updater.pinned_version("1.1.202608100000")
        for server in ("1.1.202609281200", "1.1.209912312359", "2.0.203001010000"):
            self.assertFalse(updater._is_newer_version(server, fake), server)

    def test_doc_lai_ban_that(self):
        self.assertEqual(updater.real_version("9.1.1.202609141802"), "1.1.202609141802")
        self.assertEqual(updater.real_version("1.1.202609141802"), "1.1.202609141802")
        self.assertEqual(updater.pinned_version("9.1.1.1"), "9.1.1.1")

    def test_ghi_version_json_ghim_moi_truong(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "version.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"version": "1.1.202608100000", "pc_app_version": "1.1.202608100000",
                           "bundle_version": "1.1.202608100000", "notes": "x"}, f)
            updater.pin_version_file(p, "1.1.202608100000")
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        for key in ("version", "pc_app_version", "bundle_version"):
            self.assertEqual(data[key], "9.1.1.202608100000")
        self.assertEqual(data["notes"], "x")

    def test_tick_bo_tick_ghi_ca_app_lan_core(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "version.json"), "w", encoding="utf-8") as f:
                json.dump({"version": "1.1.202608100000", "pc_app_version": "1.1.202608100000"}, f)
            os.makedirs(os.path.join(d, "bot_bundle"))
            with open(os.path.join(d, "bot_bundle", "version.txt"), "w") as f:
                f.write("1.1.202608110000")

            def doc():
                with open(os.path.join(d, "version.json"), encoding="utf-8") as f:
                    app = json.load(f)["pc_app_version"]
                with open(os.path.join(d, "bot_bundle", "version.txt")) as f:
                    return app, f.read()

            updater.set_auto_update(False, d)
            self.assertEqual(doc(), ("9.1.1.202608100000", "9.1.1.202608110000"))
            self.assertTrue(os.path.exists(os.path.join(d, updater.PIN_NOTE_FILE)))
            updater.set_auto_update(False, d)   # bo tick 2 lan khong thanh 9.9.
            self.assertEqual(doc(), ("9.1.1.202608100000", "9.1.1.202608110000"))
            updater.set_auto_update(True, d)
            self.assertEqual(doc(), ("1.1.202608100000", "1.1.202608110000"))
            self.assertFalse(os.path.exists(os.path.join(d, updater.PIN_NOTE_FILE)))

    def test_url_ban_cu_theo_tag(self):
        self.assertEqual(updater.old_release_zip_url("9.1.1.202608100000"),
                         "https://github.com/sgagamee-oss/atsbot-release/releases/download/"
                         "v1.1.202608100000/aTSBot.zip")

    def test_mac_dinh_tick_tu_dong_update(self):
        self.assertTrue(updater.auto_update_enabled("1.1.202608100000"))
        self.assertFalse(updater.auto_update_enabled("9.1.1.202608100000"))

    def test_danh_sach_loc_ban_co_zip_va_du_moi(self):
        zipa = [{"name": "aTSBot.zip"}]
        data = [
            {"tag_name": "v1.1.202608100031", "published_at": "2026-08-10T00:31:00Z", "assets": zipa},
            {"tag_name": "v1.1.202609281050", "published_at": "2026-09-28T03:50:00Z", "assets": zipa},
            {"tag_name": "v1.1.202609200000", "published_at": "2026-09-20T00:00:00Z", "assets": []},
            {"tag_name": "v1.1.202607010000", "published_at": "2026-07-01T00:00:00Z", "assets": zipa},
        ]
        self.assertEqual([v for v, _d, _n in updater.filter_releases(data)],
                         ["1.1.202609281050", "1.1.202608100031"])

    def test_build_sinh_releases_json_app_doc_duoc(self):
        import sys
        from unittest import mock
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        import build_product
        api = [
            {"tag_name": "v1.1.202609281050", "published_at": "2026-09-28T03:50:00Z",
             "assets": [{"name": "aTSBot.zip", "size": 1}, {"name": "aTSBot-bundle.zip"}]},
            {"tag_name": "v1.1.202609281601", "published_at": "x", "assets": []},   # ban dang build
            {"tag_name": "v1.1.202609200000", "published_at": "2026-09-20T00:00:00Z", "draft": True,
             "assets": [{"name": "aTSBot.zip"}]},
        ]
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(build_product, "ROOT", d), \
                mock.patch.object(build_product, "_gh_get", return_value=api):
            build_product._write_releases_json("tok", "v1.1.202609281601")
            with open(os.path.join(d, build_product.RELEASES_JSON_NAME), encoding="utf-8") as f:
                data = json.load(f)
        self.assertEqual([v for v, _d, _n in updater.filter_releases(data)],
                         ["1.1.202609281601", "1.1.202609281050"])
        self.assertEqual([v for v, _d, _n in updater.filter_releases(data, "aTSBot-bundle.zip")],
                         ["1.1.202609281601", "1.1.202609281050"])

    def test_app_doc_releases_json_truoc_api(self):
        self.assertTrue(updater.RELEASES_JSON_URL.endswith("/releases/latest/download/releases.json"))
        kt = _doc_kt("ApkUpdater.kt")
        self.assertLess(kt.index("releases/latest/download/releases.json"),
                        kt.index("api.github.com/repos/$RELEASE_REPO/releases"))

    def test_apk_cung_lay_100_ban(self):
        self.assertIn("per_page=%d" % updater.RELEASE_LIMIT, _doc_kt("ApkUpdater.kt"))


_KT =os.path.join(os.path.dirname(__file__), "..", "android", "app", "src", "main", "java", "com",
                   "tsbot", "android")


def _doc_kt(name):
    with open(os.path.join(_KT, name), encoding="utf-8") as f:
        return f.read()


class ApkGhimVersionTest(unittest.TestCase):
    def test_apk_cung_tien_to_ghim_voi_pc(self):
        self.assertIn('const val PIN_PREFIX = "%s"' % updater.PIN_PREFIX, _doc_kt("ApkUpdater.kt"))

    def test_apk_tat_tu_dong_update_thi_khong_tai_core(self):
        kt = _doc_kt("ApkUpdater.kt")
        than = kt[kt.index("fun updateBundleIfNeeded"):]
        self.assertIn("if (!isAutoUpdate(context)) return false", than[:200])

    def test_apk_tat_tu_dong_update_thi_khong_check_apk(self):
        kt = _doc_kt("MainActivity.kt")
        than = kt[kt.index("fun checkApkUpdate"):]
        self.assertIn("if (!ApkUpdater.isAutoUpdate(context))", than[:300])

    def test_apk_core_ghim_qua_cua_chan_bundle_cu(self):
        # Cua chan (06/09) so CHUOI bundleVer > VERSION_NAME: core ghim '9.' phai qua duoc cua.
        self.assertIn("ApkUpdater.isNewerVersion(bundleVer, BuildConfig.VERSION_NAME)",
                      _doc_kt("BotForegroundService.kt"))
        self.assertIn("return remoteVersion > current", _doc_kt("ApkUpdater.kt"))


if __name__ == "__main__":
    unittest.main()
