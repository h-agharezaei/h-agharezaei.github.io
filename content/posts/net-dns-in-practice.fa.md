+++
date = '2027-01-02T10:00:00+03:30'
draft = false
title = 'DNS در عمل'
description = 'DNS در عمل با اجرای واقعی dig، ساخت دستی یک query با struct پایتون و یک authoritative server کوچک در Go: رکوردها، TTL، NXDOMAIN و واگذاری.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "dns", "dig", "udp", "go", "python"]
cover = { image = "/images/covers/net-dns-in-practice.fa.png", alt = "DNS در عمل", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/net-addressing-subnets/) با آدرس‌های IP حساب کردیم، ولی کسی آن‌ها را تایپ نمی‌کند. آدم‌ها نام تایپ می‌کنند و {{< term "dns" "DNS" >}} نام را به آدرس تبدیل می‌کند. لایه‌ها را در [مقاله‌ی مدل TCP/IP](/fa/posts/net-tcp-ip-model/) دیدیم: DNS یک پروتکل لایه‌ی کاربرد است که معمولاً روی {{< term "udp" "UDP" >}} سوار می‌شود. این بار پاسخ‌های واقعی را با `dig` می‌خوانیم، یک query را بایت‌به‌بایت می‌سازیم و یک سرور کوچک می‌نویسیم.

> macOS (arm64)، Go 1.26، Python 3.14 و `dig` 9.10. در هر `dig` یک resolver عمومی (`1.1.1.1`) را صریح نوشته‌ام تا آدرس resolver خودم هیچ‌جا نیاید؛ هرجا چیزی را حذف یا جایگزین کرده‌ام گفته‌ام. دموهای loopback روی `127.0.0.1` هستند. هیچ زمانی اندازه نگرفته‌ام.

## خواندن رکوردها

`example.com` طبق مستندات (RFC 2606) برای مستندسازی رزرو شده و پرسیدنش بی‌خطر است. فقط بخش answer:

```
example.com. 177   IN A     172.66.147.243
example.com. 177   IN A     104.20.23.154
example.com. 77    IN AAAA  2606:4700:10::6814:179a
example.com. 84087 IN NS    hera.ns.cloudflare.com.
example.com. 168   IN MX    0 .
example.com. 300   IN TXT   "v=spf1 -all"
example.com. 1048  IN SOA   elliott.ns.cloudflare.com. dns.cloudflare.com. 2418004112 ...
```

(از AAAA یکی از دو خط آمده، SOA کوتاه شده و رکورد TXT یک خط دوم هم داشت که حذفش کردم.) `A` برای IPv4 است، `AAAA` برای IPv6، `NS` سرورهای صاحب zone را نام می‌برد، `SOA` شماره‌ی نسخه و زمان‌بندی zone را دارد و `TXT` متن آزاد است؛ اینجا یک سیاست SPF. رکورد `MX` با مقدار `0 .` یعنی «این دامنه ایمیل نمی‌پذیرد». ستون دوم همان {{< term "ttl" "TTL" >}} است.

## TTL و cache

یک سؤال را دو بار با فاصله‌ی شش ثانیه پرسیدم:

```
example.com. 109 IN A 172.66.147.243
example.com. 29  IN A 104.20.23.154
```

TTL کم شد، پس جواب از cache آمده. کاهش ۸۰ بود، نه ۶؛ بررسی‌اش نکردم، ولی یک resolver عمومیِ بزرگ در واقع ماشین‌های زیادی است که هرکدام cache جدا دارند.

## NXDOMAIN

```
$ dig @1.1.1.1 nonexistent-name.invalid A
status: NXDOMAIN
```

{{< term "nxdomain" "NXDOMAIN" >}} یعنی نام وجود ندارد. نکته‌ی غافلگیرکننده: `nonexistent-name.example.com` با `status: NOERROR`، جواب خالی و یک SOA در بخش authority برگشت. یا نام هست و فقط از آن نوع رکوردی ندارد، یا zone کار هوشمندانه‌ای می‌کند؛ در هر دو حالت `NOERROR` یعنی «پیدا شد» نیست. resolverها پاسخ منفی را هم cache می‌کنند، به مدتی که از SOA به دست می‌آید.

## چه کسی جواب می‌دهد: recursive در برابر authoritative

`1.1.1.1` یک {{< term "recursive-resolver" "recursive resolver" >}} است: کار را برای شما انجام می‌دهد و cache می‌کند. `dig +trace` همان کار را خودش از root شروع می‌کند. فقط نام‌ها:

```
.            NS a.root-servers.net. ... m.root-servers.net.
com.         NS a.gtld-servers.net. ... m.gtld-servers.net.
example.com. NS hera.ns.cloudflare.com. / elliott.ns.cloudflare.com.
example.com. A  172.66.147.243 / 104.20.23.154
```

root به سرورهای `com` اشاره می‌کند، `com` به name serverهای خود دامنه، و آن‌ها داده‌ی واقعی را دارند. این‌ها {{< term "authoritative-server" "authoritative serverها" >}} هستند.

## ساخت دستی یک query

پیام DNS یک header ۱۲ بایتی است (id، flags، چهار شمارنده) به‌علاوه‌ی یک سؤال: نام به شکل labelهای دارای طول، یک type و یک class. `struct` پایتون کافی است (`rawdns.py`):

```python
header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)  # RD set
qname = b"\x07example\x03com\x00"
q = header + qname + struct.pack("!HH", 1, 1)               # A, IN
```

این را به `1.1.1.1:53` روی UDP فرستادم و بعد روی {{< term "tcp" "TCP" >}} با پیشوند طول ۲ بایتی:

```
query: 29 bytes
UDP reply 61 bytes
id=0x1234 QR=1 RCODE=0 RA=1 QDCOUNT=1 ANCOUNT=2
  name bytes: c00c example.com TTL 61 A 172.66.147.243
  name bytes: c00c example.com TTL 61 A 104.20.23.154
TCP reply 61 bytes (2-byte length prefix)
id=0x1234 QR=1 RCODE=0 RA=1 QDCOUNT=1 ANCOUNT=2
  name bytes: c00c example.com TTL 155 A 104.20.23.154
```

`QR=1` یعنی پاسخ، `RCODE=0` موفقیت و `ANCOUNT=2` تعداد جواب‌ها. نام در هر جواب `c00c` است: دو بیت بالا `11` یعنی «اشاره‌گر» و ۱۴ بیت باقی‌مانده (`0x00C` = ۱۲) به offset ۱۲ اشاره می‌کند، جایی که نام سؤال قرار دارد. این همان name compression است.

## یک authoritative server کوچک

`toy/main.go` روی UDP `127.0.0.1:5300` گوش می‌دهد (نه 5353، چون macOS از آن استفاده می‌کند) و به queryهای A زیر `.test` که TLD رزرو است با `127.0.0.1` جواب می‌دهد؛ به بقیه NXDOMAIN. `dig` واقعی:

```
$ dig @127.0.0.1 -p 5300 shop.test
;; flags: qr aa rd; QUERY: 1, ANSWER: 1
shop.test.  30 IN A 127.0.0.1
$ dig @127.0.0.1 -p 5300 api.shop.test +short
127.0.0.1
$ dig @127.0.0.1 -p 5300 example.com
status: NXDOMAIN
```

`aa` پرچم authoritative است؛ dig هشدار می‌دهد recursion در دسترس نیست که درست هم هست.

## resolver درون برنامه

`net.Resolver` در Go یک `Dial` سفارشی می‌گیرد، پس اشاره‌دادنش به سرور کوچک ما سه خط است:

```
shop.test [127.0.0.1] <nil>
missing.example.com [] lookup missing.example.com no such host
```

(خطای واقعی آدرس resolver سیستم را هم نوشته بود که حذفش کردم.) `socket.getaddrinfo` در Python از سیستم‌عامل رد می‌شود: `localhost` همان `127.0.0.1` را داد و `example.com` دو آدرس IPv4 عمومی‌اش را. سیستم‌عامل `/etc/hosts` و resolverهای تنظیم‌شده را به ترتیبی که تنظیمات سیستم تعیین می‌کند بررسی می‌کند؛ آن را فقط با کلمات گفتم و چیزی از تنظیمات را paste نکردم. Go می‌تواند resolver خالص خودش یا کتاب‌خانه‌ی C را به کار ببرد: با `GODEBUG=netdns=go` و `netdns=cgo` هر دو `localhost` و `example.com` را resolve کردند و ادعای من همین است و بس.

## چند نکته‌ی مهم

- بسیاری از «درخواست‌های کند» در واقع جست‌وجوی کند هستند: cache miss چند رفت‌وبرگشت خرج دارد و resolver خراب پیش از شروع درخواست اصلی یک timeout اضافه می‌کند. یک مقاله‌ی case study بعدی یکی از این‌ها را دنبال می‌کند.
- TTL کم یعنی تغییر سریع ولی جست‌وجوی بیشتر؛ TTL زیاد برعکس.
- `NOERROR` با جواب خالی همان NXDOMAIN نیست.
- ترتیب جواب‌ها بین queryها عوض می‌شود، پس به اولین آدرس تکیه نکنید.
- جواب‌های بزرگ ممکن است به TCP نیاز داشته باشند؛ کلاینت باید آماده‌اش باشد.

## تمرین

سرور کوچک را طوری گسترش دهید که به AAAA برای `shop.test` با `::1` جواب بدهد، و تصمیم بگیرید برای نام `.test` که با type برابر MX پرسیده شود چه برگرداند.

## قدم بعدی

مقاله‌ی بعد «TCP: دست‌دادن و حالت‌های اتصال» است.
