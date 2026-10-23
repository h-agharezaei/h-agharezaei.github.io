+++
date = '2027-02-16T10:00:00+03:30'
draft = false
title = 'JetStream در پروداکشن: cluster، retention و امنیت'
description = 'اجرای JetStream با سه replica، تحمل از دست رفتن یک نود، انتخاب سیاست retention و قفل کردن دسترسی با permission و TLS، با اجرای واقعی در Go.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "cluster", "security", "production", "retention"]
cover = { image = "/images/covers/nats-jetstream-production.fa.png", alt = "JetStream در پروداکشن: cluster، retention و امنیت", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/nats-kv-object-store/) از JetStream به‌عنوان KV و ذخیره‌گاه blob استفاده کردیم. این مقاله‌ی آخرِ سری درباره‌ی چیزهایی است که وقتی JetStream از لپ‌تاپ بیرون می‌رود تغییر می‌کنند: یک سرور می‌شود سه سرور، streamها به برنامه‌ی نگهداری نیاز دارند و همه نباید اجازه‌ی publish روی همه‌جا را داشته باشند. مانیتورینگ و تست قبل از پروداکشن لازم‌اند؛ [observability](/fa/posts/nats-jetstream-observability/) و [تست](/fa/posts/nats-jetstream-testing/) را ببینید، و برای خاموش کردن تمیز workerها [graceful shutdown](/fa/posts/go-graceful-shutdown-workers/) را.

> Go 1.26، `nats-server` نسخه‌ی v2.15.1 و `nats.go` نسخه‌ی v1.54.0. همه‌ی سرورها داخل برنامه‌های نمونه embed شده‌اند و روی localhost اجرا می‌شوند. ماشین بیکار نبود، پس زمان‌بندی نمی‌دهم.

## Cluster و replica

سه سرور با معرفی یکدیگر در `Routes` یک cluster می‌سازند. هرکدام اسم و `StoreDir` جدا لازم دارد:

```go
opts := &server.Options{
	ServerName: "n1", Host: "127.0.0.1", Port: clientPort,
	JetStream: true, StoreDir: root + "/n1",
	Cluster: server.ClusterOpts{Name: "demo", Host: "127.0.0.1", Port: clusterPort},
	Routes:  server.RoutesFromStr(allThreeClusterURLs),
}
```

stream با `Replicas: 3` replicate می‌شود. هر stream یک گروه کوچک **Raft** است: یک leader نوشتن‌ها را می‌گیرد، بقیه کپی می‌کنند و نوشتن وقتی ثبت‌شده حساب می‌شود که **اکثریت** آن را داشته باشند. با سه نود، اکثریت دو تاست؛ پس می‌توانید یک نود را از دست بدهید و کار ادامه پیدا کند. با از دست دادن دو نود stream می‌ایستد، چون دیگر به اکثریت نمی‌رسد. این عمدی است: سیستم ترجیح می‌دهد نوشتن را رد کند تا اینکه دو تاریخچه‌ی متفاوت بسازد.

۱۰۰ پیام publish کردم، وقتی client به leader وصل بود leader را متوقف کردم، ۱۰۰ پیام دیگر فرستادم و بعد نود دوم را هم خاموش کردم:

```
before: msgs=100 leader=n1 replicas=[n2 current=true offline=false] [n3 current=true offline=false]
stopping leader n1
  [client] disconnected: read tcp 127.0.0.1:51843->127.0.0.1:51806: read: connection reset by peer
  [client] reconnected to n2
  publish error: context deadline exceeded
published after failover: ok=100 retried-errors=1
after 1 down: msgs=200 leader=n3 replicas=[n1 current=false offline=true] [n2 current=true offline=false]
stopping second node n2
publish with 1 of 3 up: context deadline exceeded | timeout: true | no responders: false
```

client خودش دوباره وصل شد، leader جدید (n3) انتخاب شد و تعداد پیام‌ها از ۱۰۰ دقیقاً به ۲۰۰ رسید. یک publish در زمان انتخاب leader timeout شد (timeout من ۳ ثانیه بود) و دوباره امتحانش کردم؛ پس publisher شما هم retry لازم دارد. وقتی فقط یک نود ماند، publish به‌جای موفق شدن timeout شد.

تنظیمات مهم client:

```go
nc, _ := nats.Connect(urls, nats.MaxReconnects(-1), nats.ReconnectWait(200*time.Millisecond),
	nats.ReconnectBufSize(1<<20), nats.DisconnectErrHandler(logIt))
```

`-1` یعنی هیچ‌وقت تسلیم نشو، `ReconnectBufSize` تعداد بایتی است که در زمان قطع بودن بافر می‌شود، و handler جایی است که قطعی‌ها را لاگ یا شمارش می‌کنید.

## Retention: چه چیزی در stream می‌ماند

سه سیاست، هرکدام با یک آزمایش: ۳ پیام publish کن، همه را بخوان و ack کن، بعد بشمار چه مانده.

```
LIM       after ack of all 3: msgs=3
INT       before any consumer: msgs=0
INT       after ack of all 3: msgs=0
WQ        after ack of all 3: msgs=0
WQ second overlapping consumer: nats: API error: code=400 err_code=10100 description=filtered consumer not unique on workqueue stream
```

`LimitsPolicy` (پیش‌فرض) پیام‌ها را نگه می‌دارد تا یک محدودیت آن‌ها را حذف کند، مهم نیست consumerها چه کنند. `InterestPolicy` پیام را فقط تا وقتی نگه می‌دارد که یک consumer هنوز باید ack کند؛ اگر هیچ consumer نباشد، چیزی ذخیره نمی‌شود. `WorkQueuePolicy` پیام را با اولین ack پاک می‌کند و consumerها نباید با هم همپوشانی داشته باشند.

محدودیت‌ها از دیسک محافظت می‌کنند. با `MaxMsgs: 3` و پنج publish:

```
MAXOLD: msgs=3 first_seq=3 last_seq=5
MAXNEW publish #4: nats: nats: API error: code=503 err_code=10077 description=maximum messages exceeded
MAXNEW: msgs=3 first_seq=1 last_seq=3
```

`DiscardOld` قدیمی‌ترین‌ها را دور می‌ریزد و publish هیچ‌وقت خطا نمی‌دهد. `DiscardNew` قدیمی‌ها را نگه می‌دارد و publish جدید را رد می‌کند، یعنی مشکل را به producer برمی‌گرداند. `MaxBytes` همین‌طور رفتار می‌کند (من `maximum bytes exceeded` گرفتم). با `MaxAge: time.Second` بعد از ۲ ثانیه ۳ پیام به ۰ رسید. ذخیره‌سازی `FileStorage` است (بعد از restart می‌ماند) یا `MemoryStorage`؛ حافظه را فقط برای داده‌ای بگذارید که از دست دادنش اشکالی ندارد. نمونه‌ی cluster از file storage استفاده کرد.

## امنیت

بدون تنظیمات، هر کس به پورت برسد هر کاری می‌تواند بکند. اولین قدم کاربر با permission روی subject است:

```go
{Username: "orders", Password: "orders-pw", Permissions: &server.Permissions{
	Publish:   &server.SubjectPermission{Allow: []string{"orders.>", "$JS.API.>"}},
	Subscribe: &server.SubjectPermission{Allow: []string{"_INBOX.>", "orders.>"}},
}}
```

clientهای JetStream از طریق subjectهای `$JS.API.*` با سرور حرف می‌زنند و پاسخ روی `_INBOX.>` برمی‌گردد؛ پس این permissionها هم لازم‌اند. یک reader می‌تواند فقط subjectهای مربوط به consumer را بگیرد.

```
wrong password:       nats: Authorization Violation
publish orders.new:   1 <nil>
publish billing.*:    context deadline exceeded
async error handler:  nats: permissions violation: Permissions Violation for Publish to "billing.invoice"
subscribe billing.>:  nats: permissions violation: Permissions Violation for Subscription to "billing.>"
reader create stream: context deadline exceeded
reader create consumer: <nil>
```

به نحوه‌ی ظاهر شدن publish ممنوع دقت کنید: خود فراخوانی فقط timeout می‌شود و دلیل واقعی در `ErrorHandler` اتصال می‌رسد. حتماً یکی بگذارید.

برای TLS یک CA و گواهی سرور موقت را با `crypto/x509` در خود Go ساختم و `TLSConfig` را به سرور دادم:

```
TLS, system roots:    nats: tls error: tls: failed to verify certificate: x509: “nats” certificate is not trusted
TLS, wrong CA:        nats: tls error: tls: failed to verify certificate: x509: certificate signed by unknown authority
TLS, wrong hostname:  nats: tls error: tls: failed to verify certificate: x509: certificate is valid for localhost, not wrong.example
TLS, right CA:        <nil>   (TLS 1.3)
```

verification را روشن نگه دارید؛ `InsecureSkipVerify` هم وصل می‌شود، ولی اصل کار را از بین می‌برد. NATS برای محیط‌های چند-tenant از nkeys، JWT و accountها هم پشتیبانی می‌کند؛ اینجا امتحانشان نکردم.

## چند نکته که باید حواستان باشد

- replica نسخه‌ی پشتیبان نیست. publish اشتباه یا purge هم replicate می‌شود.
- تعداد نودها را فرد بگیرید و برای هر چیز مهمی `Replicas` برابر ۳ بگذارید.
- تست نشده: نودها روی هاست یا شبکه‌ی جدا، خرابی واقعی دیسک و partition بین نودها. همه‌ی سرورها اینجا روی یک ماشین بودند.
- محدودیت‌ها را قبل از انتشار حساب کنید و `DiscardOld` یا `DiscardNew` را آگاهانه انتخاب کنید.
- به هر سرویس کمترین permission را بدهید و verification مربوط به TLS را همیشه روشن بگذارید.

## قدم بعدی

این آخرین مقاله‌ی سری NATS JetStream بود. تقویم به سری Rust برمی‌گردد و مقاله‌ی بعدی unsafe و FFI در Rust است.
