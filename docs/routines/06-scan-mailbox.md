# Scanner mail → SharePoint, and VIN reconciliation

The Apeos C2567 in Parkes emails every scan to `automation@midlandind.com.au`.
Nobody works that mailbox. The routine files the PDFs into the sales drawings
library, reconciles any VIN against the VIN Tracker, and marks the mail actioned.

Implemented in `tools/scan_ingest.py`; filename parsing in `tools/scan_filename.py`
with tests in `tools/test_scan_filename.py`.

## Measured state of the mailbox — 2026-09-08

| | |
|---|---|
| Scanner mail | **226 messages**, 26 Aug – 7 Sep 2026 |
| Sender | `noreply@viatek-scan.com.au`, device `Apeos C2567` (`FF-1C7D226F55EB`) |
| Attachments | one image-only PDF each, 480 KB – 2.6 MB |
| Read state | **all but the oldest are unread** — nothing consumes this mailbox |
| `Device Location` | blank on every message |

**Do not filter on subject.** Two forms are in use: `Scanned Document` on the
oldest message and `Scan Data from FF-1C7D226F55EB` on everything after.
`tools/scan_ingest.py` filters on the sender address, which is stable.

### The PDFs carry no text layer

`GET /attachments/{id}/$value` returns a valid `%PDF`, but the pages are raw
scanner images — the device applies no OCR. So **nothing inside a page is
machine-readable**, and every field the routine extracts comes from the filename.

That is the single biggest constraint on this routine, and it caps VIN coverage
(below). Turning on searchable-PDF output at the device would lift it.

## Filenames are the data, and operators type them

The device appends its own suffix, so every name is:

    <operator text>-<DDMMYYYYHHMMSS>-<NNNN>.pdf

The timestamp is device-local, **UTC+10** (measured against `receivedDateTime`).
Real examples, all observed:

```
job no. 917 GA ST319HDKIB - 13360-07092026163543-0001.pdf
job no. 917 Quote, VIN 6T9T25R10NAKT4003-07092026163802-0001.pdf
job no. 269 GA DW319SWKOH - 15650 - L-03092026150505-0001.pdf   <- ref split again
job no. 751-26082026163015-0001.pdf                             <- no description
job no. 564 GA TG219SFPOR - 8000A-03092026150020-0001.pdf       <- letter O ...
job no. 311 GA TG320SFP0R - 9000J-07092026150515-0001.pdf       <- ... vs digit 0
```

Consequences encoded in the parser:

- **Never validate a model code against a vocabulary.** `TG219SFPOR` and
  `TG320SFP0R` differ only in O-versus-zero and both are real. Capture verbatim.
- **A drawing ref can itself contain ` - `** (`15650 - L`), so split the device
  suffix off first, by anchored regex, and only then read the operator text.
- **Job number is the only field worth trusting.** Everything else is absent
  often enough that the parser reports problems rather than rejecting a name.
- **Sanitise before it becomes a path.** `"*:<>?/\|` are all legal in a scanner
  filename and none are legal in a SharePoint path.

### Jobs come in GA + quote pairs, and mostly arrive incomplete

Operators scan a general arrangement and a quote per job, a minute or two apart.
Of the 7 jobs in the sampled backlog, **only job 917 had both halves.** So the
GA/quote pair check is a live exception report, not a parser diagnostic.

## Destination

`SALES DRAWINGS/SCANNED JOB CARDS/job <n>/`, in the already-granted drive
`Documents` on `SalesMarketingTeam`.

**Not** `SALES DRAWINGS/TRAILERS BY JOB NO`, despite the name — that folder holds
84 subfolders keyed by **customer** (`TOLL`, `VULCAN`, `WMTH`, …), not by job
number, and the filenames carry no customer. Filing scans there would need a
customer lookup the scans cannot supply.

## VIN reconciliation — the tracker MINTS VINs, so do not just add rows

Target: `VIN Tracker`, sheet id `3933652678666116`, 1,615 rows.

Read the schema before writing anything to it. It is a **generator**, not a list:

| Column | Behaviour |
|---|---|
| `VIN` (primary) | formula: `STATIC VIN` if present, else `Calculated VIN` |
| `Calculated VIN` | WMI + VTA + year letter + place + extension + `Sequential Number` |
| `Sequential Number` | `Sequencer - 873` |
| `Sequencer` | **`AUTO_NUMBER`** — increments on every row insert |
| `STATIC VIN` | manual override, locked column |
| `Validate` | `COUNTIF` over `VIN` — the sheet's own duplicate detector |

**Inserting a row therefore mints the next VIN in the sequence.** A VIN read off a
scanned quote was minted elsewhere, so it belongs in `STATIC VIN` on a
deliberately-placed row — never as a plain insert, which would both burn a
sequence number and publish a VIN Midland did not allocate. `STATIC VIN` is also
`locked: true`, so an API write to it may need an admin-level share.

This is why `tools/scan_ingest.py` **reports** missing VINs and does not add them.
Automating the insert needs a decision on row placement and on whether the
routine may write a locked column.

### Two VIN families, and 928 static rows

- Generated VINs are `6K9…` — the `World Manufacturer Identifier` formula is
  literally `="6K9"`. All 285 rows in the first sample were `6K9`.
- **`6T9…` VINs are the static family**, and there are a lot: **928 of 1,615 rows
  carry a `STATIC VIN`**, most with no `JobNumber` at all. For those rows the VIN
  is the only join key.

So a `6T9…` VIN off a quote is not an anomaly — it is the normal shape of a
static entry, and reconciliation must check **both** the `VIN` and `STATIC VIN`
columns. `scan_ingest.load_tracker_vins()` reads both.

### The one VIN currently visible is already there

`6T9T25R10NAKT4003`, off job 917's quote scan, is **already in the tracker** —
row `4937720298596228`, in both the `VIN` and `STATIC VIN` columns. Nothing to add.

Confirming that needed `limit: 20000` on `find_in_sheet`: the default searches
only the first 100 rows and reports `occurrences: 0` with no indication that it
stopped early. A zero from that tool is meaningless without the row count.

### Job numbers do not join

Tracker `JobNumber` is `NNNN-NN` (`4529-01`, `4188-01`). Scan filenames say
`job no. 917`, `job no. 543` — bare three-digit numbers. **These are different
numbering schemes**, and none of 917/543/341/311/564/269/751 appear in the
tracker sample. Do not join scans to the tracker on job number until someone
confirms what the scanned `job no.` refers to.

### VIN coverage is capped by the missing OCR

The routine can only see VINs **typed into filenames** — in practice the
`Quote, VIN …` scans. A VIN printed on a page but not typed into the name is
invisible, because the PDFs have no text layer and cannot be read. Any claim of
full VIN reconciliation is therefore false until OCR is on at the device.

## BLOCKED: the app registration has no Mail permission

Everything below step 1 is built and tested. Step 1 is not reachable:

```
FAIL  403  GET /users/automation@midlandind.com.au/mailFolders/inbox
           Access is denied. Check credentials and try again.
```

**This is an HTTP 403, not a CONNECT 403** — the tunnel opened and Graph itself
refused, so it is a consent gap, not an egress one. (`04-graph-access.md` warns
these read alike and mean opposite things; here the distinction is the whole
diagnosis.) No new allowlist entry is needed: `graph.microsoft.com` and
`*.sharepoint.com` are already open, and the mailbox needs nothing further.

### What to grant

On the existing app registration, add **application** (not delegated) permission:

| Permission | Why |
|---|---|
| `Mail.ReadWrite` | read the mail, download attachments, set categories, mark read, move |

`Mail.Read` alone is not enough: without write there is no way to mark a message
actioned, and without that the routine cannot tell processed from unprocessed and
would re-ingest all 226 every run.

Then admin-consent it, and **scope it to this one mailbox** — the default grant
reads every mailbox in the tenant, which is far more than this needs and is the
same least-privilege argument that chose `Sites.Selected` over `Files.Read.All`:

```powershell
New-ApplicationAccessPolicy -AppId <client-id> `
  -PolicyScopeGroupId automation@midlandind.com.au `
  -AccessRight RestrictAccess `
  -Description "Scan ingest routine — automation@ only"
```

Verify with `Test-ApplicationAccessPolicy`, then `python3 tools/scan_ingest.py
--self-test`, which reports the mailbox line as PASS once consent lands.

`SMARTSHEET_ACCESS_TOKEN` is a separate, independent credential, needed only for
step 4. Without it the routine still files PDFs and reports the VINs it saw; it
just cannot say whether they are already tracked.

## Idempotency

The move in step 5 is the state marker: processed mail leaves the Inbox, so the
next run's `/mailFolders/inbox/messages` query sees only new scans. Uploads
additionally use `conflictBehavior=fail` and pre-check the path, so a run that
dies halfway resumes without duplicating a file. The category and the read flag
are for humans; the folder is what the code keys off.

There is deliberately **no local state file** — nothing in this repo has to stay
in sync with the mailbox for the routine to be correct.

## Running it

```sh
python3 tools/scan_ingest.py --self-test     # no mail access needed
python3 tools/scan_ingest.py                 # dry run, reports every action
python3 tools/scan_ingest.py --limit 5       # dry run over five messages
python3 tools/scan_ingest.py --commit --limit 1   # first real one, one message
python3 tools/scan_ingest.py --commit --ledger run.json
```

Dry run is the default and writes nothing. Do the backlog as
`--commit --limit 1` first, check the library and the mailbox by eye, then let it
run unbounded.
