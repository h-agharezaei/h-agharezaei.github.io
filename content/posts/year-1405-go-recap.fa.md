+++
date = '2027-03-16T10:00:00+03:30'
draft = false
title = 'مرور سری Go در سال ۱۴۰۵'
description = 'نقشه‌ی ۳۹ مقاله‌ی مرتبط با Go در سال ۱۴۰۵: مبانی، Go Backend، NATS JetStream و Go + Rust، به‌همراه درس‌هایی که بارها تکرار شدند.'
contentType = 'analysis'
categories = ["Meta"]
tags = ["go", "recap", "1405", "nats", "backend"]
cover = { image = "/images/covers/year-1405-go-recap.fa.png", alt = "مرور سری Go در سال ۱۴۰۵", hiddenInSingle = true }
+++

شنیده‌اید که امسال درباره‌ی Go زیاد نوشته‌ام و نمی‌دانید از کجا شروع کنید. سی‌ونه مقاله را که نمی‌شود یکی‌یکی باز کرد. این مقاله نقشه‌ی آن‌هاست: مقاله‌های Go چه چیزهایی را پوشش می‌دهند، به چه ترتیبی روی هم سوار می‌شوند، هر مقاله درباره‌ی کدام ایده است و کدام درس‌ها بارها تکرار شدند.

این ۳۹ مقاله چهار گروه‌اند: ۱۴ مقاله در Go Fundamentals، ۱۲ مقاله در Go Backend، ۹ مقاله در NATS JetStream و ۴ مقاله در Go + Rust. بیشترشان از آبان ۱۴۰۵ به بعد منتشر شده‌اند؛ دو مقاله‌ی اول NATS کمی زودتر، در مهر، آمدند. در هر گروه مقاله‌ها به ترتیب انتشار آمده‌اند و هرکدام روی قبلی سوار است. برای فهمیدن این صفحه لازم نیست هیچ‌کدامشان را خوانده باشید.

## نقشه

### Go Fundamentals (۱۴ مقاله): خود زبان

این مقاله‌ها از صفر شروع می‌کنند. فرضشان این است که برنامه‌نویسی بلدید، نه اینکه Go بلد باشید.

- [شروع کار با Go: نصب، ماژول و ابزارها](/fa/posts/go-getting-started/): Go را نصب می‌کنید، یک ماژول می‌سازید و دستورهای هرروزه را یاد می‌گیرید. Go از همان برنامه‌ی اول سخت‌گیر است: متغیر یا import استفاده‌نشده خطای کامپایل است، نه هشدار.
- [نوع‌ها، متغیرها و کنترل جریان در Go](/fa/posts/go-types-control-flow/): هر متغیر یک مقدار صفر دارد، بین نوع‌های عددی تبدیل ضمنی نداریم و `:=` در یک بلوک داخلی متغیر تازه‌ای می‌سازد که متغیر بیرونی را پنهان می‌کند.
- [توابع، defer و مدیریت خطا در Go](/fa/posts/go-functions-defer-errors/): خطا یک مقدار معمولی است که تابع برمی‌گرداند و صدازننده همان‌جا بررسی‌اش می‌کند؛ `defer` کار پاک‌سازی را انجام می‌دهد؛ اگر صدازننده ممکن است بعداً به خطای اصلی نیاز داشته باشد، خطا را با `%w` بپیچید.
- [Slice، Map و String در Go](/fa/posts/go-slices-maps-strings/): slice مثل یک پنجره روی یک آرایه است، برای همین یک sub-slice حافظه را با اصلی‌اش شریک است.
- [Struct، متد و Interface در Go](/fa/posts/go-structs-methods-interfaces/): Go کلاس ندارد و یک interface بدون اینکه هیچ نوعی اسمش را بیاورد پیاده‌سازی می‌شود. مقدار معمولی متدهایی را که pointer receiver دارند ندارد، برای همین باید `&C{}` بنویسید.
- [اشاره‌گرها و مدل حافظه در Go](/fa/posts/go-pointers-memory/): Go همیشه کپی پاس می‌دهد، اشاره‌گر به تابع اجازه می‌دهد اصل را عوض کند، و کامپایلر تصمیم می‌گیرد هر مقدار کجا بماند.
- [پکیج‌ها و ماژول‌ها: ساختار پروژه‌ی Go](/fa/posts/go-packages-modules/): پکیج یک پوشه کد است، ماژول مجموعه‌ای از پکیج‌هاست که با هم نسخه می‌گیرند، و کامپایلر خودش کنترل می‌کند چه چیزی از کجا دیده شود.
- [Goroutine و Channel در Go](/fa/posts/go-goroutines-channels/): کار هم‌زمان را چطور شروع کنیم، چرا دو goroutine که یک متغیر را دست می‌زنند بی‌هیچ خطایی جواب غلط می‌دهند، و channel و race detector چه کمکی می‌کنند.
- [sync، select و context در Go](/fa/posts/go-sync-select-context/): mutex از حافظه‌ی مشترک محافظت می‌کند، `select` هم‌زمان منتظر چند چیز می‌ماند و `context` لغو و timeout را حمل می‌کند.
- [Generics در Go](/fa/posts/go-generics/): یک تابع برای چند نوع که باز هم کامپایلر بررسی‌اش می‌کند، و اینکه کجا بهتر است سراغ generics نرویم.
- [تست در Go: table-driven و benchmark](/fa/posts/go-testing-basics/): تست و benchmark همراه خود ابزار Go می‌آیند. اگر `(cached)` دیدید یعنی Go نتیجه‌ی قبلی را دوباره به کار برده؛ `-count=1` این را خاموش می‌کند.
- [کار با فایل، io.Reader/Writer و JSON در Go](/fa/posts/go-file-io-json/): اگر کدتان را روی `io.Reader` و `io.Writer` بنویسید، همان کد با فایل و بافر و اتصال شبکه هم کار می‌کند. بسته‌ی `encoding/json` فیلدهای حرف‌کوچک (unexported) را بی‌آنکه خطایی بدهد رد می‌کند.
- [ساخت ابزار خط فرمان با Go](/fa/posts/go-cli-tool/): بسته‌ی `flag`، زیردستورها و exit code. `os.Exit` فراخوانی‌های defer را اجرا نمی‌کند، پس آن را یک‌جا نگه دارید و بگذارید تابع `run` کد خروج را برگرداند.
- [پروژه‌ی کوچک: URL shortener با Go](/fa/posts/go-mini-project-url-shortener/): یک سرویس HTTP کوچک فقط با کتابخانه‌ی استاندارد. نکته‌ی جالبش ترتیب کارها هنگام خاموش‌شدن است: اول منتظر درخواست‌های در جریان بمانید، بعد داده را ذخیره کنید.

### Go Backend (۱۲ مقاله): یک سرویس که تکه‌تکه ساخته می‌شود

بیشتر این مقاله‌ها روی همان سرویس کوچک `orders` کار می‌کنند، پس هر مقاله یک دغدغه‌ی واقعی را به کدی که می‌شناسید اضافه می‌کند.

- [ساختار پروژه و Clean Architecture در Go](/fa/posts/go-project-layout-clean-architecture/): قواعد کسب‌وکار، ذخیره‌سازی و HTTP را جدا از هم نگه دارید و بگذارید ابزار Go نشان دهد چه کسی چه چیزی را import می‌کند. برای ابزار خیلی کوچک، flat شروع کنید.
- [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/): تنظیمات را یک‌بار بخوانید، ساختاریافته لاگ کنید و تصمیم درباره‌ی لاگ و پاسخ خطا را یک‌جا، در مرز سرویس، بگیرید.
- [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/): `ListenAndServe` یک‌خطی چند تصمیم را پنهان می‌کند؛ مقاله timeout، middleware، خواندن امن JSON و خاموشی را اضافه می‌کند و نشان می‌دهد ترتیب middlewareها مهم است.
- [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/): دیتابیس فقط پیاده‌سازی دوم یک interface است که سرویس از قبل تعریف کرده. برای هر query یک deadline بگذارید.
- [تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/): اول عمداً با دو نوشتن بدون تراکنش پول گم می‌کنیم، بعد درستش می‌کنیم. تراکنش را کوتاه نگه دارید.
- [الگوهای concurrency: worker pool و errgroup](/fa/posts/go-concurrency-patterns/): کار را هم‌زمان اما محدود اجرا کنید و به هر goroutine راهی برای توقف بدهید.
- [Outbox Pattern با Postgres و NATS در Go](/fa/posts/go-outbox-pattern-nats/): هیچ تراکنشی هم دیتابیس و هم broker را پوشش نمی‌دهد، پس رویداد را در همان تراکنش سفارش می‌نویسیم و بعداً منتشرش می‌کنیم. تحویل at-least-once است و ترتیب رایگان نیست.
- [سرویس gRPC با Go](/fa/posts/go-grpc-service/): قرارداد را در یک فایل `.proto` بگذارید تا اگر اسم یک فیلد عوض شد، build بشکند نه پروداکشن. روی هر فراخوانی کلاینت deadline بگذارید.
- [Rate limit و cache در Go](/fa/posts/go-rate-limiting-caching/): یک token bucket برای هر کلاینت سرویس را از یک صدازننده‌ی پرسروصدا حفظ می‌کند و cache دیتابیس را از سؤال‌های تکراری؛ به قیمت اینکه داده ممکن است کهنه باشد.
- [پروفایلینگ با pprof در Go](/fa/posts/go-profiling-pprof/): به‌جای حدس‌زدن پیدا کنید زمان و حافظه کجا می‌رود، هر بار یک چیز را عوض کنید و قبل و بعد را مقایسه کنید.
- [Docker، CI و دیپلوی سرویس Go](/fa/posts/go-docker-ci-deploy/): باینری ایستا، image کانتینر، workflow برای CI و endpointهای سلامت. پلتفرم کانتینر را با SIGTERM متوقف می‌کند، برای همین خاموشی تمیز اینجا مهم می‌شود.
- [زمان‌بند runtime و GC در Go](/fa/posts/go-scheduler-gc-internals/): آزمایش‌های کوچک که نشان می‌دهند runtime پشت `go f()` و `make` چه می‌کند.

### NATS JetStream (۹ مقاله): پیام‌رسانی با Go

NATS JetStream یک سیستم پیام است که پیام‌ها را نگه می‌دارد، پس workerی که پایین بوده می‌تواند برگردد و از همان‌جا ادامه بدهد. این مقاله‌ها یک worker را قدم‌به‌قدم می‌سازند.

- [یک Publisher و Worker ساده با NATS JetStream در Go](/fa/posts/nats-jetstream-go/): یک publisher، یک worker و یک pull consumer با نام durable، تا وقتی worker دوباره راه می‌افتد پیامی گم نشود.
- [Retry و Dead-Letter Queue در NATS JetStream با Go](/fa/posts/nats-jetstream-retry-dlq/): تعداد تلاش‌ها را محدود کنید، بین تلاش‌ها مکث بگذارید و پیام‌های بی‌امید را کنار بگذارید. `Nak()` ساده فوراً دوباره تلاش می‌کند.
- [چند Worker روی یک Consumer و مانیتورینگ lag در JetStream](/fa/posts/nats-jetstream-scaling-lag/): با به‌اشتراک‌گذاشتن یک durable consumer worker اضافه کنید و با شمار pending ببینید صف دارد عقب می‌افتد یا نه.
- [Idempotency و معنای exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/): «exactly-once» صادقانه چه چیزی را می‌تواند تضمین کند و چرا handler باز هم باید تحمل کند که یک پیام دو بار برسد.
- [خاموشی تمیز Workerها در Go](/fa/posts/go-graceful-shutdown-workers/): با سیگنال توقف، گرفتن کار تازه را متوقف کنید، کارهای در جریان را تمام کنید و بعد خارج شوید.
- [Observability برای JetStream: متریک، لاگ و trace](/fa/posts/nats-jetstream-observability/): سه نشانه که نشان می‌دهند worker سالم است یا نه و برای یک پیام چه اتفاقی افتاده. stream مربوط به dead-letter در حالت عادی باید خالی باشد.
- [تست سرویس‌های JetStream با nats-server توکار](/fa/posts/nats-jetstream-testing/): هر تست سرور خصوصی خودش را بالا می‌آورد و به‌جای sleep ثابت منتظر یک شرط می‌ماند.
- [KV و Object Store در NATS](/fa/posts/nats-kv-object-store/): JetStream می‌تواند حالت مشترک کوچک و فایل هم نگه دارد. دیتابیس نیست.
- [JetStream در پروداکشن: cluster، retention و امنیت](/fa/posts/nats-jetstream-production/): سه سرور به‌جای یکی، یک برنامه‌ی retention و کاربر و دسترسی و TLS. replica بکاپ نیست.

### Go + Rust (۴ مقاله): دو زبان کنار هم

- [Go یا Rust؟ هرکدام برای چه کاری](/fa/posts/go-vs-rust-when-to-use/): یک اندازه‌گیری کوچک و فهرست تفاوت‌های مستند، بعد راهنمای انتخاب. روی بار کاری خودتان اندازه بگیرید.
- [ارتباط Go و Rust با gRPC](/fa/posts/go-rust-grpc-interop/): یک فایل `.proto` هر دو طرف را تولید می‌کند. قرارداد باز هم چند سؤال را بی‌جواب می‌گذارد، مثل اینکه فیلتر خالی یعنی چه.
- [صدا زدن Rust از Go با FFI](/fa/posts/go-calls-rust-ffi/): Rust را در همان پروسه و از راه قرارداد فراخوانی C صدا بزنید. حافظه را با همان allocatorی آزاد کنید که ساخته است.
- [پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS](/fa/posts/go-rust-event-pipeline-capstone/): outbox، JetStream، یک worker به زبان Rust و یک read model کنار هم، که با کشتن تکه‌ها آزموده می‌شوند. درستی از stepهایی می‌آید که تکرارشان بی‌خطر است، نه از یک کلید «exactly once».

## درس‌هایی که تکرار شدند

این‌ها نکته‌هایی‌اند که خود مقاله‌ها بارها به آن‌ها برمی‌گردند.

- **خروجی واقعی بر فرض.** در [Retry و Dead-Letter Queue در NATS JetStream با Go](/fa/posts/nats-jetstream-retry-dlq/) در اجرای من `Nak()` ساده `BackOff` را نادیده گرفت و هر سه تلاش در ثانیه‌ی صفر تمام شد.
- **تحویل at-least-once یعنی handler باید idempotent باشد.** [Idempotency و معنای exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/) نشان می‌دهد سرور ack دیرهنگام یک تحویل قدیمی را می‌پذیرد، پس ack موفق ثابت نمی‌کند که فقط شما پیام را پردازش کرده‌اید. [خاموشی تمیز Workerها در Go](/fa/posts/go-graceful-shutdown-workers/) می‌گوید خاموشی تمیز فقط بازه‌ای را که کار ممکن است نصفه قطع شود کوچک می‌کند؛ redelivery را کم می‌کند، حذف نمی‌کند، پس handler باز هم باید تکرار را تحمل کند.
- **همه‌جا deadline و لغو بگذارید.** [الگوهای concurrency: worker pool و errgroup](/fa/posts/go-concurrency-patterns/) goroutineهایی را نشان می‌دهد که `ctx.Done()` را می‌پایند و متوقف می‌شوند، و [سرویس gRPC با Go](/fa/posts/go-grpc-service/) می‌گوید همیشه برای کلاینت deadline بگذارید.
- **خطا را یک‌جا تصمیم بگیرید.** [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/) هر خطا را یک‌بار و در مرز لاگ می‌کند. [ساخت ابزار خط فرمان با Go](/fa/posts/go-cli-tool/) کد خروج را در یک جا انتخاب می‌کند.
- **قبل از تنظیم اندازه بگیرید.** [پروفایلینگ با pprof در Go](/fa/posts/go-profiling-pprof/) قبل و بعد را با بار یکسان مقایسه می‌کند، و [Go یا Rust؟ هرکدام برای چه کاری](/fa/posts/go-vs-rust-when-to-use/) می‌گوید یک microbenchmark درباره‌ی بار کاری شما مدرک نیست.

## چه چیزهایی به گفته‌ی خود مقاله‌ها هنوز کم است

این‌ها کمبودهایی‌اند که خود مقاله‌ها به آن‌ها اعتراف کرده‌اند، نه قول مقاله‌ی تازه.

- هیچ‌وقت `docker build` واقعی اجرا نشد: [Docker، CI و دیپلوی سرویس Go](/fa/posts/go-docker-ci-deploy/).
- نودهای روی میزبان‌های جدا، خرابی واقعی دیسک و partition بین نودها تست نشد: [JetStream در پروداکشن: cluster، retention و امنیت](/fa/posts/nats-jetstream-production/).
- `LISTEN/NOTIFY` در Postgres برای بیدار کردن relay امتحان نشد: [Outbox Pattern با Postgres و NATS در Go](/fa/posts/go-outbox-pattern-nats/).
- invalidationی که در یک race می‌بازد توضیح داده شد اما بازتولید نشد: [Rate limit و cache در Go](/fa/posts/go-rate-limiting-caching/).
- پروژه‌ی پایانی هیچ چیزی را درباره‌ی سرعت اندازه نمی‌گیرد، نه متریکی دارد و نه عدد throughput: [پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS](/fa/posts/go-rust-event-pipeline-capstone/).

## از کجا شروع کنم؟

اگر در Go تازه‌کارید:

1. [شروع کار با Go: نصب، ماژول و ابزارها](/fa/posts/go-getting-started/)
2. [Goroutine و Channel در Go](/fa/posts/go-goroutines-channels/)
3. [پروژه‌ی کوچک: URL shortener با Go](/fa/posts/go-mini-project-url-shortener/)

اگر می‌خواهید سرویس بسازید:

1. [ساختار پروژه و Clean Architecture در Go](/fa/posts/go-project-layout-clean-architecture/)
2. [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/)
3. [Docker، CI و دیپلوی سرویس Go](/fa/posts/go-docker-ci-deploy/)

اگر پیام‌رسانی می‌خواهید:

1. [یک Publisher و Worker ساده با NATS JetStream در Go](/fa/posts/nats-jetstream-go/)
2. [Retry و Dead-Letter Queue در NATS JetStream با Go](/fa/posts/nats-jetstream-retry-dlq/)
3. [Idempotency و معنای exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/)

بعدی: مرور سری Rust و جمع‌بندی سال ۱۴۰۵.
