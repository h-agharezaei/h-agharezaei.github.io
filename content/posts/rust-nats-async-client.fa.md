+++
date = '2027-02-02T10:00:00+03:30'
draft = false
title = 'کلاینت async NATS JetStream در Rust'
description = 'یک Publisher و Worker با pull consumer روی JetStream در Rust با async-nats و tokio: PubAck، حذف تکراری، Nak و Term، MaxDeliver، خاموش شدن تمیز و کار با Go.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "nats", "jetstream", "async", "tokio"]
cover = { image = "/images/covers/rust-nats-async-client.fa.png", alt = "کلاینت async NATS JetStream در Rust", hiddenInSingle = true }
+++

یک رویداد منتشر می‌کنید، «سفارش ساخته شد»، و تابعتان برمی‌گردد. رویداد واقعاً ذخیره شد یا فقط از کارت شبکه‌ی شما بیرون رفت؟ و آن طرف، یک worker رویداد را می‌خواند و وسط پردازش از کار می‌افتد. رویداد گم شد یا کسی دوباره تلاش می‌کند؟ یک سیستم پیام‌رسانی باید به هر دو سؤال جواب بدهد، و جوابشان تمام دلیل استفاده از یکی ماندگار به‌جای یک فراخوانی ساده‌ی تابع است.

در این مقاله هر دو سمت را با Rust می‌سازیم: یک publisher که می‌داند پیامش ذخیره شده و یک worker که پیام شکست‌خورده را به تعداد محدود دوباره امتحان می‌کند. خطاهای دارای نوع از [خطا در اپلیکیشن واقعی: thiserror و anyhow](/fa/posts/rust-thiserror-anyhow/) اینجا کار واقعی دارند: تصمیم می‌گیرند پیام شکست‌خورده دوباره امتحان شود یا کنار برود. هم‌ارز Rust دو مقاله‌ی Go است، [یک Publisher و Worker ساده با NATS JetStream در Go](/fa/posts/nats-jetstream-go/) و [Retry و Dead-Letter Queue در NATS JetStream با Go](/fa/posts/nats-jetstream-retry-dlq/)، و روی کلاینت async به نام `async-nats` و تنظیمات Tokio از [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/) ساخته شده. در پایان worker ‏Rust پیام‌هایی را مصرف می‌کند که یک برنامه‌ی Go منتشر کرده.

> همه‌چیز را با Rust نسخه‌ی 1.90، `async-nats` نسخه‌ی 0.50.0، `tokio` نسخه‌ی 1.54.1 و یک nats-server توکار نسخه‌ی 2.15.1 اجرا کرده‌ام که با یک برنامه‌ی کوچک Go (با `nats.go` نسخه‌ی 1.54.0) به‌صورت یک پروسه‌ی جدا روی یک پورت محلی تصادفی بالا آمد. برای این نسخه‌ی مقاله همه‌ی demoها را دوباره اجرا کردم. خروجی‌های زیر از همان اجراست، با ستون زمان ابتدای خط حذف‌شده. هیچ ادعای زمانی نمی‌کنم.

## چهار کلمه که لازم دارید

درباره‌ی NATS همین‌قدر که بقیه را بخوانید. NATS یک سرور پیام است. برنامه‌ها به آن وصل می‌شوند و پیام رد و بدل می‌کنند، و هر پیام به یک **subject** فرستاده می‌شود، نامی نقطه‌دار مثل `orders.created`. NATS ساده پیام را به هر که همان لحظه گوش می‌دهد می‌رساند و فراموشش می‌کند؛ سریع است ولی ماندگار نیست.

{{< term "jetstream" "JetStream" >}} بخشی از NATS است که ذخیره‌سازی اضافه می‌کند و سه کلمه‌ی دیگر می‌آورد:

- **stream** یک log نام‌دار است که هر پیامِ منتشرشده به subject‌های مشخص را ذخیره می‌کند. مال ما `ORDERS` نام دارد و `orders.>` را نگه می‌دارد (`>` یعنی «هر subject زیر `orders.`»).
- **consumer** یک خواننده‌ی نام‌دار از یک stream است. به یاد می‌سپارد تا کجا خوانده، پس workerی که دوباره راه‌اندازی شود از همان‌جا که ایستاده ادامه می‌دهد. مال ما از نوع {{< term "durable-consumer" "durable" >}} است (جایش را حتی وقتی برنامه نیست حفظ می‌کند) و از نوع {{< term "pull-consumer" "pull" >}} (worker پیام می‌خواهد، سرور هل نمی‌دهد).
- **ack** (تأیید) جواب worker بعد از پردازش یک پیام است. پیامی که ack نشود دوباره تحویل داده می‌شود. `nak` هم هست («شکست خورد، دوباره بفرست»، اختیاری بعد از یک تأخیر) و `term` («دیگر هرگز نفرست»).

حالا کد.

## اتصال و ساخت stream

```rust
async fn connect() -> Result<async_nats::Client> {
    ConnectOptions::new()
        .name("rust-demo")
        .retry_on_initial_connect()
        .max_reconnects(None)
        .connection_timeout(Duration::from_secs(5))
        .connect(URL)
        .await
        .context("connecting to NATS")
}
```

`retry_on_initial_connect` باعث می‌شود کلاینت حتی وقتی سرور هنوز بالا نیامده تلاش کند و `max_reconnects(None)` یعنی اتصال مجدد بعدی نامحدود. اولی را امتحان کردم: worker را بدون سرور شروع کردم، چند ثانیه بعد سرور را بالا آوردم و worker خودش چاپ کرد `worker: ready`، بی‌آنکه دوباره راه‌اندازی شود.

stream با `get_or_create_stream` ساخته می‌شود که idempotent است: اگر نباشد می‌سازد و اگر باشد همان را برمی‌گرداند. مثل `AddStream` در Go است ولی صدازدنش از هر پروسه بی‌خطر است، پس هم publisher هم worker آن را صدا می‌زنند و فرقی نمی‌کند کدام اول بالا بیاید:

```rust
let js = jetstream::new(connect().await?);
js.get_or_create_stream(jetstream::stream::Config {
    name: "ORDERS".into(),
    subjects: vec!["orders.>".into()],
    ..Default::default()
}).await?;
```

## انتشار: چرا دو await

حالا سؤال اول مقاله: publisher از کجا می‌فهمد پیام ذخیره شد؟

```rust
let mut headers = HeaderMap::new();
headers.insert("Nats-Msg-Id", format!("rust-{i}").as_str());
let ack = js
    .publish_with_headers("orders.created", headers, body.into())
    .await?   // await اول: درخواست را بفرست
    .await?;  // await دوم: منتظر PubAck سرور بمان
```

`await` اول پیام را می‌فرستد و future جواب را برمی‌گرداند (یک `PublishAckFuture`). `await` دوم منتظر **PubAck** سرور می‌ماند، یعنی جواب «ذخیره‌اش کردم». فقط بعد از آن می‌دانید پیام امن است. جداکردن این دو به شما اجازه می‌دهد چند پیام را پشت هم منتشر کنید و ack‌ها را بعداً جمع کنید، که سریع‌تر است؛ اگر `await` دوم را فراموش کنید هیچ تأییدی ندارید.

header ‏`Nats-Msg-Id` توضیحی می‌خواهد. شناسه‌ای است که *خودمان* انتخاب می‌کنیم و سرور با آن تکراری‌ها را دور می‌ریزد: اگر همان id دوباره برسد (در بازه‌ی حذف تکراری stream، که طبق مستندات NATS به‌طور پیش‌فرض دو دقیقه است)، پیام بار دوم ذخیره نمی‌شود. demo چهار پیام با بدنه‌های `ok` و `flaky` و `poison` و `always-fail` منتشر می‌کند و بعد id ‏`rust-0` را دوباره می‌فرستد:

```text
rust pub: id=rust-0 ok          seq=1 dup=false
rust pub: id=rust-1 flaky       seq=2 dup=false
rust pub: id=rust-2 poison      seq=3 dup=false
rust pub: id=rust-3 always-fail seq=4 dup=false
rust pub: id=rust-0 again       seq=1 dup=true
```

`seq` جای پیام در stream است. چهار پیام اول جدیدند و شماره‌ی ۱ تا ۴ می‌گیرند. پنجمی تکراری است: سرور دوباره ذخیره‌اش نکرد و ack آن می‌گوید `dup=true` و همان sequence اصلی، یعنی ۱، را برمی‌گرداند. پس publisherی که بعد از timeout دوباره تلاش کند هرگز دو سفارش نمی‌سازد.

## consumer و حلقه‌ی پردازش

حالا سؤال دوم: پیامی که شکست می‌خورد چه می‌شود؟ قاعده‌ها در تنظیم consumer هستند:

```rust
let consumer = stream.get_or_create_consumer("rust-worker", pull::Config {
    durable_name: Some("rust-worker".into()),
    ack_policy: AckPolicy::Explicit,
    ack_wait: Duration::from_secs(5),
    max_deliver: 4,
    backoff: vec![Duration::from_secs(3), Duration::from_secs(5)],
    ..Default::default()
}).await?;
let mut messages = consumer.messages().await?;
```

- `durable_name` هویت consumer را می‌دهد، پس جایش بعد از راه‌اندازی مجدد می‌ماند.
- `AckPolicy::Explicit` یعنی هر پیام را باید کد ما یکی‌یکی تأیید کند.
- {{< term "ack-wait" "ack_wait" >}} مدتی است که سرور منتظر ack می‌ماند و بعد پیام را دوباره تحویل می‌دهد. اگر worker از کار بیفتد، همین پیام را برمی‌گرداند.
- `max_deliver: 4` سقف است: بعد از چهار بار تحویل سرور آن پیام را دیگر به این consumer نمی‌فرستد. طبق مستندات NATS، `max_deliver` باید از تعداد عضوهای `backoff` بیشتر باشد؛ اینجا ۴ از ۲ بیشتر است.
- `backoff` فهرست مدت‌های انتظار بین تحویل‌های مجدد است (۳ ثانیه، بعد ۵ ثانیه). طبق مستندات NATS جای `ack_wait` را برای زمان‌بندی تحویل مجدد می‌گیرد.

`messages()` یک stream از جنس async می‌دهد (اینجا «stream» یعنی دنباله‌ای از مقدارهایی که به‌مرور می‌رسند، نه stream در JetStream)، پس حلقه `messages.next().await` است، با `StreamExt` از crate ‏`futures`. برای هر پیام worker یک منطق کسب‌وکار ساختگی اجرا می‌کند و بعد با ack یا `nak` یا `term` جواب می‌دهد. شکست‌ها یک enum کوچک `thiserror` با دو حالت هستند، `Transient` («دوباره امتحان شاید جواب بدهد») و `Poison` («این پیام هرگز موفق نمی‌شود»، یک {{< term "poison-message" "poison message" >}})، و هر حالت به تأیید متفاوتی نگاشت می‌شود:

```rust
let action = match process(&payload, delivered).await {
    Ok(()) => { msg.ack().await?; "ack" }
    Err(ProcessError::Poison(_)) => { msg.ack_with(AckKind::Term).await?; "term" }
    Err(e @ ProcessError::Transient(_)) => {
        msg.ack_with(AckKind::Nak(Some(Duration::from_millis(500)))).await?;
        "nak"
    }
};
```

(قطعه کوتاه‌شده است. در فایل واقعی خطاهای `ack` با `anyhow!` به خطای `anyhow` تبدیل می‌شوند، چون خطاهای boxed هستند، و `delivered` از `msg.info()?.delivered` می‌آید.)

بدنه‌ی پیام تعیین می‌کند چه شود: `ok` موفق می‌شود، `flaky` تا تحویل سوم شکست می‌خورد، `poison` هرگز موفق نمی‌شود، و `always-fail` هر بار شکست می‌خورد. خروجی worker برای چهار پیام ما (عدد بعد از `delivered=` تعداد دفعاتی است که سرور آن پیام را تحویل داده):

```text
worker: ready
 seq=1 delivered=1 id=rust-0  body=ok          -> ack
 seq=2 delivered=1 id=rust-1  body=flaky       -> nak(500ms): temporary failure on attempt 1
 seq=3 delivered=1 id=rust-2  body=poison      -> term
 seq=4 delivered=1 id=rust-3  body=always-fail -> nak(500ms): temporary failure on attempt 1
 seq=2 delivered=2 id=rust-1  body=flaky       -> nak(500ms): temporary failure on attempt 2
 seq=4 delivered=2 id=rust-3  body=always-fail -> nak(500ms): temporary failure on attempt 2
 seq=2 delivered=3 id=rust-1  body=flaky       -> ack
 seq=4 delivered=3 id=rust-3  body=always-fail -> nak(500ms): temporary failure on attempt 3
 seq=4 delivered=4 id=rust-3  body=always-fail -> nak(500ms): temporary failure on attempt 4
```

پیام‌به‌پیام بخوانیمش:

- `ok` (seq ‏۱) در تحویل اول ack می‌شود و دیگر دیده نمی‌شود.
- `flaky` (seq ‏۲) دو بار با `nak` شکست می‌خورد، پس سرور بعد از تأخیر ۵۰۰ میلی‌ثانیه دوباره تحویلش می‌دهد. در تحویل سوم موفق می‌شود و ack می‌گیرد.
- `poison` (seq ‏۳) در همان تحویل اول `term` می‌گیرد. سرور هرگز دوباره نمی‌فرستدش، که درست است: امتحان پیامی که نمی‌تواند موفق شود فقط وقت تلف می‌کند.
- `always-fail` (seq ‏۴) در تحویل‌های ۱ و ۲ و ۳ و ۴ `nak` می‌خورد. بعد از تحویل ۴ برنمی‌گردد، به‌خاطر `max_deliver: 4`. مثل مقاله‌ی Go در stream می‌ماند؛ فقط دیگر به این consumer تحویل داده نمی‌شود. یک سیستم واقعی پیش از دست‌کشیدن آن را به یک جای dead-letter می‌فرستد (تمرین را ببینید).

## خاموش‌شدن مرتب

یک deploy وقتی worker وسط یک پیام است `SIGTERM` می‌فرستد. می‌خواهیم آن پیام تمام و ack شود، نه رها شود:

```rust
let mut sigterm = signal(SignalKind::terminate())?;
let mut sigint = signal(SignalKind::interrupt())?;
let shutdown = async { tokio::select! { _ = sigint.recv() => {}, _ = sigterm.recv() => {} } };
tokio::pin!(shutdown);
loop {
    let msg = tokio::select! {
        _ = &mut shutdown => break,
        next = messages.next() => match next { Some(m) => m?, None => break },
    };
    // process and ack msg ...
}
```

`select!` منتظر هر چیزی می‌ماند که اول رخ بدهد، و فقط سیگنال خاموشی را با *پیام بعدی* مسابقه می‌دهد. وقتی پیامی برداشته شد، پردازشش تا آخر اجرا می‌شود و بعد حلقه دوباره چک می‌کند، پس پیامِ در دست تمام و ack می‌شود. این همان {{< term "graceful-shutdown" "خاموش‌شدن مرتب" >}} (graceful shutdown) برای یک worker است. برای آزمایش، هشت پیام از Go منتشر کردم و وقتی worker مشغول پردازششان بود `SIGTERM` فرستادم:

```text
 seq=7 delivered=1 id=go-20 ... -> ack
 seq=8 delivered=1 id=go-21 ... -> ack
 seq=9 delivered=1 id=go-22 ... -> ack
 seq=10 delivered=1 id=go-23 ... -> ack
worker: shutdown requested
worker: bye
```

چهار پیام پردازش و ack شدند و بعد worker تمیز ایستاد. چهار پیام دیگر از قبل به کلاینت تحویل داده شده بودند ولی پردازش نشده بودند، پس ack نشدند. بعد از اینکه دوباره worker را بالا آوردم برگشتند:

```text
worker: ready
 seq=11 delivered=2 id=go-24 ... -> ack
 seq=12 delivered=2 id=go-25 ... -> ack
 seq=13 delivered=2 id=go-26 ... -> ack
 seq=14 delivered=2 id=go-27 ... -> ack
```

هیچ‌چیز گم نشد. به `delivered=2` روی پیام‌هایی که قبلاً هرگز پردازش نشده بودند دقت کنید: سرور تحویل را وقتی می‌شمارد که پیام را *بیرون می‌دهد*، نه وقتی کد شما پردازشش می‌کند. در بخش تله‌ها دوباره به آن می‌رسیم.

## هم‌کاری با Go: Go منتشر می‌کند، Rust مصرف می‌کند

سمت Go برنامه‌ای کوتاه است که با `nats.go` همان header را می‌گذارد و روی همان subject منتشر می‌کند. خروجی‌اش این است، و بعد آنچه worker در حال اجرای Rust برای آن دو پیام چاپ کرد:

```text
go pub: seq=5 dup=false
go pub: seq=6 dup=false
```

```text
 seq=5 delivered=1 id=go-1 body={"id":101,"from":"go"} -> ack
 seq=6 delivered=1 id=go-2 body={"id":102,"from":"go"} -> ack
```

به هیچ کار ویژه‌ای نیاز نبود. stream و header و ack بخشی از پروتکل NATS هستند، نه یک زبان، پس هر دو سمت یک چیز را می‌بینند، از جمله id ‏`go-1` که Go در header گذاشت و Rust از `HeaderMap` خواند.

## مقایسه با nats.go

فقط چیزهایی که از آن‌ها مطمئنم. در `nats.go`، تابع `js.Publish` تا رسیدن `PubAck` مسدود می‌ماند و کتابخانه `PublishAsync` هم دارد؛ در `async-nats` همین تقسیم در نوع‌ها دیده می‌شود، به‌شکل دو `await`. مقاله‌ی Go از API قدیمی‌تر `JetStream()` استفاده کرد و `nats.go` یک بسته‌ی جدیدتر به نام `jetstream` هم دارد که consumer‌هایش شبیه Rust هستند. فرق واقعی در API نیست، در رسیدگی به خطاست: Rust مرا مجبور کرد در نوع‌ها تصمیم بگیرم کدام خطاها `Transient` و کدام `Poison` هستند.

## تله‌های retry و تحویل مجدد

- **زمان‌سنج‌های تحویل از لحظه‌ی تحویل شروع می‌شوند، نه از لحظه‌ای که شما پردازش را شروع می‌کنید.** در اجرای اولیه‌ی خودم، اولین backoff من ۳۰۰ میلی‌ثانیه بود و پردازش هم ۳۰۰ میلی‌ثانیه طول می‌کشید، و پیام‌هایی که قبلاً ack کرده بودم دوباره تحویل شدند. اولین backoff و `ack_wait` را خیلی بالاتر از زمان انتظار پیام در صف به‌علاوه‌ی زمان پردازش نگه دارید.
- **فراموش‌کردن `await` دوم هنگام انتشار یعنی هیچ تأییدی ندارید** که پیام ذخیره شد.
- **`Nak(None)` ساده می‌تواند در یک حلقه‌ی تنگ دوباره امتحان کند.** تأخیر بدهید، همان‌طور که demo می‌دهد.
- **`max_deliver` باید از طول `backoff` بیشتر باشد،** همان‌طور که بالا گفتم.
- **پیام‌های بافرشده و ack‌نشده هم تحویل‌شده حساب می‌شوند.** همان‌طور که بعد از خاموشی دیدیم، `delivered` را «تعداد تلاش‌هایی که واقعاً اجرا شد» نخوانید.

## تمرین

۱. در آخرین تحویل مجاز (`delivered == 4`) قبل از دست‌کشیدن، بدنه را به `orders.dead` منتشر کنید.
۲. تأخیر `Nak` را از `delivered` حساب کنید، به‌جای مقدار ثابت.

## قدم بعدی

worker با یک `match` روی یک enum بین `Transient` و `Poison` انتخاب کرد. مقاله‌ی بعد، «Trait Object و dyn در Rust»، نشان می‌دهد Rust چطور همان چندریختی زمان اجرا را به دست می‌آورد که interface‌های Go مفت می‌دهند.
