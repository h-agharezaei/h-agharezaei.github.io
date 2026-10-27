+++
date = '2027-04-08T10:00:00+03:30'
draft = false
title = 'load balancer لایه‌ی ۴ و ۷'
description = 'load balancer لایه‌ی ۴ و ۷ با Go روی loopback: پخش بر اساس اتصال یا درخواست، مسیریابی، hash، health check و least connections.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "load-balancer", "reverse-proxy", "http", "go", "health-check"]
cover = { image = "/images/covers/net-load-balancer-l4-l7.fa.png", alt = "load balancer لایه‌ی ۴ و ۷", hiddenInSingle = true }
+++

در [پست قبل](/fa/posts/net-grpc-over-http2/) یک اتصال HTTP/2 هفتاد و یک فراخوانی را حمل کرد. برای بازدهی عالی است، اما برای {{< term "load-balancer" "load balancer" >}} دردسر دارد: اگر فقط اتصال‌ها را ببیند، هر ۷۱ فراخوانی به یک سرور می‌رود. اینجا هر دو نوع را با Go می‌سازم، یک proxy لایه‌ی ۴ و یکی لایه‌ی ۷، و می‌شمارم درخواست‌ها کجا می‌نشینند.

> همه‌چیز روی `127.0.0.1` با port تصادفی (چاپ نشده)، Go 1.26، macOS و فقط کتابخانه‌ی استاندارد اجرا شد. ماشین مشغول بود، پس تعداد منتشر می‌کنم و زمان‌سنجی نه. nginx، HAProxy، Envoy و load balancer ابری را اجرا نکردم؛ بحث درباره‌ی ایده‌هاست.

## لایه‌ی ۴: پخش اتصال‌ها

proxy لایه‌ی ۴ یک اتصال {{< term "tcp" "TCP" >}} را می‌پذیرد، به backend بعدی (round-robin) وصل می‌شود و با `io.Copy` بایت‌ها را دوطرفه کپی می‌کند. HTTP را اصلاً نمی‌خواند. سه backend که هرکدام نام خودش را جواب می‌دهد. اول ۳۰ کلاینت که هرکدام اتصال تازه باز می‌کنند، بعد یک کلاینت با {{< term "keep-alive" "keep-alive" >}} که ۳۰ درخواست می‌فرستد:

```
L4, 30 new connections:    b0=10 b1=10 b2=10 | proxy accepted 30
L4, 1 keep-alive conn x30: b0=30 | proxy accepted 1
```

این همان تله است. انتخاب یک‌بار برای هر اتصال انجام می‌شود، پس کلاینت ماندگار تمام ترافیکش را به یک backend می‌چسباند. gRPC و هر کلاینت HTTP/2 مثل خط دوم رفتار می‌کند.

## لایه‌ی ۷: پخش درخواست‌ها

proxy لایه‌ی ۷ همان `httputil.ReverseProxy` است، یک {{< term "reverse-proxy" "reverse proxy" >}}. اتصال کلاینت را تمام می‌کند، هر درخواست را می‌خواند و برای هرکدام جداگانه backend انتخاب می‌کند. همان آزمایش، یک اتصال کلاینت و ۳۰ درخواست:

```
L7, 1 client conn x30: b0=10 b1=10 b2=10 | proxy accepted 1
```

یک اتصال، سه backend. چون درخواست را parse می‌کند، می‌تواند ویرایشش هم بکند. تابع `Rewrite` من `SetXForwarded()` را صدا می‌زند و `X-Request-ID` می‌گذارد؛ backend این را دید:

```
b2|/|xff=127.0.0.1|rid=req-0030
```

`X-Forwarded-For` آدرس کلاینت است، اینجا فقط loopback. backend واقعی باید آن را فقط وقتی باور کند که از proxy خودتان آمده، وگرنه کلاینت‌ها جعلش می‌کنند.

مسیریابی بر اساس path: `/api/` به استخر b0 و b1 رفت و `/static/` به b2. با ۱۰ درخواست از هر نوع:

```
path routing: api->b0=5 api->b1=5 static->b2=10
```

## مسیریابی چسبنده و consistent hashing

برای نگه‌داشتن کاربر روی یک backend، هدر `X-User` را hash کردم و باقی‌مانده‌ی تقسیم بر تعداد backendها را گرفتم:

```
X-User=ada -> b1    X-User=bob -> b2    X-User=cy -> b1
```

ضعف، تغییر استخر است. ۱۰٬۰۰۰ کلید برداشتم، یکی از سه backend را حذف کردم و کلیدهایی را شمردم که backendشان عوض شد. یک بار با `hash % N` و یک بار با حلقه‌ای با ۱۰۰ نقطه برای هر node ({{< term "consistent-hashing" "consistent hashing" >}}):

```
mod-N                    remapped 6672 of 10000 keys (3335 of them did not live on b1)
ring (100 points/node)   remapped 2302 of 10000 keys (0 of them did not live on b1)
```

با mod-N یک‌سوم کلیدهای سالم هم جابه‌جا شد، یعنی session از دست رفته یا cache سرد. حلقه فقط کلیدهای node حذف‌شده را جابه‌جا کرد. عددهای دقیق به hash و کلیدهای من بستگی دارند.

## Health check

یکی از سه backend را متوقف کردم و ۳۰ درخواست از proxy لایه‌ی ۷ با round-robin فرستادم، در سه حالت:

```
no detection:    failed 10 of 30
passive (mark down on first transport error): failed 1 of 30
active (2 failed probes -> down): failed 0 of 30 after removal; b0=15 b2=15
```

غیرفعال یعنی proxy از شکست واقعی یاد می‌گیرد: یک درخواست هزینه‌ی درس را داد. فعال یعنی یک {{< term "health-check" "health check" >}} هر ۲۰ میلی‌ثانیه `/healthz` را probe می‌کند و بعد از ۲ شکست backend را برمی‌دارد؛ صبر کردم تا حذف شود، پس هیچ درخواست کاربری خراب نشد. سیستم‌های production معمولاً هر دو را با هم می‌گذارند و برای درخواست‌های {{< term "idempotency" "idempotent" >}} retry اضافه می‌کنند. من retry را اینجا نساختم.

## الگوریتم‌ها: round robin و least connections

round robin به بار توجه ندارد. b0 را کند کردم (۱۰۰ میلی‌ثانیه برای هر درخواست) و ۶۰ درخواست با ۶ worker هم‌زمان فرستادم:

```
rr: b0(slow)=20 b1=20 b2=20
lc: b0(slow)=2 b1=35 b2=23
```

least connections backend با کمترین درخواست در حال اجرا را برمی‌دارد، پس کندترین فقط ۲ تا گرفت. تقسیم بین b1 و b2 در هر اجرا فرق می‌کند. «دو انتخاب تصادفی» را اجرا نکردم.

## لایه‌ی ۴ یا ۷؟

لایه‌ی ۷ می‌تواند بر اساس path یا هدر مسیریابی کند، هدر را عوض کند، retry کند، درخواست‌های HTTP/2 را پخش کند و {{< term "tls" "TLS" >}} را تمام کند. هزینه‌اش: باید buffer و parse کند، کلید خصوصی پیش اوست و لایه‌ی ۴ ساده‌تر است و به پروتکل کاری ندارد. در TLS passthrough بالانسر لایه‌ی ۴ بایت‌های رمز‌شده را رد می‌کند و path را نمی‌بیند؛ در termination بالانسر لایه‌ی ۷ رمزگشایی می‌کند و اغلب دوباره برای backend رمز می‌کند. اینجا فقط توصیف می‌کنم؛ گواهی‌ها در [TLS و گواهی‌ها با openssl](/fa/posts/net-tls-openssl/) هستند.

## چند نکته‌ی مهم

- در لایه‌ی ۴ اتصال ماندگار (HTTP/2، gRPC، WebSocket) به یک backend می‌چسبد؛ برای آن‌ها پخش لایه‌ی ۷ بگذارید.
- `X-Forwarded-For` را فقط از proxyهای خودتان باور کنید.
- شکست را هم فعال و هم غیرفعال تشخیص دهید و retry را به درخواست‌های idempotent محدود کنید.
- با تغییر N، `hash % N` تقریباً همه‌چیز را جابه‌جا می‌کند.

## تمرین

حالت `lc` را با backendی امتحان کنید که فقط برای `/report` کند است. آیا تعداد اتصال هنوز بار را نشان می‌دهد؟ به‌جایش چه چیزی را باید ردیابی کرد؟

## قدم بعدی

پست بعدی «عیب‌یابی شبکه با curl، dig و traceroute» است.
