+++
date = '2027-04-24T10:00:00+03:30'
draft = false
title = 'TLS و گواهی x509 در عمل'
description = 'TLS و گواهی x509 در Go روی loopback: خطاهای verify، زنجیره، چرخش با GetCertificate، mutual TLS، بررسی انقضا و pinning با خروجی واقعی.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "tls", "x509", "certificates", "mtls", "go"]
cover = { image = "/images/covers/sec-tls-x509-certificates.fa.png", alt = "TLS و گواهی x509 در عمل", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [CSRF، CORS و هدرهای امنیتی](/fa/posts/sec-csrf-cors-headers/)، رفتار مرورگر را محکم می‌کرد. اینجا خود لوله را محکم می‌کنیم. [TLS و گواهی‌ها با openssl](/fa/posts/net-tls-openssl/) سمت خط فرمان `openssl` بود؛ این مقاله سمت Go و عملیات است: داخل یک {{< term "x509-certificate" "گواهی x509" >}} چیست، چرا verify شکست می‌خورد، و چطور گواهی را بچرخانیم و مانیتور کنیم. سرور از همان جنس API در [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) است.

> فقط دفاعی. همه‌چیز روی `127.0.0.1` در یک برنامه‌ی Go 1.26 فقط با کتابخانه‌ی استاندارد اجرا شد. {{< term "certificate-authority" "CA" >}} یک‌بارمصرف را خودم در کد ساختم (ECDSA P-256)؛ هیچ CA عمومی در کار نیست. کلید خصوصی هرگز روی دیسک نیامد. ACME، OCSP و CT فقط توضیح داده شده‌اند و اجرا نشده‌اند. ساعت‌ها در خروجی ساعت محلی من است.

## داخل گواهی چیست

`x509.CreateCertificate` یک template را امضا می‌کند و parse کردنش این فیلدها را می‌دهد (خلاصه):

```
subject     CN=orders.local,O=Demo
issuer      CN=Demo Root CA,O=Demo
serial      ...3c4d
dns SANs    [orders.local localhost]
ip SANs     [127.0.0.1]
IsCA        false  basicConstraintsValid true
KeyUsage    DigitalSignature=true, CertSign=false
ExtKeyUsage [serverAuth]
```

CA مقدار `IsCA true` و `CertSign=true` دارد. کلاینت نام را با فهرست {{< term "subject-alt-name" "SAN" >}} تطبیق می‌دهد، پس همه‌ی نام‌های DNS و IPها را آنجا بگذارید. از serial فقط چند بایت آخر را چاپ کردم.

## خطاها، واقعی

`Verify` با pool ریشه، یک نام و کاربرد `serverAuth`:

```
unknown authority  x509: certificate signed by unknown authority
hostname mismatch  x509: certificate is valid for orders.local, localhost, not payments.local
expired            x509: certificate has expired or is not yet valid: current time 2026-10-27T10:27:14+03:30 is after 2026-10-26T06:57:14Z
not yet valid      x509: certificate has expired or is not yet valid: current time 2026-10-27T10:27:14+03:30 is before 2026-10-28T06:57:14Z
wrong ExtKeyUsage  x509: certificate specifies an incompatible key usage
no intermediate    x509: certificate signed by unknown authority
with intermediate  ok
```

مورد کاربرد اشتباه گواهی‌ای بود که برای `clientAuth` صادر شده بود. دقت کنید «نبودن intermediate» همان متن «CA ناشناس» را می‌دهد و در production گیج‌کننده است.

## زنجیره روی اتصال واقعی

{{< term "certificate-chain" "زنجیره‌ی گواهی" >}} یعنی leaf، intermediate، root. leaf را از یک intermediate صادر کردم و به دو شکل سرو کردم. فقط با leaf، کلاینت Go می‌گوید:

```
tls: failed to verify certificate: x509: certificate signed by unknown authority
```

با `tls.Certificate{Certificate: [][]byte{leaf, intermediate}}` درخواست `hello` برگرداند و کلاینت زنجیره‌ای به طول ۲ دید. سرور باید intermediateها را بفرستد. در آزمایش من کلاینت Go خودش intermediate گم‌شده را نگرفت.

## نسخه‌ها و cipher suite

با `MinVersion: tls.VersionTLS12` روی سرور، `resp.TLS` نتیجه را نشان می‌دهد:

```
client max TLS 1.2 -> TLS 1.2, TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
client max TLS 1.3 -> TLS 1.3, TLS_AES_128_GCM_SHA256
client max TLS 1.1 -> tls: no supported versions satisfy MinVersion and MaxVersion
```

`MinVersion` را صریح بگذارید و فهرست cipher را به Go بسپارید.

## چرخش بدون restart

`GetCertificate` در هر handshake اجرا می‌شود، پس عوض کردن یک pointer گواهی را می‌چرخاند. یک `atomic.Pointer[tls.Certificate]` نگه داشتم، A را سرو کردم و روی همان listener به B عوض کردم:

```
before swap, client sees serial ...aaaa
after swap,  client sees serial ...bbbb (same listener, same address)
```

در production با سیگنال یا timer از دیسک دوباره بخوانید. اتصال‌های موجود گواهی قبلی را نگه می‌دارند.

## Mutual TLS

با `ClientAuth: tls.RequireAndVerifyClientCert` و `ClientCAs` این همان {{< term "mutual-tls" "mutual TLS" >}} است:

```
no client cert     -> remote error: tls: certificate required
cert from other CA -> remote error: tls: certificate required
valid client cert  -> hello orders-client
```

خط دوم برایم غافلگیرکننده بود: کلاینت Go فقط گواهی‌ای می‌فرستد که issuerش در فهرست سرور باشد، پس گواهی جعلی اصلاً فرستاده نشد. مجبورش نکردم بفرستد.

## بررسی برای مانیتورینگ

`certcheck` (برنامه‌ی کوچک خودم) وصل می‌شود، verify می‌کند و روزهای باقی‌مانده را حساب می‌کند. leaf سرور دمو ۱۰ روز و یک ساعت عمر داشت:

```
$ certcheck 127.0.0.1:PORT 14 ca.pem   -> WARN orders.local expires in 10 days (limit 14)   exit=1
$ certcheck 127.0.0.1:PORT 7 ca.pem    -> OK orders.local expires in 10 days                exit=0
$ certcheck 127.0.0.1:PORT 7 /dev/null -> UNKNOWN cannot load CA file                       exit=2
```

کدهای خروج ۰، ۱ و ۲ برای cron یا هر مانیتوری کار می‌کنند. هشدار را از ۱۴ روز یا بیشتر بگذارید، چون تمدید گاهی شکست می‌خورد.

## Pinning و `InsecureSkipVerify`

{{< term "certificate-pinning" "Pinning" >}} در `VerifyConnection` هش SHA-256 کلید عمومی (SPKI) را مقایسه می‌کند. با pin روی کلید A، سرور A رد شد و سرور B با `pin mismatch: got b1acadcaca83edc9...` شکست خورد. pin چرخش را سخت می‌کند، پس بیشتر سرویس‌ها بهتر است pin نکنند.

ضدالگو:

```
RootCAs, wrong name   -> x509: certificate is valid for orders.local, localhost, not payments.local
InsecureSkipVerify    -> hello <nil>
RootCAs, right name   -> hello <nil>
```

`InsecureSkipVerify` عدم تطابق نام را کاملاً پنهان کرد. راه درست `RootCAs` به‌علاوه‌ی `ServerName` است.

## ACME و ابطال (اجرا نشده)

{{< term "acme" "ACME" >}} صدور و تمدید را خودکار می‌کند و برای همین عمر کوتاه عملی می‌شود. {{< term "ocsp" "OCSP" >}} از CA می‌پرسد گواهی ابطال شده یا نه؛ Certificate Transparency هم صدور عمومی را ثبت می‌کند. هیچ‌کدام را اجرا نکردم و تا جایی که می‌دانم کلاینت Go ابطال را خودش بررسی نمی‌کند.

## چند نکته‌ی مهم

- زنجیره‌ی کامل را به‌جز root بفرستید.
- نام و کاربرد را verify کنید و هرگز verify را رد نکنید.
- انقضا را مانیتور کنید؛ به حافظه تکیه نکنید.
- `MinVersion` را صریح بگذارید.
- کلیدها را بیرون از repository نگه دارید.

## تمرین

`certcheck` را طوری گسترش دهید که نام host را از آرگومان بگیرد، نه از یک ثابت، و یک flag برای چاپ SANها اضافه کنید. بعد با فایل CA اشتباه خرابش کنید و کد خروج ۲ را تأیید کنید.

## قدم بعدی

مقاله‌ی بعدی «مدیریت راز و کلید» است.
