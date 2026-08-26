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

## Test order

Cheapest-first, so each step's failure is unambiguous:

1. Token from `login.microsoftonline.com` — proves credentials and the first egress host.
2. `GET /sites/{...}/drives` — proves `Sites.Selected` was actually granted on the site.
3. `GET /drives/{driveId}/items/{itemId}` on one known file — proves item access.
4. `GET .../content` on that file — proves the redirect host is allowed. **This is the
   step most likely to fail.**
5. `GET .../thumbnails` at a large custom size — settles the EXIF and legibility question.
6. Only then a single end-to-end ingest into the media library.

Steps 1-5 are read-only and create nothing. Step 6 creates one asset in staging.

## Consequence for the enumeration routine

`01-enumeration.md` is written against the MCP connector, walking folders with
`read_resource` and checkpointing per top-level folder. With Graph available, `/delta` is
strictly better and the recursion hazard largely disappears — delta returns a flat list
of items with their parent references, so there is no walk to get wrong and no
"folder looks empty because it only holds subfolders" failure mode.

That rewrite should wait until steps 1-4 above actually pass. No point rewriting against
an API we have not yet authenticated to.
