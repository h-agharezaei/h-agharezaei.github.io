+++
date = '2027-02-16T10:00:00+03:30'
draft = false
title = 'JetStream در پروداکشن: cluster، retention و امنیت'
description = 'اجرای JetStream با سه replica، تحمل از دست رفتن یک نود، انتخاب سیاست retention و قفل کردن دسترسی با permission و TLS، با اجرای واقعی در Go.'
contentType = 'engineering'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "cluster", "security", "production", "retention"]
cover = { image = "/images/covers/nats-jetstream-production.fa.png", alt = "JetStream در پروداکشن: cluster، retention و امنیت", hiddenInSingle = true }
+++

روزی را تصور کنید که تک‌سرور NATS شما به‌روزرسانی کرنل لازم دارد. تا وقتی ریبوت می‌شود هیچ‌چیز publish نمی‌شود و همه‌ی Workerها منتظر می‌مانند. یا روزی که لپ‌تاپ یک پیمانکار تازه به شبکه‌ی دفتر وصل می‌شود و به پورت NATS دسترسی دارد. بدون فایل کانفیگ، هر کسی که به آن پورت برسد می‌تواند روی هر subject publish کند، هر stream را بخواند و حذفش کند. روی لپ‌تاپ مشکلی نیست. وقتی JetStream از آنجا بیرون می‌آید مشکل است.

این آخرین مقاله‌ی سری درباره‌ی چیزهایی است که در مسیر production عوض می‌شوند. یک سرور سه‌تا می‌شود تا cluster از دست رفتن یک node را تحمل کند. streamها به یک برنامه‌ی retention نیاز دارند تا دیسک را پر نکنند. و همه نباید اجازه داشته باشند همه‌جا publish کنند، پس کاربر، دسترسی و TLS اضافه می‌کنیم. [مقاله‌ی قبل](/fa/posts/nats-kv-object-store/) JetStream را به‌عنوان ذخیره‌ی KV و blob به کار برد. مانیتورینگ و تست قبل از راه‌اندازی می‌آیند، پس [observability](/fa/posts/nats-jetstream-observability/) و [تست](/fa/posts/nats-jetstream-testing/) را ببینید. برای خاموش کردن تمیز Workerها هم [خاموشی تمیز Workerها در Go](/fa/posts/go-graceful-shutdown-workers/).

> هر سه دمو را دوباره با Go 1.27، `nats-server` نسخه‌ی v2.15.1 و `nats.go` نسخه‌ی v1.54.0 اجرا کردم. همه‌ی سرورها داخل برنامه‌های دمو تعبیه شده‌اند و فقط روی `127.0.0.1` گوش می‌دهند. (یکی از دموها در اصل سرورش را بدون host راه می‌انداخت و روی همه‌ی interfaceها گوش می‌داد. برای این اجرای مجدد یک نسخه‌ی scratch را که به 127.0.0.1 بسته بود اجرا کردم و دموی اصلی را تغییر ندادم.) ماشین بیکار نبود، پس زمان‌بندی نمی‌دهم. سرورهای سه دمو روی یک ماشین‌اند و این در چیزی که می‌توانند ثابت کنند اثر دارد: چک‌لیست آخر را ببینید.

## Cluster و replica

اول ایده. **cluster** چند سرور NATS است که از هم خبر دارند و مثل یکی عمل می‌کنند. یک stream می‌تواند روی هرکدام یک نسخه از داده‌اش را نگه دارد. تنظیمش `Replicas` است: با `Replicas: 3` stream روی سه سرور ذخیره می‌شود.

سه نسخه چطور یکسان می‌مانند؟ JetStream برای این از **{{< term "raft" "Raft" >}}** استفاده می‌کند. هر stream تکثیرشده یک گروه کوچک Raft است. یک سرور leader است و نوشتن‌ها را می‌گیرد. بقیه آنچه را leader می‌نویسد کپی می‌کنند. نوشتن وقتی تمام حساب می‌شود که **اکثریت** ({{< term "quorum" "quorum" >}}) آن را داشته باشد. با سه سرور اکثریت دو است، پس می‌توانید یک سرور را از دست بدهید و ادامه دهید. دو تا را از دست بدهید، stream می‌ایستد چون دیگر به اکثریت نمی‌رسد. این عمدی است: stream ترجیح می‌دهد نوشتن را رد کند تا اینکه به دو تاریخچه‌ی متفاوت تقسیم شود.

برای ساختن cluster سرورها یکدیگر را به‌عنوان `Routes` فهرست می‌کنند. هرکدام نام و `StoreDir` خودش را لازم دارد:

```go
opts := &server.Options{
	ServerName: "n1", Host: "127.0.0.1", Port: clientPort,
	JetStream: true, StoreDir: root + "/n1",
	Cluster: server.ClusterOpts{Name: "demo", Host: "127.0.0.1", Port: clusterPort},
	Routes:  server.RoutesFromStr(allThreeClusterURLs),
}
```

خود stream با سه replica ساخته می‌شود:

```go
js.CreateStream(ctx, jetstream.StreamConfig{Name: "ORDERS", Subjects: []string{"orders.>"},
	Replicas: 3, Storage: jetstream.FileStorage})
```

دمو به این ترتیب کار می‌کند: سه سرور را در یک process راه می‌اندازد، ۱۰۰ پیام publish می‌کند، leader را وقتی کلاینت به آن وصل است متوقف می‌کند، ۱۰۰ پیام دیگر publish می‌کند و آخر سرور دوم را متوقف می‌کند و دوباره publish می‌کند. بعد از هر قدم یک تابع کمکی وضعیت stream را چاپ می‌کند. این خروجی واقعی یک اجراست:

```text
before: msgs=100 leader=n1 replicas=[n2 current=true offline=false] [n3 current=true offline=false] 
client now connected to: n1
stopping leader n1
  [client] disconnected: EOF
  [client] reconnected to n2
published after failover: ok=100 retried-errors=0
after 1 down: msgs=200 leader=n2 replicas=[n1 current=false offline=true] [n3 current=true offline=false] 
stopping second node n3
publish with 1 of 3 up: context deadline exceeded | timeout: true | no responders: false
  [client] disconnected: EOF
```

خط‌به‌خط:

- `before`: ۱۰۰ پیام ذخیره شده. leader برابر `n1` است و هر دو follower (یعنی `n2` و `n3`) مقدار `current=true` دارند، یعنی به leader رسیده‌اند.
- `client now connected to: n1`: کاری کردم کلاینت اول به leader وصل شود تا متوقف کردن leader مجبورش کند دوباره وصل شود.
- `stopping leader n1` و بعد کلاینت چاپ می‌کند که قطع شد و خودش `reconnected to n2` شد. هر سه آدرس در فهرستش بود.
- `published after failover: ok=100 retried-errors=0`: هر ۱۰۰ پیام تازه رد شد. یک leader جدید در پس‌زمینه انتخاب شد.
- `after 1 down`: تعداد دقیقاً ۲۰۰ است، پس چیزی گم یا تکراری نشده. leader حالا `n2` است و `n1` مقدار `offline=true` دارد.
- `stopping second node n3` و `publish with 1 of 3 up: context deadline exceeded`: با یک سرور باقی‌مانده اکثریت وجود ندارد، پس publish موفق نمی‌شود و timeout می‌خورد. «no responders» نیست: stream هست و سرور هم هست، فقط نمی‌تواند commit کند.
- آخرین خط `[client] disconnected` مربوط به خاموش شدن خود دمو است.

جزئیات failover در هر اجرا فرق می‌کند. در این اجرا leader برابر `n1` بود و در اجراهای دیگر `n3` بود. در یک اجرای قبلی (اجرای اصلی این مقاله) یک publish در زمان انتخاب leader timeout خورد، چون leader جدید هنوز انتخاب نشده بود، و حلقه‌ی retry من دوباره فرستادش (timeout کلاینت ۳ ثانیه بود). در بعضی اجراها دمو هنگام شروع چند خط `retry:` هم چاپ می‌کند، تا وقتی سه سرور همدیگر را پیدا کنند. پس Publisher شما retry لازم دارد و خطای publish بلافاصله بعد از از دست رفتن یک node عادی است، نه باگ.

تنظیمات کلاینت که مهم‌اند:

```go
nc, _ := nats.Connect(urls, nats.MaxReconnects(-1), nats.ReconnectWait(200*time.Millisecond),
	nats.ReconnectBufSize(1<<20), nats.DisconnectErrHandler(logIt))
```

`-1` یعنی هرگز از اتصال دوباره دست نکش. `ReconnectWait` فاصله‌ی بین تلاش‌هاست. `ReconnectBufSize` تعداد بایت‌هایی است که کلاینت هنگام قطع بودن بافر می‌کند. handler جایی است که قطع‌ها را لاگ یا شمارش می‌کنید.

## Retention: چه چیزی در stream می‌ماند

سؤال دوم production این است که پیام‌ها تا کی می‌مانند. به‌طور پیش‌فرض stream فقط بزرگ‌تر می‌شود. **retention** قاعده‌ی این است که یک پیام کی اجازه دارد حذف شود. JetStream سه سیاست دارد و سریع‌ترین راه فهمیدنشان یک آزمایش است: ۳ پیام publish کن، همه را با یک consumer بگیر و ack کن و بشمار چه چیزی در stream مانده.

```text
LIM       published 3:        msgs=3
LIM       after ack of all 3: msgs=3
INT       before any consumer: msgs=0
INT       published 3:        msgs=3
INT       after ack of all 3: msgs=0
WQ        published 3:        msgs=3
WQ        after ack of all 3: msgs=0
WQ second overlapping consumer: nats: API error: code=400 err_code=10100 description=filtered consumer not unique on workqueue stream
```

سه stream به نام سیاستشان نام‌گذاری شده‌اند. خواندنش:

- `LimitsPolicy` (یعنی `LIM`، پیش‌فرض) پیام‌ها را نگه می‌دارد تا یک limit حذفشان کند، consumerها هرچه بکنند. بعد از ack هر سه پیام هنوز هستند.
- `InterestPolicy` (یعنی `INT`) پیام را فقط تا وقتی نگه می‌دارد که یک consumer هنوز باید ack کند. قبل از اینکه consumerی وجود داشته باشد کسی علاقه‌مند نیست، پس پیامی که آن‌وقت publish شود اصلاً ذخیره نمی‌شود (`msgs=0`). وقتی consumer هست، پیام‌ها تا ack نگه داشته می‌شوند و بعد از ack از بین می‌روند.
- `WorkQueuePolicy` (یعنی `WQ`) پیام را با اولین ack حذف می‌کند، یعنی دقیقاً یک صف کار. خط آخر محدودیتش را نشان می‌دهد: consumer دومی که فیلترش با اولی هم‌پوشانی دارد رد می‌شود، پس هر پیام فقط به یک consumer تعلق دارد.

retention تعیین می‌کند پیام کی دیگر لازم نیست. **limit**ها با تعیین اینکه وقتی stream بیش‌ازحد بزرگ شد چه می‌شود از دیسک محافظت می‌کنند. با `MaxMsgs: 3` و پنج publish، یک بار با هر سیاست discard:

```text
MAXOLD: msgs=3 first_seq=3 last_seq=5
MAXNEW publish #4: nats: nats: API error: code=503 err_code=10077 description=maximum messages exceeded
MAXNEW publish #5: nats: nats: API error: code=503 err_code=10077 description=maximum messages exceeded
MAXNEW: msgs=3 first_seq=1 last_seq=3
```

`DiscardOld` (یعنی `MAXOLD`) برای جا باز کردن قدیمی‌ترین پیام را دور می‌ریزد، پس publish هرگز شکست نمی‌خورد: شماره‌های ۳ تا ۵ را نگه داشت. `DiscardNew` (یعنی `MAXNEW`) قدیمی‌ها را نگه می‌دارد و publish جدید را رد می‌کند، که مشکل را به Publisher برمی‌گرداند: publishهای ۴ و ۵ شکست خوردند و stream هنوز شماره‌های ۱ تا ۳ را دارد. کدام درست است بستگی دارد با کدام ضرر می‌توانید کنار بیایید: از دست دادن قدیمی‌ترین داده، یا رد کردن جدیدترین.

`MaxBytes` همین‌طور رفتار می‌کند. من حد ۱ کیلوبایت، `DiscardNew` و پیام‌های ۴۰۰ بایتی را امتحان کردم:

```text
publish #3: nats: nats: API error: code=503 err_code=10077 description=maximum bytes exceeded
publish #4: nats: nats: API error: code=503 err_code=10077 description=maximum bytes exceeded
BYTES: msgs=2 bytes=842
```

دو پیام جا شد. هر پیام ذخیره‌شده کمی بیشتر از محتوایش حساب می‌شود (۸۴۲ بایت برای دو محتوای ۴۰۰ بایتی) و سومی از ۱۰۲۴ رد می‌شد، پس رد شد. `MaxAge: time.Second` پیام‌ها را با سن منقضی می‌کند:

```text
AGE right away: msgs = 3
AGE after 2s:   msgs = 0
```

Storage یا `FileStorage` است (بعد از restart می‌ماند) یا `MemoryStorage` (سریع، ولی با توقف سرور از بین می‌رود). حافظه را فقط برای داده‌ای به کار ببرید که می‌توانید از دست بدهید. دموی cluster از file storage استفاده کرد. دموی retention از حافظه استفاده کرد، چون فقط پیام‌ها را می‌شمارد.

## امنیت

برگردیم به ابتدای مقاله. بدون کانفیگ، هر کسی که به پورت برسد می‌تواند هر کاری بکند. قدم اول کاربرها با دسترسی روی subject است: هر کاربر فقط روی بعضی subjectها اجازه‌ی publish و فقط روی بعضی اجازه‌ی subscribe دارد. این یک کاربر به نام `orders` است که اجازه‌ی `orders.>` (هر subject زیر `orders.`) را دارد:

```go
{Username: "orders", Password: "orders-pw", Permissions: &server.Permissions{
	Publish:   &server.SubjectPermission{Allow: []string{"orders.>", "$JS.API.>"}},
	Subscribe: &server.SubjectPermission{Allow: []string{"_INBOX.>", "orders.>"}},
}}
```

ورودی‌های اضافه لازم‌اند چون کلاینت‌های JetStream با سرور از طریق subjectهای `$JS.API.*` حرف می‌زنند و پاسخ‌ها روی `_INBOX.>` برمی‌گردند. کلاینتی که این دسترسی‌ها را نداشته باشد حتی نمی‌تواند consumer بسازد. کاربر فقط‌خواندنی می‌تواند فقط subjectهای consumer را بگیرد. (رمزها این‌جا مقدارهای موقت دمو هستند.)

دمو با کاربرهای مختلف وصل می‌شود و کارهایی را که نباید مجاز باشند امتحان می‌کند:

```text
no credentials:       nats: Authorization Violation
wrong password:       nats: Authorization Violation
publish orders.new:   1 <nil>
publish billing.*:    context deadline exceeded
async error handler:  nats: permissions violation: Permissions Violation for Publish to "billing.invoice"
subscribe billing.>:  nats: permissions violation: Permissions Violation for Subscription to "billing.>"
reader create stream: context deadline exceeded
reader stream info:   <nil>
reader create consumer: <nil>
reader got: orders.new ack: <nil>
```

- اتصال بدون اعتبارنامه یا با رمز اشتباه رد می‌شود.
- `orders` می‌تواند `orders.new` را publish کند (ack می‌گوید شماره‌ی ترتیب ۱).
- publish کاربر `orders` روی `billing.invoice` ممنوع است. ببینید چطور ظاهر می‌شود: فراخوانی فقط timeout می‌خورد و دلیل واقعی (`Permissions Violation for Publish`) بعداً در `ErrorHandler` اتصال می‌رسد. همیشه یکی بگذارید، وگرنه فقط timeout می‌بینید.
- برای subscribe روی `billing.>` هم همین‌طور است.
- کاربر `reader` نمی‌تواند stream بسازد (فقط timeout می‌خورد؛ دمو پیام متناظر را از error handler می‌خواند و دور می‌ریزد)، ولی می‌تواند اطلاعات stream را بخواند، consumer بسازد، یک پیام بگیرد و ack کند.

دسترسی‌ها می‌گویند چه کسی چه کاری می‌تواند بکند. TLS از خود اتصال محافظت می‌کند، تا کسی در شبکه نتواند ترافیک را بخواند یا عوض کند، و کلاینت بداند با سرور واقعی حرف می‌زند. برای دمو در Go با `crypto/x509` یک مرجع صدور گواهی (CA) موقت و یک گواهی سرور ساختم و به سرور `TLSConfig` دادم. بعد چهار کلاینت با تنظیمات اعتماد متفاوت وصل می‌شوند:

```text
TLS, system roots:    nats: tls error: tls: failed to verify certificate: x509: “nats” certificate is not trusted
TLS, wrong CA:        nats: tls error: tls: failed to verify certificate: x509: certificate signed by unknown authority
TLS, wrong hostname:  nats: tls error: tls: failed to verify certificate: x509: certificate is valid for localhost, not wrong.example
TLS, right CA:        <nil>
negotiated:           TLS 1.3
skip verify (never in prod): <nil>
```

سه کلاینت اول سرور را رد می‌کنند، هرکدام به دلیلی متفاوت: گواهی از CAیی است که سیستم نمی‌شناسد، از CA دیگری است، یا برای hostname دیگری است. (عبارت دقیق پیام اول از بررسی‌کننده‌ی سیستم‌عامل می‌آید و روی سیستم‌های دیگر فرق می‌کند.) فقط کلاینتی که به CA درست اعتماد دارد وصل می‌شود و TLS 1.3 توافق کرد. خط آخر نشان می‌دهد `InsecureSkipVerify` هم وصل می‌شود، ولی کل فایده‌ی TLS را از بین می‌برد، پس بررسی را روشن نگه دارید.

NATS از nkey، اعتبارنامه‌های مبتنی بر {{< term "jwt" "JWT" >}} و accountها برای راه‌اندازی چندمستأجری هم پشتیبانی می‌کند. این‌جا امتحانشان نکردم.

## چک‌لیست قبل از راه‌اندازی

- replicaها backup نیستند. یک publish اشتباه یا یک purge هم تکثیر می‌شود.
- تعداد node فرد بگیرید و برای هر چیزی که برایتان مهم است `Replicas` برابر ۳.
- تست نشده: nodeها روی hostها یا شبکه‌های مختلف، خرابی واقعی دیسک و partition بین nodeها. همه‌ی سرورها این‌جا روی یک ماشین بودند، پس دمو انتخاب leader و failover را نشان می‌دهد، نه رفتار cluster وقتی شبکه‌ی بین nodeها قطع شود.
- limitها را قبل از راه‌اندازی اندازه بگیرید و `DiscardOld` یا `DiscardNew` را آگاهانه انتخاب کنید.
- به هر سرویس حداقل دسترسی لازم را بدهید و بررسی TLS را همیشه روشن نگه دارید.
- روی هر اتصال یک `ErrorHandler` بگذارید، چون خطاهای دسترسی به‌صورت خطای فراخوانی publish نمی‌رسند.

## قدم بعدی

این آخرین مقاله‌ی سری NATS JetStream است. سری Rust با [Unsafe و FFI در Rust](/fa/posts/rust-unsafe-ffi/) ادامه پیدا می‌کند که از Rust امن بیرون می‌رود تا C را صدا بزند و یک کتابخانه با C-ABI را در اختیار بگذارد.
