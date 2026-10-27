+++
date = '2027-04-09T10:00:00+03:30'
draft = false
title = 'مجوزدهی: RBAC و IDOR'
description = 'مجوزدهی در Go روی localhost: مجوزهای RBAC، رفع IDOR با بررسی مالکیت و 404، ارتقای نقش با mass assignment و تستی که هر route را می‌پاید.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "authorization", "rbac", "idor", "go"]
cover = { image = "/images/covers/sec-authorization-rbac-idor.fa.png", alt = "مجوزدهی: RBAC و IDOR", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [OAuth2 و OIDC](/fa/posts/sec-oauth2-oidc/)، با توکنی تمام شد که می‌گوید فراخواننده کیست و چه scopeهایی دارد. این ورودیِ {{< term "authorization" "مجوزدهی" >}} است، نه جواب آن: سرور هنوز باید برای هر تابع و هر شیء تصمیم بگیرد این فراخواننده چه کاری می‌تواند بکند. {{< term "idor" "IDOR" >}} را کوتاه در [OWASP Top 10 در کد واقعی](/fa/posts/sec-owasp-top10-in-code/) نشان دادم؛ اینجا عمیق‌تر می‌شویم، با نقش‌ها، یک باگ mass-assignment و تستی که از هر route نگهبانی می‌کند. سبک API همان [net/http قبلی](/fa/posts/go-http-api-stdlib/) است.

> فقط دفاعی. یک برنامه‌ی کوچک Go 1.26 روی `127.0.0.1`، داده‌ی درون حافظه، کد خودم. احراز هویت به توکن‌های ثابت (`tok-alice`، `tok-bob`، `tok-carol`) ساده شده تا تمرکز روی مجوزدهی بماند. پرچم `-mode vuln|fixed` هر نسخه را می‌سازد. کاربران: alice (viewer)، bob (editor، tenant دیگر) و carol (admin). سند ۱ مال alice و سند ۲ مال bob است.

## 401، 403 یا 404

- **401**: نمی‌دانم کی هستی. توکن نیست یا بد است.
- **403**: می‌شناسمت و اجازه‌ی این کار را نداری. این هم نشان می‌دهد آن چیز وجود دارد.
- **404**: برای شیءهای کاربران دیگر، تا غریبه نتواند «مال تو نیست» را از «وجود ندارد» تشخیص دهد.

## نسخه‌ی آسیب‌پذیر

alice (viewer) build آسیب‌پذیر را صدا می‌زند:

```
GET /documents/2 (bob's) -> {"id":2,"owner":"bob","title":"bob secret"} [200]
DELETE /documents/2      -> [204]
GET /admin/users         -> [{"name":"alice",...,"role":"viewer"},{"name":"bob",...},{"name":"carol",...}] [200]
PATCH /users/me  {"name":"alice","role":"admin"} -> {"name":"alice","tenant":"acme","role":"admin"} [200]
```

چهار حفره‌ی مختلف. اولی سطح شیء است (alice سند bob را می‌خواند)؛ دومی و سومی سطح تابع‌اند (viewer حذف می‌کند و داده‌ی admin را فهرست می‌کند)؛ چهارمی {{< term "mass-assignment" "mass assignment" >}} است: handler مستقیم JSON را در struct به نام `User` decode می‌کند و کلاینت نقش خودش را انتخاب کرده. تا آنجا که یادم است فهرست OWASP API Security دو مورد اول را «Broken Object Level Authorization» و «Broken Function Level Authorization» می‌نامد، اما ویرایش فعلی را دوباره بررسی نکردم.

## رفع‌ها

**سطح شیء.** مالکیت جزو جستجوست و جواب برای شیء دیگران 404 است:

```go
if d == nil || d.Owner != u.Name {
    http.Error(w, "not found", 404)
    return
}
```

با پایگاه داده همین ایده می‌شود `WHERE id = $1 AND owner_id = $2`: یک query، بدون مرحله‌ی جدا «بگیر، بعد چک کن» که فراموشش کنیم. اینجا map بود و با Postgres اجرایش نکردم.

**سطح تابع.** نقش‌ها به مجوز نگاشت می‌شوند و route می‌گوید چه می‌خواهد:

```go
var perms = map[string][]string{
    "viewer": {"doc:read"},
    "editor": {"doc:read", "doc:write"},
    "admin":  {"doc:read", "doc:write", "doc:delete", "users:read"},
}
a.protect("DELETE /documents/{id}", "doc:delete", a.deleteDoc)
```

کد مجوز را بررسی می‌کند، نه نام نقش را؛ این همان هدف {{< term "rbac" "RBAC" >}} است. wrapper اول بررسی 401 و بعد بررسی مجوز را انجام می‌دهد.

**Mass assignment.** در یک نوع allow-list صریح decode کنید:

```go
var in struct {
    Name string `json:"name"`
}
json.NewDecoder(r.Body).Decode(&in)
```

همان alice، build اصلاح‌شده:

```
GET /documents/2         -> not found [404]
GET /documents/99        -> not found [404]
DELETE /documents/2      -> forbidden [403]
GET /admin/users         -> forbidden [403]
PATCH /users/me {"name":"alice","role":"admin"} -> {"name":"alice","tenant":"acme","role":"viewer"} [200]
GET /documents/1 (hers)  -> {"id":1,"owner":"alice","title":"alice plan"} [200]
```

سندی که هست (۲) و سندی که نیست (۹۹) حالا یکسان دیده می‌شوند. فیلد اضافه‌ی `role` نادیده گرفته می‌شود. خطوط لاگ سرور برای ردها:

```
level=WARN msg="authz denied" user=alice doc=2 owner=bob
level=WARN msg="authz denied" user=alice role=viewer need=doc:delete route="DELETE /documents/{id}"
level=WARN msg="authz denied" user=alice role=viewer need=users:read route="GET /admin/users"
```

هر رد را با «چه کسی، چه چیزی، کدام قاعده» لاگ کنید ([لاگ ساختاریافته](/fa/posts/go-config-logging-errors/) جست‌وجویش را ممکن می‌کند). موجی از 404 و 403 از یک کاربر شکل enumeration است. توکن را لاگ نکنید.

## رد پیش‌فرض و تستی که آن را اجرا می‌کند

قاعده‌ی طراحی {{< term "deny-by-default" "رد پیش‌فرض" >}} است: هر route توکن می‌خواهد مگر اینکه صریحاً عمومی اعلام شود. یک تست این قاعده را از ویرایش‌های بعدی نجات می‌دهد. routeها با دو helper ثبت می‌شوند که الگو را ضبط می‌کنند و تست هر کدام را بدون توکن صدا می‌زند:

```go
var publicRoutes = map[string]bool{"GET /healthz": true}
// for every registered route not in publicRoutes: expect 401
```

برای دیدن کارکردش موقتاً `GET /debug/vars` بدون محافظت را با `public(...)` اضافه کردم:

```
routes_test.go:26: GET /debug/vars answered 200 without a token, want 401
--- FAIL: TestEveryRouteRequiresAuth (0.00s)
    --- FAIL: TestEveryRouteRequiresAuth/GET_/debug/vars (0.00s)
FAIL
```

route را برداشتم و مجموعه‌ی تست دوباره پاس می‌شود (`TestViewerCannotDelete` هم 403 را می‌سنجد). محدودیت: این تست routeهایی را می‌گیرد که با helperهای من ثبت شده‌اند، نه handlerی که دستی روی mux نصب شود.

## فراتر از نقش‌ها

وقتی قاعده‌ها به ویژگی‌ها (مالک، tenant، زمان) یا روابط (عضو تیم یک پوشه) بستگی دارند، RBAC دست‌وپاگیر می‌شود. مدل‌های ABAC (مبتنی بر ویژگی) و ReBAC (مبتنی بر رابطه) این موارد را پوشش می‌دهند. فقط نامشان را می‌آورم؛ هیچ‌کدام را اجرا نکردم.

## چند نکته‌ی مهم

- مجوزدهی را در سرور و برای هر تابع و هر شیء بررسی کنید. پنهان کردن دکمه بررسی نیست.
- هویت را از توکن تأییدشده بگیرید، نه از شناسه‌ای در body یا URL.
- در نوع allow-list decode کنید؛ هرگز در struct پایگاه داده یا دامنه.
- ثابت‌قدم باشید: 404 برای شیء دیگران، 403 برای تابعی که نقشتان ندارد.
- ردها را لاگ کنید و تست کنید که route جدید تصادفی عمومی نشود.

## تمرین

قاعده‌ای برای `editor` اضافه کنید: editorها می‌توانند سندهای tenant خودشان را ویرایش کنند. تست دومِ آگاه از tenant بنویسید که در آن carol (admin در acme) برای سند globex مال bob باید 404 بگیرد.

## قدم بعدی

مقاله‌ی بعدی «CSRF، CORS و هدرهای امنیتی» است.
