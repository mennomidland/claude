#!/usr/bin/env python3
"""Verify Graph access for the tagging routine — steps 1-6 of routines/04-graph-access.md.

Read-only. Creates nothing. **Does not perform step 7** (the end-to-end ingest); that
step writes an asset into staging and is deliberately not automated here.

Cheapest-first, so each failure is unambiguous about which precondition is missing:

  1. egress to the media library host      -> network policy
  2. token from login.microsoftonline.com  -> credentials + first egress host
  3. GET /sites/{id}/drives                -> Sites.Selected actually granted
  4. GET /drives/{id}/items/{id}           -> item access
  5. GET .../content (no redirect follow)  -> the storage host, read from Location
  6. GET .../thumbnails at a large size    -> EXIF/legibility question

Run: python3 tools/graph_check.py [--item-id ID] [--json]

Never prints a credential or an access token. Step 5 deliberately does **not** follow
the redirect: the whole diagnostic value is reading the storage host out of `Location`
so it can be added to the allowlist before 30,000 downloads depend on it.
"""
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

SITE_HOST = "midlandind.sharepoint.com"
SITE_PATH = "/sites/SalesMarketingTeam"
DRIVE_ID = "b!kxUlnz9hTEGIP79tTDljrR9Yzea0cmdLraKjspDsTfIFN9XvZPm7RKua__mqYOLv"
LIBRARY_ROOT = "Sales/1. Trailer Photos"
# Small, known folder from the test run -- a cheap place to find one real image.
PROBE_FOLDER = f"{LIBRARY_ROOT}/Auto Twist Lock Skels"
INGEST_HOST = "https://qm3staging.midlandind.com.au/"
GRAPH = "https://graph.microsoft.com/v1.0"
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".webp", ".bmp")
THUMB_SIZE = 1600  # the long edge the vision pass needs; see step 6 note below

CREDS = ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET")
_ctx = ssl.create_default_context()


class Blocked(Exception):
    """A step could not run. `kind` separates a policy denial from an auth failure."""

    def __init__(self, kind, detail):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface a 3xx as a result rather than following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _classify(err, host):
    """Map a transport failure onto the precondition it actually implicates."""
    text = str(err)
    if "Tunnel connection failed" in text or ("403" in text and "CONNECT" in text.upper()):
        return Blocked("egress", f"{host} is not in the environment allowlist (CONNECT 403)")
    return Blocked("network", f"{host}: {text}")


def _one(url, token, method, data, headers):
    """A single hop, never following a redirect, so the host attempted is always known."""
    hdrs = dict(headers or {})
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=_ctx), _NoRedirect())
    try:
        with opener.open(req, timeout=60) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        # A 3xx lands here because redirects are not followed, and so does every 4xx/5xx.
        return e.code, dict(e.headers or {}), e.read()
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        # Name the host of THIS hop. Letting urllib follow redirects internally would
        # report the original host for a denial that actually happened at the storage
        # host -- which is the exact confusion 04-graph-access.md warns about.
        raise _classify(reason, urllib.parse.urlparse(url).hostname) from None


def request(url, token=None, method="GET", data=None, headers=None, follow=True):
    """Return (status, headers, body_bytes). Raises Blocked on a transport failure.

    Redirects are followed manually rather than by urllib, so a denial at hop N names
    hop N's host. An Authorization header is not replayed across hosts: Graph's storage
    redirect is pre-authenticated, and forwarding a bearer token to it leaks the token.
    """
    seen = []
    for _ in range(5):
        status, headers_out, body = _one(url, token, method, data, headers)
        if not (follow and status in (301, 302, 303, 307, 308)):
            return status, headers_out, body
        loc = headers_out.get("Location")
        if not loc:
            return status, headers_out, body
        url = urllib.parse.urljoin(url, loc)
        seen.append(url)
        if status == 303 or (status == 302 and method == "POST"):
            method, data = "GET", None
        token = None  # never forward credentials to a redirect target
    raise Blocked("network", f"too many redirects: {' -> '.join(seen[:5])}")


def _err(body):
    """Pull Graph's error message out of a response body, without dumping the whole thing."""
    try:
        return json.loads(body)["error"]["message"][:200]
    except Exception:
        return body[:200].decode("utf-8", "replace")


# --- steps ----------------------------------------------------------------------

def step1_egress(state):
    """The staging host resets a connection now and then; a transient reset is not a
    policy failure and must not abort the run before the Graph steps get a chance."""
    last = None
    for attempt in range(3):
        try:
            status, _, _ = request(INGEST_HOST)
        except Blocked as b:
            if b.kind == "egress":
                raise  # a policy denial is not transient -- fail immediately
            last = b.detail
            continue
        state["ingest_status"] = status
        retried = f" (after {attempt} retr{'y' if attempt == 1 else 'ies'})" if attempt else ""
        if status == 401:
            return True, f"401 — host up and wanting auth, which is the expected shape{retried}"
        return False, f"expected 401, got {status}{retried}"
    raise Blocked("network", f"3 attempts, last: {last}")


def step2_token(state):
    missing = [v for v in CREDS if not os.environ.get(v)]
    if missing:
        raise Blocked("credentials", f"unset: {', '.join(missing)}")
    tenant = os.environ["GRAPH_TENANT_ID"]
    body = urllib.parse.urlencode({
        "client_id": os.environ["GRAPH_CLIENT_ID"],
        "client_secret": os.environ["GRAPH_CLIENT_SECRET"],
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }).encode()
    status, _, raw = request(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        method="POST", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if status != 200:
        return False, f"token endpoint returned {status}: {_err(raw)}"
    token = json.loads(raw).get("access_token")
    if not token:
        return False, "no access_token in the response"
    state["token"] = token  # never printed
    return True, "token acquired"


def step3_drives(state):
    token = state["token"]
    status, _, raw = request(f"{GRAPH}/sites/{SITE_HOST}:{SITE_PATH}", token=token)
    if status != 200:
        hint = " — Sites.Selected may not be granted on this site" if status == 403 else ""
        return False, f"site lookup {status}: {_err(raw)}{hint}"
    site_id = json.loads(raw)["id"]
    state["site_id"] = site_id

    status, _, raw = request(f"{GRAPH}/sites/{site_id}/drives", token=token)
    if status != 200:
        return False, f"drives {status}: {_err(raw)}"
    drives = json.loads(raw).get("value", [])
    found = any(d.get("id") == DRIVE_ID for d in drives)
    state["drive_match"] = found
    note = "documented drive id present" if found else "documented drive id NOT among them"
    return found, f"{len(drives)} drive(s); {note}"


def step4_item(state, item_id=None):
    token = state["token"]
    if item_id is None:
        # Resolve one real image by path rather than hardcoding an item id.
        path = urllib.parse.quote(PROBE_FOLDER)
        status, _, raw = request(
            f"{GRAPH}/drives/{DRIVE_ID}/root:/{path}:/children?$top=100", token=token)
        if status != 200:
            return False, f"probe folder listing {status}: {_err(raw)}"
        files = [c for c in json.loads(raw).get("value", [])
                 if "file" in c and c["name"].lower().endswith(IMAGE_EXT)]
        if not files:
            return False, f"no image found directly under {PROBE_FOLDER}"
        item_id = files[0]["id"]
        state["item_name"] = files[0]["name"]

    status, _, raw = request(f"{GRAPH}/drives/{DRIVE_ID}/items/{item_id}", token=token)
    if status != 200:
        return False, f"item {status}: {_err(raw)}"
    item = json.loads(raw)
    state["item_id"] = item_id
    state["item_name"] = item.get("name")
    dims = item.get("image") or {}
    state["item_dims"] = (dims.get("width"), dims.get("height"))
    size_mb = (item.get("size") or 0) / 1e6
    return True, (f"{item.get('name')} — {size_mb:.1f} MB, "
                  f"{dims.get('width')}x{dims.get('height')}px")


def step5_content(state):
    """The step most likely to fail: bytes come from a different host than Graph."""
    status, headers, raw = request(
        f"{GRAPH}/drives/{DRIVE_ID}/items/{state['item_id']}/content",
        token=state["token"], follow=False)
    if status in (301, 302, 307, 308):
        loc = headers.get("Location", "")
        host = urllib.parse.urlparse(loc).hostname or "(no Location header)"
        state["storage_host"] = host
        # Reaching the redirect is the point. Now see whether that host is allowlisted.
        try:
            s2, _, body = request(loc)
            reachable = f"and it is reachable ({s2}, {len(body)} bytes)"
            ok = s2 == 200
        except Blocked as b:
            reachable = f"but it is BLOCKED — {b.detail}"
            ok = False
        return ok, f"302 -> {host} {reachable}"
    if status == 200:
        state["storage_host"] = "(served inline, no redirect)"
        return True, f"200 inline, {len(raw)} bytes"
    return False, f"content {status}: {_err(raw)}"


def _thumb_spec(state):
    """A custom size box matching the item's own aspect ratio.

    Only `_Crop` is supported here -- `_Fit` returns "Unsupported options were provided
    in the thumbnail descriptor". `_Crop` on a square box would square off a 4:3 frame
    and throw away a third of it, so the box is derived from the item's own dimensions
    and the crop becomes a no-op. Falls back to a square only when Graph reported no
    dimensions, where there is nothing better to go on.
    """
    w, h = state.get("item_dims") or (None, None)
    if not (w and h):
        return f"c{THUMB_SIZE}x{THUMB_SIZE}_Crop"
    if w >= h:
        return f"c{THUMB_SIZE}x{round(THUMB_SIZE * h / w)}_Crop"
    return f"c{round(THUMB_SIZE * w / h)}x{THUMB_SIZE}_Crop"


def step6_thumbnail(state):
    """Settles whether a rendition is legible enough to replace a full-resolution original."""
    spec = _thumb_spec(state)
    status, _, raw = request(
        f"{GRAPH}/drives/{DRIVE_ID}/items/{state['item_id']}"
        # Bare `select`/`expand`, NOT `$select`/`$expand`: with the `$` prefix Graph
        # applies strict OData property validation and rejects a custom size descriptor
        # ("Could not find a property named 'c1600x1200_Crop'"). Without it, the size is
        # routed to the thumbnail descriptor and honoured.
        f"/thumbnails?select={spec}&expand={spec}", token=state["token"])
    if status != 200:
        return False, f"thumbnails {status}: {_err(raw)}"
    sets = json.loads(raw).get("value", [])
    if not sets:
        return False, "no thumbnail set returned"
    custom = sets[0].get(spec) or {}
    w, h = custom.get("width"), custom.get("height")
    state["thumb"] = (w, h)
    if not w:
        return False, f"{spec} not honoured; available: {sorted(k for k in sets[0] if k != 'id')}"

    long_edge = max(w, h)
    big_enough = long_edge >= THUMB_SIZE
    # The rendition lives on a different host again -- not graph.microsoft.com, and not
    # the storage host /content redirects to. Reaching it is the whole point.
    host = urllib.parse.urlparse(custom.get("url", "")).hostname
    state["thumb_host"] = host
    try:
        s2, _, body = request(custom["url"])
        reach = f"fetched {len(body)} bytes" if s2 == 200 else f"host answered {s2}"
        ok = big_enough and s2 == 200
    except Blocked as b:
        reach = f"BLOCKED — add {host} (or *.svc.ms) to the allowlist"
        ok = False
    size_note = (f"{w}x{h}" if big_enough
                 else f"{w}x{h} BELOW the {THUMB_SIZE}px long edge the vision pass needs")
    return ok, f"{spec} -> {size_note}, host {host}: {reach}"


STEPS = [
    ("1. egress to media library host", step1_egress),
    ("2. Graph token", step2_token),
    ("3. site + drives (Sites.Selected)", step3_drives),
    ("4. item metadata", step4_item),
    ("5. content bytes (redirect host)", step5_content),
    ("6. large thumbnail", step6_thumbnail),
]


def main():
    item_id = None
    if "--item-id" in sys.argv:
        item_id = sys.argv[sys.argv.index("--item-id") + 1]

    state, results = {}, []
    for name, fn in STEPS:
        try:
            ok, detail = fn(state, item_id) if fn is step4_item else fn(state)
            status = "PASS" if ok else "FAIL"
        except Blocked as b:
            ok, status, detail = False, f"BLOCKED[{b.kind}]", b.detail
        except Exception as e:  # a bug here must not read as a policy failure
            ok, status, detail = False, "ERROR", f"{type(e).__name__}: {e}"
        results.append({"step": name, "status": status, "detail": detail})
        print(f"{status:16s} {name:36s} {detail}")
        if not ok:
            remaining = [n for n, _ in STEPS[len(results):]]
            if remaining:
                print(f"\nStopped. Not attempted: {', '.join(remaining)}")
                print("Each later step depends on the one above it, so running them now "
                      "would only produce the same failure with a less specific message.")
            break

    if "--json" in sys.argv:
        print(json.dumps({"results": results,
                          "storage_host": state.get("storage_host"),
                          "thumbnail": state.get("thumb")}, indent=1))
    print("\nStep 7 (end-to-end ingest) is not run by this script — it writes to staging.")
    return 0 if all(r["status"] == "PASS" for r in results) and len(results) == len(STEPS) else 1


if __name__ == "__main__":
    sys.exit(main())
