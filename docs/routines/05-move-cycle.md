# Routine 5 — the move cycle: SharePoint → media library → delete

Tested end to end on 2026-08-31 against `z.Tare Weights Copy`, a throwaway folder Midland
created for the purpose. Two files, 6.78 MB, both ingested and then removed.

A move is **not** an ingest with a delete bolted on. The delete is irreversible and the
media library exposes no read endpoint, so the whole risk sits in proving the copy landed
before destroying the source.

## The gates, in order — never reorder these

**1. Establish the source is not unique.** Compare `quickXorHash` against wherever the
originals live. For the test, `z.Tare Weights Copy` was byte-identical to `z.Tare Weights`,
so the delete could not destroy anything unique. If there is no second copy, that fact
belongs in front of a human before anything is deleted.

**2. Ingest, and read the response.** `mediaId` and `occurrenceId` returned, `HTTP 200`.

**3. Prove the bytes are actually stored — do not trust step 2 alone.** There is no read
endpoint (`x-media-key` authorises only `/api/media/ingest`), so the only available proof
is a **re-POST of the identical bytes**: the server must answer `isNew: false`,
`deduped: true`, and a `sha256` matching the locally computed hash. That is a genuine
existence check — the server can only dedup against a blob it holds.

```
3.jpg          mediaId=48 occ=44 isNew=False deduped=True  sha matched -> STORED
Deck Widener   mediaId=49 occ=45 isNew=False deduped=True  sha matched -> STORED
```

**4. Only then delete**, and verify by id, by path, and by re-listing the parent.

## The permission finding — the grant is wider than the docs assume

`04-graph-access.md` says *"Only read access is required. The routine never writes to
SharePoint."* That is still true of what the routine **needs**, but it is not true of what
the app **has**. Probed with a throwaway file before touching real data:

| Operation | Result |
|---|---|
| `PUT .../content` (create) | **201** |
| `DELETE .../items/{id}` | **204** |
| `POST .../items/{id}/permanentDelete` | **204** |

**The application can create, delete and permanently delete anything in the sales photo
library.** For a project whose enumeration and tagging passes are read-only, that is more
authority than the work requires, and it is worth a deliberate decision rather than an
accident. If move cycles become routine the grant is right; if they do not, it should be
narrowed.

## DELETE sends files to the recycle bin. permanentDelete does not.

**This is the part the test got wrong, and it matters for "make sure the data is gone".**

An ordinary `DELETE` returns `204` and the item 404s by id, by path, and in the parent
listing — it is gone from the library in every way the API can see. It is **not gone from
SharePoint**: it sits in the site recycle bin, 93 days by default, then a second-stage bin.

Graph exposes `POST /drives/{driveId}/items/{itemId}/permanentDelete` on **v1.0**, verified
returning `204` here. That is the call to use when the requirement is that the data is
actually gone.

The recycle bin itself is **not reachable from this app.** A SharePoint-scoped token issues
fine (`https://midlandind.sharepoint.com/.default` → 200) but `_api/web/RecycleBin` returns
**401**: Graph's `Sites.Selected` does not carry SharePoint REST access. So an item already
sent to the bin by an ordinary `DELETE` can only be purged by a site admin in the UI, or by
granting the app SharePoint REST permissions.

**Rule for the routine: use `permanentDelete`, not `DELETE`.** Ordinary delete leaves a
93-day copy that nobody asked for and that this app cannot clean up.

## What the test actually left behind

Two files and a folder were removed with ordinary `DELETE` before this was understood:

```
Sales/1. Trailer Photos/z.Tare Weights Copy/3.jpg
Sales/1. Trailer Photos/z.Tare Weights Copy/Deck Widener - Dyson 11.59 tonnes as pictured.JPG
Sales/1. Trailer Photos/z.Tare Weights Copy/            (the folder)
```

They are **in the site recycle bin** and need emptying by hand to complete the removal.
Nothing unique was lost: both files remain byte-identical in `z.Tare Weights`, which was
re-checked after the delete and is intact (2 files, 6.78 MB).

## Verification actually run

| Check | Result |
|---|---|
| Both items by id | `404` |
| Folder by id | `404` |
| Both by path | `404` |
| Parent listing contains `z.Tare Weights Copy` | **false** |
| Parent listing contains `z.Tare Weights` | **true** |
| Original folder | `200`, childCount 2, 6.78 MB — untouched |
| Recycle bin | **unreachable, contents unverified** |
