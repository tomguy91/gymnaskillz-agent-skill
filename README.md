# GymnaskillZ · סקיל ו‑CLI לאזור המתאמנים בבוסטאפ (Boostapp)

סקיל + כלי שורת פקודה לגישה **לאזור האישי של GymnaskillZ** באפליקציית המתאמנים של Boostapp
(`app.boostapp.co.il`) — לוח שיעורים, פרטי שיעור, הכרטיסייה/מנוי, הטפסים הרפואיים, דירוג מאמן,
והרשמה/ביטול של שיעור — ישירות מול ה‑API שהאפליקציה עצמה משתמשת בו.

הסקיל **נעול בכוונה לעסק אחד** — GymnaskillZ (חדר כושר קלסתניקס, יצחק שדה 32, תל אביב‑יפו).
לחשבון Boostapp יכולות להיות כמה עסקים מחוברים ("החלפת עסק"), ולכן כל בקשה מוצמדת למזהי העסק
הקבועים והכלי **מסרב לפעול** אם הסשן מצביע על עסק אחר. אין להשתמש בסקיל הזה לעסק אחר —
יש לשכפל אותו לסקיל נפרד.

---

## מה יש כאן

```
SKILL.md                          הסקיל עצמו: תהליכי עבודה, שדות הנתונים, מלכודות וכללי בטיחות
scripts/gym.py                    ה‑CLI (Python 3, ספרייה תקנית בלבד) — gym.py --help
references/endpoints.md           מפת נקודות הקצה שאומתו מול השרת, כולל payloads ותשובות לדוגמה
references/auth-and-sessions.md   שרשרת ההתחברות (OTP), אחסון ה‑cookies ומצבי כשל
README.md                         הקובץ הזה (עברית) — כל התיעוד המרכזי
```

---

## התקנה והרצה

אין תלויות חיצוניות — Python 3.9 ומעלה בלבד.

```bash
python3 scripts/gym.py --help          # כל הפקודות והדגלים
python3 scripts/gym.py login status    # האם הסשן השמור עדיין תקף
python3 scripts/gym.py whoami          # העסק והחשבון שמאחורי הסשן
```

מצב הסשן נשמר ב‑`~/.gym/` (`cookies.txt` בהרשאות 600 וגם `session.json` עם מטא‑דאטה).
אין שרת, אין מסד נתונים ואין קבצי הגדרה נוספים.

---

## התחברות (OTP בטלפון — אין סיסמה)

לאפליקציית המתאמנים **אין סיסמה** ו**אין API key**: הכניסה היחידה היא קוד בן 4 ספרות ב‑SMS
לנייד של המשתמש הרשום. הקוד **נקשר לסשן שביקש אותו**, ולכן הבקשה, האימות וסיום ההתחברות חייבים
לקרות באותו סשן (הכלי מחזיק cookie jar אחד לשם כך):

```bash
python3 scripts/gym.py login send          # שולח SMS אחד בלבד לנייד המוגדר
python3 scripts/gym.py login verify 1234   # אימות הקוד + סיום ההתחברות
python3 scripts/gym.py login status        # אימות: logged_in + companyNum של GymnaskillZ
```

כללי ברזל (נלמדו בדרך הקשה):

* **שליחה אחת לכל "אני מוכן".** כל `send` הוא SMS אמיתי לאדם, והשרת חוסם שליחות חוזרות
  (`blocked:true` + `end_block`). לולאת ניסיונות מציפה את הטלפון וחוסמת את המספר.
* **לא לאמת מסשן אחר** מהסשן ששלח את הקוד — מתקבל `Mobile number verification failed` ונגרפת עוד ניסיון.
* **לא לנסות במקביל דרך דפדפן** — גם זה צורך SMS נוסף.

המספר עצמו **אינו שמור בריפו** (פרטיות): מעבירים אותו בכל קריאה עם `--phone 9725XXXXXXXX`
או מגדירים `GYM_PHONE` בסביבה.

---

## פקודות ה‑CLI

| פקודה | מה היא עושה |
|---|---|
| `gym.py whoami` | העסק + החשבון מאחורי הסשן (`getStudioData`) |
| `gym.py classes [--days N] [--date YYYY-MM-DD] [--coach X] [--branch Y] [--free] [--open] [--mine] [--limit N]` | לוח השיעורים (`getClassesData`) — טבלה עם מזהה, תאריך, שעה, שם, מאמן, מקומות וסטטוס |
| `gym.py class <classId>` | פרטים מלאים לשיעור בודד (`getClassInfo`) |
| `gym.py activities` | כרטיסיות/מנויים פעילים (`getClientActivitiesForHomePage`) |
| `gym.py medical` | סטטוס טופס רפואי (`getMedicalForms`) |
| `gym.py rating` | בקשת דירוג מאמן ממתינה (`getRatingAction`) |
| `gym.py book <classId> [--yes]` | הרשמה לשיעור — **dry‑run כברירת מחדל**, `--yes` שולח בפועל |
| `gym.py cancel <classId> [--yes]` | ביטול הרשמה — דורש את מזהה ההרשמה (`classStudioActId`) |
| `gym.py page <Page.php>` | הורדת דף גולמי מהאזור האישי (למשל `MyProfile.php`) |
| `gym.py raw <Controller> <action> --data k=v` | שליחת בקשה חופשית לנקודת קצה — escape hatch למפתחים |

כל פקודה תומכת ב‑`--json` (פלט JSON גולמי במקום טבלה) וב‑`--help`:

```bash
python3 scripts/gym.py classes --days 3
python3 scripts/gym.py classes --coach "<שם המאמן>" --open --json
python3 scripts/gym.py book 26633613            # תצוגה מקדימה: בדיקת "pre-flight" + ה‑payload המדויק
python3 scripts/gym.py book 26633613 --yes      # הרשמה אמיתית (שינוי בחשבון!)
python3 scripts/gym.py raw OrderClasses getClassesData --data clientId=0
```

---

## מה אומת מול השרת (2026-10-08)

**קריאה:** `getStudioData` (עסק + משתמש), `getClientData` (מזהה לקוח), `getClassesData` (102 שיעורים,
~47 שדות לכל שיעור, חלון של כ‑11 יום), `getClassInfo`, `getPurchaseOptions` (בדיקת זכאות להרשמה),
`getClientActivitiesForHomePage` (כרטיסיות), `getMedicalForms`, `getRatingAction` — וגם כל שרשרת
ההתחברות (`send_otp` → `verify_otp` → `/ajax.php?action=newLogin`).

**כתיבה (מחווט ל‑CLI, dry‑run כברירת מחדל):** `registerToFreeClass` (הרשמה), `cancelBookingToClass` (ביטול).
שאר פעולות הכתיבה — הרשמה בחוב/כרטיסייה, רשימת המתנה, החלפת שיעור, דירוג, סל — מתועדות ב‑
`references/endpoints.md` וזמינות דרך `gym.py raw` בלבד, ובאישור מפורש.

**מצב הרישום של שיעור** (`registrationStatus` / `register_btn_status`):
`0 AVAILABLE · 1 BOOKED · 2 BOOKED_AS_WAITING · 3 WAITING_LIST_AVAILABLE · 4 WAITING_LIST_UNAVAILABLE ·
5 PENDING · 6 CLOSED · 7 RESPONSE_WAITING_LIST`. רק `0` ניתן להרשמה ישירה.

**תנאי סף להרשמה (אומת):** לפני הרשמה האפליקציה קוראת ל‑`getPurchaseOptions`, ואם אין מנוי/כרטיסייה
מתאימים היא מחזירה `לא נמצאו מנויים המאפשרים שיבוץ לשיעור זה, יש לפנות לסטודיו לקבלת מידע נוסף`.
במצב כזה גם ה‑CLI יציג את אותה אזהרה לפני שליחה.

---

## מה לא לעשות

* **לא** להפעיל נתיבי תשלום/סליקה (`shopcart/`, `CheckOut.php`, `paymentPage.php`) בלי הוראה מפורשת.
* **לא** להריץ `book`/`cancel` בלי אישור — אלו שינויים אמיתיים בחשבון של אדם.
* **לא** להעביר את הקבועים של GymnaskillZ לעסק אחר: הסקיל נעול בכוונה לעסק אחד.
* **לא** לייצר לולאות שליחת OTP: כל שליחה = SMS אמיתי, והשרת חוסם.

---

## הערות טכניות

* הבקשות הן `POST` עם `application/x-www-form-urlencoded`, User‑Agent של מובייל, ו‑
  `X-CSRF-Token` שנלקח מה‑`meta` של דף מחובר.
* כל בקשה כוללת `action`, `getUrl`, `studioUrl`, `companyNum` ובדרך כלל `clientId`.
* פרמטר חסר מחזיר HTTP 500 עם JSON של חריגת PHP — למשל `Missing required parameters: studioUrl` —
  וזה משמש כ"אורקל" לגילוי החוזה של כל נקודת קצה.
* ה‑API אינו מתועד על ידי Boostapp; כל מה שכאן אומת ידנית מול השרת בזמן אמת.

---

## רישיון והיקף

כלי פנימי. אינו קשור ל‑Boostapp או ל‑GymnaskillZ מבחינה רשמית. השימוש באחריות המשתמש.
