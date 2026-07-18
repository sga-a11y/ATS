# Phúc Thần Priority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the hardcoded Ngọc Siêu → Ngọc Đại → Túi Đại fallback flow, synchronize it to Android, and rebuild both desktop and APK artifacts.

**Architecture:** Modify the shared desktop `GameClient` item loop with a hardcoded ordered tuple of three TIDs, then use the existing synchronization script to copy the shared Python source into the APK tree. Regression tests exercise real `_use_items_from_cfg` behavior with an in-memory bag and verify Android receives the same priority constant.

**Tech Stack:** Python 3.12 `unittest`, Nuitka, 7-Zip, Gradle/Android SDK/JDK 17.

## Global Constraints

- Protective priority is exactly `0x5aab`, then `0x5a2d`, then `0xb5f4`.
- At most one protective action occurs per invocation.
- `0xb5f4` is consumed at quantity one only when neither gem is available.
- Đại Phúc Thần `0xb3d6` and Phúc Thần `0xb3d5` keep their current normal consumption behavior.
- PC and APK behavior must remain identical.
- Existing login timing, 30-minute schedule, combat guard, and Ngọc Hư cleanup remain unchanged.

---

### Task 1: Add failing priority tests

**Files:**
- Create: `tests/test_phuc_than_priority.py`
- Test: `tests/test_phuc_than_priority.py`

**Interfaces:**
- Consumes: `bot.client.GameClient._use_items_from_cfg(cfg, context_label)`.
- Produces: regression coverage for all priority branches and Android source parity.

- [x] **Step 1: Create a lightweight client fixture**

Instantiate `GameClient` with `__new__`, populate `bag_slots`, `running`, and `_label`, and replace `equip_item`/`use_slot` with recording functions. Patch `_load_gamedata_items` and `time.sleep` so the test has no network, login, or delay dependency.

- [x] **Step 2: Test the required priority branches**

Add tests asserting:

```python
all three present       -> equip slot containing 0x5aab; never use 0xb5f4
0x5a2d + 0xb5f4 present -> equip slot containing 0x5a2d; never use 0xb5f4
only 0xb5f4 present     -> use its slot once with qty=1
none present            -> no equip/use call
```

Add a mixed-bag test proving `0xb3d6` and `0xb3d5` still run after the single selected protective action while `0xb5f4` is skipped when a gem exists.

- [x] **Step 3: Run the focused tests and verify RED**

Run: `python -m unittest discover -s tests -p test_phuc_than_priority.py -v`

Expected: failures showing Túi Đại is still consumed independently and the hardcoded priority constant is absent.

### Task 2: Implement and synchronize the flow

**Files:**
- Modify: `bot/client.py`
- Modify: `android/app/src/main/python/train_bot/client.py` via `tools/sync_apk_python.py`
- Test: `tests/test_phuc_than_priority.py`

**Interfaces:**
- Produces: module constant `PHUC_THAN_PROTECTION_PRIORITY = ((0x5AAB, "equip"), (0x5A2D, "equip"), (0xB5F4, "use"))`.

- [x] **Step 1: Implement the minimal hardcoded selection**

In `_use_items_from_cfg`, scan `PHUC_THAN_PROTECTION_PRIORITY`, locate the first available TID in `bag_slots`, perform either one `equip_item(slot)` or one `use_slot(slot, qty=1)`, update tracked quantity, log the action, and stop scanning even if the selected command reports failure.

Skip every TID in `PHUC_THAN_PROTECTION_PRIORITY` in the subsequent generic consumable loop. Leave all other item logic unchanged.

- [x] **Step 2: Synchronize shared Python to APK**

Run: `python tools/sync_apk_python.py`

Expected: Android `train_bot/client.py` receives the same constant and selection logic.

- [x] **Step 3: Run focused tests and verify GREEN**

Run: `python -m unittest discover -s tests -p test_phuc_than_priority.py -v`

Expected: all priority tests PASS.

- [x] **Step 4: Run the complete test suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

### Task 3: Build and verify desktop artifacts

**Files:**
- Generated: `aTSBot/aTSBot.exe`
- Generated: `aTSBot.zip`
- Generated: `aTSBot-drive.zip`

**Interfaces:**
- Consumes: current desktop source and release data.
- Produces: a timestamped desktop build, unencrypted updater ZIP, and Drive ZIP encrypted with password `aTSBot`.

- [x] **Step 1: Build desktop without uploading**

Run: `python build_product.py --no-upload`

Expected: exit code 0; Nuitka reports the EXE path and both ZIP paths.

- [x] **Step 2: Verify desktop packages**

Confirm both ZIPs contain identical paths and bytes, `aTSBot.zip` is unencrypted, `aTSBot-drive.zip` decrypts with `aTSBot`, and the embedded/staged version matches `aTSBot/version.json`.

### Task 4: Build and verify Android artifact

**Files:**
- Generated: `android/app/build/outputs/apk/debug/aTSBot-<version>-debug.apk`

**Interfaces:**
- Consumes: synchronized Android source, canonical world navigation assets, JDK 17, and Android SDK.
- Produces: debug APK for all configured ABIs.

- [x] **Step 1: Locate JDK 17 and build APK**

Set `JAVA_HOME` to the installed JDK 17 directory, then run from `android/`:

```powershell
.\gradlew.bat assembleDebug
```

Expected: `BUILD SUCCESSFUL` and a timestamped APK under `app/build/outputs/apk/debug/`.

- [x] **Step 2: Verify APK contents and source parity**

Confirm the output APK exists and is non-empty. Confirm the synchronized Android client contains `PHUC_THAN_PROTECTION_PRIORITY` in the same order as desktop and the APK contains the packaged Python application plus `world_nav.json` and `gamedata/Ground.mmg` assets.

### Task 5: Final verification

**Files:**
- Inspect: all modified and generated files.

**Interfaces:**
- Produces: evidence-backed handoff of both platforms.

- [x] **Step 1: Run final tests and diff checks**

Run `python -m unittest discover -s tests -v`, `git diff --check`, and `git status --short --branch`.

Expected: tests PASS, no whitespace errors, generated build artifacts remain ignored, and the pre-existing untracked `aTSBot-drive/` directory is untouched.
