#!/usr/bin/env python3
"""Shared Microsoft Graph auth and transport for the audit tools.

Exists to keep interactive sign-ins to a minimum. Two things cause repeat
device-code prompts, and this module removes both:

  * Each tool asking for its own narrow scope set, so switching tools forces a
    new sign-in. SCOPES below is the union needed by every tool here.
  * Discarding the refresh token at exit. The token cache persists it, so
    later runs renew silently.

The cache holds a refresh token for read-only Graph scopes. It is written
0600 and gitignored. Delete it to force a fresh sign-in; revoke it tenant-side
with "Revoke sessions" on the account in Entra, or Disconnect-MgGraph.

Note on geography: device code flow records the sign-in against the host that
redeems the token, not the person approving it. Run these tools locally where
possible -- running them from a remote container puts that host's country in
the tenant sign-in log and trips geo-anomaly alerting.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# "Microsoft Graph Command Line Tools" -- Microsoft's own public client, the one
# Connect-MgGraph uses. Public client, no secret, device code enabled.
CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"

# Union of what every tool in this directory needs, so one sign-in covers all.
#
# The write scopes are here only because apply_changes.py disables accounts and
# sets per-user MFA state. Every other tool is read-only. Splitting the sets
# would mean a second device-code prompt each time you moved between reading and
# acting, which in practice led to sign-in fatigue and worse decisions, so they
# share one consent. If you want the read-only tools to hold no write capability,
# drop the two ReadWrite scopes and let apply_changes.py request them itself.
SCOPES = " ".join(
    [
        "User.Read.All",
        "UserAuthenticationMethod.Read.All",
        "Policy.Read.All",
        "AuditLog.Read.All",
        "Directory.Read.All",
        "User.ReadWrite.All",  # accountEnabled, revokeSignInSessions
        "offline_access",
        # Deliberately NOT included: Policy.ReadWrite.AuthenticationMethod,
        # which is what writing perUserMfaState actually requires (the
        # UserAuthenticationMethod ReadWrite scope returns 403 on it, and the
        # Policy domain has no .Read variant).
        #
        # Adding any scope invalidates the cached consent, so the next run
        # fails its silent refresh, discards the cache, and demands a fresh
        # device code. Widen this list only when a tool here genuinely needs
        # it -- each addition costs an interactive sign-in. Per-user MFA state
        # is changed in the portal instead.
    ]
)

CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".graph-token.json")


def _post_form(url: str, fields: dict) -> tuple[int, dict]:
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        # The token endpoint signals "still waiting" via HTTP 400, so error
        # bodies are expected control flow here, not failures.
        try:
            return exc.code, json.load(exc)
        except Exception:
            return exc.code, {}


def _save_refresh_token(tenant: str, refresh_token: str) -> None:
    if not refresh_token:
        return
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump({"tenant": tenant, "refresh_token": refresh_token}, fh)
        os.chmod(CACHE_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError as exc:
        print(f"  (could not cache token: {exc})", file=sys.stderr)


def _try_cached(tenant: str, authority: str) -> str | None:
    """Renew from a cached refresh token. Returns None if unavailable."""
    try:
        with open(CACHE_PATH, encoding="utf-8") as fh:
            cached = json.load(fh)
    except (OSError, ValueError):
        return None

    if cached.get("tenant") != tenant or not cached.get("refresh_token"):
        return None

    status, tok = _post_form(
        f"{authority}/token",
        {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": cached["refresh_token"],
            "scope": SCOPES,
        },
    )
    if status != 200:
        # Expired or revoked. Drop it and fall through to device code.
        try:
            os.remove(CACHE_PATH)
        except OSError:
            pass
        return None

    _save_refresh_token(tenant, tok.get("refresh_token", cached["refresh_token"]))
    print("Reusing cached sign-in -- no device code needed.\n", flush=True)
    return tok["access_token"]


def authenticate(tenant: str, scopes: str = SCOPES) -> str:
    """Return a Graph access token, prompting for device code only if needed."""
    authority = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"

    token = _try_cached(tenant, authority)
    if token:
        return token

    status, flow = _post_form(
        f"{authority}/devicecode", {"client_id": CLIENT_ID, "scope": scopes}
    )
    if status != 200:
        sys.exit(f"Could not start device code flow: {flow}")

    print("\n" + "=" * 68)
    print("  SIGN IN TO CONTINUE  (one-off -- the token is cached after this)")
    print("=" * 68)
    print(f"\n  1. Open:  {flow['verification_uri']}")
    print(f"  2. Code:  {flow['user_code']}")
    print("\n  Sign in as an account with Global Reader or Global Admin.")
    print("=" * 68 + "\n", flush=True)

    interval = int(flow.get("interval", 5))
    deadline = time.time() + int(flow.get("expires_in", 900))

    while time.time() < deadline:
        time.sleep(interval)
        status, tok = _post_form(
            f"{authority}/token",
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": CLIENT_ID,
                "device_code": flow["device_code"],
            },
        )
        if status == 200:
            _save_refresh_token(tenant, tok.get("refresh_token", ""))
            print("Authenticated.\n", flush=True)
            return tok["access_token"]

        err = tok.get("error", "")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5
            continue
        sys.exit(f"Sign-in failed: {tok.get('error_description', err)}")

    sys.exit("Sign-in timed out.")


def graph_get(token: str, url: str, attempts: int = 5):
    """GET a Graph URL, retrying on throttling and transient server errors."""
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                return None  # not readable for this principal; not an error
            retryable = exc.code == 429 or exc.code >= 500
            if not retryable or attempt == attempts:
                raise
            backoff = 2 ** attempt
            if exc.code == 429:
                backoff = int(exc.headers.get("Retry-After", backoff))
            time.sleep(backoff)
    return None
