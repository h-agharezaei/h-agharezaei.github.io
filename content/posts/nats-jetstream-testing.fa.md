+++
date = '2027-01-17T10:00:00+03:30'
draft = false
title = 'تست سرویس‌های JetStream با nats-server توکار'
description = 'تست Consumerهای JetStream با go test ساده: یک nats-server توکار برای هر تست، بدون sleep، با BackOff کوتاه، برای retry، DLQ و idempotency.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "testing", "messaging"]
cover = { image = "/images/covers/nats-jetstream-testing.fa.png", alt = "تست سرویس‌های JetStream با nats-server توکار", hiddenInSingle = true }
+++

فرض کنید یک خط از handler مربوط به retry را عوض می‌کنید و یک هفته بعد یک مشتری دو بار پول می‌دهد. هیچ‌کدام از بررسی‌های قبلی این را نمی‌گرفت. هر رفتار JetStream در این سری، از [retry و dead-letter queue](/fa/posts/nats-jetstream-retry-dlq/) تا [idempotency](/fa/posts/nats-jetstream-idempotency/)، با یک برنامه‌ی موقتی بررسی شد که خروجی‌اش را با چشم می‌خواندم. این فقط نشان می‌دهد در روزی که اجرا کردم کار می‌کرد. جلوی کسی را که بعداً آن را خراب کند نمی‌گیرد.

[مقاله‌ی قبل](/fa/posts/nats-jetstream-observability/) درباره‌ی دیدن کار سرویس در production بود. این‌جا همان بررسی‌های چشمی را به تست واقعی با [`go test`](/fa/posts/go-testing-basics/) تبدیل می‌کنیم: بدون Docker، بدون سرور بیرونی، و با تست‌هایی که اگر کسی رفتار را خراب کند بلند و واضح fail می‌شوند.

ایده‌ی اصلی کوتاه است. سرویس JetStream برای تست به یک سرور JetStream واقعی نیاز دارد و `nats-server` یک کتابخانه‌ی Go است. پس هر تست سرور خصوصی خودش را داخل همان process تست راه می‌اندازد، روی یک پورت تصادفی و با یک پوشه‌ی موقت، و وقتی تست تمام شد دورش می‌اندازد. نه mock برای NATS داریم و نه state مشترک بین تست‌ها.

> همه‌چیز را با Go 1.27، `nats-server` نسخه‌ی v2.15.1 و `nats.go` نسخه‌ی v1.54.0 روی ماشین خودم اجرا کردم. کد یک مثال محلی است، نه یک repo منتشرشده. زمان تست‌ها در هر اجرا فرق می‌کند.

## چه چیزی را تست می‌کنیم

کدی که تست می‌شود یک پکیج کوچک به نام `worker` با چهار بخش است:

- `Setup` استریم کار، یک استریم دوم به نام `DLQ` (یعنی {{< term "dlq" "صف نامه‌های مرده" >}} برای پیام‌هایی که مدام fail می‌شوند) و یک consumer می‌سازد. consumer حداکثر سه بار تحویل می‌دهد (`MaxDeliver: 3`) و بین تلاش‌ها زمان قابل‌تنظیمی صبر می‌کند (`BackOff`).
- `Run` پیام‌ها را یکی‌یکی می‌گیرد و فقط وقتی handler خطا برنگرداند ack می‌فرستد. اگر handler fail شود ack نمی‌رود و سرور بعد از زمان backoff پیام را دوباره تحویل می‌دهد.
- `RunDLQ` به advisory سرور برای «به حداکثر تحویل رسید» گوش می‌دهد و پیام را به استریم `DLQ` کپی می‌کند، مثل مقاله‌ی retry.
- `Ledger` یک handler {{< term "idempotency" "خودتوان" >}} است: مبلغ یک سفارش را فقط بار اول که شناسه‌ی آن سفارش را می‌بیند به موجودی اضافه می‌کند.

اگر این اصطلاح‌ها برایتان تازه‌اند، مقاله‌های قبلی سری توضیحشان داده‌اند. نکته‌ی این‌جا این است که همه‌ی این رفتارها بین سرور و کلاینت پخش شده‌اند، پس تست به JetStream واقعی نیاز دارد. ساده‌ترین راه، راه‌اندازی یکی داخل خود تست است.

## دو تابع کمکی

هر تست یک سرور و یک اتصال به آن لازم دارد. این دو تابع آن را فراهم می‌کنند:

```go
func newTestServer(t *testing.T) *server.Server {
	t.Helper()
	s, err := server.NewServer(&server.Options{
		Host: "127.0.0.1", Port: -1, // random free port
		JetStream: true, StoreDir: t.TempDir(),
		NoLog: true, NoSigs: true,
	})
	if err != nil {
		t.Fatal(err)
	}
	go s.Start()
	if !s.ReadyForConnections(5 * time.Second) {
		t.Fatal("nats-server not ready")
	}
	t.Cleanup(func() { s.Shutdown(); s.WaitForShutdown() })
	return s
}

func connect(t *testing.T, s *server.Server) (*nats.Conn, nats.JetStreamContext) {
	t.Helper()
	nc, err := nats.Connect(s.ClientURL())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(nc.Close)
	js, _ := nc.JetStream()
	return nc, js
}
```

چند نکته‌ی مهم:

- `Port: -1` یعنی «یک پورت آزاد تصادفی بردار». تست‌ها نه با هم برخورد می‌کنند و نه با NATSی که شاید روی لپ‌تاپتان روشن باشد. آدرس هم `127.0.0.1` است، پس هیچ‌چیز از بیرون در دسترس نیست.
- `t.TempDir()` به هر سرور پوشه‌ی ذخیره‌ی خودش را می‌دهد و Go آن را بعد از تست پاک می‌کند.
- `t.Cleanup` تابع‌های ثبت‌شده را به ترتیب معکوس اجرا می‌کند، پس اتصال اول بسته می‌شود و سرور آخر خاموش می‌شود.
- `NoSigs: true` جلوی نصب signal handler خود سرور را می‌گیرد که یک باینری تست نمی‌خواهدش.
- هر تست سرور تازه دارد، پس هیچ تستی استریم‌های تست دیگر را نمی‌بیند.

## بدون sleep: منتظر شرط بمان

حالا سراغ بخشی می‌رویم که تست‌های async را flaky می‌کند. تست یک پیام publish می‌کند و Worker چند میلی‌ثانیه بعد آن را پردازش می‌کند. تست از کجا بداند کی باید چک کند؟ با `time.Sleep` ثابت، یا sleep خیلی کوتاه است (تست گاهی fail می‌شود، یعنی {{< term "flaky-test" "تست flaky" >}}) یا خیلی بلند (مجموعه‌ی تست‌ها کند می‌شود).

راه‌حل این است که به‌جای زمان، منتظر یک شرط بمانیم. یک تابع کوچک نوشتم که شرط را هر چند میلی‌ثانیه چک می‌کند تا یک مهلت تمام شود. چیزی هم که چک می‌کند وضعیتی است که خود سرور نشان می‌دهد: `StreamInfo` و `ConsumerInfo`.

```go
func waitFor(t *testing.T, what string, cond func() bool) {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(2 * time.Millisecond)
	}
	t.Fatalf("timed out waiting for %s", what)
}

// true when the consumer acked everything up to stream sequence seq
func acked(js nats.JetStreamContext, seq uint64) bool {
	ci, err := js.ConsumerInfo(Stream, Consumer)
	return err == nil && ci.AckFloor.Stream >= seq && ci.NumAckPending == 0
}
```

`acked` دو چیز را از `ConsumerInfo` می‌خواند. `AckFloor.Stream` بالاترین شماره‌ی ترتیب است که همه‌ی پیام‌های زیر آن ack شده‌اند و `NumAckPending` تعداد پیام‌هایی است که تحویل داده شده‌اند ولی هنوز ack نگرفته‌اند. وقتی کف به پیام ما رسیده و چیزی در انتظار نیست، پیام کامل تمام شده است.

sleep دو میلی‌ثانیه‌ای فقط فاصله‌ی چک کردن است. تست همان لحظه که شرط درست شود ادامه می‌دهد و مهلت ۳ ثانیه‌ای حد شکست است، نه زمان انتظار. وقتی همه‌چیز درست است، تست دقیقاً به اندازه‌ی خود کار طول می‌کشد.

handlerهای تست آنچه دیده‌اند (مثلاً `NumDelivered`، شماره‌ی تلاش تحویل) را در یک slice محافظت‌شده با mutex ثبت می‌کنند و تست بعد از ack همان slice را بررسی می‌کند.

## تست‌های سریع: زمان را کوتاه کن

یک مشکل زمانی دیگر هم هست. consumer در production شاید `AckWait: 30s` داشته باشد و تست retry آن‌وقت یک دقیقه طول می‌کشد. برای همین تنظیمات consumer از یک مقدار `Config` می‌آید و تست‌ها مدت‌های بسیار کوتاه می‌دهند:

```go
var testCfg = Config{
	MaxDeliver: 3,
	AckWait:    200 * time.Millisecond,
	BackOff:    []time.Duration{20 * time.Millisecond, 50 * time.Millisecond},
}
```

چون Worker در حالت خطا ack نمی‌فرستد، سرور طبق `BackOff` دوباره تحویل می‌دهد: تلاش دوم حدود ۲۰ میلی‌ثانیه بعد از اولی و تلاش سوم حدود ۵۰ میلی‌ثانیه بعد از دومی. دقت کنید که ساعت را جعلی نکردم؛ فقط انتظار واقعی را کوتاه کردم. درس این بخش درباره‌ی طراحی است: این مدت‌ها را پارامتر کنید. اگر ثابتِ مدفون‌شده در کد باشند، مسیر retry را نمی‌شود سریع تست کرد.

## خود تست‌ها

اولین تست مسیر retry را می‌پوشاند: handler دو بار fail می‌شود و در تحویل سوم موفق می‌شود. assertion شماره‌های تحویلی را که handler دیده بررسی می‌کند.

```go
func TestRetryThenSuccess(t *testing.T) {
	var d deliveries
	js := start(t, func(_ context.Context, m *nats.Msg) error {
		if d.add(m) < 3 {
			return errors.New("temporary failure")
		}
		return nil
	})
	js.Publish(Subject, []byte("flaky"))
	waitFor(t, "ack after retries", func() bool { return acked(js, 1) })

	if got := d.list(); len(got) != 3 || got[2] != 3 {
		t.Fatalf("deliveries = %v, want [1 2 3]", got)
	}
}
```

`start` استریم و consumer را می‌سازد، Worker و شنونده‌ی DLQ را اجرا می‌کند و cleanup را ثبت می‌کند. تست یک پیام publish می‌کند، منتظر ack می‌ماند و بعد بررسی می‌کند handler سه بار اجرا شده، با شماره‌های تحویل ۱، ۲ و ۳. (تست واقعی هر سه عنصر را بررسی می‌کند و خالی بودن DLQ را هم؛ این‌جا کوتاهش کرده‌ام.)

چهار تست دیگر همین شکل را دارند:

- **مسیر خوشحال:** یک تحویل، یک ack و هیچ‌چیز در DLQ.
- **پیام سمی:** handler همیشه fail می‌شود. تست صبر می‌کند تا استریم DLQ یک پیام داشته باشد، بعد بررسی می‌کند دقیقاً یک پیام هست، handler دقیقاً `MaxDeliver` بار اجرا شده و محتوا سالم رسیده.
- **publish تکراری:** دو بار با یک `nats.MsgId` publish می‌کند و بررسی می‌کند `PubAck` دوم `Duplicate` است و همان شماره‌ی ترتیب را دارد و استریم یک پیام دارد.
- **تحویل مجدد بعد از crash:** handler اثر جانبی را از طریق `Ledger` اعمال می‌کند و بعد در تحویل اول خطا برمی‌گرداند، یعنی crash قبل از ack را شبیه‌سازی می‌کند. بعد از تحویل مجدد موجودی باید همچنان ۱۰۰ باشد، نه ۲۰۰.

## اجرای واقعی

`go test ./... -v` برای هر تست یک خط چاپ می‌کند:

```text
=== RUN   TestHappyPath
--- PASS: TestHappyPath (0.11s)
=== RUN   TestRetryThenSuccess
--- PASS: TestRetryThenSuccess (0.22s)
=== RUN   TestPoisonMessageGoesToDLQ
--- PASS: TestPoisonMessageGoesToDLQ (0.22s)
=== RUN   TestDuplicatePublishStoredOnce
--- PASS: TestDuplicatePublishStoredOnce (0.05s)
=== RUN   TestRedeliveryAfterCrashIsSkipped
--- PASS: TestRedeliveryAfterCrashIsSkipped (0.12s)
PASS
ok  	jstest/worker	1.117s
```

پنج تست، هرکدام با سرور خودش، در حدود یک ثانیه تمام می‌شوند. عدد داخل پرانتز زمان هر تست است. در هر اجرا فرق می‌کند و ماشین هنگام اجرا مشغول بود، پس آن‌ها را تقریبی بدانید. `go test -race -count=3` را هم اجرا کردم، یعنی کل مجموعه سه بار با race detector Go، و بدون هیچ گزارش race گذشت (اجرای اصلی `-count=10` هم داشت).

تستی که نتواند fail شود ارزشی ندارد. برای بررسی این، پروژه را کپی کردم و بررسی تکراری‌بودن در `Ledger` را با تغییر شرط به `if false && l.seen[o.ID]` غیرفعال کردم:

```text
--- FAIL: TestRedeliveryAfterCrashIsSkipped (0.13s)
    worker_test.go:227: balance = 200, want 100
FAIL
FAIL	jstest/worker	1.126s
```

این دقیقاً همان باگ اعمال دوباره از مقاله‌ی idempotency است: پیام دو بار پردازش شد و موجودی دو برابر شد. حالا مجموعه‌ی تست‌ها آن را در حدود یک ثانیه می‌گیرد. تست‌های دیگر همچنان می‌گذرند، چون به ledger وابسته نیستند.

## تله‌ها در تست JetStream

- بعد از subscribe به advisory حتماً `nc.Flush()` را صدا بزنید، مثل `RunDLQ`. وگرنه تست ممکن است قبل از اینکه سرور از subscription خبردار شود publish کند و advisory گم شود.
- `ReadyForConnections` باید قبل از اتصال بیاید. ترتیب `Cleanup` هم مهم است: اول Worker را متوقف کنید و بعد اتصال و سرور را ببندید. وگرنه Worker ممکن است هنوز از اتصال یا سروری استفاده کند که دیگر وجود ندارد.
- تست‌های کندتر (timeout واقعی، داده‌ی بزرگ‌تر) را با `testing.Short()` کنترل کنید تا `go test -short` فوری بماند.
- اثبات نبودن چیزی بدون انتظار سخت است. «پیام دوم در DLQ نیست» به `MsgId` (سرور تکراری را کنار می‌گذارد) و شمردن فراخوانی handler تکیه دارد، نه به یک sleep بلند.
- یک سرور تعبیه‌ی تکی، cluster، احراز هویت و خرابی واقعی شبکه را تست نمی‌کند. برای این‌ها به تست‌های دیگر نیاز دارید، یا ایده‌های [تست خرابی با تزریق خطا](/fa/posts/ds-fault-injection-testing/).

## قدم بعدی

مقاله‌ی بعد، [KV و Object Store در NATS](/fa/posts/nats-kv-object-store/)، همین سرور تعبیه‌شده را نگه می‌دارد و نشان می‌دهد JetStream می‌تواند یک ذخیره‌ی key-value و یک ذخیره‌ی blob هم باشد.
