#!/usr/bin/env python3
"""Profile an account: what is it, what does it do, what would break if it stopped.

Built for the question "this service account has no MFA -- what is it actually
doing?" before deciding whether to migrate it to an app registration or switch
it off. Read-only.

The sign-in log is the useful part: it names the applications and resources the
account authenticates against, which is what tells you what a migration has to
replace. That log retains 7 days without Entra ID P1 and 30 days with it, so it
only helps for accounts used recently -- for dormant ones it is legitimately
empty and the licence/group/role data carries the answer instead.

Usage:
    python3 tools/account_profile.py --upn automation@midlandind.com.au
"""

from __future__ import annotations

import argparse
import collections
import urllib.error
import urllib.parse

from graph_auth import authenticate, graph_get


def _get(token: str, url: str):
    try:
        return graph_get(token, url)
    except urllib.error.HTTPError as exc:
        return {"_error": f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:200]}"}


def profile(token: str, upn: str) -> None:
    print("=" * 78)
    print(f"  {upn}")
    print("=" * 78)

    filt = urllib.parse.quote(f"userPrincipalName eq '{upn}'")
    page = _get(
        token,
        "https://graph.microsoft.com/beta/users"
        f"?$filter={filt}"
        "&$select=id,userPrincipalName,displayName,accountEnabled,createdDateTime,"
        "jobTitle,department,description,mail,otherMails,userType,onPremisesSyncEnabled,"
        "assignedLicenses,signInActivity",
    )
    results = (page or {}).get("value", [])
    if not results:
        print(f"  Could not read: {(page or {}).get('_error', 'not found')}\n")
        return
    u = results[0]
    uid = u["id"]

    act = u.get("signInActivity") or {}
    print(f"  Display name:   {u.get('displayName')}")
    print(f"  Object id:      {uid}")
    print(f"  Enabled:        {u.get('accountEnabled')}   userType: {u.get('userType')}")
    print(f"  Created:        {u.get('createdDateTime')}")
    print(f"  Mail:           {u.get('mail')}")
    if u.get("jobTitle") or u.get("department"):
        print(f"  Job/dept:       {u.get('jobTitle')} / {u.get('department')}")
    if u.get("description"):
        print(f"  Description:    {u.get('description')}")
    if u.get("onPremisesSyncEnabled"):
        print("  Source:         synced from on-premises AD")
    print(f"  Last successful:{act.get('lastSuccessfulSignInDateTime') or ' NEVER'}")
    print(f"  Licences:       {len(u.get('assignedLicenses') or [])} assigned")

    lic = _get(token, f"https://graph.microsoft.com/v1.0/users/{uid}/licenseDetails")
    for sku in (lic or {}).get("value", []):
        print(f"                  - {sku.get('skuPartNumber')}")

    roles, groups = [], []
    for m in (_get(token, f"https://graph.microsoft.com/v1.0/users/{uid}/memberOf") or {}).get("value", []):
        (roles if "directoryRole" in m.get("@odata.type", "") else groups).append(
            m.get("displayName")
        )
    if roles:
        print(f"\n  !! DIRECTORY ROLES: {', '.join(roles)}")
    if groups:
        print(f"\n  Groups ({len(groups)}): {', '.join(g for g in groups if g)[:400]}")

    owned = (_get(token, f"https://graph.microsoft.com/v1.0/users/{uid}/ownedObjects") or {}).get("value", [])
    if owned:
        print(f"\n  Owns {len(owned)} directory object(s):")
        for o in owned[:15]:
            kind = o.get("@odata.type", "").rsplit(".", 1)[-1]
            print(f"    - [{kind}] {o.get('displayName')}")

    # What is it actually used for? Applications and callers in the retained log.
    sfilt = urllib.parse.quote(f"userPrincipalName eq '{upn}'")
    logs = _get(
        token,
        f"https://graph.microsoft.com/v1.0/auditLogs/signIns?$filter={sfilt}&$top=200",
    )
    if isinstance(logs, dict) and "_error" in logs:
        print(f"\n  Sign-in log unavailable -- {logs['_error']}")
        print()
        return

    entries = (logs or {}).get("value", [])
    if not entries:
        print("\n  No sign-ins in the retained log window (7-30 days).")
        print()
        return

    apps = collections.Counter(e.get("appDisplayName") or "(unknown)" for e in entries)
    ips = collections.Counter(e.get("ipAddress") or "(none)" for e in entries)
    clients = collections.Counter(e.get("clientAppUsed") or "(unknown)" for e in entries)
    fails = [e for e in entries if (e.get("status") or {}).get("errorCode")]

    print(f"\n  Sign-ins in retained window: {len(entries)}  ({len(fails)} failed)")
    print("\n  Applications:")
    for name, n in apps.most_common(12):
        print(f"    {n:>5}  {name}")
    print("\n  Client / protocol:")
    for name, n in clients.most_common(8):
        print(f"    {n:>5}  {name}")
    print("\n  Source IPs:")
    for name, n in ips.most_common(8):
        print(f"    {n:>5}  {name}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default="midlandind.com.au")
    ap.add_argument("--upn", action="append", required=True, help="repeatable")
    args = ap.parse_args()

    token = authenticate(args.tenant)
    for upn in args.upn:
        profile(token, upn)


if __name__ == "__main__":
    main()
