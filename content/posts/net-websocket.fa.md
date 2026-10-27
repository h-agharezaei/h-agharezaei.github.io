+++
date = '2027-03-25T10:00:00+03:30'
draft = false
title = 'WebSocket'
description = 'WebSocket با دست روی loopback: handshake مربوط به upgrade، فریم‌های mask‌شده، ping و close، و بعد hub در Go با heartbeat و محدودیت کلاینت کند.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "websocket", "http", "go", "heartbeat", "backpressure"]
cover = { image = "/images/covers/net-websocket.fa.png", alt = "WebSocket", hiddenInSingle = true }
+++

در [پست قبل](/fa/posts/net-http2/) با HTTP/2 آشنا شدیم. با این حال HTTP هنوز درخواست و پاسخ است و سرور نمی‌تواند اول حرف بزند. {{< term "websocket" "WebSocket" >}} این مشکل را حل می‌کند و یک اتصال {{< term "tcp" "TCP" >}} را به کانال پیام دوطرفه تبدیل می‌کند. شروعش {{< term "http" "HTTP" >}} معمولی است، مثل [HTTP/1.1 با دست](/fa/posts/net-http1-by-hand/)، بعد شکل بایت‌ها عوض می‌شود؛ مسئله‌ی framing همان است که در [سرور TCP از صفر](/fa/posts/net-sockets-tcp-from-scratch/) دیدیم.

> همه‌چیز روی `127.0.0.1` با port تصادفی (چاپ نشده)، Go 1.26، macOS و `github.com/coder/websocket` نسخه‌ی v1.8.15 اجرا شد. Linux را اجرا نکردم. ماشین مشغول بود، پس تعداد دارم و زمان‌سنجی ندارم. دمو یک پوشه‌ی مثال محلی است.

## handshake مربوط به upgrade

کلاینت یک GET معمولی با `Upgrade: websocket` و یک `Sec-WebSocket-Key` تصادفی می‌فرستد. سرور با `Sec-WebSocket-Accept` ثابت می‌کند که منظور را فهمیده: base64 مقدار {{< term "sha-1" "SHA-1" >}} کلید به‌اضافه‌ی یک GUID ثابت در RFC 6455. سرور دستی من (فقط stdlib، با hijack کردن اتصال) این را برای کلید نمونه‌ی RFC یعنی `dGhlIHNhbXBsZSBub25jZQ==` حساب کرد و یک کلاینت {{< term "socket" "socket" >}} خام پاسخ واقعی را چاپ کرد:

```
"HTTP/1.1 101 Switching Protocols\r\n"
"Upgrade: websocket\r\n"
"Connection: Upgrade\r\n"
"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"
"\r\n"
```

با مقدار RFC یکی است. کلید accept امنیت نیست؛ فقط نشان می‌دهد سرور upgrade را فهمیده. بعد از خط خالی اتصال دیگر HTTP نیست ({{< term "http-upgrade" "HTTP Upgrade" >}}).

## یک فریم، بایت به بایت

متن `Hello` را با کلید mask نمونه‌ی RFC یعنی `37 fa 21 3d` فرستادم:

```
client frame: 81 85 37 fa 21 3d 7f 9f 4d 51 58
byte0=10000001 (FIN=1 opcode=1)  byte1=10000101 (MASK=1 len=5)
mask key: 37 fa 21 3d  masked payload: 7f 9f 4d 51 58
server frame: 81 05 48 65 6c 6c 6f -> opcode=1 masked=false payload="Hello"
```

بایت اول FIN (آخرین تکه) و opcode را دارد (۱ یعنی متن). بایت دوم بیت MASK و طول ۷ بیتی را دارد؛ ۱۲۶ و ۱۲۷ یعنی طول ۱۶ یا ۶۴ بیتی بعدش می‌آید. هر فریم کلاینت باید mask شود: هر بایت payload با کلید mask به‌صورت XOR ترکیب می‌شود، مثلاً `0x48 ^ 0x37 = 0x7f`. فریم‌های سرور mask ندارند، پس echo همان `48 65 6c 6c 6f` است.

## ping، pong و close

فریم‌های کنترلی همین قالب را دارند. ping با payload برابر `hi` فرستادم و pong با همان payload گرفتم. بعد close با کد ۱۰۰۰ و دلیل `bye` فرستادم:

```
ping sent; got: 8a 02 68 69 opcode=10 payload="hi"
close sent; got: 88 05 03 e8 62 79 65 opcode=8 code=1000 reason="bye"
after close, read: EOF
```

close یک handshake است: هر طرف یکی می‌فرستد و بعد اتصال TCP تمام می‌شود. `0x03e8` برابر ۱۰۰۰ است، یعنی بسته‌شدن عادی.

## سرور واقعی با کتابخانه

سرور دستی من fragmentation، extension و سقف اندازه را ندارد، پس برای کار واقعی از کتابخانه استفاده کنید. من `coder/websocket` را استفاده کردم (نسخه‌ی بالا دانلود و pin شد). سرور echo یک حلقه‌ی `Read` و `Write` است و `go test -race` سبز شد:

```
TestEcho: echo: "hello"
TestEcho: close error: <nil>
```

## broadcast با hub

hub کلاینت‌های وصل را نگه می‌دارد و هر پیام را به همه {{< term "fan-out" "fan-out" >}} می‌کند. هر کلاینت goroutine نویسنده و صف محدود خودش را دارد تا یک کلاینت کند بقیه را متوقف نکند. با ۵ کلاینت و ۲۰ پیام:

```
clients=5 messages=20 deliveries=100 evicted=0
```

شش بار با `-race` اجرا کردم و همه سبز بود.

## کلاینتی که ناپدید می‌شود

یک اتصال TCP بعد از رفتن طرف مقابل هم می‌تواند باز به نظر برسد. سرور هر ۵۰ میلی‌ثانیه (فقط برای دمو کوتاه است) ping می‌فرستد و pong را با {{< term "deadline" "deadline" >}} منتظر می‌ماند. ۳ کلاینت سالم وصل کردم و یک socket خام که handshake را کامل کرد و بعد ساکت شد:

```
connected: 4
after heartbeat: connected=3 ping_failures=1
```

کلاینت ساکت شناسایی و حذف شد و بقیه ماندند. این یک {{< term "heartbeat" "heartbeat" >}} است. در پروداکشن مقدارها در حد ثانیه‌اند.

## کلاینت کند

اگر کلاینتی نخواند، TCP پر می‌شود، نویسنده بلاک می‌شود و صف بزرگ می‌شود. صف بی‌حد یعنی نشتی حافظه، پس صف ۲۵۶ پیامی گذاشتم و هرکس سرریز کند قطع می‌شود. سه کلاینت سریع و یکی که وصل شد ولی هرگز نخواند، ۶۰۰ پیام ۶۴ کیلوبایتی:

```
fast clients=3 messages=600 delivered=1800 evicted=1
```

هر ۱۸۰۰ پیام به کلاینت‌های سریع رسید و دقیقاً یک کلاینت اخراج شد. این {{< term "backpressure" "backpressure" >}} از راه قطع کلاینت است.

## WebSocket، SSE یا polling؟

نظر من است، نه اندازه‌گیری:

- polling ساده یا درخواست طولانی وقتی به‌روزرسانی کم است و سادگی مهم است.
- {{< term "server-sent-events" "SSE" >}} وقتی فقط سرور می‌فرستد (feed، پیشرفت کار)؛ HTTP ساده است و خودش دوباره وصل می‌شود. دموی SSE اینجا اجرا نکردم.
- WebSocket وقتی هر دو طرف زیاد می‌فرستند (چت، بازی، همکاری).

## چند نکته‌ی مهم

- صف هر کلاینت را محدود کنید و تعیین کنید سرریز چه می‌شود.
- heartbeat یا read deadline بگذارید؛ به اتصال ساکت اعتماد نکنید.
- سقف اندازه‌ی پیام بگذارید.
- برای کلاینت مرورگر header `Origin` را بررسی کنید؛ احراز هویت را اینجا پوشش ندادم.
- load balancer باید اتصال‌های طولانی را اجازه بدهد.

## تمرین

hub را طوری عوض کنید که به‌جای قطع کلاینت، قدیمی‌ترین پیام صف را دور بریزد. بعد بشمارید کلاینت کند چند پیام گرفت و چند پیام فرستاده شد.

## قدم بعدی

پست بعدی «gRPC روی HTTP/2» است.
