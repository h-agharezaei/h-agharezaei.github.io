+++
date = '2027-03-13T10:00:00+03:30'
draft = false
title = 'HTTP/2 و فرق‌هایش'
description = 'HTTP/2 در Go روی loopback: مذاکره‌ی ALPN، ۲۰ درخواست هم‌زمان روی یک اتصال TCP، اندازه‌گیری بایت HPACK و مقایسه‌ی h2c با HTTP/1.1.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "http2", "tls", "go", "hpack"]
cover = { image = "/images/covers/net-http2.fa.png", alt = "HTTP/2 و فرق‌هایش", hiddenInSingle = true }
+++

در پست قبلی، [TLS و گواهی با openssl](/fa/posts/net-tls-openssl/)، آخرین ایستگاه {{< term "alpn" "ALPN" >}} بود: کلاینت و سرور داخل handshake مربوط به TLS پروتکل برنامه را انتخاب می‌کنند. حالا می‌بینیم چه چیزی انتخاب می‌شود. HTTP/2 متدها، status codeها و headerهای [HTTP/1.1](/fa/posts/net-http1-by-hand/) را نگه می‌دارد، اما شکل رفت‌وآمدشان روی سیم را عوض می‌کند. معنا همان است و فقط framing فرق دارد. روی یک اتصال {{< term "tcp" "TCP" >}} کار می‌کند؛ [مدل TCP/IP](/fa/posts/net-tcp-ip-model/) را ببینید.

> همه‌چیز روی loopback و با یک گواهی خودامضای موقت (SAN برابر `localhost` و `127.0.0.1`) اجرا شد که خود برنامه‌ی demo می‌سازد؛ demo یک مثال محلی در Go است. ماشین شلوغ بود، پس فقط تعداد و بایت منتشر می‌کنم، نه زمان.

## کدام پروتکل به ما رسید؟

`net/http` در Go روی TLS خودکار HTTP/2 سرو می‌کند و client پیش‌فرض هم از آن استفاده می‌کند. handler چیزی را که سرور دیده چاپ می‌کند:

```go
fmt.Fprintf(w, "proto=%s alpn=%q\n", r.Proto, r.TLS.NegotiatedProtocol)
```

برای مجبور کردن client به HTTP/1.1، `TLSNextProto` را یک map خالی و non-nil می‌گذاریم که ارتقا به h2 را خاموش می‌کند:

```go
tr := &http.Transport{TLSClientConfig: cfg, TLSNextProto: map[string]func(string, *tls.Conn) http.RoundTripper{}}
```

خروجی واقعی:

```
== default (h2 allowed)
client resp.Proto=HTTP/2.0  ALPN="h2"
server saw: proto=HTTP/2.0 alpn="h2"
== TLSNextProto empty (HTTP/1.1 only)
client resp.Proto=HTTP/1.1  ALPN=""
server saw: proto=HTTP/1.1 alpn=""
```

در اجرای اول client هر دوی `h2` و `http/1.1` را پیشنهاد داد و سرور `h2` را برداشت. در اجرای دوم client چیزی از h2 نگفت، پس پروتکلی مذاکره نشد و HTTP/1.1 به کار رفت. هر دو با TLS 1.3 بودند (مقدار نسخه `0x0304`).

## بیست درخواست، یک اتصال

HTTP/1.1 روی هر اتصال هر بار فقط یک درخواست را جواب می‌دهد. وقتی پاسخی کند باشد، درخواست بعدیِ همان اتصال منتظر می‌ماند؛ این همان {{< term "head-of-line-blocking" "head-of-line blocking" >}} است و برای همین client چند اتصال باز می‌کند. HTTP/2 کار {{< term "multiplexing" "multiplexing" >}} می‌کند: هر درخواست یک stream شماره‌دار است و frameهایشان روی یک اتصال در هم می‌آیند.

برای اثبات، سرور اتصال‌های TCP پذیرفته‌شده را می‌شمارد و handler به نام `/barrier` هر درخواست را نگه می‌دارد تا هر ۲۰ درخواست هم‌زمان در جریان باشند. client بیست goroutine می‌فرستد:

```
HTTP/2:   TCP connections=1,  requests in flight at once=20
HTTP/1.1: TCP connections=20, requests in flight at once=20
```

کار یکی است و کد client هم یکی. در HTTP/1.1 هر درخواست هم‌زمان اتصال خودش را می‌خواست، و با آن handshake جدا برای TCP و TLS. توجه کنید که transport مربوط به HTTP/1.1 در Go سقف پیش‌فرضی برای تعداد اتصال به هر host ندارد؛ مرورگرها (طبق رویه‌ی رایج، خودم آزمایش نکردم) تعدادی کم برای هر host مجاز می‌دانند و ترفند «domain sharding» از همین‌جا آمد.

## headerها: HPACK

headerها در هر درخواست تکرار می‌شوند: cookie، user agent، accept. {{< term "hpack" "HPACK" >}} آنها را با جدولی فشرده می‌کند که دو طرف برای هر اتصال نگه می‌دارند، پس header تکراری به یک اندیس کوچک تبدیل می‌شود. اندازه‌گیری را صادقانه انجام دادم: سرور بایت‌هایی را که می‌خواند می‌شمارد. client روی یک اتصال ۵۱ درخواست `GET` پشت‌سرهم می‌فرستد، هر کدام با یک cookie چهارصدبایتی و دو header دیگر. بایت‌های بعد از درخواست اول (که handshake مربوط به TLS را هم دارد) را گرفتم و ۵۰ درخواست بعدی را شمردم:

```
HTTP/2:   1953 bytes for 50 requests = 39.1 per request
HTTP/1.1: 30500 bytes for 50 requests = 610.0 per request
```

این اعداد سربار رکوردهای TLS و در HTTP/2 چند frame کنترلی کوچک را هم دارند، پس آنها را سقف هزینه‌ی header بدانید. نسبت بزرگ است چون در HTTP/1.1 همان cookie بزرگ هر بار متن ساده فرستاده می‌شود. این فقط یک حالت مصنوعی است؛ در ترافیک واقعی سود کمتر است.

## h2c: ‏HTTP/2 بدون TLS

مرورگرها HTTP/2 را فقط روی TLS حرف می‌زنند، ولی خود پروتکل TLS را اجباری نمی‌کند. نسخه‌ی بدون رمز h2c نام دارد. از Go 1.24، `http.Protocols` آن را در دو طرف روشن می‌کند:

```go
srv.Protocols = new(http.Protocols); srv.Protocols.SetHTTP1(true); srv.Protocols.SetUnencryptedHTTP2(true)
tr.Protocols = new(http.Protocols);  tr.Protocols.SetUnencryptedHTTP2(true)
```

```
client resp.Proto=HTTP/2.0; server saw proto=HTTP/2.0 tls=false
```

بیشتر بین سرویس‌های داخلی به کار می‌آید، مثلاً پشت پروکسی‌ای که خودش TLS را تمام می‌کند.

## چه چیزهایی را اجرا نکردم

- HTTP/3 و QUIC: روی UDP سوار است ([UDP](/fa/posts/net-udp-sockets/)) و اجرایش نکردم. تا جایی که از مستندات می‌فهمم، هدفش حذف head-of-line blocking در سطح TCP است، چون در TCP یک بسته‌ی گم‌شده همه‌ی streamهای HTTP/2 را متوقف می‌کند.
- server push: در مشخصات HTTP/2 هست، ولی تا آنجا که می‌دانم مرورگرها پشتیبانی‌اش را برداشته یا غیرفعال کرده‌اند. آزمایشش نکردم.
- `curl --http2`: curl در این مک برای بررسی TLS قابل اعتماد نیست (پست قبلی را ببینید)، پس از آن استفاده نکردم.

## چند نکته‌ی مهم

- در سرویس خودتان `resp.Proto` و `r.Proto` را بررسی کنید؛ پروکسی میانی ممکن است بی‌صدا با backend شما HTTP/1.1 حرف بزند.
- یک اتصال یعنی یک جریان TCP: یک بسته‌ی گم‌شده همه‌ی درخواست‌های آن را متوقف می‌کند.
- از سر عادت برای HTTP/2 domain sharding نکنید یا همه‌چیز را bundle نکنید؛ اول اندازه بگیرید.
- سقف‌هایی مثل حداکثر streamهای هم‌زمان برای هر اتصال هست؛ موازی‌سازی نامحدود فرض نکنید.
- `TLSNextProto` را فقط وقتی لازم است HTTP/1.1 بماند عوض کنید؛ طبق مستندات Go، map خالی راه خاموش کردن h2 است.

## تمرین

demo مربوط به `/barrier` را روی ۳۰۰ درخواست هم‌زمان ببرید. حالا HTTP/2 چند اتصال TCP استفاده می‌کند؟ تنظیم حداکثر streamهای هم‌زمان سرور را در مستندات `net/http` پیدا کنید و آنچه می‌بینید توضیح دهید.

## قدم بعدی

پست بعدی WebSocket است.
