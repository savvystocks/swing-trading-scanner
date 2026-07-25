# Restore drill - 2026-07-23T00:35:19Z

Source: `C:/Users/savva/AppData/Local/Temp/claude/C--Users-savva-OneDrive-Documents-Swing-Trading/3fb6f3ba-11d1-40b3-89e5-be2d2a4e775f/scratchpad/harvest_20260722_1058.db.gz`  |  Work dir: `/tmp/restore_drill_Gbrrgr` (deleted after)

- PASS: snapshot located (harvest_20260722_1058.db.gz)
- PASS: gunzip clean (no truncation) (89944064 bytes)
- PASS: sqlite integrity_check (ok)
- PASS: tables present with sane row counts (candidates/labels/bid_path: 20129 17663 294234)
- PASS: clean repo clone 
- PASS: poller offline drill on restored DB (DRILL: full chain executed end-to-end on the COPY. Real DB never written.)

VERDICT: RESTORABLE - a working system rebuilds from the off-box backup (6/6 checks).
