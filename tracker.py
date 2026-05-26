#!/usr/bin/env python3
"""PrepFlow — Lightweight Web Dashboard

Run:  python tracker.py
Open: http://localhost:5050
"""

import json, os, re, datetime, webbrowser, sys, urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 5050))
HOST = os.environ.get("HOST", "localhost")
# Week 1 starts on this Monday — adjust if you want a different start date
START_MONDAY = "2026-02-23"
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(DATA_DIR, "progress.json")
MD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "leetcode_study_plan.md")
SD_DATA_FILE = os.path.join(DATA_DIR, "sd_progress.json")
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

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

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

        # /api/weekly-focus
        if self.path == "/api/weekly-focus":
            body = self._read_body()
            cfg = load_config()
            cfg["weekly_focus"] = body.get("coding", [])
            cfg["weekly_focus_sd"] = body.get("sd", [])
            cfg["weekly_focus_week"] = body.get("week", "")
            save_config(cfg)
            return self._json({"ok": True})

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
<title>PrepFlow</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%25' stop-color='%234f8ff7'/><stop offset='100%25' stop-color='%2334d399'/></linearGradient></defs><rect width='100' height='100' rx='20' fill='%231a1a2e'/><path d='M28 65 L45 35 L52 50 L72 28' stroke='url(%23g)' stroke-width='8' stroke-linecap='round' stroke-linejoin='round' fill='none'/><circle cx='72' cy='28' r='6' fill='%2334d399'/></svg>">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css" id="hljs-dark">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css" id="hljs-light" disabled>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/python.min.js"></script>
<style>
:root, [data-theme="dark"] {
  --bg: #0b0f15; --surface: #1c2230; --border: #3d4556;
  --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --yellow: #d29922; --red: #f85149; --purple: #bc8cff;
  --hover-row: rgba(88,166,255,.08); --week-hover: #212838;
  --noise-opacity: 0.06; --gradient: radial-gradient(ellipse at 15% 0%, rgba(88,166,255,.12) 0%, transparent 55%), radial-gradient(ellipse at 85% 100%, rgba(188,140,255,.08) 0%, transparent 55%);
}
[data-theme="light"] {
  --bg: #ffffff; --surface: #f6f8fa; --border: #d0d7de;
  --text: #1f2328; --muted: #656d76; --accent: #0969da;
  --green: #1a7f37; --yellow: #9a6700; --red: #cf222e; --purple: #8250df;
  --hover-row: rgba(9,105,218,.06); --week-hover: #eaeef2;
  --noise-opacity: 0.04; --gradient: radial-gradient(ellipse at 15% 0%, rgba(9,105,218,.08) 0%, transparent 55%), radial-gradient(ellipse at 85% 100%, rgba(130,80,223,.06) 0%, transparent 55%);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 15px; background: var(--bg); color: var(--text); letter-spacing: -0.01em; position: relative; min-height: 100vh; }
body::before { content: ''; position: fixed; inset: 0; z-index: -1; opacity: var(--noise-opacity); background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E"); background-repeat: repeat; background-size: 256px 256px; pointer-events: none; }
body::after { content: ''; position: fixed; inset: 0; z-index: -1; background: var(--gradient); pointer-events: none; }
code, pre, .mono { font-family: 'Hack Nerd Font Mono', 'Hack Nerd Font', 'SF Mono', 'Fira Code', Menlo, Consolas, monospace; }
.container { max-width: 1100px; margin: 0 auto; padding: 24px 32px; }
.sticky-header { position: sticky; top: 0; z-index: 100; background: var(--bg); padding: 12px 0 12px; border-bottom: 1px solid var(--border); margin-bottom: 24px; backdrop-filter: blur(8px); background: color-mix(in srgb, var(--bg) 85%, transparent); }
h1 { font-size: 1.4rem; margin-bottom: 4px; }
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.theme-toggle { display: flex; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; gap: 1px; }
.theme-opt { padding: 6px 10px; cursor: pointer; border: none; background: none; display: flex; align-items: center; justify-content: center; }
.theme-opt svg { width: 16px; height: 16px; stroke: var(--muted); transition: stroke .15s; }
.theme-opt:hover svg { stroke: var(--text); }
.theme-opt.active { background: var(--accent); }
.theme-opt.active svg { stroke: #fff; }
/* Tabs */
.tabs { display: flex; gap: 0; align-items: center; }
.tab { padding: 8px 16px; color: var(--muted); border-bottom: 2px solid transparent; font-size: .9rem; cursor: pointer; transition: color .15s, border-color .15s; user-select: none; }
.tab:hover { color: var(--text); }
.tab:active { opacity: .7; }
.tab.active { color: var(--accent); border-color: var(--accent); font-weight: 600; }
.panel { display: none; }
.panel.active { display: block; }
/* Filters */
.filters { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
.filters select, .filters input { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 6px; font-size: .85rem; }
/* Table */
table { width: 100%; border-collapse: collapse; font-size: .9rem; }
th { text-align: left; padding: 10px 12px; color: var(--muted); border-bottom: 1px solid var(--border); font-weight: 600; cursor: pointer; user-select: none; white-space: nowrap; }
th:hover { color: var(--text); }
th .sort-arrow { font-size: .65rem; margin-left: 3px; opacity: .4; }
th .sort-arrow.active { opacity: 1; color: var(--accent); }
td { padding: 10px 12px; border-bottom: 1px solid var(--border); }
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
.badge-skipped { background: rgba(139,148,158,.15); color: var(--muted); }
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
/* Scroll + TOC layout (Python Toolkit & Patterns) */
.ref-layout { display: flex; gap: 0; height: calc(100vh - 80px); }
.ref-sidebar { width: 200px; flex-shrink: 0; border-right: 1px solid var(--border); overflow-y: auto; padding: 12px 0; }
.ref-sidebar a { display: flex; align-items: center; gap: 6px; padding: 8px 16px; font-size: .85rem; color: var(--muted); text-decoration: none; cursor: pointer; transition: all .15s; border-left: 3px solid transparent; }
.ref-sidebar a:hover { color: var(--text); background: var(--week-hover); }
.ref-sidebar a.active { color: var(--accent); border-left-color: var(--accent); font-weight: 600; background: var(--week-hover); }
.ref-main { flex: 1; overflow-y: auto; padding: 16px 24px; }
.ref-search { display: block; width: 100%; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 8px; font-size: .85rem; margin: 0 0 8px; }
.ref-search:focus { outline: none; border-color: var(--accent); }
.ref-topic-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }
.ref-item { margin-bottom: 24px; }
.ref-item:last-child { margin-bottom: 0; }
.ref-item-label { font-weight: 600; font-size: .85rem; margin-bottom: 6px; color: var(--text); }
.ref-item pre { background: var(--surface) !important; border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; overflow-x: auto; margin: 6px 0 0; }
.ref-item pre code.hljs { background: transparent !important; padding: 0; }
.ref-item pre code { font-size: .85rem; line-height: 1.6; color: var(--text); }
.ref-item-note { font-size: .8rem; color: var(--muted); margin-top: 6px; font-style: italic; }
@media (max-width: 700px) { .ref-sidebar { display: none; } .ref-layout { height: auto; } }
/* Today's Focus */
.today-section { margin-bottom: 24px; }
.today-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.today-card { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 10px; padding: 18px 20px; display: flex; justify-content: space-between; align-items: center; }
.today-card-info { display: flex; flex-direction: column; gap: 6px; }
.today-card-title { font-weight: 600; font-size: .95rem; }
.today-card-meta { display: flex; gap: 10px; align-items: center; }
.today-empty { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 32px; text-align: center; color: var(--muted); }
/* Overall Progress */
.overall-progress { margin-bottom: 24px; display: flex; align-items: center; gap: 14px; }
.overall-bar { flex: 1; height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
.overall-fill { height: 100%; background: var(--green); border-radius: 4px; transition: width .4s; }
.overall-label { font-size: .9rem; font-weight: 600; color: var(--muted); white-space: nowrap; }
/* Weekly Planner */
.wp-section { margin-bottom: 32px; }
.wp-head { font-size: .8rem; color: var(--muted); font-weight: 600; letter-spacing: .4px; text-transform: uppercase; margin-bottom: 4px; }
.wp-range { font-size: .75rem; color: var(--border); margin-bottom: 14px; }
.wp-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }
.wp-stat { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; }
.wp-stat-num { font-size: 1.6rem; font-weight: 700; color: var(--text); line-height: 1.1; }
.wp-stat-num .wp-delta { font-size: .75rem; font-weight: 600; margin-left: 6px; }
.wp-delta.up { color: var(--green); } .wp-delta.down { color: var(--red); }
.wp-stat-label { font-size: .75rem; color: var(--muted); margin-top: 4px; }
.wp-list { margin-top: 14px; display: flex; flex-direction: column; gap: 4px; }
.wp-list-item { display: flex; align-items: center; gap: 10px; padding: 6px 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; font-size: .85rem; }
.wp-empty { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 28px; text-align: center; color: var(--muted); font-size: .85rem; }
.wp-field { margin-bottom: 16px; }
.wp-label { display: block; font-size: .8rem; color: var(--text); font-weight: 500; margin-bottom: 6px; }
.wp-input { width: 100%; box-sizing: border-box; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 8px; font-size: .85rem; font-family: inherit; }
.wp-input:focus { outline: none; border-color: var(--accent); }
textarea.wp-input { resize: vertical; min-height: 70px; }
.wp-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.wp-chip { font-size: .78rem; padding: 5px 12px; border-radius: 16px; border: 1px solid var(--border); background: var(--surface); color: var(--muted); cursor: pointer; user-select: none; transition: all .15s; }
.wp-chip:hover { color: var(--text); }
.wp-chip.on { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
.wp-saved { font-size: .72rem; color: var(--green); opacity: 0; transition: opacity .2s; }
.wp-saved.show { opacity: 1; }
/* Topic Progression */
.topic-row { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 6px; }
.topic-row:hover { background: var(--week-hover); }
.topic-header { display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; }
.topic-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.topic-dot.completed { background: var(--green); }
.topic-dot.in-progress { background: var(--accent); }
.topic-dot.up-next { background: transparent; border: 2px solid var(--accent); width: 10px; height: 10px; box-sizing: border-box; }
.topic-dot.locked { background: var(--border); }
.topic-name { font-weight: 600; font-size: .9rem; flex-shrink: 0; }
.topic-bar { flex: 1; height: 5px; background: var(--border); border-radius: 3px; overflow: hidden; margin: 0 8px; }
.topic-fill { height: 100%; border-radius: 3px; background: var(--green); transition: width .3s; }
.topic-count { font-size: .8rem; color: var(--muted); white-space: nowrap; min-width: 30px; text-align: right; }
.topic-chevron { font-size: .7rem; color: var(--muted); transition: transform .2s; }
.topic-chevron.collapsed { transform: rotate(-90deg); }
.topic-body { padding: 0 16px 16px; }
.topic-body.hidden { display: none; }
.topic-locked-label { color: var(--muted); font-size: .8rem; font-style: italic; padding: 8px 0; }
/* Sync pill in header */
.sync-pill { display: flex; align-items: center; gap: 6px; }
.sync-pill button { padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface); color: var(--muted); cursor: pointer; font-size: 1.1rem; line-height: 1; }
.sync-pill button:hover { color: var(--text); border-color: var(--muted); }
.sync-pill button:disabled { opacity: .5; cursor: not-allowed; }
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
    <div class="tab active" data-tab="weekly">Coding</div>
    <div class="tab" data-tab="sysdesign">System Design</div>
    <div class="tab" data-tab="planner">Weekly Planner</div>
  </div>
  <div class="header-actions">
    <div class="sync-pill" id="sync-pill">
      <button id="lc-sync-btn" onclick="syncLeetCode()" title="Sync from LeetCode">⟳</button>
    </div>
    <div class="theme-toggle" id="theme-toggle">
      <button class="theme-opt" data-mode="auto" onclick="setThemeMode('auto')" title="Auto"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg></button>
      <button class="theme-opt" data-mode="light" onclick="setThemeMode('light')" title="Light"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg></button>
      <button class="theme-opt" data-mode="dark" onclick="setThemeMode('dark')" title="Dark"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg></button>
    </div>
  </div>
</div>
</div>

<div id="weekly" class="panel active"></div>
<div id="sysdesign" class="panel"></div>
<div id="planner" class="panel"></div>
<div id="pytips" class="panel"></div>
<div id="mechanics" class="panel"></div>
<footer style="text-align:center;padding:32px 0 16px;color:var(--border);font-size:.7rem;letter-spacing:.5px">PrepFlow</footer>
</div>

<script>
let problems = [];
let timers = {};  // pid -> {start, interval}
const START_MONDAY = '__START_MONDAY__';

const STATUS_CYCLE = ['pending','done','struggled','review','skipped'];

// Topic dependency graph (NeetCode roadmap order)
const TOPIC_GRAPH = {
  'Arrays & Hashing': [],
  'Two Pointers': ['Arrays & Hashing'],
  'Stack': ['Arrays & Hashing'],
  'Binary Search': ['Two Pointers', 'Stack'],
  'Sliding Window': ['Two Pointers', 'Stack'],
  'Linked List': ['Two Pointers', 'Stack'],
  'Trees': ['Linked List'],
  'Backtracking': ['Trees'],
  'Tries': ['Trees'],
  'Heap / Priority Queue': ['Trees'],
  'Graphs': ['Backtracking'],
  '1-D DP': ['Backtracking'],
  'Advanced Graphs': ['Graphs'],
  'Intervals': ['Heap / Priority Queue'],
  'Greedy': ['Heap / Priority Queue'],
  '2-D DP': ['Graphs', '1-D DP'],
  'Bit Manipulation': ['1-D DP'],
  'Math & Geometry': ['2-D DP', 'Bit Manipulation'],
};

function topoSort(graph) {
  const order = [];
  const visited = new Set();
  function visit(node) {
    if (visited.has(node)) return;
    visited.add(node);
    (graph[node] || []).forEach(dep => visit(dep));
    order.push(node);
  }
  Object.keys(graph).forEach(visit);
  return order;
}
const TOPIC_ORDER = topoSort(TOPIC_GRAPH);

const TOPIC_TO_PATTERNS = {
  'Arrays & Hashing': ['hashmap-set', 'prefix-sum'],
  'Two Pointers': ['two-pointers'],
  'Stack': ['stack'],
  'Sliding Window': ['sliding-window'],
  'Binary Search': ['binary-search'],
  'Linked List': [],
  'Trees': ['bfs', 'dfs'],
  'Backtracking': ['backtracking'],
  'Tries': ['trie'],
  'Heap / Priority Q': ['heap'],
  'Graphs': ['bfs', 'dfs', 'union-find'],
  'Advanced Graphs': ['union-find'],
  '1-D DP': ['dynamic-programming'],
  '2-D DP': ['dynamic-programming'],
  'Intervals': ['intervals'],
  'Greedy': ['greedy'],
  'Bit Manipulation': [],
  'Math & Geometry': []
};

const TOPIC_TO_TOOLKIT = {
  'Arrays & Hashing': ['list', 'dict', 'set'],
  'Two Pointers': ['list', 'sorting'],
  'Stack': ['stack-queue'],
  'Sliding Window': ['dict', 'string'],
  'Binary Search': ['list', 'sorting'],
  'Linked List': [],
  'Trees': ['stack-queue'],
  'Backtracking': ['list'],
  'Tries': ['dict', 'string'],
  'Heap / Priority Q': ['heap'],
  'Graphs': ['dict', 'set', 'stack-queue'],
  'Advanced Graphs': ['dict', 'set', 'heap'],
  '1-D DP': ['list', 'dict'],
  '2-D DP': ['list', 'comprehensions'],
  'Intervals': ['list', 'sorting', 'tuple'],
  'Greedy': ['sorting', 'heap'],
  'Bit Manipulation': ['builtins'],
  'Math & Geometry': ['builtins']
};

function getQuickRefData(topicName) {
  const patternIds = TOPIC_TO_PATTERNS[topicName] || [];
  const toolkitIds = TOPIC_TO_TOOLKIT[topicName] || [];
  const patterns = [];
  const toolkit = [];
  if (mechData && mechData.topics) {
    for (const t of mechData.topics) {
      if (patternIds.includes(t.id)) {
        for (const item of t.items) patterns.push({ label: item.label, code: item.code, note: item.note, group: t.name });
      }
    }
  }
  if (pyrefData && pyrefData.topics) {
    for (const t of pyrefData.topics) {
      if (toolkitIds.includes(t.id)) {
        for (const item of t.items) toolkit.push({ label: item.label, code: item.code, note: item.note, group: t.name });
      }
    }
  }
  return { patterns, toolkit };
}

function computeTopicStates() {
  const states = {};
  for (const topic of TOPIC_ORDER) {
    const topicProblems = problems.filter(p => p.category === topic);
    const done = topicProblems.filter(p => p.status === 'done').length;
    const total = topicProblems.length;
    const prereqs = TOPIC_GRAPH[topic] || [];
    const allPrereqsDone = prereqs.length === 0 || prereqs.every(dep => {
      const s = states[dep];
      if (!s || s.total === 0) return false;
      if (s.done === s.total) return true;
      // Unlock next topic if only Hard problems remain
      const remaining = s.problems.filter(p => p.status !== 'done' && p.status !== 'skipped');
      return remaining.every(p => p.difficulty === 'H');
    });
    const solved = topicProblems.filter(p => p.status === 'done' || p.status === 'skipped').length;
    let status;
    if (total === 0) {
      status = 'locked';
    } else if (solved === total) {
      status = 'completed';
    } else if (allPrereqsDone) {
      status = done > 0 ? 'in-progress' : 'up-next';
    } else {
      status = 'locked';
    }
    states[topic] = { problems: topicProblems, done, total, status, unlocked: status !== 'locked' };
  }
  return states;
}

function computeWeeklyFocus(topicStates) {
  // Pick next 4 pending coding problems
  const ids = [];
  for (const topic of TOPIC_ORDER) {
    if (ids.length >= 4) break;
    const ts = topicStates[topic];
    if (!ts || !ts.unlocked || ts.status === 'completed') continue;
    for (const p of ts.problems) {
      if (ids.length >= 4) break;
      if (p.status === 'pending') ids.push(p.id);
    }
  }
  return ids;
}

function computeWeeklyFocusSD() {
  const ids = [];
  for (const p of sdProblems) {
    if (ids.length >= 2) break;
    if (p.status === 'pending') ids.push(p.id);
  }
  return ids;
}

async function ensureWeeklyFocus(topicStates) {
  const currentWeek = getCurrentMonday();
  const cfg = await (await fetch('/api/config')).json();
  if (cfg.weekly_focus_week === currentWeek && cfg.weekly_focus && cfg.weekly_focus.length > 0) {
    weeklyFocusIds = cfg.weekly_focus;
    weeklyFocusSDIds = cfg.weekly_focus_sd || [];
  } else {
    weeklyFocusIds = computeWeeklyFocus(topicStates);
    weeklyFocusSDIds = computeWeeklyFocusSD();
    await saveWeeklyFocus();
  }
}

async function refreshWeeklyFocus() {
  const topicStates = computeTopicStates();
  weeklyFocusIds = computeWeeklyFocus(topicStates);
  await saveWeeklyFocus();
  render();
}

async function refreshSDWeeklyFocus() {
  weeklyFocusSDIds = computeWeeklyFocusSD();
  await saveWeeklyFocus();
  render();
}

async function saveWeeklyFocus() {
  const currentWeek = getCurrentMonday();
  await fetch('/api/weekly-focus', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ coding: weeklyFocusIds, sd: weeklyFocusSDIds, week: currentWeek })
  });
}

function computeTodayQueue(topicStates) {
  todayIds.clear();
  const weekend = isWeekend();
  if (weekend) {
    const today = new Date().toISOString().split('T')[0];
    problems
      .filter(p => p.status === 'done' && p.next_review && p.next_review <= today)
      .forEach(p => todayIds.add(p.id));
  } else {
    weeklyFocusIds.forEach(id => todayIds.add(id));
  }
}

const expandedTopics = new Set();
const expandedQuickRef = new Set();

function toggleTopic(topic) {
  if (expandedTopics.has(topic)) expandedTopics.delete(topic);
  else expandedTopics.add(topic);
  renderHome();
}

function toggleQuickRef(topic) {
  if (expandedQuickRef.has(topic)) expandedQuickRef.delete(topic);
  else expandedQuickRef.add(topic);
  renderHome();
}

function hasQuickRef(topic) {
  const pIds = TOPIC_TO_PATTERNS[topic] || [];
  const tIds = TOPIC_TO_TOOLKIT[topic] || [];
  return pIds.length > 0 || tIds.length > 0;
}

function buildQuickRefHTML(topic) {
  const data = getQuickRefData(topic);
  if (data.patterns.length === 0 && data.toolkit.length === 0) return '';
  let h = '<div class="qref-section">';
  if (data.patterns.length) {
    h += '<div class="qref-group-title">Patterns</div><div class="qref-cards">';
    for (const item of data.patterns) {
      h += `<div class="qref-card"><div class="qref-label">${esc(item.label)}</div><pre><code class="language-python">${esc(item.code)}</code></pre>`;
      if (item.note) h += `<div class="qref-note">${esc(item.note)}</div>`;
      h += '</div>';
    }
    h += '</div>';
  }
  if (data.toolkit.length) {
    h += '<div class="qref-group-title">Python Toolkit</div><div class="qref-cards">';
    for (const item of data.toolkit) {
      h += `<div class="qref-card"><div class="qref-label">${esc(item.label)}</div><pre><code class="language-python">${esc(item.code)}</code></pre>`;
      if (item.note) h += `<div class="qref-note">${esc(item.note)}</div>`;
      h += '</div>';
    }
    h += '</div>';
  }
  h += '</div>';
  return h;
}

function isWeekend() {
  const day = new Date().getDay();
  return day === 0 || day === 6;
}

const todayIds = new Set();
let weeklyFocusIds = [];
let weeklyFocusSDIds = [];
let reviewCollapsed = true;
function toggleReviewCollapse() { reviewCollapsed = !reviewCollapsed; renderHome(); }
const sdTodayIds = new Set();

function getCurrentMonday() {
  const d = new Date();
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.getFullYear(), d.getMonth(), diff).toISOString().split('T')[0];
}

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

function skipHard(pid) {
  setStatus(pid, 'skipped');
}

async function markReviewed(pid) {
  await setStatus(pid, 'done');
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

const SLUG_OVERRIDES = {
  '121': 'best-time-to-buy-and-sell-stock',
  '124': 'binary-tree-maximum-path-sum',
  '309': 'best-time-to-buy-and-sell-stock-with-cooldown',
  '787': 'cheapest-flights-within-k-stops',
  '323': 'number-of-connected-components-in-an-undirected-graph',
  '105': 'construct-binary-tree-from-preorder-and-inorder-traversal',
  '1448': 'count-good-nodes-in-binary-tree',
  '211': 'design-add-and-search-words-data-structure',
  '208': 'implement-trie-prefix-tree',
  '215': 'kth-largest-element-in-an-array',
  '703': 'kth-largest-element-in-a-stream',
  '230': 'kth-smallest-element-in-a-bst',
  '235': 'lowest-common-ancestor-of-a-binary-search-tree',
  '17': 'letter-combinations-of-a-phone-number',
  '102': 'binary-tree-level-order-traversal',
  '329': 'longest-increasing-path-in-a-matrix',
  '424': 'longest-repeating-character-replacement',
  '3': 'longest-substring-without-repeating-characters',
  '1899': 'merge-triplets-to-form-target-triplet',
  '1851': 'minimum-interval-to-include-each-query',
  '50': 'powx-n',
  '19': 'remove-nth-node-from-end-of-list',
  '199': 'binary-tree-right-side-view',
  '297': 'serialize-and-deserialize-binary-tree',
  '167': 'two-sum-ii-input-array-is-sorted',
  '98': 'validate-binary-search-tree',
};
function lcUrl(p) {
  const slug = SLUG_OVERRIDES[p.id] || p.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
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
  const isToday = todayIds.has(p.id);
  const trClass = [isLast && 'last-solved', isToday && 'today-item'].filter(Boolean).join(' ');
  return `<tr${trClass ? ` class="${trClass}"` : ''}>
    <td><a class="prob-link" href="${probUrl(p)}" target="_blank" rel="noopener">${p.title}</a></td>
    <td>${diffHTML(p.difficulty)}</td>
    <td>${cat}</td>
    <td>${statusHtml}</td>
  </tr>`;
}

function tableHeader(ctx, renderFn) {
  return `<table><thead><tr>${sortableTh(ctx,'title','Title',renderFn)}${sortableTh(ctx,'diff','Diff',renderFn)}${sortableTh(ctx,'category','Category',renderFn)}${sortableTh(ctx,'status','Status',renderFn)}</tr></thead><tbody>`;
}

function sdTableHeader(ctx, renderFn) {
  return `<table><thead><tr>${sortableTh(ctx,'problem','Problem',renderFn)}${sortableTh(ctx,'diff','Diff',renderFn)}${sortableTh(ctx,'status','Status',renderFn)}</tr></thead><tbody>`;
}

function renderHome() {
  const el = document.getElementById('weekly');
  const topicStates = computeTopicStates();
  computeTodayQueue(topicStates);

  let html = '';

  // Section 1: Today's Focus
  html += '<div class="today-section">';
  const todayProbs = [...todayIds].map(id => problems.find(p => p.id === id)).filter(Boolean);
  if (isWeekend()) {
    const reviewCount = todayProbs.length;
    html += `<div onclick="toggleReviewCollapse()" style="font-size:.85rem;color:var(--muted);font-weight:600;margin-bottom:10px;cursor:pointer;display:flex;align-items:center;gap:6px;user-select:none">Review Today <span style="font-size:.75rem;color:var(--muted)">(${reviewCount})</span><span style="font-size:.7rem;transition:transform .15s;transform:rotate(${reviewCollapsed?'-90':'0'}deg)">▼</span></div>`;
  } else {
    html += `<div style="font-size:.85rem;color:var(--muted);font-weight:600;margin-bottom:10px">This Week's Focus</div>`;
  }
  if (todayProbs.length > 0) {
    if (isWeekend()) {
      // Compact review list
      html += `<div style="display:flex;flex-direction:column;gap:4px;${reviewCollapsed ? 'display:none' : ''}">`;
      todayProbs.forEach(p => {
        html += `<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 12px;background:var(--surface);border-radius:8px;border:1px solid var(--border)">
          <div style="display:flex;align-items:center;gap:10px;min-width:0">
            <a class="prob-link" href="${probUrl(p)}" target="_blank" rel="noopener" style="font-size:.85rem;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${p.title}</a>
            <span style="font-size:.7rem;padding:1px 6px;border-radius:8px;background:var(--border);color:var(--muted);white-space:nowrap">${p.category}</span>
            ${diffHTML(p.difficulty)}
          </div>
          <button onclick="markReviewed('${p.id}')" style="padding:2px 10px;font-size:.7rem;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--green);cursor:pointer;white-space:nowrap;margin-left:8px">Reviewed</button>
        </div>`;
      });
      html += '</div>';
    } else {
      // Weekly focus cards
      html += '<div class="today-cards">';
      todayProbs.forEach(p => {
        const isDone = p.status === 'done' || p.status === 'skipped';
        const doneStyle = isDone ? 'opacity:.5;' : '';
        const doneLabel = isDone ? `<span style="font-size:.7rem;padding:2px 8px;border-radius:8px;background:rgba(63,185,80,.15);color:var(--green)">${p.status === 'skipped' ? 'skipped' : 'done'}</span>` : '';
        const skipBtn = !isDone && p.difficulty === 'H' ? `<button onclick="skipHard('${p.id}')" style="padding:4px 12px;font-size:.75rem;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--muted);cursor:pointer;white-space:nowrap">Skip</button>` : '';
        html += `<div class="today-card" style="${doneStyle}">
          <div class="today-card-info">
            <a class="prob-link today-card-title" href="${probUrl(p)}" target="_blank" rel="noopener">${p.title}</a>
            <div class="today-card-meta">
              <span style="font-size:.75rem;padding:2px 8px;border-radius:10px;background:var(--border);color:var(--text)">${p.category}</span>
              ${diffHTML(p.difficulty)}
              ${doneLabel}
            </div>
          </div>
          ${skipBtn}
        </div>`;
      });
      html += '</div>';
      // Show "New Problems" button when all weekly focus are done
      const allDone = todayProbs.every(p => p.status === 'done' || p.status === 'skipped');
      if (allDone && todayProbs.length > 0) {
        html += `<div style="margin-top:12px;text-align:center"><button onclick="refreshWeeklyFocus()" style="padding:6px 16px;font-size:.8rem;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--accent);cursor:pointer">Pull New Problems</button></div>`;
      }
    }
  } else {
    html += '<div class="today-empty">All caught up! Keep going.</div>';
  }
  html += '</div>';

  // Section 2: Overall Progress
  const lcDone = problems.filter(p => p.status === 'done').length;
  const pct = problems.length ? Math.round(lcDone / problems.length * 100) : 0;
  html += `<div class="overall-progress">
    <span class="overall-label">${lcDone}/${problems.length}</span>
    <div class="overall-bar"><div class="overall-fill" style="width:${pct}%"></div></div>
    <span class="overall-label">${pct}%</span>
  </div>`;

  // Filter bar
  const allCats = [...new Set(problems.map(p=>p.category))].sort();
  html += `<div class="filters">
    <select id="f-cat" onchange="applyFilter('cat',this.value)"><option value="">All Categories</option>${allCats.map(c=>`<option${filterState.cat===c?' selected':''}>${c}</option>`).join('')}</select>
    <select id="f-diff" onchange="applyFilter('diff',this.value)"><option value="">All Difficulties</option>${['E','M','H'].map(d=>`<option value="${d}"${filterState.diff===d?' selected':''}>${{E:'Easy',M:'Medium',H:'Hard'}[d]}</option>`).join('')}</select>
    <select id="f-status" onchange="applyFilter('status',this.value)"><option value="">All Statuses</option>${['pending','done','struggled','review','skipped'].map(s=>`<option${filterState.status===s?' selected':''}>${s}</option>`).join('')}</select>
    <input id="f-search" placeholder="Search title..." value="${filterState.search.replace(/"/g,'&quot;')}" oninput="applyFilter('search',this.value)" />
  </div>`;

  if (hasActiveFilter()) {
    // Flat filtered view
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
      html += tableHeader('filtered', 'renderHome');
      sorted.forEach(p => html += problemRow(p));
      html += '</tbody></table>';
    } else {
      html += '<p style="color:var(--muted);padding:24px;text-align:center">No problems match your filters.</p>';
    }
  } else {
    // Section 3: Topic Progression (completed topics sink to bottom)
    const sortedTopics = [...TOPIC_ORDER].sort((a, b) => {
      const aComp = topicStates[a] && topicStates[a].status === 'completed' ? 1 : 0;
      const bComp = topicStates[b] && topicStates[b].status === 'completed' ? 1 : 0;
      return aComp - bComp;
    });
    for (const topic of sortedTopics) {
      const ts = topicStates[topic];
      if (!ts) continue;
      const expanded = expandedTopics.has(topic);
      const topicId = topic.replace(/[^a-zA-Z0-9]/g, '-');
      html += `<div class="topic-row">
        <div class="topic-header" onclick="toggleTopic('${topic}')">
          <span class="topic-dot ${ts.status}"></span>
          <span class="topic-name">${topic}</span>
          <div class="topic-bar"><div class="topic-fill" style="width:${ts.total ? Math.round(ts.done/ts.total*100) : 0}%"></div></div>
          <span class="topic-count">${ts.done}/${ts.total}</span>
          <span class="topic-chevron ${expanded ? '' : 'collapsed'}">&#9660;</span>
        </div>`;
      if (expanded) {
        html += '<div class="topic-body">';
        if (!ts.unlocked) {
          const deps = (TOPIC_GRAPH[topic] || []).join(', ');
          html += `<div class="topic-locked-label">Locked — complete ${deps} first</div>`;
        } else if (ts.problems.length) {
          const ctx = 'topic-' + topicId;
          ts.problems.forEach((p, i) => { p._rowNum = i + 1; });
          const sorted = sortProblems(ts.problems, ctx);
          sorted.forEach((p, i) => { p._rowNum = i + 1; });
          html += tableHeader(ctx, 'renderHome');
          sorted.forEach(p => html += problemRow(p));
          html += '</tbody></table>';
        }
        html += '</div>';
      }
      html += '</div>';
    }
  }

  el.innerHTML = html;


  // Restore search focus
  const searchEl = document.getElementById('f-search');
  if (searchEl && filterState.search) { searchEl.focus(); searchEl.selectionStart = searchEl.selectionEnd = searchEl.value.length; }
}

let filterState = { cat: '', diff: '', status: '', search: '' };

function hasActiveFilter() {
  return filterState.cat || filterState.diff || filterState.status || filterState.search;
}

function applyFilter(field, value) {
  filterState[field] = value;
  renderHome();
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

async function fetchPyRef() {
  const r = await fetch('/api/pyref');
  pyrefData = await r.json();
}

// --- Patterns ---
let mechData = null;
let mechSearch = '';

async function fetchMech() {
  const r = await fetch('/api/mechanics');
  mechData = await r.json();
}

// --- Shared scroll+TOC renderer ---
const selectedRefTopic = {};

function selectRefTopic(tabKey, topicId, renderFn) {
  selectedRefTopic[tabKey] = topicId;
  renderFn();
}

function renderRefTab(el, topics, search, searchId, searchVar, renderFn) {
  const q = search.toLowerCase();
  const filtered = q
    ? topics.filter(t => t.name.toLowerCase().includes(q) ||
        t.items.some(it =>
          it.label.toLowerCase().includes(q) ||
          it.code.toLowerCase().includes(q) ||
          (it.note && it.note.toLowerCase().includes(q))
        ))
    : topics;

  // Default to first topic if none selected
  if (!selectedRefTopic[searchVar] && filtered.length) {
    selectedRefTopic[searchVar] = filtered[0].id;
  }
  const activeId = selectedRefTopic[searchVar];
  const activeTopic = filtered.find(t => t.id === activeId) || filtered[0];

  // Sidebar
  let sidebarHtml = '';
  for (const t of filtered) {
    sidebarHtml += `<a class="${t.id === activeTopic?.id ? 'active' : ''}" onclick="selectRefTopic('${searchVar}','${t.id}',${renderFn.name})"><span>${t.name}</span><span style="font-size:.75rem;color:var(--muted);margin-left:auto">${t.items.length}</span></a>`;
  }

  // Content
  let contentHtml = '';
  if (activeTopic) {
    let items = activeTopic.items;
    if (q) {
      items = items.filter(it =>
        it.label.toLowerCase().includes(q) ||
        it.code.toLowerCase().includes(q) ||
        (it.note && it.note.toLowerCase().includes(q))
      );
    }
    contentHtml += `<div class="ref-topic-title">${activeTopic.name}</div>`;
    for (const item of items) {
      contentHtml += `<div class="ref-item">`;
      contentHtml += `<div class="ref-item-label">${esc(item.label)}</div>`;
      contentHtml += `<pre><code class="language-python">${esc(item.code)}</code></pre>`;
      if (item.note) contentHtml += `<div class="ref-item-note">${esc(item.note)}</div>`;
      contentHtml += `</div>`;
    }
  }

  el.innerHTML = `<div class="ref-layout"><nav class="ref-sidebar">${sidebarHtml}</nav><div class="ref-main">${contentHtml}</div></div>`;

  // Highlight code
  el.querySelectorAll('.ref-main pre code').forEach(b => hljs.highlightElement(b));

}

async function renderPyRef() {
  const el = document.getElementById('pytips');
  if (!pyrefData) await fetchPyRef();
  renderRefTab(el, pyrefData.topics || [], pyrefSearch, 'pyref-search', 'pyref', renderPyRef);
}

async function renderMech() {
  const el = document.getElementById('mechanics');
  if (!mechData) await fetchMech();
  renderRefTab(el, mechData.topics || [], mechSearch, 'mech-search', 'mech', renderMech);
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
  const isToday = sdTodayIds.has(p.id);
  return `<tr${isToday ? ' class="today-item"' : ''}>
    <td><a class="prob-link" href="${probUrl(p)}" target="_blank" rel="noopener">${p.title}</a></td>
    <td>${diffHTML(p.difficulty)}</td>
    <td><span class="badge badge-${p.status}" onclick="sdCycleStatus('${p.id}')">${p.status}</span></td>
  </tr>`;
}


let sdFilterState = { diff: '', status: '', search: '' };

function sdApplyFilter(field, value) {
  sdFilterState[field] = value;
  renderSD();
}

function sdHasActiveFilter() {
  return sdFilterState.diff || sdFilterState.status || sdFilterState.search;
}

function computeSDTodayQueue() {
  sdTodayIds.clear();
  weeklyFocusSDIds.forEach(id => sdTodayIds.add(id));
}

function renderSD() {
  const el = document.getElementById('sysdesign');
  computeSDTodayQueue();
  let html = '';

  // Section 1: Today's Focus
  html += '<div class="today-section">';
  html += `<div style="font-size:.85rem;color:var(--muted);font-weight:600;margin-bottom:10px">This Week's Focus</div>`;
  const sdFocusProbs = [...sdTodayIds].map(id => sdProblems.find(p => p.id === id)).filter(Boolean);
  if (sdFocusProbs.length > 0) {
    html += '<div class="today-cards">';
    sdFocusProbs.forEach(p => {
      const isDone = p.status === 'done';
      const doneStyle = isDone ? 'opacity:.5;' : '';
      const doneLabel = isDone ? `<span style="font-size:.7rem;padding:2px 8px;border-radius:8px;background:rgba(63,185,80,.15);color:var(--green)">done</span>` : '';
      const doneBtn = !isDone ? `<button onclick="sdSetStatus('${p.id}','done')" style="padding:4px 12px;font-size:.75rem;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--green);cursor:pointer;white-space:nowrap">✓ Done</button>` : '';
      html += `<div class="today-card" style="${doneStyle}">
        <div class="today-card-info">
          <a class="prob-link today-card-title" href="${probUrl(p)}" target="_blank" rel="noopener">${p.title}</a>
          <div class="today-card-meta">
            ${diffHTML(p.difficulty)}
            ${doneLabel}
          </div>
        </div>
        ${doneBtn}
      </div>`;
    });
    html += '</div>';
    const allSDDone = sdFocusProbs.every(p => p.status === 'done');
    if (allSDDone) {
      html += `<div style="margin-top:12px;text-align:center"><button onclick="refreshSDWeeklyFocus()" style="padding:6px 16px;font-size:.8rem;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--accent);cursor:pointer">Pull New Problems</button></div>`;
    }
  } else {
    html += '<div class="today-empty">All caught up! Keep going.</div>';
  }
  html += '</div>';

  // Section 2: Overall Progress
  const sdDone = sdProblems.filter(p => p.status === 'done').length;
  const sdTotal = sdProblems.length;
  const pct = sdTotal ? Math.round(sdDone / sdTotal * 100) : 0;
  html += `<div class="overall-progress">
    <span class="overall-label">${sdDone}/${sdTotal}</span>
    <div class="overall-bar"><div class="overall-fill" style="width:${pct}%"></div></div>
    <span class="overall-label">${pct}%</span>
  </div>`;

  // Filter bar
  html += `<div class="filters">
    <select id="sd-f-diff" onchange="sdApplyFilter('diff',this.value)"><option value="">All Difficulties</option>${['E','M','H'].map(d=>`<option value="${d}"${sdFilterState.diff===d?' selected':''}>${{E:'Easy',M:'Medium',H:'Hard'}[d]}</option>`).join('')}</select>
    <select id="sd-f-status" onchange="sdApplyFilter('status',this.value)"><option value="">All Statuses</option>${['pending','done'].map(s=>`<option${sdFilterState.status===s?' selected':''}>${s}</option>`).join('')}</select>
    <input id="sd-f-search" placeholder="Search title..." value="${sdFilterState.search.replace(/"/g,'&quot;')}" oninput="sdApplyFilter('search',this.value)" />
  </div>`;

  // SD table
  if (sdTotal) {
    const q = sdFilterState.search.toLowerCase();
    let filtered = sdProblems.filter(p =>
      (!sdFilterState.diff || p.difficulty === sdFilterState.diff) &&
      (!sdFilterState.status || p.status === sdFilterState.status) &&
      (!q || p.title.toLowerCase().includes(q))
    );
    if (sdHasActiveFilter()) {
      const fDone = filtered.filter(p => p.status === 'done').length;
      html += `<p style="color:var(--muted);font-size:.85rem;margin-bottom:8px">Filtered · ${fDone}/${filtered.length} done</p>`;
    }
    if (filtered.length) {
      const diffGroups = [
        { key: 'E', label: 'Easy' },
        { key: 'M', label: 'Medium' },
        { key: 'H', label: 'Hard' }
      ];
      for (const g of diffGroups) {
        const group = filtered.filter(p => p.difficulty === g.key);
        if (!group.length) continue;
        const gDone = group.filter(p => p.status === 'done').length;
        html += `<div style="display:flex;align-items:center;gap:8px;margin:16px 0 8px;font-size:.8rem;color:var(--muted);font-weight:600"><span>${g.label}</span><span style="flex:1;height:1px;background:var(--border)"></span><span>${gDone}/${group.length}</span></div>`;
        const ctx = 'sd-' + g.key;
        group.forEach((p, i) => { p._rowNum = i + 1; });
        const sorted = sortProblems(group, ctx);
        sorted.forEach((p, i) => { p._rowNum = i + 1; });
        html += sdTableHeader(ctx, 'renderSD');
        sorted.forEach(p => html += sdRow(p));
        html += '</tbody></table>';
      }
    } else {
      html += '<p style="color:var(--muted);padding:24px;text-align:center">No problems match your filters.</p>';
    }
  } else {
    html += '<p style="color:var(--muted);padding:24px;text-align:center">No system design problems loaded.</p>';
  }

  el.innerHTML = html;

  // Restore search focus
  const searchEl = document.getElementById('sd-f-search');
  if (searchEl && sdFilterState.search) { searchEl.focus(); searchEl.selectionStart = searchEl.selectionEnd = searchEl.value.length; }
}

// --- Weekly Planner tab ---
function localISO(d) {
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function mondayOf(date) {
  const d = new Date(date);
  d.setHours(0,0,0,0);
  const offset = (d.getDay() + 6) % 7; // Mon=0 ... Sun=6
  d.setDate(d.getDate() - offset);
  return d;
}
function addDays(date, n) { const d = new Date(date); d.setDate(d.getDate() + n); return d; }
function fmtDay(d) {
  return d.toLocaleDateString(undefined, {month: 'short', day: 'numeric'});
}

// Stats for problems with an attempt dated in [start, end] (inclusive ISO strings).
function weekStats(startISO, endISO) {
  const all = [...problems, ...sdProblems];
  const solved = [];   // distinct problems solved (a done attempt) in range
  let attempted = 0, seconds = 0;
  const diff = {E: 0, M: 0, H: 0};
  const seen = new Set();
  all.forEach(p => {
    const inRange = (p.attempts || []).filter(a => a.date >= startISO && a.date <= endISO);
    if (!inRange.length) return;
    if (!seen.has(p.id)) { seen.add(p.id); attempted++; }
    inRange.forEach(a => { seconds += a.duration_sec || 0; });
    if (inRange.some(a => a.result === 'done')) {
      solved.push(p);
      if (diff[p.difficulty] !== undefined) diff[p.difficulty]++;
    }
  });
  return {solved, attempted, seconds, diff};
}

function loadPlan(key) {
  try { return JSON.parse(localStorage.getItem('plan:' + key) || '{}'); }
  catch (e) { return {}; }
}
function savePlan(key, plan) {
  localStorage.setItem('plan:' + key, JSON.stringify(plan));
  const s = document.getElementById('wp-saved');
  if (s) { s.classList.add('show'); clearTimeout(window._wpSaveT); window._wpSaveT = setTimeout(() => s.classList.remove('show'), 1500); }
}

let plannerNextKey = null;
function plannerUpdate(field, value) {
  const plan = loadPlan(plannerNextKey);
  plan[field] = value;
  savePlan(plannerNextKey, plan);
}
function plannerToggleTopic(topic) {
  const plan = loadPlan(plannerNextKey);
  const topics = new Set(plan.topics || []);
  if (topics.has(topic)) topics.delete(topic); else topics.add(topic);
  plan.topics = [...topics];
  savePlan(plannerNextKey, plan);
  document.querySelector(`.wp-chip[data-topic="${CSS.escape(topic)}"]`)?.classList.toggle('on');
}

function renderPlanner() {
  const el = document.getElementById('planner');
  const thisMon = mondayOf(new Date());
  const lastMon = addDays(thisMon, -7);
  const lastSun = addDays(thisMon, -1);
  const prevMon = addDays(thisMon, -14);
  const prevSun = addDays(thisMon, -8);
  const nextMon = addDays(thisMon, 7);
  const nextSun = addDays(thisMon, 13);

  const last = weekStats(localISO(lastMon), localISO(lastSun));
  const prev = weekStats(localISO(prevMon), localISO(prevSun));
  const delta = last.solved.length - prev.solved.length;
  const deltaHtml = delta === 0 ? ''
    : `<span class="wp-delta ${delta > 0 ? 'up' : 'down'}">${delta > 0 ? '▲' : '▼'} ${Math.abs(delta)}</span>`;
  const hrs = Math.round(last.seconds / 360) / 10; // hours, 1 decimal

  let html = '';

  // Section 1 — Last week review
  html += '<div class="wp-section">';
  html += '<div class="wp-head">Last Week</div>';
  html += `<div class="wp-range">${fmtDay(lastMon)} – ${fmtDay(lastSun)}</div>`;
  html += '<div class="wp-stats">';
  html += `<div class="wp-stat"><div class="wp-stat-num">${last.solved.length}${deltaHtml}</div><div class="wp-stat-label">solved</div></div>`;
  html += `<div class="wp-stat"><div class="wp-stat-num">${last.attempted}</div><div class="wp-stat-label">attempted</div></div>`;
  html += `<div class="wp-stat"><div class="wp-stat-num">${hrs}h</div><div class="wp-stat-label">time spent</div></div>`;
  html += `<div class="wp-stat"><div class="wp-stat-num"><span class="diff-E">${last.diff.E}</span> · <span class="diff-M">${last.diff.M}</span> · <span class="diff-H">${last.diff.H}</span></div><div class="wp-stat-label">easy · med · hard</div></div>`;
  html += '</div>';
  if (last.solved.length) {
    html += '<div class="wp-list">';
    last.solved.forEach(p => {
      html += `<div class="wp-list-item"><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.title}</span>${diffHTML(p.difficulty)}<span style="font-size:.72rem;color:var(--muted)">${p.category || 'System Design'}</span></div>`;
    });
    html += '</div>';
  } else {
    html += '<div class="wp-empty" style="margin-top:14px">No tracked activity last week. Use the timer on a problem to log attempts.</div>';
  }
  html += '</div>';

  // Section 2 — Plan next week
  plannerNextKey = localISO(nextMon);
  const plan = loadPlan(plannerNextKey);
  html += '<div class="wp-section">';
  html += '<div class="wp-head">Plan Next Week</div>';
  html += `<div class="wp-range">${fmtDay(nextMon)} – ${fmtDay(nextSun)}</div>`;
  html += `<div class="wp-field">
    <label class="wp-label" for="wp-target">Target problems</label>
    <input class="wp-input" id="wp-target" type="number" min="0" placeholder="e.g. 10" value="${plan.target != null ? plan.target : ''}" oninput="plannerUpdate('target', this.value)" style="max-width:160px">
  </div>`;
  html += '<div class="wp-field"><label class="wp-label">Focus areas</label><div class="wp-chips">';
  const selected = new Set(plan.topics || []);
  TOPIC_ORDER.forEach(t => {
    html += `<span class="wp-chip ${selected.has(t) ? 'on' : ''}" data-topic="${t}" onclick="plannerToggleTopic('${t.replace(/'/g, "\\'")}')">${t}</span>`;
  });
  html += '</div></div>';
  html += `<div class="wp-field">
    <label class="wp-label" for="wp-notes">Goals &amp; notes</label>
    <textarea class="wp-input" id="wp-notes" placeholder="What do you want to accomplish next week?" oninput="plannerUpdate('notes', this.value)">${(plan.notes || '').replace(/</g, '&lt;')}</textarea>
  </div>`;
  html += '<div style="text-align:right"><span class="wp-saved" id="wp-saved">Saved ✓</span></div>';
  html += '</div>';

  el.innerHTML = html;
}

function render() {
  computeLastSolved();
  const tab = activeTab();
  if (tab === 'weekly') renderHome();
  else if (tab === 'sysdesign') renderSD();
  else if (tab === 'planner') renderPlanner();
  else if (tab === 'pytips') renderPyRef();
  else if (tab === 'mechanics') renderMech();
}

// Tabs
const TAB_HASH = { weekly: 'coding', sysdesign: 'system-design', planner: 'weekly-planner' };
const HASH_TAB = Object.fromEntries(Object.entries(TAB_HASH).map(([k,v]) => [v, k]));

function switchTab(tabId) {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
  const tabEl = document.querySelector(`.tab[data-tab="${tabId}"]`);
  if (tabEl) {
    tabEl.classList.add('active');
    document.getElementById(tabId).classList.add('active');
    localStorage.setItem('activeTab', tabId);
    window.location.hash = TAB_HASH[tabId] || tabId;
    render();
  }
}

document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => {
    switchTab(t.dataset.tab);
    window.scrollTo(0, 0);
  });
});

// Restore tab from hash or localStorage
function restoreTab() {
  const hash = window.location.hash.slice(1);
  const tabFromHash = HASH_TAB[hash];
  const tabId = tabFromHash || localStorage.getItem('activeTab') || 'weekly';
  if (tabId !== 'weekly' && tabId !== 'stats' && tabId !== 'all' && tabId !== 'review') {
    switchTab(tabId);
  } else if (tabFromHash) {
    switchTab(tabId);
  }
}
restoreTab();
window.addEventListener('hashchange', restoreTab);

function setHljsTheme(theme) {
  document.getElementById('hljs-dark').disabled = (theme === 'light');
  document.getElementById('hljs-light').disabled = (theme !== 'light');
}

function getSystemTheme() {
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function applyTheme(resolved) {
  document.documentElement.setAttribute('data-theme', resolved);
  setHljsTheme(resolved);
}

function setThemeMode(mode) {
  localStorage.setItem('themeMode', mode);
  const resolved = mode === 'auto' ? getSystemTheme() : mode;
  applyTheme(resolved);
  updateThemeToggle(mode);
}

function updateThemeToggle(mode) {
  document.querySelectorAll('.theme-opt').forEach(b => {
    b.classList.toggle('active', b.dataset.mode === mode);
  });
}

// Listen for system theme changes when in auto mode
window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
  if ((localStorage.getItem('themeMode') || 'dark') === 'auto') {
    applyTheme(getSystemTheme());
  }
});

// Restore saved theme
const savedMode = localStorage.getItem('themeMode') || 'dark';
setThemeMode(savedMode);

async function init() {
  await Promise.all([fetchProblems(), fetchSD(), loadConfig(), fetchPyRef(), fetchMech()]);
  const topicStates = computeTopicStates();
  await ensureWeeklyFocus(topicStates);
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
    server = HTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Dashboard: {url}")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
