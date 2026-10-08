---
name: gymnaskillz-app
category: productivity
description: Use when touching GymnaskillZ on Boostapp (client area). CLI + verified endpoint map for the class schedule, account, cards and the OTP login.
version: 1.0.0
author: GymnaskillZ (Boostapp member app) skill
platforms: [linux]
metadata:
  hermes:
    tags: [boostapp, gymnaskillz, api, cli, schedule, israel]
---

# GymnaskillZ client area on Boostapp

Boostapp (`app.boostapp.co.il`) is the member app used by GymnaskillZ — a calisthenics studio in
Tel Aviv (יצחק שדה 32). This skill is the API access path to **that one business only**:

| field | value |
|---|---|
| business | `GymnaskillZ` — `companyNum 893988` |
| business handle | `GetUrl` / `studioUrl` = `61c884e509bba` |
| client | resolve at runtime via `getClientData` — never hardcode a `clientId` into payloads |
| CLI | `python3 scripts/gym.py <command>` — start with `--help` |

Boostapp accounts can be attached to more than one business (`changeStudio.php`). Every payload here
is pinned to the ids above and the CLI aborts if the session resolves to a different `companyNum`.
**Do not generalise this skill to other businesses** — clone it into a separate skill instead.

## Quick start

```bash
python3 scripts/gym.py --help                 # full command list
python3 scripts/gym.py login status           # is the stored session still valid?
python3 scripts/gym.py whoami                 # studio + account behind the session
python3 scripts/gym.py classes --days 3       # schedule table (id, date, time, class, coach, spots, status)
python3 scripts/gym.py classes --date 2026-10-09 --json
python3 scripts/gym.py class 26548307         # one class (coach, spots, address, coords)
python3 scripts/gym.py activities             # punch cards / subscriptions
python3 scripts/gym.py medical                # medical-form status
python3 scripts/gym.py book 26633613          # dry-run: pre-flight verdict + exact payload
python3 scripts/gym.py book 26633613 --yes    # real registration (only on an explicit go-ahead)
python3 scripts/gym.py raw OrderClasses getClassInfo --data classId=26548307
```

State lives in `~/.gym/` (`cookies.txt` mode 600 + `session.json`); nothing else is persisted.

## Logging in (when the session expired)

There is **no password**: the only entry is a 4-digit OTP by SMS to the account owner's mobile
(pass it with `--phone` or export `GYM_PHONE` — it is deliberately not stored in the repo),
and the OTP is bound to the session that requested it. Workflow that works:

```bash
python3 scripts/gym.py login send          # sends ONE SMS; the owner reads the code out
python3 scripts/gym.py login verify 1234    # verify in the same jar, then POST /ajax.php newLogin
python3 scripts/gym.py login status         # confirm: logged_in true + companyNum 893988
```

Rules (learned the hard way — see `references/auth-and-sessions.md`):
* **One `send` per "I'm ready" signal.** Each send is a real SMS to the account holder and the endpoint
  rate-limits (`blocked:true` + `end_block`); retry loops flood the phone and get the number blocked.
* Never verify from a different session than the one that sent the code — it fails with
  `Mobile number verification failed` and burns an attempt.
* Never "try the browser instead" as a parallel path; that also consumes an SMS.

## What is read vs written

Read: 9 endpoints (schedule, class details, studio/account, cards, medical form, ratings) plus the
full login chain — all verified.

Write: two commands are wired into the CLI, both **dry-run by default** and requiring `--yes`:

```bash
python3 scripts/gym.py book 26633613          # prints a pre-flight verdict + the exact payload
python3 scripts/gym.py book 26633613 --yes    # actually registers (real booking on the account)
python3 scripts/gym.py cancel 26633613 --yes  # cancel (needs the booking's classStudioActId; unverified)
```

`book` pre-flights with `getPurchaseOptions` (exactly like the web app) and refuses nothing silently:
if the studio's funnel will reject the booking it says so before sending.

**Current account blocker (2026-10-08, verified):** every class in the window comes back with
`need_subscription: 0` (= *NEED_SUBSCRIPTION*) and `getPurchaseOptions` answers
`לא נמצאו מנויים המאפשרים שיבוץ לשיעור זה, יש לפנות לסטודיו לקבלת מידע נוסף` — the account used here has
**no active subscription / punch card** at GymnaskillZ, so the studio's own funnel refuses registrations
(also visible as an empty `activities` list). Adding a כרטיסייה (studio side) is the unblock.

Registration-slot status (`registrationStatus` / `register_btn_status`):
`0 AVAILABLE · 1 BOOKED · 2 BOOKED_AS_WAITING · 3 WAITING_LIST_AVAILABLE · 4 WAITING_LIST_UNAVAILABLE ·
5 PENDING · 6 CLOSED · 7 RESPONSE_WAITING_LIST`. Only `0` can be booked directly.

Remaining write endpoints (`registerToDebtableClass`, `registerWithNewItem`,
`switchClassOnCancel`, `confirmWaitingApproval`, waiting-list actions, ratings, cart) stay
documented-only in `references/endpoints.md` — use `gym.py raw` with an explicit instruction.
Never touch a payment path (`shopcart/`, `CheckOut.php`, `paymentPage.php`) without an explicit order.

## Reading the data

`getClassesData` returns `data.classes` — ~102 entries covering ~11 days ahead regardless of
`enableDays:28`. Per class the fields worth using:

* `id` (classId), `className`, `guideName`, `startDate` + `startTime`/`endTime`
* `brandName` (branch: `ג׳ימנסקילז` / `סניף ראשי`), `section.Title` (room, e.g. `GymnaskillZ Temple`)
* `clientRegister` / `maxClient` (spots), `isClassFull`, `isClientRegistered`, `registrationStatus`
* `freeClass`, `waitingListAvailability`, `unorderable`, `isCancelSwitchable`, `openOrderTime`/`closeOrderTime`

## Files

* `scripts/gym.py` — the CLI (argparse, `--help`, `--json`, pinned constants, session handling).
* `references/endpoints.md` — verified endpoint map, payloads, response samples, write endpoints.
* `references/auth-and-sessions.md` — login sequence, cookie/storage layout, traps and failure modes.

## When something breaks

| symptom | cause / fix |
|---|---|
| `not logged in` | session expired → `login send` + `login verify` |
| `Mobile number verification failed` | verified from a different session, code expired, or too many attempts |
| `Too many requests` + `end_block` | OTP rate limit — wait until that timestamp, one send only |
| HTTP 500 `Missing required parameters: studioUrl`/`getUrl` | controller call without the pinned params |
| `Method XController::y() does not exist` | wrong controller for that action — check the map |
| `getPurchaseOptions` → `לא נמצאו מנויים…` | the account has no usable subscription |
| empty `activities` array | no punch cards/subscriptions — the UI shows a CTA to `CheckOut.php` |
