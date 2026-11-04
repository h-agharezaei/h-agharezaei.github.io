+++
date = '2027-03-04T10:00:00+03:30'
draft = false
title = 'Observability در Rust با tracing'
description = 'رویداد و span ساخت‌یافته، EnvFilter، خروجی JSON و تله‌ی گم شدن span در tokio::spawn: چطور crate به نام tracing سرویس async را قابل عیب‌یابی می‌کند.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "tracing", "observability", "async", "logging"]
cover = { image = "/images/covers/rust-tracing-observability.fa.png", alt = "Observability در Rust با tracing", hiddenInSingle = true }
+++

سرویسی این را در لاگ می‌نویسد:

```text
done
```

این مال کدام درخواست بود؟ وقتی هزار درخواست هم‌زمان در جریان است، این خط به هیچ دردی نمی‌خورد. چیزی شبیه این می‌خواهید: «درخواست ۴۲، در حال کم کردن از کارت، ۳۰ میلی‌ثانیه طول کشید، با `card declined` شکست خورد». رسیدن از خط اول به جمله‌ی دوم موضوع این مقاله است.

Rust برایش crate‌ای به نام `tracing` دارد. آن را روی کدی شبیه [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/) به کار می‌بریم، درست بعد از [درون async](/fa/posts/rust-pin-future-internals/)، و همین ایده‌ها برای سرویسی مثل [ساخت API با Axum در Rust](/fa/posts/rust-http-axum-api/) هم صدق می‌کند. آخر مقاله آن را با `slog` در [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/) مقایسه می‌کنم.

> همه‌چیز را با Rust نسخه‌ی 1.90 (`rustc 1.90.0`)، edition 2024، `tracing` نسخه‌ی 0.1.44، `tracing-subscriber` نسخه‌ی 0.3.23 (با featureهای `env-filter` و `json`) و `tokio` نسخه‌ی 1.54.1 اجرا کرده‌ام، همان نسخه‌هایی که در `Cargo.lock` ‏demo قفل شده‌اند. برای این نسخه‌ی مقاله همه‌ی demoها را دوباره اجرا کردم. خروجی‌ها واقعی‌اند و رنگ با `NO_COLOR=1` خاموش بود. زمان‌ها و ترتیب خط‌ها میان taskهای هم‌زمان از اجرایی به اجرای دیگر فرق می‌کند؛ خروجی‌هایی که آن‌ها را نشان می‌دهند از اجرای اول کپی شده‌اند و در اجرای دوباره همان نوع خط‌ها را دیدم.

## چرا لاگ ساده کافی نیست

کوچک‌ترین نسخه‌ی مسئله این است. سه task هم‌زمان اجرا می‌شوند و هرکدام با `println!` سه خط چاپ می‌کند:

```rust
async fn handle(order_id: u32) {
    println!("start");
    sleep(Duration::from_millis(10 * order_id as u64)).await;
    println!("charging card");
    sleep(Duration::from_millis(10)).await;
    println!("done");
}
```

اجرا کردم و این را گرفتم:

```text
start
start
start
charging card
charging card
charging card
done
done
done
```

کدام `done` مال کدام سفارش است؟ نمی‌شود فهمید. هر سه task در هر `.await` کنترل را به هم می‌دهند و خط‌هایشان در هم بافته می‌شود، و وقتی کار واقعی داخلشان باشد ترتیب از اجرایی به اجرای دیگر فرق می‌کند. می‌شود دستی اول هر خط یک شناسه چسباند، ولی کافی است یک بار، در یک جا، فراموشش کنید؛ و همان خطی است که نیمه‌شب لازمش دارید.

راه‌حل این است که شناسه را یک بار روی یک بازه‌ی کامل از کار بگذاریم و بگذاریم هر خطِ داخلش خودش آن را با خود داشته باشد. کار span دقیقاً همین است.

## رویداد و span

`tracing` دو مفهوم پایه دارد:

- **رویداد** (event) یک نقطه در زمان است. همان چیزی است که قبلاً «خط لاگ» می‌نامیدید: `info!`، `warn!`، `debug!`.
- {{< term "tracing-span" "span" >}} بازه‌ای از زمان است با یک نام و چند فیلد. هر رویدادی داخلش اتفاق بیفتد فیلدهای span را خودکار با خود دارد. به مهر روی یک پوشه فکر کنید: هر برگه‌ای که داخل پوشه بگذارید همان مهر را می‌خورد.

هر دو می‌توانند **فیلد** داشته باشند: مقدارهای نام‌دار مثل `order_id=42` که جدا از متن پیام می‌مانند. «ساخت‌یافته» اینجا یعنی همین. یک ابزار بعداً می‌تواند همه‌ی خط‌های دارای `order_id=42` را پیدا کند، بی‌آنکه یک جمله را تجزیه کند.

اول رویدادها با فیلد:

```rust
let order = Order { id: 42, total: 19.5 };   // derives Debug
let user = "roham";
info!(order_id = order.id, "created");
info!(%user, ?order, "details");
debug!(step = "validate", "checking stock");
warn!(retry_in = ?Duration::from_millis(250), "payment slow");
```

`order_id = order.id` یک فیلد با نام صریح ثبت می‌کند. `%user` متغیر `user` را با پیاده‌سازی `Display` ثبت می‌کند و `?order` متغیر `order` را با `Debug`. متن داخل گیومه خود پیام است.

این ماکروها فقط اعلام می‌کنند که اتفاقی افتاده. تا برنامه یک {{< term "tracing-subscriber" "subscriber" >}} نصب نکند چیزی چاپ نمی‌شود؛ subscriber بخشی است که رویدادها را می‌گیرد و تصمیم می‌گیرد با آن‌ها چه کند. ساده‌ترین نوعش در کنسول چاپ می‌کند و ما یک فیلتر به آن می‌دهیم که متغیر محیطی `RUST_LOG` را می‌خواند:

```rust
tracing_subscriber::fmt()
    .with_env_filter(EnvFilter::from_default_env())
    .init();
```

رویدادها سطح دارند، از مهم‌ترین تا کم‌اهمیت‌ترین: `error`، `warn`، `info`، `debug`، `trace`. فیلتر همان را نگه می‌دارد که بخواهید. `RUST_LOG=info` یعنی «`info` و هر چه مهم‌تر از آن»؛ `RUST_LOG=info,basic=debug` یعنی «به‌طور کلی `info`، ولی برای crate با نام `basic` (باینری demo ما) تا `debug`».

همین برنامه را سه‌جور اجرا کردم. بدون `RUST_LOG` فیلتر خالی است و اصلاً چیزی چاپ نشد. با `RUST_LOG=info` فقط خط‌های `info` و `warn` آمدند. با `RUST_LOG=info,basic=debug`:

```text
2026-10-23T21:26:02.055509Z  INFO basic: created order_id=42
2026-10-23T21:26:02.055634Z  INFO basic: details user=roham order=Order { id: 42, total: 19.5 }
2026-10-23T21:26:02.055669Z DEBUG basic: checking stock step="validate"
2026-10-23T21:26:02.055694Z  WARN basic: payment slow retry_in=250ms
2026-10-23T21:26:02.055723Z DEBUG basic::other: inside module other
2026-10-23T21:26:02.055744Z  INFO basic::other: module other done
```

هر خط زمان، سطح، ماژولی که لاگ کرده (`basic` یا `basic::other`، یعنی تابعی در یک ماژول demo)، پیام و بعد فیلدها را دارد. به `user=roham` (از `%user`) و `order=Order { id: 42, total: 19.5 }` (از `?order`) توجه کنید. در demo یک خط `trace!("very noisy")` هم هست که هیچ‌وقت نمی‌آید: trace پایین‌تر از debug است و حتی با این تنظیم هم پنهان می‌ماند. فیلتر موقع شروع برنامه خوانده می‌شود، پس جزئیات را با عوض کردن متغیر کم و زیاد می‌کنید، بدون کامپایل دوباره.

## span روی تابع‌های async

رویداد تنها مسئله‌ی ابتدای مقاله را حل نمی‌کند. حالا به span نیاز داریم. ساده‌ترین راه attribute به نام `#[instrument]` است: کل تابع را در یک span هم‌نام تابع می‌پیچد و آرگومان‌ها را فیلد می‌کند. دو تابع demo اینجاست، `handle` و `charge` که آن صدا می‌زند (بدنه‌ی `handle` به یک کامنت کوتاه شده):

```rust
#[instrument(skip(token), fields(user = "roham", amount_cents = field::Empty), err)]
async fn charge(order_id: u32, token: &str) -> Result<(), PaymentError> {
    sleep(Duration::from_millis(10)).await;
    Span::current().record("amount_cents", 1000 + order_id as u64);
    info!("charging card");
    if order_id == 3 { return Err(PaymentError("card declined")); }
    Ok(())
}

#[instrument]
async fn handle(order_id: u32) { /* info!("start"); sleep; charge(...).await; info!("done") */ }
```

گزینه‌های `charge` چهار کار می‌کنند:

- `skip(token)` آرگومان `token` را از فیلدها بیرون نگه می‌دارد. به‌طور پیش‌فرض همه‌ی آرگومان‌ها با `Debug` ثبت می‌شوند و راز جایش در لاگ نیست.
- `fields(user = "roham")` یک فیلد اضافه می‌کند.
- `amount_cents = field::Empty` فیلدی را بدون مقدار رزرو می‌کند. چند خط بعد `Span::current().record(...)` آن را پر می‌کند، که وقتی مقدار را وسط کار می‌فهمید به کار می‌آید.
- `err` یعنی «اگر این تابع `Err` برگرداند، آن را به‌صورت رویداد `ERROR` ثبت کن».

demo سه `handle` را هم‌زمان با `JoinSet` اجرا می‌کند و سفارش ۳ با `card declined` شکست می‌خورد. خروجی (زمان‌ها حذف شده):

```text
INFO handle{order_id=3}: start
INFO handle{order_id=1}: start
INFO handle{order_id=2}: start
INFO handle{order_id=1}:charge{order_id=1 user="roham" amount_cents=1001}: charging card
INFO handle{order_id=1}: done
INFO handle{order_id=2}:charge{order_id=2 user="roham" amount_cents=1002}: charging card
INFO handle{order_id=2}: done
INFO handle{order_id=3}:charge{order_id=3 user="roham" amount_cents=1003}: charging card
ERROR handle{order_id=3}:charge{order_id=3 user="roham" amount_cents=1003}: error=card declined
WARN handle{order_id=3}: order failed error=card declined
```

به ابتدای هر خط نگاه کنید. `handle{order_id=1}` خود span است و فیلدها داخل آکولادند. `handle{order_id=1}:charge{...}` یعنی «span به نام `charge` که داخل span به نام `handle` برای سفارش ۱ در حال اجراست». خط‌ها هنوز قاطی‌اند و سفارش ۳ قبل از سفارش ۱ شروع شده، ولی حالا هر خط می‌گوید مال کیست. دو خط آخر کل داستان سفارش شکست‌خورده را می‌گویند: `ERROR` از `charge` آمد (به‌لطف `err`) و بعد `handle` نوشت `order failed`.

ثمره‌ی اصلی همین است. span در هر `.await` همراه task می‌ماند، حتی وقتی runtime کار را بین threadها جابه‌جا می‌کند، و لازم نیست شناسه را دستی از تابعی به تابع دیگر پاس بدهید.

## خروجی JSON

کنسول برای خود شماست. سامانه‌ی جمع‌آوری لاگ می‌خواهد ماشین خط‌ها را بخواند. `.init()` را با `.json().init()` عوض کنید تا هر رویداد یک شیء JSON شود. این همان خط `ERROR` بالاست:

```text
{"timestamp":"2026-10-23T21:25:56.264438Z","level":"ERROR","fields":{"error":"card declined"},"span":{"amount_cents":1003,"order_id":3,"user":"roham","name":"charge"},"spans":[{"order_id":3,"name":"handle"},{"amount_cents":1003,"order_id":3,"user":"roham","name":"charge"}]}
```

`fields` فیلدهای خود رویداد است، `span` درونی‌ترین span است و `spans` کل زنجیره از بیرون به درون. حالا یک ابزار لاگ می‌تواند بدون هیچ تجزیه‌ی متنی بر اساس `order_id` فیلتر کند.

## تله‌ی tokio::spawn

span همراه task می‌ماند، ولی `tokio::spawn` یک task تازه می‌سازد. task ساخته‌شده با spawn یک task مستقل در سطح بالاست و span کدی را که آن را ساخته به ارث نمی‌برد. این درخواستی است که یک audit پس‌زمینه spawn می‌کند:

```rust
let span = info_span!("request", request_id = "req-7");
async {
    info!("handling");
    tokio::spawn(background_audit()).await.unwrap();   // lost context
    info!("responded");
}.instrument(span).await;
```

(`.instrument(span)` کل بلوک async را داخل span اجرا می‌کند و از trait به نام `Instrument` می‌آید.) خروجی:

```text
INFO request{request_id="req-7"}: handling
INFO audit written
INFO request{request_id="req-7"}: responded
```

خط `audit written` شناسه‌ی درخواست ندارد. اگر شب آن audit شکست بخورد، نمی‌فهمید از کدام درخواست بوده. راه‌حل این است که span فعلی را خودتان به future ساخته‌شده بدهید، با همان `.instrument(...)`:

```rust
tokio::spawn(background_audit().instrument(tracing::Span::current()))
```

```text
INFO request{request_id="req-7"}: handling
INFO request{request_id="req-7"}: audit written
INFO request{request_id="req-7"}: responded
```

حالا هر سه خط `request_id="req-7"` را دارند.

## زمان‌سنجی span

span می‌داند کی باز شده و کی بسته شده، پس می‌تواند بگوید کار چقدر طول کشید. `.with_span_events(FmtSpan::CLOSE)` باعث می‌شود subscriber موقع بسته شدن span یک خط اضافه چاپ کند. تابع demo ۵۰ میلی‌ثانیه می‌خوابد و بعد ۲۰ میلی‌ثانیه CPU را مشغول می‌کند. میانگین load این ماشین هنگام اجرای دوباره حدود ۳٫۸ بود، پس اعداد را تقریبی بدانید. این خط از اجرای اول است (load حدود ۳):

```text
INFO work: close time.busy=20.1ms time.idle=52.9ms
```

`busy` زمانی است که future واقعاً در حال poll شدن، یعنی اجرای کد، بوده: همان ۲۰ میلی‌ثانیه‌ی چرخیدن. `idle` زمان انتظار بین pollهاست: همان ۵۰ میلی‌ثانیه خواب به‌اضافه‌ی کمی انحراف timer. در اجرای دوباره `busy` باز هم `20.1ms` بود و `idle` کمی بیشتر، `58.2ms`، که با ماشین پرمشغله جور است.

## فراتر از کنسول

ارسال span‌ها به Jaeger یا هر backend مبتنی بر OpenTelemetry با افزودن یک layer دیگر به نام `tracing-opentelemetry` به همین subscriber انجام می‌شود. اینجا فقط اشاره می‌کنم و اجرایش نکردم.

مقایسه با Go: `log/slog` لاگ ساخت‌یافته‌ی key-value می‌دهد و `With` فیلد را به logger می‌چسباند، اما مفهوم span ندارد. برای ربط دادن خط‌ها بین goroutineها باید خودتان logger یا context را پاس بدهید. در `tracing` این اطلاعات را خود span حمل می‌کند.

## تله‌های tracing در کد async

- **`tokio::spawn` span را گم می‌کند.** task ساخته‌شده بدون span والد شروع می‌شود و خط‌هایش شناسه ندارند. از `.instrument(Span::current())` استفاده کنید، مثل بالا.
- **`#[instrument]` پیش‌فرض همه‌ی آرگومان‌ها را با `Debug` ثبت می‌کند.** این می‌تواند یک توکن را فاش کند یا در هر فراخوانی یک بافر بزرگ چاپ کند. برای رازها و مقدارهای بزرگ `skip` بگذارید.
- **guard مربوط به `Span::enter()` را در طول `.await` نگه ندارید.** guard span را روی thread فعلی فعال علامت می‌زند. وقتی task معلق شود و task دیگری روی همان thread اجرا شود، ممکن است span به کار اشتباهی نسبت داده شود. از `#[instrument]` یا `.instrument(span)` استفاده کنید که در هر poll وارد span می‌شوند و خارج می‌شوند.
- **بدون `RUST_LOG` (یا یک directive پیش‌فرض) فیلتر `EnvFilter` چیزی چاپ نمی‌کند.** شبیه باگ لاگ‌گیری به نظر می‌رسد، ولی فیلتر دارد همان کاری را می‌کند که به آن گفته‌اید.
- **زمان `FmtSpan::CLOSE` را سرنخ بدانید، نه benchmark.** یک اجرا روی ماشینی را اندازه می‌گیرد که شاید مشغول بوده.

## تمرین

دور handler خودتان یک span با فیلد `request_id` بگذارید، از داخلش یک task پس‌زمینه spawn کنید و ببینید خط‌هایش شناسه را دارند. بعد به JSON تغییر دهید و خروجی را با همان شناسه فیلتر کنید.

## قدم بعدی

«الگوی Type-State و طراحی API در Rust» یک قدم پیش از هر خط log می‌رود: کد کردن حالت‌های معتبر در type تا استفاده‌ی غلط اصلاً کامپایل نشود.
