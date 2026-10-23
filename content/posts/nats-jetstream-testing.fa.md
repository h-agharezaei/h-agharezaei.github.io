+++
date = '2027-01-17T10:00:00+03:30'
draft = false
title = 'تست سرویس‌های JetStream با nats-server توکار'
description = 'تست Consumerهای JetStream با go test ساده: یک nats-server توکار برای هر تست، بدون sleep، با BackOff کوتاه، برای retry، DLQ و idempotency.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "testing", "messaging"]
cover = { image = "/images/covers/nats-jetstream-testing.fa.png", alt = "تست سرویس‌های JetStream با nats-server توکار", hiddenInSingle = true, hiddenInList = true }
+++

[مقاله‌ی قبل](/fa/posts/nats-jetstream-observability/) درباره‌ی این بود که در production چطور ببینیم یک سرویس JetStream چه می‌کند. این مقاله درباره‌ی دیدن همین رفتار قبل از production است. در مقاله‌های اخیر چند رفتار را توضیح دادیم: [retry و dead-letter queue](/fa/posts/nats-jetstream-retry-dlq/) و [idempotency](/fa/posts/nats-jetstream-idempotency/). هر کدام را با یک برنامه‌ی موقت امتحان کردیم و خروجی را با چشم خواندیم. حالا همان بررسی‌ها را با [`go test`](/fa/posts/go-testing-basics/) به تست واقعی تبدیل می‌کنیم، بدون Docker و بدون سرور بیرونی، تا اگر کسی رفتار را خراب کرد، تست بلند شکست بخورد.

> همه‌چیز با Go 1.26، `nats-server` نسخه‌ی v2.15.1 و `nats.go` نسخه‌ی v1.54.0 اجرا شده و خروجی‌ها از ماشین خودم است.

## چه چیزی را تست می‌کنیم

یک package کوچک به نام `worker` با چهار بخش: `Setup` یک stream، یک stream به نام `DLQ` و یک consumer با `MaxDeliver: 3` و `BackOff` می‌سازد؛ `Run` پیام‌ها را pull می‌کند و فقط وقتی handler مقدار nil برگرداند ack می‌زند؛ `RunDLQ` به advisory مربوط به max-deliveries گوش می‌دهد و پیام را به stream مربوط به DLQ کپی می‌کند (مثل مقاله‌ی retry)؛ و `Ledger` یک handler از نوع idempotent است که هر شناسه‌ی سفارش را فقط یک بار اعمال می‌کند. تست‌ها JetStream واقعی می‌خواهند و ساده‌ترین راه این است که آن را داخل همان process تست راه بیندازیم.

## دو helper

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

`Port: -1` یعنی یک پورت آزاد تصادفی، پس تست‌ها نه با هم تداخل دارند و نه با NATS ای که روی لپ‌تاپ شما در حال اجراست. `t.TempDir()` برای هر سرور یک store جدا می‌دهد که Go بعداً پاکش می‌کند و `t.Cleanup` همه‌چیز را به ترتیب معکوس خاموش می‌کند. هر تست سرور تازه‌ی خودش را دارد، پس هیچ تستی stream تست دیگر را نمی‌بیند.

## بدون sleep: منتظر شرط بمان

`time.Sleep` ثابت یا کوتاه است (تست flaky می‌شود) یا بلند است (تست کند می‌شود). به جایش یک helper کوچک نوشتم که یک شرط را تا رسیدن deadline poll می‌کند، و چیزی را poll می‌کنم که خود سرور در اختیار می‌گذارد: `StreamInfo` و `ConsumerInfo`.

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

آن ۲ میلی‌ثانیه فقط فاصله‌ی poll است؛ تست به محض برقرار شدن شرط ادامه می‌دهد و deadline سه‌ثانیه‌ای سقف شکست است، نه زمان انتظار. handlerها آنچه اتفاق افتاده (مثلاً `NumDelivered`) را در یک slice محافظت‌شده با mutex ثبت می‌کنند و تست بعد از ack روی آن assert می‌کند.

## تست سریع: زمان را کوچک کن

مقدارهای production مثل `AckWait: 30s` یک تست retry را یک دقیقه طولانی می‌کنند. تنظیمات consumer از یک `Config` می‌آید، پس تست‌ها مقدارهای خیلی کوچک می‌دهند:

```go
var testCfg = Config{
	MaxDeliver: 3,
	AckWait:    200 * time.Millisecond,
	BackOff:    []time.Duration{20 * time.Millisecond, 50 * time.Millisecond},
}
```

چون Worker در شکست ack نمی‌زند، سرور طبق `BackOff` دوباره تحویل می‌دهد و تلاش دوم و سوم بعد از ۲۰ و ۵۰ میلی‌ثانیه می‌رسند. کد را طوری طراحی کنید که این زمان‌ها پارامتر باشند؛ وگرنه نمی‌توانید سریع تستش کنید.

## تست‌ها

Retry و بعد موفقیت: handler دوبار شکست می‌خورد و در تحویل سوم موفق می‌شود.

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

تست پیام poison صبر می‌کند تا stream مربوط به DLQ پیام داشته باشد، بعد بررسی می‌کند دقیقاً یک پیام هست، handler دقیقاً `MaxDeliver` بار اجرا شده و payload سالم است. تست انتشار تکراری دوبار با همان `nats.MsgId` publish می‌کند و `Duplicate` را در `PubAck` دوم و وجود یک پیام در stream چک می‌کند. تست crash از handlerی استفاده می‌کند که side effect را با `Ledger` اعمال می‌کند و در تحویل اول خطا برمی‌گرداند (شبیه crash قبل از ack)؛ بعد از تحویل مجدد، balance باید همچنان ۱۰۰ باشد. تست happy path همان شکل retry را با یک تحویل دارد.

## اجرای واقعی

```
$ go test ./... -v
--- PASS: TestHappyPath (0.13s)
--- PASS: TestRetryThenSuccess (0.18s)
--- PASS: TestPoisonMessageGoesToDLQ (0.24s)
--- PASS: TestDuplicatePublishStoredOnce (0.05s)
--- PASS: TestRedeliveryAfterCrashIsSkipped (0.14s)
ok  	jstest/worker	1.125s
```

پنج تست که هر کدام سرور خودشان را دارند، در حدود یک ثانیه تمام می‌شوند. `go test -race -count=3` (۳٫۶ ثانیه) و بعد `-count=10` (۸٫۶ ثانیه) را اجرا کردم و همه پاس شدند، بدون گزارش race. ماشین مشغول بود (load average بین ۶ تا ۱۰)، پس زمان‌ها را تقریبی بدانید.

برای اینکه مطمئن شوم تست‌ها واقعاً می‌توانند شکست بخورند، پروژه را کپی کردم و در `Ledger` بررسی تکراری‌بودن را خاموش کردم (`if false && l.seen[o.ID]`):

```
--- FAIL: TestRedeliveryAfterCrashIsSkipped (0.13s)
    worker_test.go:227: balance = 200, want 100
FAIL
FAIL	jstest/worker	1.083s
```

این همان باگ اعمال دوباره در مقاله‌ی idempotency است که حالا در حدود یک ثانیه گرفته می‌شود.

## چند نکته‌ی مهم

- بعد از subscribe به advisory حتماً `nc.Flush()` بزنید، همان‌طور که `RunDLQ` می‌زند؛ وگرنه تست ممکن است پیام را قبل از ثبت subscription در سرور publish کند.
- `ReadyForConnections` باید قبل از اتصال باشد و ترتیب `Cleanup` مهم است: اول Worker را متوقف کنید، بعد connection و سرور را ببندید.
- تست‌های کندتر (timeout واقعی، داده‌ی بزرگ) را با `testing.Short()` شرطی کنید تا `go test -short` فوری بماند.
- اثبات «نبودن» بدون انتظار سخت است: «پیام دوم در DLQ نیست» به `MsgId` و شمارش دفعات اجرای handler تکیه دارد، نه یک sleep طولانی.
- یک سرور توکار تکی، clustering، auth و خطاهای واقعی شبکه را تست نمی‌کند.

## قدم بعدی

مقاله‌ی بعد: KV و Object Store در NATS، جایی که JetStream به یک key-value store و یک ذخیره‌گاه blob تبدیل می‌شود.
