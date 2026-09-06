# MFA posture — audit findings and actions

Midland Pty Ltd — audit run 6 Sep 2026 via `tools/mfa_audit.py`

## Headline: the Feb 2027 deadline is not your problem

**Zero accounts are exposed to the 1 February 2027 SMS/voice retirement.**

Every account in the tenant that has a phone number registered also has a
stronger method alongside it. The retirement blocks only accounts whose *only*
second factor is SMS or voice. Midland has none.

This overturns the concern that prompted the audit. No purchase, no scramble,
no deadline project. The tenant does have real gaps — they are just different
gaps, listed below.

## What the audit found

117 accounts total; 79 enabled, 38 disabled.

| Finding | Count |
|---|---|
| Blocked after 1 Feb 2027 | **0** |
| Still on legacy per-user MFA (all `enforced`) | 38 |
| Sign-in-capable accounts with no MFA at all | **16** |
| Guest accounts with no MFA (authenticate at their home tenant) | 5 |
| Room/resource mailboxes with no MFA (cannot sign in interactively) | 6 |

The raw 27 "no MFA" accounts break down into 16 that actually matter, 5 guests
that are LEAP's responsibility to secure, and 6 room mailboxes that cannot sign
in at all. Only the 16 are real.

### Windows Hello for Business is already doing the job

Nearly every protected account shows `windowsHelloForBusinessAuthenticationMethod`,
usually paired with Microsoft Authenticator. WHfB is TPM-backed and
phishing-resistant — the same security property as a passkey, already deployed
across the fleet at no cost.

This is why hardware security keys are not needed here. An earlier draft of this
document recommended buying FIDO2 keys for the shared terminals. That was wrong:
those terminals already have phishing-resistant authentication. Where a shared
account needs a strong method in future, WHfB on the terminal is the answer, not
a purchase.

### The shared production accounts are fine

The accounts the third-party monitor has been alerting on are already covered:

| Account | Per-user MFA | Registered methods |
|---|---|---|
| `kynproduction` | disabled | Authenticator, WHfB |
| `parkesproduction` | disabled | Authenticator, phone, WHfB |
| `powdercoat` | disabled | Authenticator, WHfB |
| `warroom-pks` | disabled | Authenticator, WHfB |
| `KynBoardRoom` | disabled | phone, WHfB |

All have a strong second factor. The alert stream on these was noise, as
suspected — the monitor was reporting per-sign-in "no MFA evidence" rather than
account posture.

## The real gaps

### 1. Sixteen sign-in-capable accounts with no MFA

Sign-in activity (`tools/signin_activity.py`, 6 Sep 2026) makes these far less
alarming than the raw count suggests. Most have never been used.

| Account | Last successful sign-in | Idle |
|---|---|---|
| `windchill` | 2024-02-26 | 923 days |
| `midlandreporting` | 2024-03-05 | 915 days |
| `marketing` | 2025-11-20 | 290 days |
| `copier` | 2025-11-26 | 284 days |
| `timb3D` | 2025-12-26 | 254 days |
| `dummytestuser` | 2026-05-19 | 110 days |
| `automation` | 2026-09-04 | 2 days — **live** |
| `MidlandSharepoint` | 2026-09-04 | 2 days — **live** |
| `3cx`, `automationtriggers`, `careers`, `design-shared`, `midlandproductsupport`, `parkesfold`, `sales`, `spares` | **never** | — |
| 6 room/resource mailboxes | **never** | — |

**Fourteen accounts have never signed in at all** — no interactive and no
non-interactive sign-in since creation, some going back to 2017. Blocking
sign-in on these carries essentially no operational risk, because nothing has
ever used them to authenticate. That removes 14 of the 16 from the risk
surface without touching a workflow.

Actions by group:

- **Never used (14)** → block sign-in. Convert the mail-bearing ones (`sales`,
  `spares`, `careers`, `design-shared`, `midlandproductsupport`, `parkesfold`)
  to **shared mailboxes**: no sign-in, no licence, no password, no MFA. The
  room mailboxes are already resource accounts and need nothing.
- **Dormant over a year (2)** — `windchill`, `midlandreporting` → disable.
  `windchill` is the priority: enabled and unauthenticated throughout the July
  2026 Windchill incident, and a dormant account with no second factor is a
  standard re-entry path afterwards.
- **Live service accounts (2)** — `automation`, `MidlandSharepoint` → migrate
  to an **Entra app registration with certificate credentials**, or a managed
  identity for anything in Azure. These are the only two that actually need
  migrating rather than switching off.
- **Idle, decide (3)** — `marketing`, `copier`, `timb3D`. `copier` is
  scan-to-email; confirm what it uses before disabling. `timb3D` is a real
  vendor (Tim Brickle, 3D Walkabout) but has not signed in since December 2025
  and, unlike the other active 3D vendor accounts, has no MFA registered.
- **Delete** — `dummytestuser`.

### 2. Thirty-eight accounts on legacy per-user MFA

All are in `enforced` state. Most already carry Authenticator and WHfB, so the
*protection* is fine — it is the *management surface* that is legacy and
unsupported since 30 September 2025.

This blocks nothing today, but it must be cleared before Security Defaults or
Conditional Access can be enabled, because per-user MFA state cannot coexist
with either.

### 3. No tenant-level enforcement

Security Defaults off, no Conditional Access. Nothing enforces MFA on a new
account — which is exactly how 16 accounts ended up with none.

## Licensing constraints

One Business Premium licence. This bounds the options:

| Capability | Needs | Available |
|---|---|---|
| Security Defaults | nothing | yes |
| Windows Hello for Business | nothing | yes, already deployed |
| Conditional Access | Entra ID P1 per covered user | no |
| Graph `signIns` API | Entra ID P1/P2 | no |
| Unified audit log (`UserLoggedIn`) | any M365 subscription | yes |

Worth noting in any MSP conversation: a monitor built on the Graph `signIns`
API needs P1 too. The licensing argument made about Conditional Access applies
equally to that product.

## Actions, in order

1. **Disable `windchill@`** — 923 days idle, no MFA, enabled throughout the
   July 2026 incident. Highest value, lowest risk change on this list.
2. **Block sign-in on the 14 never-used accounts.** No account has ever
   authenticated, so nothing breaks. Convert the mail-bearing ones to shared
   mailboxes, which also reclaims licences.
3. **Delete `dummytestuser@`** and disable `midlandreporting@` (915 days idle).
4. **Migrate `automation@` and `MidlandSharepoint@`** to app registrations —
   the only two live service accounts. OpsMachine already uses this pattern.
5. **Decide on `marketing`, `copier`, `timb3D`** — idle 8-10 months. Confirm
   what `copier` uses for scan-to-email before disabling it.
6. **Review the 38 disabled accounts** — delete or document why they persist.
7. **Clear per-user MFA**: set `perUserMfaState` to `disabled` across the 38
   enforced accounts, once everything above is settled.
8. **Inventory legacy-authentication usage** before the next step. Security
   Defaults blocks it, and that is what breaks integrations.
9. **Enable Security Defaults** — last, not first.

Steps 7–9 must stay in that order. Security Defaults cannot coexist with
per-user MFA state and forces MFA registration tenant-wide within 14 days.

## Replacing the MFA monitor

The current product alerts per sign-in event on "no MFA evidence". Token
refreshes, SSO and remembered devices all legitimately show no MFA on the event
itself, so most alerts are false positives — which is why they get ignored.
This audit is the proof: the accounts it alerts on loudest are fully covered.

A replacement should invert the model:

- **Watch state, not events.** Snapshot posture nightly — `tools/mfa_audit.py`
  already produces exactly this — and alert only on *changes*: an account loses
  its last strong method, a new account appears with no MFA, per-user MFA
  reappears after migration.
- **Per-event alerts only for real anomalies**, from the unified audit log
  (licence-safe): new country, legacy auth protocol, shop-floor account
  authenticating from outside Australia.
- **Daily digest, not a stream.** One table of deltas; only high severity
  interrupts.
- **Exclusions in version control**, reviewed like any other change — which
  fixes the "my overrides didn't stick" failure directly.

As an OpsMachine module: nightly cron alongside existing jobs, existing app
registration for auth, previous snapshot persisted for delta comparison,
existing `noreply@midlandind.com.au` transport, config committed to the repo.
