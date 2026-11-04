+++
date = '2027-05-03T10:00:00+03:30'
draft = false
title = 'طراحی pipeline برای CI/CD'
contentType = 'engineering'
description = 'طراحی pipeline برای CI/CD در Go: مرحله‌های مرتب، آستانه‌ی coverage، build تکرارپذیر، deploy آبی/سبز با rollback و workflow بررسی‌شده.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["ci-cd", "pipeline", "github-actions", "software-engineering", "go", "deployment"]
cover = { image = "/images/covers/eng-ci-cd-pipeline-design.fa.png", alt = "طراحی pipeline برای CI/CD", hiddenInSingle = true }
+++

دو deploy از یک سرویس کوچک را تصور کنید. در اولی نسخه‌ی تازه آدرس listen خراب دارد. pipeline آن را بالا می‌آورد، می‌پرسد «سالمی؟»، جوابی نمی‌گیرد، نسخه‌ی قدیمی را سر جایش می‌گذارد و قرمز می‌شود. کسی بیدار نمی‌شود و هیچ کاربری چیزی نمی‌فهمد. در دومی یک نفر عصر جمعه فایل اجرایی را دستی روی server کپی می‌کند و از آدرس خراب از صندوق پشتیبانی باخبر می‌شود. pipeline برای این است که داستان اول، داستان عادی و کسل‌کننده باشد. داستان اول یکی از demoهای همین پست هم هست.

روش trunk-based در [feature flag و trunk-based development](/fa/posts/eng-feature-flags-trunk-based/) به چنین pipelineای وابسته است که روی هر merge اجرا شود. سه اصطلاح اینجا مدام با هم قاطی می‌شوند. {{< term "ci" "CI" >}} (یکپارچه‌سازی پیوسته) یعنی هر تغییر خودکار merge و بررسی می‌شود. تحویل پیوسته (continuous delivery) یعنی `main` همیشه در حالتی است که بشود منتشرش کرد. استقرار پیوسته (continuous deployment) یک قدم جلوتر می‌رود: هر تغییری که قبول شود بدون اینکه آدمی دکمه‌ای بزند منتشر هم می‌شود. پست‌های مرتبط: [تست در Go](/fa/posts/go-testing-basics/)، [هرم تست و TDD](/fa/posts/eng-testing-pyramid-tdd/) و [Docker، CI و deploy یک سرویس Go](/fa/posts/go-docker-ci-deploy/). نظرها مشخص شده‌اند. بقیه اجرا شده است.

> اجرای اولیه با Go 1.26 بود. برای این ویرایش pipeline، بررسی تکرارپذیری و deploy را با Go 1.27.3 دوباره اجرا کردم. demo یک مثال محلی است: یک سرویس کوچک، `scripts/ci.sh` و `scripts/deploy.sh` در یک repo git با نویسنده‌ی جعلی. workflow مربوط به GitHub Actions روی GitHub اجرا **نشد**. checksumها و hash مربوط به commit در خروجی‌ها به نسخه‌ی Go و به commit بستگی دارند، پس با مقدارهای نسخه‌ی اول این پست فرق دارند. روی ماشین شما هم فرق خواهند داشت.

## مرحله‌ها، اول ارزان‌ترین

pipeline فهرستی از مرحله‌هاست و ترتیب مهم است. بررسی‌های ارزانی را که زیاد شکست می‌خورند اول بگذارید و گران‌ها را آخر، تا شکست زود اجرا را متوقف کند و توسعه‌دهنده زود بفهمد. ترتیب من این است: format، vet، تست، دروازه‌ی coverage، build، checksum، smoke test.

یک ایده‌ی دیگر: script همان pipeline است و سرور CI فقط آن را صدا می‌زند. پس دقیقاً همان کار را روی لپ‌تاپ خودم اجرا می‌کنم و مجبور نیستم یک commit بفرستم تا بفهمم CI چه می‌گوید. **نظر من:** pipeline مخصوص pull request را کوتاه نگه دارید، چند دقیقه و نه ده‌ها دقیقه، چون بازخورد کند را دور می‌زنند.

مرحله‌های اول این را چاپ می‌کنند:

```text
== 1 format
== 2 vet
== 3 test
ok  	example.com/cidemo/internal/greet	2.426s	coverage: 80.0% of statements
```

format و vet وقتی راضی‌اند چیزی چاپ نمی‌کنند. تست‌ها با `-race -count=1` اجرا می‌شوند: race detector روشن است و نتیجه هیچ‌وقت از cache نمی‌آید. {{< term "flaky-test" "تست flaky" >}}، تستی که گاهی بی‌دلیل شکست می‌خورد و با تکرار سبز می‌شود، یک باگ است که باید درست شود؛ چیزی نیست که پشت یک تنظیم retry پنهانش کنید. (زمان اجرا در هر بار فرق می‌کند.)

## دروازه‌ی coverage

دروازه (gate) مرحله‌ای است که می‌تواند «نه» بگوید. این یکی وقتی شکست می‌خورد که {{< term "code-coverage" "coverage" >}}، یعنی سهم دستورهایی که تست‌ها اجرایشان می‌کنند، زیر یک آستانه باشد. یک تابع را عمداً بدون تست گذاشتم که ۸۰٫۰٪ می‌دهد. با حد ۹۰ pipeline متوقف می‌شود:

```text
== 4 coverage gate (min 90%)
total coverage: 80.0%
FAIL: coverage below 90%
```

با حد ۷۵ اجرا از build و smoke test هم گذشت و با `pipeline ok` تمام شد. حد پیش‌فرض در script برابر ۸۰ است.

coverage را فقط روی `./internal/...` می‌شمارم. با شمردن `main` هم، مجموع به ۲۳٫۵٪ افتاد، چون `main` تست ندارد، پس آن عدد چیدمان پروژه‌ی مرا اندازه می‌گرفت، نه تست‌هایم را. **به نظر من** دروازه کفی در برابر فرسایش است، نه هدف. coverage بالا ثابت نمی‌کند تست‌ها خوب‌اند.

## build، نسخه، checksum

بعد pipeline فایل اجرایی را یک بار می‌سازد، نسخه‌ای رویش می‌زند و checksum ثبت می‌کند:

```text
== 5 build
cidemo 0.1.0 (5572165)
== 6 checksum
24dfd3de06b004a6871320fa543045c505ede3a97f577068fca88e6c555daed5  cidemo
```

build از `-trimpath -ldflags "-X main.version=... -X main.commit=..."` استفاده می‌کند. خط اول جواب خود فایل اجرایی به `-version` است: نسخه و commitی را که از آن ساخته شده می‌گوید، پس وقتی چیزی در production اجرا می‌شود می‌توانید بفهمید چیست. checksum اثر انگشت فایل است. اگر دو build همان checksum را داشته باشند، بایت‌هایشان یکی است.

## آیا build تکرارپذیر است؟

{{< term "reproducible-build" "build تکرارپذیر" >}} از یک سورس واحد بایت‌های واحد می‌دهد. مفید است، چون می‌توانید مطمئن باشید فایلی که تست کردید همان فایلی است که منتشر می‌کنید. ساده‌ترین راه را رفتم: دو بار در دو پوشه‌ی مختلف build کردم و hashها را مقایسه کردم. اولین تلاش فرق داشت:

```text
24dfd3de06b004a6871320fa543045c505ede3a97f577068fca88e6c555daed5  dist-a/cidemo
753b835cfbe71a575683684f11a31c9e8f4f3ed7c568f3b5f412051a2d7b6e8e  dist-b/cidemo
```

با `go version -m` دلیلش را دیدم. Go مقدار `vcs.modified` را داخل فایل اجرایی می‌گذارد: در اولی `false` و در دومی `true`. build اول یک پوشه‌ی untracked به نام `dist-a/` ساخته بود، پس تا زمان build دوم git درخت را «تغییرکرده» می‌دید. بعد از اینکه `dist/` را به `.gitignore` اضافه کردم و هر دو بار داخل آن build کردم، hashها یکی شدند (`24dfd3de...`). پس build تکرارپذیر درخت تمیز می‌خواهد، نه فقط `-trimpath`. بدون `-trimpath` مسیرهای محلی داخل فایل اجرایی می‌روند. build روی ماشین‌های مختلف را امتحان نکردم.

## وابستگی‌ها و آسیب‌پذیری‌ها

`go list -m all` فقط `example.com/cidemo` را چاپ می‌کند، پس در این demo چیزی برای بررسی نیست. `govulncheck@v1.1.4` را هم امتحان کردم و در اجرای اولیه شکست خورد:

```text
govulncheck: fetching vulnerabilities: HTTP GET https://vuln.go.dev/index/modules.json.gz returned unexpected status: 403 Forbidden
```

پس مرحله‌ی آسیب‌پذیری روی این ماشین اجرا **نشد**. در یک pipeline واقعی آن را یک مرحله‌ی جدا نگه دارید.

## deploy: blue/green با دروازه‌ی سلامت

حالا deploy. `deploy.sh` یک پوشه‌ی ریشه را مثل یک server در نظر می‌گیرد. دو جایگاه دارد، `releases/blue` و `releases/green`، و یک symlink به نام `current` که می‌گوید کدام زنده است. script فایل اجرایی را در جایگاه بیکار کپی می‌کند، روی loopback بالایش می‌آورد، منتظر جواب `/healthz` می‌ماند و تازه بعد symlink `current` را جابه‌جا می‌کند. {{< term "blue-green-deployment" "blue/green" >}} در یک جمله همین است: نسخه‌ی جدید پیش از رسیدن هر ترافیکی سالم‌بودنش ثابت می‌شود.

این سه اجرا است. دو تای اول موفق‌اند و بین جایگاه‌ها عوض می‌شوند. برای سومی عمداً آدرس listen خراب می‌دهم:

```text
deploy: health ok, current -> releases/blue
deploy: health ok, current -> releases/green
deploy: health check FAILED on blue, rollback: current stays -> releases/green
```

در اجرای سوم، نسخه‌ی جدید هرگز جواب نمی‌دهد، `current` دست نمی‌خورد و script با کد ۱ خارج می‌شود، پس pipeline قرمز می‌شود. دقیق‌تر بگوییم، این «هرگز جابه‌جا نشد» است و نه «برگردانده شد»، اما برای کاربران اثرش یکی است. این همان خاصیت ارزان blue/green است.

چند اصطلاح دیگر: {{< term "canary-release" "canary" >}} اول سهم کوچکی از ترافیک را به نسخه‌ی جدید می‌فرستد، همان‌طور که در پست flagها بود. {{< term "rollback" "rollback" >}} در برابر roll-forward: کد آسان برمی‌گردد، داده نه. اگر یک release شکل پایگاه داده را عوض کرده باشد، برگشتن شاید ممکن نباشد، پس از migrationهای {{< term "expand-contract" "expand/contract" >}} استفاده کنید، یعنی شکل جدید را اول اضافه می‌کنید و قدیمی را بعداً حذف ([refactor امن](/fa/posts/eng-refactoring-safely/)).

## فایل workflow

همین مرحله‌ها در یک workflow برای GitHub Actions، یعنی `ci.yml`، می‌روند. یک job به نام `test` دارد با ماتریسی از نسخه‌های Go و cache مربوط به `actions/setup-go@v5`، `permissions: contents: read` و یک گروه `concurrency` که اجراهای قدیمی‌تر همان branch را لغو می‌کند. job به نام `deploy` مقدار `needs: test` دارد، پس فقط بعد از سبزشدن تست‌ها شروع می‌شود، و در `environment: production` اجرا می‌شود که می‌شود برایش reviewer اجباری تعیین کرد. از `secrets.DEPLOY_TOKEN` استفاده می‌کند.

در اجرای اولیه آن را با `actionlint` نسخه‌ی v1.7.7 بررسی کردم و قبول شد. وقتی `needs` را به یک غلط تایپی عوض کردم، پیام داد `job "deploy" needs job "tset" which does not exist`. این بار نتوانستم `actionlint` را دوباره اجرا کنم، پس آن نتیجه از اجرای اولیه است. job مربوط به deploy فقط یک طرح است: در workflow واقعی باید فایل اجرایی ساخته‌شده را از یک job به دیگری هم منتقل کند. طبق توصیه‌ی امنیتی GitHub، actionهای شخص ثالث را باید به یک SHA کامل commit pin کرد. من برای خوانایی از tagهای major استفاده کردم.

## چیزهایی که pipeline نباید جا بیندازد

- secretها جایشان مخزن secret در CI است، نه repo و نه لاگ.
- مرحله‌ی deploy را idempotent نگه دارید تا اجرای دوباره‌اش امن باشد.
- {{< term "smoke-test" "smoke test" >}} را جا نیندازید. unit testهای سبز هم می‌توانند فایلی را منتشر کنند که اصلاً بالا نمی‌آید.
- تعریف pipeline کد است. review‌اش کنید.

## قدم بعدی

پست بعدی «SLI، SLO و error budget» است. pipeline سبز می‌گوید یک release شروع شد. سؤال بعدی این است که آیا کاربران واقعاً خوب سرویس می‌گیرند.
