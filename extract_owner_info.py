#!/usr/bin/env python3
"""Extract the presumed location and occupation of the user who posted the comments.

The script reads ``johnnyanmac_comments.json`` (a plain‑text file containing
multiple comments separated by newlines).  It looks for informal clues such as
"I work with …", "I work as a …", "I am a …" for occupation, and
"from …", "live in …", "based in …" for location.  All found candidates are
counted and the most frequent ones are printed as JSON.

Usage:
    python extract_owner_info.py

The output looks like::

    {
        "location": "Los Angeles, USA",
        "occupation": "Software Engineer"
    }

If no confident match is found the corresponding field will be ``null``.
"""

import json
import re
import sys
from collections import Counter

COMMENT_FILE = "johnnyanmac_comments.json"

# Simple regex patterns for occupation and location clues.
OCCUPATION_PATTERNS = [
    re.compile(r"(?i)\bI\s+work\s+with\s+([\w\s]+)") ,
    re.compile(r"(?i)\bI\s+work\s+as\s+a\s+([\w\s]+)") ,
    re.compile(r"(?i)\bI\s+work\s+as\s+an\s+([\w\s]+)") ,
    re.compile(r"(?i)\bI\s+am\s+a\s+([\w\s]+)") ,
    re.compile(r"(?i)\bI\s+am\s+an\s+([\w\s]+)") ,
]

LOCATION_PATTERNS = [
    re.compile(r"(?i)\bfrom\s+([A-Za-z][\w\s,]+)") ,
    re.compile(r"(?i)\blive\s+in\s+([A-Za-z][\w\s,]+)") ,
    re.compile(r"(?i)\bbased\s+in\s+([A-Za-z][\w\s,]+)") ,
]

def extract_candidates(text: str):
    occs = []
    locs = []
    for pat in OCCUPATION_PATTERNS:
        for m in pat.finditer(text):
            occs.append(m.group(1).strip())
    for pat in LOCATION_PATTERNS:
        for m in pat.finditer(text):
            locs.append(m.group(1).strip())
    return occs, locs


def main():
    try:
        with open(COMMENT_FILE, "r", encoding="utf-8") as f:
            data = f.read()
    except FileNotFoundError:
        print(f"Error: {COMMENT_FILE} not found", file=sys.stderr)
        sys.exit(1)

    # Comments are separated by newlines; split and strip.
    comments = [c.strip() for c in data.split("\n") if c.strip()]
    occupation_counter = Counter()
    location_counter = Counter()
    for comment in comments:
        occs, locs = extract_candidates(comment)
        occupation_counter.update(occs)
        location_counter.update(locs)

    # Pick the most common non‑empty candidate.
    location = None
    if location_counter:
        location = location_counter.most_common(1)[0][0]
    occupation = None
    if occupation_counter:
        occupation = occupation_counter.most_common(1)[0][0]

    result = {
        "location": location,
        "occupation": occupation,
    }
    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    main()
