+++
date = '2027-02-02T10:00:00+03:30'
draft = false
title = 'کلاینت async NATS JetStream در Rust'
description = 'یک Publisher و Worker با pull consumer روی JetStream در Rust با async-nats و tokio: PubAck، حذف تکراری، Nak و Term، MaxDeliver، خاموش شدن تمیز و کار با Go.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "nats", "jetstream", "async", "tokio"]
cover = { image = "/images/covers/rust-nats-async-client.fa.png", alt = "کلاینت async NATS JetStream در Rust", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-thiserror-anyhow/) خطاهای تایپ‌دار را با `thiserror` و `anyhow` در سطح برنامه دیدیم. حالا آن‌ها را روی چیزی می‌گذارم که از Go می‌شناسم: یک Publisher و یک Worker روی JetStream با retry و سقف تعداد تحویل. نسخه‌ی Go در [مقاله‌ی اول JetStream](/fa/posts/nats-jetstream-go/) و [مقاله‌ی retry و dead-letter](/fa/posts/nats-jetstream-retry-dlq/) آمده است. این مقاله هم‌ارز Rust آن‌هاست، با `async-nats` و همان Tokio که در [مقاله‌ی async](/fa/posts/rust-async-tokio/) دیدیم. قسمت جذاب آخر کار است: Worker ِRust پیام‌هایی را مصرف می‌کند که یک برنامه‌ی Go منتشر کرده.

> همه‌ی کدها را با Rust 1.90، `async-nats` نسخه‌ی 0.50.0، `tokio` نسخه‌ی 1.54.1 و یک nats-server 2.15.1 تعبیه‌شده اجرا کردم که از یک برنامه‌ی کوچک Go به صورت پروسه‌ی جدا بالا آمد. ماشین زیر بار سنگین بود (load average حدود ۱۱)، برای همین ادعایی درباره‌ی زمان نمی‌کنم.

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

`retry_on_initial_connect` باعث می‌شود کلاینت حتی اگر سرور هنوز بالا نیامده تلاش کند. آزمایشش کردم: Worker را بدون سرور اجرا کردم و چند ثانیه بعد سرور را بالا آوردم؛ Worker خودش `worker: ready` چاپ کرد. `max_reconnects(None)` یعنی تعداد reconnectهای بعدی نامحدود باشد.

ساخت stream idempotent است، مثل `AddStream` در Go ولی بی‌خطر برای صدا زدن از هر پروسه:

```rust
let js = jetstream::new(connect().await?);
js.get_or_create_stream(jetstream::stream::Config {
    name: "ORDERS".into(),
    subjects: vec!["orders.>".into()],
    ..Default::default()
}).await?;
```

## Publish: چرا دو await

```rust
let mut headers = HeaderMap::new();
headers.insert("Nats-Msg-Id", format!("rust-{i}").as_str());
let ack = js
    .publish_with_headers("orders.created", headers, body.into())
    .await?   // await اول: ارسال درخواست
    .await?;  // await دوم: منتظر PubAck سرور
```

`await` اول پیام را می‌فرستد و یک `PublishAckFuture` برمی‌گرداند. دومی منتظر **PubAck** می‌ماند، یعنی مدرک اینکه پیام ذخیره شده. این جداسازی اجازه می‌دهد چند پیام پشت‌سرهم بفرستید و ackها را بعداً جمع کنید، ولی اگر await دوم را فراموش کنید هیچ چیز تایید نشده است. چهار پیام و بعد دوباره شناسه‌ی اول را منتشر می‌کنم:

```
rust pub: id=rust-0 ok          seq=1 dup=false
rust pub: id=rust-1 flaky       seq=2 dup=false
rust pub: id=rust-2 poison      seq=3 dup=false
rust pub: id=rust-3 always-fail seq=4 dup=false
rust pub: id=rust-0 again       seq=1 dup=true
```

سرور برای حذف تکراری‌ها از هدر `Nats-Msg-Id` استفاده می‌کند: پیام تکراری دوباره ذخیره نشد و ack با `duplicate` و شماره‌ی توالی اصلی برگشت.

## Consumer و حلقه‌ی پردازش

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

`messages()` یک stream ناهمگام می‌دهد؛ پس حلقه همان `messages.next().await` از `futures::StreamExt` است. خطاها یک `enum` کوچک با `thiserror` هستند، `Transient` یا `Poison`، و هرکدام ack متفاوتی می‌گیرد:

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

(در فایل واقعی خطاهای `ack` با `anyhow!` تبدیل می‌شوند چون boxed هستند، و `delivered` از `msg.info()?.delivered` می‌آید.) متن پیام نتیجه را تعیین می‌کند: `ok` موفق می‌شود، `flaky` تا تحویل سوم fail می‌شود، `poison` هیچ‌وقت موفق نمی‌شود و `always-fail` همیشه fail می‌شود. خروجی واقعی:

```
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

(ستون زمان را حذف کرده‌ام.) `Term` پیام poison را بعد از یک تحویل تمام کرد، `flaky` در تحویل سوم موفق شد و `always-fail` به خاطر `max_deliver: 4` در تحویل چهارم متوقف شد. مثل مقاله‌ی Go، پیام در stream می‌ماند؛ فقط دیگر به این consumer تحویل داده نمی‌شود.

## خاموش شدن تمیز

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

`select!` فقط سیگنال خاموشی را با *پیام بعدی* رقابت می‌دهد. وقتی پیامی برداشته شد، پردازشش تا آخر اجرا می‌شود و بعد حلقه دوباره چک می‌کند؛ پس پیام در حال پردازش تمام و ack می‌شود. هشت پیام منتشر کردم و در حین پردازش `SIGTERM` فرستادم:

```
 seq=16 delivered=1 id=go-20 ... -> ack
 seq=17 delivered=1 id=go-21 ... -> ack
 seq=18 delivered=1 id=go-22 ... -> ack
 seq=19 delivered=1 id=go-23 ... -> ack
worker: shutdown requested
worker: bye
```

چهار پیام دیگر قبلاً دریافت شده بودند ولی ack نشدند. بعد از اجرای دوباره با `delivered=2` برگشتند (seq ‏21 و 22 و 23 و بعد 20): سرور وقتی پیام را تحویل می‌دهد شمارش می‌کند، نه وقتی شما پردازشش می‌کنید.

## Interop: Go منتشر می‌کند، Rust مصرف می‌کند

طرف Go یک برنامه‌ی کوتاه با `nats.go` نسخه‌ی v1.54.0 است که همان هدر را می‌گذارد و روی همان subject منتشر می‌کند. خروجی آن و آنچه Worker ِRust برایش چاپ کرد:

```
go pub: seq=5 dup=false
go pub: seq=6 dup=false
```
```
 seq=5 delivered=1 id=go-1 body={"id":101,"from":"go"} -> ack
 seq=6 delivered=1 id=go-2 body={"id":102,"from":"go"} -> ack
```

هیچ کار خاصی لازم نبود: stream و هدر و ack در سطح پروتکل هستند و هر دو زبان یک چیز را می‌بینند، از جمله شناسه‌ی `go-1` در `HeaderMap` ِRust.

## مقایسه با nats.go

فقط چیزهایی که مطمئنم: در `nats.go` متد `js.Publish` منتظر می‌ماند و `PubAck` را برمی‌گرداند و `PublishAsync` هم وجود دارد؛ در `async-nats` همین جداسازی در تایپ‌ها دیده می‌شود (دو await). مقاله‌ی Go از API قدیمی‌تر `JetStream()` استفاده کرد و `nats.go` یک پکیج جدیدتر به نام `jetstream` هم دارد که consumerهایش شبیه نسخه‌ی Rust است. تفاوت واقعی در مدیریت خطاست: در Rust مجبورم در تایپ‌ها تصمیم بگیرم کدام خطا `Transient` و کدام `Poison` است.

## چند نکته‌ی مهم

- تایمر تحویل از لحظه‌ی تحویل شروع می‌شود، نه شروع پردازش. در اولین اجرا، backoff اول ۳۰۰ میلی‌ثانیه بود و پردازش هم ۳۰۰ میلی‌ثانیه طول می‌کشید؛ پیام‌هایی که ack کرده بودم دوباره تحویل داده شدند. backoff اول و `ack_wait` را خیلی بیشتر از زمان انتظار در صف به‌علاوه‌ی پردازش بگذارید.
- فراموش کردن await دوم در publish یعنی هیچ تاییدی ندارید.
- `Nak(None)` ساده می‌تواند حلقه‌ی retry سریع بسازد؛ تاخیر بدهید.
- `max_deliver` باید از طول `backoff` بزرگ‌تر باشد.
- پیام‌های بافرشده‌ی ack‌نشده هم تحویل‌شده حساب می‌شوند؛ `delivered` را «تعداد تلاش‌های اجراشده» فرض نکنید.

## تمرین

1. در آخرین تحویل مجاز (`delivered == 4`) قبل از رها کردن، محتوای پیام را روی `orders.dead` منتشر کنید.
2. تاخیر `Nak` را به‌جای مقدار ثابت از روی `delivered` حساب کنید.

## قدم بعدی

مقاله‌ی بعد: trait objectها و `dyn` در Rust.
