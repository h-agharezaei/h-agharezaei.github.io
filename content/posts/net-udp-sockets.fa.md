+++
date = '2027-02-03T10:00:00+03:30'
draft = false
title = 'UDP و تفاوتش با TCP'
description = 'UDP در Go روی loopback: مرز datagramها، سقف اندازه، خطای ICMP، یک proxy با از دست رفتن بسته و لایه‌ی stop-and-wait برای قابل‌اعتماد شدن.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "udp", "sockets", "go", "datagram", "reliability"]
cover = { image = "/images/covers/net-udp-sockets.fa.png", alt = "UDP و تفاوتش با TCP", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/net-sockets-tcp-from-scratch/) یک سرور TCP نوشتیم و دیدیم جریان بایتی پیام ندارد. {{< term "udp" "UDP" >}} برعکس است: فقط پیام دارد و هیچ قولی نمی‌دهد. هر دو را در [پست مدل TCP/IP](/fa/posts/net-tcp-ip-model/) دیدیم و UDP را در [DNS در عمل](/fa/posts/net-dns-in-practice/) برای DNS به کار بردیم. اینجا روی رابط {{< term "loopback" "loopback" >}} سراغش می‌رویم و بعد تضمین‌های گم‌شده را خودمان می‌سازیم.

> همه‌چیز روی `127.0.0.1` با port تصادفی، Go 1.26 و macOS اجرا شده است. port‌های موقت در خطوط خطا با `PORT` عوض شده‌اند. Linux را اجرا نکردم و ماشین مشغول بود، پس زمان‌بندی نشان نمی‌دهم. دمو یک پوشه‌ی نمونه‌ی محلی است.

## یک echo server

```go
pc, _ := net.ListenPacket("udp", "127.0.0.1:0")
n, addr, _ := pc.ReadFrom(buf)   // چه کسی فرستاد؟
pc.WriteTo(buf[:n], addr)        // به همان آدرس جواب بده
```

`Accept` وجود ندارد: یک {{< term "socket" "socket" >}} به همه سرویس می‌دهد و هر datagram آدرس فرستنده‌اش را همراه دارد. کلاینت `client got "ping"` چاپ کرد. نسخه‌ی Python همین شکل را با `sendto` و `recvfrom` دارد و `client got b'ping'` چاپ کرد.

## مرزها حفظ می‌شوند

نتیجه‌ی TCP را یادتان هست که دو write یک read شد؟ اینجا کلاینت `hello\n` و `world\n` را با دو write می‌فرستد، سرور صبر می‌کند تا هر دو در صف باشند و بعد می‌خواند:

```
ReadFrom #1: 6 bytes "hello\n"
ReadFrom #2: 6 bytes "world\n"
ReadFrom(4): 4 bytes "0123"
next read: timeout (the other 6 bytes are gone)
```

هر {{< term "datagram" "datagram" >}} یک read است و به {{< term "message-framing" "فریم‌بندی" >}} نیازی نیست. روی دیگرِ سکه دو خط آخر است: datagram ده بایتی که در بافر ۴ بایتی خوانده شود ۴ بایت می‌دهد و بقیه دور ریخته می‌شود. بافر را برای بزرگ‌ترین datagram بسازید.

## datagram تا چه اندازه می‌تواند بزرگ باشد؟

طبق مستندات، payload یو‌دی‌پی در IPv4 حداکثر ۶۵٬۵۰۷ بایت است. روی همین Mac اندازه‌های رو‌به‌رشد فرستادم:

```
  9000 bytes: write ok
  9216 bytes: write ok
  9217 bytes: write error: write: message too long
 65507 bytes: write error: write: message too long
```

خطا همان‌جا در `Write` و پیش از ارسال می‌آید و خیلی پایین‌تر از ۶۵٬۵۰۷ است. تنظیم macOS به نام `net.inet.udp.maxdgram` اینجا ۹۲۱۶ بود که با نتیجه می‌خواند. Linux را امتحان نکردم، پس این عدد را کپی نکنید. شبکه‌های واقعی datagram بزرگ را تکه یا دور می‌اندازند؛ عادت امن ماندن زیر یک {{< term "mtu" "MTU" >}} است (حدود ۱۲۰۰ تا ۱۴۰۰ بایت).

## اتصالی نیست؛ پس خطا را چه کسی خبر می‌دهد؟

`net.Dial("udp", ...)` به چیزی وصل نمی‌شود و فقط یک طرف پیش‌فرض را نگه می‌دارد. وقتی روی port کسی گوش نمی‌دهد:

```
connected socket, Write error: <nil>
connected socket, next Read error: read udp 127.0.0.1:PORT->127.0.0.1:PORT: read: connection refused
unconnected socket, WriteTo error: <nil>
unconnected socket, ReadFrom error: read udp 127.0.0.1:PORT: i/o timeout
```

نوشتن همیشه موفق است. میزبان با پیام port-unreachable از نوع {{< term "icmp" "ICMP" >}} جواب می‌دهد و socket متصل آن را در read بعدی به شکل `connection refused` نشان می‌دهد. socket نامتصل چیزی نمی‌شنود و فقط timeout می‌خورد (به {{< term "deadline" "deadline" >}} نگاه کنید). این تنها بازخورد خطای UDP است و رسیدنش هم تضمین نیست.

## گم شدن، تکرار، جابه‌جایی

loopback تقریباً هیچ‌وقت بسته گم نمی‌کند، پس یک UDP proxy کوچک با الگوی ثابت نوشتم: datagram ۳ و ۷ را دور بینداز، ۱ را دوبار بفرست و ۴ و ۵ را جابه‌جا کن. فرستنده `m0` تا `m9` می‌فرستد:

```
sent:    m0 m1 m2 m3 m4 m5 m6 m7 m8 m9
receiver: m0 m1 m1 m2 m5 m4 m6 m8 m9
```

دو بسته گم شد، یکی دوبار آمد، یک جفت جابه‌جا شد و هیچ خطایی نیامد. اینترنت واقعی گاهی همین کار را می‌کند، پس برنامه‌ی UDP باید انتظارش را داشته باشد.

## قابل‌اعتماد کردن: stop-and-wait

کوچک‌ترین راه‌حل {{< term "stop-and-wait" "stop-and-wait" >}} است: جلوی هر پیام یک شماره‌ی ۴ بایتی می‌گذاریم، منتظر ACK با همان شماره می‌مانیم و بعد از timeout دوباره می‌فرستیم. گیرنده فقط شماره‌ی مورد انتظار را تحویل می‌دهد و همه‌ی دیده‌شده‌ها را ACK می‌کند، پس تکراری‌ها بی‌ضررند. در کل حدود ۶۰ خط است؛ هسته‌ی فرستنده:

```go
for tries := 0; ; tries++ {
    c.Write(pkt)
    c.SetReadDeadline(time.Now().Add(100 * time.Millisecond))
    n, err := c.Read(buf)
    if err == nil && n == 4 && binary.BigEndian.Uint32(buf) == uint32(seq) { break }
}
```

حالا proxy هر datagram داده‌ی سوم را دور می‌اندازد، دومی را تکرار می‌کند و هر ACK چهارم را حذف می‌کند. دو اجرا نتیجه‌ی یکسان دادند:

```
sent 8 messages: 14 datagrams on the wire, 6 retransmits, 1 stale ACKs ignored
delivered in order: alpha bravo charlie delta echo foxtrot golf hotel
```

هر هشت پیام به ترتیب و دقیقاً یک‌بار رسید، به بهای ۶ ارسال دوباره. stop-and-wait در هر رفت‌وبرگشت فقط یک بسته می‌فرستد و کند است؛ پروتکل‌های واقعی چند بسته را هم‌زمان در راه نگه می‌دارند. این همان کاری است که {{< term "tcp" "TCP" >}} در مقیاس کوچک برایتان می‌کند.

## پس چرا UDP؟

وقتی قواعد خودتان را می‌خواهید. DNS سؤال و جواب را در یک datagram جا می‌دهد و handshake ندارد. صدا و تصویر زنده بسته‌ی دیررسیده را ترجیحاً دور می‌اندازند تا بسته‌ی کهنه تحویل شود. QUIC، لایه‌ی انتقال زیر HTTP/3، قابل‌اعتمادی را خودش روی UDP می‌سازد؛ اینجا فقط ذکرش می‌کنم و امتحانش نکردم.

## چند نکته‌ی مهم

- یک `Write` یک datagram است و یک `Read` هم؛ بافر را به اندازه‌ی کافی بزرگ بگیرید.
- موفق بودن `Write` چیزی درباره‌ی رسیدن نمی‌گوید.
- payload را زیر MTU نگه دارید.
- همیشه read deadline بگذارید؛ سکوت عادی است.
- اگر ترتیب یا تکراری‌ها مهم است پیام‌ها را شماره بزنید.

## تمرین

الگوی proxy را طوری عوض کنید که سه نسخه‌ی اول هر بسته را دور بیندازد و ببینید فرستنده چند بار باید دوباره بفرستد. بعد یک سقف تلاش اضافه کنید که به‌جای حلقه‌ی بی‌پایان خطا برگرداند.

## قدم بعدی

پست بعدی «HTTP/1.1 با دست» است.
