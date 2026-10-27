+++
date = '2027-01-12T10:00:00+03:30'
draft = false
title = 'TCP: دست‌دادن و حالت‌های اتصال'
description = 'دست‌دادن TCP و حالت‌های اتصال روی loopback: LISTEN، ESTABLISHED، TIME_WAIT، half-close، RST، connection refused، timeout و backlog.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tcp", "sockets", "handshake", "tcp-states", "python"]
cover = { image = "/images/covers/net-tcp-handshake-states.fa.png", alt = "TCP: دست‌دادن و حالت‌های اتصال", hiddenInSingle = true }
+++

در پست قبل، [DNS در عمل](/fa/posts/net-dns-in-practice/)، یک نام را به آدرس تبدیل کردیم. حالا به آن آدرس وصل می‌شویم. یک اتصال {{< term "tcp" "TCP" >}} عمر دارد: باز می‌شود، استفاده می‌شود و بسته می‌شود، و هر مرحله یک حالت قابل‌مشاهده در کرنل دارد. اگر تا حالا `connection refused`، timeout یا هزاران socket گیرکرده در `TIME_WAIT` دیده‌اید، این پست معنی‌شان را توضیح می‌دهد. پایه‌اش [مدل TCP/IP](/fa/posts/net-tcp-ip-model/) است.

> همه‌چیز روی macOS (arm64) با Python 3.14 اجرا شده، روی `127.0.0.1` با یک port تصادفی (در خروجی `PORT` نوشته شده و port موقت کلاینت `EPH`) یا روی آدرس نمونه‌ی مستندات `192.0.2.1`. root ندارم، پس packet capture در کار نیست. فقط خط‌های مربوط به port دموی خودم را نشان می‌دهم.

## دست‌دادن سه‌مرحله‌ای

{{< term "three-way-handshake" "دست‌دادن سه‌مرحله‌ای" >}} (three-way handshake) اتصال را با سه segment باز می‌کند: کلاینت **SYN** می‌فرستد، سرور با **SYN+ACK** جواب می‌دهد و کلاینت **ACK** می‌فرستد. هر طرف یک شماره‌ی ترتیب اولیه انتخاب می‌کند و طرف مقابل آن را به‌اضافه‌ی یک تأیید می‌کند. روی این دستگاه نمی‌توانم این بسته‌ها را capture کنم، پس این اسکریپت فقط سه header را دستی می‌سازد، مثل ایده‌ی پست قبلی (شماره‌های ترتیب ساختگی، نه بسته‌ی واقعی):

```
client: 49152->80 seq=1000 ack=0 flags=SYN (0x02)
server: 80->49152 seq=5000 ack=1001 flags=SYN+ACK (0x12)
client: 49152->80 seq=1001 ack=5001 flags=ACK (0x10)
```

در کد واقعی کرنل این کار را می‌کند: `connect()` بعد از تمام‌شدن handshake برمی‌گردد.

## حالت‌هایی که می‌توان دید

سرور `listen()` را صدا می‌زند، یک کلاینت وصل می‌شود و کلاینت اول می‌بندد. در هر مرحله اسکریپت می‌ایستد و من در یک shell دیگر `netstat -an -p tcp` را اجرا می‌کنم (در تنظیمات من وقتی از داخل Python اجرا می‌شد خروجی نمی‌داد، برای همین از shell اجرایش کردم):

```
== 1-listen
127.0.0.1.PORT    *.*                LISTEN
== 2-established
127.0.0.1.PORT    127.0.0.1.EPH    ESTABLISHED
127.0.0.1.EPH    127.0.0.1.PORT    ESTABLISHED
127.0.0.1.PORT    *.*                LISTEN
== 3-client-closed
127.0.0.1.PORT    127.0.0.1.EPH    CLOSE_WAIT
127.0.0.1.EPH    127.0.0.1.PORT    FIN_WAIT_2
127.0.0.1.PORT    *.*                LISTEN
== 4-both-closed
127.0.0.1.PORT    *.*                LISTEN
127.0.0.1.EPH    127.0.0.1.PORT    TIME_WAIT
server recv after client FIN: b''
```

یک اتصال دو socket دارد، یکی برای هر طرف. بعد از `close()` کلاینت (FIN فرستاد و سرور تأییدش کرد) سرور در `CLOSE_WAIT` است: می‌داند طرف مقابل تمام کرده و منتظر است **کد من** ببندد. کلاینت در `FIN_WAIT_2` است. انبوه socket در `CLOSE_WAIT` یعنی برنامه‌ات `close()` را فراموش می‌کند. مقدار `b''` از `recv` همان EOF است.

بعد از اینکه سرور هم بست، طرفی که اول بسته بود، یعنی کلاینت، در حالت {{< term "time-wait" "TIME_WAIT" >}} می‌ماند. طبق مستندات حدود 2*MSL (دو برابر عمر بیشینه‌ی segment) آنجا می‌ماند تا بسته‌های سرگردان بمیرند؛ من منتظر پایانش نماندم.

## Half-close

بستن دو جهت مستقل دارد. `shutdown(SHUT_WR)` ({{< term "half-close" "half-close" >}}) می‌گوید «دیگر نمی‌فرستم» ولی socket هنوز می‌تواند بخواند:

```
server: got b'hello' then EOF
client: after SHUT_WR, still reading -> b'reply sent after EOF: HELLO'
client: next recv -> b''
client: send after SHUT_WR -> BrokenPipeError [Errno 32] Broken pipe
```

در Go معادلش `CloseWrite()` روی `*net.TCPConn` است؛ نسخه‌ی Go را اینجا اجرا نکردم.

## Refused و timeout

دو خطای کاملاً متفاوت:

```
loopback, closed port -> ConnectionRefusedError | [Errno 61] Connection refused
192.0.2.1:80 -> TimeoutError | timed out
```

روی port بسته کرنل فوراً به SYN با {{< term "tcp-rst" "RST" >}} جواب می‌دهد، پس `refused` سریع می‌گیرید: میزبان هست ولی کسی گوش نمی‌دهد. `192.0.2.1` آدرس نمونه‌ی مستندات است و کسی جواب نمی‌دهد؛ SYN فقط بی‌پاسخ می‌ماند و کلاینت تا timeout دو‌ثانیه‌ای من صبر می‌کند. شکست سریع معمولاً یعنی «port اشتباه»، شکست کند یعنی «میزبان در دسترس نیست یا firewall بسته‌ها را دور می‌ریزد».

## RST در برابر FIN

FIN بستن مرتب است و RST قطع ناگهانی. اینجا سرور قبل از `close()` مقدار `SO_LINGER` را با timeout صفر تنظیم می‌کند:

```
client recv -> ConnectionResetError | [Errno 54] Connection reset by peer
```

کلاینت به‌جای EOF تمیز، `ECONNRESET` می‌گیرد.

## backlog در listen

`listen(backlog)` اندازه‌ی صف اتصال‌هایی را تعیین می‌کند که handshake را تمام کرده‌اند ولی `accept()` نشده‌اند. من با backlog برابر ۱ گوش دادم، هرگز `accept()` نکردم و شش کلاینت باز کردم. نتیجه به سیستم‌عامل بستگی دارد؛ این macOS است و سه اجرای یکسان:

```
client 1: connect() returned
client 2: ConnectionResetError | [Errno 54] Connection reset by peer
client 3: ConnectionResetError | [Errno 54] Connection reset by peer
...
```

`netstat -L` مقدار `1/0/1` (یک اتصال در صف) نشان داد و `lsof` بقیه‌ی socketهای کلاینت را `CLOSED` نشان داد. انتظار دارم سیستم‌های دیگر فرق کنند، مثلاً SYN را دور بریزند تا کلاینت‌ها منتظر بمانند و دوباره تلاش کنند، ولی اینجا Linux ندارم. حلقه‌ی کند `accept()` برای کلاینت‌ها خطا می‌شود.

## اتصال بیکار و keepalive

اتصالی که ترافیک ندارد برای همیشه ESTABLISHED می‌ماند، حتی اگر دستگاه طرف مقابل ناپدید شده باشد. {{< term "tcp-keepalive" "keepalive در TCP" >}} کاری می‌کند که کرنل اتصال بیکار را پروب کند. من فقط گزینه‌ها را خواندم و تنظیم کردم (منتظر هیچ پروبی نماندم):

```
SO_KEEPALIVE default: 0
SO_KEEPALIVE now:     8
idle seconds before the first probe (TCP_KEEPALIVE): 7200
after setting 30: 30
```

عدد `8` فقط چیزی است که macOS برای «روشن» برمی‌گرداند؛ پیش‌فرض ۷۲۰۰ ثانیه هم مقدار macOS اینجاست و در هر سیستم فرق دارد.

## چند نکته‌ی مهم

- socketهای زیاد در `CLOSE_WAIT` باگ شماست؛ زیاد بودن `TIME_WAIT` عادی است و روی طرفی است که اول بسته.
- موقع اشکال‌یابی `refused` (سریع، RST) را از timeout (بی‌پاسخ) جدا کنید.
- همیشه timeout اتصال و خواندن بگذارید؛ پیش‌فرض می‌تواند چند دقیقه باشد.
- `ECONNRESET` و EOF را رویداد عادی شبکه بدانید.
- رفتار backlog و پیش‌فرض‌های keepalive به سیستم‌عامل بستگی دارد.

## تمرین

`states.py` را طوری عوض کنید که سرور اول ببندد. حالا کدام طرف `TIME_WAIT` نشان می‌دهد؟ بعد از پایان برنامه `netstat` را بخوانید و ببینید ورودی چقدر می‌ماند.

## قدم بعدی

پست بعدی «سرور و کلاینت TCP از صفر» است.
