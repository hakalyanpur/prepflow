#!/usr/bin/env python3
"""Interview Prep Hub — Lightweight Web Dashboard

Run:  python tracker.py
Open: http://localhost:5050
"""

import json, os, re, datetime, webbrowser, sys, urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 5050
# Week 1 starts on this Monday — adjust if you want a different start date
START_MONDAY = "2026-02-23"
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.json")
MD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "leetcode_study_plan.md")
SD_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sd_progress.json")
REF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python_ref.json")
MECH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python_mechanics.json")

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
    # Medium — reordered for thematic synergy with coding topics
    {"id": "sd-12", "title": "Rate Limiter",           "difficulty": "M", "slug": "distributed-rate-limiter", "week": 3},
    {"id": "sd-14", "title": "FB Live Comments",       "difficulty": "M", "slug": "fb-live-comments", "week": 3},
    {"id": "sd-8",  "title": "LeetCode",               "difficulty": "M", "slug": "leetcode",       "week": 4},
    {"id": "sd-16", "title": "Price Tracking Service", "difficulty": "M", "slug": "price-tracking", "week": 4},
    {"id": "sd-6",  "title": "FB News Feed",           "difficulty": "M", "slug": "fb-news-feed",   "week": 5},
    {"id": "sd-15", "title": "FB Post Search",         "difficulty": "M", "slug": "fb-post-search", "week": 5},
    {"id": "sd-10", "title": "Yelp",                   "difficulty": "M", "slug": "yelp",           "week": 6},
    {"id": "sd-11", "title": "Strava",                 "difficulty": "M", "slug": "strava",         "week": 6},
    {"id": "sd-5",  "title": "Ticketmaster",           "difficulty": "M", "slug": "ticketmaster",   "week": 7},
    {"id": "sd-13", "title": "Online Auction",         "difficulty": "M", "slug": "online-auction", "week": 7},
    {"id": "sd-7",  "title": "Tinder",                 "difficulty": "M", "slug": "tinder",         "week": 8},
    {"id": "sd-9",  "title": "WhatsApp",               "difficulty": "M", "slug": "whatsapp",       "week": 8},
    # Hard — reordered for thematic synergy with coding topics
    {"id": "sd-19", "title": "Uber",                   "difficulty": "H", "slug": "uber",           "week": 9},
    {"id": "sd-25", "title": "Web Crawler",            "difficulty": "H", "slug": "web-crawler",    "week": 9},
    {"id": "sd-21", "title": "Google Docs",            "difficulty": "H", "slug": "google-docs",    "week": 10},
    {"id": "sd-22", "title": "Distributed Cache",      "difficulty": "H", "slug": "distributed-cache", "week": 10},
    {"id": "sd-18", "title": "YouTube Top K",          "difficulty": "H", "slug": "top-k",          "week": 11},
    {"id": "sd-26", "title": "Ad Click Aggregator",    "difficulty": "H", "slug": "ad-click-aggregator", "week": 11},
    {"id": "sd-24", "title": "Job Scheduler",          "difficulty": "H", "slug": "job-scheduler",  "week": 12},
    {"id": "sd-20", "title": "Robinhood",              "difficulty": "H", "slug": "robinhood",      "week": 12},
    {"id": "sd-27", "title": "Payment System",         "difficulty": "H", "slug": "payment-system", "week": 13},
    {"id": "sd-28", "title": "Metrics Monitoring",     "difficulty": "H", "slug": "metrics-monitoring", "week": 13},
    {"id": "sd-17", "title": "Instagram",              "difficulty": "H", "slug": "instagram",      "week": 14},
    {"id": "sd-23", "title": "YouTube",                "difficulty": "H", "slug": "youtube",        "week": 14},
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
# Python Reference data
# ---------------------------------------------------------------------------

def load_ref():
    """Read python_ref.json from disk (no caching) so edits appear on refresh."""
    if os.path.exists(REF_FILE):
        with open(REF_FILE, "r") as f:
            return json.load(f)
    return {"topics": []}

def load_mech():
    """Read python_mechanics.json from disk (no caching) so edits appear on refresh."""
    if os.path.exists(MECH_FILE):
        with open(MECH_FILE, "r") as f:
            return json.load(f)
    return {"topics": []}

# ---------------------------------------------------------------------------
# LeetCode Sync — slug mapping, config, fetch, sync
# ---------------------------------------------------------------------------

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Hardcoded mapping: LeetCode title slug -> problem ID in progress.json
# The NeetCode 150 list is static, so this is the most reliable matching strategy.
SLUG_TO_ID = {
    "contains-duplicate": "217",
    "valid-anagram": "242",
    "two-sum": "1",
    "group-anagrams": "49",
    "top-k-frequent-elements": "347",
    "product-of-array-except-self": "238",
    "valid-sudoku": "36",
    "encode-and-decode-strings": "271",
    "longest-consecutive-sequence": "128",
    "valid-palindrome": "125",
    "two-sum-ii-input-array-is-sorted": "167",
    "3sum": "15",
    "container-with-most-water": "11",
    "trapping-rain-water": "42",
    "best-time-to-buy-and-sell-stock": "121",
    "longest-substring-without-repeating-characters": "3",
    "longest-repeating-character-replacement": "424",
    "permutation-in-string": "567",
    "minimum-window-substring": "76",
    "sliding-window-maximum": "239",
    "valid-parentheses": "20",
    "min-stack": "155",
    "evaluate-reverse-polish-notation": "150",
    "generate-parentheses": "22",
    "daily-temperatures": "739",
    "car-fleet": "853",
    "largest-rectangle-in-histogram": "84",
    "binary-search": "704",
    "search-a-2d-matrix": "74",
    "koko-eating-bananas": "875",
    "find-minimum-in-rotated-sorted-array": "153",
    "search-in-rotated-sorted-array": "33",
    "time-based-key-value-store": "981",
    "median-of-two-sorted-arrays": "4",
    "reverse-linked-list": "206",
    "merge-two-sorted-lists": "21",
    "reorder-list": "143",
    "remove-nth-node-from-end-of-list": "19",
    "copy-list-with-random-pointer": "138",
    "add-two-numbers": "2",
    "linked-list-cycle": "141",
    "find-the-duplicate-number": "287",
    "lru-cache": "146",
    "merge-k-sorted-lists": "23",
    "reverse-nodes-in-k-group": "25",
    "invert-binary-tree": "226",
    "maximum-depth-of-binary-tree": "104",
    "diameter-of-binary-tree": "543",
    "balanced-binary-tree": "110",
    "same-tree": "100",
    "subtree-of-another-tree": "572",
    "lowest-common-ancestor-of-a-binary-search-tree": "235",
    "binary-tree-level-order-traversal": "102",
    "binary-tree-right-side-view": "199",
    "count-good-nodes-in-binary-tree": "1448",
    "validate-binary-search-tree": "98",
    "kth-smallest-element-in-a-bst": "230",
    "construct-binary-tree-from-preorder-and-inorder-traversal": "105",
    "binary-tree-maximum-path-sum": "124",
    "serialize-and-deserialize-binary-tree": "297",
    "implement-trie-prefix-tree": "208",
    "design-add-and-search-words-data-structure": "211",
    "word-search-ii": "212",
    "kth-largest-element-in-a-stream": "703",
    "last-stone-weight": "1046",
    "k-closest-points-to-origin": "973",
    "kth-largest-element-in-an-array": "215",
    "task-scheduler": "621",
    "design-twitter": "355",
    "find-median-from-data-stream": "295",
    "subsets": "78",
    "combination-sum": "39",
    "permutations": "46",
    "subsets-ii": "90",
    "combination-sum-ii": "40",
    "word-search": "79",
    "palindrome-partitioning": "131",
    "letter-combinations-of-a-phone-number": "17",
    "n-queens": "51",
    "number-of-islands": "200",
    "clone-graph": "133",
    "max-area-of-island": "695",
    "pacific-atlantic-water-flow": "417",
    "surrounded-regions": "130",
    "rotting-oranges": "994",
    "walls-and-gates": "286",
    "course-schedule": "207",
    "course-schedule-ii": "210",
    "redundant-connection": "684",
    "number-of-connected-components-in-an-undirected-graph": "323",
    "graph-valid-tree": "261",
    "word-ladder": "127",
    "reconstruct-itinerary": "332",
    "min-cost-to-connect-all-points": "1584",
    "network-delay-time": "743",
    "swim-in-rising-water": "778",
    "cheapest-flights-within-k-stops": "787",
    "alien-dictionary": "269",
    "climbing-stairs": "70",
    "min-cost-climbing-stairs": "746",
    "house-robber": "198",
    "house-robber-ii": "213",
    "longest-palindromic-substring": "5",
    "palindromic-substrings": "647",
    "decode-ways": "91",
    "coin-change": "322",
    "maximum-product-subarray": "152",
    "word-break": "139",
    "longest-increasing-subsequence": "300",
    "partition-equal-subset-sum": "416",
    "unique-paths": "62",
    "longest-common-subsequence": "1143",
    "best-time-to-buy-and-sell-stock-with-cooldown": "309",
    "coin-change-ii": "518",
    "target-sum": "494",
    "interleaving-string": "97",
    "longest-increasing-path-in-a-matrix": "329",
    "distinct-subsequences": "115",
    "edit-distance": "72",
    "burst-balloons": "312",
    "regular-expression-matching": "10",
    "maximum-subarray": "53",
    "jump-game": "55",
    "jump-game-ii": "45",
    "gas-station": "134",
    "hand-of-straights": "846",
    "merge-triplets-to-form-target-triplet": "1899",
    "partition-labels": "763",
    "valid-parenthesis-string": "678",
    "insert-interval": "57",
    "merge-intervals": "56",
    "non-overlapping-intervals": "435",
    "meeting-rooms": "252",
    "meeting-rooms-ii": "253",
    "minimum-interval-to-include-each-query": "1851",
    "rotate-image": "48",
    "spiral-matrix": "54",
    "set-matrix-zeroes": "73",
    "happy-number": "202",
    "plus-one": "66",
    "powx-n": "50",
    "multiply-strings": "43",
    "detect-squares": "2013",
    "single-number": "136",
    "number-of-1-bits": "191",
    "counting-bits": "338",
    "reverse-bits": "190",
    "missing-number": "268",
    "sum-of-two-integers": "371",
    "reverse-integer": "7",
}

ID_TO_SLUG = {v: k for k, v in SLUG_TO_ID.items()}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


def fetch_leetcode_accepted(username):
    """Fetch recent accepted submissions from LeetCode's public GraphQL API."""
    query = {
        "query": """
            query recentAcSubmissions($username: String!, $limit: Int!) {
                recentAcSubmissionList(username: $username, limit: $limit) {
                    titleSlug
                    title
                    timestamp
                }
            }
        """,
        "variables": {"username": username, "limit": 300},
    }
    data = json.dumps(query).encode()
    req = urllib.request.Request(
        "https://leetcode.com/graphql/",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
            "Origin": "https://leetcode.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 400:
            return {"error": f"User '{username}' not found or profile is private"}
        return {"error": f"LeetCode API error: HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"error": f"Network error: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

    subs = result.get("data", {}).get("recentAcSubmissionList")
    if subs is None:
        errors = result.get("errors", [])
        msg = errors[0].get("message", "Unknown error") if errors else "User not found or profile is private"
        return {"error": msg}
    return {"submissions": subs}


def sync_from_leetcode(username):
    """Match LeetCode accepted submissions to progress.json and mark as done.

    Only considers submissions made on or after START_MONDAY so that problems
    solved before the study plan aren't auto-marked done.

    Uses a persistent cache of previously-seen accepted slugs in config.json
    so that problems which drop off LeetCode's limited recent-submissions
    window are still recognized on subsequent syncs.
    """
    result = fetch_leetcode_accepted(username)
    if "error" in result:
        return result

    # Filter to submissions on or after study plan start
    cutoff = int(datetime.datetime.combine(
        datetime.date.fromisoformat(START_MONDAY),
        datetime.time.min,
    ).timestamp())
    recent_subs = [s for s in result["submissions"] if int(s["timestamp"]) >= cutoff]
    skipped = len(result["submissions"]) - len(recent_subs)

    # Merge fresh API slugs with previously cached slugs
    cfg = load_config()
    cached_slugs = set(cfg.get("synced_slugs", []))
    api_slugs = {s["titleSlug"] for s in recent_subs}
    accepted_slugs = api_slugs | cached_slugs

    # Also build normalized title set for fallback matching
    accepted_titles_norm = {}
    for s in recent_subs:
        norm = re.sub(r"[^a-z0-9]", "", s["title"].lower())
        accepted_titles_norm[norm] = s["titleSlug"]

    problems = load_data()
    synced = []
    already_done = 0
    all_matched_slugs = set(cached_slugs)  # start with existing cache

    for p in problems:
        pid = p["id"]
        slug = ID_TO_SLUG.get(pid)
        matched = False

        if slug and slug in accepted_slugs:
            matched = True
        else:
            # Fallback: normalized title matching
            norm_title = re.sub(r"[^a-z0-9]", "", p["title"].lower())
            if norm_title in accepted_titles_norm:
                matched = True
                slug = accepted_titles_norm[norm_title]

        if matched:
            if slug:
                all_matched_slugs.add(slug)
            if p["status"] == "done":
                already_done += 1
            else:
                p["status"] = "done"
                p["review_interval"] = min(p.get("review_interval", 1) * 2, 30)
                if p["review_interval"] < 1:
                    p["review_interval"] = 1
                p["next_review"] = (datetime.date.today() + datetime.timedelta(days=p["review_interval"])).isoformat()
                synced.append(p["title"])

    if synced:
        save_data(problems)

    # Persist the merged slug cache
    cfg["synced_slugs"] = sorted(all_matched_slugs)
    save_config(cfg)

    return {
        "synced": len(synced),
        "already_done": already_done,
        "total_accepted": len(api_slugs),
        "skipped_before_plan": skipped,
        "matched_titles": synced,
    }


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
        if self.path == "/api/pyref":
            return self._json(load_ref())
        if self.path == "/api/mechanics":
            return self._json(load_mech())
        if self.path == "/api/config":
            return self._json(load_config())
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

        # /api/problems/<id>/week
        m = re.match(r"/api/problems/(\d+)/week", self.path)
        if m:
            pid = m.group(1)
            body = self._read_body()
            week = body.get("week")
            if week is None or not isinstance(week, int) or week < 1 or week > 14:
                return self._json({"error": "Invalid week (1-14)"}, 400)
            problems = load_data()
            for p in problems:
                if p["id"] == pid:
                    p["week"] = week
                    save_data(problems)
                    return self._json(p)
            return self._json({"error": "not found"}, 404)

        # /api/sd/problems/<id>/week
        m = re.match(r"/api/sd/problems/(sd-\d+)/week", self.path)
        if m:
            pid = m.group(1)
            body = self._read_body()
            week = body.get("week")
            if week is None or not isinstance(week, int) or week < 1 or week > 14:
                return self._json({"error": "Invalid week (1-14)"}, 400)
            problems = load_sd_data()
            for p in problems:
                if p["id"] == pid:
                    p["week"] = week
                    save_sd_data(problems)
                    return self._json(p)
            return self._json({"error": "not found"}, 404)

        # /api/sync/leetcode
        if self.path == "/api/sync/leetcode":
            body = self._read_body()
            username = body.get("username", "").strip()
            if not username:
                return self._json({"error": "Username is required"}, 400)
            # Save username to config
            cfg = load_config()
            cfg["leetcode_username"] = username
            save_config(cfg)
            # Invalidate problems cache so sync reads fresh data
            global _cache
            _cache = None
            result = sync_from_leetcode(username)
            return self._json(result)

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
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css" id="hljs-dark">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css" id="hljs-light" disabled>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/python.min.js"></script>
<style>
:root, [data-theme="dark"] {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --yellow: #d29922; --red: #f85149; --purple: #bc8cff;
  --hover-row: rgba(88,166,255,.06); --week-hover: #1c2128;
}
[data-theme="light"] {
  --bg: #ffffff; --surface: #f6f8fa; --border: #d0d7de;
  --text: #1f2328; --muted: #656d76; --accent: #0969da;
  --green: #1a7f37; --yellow: #9a6700; --red: #cf222e; --purple: #8250df;
  --hover-row: rgba(9,105,218,.06); --week-hover: #eaeef2;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 15px; background: var(--bg); color: var(--text); }
code, pre, .mono { font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', Menlo, Consolas, monospace; }
.container { max-width: 1100px; margin: 0 auto; padding: 16px; }
.sticky-header { position: sticky; top: 0; z-index: 100; background: var(--bg); padding-bottom: 8px; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
h1 { font-size: 1.4rem; margin-bottom: 4px; }
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.theme-btn { background: var(--surface); border: 1px solid var(--border); color: var(--muted); padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: .85rem; }
.theme-btn:hover { color: var(--text); border-color: var(--muted); }
/* Tabs */
.tabs { display: flex; gap: 0; align-items: center; }
.tab { padding: 6px 14px; cursor: pointer; color: var(--muted); border-bottom: 2px solid transparent; font-size: .85rem; }
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-color: var(--accent); }
.panel { display: none; }
.panel.active { display: block; }
/* Filters */
.filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.filters select, .filters input { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 6px 10px; border-radius: 6px; font-size: .85rem; }
/* Table */
table { width: 100%; border-collapse: collapse; font-size: .9rem; }
th { text-align: left; padding: 8px; color: var(--muted); border-bottom: 1px solid var(--border); font-weight: 600; cursor: pointer; user-select: none; white-space: nowrap; }
th:hover { color: var(--text); }
th .sort-arrow { font-size: .65rem; margin-left: 3px; opacity: .4; }
th .sort-arrow.active { opacity: 1; color: var(--accent); }
td { padding: 7px 8px; border-bottom: 1px solid var(--border); }
tr:hover { background: var(--hover-row); }
tr.last-solved { background: rgba(248,81,73,.06); }
tr.last-solved td:first-child { border-left: 3px solid var(--red); padding-left: 9px; }
tr.last-solved .last-solved-marker { color: var(--red); font-size: .7rem; margin-right: 4px; }
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
/* Collapsible cards (Python Toolkit & Patterns) */
.cards-search { display: block; width: 100%; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 6px; font-size: .9rem; margin-bottom: 12px; }
.cards-search:focus { outline: none; border-color: var(--accent); }
.card { border: 1px solid var(--border); border-radius: 8px; margin-bottom: 8px; overflow: hidden; }
.card-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; cursor: pointer; background: var(--surface); font-weight: 600; font-size: .95rem; user-select: none; }
.card-header:hover { background: var(--week-hover); }
.card-header .chevron { transition: transform .2s; font-size: .7rem; color: var(--muted); }
.card-header.collapsed .chevron { transform: rotate(-90deg); }
.card-body { padding: 8px 16px 16px; }
.card-body.hidden { display: none; }
.card-item { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; margin-bottom: 6px; }
.card-item-label { font-weight: 600; font-size: .85rem; margin-bottom: 4px; }
.card-item pre { background: var(--bg) !important; border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; overflow-x: auto; margin: 4px 0 0; }
.card-item pre code.hljs { background: transparent !important; padding: 0; }
.card-item pre code { font-size: .85rem; line-height: 1.5; color: var(--text); }
.card-item-note { font-size: .8rem; color: var(--muted); margin-top: 4px; font-style: italic; }
/* Progress donuts */
.progress-summary { display: flex; gap: 24px; align-items: center; padding: 12px 16px; }
.donut-wrap { display: flex; align-items: center; gap: 10px; }
.donut-label { font-size: .8rem; color: var(--muted); }
.donut-label .donut-title { font-weight: 600; color: var(--text); font-size: .85rem; }
.donut-label .donut-num { font-size: 1.1rem; font-weight: 700; color: var(--accent); }
.progress-summary { cursor: pointer; user-select: none; }
.progress-breakdown { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 6px 16px; padding: 10px 16px 12px; border-top: 1px solid var(--border); }
.progress-breakdown.hidden { display: none; }
.breakdown-item { display: flex; align-items: center; gap: 8px; font-size: .8rem; }
.breakdown-bar { flex: 1; height: 5px; background: var(--border); border-radius: 3px; overflow: hidden; }
.breakdown-fill { height: 100%; border-radius: 3px; background: var(--green); }
.breakdown-pct { color: var(--muted); min-width: 28px; text-align: right; }
/* Sync pill in header */
.sync-pill { display: flex; align-items: center; gap: 6px; }
.sync-pill button { padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface); color: var(--muted); cursor: pointer; font-size: 1.1rem; line-height: 1; }
.sync-pill button:hover { color: var(--text); border-color: var(--muted); }
.sync-pill button:disabled { opacity: .5; cursor: not-allowed; }
/* Week picker */
.week-num { cursor: pointer; position: relative; }
.week-num:hover { color: var(--accent); }
.week-picker { position: absolute; top: 100%; left: 0; z-index: 200; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 6px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; box-shadow: 0 4px 12px rgba(0,0,0,.3); min-width: 140px; }
.week-picker span { padding: 4px 8px; border-radius: 4px; cursor: pointer; text-align: center; font-size: .8rem; color: var(--text); }
.week-picker span:hover { background: var(--accent); color: #fff; }
.week-picker span.current { background: var(--border); font-weight: 600; }
/* Week group header */
.week-header { background: var(--surface); padding: 8px 12px; font-weight: 600; font-size: .9rem; border-radius: 6px; margin: 12px 0 6px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
.week-header:hover { background: var(--week-hover); }
.week-header .chevron { transition: transform .2s; font-size: .7rem; color: var(--muted); }
.week-header.collapsed .chevron { transform: rotate(-90deg); }
.week-body.hidden { display: none; }
/* Week in Review */
/* Today marker */
tr.today-item { background: color-mix(in srgb, var(--accent) 8%, transparent); }
tr.today-item td:first-child { border-left: 3px solid var(--accent); }
/* Links */
a.prob-link { color: var(--text); text-decoration: none; }
a.prob-link:hover { color: var(--accent); text-decoration: underline; }
</style>
</head>
<body>
<div class="container">
<div class="sticky-header">
<div class="header-row">
  <div class="tabs">
    <div class="tab active" data-tab="weekly">Weekly Plan</div>
    <div class="tab" data-tab="pytips">Python Toolkit</div>
    <div class="tab" data-tab="mechanics">Patterns</div>
  </div>
  <div class="header-actions">
    <div class="sync-pill" id="sync-pill">
      <button id="lc-sync-btn" onclick="syncLeetCode()" title="Sync from LeetCode">⟳</button>
    </div>
    <button class="theme-btn" onclick="toggleTheme()" id="theme-btn">Light</button>
  </div>
</div>
</div>

<div id="weekly" class="panel active"></div>
<div id="pytips" class="panel"></div>
<div id="mechanics" class="panel"></div>
<footer style="text-align:center;padding:32px 0 16px;color:var(--border);font-size:.7rem;letter-spacing:.5px">Interview Prep Hub</footer>
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

function getCurrentPlanWeek() {
  const planStart = new Date(START_MONDAY + 'T00:00:00');
  const now = new Date();
  now.setHours(0,0,0,0);
  const diffDays = Math.floor((now - planStart) / (1000*60*60*24));
  return Math.max(1, Math.floor(diffDays / 7) + 1);
}

function isWeekend() {
  const day = new Date().getDay();
  return day === 0 || day === 6;
}

const todayIds = new Set();

async function fetchProblems() {
  const r = await fetch('/api/problems');
  problems = await r.json();
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

function probUrl(p) {
  return p.url || lcUrl(p);
}

let lastSolvedId = null;

function computeLastSolved() {
  let latest = null;
  [...problems, ...sdProblems].forEach(p => {
    if (p.status === 'done' && p.next_review) {
      if (!latest || p.next_review >= latest.next_review) latest = p;
    }
  });
  lastSolvedId = latest ? latest.id : null;
}

function showWeekPicker(event, pid, currentWeek) {
  event.stopPropagation();
  // Remove any existing picker
  document.querySelectorAll('.week-picker').forEach(el => el.remove());
  const picker = document.createElement('div');
  picker.className = 'week-picker';
  for (let w = 1; w <= 14; w++) {
    const s = document.createElement('span');
    s.textContent = w === 13 ? 'OF' : `W${w}`;
    s.title = w === 13 ? 'Overflow' : `Week ${w}`;
    if (w === currentWeek) s.classList.add('current');
    s.onclick = (e) => { e.stopPropagation(); moveToWeek(pid, w); };
    picker.appendChild(s);
  }
  event.currentTarget.style.position = 'relative';
  event.currentTarget.appendChild(picker);
  // Close on outside click
  const close = (e) => { if (!picker.contains(e.target)) { picker.remove(); document.removeEventListener('click', close); } };
  setTimeout(() => document.addEventListener('click', close), 0);
}

async function moveToWeek(pid, week) {
  document.querySelectorAll('.week-picker').forEach(el => el.remove());
  const isSD = pid.startsWith('sd-');
  const url = isSD ? `/api/sd/problems/${pid}/week` : `/api/problems/${pid}/week`;
  await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({week})
  });
  // Update local data and re-render
  const arr = isSD ? sdProblems : problems;
  const p = arr.find(x => x.id === pid);
  if (p) p.week = week;
  render();
}

// --- Sorting ---
const sortState = {}; // key: context string, value: {col, asc}
const diffOrder = {E:0, M:1, H:2};
const statusOrder = {pending:0, struggled:1, review:2, done:3};

function getSort(ctx) { return sortState[ctx] || {col: null, asc: true}; }

function toggleSort(ctx, col, renderFn) {
  const cur = getSort(ctx);
  if (cur.col === col) sortState[ctx] = {col, asc: !cur.asc};
  else sortState[ctx] = {col, asc: true};
  renderFn();
}

function sortArrow(ctx, col) {
  const s = getSort(ctx);
  if (s.col !== col) return '<span class="sort-arrow">⇅</span>';
  return `<span class="sort-arrow active">${s.asc ? '▲' : '▼'}</span>`;
}

function lastTime(p) {
  return p.attempts.length ? p.attempts[p.attempts.length-1].duration_sec : -1;
}

function sortProblems(arr, ctx) {
  const s = getSort(ctx);
  if (!s.col) return arr;
  const sorted = [...arr];
  const dir = s.asc ? 1 : -1;
  sorted.sort((a, b) => {
    let va, vb;
    switch(s.col) {
      case '#': va = a._rowNum||0; vb = b._rowNum||0; break;
      case 'title': case 'problem': va = a.title.toLowerCase(); vb = b.title.toLowerCase(); break;
      case 'diff': va = diffOrder[a.difficulty]||0; vb = diffOrder[b.difficulty]||0; break;
      case 'category': va = (a.category||'').toLowerCase(); vb = (b.category||'').toLowerCase(); break;
      case 'status': va = statusOrder[a.status]||0; vb = statusOrder[b.status]||0; break;
      case 'last time': va = lastTime(a); vb = lastTime(b); break;
      default: return 0;
    }
    if (va < vb) return -dir;
    if (va > vb) return dir;
    return 0;
  });
  return sorted;
}

function sortableTh(ctx, col, label, renderFn) {
  return `<th onclick="toggleSort('${ctx}','${col}',${renderFn})">${label} ${sortArrow(ctx, col)}</th>`;
}

function problemRow(p) {
  const lastAttempt = p.attempts.length ? fmtTime(p.attempts[p.attempts.length-1].duration_sec) : '-';
  const isSD = p.id.startsWith('sd-');
  const cat = isSD ? 'System Design' : p.category;
  const statusHtml = isSD
    ? `<span class="badge badge-${p.status}" onclick="sdCycleStatus('${p.id}')">${p.status}</span>`
    : badgeHTML(p);
  const notesCol = isSD ? sdNotesHTML(p) : notesHTML(p);
  const timerCol = isSD ? sdTimerHTML(p) : timerHTML(p);
  const isLast = p.id === lastSolvedId;
  const marker = isLast ? '<span class="last-solved-marker">&#9654;</span>' : '';
  const numCell = `<span class="week-num" onclick="showWeekPicker(event,'${p.id}',${p.week})" title="Move to another week">${marker}${p._rowNum || ''}</span>`;
  const isToday = todayIds.has(p.id);
  const trClass = [isLast && 'last-solved', isToday && 'today-item'].filter(Boolean).join(' ');
  return `<tr${trClass ? ` class="${trClass}"` : ''}>
    <td>${numCell}</td>
    <td><a class="prob-link" href="${probUrl(p)}" target="_blank" rel="noopener">${p.title}</a></td>
    <td>${diffHTML(p.difficulty)}</td>
    <td>${cat}</td>
    <td>${statusHtml}</td>
    <td>${notesCol}</td>
    <td>${lastAttempt}</td>
    <td>${timerCol}</td>
  </tr>`;
}

function tableHeader(ctx, renderFn) {
  return `<table><thead><tr>${sortableTh(ctx,'#','#',renderFn)}${sortableTh(ctx,'title','Title',renderFn)}${sortableTh(ctx,'diff','Diff',renderFn)}${sortableTh(ctx,'category','Category',renderFn)}${sortableTh(ctx,'status','Status',renderFn)}<th>Notes</th>${sortableTh(ctx,'last time','Last Time',renderFn)}<th>Timer</th></tr></thead><tbody>`;
}

function sdTableHeader(ctx, renderFn) {
  return `<table><thead><tr>${sortableTh(ctx,'problem','Problem',renderFn)}${sortableTh(ctx,'diff','Diff',renderFn)}${sortableTh(ctx,'status','Status',renderFn)}<th>Notes</th>${sortableTh(ctx,'last time','Last Time',renderFn)}<th>Timer</th></tr></thead><tbody>`;
}

const collapsedWeeks = new Set();
let breakdownOpen = false;

function toggleBreakdown() {
  breakdownOpen = !breakdownOpen;
  renderWeekly();
}

function donutSvg(done, total, color) {
  const r = 24, c = 2 * Math.PI * r;
  const pct = total ? done / total : 0;
  const offset = c * (1 - pct);
  return `<svg width="56" height="56" viewBox="0 0 56 56">
    <circle cx="28" cy="28" r="${r}" fill="none" stroke="var(--border)" stroke-width="5"/>
    <circle cx="28" cy="28" r="${r}" fill="none" stroke="${color}" stroke-width="5"
      stroke-dasharray="${c}" stroke-dashoffset="${offset}" stroke-linecap="round"
      transform="rotate(-90 28 28)" style="transition:stroke-dashoffset .4s"/>
    <text x="28" y="30" text-anchor="middle" font-size="11" font-weight="700" fill="var(--text)">${total ? Math.round(pct*100) : 0}%</text>
  </svg>`;
}

function renderWeekly() {
  const el = document.getElementById('weekly');

  // Compute today's queue
  const curWeek = getCurrentPlanWeek();
  todayIds.clear();
  const weekend = isWeekend();
  const curWeekProblems = problems.filter(p => p.week === curWeek);
  if (weekend) {
    // Weekend: mark done problems for review
    curWeekProblems.filter(p => p.status === 'done').forEach(p => todayIds.add(p.id));
  } else {
    // Weekday: mark next 2 pending
    curWeekProblems.filter(p => p.status === 'pending').slice(0, 2).forEach(p => todayIds.add(p.id));
  }

  // Auto-expand current week, collapse others (only on first render)
  if (!collapsedWeeks._initialized) {
    const allWeeks = [...new Set([...problems.map(p=>p.week), ...sdProblems.map(p=>p.week)])];
    allWeeks.forEach(w => { if (String(w) !== String(curWeek)) collapsedWeeks.add(String(w)); });
    collapsedWeeks._initialized = true;
  }

  // Compute progress
  const lcDone = problems.filter(p => p.status === 'done').length;
  const sdDone = sdProblems.filter(p => p.status === 'done').length;

  // Category breakdown
  const cats = {};
  problems.forEach(p => {
    if (!cats[p.category]) cats[p.category] = {total:0, done:0};
    cats[p.category].total++;
    if (p.status === 'done') cats[p.category].done++;
  });
  const sdDiffs = {E:{total:0,done:0}, M:{total:0,done:0}, H:{total:0,done:0}};
  const diffLabels = {E:'Easy', M:'Medium', H:'Hard'};
  const diffColors = {E:'var(--green)', M:'var(--yellow)', H:'var(--red)'};
  sdProblems.forEach(p => {
    if (sdDiffs[p.difficulty]) { sdDiffs[p.difficulty].total++; }
    if (p.status === 'done' && sdDiffs[p.difficulty]) sdDiffs[p.difficulty].done++;
  });

  let breakdownHtml = `<div class="progress-breakdown${breakdownOpen ? '' : ' hidden'}">`;
  Object.keys(cats).sort().forEach(c => {
    const {total, done} = cats[c];
    const p = total ? Math.round(done/total*100) : 0;
    breakdownHtml += `<div class="breakdown-item"><span>${c}</span><div class="breakdown-bar"><div class="breakdown-fill" style="width:${p}%"></div></div><span class="breakdown-pct">${done}/${total}</span></div>`;
  });
  breakdownHtml += `<div style="grid-column:1/-1;margin-top:4px;font-size:.75rem;color:var(--muted);font-weight:600">System Design</div>`;
  ['E','M','H'].forEach(d => {
    const {total, done} = sdDiffs[d];
    const p = total ? Math.round(done/total*100) : 0;
    breakdownHtml += `<div class="breakdown-item"><span>${diffLabels[d]}</span><div class="breakdown-bar"><div class="breakdown-fill" style="width:${p}%;background:${diffColors[d]}"></div></div><span class="breakdown-pct">${done}/${total}</span></div>`;
  });
  breakdownHtml += '</div>';

  let html = `<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;margin-bottom:16px;">
    <div class="progress-summary" onclick="toggleBreakdown()">
      <div class="donut-wrap">${donutSvg(lcDone, problems.length, 'var(--green)')}
        <div class="donut-label"><div class="donut-title">LeetCode</div><div class="donut-num">${lcDone}/${problems.length}</div></div>
      </div>
      <div class="donut-wrap">${donutSvg(sdDone, sdProblems.length, 'var(--accent)')}
        <div class="donut-label"><div class="donut-title">System Design</div><div class="donut-num">${sdDone}/${sdProblems.length}</div></div>
      </div>
      <span class="chevron" style="margin-left:auto;font-size:.7rem;color:var(--muted);transition:transform .2s;${breakdownOpen ? '' : 'transform:rotate(-90deg)'}">▼</span>
    </div>
    ${breakdownHtml}
  </div>`;

  // Filter bar
  const allCats = [...new Set(problems.map(p=>p.category))].sort();
  html += `<div class="filters">
    <select id="f-cat" onchange="applyFilter('cat',this.value)"><option value="">All Categories</option>${allCats.map(c=>`<option${filterState.cat===c?' selected':''}>${c}</option>`).join('')}</select>
    <select id="f-diff" onchange="applyFilter('diff',this.value)"><option value="">All Difficulties</option>${['E','M','H'].map(d=>`<option value="${d}"${filterState.diff===d?' selected':''}>${{E:'Easy',M:'Medium',H:'Hard'}[d]}</option>`).join('')}</select>
    <select id="f-status" onchange="applyFilter('status',this.value)"><option value="">All Statuses</option>${['pending','done','struggled','review'].map(s=>`<option${filterState.status===s?' selected':''}>${s}</option>`).join('')}</select>
    <input id="f-search" placeholder="Search title..." value="${filterState.search.replace(/"/g,'&quot;')}" oninput="applyFilter('search',this.value)" />
  </div>`;

  if (hasActiveFilter()) {
    // Flat filtered view (LeetCode only)
    const q = filterState.search.toLowerCase();
    let filtered = problems.filter(p =>
      (!filterState.cat || p.category === filterState.cat) &&
      (!filterState.diff || p.difficulty === filterState.diff) &&
      (!filterState.status || p.status === filterState.status) &&
      (!q || p.title.toLowerCase().includes(q))
    );
    const fDone = filtered.filter(p => p.status === 'done').length;
    const label = filterState.cat || 'Filtered';
    html += `<p style="color:var(--muted);font-size:.85rem;margin-bottom:8px">${label} · ${fDone}/${filtered.length} done</p>`;
    if (filtered.length) {
      filtered.forEach((p, i) => { p._rowNum = i + 1; });
      const sorted = sortProblems(filtered, 'filtered');
      sorted.forEach((p, i) => { p._rowNum = i + 1; });
      html += tableHeader('filtered', 'renderWeekly');
      sorted.forEach(p => html += problemRow(p));
      html += '</tbody></table>';
    } else {
      html += '<p style="color:var(--muted);padding:24px;text-align:center">No problems match your filters.</p>';
    }
  } else {
    // Weekly grouped view
    const weeks = {};
    problems.forEach(p => { (weeks[p.week] = weeks[p.week]||{coding:[], sd:[]}).coding.push(p); });
    sdProblems.forEach(p => { (weeks[p.week] = weeks[p.week]||{coding:[], sd:[]}).sd.push(p); });
    Object.keys(weeks).sort((a,b)=>a-b).forEach(w => {
      const wk = weeks[w];
      const allProbs = [...wk.coding, ...wk.sd];
      const isCur = String(w) === String(curWeek);
      const label = w == 13 ? 'Overflow' : `Week ${w} · ${weekDates(Number(w))}`;
      const done = allProbs.filter(p=>p.status==='done').length;
      const total = allProbs.length;
      const collapsed = collapsedWeeks.has(w);
      const pct = Math.round(done/total*100);
      const todayBadge = isCur ? `<span style="font-size:.7rem;background:var(--accent);color:#fff;padding:2px 6px;border-radius:4px;margin-left:8px">${weekend ? 'Review Day' : todayIds.size + ' today'}</span>` : '';
      html += `<div class="week-header ${collapsed?'collapsed':''}" onclick="toggleWeek('${w}')">
        <span>${label} — ${done}/${total} done (${pct}%)${todayBadge}</span>
        <span class="chevron">&#9660;</span>
      </div>`;
      html += `<div class="week-body ${collapsed?'hidden':''}">`;
      const codingCtx = 'wk'+w+'c', sdCtx = 'wk'+w+'s';
      if (wk.coding.length) {
        if (wk.sd.length) html += `<p style="margin:8px 0 4px;color:var(--muted);font-size:.8rem;font-weight:600">Coding</p>`;
        html += tableHeader(codingCtx, 'renderWeekly');
        let rowNum = 1;
        const sorted = sortProblems(wk.coding, codingCtx);
        sorted.forEach(p => { p._rowNum = rowNum++; html += problemRow(p); });
        html += '</tbody></table>';
      }
      if (wk.sd.length) {
        if (wk.coding.length) html += `<p style="margin:12px 0 4px;color:var(--muted);font-size:.8rem;font-weight:600">System Design</p>`;
        html += sdTableHeader(sdCtx, 'renderWeekly');
        const sdSorted = sortProblems(wk.sd, sdCtx);
        sdSorted.forEach(p => html += sdRow(p));
        html += '</tbody></table>';
      }
      html += '</div>';
    });
  }
  el.innerHTML = html;

  // Restore search focus
  const searchEl = document.getElementById('f-search');
  if (searchEl && filterState.search) { searchEl.focus(); searchEl.selectionStart = searchEl.selectionEnd = searchEl.value.length; }
}

function toggleWeek(w) {
  if (collapsedWeeks.has(w)) collapsedWeeks.delete(w);
  else collapsedWeeks.add(w);
  renderWeekly();
}

let filterState = { cat: '', diff: '', status: '', search: '' };

function hasActiveFilter() {
  return filterState.cat || filterState.diff || filterState.status || filterState.search;
}

function applyFilter(field, value) {
  filterState[field] = value;
  renderWeekly();
}

function getAllProblems() {
  const sdWithCat = sdProblems.map(p => ({...p, category: 'System Design'}));
  return [...problems, ...sdWithCat];
}



let lcUsername = '';
async function loadConfig() {
  try {
    const r = await fetch('/api/config');
    const cfg = await r.json();
    if (cfg.leetcode_username) lcUsername = cfg.leetcode_username;
  } catch(e) {}
}

async function syncLeetCode() {
  if (!lcUsername) return;
  const btn = document.getElementById('lc-sync-btn');
  btn.disabled = true;
  btn.textContent = '⟳';
  try {
    const r = await fetch('/api/sync/leetcode', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username: lcUsername})
    });
    await r.json();
    await fetchProblems();
    render();
  } catch(e) {}
  finally {
    btn.disabled = false;
    btn.textContent = '⟳';
  }
}


function activeTab() {
  const t = document.querySelector('.tab.active');
  return t ? t.dataset.tab : 'weekly';
}

function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// --- Python Toolkit ---
let pyrefData = null;
let pyrefSearch = '';
const pyrefExpanded = new Set();

async function fetchPyRef() {
  const r = await fetch('/api/pyref');
  pyrefData = await r.json();
}

function toggleCard(set, id, renderFn) {
  if (set.has(id)) set.delete(id); else set.add(id);
  renderFn();
}

function renderCards(el, topics, search, expanded, searchId, renderFn) {
  const q = search.toLowerCase();
  const filtered = q
    ? topics.filter(t => t.name.toLowerCase().includes(q) ||
        t.items.some(it =>
          it.label.toLowerCase().includes(q) ||
          it.code.toLowerCase().includes(q) ||
          (it.note && it.note.toLowerCase().includes(q))
        ))
    : topics;

  let html = `<input class="cards-search" id="${searchId}" placeholder="Search..." value="${search.replace(/"/g,'&quot;')}" />`;
  for (const t of filtered) {
    const isCollapsed = !expanded.has(t.id);
    let items = t.items;
    if (q) {
      items = items.filter(it =>
        it.label.toLowerCase().includes(q) ||
        it.code.toLowerCase().includes(q) ||
        (it.note && it.note.toLowerCase().includes(q))
      );
    }
    html += `<div class="card">`;
    html += `<div class="card-header${isCollapsed ? ' collapsed' : ''}" onclick="toggleCard(${expanded === pyrefExpanded ? 'pyrefExpanded' : 'mechExpanded'}, '${t.id}', ${renderFn})"><span>${t.name}</span><span class="chevron">▼</span></div>`;
    html += `<div class="card-body${isCollapsed ? ' hidden' : ''}">`;
    for (const item of items) {
      html += `<div class="card-item">`;
      html += `<div class="card-item-label">${esc(item.label)}</div>`;
      html += `<pre><code class="language-python">${esc(item.code)}</code></pre>`;
      if (item.note) html += `<div class="card-item-note">${esc(item.note)}</div>`;
      html += `</div>`;
    }
    html += `</div></div>`;
  }

  el.innerHTML = html;
  hljs.highlightAll();

  const searchEl = document.getElementById(searchId);
  if (searchEl) {
    searchEl.oninput = e => {
      if (expanded === pyrefExpanded) pyrefSearch = e.target.value;
      else mechSearch = e.target.value;
      renderFn();
      const newEl = document.getElementById(searchId);
      if (newEl) { newEl.focus(); newEl.selectionStart = newEl.selectionEnd = e.target.selectionStart; }
    };
  }
}

async function renderPyRef() {
  const el = document.getElementById('pytips');
  if (!pyrefData) await fetchPyRef();
  renderCards(el, pyrefData.topics || [], pyrefSearch, pyrefExpanded, 'pyref-search', renderPyRef);
}

// --- Patterns ---
let mechData = null;
let mechSearch = '';
const mechExpanded = new Set();

async function fetchMech() {
  const r = await fetch('/api/mechanics');
  mechData = await r.json();
}

async function renderMech() {
  const el = document.getElementById('mechanics');
  if (!mechData) await fetchMech();
  renderCards(el, mechData.topics || [], mechSearch, mechExpanded, 'mech-search', renderMech);
}

// --- System Design tab ---
let sdProblems = [];
let sdTimers = {};
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
  render();
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
    render();
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
    render();
  }
}

function sdOpenNotes(pid) {
  sdExpandedNotes.add(pid);
  render();
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
  render();
}

function sdNotesHTML(p) {
  const note = p.notes || '';
  if (sdExpandedNotes.has(p.id)) {
    return `<div class="notes-inner"><textarea class="notes-input" id="sd-notes-${p.id}" rows="2">${note.replace(/</g,'&lt;')}</textarea><button class="notes-save" onclick="sdSaveNotes('${p.id}')">Save</button></div>`;
  }
  if (note) {
    return `<span class="notes-preview" onclick="sdOpenNotes('${p.id}')" title="${note.replace(/"/g,'&quot;')}">${note.replace(/</g,'&lt;')}</span>`;
  }
  return `<button class="notes-toggle" onclick="sdOpenNotes('${p.id}')">+ add</button>`;
}

function sdTimerHTML(p) {
  const running = !!sdTimers[p.id];
  return `<span class="timer-display" id="sd-td-${p.id}">${running?'':''}</span>
    <button class="timer-btn ${running?'running':''}" onclick="sdToggleTimer('${p.id}')">${running?'Stop':'Start'}</button>`;
}

function sdRow(p) {
  const lastAttempt = p.attempts.length ? fmtTime(p.attempts[p.attempts.length-1].duration_sec) : '-';
  return `<tr>
    <td><a class="prob-link" href="${probUrl(p)}" target="_blank" rel="noopener">${p.title}</a></td>
    <td>${diffHTML(p.difficulty)}</td>
    <td><span class="badge badge-${p.status}" onclick="sdCycleStatus('${p.id}')">${p.status}</span></td>
    <td>${sdNotesHTML(p)}</td>
    <td>${lastAttempt}</td>
    <td>${sdTimerHTML(p)}</td>
  </tr>`;
}


function render() {
  computeLastSolved();
  const tab = activeTab();
  if (tab === 'weekly') renderWeekly();
else if (tab === 'pytips') renderPyRef();
  else if (tab === 'mechanics') renderMech();
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
if (savedTab && savedTab !== 'sysdesign' && savedTab !== 'stats' && savedTab !== 'all' && savedTab !== 'review') {
  const tabEl = document.querySelector(`.tab[data-tab="${savedTab}"]`);
  if (tabEl) {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
    tabEl.classList.add('active');
    document.getElementById(savedTab).classList.add('active');
  }
}

function setHljsTheme(theme) {
  document.getElementById('hljs-dark').disabled = (theme === 'light');
  document.getElementById('hljs-light').disabled = (theme !== 'light');
}

function toggleTheme() {
  const html = document.documentElement;
  const curr = html.getAttribute('data-theme') || 'dark';
  const next = curr === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  document.getElementById('theme-btn').textContent = next === 'dark' ? 'Light' : 'Dark';
  setHljsTheme(next);
  localStorage.setItem('theme', next);
}
// Restore saved theme
const saved = localStorage.getItem('theme');
if (saved) {
  document.documentElement.setAttribute('data-theme', saved);
  document.getElementById('theme-btn').textContent = saved === 'dark' ? 'Light' : 'Dark';
  setHljsTheme(saved);
}

async function init() {
  await Promise.all([fetchProblems(), fetchSD(), loadConfig()]);
  render();
}
init();
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
