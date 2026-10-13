# Invalid Week 6 / Week 7 live locks (archived 2026-10-13)

Both files were built by `scripts/pipeline/build_corrected_successor_lock.py` / `build_corrected_live_lock.py` with the 6A, Task 4 and 6B lineage flags left at their Week 5 defaults. On these locks the rating builder would silently leave out Week 6 play-by-play, and the forecast builder would fail its population check. They are replaced by locks rebuilt with explicit Week 6 lineage flags (Phase 4 of the Week 7 plan).

| File | sha256 |
|---|---|
| successor_lock_w6_v1.json | da69494b58e0e7747a5014d564e8d94701025c09264b57269813cbc790051fa0 |
| successor_lock_w7live_v1.json | a0137d3309ac99e74d7b56fa18797d2d72bdd2462ba43ae6274c5c4bd1f67e8f |
