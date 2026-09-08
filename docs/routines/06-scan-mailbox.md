# Scanner mail → SharePoint, and VIN reconciliation

The Apeos C2567 in Parkes emails every scan to `automation@midlandind.com.au`.
Nobody works that mailbox. The routine files the PDFs into the **Completed Jobs**
library on the jobs site, reconciles any VIN against the VIN Tracker, and marks
the mail actioned.

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

## Destination: the Completed Jobs library

```
site    https://midlandind.sharepoint.com/sites/jobs
library Completed Jobs
drive   b!yK4jkE2PMEO7TLWlHgVkQR9Yzea0cmdLraKjspDsTfIYGnoqr1WfTry1_41JYSsj
path    <job no>/SCANNED PAPERWORK/<original filename>
```

**Not the sales drawings library**, which is what `graph_check.DRIVE_ID` points
at and what an earlier draft of this file wrongly specified. Scans belong with
the job, not with the drawing masters.

2,005 job folders, keyed by **bare job number** (`784`, `904`, `1130`, `2813`),
some with work-order subfolders (`W00475`, `FEA`). Each job folder carries a
standard set of categories — present on 10 of 12 sampled folders:

```
DRAWINGS   MANUFACTURING JOB CARD   NEW ORDER   PARTS
PHOTOS     PURCHASE ORDERS          VARIATIONS TO ORDER
```

Ingested scans go to a **`SCANNED PAPERWORK/`** subfolder rather than into
`DRAWINGS/` or `NEW ORDER/`, so machine-filed paper never mixes with the
hand-curated files. One constant in `scan_ingest.py` if that name should change.

Where a job has no folder, the routine **creates it with the standard
categories**, so an ingested scan never lands in a bare directory unlike every
other job. Job 751 uses `OUTSOURCED PARTS` in place of `PARTS`; that variant is
left alone where it already exists.

### The dedicated app needs this site granted to it

Measured with the *QM3* credential, `GET /sites/jobs` and the Completed Jobs
drive both return **200** — so that app already reaches this site, which is
contrary to what `04-graph-access.md` anticipated. **That does not carry over.**
The routine now runs under its own registration (below), and `Sites.Selected`
grants nothing until the site is named for that specific app.

So the jobs site must be granted to the new app explicitly, with **`write`** —
the routine creates folders and uploads files. Command and site id are in
"Grant it write on the jobs site only" below.

Write access to this library has never been probed under *any* credential: the
`PUT`/`DELETE`/`permanentDelete` probe recorded in `04-graph-access.md` was
against the *sales photo* library. The first `--commit --limit 1` run is the
check, and `--self-test` says so.

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

### RESOLVED — the scan job number is the Completed Jobs folder, not the tracker's

An earlier draft of this file said the scan job numbers "do not join" anything,
on the grounds that tracker `JobNumber` is `NNNN-NN` (`4529-01`) while scans say
`job no. 917`. The first half stands — **do not join scans to the VIN Tracker on
job number** — but the scans do join, to `Completed Jobs`:

- `Completed Jobs/917/` exists, and contains **`st319hdkib-13360.pvz`** — the
  exact model and drawing ref from `job no. 917 GA ST319HDKIB - 13360`.
- `Completed Jobs/917/PHOTOS/Job 917 - Civil Independence - ST-3/` holds 79 files
  named `Job 917 ST-3 #6T9T25R10NAKT4003 (38).JPG` — which independently
  confirms job 917 ↔ VIN `6T9T25R10NAKT4003`, the same pairing the quote scan's
  filename asserts.
- `ST-3` in those names is a value from the VIN Tracker's `TrailerType
  Identifier` picklist, and the scan's model code `ST319HDKIB` starts `ST3`.

So the join path is **scan → Completed Jobs job folder → VIN**, and the VIN is
the key into the tracker. The job number is not.

Of the 7 sampled job numbers, **917 and 751 have folders; 543, 341, 311, 564 and
269 do not** — most likely because those jobs are not finished. The routine
creates the folder rather than holding the mail (decided 2026-09-08), so watch
the first unbounded run for job folders appearing for live jobs.

### VIN coverage is capped by the missing OCR

The routine can only see VINs **typed into filenames** — in practice the
`Quote, VIN …` scans. A VIN printed on a page but not typed into the name is
invisible, because the PDFs have no text layer and cannot be read. Any claim of
full VIN reconciliation is therefore false until OCR is on at the device.

## BLOCKED: no app registration can reach the mailbox yet

Everything below step 1 is built and tested. Step 1 is not reachable:

```
FAIL  403  GET /users/automation@midlandind.com.au/mailFolders/inbox
FAIL  403  GET /users/menno@midlandind.com.au/mailFolders/inbox
PASS  200  GET /users/automation@  (directory)
PASS  200  Completed Jobs drive
```

**This is an HTTP 403, not a CONNECT 403** — the tunnel opened and Graph itself
refused, so it is a consent gap, not an egress one. (`04-graph-access.md` warns
these read alike and mean opposite things; here the distinction is the whole
diagnosis.) No new allowlist entry is needed: `graph.microsoft.com` and
`*.sharepoint.com` are already open, and the mailbox needs nothing further.

The last two lines are what make the diagnosis specific. The **same token** reads
the directory and SharePoint fine, so the credential is healthy and the denial is
mail-specific. And **every** mailbox 403s, not just `automation@` — which rules
out an `ApplicationAccessPolicy` scoping an existing Mail permission away from
that one mailbox. There is simply no Mail permission anywhere yet.

Diagnose a future 403 here the same way: try a second mailbox. One denied and one
allowed means a policy; both denied means a missing permission.

### A dedicated app registration

**Decided 2026-09-08: this routine gets its own app registration**, not a Mail
grant bolted onto the existing `QM3_DEV_Sharepoint`. The QM3 app was briefly
chosen and then reversed; the reasoning for the split is worth keeping because it
is what the credential layout now encodes:

- `QM3_DEV_Sharepoint` is a **dev** registration for the photo-tagging work,
  `HideApp`-tagged, holding exactly two permissions
  (`9492366f-…` / `df021288-…`, the well-known ids for `Sites.Selected` and
  `User.Read.All` — not resolvable in-tenant, the credential gets 403 on Graph's
  own `appRoles`). Adding mail to it would mean one weakly-protected secret
  reaching both the SharePoint estate and a mailbox.
- Its secret lives in an environment variable, which `04-graph-access.md` already
  flags: *"visible to anyone who can use the environment, and there is no secrets
  store yet."*
- Split as it is now, the scan app cannot touch the photo library and the QM3 app
  cannot touch a mailbox. Neither blast radius contains the other.

### Create it: run the provisioning script

`tools/provision_scan_app.ps1` does the whole thing in one run — app, service
principal, both permissions, consent, secret, the mail access policy, the
jobs-site grant, then verifies and prints the three environment variables.

```powershell
Install-Module Microsoft.Graph, ExchangeOnlineManagement, PnP.PowerShell
./tools/provision_scan_app.ps1 -WhatIf     # show what would change
./tools/provision_scan_app.ps1
```

Idempotent — re-running finds what exists and fills in the rest. The exception is
the client secret, which cannot be read back after creation; `-NewSecret` rotates
it. **Not validated by execution**: no PowerShell in the repo's container, so it
has been written carefully but never run. Use `-WhatIf` first.

#### Why a script and not automation from the repo

This step cannot be automated from a session, and the reason is worth recording
so nobody retries it:

```
POST /applications              -> 403 Insufficient privileges
GET  /servicePrincipals (list)  -> 403 Insufficient privileges
GET  /oauth2PermissionGrants    -> 403 Insufficient privileges
```

Measured with the QM3 credential, which holds `Sites.Selected` and
`User.Read.All`. Adding directory-write rights to an app so it could create
another app would make every app-only credential a privilege-escalation path,
which is exactly why Entra requires an interactive admin for consent. There is a
bootstrap floor and any credential this repo holds sits below it.

Everything *after* consent is automatable, and the routine itself needs no admin
rights at run time — only the three variables.

#### What the app needs, for reference

| Permission | Scope | Why |
|---|---|---|
| `Mail.ReadWrite` | `automation@` only, by access policy | read mail, download attachments, categorise, mark read, move |
| `Sites.Selected` | the **jobs** site only, `write` | create folders and upload into `Completed Jobs` |

`Mail.Read` alone is not enough: without write there is no way to mark a message
actioned, and without that the routine cannot tell processed from unprocessed and
would re-ingest all 226 every run. `Mail.Send` is **not** needed and must not be
added — the routine never sends. Do **not** grant `Sites.ReadWrite.All`; that is
the whole estate, and `Sites.Selected` plus a per-site grant is the pattern this
repo already uses.

The script resolves both role IDs **by name** from Microsoft Graph's own service
principal rather than hardcoding GUIDs, so a wrong name fails loudly instead of
granting the wrong permission.

Portal equivalent, if the script cannot be used: **Entra ID → App registrations →
New registration**, then **API permissions → Add a permission → Microsoft Graph →
Application permissions**, add both, then **Grant admin consent for Midland**.
Both permissions are inert until that consent button is pressed.

### Scope the mail grant in the same change, not afterwards

`Sites.Selected` is safe by default — it grants nothing until a site is named.
`Mail.ReadWrite` is the opposite: **on consent it reaches every mailbox in the
tenant.** Close that window immediately.

```powershell
Connect-ExchangeOnline
New-ApplicationAccessPolicy `
  -AppId <new-client-id> `
  -PolicyScopeGroupId automation@midlandind.com.au `
  -AccessRight RestrictAccess `
  -Description "Scan ingest routine - automation@ only"
```

Prove the scope actually bit — **both** checks, because only the second can fail
informatively:

```powershell
Test-ApplicationAccessPolicy -Identity automation@midlandind.com.au -AppId <new-client-id>   # expect: Granted
Test-ApplicationAccessPolicy -Identity menno@midlandind.com.au      -AppId <new-client-id>   # expect: Denied
```

`Granted` on the first with `Denied` on the second is the only result meaning the
grant is both working and contained. Propagation takes a few minutes; re-probe
rather than assuming failure.

### Grant it write on the jobs site only

```
site        https://midlandind.sharepoint.com/sites/jobs
site id     midlandind.sharepoint.com,9023aec8-8f4d-4330-bb4c-b5a51e056441,e6cd581f-72b4-4b67-ada2-a3b290ec4df2
library     Completed Jobs
drive id    b!yK4jkE2PMEO7TLWlHgVkQR9Yzea0cmdLraKjspDsTfIYGnoqr1WfTry1_41JYSsj
```

`write` — not `read`. The routine creates folders and uploads files:

```powershell
Connect-PnPOnline -Url https://midlandind.sharepoint.com/sites/jobs -Interactive
Grant-PnPAzureADAppSitePermission `
  -AppId <new-client-id> `
  -DisplayName "Midland-ScanIngest" `
  -Site https://midlandind.sharepoint.com/sites/jobs `
  -Permissions Write
```

Note this is a **site**-level grant, so it covers every library on the jobs site,
not just `Completed Jobs` — Graph has no per-library granularity here. That is
wider than strictly needed and is the accepted floor.

### Then set three variables

On the `Midland` cloud environment, alongside the existing `GRAPH_*` set, which
stays untouched and keeps serving the QM3 tooling:

```
SCAN_GRAPH_TENANT_ID=36c6a58f-2544-4e95-b4bc-039423137847
SCAN_GRAPH_CLIENT_ID=<new-client-id>
SCAN_GRAPH_CLIENT_SECRET=<new-secret>
```

`scan_ingest.py` reads **only** these and **deliberately does not fall back** to
`GRAPH_*`. A silent fallback would run the routine under an app that is not
scoped for it, and the resulting failure would read as a permissions bug rather
than a missing variable.

Per `04-graph-access.md`, both variable and allowlist changes reach a running
session — re-probe, do not restart. No new allowlist entry is needed:
`login.microsoftonline.com`, `graph.microsoft.com` and `*.sharepoint.com` are
already open, and mail needs nothing further.

Then, from this repo:

```sh
python3 tools/scan_ingest.py --self-test    # token and mailbox lines flip to PASS
```

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
