#!/usr/bin/env python3
"""Interview Prep Hub — Lightweight Web Dashboard

Run:  python tracker.py
Open: http://localhost:5050
"""

import json, os, re, datetime, webbrowser, sys
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 5050
# Week 1 starts on this Monday — adjust if you want a different start date
START_MONDAY = "2026-02-23"
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.json")
MD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "leetcode_study_plan.md")
PATTERNS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patterns.md")
SD_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sd_progress.json")
TIPS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tips.json")

# ---------------------------------------------------------------------------
# Markdown parser — seeds progress.json on first run
# ---------------------------------------------------------------------------

def parse_markdown(path):
    with open(path, "r") as f:
        text = f.read()

    problems = []
    seen = set()
    week = 0
    category = ""

    # Detect week headers
    week_re = re.compile(r"###\s+Week\s+(\d+)")
    # Table row with problem: status Title (id) Difficulty
    prob_re = re.compile(r"(✅|⬜|🔄|❌)\s+(.+?)\s+\((\d+)\)\s+([EMH])")
    # Overflow section category headers
    cat_re = re.compile(r"###\s+(.+)")
    # Overflow table row: | Title (id) | Difficulty | Status |
    overflow_re = re.compile(r"\|\s*(.+?)\s+\((\d+)\)\s*\|\s*(Easy|Medium|Hard)\s*\|\s*(✅|⬜|🔄|❌)\s*\|")

    in_overflow = False
    diff_map = {"Easy": "E", "Medium": "M", "Hard": "H"}
    status_map = {"✅": "done", "⬜": "pending", "🔄": "pending", "❌": "struggled"}

    # Figure out categories from week titles
    week_cat_re = re.compile(r"###\s+Week\s+\d+\s*—\s*(.+)")

    lines = text.split("\n")
    current_cats = []

    for line in lines:
        # Overflow section
        if "Overflow" in line and "Remaining" in line:
            in_overflow = True
            week = 13
            continue

        if in_overflow:
            cm = cat_re.match(line)
            if cm:
                raw = cm.group(1).strip()
                # Clean up overflow category names
                if "Greedy" in raw: category = "Greedy"
                elif "Interval" in raw: category = "Intervals"
                elif "Math" in raw: category = "Math & Geometry"
                elif "Bit" in raw: category = "Bit Manipulation"
                continue
            om = overflow_re.search(line)
            if om:
                title, pid, diff, status = om.group(1).strip(), om.group(2), diff_map[om.group(3)], status_map[om.group(4)]
                if pid not in seen:
                    seen.add(pid)
                    problems.append(make_problem(pid, title, diff, category, week, status))
            continue

        # Week headers
        wm = week_re.search(line)
        if wm:
            week = int(wm.group(1))
            # Extract categories from week title
            wcm = week_cat_re.search(line)
            if wcm:
                cats_raw = wcm.group(1)
                current_cats = [c.strip().replace("(start)", "").replace("(finish)", "").replace("(continue)", "").replace("(remaining)", "").strip() for c in re.split(r"\+|&(?!\s*\w+ing)", cats_raw) if c.strip()]
                # Fix combined names like "Arrays & Hashing"
                current_cats = fix_categories(cats_raw)
            continue

        # Problem rows in weekly tables
        for m in prob_re.finditer(line):
            status_char, title, pid, diff = m.group(1), m.group(2).strip(), m.group(3), m.group(4)
            if pid in seen:
                continue
            seen.add(pid)
            # Determine category from column position or title context
            cat = guess_category(line, title, pid, current_cats)
            problems.append(make_problem(pid, title, diff, cat, week, status_map[status_char]))

    # Add any canonical NeetCode 150 problems missing from the markdown
    missing_canonical = [
        ("4", "Median of Two Sorted Arrays", "H", "Binary Search", 4),
    ]
    for pid, title, diff, cat, wk in missing_canonical:
        if pid not in seen:
            seen.add(pid)
            problems.append(make_problem(pid, title, diff, cat, wk, "pending"))

    return problems


def fix_categories(raw):
    """Parse category string like 'Arrays & Hashing + Two Pointers' into list."""
    cats = []
    # Split on + but preserve & within names
    parts = re.split(r'\s*\+\s*', raw)
    for p in parts:
        p = p.strip()
        for remove in ["(start)", "(finish)", "(continue)", "(remaining)"]:
            p = p.replace(remove, "").strip()
        if p:
            # Normalize category names
            norm = {
                "Heap/Priority Queue": "Heap / Priority Queue",
                "Heap": "Heap / Priority Queue",
            }
            p = norm.get(p, p)
            cats.append(p)
    return cats


def guess_category(line, title, pid, current_cats):
    """Heuristic to assign category based on table column and week context."""
    # Known problem-to-category mappings for ambiguous cases
    known = {
        "787": "Advanced Graphs",  # Cheapest Flights Within K Stops
        "127": "Graphs",  # Word Ladder — canonical NeetCode category
        "91": "2-D DP",
        "53": "Greedy",
        "55": "Greedy",
        "45": "Greedy",
        "134": "Greedy",
        "846": "Greedy",
        "1899": "Greedy",
        "97": "2-D DP",
        "329": "2-D DP",
        "115": "2-D DP",
        "72": "2-D DP",
        "312": "2-D DP",
        "10": "2-D DP",
        "17": "Backtracking",
        "295": "Heap / Priority Queue",
        # Week 6 col2: Tries vs Trees
        "208": "Tries", "211": "Tries", "212": "Tries",
        "98": "Trees", "105": "Trees", "297": "Trees",
    }
    if pid in known:
        return known[pid]

    if not current_cats:
        return "Uncategorized"

    # Check if the line mentions a specific category in parens
    cat_in_line = re.search(r'\(([^)]*(?:Arrays|Hash|Pointer|Stack|Sliding|Binary|Linked|Tree|Trie|Heap|Back|Graph|DP|Greedy)[^)]*)\)', line)
    if cat_in_line:
        raw = cat_in_line.group(1).strip()
        # Normalize
        cat_map = {
            "Arrays & Hashing": "Arrays & Hashing",
            "Two Pointers": "Two Pointers",
            "Stack": "Stack",
            "Sliding Window": "Sliding Window",
            "Binary Search": "Binary Search",
            "Linked List": "Linked List",
            "Trees": "Trees",
            "Tries": "Tries",
            "Tries / Trees": "Tries",
            "Heap": "Heap / Priority Queue",
            "Heap/Priority Queue": "Heap / Priority Queue",
            "Backtracking": "Backtracking",
            "Graphs": "Graphs",
            "Adv Graphs": "Advanced Graphs",
            "1-D DP": "1-D DP",
            "2-D DP": "2-D DP",
            "Greedy": "Greedy",
        }
        for key, val in cat_map.items():
            if key.lower() in raw.lower():
                return val

    # Default to first category if in column 1 area, second if column 2
    # Rough heuristic: if problem appears after a |...| it's column 2
    parts = line.split("|")
    if len(parts) >= 4:
        col1 = parts[2] if len(parts) > 2 else ""
        col2 = parts[3] if len(parts) > 3 else ""
        if pid in col1 and len(current_cats) >= 1:
            return current_cats[0]
        if pid in col2 and len(current_cats) >= 2:
            return current_cats[1]
        if len(current_cats) >= 1:
            return current_cats[0]

    return current_cats[0] if current_cats else "Uncategorized"


def week_date_range(week_num):
    """Return (start, end) date strings for a given week number."""
    start = datetime.date.fromisoformat(START_MONDAY) + datetime.timedelta(weeks=week_num - 1)
    end = start + datetime.timedelta(days=6)
    return start.isoformat(), end.isoformat()


def make_problem(pid, title, diff, category, week, status):
    return {
        "id": pid,
        "title": title,
        "difficulty": diff,
        "category": category,
        "week": week,
        "status": status,
        "attempts": [],
        "next_review": None,
        "review_interval": 1,
        "notes": "",
    }

# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------

_cache = None

def load_data():
    global _cache
    if _cache is not None:
        return _cache
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            _cache = json.load(f)
        return _cache
    # Seed from markdown
    if os.path.exists(MD_FILE):
        _cache = parse_markdown(MD_FILE)
    else:
        _cache = []
    save_data(_cache)
    return _cache


def save_data(problems):
    global _cache
    _cache = problems
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(problems, f, indent=2)
    os.replace(tmp, DATA_FILE)

# ---------------------------------------------------------------------------
# System Design data
# ---------------------------------------------------------------------------

SD_BASE = "https://www.hellointerview.com/learn/system-design/problem-breakdowns"

SD_PROBLEMS = [
    # Easy
    {"id": "sd-1",  "title": "Bit.ly",                "difficulty": "E", "slug": "bitly",          "week": 1},
    {"id": "sd-2",  "title": "Dropbox",               "difficulty": "E", "slug": "dropbox",        "week": 1},
    {"id": "sd-3",  "title": "Local Delivery Service", "difficulty": "E", "slug": "local-delivery", "week": 2},
    {"id": "sd-4",  "title": "News Aggregator",        "difficulty": "E", "slug": "google-news",    "week": 2},
    # Medium
    {"id": "sd-5",  "title": "Ticketmaster",           "difficulty": "M", "slug": "ticketmaster",   "week": 3},
    {"id": "sd-6",  "title": "FB News Feed",           "difficulty": "M", "slug": "fb-news-feed",   "week": 3},
    {"id": "sd-7",  "title": "Tinder",                 "difficulty": "M", "slug": "tinder",         "week": 4},
    {"id": "sd-8",  "title": "LeetCode",               "difficulty": "M", "slug": "leetcode",       "week": 4},
    {"id": "sd-9",  "title": "WhatsApp",               "difficulty": "M", "slug": "whatsapp",       "week": 5},
    {"id": "sd-10", "title": "Yelp",                   "difficulty": "M", "slug": "yelp",           "week": 5},
    {"id": "sd-11", "title": "Strava",                 "difficulty": "M", "slug": "strava",         "week": 6},
    {"id": "sd-12", "title": "Rate Limiter",           "difficulty": "M", "slug": "distributed-rate-limiter", "week": 6},
    {"id": "sd-13", "title": "Online Auction",         "difficulty": "M", "slug": "online-auction", "week": 7},
    {"id": "sd-14", "title": "FB Live Comments",       "difficulty": "M", "slug": "fb-live-comments", "week": 7},
    {"id": "sd-15", "title": "FB Post Search",         "difficulty": "M", "slug": "fb-post-search", "week": 8},
    {"id": "sd-16", "title": "Price Tracking Service", "difficulty": "M", "slug": "price-tracking", "week": 8},
    # Hard
    {"id": "sd-17", "title": "Instagram",              "difficulty": "H", "slug": "instagram",      "week": 9},
    {"id": "sd-18", "title": "YouTube Top K",          "difficulty": "H", "slug": "top-k",          "week": 9},
    {"id": "sd-19", "title": "Uber",                   "difficulty": "H", "slug": "uber",           "week": 10},
    {"id": "sd-20", "title": "Robinhood",              "difficulty": "H", "slug": "robinhood",      "week": 10},
    {"id": "sd-21", "title": "Google Docs",            "difficulty": "H", "slug": "google-docs",    "week": 11},
    {"id": "sd-22", "title": "Distributed Cache",      "difficulty": "H", "slug": "distributed-cache", "week": 11},
    {"id": "sd-23", "title": "YouTube",                "difficulty": "H", "slug": "youtube",        "week": 12},
    {"id": "sd-24", "title": "Job Scheduler",          "difficulty": "H", "slug": "job-scheduler",  "week": 12},
    {"id": "sd-25", "title": "Web Crawler",            "difficulty": "H", "slug": "web-crawler",    "week": 13},
    {"id": "sd-26", "title": "Ad Click Aggregator",    "difficulty": "H", "slug": "ad-click-aggregator", "week": 13},
    {"id": "sd-27", "title": "Payment System",         "difficulty": "H", "slug": "payment-system", "week": 14},
    {"id": "sd-28", "title": "Metrics Monitoring",     "difficulty": "H", "slug": "metrics-monitoring", "week": 14},
]

_sd_cache = None

def load_sd_data():
    global _sd_cache
    if _sd_cache is not None:
        return _sd_cache
    if os.path.exists(SD_DATA_FILE):
        with open(SD_DATA_FILE, "r") as f:
            _sd_cache = json.load(f)
        return _sd_cache
    # Seed
    _sd_cache = []
    for p in SD_PROBLEMS:
        _sd_cache.append({
            "id": p["id"],
            "title": p["title"],
            "difficulty": p["difficulty"],
            "url": f"{SD_BASE}/{p['slug']}",
            "week": p["week"],
            "status": "pending",
            "attempts": [],
            "next_review": None,
            "review_interval": 1,
            "notes": "",
        })
    save_sd_data(_sd_cache)
    return _sd_cache


def save_sd_data(problems):
    global _sd_cache
    _sd_cache = problems
    tmp = SD_DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(problems, f, indent=2)
    os.replace(tmp, SD_DATA_FILE)

# ---------------------------------------------------------------------------
# Python Tips data
# ---------------------------------------------------------------------------

def load_tips():
    """Read tips.json from disk each time (no caching) so newly generated tips
    appear on the next browser refresh without restarting the server."""
    if os.path.exists(TIPS_FILE):
        with open(TIPS_FILE, "r") as f:
            return json.load(f)
    return []

# ---------------------------------------------------------------------------
# HTTP Server
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # quiet logs

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        if self.path == "/":
            return self._html(HTML.replace("__START_MONDAY__", START_MONDAY))
        if self.path == "/api/problems":
            return self._json(load_data())
        if self.path == "/api/sd/problems":
            return self._json(load_sd_data())
        if self.path == "/api/patterns":
            try:
                with open(PATTERNS_FILE, "r") as f:
                    return self._json({"content": f.read()})
            except FileNotFoundError:
                return self._json({"content": "_No patterns file found at:_\n\n`" + PATTERNS_FILE + "`"})
        if self.path == "/api/tips":
            return self._json(load_tips())
        self.send_error(404)

    def do_POST(self):
        # /api/problems/<id>/status
        m = re.match(r"/api/problems/(\d+)/status", self.path)
        if m:
            pid = m.group(1)
            body = self._read_body()
            problems = load_data()
            for p in problems:
                if p["id"] == pid:
                    p["status"] = body.get("status", p["status"])
                    # Update spaced repetition
                    if p["status"] == "done":
                        p["review_interval"] = min(p.get("review_interval", 1) * 2, 30)
                        if p["review_interval"] < 1:
                            p["review_interval"] = 1
                        p["next_review"] = (datetime.date.today() + datetime.timedelta(days=p["review_interval"])).isoformat()
                    elif p["status"] == "struggled":
                        p["review_interval"] = 1
                        p["next_review"] = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
                    elif p["status"] == "review":
                        p["next_review"] = datetime.date.today().isoformat()
                    elif p["status"] == "pending":
                        p["next_review"] = None
                        p["review_interval"] = 1
                    save_data(problems)
                    return self._json(p)
            return self._json({"error": "not found"}, 404)

        # /api/problems/<id>/attempt
        m = re.match(r"/api/problems/(\d+)/attempt", self.path)
        if m:
            pid = m.group(1)
            body = self._read_body()
            problems = load_data()
            for p in problems:
                if p["id"] == pid:
                    p["attempts"].append({
                        "duration_sec": body.get("duration_sec", 0),
                        "date": datetime.date.today().isoformat(),
                        "result": p["status"],
                    })
                    save_data(problems)
                    return self._json(p)
            return self._json({"error": "not found"}, 404)

        # /api/problems/<id>/notes
        m = re.match(r"/api/problems/(\d+)/notes", self.path)
        if m:
            pid = m.group(1)
            body = self._read_body()
            problems = load_data()
            for p in problems:
                if p["id"] == pid:
                    p["notes"] = body.get("notes", "")
                    save_data(problems)
                    return self._json(p)
            return self._json({"error": "not found"}, 404)

        # /api/sd/problems/<id>/status
        m = re.match(r"/api/sd/problems/(sd-\d+)/status", self.path)
        if m:
            pid = m.group(1)
            body = self._read_body()
            problems = load_sd_data()
            for p in problems:
                if p["id"] == pid:
                    p["status"] = body.get("status", p["status"])
                    if p["status"] == "done":
                        p["review_interval"] = min(p.get("review_interval", 1) * 2, 30)
                        if p["review_interval"] < 1: p["review_interval"] = 1
                        p["next_review"] = (datetime.date.today() + datetime.timedelta(days=p["review_interval"])).isoformat()
                    elif p["status"] == "struggled":
                        p["review_interval"] = 1
                        p["next_review"] = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
                    elif p["status"] == "review":
                        p["next_review"] = datetime.date.today().isoformat()
                    elif p["status"] == "pending":
                        p["next_review"] = None
                        p["review_interval"] = 1
                    save_sd_data(problems)
                    return self._json(p)
            return self._json({"error": "not found"}, 404)

        # /api/sd/problems/<id>/attempt
        m = re.match(r"/api/sd/problems/(sd-\d+)/attempt", self.path)
        if m:
            pid = m.group(1)
            body = self._read_body()
            problems = load_sd_data()
            for p in problems:
                if p["id"] == pid:
                    p["attempts"].append({
                        "duration_sec": body.get("duration_sec", 0),
                        "date": datetime.date.today().isoformat(),
                        "result": p["status"],
                    })
                    save_sd_data(problems)
                    return self._json(p)
            return self._json({"error": "not found"}, 404)

        # /api/sd/problems/<id>/notes
        m = re.match(r"/api/sd/problems/(sd-\d+)/notes", self.path)
        if m:
            pid = m.group(1)
            body = self._read_body()
            problems = load_sd_data()
            for p in problems:
                if p["id"] == pid:
                    p["notes"] = body.get("notes", "")
                    save_sd_data(problems)
                    return self._json(p)
            return self._json({"error": "not found"}, 404)

        self.send_error(404)

# ---------------------------------------------------------------------------
# Inline HTML Dashboard
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Interview Prep Hub</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🚀</text></svg>">
<style>
:root, [data-theme="dark"] {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --yellow: #d29922; --red: #f85149; --purple: #bc8cff;
  --hover-row: rgba(88,166,255,.05); --week-hover: #1c2129;
}
[data-theme="light"] {
  --bg: #ffffff; --surface: #f6f8fa; --border: #d0d7de;
  --text: #1f2328; --muted: #656d76; --accent: #0969da;
  --green: #1a7f37; --yellow: #9a6700; --red: #cf222e; --purple: #8250df;
  --hover-row: rgba(9,105,218,.04); --week-hover: #eaeef2;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); }
.container { max-width: 1100px; margin: 0 auto; padding: 16px; }
h1 { font-size: 1.4rem; margin-bottom: 4px; }
.header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.subtitle { color: var(--muted); font-size: .85rem; margin-bottom: 16px; }
.theme-btn { background: var(--surface); border: 1px solid var(--border); color: var(--muted); padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: .85rem; }
.theme-btn:hover { color: var(--text); border-color: var(--muted); }
/* Tabs */
.tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
.tab { padding: 8px 18px; cursor: pointer; color: var(--muted); border-bottom: 2px solid transparent; font-size: .9rem; }
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-color: var(--accent); }
.panel { display: none; }
.panel.active { display: block; }
/* Filters */
.filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.filters select, .filters input { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 6px 10px; border-radius: 6px; font-size: .85rem; }
/* Table */
table { width: 100%; border-collapse: collapse; font-size: .85rem; }
th { text-align: left; padding: 8px; color: var(--muted); border-bottom: 1px solid var(--border); font-weight: 600; }
td { padding: 7px 8px; border-bottom: 1px solid var(--border); }
tr:hover { background: var(--hover-row); }
/* Badges */
.badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: .75rem; font-weight: 600; cursor: pointer; user-select: none; }
.badge-pending { background: var(--border); color: var(--muted); }
.badge-done { background: rgba(63,185,80,.15); color: var(--green); }
.badge-struggled { background: rgba(248,81,73,.15); color: var(--red); }
.badge-review { background: rgba(210,153,34,.15); color: var(--yellow); }
.diff-E { color: var(--green); } .diff-M { color: var(--yellow); } .diff-H { color: var(--red); }
/* Timer */
.timer-btn { background: none; border: 1px solid var(--border); color: var(--muted); padding: 2px 8px; border-radius: 6px; cursor: pointer; font-size: .75rem; }
.timer-btn:hover { border-color: var(--accent); color: var(--accent); }
.timer-btn.running { border-color: var(--red); color: var(--red); }
.timer-display { font-variant-numeric: tabular-nums; font-size: .75rem; color: var(--accent); min-width: 48px; display: inline-block; }
/* Notes */
.notes-row td { padding: 0 8px 8px 8px; border-bottom: 1px solid var(--border); }
.notes-inner { display: flex; gap: 6px; align-items: flex-start; }
.notes-input { flex: 1; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 6px 8px; border-radius: 6px; font-size: .8rem; font-family: inherit; resize: vertical; min-height: 28px; }
.notes-input:focus { outline: none; border-color: var(--accent); }
.notes-save { background: var(--accent); color: #fff; border: none; padding: 5px 10px; border-radius: 6px; font-size: .75rem; cursor: pointer; white-space: nowrap; }
.notes-save:hover { opacity: .85; }
.notes-toggle { background: none; border: none; color: var(--muted); cursor: pointer; font-size: .7rem; padding: 0 4px; }
.notes-toggle:hover { color: var(--accent); }
.notes-preview { font-size: .75rem; color: var(--muted); font-style: italic; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
.notes-preview:hover { color: var(--accent); }
/* Patterns */
.patterns-toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
.patterns-toolbar input { flex: 1; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 6px; font-size: .85rem; }
.patterns-toolbar button { background: var(--surface); border: 1px solid var(--border); color: var(--muted); padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: .85rem; white-space: nowrap; }
.patterns-toolbar button:hover { color: var(--text); border-color: var(--muted); }
.md-body { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px 24px; line-height: 1.7; font-size: .9rem; }
.md-body h1 { font-size: 1.5rem; margin: 24px 0 12px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.md-body h1:first-child { margin-top: 0; }
.md-body h2 { font-size: 1.25rem; margin: 20px 0 10px; color: var(--accent); }
.md-body h3 { font-size: 1.05rem; margin: 16px 0 8px; }
.md-body p { margin: 8px 0; }
.md-body ul, .md-body ol { margin: 8px 0 8px 20px; }
.md-body li { margin: 4px 0; }
.md-body code { background: var(--bg); padding: 2px 6px; border-radius: 4px; font-size: .85em; font-family: 'SF Mono', Menlo, monospace; }
.md-body pre { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 14px; overflow-x: auto; margin: 10px 0; }
.md-body pre code { background: none; padding: 0; font-size: .82em; line-height: 1.5; }
.md-body blockquote { border-left: 3px solid var(--accent); padding-left: 12px; color: var(--muted); margin: 8px 0; }
.md-body strong { color: var(--text); }
.md-body hr { border: none; border-top: 1px solid var(--border); margin: 16px 0; }
.md-body mark { background: rgba(210,153,34,.25); color: var(--text); padding: 1px 3px; border-radius: 2px; }
.md-body table { border-collapse: collapse; margin: 10px 0; width: 100%; }
.md-body th, .md-body td { border: 1px solid var(--border); padding: 6px 10px; text-align: left; }
.md-body th { background: var(--bg); }
/* Python Tips */
.tips-toolbar { display: flex; gap: 8px; margin-bottom: 16px; align-items: center; }
.tips-toolbar button { background: var(--accent); color: #fff; border: none; padding: 8px 18px; border-radius: 6px; cursor: pointer; font-size: .85rem; font-weight: 600; }
.tips-toolbar button:hover { opacity: .85; }
.tips-toolbar .tip-count { color: var(--muted); font-size: .85rem; }
.tips-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
.tip-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
.tip-card .tip-meta { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.tip-card .tip-cat { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: .7rem; font-weight: 600; background: rgba(88,166,255,.12); color: var(--accent); }
.tip-card .tip-title { font-size: .95rem; font-weight: 600; margin-bottom: 8px; }
.tip-card pre { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 12px; overflow-x: auto; margin: 0; }
.tip-card pre code { font-family: 'SF Mono', Menlo, monospace; font-size: .82rem; line-height: 1.5; color: var(--text); }
.tip-card .tip-note { font-size: .82rem; color: var(--muted); margin-top: 8px; line-height: 1.5; }
/* Tag bar for tips filtering */
.tag-bar { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
.tag-btn { display: inline-block; padding: 4px 14px; border-radius: 14px; font-size: .75rem; font-weight: 600; background: rgba(88,166,255,.12); color: var(--accent); border: 1px solid transparent; cursor: pointer; transition: all .15s; }
.tag-btn:hover { border-color: var(--accent); }
.tag-btn.active { background: var(--accent); color: #fff; }
/* Stats */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.stat-card h3 { font-size: .9rem; margin-bottom: 8px; }
.bar-bg { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; background: var(--green); transition: width .3s; }
.stat-nums { display: flex; justify-content: space-between; font-size: .8rem; color: var(--muted); margin-top: 4px; }
.big-stat { text-align: center; padding: 24px; }
.big-stat .num { font-size: 2.5rem; font-weight: 700; color: var(--accent); }
.big-stat .label { color: var(--muted); font-size: .85rem; }
/* Side-by-side stats */
.stats-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
@media (max-width: 800px) { .stats-columns { grid-template-columns: 1fr; } }
/* Week group header */
.week-header { background: var(--surface); padding: 8px 12px; font-weight: 600; font-size: .9rem; border-radius: 6px; margin: 12px 0 6px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
.week-header:hover { background: var(--week-hover); }
.week-header .chevron { transition: transform .2s; font-size: .7rem; color: var(--muted); }
.week-header.collapsed .chevron { transform: rotate(-90deg); }
.week-body.hidden { display: none; }
/* Week in Review */
.week-review { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px 20px; margin-bottom: 20px; }
.week-review-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.week-review-header h2 { font-size: 1.05rem; margin: 0; }
.week-review-header .chevron { transition: transform .2s; font-size: .7rem; color: var(--muted); }
.week-review-header.collapsed .chevron { transform: rotate(-90deg); }
.week-review-body.hidden { display: none; }
.week-review-stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin: 12px 0; }
.week-review-stat { text-align: center; padding: 12px; background: var(--bg); border-radius: 6px; }
.week-review-stat .num { font-size: 1.5rem; font-weight: 700; color: var(--accent); }
.week-review-stat .label { color: var(--muted); font-size: .8rem; }
.week-review-list { margin: 8px 0; }
.week-review-list h3 { font-size: .9rem; color: var(--muted); margin-bottom: 6px; }
.week-review-list ul { list-style: none; padding: 0; }
.week-review-list li { padding: 4px 0; font-size: .85rem; display: flex; align-items: center; gap: 8px; }
/* Links */
a.prob-link { color: var(--text); text-decoration: none; }
a.prob-link:hover { color: var(--accent); text-decoration: underline; }
</style>
</head>
<body>
<div class="container">
<div class="header-row">
  <h1>Interview Prep Hub</h1>
  <button class="theme-btn" onclick="toggleTheme()" id="theme-btn">Light</button>
</div>
<p class="subtitle">NeetCode 150 + System Design + Python Tips — Interactive Study Dashboard</p>

<div class="tabs">
  <div class="tab active" data-tab="weekly">Weekly Plan</div>
  <div class="tab" data-tab="all">All Problems</div>
  <div class="tab" data-tab="review">Review Today</div>
  <div class="tab" data-tab="stats">Stats</div>
  <div class="tab" data-tab="sysdesign">System Design</div>
  <div class="tab" data-tab="pytips">Python Tips</div>
</div>

<div id="weekly" class="panel active"></div>
<div id="all" class="panel"></div>
<div id="review" class="panel"></div>
<div id="stats" class="panel"></div>
<div id="sysdesign" class="panel"></div>
<div id="pytips" class="panel"></div>
</div>

<script>
let problems = [];
let timers = {};  // pid -> {start, interval}
const START_MONDAY = '__START_MONDAY__';

const STATUS_CYCLE = ['pending','done','struggled','review'];

function weekDates(w) {
  const d = new Date(START_MONDAY + 'T00:00:00');
  d.setDate(d.getDate() + (w - 1) * 7);
  const end = new Date(d);
  end.setDate(end.getDate() + 6);
  const fmt = d => d.toLocaleDateString('en-US', {month:'short', day:'numeric'});
  return `${fmt(d)} – ${fmt(end)}`;
}

function getWeekRange(offsetWeeks = 0) {
  const now = new Date();
  const day = now.getDay();
  const monday = new Date(now);
  monday.setDate(now.getDate() - (day === 0 ? 6 : day - 1) + (offsetWeeks * 7));
  monday.setHours(0,0,0,0);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return { start: monday, end: sunday };
}

function getWeekAttempts() {
  const {start, end} = getWeekRange();
  const startStr = start.toISOString().split('T')[0];
  const endStr = end.toISOString().split('T')[0];
  const results = { done: [], struggled: [], totalTime: 0, totalAttempts: 0 };
  const seen = new Set();

  [...problems, ...sdProblems].forEach(p => {
    p.attempts.forEach(a => {
      if (a.date >= startStr && a.date <= endStr) {
        results.totalTime += a.duration_sec;
        results.totalAttempts++;
        if (!seen.has(p.id)) {
          seen.add(p.id);
          if (a.result === 'done') results.done.push(p);
          else if (a.result === 'struggled') results.struggled.push(p);
        }
      }
    });
  });
  return results;
}

let weekReviewCollapsed = localStorage.getItem('weekReviewCollapsed') === 'true';

function toggleWeekReview() {
  weekReviewCollapsed = !weekReviewCollapsed;
  localStorage.setItem('weekReviewCollapsed', weekReviewCollapsed);
  renderReview();
}

function renderWeekReview() {
  const {start, end} = getWeekRange();
  const fmt = d => d.toLocaleDateString('en-US', {month:'short', day:'numeric'});
  const dateRange = `${fmt(start)} – ${fmt(end)}`;
  const wa = getWeekAttempts();

  const hrs = Math.floor(wa.totalTime / 3600);
  const mins = Math.floor((wa.totalTime % 3600) / 60);
  const timeStr = hrs > 0 ? `${hrs}h ${mins}m` : `${mins}m`;

  // Coming up next week: find the next study plan week's pending problems
  const {start: nextStart} = getWeekRange(1);
  const nextStartStr = nextStart.toISOString().split('T')[0];
  // Determine which study plan week corresponds to next week
  const planStart = new Date(START_MONDAY + 'T00:00:00');
  const diffDays = Math.floor((nextStart - planStart) / (1000*60*60*24));
  const nextPlanWeek = Math.floor(diffDays / 7) + 1;
  const comingUp = problems.filter(p => p.week === nextPlanWeek && p.status === 'pending');

  let html = '<div class="week-review">';
  html += `<div class="week-review-header ${weekReviewCollapsed ? 'collapsed' : ''}" onclick="toggleWeekReview()">
    <h2>Week in Review — ${dateRange}</h2>
    <span class="chevron">&#9660;</span>
  </div>`;
  html += `<div class="week-review-body ${weekReviewCollapsed ? 'hidden' : ''}">`;

  // Stat cards
  html += '<div class="week-review-stats">';
  html += `<div class="week-review-stat"><div class="num">${wa.done.length}</div><div class="label">Problems Done</div></div>`;
  html += `<div class="week-review-stat"><div class="num">${wa.struggled.length}</div><div class="label">Struggled</div></div>`;
  html += `<div class="week-review-stat"><div class="num">${wa.totalAttempts}</div><div class="label">Total Attempts</div></div>`;
  html += `<div class="week-review-stat"><div class="num">${timeStr}</div><div class="label">Time Invested</div></div>`;
  html += '</div>';

  // Completed list
  if (wa.done.length) {
    html += '<div class="week-review-list"><h3>Completed</h3><ul>';
    wa.done.forEach(p => {
      html += `<li><span class="diff-${p.difficulty}">${{E:'E',M:'M',H:'H'}[p.difficulty]}</span> ${p.title}</li>`;
    });
    html += '</ul></div>';
  }

  // Struggled list
  if (wa.struggled.length) {
    html += '<div class="week-review-list"><h3>Need More Practice</h3><ul>';
    wa.struggled.forEach(p => {
      html += `<li><span class="diff-${p.difficulty}">${{E:'E',M:'M',H:'H'}[p.difficulty]}</span> ${p.title}</li>`;
    });
    html += '</ul></div>';
  }

  // Coming up
  if (comingUp.length) {
    html += `<div class="week-review-list"><h3>Coming Up (Week ${nextPlanWeek})</h3><ul>`;
    comingUp.forEach(p => {
      html += `<li><span class="diff-${p.difficulty}">${{E:'E',M:'M',H:'H'}[p.difficulty]}</span> ${p.title}</li>`;
    });
    html += '</ul></div>';
  }

  html += '</div></div>';
  return html;
}

async function fetchProblems() {
  const r = await fetch('/api/problems');
  problems = await r.json();
  render();
}

async function setStatus(pid, status) {
  await fetch(`/api/problems/${pid}/status`, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({status})
  });
  const p = problems.find(x => x.id === pid);
  if (p) {
    p.status = status;
    if (status === 'done') {
      p.review_interval = Math.min((p.review_interval || 1) * 2, 30);
      const d = new Date(); d.setDate(d.getDate() + p.review_interval);
      p.next_review = d.toISOString().split('T')[0];
    } else if (status === 'struggled') {
      p.review_interval = 1;
      const d = new Date(); d.setDate(d.getDate() + 1);
      p.next_review = d.toISOString().split('T')[0];
    } else if (status === 'pending') {
      p.next_review = null; p.review_interval = 1;
    }
  }
  render();
}

function cycleStatus(pid) {
  const p = problems.find(x => x.id === pid);
  if (!p) return;
  const i = STATUS_CYCLE.indexOf(p.status);
  const next = STATUS_CYCLE[(i + 1) % STATUS_CYCLE.length];
  setStatus(pid, next);
}

function badgeHTML(p) {
  return `<span class="badge badge-${p.status}" onclick="cycleStatus('${p.id}')">${p.status}</span>`;
}

function diffHTML(d) {
  const labels = {E:'Easy',M:'Medium',H:'Hard'};
  return `<span class="diff-${d}">${labels[d]||d}</span>`;
}

function timerHTML(p) {
  const running = !!timers[p.id];
  return `<span class="timer-display" id="td-${p.id}">${running ? '' : ''}</span>
    <button class="timer-btn ${running?'running':''}" onclick="toggleTimer('${p.id}')">${running?'Stop':'Start'}</button>`;
}

function toggleTimer(pid) {
  if (timers[pid]) {
    // Stop
    const elapsed = Math.floor((Date.now() - timers[pid].start) / 1000);
    clearInterval(timers[pid].interval);
    delete timers[pid];
    // Log attempt
    fetch(`/api/problems/${pid}/attempt`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({duration_sec: elapsed})
    });
    const p = problems.find(x => x.id === pid);
    if (p) p.attempts.push({duration_sec: elapsed, date: new Date().toISOString().split('T')[0], result: p.status});
    render();
  } else {
    // Start
    const start = Date.now();
    const iv = setInterval(() => {
      const el = document.getElementById(`td-${pid}`);
      if (el) {
        const s = Math.floor((Date.now() - start) / 1000);
        el.textContent = `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
      }
    }, 250);
    timers[pid] = {start, interval: iv};
    render();
  }
}

function fmtTime(sec) {
  if (!sec) return '-';
  return `${Math.floor(sec/60)}m ${sec%60}s`;
}

function lcUrl(p) {
  const slug = p.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  return `https://leetcode.com/problems/${slug}/`;
}

const expandedNotes = new Set();

function notesHTML(p) {
  const note = p.notes || '';
  if (expandedNotes.has(p.id)) {
    return `<div class="notes-inner">
      <textarea class="notes-input" id="notes-${p.id}" rows="2">${note.replace(/</g,'&lt;')}</textarea>
      <button class="notes-save" onclick="saveNotes('${p.id}')">Save</button>
    </div>`;
  }
  if (note) {
    return `<span class="notes-preview" onclick="openNotes('${p.id}')" title="${note.replace(/"/g,'&quot;')}">${note.replace(/</g,'&lt;')}</span>`;
  }
  return `<button class="notes-toggle" onclick="openNotes('${p.id}')">+ add</button>`;
}

function openNotes(pid) {
  expandedNotes.add(pid);
  render();
  const el = document.getElementById('notes-' + pid);
  if (el) el.focus();
}

async function saveNotes(pid) {
  const el = document.getElementById('notes-' + pid);
  if (!el) return;
  const notes = el.value.trim();
  await fetch(`/api/problems/${pid}/notes`, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({notes})
  });
  const p = problems.find(x => x.id === pid);
  if (p) p.notes = notes;
  expandedNotes.delete(pid);
  render();
}

function problemRow(p) {
  const lastAttempt = p.attempts.length ? fmtTime(p.attempts[p.attempts.length-1].duration_sec) : '-';
  return `<tr>
    <td>${p.id}</td>
    <td><a class="prob-link" href="${lcUrl(p)}" target="_blank" rel="noopener">${p.title}</a></td>
    <td>${diffHTML(p.difficulty)}</td>
    <td>${p.category}</td>
    <td>${badgeHTML(p)}</td>
    <td>${notesHTML(p)}</td>
    <td>${lastAttempt}</td>
    <td>${timerHTML(p)}</td>
  </tr>`;
}

function tableHeader() {
  return `<table><thead><tr><th>#</th><th>Title</th><th>Diff</th><th>Category</th><th>Status</th><th>Notes</th><th>Last Time</th><th>Timer</th></tr></thead><tbody>`;
}

const collapsedWeeks = new Set();

function renderWeekly() {
  const el = document.getElementById('weekly');
  const weeks = {};
  problems.forEach(p => { (weeks[p.week] = weeks[p.week]||[]).push(p); });
  let html = '';
  Object.keys(weeks).sort((a,b)=>a-b).forEach(w => {
    const label = w == 13 ? 'Overflow' : `Week ${w} · ${weekDates(Number(w))}`;
    const done = weeks[w].filter(p=>p.status==='done').length;
    const total = weeks[w].length;
    const collapsed = collapsedWeeks.has(w);
    const pct = Math.round(done/total*100);
    html += `<div class="week-header ${collapsed?'collapsed':''}" onclick="toggleWeek('${w}')">
      <span>${label} — ${done}/${total} done (${pct}%)</span>
      <span class="chevron">&#9660;</span>
    </div>`;
    html += `<div class="week-body ${collapsed?'hidden':''}">`;
    html += tableHeader();
    weeks[w].forEach(p => html += problemRow(p));
    html += '</tbody></table></div>';
  });
  el.innerHTML = html;
}

function toggleWeek(w) {
  if (collapsedWeeks.has(w)) collapsedWeeks.delete(w);
  else collapsedWeeks.add(w);
  renderWeekly();
}

let filterState = { cat: '', diff: '', status: '', search: '' };
let allInitialized = false;

function renderAll() {
  const el = document.getElementById('all');
  if (!allInitialized) {
    const cats = [...new Set(problems.map(p=>p.category))].sort();
    const diffs = ['E','M','H'];
    const statuses = ['pending','done','struggled','review'];

    let html = `<div class="filters">
      <select id="f-cat"><option value="">All Categories</option>${cats.map(c=>`<option>${c}</option>`).join('')}</select>
      <select id="f-diff"><option value="">All Difficulties</option>${diffs.map(d=>`<option value="${d}">${{E:'Easy',M:'Medium',H:'Hard'}[d]}</option>`).join('')}</select>
      <select id="f-status"><option value="">All Statuses</option>${statuses.map(s=>`<option>${s}</option>`).join('')}</select>
      <input id="f-search" placeholder="Search title..." />
    </div>
    <div id="all-table"></div>`;
    el.innerHTML = html;

    document.getElementById('f-cat').onchange = e => { filterState.cat = e.target.value; filterAll(); };
    document.getElementById('f-diff').onchange = e => { filterState.diff = e.target.value; filterAll(); };
    document.getElementById('f-status').onchange = e => { filterState.status = e.target.value; filterAll(); };
    document.getElementById('f-search').oninput = e => { filterState.search = e.target.value; filterAll(); };
    allInitialized = true;
  }
  filterAll();
}

function filterAll() {
  const cat = filterState.cat;
  const diff = filterState.diff;
  const status = filterState.status;
  const q = filterState.search.toLowerCase();
  let filtered = problems.filter(p =>
    (!cat || p.category === cat) &&
    (!diff || p.difficulty === diff) &&
    (!status || p.status === status) &&
    (!q || p.title.toLowerCase().includes(q) || p.id.includes(q))
  );
  let html = tableHeader();
  filtered.forEach(p => html += problemRow(p));
  html += '</tbody></table>';
  document.getElementById('all-table').innerHTML = html;
}

function renderReview() {
  const el = document.getElementById('review');
  let html = renderWeekReview();
  const today = new Date().toISOString().split('T')[0];
  const due = problems.filter(p => p.next_review && p.next_review <= today);
  const sdDue = sdProblems.filter(p => p.next_review && p.next_review <= today);
  if (!due.length && !sdDue.length) {
    html += '<p style="color:var(--muted);padding:24px;text-align:center">No problems due for review today. Nice!</p>';
    el.innerHTML = html;
    return;
  }
  if (due.length) {
    html += `<p style="margin-bottom:8px;color:var(--muted)"><strong>Coding</strong> — ${due.length} due</p>`;
    html += tableHeader();
    due.forEach(p => html += problemRow(p));
    html += '</tbody></table>';
  }
  if (sdDue.length) {
    html += `<p style="margin:16px 0 8px;color:var(--muted)"><strong>System Design</strong> — ${sdDue.length} due</p>`;
    html += `<table><thead><tr><th>Problem</th><th>Diff</th><th>Status</th><th>Notes</th><th>Last Time</th><th>Timer</th></tr></thead><tbody>`;
    sdDue.forEach(p => html += sdRow(p));
    html += '</tbody></table>';
  }
  el.innerHTML = html;
}

async function renderStats() {
  const el = document.getElementById('stats');
  const cats = {};
  let totalDone = 0, totalTime = 0, totalAttempts = 0;
  problems.forEach(p => {
    if (!cats[p.category]) cats[p.category] = {total:0, done:0};
    cats[p.category].total++;
    if (p.status === 'done') { cats[p.category].done++; totalDone++; }
    p.attempts.forEach(a => { totalTime += a.duration_sec; totalAttempts++; });
  });

  const avgTime = totalAttempts ? Math.round(totalTime / totalAttempts) : 0;
  const pct = problems.length ? Math.round(totalDone/problems.length*100) : 0;

  // --- Build LeetCode column ---
  let lcHtml = `<div class="stats-col">`;
  lcHtml += `<h2 style="margin-bottom:12px;font-size:1.1rem;">LeetCode</h2>`;
  lcHtml += `<div class="stat-grid">
    <div class="stat-card big-stat"><div class="num">${pct}%</div><div class="label">${totalDone} / ${problems.length} completed</div></div>
    <div class="stat-card big-stat"><div class="num">${fmtTime(avgTime)}</div><div class="label">avg solve time (${totalAttempts} attempts)</div></div>
  </div><div class="stat-grid" style="margin-top:12px">`;

  Object.keys(cats).sort().forEach(c => {
    const {total, done} = cats[c];
    const p = Math.round(done/total*100);
    lcHtml += `<div class="stat-card">
      <h3>${c}</h3>
      <div class="bar-bg"><div class="bar-fill" style="width:${p}%"></div></div>
      <div class="stat-nums"><span>${done}/${total}</span><span>${p}%</span></div>
    </div>`;
  });
  lcHtml += '</div></div>';

  // --- Build System Design column ---
  if (!sdProblems.length) await fetchSD();
  let sdDone = 0, sdTime = 0, sdAttempts = 0;
  const sdDiffs = {E:{total:0,done:0}, M:{total:0,done:0}, H:{total:0,done:0}};
  sdProblems.forEach(p => {
    if (sdDiffs[p.difficulty]) { sdDiffs[p.difficulty].total++; }
    if (p.status === 'done') { sdDone++; if (sdDiffs[p.difficulty]) sdDiffs[p.difficulty].done++; }
    p.attempts.forEach(a => { sdTime += a.duration_sec; sdAttempts++; });
  });
  const sdAvg = sdAttempts ? Math.round(sdTime / sdAttempts) : 0;
  const sdPct = sdProblems.length ? Math.round(sdDone / sdProblems.length * 100) : 0;

  let sdHtml = `<div class="stats-col">`;
  sdHtml += `<h2 style="margin-bottom:12px;font-size:1.1rem;">System Design</h2>`;
  sdHtml += `<div class="stat-grid">
    <div class="stat-card big-stat"><div class="num">${sdPct}%</div><div class="label">${sdDone} / ${sdProblems.length} completed</div></div>
    <div class="stat-card big-stat"><div class="num">${fmtTime(sdAvg)}</div><div class="label">avg solve time (${sdAttempts} attempts)</div></div>
  </div><div class="stat-grid" style="margin-top:12px">`;

  const diffLabels = {E:'Easy', M:'Medium', H:'Hard'};
  const diffColors = {E:'var(--green)', M:'var(--yellow)', H:'var(--red)'};
  ['E','M','H'].forEach(d => {
    const {total, done} = sdDiffs[d];
    const p = total ? Math.round(done/total*100) : 0;
    sdHtml += `<div class="stat-card">
      <h3>${diffLabels[d]}</h3>
      <div class="bar-bg"><div class="bar-fill" style="width:${p}%;background:${diffColors[d]}"></div></div>
      <div class="stat-nums"><span>${done}/${total}</span><span>${p}%</span></div>
    </div>`;
  });
  sdHtml += '</div></div>';

  el.innerHTML = `<div class="stats-columns">${lcHtml}${sdHtml}</div>`;
}

function activeTab() {
  const t = document.querySelector('.tab.active');
  return t ? t.dataset.tab : 'weekly';
}

// --- Minimal markdown to HTML renderer ---
function md2html(src) {
  let html = '';
  const lines = src.split('\n');
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    // Code blocks
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim();
      let code = '';
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        code += lines[i] + '\n';
        i++;
      }
      i++; // skip closing ```
      html += `<pre><code>${esc(code.replace(/\n$/,''))}</code></pre>`;
      continue;
    }
    // Headers
    const hm = line.match(/^(#{1,6})\s+(.*)/);
    if (hm) { const id = hm[2].toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,''); html += `<h${hm[1].length} id="${id}">${inline(hm[2])}</h${hm[1].length}>`; i++; continue; }
    // HR
    if (/^[-*_]{3,}\s*$/.test(line)) { html += '<hr>'; i++; continue; }
    // Blockquote
    if (line.startsWith('> ')) { html += `<blockquote>${inline(line.slice(2))}</blockquote>`; i++; continue; }
    // Table
    if (line.includes('|') && i + 1 < lines.length && /^\|?[\s-:|]+\|/.test(lines[i+1])) {
      let t = '<table><thead><tr>';
      line.split('|').filter(c=>c.trim()).forEach(c => t += `<th>${inline(c.trim())}</th>`);
      t += '</tr></thead><tbody>';
      i += 2; // skip header + separator
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        t += '<tr>';
        lines[i].split('|').filter(c=>c.trim()).forEach(c => t += `<td>${inline(c.trim())}</td>`);
        t += '</tr>';
        i++;
      }
      html += t + '</tbody></table>';
      continue;
    }
    // Unordered list
    if (/^[\s]*[-*]\s/.test(line)) {
      html += '<ul>';
      while (i < lines.length && /^[\s]*[-*]\s/.test(lines[i])) {
        html += `<li>${inline(lines[i].replace(/^[\s]*[-*]\s+/,''))}</li>`;
        i++;
      }
      html += '</ul>';
      continue;
    }
    // Ordered list
    if (/^[\s]*\d+\.\s/.test(line)) {
      html += '<ol>';
      while (i < lines.length && /^[\s]*\d+\.\s/.test(lines[i])) {
        html += `<li>${inline(lines[i].replace(/^[\s]*\d+\.\s+/,''))}</li>`;
        i++;
      }
      html += '</ol>';
      continue;
    }
    // Empty line
    if (!line.trim()) { i++; continue; }
    // Paragraph
    html += `<p>${inline(line)}</p>`;
    i++;
  }
  return html;
}
function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function inline(s) {
  return s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/_(.+?)_/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, href) =>
      href.startsWith('#') ? `<a href="${href}">${text}</a>` : `<a href="${href}" target="_blank">${text}</a>`
    );
}

// --- Patterns tab ---
let patternsCache = '';
let patternsSearch = '';

async function loadPatterns() {
  const r = await fetch('/api/patterns');
  const d = await r.json();
  patternsCache = d.content || '';
  renderPatternsContent();
}

function renderPatternsContent() {
  const el = document.getElementById('patterns-body');
  if (!el) return;
  let src = patternsCache;
  if (patternsSearch.trim()) {
    // Filter to sections that match search
    const q = patternsSearch.toLowerCase();
    const sections = src.split(/(?=^#{1,3}\s)/m);
    const matched = sections.filter(s => s.toLowerCase().includes(q));
    src = matched.length ? matched.join('\n') : '_No matches found._';
  }
  el.innerHTML = md2html(src);
  // Highlight search term
  if (patternsSearch.trim()) {
    const q = patternsSearch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    el.innerHTML = el.innerHTML.replace(
      new RegExp(`(${q})`, 'gi'),
      '<mark>$1</mark>'
    );
  }
}

// --- Python Tips ---
let pythonTips = [];
let currentTips = [];
let activeCategory = '';

async function fetchTips() {
  const r = await fetch('/api/tips');
  pythonTips = await r.json();
}

function shuffleTips() {
  activeCategory = '';
  const shuffled = [...pythonTips].sort(() => Math.random() - 0.5);
  currentTips = shuffled.slice(0, 5);
  renderPyTips();
}

function filterByCategory(cat) {
  if (activeCategory === cat) {
    activeCategory = '';
    const shuffled = [...pythonTips].sort(() => Math.random() - 0.5);
    currentTips = shuffled.slice(0, 5);
  } else {
    activeCategory = cat;
    if (cat !== 'Interview Patterns') {
      currentTips = pythonTips.filter(t => t.cat === cat);
    }
  }
  renderPyTips();
}

async function renderPyTips() {
  const el = document.getElementById('pytips');
  if (!pythonTips.length) await fetchTips();
  if (!currentTips.length && !activeCategory) {
    const shuffled = [...pythonTips].sort(() => Math.random() - 0.5);
    currentTips = shuffled.slice(0, 5);
  }

  const cats = [...new Set(pythonTips.map(t => t.cat))].sort();
  // Ensure Interview Patterns tag exists even if no tips have that cat
  if (!cats.includes('Interview Patterns')) cats.push('Interview Patterns');
  cats.sort();

  const isPatterns = activeCategory === 'Interview Patterns';
  const countLabel = isPatterns
    ? 'Showing interview patterns'
    : activeCategory
      ? `${currentTips.length} / ${pythonTips.length} tips in "${activeCategory}"`
      : `${pythonTips.length} tips · showing 5`;

  let html = `<div class="tips-toolbar">
    <button onclick="shuffleTips()">Shuffle Tips</button>
    <span class="tip-count">${countLabel}</span>
  </div>
  <div class="tag-bar">
    <span class="tag-btn ${activeCategory===''?'active':''}" onclick="shuffleTips()">All</span>
    ${cats.map(c => `<span class="tag-btn ${activeCategory===c?'active':''}" onclick="filterByCategory('${c.replace(/'/g,"\\'")}')">${c}</span>`).join('')}
  </div>`;

  if (isPatterns) {
    html += `<div class="patterns-toolbar">
      <input id="p-search" placeholder="Search patterns..." value="${patternsSearch.replace(/"/g,'&quot;')}" />
    </div>
    <div class="md-body" id="patterns-body"></div>`;
    el.innerHTML = html;
    document.getElementById('p-search').oninput = e => {
      patternsSearch = e.target.value;
      renderPatternsContent();
    };
    if (!patternsCache) await loadPatterns();
    else renderPatternsContent();
  } else {
    html += `<div class="tips-grid" id="tips-grid"></div>`;
    el.innerHTML = html;
    renderTipsContent();
  }
}

function renderTipsContent() {
  const el = document.getElementById('tips-grid');
  if (!el) return;
  el.innerHTML = currentTips.map(t => `<div class="tip-card">
    <div class="tip-meta"><span class="tip-cat">${t.cat}</span></div>
    <div class="tip-title">${t.title}</div>
    <pre><code>${t.code.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</code></pre>
    ${t.note ? `<div class="tip-note">${t.note}</div>` : ''}
  </div>`).join('');
}

// --- System Design tab ---
let sdProblems = [];
let sdTimers = {};
const sdCollapsed = new Set();
const sdExpandedNotes = new Set();

async function fetchSD() {
  const r = await fetch('/api/sd/problems');
  sdProblems = await r.json();
}

async function sdSetStatus(pid, status) {
  await fetch(`/api/sd/problems/${pid}/status`, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({status})
  });
  const p = sdProblems.find(x => x.id === pid);
  if (p) {
    p.status = status;
    if (status === 'done') {
      p.review_interval = Math.min((p.review_interval || 1) * 2, 30);
      const d = new Date(); d.setDate(d.getDate() + p.review_interval);
      p.next_review = d.toISOString().split('T')[0];
    } else if (status === 'struggled') {
      p.review_interval = 1;
      const d = new Date(); d.setDate(d.getDate() + 1);
      p.next_review = d.toISOString().split('T')[0];
    } else if (status === 'pending') {
      p.next_review = null; p.review_interval = 1;
    }
  }
  renderSD();
}

function sdCycleStatus(pid) {
  const p = sdProblems.find(x => x.id === pid);
  if (!p) return;
  const i = STATUS_CYCLE.indexOf(p.status);
  sdSetStatus(pid, STATUS_CYCLE[(i + 1) % STATUS_CYCLE.length]);
}

function sdToggleTimer(pid) {
  if (sdTimers[pid]) {
    const elapsed = Math.floor((Date.now() - sdTimers[pid].start) / 1000);
    clearInterval(sdTimers[pid].interval);
    delete sdTimers[pid];
    fetch(`/api/sd/problems/${pid}/attempt`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({duration_sec: elapsed})
    });
    const p = sdProblems.find(x => x.id === pid);
    if (p) p.attempts.push({duration_sec: elapsed, date: new Date().toISOString().split('T')[0], result: p.status});
    renderSD();
  } else {
    const start = Date.now();
    const iv = setInterval(() => {
      const el = document.getElementById(`sd-td-${pid}`);
      if (el) {
        const s = Math.floor((Date.now() - start) / 1000);
        el.textContent = `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
      }
    }, 250);
    sdTimers[pid] = {start, interval: iv};
    renderSD();
  }
}

function sdOpenNotes(pid) {
  sdExpandedNotes.add(pid);
  renderSD();
  const el = document.getElementById('sd-notes-' + pid);
  if (el) el.focus();
}

async function sdSaveNotes(pid) {
  const el = document.getElementById('sd-notes-' + pid);
  if (!el) return;
  const notes = el.value.trim();
  await fetch(`/api/sd/problems/${pid}/notes`, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({notes})
  });
  const p = sdProblems.find(x => x.id === pid);
  if (p) p.notes = notes;
  sdExpandedNotes.delete(pid);
  renderSD();
}

function sdRow(p) {
  const lastAttempt = p.attempts.length ? fmtTime(p.attempts[p.attempts.length-1].duration_sec) : '-';
  const running = !!sdTimers[p.id];
  const note = p.notes || '';
  let notesHtml;
  if (sdExpandedNotes.has(p.id)) {
    notesHtml = `<div class="notes-inner"><textarea class="notes-input" id="sd-notes-${p.id}" rows="2">${note.replace(/</g,'&lt;')}</textarea><button class="notes-save" onclick="sdSaveNotes('${p.id}')">Save</button></div>`;
  } else if (note) {
    notesHtml = `<span class="notes-preview" onclick="sdOpenNotes('${p.id}')" title="${note.replace(/"/g,'&quot;')}">${note.replace(/</g,'&lt;')}</span>`;
  } else {
    notesHtml = `<button class="notes-toggle" onclick="sdOpenNotes('${p.id}')">+ add</button>`;
  }
  return `<tr>
    <td><a class="prob-link" href="${p.url}" target="_blank" rel="noopener">${p.title}</a></td>
    <td>${diffHTML(p.difficulty)}</td>
    <td><span class="badge badge-${p.status}" onclick="sdCycleStatus('${p.id}')">${p.status}</span></td>
    <td>${notesHtml}</td>
    <td>${lastAttempt}</td>
    <td><span class="timer-display" id="sd-td-${p.id}">${running?'':''}</span>
      <button class="timer-btn ${running?'running':''}" onclick="sdToggleTimer('${p.id}')">${running?'Stop':'Start'}</button></td>
  </tr>`;
}

function renderSD() {
  const el = document.getElementById('sysdesign');
  if (!sdProblems.length) { fetchSD().then(renderSD); return; }

  const weeks = {};
  sdProblems.forEach(p => { (weeks[p.week] = weeks[p.week]||[]).push(p); });
  const totalDone = sdProblems.filter(p => p.status === 'done').length;
  const pct = Math.round(totalDone / sdProblems.length * 100);

  let html = `<p style="margin-bottom:12px;color:var(--muted)">28 problems · 14 weeks · 2/week — ${totalDone}/${sdProblems.length} done (${pct}%)</p>`;

  Object.keys(weeks).sort((a,b)=>a-b).forEach(w => {
    const label = `Week ${w} · ${weekDates(Number(w))}`;
    const done = weeks[w].filter(p => p.status === 'done').length;
    const total = weeks[w].length;
    const collapsed = sdCollapsed.has(w);
    const wpct = Math.round(done/total*100);
    html += `<div class="week-header ${collapsed?'collapsed':''}" onclick="sdToggleWeek('${w}')">
      <span>${label} — ${done}/${total} done (${wpct}%)</span>
      <span class="chevron">&#9660;</span>
    </div>`;
    html += `<div class="week-body ${collapsed?'hidden':''}">`;
    html += `<table><thead><tr><th>Problem</th><th>Diff</th><th>Status</th><th>Notes</th><th>Last Time</th><th>Timer</th></tr></thead><tbody>`;
    weeks[w].forEach(p => html += sdRow(p));
    html += '</tbody></table></div>';
  });
  el.innerHTML = html;
}

function sdToggleWeek(w) {
  if (sdCollapsed.has(w)) sdCollapsed.delete(w);
  else sdCollapsed.add(w);
  renderSD();
}

function render() {
  const tab = activeTab();
  if (tab === 'weekly') renderWeekly();
  else if (tab === 'all') renderAll();
  else if (tab === 'review') renderReview();
  else if (tab === 'stats') renderStats();
  else if (tab === 'sysdesign') renderSD();
  else if (tab === 'pytips') renderPyTips();
}

// Tabs
document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    document.getElementById(t.dataset.tab).classList.add('active');
    localStorage.setItem('activeTab', t.dataset.tab);
    render();
  });
});

// Restore saved tab
const savedTab = localStorage.getItem('activeTab');
if (savedTab) {
  const tabEl = document.querySelector(`.tab[data-tab="${savedTab}"]`);
  if (tabEl) {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
    tabEl.classList.add('active');
    document.getElementById(savedTab).classList.add('active');
  }
}

function toggleTheme() {
  const html = document.documentElement;
  const curr = html.getAttribute('data-theme') || 'dark';
  const next = curr === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  document.getElementById('theme-btn').textContent = next === 'dark' ? 'Light' : 'Dark';
  localStorage.setItem('theme', next);
}
// Restore saved theme
const saved = localStorage.getItem('theme');
if (saved) {
  document.documentElement.setAttribute('data-theme', saved);
  document.getElementById('theme-btn').textContent = saved === 'dark' ? 'Light' : 'Dark';
}

fetchProblems();
</script>
</body>
</html>"""

if __name__ == "__main__":
    data = load_data()
    print(f"Loaded {len(data)} problems")
    print(f"Data file: {DATA_FILE}")
    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("localhost", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Dashboard: {url}")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
