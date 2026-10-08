# Auth, sessions and their traps (Boostapp member app)

Verified 2026-10-08 against GymnaskillZ / `companyNum 893988`.

## Why this is not a normal API login

Boostapp's member app has **no password login** and **no API key**: the only way in is a 4-digit
OTP sent by SMS to the client's mobile. Worse, the OTP is bound to the **PHP session that requested
it** — verifying it from a second session returns
`{"type":"error","message":"Mobile number verification failed"}` even when the code is correct.
So: *request + verify + finish must happen inside one session* (the CLI keeps one cookie jar in
`~/.gym/cookies.txt` and `gym.py login send` / `gym.py login verify <code>` run against it).

## The full login sequence

```text
1. GET  /indexnew.php
   → cookies: BoostApp_session, boostapp_lang, boostapp_dir ; page has <meta name="csrf-token">

2. POST /loginController.php      (JSON body)
   {"mobile_number": <mobile, digits only>, "action": "send_otp", "type": 0}      # type is an INT: 0=SMS 1=WhatsApp
   → {"message":"OTP sent successfully","blocked":false}
   → if flooded: {"message":"Too many requests","blocked":true,
                  "end_block":"2026-10-08T13:19:17+03:00"}   ← wait until that timestamp, do NOT loop

3. POST /loginController.php      (form-encoded)
   otp=<4 digits>&action=verify_otp
   → {"type":"success","message":"Your mobile number is verified!","updated":1}
   <!-- NOTE: the response carries NO token; the value of this step is that the SESSION
        is now marked "phone verified". Nothing is authenticated yet. -->

4. POST /ajax.php                 (form-encoded, header X-CSRF-Token from step 1)
   action=newLogin&mobile=+972<9 digits>&areaCode=+972
   → {"message":{"redirect":"parentClient.php"},"success":true}
   → cookies added: login_<md5>, GetUrl=<business token>     ← THIS is the logged-in state
```

After step 4, `GET /Home.php?GetUrl=<token>` returns the member app and contains
`<div id="clientHeaderId" data-companyNum="893988" data-source="1" data-id="<clientId>">`.

### Traps that cost real time

* `/newLogin` and `/newLogin.php` return **404**. `newLogin` is a `BeePOS.ajaxFormCb` **callback name**
  (see `assets/js/main.js`), not a route: the form is posted to `BeePOS.options.ajaxUrl` = `/ajax.php`
  with `action=newLogin`. Reading the JS bundle instead of the HTML form `action=` attribute prevents this.
* `send_otp` is rate-limited per phone number. Each retry is a real SMS to a human. One attempt per
  "ready" signal — never a retry loop, never a "let me try the browser instead" second attempt.
* A verification attempt from a session that did not request the code fails and burns one of the
  ~3 allowed code attempts.
* `X-CSRF-Token` is required by `/ajax.php`; controller calls tolerate its absence but the CMS-side
  actions do not.
* Sessions survive for a long time (cookie `login_<md5>`), but `GET /indexnew.php` silently falls back
  to the login page when they expire — always check for `clientHeaderId` before assuming you are in.

## Session storage used by this repo

| path | content |
|---|---|
| `~/.gym/cookies.txt` | Mozilla-format cookie jar (`BoostApp_session`, `login_*`, `GetUrl`, …), mode 600 |
| `~/.gym/session.json` | metadata: base URL, pinned `companyNum`/`GetUrl`, cookie names, save time |

`gym.py login status` reports whether the stored session is still authenticated.
`gym.py login logout` deletes both files locally (the server side session simply ages out).

## Multi-business hazard

An account can be a client of several businesses (the app exposes `changeStudio.php`). The cookie
`GetUrl` decides which business every page and controller call resolves to. Therefore:

1. the CLI always sends `getUrl` + `studioUrl` = the pinned GymnaskillZ token, and
2. `gym.py whoami` refuses to continue if `getStudioData.studio.companyNum != 893988`.

If a future task needs another business, add a **separate** script/skill — do not parameterise this one.
