# Microsoft Graph access for the tagging routine

Agreed: the routine uses Graph directly rather than waiting for a server-side
`sourceUrl` fetch in the media library. This unblocks `dataBase64`, and it turns out to
improve the enumeration pass too.

## Why this is an upgrade, not just a workaround

The MCP connector was only ever going to give us rendered images. Graph gives the routine
three things the connector cannot:

1. **Raw bytes** — `GET /drives/{driveId}/items/{itemId}/content`, which is what
   `dataBase64` needs.
2. **Delta enumeration** — `GET /drives/{driveId}/root/delta` returns a token, and a
   later call with that token returns *only what changed*. That is a far better resume
   mechanism than the checkpoint-per-folder scheme in `01-enumeration.md`: the second run
   over a 250 GB library sees the handful of new files rather than re-walking the tree.
   Worth reworking the enumeration routine around this.
3. **Server-side thumbnails** — `/thumbnails` with a custom size. These are generated
   auto-oriented, which may settle the EXIF question independently of the media library's
   `md` rendition. Worth testing whether a large custom thumbnail keeps VIN plates and
   chassis-marked job numbers legible; if it does, the vision pass can read Graph
   thumbnails and never touch a full-resolution original.

Graph also carries `file.hashes.quickXorHash`, `photo` facets and `image` dimensions,
which sharpen the manifest at no extra cost.

## Permissions — ask for `Sites.Selected`, not `Files.Read.All`

Routines run unattended, so this needs **application** permissions via client
credentials, not delegated. The instinct is `Files.Read.All` or `Sites.Read.All`; both
grant the app read access to *every* site in the tenant, which is far more than this needs.

**`Sites.Selected`** is the least-privilege option: the app gets no access by default,
and an administrator then grants read on specific sites — here just
`SalesMarketingTeam`. If the job-card join is ever unparked, `jobs` gets added the same
way, deliberately.

Only read access is required. The routine never writes to SharePoint; its only write is
to the media library.

## Credentials

Client credentials flow against Entra ID. Three values, set as environment variables on
the `Midland` cloud environment:

```
GRAPH_TENANT_ID=...
GRAPH_CLIENT_ID=...
GRAPH_CLIENT_SECRET=...
```

Note the caveat from the cloud environment docs: **environment variables are visible to
anyone who can use the environment, and there is no secrets store yet.** A client secret
here is not well protected. Two mitigations worth considering: prefer a
certificate-based credential if the tooling allows it, and give the secret a short
expiry with a rotation reminder. Same applies to `MEDIA_INGEST_KEY`.

Nothing goes in the repo. The routine reads from `os.environ`.

## Egress: three or four more hosts, and one that is easy to miss

This is the part that will fail mid-run if it is missed. The `Midland` environment's
`Custom` allowlist currently contains only `qm3staging.midlandind.com.au`. Graph traffic
from the routine goes out through the session's network — it is *not* covered by the MCP
connector's bypass, because the routine is calling Graph itself, not through the
connector.

Add:

```
login.microsoftonline.com
graph.microsoft.com
*.sharepoint.com
```

The third one is the trap. A Graph content request does not stream bytes from
`graph.microsoft.com` — it **302s to a pre-authenticated storage URL on a different
host**, typically under `*.sharepoint.com`, and depending on tenant also `*.svc.ms` or
`*.blob.core.windows.net`. Allow `graph.microsoft.com` alone and every download fails at
the redirect, after authentication has already succeeded — which reads like a code bug
rather than a network policy.

Practical approach: add the three above, then run a single-file download test and read
the actual redirect host out of the failure or the `Location` header before adding more.
Better to discover that on one file than 30,000.

## Verified state — 2026-08-26, from the `Midland` environment

Measured in session `session_016EmSbCtVTxyNtCkqCimdwn`, environment
`env_0175ZY9ro2ikpeDDEHXq7R4t`. Run `python3 tools/graph_check.py` to re-measure.

**Steps 1-5 pass. Step 6 fails on one missing allowlist entry** — see the table below.

| Host | Result | Meaning |
|---|---|---|
| `qm3staging.midlandind.com.au` | **401** | Step 1 passes. Host up, wanting auth |
| `login.microsoftonline.com` | **302** | Allowlisted. Step 2 acquires a token |
| `graph.microsoft.com` | **open** | Allowlisted. Steps 3-6 reach the API |
| `midlandind.sharepoint.com` | **open** | Allowlisted. **This is where `/content` redirects** |
| `australiaeast1-mediap.svc.ms` | **CONNECT 403** | **Not allowlisted.** Thumbnails come from here. Blocks step 6 |
| `pypi.org`, `registry.npmjs.org` | 200 | Reachable — but via the proxy's `noProxy` bypass, not the tick |
| `raw.githubusercontent.com` | 301 | Allowed through the gateway |

So the package-manager question is answered — installs work — though note the mechanism
is the bypass list, so it is not evidence about the allowlist itself.

**Outstanding: add `*.svc.ms`** (or at minimum `australiaeast1-mediap.svc.ms`) to the
`Midland` allowlist. Nothing else is missing.

### Bytes and thumbnails come from two *different* hosts

The warning in this file was right that a content request redirects, and half right about
where. Measured on a real 4000x3000 item:

- `GET /items/{id}/content` → **302 → `midlandind.sharepoint.com`** → 200, 3,154,822 bytes.
  Covered by the `*.sharepoint.com` entry, so `dataBase64` works today.
- `GET /items/{id}/thumbnails` → URLs on **`australiaeast1-mediap.svc.ms`**, a
  region-specific media host that `*.sharepoint.com` does **not** cover.

So `*.svc.ms` is not an "and depending on tenant also" footnote — on this tenant it is
required the moment the vision pass prefers a rendition over a full original. Note the
region prefix: another tenant region would give a different subdomain, which is the
argument for the `*.svc.ms` wildcard over pinning one host.

### Allowlist propagation, and a wildcard that does not match

`*.sharepoint.com` went live **within about two minutes** of being added.
`graph.microsoft.com` was reported added and then refused CONNECT for a further ten
minutes — because it had been entered as `*.graph.microsoft.com`. **A leading `*.` does
not match the bare host.** It opened immediately once the `*.` was dropped.

If a host has not opened within a few minutes, do not wait longer: check the entry saved,
and that it is a bare hostname (no scheme, no path, no trailing slash, no stray `*.`).

Distinguish the two 403s carefully, because they read alike and mean opposite things:
a **CONNECT 403** is the gateway refusing to open the tunnel (host not allowlisted),
while a plain **HTTP 403** means the tunnel opened and the *server* answered. The first
is a policy problem, the second is progress.

### CORRECTED — an allowlist change *does* reach a running session

This file previously stated that network policy is bound at container start and that
"a *running* session never picks up an egress change, so verification always needs a
freshly started session." **That is wrong, and it was disproved here.**
`*.sharepoint.com` was added mid-session and went from CONNECT 403 to a live HTTP 403
with no restart — the proxy's own `recentRelayFailures` log shows the rejections stopping
at the moment of the change. Do not burn a session restart on an allowlist edit; re-probe
the host instead.

### CORRECTED — environment variables also reach a running session

An earlier draft of this section claimed the opposite: that variables are inherited at
process start and therefore need a fresh session. **That is wrong.** All four credentials
were added mid-session and became readable with no restart, in the same session that had
reported them missing minutes earlier.

The reasoning behind the wrong claim is worth recording, because the diagnostic that
produced it is still misleading. The variables do **not** appear in **PID 1's**
environment even once they are working — the runner injects them into the agent process,
not into container init. So `/proc/1/environ` is **not** a valid test of whether a
variable is available; it reports absent for a variable that is present and usable.

Check the shell's own environment instead, which is what `tools/graph_check.py` does:

```sh
[ -n "$GRAPH_CLIENT_ID" ] && echo set     # never echo the value
```

Short version: **both allowlist and variable changes are live. Neither needs a new
session — re-probe instead of restarting.**

### The redirect trap also catches your diagnostics

`login.microsoftonline.com` first appeared blocked. It is not — it answers `302` to
`https://www.office.com/login`, and it is *that* host which is denied. Any client
following redirects automatically reports the denial against the **original** host, so a
reachable host looks blocked and the allowlist entry gets added in the wrong place.

`tools/graph_check.py` therefore follows redirects manually, one hop at a time, and names
the host of the hop that actually failed. It also drops the `Authorization` header when
crossing to a redirect target — Graph's storage URL is pre-authenticated, and forwarding
a bearer token to another host leaks it.

## Test order

Cheapest-first, so each step's failure is unambiguous. Automated in
`tools/graph_check.py`, which runs steps 1-6 and stops at the first failure:

1. Token from `login.microsoftonline.com` — proves credentials and the first egress host.
2. `GET /sites/{...}/drives` — proves `Sites.Selected` was actually granted on the site.
3. `GET /drives/{driveId}/items/{itemId}` on one known file — proves item access.
4. `GET .../content` on that file — proves the redirect host is allowed. **This is the
   step most likely to fail.**
5. `GET .../thumbnails` at a large custom size — settles the EXIF and legibility question.
6. Only then a single end-to-end ingest into the media library.

Steps 1-5 are read-only and create nothing. Step 6 creates one asset in staging.

## Thumbnails: the API is fussier than the docs suggest

Four things cost time here; all are encoded in `tools/graph_check.py`.

1. **The default sizes are useless for this task.** `large` came back **600px** on the
   long edge. VIN plates and chassis-marked job numbers are gone well before that, so a
   custom size is mandatory, not an optimisation.
2. **Use bare `select=` / `expand=`, not `$select=` / `$expand=`.** With the `$` prefix
   Graph applies strict OData property validation and rejects the size outright —
   *"Could not find a property named 'c1600x1200_Crop' on type
   `microsoft.graph.thumbnailSet`"*. Without the `$`, the same string is read as a
   thumbnail descriptor and honoured. Requesting the size as a path segment
   (`/thumbnails/0/c1600x1600`) fails differently again, with an internal server error.
3. **`_Fit` is not supported; only `_Crop`.** `c1600x1600_Fit` returns *"Unsupported
   options were provided in the thumbnail descriptor."*
4. **Therefore never request a square box.** `_Crop` on `c1600x1600` against a 4:3 frame
   squares it off and discards a third of the image — including, quite possibly, the axle
   group you are trying to count. Derive the box from the item's own `image.width` /
   `image.height` so the crop is a no-op: `c1600x1200_Crop` on a 4000x3000 original
   returns a true 1600x1200. `c2048x1536_Crop` also works, so there is headroom.

### This answers the `md` rendition question

`routines/03-media-library-api.md` left open whether the media library's `md.webp` is at
least 1600px on the long edge, and flagged that VIN plates and chassis-marked job numbers
are the only real identity signals — so a small rendition would cost the ability to say
*which* trailer is in shot.

Graph settles it independently: **a custom thumbnail at 1600px or 2048px on the long
edge, auto-oriented, is available per item.** The vision pass never needs a
full-resolution original and never needs the media library's rendition, so `md`'s long
edge stops being on the critical path. It still wants confirming before anything depends
on `md` specifically, but nothing does now.

Legibility at 1600px has **not** been eyeball-checked yet — that needs `*.svc.ms`
allowlisted so a rendition can actually be fetched and looked at. Treat 1600px as the
requirement, not as a verified sufficiency.

## Consequence for the enumeration routine

`01-enumeration.md` is written against the MCP connector, walking folders with
`read_resource` and checkpointing per top-level folder. With Graph available, `/delta` is
strictly better and the recursion hazard largely disappears — delta returns a flat list
of items with their parent references, so there is no walk to get wrong and no
"folder looks empty because it only holds subfolders" failure mode.

That rewrite should wait until steps 1-4 above actually pass. No point rewriting against
an API we have not yet authenticated to.
