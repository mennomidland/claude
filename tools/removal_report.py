#!/usr/bin/env python3
"""Render the pending-removal work list as a checklist to work through in the media UI.

The endpoint cannot retract a tag, so until it can, the retractions a re-tag computes have
to be applied by hand. This turns that from an unbounded hunt into a finite, ordered job:
one section per asset, sorted by mediaId, every tag to strike listed once.

    python3 tools/removal_report.py manifest/_ingested_removals.json > removals.md
"""
import json
import pathlib
import sys


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    book = json.loads(pathlib.Path(sys.argv[1]).read_text())
    rows = sorted(book.values(), key=lambda r: (r.get("media_id") or 0, r.get("filename") or ""))
    total = sum(len(t) for r in rows for t in r["pending"].values())

    print(f"# Tags to strike — {total} across {len(rows)} assets\n")
    print("Each line is one tag to remove from that asset in the media library UI. "
          "Grouped by\nasset because the UI is per-asset; ordered by `mediaId` so the list "
          "matches the order\nassets appear.\n")
    for r in rows:
        print(f"## {r.get('media_id')} — {r.get('filename')}\n")
        if r.get("path"):
            print(f"`{r['path']}`\n")
        for ns, tags in sorted(r["pending"].items()):
            print(f"**{ns}**\n")
            for t in tags:
                print(f"- [ ] `{t}`")
            print()


if __name__ == "__main__":
    main()
