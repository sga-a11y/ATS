# Single party controller implementation plan

> **For agentic workers:** Use the existing workspace and test each change before integration. The user explicitly requested continuing the unfinished implementation here.

**Goal:** Remove the global coordinator and make one `PartyEngine` thread own all decisions for its party.

**Architecture:** Login, socket reception and blocking game operations remain executors. `PartyEngine.nhip()` reads state, runs the existing party rules, applies the resulting state changes and assigns cancellable work. No global scan, watcher or account script may independently plan party movement.

**Tech stack:** Python unittest, shared Python core for PC and Android.

**Spec:** User clarification on 24 September 2026 supersedes the older documents retaining the global coordinator. Preserve the game flows in `documents/CORE_FLOW.md`; do not edit that protected document.

## Constraints and review focus

- Preserve all unfinished user changes; work directly on this checkout because those changes are the starting point. Do not build, publish or run live accounts.
- Preserve missing-member, battle, dungeon, event, map and channel rules. Unknown server state is not success.
- Support the existing train, DG, event, city and stand modes before removing their fallback controller.
- Repeated starts/relogin must not create a second controller or leave a stopped worker attached.
- Channel switching uses existing workers, not a second command thread. Tick failures must not fall through to a different decision source.
- Update stale structural tests only where this requested architecture intentionally changes their contract; retain their behavior coverage.

## Tasks

- [x] Add regression tests for one controller, serialized decisions, worker channel execution and restart/relogin.
- [x] Move the party decision into the engine tick. Replace the deciding callback with snapshot/effect adapters and keep the established pure rules.
- [x] Route the remaining supported modes through the engine with bounded actions and preserve manual commands.
- [x] Remove global coordinator/watcher startup and legacy account planning. Keep login/reconnect and protocol helpers.
- [x] Sync Android Python and run the full unittest suite; review finding fixed (independent review limitation recorded below).

## Progress

- Baseline: 472 tests in changed files, one failure caused by the unfinished PC/APK rename. No live game verification performed.
- Architecture audit: global coordinator skips engine parties but is still started; train/city/stand/chaos still use account scripts. Engine snapshots currently invoke a deciding runner callback, and channel commands spawn extra threads.

## Test migration

Removed assertions about the deleted account closures and watcher loops rather than retaining dead production code to satisfy them. Active client/protocol/helper tests are preserved. Behavior is covered by:

- `test_party_engine_nhip`, `test_party_engine_vong`: map/channel/roster order, DG transitions, full-team gates, worker cancellation, bounded retries and shutdown.
- `test_engine_mot_luong`: controller lifecycle, reconnect, channel work, route continuation and PB exits with a disconnected account.
- `test_party_controller_regressions`, `test_party_controller_runner`: no second controller, safe gathering and arrival, foreign-party handling, boss priority, scan execution, login chores and event exit/rewards.
- `test_party_modes`, `test_party_route_engine`: city/stand/solo event actions and whole-party manual routing.
- Channel worker test modules: battle/grace guards, uncertain channels, stale results and overlap.

Retired closure-specific test classes were in: `test_bi_van_khac_di_duong`, `test_du_party_thi_phai_ra_diem_quai`, `test_gom_party_thi_ca_lu_ra_safe`, `test_khong_cho_vo_han_co_cua_leader`, `test_khong_con_bang_bao_cao`, `test_khong_lenh_thi_acc_khong_di`, `test_khong_roi_party_cua_chinh_leader`, `test_kien_tri_tim_kenh_khong_bo_party`, `test_login_ra_safe_truoc_viec_vat`, `test_login_train_khong_tele`, `test_member_don_party_ma`, `test_ra_safe_sau_login_party_tu_chon_map`, `test_o_safe_roi_thi_dung_di_lai`, `test_vong_cho_thoat_khi_co_lenh`, `test_train_khong_ve_thanh`, `test_ra_soat_acc_khong_tu_quyet`, `test_event_thua_chi_tinh_trong_phien`, `test_ngoai_gio_chan_truoc_khi_vao_map_event`, `test_p3_ket_vi_kenh_day`, `test_kenh_phai_hoi_server`, `test_biet_minh_dang_ket_party_nao`, `test_pho_ban_doi_thieu_level`.

## Final review findings

A separate read-only reviewer found that destination retries still used the original
source map after a multi-gate route had reached an intermediate map. The executor
now resumes from the client's observed current map; its regression was observed
failing before the fix and passing afterward. The reviewer subsequently hit its
usage limit, so the independent review did not produce a complete verdict.

Other verified regressions cover manual channel pins, follower position correction,
safe battle warning edges, account option propagation, no-leader event handling,
and follower grace resetting when a route progresses to another map.

## Verification result — 26 September 2026

- Final command: `python -B -m unittest discover -s tests`.
- 3,567 tests, `OK (skipped=9)`, 168.380 seconds, exit code 0.
- PC/APK sync script passed with 29 shared Python files, including the mode and route modules.
- Python syntax and `git diff --check` passed.
- No product EXE/APK build, release, commit, or live game validation was performed.
