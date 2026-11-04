+++
date = '2027-04-02T10:00:00+03:30'
draft = false
title = 'OAuth2 و OIDC'
description = 'OAuth2 و OIDC در Go روی localhost: جریان Authorization Code با PKCE، state، اعتبارسنجی ID token با JWKS، scope و چرخش refresh token، با خروجی واقعی.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "oauth2", "oidc", "pkce", "jwt", "go"]
cover = { image = "/images/covers/sec-oauth2-oidc.fa.png", alt = "OAuth2 و OIDC", hiddenInSingle = true }
+++

فرض کنید یک برنامه‌ی سفارش‌ها می‌خواهد سفارش‌های شما را از یک سرویس دیگر نشان بدهد. ساده‌ترین راه این است که نام کاربری و رمز عبور شما را بگیرد و به‌جای شما آنجا وارد شود. این کار جواب می‌دهد، ولی ایده‌ی بدی است: برنامه رمز کامل شما را دارد، هر کاری که شما می‌توانید بکنید او هم می‌تواند، و تنها راه گرفتن دسترسی‌اش عوض‌کردن رمز خودتان است. دکمه‌های «ورود با X» برای همین ساخته شده‌اند. برنامه هیچ‌وقت رمز شما را نمی‌بیند؛ به‌جایش یک توکن کوچک، محدود و قابل‌ابطال می‌گیرد.

پروتکل پشت این کار {{< term "oauth2" "OAuth2" >}} است. ایده‌اش در یک جمله: کاربر خودش را به سروری که از قبل به آن اعتماد دارد ثابت می‌کند، و آن سرور به برنامه توکنی می‌دهد که می‌گوید «این برنامه برای این کاربر فقط این کارهای مشخص را می‌تواند بکند». OAuth2 درباره‌ی **مجوزدهی** (authorization) است، یعنی اینکه توکن چه کاری می‌تواند بکند. نمی‌گوید چه کسی وارد شده. {{< term "oidc" "OpenID Connect" >}} (به اختصار OIDC) لایه‌ی نازکی روی آن است که تکه‌ی گم‌شده را اضافه می‌کند: یک **ID token** که به برنامه می‌گوید چه کسی وارد شده. این **احراز هویت** (authentication) است.

مقاله‌ی قبل، [session یا JWT؟](/fa/posts/sec-sessions-vs-jwt/)، درباره‌ی چیزی بود که سرور بعد از login نگه می‌دارد. این مقاله درباره‌ی این است که وقتی سرور خودتان نیست، login را چه کسی انجام می‌دهد. کل جریان را روی یک پیاده‌سازی اسباب‌بازی قدم‌به‌قدم می‌روم و در هر مرحله هم رفتار درست را نشان می‌دهم و هم یک درخواست غلط را. API آخر کار همان ایده‌ی API سفارش‌هاست از [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/).

> فقط دفاعی. همه‌چیز روی `127.0.0.1` در یک برنامه‌ی Go اجرا شد (Go 1.27.3 روی macOS با معماری arm64، فقط کتابخانه‌ی استاندارد؛ در `go.mod` خود دمو عدد 1.26 نوشته شده): یک authorization server، یک resource server و یک کلاینت. توکن‌ها {{< term "jwt" "JWT" >}} با RS256 هستند که خودم با `crypto/rsa` امضا کردم. هیچ identity provider واقعی، مرورگر یا حساب شخص ثالثی در کار نبود. «کاربر» از قبل وارد شده و خودکار موافقت می‌کند، و callback کلاینت به‌جای listener واقعی یک پاسخ `302` چاپ‌شده است. مقدارهای تصادفی (state، nonce، codeها، توکن‌ها و challenge مربوط به PKCE) در هر اجرا فرق می‌کنند؛ خروجی‌های زیر همه از یک اجرا هستند.

## نقش‌ها

در هر داستان OAuth2 چهار نقش هست و بهتر است پیش از هر کدی اسمشان را بدانیم:

- **کاربر** (صاحب داده): داده مال اوست، اینجا Alice و سفارش‌هایش.
- **کلاینت**: برنامه‌ای که دسترسی می‌خواهد، اینجا `orders-web`.
- **authorization server**: Alice را می‌شناسد، login او را بررسی می‌کند و توکن صادر می‌کند.
- **resource server**: همان API که سفارش‌ها را نگه می‌دارد و توکن می‌پذیرد.

جریانی که استفاده می‌کنیم {{< term "authorization-code-flow" "جریان Authorization Code" >}} است. کلاینت مرورگر Alice را به authorization server می‌فرستد. Alice آنجا وارد می‌شود. authorization server مرورگر را با یک **code** کوتاه‌عمر به کلاینت برمی‌گرداند. بعد کلاینت، مستقیم و نه از راه مرورگر، آن code را با توکن‌ها عوض می‌کند. مرورگر فقط code حمل می‌کند، هرگز توکن. این مهم است، چون URLها در تاریخچه‌ی مرورگر و لاگ‌ها می‌مانند، ولی عوض‌کردن code روی یک اتصال مستقیم انجام می‌شود.

## قدم اول: درخواست مجوز

اول کلاینت مرورگر را با یک فهرست پارامتر به `/authorize` می‌فرستد. دمو آن‌ها را یکی‌یکی چاپ می‌کند:

```
  response_type          code
  client_id              orders-web
  redirect_uri           http://127.0.0.1:5555/callback
  scope                  openid profile orders:read
  state                  y7FOdbYUeHr2wiig
  nonce                  ClK8-HVEFlLlrCsJ
  code_challenge         w-6XYQt_NIcmO5PWi7-2y1Tprfe31qIFJ7Gzze-LM4c
  code_challenge_method  S256
```

معنی هرکدام:

- `response_type=code` یعنی «جریان code را می‌خواهم».
- `client_id` می‌گوید کدام برنامه درخواست می‌دهد.
- `redirect_uri` جایی است که مرورگر باید به آن برگردد. سرور باید این نشانی را از قبل بداند و دقیقاً مقایسه کند. اگر مقایسه شل باشد، یک لینک ساختگی می‌تواند code را به نشانی دیگری بفرستد. (در دمو روی پورت 5555 هیچ‌چیز گوش نمی‌دهد؛ فقط redirect را می‌خوانیم.)
- `scope` فهرست چیزهایی است که کلاینت می‌خواهد. `orders:read` یعنی «خواندن سفارش‌ها». `openid` کلمه‌ای است که این را به login از نوع OIDC تبدیل می‌کند و ID token می‌دهد. `profile` اطلاعات پایه‌ی پروفایل را می‌خواهد.
- `state` مقدار تصادفی‌ای است که کلاینت می‌سازد و انتظار دارد بدون تغییر پس بگیرد. پایین‌تر توضیح می‌دهم.
- `nonce` یک مقدار تصادفی دیگر است که سرور آن را داخل ID token می‌گذارد. این هم پایین‌تر.
- `code_challenge` و `code_challenge_method` مال {{< term "pkce" "PKCE" >}} هستند، آن هم پایین‌تر.

سرور دموی من PKCE با `S256` را اجباری کرده و درخواست بدون آن را رد می‌کند. این انتخاب همین دموست؛ RFC 9700 (بهترین رویه‌ی فعلی امنیت OAuth 2.0) می‌گوید کلاینت‌های عمومی باید از PKCE استفاده کنند و authorization serverها باید از آن پشتیبانی کنند.

## قدم دوم: بازگشت به کلاینت و کار state

authorization server با یک redirect به `redirect_uri` کلاینت جواب می‌دهد، با یک code کوتاه‌عمر و همان `state`:

```
302 Location: http://127.0.0.1:5555/callback?code=HS3Ow0BUavIsfJqRHr7bpQ&state=y7FOdbYUeHr2wiig
state matches what we sent: true
callback with state=attacker-chosen accepted: false -> client drops it, never exchanges the code
```

`302` یعنی redirect: مرورگر به نشانی `Location` می‌رود. حالا پرسش این است که کلاینت اصلاً چرا `state` لازم دارد. مهاجمی را تصور کنید که با حساب خودش یک جریان login را شروع می‌کند، در مرحله‌ی callback می‌ایستد و مرورگر شما را فریب می‌دهد که همان لینک callback را باز کند. اگر کلاینت چیزی را بررسی نکند، جریان را تمام می‌کند و حساب مهاجم را به نشست شما وصل می‌کند. این یک {{< term "csrf" "CSRF" >}} روی login است: درخواستی که مرورگر شما فرستاده بی‌آنکه شما بخواهید. درمانش ساده است. کلاینت `state`ای را که فرستاده در همین مرورگر نگه می‌دارد و با `state` روی callback مقایسه می‌کند. اگر فرق داشت، callback را دور می‌اندازد و هرگز از code استفاده نمی‌کند.

خط آخر این خروجی در دموی من یک مقایسه‌ی ساده‌ی رشته‌ای است، نه یک درخواست جعلی از مرورگر واقعی. RFC 9700 می‌گوید کلاینت‌ها باید در برابر CSRF دفاع کنند، یا با PKCE یا با توکن‌های یک‌بارمصرف در `state`.

## قدم سوم: PKCE و code دزدیده‌شده

code فقط یک بلیت کوتاه‌عمر است، ولی فرض کنید به هر دلیلی نشت کرده: در یک لاگ مانده یا یک برنامه‌ی مخرب روی همان دستگاه redirect را دیده. PKCE (Proof Key for Code Exchange) کاری می‌کند که code نشت‌کرده به درد نخورد.

قبل از شروع جریان، کلاینت یک راز تصادفی می‌سازد به اسم **verifier**. در قدم اول فقط یک اثر انگشت از آن فرستاد، یعنی **challenge** که برابر است با `base64url(sha256(verifier))`. وقتی کلاینت بعداً code را با توکن عوض می‌کند، خود verifier را می‌فرستد. سرور آن را hash می‌کند و با challenge ذخیره‌شده مقایسه می‌کند. کسی که فقط code را دزدیده verifier ندارد و از روی challenge هم نمی‌تواند آن را حدس بزند.

اول محاسبه‌ی challenge را با مثال عددی RFC 7636 (مشخصات PKCE) مقایسه کردم:

```
verifier   dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
challenge  E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM  matches RFC example: true
```

بعد دمو با code قدم دوم اول نقش دزد را بازی می‌کند و بعد نقش صاحب واقعی را:

```
thief, wrong verifier: 400 invalid_grant - PKCE verification failed
owner, right verifier, after the failed try: 400 invalid_grant - unknown or already used code
```

دزد `400 invalid_grant` می‌گیرد چون verifier نمی‌خواند. خط دوم یک انتخاب طراحی سرور من را نشان می‌دهد: با هر تلاش ناموفق code را می‌سوزاند، پس صاحب واقعی باید جریان تازه‌ای شروع کند. code در هر حال یک‌بارمصرف است؛ استاندارد استفاده‌ی دوباره را ممنوع می‌کند و اینکه بعد از یک تلاش ناموفق چه شود به سرور بستگی دارد.

یک قاعده‌ی دیگر هم از اینجا می‌آید: راز را هرگز در URL نگذارید. code در URL قابل تحمل است چون کوتاه‌عمر است و تنها بی‌فایده. اما توکن یا verifier در URL به لاگ و تاریخچه می‌رسد.

## قدم چهارم: عوض‌کردن code با توکن

حالا یک درخواست مجوز تازه و تبادل واقعی. کلاینت code و verifier را مستقیم به `/token` می‌فرستد:

```
POST /token  grant_type=authorization_code code=yXGZdohLuZIlVIoPUqNjPg code_verifier=FrJZv68hLfzPElLjh4kQ...kTjnpQ
status 200
  token_type     Bearer
  expires_in     300
  scope          openid profile orders:read
  access_token   eyJhbGciOiJSUzI1NiIs...9X62Dw
  id_token       eyJhbGciOiJSUzI1NiIs...AyfO-Q
  refresh_token  _IAdvsu67RynDgwo
code reuse: 400 unknown or already used code
```

دمو توکن‌های بلند را کوتاه کرده است. پاسخ سه توکن دارد که هرکدام کار جدایی دارد:

- **access token** چیزی است که کلاینت به API نشان می‌دهد. ۳۰۰ ثانیه عمر دارد (`expires_in`)، عمداً کوتاه.
- **ID token** فقط برای خود کلاینت است و می‌گوید چه کسی وارد شده. چون scope `openid` را خواسته‌ایم آمده است.
- **refresh token** به کلاینت اجازه می‌دهد بعداً بدون اینکه Alice دوباره login کند access token تازه بگیرد.

خط آخر نشان می‌دهد استفاده‌ی دوباره از همان code شکست می‌خورد.

## قدم پنجم: اعتبارسنجی ID token

ID token یک JWT است: سه بخش base64url به نام header، payload و امضا. payload فقط encode شده، رمز نشده؛ پس هرکسی می‌تواند آن را بخواند. چیزی که آن را قابل‌اعتماد می‌کند امضا و بررسی‌هایی است که کلاینت انجام می‌دهد. کلاینت کلید عمومی authorization server را از `/jwks.json` می‌گیرد ({{< term "jwks" "JWKS" >}}، یک فهرست JSON از کلیدهای عمومی)، امضا را بررسی می‌کند و بعد claimها را:

- `iss`: صادرکننده همان authorization server مورد انتظار من است.
- `aud`: مخاطب همان `client_id` خود من است، یعنی توکن برای من ساخته شده.
- `exp`: توکن منقضی نشده.
- `nonce`: با مقداری که در قدم اول فرستادم برابر است. این ID token را به همین تلاش login گره می‌زند، پس توکن قدیمی را نمی‌شود در login جدید دوباره پخش کرد.

دمو یک توکن سالم و شش توکن خراب به این بررسی می‌دهد:

```
good               OK sub=alice name=Alice
wrong nonce        REJECT nonce
tampered payload   REJECT bad signature
other signing key  REJECT bad signature
wrong aud          REJECT aud=another-app
expired            REJECT expired
alg=none token: alg not allowed: none
```

خط‌به‌خط: توکن سالم قبول می‌شود و `sub=alice` را می‌دهد، یعنی شناسه‌ی پایدار کاربر. nonce اشتباه رد می‌شود. توکنی که payload آن دست‌کاری شده دیگر با امضایش نمی‌خواند. توکنی که با کلید دیگری امضا شده با کلید منتشرشده نمی‌خواند. توکنی که برای `another-app` ساخته شده رد می‌شود چون `aud` مال ما نیست. توکن منقضی رد می‌شود. خط آخر توکنی است که header آن `alg: none` دارد، یعنی «امضا لازم نیست». بررسی‌کننده هرگز الگوریتمی را که خود توکن اعلام می‌کند باور نمی‌کند. فهرست مجاز ثابتی دارد (فقط RS256) و بقیه را رد می‌کند.

## قدم ششم: صدازدن API

حالا کلاینت access token را به‌عنوان {{< term "bearer-token" "bearer token" >}} به کار می‌برد، یعنی هرکس آن را داشته باشد می‌تواند استفاده‌اش کند، و آن را در هدر `Authorization: Bearer ...` می‌فرستد:

```
GET  /orders, no token      -> 401 missing bearer token
GET  /orders, Bearer        -> 200 ok GET /orders for sub=alice
POST /orders, Bearer        -> 403 insufficient_scope: need orders:write
GET  /orders, ID token      -> 401 bad iss/aud/exp
GET  /userinfo, Bearer      -> 200 {"name":"Alice","sub":"alice"}
```

بدون توکن `401` می‌گیریم. توکنی که `orders:read` دارد می‌تواند بخواند. ساختن سفارش `orders:write` می‌خواهد که Alice هرگز نداده، پس جواب `403` است. خط چهارم مهم‌ترین است: ID token خود کلاینت را API رد می‌کند، چون `aud` آن کلاینت است نه API سفارش‌ها. ID token اثبات login برای کلاینت است، نه اعتبارنامه‌ای برای API. خط آخر endpoint به نام `userinfo` در OIDC است که با یک access token پروفایل را برمی‌گرداند.

**scope** چیزی است که کاربر به این کلاینت اجازه داده. **role** چیزی است که کاربر اصلاً در سیستم شما حق دارد. درخواست باید از هر دو رد شود. مقاله‌ی بعد درباره‌ی roleها و بررسی‌های داخل API است.

## قدم هفتم: چرخش refresh token

{{< term "refresh-token" "refresh token" >}} عمر طولانی دارد، پس هدف وسوسه‌انگیزی است. دفاع رایج این است که آن را بچرخانیم: هر استفاده یک refresh token تازه می‌دهد و قدیمی را باطل می‌کند.

```
use rt1: 200 new refresh token: 2LvNOnObhmBiCR6D differs: true
use rt1 again: 400 refresh token reuse detected, family revoked
use rt2 (same family): 400 family revoked
```

استفاده‌ی اول کار می‌کند و توکن تازه‌ای (`rt2`) می‌دهد. استفاده‌ی دوباره از `rt1` مشکوک است: یا دزد یک نسخه‌ی کهنه دارد یا صاحب واقعی، و سرور نمی‌تواند تشخیص بدهد کدام. پس کل **خانواده** را باطل می‌کند، یعنی همه‌ی توکن‌هایی که از همین login آمده‌اند، و خط آخر نشان می‌دهد حتی `rt2` تازه هم دیگر کار نمی‌کند. کاربر واقعی باید دوباره login کند که هزینه‌ی کوچکی است. RFC 9700 می‌گوید refresh tokenهای کلاینت‌های عمومی باید به فرستنده مقید شوند (sender-constrained) یا بچرخند.

## جایی که پیاده‌سازی OAuth خراب می‌شود

- **مقایسه‌ی شل `redirect_uri`.** تطبیق پیشوندی یا wildcard به مهاجم اجازه می‌دهد code را به نشانی خودش بفرستد. RFC 9700 می‌گوید سرور باید از تطبیق دقیق رشته استفاده کند.
- **grantهای نادرست.** طبق RFC 9700 کلاینت‌ها نباید از Implicit grant استفاده کنند (توکن را در URL برمی‌گرداند) و Resource Owner Password Credentials grant، که در آن خود برنامه رمز را می‌گیرد، اصلاً نباید استفاده شود. از جریان code با PKCE استفاده کنید. هیچ‌کدام از آن دو جریان را اجرا نکردم.
- **قاطی‌کردن توکن‌ها.** ID token را اعتبارنامه‌ی API نکنید و access token را مدرک اینکه کسی همین الان login کرده ندانید.
- **access token طولانی‌مدت.** آن را کوتاه نگه دارید و بیرون از این دموی loopback همه‌جا HTTPS داشته باشید. بدون HTTPS هر کسی روی مسیر می‌تواند code و توکن‌ها را بخواند.
- **لاگ‌کردن توکن.** توکن‌ها و URL کامل callback را لاگ نکنید.
- **چیزی که دمو ندارد.** صفحه‌ی واقعی login و رضایت، client secret و مرورگر واقعی در کار نبود. فقط قواعد سمت سرور را نشان دادم.

## تمرین

ابطال توکن اضافه کنید: endpointای به نام `/revoke` که خانواده‌ی یک refresh token را باطل می‌کند، و تستی که نشان دهد refresh بعدی شکست می‌خورد.

## قدم بعدی

«مجوزدهی: RBAC و IDOR» بعد از این می‌آید، چون توکن معتبر فقط می‌گوید فراخواننده کیست. اینکه او با هر شیء چه کاری می‌تواند بکند هنوز تصمیم سرور است.
