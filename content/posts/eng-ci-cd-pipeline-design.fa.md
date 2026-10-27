+++
date = '2027-05-03T10:00:00+03:30'
draft = false
title = 'طراحی pipeline برای CI/CD'
description = 'طراحی pipeline برای CI/CD در Go: مرحله‌های مرتب، آستانه‌ی coverage، build تکرارپذیر، deploy آبی/سبز با rollback و workflow بررسی‌شده.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["ci-cd", "pipeline", "github-actions", "software-engineering", "go", "deployment"]
cover = { image = "/images/covers/eng-ci-cd-pipeline-design.fa.png", alt = "طراحی pipeline برای CI/CD", hiddenInSingle = true }
+++

پست قبل، [feature flag و trunk-based development](/fa/posts/eng-feature-flags-trunk-based/)، با «pipeline‌ای که با هر merge اجرا می‌شود» تمام شد. این همان pipeline است. {{< term "ci" "CI" >}} هر تغییر را ادغام و بررسی می‌کند؛ continuous delivery یعنی `main` همیشه آماده‌ی انتشار است؛ continuous deployment یعنی بدون دخالت انسان منتشر هم می‌شود. مرتبط: [تست در Go](/fa/posts/go-testing-basics/)، [هرم تست و TDD](/fa/posts/eng-testing-pyramid-tdd/) و [Docker، CI و deploy سرویس Go](/fa/posts/go-docker-ci-deploy/). نظرها مشخص شده‌اند؛ بقیه اجرا شده است.

> Go 1.26. دمو نمونه‌ی محلی است: سرویس کوچک، `scripts/ci.sh` و `scripts/deploy.sh` در repoی git با نویسنده‌ی جعلی. workflow‌ی GitHub Actions روی GitHub **اجرا نشد**.

## مرحله‌ها، ارزان‌ترین اول

ترتیب بر اساس هزینه و ارزش سیگنال: format، vet، تست، آستانه‌ی coverage، build، checksum، smoke test. شکست باید اجرا را زود متوقف کند. خودِ اسکریپت pipeline است و سرور CI فقط آن را صدا می‌زند، پس همان را روی لپ‌تاپ هم اجرا می‌کنم. **نظر من:** pipelineِ PR کوتاه باشد (دقیقه، نه ده‌ها دقیقه)، چون بازخورد کند را دور می‌زنند.

```text
== 1 format
== 2 vet
== 3 test
ok  	example.com/cidemo/internal/greet	1.224s	coverage: 80.0% of statements
```

تست‌ها با `-race -count=1` اجرا می‌شوند: race detector روشن و بدون نتیجه‌ی cache‌شده. {{< term "flaky-test" "تست flaky" >}} که با تکرار می‌گذرد باگی است که باید رفع شود، نه تنظیمی به نام retry.

## آستانه‌ی coverage

وقتی {{< term "code-coverage" "coverage" >}} زیر آستانه باشد gate شکست می‌خورد. یک تابع را عمداً بدون تست گذاشتم و ۸۰٫۰٪ شد. با حد ۹۰:

```text
== 4 coverage gate (min 90%)
total coverage: 80.0%
FAIL: coverage below 90%
```

با حد ۷۵ اجرا ادامه یافت و با `pipeline ok` تمام شد. coverage را فقط روی `./internal/...` می‌شمارم: شمردن `main` جمع را به ۲۳٫۵٪ می‌رساند که ساختار پروژه‌ی مرا می‌سنجید، نه تست‌هایم را. **به نظر من** gate کف است در برابر فرسایش، نه هدف؛ coverage بالا خوب بودن تست‌ها را ثابت نمی‌کند.

## build، نسخه، checksum

```text
== 5 build
cidemo 0.1.0 (8874951)
== 6 checksum
1e236e486199babaee49164bc168dfc768fe7732b2a173d16c7b94e6503be4f9  cidemo
```

build با `-trimpath -ldflags "-X main.version=... -X main.commit=..."` ساخته می‌شود، پس باینری می‌گوید چیست.

## آیا build تکرارپذیر است؟

دو بار در دو پوشه‌ی متفاوت build کردم و hashها را مقایسه کردم. بار اول فرق داشتند:

```text
1e236e48...3be4f9  dist-a/cidemo
b5d744f5...956d08  dist-b/cidemo
```

`go version -m` دلیل را نشان داد: Go در یکی `vcs.modified=false` و در دیگری `true` نوشته بود، چون build اول پوشه‌ی untracked به نام `dist-a/` ساخته بود. بعد از افزودن `dist/` به `.gitignore` و build داخل آن، هر دو hash یکی شد (`1e236e48...`). پس {{< term "reproducible-build" "build تکرارپذیر" >}} فقط `-trimpath` نمی‌خواهد، درخت تمیز هم می‌خواهد. بدون `-trimpath` مسیرها وارد باینری می‌شوند؛ build بین دو ماشین را امتحان نکردم.

## وابستگی‌ها و آسیب‌پذیری

`go list -m all` فقط `example.com/cidemo` را چاپ کرد، پس چیزی برای ممیزی نیست. `govulncheck@v1.1.4` را امتحان کردم و شکست خورد:

```text
govulncheck: fetching vulnerabilities: HTTP GET https://vuln.go.dev/index/modules.json.gz returned unexpected status: 403 Forbidden
```

یعنی مرحله‌ی آسیب‌پذیری روی این ماشین **اجرا نشد**. در pipeline واقعی آن را مرحله‌ی جدا نگه دارید.

## deploy: آبی/سبز با gate سلامت

`deploy.sh` یک پوشه‌ی ریشه را مثل سرور می‌بیند: `releases/blue` و `releases/green` و symlink به نام `current`. باینری را در slot بیکار می‌گذارد، روی loopback اجرا می‌کند، منتظر `/healthz` می‌ماند و بعد symlink را عوض می‌کند. خروجی واقعی سه اجرا؛ آخری با آدرس listen خراب عمدی:

```text
deploy: health ok, current -> releases/blue
deploy: health ok, current -> releases/green
deploy: health check FAILED on blue, rollback: current stays -> releases/green
```

دقیقاً این «هرگز سوییچ نشد» است، نه بازگرداندن وضعیت، و اسکریپت با کد ۱ خارج می‌شود تا pipeline قرمز شود. این ویژگی ارزان {{< term "blue-green-deployment" "blue/green" >}} است. {{< term "canary-release" "canary" >}} اول سهم کوچکی را می‌فرستد، مثل پست پرچم‌ها. {{< term "rollback" "rollback" >}} در برابر roll-forward: کد آسان برمی‌گردد و داده نه، پس از migration با الگوی {{< term "expand-contract" "expand/contract" >}} استفاده کنید ([refactor امن](/fa/posts/eng-refactoring-safely/)).

## فایل workflow

`ci.yml` یک job به نام `test` با matrix نسخه‌ی Go و cache در `actions/setup-go@v5` دارد، `permissions: contents: read`، یک گروه `concurrency` که اجراهای قدیمی را لغو می‌کند، و job‌ی `deploy` با `needs: test` در `environment: production` (که می‌توان برایش reviewer اجباری تنظیم کرد) و `secrets.DEPLOY_TOKEN`. `actionlint` نسخه‌ی v1.7.7 آن را پذیرفت؛ با غلط املایی در `needs` گزارش داد `job "deploy" needs job "tset" which does not exist`. job‌ی deploy فقط طرح است: باید باینری را بین jobها هم منتقل کند. طبق توصیه‌ی امنیتی GitHub، actionهای شخص ثالث را به commit SHA کامل pin کنید؛ من برای خوانایی از tag اصلی استفاده کردم.

## چند نکته‌ی مهم

- secretها در مخزن secret خود CI هستند، نه در repo و نه در log.
- مرحله‌ی deploy را idempotent بنویسید تا اجرای دوباره امن باشد.
- {{< term "smoke-test" "smoke test" >}} را حذف نکنید؛ تست‌های واحد سبز هم می‌توانند باینری‌ای را بفرستند که بالا نمی‌آید.
- تعریف pipeline کد است: review‌اش کنید.

## تمرین

مرحله‌ای اضافه کنید که اگر `gofmt -l` فایلی نشان داد شکست بخورد، بعد عمداً آن را خراب کنید و توقف pipeline را ببینید.

## قدم بعدی

پست بعدی «SLI، SLO و error budget» است.
