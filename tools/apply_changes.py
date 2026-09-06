#!/usr/bin/env python3
"""Apply the agreed account changes. Plans by default; writes only with --apply.

Changes, all authorised by name rather than derived from a rule:

  block   windchill, midlandreporting, copier, dummytestuser
          Set accountEnabled=false and revoke existing sessions. Blocking
          sign-in alone does not invalidate tokens already issued, so a
          dormant account could keep working from a live session without the
          revoke.

  enforce timb3D
          Set per-user MFA to 'enforced' so registration is required at next
          sign-in.

Every change is reversible: re-enable sets accountEnabled=true, and per-user
MFA can be set back to 'disabled'. Nothing here deletes anything.

Usage:
    python3 tools/apply_changes.py            # show the plan, change nothing
    python3 tools/apply_changes.py --apply    # make the changes
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from graph_auth import authenticate, graph_get

BLOCK_SIGNIN = [
    "windchill@midlandind.com.au",
    "midlandreporting@midlandind.com.au",
    "copier@midlandind.com.au",
    "dummytestuser@midlandind.com.au",
]

ENFORCE_MFA = [
    "timb3D@midlandind.com.au",
]


def graph_write(token: str, url: str, body: dict | None, method: str) -> tuple[bool, str]:
    data = json.dumps(body).encode() if body is not None else b"{}"
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:250]}"
    except urllib.error.URLError as exc:
        return False, str(exc)


def resolve(token: str, upn: str) -> dict | None:
    filt = urllib.parse.quote(f"userPrincipalName eq '{upn}'")
    page = graph_get(
        token,
        "https://graph.microsoft.com/beta/users"
        f"?$filter={filt}&$select=id,userPrincipalName,displayName,accountEnabled,signInActivity",
    )
    results = (page or {}).get("value", [])
    return results[0] if results else None


def per_user_state(token: str, uid: str) -> str:
    doc = graph_get(
        token, f"https://graph.microsoft.com/beta/users/{uid}/authentication/requirements"
    )
    return (doc or {}).get("perUserMfaState", "?")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default="midlandind.com.au")
    ap.add_argument("--apply", action="store_true", help="actually make the changes")
    args = ap.parse_args()

    token = authenticate(args.tenant)

    print("=" * 78)
    print("  PLAN" if not args.apply else "  APPLYING CHANGES")
    print("=" * 78)

    targets = []
    for upn in BLOCK_SIGNIN:
        u = resolve(token, upn)
        if not u:
            print(f"  ?  {upn:<40} NOT FOUND -- skipping")
            continue
        act = (u.get("signInActivity") or {}).get("lastSuccessfulSignInDateTime") or "never"
        state = "already blocked" if not u.get("accountEnabled") else "enabled"
        print(f"  BLOCK    {upn:<40} [{state}] last sign-in {act[:10]}")
        targets.append(("block", u))

    for upn in ENFORCE_MFA:
        u = resolve(token, upn)
        if not u:
            print(f"  ?  {upn:<40} NOT FOUND -- skipping")
            continue
        print(f"  ENFORCE  {upn:<40} per-user MFA currently '{per_user_state(token, u['id'])}'")
        targets.append(("enforce", u))

    if not args.apply:
        print("\n  Nothing changed. Re-run with --apply to make these changes.")
        return

    print()
    failures = 0
    for action, u in targets:
        uid, upn = u["id"], u["userPrincipalName"]

        if action == "block":
            ok, msg = graph_write(
                token,
                f"https://graph.microsoft.com/v1.0/users/{uid}",
                {"accountEnabled": False},
                "PATCH",
            )
            print(f"  {'OK ' if ok else 'FAIL'} block {upn}: {msg}")
            failures += 0 if ok else 1

            # Blocking sign-in does not kill tokens already issued.
            ok2, msg2 = graph_write(
                token,
                f"https://graph.microsoft.com/v1.0/users/{uid}/revokeSignInSessions",
                None,
                "POST",
            )
            print(f"  {'OK ' if ok2 else 'FAIL'} revoke sessions {upn}: {msg2}")
            failures += 0 if ok2 else 1

        else:
            ok, msg = graph_write(
                token,
                f"https://graph.microsoft.com/beta/users/{uid}/authentication/requirements",
                {"perUserMfaState": "enforced"},
                "PATCH",
            )
            print(f"  {'OK ' if ok else 'FAIL'} enforce MFA {upn}: {msg}")
            failures += 0 if ok else 1

    print("\n  Verifying...")
    for action, u in targets:
        fresh = resolve(token, u["userPrincipalName"])
        if action == "block":
            print(f"    {u['userPrincipalName']:<40} enabled={fresh.get('accountEnabled')}")
        else:
            print(
                f"    {u['userPrincipalName']:<40} "
                f"perUserMfaState={per_user_state(token, u['id'])}"
            )

    if failures:
        sys.exit(f"\n{failures} operation(s) failed -- see above.")
    print("\n  All changes applied.")


if __name__ == "__main__":
    main()
