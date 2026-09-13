#!/usr/bin/env python3
"""Preflight check: what breaks when Security Defaults is switched on.

Security Defaults has two properties that make this worth checking first:

  * **No exclusions.** Only Entra Connect / Cloud Sync accounts are exempt.
    A service account that cannot complete MFA cannot be excused -- it breaks.
  * **Authenticator-app only.** The registration flow does not offer SMS or
    voice. An account whose only method is a phone number must register the
    Authenticator app within 14 days or be blocked from signing in.

It also cannot coexist with legacy per-user MFA, so any account left in
'enabled' or 'enforced' has to be set to 'disabled' first.

This reports each of those conditions against the live tenant and gives a
go / no-go. Read-only.

Usage:
    python3 tools/security_defaults_preflight.py
"""

from __future__ import annotations

import argparse
import sys

from graph_auth import authenticate, graph_get
from mfa_audit import IGNORED_METHODS, assess, get_all_users

# Methods that satisfy the Security Defaults registration requirement.
# phoneAuthenticationMethod deliberately absent: SMS and voice are not offered
# in the registration flow, so a phone-only account cannot complete it.
# windowsHelloForBusinessAuthenticationMethod also absent: it is per-device and
# Windows-only, so it does not help an Android tablet or a service account.
SATISFIES_REGISTRATION = {
    "microsoftAuthenticatorAuthenticationMethod",
    "passwordlessMicrosoftAuthenticatorAuthenticationMethod",
    "softwareOathAuthenticationMethod",
    "fido2AuthenticationMethod",
}


def classify(row: dict) -> list[str]:
    """Return the reasons this account is a problem, if any."""
    problems = []
    methods = set(row["methods"].split(";")) - IGNORED_METHODS - {""}

    if row["per_user_mfa_state"] in ("enabled", "enforced"):
        problems.append("per-user MFA must be disabled first")

    if not (methods & SATISFIES_REGISTRATION):
        if "phoneAuthenticationMethod" in methods:
            # Has a factor, but not one the registration flow will accept.
            problems.append("phone only -- cannot complete Authenticator-only registration")
        else:
            problems.append("no usable method -- 14 days then blocked")

    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default="midlandind.com.au")
    args = ap.parse_args()

    token = authenticate(args.tenant)

    print("Enumerating users...", flush=True)
    users = get_all_users(token)
    print(f"Found {len(users)} accounts. Checking readiness...\n", flush=True)

    rows = []
    for i, user in enumerate(users, 1):
        try:
            rows.append(assess(token, user))
        except Exception as exc:
            print(f"  ! {user.get('userPrincipalName')}: {exc}", file=sys.stderr)
        if i % 20 == 0 or i == len(users):
            print(f"  {i}/{len(users)}", flush=True)

    live = [r for r in rows if r["enabled"]]

    legacy_mfa, no_method, phone_only, guests = [], [], [], []
    for row in live:
        problems = classify(row)
        if not problems:
            continue
        if "#EXT#" in row["upn"]:
            guests.append(row)
            continue
        for p in problems:
            if p.startswith("per-user"):
                legacy_mfa.append(row)
            elif p.startswith("phone only"):
                phone_only.append(row)
            else:
                no_method.append(row)

    print("\n" + "=" * 74)
    print("  SECURITY DEFAULTS PREFLIGHT")
    print("=" * 74)
    print(f"  Enabled accounts checked:                 {len(live)}")
    print(f"  BLOCKER  still on per-user MFA:           {len(legacy_mfa)}")
    print(f"  BLOCKER  no method usable for registration:{len(no_method):>3}")
    print(f"  WARN     phone only (SMS not accepted):   {len(phone_only)}")
    print(f"  INFO     guests affected:                 {len(guests)}")
    print("=" * 74)

    def show(title: str, items: list[dict], note: str) -> None:
        if not items:
            return
        print(f"\n{title}")
        print(f"  {note}")
        for r in sorted(items, key=lambda x: x["upn"].lower()):
            print(f"    {r['upn']:<46} [{r['methods'] or 'no methods'}]")

    show(
        "BLOCKER — per-user MFA still set",
        legacy_mfa,
        "Security Defaults cannot coexist with these. Set perUserMfaState to"
        " 'disabled' first.",
    )
    show(
        "BLOCKER — no method that satisfies registration",
        no_method,
        "These get 14 days then cannot sign in. No exclusion is possible."
        " Service accounts here must move to an app registration before"
        " Security Defaults goes on.",
    )
    show(
        "WARN — phone only",
        phone_only,
        "SMS and voice are not offered during Security Defaults registration."
        " Each must register the Authenticator app within 14 days.",
    )
    show(
        "INFO — guest accounts",
        guests,
        "Guests are in scope. They authenticate at their home tenant, but"
        " confirm before a vendor is locked out mid-project.",
    )

    print("\n" + "-" * 74)
    if legacy_mfa or no_method:
        print("  NO-GO. Resolve the blockers above first.")
        print("  Re-run this check until it returns GO.")
    elif phone_only:
        print("  GO, with care. No hard blockers, but the phone-only accounts")
        print("  above will each need Authenticator registered within 14 days.")
    else:
        print("  GO. No blockers found.")
    print("-" * 74)
    print("\n  Not checked here — verify separately:")
    print("   * Legacy auth (SMTP AUTH scan-to-email, POP/IMAP, old Office")
    print("     clients). Security Defaults blocks it outright.")
    print("   * At least two admin accounts with working Authenticator. There")
    print("     is no break-glass exclusion, including for turning this back off.")


if __name__ == "__main__":
    main()
