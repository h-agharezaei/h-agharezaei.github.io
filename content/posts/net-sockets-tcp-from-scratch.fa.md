+++
date = '2027-01-22T10:00:00+03:30'
draft = false
title = 'سرور و کلاینت TCP از صفر'
description = 'سرور TCP از صفر در Go: حلقه‌ی Accept، فریم‌بندی جریان بایتی، پروتکل KV با length prefix، deadline، half-close و خاموشی تمیز.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tcp", "sockets", "go", "framing", "protocol"]
cover = { image = "/images/covers/net-sockets-tcp-from-scratch.fa.png", alt = "سرور و کلاینت TCP از صفر", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/net-tcp-handshake-states/) دیدیم یک اتصال چطور باز و بسته می‌شود. حالا هر دو سر را می‌نویسیم. API مربوط به {{< term "socket" "socket" >}} کوچک است ولی یک واقعیت درباره‌ی {{< term "tcp" "TCP" >}} همه را گیر می‌اندازد: پیام ندارد. این را در [پست مدل TCP/IP](/fa/posts/net-tcp-ip-model/) دیدیم؛ اینجا باهاش کار می‌کنیم. کد از {{< term "goroutine" "goroutine" >}} استفاده می‌کند، مثل [goroutine و channel](/fa/posts/go-goroutines-channels/).

> همه‌چیز روی `127.0.0.1` با port تصادفی (`:0`)، Go 1.26 و macOS اجرا شده است. هیچ آدرسی از دستگاه من نیامده؛ port‌های موقت در یک خط خطا با `PORT` عوض شده‌اند. دمو یک پوشه‌ی نمونه‌ی محلی است. ماشین مشغول بود، پس زمان‌بندی نشان نمی‌دهم.

## Listen، accept و یک goroutine برای هر اتصال

```go
ln, _ := net.Listen("tcp", "127.0.0.1:0")
for {
    c, err := ln.Accept()
    if err != nil {
        if errors.Is(err, net.ErrClosed) { return nil } // listener بسته شد: توقف عادی
        return err
    }
    go func() { defer c.Close(); handle(c) }()
}
```

`Accept` تا وقتی کلاینتی handshake را کامل کند بلاک می‌شود و یک socket تازه برای آن کلاینت برمی‌گرداند؛ socket شنونده می‌ماند و پذیرفتن ادامه دارد.

## TCP یک جریان بایتی است

کلاینت `hello\n` و `world\n` را با دو `Write` می‌فرستد؛ سرور ۳۰۰ میلی‌ثانیه می‌خوابد تا هر دو برسند و بعد می‌خواند. بعد کلاینت ۱۰ بایت را با یک write می‌فرستد و سرور با بافر ۴ بایتی می‌خواند:

```
one Read: 12 bytes "hello\nworld\n"
Read(4):  4 bytes "0123"
Read(4):  4 bytes "4567"
Read(4):  2 bytes "89"
```

دو write یک read شد و یک write سه read. sleep فقط چسبیدن را تکرارپذیر می‌کند؛ بدون آن نتیجه به زمان‌بندی بستگی دارد. پس یک {{< term "stream" "stream" >}} به {{< term "message-framing" "فریم‌بندی" >}} (framing) نیاز دارد.

## فریم‌بندی ۱: جداشده با newline

یک پروتکل KV کوچک: `SET k v`، `GET k` و `QUIT`، هر فرمان در یک خط. سرور از `bufio.Reader.ReadString('\n')` استفاده می‌کند و دور map یک `sync.Mutex` دارد (به {{< term "mutex" "mutex" >}} نگاه کنید). اجرای واقعی:

```
> SET lang go  < OK
> GET lang     < VALUE go
> GET nope     < NOTFOUND
> QUIT         < BYE
```

ساده و با `nc` خوانا است، ولی مقدار نمی‌تواند `\n` داشته باشد و خطِ بی‌پایان بدون newline حافظه را بالا می‌برد مگر سقف بگذارید.

## فریم‌بندی ۲: length prefix

هر فریم یک طول ۴ بایتی big-endian است و بعد payload. خواننده از `io.ReadFull` استفاده می‌کند که تا پر شدن بافر تکرار می‌کند:

```go
var hdr [4]byte
if _, err := io.ReadFull(r, hdr[:]); err != nil { return nil, err }
n := binary.BigEndian.Uint32(hdr[:])
if n > max { return nil, fmt.Errorf("%w: %d bytes (max %d)", ErrFrameTooLarge, n, max) }
p := make([]byte, n) // فقط بعد از بررسی
_, err := io.ReadFull(r, p)
```

همان سه فرمان کار می‌کنند و همان پاسخ‌ها را می‌دهند. دو کلاینت بدخواه نشان می‌دهند جزئیات چرا مهم‌اند. یکی ۱۰۰ بایت اعلام می‌کند، ۵ بایت می‌فرستد و می‌بندد؛ دیگری حدود ۲ گیگابایت ادعا می‌کند:

```
server: read error: unexpected EOF
server: read error: frame too large: 2147483647 bytes (max 1048576)
```

`io.ErrUnexpectedEOF` یعنی جریان وسط یک فریم تمام شد (`io.EOF` ساده یعنی بین دو فریم تمام شد، که بسته‌شدن تمیز است). بررسی اندازه پیش از `make` است، پس دروغگو هیچ هزینه‌ای برایمان ندارد.

## Deadline و half-close

بدون محدودیت زمانی، کلاینتِ ساکت یک goroutine را تا ابد نگه می‌دارد. سرور پیش از هر خواندن `SetReadDeadline(now + idle)` را صدا می‌زند. با idle برابر ۳۰۰ میلی‌ثانیه و کلاینتی که وصل می‌شود و حرف نمی‌زند:

```
server: read error: read tcp 127.0.0.1:PORT->127.0.0.1:PORT: i/o timeout
client read after server gave up: EOF
```

{{< term "deadline" "Deadline" >}} زمان مطلق است، پس باید برای هر درخواست تمدید شود. ابزار دیگر {{< term "half-close" "half-close" >}} است: کلاینت بدنه را می‌فرستد، `CloseWrite()` را صدا می‌زند و باز هم پاسخ را می‌خواند. `io.ReadAll` در سرور فقط بعد از همان EOF برمی‌گردد:

```
server got 17 bytes, now replying
client got: counted 17 bytes
```

## خاموشی و تست

`Shutdown` listener را می‌بندد (پس `Accept` با `net.ErrClosed` برمی‌گردد) و با `sync.WaitGroup` منتظر اتصال‌های باز می‌ماند؛ به [خاموشی تمیز](/fa/posts/go-graceful-shutdown-workers/) و [sync، select و context](/fa/posts/go-sync-select-context/) نگاه کنید. خروجی:

```
Serve returned: <nil>
dial after shutdown: refused=true
```

یک تست `go test -race` ۲۰ کلاینت را بالا می‌آورد که هرکدام ۵۰ جفت SET/GET انجام می‌دهند؛ با race detector روشن پاس شد (`ok example.com/netkv`) و ۱۰۰۰ کلید ذخیره شد.

## همین در Python و Node

ماژول `socket` در Python پوشش نازکی روی همان فراخوانی‌هاست: `bind`، `listen`، `accept`، `recv` و `sendall`. یک echo server و کلاینت ۱۴ خطی در یک پردازه، `client got b'ping\n'` چاپ کرد. Node تابع `net.createServer` را دارد که برای هر اتصال یک callback صدا می‌زند (با [node:http](/fa/posts/node-http-server/) مقایسه کنید)؛ نسخه‌ی Node را اینجا اجرا نکردم.

## چند نکته‌ی مهم

- فرض نکنید یک `Write` برابر یک `Read` است؛ حلقه بزنید یا از `io.ReadFull` استفاده کنید.
- هر طولی را که از شبکه می‌خوانید پیش از allocate سقف‌دار کنید.
- روی هر اتصالی که کنترلش با شما نیست deadline بگذارید.
- `net.ErrClosed` را بررسی کنید تا خاموشی عادی به‌عنوان خطا لاگ نشود.
- mutex از map محافظت می‌کند؛ تست‌ها را با `-race` اجرا کنید.

## تمرین

فرمان `DEL k` را به هر دو حالت اضافه کنید. بعد خواننده‌ی فریم را طوری امتحان کنید که کلاینت header را بایت‌به‌بایت بفرستد (با حلقه و sleep) و نشان دهید هنوز کار می‌کند.

## قدم بعدی

پست بعدی «UDP و تفاوتش با TCP» است.
