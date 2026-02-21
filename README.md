# LeetCode Tracker

Local web dashboard for the NeetCode 150 study plan. Zero dependencies — just Python stdlib.

## Run

```bash
python3 tracker.py
```

Opens at [http://localhost:5050](http://localhost:5050).

## Features

- **Weekly Plan** — problems grouped by week with calendar dates, collapsible sections
- **All Problems** — filterable by category, difficulty, status; searchable
- **Review Today** — spaced repetition reminders (1, 2, 4, 8, 16, 30 day intervals)
- **Stats** — progress bars per category, completion %, average solve time
- **Patterns** — renders your Python coding patterns guide (live from disk)
- Status cycling (pending → done → struggled → review)
- Built-in per-problem stopwatch
- Notes field for key insights per problem
- Light/dark mode toggle
- All data persists to `progress.json` on disk

## How it works

On first run, `tracker.py` parses `../leetcode_study_plan.md` and seeds `progress.json`. After that, all state lives in the JSON file. The patterns tab reads from `~/Documents/hk-organizer/Python/coding-patterns-guide.md`.
