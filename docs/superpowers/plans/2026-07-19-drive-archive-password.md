# Drive Archive Password Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the password of `aTSBot-drive.zip` from `aTSbot` to `aTSBot` and regenerate the desktop release archives without rebuilding the executable.

**Architecture:** Keep the dual-archive packaging flow unchanged and update its single password constant. Drive the change through the existing real-archive regression test, then repackage from the current `aTSBot` release directory and verify encryption, rejected legacy password, and byte-for-byte equality with the updater archive.

**Tech Stack:** Python 3.12, `unittest`, `zipfile`, 7-Zip ZipCrypto.

## Global Constraints

- `aTSBot.zip` remains unencrypted and compatible with existing auto-update clients.
- `aTSBot-drive.zip` uses ZipCrypto and requires password `aTSBot`.
- Password `aTSbot` must no longer decrypt the Drive archive.
- Both archives contain identical relative file paths and bytes.
- The existing executable and version are reused; Android is unchanged.

---

### Task 1: Change the archive password with TDD

**Files:**
- Modify: `tests/test_release_archives.py`
- Modify: `build_product.py`
- Modify: `docs/superpowers/plans/2026-07-18-dual-release-archives.md`

**Interfaces:**
- Consumes: `build_product.DRIVE_ARCHIVE_PASSWORD` and `build_product.make_zip()`.
- Produces: future Drive archives encrypted with password `aTSBot`.

- [x] **Step 1: Change the test expectation first**

Update both encrypted reads in `tests/test_release_archives.py`:

```python
drive.read("aTSBot.exe", pwd=b"aTSBot")
drive.read("gamedata/Ground.mmg", pwd=b"aTSBot")
```

- [x] **Step 2: Run the focused test and verify RED**

Run: `python -m unittest discover -s tests -p test_release_archives.py -v`

Expected: FAIL with `Bad password for file` because production still creates the archive with `aTSbot`.

- [x] **Step 3: Change the production constant**

Update `build_product.py`:

```python
DRIVE_ARCHIVE_PASSWORD = "aTSBot"
```

Update the earlier dual-archive plan so every password example is `aTSBot`.

- [x] **Step 4: Run the focused test and verify GREEN**

Run: `python -m unittest discover -s tests -p test_release_archives.py -v`

Expected: both release archive tests PASS.

- [x] **Step 5: Run the complete test suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

### Task 2: Repackage and verify the existing release

**Files:**
- Generated: `aTSBot.zip`
- Generated: `aTSBot-drive.zip`

**Interfaces:**
- Consumes: existing release directory `aTSBot/` and `build_product.make_zip()`.
- Produces: refreshed updater and Drive ZIP files without changing the executable version.

- [x] **Step 1: Repackage without compiling**

Run: `python -c "import build_product; build_product.make_zip()"`

Expected: exit code 0; both archive paths and sizes are printed.

- [x] **Step 2: Verify the real artifacts**

Open both archives with Python `zipfile`. Assert the path sets match, all updater entries are unencrypted, all Drive entries are encrypted, every Drive entry reads with `pwd=b"aTSBot"`, every extracted byte sequence matches the updater archive, and reading a non-empty Drive entry with `pwd=b"aTSbot"` raises `RuntimeError`.

- [x] **Step 3: Verify the working tree**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors; generated ZIPs remain ignored; the pre-existing untracked `aTSBot-drive/` directory is left untouched.
