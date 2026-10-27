+++
date = '2027-04-23T10:00:00+03:30'
draft = false
title = 'case study: چرا این درخواست کند است'
description = 'چرا این درخواست کند است: تفکیک فازها با httptrace در Go برای چهار درخواست مرموز روی loopback، زمان‌های curl و چک‌لیست لایه‌به‌لایه.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "latency", "troubleshooting", "httptrace", "curl", "case-study"]
cover = { image = "/images/covers/net-slow-request-case-study.fa.png", alt = "case study: چرا این درخواست کند است", hiddenInSingle = true }
+++

در [پست قبل](/fa/posts/net-troubleshooting-curl-traceroute/) یک جعبه‌ابزار ساختیم. این پست آخر سری آن را روی سؤالی می‌گذارد که هر مهندس backend می‌شنود: «این درخواست کند است، چرا؟» ترفند این است که به جمع کل نگاه نکنیم و آن را به فازها بشکنیم: پیدا کردن نام، connect در {{< term "tcp" "TCP" >}}، handshake در {{< term "tls" "TLS" >}}، انتظار برای اولین بایت ({{< term "ttfb" "TTFB" >}}) و دانلود بدنه. نگاه کنید به [مدل TCP/IP](/fa/posts/net-tcp-ip-model/) و [DNS در عمل](/fa/posts/net-dns-in-practice/).

> حریم خصوصی: همه‌چیز روی `127.0.0.1` و با گواهی self-signed برای `localhost` اجرا شد (کلاینت verification را رد می‌کند، فقط برای همین دموی محلی قابل قبول است). ماشین خیلی مشغول بود (load average بالای 20)، پس عددها به نزدیک‌ترین 50 میلی‌ثانیه گرد شده‌اند: تأخیرهای تزریق‌شده (300 تا 400 میلی‌ثانیه) غالب‌اند. DNS واقعی، تأخیر واقعی ISP، packet loss و packet capture را امتحان نکردم.

## راه‌اندازی

یک برنامه‌ی کوچک Go (مثال محلی) هم سرور دارد هم کلاینت. سرور می‌تواند در هر فاز تأخیر تزریق کند: listener که بعد از `Accept` می‌خوابد، `GetCertificate` در TLS که می‌خوابد، handler که قبل از header می‌خوابد (`?h=400`)، بدنه‌ای که قطره‌قطره می‌آید (`?b=3&bd=100`) و بدنه‌ی بزرگی که آهسته نوشته می‌شود (`?big=15`). کلاینت از `net/http/httptrace` استفاده می‌کند. تأخیر «name resolution» یک sleep داخل `DialContext` است: یک جست‌وجوی کند را شبیه‌سازی می‌کند و DNS واقعی نیست.

## چهار درخواست مرموز

خروجی کلاینت برحسب میلی‌ثانیه (گرد شده به 50) برای هر درخواست:

```
baseline  dns=  0 connect=  0 tls=  0 wait=  0 ttfb=  0 body=  0  bytes=3
mystery 1 dns=300 connect=  0 tls=  0 wait=  0 ttfb=  0 body=  0  bytes=3
mystery 2 dns=  0 connect=  0 tls=300 wait=  0 ttfb=  0 body=  0  bytes=3
mystery 3 dns=  0 connect=  0 tls=  0 wait=  0 ttfb=400 body=  0  bytes=3
mystery 4 dns=  0 connect=  0 tls=  0 wait=  0 ttfb=  0 body=300  bytes=30
```

در 1 زمان قبل از ساخته شدن هر socket صرف شده: کلاینت منتظر یک نام است. در 2 connect فوری است اما handshake کند است: لایه‌ی TLS سرور مشغول است. در 3 تا لحظه‌ی نوشته شدن درخواست همه‌چیز سریع است و بعد 400 میلی‌ثانیه سکوت: handler کند است، نه شبکه. در 4 header زود رسید ولی 30 بایت 300 میلی‌ثانیه طول کشید: قطره‌قطره آمده، نه اینکه پهنای باند کم باشد. با یک پاسخ بزرگ و throttle‌شده مقایسه کنید:

```
big       ... ttfb=  0 body=300  bytes=245760
```

همان 300 میلی‌ثانیه، اما 245,760 بایت. بایت‌ها می‌گویند بدنه کند است یا فقط بزرگ.

curl با `-w` همین داستان را نشان می‌دهد؛ متغیرهایش تجمعی‌اند:

```
$ curl -sk -o /dev/null -w 'connect=%{time_connect} tls_done=%{time_appconnect} first_byte=%{time_starttransfer} total=%{time_total}\n' https://localhost:18102/
connect=0.000307 tls_done=0.327153 first_byte=0.327520 total=0.327621
```

در حالت handler کند، first_byte برابر 0.41 ثانیه بود و tls_done برابر 0.013 ثانیه. در حالت قطره‌قطره total برابر 0.306 و first_byte برابر 0.0036 ثانیه بود. curl تأخیر DNS شبیه‌سازی‌شده‌ی مرا نمی‌بیند؛ جست‌وجوی خودش را می‌کند. tls_done در baseline آن 0.078 ثانیه بود (شلوغی ماشین).

## یک تله: accept دیرهنگام

وقتی سرور بعد از `Accept` می‌خوابید:

```
accept    dns=  0 connect=  0 tls=300 wait=  0 ttfb=  0 body=  0
```

kernel پیش از آنکه برنامه accept را صدا بزند handshake‌ی TCP را تمام می‌کند، پس تأخیر به شکل handshake‌ی کند TLS دیده می‌شود. از سمت کلاینت نمی‌شود `GetCertificate`ِ کند را از accept loopِ گیرکرده تشخیص داد؛ داده‌ی سمت سرور لازم است.

## استفاده‌ی مجدد، pool و HTTP/2

با {{< term "keep-alive" "keep-alive" >}} درخواست دوم فازهای اول را رد می‌کند. دو درخواست، جست‌وجوی شبیه‌سازی‌شده‌ی 300 میلی‌ثانیه و handler با 100 میلی‌ثانیه:

```
request 1: dns=300 ... ttfb=100 reused=false
request 2: dns=  0 ... ttfb=100 reused=true
```

`GotConn.Reused` برابر `true` بود و هزینه‌ی lookup، connect و TLS از بین رفت. تمام شدن pool شبیه انتظار قبل از connect است. با `MaxConnsPerHost=1` و سه درخواست هم‌زمان به handler با 200 میلی‌ثانیه:

```
HTTP/1.1  req 0: wait=  0  done at 200
          req 1: wait=200  done at 400
          req 2: wait=400  done at 600
HTTP/2    all three: wait=0  done at 200
```

درخواست‌ها در صف {{< term "connection-pool" "connection pool" >}} می‌مانند. با حالت پایگاه‌داده در [connection pool و حالت‌های خرابی](/fa/posts/db-connection-pooling/) و کلاینت HTTP در [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) مقایسه کنید. در HTTP/2 هر سه درخواست یک اتصال را شریک شدند ({{< term "multiplexing" "multiplexing" >}}، نگاه کنید به [HTTP/2 و فرق‌هایش](/fa/posts/net-http2/)). retry هم می‌تواند تأخیر را پنهان کند (یک درخواست کند که در واقع دو بار رفته)؛ این حالت را اجرا نکردم.

## روش حذف لایه‌به‌لایه

| ترتیب | لایه | فازی که بزرگ می‌شود | اولین سؤال |
|---|---|---|---|
| 1 | کلاینت | wait قبل از dns | pool تمام شده؟ CPU شلوغ است؟ |
| 2 | DNS | dns | کدام resolver جواب داد؟ |
| 3 | connect | connect | refused، timeout، دور؟ |
| 4 | TLS | tls | زنجیره‌ی گواهی، صف accept؟ |
| 5 | صف سرور | tls یا ttfb | thread، backlog پر؟ |
| 6 | handler | ttfb | query کند، lock، upstream؟ |
| 7 | بدنه | body | بایت زیاد یا قطره‌قطره؟ |
| 8 | دوباره کلاینت | بعد از body | parse؟ |

## چند نکته‌ی مهم

- قبل از حدس زدن، فازهای یک درخواست را اندازه بگیرید؛ جمع کل مقصر را پنهان می‌کند.
- بدنه‌ی بزرگ و بدنه‌ی قطره‌قطره هر دو دانلود طولانی نشان می‌دهند؛ بایت‌ها را ببینید.
- عددهای فقط-کلاینت نمی‌توانند handshake کند را از گیرکردن accept جدا کنند.

## تمرین

یک flag به سرور اضافه کنید که اتصال را بعد از header ببندد. کلاینت چه خطایی گزارش می‌کند؟ بعد یک retry اضافه کنید و فکر کنید تلاش دوم پنهان را چطور متوجه می‌شوید.

## قدم بعدی

سری Networking همین‌جا تمام می‌شود. با سری Linux و سری Distributed Systems ادامه بدهید.
