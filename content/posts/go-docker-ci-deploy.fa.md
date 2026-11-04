+++
date = '2027-02-28T10:00:00+03:30'
draft = false
title = 'Docker، CI و دیپلوی سرویس Go'
description = 'کانتینری کردن سرویس Go: باینری استاتیک، Dockerfile چندمرحله‌ای با distroless، endpoint‌های سلامت و آمادگی و CI با GitHub Actions و actionlint.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "docker", "ci", "github-actions", "deploy"]
cover = { image = "/images/covers/go-docker-ci-deploy.fa.png", alt = "Docker، CI و دیپلوی سرویس Go", hiddenInSingle = true }
+++

سرویس روی لپ‌تاپ من کار می‌کند. بیشتر داستان‌های دیپلوی با همین جمله شروع می‌شوند. برای اجرا روی هر جای دیگر باید سه سؤال جواب داده شود. چطور بسته‌اش کنیم که روی همه‌ی ماشین‌ها یکسان اجرا شود؟ از کجا بدانیم هر تغییر پیش از رسیدن به آن‌جا هنوز build می‌شود و تست‌هایش می‌گذرد؟ و لحظه‌ای که پلتفرم می‌خواهد نسخه‌ی قدیمی را خاموش و نسخه‌ی جدید را روشن کند چه می‌شود؟

این نوشته برای سرویس `orders` از [مقاله‌ی net/http](/fa/posts/go-http-api-stdlib/) جواب می‌دهد. یک باینری کوچک و ایستا می‌سازیم؛ آن را با Dockerfile داخل یک image کانتینر می‌گذاریم؛ {{< term "ci" "CI" >}} را (یعنی یکپارچه‌سازی پیوسته: ماشینی که روی هر push بررسی‌ها را اجرا می‌کند) مسئول تست و انتشار image می‌کنیم؛ و به سرویس دو endpoint سلامت می‌دهیم. سؤال آخر از همه مهم‌تر است، چون پلتفرم {{< term "container" "کانتینر" >}} را با فرستادن {{< term "sigterm" "SIGTERM" >}} متوقف می‌کند و مدیریت سیگنالی که در [graceful shutdown](/fa/posts/go-graceful-shutdown-workers/) دیدیم وقتی سرویس از لپ‌تاپ من بیرون می‌رود مهم‌تر می‌شود. این نوشته درست بعد از [پروفایلینگ با pprof](/fa/posts/go-profiling-pprof/) می‌آید: حالا می‌دانیم سرویس وقتش را هدر نمی‌دهد، پس می‌فرستیمش.

> **توضیح صادقانه.** Docker daemon روی این ماشین خاموش است و تصمیم گرفتم روشنش نکنم، پس `docker build` را این‌جا هرگز اجرا نکردم. Dockerfile و workflow زیر با هدف درست بودن نوشته شده‌اند، ولی **image ساخته نشد** و نه اندازه‌ی image را نشان می‌دهم و نه خروجی `docker build` را. آنچه واقعاً اجرا کردم، با Go 1.27 روی macOS (arm64): باینری ایستای cross-compile‌شده، endpointهای سلامت، فلگ `-healthcheck`، SIGTERM و `actionlint` روی workflow. فایل `go.mod` دمو `go 1.26` می‌گوید، پس Dockerfile هم همان نسخه‌ی Go را به کار می‌برد.

## باینری ایستا

چرا با باینری شروع کنیم؟ چون برنامه‌ی Go را می‌شود به یک فایل واحد بدون وابستگی بیرونی کامپایل کرد و این image را کوچک و ساده می‌کند. برنامه‌ای که از بخش‌هایی از کتابخانه‌ی استاندارد مثل جست‌وجوی DNS استفاده می‌کند ممکن است به‌طور پیش‌فرض به کتابخانه‌ی C سیستم (libc) لینک شود. با `CGO_ENABLED=0` گو اصلاً از C استفاده نمی‌کند و نتیجه یک **باینری ایستا** است: به هیچ چیزِ سیستمی که روی آن اجرا می‌شود نیاز ندارد، حتی libc.

سرویس را برای Linux روی arm64 cross-compile کردم (`GOOS=linux GOARCH=arm64`؛ ماشین من Mac است و کانتینر Linux اجرا می‌کند) و به چهار شکل ساختم تا ببینم هر فلگ چه می‌کند:

```
$ CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -o plain ./cmd/api
$ ... go build -trimpath ...                    # trim
$ ... go build -ldflags="-s -w" ...             # sw
$ ... go build -trimpath -ldflags="-s -w -X main.version=v1.2.3" ...   # full
plain  10103228 bytes
trim   10098362 bytes
sw      6881440 bytes
full    6881440 bytes
```

- `-s -w` جدول symbol و اطلاعات debug از نوع DWARF را حذف می‌کند و این‌جا حدود ۳٫۲ مگابایت کم می‌کند. بهایش این است که debugger یا ابزار خواندن stack trace چیز کمتری برای کار دارد.
- `-trimpath` تقریباً چیزی کم نمی‌کند (۴٫۹ کیلوبایت). کار اصلی‌اش پاک‌کردن مسیر فایل‌های محلی از باینری است تا build روی ماشین‌های مختلف نتیجه‌ی یکسان بدهد.
- `-X main.version=v1.2.3` یک متغیر رشته‌ای را هنگام لینک مقدار می‌دهد. build به اسم `full` هم‌اندازه‌ی `sw` است، چون یک رشته‌ی کوتاه هزینه‌ای ندارد. بررسی کردم که باینری ساخته‌شده روی میزبان با `-version` عبارت `v1.2.3` را چاپ می‌کند.

`file` روی build کامل می‌گوید `ELF 64-bit LSB executable, ARM aarch64, statically linked, stripped`. اندازه‌ی دقیق به نسخه‌ی Go بستگی دارد: اجرای اصلی با Go 1.26 برای `plain` عدد ۹٬۱۱۴٬۸۱۴ بایت و برای build‌های stripped عدد ۶٬۲۹۱٬۶۱۸ را اندازه گرفته بود.

## endpointهای سلامت و فلگ healthcheck

وقتی پلتفرم سرویس شما را اجرا می‌کند باید بتواند از سرویس وضعیتش را بپرسد. دو پرسش متفاوت وجود دارد و قاطی‌کردنشان اشتباه کلاسیک است:

- **Liveness** («پروسه زنده است؟»). اگر شکست بخورد، پلتفرم پروسه را دوباره راه می‌اندازد.
- **Readiness** («الان ترافیک به تو بفرستم؟»). اگر شکست بخورد، پلتفرم پروسه را نگه می‌دارد ولی دیگر درخواست به آن نمی‌فرستد.

به `main.go` یک `/healthz` برای liveness، یک `/readyz` برای readiness و یک فلگ `-healthcheck` اضافه کردم. آمادگی یک `atomic.Bool` است که بعد از بالا آمدن listener درست می‌شود و همان لحظه که SIGTERM برسد پاک می‌شود:

```go
root.HandleFunc("GET /readyz", func(w http.ResponseWriter, _ *http.Request) {
	if !ready.Load() {
		http.Error(w, "not ready", http.StatusServiceUnavailable)
		return
	}
	w.Write([]byte("ready\n"))
})
// ... after SIGTERM:
ready.Store(false) // fail readiness first, then srv.Shutdown
```

فلگ `-healthcheck` باینری را وادار می‌کند `/healthz` خودش را صدا بزند و با کد ۰ یا ۱ خارج شود. چرا لازم است؟ image نهایی از نوع «distroless» است که نه shell دارد و نه `curl`، پس یک فرمان معمولی health check چیزی برای اجرا ندارد. با این فلگ، `HEALTHCHECK CMD ["/api", "-healthcheck"]` در Docker فقط با خود باینری کار می‌کند. (در Docker اجرایش نکردم. روی Kubernetes به‌جایش از probeهای HTTP روی `/healthz` و `/readyz` استفاده می‌کنید.)

این باینری ساخته‌شده روی میزبان است که تنظیماتش را از محیط می‌خواند. راهش انداختم، دو endpoint را صدا زدم، health check را اجرا کردم و بعد SIGTERM فرستادم:

```
$ ORDERS_ADDR=:18431 ORDERS_DB_PASSWORD=s3cret ORDERS_LOG_FORMAT=json ./host &
$ curl -si localhost:18431/healthz | sed -n '1p;$p'
HTTP/1.1 200 OK
ok
$ curl -si localhost:18431/readyz | sed -n '1p;$p'
HTTP/1.1 200 OK
ready
$ ./host -healthcheck; echo $?
0
$ kill -TERM $PID; wait $PID; echo "exit=$?"
exit=0
```

(پورت اجرای من یک پورت آزاد دیگر بود؛ `18431` را نشان می‌دهم. `sed -n '1p;$p'` فقط خط وضعیت و آخرین خط هر پاسخ را چاپ می‌کند.) هر دو endpoint با ۲۰۰ جواب می‌دهند، health check با کد ۰ خارج می‌شود و SIGTERM به یک خروج تمیز با کد ۰ می‌انجامد. لاگ JSON خط‌های `"shutting down"` و بعد `"stopped"` را دارد که همان مسیر graceful است.

دو حالت شکست هم باید شناخته شوند. وقتی سروری گوش نمی‌دهد، `-healthcheck` پیام `connection refused` را چاپ می‌کند و با کد ۱ خارج می‌شود. بدون `ORDERS_DB_PASSWORD` سرویس از شروع امتناع می‌کند و مثل نوشته‌های قبل با کد ۲ خارج می‌شود.

## Dockerfile

حالا image. **image** در Docker بسته‌ای منجمد از فایل‌ها به‌علاوه‌ی فرمان اجراست؛ **کانتینر** نمونه‌ی در حال اجرای یک image است. image لایه‌لایه ساخته می‌شود، یک لایه برای هر دستور، و Docker هر لایه را cache می‌کند و اگر چیزی بالاتر از آن عوض نشده باشد دوباره به کارش می‌برد. Dockerfile زیر دو مرحله دارد (**multi-stage build**): مرحله‌ی اول کل toolchain گو را دارد و باینری را کامپایل می‌کند و مرحله‌ی دوم یک image کوچک است که فقط باینری را تحویل می‌گیرد.

```dockerfile
FROM --platform=$BUILDPLATFORM golang:1.26 AS build
WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
ARG TARGETOS
ARG TARGETARCH
ARG VERSION=dev
RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -trimpath -ldflags="-s -w -X main.version=${VERSION}" \
    -o /out/api ./cmd/api

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/api /api
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/api"]
```

از بالا بخوانیم:

- مرحله‌ی build روی پلتفرم خود سازنده (`$BUILDPLATFORM`) اجرا می‌شود و برای هدف cross-compile می‌کند (`GOOS` و `GOARCH` از `TARGETOS` و `TARGETARCH` می‌آیند). به این ترتیب ساختن image با arm64 روی ماشین amd64 شبیه‌سازی لازم ندارد.
- اول `go.mod` را کپی می‌کنیم و `go mod download` را اجرا می‌کنیم. این لایه تا وقتی وابستگی‌ها عوض نشده دوباره استفاده می‌شود؛ تغییر کد منبع فقط لایه‌های بعدی را باطل می‌کند. این مفیدترین ترفند برای build سریع است.
- `ARG VERSION` با `-X main.version` وارد باینری می‌شود تا سرویس در حال اجرا بتواند بگوید کدام build است.
- مرحله‌ی نهایی کامپایلر ندارد و shell هم ندارد. `USER nonroot:nonroot` پروسه را با یک کاربر معمولی اجرا می‌کند، نه root.
- فایل `.dockerignore` (`.git`، `.github`، `bin`، لاگ‌ها، فایل‌های markdown و خود Dockerfile) حجم context ساخت را کوچک نگه می‌دارد.

برای مرحله‌ی نهایی سه انتخاب رایج هست، به برداشت من:

- **distroless/static با `:nonroot`**: طبق مستنداتش گواهی‌های CA، داده‌ی منطقه‌ی زمانی و یک کاربر غیر root دارد. ساده‌ترین انتخاب امن است. نداشتن shell یعنی دیباگ با `docker exec` سخت‌تر است.
- **scratch**: کوچک‌ترین ممکن، یک image خالی. گواهی‌های CA را باید خودتان کپی کنید و کاربر را خودتان بسازید.
- **alpine یا debian**: برای دیباگ shell دارند، به بهای بسته‌های بیشتری که باید وصله‌شان را به‌روز نگه دارید.

## CI با GitHub Actions

CI یعنی روی هر push یک ماشین کد را می‌گیرد، می‌سازد و تست‌ها را اجرا می‌کند. در GitHub Actions این فایل یک **workflow** در `.github/workflows/` است. workflow چند **job** دارد، هر job روی یک **runner** (یک ماشین تازه؛ این‌جا `ubuntu-latest`) اجرا می‌شود و هر job چند **step** دارد.

workflow ما دو job دارد:

- `test`: `go vet`، `go test -race ./...` و `go build ./...` را اجرا می‌کند.
- `image`: فقط بعد از موفقیت `test` و نه روی pull requestها اجرا می‌شود. با `GITHUB_TOKEN` داخلی به GHCR (رجیستری کانتینر GitHub) وارد می‌شود، بعد `docker/metadata-action` تگ‌های image را حساب می‌کند و `docker/build-push-action` می‌سازد و push می‌کند.

چند جزئیات که برایم مهم است:

- actionها به تگ کامل نسخه pin شده‌اند (`actions/checkout@v7.0.1`، `docker/build-push-action@v7.4.0` و بقیه). pin به commit SHA سخت‌گیرانه‌تر است، چون یک تگ را می‌شود جابه‌جا کرد.
- مجوز پیش‌فرض workflow برابر `contents: read` است. فقط job به اسم `image` اضافه بر آن `packages: write` می‌گیرد، پس job تست فقط دسترسی خواندنی به مخزن دارد و نمی‌تواند چیزی منتشر کند.
- `golangci-lint` را کنار گذاشتم. اضافه‌کردنش یک step است.

فایل workflow را با `actionlint` اعتبارسنجی کردم، یک linter برای فایل‌های GitHub Actions (نسخه‌ی 1.7.12):

```
$ actionlint .github/workflows/ci.yml
$ echo $?
0
```

بعد از یک نسخه‌ی کپی عمداً دو خطا ساختم: `runs-on: ubuntu-lastest` (غلط املایی) و یک ارجاع به step که از `steps.meta` به `steps.metadata` تغییر نام داده بود. `actionlint` هر دو را گرفت:

```
broken/ci-broken.yml:14:14: label "ubuntu-lastest" is unknown. available labels are ...
broken/ci-broken.yml:50:21: property "metadata" is not defined in object type
{meta: {conclusion: string; outcome: string; outputs: {string => string}}} [expression]
```

(در خروجی واقعی خط اول فهرست بلندی از labelهای معتبر دارد که حذفش کردم. غلط املایی برای هر دو job گزارش می‌شود، در خط‌های ۱۴ و ۲۷.) به یاد داشته باشید این چه چیزی را ثابت می‌کند: `actionlint` نحو و عبارت‌ها را بررسی می‌کند. ثابت نمی‌کند push به رجیستری کار می‌کند. آن یک اجرای واقعی روی GitHub می‌خواهد که انجام ندادم.

## مفاهیم دیپلوی

- **تنظیمات از محیط.** همان image همه‌جا اجرا می‌شود؛ فقط متغیرهای `ORDERS_*` بین محیط‌ها فرق می‌کنند.
- **راز داخل image نیست.** `ORDERS_DB_PASSWORD` هنگام شروع کانتینر تزریق می‌شود. هر چیزی که در یک لایه‌ی image نوشته شود را هر کسی که image را بگیرد می‌تواند بخواند.
- **liveness و readiness فرق دارند.** شکست liveness یعنی «دوباره راهم بینداز». شکست readiness یعنی «ترافیک نفرست». `/readyz` ما به محض شروع shutdown به حالت شکست می‌رود.
- **پنجره‌ی توقف.** پلتفرم SIGTERM می‌فرستد و بعد مدت محدودی صبر می‌کند تا پروسه را بکشد (روی Kubernetes این `terminationGracePeriodSeconds` است). timeout خاموشی ما، ۱۰ ثانیه، باید در آن پنجره جا شود. مقدار واقعی پلتفرم خودتان را بررسی کنید.
- **rollback با تگ.** تگ‌های تغییرناپذیر deploy کنید (`type=sha` در metadata action که طبق مستنداتش از SHA کامیت تگ می‌سازد)، تا rollback یعنی deploy تگ قبلی و نه build دوباره.

## دام‌های کانتینر و CI

- **Dockerfile ساخته نشد.** با build واقعی راستی‌آزمایی‌اش نکردم، پس پیش از اعتماد به آن `docker build` را اجرا کنید.
- **`-healthcheck` فقط `127.0.0.1` را بررسی می‌کند.** پورت را از `ORDERS_ADDR` برمی‌دارد. اگر سرور را روی آدرس میزبان دیگری bind کنید، بررسی شکست می‌خورد.
- **`latest` نسخه نیست.** به هر چیزی اشاره می‌کند که آخر بار push شده، پس نمی‌توانید بگویید چه چیزی در حال اجراست. از تگ SHA یا semver استفاده کنید.
- **`go test -race` به cgo نیاز دارد.** race detector یک toolchain C می‌خواهد که `ubuntu-latest` دارد. داخل build image با `CGO_ENABLED=0` کار نمی‌کند، پس تست جایش در job به اسم `test` است، نه در Dockerfile.
- **عوض‌شدن readiness همه‌ی ماجرا نیست.** سرویس ما خودش را «ناآماده» علامت می‌زند و بلافاصله شروع به خاموش‌شدن می‌کند. اینکه پلتفرم تا آن لحظه ارسال ترافیک را قطع کرده یا نه به خود پلتفرم بستگی دارد؛ روی بعضی‌ها یک خواب کوتاه بین این دو مرحله رایج است. این را امتحان نکردم.

## قدم بعدی

نوشته‌ی بعدی «زمان‌بند runtime و GC در Go» است. سرویس را فرستادیم؛ حالا داخل runtime گو را می‌بینیم که روی آن اجرا می‌شود، تا بفهمیم چرا goroutineها ارزان‌اند و garbage collector وقتی درخواست‌ها جواب داده می‌شوند چه می‌کند.
