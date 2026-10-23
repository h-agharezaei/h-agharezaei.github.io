+++
date = '2027-02-28T10:00:00+03:30'
draft = false
title = 'Docker، CI و دیپلوی سرویس Go'
description = 'کانتینری کردن سرویس Go: باینری استاتیک، Dockerfile چندمرحله‌ای با distroless، endpoint‌های سلامت و آمادگی و CI با GitHub Actions و actionlint.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "docker", "ci", "github-actions", "deploy"]
cover = { image = "/images/covers/go-docker-ci-deploy.fa.png", alt = "Docker، CI و دیپلوی سرویس Go", hiddenInSingle = true, hiddenInList = true }
+++

موضوع مقاله‌ی قبل profiling بود. حالا سرویس باید از لپ‌تاپ من بیرون برود. سرویس `orders` از [مقاله‌ی net/http](/fa/posts/go-http-api-stdlib/) را در یک کانتینر می‌گذاریم و CI را مسئول تست و انتشارش می‌کنیم. مدیریت SIGTERM از [مقاله‌ی graceful shutdown](/fa/posts/go-graceful-shutdown-workers/) اینجا مهم‌تر هم می‌شود، چون orchestrator دقیقاً با همین سیگنال کانتینر را متوقف می‌کند.

> **توضیح صادقانه.** Docker daemon روی این ماشین خاموش است و تصمیم گرفتم روشنش نکنم، پس `docker build` را هرگز اجرا نکردم. Dockerfile و workflow زیر با هدف درست بودن نوشته شده‌اند، ولی image ساخته نشده است. چیزی که واقعاً اجرا کردم، روی Go 1.26.0 (macOS arm64): باینری استاتیک cross-compile شده، endpoint‌های سلامت، `-healthcheck`، SIGTERM و `actionlint` روی workflow. بنابراین در این مقاله نه اندازه‌ی image هست و نه خروجی `docker build`.

## باینری استاتیک

با `CGO_ENABLED=0` باینری به libc وابسته نیست. آن را برای linux/arm64 به چهار شکل ساختم:

```
$ CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -o plain ./cmd/api
$ ... go build -trimpath ...                    # trim
$ ... go build -ldflags="-s -w" ...             # sw
$ ... go build -trimpath -ldflags="-s -w -X main.version=v1.2.3" ...   # full
plain  9114814 bytes
trim   9110092 bytes
sw     6291618 bytes
full   6291618 bytes
```

`-s -w` جدول symbol و اطلاعات debug از نوع DWARF را حذف می‌کند و حدود ۲٫۸ مگابایت کم می‌کند. `-trimpath` تقریباً چیزی کم نمی‌کند (۴٫۷ کیلوبایت)؛ کارش پاک کردن مسیرهای محلی از باینری است تا build‌ها تکرارپذیر باشند. `-X main.version=...` یک متغیر رشته‌ای را موقع link مقدار می‌دهد. خروجی `file` برای build کامل: `ELF 64-bit LSB executable, ARM aarch64, statically linked, stripped`.

## endpoint‌های سلامت و فلگ healthcheck

سه چیز به `main.go` اضافه کردم: `/healthz` (**liveness**، یعنی «پروسه جواب می‌دهد»)، `/readyz` (**readiness**، یعنی «به من ترافیک بفرست») و فلگ `-healthcheck`. آمادگی یک `atomic.Bool` است که بعد از بالا آمدن listener روشن می‌شود و به‌محض رسیدن SIGTERM خاموش:

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

فلگ `-healthcheck` باینری را وادار می‌کند `/healthz` خودش را صدا بزند و با کد ۰ یا ۱ خارج شود. image از نوع distroless نه shell دارد و نه `curl`، پس `HEALTHCHECK` در Docker این‌طور ممکن می‌شود: `HEALTHCHECK CMD ["/api", "-healthcheck"]` (در Docker اجرایش نکردم). در Kubernetes به‌جایش probe‌های HTTP می‌گذارید. باینری ساخته‌شده برای میزبان را با تنظیمات از محیط اجرا کردم:

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

لاگ `"shutting down"` و بعد `"stopped"` را نشان داد. بدون سرور، `-healthcheck` پیام `connection refused` چاپ می‌کند و با کد ۱ خارج می‌شود. بدون `ORDERS_DB_PASSWORD` هم مثل قبل سرویس با کد ۲ بالا نمی‌آید.

## Dockerfile

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

اول `go.mod` را کپی می‌کنیم و `go mod download` می‌زنیم؛ تا وقتی وابستگی‌ها عوض نشوند این لایه از cache می‌آید و تغییر کد فقط لایه‌های بعدی را باطل می‌کند. فایل `.dockerignore` (`.git`، `bin`، لاگ‌ها و مستندات) context ساخت را کوچک نگه می‌دارد. مرحله‌ی نهایی کامپایلر و shell ندارد.

مصالحه‌ی انتخاب مرحله‌ی نهایی، تا جایی که می‌دانم:

- **distroless/static با `:nonroot`**: طبق مستندات‌اش گواهی‌های CA، داده‌ی timezone و کاربر غیر root دارد. ساده‌ترین انتخاب امن. نبودن shell یعنی دیباگ با `docker exec` سخت‌تر است.
- **scratch**: کوچک‌ترین، ولی گواهی‌های CA و کاربر را باید خودتان اضافه کنید.
- **alpine/debian**: shell برای دیباگ دارد، به قیمت بسته‌های بیشتری که باید patch شوند.

## CI با GitHub Actions

workflow یک job به نام `test` دارد (`go vet`، `go test -race ./...`، `go build ./...`) و یک job به نام `image` که با `GITHUB_TOKEN` به GHCR وارد می‌شود و `docker/metadata-action` و `docker/build-push-action` را اجرا می‌کند (روی pull request نه). نسخه‌ی action‌ها با تگ کامل pin شده (`actions/checkout@v7.0.1`، `docker/build-push-action@v7.4.0` و غیره؛ pin با SHA کامیت سخت‌گیرانه‌تر است). فقط job مربوط به `image` مجوز `packages: write` دارد. `golangci-lint` را کنار گذاشتم؛ اضافه‌کردنش یک step است. فایل را اعتبارسنجی کردم:

```
$ go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 .github/workflows/ci.yml
$ echo $?
0
```

بعد عمداً خرابش کردم (`steps.meta` را به `steps.metadata` تغییر دادم):

```
ci-broken.yml:50:21: property "metadata" is not defined in object type
{meta: {conclusion: string; outcome: string; outputs: {string => string}}} [expression]
```

غلط املایی `runs-on: ubuntu-lastest` هم به‌عنوان label ناشناخته گرفته شد. `actionlint` سینتکس و expression‌ها را می‌سنجد؛ ثابت نمی‌کند push کار می‌کند. برای آن باید یک اجرای واقعی روی GitHub داشت.

## مفاهیم دیپلوی

- **تنظیمات از محیط**: یک image همه‌جا اجرا می‌شود؛ فقط متغیرهای `ORDERS_*` فرق می‌کنند.
- **راز‌ها داخل image نیستند**: `ORDERS_DB_PASSWORD` موقع اجرا تزریق می‌شود؛ هر چیزی در یک لایه را هر کسی که image را pull کند می‌تواند بخواند.
- **liveness در برابر readiness**: شکست liveness یعنی «من را ری‌استارت کن»؛ شکست readiness یعنی «ترافیک نفرست». `/readyz` ما موقع خاموشی خاموش می‌شود.
- **پنجره‌ی توقف**: orchestrator SIGTERM می‌فرستد و قبل از kill منتظر می‌ماند (در Kubernetes: `terminationGracePeriodSeconds`). timeout خاموشی ما، ۱۰ ثانیه، باید در این پنجره جا شود. مقدار واقعی پلتفرم‌تان را بررسی کنید.
- **rollback با تگ**: تگ‌های تغییرناپذیر دیپلوی کنید (`type=sha`)، تا rollback یعنی دیپلوی تگ قبلی، نه build دوباره.

## چند نکته که باید حواستان باشد

- Dockerfile را با build واقعی نیازموده‌ام؛ قبل از اعتماد، `docker build` را خودتان اجرا کنید.
- `-healthcheck` به `127.0.0.1` و پورت `ORDERS_ADDR` وصل می‌شود؛ اگر روی میزبان دیگری bind کنید شکست می‌خورد.
- `latest` نسخه نیست؛ از تگ SHA یا semver استفاده کنید.
- `go test -race` به cgo نیاز دارد؛ روی `ubuntu-latest` مشکلی نیست، ولی داخل build با `CGO_ENABLED=0` نه.

## قدم بعدی

مقاله‌ی بعد: scheduler و garbage collector در Go، تا ببینیم داخل runtime پروسه‌ای که تازه ship کردیم چه می‌گذرد.
