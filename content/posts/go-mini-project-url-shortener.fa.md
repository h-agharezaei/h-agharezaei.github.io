+++
date = '2026-12-14T10:00:00+03:30'
draft = false
title = 'پروژه‌ی کوچک: URL shortener با Go'
description = 'یک URL shortener کوچک فقط با کتاب‌خانه‌ی استاندارد: مسیریابی net/http، store با RWMutex، کد تصادفی با crypto/rand، JSON، اعتبارسنجی و تست با httptest.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "project", "http"]
cover = { image = "/images/covers/go-mini-project-url-shortener.fa.png", alt = "پروژه‌ی کوچک: URL shortener با Go", hiddenInSingle = true }
+++

لینک‌های بلند آزاردهنده‌اند. در پیام‌رسان می‌شکنند، در چاپ زشت‌اند و هیچ‌کس دوست ندارد تایپشان کند. **URL shortener** این مشکل را حل می‌کند: آدرس بلند را به آن می‌دهید، یک کد کوتاه پس می‌دهد و وقتی کسی لینک کوتاه را باز کند، به آدرس بلند فرستاده می‌شود. سرویس‌هایی از این نوع از بیرون بزرگ به نظر می‌رسند، ولی هسته‌شان کوچک است: جدولی که کد کوتاه را به URL بلند نگاشت می‌کند، به‌علاوه‌ی دو endpoint در HTTP.

این آخرین نوشته‌ی مجموعه‌ی Go Fundamentals است؛ پس به‌جای یک ویژگی تازه، از چیزهایی که تا اینجا یاد گرفته‌ایم استفاده می‌کنیم. بعد از [ابزار خط فرمان](/fa/posts/go-cli-tool/)، یک سرویس HTTP کوچک می‌سازیم که فقط از کتاب‌خانه‌ی استاندارد استفاده می‌کند. یک URL بلند را با `POST /shorten` به شکل JSON می‌فرستید و یک کد می‌گیرید. باز کردن `/<code>` شما را به آدرس اصلی redirect می‌کند. جالب‌ترین بخش برای من خودِ کد نیست، ترتیب کارها هنگام خاموش شدن است، چون سرویسی که داده‌اش را در حافظه نگه می‌دارد باید قبل از خروج آن را ذخیره کند. به آن می‌رسیم.

> همه‌چیز را با Go 1.27 روی macOS اجرا کرده‌ام و خروجی‌ها از اجراهای واقعی کپی شده‌اند، جز اینکه کدهای تصادفی از اجرایی به اجرای دیگر فرق می‌کنند. کد یک مثال محلی است، نه مخزن منتشرشده.

## تکه‌ها چطور به هم وصل می‌شوند

مثل [نوشته‌ی پکیج‌ها](/fa/posts/go-packages-modules/)، ماژول `example.com/shortener` سه بخش کوچک دارد:

- `store` داده را نگه می‌دارد: کدام کد به کدام URL اشاره می‌کند و چطور ذخیره و بارگذاری شود.
- `server` لایه‌ی HTTP است: handlerهایی که درخواست را می‌خوانند و پاسخ می‌نویسند.
- `main.go` آن‌ها را به هم وصل می‌کند و راه‌اندازی و خاموشی را مدیریت می‌کند.

وابستگی یک‌طرفه است: `server` از `store` خبر دارد و `store` از HTTP هیچ نمی‌داند. یعنی store را بدون هیچ وب‌سروری می‌توانیم تست کنیم و بعداً هم می‌شود رابط دیگری رویش گذاشت.

## store

هسته‌ی store یک map از کد به URL است. ولی handlerهای HTTP در goroutineهای زیادی همزمان اجرا می‌شوند و نباید وقتی یک goroutine در map می‌نویسد، دیگری از آن بخواند. برای همین map را مثل [نوشته‌ی sync](/fa/posts/go-sync-select-context/) با یک `sync.RWMutex` محافظت می‌کنیم. **read-write mutex** دو نوع قفل دارد. چند خواننده می‌توانند همزمان قفل خواندن را داشته باشند؛ قفل نوشتن انحصاری است. ترافیک ما بیشتر redirect است که فقط می‌خواند، پس این کار اجازه می‌دهد موازی اجرا شوند؛ فقط `Add` قفل انحصاری می‌خواهد:

```go
type Store struct {
	mu    sync.RWMutex
	links map[string]string
}

func (s *Store) Get(code string) (string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	target, ok := s.links[code]
	if !ok {
		return "", ErrNotFound
	}
	return target, nil
}
```

`Get` یک **sentinel error** برمی‌گرداند، یعنی `ErrNotFound`؛ مقدار خطای نام‌داری که فراخواننده با `errors.Is` تشخیصش می‌دهد. می‌بینیم handler چطور از آن استفاده می‌کند.

کدها از کجا می‌آیند؟ ۷ نویسه‌ی تصادفی از رقم‌ها و حروف بزرگ و کوچک می‌سازیم، در مجموع ۶۲ نماد (به این الفبا **base62** می‌گویند). تصادفی بودن از `crypto/rand` می‌آید. یک نکته: اگر یک بایت تصادفی را به پیمانه‌ی ۶۲ بگیریم، چند نویسه‌ی اول الفبا خیلی کم محتمل‌تر از بقیه می‌شوند. برای لینک کوتاه مهم نیست، ولی برای توکن محرمانه مهم است و آنجا باید روش دیگری به کار برد.

```go
func newCode(n int) (string, error) {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	for i := range b {
		b[i] = alphabet[int(b[i])%len(alphabet)]
	}
	return string(b), nil
}
```

`Add` قفل نوشتن را می‌گیرد، یک کد می‌سازد و چک می‌کند آزاد باشد. اگر کد اتفاقاً وجود داشته باشد، که نادر است ولی ممکن، فقط یکی دیگر می‌کشد:

```go
func (s *Store) Add(target string) (string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for {
		code, err := newCode(7)
		if err != nil {
			return "", err
		}
		if _, taken := s.links[code]; !taken {
			s.links[code] = target
			return code, nil
		}
	}
}
```

ماندگاری با جفت `Save(path)` و `Load(path)` است که map را به JSON تبدیل می‌کنند، با همان `encoding/json` و `os.WriteFile` از [نوشته‌ی فایل و JSON](/fa/posts/go-file-io-json/). `Load` با چک کردن `errors.Is(err, os.ErrNotExist)` فایل ناموجود را «با حالت خالی شروع کن» حساب می‌کند؛ پس اولین اجرا شکست نمی‌خورد.

## handlerها

حالا سمت HTTP. از Go 1.22 `ServeMux` استاندارد در الگوهایش متد HTTP و wildcard مسیر را می‌فهمد، پس به کتاب‌خانه‌ی router نیازی نیست. دو خط کل API ما را اعلام می‌کند:

```go
mux := http.NewServeMux()
mux.HandleFunc("POST /shorten", srv.shorten)
mux.HandleFunc("GET /{code}", srv.redirect)
```

`POST /shorten` فقط درخواست‌های POST به آن مسیر را می‌گیرد. `GET /{code}` هر GET به مسیرِ یک‌بخشی را می‌گیرد و آن بخش را به‌عنوان `code` به ما می‌دهد.

handler مربوط به `shorten` چهار کار را به ترتیب انجام می‌دهد: اندازه‌ی بدنه را محدود می‌کند (با `http.MaxBytesReader`، اینجا ۱ مگابایت)، JSON را decode می‌کند، URL را اعتبارسنجی می‌کند و ذخیره‌اش می‌کند. در صورت موفقیت `201 Created` می‌دهد. اعتبارسنجی با `net/url` است. URL باید parse شود، scheme باید `http` یا `https` باشد و host داشته باشد:

```go
func validate(raw string) error {
	u, err := url.Parse(raw)
	if err != nil {
		return errors.New("url is not valid")
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return errors.New("url must start with http:// or https://")
	}
	if u.Host == "" {
		return errors.New("url must have a host")
	}
	return nil
}
```

چرا اصلاً اعتبارسنجی؟ بدونش کسی می‌توانست `javascript:...` یا رشته‌ای که URL نیست ذخیره کند و redirect ما کاربرها را به آنجا می‌فرستاد.

handler مربوط به redirect، wildcard را با `r.PathValue("code")` می‌خواند و خطای sentinel مربوط به store را به کد وضعیت HTTP تبدیل می‌کند:

```go
func (s *Server) redirect(w http.ResponseWriter, r *http.Request) {
	target, err := s.store.Get(r.PathValue("code"))
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "unknown code")
		return
	}
	// ...
	http.Redirect(w, r, target, http.StatusFound)
}
```

store با زبان خودش می‌گوید «پیدا نشد» و handler آن را به 404 ترجمه می‌کند. خط آخر یک {{< term "http-redirect" "redirect" >}} می‌فرستد: پاسخی با وضعیت `302` و هدر `Location` که URL بلند را دارد. بعد مرورگر خودش آن آدرس را درخواست می‌کند.

عمداً 302 را انتخاب کردم. مرورگرها ممکن است 301 (انتقال دائمی) را برای مدت طولانی cache کنند و آن‌وقت دیگر نمی‌شود لینک را عوض کرد یا شمرد، چون مرورگر دیگر از ما نمی‌پرسد. 302 یعنی «موقت»، پس هر بازدید به سرور ما برمی‌گردد.

## خاموشی و ذخیره

store در حافظه است؛ پس داده فقط وقتی می‌ماند که قبل از پایان پروسه روی دیسک بنویسیمش. `main` این کار را این‌طور می‌کند:

```go
st := store.New()
if err := st.Load(dataFile); err != nil {
	log.Fatal(err)
}
srv := &http.Server{Addr: addr, Handler: server.New(st, "http://localhost:8080")}

ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()

go func() {
	if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
}()
log.Printf("listening on %s", addr)

<-ctx.Done()
shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
srv.Shutdown(shutdownCtx)
if err := st.Save(dataFile); err != nil {
	log.Fatal(err)
}
log.Printf("saved %s, bye", dataFile)
```

قدم‌به‌قدم: `main` فایل `links.json` را بارگذاری می‌کند (اگر نباشد خالی) و سرور را در یک goroutine راه می‌اندازد تا خودِ `main` آزاد باشد و منتظر بماند. `signal.NotifyContext` یک context می‌دهد که وقتی پروسه Ctrl+C (یعنی `os.Interrupt`) یا `SIGTERM` را بگیرد لغو می‌شود. `SIGTERM` سیگنال مؤدبانه‌ی «لطفاً بایست» است که بیشتر ابزارهای استقرار می‌فرستند. خط `<-ctx.Done()` تا وقوع این اتفاق می‌ایستد.

بعد بخش مهم می‌رسد. `srv.Shutdown` پذیرفتن اتصال تازه را متوقف می‌کند و حداکثر ۵ ثانیه منتظر درخواست‌هایی می‌ماند که همین حالا در حال اجرا هستند. فقط بعد از برگشتن آن، `Save` را صدا می‌زنیم. ترتیب همان نکته است: اگر اول ذخیره می‌کردیم، لینکی که درخواستِ هنوز در جریان ساخته بود ممکن بود در فایل نباشد. چون `Shutdown` منتظر آن درخواست‌ها مانده، ذخیره همه‌ی لینک‌ها را می‌بیند.

## تست با httptest

راه انداختن سرور واقعی برای هر تست کند است و یک پورت آزاد هم می‌خواهد. پکیج `net/http/httptest` از این بی‌نیازمان می‌کند: `httptest.NewRequest` یک درخواست می‌سازد و `httptest.NewRecorder` پاسخ را ضبط می‌کند؛ پس handler را مستقیم، مثل یک تابع معمولی، صدا می‌زنیم. مثل [نوشته‌ی تست](/fa/posts/go-testing-basics/)، ورودی‌های نامعتبر یک جدول‌اند:

```go
func TestShortenInvalid(t *testing.T) {
	tests := []struct{ name, body string }{
		{"not json", `hello`},
		{"empty url", `{"url":""}`},
		{"no scheme", `{"url":"example.com"}`},
		{"bad scheme", `{"url":"ftp://example.com/file"}`},
		{"no host", `{"url":"https://"}`},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if rec := post(newTestServer(), tt.body); rec.Code != http.StatusBadRequest {
				t.Errorf("status = %d, want 400", rec.Code)
			}
		})
	}
}
```

هر ردیف ورودی‌ای است که باید با `400 Bad Request` رد شود. تست‌های دیگر ساخت و سپس redirect، کد ناشناخته، 405 برای متد اشتباه، رفت‌وبرگشت save/load و ۵۰ درخواست POST همزمان را پوشش می‌دهند. این هم اجرایشان، اول ساده و بعد با race detector (`-race`) که دسترسی محافظت‌نشده به map را گزارش می‌کرد:

```text
$ go test -count=1 ./...
?   	example.com/shortener	[no test files]
ok  	example.com/shortener/server	0.289s
ok  	example.com/shortener/store	0.192s
$ go test -race -count=1 ./...
ok  	example.com/shortener/server	1.315s
ok  	example.com/shortener/store	1.297s
```

خط اول می‌گوید پکیج ریشه، یعنی `main.go`، تست ندارد. دو پکیج دیگر قبول شده‌اند. اجرای race کندتر است چون detector برنامه را کند می‌کند، و آن هم قبول شد؛ یعنی mutex واقعاً از map محافظت می‌کند. زمان‌ها از اجرایی به اجرای دیگر فرق می‌کنند.

## اجرای واقعی

تست خوب است، ولی سرور واقعی را هم اجرا می‌کنیم و با `curl` با آن حرف می‌زنیم. فلگ `-i` هدرهای پاسخ را نشان می‌دهد. اول یک URL را کوتاه می‌کنیم، بعد کد را دنبال می‌کنیم، بعد کدی که وجود ندارد را امتحان می‌کنیم و آخر یک URL نامعتبر:

```text
$ curl -i -X POST localhost:8080/shorten -d '{"url":"https://go.dev/doc/"}'
HTTP/1.1 201 Created
Content-Type: application/json
Content-Length: 63

{"code":"LcUU3Dk","short_url":"http://localhost:8080/LcUU3Dk"}

$ curl -i localhost:8080/LcUU3Dk
HTTP/1.1 302 Found
Content-Type: text/html; charset=utf-8
Location: https://go.dev/doc/
Content-Length: 42

<a href="https://go.dev/doc/">Found</a>.

$ curl -i localhost:8080/zzzzzzz
HTTP/1.1 404 Not Found
{"error":"unknown code"}

$ curl -i -X POST localhost:8080/shorten -d '{"url":"example.com"}'
HTTP/1.1 400 Bad Request
{"error":"url must start with http:// or https://"}
```

(بعضی هدرها مثل `Date` را حذف کرده‌ام.) پاسخ اول `201 Created` با کد تازه است (تصادفی است، پس مال شما فرق می‌کند). دومی redirect است: وضعیت `302` و هدر `Location` با آدرس اصلی. بدنه یک لینک HTML کوچک است برای کلاینت‌هایی که redirect را دنبال نمی‌کنند. درخواست سوم کدی را خواست که هرگز ساخته نشده بود و `404` گرفت، و چهارمی را اعتبارسنجی با `400` و پیامی که دلیلش را می‌گوید رد کرد.

آخرین آزمایش همان است که به داستان خاموشی مربوط است. بعد از Ctrl+C لاگ نوشت `saved links.json, bye` و فایل دو لینکی را که ساخته بودم داشت. سرور را دوباره راه انداختم و کد قدیمی هنوز با `302` redirect می‌کرد.

## جاهایی که این نسخه کم می‌آورد

- **`GET /{code}` با `GET /shorten` هم می‌خواند.** امتحانش کردم و `/shorten` مثل یک کد ناشناخته با 404 جواب گرفت. سرویس‌های واقعی چند کلمه را رزرو می‌کنند تا هرگز کد نشوند.
- **همیشه بدنه‌ی درخواست را محدود کنید.** بدون محدودیت، یک کلاینت می‌تواند بدنه‌ی بسیار بزرگی بفرستد و همه‌ی حافظه را بگیرد. اینجا `http.MaxBytesReader` آن را به ۱ مگابایت محدود می‌کند.
- **فایل فقط در خاموشی تمیز نوشته می‌شود.** crash یا `kill -9` هرچه از آخرین ذخیره مانده را از دست می‌دهد. پایگاه داده یا ذخیره‌ی دوره‌ای این را درست می‌کند.
- **قفل هنگام ساخت کد نگه داشته می‌شود.** ساده است و در این مقیاس اشکالی ندارد، ولی در سرویس پرترافیک گلوگاه می‌شود.
- **redirect به هر URLی که کاربر بدهد خطرناک است.** سرویس ما به هر چیزی که مردم بفرستند redirect می‌کند و این می‌تواند برای فیشینگ سوءاستفاده شود. سرویس واقعی بررسی سوءاستفاده لازم دارد.

## تمرین

۱. `GET /stats/{code}` را اضافه کنید که بگوید یک کد چند بار بازدید شده (راهنمایی: یک شمارنده داخل store، زیر همان قفل).
۲. اجازه دهید `POST /shorten` یک `"code"` دلخواه (alias) اختیاری بپذیرد و اگر گرفته شده بود `409 Conflict` برگرداند.

## قدم بعدی

مبانی تمام شد و از اینجا نوشته‌های Go به موضوع‌های backend می‌روند. «خاموشی تمیز Workerها در Go» مشکل خاموشی را که اینجا دیدیم به workerهایی می‌برد که از NATS می‌خوانند.
