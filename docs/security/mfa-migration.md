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
- **Live service accounts (2)** — `automation`, `MidlandSharepoint`. The only
  two needing migration rather than switching off. See below; neither is a
  simple swap to an app registration.
- **Idle, decide (3)** — `marketing`, `copier`, `timb3D`. `copier` is
  scan-to-email; confirm what it uses before disabling. `timb3D` is a real
  vendor (Tim Brickle, 3D Walkabout) but has not signed in since December 2025
  and, unlike the other active 3D vendor accounts, has no MFA registered.
- **Delete** — `dummytestuser`.

### 1a. Shared production accounts — the turnover problem

`kynproduction`, `parkesproduction`, `powdercoat`, `warroom-pks`, `KynBoardRoom`
are used by many people across many devices, with high staff turnover. All
already carry Authenticator and/or WHfB, so they are not an MFA gap.

**The actual risk is not MFA, and MFA cannot fix it.** With a shared account
under high turnover:

- every leaver keeps a working credential until the password is rotated, and
  rotating it means retraining everyone still there, so in practice it does not
  happen
- the Authenticator registration usually sits on one person's phone. When that
  person leaves, either MFA breaks or the leaver still holds the second factor
- nothing is attributable. After an incident there is no way to say who did
  what from a shared account

Hardening the shared account does not address any of those three. Only
removing the sharing does.

#### The option that is usually missed: frontline licensing

Named identities for floor staff are normally dismissed on cost, because the
comparison is against Business Premium. That is the wrong comparison.
**Microsoft 365 F1 and F3** are built for exactly this shape — "kiosk workers"
who use Microsoft 365 only through shared devices — and cost a fraction of
Business Premium.

Both **F1 and F3 include Entra ID P1**, which means adopting them would also
resolve the Conditional Access constraint recorded above. That is the same
licensing blocker CMS raised, solved from the other direction and at frontline
rather than Business Premium rates.

The pattern is **Shared Device Mode**: the *device* is shared, the *identity*
is not. Each person signs in as themselves on a shared terminal, signs out, and
the next person signs in. Turnover becomes a normal joiner/leaver process, and
sign-ins become attributable.

Worth pricing properly before committing. Published list pricing puts F1 in the
low single digits USD per user per month, but that is a secondary source and not
a quote — get AUD numbers from the reseller, for the actual headcount, and weigh
against the licences reclaimed from the shared and never-used accounts.

#### If frontline licensing is rejected

Shared accounts can be made meaningfully safer, but attribution is lost
permanently and the leaver problem is reduced rather than solved:

- **Register the second factor to a site-owned device**, never a personal
  phone. A cheap tablet that stays on the floor, or TOTP seeded into the shared
  password vault. Removes the "MFA left with the employee" failure.
- **Rely on WHfB for daily sign-in**, not the password. WHfB credentials are
  per-device and TPM-bound, so a leaver who knows the password cannot use it
  from anywhere else. Revocation becomes a device operation.
- **Vault the password** and rotate it on departure as a defined step in the
  offboarding process, not on best effort.
- **Restrict sign-in to the sites** once Conditional Access is available —
  which again points back to F1/F3.

### 2. Thirty-eight accounts on legacy per-user MFA

All are in `enforced` state. Most already carry Authenticator and WHfB, so the
*protection* is fine — it is the *management surface* that is legacy and
unsupported since 30 September 2025.

This blocks nothing today, but it must be cleared before Security Defaults or
Conditional Access can be enabled, because per-user MFA state cannot coexist
with either.

### 2a. `automation@` — two jobs in one account

Sign-in log over the retained 30 days:

```
172 x QM3_Authentication      (browser client, Azure source IPs)
  2 x Microsoft Power BI
174 total, 65 failed (37%)
Licences: O365_BUSINESS_PREMIUM, POWER_BI_STANDARD, FLOW_FREE
Groups:   IT Team, ReportingArea, Production Team
Owns:     group "Jobs"
```

Three separate issues, and they need separating before anything is changed:

1. **QM3 authenticates as this user through a browser flow from Azure IPs.**
   Scripted browser sign-in is the pattern app registrations exist to replace.
   Since QM3 already runs in Azure, a **managed identity** is the clean target —
   no credential to store or rotate at all. An app registration with a
   certificate is the fallback.
2. **M365 SSO for automation inside Power BI reports.** This is a genuine user-
   identity dependency and may *not* be replaceable with a service principal —
   it depends on the specific connector and whether SSO passthrough is in use.
   Verify per data source before assuming it can move. This is the part most
   likely to force the account to survive in some form.
3. **A 37% sign-in failure rate.** 65 failures in 174 attempts is either a
   retry loop or something genuinely broken, and it is worth diagnosing on its
   own merits regardless of the migration. Pull the error codes before
   redesigning around behaviour that may itself be a bug.

It also holds a **Business Premium licence on a service account** — quite
possibly the single one the Conditional Access licensing discussion has been
about.

### 2b. `MidlandSharepoint@` — unexplained, do not block blind

0 licences, no groups, no directory roles, no owned objects.
`signInActivity` reports a successful sign-in on 2026-09-04, but there are
**zero entries in the sign-in log for either event type**, and the log demonstrably
retains back to 2026-08-08 — so this is not a retention gap.

No confident explanation. It authenticates in a way that reaches neither the
interactive nor the non-interactive sign-in log, which is characteristic of
legacy SharePoint app-only / ACS auth, but that is a hypothesis and untested.

Before touching it, look in the **unified audit log** — it records SharePoint
file operations even where Entra sign-in logs show nothing — and check Power
Automate flows and OpsMachine jobs for references to the account.

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

## Done, 6 Sep 2026

Applied and verified via `tools/apply_changes.py` — sign-in blocked and
existing sessions revoked. Disabling an account does not invalidate tokens
already issued, hence the revoke.

| Account | Was idle |
|---|---|
| `windchill` | 923 days |
| `midlandreporting` | 915 days |
| `copier` | 284 days |
| `dummytestuser` | 110 days |

`copier` was scan-to-email. Its last sign-in was 284 days ago, so scanning
either already relies on direct send / a connector or had stopped working;
if scan-to-email breaks, re-enabling is the first thing to try.

`timb3D` was set to per-user MFA enforced by hand in the portal.

## Actions, in order

1. **Block sign-in on the 14 never-used accounts.** No account has ever
   authenticated, so nothing breaks. Convert the mail-bearing ones to shared
   mailboxes, which also reclaims licences.
2. **Migrate `automation@`** — see below. The largest single piece of work
   here and the one with real operational risk attached.
3. **Identify what uses `MidlandSharepoint@`** before touching it — see below.
4. **Decide on `marketing`** — idle 290 days.
5. **Review the 38 disabled accounts** — delete or document why they persist.
6. **Clear per-user MFA**: set `perUserMfaState` to `disabled` across the 38
   enforced accounts, once everything above is settled.
7. **Inventory legacy-authentication usage** before the next step. Security
   Defaults blocks it, and that is what breaks integrations.
8. **Enable Security Defaults** — last, not first.

Steps 6–8 must stay in that order. Security Defaults cannot coexist with
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
