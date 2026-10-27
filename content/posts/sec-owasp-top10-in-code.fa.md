+++
date = '2027-02-21T10:00:00+03:30'
draft = false
title = 'OWASP Top 10 در کد واقعی'
description = 'OWASP Top 10 در کد واقعی: دسته‌های نسخه‌ی ۲۰۲۵ روی Go، با دموی محلی IDOR، pprof بازمانده، تزریق در لاگ و SSRF و راه‌حل هرکدام.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "owasp", "appsec", "go", "idor", "ssrf"]
cover = { image = "/images/covers/sec-owasp-top10-in-code.fa.png", alt = "OWASP Top 10 در کد واقعی", hiddenInSingle = true }
+++

در [مدل‌سازی تهدید با STRIDE](/fa/posts/sec-threat-modeling-stride/) فهرستی رتبه‌بندی‌شده از تهدیدها ساختیم. {{< term "owasp-top-10" "OWASP Top 10" >}} واژگان رایج برای همین تهدیدهاست؛ پس اینجا آن را به کد نگاشت می‌کنم: ایده‌ی سرویس `orders` از [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/)، در قالب برنامه‌های خیلی کوچک.

در تاریخ ۲۰۲۶-۱۰-۲۷ نشانی https://owasp.org/Top10/ را خواندم؛ به **OWASP Top 10:2025** منتقل شد و نام دسته‌ها در زیر از همان صفحه کپی شده است.

> فقط دفاعی. همه‌ی دموها برنامه‌ی Go خودم با کتابخانه‌ی استاندارد روی `127.0.0.1` هستند (Go 1.26). «کاربر» هدر `X-User` است که جای توکن تأییدشده نشسته.

## ده دسته

| # | دسته | در یک جمله |
|---|---|---|
| A01 | Broken Access Control | کاربر به داده یا کاری می‌رسد که نباید (دمو ۱) |
| A02 | Security Misconfiguration | پیش‌فرض ناامن یا قابلیت دیباگ در معرض دید (دمو ۲) |
| A03 | Software Supply Chain Failures | وابستگی یا مرحله‌ی build آسیب‌پذیر یا دست‌کاری‌شده |
| A04 | Cryptographic Failures | محافظت ضعیف یا ناموجود از داده و رمزها (دمو ۵) |
| A05 | Injection | ورودی نامطمئن به‌عنوان کد یا دستور تفسیر می‌شود (مقاله‌ی بعد) |
| A06 | Insecure Design | ایراد در طراحی است نه کد؛ به threat modeling نگاه کنید |
| A07 | Authentication Failures | ورود، session یا مدیریت credential ضعیف |
| A08 | Software or Data Integrity Failures | اعتماد به کد یا داده بدون راستی‌آزمایی |
| A09 | Security Logging and Alerting Failures | حمله ثبت یا دیده نمی‌شود (دمو ۳) |
| A10 | Mishandling of Exceptional Conditions | خطاهایی که باز می‌مانند یا جزئیات لو می‌دهند |

SSRF (دمو ۴) در فهرست ۲۰۲۱ دسته‌ی جدا بود؛ نمی‌گویم نسخه‌ی ۲۰۲۵ کجا جایش داده، پس آن را یک ضعف مستقل می‌گیرم.

## دمو ۱: broken access control

handler ساده سفارش را با شناسه پیدا می‌کند و برمی‌گرداند. این یک {{< term "idor" "IDOR" >}} است:

```
$ curl -s -H 'X-User: alice' 127.0.0.1:8201/orders/2
{"id":"2","owner":"bob","sku":"laptop"}
```

آلیس سفارش باب را خواند. در راه‌حل `o.Owner` با فراخواننده مقایسه می‌شود و برای هر دو حالت «وجود ندارد» و «مال تو نیست» 404 می‌آید تا شناسه‌ها قابل‌کاوش نباشند:

```
$ curl -s -H 'X-User: alice' 127.0.0.1:8202/orders/2
{"error":"not found"}
$ curl -s -H 'X-User: alice' 127.0.0.1:8202/orders/1
{"id":"1","owner":"alice","sku":"book"}
```

## دمو ۲: security misconfiguration

import کردن `net/http/pprof` handlerها را روی mux پیش‌فرض ثبت می‌کند. اگر آن mux روی mux عمومی سوار شود، در معرض دید می‌ماند:

```
$ curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8211/debug/pprof/cmdline
200
```

راه‌حل: {{< term "pprof" "pprof" >}} فقط روی listener دومی در `127.0.0.1` سرو شود (پورت عمومی: 404، پورت مدیریتی: 200). خود پروفایلینگ در [پروفایلینگ با pprof در Go](/fa/posts/go-profiling-pprof/) آمده. bind به loopback حداقل کار است؛ در پروداکشن قوانین شبکه هم لازم است.

## دمو ۳: logging failures

نام کاربری با newline می‌تواند خط لاگ جعلی بسازد. با لاگ به سبک `Printf`:

```
level=INFO msg="login failed" user=bob
time=2027-02-21 level=INFO msg="login ok" user=admin
```

این {{< term "log-injection" "تزریق در لاگ" >}} (**log injection**) است: یک «login ok» جعلی برای admin. با `log/slog` مقدار quote و escape می‌شود و هر رویداد در یک خط می‌ماند:

```
level=INFO msg="login failed" user="bob\ntime=2027-02-21 level=INFO msg=\"login ok\" user=admin"
```

[کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/) را ببینید. این فقط نیمه‌ی «ثبت» در A09 است؛ بخش alerting را نشان نداده‌ام.

## دمو ۴: SSRF

handler مسیر `/fetch?url=` هر چیزی را که بدهند دانلود می‌کند. یک سرویس «داخلی» ساختگی روی loopback راه انداختم:

```
$ curl -s '127.0.0.1:8221/fetch?url=http://127.0.0.1:8223/secret'
internal-only: db-password-demo
```

این {{< term "ssrf" "SSRF" >}} است: سرور چیزی را گرفت که فراخواننده خودش به آن نمی‌رسید. راه‌حل فقط `https` و یک allow-list از میزبان‌ها را می‌پذیرد:

```
$ curl -s '127.0.0.1:8222/fetch?url=http://127.0.0.1:8223/secret'
{"error":"url not allowed"}
```

allow-list من فقط یک میزبان نمونه است؛ redirect و ترفندهای DNS را آزمایش نکردم و راه‌حل واقعی باید آن‌ها را پوشش دهد.

## دمو ۵: cryptographic failures

SHA-256 بدون salt برای یک رمز یکسان در دو کاربر:

```
alice f52fbd32b2b3b86ff88ef6c490628285f482af15ddcb29541f94bcf526a3f6c7
bob f52fbd32b2b3b86ff88ef6c490628285f482af15ddcb29541f94bcf526a3f6c7
```

hash برابر یعنی رمز برابر، و hash سریع برای حدس‌زدن ارزان است. روش درست موضوع «ذخیره‌ی امن رمز عبور: argon2 و bcrypt» است.

## زنجیره‌ی تأمین: آنچه نتوانستم اجرا کنم

می‌خواستم `govulncheck` را روی ماژولی با `golang.org/x/text` قدیمی اجرا کنم. درخواست به پایگاه آسیب‌پذیری (`vuln.go.dev`) اینجا `403 Forbidden` برگرداند؛ پس یافته‌ی واقعی ندارم و چیزی نشان نمی‌دهم. `govulncheck ./...` را در CI خودتان اجرا کنید.

## چند نکته‌ی مهم

- دسترسی را در سرور و برای هر شیء بررسی کنید، نه فقط در UI.
- قابلیت‌های دیباگ جایشان listener جدا و غیرعمومی است.
- خط لاگ را هرگز با الحاق رشته نسازید.
- برای URLهای خروجی allow-list بهتر از block-list است.
- Top 10 فهرست آگاهی است؛ رد کردنش یعنی امن‌بودن نیست.

## تمرین

به دموی ۱ مسیر `DELETE /orders/{id}` را اضافه کنید. آیا بررسی مالکیت آن را پوشش می‌دهد؟ تستی بنویسید که ثابت کند آلیس 404 می‌گیرد.

## قدم بعدی

مقاله‌ی بعد «تزریق و XSS» است.
