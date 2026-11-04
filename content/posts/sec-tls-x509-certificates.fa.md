+++
date = '2027-04-24T10:00:00+03:30'
draft = false
title = 'TLS و گواهی x509 در عمل'
description = 'TLS و گواهی x509 در Go روی loopback: خطاهای verify، زنجیره، چرخش با GetCertificate، mutual TLS، بررسی انقضا و pinning با خروجی واقعی.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "tls", "x509", "certificates", "mtls", "go"]
cover = { image = "/images/covers/sec-tls-x509-certificates.fa.png", alt = "TLS و گواهی x509 در عمل", hiddenInSingle = true }
+++

یک سرویس را deploy می‌کنید، یک کلاینت Go را به آن وصل می‌کنید و این خطا را می‌گیرید:

```
x509: certificate signed by unknown authority
```

برداشت اول این است که «کلاینت به مرجع صدور گواهی این سرور اعتماد ندارد». گاهی درست است. ولی همین پیام وقتی هم می‌آید که به مرجع کاملاً اعتماد دارید و سرور فقط یک فایل را فراموش کرده بفرستد. وقتی دو مشکل متفاوت یک خطا چاپ می‌کنند، باید بدانید کلاینت واقعاً چه چیزهایی را بررسی می‌کند. موضوع این مقاله همین است.

[CSRF، CORS و هدرهای امنیتی](/fa/posts/sec-csrf-cors-headers/) کاری را که مرورگر با یک صفحه می‌کند مستحکم کرد. این‌جا لوله‌ی زیرش را مستحکم می‌کنیم. [TLS و گواهی‌ها با openssl](/fa/posts/net-tls-openssl/) خط فرمان `openssl` را پوشش داد، با همین بررسی‌ها از بیرون؛ این مقاله سمت Go و عملیات است: داخل یک {{< term "x509-certificate" "گواهی x509" >}} چه هست، چرا تأیید شکست می‌خورد، چطور گواهی را بدون restart عوض کنیم و چطور پیش از انقضا بفهمیم. سرور از نوع همان API در [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) است.

> فقط دفاعی. همه‌چیز روی `127.0.0.1` در یک برنامه‌ی Go فقط با کتابخانه‌ی استاندارد اجرا شد (Go 1.27.3 روی macOS با معماری arm64؛ در `go.mod` خود دمو عدد 1.26 نوشته شده). {{< term "certificate-authority" "مرجع صدور گواهی" >}} (CA) یک‌بارمصرف خودم را با کلیدهای ECDSA P-256 در کد ساختم؛ CA عمومی در کار نیست. کلید خصوصی هرگز روی دیسک نیامد (تنها سروری که فایل می‌نویسد فقط گواهی CA خودش را می‌نویسد). ACME، OCSP و Certificate Transparency فقط توضیح داده شده‌اند، اجرا نشده‌اند. زمان‌های خروجی ساعت محلی من است و بخش‌های تصادفی (شماره‌ی پورت‌ها، hash پین‌ها) در هر اجرا عوض می‌شوند.

## کلاینت چه چیزهایی را بررسی می‌کند

گواهی یک بیانیه‌ی امضاشده است: «این کلید عمومی مال این نام است، در این بازه‌ی زمانی». امضاکننده **issuer** نام دارد. وقتی کلاینت وصل می‌شود، سرور گواهی خودش را، یعنی **leaf** را، می‌فرستد و ثابت می‌کند کلید خصوصی متناظر را دارد. بعد کلاینت چهار پرسش می‌پرسد:

1. آیا leaf را کسی امضا کرده که به او اعتماد دارم؟ امضا باید از راه یک **زنجیره** (leaf، بعد CAهای میانی، بعد یک **root**) به یک گواهی root در مجموعه‌ی مورد اعتماد کلاینت برسد.
2. آیا نامی که به آن وصل شدم در گواهی هست؟ نام‌ها در فهرست {{< term "subject-alt-name" "SubjectAltName" >}} (به اختصار SAN) هستند.
3. آیا امروز داخل بازه‌ی اعتبار است؟
4. آیا گواهی اجازه دارد این‌طور استفاده شود؟ extended key usage (`serverAuth`، `clientAuth`) می‌گوید برای چه کاری است.

تابع `Verify` در Go دقیقاً همین‌ها را می‌پرسد. بقیه‌ی مقاله هرکدام را عمداً خراب می‌کند.

## داخل یک گواهی چه هست

دمو CA و یک leaf را با `x509.CreateCertificate` می‌سازد، بعد leaf را parse می‌کند و فیلدهایش را چاپ می‌کند:

```
subject     CN=orders.local,O=Demo
issuer      CN=Demo Root CA,O=Demo
serial      ...3c4d
dns SANs    [orders.local localhost]
ip SANs     [127.0.0.1]
valid for   25h0m0s
IsCA        false  basicConstraintsValid true
KeyUsage    1 (DigitalSignature=true, CertSign=false)
ExtKeyUsage [serverAuth]
sig alg     ECDSA-SHA256
```

`subject` گواهی برای چه کسی است و `issuer` همان CAای است که امضایش کرده. دمو فقط چند رقم آخر serial را چاپ می‌کند. دو خط SAN چیزی است که کلاینت نام‌ها را با آن مقایسه می‌کند، پس هر نام DNS و هر IP را آنجا بگذارید. `valid for` از یک ساعت قبل تا ۲۴ ساعت بعد است. `IsCA false` و `CertSign=false` می‌گویند این گواهی نمی‌تواند گواهی دیگری را امضا کند، و `ExtKeyUsage [serverAuth]` می‌گوید برای سرور است. گواهی CA که بلافاصله بعد از آن چاپ می‌شود `IsCA true` و `CertSign=true` دارد.

## خطاها، واقعی

حالا همان `Verify` با یک مجموعه‌ی root، یک نام و کاربرد `serverAuth`، روی یک leaf سالم و شش تنظیم خراب:

```
good               ok
unknown authority  x509: certificate signed by unknown authority
hostname mismatch  x509: certificate is valid for orders.local, localhost, not payments.local
expired            x509: certificate has expired or is not yet valid: current time 2026-11-04T21:05:27+03:30 is after 2026-11-03T17:35:27Z
not yet valid      x509: certificate has expired or is not yet valid: current time 2026-11-04T21:05:27+03:30 is before 2026-11-05T17:35:27Z
wrong ExtKeyUsage  x509: certificate specifies an incompatible key usage
no intermediate    x509: certificate signed by unknown authority
with intermediate  ok
```

خط‌به‌خط:

- **unknown authority**: با مجموعه‌ی rootی تأیید می‌کنم که CA دیگری در آن است. leaf به هیچ چیزی که کلاینت به آن اعتماد دارد نمی‌رسد.
- **hostname mismatch**: leaf سالم است، ولی من `payments.local` را خواستم، و خطا حتی نام‌هایی را که گواهی برایشان معتبر است فهرست می‌کند. از میان این خطاها مفیدترین پیام همین است.
- **expired** و **not yet valid**: متن خطا یکی است، با زمان کنونی و مرز بازه. ساعت اشتباه روی یک گواهی کاملاً سالم دومی را می‌دهد.
- **wrong ExtKeyUsage**: این leaf برای `clientAuth` صادر شده بود و من `serverAuth` خواستم.
- **no intermediate** و **with intermediate**: این‌جا leaf را یک CA میانی امضا کرده و آن میانی را root. اگر کلاینت فقط root را داشته باشد نمی‌تواند این دو را به هم وصل کند و می‌گوید «unknown authority»، همان متن خط اول. میانی را به آن بدهید تا زنجیره بسته شود.

## زنجیره روی یک اتصال واقعی

خط «no intermediate» همان است که در عمل گیج‌کننده می‌شود، پس آن را روی یک اتصال واقعی نشان می‌دهم. leaf از CA میانی صادر شده. اول سروری که فقط leaf را می‌فرستد. کلاینت Go می‌گوید:

```
leaf only      -> Get "https://127.0.0.1:55975/": tls: failed to verify certificate: x509: certificate signed by unknown authority
```

بعد سروری که leaf و میانی را با `tls.Certificate{Certificate: [][]byte{leaf, intermediate}}` می‌فرستد (در دمو `l2.TLS(inter)` همین را می‌سازد):

```
leaf+inter     -> hello <nil> chain length seen by client: 2
```

درخواست `hello` برمی‌گرداند و کلاینت زنجیره‌ای به طول ۲ می‌بیند. پس سرور باید میانی‌ها را بفرستد (نه root را؛ کلاینت آن را از قبل دارد). در آزمایش من کلاینت Go میانیِ گم‌شده را خودش نگرفت. مرورگر ممکن است فرق داشته باشد، و یکی از دلایلی که زنجیره‌ی خراب یک‌جا سالم به نظر می‌رسد و جای دیگر شکست می‌خورد همین است.

## نسخه‌ها و cipher suiteها

بررسی بعدی نسخه‌ی TLS است. سرور `MinVersion: tls.VersionTLS12` دارد و من حداکثر نسخه‌ی کلاینت را عوض می‌کنم. `resp.TLS` نشان می‌دهد چه چیزی توافق شد:

```
client max TLS 1.2 -> TLS 1.2, TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256, body="hello"
client max TLS 1.3 -> TLS 1.3, TLS_AES_128_GCM_SHA256, body="hello"
client max TLS 1.1 -> Get "https://127.0.0.1:55971/": tls: no supported versions satisfy MinVersion and MaxVersion
```

دو خط اول همان چیزی را توافق می‌کنند که کلاینت اجازه می‌دهد. خط سوم را با دقت بخوانید. این کلاینت است که امتناع می‌کند: کلاینت Go با `MaxVersion` برابر 1.1 با حداقل پیش‌فرض خودش (TLS 1.2) تناقض دارد، پس اصلاً اتصالی شروع نمی‌شود. این نشان نمی‌دهد سرور کلاینت قدیمی را رد کرده است. توصیه همان است: `MinVersion` را صریحاً بگذارید و فهرست cipherها را به Go بسپارید.

## چرخش گواهی بدون restart

گواهی‌ها منقضی می‌شوند، پس باید عوضشان کنید. `GetCertificate` در هر handshake صدا زده می‌شود، پس تغییر چیزی که برمی‌گرداند گواهی را روی یک listener زنده می‌چرخاند. دمو یک `atomic.Pointer[tls.Certificate]` نگه می‌دارد، اول گواهی A را سرو می‌کند و بعد آن را با B عوض می‌کند:

```
before swap, client sees serial ...aaaa
after swap,  client sees serial ...bbbb (same listener, same address)
```

کلاینت در اتصال بعدی serial جدید را می‌بیند، بدون restart. در محیط واقعی گواهی را با یک signal یا یک timer از دیسک دوباره می‌خوانید. اتصال‌هایی که از قبل باز بوده‌اند همان گواهی‌ای را نگه می‌دارند که با آن شروع کرده‌اند.

## mutual TLS

در TLS معمولی فقط سرور گواهی نشان می‌دهد. با `ClientAuth: tls.RequireAndVerifyClientCert` و یک مجموعه‌ی `ClientCAs` سرور از کلاینت هم گواهی می‌خواهد. این {{< term "mutual-tls" "mutual TLS" >}} است که بین سرویس‌های داخلی رایج است:

```
no client cert    -> Get "https://127.0.0.1:55982/": remote error: tls: certificate required
cert from other CA-> Get "https://127.0.0.1:55982/": remote error: tls: certificate required
valid client cert -> hello orders-client <nil>
```

خط دوم مرا غافلگیر کرد: همان خطای نفرستادنِ گواهی را می‌دهد. کلاینت Go فقط گواهی‌ای را پیشنهاد می‌کند که issuer آن در فهرست قابل‌قبولِ سرور باشد، پس گواهی جعلی هرگز فرستاده نشد. در اجرای اصلی مجبورش نکردم بفرستد. این بار در یک نسخه‌ی موقت این کار را کردم: به کلاینت یک callback به نام `GetClientCertificate` دادم که گواهی جعلی را به هر حال برمی‌گرداند. بعد سرور جواب داد:

```
forced rogue -> Get "https://127.0.0.1:56067/": remote error: tls: unknown certificate authority
```

پس گواهی CA اشتباه در هر دو حالت رد می‌شود، فقط پیام بسته به اینکه کلاینت آن را فرستاده یا نه فرق می‌کند.

## یک بررسی پایش

انقضا کسل‌کننده‌ترین و رایج‌ترین دلیل قطعی‌های TLS است، پس آن را از بیرون بررسی کنید. `certcheck` برنامه‌ی کوچکی از خودم است: وصل می‌شود، با یک فایل CA تأیید می‌کند و روزهای باقی‌مانده‌ی leaf را حساب می‌کند. leaf سرور دمو ۱۰ روز و یک ساعت عمر دارد. (نام میزبان داخل `certcheck` یک ثابت است، `orders.local`، که تمرین پایین آن را برمی‌دارد.)

```
$ certcheck 127.0.0.1:PORT 14 ca.pem   -> WARN orders.local expires in 10 days (limit 14)   exit=1
$ certcheck 127.0.0.1:PORT 7 ca.pem    -> OK orders.local expires in 10 days                exit=0
$ certcheck 127.0.0.1:PORT 7 /dev/null -> UNKNOWN cannot load CA file                       exit=2
```

`14` و `7` حداقل روزهای باقی‌مانده هستند. با حد ۱۴، گواهی ۱۰ روزه هشدار می‌دهد؛ با ۷ مشکلی نیست؛ و با فایل CA خراب، ابزار حدس نمی‌زند و می‌گوید UNKNOWN. کدهای خروج 0، 1 و 2 برای cron یا هر سیستم پایش کار می‌کنند. زود هشدار بدهید، ۱۴ روز یا بیشتر، چون تمدید خودکار هم شکست می‌خورد و برای متوجه‌شدن وقت لازم دارید.

## Pinning و `InsecureSkipVerify`

{{< term "certificate-pinning" "Pinning" >}} یعنی کلاینت فقط سروری را می‌پذیرد که hash کلید عمومی‌اش را از قبل می‌داند. دمو SHA-256 کلید عمومی (SPKI) را داخل `VerifyConnection` مقایسه می‌کند. با pin روی کلید A، سرور A پاس می‌شود و سرور B شکست می‌خورد:

```
pin (sha256 of SPKI, first 16 hex): 20fd40a79e4fe868
server key ...aaaa: err=<nil>
server key ...bbbb: err=Get "https://127.0.0.1:55988/": pin mismatch: got ca33a5ac52cd79b2...
```

pin چرخش را سخت‌تر می‌کند، چون گواهی بعدی باید همان کلید را نگه دارد یا اول با pin تازه منتشر شود؛ برای همین بیشتر سرویس‌ها نباید pin کنند.

حالا ضدالگو. توسعه‌دهنده‌ها اغلب خطای تأیید را با `InsecureSkipVerify` ساکت می‌کنند:

```
RootCAs, wrong name   -> Get "https://127.0.0.1:55990/": tls: failed to verify certificate: x509: certificate is valid for orders.local, localhost, not payments.local
InsecureSkipVerify    -> hello <nil>
RootCAs, right name   -> hello <nil>
```

با تنظیم درست، خواستن نام اشتباه شکست می‌خورد. با `InsecureSkipVerify` همان نام اشتباه فقط کار می‌کند، پس ناهمخوانی کاملاً پنهان می‌شود، و گواهی یک مهاجم واقعی هم همین‌طور. راه درست `RootCAs` به‌علاوه‌ی `ServerName` درست است.

## ACME و ابطال (اجرا نشده)

سه چیز فقط توضیح داده شده است. {{< term "acme" "ACME" >}} پروتکلی است که صدور و تمدید گواهی را خودکار می‌کند؛ دلیلی که عمرهای خیلی کوتاه عملی می‌شوند. {{< term "ocsp" "OCSP" >}} اجازه می‌دهد کلاینت از CA بپرسد گواهی باطل شده یا نه. Certificate Transparency مجموعه‌ای از لاگ‌های عمومی گواهی‌های صادرشده است. هیچ‌کدام را اجرا نکردم. تا جایی که می‌دانم تأیید در `crypto/x509` خود Go ابطال را بررسی نمی‌کند، پس فرض نکنید گواهی باطل‌شده آنجا شکست می‌خورد.

## عادت‌های عملیاتی

- زنجیره‌ی کامل را به‌جز root بفرستید. میانیِ گم‌شده شبیه CA نامعتبر دیده می‌شود.
- نام و کاربرد را تأیید کنید و برای از بین بردن یک خطا هرگز تأیید را خاموش نکنید.
- انقضا را از بیرون پایش کنید؛ به حافظه تکیه نکنید.
- `MinVersion` را صریحاً بگذارید.
- کلیدهای خصوصی را از repositoryها دور نگه دارید.

## تمرین

`certcheck` را طوری گسترش دهید که نام میزبان را از آرگومان بگیرد، نه از یک ثابت، و یک فلگ اضافه کنید که SANها را چاپ کند. بعد با یک فایل CA اشتباه خرابش کنید و مطمئن شوید کد خروج 2 می‌شود.

## قدم بعدی

«مدیریت راز و کلید» آخرین عادت بالا را ادامه می‌دهد: اینکه کلیدها و رازهای دیگر با این همه چطور نشت می‌کنند و چطور باید آن‌ها را امن بارگذاری کرد.
