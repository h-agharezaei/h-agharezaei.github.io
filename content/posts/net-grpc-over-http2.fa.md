+++
date = '2027-04-01T10:00:00+03:30'
draft = false
title = 'gRPC روی HTTP/2'
description = 'gRPC روی HTTP/2 و loopback: هدرها و trailerهای واقعی، پیشوند ۵ بایتی پیام، grpc-timeout، کدهای وضعیت، یک اتصال و GOAWAY.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "grpc", "http2", "protobuf", "go", "deadline"]
cover = { image = "/images/covers/net-grpc-over-http2.fa.png", alt = "gRPC روی HTTP/2", hiddenInSingle = true }
+++

در [پست قبل](/fa/posts/net-websocket/) یک اتصال را به کانال پیام تبدیل کردیم. {{< term "grpc" "gRPC" >}} راه دیگری می‌رود: داخل {{< term "http" "HTTP" >}}/2 می‌ماند، مثل [HTTP/2 و آنچه عوض می‌شود](/fa/posts/net-http2/)، و چند قاعده رویش اضافه می‌کند. [سرویس gRPC در Go](/fa/posts/go-grpc-service/) و [Go و Rust روی gRPC](/fa/posts/go-rust-grpc-interop/) سمت API را گفتند؛ اینجا فقط بایت‌ها را نگاه می‌کنم.

> همه‌چیز روی `127.0.0.1` با port تصادفی (چاپ نشده)، Go 1.26، macOS و grpc-go نسخه‌ی v1.84.0 اجرا شد. کد {{< term "protobuf" "protobuf" >}} همان قرارداد `orders` پست قبلی است (کپی شده)، با یک سرور کوچک تازه. Linux، grpc-web و load balancing را اجرا نکردم. ماشین مشغول بود، پس تعداد دارم و زمان‌سنجی ندارم.

## یک کلاینت خام HTTP/2

برای دیدن سیم، کلاینتی نوشتم که از grpc-go استفاده نمی‌کند: preface اتصال HTTP/2 را می‌نویسد، یک فریم HEADERS و یک DATA می‌فرستد و جواب را چاپ می‌کند (فریم‌ها با `golang.org/x/net/http2`). یک فراخوانی، `GetOrder` با id برابر `o1`:

```
request body bytes: 00 00 00 00 04 0a 02 6f 31
  HEADERS stream=1 end_stream=false
      :status: 200
      content-type: application/grpc
  DATA stream=1 end_stream=false len=23
      prefix=00 00 00 00 12 -> compressed=0 length=18
      message=0a026f31120361646118e209220470616964
    decoded: id="o1" customer="ada" cents=1250
  HEADERS stream=1 end_stream=true
      grpc-status: 0
      grpc-message: 
```

درخواستی که فرستادم یک POST به مسیر `/orders.v1.OrdersService/GetOrder` بود (package، service، method) با `content-type: application/grpc` و `te: trailers`. پس فراخوانی gRPC یک درخواست معمولی HTTP/2 است. پاسخ هدرها، یک فریم DATA و یک HEADERS پایانی با `end_stream=true` است. آن بلوک آخر {{< term "http-trailers" "trailer" >}} است: نتیجه‌ی فراخوانی آنجا می‌آید چون بعد از آخرین پیام معلوم می‌شود.

## پیشوند ۵ بایتی

هر پیام داخل DATA با پنج بایت شروع می‌شود: یک بایت برای پرچم فشرده‌سازی (۰ یعنی فشرده نیست) و یک طول ۴ بایتی big-endian. این دوباره {{< term "message-framing" "message framing" >}} است: فریم‌های DATA در HTTP/2 مرز پیام را رعایت نمی‌کنند و gRPC طول خودش را اضافه می‌کند. در درخواست بعد از `00 00 00 00 04` بایت‌های `0a 02 6f 31` می‌آیند: فیلد ۱ در protobuf، طول ۲، متن `o1`. طول پاسخ یعنی 0x12 = 18 با ۲۳ بایت DATA منهای پیشوند جور است.

## کلاینت واقعی چه می‌فرستد

حالا همان فراخوانی از کلاینت معمولی grpc-go، در حالی که سمت سرور بایت‌های دریافتی را ثبت و رمزگشایی می‌کرد:

```
HEADERS stream=1 end_stream=false
    :method: POST
    :scheme: http
    :path: /orders.v1.OrdersService/GetOrder
    :authority: <addr>
    content-type: application/grpc
    user-agent: grpc-go/1.84.0
    te: trailers
    grpc-timeout: 1999472u
DATA stream=1 end_stream=true len=9
```

`:authority` آدرس و port است که با `<addr>` عوضش کردم. کلاینت deadline ۲ ثانیه داشت و هدر `1999472u` می‌گوید: زمان باقی‌مانده به میکروثانیه (`u`؛ `m` میلی‌ثانیه و `S` ثانیه است). {{< term "deadline" "deadline" >}} به‌صورت مدت نسبی می‌رود تا سرور بتواند کارش را لغو کند و باقی‌مانده را به فراخوانی بعدی بدهد.

## کدهای وضعیت

وضعیت HTTP همیشه 200 است. نتیجه‌ی واقعی `grpc-status` در trailer است. سفارش ناموجود یک پاسخ **Trailers-Only** بود: یک فریم HEADERS با `end_stream=true` که هم بخش HTTP و هم وضعیت را دارد:

```
HEADERS stream=1 end_stream=true
    :status: 200
    content-type: application/grpc
    grpc-status: 5
    grpc-message: order zzz not found
```

فراخوانی‌های واقعی با کلاینت Go، با چاپ نام `codes.Code`:

```
not found:         NotFound | "order zzz not found"
deadline:          DeadlineExceeded | "context deadline exceeded"
nothing listening: Unavailable
not implemented:   Unimplemented
```

حالت deadline با ۱۵۰ میلی‌ثانیه روی handlerی بود که ۳ ثانیه صبر می‌کند. وقتی از کلاینت خام `grpc-timeout: 150m` فرستادم، trailer نیامد و فقط `RST_STREAM stream=1 code=CANCEL` آمد: این سرور با تمام شدن زمان stream را لغو کرد و کتابخانه‌ی کلاینت تایمر منقضی‌شده‌ی خودش را به `DeadlineExceeded` تبدیل می‌کند. `Unavailable` یعنی اصلاً اتصالی ساخته نشد.

## یک اتصال، فراخوانی‌های زیاد

روی یک اتصال کلاینت: ۵۰ فراخوانی unary پشت‌سرهم، یک server stream با ۵ پیام و بعد ۲۰ فراخوانی هم‌زمان. listener تعداد accept را شمرد و فریم‌های HEADERS کلاینت را رمزگشایی کردم:

```
tcp connections accepted: 1
server-stream messages received: 5 (one RPC)
HTTP/2 streams opened: 71 (highest id 141)
```

یک اتصال {{< term "tcp" "TCP" >}}، ۷۱ فراخوانی، ۷۱ stream. شماره‌ی streamهای شروع‌شده از کلاینت فرد و صعودی است، برای همین ۱۴۱. server stream یک stream بود با پنج فریم DATA که هرکدام پیشوند ۵ بایتی خودش را دارد و در پایان یک بلوک trailer. این همان {{< term "multiplexing" "multiplexing" >}} است. SETTINGS در HTTP/2 می‌تواند تعداد streamهای هم‌زمان هر اتصال را محدود کند؛ پیش‌فرض‌های grpc-go را امتحان نکردم، پس مستندات را ببینید.

## GOAWAY هنگام توقف تمیز

یک server stream (۵ پیام با فاصله‌ی ۱۵۰ میلی‌ثانیه) شروع کردم، وسطش `GracefulStop` را صدا زدم و فریم‌های سرور را ثبت کردم:

```
GOAWAY last_stream=2147483647 code=NO_ERROR
PING ack=false
PING ack=true
GOAWAY last_stream=1 code=NO_ERROR
DATA stream=1 ...   (messages 2 to 5)
HEADERS stream=1 end_stream=true
    grpc-status: 0
```

سرور اول یک {{< term "goaway" "GOAWAY" >}} می‌فرستد که چیزی را محدود نمی‌کند، بعد یک رفت‌وبرگشت PING و بعد GOAWAY دوم که stream شماره‌ی ۱ را آخرین streamی اعلام می‌کند که پردازش می‌شود. stream در حال اجرا تمام شد، هر ۵ پیام رسید و فراخوانی تازه بعدش `Unavailable` گرفت. همان ایده‌ی [graceful shutdown برای workerهای Go](/fa/posts/go-graceful-shutdown-workers/) است.

## چند نکته‌ی مهم

- در کلاینت همیشه deadline بگذارید؛ بدون آن فراخوانی می‌تواند تا ابد منتظر بماند.
- وضعیت را از trailer بخوانید، نه از وضعیت HTTP.
- پروکسی میانی باید HTTP/2 و trailer را پشتیبانی کند وگرنه gRPC خراب می‌شود.
- `Unavailable` را با احتیاط و فقط برای فراخوانی‌های idempotent دوباره امتحان کنید.

## تمرین

دمو را عوض کنید که پیامی ۱ کیلوبایتی بفرستد و فریم‌های DATA را ببینید. آیا طول پیشوند با مجموع اندازه‌ی فریم‌ها برابر است؟

## قدم بعدی

پست بعدی «load balancer لایه‌ی ۴ و ۷» است.
