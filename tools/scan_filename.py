#!/usr/bin/env python3
"""Parse the Apeos C2567 scan filenames arriving in automation@midlandind.com.au.

The operator types a description at the device panel; the device appends its own
timestamp and page-sequence. So every name is:

    <operator text>-<DDMMYYYYHHMMSS>-<NNNN>.pdf

The operator text is the only part carrying job data, and it is typed by hand, so
this module is deliberately permissive: it extracts what is there and reports what
is missing rather than rejecting a name. `job_no` is the one field worth trusting;
everything else is best-effort and may be absent.

Deliberately has no Graph dependency so it can be tested against real filenames
without credentials. See tools/test_scan_filename.py.
"""
import datetime
import re

# The device's own suffix. Anchored to the end, and matched before anything else,
# because the operator text may itself contain ' - ' and digits.
_DEVICE_SUFFIX = re.compile(r"-(?P<stamp>\d{14})-(?P<seq>\d{4})$")

# 'job no. 917', 'Job No 917', 'job no.917'. The number is occasionally suffixed
# by hand ('917A'), so capture the token rather than \d+.
_JOB_NO = re.compile(r"job\s*no\.?\s*(?P<job>[0-9]+[A-Za-z]?)", re.IGNORECASE)

# A VIN as typed after 'Quote, VIN' — 17 chars of the standard alphabet.
_VIN = re.compile(r"\bVIN\s*[:,]?\s*(?P<vin>[A-HJ-NPR-Z0-9]{17})\b", re.IGNORECASE)

# 'GA <model> - <drawing ref>', where the ref may itself be split further
# ('GA DW319SWKOH - 15650 - L'). Model codes are typed inconsistently — TG320SFP0R
# with a zero and TG219SFPOR with a letter O both occur — so the model is captured
# as an opaque token and never validated against a vocabulary.
_GA = re.compile(
    r"\bGA\s+(?P<model>[A-Za-z0-9]{6,})\s*(?:-\s*(?P<ref>.+))?$", re.IGNORECASE)

QUOTE, GENERAL_ARRANGEMENT, UNSPECIFIED = "quote", "ga", "unspecified"


def _stamp_to_iso(stamp):
    """DDMMYYYYHHMMSS -> ISO 8601, or None if it is not a real instant.

    Local wall-clock at the device (UTC+10 as measured against receivedDateTime);
    no timezone is attached because the device does not record one.
    """
    try:
        return datetime.datetime.strptime(stamp, "%d%m%Y%H%M%S").isoformat()
    except ValueError:
        return None


def _sanitise(text):
    """Make a token safe as a SharePoint path segment.

    SharePoint rejects " * : < > ? / \\ | and leading/trailing whitespace or dots.
    """
    cleaned = re.sub(r'[\"*:<>?/\\|#%]', "", text)
    return re.sub(r"\s+", " ", cleaned).strip(" .")


def parse(filename):
    """Return a dict describing one scan. Never raises.

    Keys always present: filename, job_no, doc_type, model, drawing_ref, vin,
    scanned_at, sequence, operator_text, problems. Any unextractable field is
    None, and the reason lands in `problems` — a name with problems is still
    filed, under 'unfiled' when even the job number is missing.
    """
    out = {
        "filename": filename,
        "job_no": None,
        "doc_type": UNSPECIFIED,
        "model": None,
        "drawing_ref": None,
        "vin": None,
        "scanned_at": None,
        "sequence": None,
        "operator_text": None,
        "problems": [],
    }

    stem = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)

    m = _DEVICE_SUFFIX.search(stem)
    if m:
        out["sequence"] = m.group("seq")
        out["scanned_at"] = _stamp_to_iso(m.group("stamp"))
        if out["scanned_at"] is None:
            out["problems"].append(f"unparseable device timestamp {m.group('stamp')!r}")
        operator_text = stem[: m.start()].strip()
    else:
        # Not fatal: the mail's own receivedDateTime is a fallback for ordering.
        out["problems"].append("no device timestamp suffix")
        operator_text = stem.strip()
    out["operator_text"] = operator_text

    m = _JOB_NO.search(operator_text)
    if m:
        out["job_no"] = m.group("job")
        # Everything after the job number is the description of what was scanned.
        rest = operator_text[m.end():].strip(" -,")
    else:
        out["problems"].append("no job number")
        rest = operator_text

    m = _VIN.search(rest)
    if m:
        out["vin"] = m.group("vin").upper()

    if re.search(r"\bquote\b", rest, re.IGNORECASE):
        out["doc_type"] = QUOTE
        if not out["vin"]:
            # Every quote seen so far carries one; worth surfacing when it does not.
            out["problems"].append("quote without a VIN")
    else:
        m = _GA.search(rest)
        if m:
            out["doc_type"] = GENERAL_ARRANGEMENT
            out["model"] = m.group("model").upper()
            if m.group("ref"):
                out["drawing_ref"] = _sanitise(m.group("ref"))
        elif rest:
            out["problems"].append(f"unrecognised description {rest!r}")
        else:
            out["problems"].append("job number only, no description")

    return out


def job_folder(record):
    """The SharePoint subfolder for a scan: 'job 917', or 'unfiled' with no job no."""
    job = record.get("job_no")
    return f"job {_sanitise(job)}" if job else "unfiled"


def pair_status(records):
    """Group parsed records by job and report which half of the GA/quote pair is missing.

    Operators scan a general arrangement and a quote per job; in the sampled backlog
    most jobs show only one of the two, which is the exception worth reporting rather
    than a parse failure.
    """
    jobs = {}
    for r in records:
        jobs.setdefault(r.get("job_no") or "unfiled", []).append(r)
    summary = {}
    for job, rs in jobs.items():
        kinds = {r["doc_type"] for r in rs}
        summary[job] = {
            "scans": len(rs),
            "has_ga": GENERAL_ARRANGEMENT in kinds,
            "has_quote": QUOTE in kinds,
            "missing": sorted(
                ({GENERAL_ARRANGEMENT, QUOTE} - kinds) if job != "unfiled" else []),
        }
    return summary
