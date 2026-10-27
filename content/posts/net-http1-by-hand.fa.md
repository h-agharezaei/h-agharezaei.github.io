+++
date = '2027-02-15T10:00:00+03:30'
draft = false
title = 'HTTP/1.1 با دست'
description = 'HTTP/1.1 با دست روی loopback: درخواست خام، header اجباری Host، تفاوت Content-Length و chunked، اتصال پایدار و سرور ۵۰ خطی.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "http", "http1", "sockets", "go", "chunked"]
cover = { image = "/images/covers/net-http1-by-hand.fa.png", alt = "HTTP/1.1 با دست", hiddenInSingle = true }
+++

در [پست قبل](/fa/posts/net-udp-sockets/) با datagramها آشنا شدیم و پیش‌تر در [سرور TCP](/fa/posts/net-sockets-tcp-from-scratch/) دیدیم که stream مرز پیام ندارد. {{< term "http" "HTTP" >}}/1.1 یک جواب به پرسش «پیام کجا تمام می‌شود؟» است که روی {{< term "tcp" "TCP" >}} ساخته شده. امروز آن را با بایت خام حرف می‌زنیم، بدون هیچ کتابخانه‌ی HTTP در سمت کلاینت. برای نگاه با کتابخانه به [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) و [سرور HTTP با node:http](/fa/posts/node-http-server/) سر بزنید.

> همه‌چیز روی `127.0.0.1` با port تصادفی، Go 1.26، Python 3.14 و macOS اجرا شد. هدف یک سرور `net/http` بود و کلاینت یک socket خام در Python (و `nc`). Linux را اجرا نکردم و ماشین مشغول بود، پس زمان‌سنجی ندارم. دموی کار یک پوشه‌ی مثال محلی است.

## شکل یک درخواست

```python
b"GET /hello HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
```

یک خط درخواست (متد، مقصد، نسخه)، چند خط header و یک خط خالی که هر کدام با CRLF (`\r\n`) تمام می‌شوند. جواب سرور Go (CRLF در انتهای خط‌ها نشان داده شده):

```
HTTP/1.1 200 OK\r\n
Date: Tue, 27 Oct 2026 05:50:20 GMT\r\n
Content-Length: 6\r\n
Content-Type: text/plain; charset=utf-8\r\n
Connection: close\r\n
\r\n
hello\n
```

خط وضعیت، header، خط خالی و بعد body. `nc` همین بایت‌ها را می‌گیرد، چون HTTP فقط متن روی یک {{< term "socket" "socket" >}} است.

## Host اجباری است

HTTP/1.1 داشتن `Host` را لازم می‌داند تا یک IP بتواند چند سایت را سرو کند. بدون آن این سرور جواب داد:

```
HTTP/1.1 400 Bad Request: missing required Host header\r\n
Content-Type: text/plain; charset=utf-8\r\n
Connection: close\r\n
\r\n
400 Bad Request: missing required Host header
```

## body و HEAD

برای POST عدد `Content-Length: 10` و ده بایت (`name=roham`) فرستادم. handler جواب داد `got 10 bytes: name=roham` و لاگ سرور هم `body=10 bytes` نشان داد. header طول به گیرنده می‌گوید چند بایت بخواند؛ همان ایده‌ی length-prefix در {{< term "message-framing" "message framing" >}}.

درخواست `HEAD` همان headerها از جمله `Content-Length: 6` را برگرداند ولی هیچ body نداد. طول مربوط به چیزی است که GET برمی‌گرداند.

## Chunked: framing بدون طول

وقتی اندازه از قبل معلوم نیست، پاسخ از `Transfer-Encoding: chunked` استفاده می‌کند. handler سه تکه‌ی `alpha`، `bravo-bravo` و `c` را نوشت و بعد از هرکدام flush کرد. کلاینت Python آن را دستی decode کرد: خط اندازه به hex، داده، CRLF و تا رسیدن اندازه‌ی ۰:

```
Transfer-Encoding: chunked
size line b'5\r\n' -> 5       data b'alpha'
size line b'b\r\n' -> 11      data b'bravo-bravo'
size line b'1\r\n' -> 1       data b'c'
size line b'0\r\n' -> 0       data b''
```

`b` در hex برابر ۱۱ است. این همان {{< term "chunked-encoding" "chunked encoding" >}} است و در آن پاسخ `Content-Length` وجود ندارد.

## یک اتصال، چند درخواست

اتصال‌های HTTP/1.1 به‌طور پیش‌فرض {{< term "keep-alive" "پایدار" >}} هستند. سه درخواست را روی یک socket فرستادم که سومی `Connection: close` داشت. port محلی کلاینت ۵۰۴۲۹ بود و لاگ سرور سه بار همین port را نشان داد:

```
server: GET /hello from client port 50429
server: GET /hello from client port 50429
server: GET /hello from client port 50429
```

درخواست‌های تک‌باره‌ی قبلی هرکدام port متفاوتی داشتند (50424، 50426 و 50427). بعد از جواب سوم سرور بست و `recv` مقدار `b''` برگرداند، یعنی پایان stream.

## یک سرور ۵۰ خطی

سرور فقط یک listener، یک حلقه برای خواندن خط‌ها تا خط خالی و پاسخی با `Content-Length` درست می‌خواهد:

```go
line, _ := br.ReadString('\n')          // request line
for {                                    // headers
    h, _ := br.ReadString('\n')
    if strings.TrimRight(h, "\r\n") == "" { break }
}
fmt.Fprintf(c, "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"+
    "Content-Length: %d\r\n\r\n%s", len(body), body)
```

فایل کامل (مدیریت خطا، یک goroutine برای هر اتصال و پشتیبانی از `Connection: close`) ۵۳ خط است. `curl -v --http1.1` روی آن این را چاپ کرد:

```
> GET /path?x=1 HTTP/1.1
> Host: 127.0.0.1:50433
> User-Agent: curl/8.7.1
> Accept: */*
>
< HTTP/1.1 200 OK
< Content-Type: text/plain
< Content-Length: 13
<
hi from tiny
```

سرور من همان خط درخواست و سه header را لاگ کرد. کار می‌کند، ولی body درخواست، chunked در درخواست، سقف اندازه‌ی header، timeout، pipelining و لبه‌های فراوان دیگر را نادیده می‌گیرد. برای همین در پروداکشن از `net/http` استفاده می‌کنید.

## چرا parserها باید هم‌نظر باشند

فقط یک مفهوم: اگر proxy و backend درباره‌ی اینکه `Content-Length` پایان درخواست را تعیین می‌کند یا `Transfer-Encoding` اختلاف داشته باشند، بایت‌ها می‌توانند به‌عنوان شروع درخواست دیگری خوانده شوند. این {{< term "request-smuggling" "request smuggling" >}} است. آن را نشان ندادم و جایش در سری امنیت است.

## چند نکته‌ی مهم

- خط‌ها با CRLF تمام می‌شوند و headerها با یک خط خالی؛ به `\n` تنها تکیه نکنید.
- body به `Content-Length` یا framing از نوع chunked نیاز دارد، وگرنه گیرنده پایانش را نمی‌داند.
- `Host` اجباری است؛ بدون آن انتظار 400 داشته باشید.
- از اتصال پایدار باید دقیقاً یک پیام بخوانید، نه «تا EOF».
- برای هر چیزی فراتر از یادگیری از کتابخانه‌ی HTTP واقعی استفاده کنید.

## تمرین

سرور کوچک را طوری گسترش دهید که `Content-Length` را بخواند و body را برگرداند. بعد bodyای کوتاه‌تر از ادعای header بفرستید و ببینید سرورتان در انتظار چه می‌کند. یک read deadline چه چیزی را عوض می‌کند؟

## قدم بعدی

پست بعدی «TLS و گواهی با openssl» است.
