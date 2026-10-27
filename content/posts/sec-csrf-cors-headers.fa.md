+++
date = '2027-04-17T10:00:00+03:30'
draft = false
title = 'CSRF، CORS و هدرهای امنیتی'
description = 'CSRF، CORS و هدرهای امنیتی در Go روی localhost: چرا CORS جلوی نوشتن جعلی را نمی‌گیرد، CORS با allow-list، توکن و بررسی Origin و تست هدرها.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "csrf", "cors", "security-headers", "go"]
cover = { image = "/images/covers/sec-csrf-cors-headers.fa.png", alt = "CSRF، CORS و هدرهای امنیتی", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [مجوزدهی: RBAC و IDOR](/fa/posts/sec-authorization-rbac-idor/)، می‌پرسید فراخواننده چه کاری می‌تواند بکند. این مقاله می‌پرسد آیا درخواست واقعاً از صفحه‌ی خودِ او آمده است. [نشست یا JWT؟](/fa/posts/sec-sessions-vs-jwt/) {{< term "csrf" "CSRF" >}} و {{< term "samesite" "SameSite" >}} را معرفی کرد و [تزریق و XSS](/fa/posts/sec-injection-xss/) {{< term "content-security-policy" "CSP" >}} و `HttpOnly` را؛ اینجا از سمت سرور عمیق‌تر می‌شوم. سبک API همان [net/http](/fa/posts/go-http-api-stdlib/) است.

> فقط دفاعی. یک برنامه‌ی Go 1.26 روی `127.0.0.1:9100`، داده‌ی درون حافظه، کوکی نشست ثابت `sid=s-alice` و پرچم `-mode vuln|fixed`. «origin بیگانه» فقط هدر `Origin` است که با curl می‌فرستم. **رفتار هیچ مرورگری را آزمایش نکردم**؛ هر ادعا درباره‌ی کار مرورگر از روی استانداردهاست و محتاطانه گفته شده.

## CORS را مرورگر اعمال می‌کند، نه سرور

{{< term "cors" "CORS" >}} به مرورگر می‌گوید صفحه‌ای از origin دیگر مجاز است پاسخ را *بخواند* یا نه. جلوی فرستاده‌شدن درخواست را نمی‌گیرد. POST با بدنه‌ی form یک «simple request» است: بدون preflight و با کوکی. در نسخه‌ی آسیب‌پذیر:

```
$ curl -si -H 'Cookie: sid=s-alice' -H 'Origin: https://evil.test' -d amount=30 /transfer
HTTP/1.1 200 OK
Access-Control-Allow-Credentials: true
Access-Control-Allow-Origin: https://evil.test
{"balance":70}
```

موجودی روی سرور از ۱۰۰ به ۷۰ رسید. حتی با CORS بی‌نقص این نوشتن انجام می‌شد؛ پس CORS دفاع CSRF نیست.

## درخواست preflight

بدنه‌ی JSON یا هدر سفارشی باعث می‌شود مرورگر اول یک درخواست {{< term "preflight" "preflight" >}} از نوع `OPTIONS` بفرستد. میان‌افزار من آن را از روی allow-list جواب می‌دهد (نسخه‌ی fixed، origin مجاز):

```
Access-Control-Allow-Credentials: true
Access-Control-Allow-Headers: Content-Type, X-CSRF-Token
Access-Control-Allow-Methods: GET, POST
Access-Control-Allow-Origin: https://app.example.test
Access-Control-Max-Age: 600
Vary: Origin
```

origin ناشناس فقط `Vary: Origin` می‌گیرد و هیچ هدر `Allow-*` نه؛ پس مرورگر درخواست اصلی را رد می‌کند. `Vary: Origin` مهم است چون جواب به این هدر وابسته است؛ بدون آن یک cache مشترک ممکن است جواب یک origin را به origin دیگر بدهد.

## اشتباه‌های کلاسیک CORS

- **بازتاب هر Origin همراه با credentials.** نسخه‌ی آسیب‌پذیر بالا همین را می‌کند. صفحه‌ی بدخواه آن‌وقت می‌تواند پاسخ‌های احراز‌شده را بخواند.
- **مجاز کردن `null`.** در نسخه‌ی آسیب‌پذیر، `Origin: null` هم `Access-Control-Allow-Origin: null` و credentials می‌گیرد. frameهای sandbox و ریدایرکت‌ها می‌توانند `null` بفرستند؛ پس هویت امنی نیست.
- **prefix یا regex شل.** تست matcher من:

```
https://app.example.test               bad=true  good=true
https://app.example.test.evil.test     bad=true  good=false
null                                   bad=false good=false
```

`bad` همان `strings.HasPrefix` است که شبیه‌ساز را می‌پذیرد؛ `good` جست‌وجوی دقیق در map است. regex را با `^...$` قفل کنید یا بهتر، اصلاً استفاده نکنید.

- **`*` همراه با credentials.** «CORS check» استاندارد Fetch را گرفتم: `*` را فقط وقتی می‌پذیرد که credentials mode برابر `include` نباشد؛ وگرنه هدر باید دقیقاً با origin درخواست برابر باشد و `Access-Control-Allow-Credentials: true` هم لازم است. پس `*` با کوکی ترکیب نمی‌شود.

## دفاع‌های CSRF با نتیجه

نسخه‌ی fixed، همان درخواست `/transfer`. کوکی حالا `SameSite=Lax` دارد (هدر نشان داده شده، مرورگر آزمایش نشده):

```
Set-Cookie: sid=s-alice; Path=/; HttpOnly; SameSite=Lax
```

بررسی‌های سمت سرور با curl:

```
Origin: https://evil.test            -> 403 cross-site request refused
Sec-Fetch-Site: cross-site           -> 403 cross-site request refused
Sec-Fetch-Site: same-origin, no token-> 403 bad csrf token
Sec-Fetch-Site: same-origin + token  -> 200 {"balance":70}
no Origin, no Sec-Fetch-Site         -> 403 cross-site request refused
```

موجودی تا درخواست معتبر ۱۰۰ ماند. سه لایه:

1. **بررسی Origin / Sec-Fetch-Site.** طبق استانداردها مرورگر این هدرها را می‌گذارد و اسکریپت صفحه نمی‌تواند عوضشان کند. درخواستِ بدون هر دو اینجا رد می‌شود؛ این کلاینت‌های غیرمرورگر را هم رد می‌کند، پس API واقعی برای آن‌ها راه احراز دیگری لازم دارد.
2. **توکن synchroniser.** `GET /csrf` یک HMAC از شناسه‌ی نشست برمی‌گرداند و `/transfer` آن را در فیلد فرم `csrf` می‌خواهد.
3. **کوکی double-submit.** `/api/settings` می‌خواهد کوکی `csrf` با هدر `X-CSRF-Token` برابر باشد. هدر نبود یا غلط بود: 403؛ برابر بود: 200. جواب می‌دهد چون صفحه‌ی بیگانه نمی‌تواند کوکی‌های این سایت را بخواند یا بگذارد؛ اگر زیردامنه‌ها قابل‌اعتماد نباشند ضعیف‌تر است.

## هدرهای امنیتی

نسخه‌ی fixed این‌ها را به هر پاسخ اضافه می‌کند (با `curl -i` دیده شد):

| هدر | هدف |
|---|---|
| `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'` | فقط منابع هم‌origin؛ جلوی frame شدن |
| `Strict-Transport-Security: max-age=31536000; includeSubDomains` | {{< term "hsts" "HSTS" >}}: دفعه‌ی بعد HTTPS |
| `X-Content-Type-Options: nosniff` | حدس‌زدن MIME ممنوع |
| `Referrer-Policy: strict-origin-when-cross-origin` | URL کمتر به سایت‌های دیگر |
| `Permissions-Policy: camera=(), microphone=(), geolocation=()` | خاموش کردن قابلیت‌های مرورگر |
| `Cross-Origin-Opener-Policy: same-origin` | جدا کردن پنجره از بازکننده‌ی بین‌origin |

طبق مشخصاتش HSTS روی HTTP ساده نادیده گرفته می‌شود؛ پس روی localhost فقط خودِ هدر دیده می‌شود و روی HTTPS اهمیت دارد (مقاله‌ی بعد).

یک تست جلوی پس‌رفت را می‌گیرد: همه‌ی routeها و یک مسیر ناشناس (404) را صدا می‌زند و حضور هر شش هدر را بررسی می‌کند. با `go test` سبز است؛ میان‌افزار دور کل mux است، پس پاسخ‌های خطا هم پوشش دارند.

## چند نکته‌ی مهم

- CORS خواندن را کنترل می‌کند، نه فرستادن را. نوشتن را با توکن یا بررسی origin محافظت کنید.
- origin دقیق در allow-list، `Vary: Origin`، هرگز بازتاب و هرگز `null`.
- فقط به `SameSite` تکیه نکنید؛ یک لایه است.
- با `GET` وضعیت را عوض نکنید.
- هدرها دفاع در عمق‌اند؛ XSS یا مجوزدهی نادرست را درست نمی‌کنند.

## تمرین

`/transfer` را طوری کنید که بدنه‌ی JSON با `X-CSRF-Token` بپذیرد و تستی بنویسید که `Origin` جعلی با توکن معتبر باز هم 403 بگیرد.

## قدم بعدی

مقاله‌ی بعد «TLS و گواهی x509 در عمل» است.
