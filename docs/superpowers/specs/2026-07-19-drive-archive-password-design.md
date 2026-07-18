# Drive Archive Password Design

## Goal

Change the manual Google Drive archive password from `aTSbot` to `aTSBot`, matching the product and executable name.

## Scope

- Keep `aTSBot.zip` unencrypted for backward-compatible automatic updates.
- Encrypt `aTSBot-drive.zip` with ZipCrypto and password `aTSBot`.
- Update the build constant, regression test, and release packaging documentation.
- Repackage both ZIP files from the existing `aTSBot` build directory without recompiling the executable or changing its version.
- Leave Android unchanged because it does not consume the desktop ZIP archives.

## Packaging Flow

`build_product.make_zip()` continues to create both archives from the same release file list. The normal archive uses Python `zipfile`; the Drive archive uses 7-Zip ZipCrypto with the password supplied by `DRIVE_ARCHIVE_PASSWORD`.

## Verification

- First change the regression test to require `aTSBot` and confirm it fails against the old password.
- Change the build constant and confirm the focused test passes.
- Run the complete desktop/navigation test suite.
- Repackage the existing release directory.
- Confirm both archives contain identical files and bytes, the normal ZIP is unencrypted, the Drive ZIP is encrypted, `aTSBot` decrypts every entry, and `aTSbot` is rejected.

## Error Handling

The existing behavior remains: packaging fails clearly if 7-Zip is unavailable or archive creation returns a non-zero exit code. A failed Drive archive build does not silently publish an unencrypted manual package.
