+++
date = '2027-03-16T10:00:00+03:30'
draft = false
title = 'مرور سری Go در سال ۱۴۰۵'
description = 'نقشه‌ی ۳۹ مقاله‌ی مرتبط با Go در سال ۱۴۰۵: مبانی، Go Backend، NATS JetStream و Go + Rust، به‌همراه درس‌هایی که بارها تکرار شدند.'
categories = ["Meta"]
tags = ["go", "recap", "1405", "nats", "backend"]
cover = { image = "/images/covers/year-1405-go-recap.fa.png", alt = "مرور سری Go در سال ۱۴۰۵", hiddenInSingle = true, hiddenInList = true }
+++

نقشه‌ای برای کسانی که تازه به مقاله‌های Go رسیده‌اند و مرجعی برای خودم. ۳۹ مقاله‌ی مرتبط با Go داریم: ۱۴ مقاله در Go Fundamentals، ۱۲ در Go Backend، ۹ در NATS JetStream و ۴ در Go + Rust. بیشترشان از آبان ۱۴۰۵ منتشر شده‌اند؛ دو مقاله‌ی اول NATS پیش از آن تقویم‌اند.

## نقشه

**Go Fundamentals (۱۴)**

- [شروع کار با Go: نصب، ماژول و ابزارها](/fa/posts/go-getting-started/): `go run .` کل پکیج را می‌سازد
- [نوع‌ها، متغیرها و کنترل جریان در Go](/fa/posts/go-types-control-flow/): `:=` در بلوک داخلی shadow می‌کند
- [توابع، defer و مدیریت خطا در Go](/fa/posts/go-functions-defer-errors/): خطا را با `%w` wrap کنید
- [Slice، Map و String در Go](/fa/posts/go-slices-maps-strings/): sub-sliceها حافظه را share می‌کنند
- [Struct، متد و Interface در Go](/fa/posts/go-structs-methods-interfaces/): pointer receiver به `&C{}` نیاز دارد
- [اشاره‌گرها و مدل حافظه در Go](/fa/posts/go-pointers-memory/): قبل از بهینه‌سازی اندازه بگیرید
- [پکیج‌ها و ماژول‌ها: ساختار پروژه‌ی Go](/fa/posts/go-packages-modules/): زیاده‌ساختاردهی تله است
- [Goroutine و Channel در Go](/fa/posts/go-goroutines-channels/): پایان هر goroutine را بدانید
- [sync، select و context در Go](/fa/posts/go-sync-select-context/): context آرگومان اول است
- [Generics در Go](/fa/posts/go-generics/): از کد concrete شروع کنید
- [تست در Go: table-driven و benchmark](/fa/posts/go-testing-basics/): `-count=1` کش را دور می‌زند
- [کار با فایل، io.Reader/Writer و JSON در Go](/fa/posts/go-file-io-json/): فیلد حرف‌کوچک بی‌صدا رد می‌شود
- [ساخت ابزار خط فرمان با Go](/fa/posts/go-cli-tool/): exit code را یک‌جا تعیین کنید
- [پروژه‌ی کوچک: URL shortener با Go](/fa/posts/go-mini-project-url-shortener/): فقط در خاموشی تمیز ذخیره

**Go Backend (۱۲)**

- [ساختار پروژه و Clean Architecture در Go](/fa/posts/go-project-layout-clean-architecture/): flat شروع کنید
- [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/): خطا را یک‌بار لاگ کنید
- [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/): ترتیب middleware مهم
- [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/): برای هر درخواست deadline
- [تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/): تراکنش را کوتاه نگه دارید
- [الگوهای concurrency: worker pool و errgroup](/fa/posts/go-concurrency-patterns/): به goroutine راه خروج بدهید
- [Outbox Pattern با Postgres و NATS در Go](/fa/posts/go-outbox-pattern-nats/): ترتیب رایگان نیست
- [سرویس gRPC با Go](/fa/posts/go-grpc-service/): همیشه deadline کلاینت
- [Rate limit و cache در Go](/fa/posts/go-rate-limiting-caching/): cache با تازگی معامله می‌کند
- [پروفایلینگ با pprof در Go](/fa/posts/go-profiling-pprof/): قبل و بعد با بار یکسان
- [Docker، CI و دیپلوی سرویس Go](/fa/posts/go-docker-ci-deploy/): `latest` نسخه نیست
- [زمان‌بند runtime و GC در Go](/fa/posts/go-scheduler-gc-internals/): قبل از `GOGC` پروفایل بگیرید

**NATS JetStream (۹)**

- [یک Publisher و Worker ساده با NATS JetStream در Go](/fa/posts/nats-jetstream-go/): Pull Consumer با نام durable
- [Retry و Dead-Letter Queue در NATS JetStream با Go](/fa/posts/nats-jetstream-retry-dlq/): `Nak()` ساده فوراً retry می‌کند
- [چند Worker روی یک Consumer و مانیتورینگ lag در JetStream](/fa/posts/nats-jetstream-scaling-lag/): هشدار روی رشد pending
- [Idempotency و معنای exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/): handler باید تکرار را تحمل کند
- [خاموشی تمیز Workerها در Go](/fa/posts/go-graceful-shutdown-workers/): کار در جریان را تمام کنید
- [Observability برای JetStream: متریک، لاگ و trace](/fa/posts/nats-jetstream-observability/): عمق dead-letter صفر باشد
- [تست سرویس‌های JetStream با nats-server توکار](/fa/posts/nats-jetstream-testing/): به‌جای sleep منتظر شرط
- [KV و Object Store در NATS](/fa/posts/nats-kv-object-store/): دیتابیس نیست
- [JetStream در پروداکشن: cluster، retention و امنیت](/fa/posts/nats-jetstream-production/): replica بکاپ نیست

**Go + Rust (۴)**

- [Go یا Rust؟ هرکدام برای چه کاری](/fa/posts/go-vs-rust-when-to-use/): روی بار خودتان اندازه بگیرید
- [ارتباط Go و Rust با gRPC](/fa/posts/go-rust-grpc-interop/): معنای مقدار خالی را بنویسید
- [صدا زدن Rust از Go با FFI](/fa/posts/go-calls-rust-ffi/): با allocator سازنده آزاد کنید
- [پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS](/fa/posts/go-rust-event-pipeline-capstone/): درستی از stepهای idempotent می‌آید

## درس‌هایی که تکرار شدند

- **خروجی واقعی بر فرض.** در [Retry و Dead-Letter Queue در NATS JetStream با Go](/fa/posts/nats-jetstream-retry-dlq/) در اجرای من `Nak()` ساده `BackOff` را نادیده گرفت.
- **at-least-once یعنی idempotent.** [Idempotency و معنای exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/) ack دیرهنگام را پذیرفته‌شده نشان می‌دهد. [خاموشی تمیز Workerها در Go](/fa/posts/go-graceful-shutdown-workers/) می‌گوید فقط redelivery را کم می‌کند.
- **deadline و cancellation همه‌جا.** [الگوهای concurrency: worker pool و errgroup](/fa/posts/go-concurrency-patterns/) مراقب `ctx.Done()` است؛ [سرویس gRPC با Go](/fa/posts/go-grpc-service/) deadline می‌گذارد.
- **خطا را یک‌جا تصمیم بگیرید.** [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/) در مرز لاگ می‌کند؛ [ساخت ابزار خط فرمان با Go](/fa/posts/go-cli-tool/) exit code را یک‌بار انتخاب می‌کند.
- **قبل از تنظیم اندازه بگیرید.** [پروفایلینگ با pprof در Go](/fa/posts/go-profiling-pprof/) با بار یکسان مقایسه می‌کند؛ [Go یا Rust؟ هرکدام برای چه کاری](/fa/posts/go-vs-rust-when-to-use/) می‌گوید یک microbenchmark مدرک نیست.

## چه چیزی را بعد اضافه می‌کنم

کمبودها به قول خود مقاله‌ها:

- build واقعی Docker نشد: [Docker، CI و دیپلوی سرویس Go](/fa/posts/go-docker-ci-deploy/).
- چندمیزبانی، خرابی دیسک و partition تست نشد: [JetStream در پروداکشن: cluster، retention و امنیت](/fa/posts/nats-jetstream-production/).
- `LISTEN/NOTIFY` امتحان نشد: [Outbox Pattern با Postgres و NATS در Go](/fa/posts/go-outbox-pattern-nats/).
- race در invalidation بازتولید نشد: [Rate limit و cache در Go](/fa/posts/go-rate-limiting-caching/).
- throughput و متریک اندازه‌گیری نشد: [پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS](/fa/posts/go-rust-event-pipeline-capstone/).

## از اینجا کجا برویم

تازه‌کار در Go:

1. [شروع کار با Go: نصب، ماژول و ابزارها](/fa/posts/go-getting-started/)
2. [Goroutine و Channel در Go](/fa/posts/go-goroutines-channels/)
3. [پروژه‌ی کوچک: URL shortener با Go](/fa/posts/go-mini-project-url-shortener/)

ساخت سرویس:

1. [ساختار پروژه و Clean Architecture در Go](/fa/posts/go-project-layout-clean-architecture/)
2. [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/)
3. [Docker، CI و دیپلوی سرویس Go](/fa/posts/go-docker-ci-deploy/)

پیام‌رسانی:

1. [یک Publisher و Worker ساده با NATS JetStream در Go](/fa/posts/nats-jetstream-go/)
2. [Retry و Dead-Letter Queue در NATS JetStream با Go](/fa/posts/nats-jetstream-retry-dlq/)
3. [Idempotency و معنای exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/)

بعدی: مرور سری Rust و جمع‌بندی سال ۱۴۰۵.
