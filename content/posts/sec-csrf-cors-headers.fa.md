+++
date = '2027-04-17T10:00:00+03:30'
draft = false
title = 'CSRF، CORS و هدرهای امنیتی'
description = 'CSRF، CORS و هدرهای امنیتی در Go روی localhost: چرا CORS جلوی نوشتن جعلی را نمی‌گیرد، CORS با allow-list، توکن و بررسی Origin و تست هدرها.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "csrf", "cors", "security-headers", "go"]
cover = { image = "/images/covers/sec-csrf-cors-headers.fa.png", alt = "CSRF، CORS و هدرهای امنیتی", hiddenInSingle = true }
+++

Alice را در نظر بگیرید که در یک تب مرورگر وارد حساب بانکش شده است. در تب دیگری صفحه‌ای به‌ظاهر بی‌آزار باز می‌کند. آن صفحه یک فرم پنهان دارد که به `https://bank.example/transfer` ارسال می‌شود و یک اسکریپت که به‌محض بارشدن صفحه همان فرم را submit می‌کند. مرورگر همان کاری را می‌کند که همیشه می‌کند: درخواست را می‌فرستد و کوکی بانک را هم ضمیمه می‌کند، چون مقصد درخواست بانک است. بانک یک نشست معتبر می‌بیند و پول را جابه‌جا می‌کند. Alice هیچ‌چیز را کلیک نکرده است.

این {{< term "csrf" "CSRF" >}} است (cross-site request forgery، جعل درخواست بین‌سایتی) و یکی از دلایلی است که دانستن «فراخواننده کیست و چه اجازه‌ای دارد» ([مجوزدهی: RBAC و IDOR](/fa/posts/sec-authorization-rbac-idor/)) کافی نیست. درخواست باید واقعاً از صفحه‌ی خود فراخواننده آمده باشد. [session یا JWT؟](/fa/posts/sec-sessions-vs-jwt/) از CSRF و ویژگی کوکی به نام {{< term "samesite" "SameSite" >}} گفت و [تزریق و XSS](/fa/posts/sec-injection-xss/) {{< term "content-security-policy" "CSP" >}} و `HttpOnly` را معرفی کرد. در این مقاله سمت سرور را می‌بینم: چطور چنین درخواستی را رد کنیم، {{< term "cors" "CORS" >}} کجای ماجراست (اغلب آن را با دفاع در برابر CSRF اشتباه می‌گیرند و دفاع نیست)، و کدام هدرهای پاسخ لایه‌ی دیگری اضافه می‌کنند. سبک API همان [net/http مقاله‌های قبل](/fa/posts/go-http-api-stdlib/) است.

> فقط دفاعی. یک برنامه‌ی Go روی loopback با داده‌ی درون حافظه، یک کوکی نشست ثابت به نام `sid=s-alice` و فلگ `-mode vuln|fixed` (Go 1.27.3 روی macOS با معماری arm64؛ در `go.mod` خود دمو عدد 1.26 نوشته شده). دمو به‌طور پیش‌فرض روی `127.0.0.1:9100` گوش می‌دهد؛ من آن را روی یک پورت آزاد تصادفی اجرا کردم. «origin بیگانه» در اینجا فقط هدر `Origin` است که با `curl` می‌فرستم. **هیچ رفتار مرورگری را آزمایش نکردم**: هر ادعا درباره‌ی کار مرورگر از مشخصات یا MDN آمده و با احتیاط نوشته شده است.

## origin چیست و مرورگر چه چیزی را می‌بندد

**origin** سه‌تایی scheme، host و port است: `https://app.example.test` و `https://app.example.test:8443` دو origin متفاوت‌اند. **same-origin policy** مرورگر قاعده‌ای دارد که بسیاری را غافلگیر می‌کند: صفحه‌ای از یک origin می‌تواند به origin دیگر درخواست *بفرستد*، ولی نمی‌تواند جواب را *بخواند*. CORS برای شل‌کردن نیمه‌ی دوم است. سرور می‌تواند با هدرهای `Access-Control-Allow-*` بگوید «این origin دیگر اجازه دارد جواب‌های من را بخواند».

پس دو مشکل متفاوت قاطی می‌شوند:

- **خواندن** میان originها را CORS کنترل می‌کند. دشمن، صفحه‌ی مخربی است که داده‌ی خصوصی Alice را می‌خواند.
- **فرستادن** میان originها را CORS اصلاً نمی‌بندد. دشمن، صفحه‌ی مخربی است که مرورگر Alice را وادار به انجام کاری می‌کند. این همان CSRF است.

اول مورد دوم را روی نسخه‌ی آسیب‌پذیر نشان می‌دهم.

## CORS جلوی خود درخواست را نمی‌گیرد

یک `POST` با بدنه‌ی form همان چیزی است که مشخصات به آن «درخواست ساده» (simple request) می‌گویند: preflight ندارد و مرورگر همان لحظه آن را می‌فرستد (MDN متدهای `GET`، `HEAD`، `POST` و انواع محتوای `application/x-www-form-urlencoded`، `multipart/form-data` و `text/plain` را ساده می‌داند). در مرورگر واقعی کوکی فقط وقتی ضمیمه می‌شود که SameSite اجازه بدهد، و MDN می‌گوید بعضی مرورگرها کوکی بدون `SameSite` را به‌طور پیش‌فرض `Lax` حساب می‌کنند، پس حمله‌ی واقعی به این بستگی دارد. من آن را آزمایش نکردم. چیزی که می‌توانم نشان بدهم این است که وقتی چنین درخواستی می‌رسد، با هدر `Origin` از یک سایت بیگانه و کوکی Alice، سرور چه می‌کند:

```
$ curl -si -H 'Cookie: sid=s-alice' -H 'Origin: https://evil.test' -d amount=30 .../transfer
HTTP/1.1 200 OK
Access-Control-Allow-Credentials: true
Access-Control-Allow-Origin: https://evil.test
Vary: Origin
Content-Type: text/plain; charset=utf-8

{"balance":70}
```

(خط‌های `Date` و `Content-Length` را حذف کرده‌ام.) موجودی روی سرور از 100 به 70 رسید. نسخه‌ی آسیب‌پذیر origin بیگانه را هم در `Access-Control-Allow-Origin` بازتاب می‌دهد و credentials را مجاز می‌کند، که به آن صفحه اجازه می‌دهد جواب را هم بخواند. ولی حتی یک تنظیم کاملِ CORS هم جلوی خود انتقال را نمی‌گرفت: CORS دفاع در برابر CSRF نیست.

## درخواست preflight

اگر درخواست «ساده» نباشد، مثلاً بدنه‌ی JSON یا هدر سفارشی مثل `X-CSRF-Token` داشته باشد، مرورگر اول یک {{< term "preflight" "preflight" >}} می‌فرستد: یک درخواست `OPTIONS` که می‌پرسد «این را قبول می‌کنی؟». فقط اگر جواب اجازه بدهد درخواست واقعی می‌آید. middleware من از روی یک فهرست مجاز جواب می‌دهد. برای origin مجاز در نسخه‌ی اصلاح‌شده، جواب preflight این هدرهای CORS را دارد (جواب واقعی شش هدر امنیتیِ پایین‌تر را هم دارد که این‌جا نیاورده‌ام):

```
Access-Control-Allow-Credentials: true
Access-Control-Allow-Headers: Content-Type, X-CSRF-Token
Access-Control-Allow-Methods: GET, POST
Access-Control-Allow-Origin: https://app.example.test
Access-Control-Max-Age: 600
Vary: Origin
```

برای origin ناشناس (`https://evil.test`) و همین‌طور برای `null` جواب فقط `Vary: Origin` دارد و هیچ هدر `Access-Control-*` ندارد، پس مرورگر درخواست واقعی را نمی‌فرستد. `Vary: Origin` برای این است که جواب به هدر `Origin` بستگی دارد؛ بدون آن یک cache مشترک می‌تواند جواب یک origin را به origin دیگری بدهد. MDN می‌گوید سروری که یک origin واحدِ پویا را جواب می‌دهد باید `Vary: Origin` هم بفرستد.

## اشتباه‌های کلاسیک CORS

- **بازتاب هر `Origin` همراه با credentials.** نسخه‌ی آسیب‌پذیر بالا دقیقاً همین کار را می‌کند. یک صفحه‌ی مخرب می‌تواند پاسخ‌های احراز هویت‌شده را بخواند.
- **مجازکردن `null`.** در نسخه‌ی آسیب‌پذیر `Origin: null` جواب `Access-Control-Allow-Origin: null` و `Access-Control-Allow-Credentials: true` می‌گیرد. frameهای sandbox‌شده و بعضی redirectها می‌توانند `null` بفرستند، پس هویت هیچ‌کس نیست.
- **پیشوند یا regex خیلی شل.** تست دمو دو تطبیق‌دهنده را روی سه origin مقایسه می‌کند:

```
https://app.example.test                 bad=true  good=true
https://app.example.test.evil.test       bad=true  good=false
null                                     bad=false good=false
```

`bad` همان `strings.HasPrefix` است و `app.example.test.evil.test` را که مهاجم می‌تواند ثبت کند قبول می‌کند. `good` یک جست‌وجوی دقیق در map است. اگر ناچار به regex هستید با `^...$` لنگرش کنید؛ بهتر است اصلاً استفاده نکنید.

- **`*` همراه با کوکی.** MDN می‌گوید برای درخواستی که credentials دارد سرور نباید در `Access-Control-Allow-Origin` از `*` استفاده کند؛ باید origin را نام ببرد، وگرنه مرورگر جواب را مسدود می‌کند.

## دفاع در برابر CSRF، با نتیجه

حالا نسخه‌ی اصلاح‌شده. کوکی login حالا `SameSite=Lax` دارد (این خود هدر است؛ سمت مرورگر را آزمایش نکردم):

```
Set-Cookie: sid=s-alice; Path=/; HttpOnly; SameSite=Lax
```

`Lax` از مرورگر می‌خواهد کوکی را از بیشتر درخواست‌های بین‌سایتی کنار بگذارد، که فرم پنهان بالا را همین حالا هم می‌گیرد. این یک لایه است و سرور نباید فقط به آن تکیه کند. پس `/transfer` دو لایه‌ی دیگر دارد. اسکریپت دمو اول با `GET /csrf` یک توکن CSRF می‌گیرد و موجودی را می‌خواند (100). بعد پنج درخواست با curl می‌فرستد، همه با کوکی Alice:

```
Origin: https://evil.test                              -> 403 cross-site request refused
Origin: https://evil.test + valid token                -> 403 cross-site request refused
Sec-Fetch-Site: cross-site                             -> 403 cross-site request refused
Sec-Fetch-Site: same-origin, no token                  -> 403 bad csrf token
no Origin, no Sec-Fetch-Site, valid token              -> 403 cross-site request refused
```

بعد از هر پنج درخواست موجودی هنوز 100 بود. در پایان:

```
Sec-Fetch-Site: same-origin + valid token              -> 200 {"balance":70}
```

لایه‌ها یکی‌یکی:

1. **بررسی `Origin` و `Sec-Fetch-Site`.** مرورگر این هدرها را خودش اضافه می‌کند و اسکریپت صفحه نمی‌تواند عوضشان کند (در مشخصات Fetch این‌ها نام هدر ممنوع هستند). سرور درخواست را فقط وقتی قبول می‌کند که `Sec-Fetch-Site` برابر `same-origin` یا `none` باشد، یا اگر این هدر نبود، host در `Origin` با `Host` درخواست برابر باشد. درخواستی که هیچ‌کدام را ندارد رد می‌شود. برای همین پنجمی حتی با توکن معتبر شکست می‌خورد، و برای همین کلاینت‌های غیرمرورگری هم رد می‌شوند؛ پس یک API واقعی برای آن‌ها راه احراز هویت دیگری لازم دارد.
2. **توکن همگام (synchroniser token).** `GET /csrf` یک HMAC از شناسه‌ی نشست برمی‌گرداند (مقداری که صفحه‌ی مهاجم به‌خاطر same-origin policy نمی‌تواند بخواند) و `/transfer` آن را در فیلد form به نام `csrf` می‌خواهد. برای همین «same-origin بدون توکن» با `bad csrf token` شکست می‌خورد.
3. **کوکی double-submit**، برای endpoint به نام `/api/settings` که JSON می‌گیرد. سرور کوکی `csrf` را می‌گذارد و درخواست باید مقدار آن را در هدر `X-CSRF-Token` تکرار کند. صفحه‌ی بیگانه می‌تواند مرورگر را وادار کند کوکی را بفرستد، ولی نمی‌تواند آن را بخواند تا در هدر کپی کند. با کوکی ولی بدون هدر، یا با هدر غلط، `403 bad csrf token` گرفتم؛ با هدر مطابق، `200 {"saved":{"a":1}}`. اگر subdomainها قابل اعتماد نباشند ضعیف‌تر است، چون یک subdomain همسایه می‌تواند برای کل سایت کوکی بگذارد.

## هدرهای امنیتی

نسخه‌ی اصلاح‌شده شش هدر به هر پاسخ اضافه می‌کند. آن‌ها را با `curl -i` روی یک route عادی و روی یک 404 بررسی کردم:

| هدر | کار |
|---|---|
| `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'` | فقط منبع‌های هم‌origin بارگذاری شوند؛ قرار گرفتن صفحه در frame ممنوع |
| `Strict-Transport-Security: max-age=31536000; includeSubDomains` | {{< term "hsts" "HSTS" >}}: از این به بعد، یک سال، فقط HTTPS |
| `X-Content-Type-Options: nosniff` | نوع فایل را حدس نزن، به `Content-Type` اعتماد کن |
| `Referrer-Policy: strict-origin-when-cross-origin` | کمتر از URL را به سایت‌های دیگر بفرست |
| `Permissions-Policy: camera=(), microphone=(), geolocation=()` | این قابلیت‌های مرورگر را برای صفحه خاموش کن |
| `Cross-Origin-Opener-Policy: same-origin` | پنجره را از پنجره‌های بین‌originی که آن را باز کرده‌اند جدا نگه دار |

طبق RFC 6797 مرورگر باید HSTS را وقتی روی HTTP ساده می‌رسد نادیده بگیرد، پس در این دموی localhost هدر فقط نمایش داده می‌شود و روی HTTPS اهمیت پیدا می‌کند (مقاله‌ی بعد).

یک تست جلوی ناپدیدشدن هدرها را می‌گیرد. به هر route به‌علاوه‌ی یک مسیر ناشناس (همان 404) درخواست می‌فرستد و بررسی می‌کند هر شش هدر هست. `go test` پاس می‌شود. middleware دور کل mux است، پس پاسخ‌های خطا هم پوشش داده می‌شوند. خروجی تطبیق‌دهنده‌های بالا هم از همین اجرای `go test -v` است.

## لایه‌ها، نه یک راه‌حل واحد

- CORS کنترل می‌کند چه کسی بخواند، نه چه کسی بفرستد. درخواست‌های تغییردهنده‌ی وضعیت را با توکن یا بررسی origin محافظت کنید.
- originهای دقیق را در فهرست مجاز بگذارید، `Vary: Origin` بفرستید، origin درخواست را کورکورانه بازتاب ندهید و `null` را هرگز مجاز نکنید.
- فقط به `SameSite` تکیه نکنید؛ یک لایه است و پیش‌فرض مرورگرها فرق می‌کند.
- با `GET` وضعیت را تغییر ندهید. `Lax` هنوز اجازه می‌دهد کلیک روی لینک بین‌سایتی کوکی را با `GET` ببرد.
- هدرها دفاع در عمق هستند. XSS و نبود مجوزدهی را درست نمی‌کنند.

## تمرین

`/transfer` را طوری کنید که بدنه‌ی JSON با توکن در `X-CSRF-Token` بپذیرد، و تستی بنویسید که در آن `Origin` جعلی همراه با توکن معتبر باز هم 403 می‌گیرد.

## قدم بعدی

«TLS و گواهی x509 در عمل» اتصال زیر همه‌ی این‌ها را مستحکم می‌کند، و جایی است که HSTS بالاخره اثر می‌کند.
