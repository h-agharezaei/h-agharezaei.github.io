+++
date = '2027-01-01T10:00:00+03:30'
draft = false
title = 'Observability برای JetStream: متریک، لاگ و trace'
description = 'به یک Worker جت‌استریم در Go متریک Prometheus، لاگ ساختاریافته‌ی slog و انتقال trace context از طریق هدرهای NATS اضافه می‌کنیم؛ با خروجی واقعی.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "observability", "metrics", "tracing", "prometheus", "slog", "opentelemetry"]
cover = { image = "/images/covers/nats-jetstream-observability.fa.png", alt = "Observability برای JetStream: متریک، لاگ و trace", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-graceful-shutdown-workers/) Worker یاد گرفت تمیز خاموش شود، ولی وقتی چیزی خراب می‌شود هنوز بیشتر حدس می‌زنیم. صف این وضع را بدتر می‌کند: Publisher و Worker مستقیم با هم حرف نمی‌زنند، پس یک پیام کند یا ناموفق ردپای روشنی باقی نمی‌گذارد. در این مقاله سه سیگنال معمول را اضافه می‌کنیم: **متریک** (الان سالم است؟)، **لاگ** (برای این پیام چه اتفاقی افتاد؟) و **trace** (یک درخواست چطور از Publisher به Worker رسید؟).

دمو یک برنامه‌ی Go محلی است: سرور `nats-server` نسخه‌ی v2.15.1 تعبیه‌شده با JetStream، `nats.go` نسخه‌ی v1.54.0، `prometheus/client_golang` نسخه‌ی v1.23.2 و OpenTelemetry نسخه‌ی v1.43.0 روی Go 1.26. یک Publisher حدود ۶۰ کار در ثانیه برای یک Worker سریال می‌فرستد و هر دهمین کار در تحویل اول fail می‌شود. درباره‌ی خود اعداد lag به [مقاله‌ی مقیاس‌پذیری](/fa/posts/nats-jetstream-scaling-lag/) و درباره‌ی `slog` به [مقاله‌ی کانفیگ، لاگ و خطا](/fa/posts/go-config-logging-errors/) نگاه کن.

## متریک: سه سؤال، سه ابزار

```go
processed = prometheus.NewCounterVec(prometheus.CounterOpts{
    Name: "worker_messages_total"}, []string{"result"})
duration = prometheus.NewHistogram(prometheus.HistogramOpts{
    Name: "worker_process_seconds",
    Buckets: []float64{0.01, 0.025, 0.05, 0.1, 0.25}})
pending = prometheus.NewGauge(prometheus.GaugeOpts{Name: "consumer_num_pending"})
ackPending = prometheus.NewGauge(prometheus.GaugeOpts{Name: "consumer_num_ack_pending"})
```

Worker بعد از هر پیام `processed.WithLabelValues(result).Inc()` و `duration.Observe(...)` را صدا می‌زند؛ `result` یکی از `ok`، `failed` یا `redelivered_ok` است (از `Metadata().NumDelivered` تشخیص می‌دهیم). Gaugeهای lag را خود Worker تغییر نمی‌دهد. یک goroutine جدا هر نیم‌ثانیه `ConsumerInfo` را نمونه‌برداری می‌کند:

```go
for ctx.Err() == nil {
    if ci, err := js.ConsumerInfo("JOBS", "w"); err == nil {
        pending.Set(float64(ci.NumPending))
        ackPending.Set(float64(ci.NumAckPending))
    }
    time.Sleep(500 * time.Millisecond)
}
```

وقتی Worker زیر بار بود این را اجرا کردم: `curl localhost:9100/metrics | grep -E '^(worker_|consumer_)'` (کوتاه‌شده):

```text
consumer_num_ack_pending 5
consumer_num_pending 162
worker_messages_total{result="failed"} 17
worker_messages_total{result="ok"} 155
worker_messages_total{result="redelivered_ok"} 13
worker_process_seconds_bucket{le="0.025"} 75
worker_process_seconds_bucket{le="0.05"} 181
worker_process_seconds_bucket{le="+Inf"} 185
worker_process_seconds_sum 5.429341470999997
worker_process_seconds_count 185
```

هر متریک به کدام سؤال جواب می‌دهد:

- **کند است؟** هیستوگرام. جمع تقسیم بر تعداد میانگین است (اینجا حدود ۲۹ میلی‌ثانیه) و از bucketها درصدی‌ها (percentile) را می‌گیری. (ماشین مشغول بود و load average نزدیک ۱۰ بود، پس زمان‌های مطلق را تقریبی بدان.)
- **fail می‌شود؟** شمارنده. سهم `failed` و `redelivered_ok` نسبت به کل.
- **صف دارد پر می‌شود؟** `consumer_num_pending`. عدد ۱۶۲ یعنی Publisher از این یک Worker سریع‌تر است. `consumer_num_ack_pending` فرق دارد: پیام‌هایی که تحویل شده‌اند ولی هنوز ack نشده‌اند؛ مقدار بالا و ثابت یعنی handlerهای گیرکرده یا کند.

مراقب label باش: هر ترکیب متفاوت label یک time series جداست. اگر با شناسه‌ی پیام یا کاربر label بزنی، تعداد series بی‌نهایت می‌شود و می‌تواند Prometheus را از کار بیندازد. labelها را به مجموعه‌های کوچک و ثابت (مثل `result` و `subject`) محدود کن و جزئیات هر پیام را در لاگ و trace بگذار.

## لاگ: یک خط JSON برای هر تلاش

از `log/slog` با handler از نوع JSON استفاده می‌کنم و مشخصات پیام را یک بار با `log.With(...)` اضافه می‌کنم: `trace_id`، `stream_seq`، `delivery` و `subject`. فیلد `time` فقط برای کوتاه ماندن خروجی حذف شده. خط‌های واقعی:

```json
{"level":"ERROR","msg":"processing failed, will retry","trace_id":"9b02d5c801cb5d9b61787ea8fcf97a45","stream_seq":10,"delivery":1,"subject":"jobs.run","err":"upstream timeout"}
{"level":"INFO","msg":"processed","trace_id":"9b02d5c801cb5d9b61787ea8fcf97a45","stream_seq":10,"delivery":2,"subject":"jobs.run","result":"redelivered_ok"}
```

`stream_seq` پیام را در استریم مشخص می‌کند و `delivery` می‌گوید این چندمین تلاش است. با `trace_id` می‌شود یک پیام را در تلاش‌های مختلف دنبال کرد.

## Trace: انتقال context از طریق هدر NATS

پیام‌های NATS هدر دارند، پس هدر `traceparent` استاندارد W3C جای طبیعی‌ای است. Publisher یک span می‌سازد و context را در `msg.Header` می‌گذارد (inject)؛ Worker آن را بیرون می‌کشد (extract) و یک span فرزند می‌سازد. من از SDK واقعی OpenTelemetry با exporter استاندارد خروجی (stdout) استفاده کردم، نه هدر دست‌ساز؛ فرمت‌دهی را `propagation.TraceContext{}` انجام می‌دهد:

```go
// publisher
pctx, span := tracer.Start(ctx, "publish jobs.run", trace.WithSpanKind(trace.SpanKindProducer))
msg := nats.NewMsg("jobs.run")
otel.GetTextMapPropagator().Inject(pctx, propagation.HeaderCarrier(msg.Header))
js.PublishMsg(msg)
span.End()

// worker
pctx := otel.GetTextMapPropagator().Extract(ctx, propagation.HeaderCarrier(m.Header))
_, span := tracer.Start(pctx, "process jobs.run", trace.WithSpanKind(trace.SpanKindConsumer))
```

`nats.Header` از نوع `map[string][]string` است، پس مستقیم با `propagation.HeaderCarrier` کار می‌کند. Worker برای کار شماره‌ی ۱۰ trace `9b02d5c8...` را لاگ کرد و وقتی خروجی exporter را روی همین شناسه فیلتر کردم:

```text
publish jobs.run  span 3eb7ba61771c4eb6  parent 0000000000000000
process jobs.run  span 2ae949162024bb0b  parent 3eb7ba61771c4eb6
process jobs.run  span 5c206277c8cc28eb  parent 3eb7ba61771c4eb6
```

شناسه‌ی trace در دو طرف یکی است، و تلاش اول ناموفق و تلاش دوم هر دو span فرزند همان span انتشار هستند.

## روی چه چیزی alert بگذاریم

بدون اختراع عدد: روی `consumer_num_pending` که به‌جای آرام گرفتن مدام بالا می‌رود (Worker نمی‌رسد)، روی بالا رفتن سهم `failed` و `redelivered_ok`، و روی هر پیام داخل استریم dead-letter از [مقاله‌ی retry](/fa/posts/nats-jetstream-retry-dlq/) که عمق آن در حالت عادی باید صفر باشد. آستانه‌ها را از baseline خودت انتخاب کن.

## چند نکته‌ی مهم

- `ConsumerInfo` یک درخواست به سرور است؛ تقریباً هر ثانیه نمونه بگیر، نه برای هر پیام.
- Gaugeها فقط به اندازه‌ی فاصله‌ی نمونه‌برداری تازه‌اند.
- bucketهای هیستوگرام موقع ساخت ثابت می‌شوند؛ آن‌ها را حول تأخیر واقعی خودت انتخاب کن.
- انتقال هدر فقط وقتی مفید است که هر مرحله آن را extract کند؛ سرویسی که دوباره publish می‌کند و هدرها را کپی نمی‌کند، trace را می‌شکند.
- exporter استاندارد خروجی برای دمو است؛ در production به یک collector صادر می‌کنند.

## قدم بعدی

همه‌ی این‌ها روی سرور تعبیه‌شده اجرا شد و همین تست کردن را هم آسان می‌کند. مقاله‌ی بعد درباره‌ی تست سرویس‌های JetStream با nats-server تعبیه‌شده است.
