+++
date = '2027-01-01T10:00:00+03:30'
draft = false
title = 'Observability برای JetStream: متریک، لاگ و trace'
description = 'به یک Worker جت‌استریم در Go متریک Prometheus، لاگ ساختاریافته‌ی slog و انتقال trace context از طریق هدرهای NATS اضافه می‌کنیم؛ با خروجی واقعی.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "observability", "metrics", "tracing", "prometheus", "slog", "opentelemetry"]
cover = { image = "/images/covers/nats-jetstream-observability.fa.png", alt = "Observability برای JetStream: متریک، لاگ و trace", hiddenInSingle = true }
+++

فرض کنید یک Worker صف یک هفته است که بی‌سروصدا کار می‌کند. صبح دوشنبه یکی متوجه می‌شود ایمیل‌های «بعد از ثبت‌نام» یک ساعت دیر می‌رسند. Worker از کار نیفتاده و در هیچ لاگی خطایی نیست. فقط عقب افتاده است: پیام‌ها سریع‌تر از آنچه Worker بتواند برسد می‌آمدند و صف هر دقیقه کمی بلندتر می‌شد. هیچ‌کس به همان یک عددی نگاه نمی‌کرد که این را نشان می‌داد.

صف این جور مشکل‌ها را راحت پنهان می‌کند. Publisher و Worker مستقیم با هم حرف نمی‌زنند، پس یک پیام کند یا ناموفق ردپای روشنی باقی نمی‌گذارد. Worker [مقاله‌ی قبل](/fa/posts/go-graceful-shutdown-workers/) حالا تمیز خاموش می‌شود، ولی این به ما نمی‌گوید در حین کار چه می‌کند. در این مقاله سه سیگنال معمول را اضافه می‌کنیم که این را نشان می‌دهند:

- **متریک** می‌گوید «الان سالم است؟» عددهایی هستند که در طول زمان نمونه‌برداری می‌شوند.
- **لاگ** می‌گوید «برای این پیام چه اتفاقی افتاد؟» خط‌های متنی‌اند، یکی برای هر رویداد.
- **trace** می‌گوید «یک درخواست چطور از Publisher به Worker رسید؟» کار انجام‌شده در دو طرف را به یک داستان وصل می‌کند.

> دمو یک برنامه‌ی Go محلی است. دوباره با Go 1.27 اجرایش کردم: سرور `nats-server` نسخه‌ی v2.15.1 تعبیه‌شده با {{< term "jetstream" "JetStream" >}}، `nats.go` نسخه‌ی v1.54.0، `prometheus/client_golang` نسخه‌ی v1.23.2 و OpenTelemetry نسخه‌ی v1.43.0. یک Publisher حدود ۶۰ کار در ثانیه برای یک Worker می‌فرستد که هر بار یک کار را انجام می‌دهد و برای هر کار به‌طور تصادفی ۵ تا ۴۹ میلی‌ثانیه می‌خوابد. هر دهمین کار در تحویل اول fail می‌شود. برنامه ۹ ثانیه اجرا می‌شود و هرچه پایین می‌بینید خروجی واقعی آن است.

درباره‌ی اینکه consumer چیست و اعداد lag از کجا می‌آیند، [مقاله‌ی مقیاس‌پذیری](/fa/posts/nats-jetstream-scaling-lag/) را ببینید. درباره‌ی `slog` هم [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/).

## متریک: سه سؤال، سه ابزار

قبل از کد، ایده را ساده بگویم. متریک عددی است که برنامه آن را به‌روز نگه می‌دارد و یک سیستم مانیتورینگ (اینجا Prometheus) هر چند ثانیه یک بار آن را می‌خواند. چون بارها خوانده می‌شود، می‌شود آن را در طول زمان رسم کرد و رویش هشدار گذاشت. Prometheus چند نوع متریک دارد و ما سه‌تایشان را لازم داریم:

- **counter** (شمارنده) فقط بالا می‌رود: «تا الان چند پیام پردازش شده». معمولاً به سرعت رشدش نگاه می‌کنند.
- **gauge** هم بالا می‌رود و هم پایین: «همین الان چند پیام منتظر است».
- **histogram** مشاهده‌ها را در bucket (سطل) می‌شمارد، مثلاً «چند کار تا ۲۵ میلی‌ثانیه طول کشید، چند کار تا ۵۰ میلی‌ثانیه و...». از روی bucketها می‌شود یک {{< term "percentile" "صدک" >}} تخمین زد، مثل «۹۵٪ کارها کمتر از ۵۰ میلی‌ثانیه طول کشیدند».

Worker ما از هر کدام یکی لازم دارد:

```go
processed = prometheus.NewCounterVec(prometheus.CounterOpts{
    Name: "worker_messages_total"}, []string{"result"})
duration = prometheus.NewHistogram(prometheus.HistogramOpts{
    Name: "worker_process_seconds",
    Buckets: []float64{0.01, 0.025, 0.05, 0.1, 0.25}})
pending = prometheus.NewGauge(prometheus.GaugeOpts{Name: "consumer_num_pending"})
ackPending = prometheus.NewGauge(prometheus.GaugeOpts{Name: "consumer_num_ack_pending"})
```

Worker بعد از هر پیام `processed.WithLabelValues(result).Inc()` و `duration.Observe(...)` را صدا می‌زند. label به نام `result` یکی از `ok`، `failed` یا `redelivered_ok` است و Worker آن را از `Metadata().NumDelivered` تشخیص می‌دهد، یعنی از اینکه سرور این پیام را تا الان چند بار تحویل داده. label به نام `result` یک شمارنده را به سه series تقسیم می‌کند: چند پیام موفق شد، چند پیام fail شد و چند پیام در تلاش دوم موفق شد.

دو gauge مربوط به lag فرق دارند. Worker نمی‌داند پشت سرش چند پیام منتظر است، ولی سرور می‌داند. پس یک goroutine جدا هر نیم‌ثانیه با `ConsumerInfo` از سرور می‌پرسد:

```go
for ctx.Err() == nil {
    if ci, err := js.ConsumerInfo("JOBS", "w"); err == nil {
        pending.Set(float64(ci.NumPending))
        ackPending.Set(float64(ci.NumAckPending))
    }
    time.Sleep(500 * time.Millisecond)
}
```

`NumPending` تعداد پیام‌هایی از stream است که سرور هنوز به consumer تحویل نداده. `NumAckPending` تعداد پیام‌هایی است که تحویل داده شده‌اند ولی هنوز ack نگرفته‌اند.

وقتی برنامه کار می‌کرد، endpoint متریک‌ها را با `curl 127.0.0.1:<port>/metrics | grep -E '^(worker_|consumer_)'` خواندم. این خروجی واقعی است، حدود ثانیه‌ی ششم اجرا (bucketهای `0.1` و `0.25` را که هر دو ۱۹۱ بودند، مثل `+Inf`، حذف کردم):

```text
consumer_num_ack_pending 5
consumer_num_pending 139
worker_messages_total{result="failed"} 17
worker_messages_total{result="ok"} 160
worker_messages_total{result="redelivered_ok"} 14
worker_process_seconds_bucket{le="0.01"} 22
worker_process_seconds_bucket{le="0.025"} 89
worker_process_seconds_bucket{le="0.05"} 188
worker_process_seconds_bucket{le="+Inf"} 191
worker_process_seconds_sum 5.329840419
worker_process_seconds_count 191
```

خط‌به‌خط بخوانیم.

- `consumer_num_pending 139`: ۱۳۹ پیام در stream منتظرند. Publisher حدود ۶۰ پیام در ثانیه می‌فرستد و یک Worker با ۵ تا ۴۹ میلی‌ثانیه برای هر کار به این سرعت نمی‌رسد، پس این عدد تا پایان اجرا بالاتر می‌رود. این همان سیگنال «Worker عقب افتاده» از ابتدای مقاله است.
- `consumer_num_ack_pending 5`: پنج پیام تحویل داده شده‌اند و هنوز ack نگرفته‌اند. یکی‌شان همان پیامی است که الان در حال پردازش است. فکر می‌کنم بیشتر بقیه پیام‌های ناموفقی هستند که صبر یک‌ثانیه‌ی `NakWithDelay` را می‌گذرانند تا سرور دوباره تحویلشان بدهد، چون شمارنده‌ها ۱۷ شکست و فقط ۱۴ تلاش مجدد را نشان می‌دهند. gauge هر نیم‌ثانیه نمونه‌برداری می‌شود، پس ممکن است کمی کهنه‌تر از شمارنده‌ها باشد.
- `worker_messages_total`: در مجموع ۱۹۱ پیام. ۱۷ پیام در تحویل اول fail شدند، ۱۶۰ پیام موفق شدند و ۱۴ تا از پیام‌های ناموفق در تلاش مجدد موفق شده بودند. ۳ تای دیگر هنوز منتظر تلاش مجدد بودند.
- bucketها تجمعی‌اند: `le="0.05"` یعنی «حداکثر ۰٫۰۵ ثانیه طول کشید» و همه‌ی کارها تا آن حد را می‌شمارد. پس ۱۸۸ کار از ۱۹۱ کار حداکثر ۵۰ میلی‌ثانیه طول کشیدند و ۸۹ کار حداکثر ۲۵ میلی‌ثانیه. برای صدک ۹۵ تقریبی، ۹۵٪ از ۱۹۱ را حساب کنید، یعنی حدود ۱۸۲، و اولین bucketی را پیدا کنید که این‌قدر کار در خودش دارد: bucket ۰٫۰۵. یعنی «۹۵٪ کارها حداکثر ۵۰ میلی‌ثانیه طول کشیدند».
- `sum / count` میانگین است: ۵٫۳۳ ثانیه تقسیم بر ۱۹۱ حدود ۲۸ میلی‌ثانیه می‌شود. انتظارش را هم داشتیم، چون handler بین ۵ و ۴۹ میلی‌ثانیه می‌خوابد. ماشین هنگام اجرا مشغول بود، برای همین عدد دقیق تأخیر منتشر نمی‌کنم؛ شمارش‌ها بخش قابل‌اعتماد هستند.

حالا هر متریک به کدام سؤال جواب می‌دهد:

- **کند است؟** هیستوگرام.
- **fail می‌شود؟** شمارنده: سهم `failed` و `redelivered_ok` از کل.
- **صف دارد پر می‌شود؟** `consumer_num_pending`. `consumer_num_ack_pending` بالا که پایین نمی‌آید مشکل دیگری است: پیام‌هایی که تحویل داده شده‌اند و هیچ‌وقت ack نمی‌گیرند، یعنی handlerهای گیرکرده یا کند.

یک دام درباره‌ی label: هر ترکیب متفاوت از مقدار labelها یک **time series** جداست، یعنی یک خط جدا که Prometheus باید نگه دارد. اگر با شناسه‌ی پیام یا کاربر label بزنید، تعداد series بی‌نهایت رشد می‌کند و می‌تواند Prometheus را از کار بیندازد. labelها را به مجموعه‌های کوچک و ثابت مثل `result` و `subject` محدود کنید و جزئیات هر پیام را در لاگ و trace بگذارید.

## لاگ: یک خط JSON برای هر تلاش

متریک می‌گوید چیزی خراب است، ولی نمی‌گوید کدام پیام. برای این به لاگ نیاز داریم. من از `log/slog` با handler از نوع JSON استفاده می‌کنم که هر خط لاگ را یک شیء JSON می‌نویسد، پس سیستم لاگ می‌تواند روی هر فیلد جست‌وجو کند. ترفند این است که مشخصات پیام را یک بار با `log.With(...)` اضافه کنیم تا هر خط آن پیام آن‌ها را داشته باشد: `trace_id`، `stream_seq` (جای پیام در stream)، `delivery` (این چندمین تلاش است) و `subject`. فیلد `time` فقط برای کوتاه ماندن خروجی حذف شده.

این خط‌ها واقعی‌اند و مال کار شماره‌ی ۱۰ همین اجرا هستند. اولی تلاش اول ناموفق است و دومی تلاش مجدد، حدود یک ثانیه بعد، وقتی در این فاصله چند کار دیگر پردازش شده بود:

```json
{"level":"ERROR","msg":"processing failed, will retry","trace_id":"bf9fafe748b0075f7053c4cf8e65c3d3","stream_seq":10,"delivery":1,"subject":"jobs.run","err":"upstream timeout"}
{"level":"INFO","msg":"processed","trace_id":"bf9fafe748b0075f7053c4cf8e65c3d3","stream_seq":10,"delivery":2,"subject":"jobs.run","result":"redelivered_ok"}
```

`stream_seq` پیام را مشخص می‌کند و `delivery` می‌گوید به کدام تلاش نگاه می‌کنیم. چون `trace_id` در هر دو خط یکی است، با جست‌وجوی همان یک مقدار می‌توانید پیام را در تلاش‌های مختلف دنبال کنید. این شناسه را Publisher می‌سازد؛ بخش بعد نشان می‌دهد چطور به Worker می‌رسد.

## Trace: انتقال context از طریق هدر NATS

trace کار انجام‌شده در برنامه‌های مختلف را برای یک درخواست به هم وصل می‌کند. از **span** ساخته شده، و {{< term "tracing-span" "span" >}} یک تکه کار زمان‌دار است، مثل «این پیام را publish کن» یا «این پیام را پردازش کن». هر span یک شناسه دارد و span فرزند شناسه‌ی والدش را ثبت می‌کند. برای اینکه span‌ی Worker فرزند span‌ی Publisher شود، Publisher باید شناسه‌هایش را همراه پیام بفرستد. به این کار انتقال context گفته می‌شود.

پیام‌های NATS مثل درخواست‌های HTTP می‌توانند هدر داشته باشند، پس هدر `traceparent` استاندارد W3C جای طبیعی‌ای برای این کار است. فرمت استاندارد این هدر از نسخه، شناسه‌ی trace، شناسه‌ی span و پرچم‌ها تشکیل شده که با خط تیره به هم وصل شده‌اند. Publisher یک span می‌سازد و context را در `msg.Header` می‌گذارد (inject). Worker آن را بیرون می‌کشد (extract) و یک span فرزند می‌سازد. من از SDK واقعی OpenTelemetry با exporter استاندارد خروجی (exporter‌ای که spanهای تمام‌شده را به‌صورت JSON چاپ می‌کند) استفاده کردم، نه هدر دست‌ساز، و فرمت‌دهی را `propagation.TraceContext{}` انجام می‌دهد:

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

`nats.Header` از نوع `map[string][]string` است و شکلش با `http.Header` یکی است، پس مستقیم با `propagation.HeaderCarrier` کار می‌کند.

Worker برای کار شماره‌ی ۱۰ trace با شناسه‌ی `bf9fafe7...` را لاگ کرد. خروجی exporter را روی همین شناسه فیلتر کردم و نام span، شناسه‌ی span و شناسه‌ی والد هر کدام را چاپ کردم:

```text
publish jobs.run  span a7ea4be0b56bf913  parent 0000000000000000
process jobs.run  span 0f90631928129dbb  parent a7ea4be0b56bf913
process jobs.run  span 9ed57a5cf1fb5a99  parent a7ea4be0b56bf913
```

خط اول span Publisher است. والدی که همه‌اش صفر است یعنی «والد ندارد»: ریشه است. هر دو span از نوع `process` شناسه‌ی span Publisher را به‌عنوان والد دارند. یکی تلاش اول ناموفق است و دیگری تلاش مجدد موفق. پس یک trace کل زندگی کار ۱۰ را نشان می‌دهد: یک بار publish شده و دو بار پردازش. شناسه‌های trace و span تصادفی‌اند و در هر اجرا فرق می‌کنند.

## روی چه چیزی alert بگذاریم

متریک فقط وقتی به کار می‌آید که وقتی بد می‌شود کسی خبردار شود. آستانه اختراع نمی‌کنم چون به سیستم شما بستگی دارد، ولی این سه سیگنال را زیر نظر می‌گیرم:

- `consumer_num_pending` که به‌جای ثابت شدن روی یک سطح مدام بالا می‌رود. یک جهش کوتاه عادی است. خطی که فقط بالا می‌رود یعنی Worker نمی‌رسد.
- بالا رفتن سهم `failed` یا `redelivered_ok` از کل پیام‌ها.
- هر پیام داخل استریم dead-letter از [مقاله‌ی retry](/fa/posts/nats-jetstream-retry-dlq/). عمق آن در حالت عادی باید صفر باشد، پس هر رشدی ارزش نگاه کردن دارد.

آستانه‌ها را از baseline خودتان انتخاب کنید: مدتی مقدارهای عادی را ببینید و بعد روی انحراف روشن از آن‌ها هشدار بگذارید. هشدارهایی که مدام می‌خورند به مردم یاد می‌دهند نادیده‌شان بگیرند، و به این می‌گویند {{< term "alert-fatigue" "خستگی از هشدار" >}}.

## نقاط کور و هزینه‌ها

- `ConsumerInfo` یک درخواست به سرور است. تقریباً هر ثانیه نمونه بگیرید، نه برای هر پیام.
- gaugeها فقط به اندازه‌ی فاصله‌ی نمونه‌برداری تازه‌اند. در خروجی بالا `consumer_num_ack_pending` تا نیم‌ثانیه از شمارنده‌ها عقب بود.
- bucketهای هیستوگرام موقع ساخت ثابت می‌شوند. آن‌ها را حول تأخیرهای واقعی خودتان انتخاب کنید. اگر همه‌ی کارها در آخرین bucket بیفتند، هیستوگرام چیزی نمی‌گوید.
- انتقال هدر فقط وقتی مفید است که هر مرحله آن را extract کند. سرویسی که پیام را دوباره publish می‌کند و هدرها را کپی نمی‌کند، trace را به دو نیم می‌کند.
- exporter استاندارد خروجی برای دمو است. در production spanها را به یک collector می‌فرستند.

## قدم بعدی

همه‌ی این‌ها روی سروری اجرا شد که داخل همان برنامه‌ی Go تعبیه شده بود، و همین تست کردن را هم آسان می‌کند: نه Docker لازم است و نه سرور مشترک. مقاله‌ی بعد، [تست سرویس‌های JetStream با nats-server توکار](/fa/posts/nats-jetstream-testing/)، دقیقاً روی همین بنا شده است.
