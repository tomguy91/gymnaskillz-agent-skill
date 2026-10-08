#!/usr/bin/env python3
"""
gym.py — CLI for the GymnaskillZ client area on Boostapp (app.boostapp.co.il).

IMPORTANT: this CLI is hard-wired to ONE business:
    GymnaskillZ  ·  companyNum 893988  ·  GetUrl 61c884e509bba
Boostapp accounts can be attached to several businesses ("החלפת עסק" / changeStudio.php),
so every request is pinned to the GymnaskillZ ids and the CLI refuses to talk to
another business even if the session cookie points elsewhere.

Run `gym.py --help` or `gym.py <command> --help` for usage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import MozillaCookieJar

# --------------------------------------------------------------------------- #
# Pinned business (GymnaskillZ) — the whole point of this skill is to stay on
# this one business. The business ids below are public URL/id values of the
# studio; NO personal identifiers belong in this file.
# --------------------------------------------------------------------------- #
BASE = os.environ.get("GYM_BASE", "https://app.boostapp.co.il")
COMPANY_NUM = int(os.environ.get("GYM_COMPANY_NUM", "893988"))   # GymnaskillZ business id
GET_URL = os.environ.get("GYM_GET_URL", "61c884e509bba")         # business handle used by every call
STUDIO_NAME = os.environ.get("GYM_STUDIO_NAME", "GymnaskillZ")
STUDIO_ADDRESS = "יצחק שדה 32, תל אביב-יפו"

# The OTP phone number is personal data and is deliberately NOT stored in this
# repo: pass it per call (`--phone`) or export GYM_PHONE in your environment.
DEFAULT_PHONE = os.environ.get("GYM_PHONE", "")

HOME = os.path.expanduser("~")
STATE_DIR = os.path.join(HOME, ".gym")
COOKIE_FILE = os.path.join(STATE_DIR, "cookies.txt")
META_FILE = os.path.join(STATE_DIR, "session.json")

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

CTX = ssl._create_unverified_context()


# --------------------------------------------------------------------------- #
# HTTP layer
# --------------------------------------------------------------------------- #
class GymError(RuntimeError):
    pass


class GymClient:
    def __init__(self) -> None:
        os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
        self.jar = MozillaCookieJar(COOKIE_FILE)
        try:
            self.jar.load(ignore_discard=True)
        except Exception:
            pass
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self._csrf: str | None = None

    # -- low level ---------------------------------------------------------- #
    def _headers(self, referer: str, json_like: bool = True) -> dict:
        h = {
            "User-Agent": UA,
            "Accept": "application/json, text/javascript, */*; q=0.01" if json_like else "text/html,*/*",
            "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
            "Origin": BASE,
            "Referer": referer,
        }
        return h

    def get_page(self, page: str) -> str:
        """GET a member-app page (Home.php, MyMemberShip.php, ...)."""
        url = f"{BASE}/{page}"
        if "?" not in url:
            url += f"?GetUrl={GET_URL}"
        req = urllib.request.Request(url, headers=self._headers(url, json_like=False))
        with self.opener.open(req, timeout=45) as r:
            return r.read().decode("utf-8", "replace")

    def logged_in(self, page_html: str | None = None) -> tuple[bool, dict]:
        html = page_html if page_html is not None else self.get_page("Home.php")
        m = re.search(r'id="clientHeaderId"[^>]*>', html)
        if not m:
            return False, {}
        attrs = dict(re.findall(r'data-([a-zA-Z0-9_\-]+)="([^"]*)"', m.group(0)))
        return True, attrs

    def csrf(self) -> str:
        if not self._csrf:
            html = self.get_page("Home.php")
            m = re.search(r'name="csrf-token" content="([^"]+)"', html)
            self._csrf = m.group(1) if m else ""
        return self._csrf

    def post(self, path: str, payload: dict, page: str = "Home.php") -> dict | list | str:
        """POST to an app endpoint. `path` is absolute-path style, e.g. /ajax.php."""
        url = BASE + path
        referer = f"{BASE}/{page}" + ("" if "?" in page else f"?GetUrl={GET_URL}")
        h = self._headers(referer)
        h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        h["X-Requested-With"] = "XMLHttpRequest"
        if path.endswith(".php") and "/controllerAction/" in path:
            h["X-CSRF-Token"] = self.csrf()
        elif path == "/ajax.php":
            h["X-CSRF-Token"] = self.csrf()
        data = urllib.parse.urlencode(payload).encode()
        req = urllib.request.Request(url, headers=h, data=data, method="POST")
        try:
            with self.opener.open(req, timeout=45) as r:
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            body = e.read(2000).decode("utf-8", "replace")
            raise GymError(f"HTTP {e.code} on {path}: {body[:300]}") from None
        try:
            return json.loads(raw)
        except ValueError:
            return raw

    # -- business calls ----------------------------------------------------- #
    def call(self, controller: str, action: str, extra: dict | None = None) -> dict | list | str:
        """POST to /controllerAction/<controller>.php pinned to GymnaskillZ."""
        payload = {
            "action": action,
            "getUrl": GET_URL,
            "studioUrl": GET_URL,
            "companyNum": COMPANY_NUM,
        }
        payload.update(extra or {})
        payload.pop("clientId", None) if "clientId" not in (extra or {}) else None
        return self.post(f"/controllerAction/{controller}.php", payload)

    def whoami_data(self) -> dict:
        res = self.call("OrderMeeting", "getStudioData")
        if isinstance(res, str):
            raise GymError(f"unexpected response: {res[:200]}")
        if not res.get("success"):
            raise GymError(res.get("message") or "getStudioData failed")
        studio = res.get("studio") or {}
        if str(studio.get("companyNum")) != str(COMPANY_NUM):
            raise GymError(
                f"session is attached to companyNum={studio.get('companyNum')} "
                f"({studio.get('name')}), not GymnaskillZ ({COMPANY_NUM}). "
                "Run `gym.py login` with a GymnaskillZ account.")
        user = res.get("user") or {}
        return {"studio": studio, "user": user, "clientId": user.get("id")}

    def client_id(self) -> int:
        d = self.call("ClientAction", "getClientData", {"studioUrl": GET_URL})
        if isinstance(d, dict) and d.get("status") == 1:
            data = d.get("data") or {}
            if str(data.get("companyNum")) not in ("", str(COMPANY_NUM)):
                raise GymError("session returned a different business (changeStudio)")
            return int(data["client"])
        raise GymError(f"getClientData failed: {d if isinstance(d,str) else json.dumps(d)[:200]}")

    # -- auth --------------------------------------------------------------- #
    def send_otp(self, phone: str = DEFAULT_PHONE, channel: int = 0) -> dict:
        """channel: 0=SMS, 1=WhatsApp. Sends ONE code (server rate-limits repeats)."""
        self.get_page("indexnew.php")           # session + csrf
        res = self.post("/loginController.php", {
            "mobile_number": int(phone),
            "action": "send_otp",
            "type": channel,
        }, page="indexnew.php")
        self.save()
        return res if isinstance(res, dict) else {"raw": res}

    def verify_otp(self, code: str, phone: str = DEFAULT_PHONE) -> dict:
        """Verify the code in the SAME session, then finish the login (/ajax.php newLogin)."""
        res = self.post("/loginController.php",
                        {"otp": code, "action": "verify_otp"}, page="indexnew.php")
        if isinstance(res, str):
            # jQuery-style form encoding fallback
            res = self.post("/loginController.php",
                            {"otp": code, "action": "verify_otp"}, page="indexnew.php")
        if not isinstance(res, dict) or res.get("type") != "success":
            raise GymError(f"verify_otp failed: {res if isinstance(res,str) else json.dumps(res, ensure_ascii=False)}")
        intl = "+" + str(phone).lstrip("+") if not str(phone).startswith("+972") else str(phone)
        done = self.post("/ajax.php", {"action": "newLogin", "mobile": "+972" + str(phone)[-9:], "areaCode": "+972"},
                         page="indexnew.php")
        self._csrf = None
        logged, attrs = self.logged_in()
        self.save()
        return {"verify": res, "newLogin": done, "logged_in": logged, "client": attrs}

    def save(self) -> None:
        os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
        self.jar.save(ignore_discard=True)
        try:
            os.chmod(COOKIE_FILE, 0o600)
        except OSError:
            pass
        meta = {"saved": time.strftime("%Y-%m-%d %H:%M:%S"), "base": BASE,
                "companyNum": COMPANY_NUM, "getUrl": GET_URL, "studio": STUDIO_NAME,
                "cookies": [c.name for c in self.jar]}
        with open(META_FILE, "w") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)
        try:
            os.chmod(META_FILE, 0o600)
        except OSError:
            pass

    def forget(self) -> None:
        for f in (COOKIE_FILE, META_FILE):
            if os.path.exists(f):
                os.remove(f)
        self.jar.clear()
        self._csrf = None


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
def out_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def fmt_time(t: str | None) -> str:
    return (t or "")[:5]


def print_classes(rows: list[dict]) -> None:
    if not rows:
        print("no classes matched")
        return
    print(f"{'id':>10}  {'date':<10} {'time':<13} {'class':<26} {'coach':<18} {'spots':<7} {'status'}")
    for c in rows:
        spots = f"{c.get('clientRegister', '?')}/{c.get('maxClient', '?')}"
        status = "FULL" if c.get("isClassFull") else ("mine" if c.get("isClientRegistered") else "open")
        print(f"{c['id']:>10}  {c.get('startDate',''):<10} "
              f"{fmt_time(c.get('startTime'))}-{fmt_time(c.get('endTime')):<8} "
              f"{str(c.get('className',''))[:25]:<26} {str(c.get('guideName',''))[:17]:<18} {spots:<7} {status}")
    print(f"\n{len(rows)} classes")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_login(args) -> int:
    g = GymClient()
    if args.step in ("send", "verify") and not args.phone:
        print("no phone number given.\n"
              "The OTP phone is personal data and is not stored in this tool — pass it explicitly:\n"
              "  gym.py login send --phone 9725XXXXXXX   (digits only, country code, no +)\n"
              "or export GYM_PHONE in the environment.", file=sys.stderr)
        return 2
    if args.step == "status":
        logged, attrs = g.logged_in()
        out_json({"logged_in": logged, "header": attrs, "state_dir": STATE_DIR})
        return 0
    if args.step == "send":
        res = g.send_otp(args.phone, 0 if args.channel == "sms" else 1)
        out_json(res)
        print("\nSMS requested. Rate limits are aggressive — ask the user for the code and run:\n"
              f"  gym.py login verify <4-digit-code>", file=sys.stderr)
        return 0 if res.get("message", "").startswith("OTP sent") else 2
    if args.step == "verify":
        if not args.code:
            print("verify needs the 4-digit code: gym.py login verify 1234", file=sys.stderr)
            return 2
        res = g.verify_otp(args.code, args.phone)
        out_json(res)
        return 0 if res.get("logged_in") else 2
    if args.step == "logout":
        g.forget()
        print("local session cookies deleted")
        return 0
    return 2


def cmd_whoami(args) -> int:
    g = GymClient()
    logged, attrs = g.logged_in()
    if not logged:
        print("not logged in — run: gym.py login send  (then: gym.py login verify <code>)", file=sys.stderr)
        return 3
    data = g.whoami_data()
    if args.json:
        out_json(data)
        return 0
    s, u = data["studio"], data["user"]
    print(f"studio      : {s.get('name')}  (companyNum {s.get('companyNum')})")
    print(f"address     : {s.get('address')}")
    print(f"lessons     : {s.get('lessons')}   meetings: {s.get('meetings')}   medical form: {s.get('medicalForm')}")
    print(f"account     : {u.get('name')}  (clientId {u.get('id')})")
    print(f"email       : {u.get('email')}")
    print(f"session     : companyNum {attrs.get('companyNum')} / clientId {attrs.get('id')} (from page header)")
    return 0


def cmd_classes(args) -> int:
    g = GymClient()
    cid = g.client_id()
    res = g.call("OrderClasses", "getClassesData", {"clientId": cid})
    if not isinstance(res, dict) or not res.get("success"):
        raise GymError(str(res)[:300])
    rows = (res.get("data") or {}).get("classes") or []
    if args.days:
        today = time.strftime("%Y-%m-%d")
        end = time.strftime("%Y-%m-%d", time.localtime(time.time() + args.days * 86400))
        rows = [c for c in rows if today <= c["startDate"] <= end]
    if args.date:
        rows = [c for c in rows if c["startDate"] == args.date]
    if args.coach:
        rows = [c for c in rows if args.coach in (c.get("guideName") or "")]
    if args.free:
        rows = [c for c in rows if c.get("freeClass")]
    if args.open_only:
        rows = [c for c in rows if not c.get("isClassFull")]
    if args.mine:
        rows = [c for c in rows if c.get("isClientRegistered")]
    if args.branch:
        rows = [c for c in rows if args.branch in (c.get("brandName") or "")]
    rows.sort(key=lambda c: (c["startDate"], c.get("startTime") or ""))
    if args.limit:
        rows = rows[: args.limit]
    if args.json:
        out_json(rows)
    else:
        print_classes(rows)
    return 0


def cmd_class(args) -> int:
    g = GymClient()
    res = g.call("OrderClasses", "getClassInfo", {"classId": int(args.class_id)})
    if args.json:
        out_json(res)
        return 0
    d = (res or {}).get("data") if isinstance(res, dict) else None
    if not d:
        out_json(res)
        return 0
    print(json.dumps(d, ensure_ascii=False, indent=2))
    return 0


def _find_class(g: GymClient, class_id: int) -> dict:
    cid = g.client_id()
    res = g.call("OrderClasses", "getClassesData", {"clientId": cid})
    classes = ((res or {}).get("data") or {}).get("classes") or []
    for c in classes:
        if int(c["id"]) == int(class_id):
            return c
    raise GymError(f"class {class_id} is not in the current schedule window "
                   f"({len(classes)} classes returned)")


def cmd_book(args) -> int:
    """Register for a class. Dry-run unless --yes is given."""
    g = GymClient()
    cid = g.client_id()
    c = _find_class(g, args.class_id)
    status = c.get("registrationStatus")
    labels = {0: "AVAILABLE", 1: "already BOOKED", 2: "BOOKED_AS_WAITING", 3: "WAITING_LIST_AVAILABLE",
              4: "WAITING_LIST_UNAVAILABLE", 5: "PENDING", 6: "CLOSED", 7: "RESPONSE_WAITING_LIST"}
    print(f"class {c['id']} · {c.get('className')} · {c.get('startDate')} "
          f"{fmt_time(c.get('startTime'))}-{fmt_time(c.get('endTime'))} · {c.get('guideName')}")
    print(f"  spots {c.get('clientRegister')}/{c.get('maxClient')} · status {status} "
          f"({labels.get(status, '?')}) · need_subscription {c.get('need_subscription')} · "
          f"price {c.get('purchaseAmount')}")

    if status != 0:
        print(f"\nnothing to do: registration slot status is {labels.get(status, status)} — "
              "not an open AVAILABLE slot.")
        return 1

    # Pre-flight exactly like the web app does (orderType=1) — it is the call that tells you
    # whether a subscription/card allows booking at all.
    pre = g.call("OrderClasses", "getPurchaseOptions",
                 {"classStudioDateId": c["id"], "orderType": 1})
    if isinstance(pre, dict) and not pre.get("success", True):
        print(f"\npre-flight (getPurchaseOptions) says: {pre.get('message')}")
        print("=> the studio's booking funnel will refuse this registration.")

    payload = {"classStudioDateId": int(c["id"]), "clientId": cid}
    if not args.yes:
        print("\nDRY RUN — nothing sent. With --yes this would POST to /controllerAction/OrderClasses.php:")
        print("  " + json.dumps({"action": "registerToFreeClass", "companyNum": COMPANY_NUM, **payload},
                                ensure_ascii=False))
        return 0

    res = g.call("OrderClasses", "registerToFreeClass", payload)
    out_json(res)
    after = _find_class(g, args.class_id)
    ok = bool(after.get("isClientRegistered")) or after.get("registrationStatus") in (1, 2, 5)
    print(f"\nverify: isClientRegistered={after.get('isClientRegistered')} "
          f"registrationStatus={after.get('registrationStatus')} -> {'BOOKED' if ok else 'NOT BOOKED'}")
    return 0 if ok else 1


def cmd_cancel(args) -> int:
    """Cancel a booking. Needs the booking's classStudioActId (shown by `classes --mine` when booked)."""
    g = GymClient()
    c = _find_class(g, args.class_id)
    act_id = args.act_id or c.get("userAct") or c.get("classStudioActId")
    act_status = args.act_status if args.act_status is not None else c.get("registrationStatus")
    if not act_id:
        print("no booking id (classStudioActId) available for this class — nothing to cancel.\n"
              "The field is only populated for classes you are actually booked to; take it from\n"
              "`gym.py --json classes --mine` (userAct / classStudioActId).")
        return 1
    payload = {"classStudioActId": int(act_id), "actStatus": int(act_status)}
    if not args.yes:
        print("DRY RUN — nothing sent. With --yes this would POST to /controllerAction/OrderClasses.php:")
        print("  " + json.dumps({"action": "cancelBookingToClass", "companyNum": COMPANY_NUM, **payload},
                                ensure_ascii=False))
        print("  (unverified path: first real cancellation will confirm it end-to-end)")
        return 0
    res = g.call("OrderClasses", "cancelBookingToClass", payload)
    out_json(res)
    after = _find_class(g, args.class_id)
    print(f"\nverify: isClientRegistered={after.get('isClientRegistered')} "
          f"registrationStatus={after.get('registrationStatus')}")
    return 0


def cmd_activities(args) -> int:
    g = GymClient()
    cid = g.client_id()
    res = g.call("ClientActivity", "getClientActivitiesForHomePage",
                 {"clientId": cid, "companyNum": COMPANY_NUM})
    if args.json:
        out_json(res)
        return 0
    data = (res or {}).get("data") if isinstance(res, dict) else None
    if not data:
        print("no active subscriptions / punch cards (כרטיסיות) for this business")
        return 0
    for a in data:
        print(json.dumps(a, ensure_ascii=False))
    return 0


def cmd_medical(args) -> int:
    g = GymClient()
    res = g.call("ClientAction", "getMedicalForms")
    out_json(res)
    return 0


def cmd_rating(args) -> int:
    g = GymClient()
    res = g.call("Ratings", "getRatingAction", {"clientId": g.client_id()})
    out_json(res)
    return 0


def cmd_pages(args) -> int:
    g = GymClient()
    html = g.get_page(args.page)
    if args.json:
        out_json({"page": args.page, "bytes": len(html)})
    else:
        print(html)
    return 0


def cmd_raw(args) -> int:
    """Raw POST to any controller — escape hatch, bypasses the pins only for the action name."""
    g = GymClient()
    extra = {}
    for kv in args.data or []:
        if "=" not in kv:
            raise GymError(f"--data expects k=v, got {kv!r}")
        k, v = kv.split("=", 1)
        if v.isdigit():
            v = int(v)
        elif v.lower() in ("true", "false"):
            v = v.lower() == "true"
        extra[k] = v
    if not args.action:
        payload = dict(extra)
        payload.setdefault("getUrl", GET_URL)
        payload.setdefault("studioUrl", GET_URL)
        payload.setdefault("companyNum", COMPANY_NUM)
        res = g.post(args.path if args.path.startswith("/") else "/" + args.path, payload)
    else:
        ctrl = args.controller or "OrderClasses"
        res = g.call(ctrl, args.action, extra)
    out_json(res)
    return 0


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gym.py",
        description=("CLI for the GymnaskillZ client area on Boostapp "
                     f"(companyNum {COMPANY_NUM}, GetUrl {GET_URL}). Read-oriented: "
                     "listing the schedule, the account and the cards. Booking calls are "
                     "documented in references/endpoints.md but NOT wired here on purpose."),
        epilog=("examples:\n"
                "  gym.py whoami\n"
                "  gym.py classes --days 3\n"
                "  gym.py classes --date 2026-10-09 --json\n"
                "  gym.py class 26548307\n"
                "  gym.py activities\n"
                "  gym.py raw OrderClasses getClassesData --data classId=26548307\n"
                "  gym.py login send   &&   gym.py login verify 1234\n"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--json", action="store_true", help="print raw JSON instead of a table (global)")

    sub = p.add_subparsers(dest="cmd", metavar="<command>")

    sp = sub.add_parser("login", help="OTP login flow (phone + SMS code) and session handling")
    sp.add_argument("step", choices=["send", "verify", "status", "logout"],
                    help="send = request code, verify = finish with code, status = show session, logout = delete local cookies")
    sp.add_argument("code", nargs="?", help="4-digit code (for `verify`)")
    sp.add_argument("--phone", default=DEFAULT_PHONE,
                    help="mobile number, digits only incl. country code (or set GYM_PHONE); "
                         "never stored in this repo")
    sp.add_argument("--channel", choices=["sms", "whatsapp"], default="sms", help="delivery channel (default sms)")
    sp.set_defaults(func=cmd_login)

    sp = sub.add_parser("whoami", help="studio + account behind the current session")
    sp.set_defaults(func=cmd_whoami)

    sp = sub.add_parser("classes", help="class schedule (getClassesData)")
    sp.add_argument("--days", type=int, help="only the next N days")
    sp.add_argument("--date", help="only this date (YYYY-MM-DD)")
    sp.add_argument("--coach", help="filter by coach name substring")
    sp.add_argument("--branch", help="filter by branch/brand name substring")
    sp.add_argument("--free", action="store_true", help="only free classes")
    sp.add_argument("--open", dest="open_only", action="store_true", help="hide full classes")
    sp.add_argument("--mine", action="store_true", help="only classes I am registered to")
    sp.add_argument("--limit", type=int, help="max rows")
    sp.set_defaults(func=cmd_classes)

    sp = sub.add_parser("class", help="details for one class (getClassInfo)")
    sp.add_argument("class_id", help="class id from `classes`")
    sp.set_defaults(func=cmd_class)

    sp = sub.add_parser("activities", help="subscriptions / punch cards (getClientActivitiesForHomePage)")
    sp.set_defaults(func=cmd_activities)

    sp = sub.add_parser("book", help="register for a class (dry-run unless --yes)")
    sp.add_argument("class_id", help="class id from `classes`")
    sp.add_argument("--yes", action="store_true",
                    help="actually send the registration (a real booking on the account)")
    sp.set_defaults(func=cmd_book)

    sp = sub.add_parser("cancel", help="cancel a booking (dry-run unless --yes)")
    sp.add_argument("class_id", help="class id from `classes --mine`")
    sp.add_argument("--act-id", type=int, help="classStudioActId of the booking (defaults to the class field)")
    sp.add_argument("--act-status", type=int, help="actStatus of the booking (defaults to the class field)")
    sp.add_argument("--yes", action="store_true", help="actually send the cancellation")
    sp.set_defaults(func=cmd_cancel)

    sp = sub.add_parser("medical", help="medical-form status (getMedicalForms)")
    sp.set_defaults(func=cmd_medical)

    sp = sub.add_parser("rating", help="pending coach-rating request (getRatingAction)")
    sp.set_defaults(func=cmd_rating)

    sp = sub.add_parser("page", help="dump a raw member-app page (Home.php, MyProfile.php, ...)")
    sp.add_argument("page", help="page name, e.g. MyMemberShip.php")
    sp.set_defaults(func=cmd_pages)

    sp = sub.add_parser("raw", help="raw POST to a controller action (escape hatch)")
    sp.add_argument("controller", help="controller name without .php, e.g. OrderClasses")
    sp.add_argument("action", nargs="?", help="controller action, e.g. getClassesData")
    sp.add_argument("--path", help="POST to this path instead (e.g. /ajax.php)")
    sp.add_argument("--data", action="append", help="extra field k=v (repeatable)")
    sp.set_defaults(func=cmd_raw)

    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # allow `--json` after the subcommand too
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except GymError as e:
        print(f"error: {e}", file=sys.stderr)
        return 4
    except BrokenPipeError:            # e.g. `gym.py classes --json | head`
        try:
            sys.stdout.close()
        except Exception:
            pass
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
