# GymnaskillZ member API on Boostapp — endpoint map

Everything below was verified live against `https://app.boostapp.co.il` on 2026-10-08 with a
logged-in GymnaskillZ client session.

## Pinned business constants (do not parameterise)

| field | value | note |
|---|---|---|
| `companyNum` | `893988` | business id, appears in every payload |
| `GetUrl` / `studioUrl` | `61c884e509bba` | business handle; **the same token is used for both params** |
| studio name | `GymnaskillZ` | יצחק שדה 32, תל אביב-יפו |
| `clientId` | resolved at runtime | account id — comes from `getClientData`, never stored in the repo |
| base | `https://app.boostapp.co.il` | member app (`app.*`), **not** `login.*` (that is the staff console) |

> Boostapp accounts may be attached to several businesses (the app has `changeStudio.php`).
> Never let a payload fall back to a session default — always send the pinned ids, and verify
> `getStudioData.studio.companyNum == 893988` before acting.

## Request conventions

* POST, `application/x-www-form-urlencoded`, mobile Safari user-agent.
* `X-Requested-With: XMLHttpRequest` on controller calls.
* `X-CSRF-Token: <meta name="csrf-token">` taken from any logged-in page (`Home.php?GetUrl=…`).
* Standard payload:

```json
{ "action": "<method>", "getUrl": "61c884e509bba", "studioUrl": "61c884e509bba",
  "companyNum": 893988, "clientId": <resolved at runtime via getClientData> }
```

* Missing required parameters are reported as HTTP 500 JSON:
  `{"error":{"message":"Missing required parameters: studioUrl"}}`, and controller/method typos as
  `ReflectionException: Method UserController::getStudioData() does not exist`. Use that as an oracle
  while probing.

## Verified read endpoints

| controller (POST `/controllerAction/<x>.php`) | `action` | required extras | returns |
|---|---|---|---|
| `OrderMeeting` | `getStudioData` | – | `{status,success,studio:{name,address,companyNum,lessons,meetings,medicalForm,branches,workHours,logo,…},user:{id,name,avatar,email,medical}}` |
| `ClientAction` | `getClientData` | `studioUrl` | `{status:1,message:"success",data:{client:<clientId>,companyNum:893988}}` |
| `OrderClasses` | `getClassesData` | `clientId` | `{success,code:200,data:{enableDays:28,earliestClassDate,classes:[…]}}` (102 classes, ~11 days) |
| `OrderClasses` | `getClassInfo` | `classId` | `{success,code:200,data:{id,name,start_date,end_date,branch,coach,registered,registered_max,price,address,coords,FreeClass,WatingListOrederShow,…}}` |
| `OrderClasses` | `getPurchaseOptions` | `classStudioDateId` | booking options; returns Hebrew error `לא נמצאו מנויים המאפשרים שיבוץ לשיעור זה` when the client has no usable membership |
| `ClientActivity` | `getClientActivitiesForHomePage` | `clientId`, `companyNum` | `{status:200,success:true,data:[…]}` — punch cards / subscriptions; `data:[]` = none |
| `ClientAction` | `getMedicalForms` | – | `{status:200,success:true,data:{signed:true}}` |
| `Ratings` | `getRatingAction` | `clientId` | `[]` when there is no pending coach rating |

### `getClassesData` — class object (47 fields, real sample)

```json
{"id":26548307,"className":"Strength","guideName":"שגיא טסלר",
 "startDate":"2026-10-08","endDate":"2026-10-08","startTime":"16:00:00","endTime":"16:55:00",
 "brandId":0,"brandName":"סניף ראשי","section":{"id":3837,"Title":"GymnaskillZ Temple","CompanyNum":893988},
 "clientRegister":10,"maxClient":16,"purchaseAmount":"0.00","freeClass":0,
 "openOrder":1,"openOrderType":1,"closeOrder":1,"closeOrderType":1,"openOrderTime":"10","closeOrderTime":"10",
 "isClassFull":false,"isClientRegistered":false,"registrationStatus":0,"registerationText":"registration",
 "waitingListAvailability":true,"unorderable":false,"isCancelSwitchable":false,
 "color":"#ad53ff","class_color":"#ad53ff","classNameType":14001,"sectionId":3837,"sectionName":null,
 "genderLimit":0,"showClientNum":true,"limitLevel":"0","need_subscription":0,"classLimitTypes":0,
 "classMemberType":null,"tag":null,"userAct":null,"isOnline":false,"start_date":"2026-10-08T13:00:00.000Z"}
```

Useful fields: `id` (classId), `className`, `guideName`, `startDate`/`startTime`/`endTime`,
`brandName` (branch), `clientRegister`/`maxClient` (spots), `isClassFull`, `isClientRegistered`,
`registrationStatus` (`0` = not registered, `3` = full/closed in October data), `freeClass`,
`waitingListAvailability`, `section.Title` (room).

## Session / auth endpoints

| endpoint | payload | result |
|---|---|---|
| POST `/loginController.php` | `{"mobile_number":<mobile, digits only>,"action":"send_otp","type":0}` (JSON; `type` **int**, `0`=SMS `1`=WhatsApp) | `{"message":"OTP sent successfully","blocked":false}` or `{"message":"Too many requests","blocked":true,"end_block":"2026-10-08T13:19:17+03:00"}` |
| POST `/loginController.php` | `otp=<4 digits>&action=verify_otp` (form) | `{"type":"success","message":"Your mobile number is verified!","updated":1}` — **same session as the send** |
| POST `/ajax.php` | `action=newLogin&mobile=+972<9 digits>&areaCode=+972` (+ `X-CSRF-Token`) | `{"message":{"redirect":"parentClient.php"},"success":true}` → sets `login_<md5>` + `GetUrl` cookies = logged in |
| POST `/ajax.php` | `action=logout` | ends the session |
| GET `/indexnew.php` | – | login page when anonymous; the member app (with `#clientHeaderId data-companyNum`) when logged in |

## Member-app pages (JS-rendered shells — they need `?GetUrl=61c884e509bba`)

`Home.php`, `ClassWeek.php`, `lessons.php`, `ClassHistory.php`, `MyMemberShip.php`, `MyProfile.php`,
`Order.php`, `Invoice.php`, `Notification.php`, `OnlineLibrary.php`, `TakanonFix.php`, `MedicalFix.php`,
`CheckOut.php`, `changeStudio.php`, `logout.php`.
They are page shells: content is fetched with the controller calls above, so scraping is a last resort.

## Write endpoints

`book` and `cancel` are wired into the CLI (dry-run by default, `--yes` to send). The rest stay
documented-only — call them through `gym.py raw` only on an explicit instruction, because they
register, cancel or charge.

| controller | `action` | extras | effect |
|---|---|---|---|
| `OrderClasses` | `registerToFreeClass` | `classStudioDateId`, `clientId` | **wired**: `gym.py book <id> --yes` |
| `OrderClasses` | `registerToDebtableClass` | `classStudioActId`, `clientId` | book against a subscription (creates a debt) |
| `OrderClasses` | `registerToClassWithClientActivity` | `classStudioActId`, `clientActivityId` | book using a card |
| `OrderClasses` | `registerWithNewItem` | `classStudioActId`, `itemId`/`isSingleClassItem` | book + buy an item |
| `OrderClasses` | `cancelBookingToClass` | `classStudioActId`, `actStatus` | **wired**: `gym.py cancel <id> --yes` (unverified until a real booking exists) |
| `OrderClasses` | `cancelBookingInfo` | `classId` | (read-ish) cancellation terms; returns `Server error` without a live booking |
| `OrderClasses` | `checkOrderCancellation`, `checkWaitingClassApprovals` | `classId` / – | policy + waiting-list state |
| `OrderClasses` | `confirmWaitingApproval`, `rejectWaitingApproval` | `oldClassStudioActId` | answer a waiting-list offer |
| `OrderClasses` | `waitingListFirstWinBooking` | `classStudioActId` | take the first freed spot |
| `OrderClasses` | `switchClassOnCancel` | `oldClassStudioActId`, `newClassId` | move instead of cancelling |
| `OrderClasses` | `deleteReservationTime` | `classStudioActId`, `classId` | drop a reservation |
| `Ratings` | `saveNewRating`, `denyAnswerRating` | `actionId`, `clientId`, `rating`, `review` | rate a coach |
| `shopcart/ShopCartAjax.php` | `addMeetingToCart` | – | cart (meetings only; this studio has `meetings:false`) |

### Booking prerequisites (verified 2026-10-08)

* `getPurchaseOptions` is the funnel the web app uses before registering
  (`{classStudioDateId: <class id>, orderType: 1}`; `orderType: 2` for the waiting-list branch).
  With no usable subscription it returns HTTP-level
  `{"status":400,"success":false,"message":"לא נמצאו מנויים המאפשרים שיבוץ לשיעור זה, יש לפנות לסטודיו לקבלת מידע נוסף"}`.
* Every class in the window carries `need_subscription: 0` → *NEED_SUBSCRIPTION*
  (`-1 FREE`, `0 NEED_SUBSCRIPTION`, `1 PRICE_AND_SUBSCRIPTION`) and `debtable: false`.
* Slot status codes (`registrationStatus`): `0 AVAILABLE`, `1 BOOKED`, `2 BOOKED_AS_WAITING`,
  `3 WAITING_LIST_AVAILABLE`, `4 WAITING_LIST_UNAVAILABLE`, `5 PENDING`, `6 CLOSED`,
  `7 RESPONSE_WAITING_LIST`.
* Success shape from a registration call: `{success, code, message, data:{success, message, reasonId, text}}`
  (`reasonId` explains a refusal).
* Good extras on a class: `classStudioActId` / `user_registration_id` (booking id, needed for cancel),
  `register_btn_status`, `studioUrl` (short studio slug, e.g. `U6kKZ` — distinct from the `GetUrl`
  cookie token, yet the controllers accept the cookie value in both `getUrl` and `studioUrl`).

## Error shapes seen

* `{"status":400,"success":false,"message":"<Hebrew text>"}` — business-level refusal.
* `{"status":400,"success":false,"message":"Server error"}` — bad/absent extra params.
* HTTP 500 with a PHP exception JSON — missing mandatory param or unknown controller method.
* Rate limit on the OTP endpoint: `blocked:true` + `end_block` (ISO with offset).
