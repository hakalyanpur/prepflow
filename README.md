# Interview Prep Hub

Web dashboard for interview preparation — NeetCode 150, System Design, and Python tips. Zero dependencies — just Python stdlib.

**Live at [prepflow.dev](https://prepflow.dev/)** — hosted on Fly.io.

## Run locally

```bash
python3 tracker.py
```

Opens at [http://localhost:5050](http://localhost:5050).

## Features

- **Weekly Plan** — problems grouped by week with calendar dates, collapsible sections
- **All Problems** — filterable by category, difficulty, status; searchable
- **Review Today** — spaced repetition reminders (1, 2, 4, 8, 16, 30 day intervals)
- **Stats** — LeetCode and System Design stats side by side, progress bars per category, completion %, average solve time
- **System Design** — 28 system design problems from HelloInterview, 14-week plan
- **Python Tips** — 50+ random Python tips with code snippets, shuffled on each load; "Interview Patterns" tag renders your coding patterns guide inline
- Status cycling (pending → done → struggled → review)
- Built-in per-problem stopwatch
- Notes field for key insights per problem
- Light/dark mode toggle
- All data persists to `progress.json` on disk

## How it works

On first run, `tracker.py` parses `../leetcode_study_plan.md` and seeds `progress.json`. After that, all state lives in the JSON file. The "Interview Patterns" view within Python Tips reads from `patterns.md`.
