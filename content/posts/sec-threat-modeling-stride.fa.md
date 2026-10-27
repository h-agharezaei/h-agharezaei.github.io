+++
date = '2027-02-09T10:00:00+03:30'
draft = false
title = 'مدل‌سازی تهدید با STRIDE'
description = 'مدل‌سازی تهدید با STRIDE روی یک API سفارش در Go: نمودار جریان داده، جدول STRIDE، سه دموی واقعی (دست‌کاری، نشت خطا، DoS) و یک الگوی آماده.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "threat-modeling", "stride", "appsec", "go"]
cover = { image = "/images/covers/sec-threat-modeling-stride.fa.png", alt = "مدل‌سازی تهدید با STRIDE", hiddenInSingle = true }
+++

این مقاله شروع سری Software Security است. به‌جای اینکه باگ‌ها را یکی‌یکی بعد از وقوع درست کنیم، می‌خواهم راهی برای پیدا کردنشان در همان ابتدا داشته باشیم: {{< term "threat-modeling" "مدل‌سازی تهدید" >}} (**threat modeling**). موضوع ما سرویس `orders` همین وبلاگ است: همان API از [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) که پشتش Postgres ([pgx و sqlc](/fa/posts/go-postgres-pgx-sqlc/)) و NATS JetStream قرار دارد.

> فقط دفاعی. همه‌ی دموها برنامه‌ی کوچک Go خودم روی `127.0.0.1` هستند، فقط با کتابخانه‌ی استاندارد و Go 1.26. هیچ‌چیز علیه سیستم دیگران نیست. «خطای دیتابیس» در دموی ۲ متن ساختگی است و از اجرای واقعی Postgres نیامده.

## چهار سؤال

فرایند چهار سؤال است: روی چه چیزی کار می‌کنیم، چه چیزی می‌تواند خراب شود، چه کاری برایش می‌کنیم، و آیا کارمان را خوب انجام دادیم. این چارچوبی رایج است و به شخص خاصی نسبتش نمی‌دهم.

## مدل

```
 [ Client ] --1 HTTPS--> ( Orders API ) --2 SQL--> =Postgres=
  external      |            process   \--3 publish--> =NATS JetStream=
                |                                       |
   ===== trust boundary =====          ( Worker ) <--4--/
```

`[ ]` موجودیت بیرونی، `( )` فرایند و `= =` محل ذخیره‌ی داده است. {{< term "trust-boundary" "مرز اعتماد" >}} (**trust boundary**) جایی است که اینترنت به API می‌رسد: هرچه روی جریان ۱ می‌آید غیرقابل‌اعتماد است. جریان‌های ۲ تا ۴ داخلی‌اند ولی باز از فرایندی به فرایند دیگر می‌روند.

## STRIDE برای هر عنصر

{{< term "stride" "STRIDE" >}} شش سؤال می‌پرسد: Spoofing، Tampering، Repudiation، Information disclosure، {{< term "denial-of-service" "Denial of service" >}} و Elevation of privilege.

| عنصر | تهدید | راه‌حل |
|---|---|---|
| API، جریان ۱ | **S**: توکن دزدیده یا جعلی | اعتبارسنجی توکن، انقضای کوتاه |
| API، جریان ۱ | **T**: کلاینت `price_cents` را تعیین می‌کند | ورودی allow-list، قیمت‌گذاری در سرور (دموی ۱) |
| API | **R**: ردی از اینکه چه کسی چه کرد نیست | لاگ ساختاریافته با request ID، [کانفیگ و لاگ](/fa/posts/go-config-logging-errors/) |
| API | **I**: خطای خام به کلاینت می‌رسد | خطای عمومی و لاگ (دموی ۲) |
| API | **D**: درخواست حجیم یا کند | محدودیت بدنه، timeout (دموی ۳)، [rate limit](/fa/posts/go-rate-limiting-caching/) |
| API | **E**: کاربر سفارش دیگری را می‌خواند | بررسی مالکیت در هر خواندن |
| Postgres | **I**: نشت رمز | رمز بیرون از لاگ، کاربر DB با حداقل دسترسی |
| NATS | **T/E**: هر کسی event منتشر می‌کند | TLS و احراز هویت، [JetStream در پروداکشن](/fa/posts/nats-jetstream-production/) |
| NATS به worker | **T**: پیام تکراری یا replay | [idempotency](/fa/posts/nats-jetstream-idempotency/) |

سه مورد را واقعاً اجرا کردم.

## دموی ۱: دست‌کاری (Tampering)

endpoint ساده بدنه را مستقیم در struct به نام `Order` می‌خواند، پس کلاینت همه‌ی فیلدها را کنترل می‌کند. این همان {{< term "mass-assignment" "mass assignment" >}} است:

```
$ curl -s -X POST 127.0.0.1:8101/orders -d '{"sku":"book","qty":1,"price_cents":1,"status":"paid"}'
{"id":1,"sku":"book","qty":1,"price_cents":1,"status":"paid"}
```

کتابی که ۱۵۰۰ سنت بود شد ۱ سنت و «paid». نسخه‌ی اصلاح‌شده در یک ورودی دوفیلدی (`sku` و `qty`) می‌خواند، قیمت را از کاتالوگ سمت سرور برمی‌دارد و status را خودش می‌گذارد:

```
$ curl -s -X POST 127.0.0.1:8102/orders -d '{"sku":"book","qty":1,"price_cents":1,"status":"paid"}'
{"error":"bad request"}
$ curl -s -X POST 127.0.0.1:8102/orders -d '{"sku":"book","qty":2}'
{"id":1,"sku":"book","qty":2,"price_cents":1500,"status":"pending"}
```

`DisallowUnknownFields` فیلدهای اضافه را رد می‌کند.

## دموی ۲: افشای اطلاعات

handler ساده `err.Error()` را برمی‌گرداند. خطای ساختگی و شبیه درایور من نام ستون، SQLSTATE، نام میزبان و کاربر دیتابیس را لو می‌دهد:

```
{"error":"query orders: ERROR: column \"total_cents\" does not exist (SQLSTATE 42703) [host=db.internal port=5432 user=orders_app]"}
```

handler اصلاح‌شده جزئیات را در لاگ می‌نویسد و پیامی ثابت همراه request ID برمی‌گرداند تا کلاینت بتواند به آن ارجاع دهد:

```
{"error":"internal error","request_id":"a1b2c3"}
level=ERROR msg="request failed" path=/orders/1/total error="query orders: ERROR: ..." request_id=a1b2c3
```

(در این دمو ID ثابت است؛ در کد واقعی برای هر درخواست ساخته می‌شود.)

## دموی ۳: منع سرویس

یک بدنه‌ی ۵۰ مگابایتی (صفر) به endpointی فرستادم که فقط آن را می‌خواند و دور می‌ریزد. سرور ساده همه‌اش را خواند: `{"read":"52428800"}`. با `http.MaxBytesReader` روی ۱ مگابایت جواب شد `{"error":"body too large"}`.

برای هدر کند، یک probe کوچک Go اتصال باز می‌کند، نصف هدر را می‌فرستد و بعد هر ۲۰۰ میلی‌ثانیه یک بایت (الگوی {{< term "slowloris" "slowloris" >}}). سرور بدون timeout: `still open after 4s, giving up`. با `ReadHeaderTimeout` برابر ۱ ثانیه: `server closed after ~1.0s`. حافظه و throughput را اندازه نگرفتم.

## رتبه‌بندی

احتمال ضرب در اثر، هرکدام ۱ تا ۳. این قضاوت من برای همین سرویس است، نه اندازه‌گیری:

| تهدید | احتمال | اثر | امتیاز |
|---|---|---|---|
| قیمت تعیین‌شده توسط کلاینت | 3 | 3 | 9 |
| سفارش کاربر دیگر | 2 | 3 | 6 |
| خطاهای پرجزئیات | 3 | 2 | 6 |
| درخواست کند یا حجیم | 2 | 2 | 4 |

اول بالاترین امتیازها را درست کنید.

## الگو

```markdown
# Threat model: <system>
Scope / out of scope:
Diagram: (elements, flows, trust boundaries)
| Element | S | T | R | I | D | E | Mitigation | Owner | Status |
Top risks (L x I):
Review date / trigger (new feature, new dependency):
```

## چند نکته‌ی مهم

- با تغییر معماری نمودار را دوباره بکشید؛ مدل کهنه بدتر از نبودن مدل است.
- تهدید روی جریان‌ها به اندازه‌ی تهدید روی جعبه‌ها واقعی است.
- راه‌حل بدون مسئول فقط یک آرزوست.
- ابزارهایی مثل OWASP Threat Dragon و Microsoft Threat Modeling Tool وجود دارند؛ فقط نامشان را می‌آورم و اینجا استفاده نکردم.

## تمرین

یک عنصر به نمودار اضافه کنید (مثلاً cache با Redis) و شش ردیف STRIDE آن را بنویسید. کدام امتیاز بالاتری می‌گیرد؟

## قدم بعدی

مقاله‌ی بعدی «OWASP Top 10 در کد واقعی» است.
