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

#### Fixed constraints

These are requirements, not preferences, and they eliminate most of the
textbook answers:

- **£0/$0.** No licence spend. Rules out F1/F3 frontline licensing, Conditional
  Access, and Intune.
- **Many shared devices are Android tablets.** Rules out Windows Hello for
  Business entirely — WHfB is Windows-only and does nothing here.
- **Per-person sign-in/sign-out is unacceptable.** The time cost on the floor
  is prohibitive. This rules out Shared Device Mode, which was the only reason
  to consider frontline licensing, and rules out named per-worker Entra
  accounts as a daily-use pattern.
- **The users are metal workers with no patience for IT.** Anything requiring a
  per-shift action will not be used.

Taken together: the tablets stay permanently signed in as a shared identity.
That is a given. The work is making that arrangement safe for nothing.

#### The $0 answer: the password was never the control

Workers do sometimes have to re-authenticate on the tablets, unattended by IT,
so they must be able to enter a credential themselves. A long random vaulted
password is therefore not workable. An earlier draft of this document proposed
exactly that, and it was solving the wrong problem.

The password is not what keeps a leaver out. **The second factor is.** If the
second factor lives on a site-owned tablet, a leaver who knows the password
still cannot sign in — they do not have the tablet. The password can stay
simple, memorable and known to the floor, exactly as it is today.

That reduces the whole thing to **one change**:

> **Move the second factor off personal phones and onto the site-owned
> tablets** — Microsoft Authenticator installed on the devices themselves.

Nothing else has to change. Workers keep the password they already know, can
re-authenticate themselves whenever prompted, and approve with one tap on the
device in their hands. Total spend: nothing. Worker retraining: none.

Password rotation on departure drops from being the primary control to being
defence in depth — still worth doing when convenient, but no longer the thing
standing between a leaver and the tenant.

#### Optional upgrade, also free: passwordless phone sign-in

If you want to remove the password from re-authentication altogether,
**Microsoft Authenticator passwordless phone sign-in** does it: the user enters
the username, Authenticator on the same tablet shows a number to match, they
tap it. No password typed, ever, including at re-auth.

Confirmed as **not requiring a licence** — it works on Entra ID Free; P1 only
adds Conditional Access enforcement and richer reporting. Multiple accounts per
device are supported.

One thing to verify before rolling it out: the documentation covers *multiple
accounts on one device* clearly, but is not explicit about *one account across
many devices*, which is the shape here. Pilot it on a single tablet and confirm
a second tablet can register the same shared account before committing to it.

The tablet-bound-Authenticator change above stands on its own and does not
depend on this working.

#### Why named identities are not merely inconvenient but uneconomic

The tablets need **Smartsheet and SharePoint-hosted files** on sign-in.
SharePoint access requires a licensed account — an unlicensed Entra user cannot
reach it. So named per-worker identities would mean a licence per worker, for
every metal worker on the floor, at Business Premium or F3 rates.

That is the real reason shared accounts are correct here, rather than merely
convenient: a shared licensed identity serving a shared tablet is the only
arrangement that delivers SharePoint files to the floor at no incremental cost.
The shared accounts must therefore keep the licences they already hold.

If Smartsheet is reached through Entra SSO it comes along with the same
session. If it uses its own separate Smartsheet login, that is a second shared
credential and belongs in the vault under the same rules as the password below.

#### Limit the blast radius, since the tablet is now the credential

A permanently signed-in tablet with SharePoint access means a stolen tablet
reaches company files. This raises the stakes on device handling, and there is
a free control that materially reduces it:

**Scope the shared account's SharePoint permissions to only the libraries the
floor actually needs.** Not tenant-wide, not inherited-from-everyone. This costs
nothing, takes an afternoon, and converts "a lost tablet exposes the file
estate" into "a lost tablet exposes the shop-floor drawings". Do this before
worrying about anything else on the device side.

#### What this trades away, honestly

The risk moves from people to devices: whoever physically holds a signed-in
tablet has access. That is an acceptable trade for equipment that stays on site,
but it must be managed:

- **Android screen lock** on every tablet, and **screen pinning** to keep users
  in the app and out of settings. Both built into Android, no MDM, no licence.
- **On a lost or stolen tablet**: revoke sessions and rotate the password
  immediately. `tools/apply_changes.py` already performs the revoke.

**Attribution is not achievable in Entra under these constraints** and should
stop being chased there. It belongs in the application layer: QM3 already has
named vendor logins with an access audit (`feat/vendor-portal`), and the same
pattern applied to floor staff gives a per-person trail from a tap in the app,
at a fraction of the friction of an OS sign-out. Shared identity for the
device, named identity inside the app.

#### Where the second factor actually sits

Critical floor accounts have their second factor on the **team lead's phone**.
The non-urgent ones sit on the IT lead's. That is a more sensible arrangement
than it first appeared, and it defeats two arguments made earlier in this
document:

- It is **not** a leaver risk in the way originally written — these are current
  staff, not departed ones.
- IT is **not** a daily bottleneck for the floor. The team lead is on site, so
  re-authentication does not require interrupting IT. An earlier draft claimed
  otherwise; that was wrong.

#### The argument that does survive: team leads turn over

Staff turnover is high, and team lead is not exempt from it. So the second
factor for critical production accounts sits on the personal phone of someone
in a role that changes hands.

Each time it does:

- the factor leaves with them unless it is deliberately re-registered first
- a company-critical production credential has been living on personal
  hardware, and must be confirmed removed on departure
- someone has to redo the registration across every affected account, under
  time pressure, because the floor needs the accounts working

That is the real cost — not daily friction, but recurring churn plus a window
of exposure at each handover. Tablet-bound Authenticator removes the churn
entirely: the factor belongs to the device, which does not resign.

**The deciding question is whether the team lead's phone is company-owned or
personal.** If it is a company handset that stays with the role, the current
arrangement is defensible and this becomes low priority. If it is personal, the
factor is on hardware the business does not control and moving it is worth
doing.

#### Still worth doing regardless: `KynBoardRoom`

It has no Authenticator registration at all — only phone and WHfB. WHfB does
nothing on Android, so SMS to a single mobile is its only usable factor on a
tablet. That is fragile today and independent of the turnover question.

Once Authenticator is on the tablets, remove the phone methods to clear the
SMS dependency ahead of the February 2027 retirement.

### 2. Thirty-eight accounts on legacy per-user MFA

All are in `enforced` state. Most already carry Authenticator and WHfB, so the
*protection* is fine — it is the *management surface* that is legacy and
unsupported since 30 September 2025.

This blocks nothing today, but it must be cleared before Security Defaults or
Conditional Access can be enabled, because per-user MFA state cannot coexist
with either.

### 2a. `automation@` — UAT running as a privileged production identity

Sign-in log over the retained 30 days:

```
172 x QM3_Authentication      (browser client, Azure source IPs)
  2 x Microsoft Power BI
174 total, 65 failed (37%)
Licences: O365_BUSINESS_PREMIUM, POWER_BI_STANDARD, FLOW_FREE
Groups:   IT Team, ReportingArea, Production Team
Owns:     group "Jobs"
```

The 172 `QM3_Authentication` sign-ins are the **UAT app** logging into QM3.
Only the 2 Power BI sign-ins are the production purpose — M365 SSO for
automation inside Power BI reports.

That reordering matters, because it makes one issue smaller and one larger.

**Smaller: the managed identity migration.** A UAT app is not a production
dependency, so replacing the browser sign-in flow is engineering hygiene rather
than urgent risk. It also explains the 37% failure rate — a test environment
being tested will fail often, and 65 failures in 174 attempts is unremarkable
for UAT. Worth a glance at the error codes to confirm they are UAT noise and
not a real fault, but no longer alarming.

**Larger: UAT is authenticating as an over-privileged production identity.**
This account holds a Business Premium licence and Power BI, sits in **IT Team**,
**ReportingArea** and **Production Team**, and **owns the "Jobs" group** — with
**no MFA**. A test environment holding those credentials means any UAT
compromise, leaked config, or developer laptop yields a licensed account inside
IT Team. This is the sharpest finding in the audit and the cheapest to fix.

The account therefore splits three ways:

1. **UAT gets its own dedicated identity.** Separate account, minimum
   privilege, no group memberships it does not need, and unlicensed if UAT does
   not require SharePoint or Power BI. Costs nothing and removes production
   privilege from the test environment.
2. **Power BI SSO stays** on a much more tightly scoped `automation@` — the
   genuine user-identity dependency, which may not move to a service principal
   depending on the connector and whether SSO passthrough is in use.
3. **Strip the group memberships** that only exist because one account was
   doing several jobs. IT Team membership in particular has no business being
   reachable from a UAT credential.

Do (1) and (3) first. The managed identity work can follow whenever QM3's
roadmap suits.

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
2. **Give the QM3 UAT app its own identity** and strip `automation@` of the
   group memberships it only holds because one account does several jobs —
   IT Team especially. See 2a. Cheapest high-value fix on this list.
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
