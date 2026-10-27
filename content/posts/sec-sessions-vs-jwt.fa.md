+++
date = '2027-03-29T10:00:00+03:30'
draft = false
title = 'session یا JWT؟'
description = 'session یا JWT در Go: ویژگی‌های کوکی، logout فوری، payload خوانا در JWT، دست‌کاری، alg none، ابطال توکن و CSRF token، با خروجی واقعی.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "sessions", "jwt", "cookies", "csrf", "authentication", "go"]
cover = { image = "/images/covers/sec-sessions-vs-jwt.fa.png", alt = "session یا JWT؟", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [ذخیره‌ی امن پسورد: argon2 و bcrypt](/fa/posts/sec-password-hashing/)، در لحظه‌ی موفق شدن login تمام شد. حالا سرور باید برای درخواست بعدی به یاد بیاورد شما کی هستید. دو پاسخ رایج وجود دارد: {{< term "session" "نشست" >}} (**session**؛ سرور به یاد می‌سپارد) و {{< term "jwt" "JWT" >}} (کلاینت claimهای امضاشده را با خود می‌برد). زمینه یک API کوچک شبیه سفارش‌هاست از [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/). HttpOnly و CSP از [تزریق و XSS](/fa/posts/sec-injection-xss/) می‌آیند.

> فقط دفاعی. یک برنامه‌ی کوچک Go 1.26 با `github.com/golang-jwt/jwt/v5` نسخه‌ی v5.2.1 که روی 127.0.0.1 گوش می‌دهد و فقط خودم با `curl` به آن حمله کردم. **در مرورگر آزمایش نکردم**؛ فقط headerها را دیدم. دمویی جداست و ادامه‌ی دموی قبلی نیست.

## session سمت سرور

هنگام login، ۱۶ بایت تصادفی با `crypto/rand` می‌سازم، hex می‌کنم (۱۲۸ بیت) و `id -> user` را در یک map درون‌حافظه نگه می‌دارم:

```go
http.SetCookie(w, &http.Cookie{Name: "sid", Value: id, Path: "/",
	MaxAge: 3600, HttpOnly: true, Secure: true, SameSite: http.SameSiteLaxMode})
```

`curl -i` این را نشان می‌دهد (id جایگزین شده):

```
HTTP/1.1 200 OK
Set-Cookie: sid=<id>; Path=/; Max-Age=3600; HttpOnly; Secure; SameSite=Lax
```

id برابر ۳۲ کاراکتر hex بود. {{< term "httponly" "HttpOnly" >}} کوکی را از JavaScript صفحه پنهان می‌کند، `Secure` یعنی فقط HTTPS، و {{< term "samesite" "SameSite" >}}=Lax ارسال بین‌سایتی را محدود می‌کند. توجه: مرورگر ممکن است کوکی `Secure` را از http ساده ذخیره نکند (بعضی برای localhost استثنا می‌گذارند). من فقط header را دیدم و کوکی را دستی با `-H` فرستادم.

logout ورودی map را حذف می‌کند، پس ابطال فوری است:

```
GET /me      -> hello alice [200]
POST /logout -> logged out  [200]
GET /me      -> unauthorized [401]
```

هزینه: هر درخواست یک جستجو دارد و با چند سرور، store باید مشترک باشد (پایگاه داده یا cache). map من با restart از بین می‌رفت.

## JWT

JWT سه بخش base64url است. دو بخش اول توکنی را که با HS256 امضا کردم decode کردم:

```
parts: 3
header: {"alg":"HS256","typ":"JWT"}
payload: {"exp":1793085367,"role":"user","sub":"alice"}
signature bytes: 32
```

امضا شده، **نه رمزنگاری**: هر کسی توکن را دارد payload را می‌خواند، پس هرگز راز در آن نگذارید. امضا فقط تغییر را تشخیص می‌دهد. `role` را به `admin` تغییر دادم، امضای قدیمی را نگه داشتم و verify کردم:

```
verify original: <nil>
verify tampered: token signature is invalid: signature is invalid
```

## alg none و algorithm confusion

کتابخانه‌های قدیمی به فیلد `alg` خودِ توکن اعتماد می‌کردند و مهاجم می‌توانست `none` (بدون امضا) یا خانواده‌ی دیگری از الگوریتم را انتخاب کند. راه‌حل این است که سرور تصمیم بگیرد. verifier من الگوریتم را ثابت می‌کند و `exp` را الزامی می‌داند:

```go
jwt.Parse(tok, keyFunc, jwt.WithValidMethods([]string{"HS256"}), jwt.WithExpirationRequired())
```

توکن‌ها را برای verifier خودم ساختم:

```
verify alg=none:  token signature is invalid: signing method none is invalid
verify alg=HS512: token signature is invalid: signing method HS512 is invalid
verify expired:   token has invalid claims: token is expired
verify no exp:    token has invalid claims: token is missing required claim: exp claim is required
```

حمله‌ی confusion بین RS256 و HS256 را آزمایش نکردم؛ با ثابت‌کردن الگوریتم طبق طراحی همین رد می‌شود، ولی این استدلال است.

## مشکل ابطال

بعد از «logout» توکن هنوز معتبر است، چون سرور چیزی نگه نداشته:

```
POST /jwt/logout        -> logged out (client discards token)
GET  /jwt/me            -> hello alice [200]
```

راه‌ها: `exp` کوتاه (چند دقیقه) به‌همراه refresh token قابل‌ابطال، یا denylist شناسه‌ی توکن (`jti`). denylist را امتحان کردم:

```
POST /jwt/logout?denylist=1
GET  /jwt/me            -> unauthorized: revoked [401]
```

ببینید چه شد: سرور حالا وضعیت نگه می‌دارد و در هر درخواست جستجو می‌کند، یعنی همان session با چند قدم اضافه.

## CSRF

کوکی خودکار فرستاده می‌شود، پس سایت دیگری می‌تواند مرورگر را به فرستادن یک POST تغییردهنده‌ی وضعیت وادار کند. SameSite=Lax کمک می‌کند و توکن مخصوص هر نشست در header لایه‌ی دوم است. بدون توکن درخواست رد می‌شود و با توکن پذیرفته:

```
POST /transfer (no token)       -> csrf token missing or wrong [403]
POST /transfer (X-CSRF-Token)   -> transfer accepted [200]
```

مقایسه با `subtle.ConstantTimeCompare` است، مثل مقاله‌ی قبل. {{< term "csrf" "CSRF" >}} در مرورگر واقعی انجام نشد؛ این فقط بررسی سمت سرور را نشان می‌دهد.

## توکن را کجا نگه داریم (نظر شخصی)

- کوکی (HttpOnly): XSS نمی‌تواند بخواندش، ولی SameSite و دفاع در برابر CSRF لازم است.
- localStorage یا حافظه‌ی JS با header از نوع Bearer: CSRF ندارد، ولی هر XSS توکن را می‌خواند.
- نظر من: برای وب‌اپ کلاسیک، session با کوکی ساده‌ترین پیش‌فرض امن است. JWT برای فراخوانی سرویس‌به‌سرویس یا توکن‌های کوتاه‌عمر میان سیستم‌ها مناسب‌تر است.

## چند نکته‌ی مهم

- راز یا داده‌ای که باید ابطال شود در payload نگذارید.
- هنگام login شناسه‌ی session را عوض کنید (برای session fixation)؛ نمایش ندادم.
- راز HS256 بلند و تصادفی باشد؛ راز ضعیف آفلاین حدس زده می‌شود.
- همیشه `exp` را بررسی و الگوریتم را ثابت کنید.
- توکن کامل یا شناسه‌ی session را لاگ نکنید.

## تمرین

refresh token اضافه کنید: یک JWT پنج‌دقیقه‌ای و یک شناسه‌ی refresh تصادفی که سمت سرور ذخیره می‌شود. تستی بنویسید که نشان دهد ابطال شناسه‌ی refresh جلوی توکن‌های دسترسی جدید را می‌گیرد، و بسنجید توکن دسترسی قدیمی چقدر هنوز کار می‌کند.

## قدم بعدی

مقاله‌ی بعدی «OAuth2 و OIDC» است.
