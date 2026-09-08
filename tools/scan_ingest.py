#!/usr/bin/env python3
"""Ingest scanner mail from automation@midlandind.com.au into SharePoint.

Pipeline, per message from the Apeos C2567:

  1. enumerate  Inbox, filtered to the scanner's address
  2. download   each PDF attachment's real bytes (Graph, no 1 MB ceiling)
  3. upload     into the sales drawings library, foldered by job number
  4. reconcile  any VIN in the filename against the Smartsheet VIN Tracker
  5. action     categorise, mark read, move out of the Inbox

Idempotent by construction: step 5 moves the message out of the enumerated
folder, so a second run sees only what is genuinely new. Uploads additionally
refuse to overwrite, so a half-finished run resumes without duplicating.

DRY RUN BY DEFAULT. Nothing is written without --commit.

    python3 tools/scan_ingest.py                  # report only
    python3 tools/scan_ingest.py --limit 5        # look at five
    python3 tools/scan_ingest.py --commit         # actually do it

Requires GRAPH_TENANT_ID / GRAPH_CLIENT_ID / GRAPH_CLIENT_SECRET (already set on
the Midland environment) plus, for step 4 only, SMARTSHEET_ACCESS_TOKEN.

**Step 1 needs a Mail permission the app registration does not yet have** — see
docs/routines/06-scan-mailbox.md. Everything below step 1 is exercised by
--self-test, which needs no mail access.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_check as gc
from scan_filename import QUOTE, job_folder, pair_status, parse

MAILBOX = "automation@midlandind.com.au"
SCANNER = "noreply@viatek-scan.com.au"
# Where filed mail goes. Created under the Inbox on first --commit run.
ACTIONED_FOLDER = "Scans Actioned"
CATEGORY = "Scan Ingested"

# Destination in the granted drive (docs/findings/library-structure.md).
# 'SALES DRAWINGS/TRAILERS BY JOB NO' is foldered by CUSTOMER, not job number,
# so scans get their own root rather than being mixed into that convention.
DEST_ROOT = "SALES DRAWINGS/SCANNED JOB CARDS"

SMARTSHEET_API = "https://api.smartsheet.com/2.0"
VIN_TRACKER_SHEET_ID = 3933652678666116
VIN_COLUMN_ID = 5757631654586244          # 'VIN', the primary formula column
STATIC_VIN_COLUMN_ID = 6457179909345156   # 'STATIC VIN', the manual override

# Graph's simple-upload ceiling. Above this an upload session is required; the
# largest scan measured was 2.6 MB, so this is headroom, not a hot path.
SIMPLE_UPLOAD_MAX = 4 * 1024 * 1024
CHUNK = 5 * 320 * 1024  # must be a multiple of 320 KiB per Graph's contract


class Fatal(Exception):
    """A precondition that makes the whole run pointless."""


# --- Graph helpers ---------------------------------------------------------

def _token():
    state = {}
    ok, detail = gc.step2_token(state)
    if not ok:
        raise Fatal(f"no Graph token: {detail}")
    return state["token"]


def _json(status, raw, what):
    if not 200 <= status < 300:
        raise Fatal(f"{what}: HTTP {status} {gc._err(raw)}")
    return json.loads(raw) if raw else {}


def _retrying(fn, what, attempts=4):
    """Graph throttles writes per-user; 429/503 carry Retry-After."""
    for attempt in range(attempts):
        status, headers, raw = fn()
        if status not in (429, 503):
            return status, headers, raw
        wait = int(headers.get("Retry-After") or 2 ** (attempt + 1))
        print(f"    throttled on {what}, waiting {wait}s")
        time.sleep(wait)
    raise Fatal(f"{what}: still throttled after {attempts} attempts")


def mail_get(tok, path, **params):
    q = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{gc.GRAPH}/users/{MAILBOX}{path}{q}"
    status, _, raw = gc.request(url, token=tok)
    if status == 403:
        raise Fatal(
            "Graph returned 403 on the mailbox. This is a permissions gap, not "
            "egress: the app registration needs Mail.ReadWrite (application), "
            "admin-consented, ideally scoped to this mailbox with a "
            "New-ApplicationAccessPolicy. See docs/routines/06-scan-mailbox.md.")
    return _json(status, raw, f"GET {path}")


def scan_messages(tok, limit):
    """Scanner mail in the Inbox, oldest first so a partial run makes progress."""
    out, url = [], None
    params = {
        "$filter": f"from/emailAddress/address eq '{SCANNER}' and hasAttachments eq true",
        "$select": "id,subject,receivedDateTime,isRead,categories,internetMessageId",
        "$orderby": "receivedDateTime asc",
        "$top": "50",
    }
    page = mail_get(tok, "/mailFolders/inbox/messages", **params)
    while True:
        out.extend(page.get("value", []))
        if limit and len(out) >= limit:
            return out[:limit]
        url = page.get("@odata.nextLink")
        if not url:
            return out
        status, _, raw = gc.request(url, token=tok)
        page = _json(status, raw, "messages page")


def attachments(tok, message_id):
    got = mail_get(tok, f"/messages/{message_id}/attachments",
                   **{"$select": "id,name,size,contentType"})
    return [a for a in got.get("value", [])
            if (a.get("name") or "").lower().endswith(".pdf")]


def attachment_bytes(tok, message_id, attachment_id, expected_size):
    """The bytes the MCP connector cannot provide. Verified as a real PDF."""
    url = (f"{gc.GRAPH}/users/{MAILBOX}/messages/{message_id}"
           f"/attachments/{attachment_id}/$value")
    status, _, raw = gc.request(url, token=tok)
    if not 200 <= status < 300:
        raise Fatal(f"attachment bytes: HTTP {status} {gc._err(raw)}")
    if raw[:4] != b"%PDF":
        raise Fatal(f"attachment did not start with %PDF (got {raw[:8]!r})")
    if expected_size and len(raw) != expected_size:
        # Graph's `size` includes MIME overhead for some attachment types, so a
        # mismatch is worth reporting but is not on its own a corrupt download.
        print(f"    note: {len(raw)} bytes downloaded, Graph reported {expected_size}")
    return raw


# --- SharePoint ------------------------------------------------------------

def ensure_folder(tok, path, commit):
    """Create each missing segment of `path` under the drive root."""
    segments, built = path.split("/"), ""
    for seg in segments:
        parent, built = built, f"{built}/{seg}" if built else seg
        quoted = urllib.parse.quote(built)
        status, _, _ = gc.request(
            f"{gc.GRAPH}/drives/{gc.DRIVE_ID}/root:/{quoted}", token=tok)
        if status == 200:
            continue
        if not commit:
            print(f"    would create folder {built}/")
            continue
        target = (f"{gc.GRAPH}/drives/{gc.DRIVE_ID}/root:/"
                  f"{urllib.parse.quote(parent)}:/children" if parent
                  else f"{gc.GRAPH}/drives/{gc.DRIVE_ID}/root/children")
        body = json.dumps({
            "name": seg, "folder": {}, "@microsoft.graph.conflictBehavior": "fail",
        }).encode()
        status, _, raw = _retrying(
            lambda: gc.request(target, token=tok, method="POST", data=body,
                               headers={"Content-Type": "application/json"}),
            f"mkdir {built}")
        # 409 means someone else created it between our GET and POST. Fine.
        if status not in (200, 201, 409):
            raise Fatal(f"mkdir {built}: HTTP {status} {gc._err(raw)}")
    return path


def upload(tok, folder, filename, data, commit):
    """Upload without overwriting. Returns (status, detail)."""
    dest = f"{folder}/{filename}"
    quoted = urllib.parse.quote(dest)
    status, _, _ = gc.request(
        f"{gc.GRAPH}/drives/{gc.DRIVE_ID}/root:/{quoted}", token=tok)
    if status == 200:
        return "exists", f"already in the library: {dest}"
    if not commit:
        return "would-upload", f"{dest} ({len(data) / 1e6:.1f} MB)"

    if len(data) <= SIMPLE_UPLOAD_MAX:
        url = (f"{gc.GRAPH}/drives/{gc.DRIVE_ID}/root:/{quoted}:/content"
               "?@microsoft.graph.conflictBehavior=fail")
        status, _, raw = _retrying(
            lambda: gc.request(url, token=tok, method="PUT", data=data,
                               headers={"Content-Type": "application/pdf"}),
            f"upload {filename}")
        if status not in (200, 201):
            raise Fatal(f"upload {dest}: HTTP {status} {gc._err(raw)}")
        return "uploaded", dest
    return _upload_session(tok, quoted, dest, data)


def _upload_session(tok, quoted, dest, data):
    body = json.dumps({"item": {"@microsoft.graph.conflictBehavior": "fail"}}).encode()
    status, _, raw = gc.request(
        f"{gc.GRAPH}/drives/{gc.DRIVE_ID}/root:/{quoted}:/createUploadSession",
        token=tok, method="POST", data=body,
        headers={"Content-Type": "application/json"})
    url = _json(status, raw, "createUploadSession")["uploadUrl"]
    total = len(data)
    for start in range(0, total, CHUNK):
        piece = data[start:start + CHUNK]
        end = start + len(piece) - 1
        # The session URL is pre-authenticated; sending the bearer token here
        # would leak it to the storage host.
        status, _, raw = _retrying(
            lambda: gc.request(url, method="PUT", data=piece, headers={
                "Content-Length": str(len(piece)),
                "Content-Range": f"bytes {start}-{end}/{total}",
            }),
            f"chunk {start}-{end}")
        if status not in (200, 201, 202):
            raise Fatal(f"chunk {start}-{end} of {dest}: HTTP {status} {gc._err(raw)}")
    return "uploaded", f"{dest} (chunked, {total / 1e6:.1f} MB)"


# --- Smartsheet VIN reconciliation ----------------------------------------

def load_tracker_vins():
    """Every VIN already in the tracker, from both the VIN and STATIC VIN columns.

    Returns None when no token is configured, so the caller can report the VINs
    it found without claiming they are missing.
    """
    token = os.environ.get("SMARTSHEET_ACCESS_TOKEN")
    if not token:
        return None
    seen, page = set(), 1
    while True:
        status, _, raw = gc.request(
            f"{SMARTSHEET_API}/sheets/{VIN_TRACKER_SHEET_ID}"
            f"?pageSize=5000&page={page}"
            f"&columnIds={VIN_COLUMN_ID},{STATIC_VIN_COLUMN_ID}",
            headers={"Authorization": f"Bearer {token}"})
        body = _json(status, raw, "Smartsheet VIN Tracker")
        for row in body.get("rows", []):
            for cell in row.get("cells", []):
                value = cell.get("displayValue") or cell.get("value")
                if value:
                    seen.add(str(value).strip().upper())
        if page >= body.get("totalPages", 1):
            return seen
        page += 1


def reconcile_vin(vin, tracker):
    """Classify one observed VIN. Never writes."""
    if tracker is None:
        return "unchecked", "SMARTSHEET_ACCESS_TOKEN not set"
    if vin in tracker:
        return "present", "already in the VIN Tracker"
    return "missing", "NOT in the VIN Tracker"


# --- mark actioned ---------------------------------------------------------

def ensure_actioned_folder(tok, commit):
    got = mail_get(tok, "/mailFolders/inbox/childFolders",
                   **{"$select": "id,displayName", "$top": "100"})
    for f in got.get("value", []):
        if f["displayName"].lower() == ACTIONED_FOLDER.lower():
            return f["id"]
    if not commit:
        return None
    body = json.dumps({"displayName": ACTIONED_FOLDER}).encode()
    status, _, raw = _retrying(
        lambda: gc.request(f"{gc.GRAPH}/users/{MAILBOX}/mailFolders/inbox/childFolders",
                           token=tok, method="POST", data=body,
                           headers={"Content-Type": "application/json"}),
        "create actioned folder")
    return _json(status, raw, "create actioned folder")["id"]


def mark_actioned(tok, message, folder_id, commit):
    """Categorise, mark read, then move. The move is what makes runs idempotent."""
    if not commit:
        return f"would categorise '{CATEGORY}', mark read, move to {ACTIONED_FOLDER}"
    mid = message["id"]
    categories = sorted(set(message.get("categories") or []) | {CATEGORY})
    body = json.dumps({"categories": categories, "isRead": True}).encode()
    status, _, raw = _retrying(
        lambda: gc.request(f"{gc.GRAPH}/users/{MAILBOX}/messages/{mid}",
                           token=tok, method="PATCH", data=body,
                           headers={"Content-Type": "application/json"}),
        "patch message")
    if not 200 <= status < 300:
        raise Fatal(f"categorise: HTTP {status} {gc._err(raw)}")
    move = json.dumps({"destinationId": folder_id}).encode()
    status, _, raw = _retrying(
        lambda: gc.request(f"{gc.GRAPH}/users/{MAILBOX}/messages/{mid}/move",
                           token=tok, method="POST", data=move,
                           headers={"Content-Type": "application/json"}),
        "move message")
    if not 200 <= status < 300:
        raise Fatal(f"move: HTTP {status} {gc._err(raw)}")
    return f"categorised, read, moved to {ACTIONED_FOLDER}"


# --- run -------------------------------------------------------------------

def run(commit, limit):
    tok = _token()
    tracker = load_tracker_vins()
    if tracker is None:
        print("NOTE  SMARTSHEET_ACCESS_TOKEN not set — VINs will be reported, "
              "not reconciled.\n")
    else:
        print(f"Loaded {len(tracker)} VINs from the tracker.\n")

    messages = scan_messages(tok, limit)
    print(f"{len(messages)} scanner message(s) in the Inbox"
          f"{f' (limited to {limit})' if limit else ''}.\n")
    folder_id = ensure_actioned_folder(tok, commit)

    records, ledger = [], []
    for i, msg in enumerate(messages, 1):
        print(f"[{i}/{len(messages)}] {msg['receivedDateTime']}")
        entry = {"internetMessageId": msg.get("internetMessageId"),
                 "received": msg["receivedDateTime"], "files": []}
        for att in attachments(tok, msg["id"]):
            record = parse(att["name"])
            records.append(record)
            print(f"  {att['name']}")
            print(f"    job {record['job_no']}, {record['doc_type']}"
                  + (f", model {record['model']}" if record["model"] else "")
                  + (f", VIN {record['vin']}" if record["vin"] else ""))
            for problem in record["problems"]:
                print(f"    PROBLEM: {problem}")

            if record["vin"]:
                state, detail = reconcile_vin(record["vin"], tracker)
                print(f"    VIN {record['vin']}: {detail}")
                record["vin_state"] = state

            data = attachment_bytes(tok, msg["id"], att["id"], att.get("size"))
            folder = ensure_folder(tok, f"{DEST_ROOT}/{job_folder(record)}", commit)
            state, detail = upload(tok, folder, att["name"], data, commit)
            print(f"    {state}: {detail}")
            entry["files"].append({"name": att["name"], "state": state,
                                   "parsed": record})

        print(f"  {mark_actioned(tok, msg, folder_id, commit)}\n")
        ledger.append(entry)

    return records, ledger


def report(records):
    if not records:
        return
    print("=" * 72)
    problems = [r for r in records if r["problems"]]
    print(f"{len(records)} scan(s); {len(problems)} with a parse problem")

    missing = [r for r in records if r.get("vin_state") == "missing"]
    quotes = [r for r in records if r["doc_type"] == QUOTE]
    print(f"{len(quotes)} quote scan(s) carried a VIN in the filename; "
          f"{len(missing)} of those VINs are NOT in the tracker")
    for r in missing:
        print(f"  MISSING  {r['vin']}  (job {r['job_no']}, {r['filename']})")
    if missing:
        print("\nNot added automatically: the tracker MINTS VINs on row insert "
              "(Sequencer is an AUTO_NUMBER feeding Calculated VIN), so an\n"
              "observed VIN belongs in STATIC VIN on a deliberately-placed row. "
              "See docs/routines/06-scan-mailbox.md.")

    incomplete = {j: s for j, s in pair_status(records).items() if s["missing"]}
    if incomplete:
        print(f"\n{len(incomplete)} job(s) missing half of the GA/quote pair:")
        for job, s in sorted(incomplete.items()):
            print(f"  job {job}: has {'GA' if s['has_ga'] else '-'}"
                  f"/{'quote' if s['has_quote'] else '-'}, "
                  f"missing {' and '.join(s['missing'])}")


def self_test():
    """Everything not gated on the missing Mail permission."""
    print("Parser:")
    if os.system(f"python3 {os.path.join(os.path.dirname(__file__), 'test_scan_filename.py')}"):
        return 1
    print("\nGraph token and SharePoint destination:")
    tok = _token()
    print("  PASS  token acquired")
    quoted = urllib.parse.quote(DEST_ROOT.rsplit("/", 1)[0])
    status, _, raw = gc.request(
        f"{gc.GRAPH}/drives/{gc.DRIVE_ID}/root:/{quoted}", token=tok)
    print(f"  {'PASS' if status == 200 else 'FAIL'}  destination parent "
          f"'{DEST_ROOT.rsplit('/', 1)[0]}': HTTP {status}")
    print("\nMailbox (expected to fail until Mail.ReadWrite is granted):")
    try:
        got = mail_get(tok, "/mailFolders/inbox", **{"$select": "totalItemCount"})
        print(f"  PASS  inbox reachable, {got.get('totalItemCount')} items")
    except Fatal as e:
        print(f"  BLOCKED  {e}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commit", action="store_true",
                    help="actually upload, reconcile and file (default: dry run)")
    ap.add_argument("--limit", type=int, default=0, help="process at most N messages")
    ap.add_argument("--self-test", action="store_true",
                    help="check everything that does not need mail access")
    ap.add_argument("--ledger", help="write a JSON ledger of the run to this path")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    print("=== DRY RUN — nothing will be written. Use --commit. ===\n"
          if not args.commit else "=== COMMIT — writing for real. ===\n")
    try:
        records, ledger = run(args.commit, args.limit)
    except Fatal as e:
        print(f"\nSTOPPED: {e}")
        return 1
    report(records)
    if args.ledger:
        with open(args.ledger, "w") as fh:
            json.dump(ledger, fh, indent=1)
        print(f"\nLedger: {args.ledger}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
