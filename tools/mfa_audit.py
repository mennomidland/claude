#!/usr/bin/env python3
"""Read-only MFA posture audit for the Midland tenant.

Answers three questions ahead of the 1 Feb 2027 Microsoft-provided SMS/voice
retirement:

  1. Who is still on legacy per-user MFA?
  2. Who gets BLOCKED after 1 Feb 2027 (phone is their only second factor)?
  3. Who has no MFA method at all?

Authenticates with OAuth device code flow (see graph_auth), so it runs anywhere
with outbound HTTPS -- no PowerShell, no Azure CLI. Deliberately avoids
the Graph signIns API, which requires Entra ID P1/P2 the tenant does not have.
Every call is a GET; nothing is written or changed.

Usage:
    python3 tools/mfa_audit.py [--tenant DOMAIN] [--out DIR]
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from graph_auth import authenticate, graph_get

# Methods that survive Feb 2027 and count as a real second factor.
# phoneAuthenticationMethod (SMS/voice) is deliberately excluded -- that is the
# whole point of the audit.
STRONG_METHODS = {
    "fido2AuthenticationMethod",  # security keys AND passkeys
    "passwordlessMicrosoftAuthenticatorAuthenticationMethod",
    "microsoftAuthenticatorAuthenticationMethod",
    "softwareOathAuthenticationMethod",
    "windowsHelloForBusinessAuthenticationMethod",
}

# Not a second factor; noise in the methods list.
IGNORED_METHODS = {"passwordAuthenticationMethod"}


def get_all_users(token: str) -> list[dict]:
    users, url = [], (
        "https://graph.microsoft.com/v1.0/users"
        "?$select=id,userPrincipalName,displayName,accountEnabled&$top=999"
    )
    while url:
        page = graph_get(token, url)
        if not page:
            break
        users.extend(page.get("value", []))
        url = page.get("@odata.nextLink")
    return users


def assess(token: str, user: dict) -> dict:
    uid = user["id"]

    methods_doc = graph_get(
        token, f"https://graph.microsoft.com/v1.0/users/{uid}/authentication/methods"
    )
    raw = (methods_doc or {}).get("value", [])
    # '#microsoft.graph.fido2AuthenticationMethod' -> 'fido2AuthenticationMethod'
    types = {m.get("@odata.type", "").rsplit(".", 1)[-1] for m in raw}

    req_doc = graph_get(
        token,
        f"https://graph.microsoft.com/beta/users/{uid}/authentication/requirements",
    )
    per_user = (req_doc or {}).get("perUserMfaState")

    has_phone = "phoneAuthenticationMethod" in types
    has_strong = bool(types & STRONG_METHODS)

    return {
        "upn": user.get("userPrincipalName", ""),
        "display_name": user.get("displayName", ""),
        "enabled": bool(user.get("accountEnabled")),
        "per_user_mfa_state": per_user or "",
        "has_phone": has_phone,
        "has_strong": has_strong,
        # The Feb 2027 blocking condition: phone and nothing else.
        "blocked_feb_2027": has_phone and not has_strong,
        "no_mfa_at_all": not has_phone and not has_strong,
        "methods": ";".join(sorted(types - IGNORED_METHODS)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default="midlandind.com.au")
    ap.add_argument("--out", default="mfa-audit")
    args = ap.parse_args()

    token = authenticate(args.tenant)

    print("Enumerating users...", flush=True)
    users = get_all_users(token)
    print(f"Found {len(users)} accounts. Reading authentication state...\n", flush=True)

    rows = []
    for i, user in enumerate(users, 1):
        try:
            rows.append(assess(token, user))
        except Exception as exc:  # one bad account must not sink the run
            print(f"  ! {user.get('userPrincipalName')}: {exc}", file=sys.stderr)
        if i % 10 == 0 or i == len(users):
            print(f"  {i}/{len(users)}", flush=True)

    if not rows:
        sys.exit("No accounts could be read. Check the sign-in account's permissions.")

    rows.sort(key=lambda r: r["upn"].lower())

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "mfa-posture.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    live = [r for r in rows if r["enabled"]]
    blocked = [r for r in live if r["blocked_feb_2027"]]
    no_mfa = [r for r in live if r["no_mfa_at_all"]]
    legacy = [r for r in live if r["per_user_mfa_state"] in ("enabled", "enforced")]

    print("\n" + "=" * 68)
    print("  MFA POSTURE")
    print("=" * 68)
    print(f"  Enabled accounts:              {len(live)}")
    print(f"  Still on legacy per-user MFA:  {len(legacy)}")
    print(f"  BLOCKED after 1 Feb 2027:      {len(blocked)}")
    print(f"  No MFA method at all:          {len(no_mfa)}")
    print("=" * 68)

    if blocked:
        print("\nPhone is the ONLY second factor (blocked 1 Feb 2027):")
        for r in blocked:
            print(f"  {r['upn']:<45} per-user={r['per_user_mfa_state'] or 'n/a'}")

    if no_mfa:
        print("\nNo MFA method registered:")
        for r in no_mfa:
            print(f"  {r['upn']:<45} per-user={r['per_user_mfa_state'] or 'n/a'}")

    print(f"\nFull results: {csv_path}")


if __name__ == "__main__":
    main()
