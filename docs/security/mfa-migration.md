# MFA migration & shared account design

Midland Pty Ltd — prepared 6 Sep 2026

## Why now

Microsoft-provided SMS and voice MFA retire **1 February 2027**. There is no
opt-out. Any account whose only second factor is a phone number gets a blocking
prompt and cannot sign in until it registers a passkey.

Separately, the tenant is still on **legacy per-user MFA**, which Microsoft
stopped supporting as a management surface on 30 September 2025. Security
Defaults are off and no Conditional Access is in force, so there is currently no
tenant-level control surface to manage the transition through.

Run `tools/mfa-audit.ps1` for the authoritative list of affected accounts.

## Constraint: licensing

The tenant has one Business Premium licence. This bounds the options:

| Capability | Needs | Available today |
|---|---|---|
| Security Defaults | nothing | yes |
| Conditional Access | Entra ID P1 per covered user | no |
| Graph `signIns` API | Entra ID P1/P2 | no |
| Unified audit log (`UserLoggedIn`) | any M365 subscription | yes |
| FIDO2 / passkeys | nothing | yes |

Two consequences worth stating plainly:

- Passkeys and FIDO2 security keys are **free**. The fix for the Feb 2027
  deadline does not require a licence upgrade.
- Any monitor built on the Graph `signIns` API needs P1. A licence-safe monitor
  must read the Office 365 unified audit log instead.

## Shared accounts

The six shared accounts are real, necessary and ongoing. They are not one
problem — they are three, and each has a different correct answer.

### A. Shop-floor and meeting-room terminals

`kynproduction` · `parkesproduction` · `powdercoat` · `warroom-pks` · `kynboardroom`

**Register two FIDO2 security keys per account.**

A passkey does not have to live on a phone. A hardware key physically attached
to the terminal satisfies phishing-resistant MFA, survives the Feb 2027
retirement, and needs no personal device, no SIM, and no licence upgrade. It is
precisely what Microsoft is steering everyone toward.

- Enable **FIDO2** in the Authentication Methods Policy first.
- Two keys per account, always: one on the terminal, one spare in the site safe.
  A single key is one loss away from a locked-out production line.
- Once both keys are registered, **remove the phone number** from the account.
  That is the step that actually clears the Feb 2027 exposure.
- Record a named human owner for each account. An account nobody owns is an
  account nobody rotates.

Budget roughly $40–80 per key, so ~$400–800 for the set with spares.

### B. Accounts that are really just a mailbox

Before buying keys, check which of the five above exist mainly so several people
can *read mail* rather than *log into a terminal*.

If it is a mailbox, convert it to a **shared mailbox**: no sign-in, no MFA, no
password, no licence, no Feb 2027 exposure. Named users are granted access and
authenticate as themselves. This removes the account from the problem entirely
rather than hardening it — always prefer it where it fits.

### C. `automation@` — a service account

This is the wrong shape for the job and should not be a user account at all.

Replace it with an **Entra app registration using certificate credentials**
(or a managed identity, for anything running in Azure). Benefits:

- Completely unaffected by the SMS/voice retirement — no interactive sign-in.
- Scoped, least-privilege permissions instead of a full user's access.
- Certificate rotation instead of a shared password.
- Clean audit trail attributable to the integration, not to "someone".

OpsMachine already runs Graph and Smartsheet integrations, so this is an
established pattern here rather than new ground.

**If a SaaS product genuinely only accepts a user login** (CIN7 Core may be one —
confirm before assuming), keep it as a user account but treat it as break-glass:
FIDO2 key stored in the safe, long random password in the vault, no interactive
day-to-day use, and access reviewed on every staff departure.

## Sequencing

Order matters. Getting this wrong causes lockouts.

1. Run `tools/mfa-audit.ps1`. Get the real list.
2. Enable FIDO2 and passkeys in the Authentication Methods Policy.
3. Triage the five shared terminals into "terminal" (keys) vs "mailbox"
   (convert to shared mailbox).
4. Register keys / convert mailboxes. Verify each one signs in.
5. Remove phone numbers from every migrated account.
6. Migrate `automation@` to an app registration.
7. Inventory anything still using legacy authentication — Security Defaults
   blocks it, and that is what will break integrations.
8. **Only then**: set `perUserMfaState` to `disabled` for all users, then
   enable Security Defaults.

Step 8 is last for a reason. Security Defaults cannot coexist with per-user MFA
states, and it forces MFA registration for everyone within 14 days.

## Replacing the MFA monitor

The current third-party monitor alerts per sign-in event on "no MFA evidence".
That is why it is noisy: token refreshes, SSO, and remembered devices all
legitimately show no MFA on the event itself, so the signal is mostly false
positives and gets ignored — which is worse than no monitor.

A useful replacement inverts the model.

**Watch state, not events.** Snapshot MFA posture nightly (the same query
`mfa-audit.ps1` runs) and alert only on *changes*:

- an account loses its last strong method
- a new account appears with no MFA
- an account still has phone as its only factor (a countdown, not a nag)
- per-user MFA reappears on any account after migration

**Reserve per-event alerts for genuine anomalies**, from the unified audit log
(`UserLoggedIn`, licence-safe): sign-in from a new country, legacy auth protocol
used, shop-floor account authenticating from outside Australia.

**Deliver a daily digest, not a stream.** One email, one table of deltas. Only
high-severity events interrupt.

**Keep exclusions in version control** — a config file in the repo, reviewed
like any other change. This directly fixes the "my overrides didn't stick"
failure of the current product.

Suggested shape as an OpsMachine module:

| Concern | Approach |
|---|---|
| Data source | Office 365 Management Activity API + per-user Graph state |
| Auth | Existing app registration, certificate credential |
| Schedule | Nightly, alongside existing cron jobs |
| State | Previous snapshot persisted for delta comparison |
| Transport | Existing `noreply@midlandind.com.au` sender |
| Config | `security-monitor.config.json`, committed |
| Escalation | Digest by default; immediate mail on severity ≥ high |
