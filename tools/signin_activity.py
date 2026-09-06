#!/usr/bin/env python3
"""Report last sign-in activity for named accounts, or for every account with no MFA.

Answers "is this account actually used?" -- the question that decides whether a
no-MFA account is an active risk, a dormant account to disable, or an
integration to migrate.

Two independent sources, because they fail differently:

  signInActivity   a rolling last-sign-in stamp on the user object. Survives
                   log expiry, so it is the reliable "ever used?" signal.
  auditLogs/signIns the actual log. Richer (app, IP, protocol) but retained
                   only 7 days without Entra ID P1, 30 days with it -- so an
                   empty result here does NOT mean the account is unused.

Both need AuditLog.Read.All and tenant-level Entra ID premium. If premium is
absent Graph returns an explicit error, which this script surfaces rather than
reporting a misleading zero.

Usage:
    python3 tools/signin_activity.py --upn windchill@midlandind.com.au
    python3 tools/signin_activity.py --from-audit mfa-audit/mfa-posture.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import urllib.error
import urllib.parse
import urllib.request

from mfa_audit import authenticate, graph_get

SCOPES = "AuditLog.Read.All User.Read.All Directory.Read.All offline_access"


def get_activity(token: str, upn: str) -> dict:
    """Fetch the rolling sign-in stamps from the user object.

    Must use a $filter collection query, not a key lookup: Graph rejects
    /users/{upn} with signInActivity in $select ("Get By Key only supports
    UserId and the key has to be a valid Guid").
    """
    filt = urllib.parse.quote(f"userPrincipalName eq '{upn}'")
    url = (
        "https://graph.microsoft.com/beta/users"
        f"?$filter={filt}"
        "&$select=id,userPrincipalName,displayName,accountEnabled,createdDateTime,signInActivity"
    )
    try:
        page = graph_get(token, url)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        return {"upn": upn, "error": f"HTTP {exc.code}: {detail}"}

    results = (page or {}).get("value", [])
    if not results:
        return {"upn": upn, "error": "not found or not readable"}
    doc = results[0]

    activity = doc.get("signInActivity") or {}
    return {
        "upn": doc.get("userPrincipalName", upn),
        "display_name": doc.get("displayName", ""),
        "enabled": doc.get("accountEnabled"),
        "created": doc.get("createdDateTime", ""),
        "last_interactive": activity.get("lastSignInDateTime", ""),
        "last_non_interactive": activity.get("lastNonInteractiveSignInDateTime", ""),
        "last_successful": activity.get("lastSuccessfulSignInDateTime", ""),
    }


def get_recent_signins(token: str, upn: str, top: int = 15) -> list[dict] | str:
    """Fetch recent log entries. Returns an error string if the log is unavailable."""
    filt = urllib.parse.quote(f"userPrincipalName eq '{upn}'")
    url = f"https://graph.microsoft.com/v1.0/auditLogs/signIns?$filter={filt}&$top={top}"
    try:
        doc = graph_get(token, url)
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:300]}"
    if doc is None:
        return "not readable (403/404)"

    return [
        {
            "when": s.get("createdDateTime", ""),
            "app": s.get("appDisplayName", ""),
            "ip": s.get("ipAddress", ""),
            "client": s.get("clientAppUsed", ""),
            "status": (s.get("status") or {}).get("errorCode"),
        }
        for s in doc.get("value", [])
    ]


def render(token: str, upn: str) -> None:
    act = get_activity(token, upn)

    print("=" * 74)
    print(f"  {upn}")
    print("=" * 74)

    if "error" in act:
        print(f"  Could not read user: {act['error']}")
        return

    never = not (act["last_interactive"] or act["last_non_interactive"])
    print(f"  Display name:         {act['display_name']}")
    print(f"  Enabled:              {act['enabled']}")
    print(f"  Created:              {act['created']}")
    print(f"  Last interactive:     {act['last_interactive'] or 'NEVER'}")
    print(f"  Last non-interactive: {act['last_non_interactive'] or 'NEVER'}")
    print(f"  Last successful:      {act['last_successful'] or 'NEVER'}")
    if never:
        print("\n  >> No sign-in of any kind has ever been recorded.")

    recent = get_recent_signins(token, upn)
    if isinstance(recent, str):
        print(f"\n  Sign-in log unavailable -- {recent}")
    elif not recent:
        print("\n  No entries in the retained sign-in log (7-30 day window only).")
    else:
        print(f"\n  Recent sign-ins ({len(recent)}):")
        for s in recent:
            ok = "OK  " if s["status"] == 0 else f"E{s['status']}"
            print(f"    {s['when']:<26} {ok:<7} {s['app'][:24]:<24} {s['ip']:<16} {s['client']}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default="midlandind.com.au")
    ap.add_argument("--upn", action="append", default=[], help="repeatable")
    ap.add_argument(
        "--from-audit",
        metavar="CSV",
        help="also check every no-MFA, sign-in-capable account in an mfa_audit CSV",
    )
    args = ap.parse_args()

    targets = list(args.upn)

    if args.from_audit:
        with open(args.from_audit, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if (
                    row["no_mfa_at_all"] == "True"
                    and row["enabled"] == "True"
                    and "#EXT#" not in row["upn"]  # guests authenticate elsewhere
                ):
                    if row["upn"] not in targets:
                        targets.append(row["upn"])

    if not targets:
        sys.exit("Nothing to check. Pass --upn and/or --from-audit.")

    print(f"Checking {len(targets)} account(s). Scopes: {SCOPES}")
    token = authenticate(args.tenant, SCOPES)

    for upn in targets:
        render(token, upn)


if __name__ == "__main__":
    main()
