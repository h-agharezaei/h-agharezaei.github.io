+++
date = '2027-04-02T10:00:00+03:30'
draft = false
title = 'OAuth2 و OIDC'
description = 'OAuth2 و OIDC در Go روی localhost: جریان Authorization Code با PKCE، state، اعتبارسنجی ID token با JWKS، scope و چرخش refresh token، با خروجی واقعی.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "oauth2", "oidc", "pkce", "jwt", "go"]
cover = { image = "/images/covers/sec-oauth2-oidc.fa.png", alt = "OAuth2 و OIDC", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [session یا JWT؟](/fa/posts/sec-sessions-vs-jwt/)، درباره‌ی چیزی بود که سرور بعد از login نگه می‌دارد. اینجا پرسش این است که login را چه کسی انجام می‌دهد. «ورود با X» و «به این برنامه اجازه بده سفارش‌هایم را بخواند» هر دو {{< term "oauth2" "OAuth2" >}} و {{< term "oidc" "OpenID Connect" >}} هستند. خلاصه: OAuth2 **مجوزدهی** (authorization) است، یعنی این توکن چه کاری می‌تواند بکند، و OIDC با ID token **احراز هویت** (authentication) را اضافه می‌کند، یعنی چه کسی وارد شده. API سمت منبع همان API سفارش‌هاست از [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/).

> فقط دفاعی. همه‌چیز روی `127.0.0.1` در یک برنامه‌ی Go 1.26 فقط با کتابخانه‌ی استاندارد اجرا شد: یک authorization server، یک resource server و یک کلاینت. توکن‌ها JWT با RS256 هستند که خودم با `crypto/rsa` امضا کردم. هیچ identity provider واقعی، مرورگر یا حساب شخص ثالثی در کار نبود. «کاربر» از قبل وارد شده و خودکار موافقت می‌کند و callback کلاینت یک 302 چاپ‌شده است، نه listener واقعی. دمویی جداست.

## جریان Authorization Code با PKCE

کلاینت مرورگر را به `/authorize` می‌فرستد. challenge مربوط به {{< term "pkce" "PKCE" >}} را با `base64url(sha256(verifier))` حساب کردم و با مثال RFC 7636 مقایسه کردم:

```
verifier   dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
challenge  E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM  matches RFC example: true
```

درخواست واقعی، پارامتر به پارامتر:

```
  response_type          code
  client_id              orders-web
  redirect_uri           http://127.0.0.1:5555/callback
  scope                  openid profile orders:read
  state                  p84e_dRe79Q8wp1b
  nonce                  NL5oWAIUD41i8noq
  code_challenge         1ISr_nQK-v-0F1yoMU-Gn9D1j-j-l8_I6Ro1EJTgn1g
  code_challenge_method  S256
```

سرور با یک redirect جواب می‌دهد که یک code کوتاه‌عمر و همان state را دارد. این همان {{< term "authorization-code-flow" "جریان Authorization Code" >}} است: مرورگر فقط code حمل می‌کند، هرگز توکن.

```
302 Location: http://127.0.0.1:5555/callback?code=Zz-fQ1CTqGbvgNXeaY2f7g&state=p84e_dRe79Q8wp1b
```

## state از چه جلوگیری می‌کند

`state` callback را به درخواستی گره می‌زند که همین مرورگر شروع کرده. بدون آن مهاجم می‌تواند مرورگر شما را وادار کند جریانی را تمام کند که خودش شروع کرده؛ این یک {{< term "csrf" "CSRF" >}} روی login است. کلاینت مقایسه می‌کند و قبل از استفاده از code، ناهمخوانی را دور می‌اندازد:

```
state matches what we sent: true
callback with state=attacker-chosen accepted: false -> client drops it, never exchanges the code
```

خط دوم در دموی من یک مقایسه‌ی ساده است، نه درخواست جعلی واقعی از یک مرورگر.

## PKCE از چه جلوگیری می‌کند

فرض کنید code نشت کند (لاگ، یک برنامه‌ی مخرب روی همان دستگاه). بدون verifier بی‌فایده است:

```
thief, wrong verifier: 400 invalid_grant - PKCE verification failed
owner, right verifier, after the failed try: 400 invalid_grant - unknown or already used code
```

سرور من code را با هر تلاش ناموفق می‌سوزاند، پس صاحب باید از اول شروع کند. این یک انتخاب طراحی است؛ code در هر حال یک‌بارمصرف است. راز را هرگز در URL نگذارید: code کوتاه‌عمر است و تنها بی‌فایده، اما توکن یا verifier در URL به لاگ و تاریخچه می‌رسد.

## توکن‌ها و اعتبارسنجی ID token

```
POST /token  grant_type=authorization_code code=n9yU0uooh8YRQbKfml7Wew code_verifier=W4gzTNnQL1wPyM6MGnLo...y9dRAQ
  token_type     Bearer
  expires_in     300
  scope          openid profile orders:read
  access_token   eyJhbGciOiJSUzI1NiIs...kneOSA
  id_token       eyJhbGciOiJSUzI1NiIs...gnMBVA
  refresh_token  v7QR2NLJy8l4-0tw
```

کلاینت کلید عمومی را از `/jwks.json` ({{< term "jwks" "JWKS" >}}) می‌گیرد و امضا را بررسی می‌کند، سپس `iss`، `aud` (باید `client_id` من باشد)، `exp` و `nonce`:

```
good               OK sub=alice name=Alice
wrong nonce        REJECT nonce
tampered payload   REJECT bad signature
other signing key  REJECT bad signature
wrong aud          REJECT aud=another-app
expired            REJECT expired
alg=none token:    alg not allowed: none
```

هرگز الگوریتمی را که خود توکن می‌خواهد نپذیرید؛ فهرست مجاز ثابت داشته باشید. payload یک {{< term "jwt" "JWT" >}} فقط encode شده است، پس همین بررسی‌ها آن را قابل اعتماد می‌کنند.

## access token، scope و role

کلاینت API را با {{< term "bearer-token" "bearer token" >}} صدا می‌زند:

```
GET  /orders, no token      -> 401 missing bearer token
GET  /orders, Bearer        -> 200 ok GET /orders for sub=alice
POST /orders, Bearer        -> 403 insufficient_scope: need orders:write
GET  /orders, ID token      -> 401 bad iss/aud/exp
```

**scope** چیزی است که کاربر به این کلاینت اجازه داده؛ **role** چیزی است که کاربر در سیستم شما حق دارد. درخواست به هر دو نیاز دارد. ID token برای کلاینت است، نه API: API آن را رد می‌کند چون `aud` درست نیست. roleها در مقاله‌ی بعد می‌آیند.

## چرخش refresh token

{{< term "refresh-token" "refresh token" >}} بلندمدت است، پس هر استفاده یکی تازه می‌دهد و قبلی را می‌کشد:

```
use rt1: 200 new refresh token: QdxTjk6f54VwJgIb differs: true
use rt1 again: 400 refresh token reuse detected, family revoked
use rt2 (same family): 400 family revoked
```

اگر توکن قدیمی دوباره ظاهر شود، یا دزد از آن استفاده می‌کند یا صاحب، پس سرور کل خانواده را باطل می‌کند.

## چند نکته‌ی مهم

- `redirect_uri` را در سرور دقیقاً مطابقت دهید؛ تطبیق پیشوندی یا wildcard زمینه‌ی open-redirect می‌سازد.
- طبق RFC 9700 (بهترین رویه‌ی فعلی امنیت OAuth 2.0، که برای این دو نکته بررسی‌اش کردم) کلاینت‌ها نباید از Implicit grant استفاده کنند و Resource Owner Password Credentials grant نباید استفاده شود. از جریان code با PKCE استفاده کنید. هیچ‌کدام از این دو جریان ناپسند را اجرا نکردم.
- ID token را اعتبارنامه‌ی API نکنید و access token را مدرک login ندانید.
- access tokenها را کوتاه نگه دارید؛ بیرون از این دموی loopback همه‌جا HTTPS.
- توکن‌ها و URL کامل callback را لاگ نکنید.

## تمرین

ابطال توکن اضافه کنید: endpoint به نام `/revoke` که خانواده‌ی یک refresh token را باطل می‌کند، و تستی که نشان دهد refresh بعدی شکست می‌خورد.

## قدم بعدی

مقاله‌ی بعدی «مجوزدهی: RBAC و IDOR» است.
