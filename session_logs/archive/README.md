# Session Logs Archive

This directory contains archived daily session logs that have been aggregated into weekly summaries.

## Structure

- `daily/` - Original daily session logs (preserved for reference)
  - Organized by date: `YYYY-MM-DD/`
  - Contains 26 date folders from Sept 25 - Oct 30, 2025

## Weekly Summaries

Daily logs from this archive have been aggregated into weekly summaries located in `../weekly/`:

| Week            | Dates                    | Sessions | Summary File         |
| --------------- | ------------------------ | -------- | -------------------- |
| Sept 23-29      | 2025-09-25 to 2025-09-29 | 7        | `2025-09-23_week.md` |
| Sept 30 - Oct 6 | 2025-09-30 to 2025-10-06 | 14       | `2025-09-30_week.md` |
| Oct 7-13        | 2025-10-07 to 2025-10-11 | 7        | `2025-10-07_week.md` |
| Oct 14-20       | 2025-10-17 to 2025-10-20 | 13       | `2025-10-14_week.md` |
| Oct 21-27       | 2025-10-21 to 2025-10-24 | 17       | `2025-10-21_week.md` |
| Oct 28 - Nov 3  | 2025-10-28 to 2025-10-30 | 4        | `2025-10-28_week.md` |

**Total**: 62 sessions across 25 days

## Archived On

2025-11-22

## Restoration

If you need to restore the original daily logs to the main `session_logs/` directory:

```bash
cd session_logs
cp -r archive/daily/* .
```

Note: This will not overwrite the weekly summaries in `weekly/`.
