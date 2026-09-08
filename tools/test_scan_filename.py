#!/usr/bin/env python3
"""Tests for scan_filename.parse, against filenames read out of the real mailbox.

Every name in REAL_NAMES was observed in automation@midlandind.com.au between
2026-08-26 and 2026-09-07. They are the whole point of this file: the parser is
guessing at hand-typed text, so the only meaningful check is real input.

Run: python3 tools/test_scan_filename.py
"""
import sys

from scan_filename import (GENERAL_ARRANGEMENT, QUOTE, UNSPECIFIED, job_folder,
                           pair_status, parse)

# (filename, expected subset) — sampled across the backlog to catch format drift.
REAL_NAMES = [
    ("job no. 917 GA ST319HDKIB - 13360-07092026163543-0001.pdf",
     {"job_no": "917", "doc_type": GENERAL_ARRANGEMENT, "model": "ST319HDKIB",
      "drawing_ref": "13360", "vin": None, "sequence": "0001",
      "scanned_at": "2026-09-07T16:35:43"}),

    # The other half of job 917's pair: a quote carrying a VIN, no model code.
    ("job no. 917 Quote, VIN 6T9T25R10NAKT4003-07092026163802-0001.pdf",
     {"job_no": "917", "doc_type": QUOTE, "model": None,
      "vin": "6T9T25R10NAKT4003", "scanned_at": "2026-09-07T16:38:02"}),

    ("job no. 543 GA DT320SSR0B - 9000B-07092026162731-0001.pdf",
     {"job_no": "543", "doc_type": GENERAL_ARRANGEMENT, "model": "DT320SSR0B",
      "drawing_ref": "9000B"}),

    ("job no. 341 GA DT417HFWRB - 9000-07092026153837-0001.pdf",
     {"job_no": "341", "doc_type": GENERAL_ARRANGEMENT, "model": "DT417HFWRB",
      "drawing_ref": "9000"}),

    # Model code ending in a digit zero...
    ("job no. 311 GA TG320SFP0R - 9000J-07092026150515-0001.pdf",
     {"job_no": "311", "model": "TG320SFP0R", "drawing_ref": "9000J"}),

    # ...against the same code typed with a letter O. Both are accepted verbatim;
    # validating model codes against a vocabulary would reject one of these.
    ("job no. 564 GA TG219SFPOR - 8000A-03092026150020-0001.pdf",
     {"job_no": "564", "model": "TG219SFPOR", "drawing_ref": "8000A"}),

    # A drawing ref that is itself split by ' - ' — the ref must keep both parts.
    ("job no. 269 GA DW319SWKOH - 15650 - L-03092026150505-0001.pdf",
     {"job_no": "269", "model": "DW319SWKOH", "drawing_ref": "15650 - L"}),

    # Job number only. Two of these exist for job 751 on consecutive days, so the
    # timestamp is the only thing telling them apart.
    ("job no. 751-26082026163015-0001.pdf",
     {"job_no": "751", "doc_type": UNSPECIFIED, "model": None,
      "scanned_at": "2026-08-26T16:30:15"}),
    ("job no. 751-27082026074658-0001.pdf",
     {"job_no": "751", "doc_type": UNSPECIFIED,
      "scanned_at": "2026-08-27T07:46:58"}),
]

# Names that have not been observed but are the obvious ways this can go wrong.
EDGE_CASES = [
    # Nothing recognisable: must still parse, and must file under 'unfiled'.
    ("random scan-01012026120000-0001.pdf", {"job_no": None, "doc_type": UNSPECIFIED}),
    # No device suffix at all (someone renamed it by hand).
    ("job no. 400 GA DT320SSR0B - 9000.pdf",
     {"job_no": "400", "model": "DT320SSR0B", "scanned_at": None, "sequence": None}),
    # Casing and spacing variants of the job-number prefix.
    ("Job No 401 GA DT320SSR0B - 9000-01012026120000-0001.pdf", {"job_no": "401"}),
    ("job no.402 GA DT320SSR0B - 9000-01012026120000-0001.pdf", {"job_no": "402"}),
    # A hand-suffixed job number.
    ("job no. 403A GA DT320SSR0B - 9000-01012026120000-0001.pdf", {"job_no": "403A"}),
    # An impossible date must be reported, not crash or silently pass through.
    ("job no. 404-99999999999999-0001.pdf", {"job_no": "404", "scanned_at": None}),
    # Path-hostile characters in the typed text must not reach a SharePoint path.
    ("job no. 405 GA DT320SSR0B - 9000/rev:2-01012026120000-0001.pdf",
     {"job_no": "405", "drawing_ref": "9000rev2"}),
]


def check(cases, label):
    failures = []
    for name, expected in cases:
        got = parse(name)
        for key, want in expected.items():
            if got[key] != want:
                failures.append(f"  {name}\n    {key}: expected {want!r}, got {got[key]!r}")
    print(f"{'FAIL' if failures else 'PASS'}  {label} ({len(cases)} names)")
    for f in failures:
        print(f)
    return not failures


def check_invariants():
    """Properties that must hold for every name, however mangled."""
    failures = []
    for name, _ in REAL_NAMES + EDGE_CASES:
        r = parse(name)
        folder = job_folder(r)
        if any(c in folder for c in '"*:<>?/\\|'):
            failures.append(f"  {name}: unsafe folder {folder!r}")
        if r["job_no"] is None and folder != "unfiled":
            failures.append(f"  {name}: no job no. but folder is {folder!r}")
        if r["drawing_ref"] and any(c in r["drawing_ref"] for c in '"*:<>?/\\|'):
            failures.append(f"  {name}: unsafe drawing_ref {r['drawing_ref']!r}")
        # A problem-free parse must have produced a job number.
        if not r["problems"] and not r["job_no"]:
            failures.append(f"  {name}: reported no problems yet has no job number")
    print(f"{'FAIL' if failures else 'PASS'}  path safety and problem-reporting invariants")
    for f in failures:
        print(f)
    return not failures


def check_pairing():
    records = [parse(n) for n, _ in REAL_NAMES]
    summary = pair_status(records)
    ok = True
    # Job 917 is the one job in the sample with both halves.
    if summary["917"] != {"scans": 2, "has_ga": True, "has_quote": True, "missing": []}:
        print(f"FAIL  job 917 should be a complete pair, got {summary['917']}")
        ok = False
    # 751 was scanned twice, both times without a description.
    if summary["751"]["scans"] != 2 or summary["751"]["missing"] != ["ga", "quote"]:
        print(f"FAIL  job 751 should be 2 scans missing both halves, got {summary['751']}")
        ok = False
    if ok:
        print(f"PASS  pair detection ({len(summary)} jobs in sample)")
        incomplete = [j for j, s in summary.items() if s["missing"]]
        print(f"      {len(incomplete)} of {len(summary)} sampled jobs are missing a half: "
              f"{', '.join(sorted(incomplete))}")
    return ok


def main():
    results = [
        check(REAL_NAMES, "real filenames from the mailbox"),
        check(EDGE_CASES, "edge cases"),
        check_invariants(),
        check_pairing(),
    ]
    print()
    if all(results):
        print("All checks passed.")
        return 0
    print("FAILURES above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
