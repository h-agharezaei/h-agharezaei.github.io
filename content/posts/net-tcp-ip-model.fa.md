+++
date = '2026-12-19T10:00:00+03:30'
draft = false
title = 'مدل TCP/IP و مسیر یک بسته'
description = 'مدل TCP/IP با کد واقعی: ساخت دستی header‌های IPv4 و TCP، راستی‌آزمایی checksum و دیدن یک اتصال loopback و جریان بایتی TCP.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tcp-ip", "tcp", "ip", "sockets", "http"]
cover = { image = "/images/covers/net-tcp-ip-model.fa.png", alt = "مدل TCP/IP و مسیر یک بسته", hiddenInSingle = true }
+++

هر سرویسی که در این وبلاگ نوشتم، مثل [API با net/http](/fa/posts/go-http-api-stdlib/) یا [سرویس gRPC](/fa/posts/go-grpc-service/)، آخرش به یک فراخوانی می‌رسد: «این بایت‌ها را به آن آدرس بفرست». این سری نگاهی است به آنچه زیر آن فراخوانی اتفاق می‌افتد. با نقشه شروع می‌کنیم: لایه‌ها و اینکه یک درخواست HTTP چطور بسته می‌شود.

> همه‌چیز روی macOS (arm64) با Python 3.14، `curl`، `nc` و `lsof` اجرا شده است. اینجا دسترسی root ندارم، پس packet capture در کار نیست؛ به‌جایش header‌ها را دستی می‌سازیم و socket‌ها را می‌بینیم. همه‌ی آدرس‌ها loopback یا نمونه‌ی مستندات هستند (`192.0.2.10` و `198.51.100.20`) و دمو از یک port تصادفی محلی استفاده می‌کند.

## چهار لایه

{{< term "tcp-ip-model" "مدل TCP/IP" >}} چهار لایه دارد: **link** (یک گام روی یک شبکه، مثل Ethernet یا Wi-Fi)، **internet** (‏IP: آدرس و مسیریابی گام‌به‌گام)، **transport** (‏TCP یا UDP: port و برای TCP قابلیت اطمینان) و **application** (‏HTTP، DNS، gRPC). مدل ۷ لایه‌ی **OSI** همین پشته را ریزتر تقسیم می‌کند. هر دو وجود دارند چون OSI واژگان خوبی برای آموزش است («لایه‌ی ۴»، «لایه‌ی ۷») ولی چیزی که اینترنت واقعاً پیاده کرده TCP/IP است.

در مسیر پایین، هر لایه لایه‌ی بالایی را در خودش می‌پیچد؛ به این کار {{< term "encapsulation" "کپسوله‌سازی" >}} (encapsulation) می‌گویند:

```
[ Ethernet header | [ IP header | [ TCP header | [ HTTP request ] ] ] ]
   link               internet      transport      application
```

## ساخت دستی header‌ها

header در IPv4 بدون option بیست بایت است و header در TCP هم بیست بایت. `struct` در Python می‌تواند آن‌ها را بسازد (`!` یعنی ترتیب بایت شبکه، big-endian). اسکریپت یک بسته با یک درخواست کوچک HTTP از `192.0.2.10:49152` به `198.51.100.20:80` می‌سازد و بعد دوباره parse می‌کند:

```python
ip_hdr = struct.pack("!BBHHHBBH4s4s", (4 << 4) | 5, 0, total, 0x1234, 0x4000,
                     64, 6, csum, src, dst)
tcp_hdr = struct.pack("!HHIIBBHHH", 49152, 80, 1000, 5000, 5 << 4, 0x18, 64240, tcp_csum, 0)
```

```
IPv4 header:
  version+IHL      45
  total length     004d
  TTL              40
  protocol         06
  header checksum  3c25
  source           c000020a
  destination      c6336414
TCP header:
  src port         c000
  dst port         0050
  sequence         000003e8
  offset+flags     5018
  window           faf0
total bytes: 77 = 20 + 20 + 37
parsed: 192.0.2.10 -> 198.51.100.20 proto 6 ttl 64 len 77
parsed: port 49152 -> 80 PSH+ACK set: True window 64240
```

(بعضی فیلدها حذف شده‌اند.) `45` یعنی نسخه‌ی ۴ و header پنج کلمه‌ای؛ `06` شماره‌ی پروتکل TCP است؛ `c000020a` همان `192.0.2.10` است. {{< term "checksum" "checksum" >}} مکمل مجموع کلمه‌های ۱۶ بیتی header است. برای راستی‌آزمایی، هر ده کلمه را با خود فیلد checksum جمع می‌کنیم:

```
IPv4 header checksum field: 0x3c25
sum of header words incl. checksum: 0xffff
```

همین `0xffff` دقیقاً چیزی است که الگوریتم برای header سالم تضمین می‌کند. router در هر گام TTL را کم می‌کند و پس مجبور است این مقدار را دوباره حساب کند. checksum در TCP علاوه بر این یک pseudo-header با آدرس‌ها را هم پوشش می‌دهد؛ آن را هم حساب کردم ولی با stack واقعی مقایسه نکردم.

## loopback و MTU

خروجی `ifconfig lo0` که فقط به خطوط loopback کاهش داده‌ام (خروجی واقعی بقیه‌ی interface‌های من را هم دارد که حذف شدند):

```
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
	inet 127.0.0.1 netmask 0xff000000
```

{{< term "mtu" "MTU" >}} در loopback اینجا ۱۶۳۸۴ است. طبق مستندات، Ethernet معمولی MTU برابر ۱۵۰۰ دارد، پس یک segment در TCP حداکثر حدود ۱۴۶۰ بایت داده حمل می‌کند ({{< term "mss" "MSS" >}}: ۱۵۰۰ منهای ۲۰ برای IP و ۲۰ برای TCP). بسته‌ی IP بزرگ‌تر از MTU باید fragment شود یا دور ریخته شود؛ TCP با انتخاب segmentهای کوچک‌تر از این مشکل دور می‌ماند.

## یک اتصال واقعی و لایه‌ی application

یک سرور HTTP کوچک روی `127.0.0.1` اجرا می‌کنم (port تصادفی که `PORT` نوشته‌ام). `curl -v` لایه‌ی application را نشان می‌دهد که متن ساده است:

```
> GET / HTTP/1.1
> Host: 127.0.0.1:PORT
> User-Agent: curl/8.7.1
> Accept: */*
< HTTP/1.0 200 OK
< Content-Length: 33
hello from the application layer
```

وقتی `nc` یک اتصال را باز نگه می‌دارد، `lsof -nP -iTCP:PORT` این {{< term "socket" "socket" >}}‌ها را نشان می‌دهد (ستون‌ها کوتاه شده و port جایگزین شده است):

```
python3.1  3u  IPv4  TCP 127.0.0.1:PORT (LISTEN)
python3.1  4u  IPv4  TCP 127.0.0.1:PORT->127.0.0.1:58632 (ESTABLISHED)
nc         3u  IPv4  TCP 127.0.0.1:58632->127.0.0.1:PORT (ESTABLISHED)
```

سرور یک socket در حالت listen و یک socket پذیرفته‌شده دارد و سر دیگر اتصال دست `nc` است. اتصال با چهار مقدار آدرس مبدأ، port مبدأ، آدرس مقصد و port مقصد شناخته می‌شود. `nc -v` هم وقتی handshake در {{< term "tcp" "TCP" >}} کامل شود می‌نویسد `Connection to 127.0.0.1 port PORT [tcp/*] succeeded!`.

## TCP یک جریان است

۱۰۰٬۰۰۰ بایت را در ده write جدا از ۱۰٬۰۰۰ بایت می‌فرستم و می‌بینم گیرنده با `recv()` چه می‌گیرد. دو بار اجرا کردم:

```
sent: 10 writes of 10000 bytes = 100000
recv() sizes: [26332, 20000, 3668, 32664, 17336] total 100000
recv() sizes: [65536, 4464, 30000] total 100000
```

مجموع همیشه درست است، ولی اندازه‌ی تکه‌ها از writeهای من پیروی نمی‌کند و بین اجراها فرق دارد. TCP جریانی مرتب از بایت‌ها تحویل می‌دهد و مرز پیام ندارد. به همین دلیل HTTP هدر `Content-Length` و chunked encoding دارد و gRPC قبل از هر پیام طول آن را می‌گذارد.

## چند نکته‌ی مهم

- load balancer «لایه‌ی ۷» و «لایه‌ی ۴» در این فرق دارند که کدام header را می‌خوانند: اولی HTTP می‌فهمد و دومی فقط IP و port.
- هرگز فرض نکنید یک `Write` برابر یک `Read` است؛ پیام‌هایتان را خودتان frame کنید.
- checksum حادثه را پیدا می‌کند، نه مهاجم را. امنیت از TLS می‌آید که موضوع یکی از مقاله‌های بعدی است.
- اندازه‌ی header مهم است: با option‌ها header از ۲۰ بایت بیشتر می‌شود و MSS کوچک‌تر.
- اینجا بسته‌ی واقعی capture نکردم؛ بایت‌های دستی فقط قالب را نشان می‌دهند، نه آنچه ماشین من فرستاده.

## تمرین

اسکریپت را طوری تغییر دهید که یک option به TCP اضافه کند (مثلاً MSS با kind برابر ۲، طول ۴ و مقدار ۱۴۶۰)، data offset در header را ۶ کلمه کند و parser آن را بخواند. بعد یک بیت از header در IP را برگردانید و نشان دهید مجموع دیگر `0xffff` نیست.

## قدم بعدی

مقاله‌ی بعدی «آدرس‌دهی IP و subnet» است.
