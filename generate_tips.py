#!/usr/bin/env python3
"""Generate new Python tips using the Anthropic API and append them to tips.json.

Usage:
    python generate_tips.py            # generate 10 new tips
    python generate_tips.py --count 5  # generate 5 new tips

Requires:
    pip install anthropic
"""

import argparse
import json
import os
import sys

TIPS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tips.json")


def load_existing_tips():
    if os.path.exists(TIPS_FILE):
        with open(TIPS_FILE, "r") as f:
            return json.load(f)
    return []


def generate_tips(count=10):
    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed.")
        print("Install it with: pip install anthropic")
        sys.exit(1)

    existing = load_existing_tips()
    existing_titles = [t["title"] for t in existing]

    client = anthropic.Anthropic()

    prompt = f"""Generate exactly {count} new Python tips for a LeetCode/interview prep dashboard.

Each tip must have these fields:
- "cat": category (one of: "Data Structures", "Strings & Slicing", "Comprehensions", "Built-in Functions", "Interview Patterns", "Gotchas", "Complexity", or a new relevant category)
- "title": short descriptive title
- "code": Python code snippet with comments (use \\n for newlines)
- "note": one-sentence practical takeaway

Rules:
1. Do NOT duplicate any of these existing titles: {json.dumps(existing_titles)}
2. Tips should be practical for coding interviews and competitive programming
3. Code snippets should be concise but complete enough to understand
4. Focus on Python-specific tricks, patterns, and common pitfalls
5. Return ONLY a valid JSON array, no markdown fences or extra text

Example format:
[
  {{"cat": "Data Structures", "title": "Example Title", "code": "# Example\\nprint('hello')", "note": "Practical note here."}}
]"""

    print(f"Generating {count} new tips (currently have {len(existing)})...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Strip markdown fences if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Remove first and last fence lines
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines[-1].startswith("```") else lines
        response_text = "\n".join(lines)

    try:
        new_tips = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"Error parsing API response: {e}")
        print(f"Raw response:\n{response_text[:500]}")
        sys.exit(1)

    if not isinstance(new_tips, list):
        print("Error: API response is not a JSON array")
        sys.exit(1)

    # Filter out any that accidentally duplicate existing titles
    unique_tips = [t for t in new_tips if t.get("title") not in existing_titles]
    skipped = len(new_tips) - len(unique_tips)

    # Append to existing tips
    existing.extend(unique_tips)
    with open(TIPS_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"Added {len(unique_tips)} new tips to tips.json (total: {len(existing)})")
    if skipped:
        print(f"Skipped {skipped} duplicate(s)")
    for tip in unique_tips:
        print(f"  + [{tip['cat']}] {tip['title']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Python tips using Claude API")
    parser.add_argument("--count", type=int, default=10, help="Number of tips to generate (default: 10)")
    args = parser.parse_args()
    generate_tips(args.count)
