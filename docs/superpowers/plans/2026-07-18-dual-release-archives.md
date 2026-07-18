# Dual Release Archives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an unencrypted `aTSBot.zip` for automatic updates and a password-protected `aTSBot-drive.zip` for manual Google Drive distribution.

**Architecture:** Keep the existing standard-library ZIP path unchanged for updater compatibility. Build a second archive from the same staged desktop release directory with installed 7-Zip, ZipCrypto encryption, and password `aTSBot`; the Android build is unaffected because it does not consume either desktop release archive.

**Tech Stack:** Python 3, `zipfile`, 7-Zip CLI, `unittest`.

## Global Constraints

- `aTSBot.zip` must remain readable without a password.
- `aTSBot-drive.zip` must require password `aTSBot` and use ZipCrypto for Windows Explorer compatibility.
- Both archives must contain identical relative paths and file contents.
- GitHub auto-update must continue publishing only `aTSBot.zip`.
- No APK code change is required for this PC-only packaging behavior.

---

### Task 1: Test dual archive behavior

**Files:**
- Create: `tests/test_release_archives.py`
- Test: `tests/test_release_archives.py`

**Interfaces:**
- Consumes: `build_product.make_zip()` and module paths `ROOT`, `DIST`.
- Produces: regression coverage for archive names, contents, and password behavior.

- [x] **Step 1: Write the failing test**

Create a temporary release directory with a root file and a nested file, patch `build_product.ROOT` and `build_product.DIST`, call `make_zip()`, then assert both output archives have identical names and contents. Assert the normal archive reads without a password, while the Drive archive rejects an unauthenticated read and accepts `pwd=b"aTSBot"`.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p test_release_archives.py -v`

Expected: FAIL because `aTSBot-drive.zip` does not exist.

### Task 2: Build the password-protected Drive archive

**Files:**
- Modify: `build_product.py`
- Test: `tests/test_release_archives.py`

**Interfaces:**
- Consumes: installed `7z.exe` and the contents of `DIST`.
- Produces: `find_7zip() -> str` and dual output from `make_zip()`.

- [x] **Step 1: Implement minimal production code**

Add constants for the Drive archive suffix and password. Resolve 7-Zip from `PATH` or the standard Windows installation paths. Keep the existing `zipfile` creation for `aTSBot.zip`, then run 7-Zip from `DIST` with `-tzip`, `-mem=ZipCrypto`, and `-paTSBot` to create `aTSBot-drive.zip` with relative paths.

- [x] **Step 2: Run the focused test**

Run: `python -m unittest discover -s tests -p test_release_archives.py -v`

Expected: PASS.

- [x] **Step 3: Run the full test suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

### Task 3: Verify real release artifacts

**Files:**
- Generated: `aTSBot.zip`
- Generated: `aTSBot-drive.zip`

**Interfaces:**
- Consumes: the existing `aTSBot` release directory produced by the desktop build.
- Produces: two distributable archives with matching content.

- [x] **Step 1: Run the desktop build without uploading**

Run: `python build_product.py --no-upload`

Expected: exit code 0 and both ZIP paths printed.

- [x] **Step 2: Verify archive behavior**

Use Python `zipfile` to confirm `aTSBot.zip` reads unauthenticated, `aTSBot-drive.zip` rejects unauthenticated reads, the password `aTSBot` reads every encrypted entry, and both archives contain identical names.

- [x] **Step 3: Inspect the Git diff**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors; only the intended source, test, and plan files are changed.
