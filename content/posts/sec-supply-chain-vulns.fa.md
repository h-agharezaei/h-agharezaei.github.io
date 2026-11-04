+++
date = '2027-05-05T10:00:00+03:30'
draft = false
title = 'زنجیره‌ی تأمین و آسیب‌پذیری وابستگی‌ها'
description = 'امنیت زنجیره‌ی تأمین نرم‌افزار با اجرای واقعی در Go، npm و Python: go.sum، npm audit، hash در lockfile، اسکریپت نصب و pip-audit.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "supply-chain", "dependencies", "go", "npm", "python"]
cover = { image = "/images/covers/sec-supply-chain-vulns.fa.png", alt = "زنجیره‌ی تأمین و آسیب‌پذیری وابستگی‌ها", hiddenInSingle = true }
+++

فایل `go.mod` یک سرویس کوچک سفارش‌ها را باز کنید؛ چند خط بیشتر نیست. حالا `go list -m all` را اجرا کنید؛ فهرست بلندتر است. هر ماژولِ اضافه را یک غریبه نوشته، یکی از کتابخانه‌هایی که خودتان انتخاب کرده‌اید آن را آورده، و حالا داخل سرویس شما با همان اختیارات کد خودتان اجرا می‌شود. شما آن را نخوانده‌اید. احتمالاً هیچ‌کس در تیمتان هم نخوانده است.

به این وضع می‌گویند {{< term "software-supply-chain" "زنجیره‌ی تأمین نرم‌افزار" >}}: هرچه در برنامه‌ی شما هست و خودتان ننوشته‌اید، به‌علاوه‌ی ابزار و سرورهایی که آن را به دست شما می‌رسانند. بیشترِ این کدها {{< term "transitive-dependency" "وابستگی غیرمستقیم" >}} هستند، یعنی بسته‌ای که مستقیم سراغش نرفته‌اید ولی چیزی که سراغش رفته‌اید به آن نیاز دارد. اگر سرویس سفارش‌ها را مثل [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) نوشته باشید، این درباره‌ی آن هم صدق می‌کند.

مقاله‌ی قبل، [مدیریت راز و کلید](/fa/posts/sec-secrets-management/)، از اعتبارنامه‌هایی محافظت می‌کرد که مال خودتان است. این مقاله درباره‌ی کدی است که مال شما نیست. سؤال کوچک و عملی است: وقتی فردا `go build` یا `npm ci` یا `pip install` را اجرا می‌کنم، از کجا بدانم همان بایت‌های امروز را گرفته‌ام؟ و از کجا بفهمم بعضی از این بایت‌ها یک مشکل امنیتی شناخته‌شده دارند؟ پیش‌زمینه: [بسته‌ها و ماژول‌ها](/fa/posts/go-packages-modules/)، [npm، package.json و lockfile](/fa/posts/node-npm-package-json/) و [محیط Python: venv و uv](/fa/posts/py-environment-uv-venv/).

> این مقاله فقط دفاعی است. همه‌چیز در پروژه‌های موقت با cache خصوصی اجرا شد که بعداً پاکشان کردم؛ چیزی منتشر نشد و به هیچ هدف بیرونی دست نزدم. متن advisoryهای npm و ردیف‌های pip-audit مال اجرای اولیه در تاریخ 2026-10-27 است. برای این بازنویسی دموهای Go، npm و `--require-hashes` در uv را دوباره با Go 1.27.3 و npm 10.5.2 اجرا کردم و خروجی‌ها یکی بود، مگر جایی که خلافش را بگویم.

## ایده‌ی اصلی: pin، verify، scan

هر سه اکوسیستمی که پایین می‌آید همین سه ایده را دارند، فقط با اسم فایل‌های متفاوت.

1. **Pin (میخ‌کردن).** دقیق بنویسید کدام نسخه و کدام بایت‌ها را استفاده می‌کنید. شماره‌ی نسخه فقط یک قول است؛ hash فایل یک بررسی است.
2. **Verify (راستی‌آزمایی).** هر بار که کد دانلود می‌شود، آن را با چیزی که نوشته‌اید مقایسه کنید و اگر فرق داشت بلند و واضح شکست بخورید.
3. **Scan (اسکن).** جدا از این‌ها، از یک پایگاه آسیب‌پذیری‌های شناخته‌شده بپرسید آیا نسخه‌های pinشده‌ی شما در آن هست یا نه.

Pin و verify از شما در برابر بسته‌ای محافظت می‌کنند که بی‌صدا زیر پایتان عوض می‌شود. Scan از شما در برابر بسته‌ای محافظت می‌کند که از همان روز اول بد بوده است. هر دو لازم است، چون به دو سؤال متفاوت جواب می‌دهند.

## Go: pin، verify و دستکاری

یک ماژول کوچک به اسم `example.com/orders` ساختم با دو وابستگی عمداً قدیمی: `uuid v1.3.0` و `yaml.v2 v2.2.2`. اول ببینیم Go فکر می‌کند ماژول به چه چیزهایی وابسته است:

```
$ go list -m all
example.com/orders
github.com/google/uuid v1.3.0
gopkg.in/check.v1 v0.0.0-20161208181325-20d25e280405
gopkg.in/yaml.v2 v2.2.2
$ go mod graph | wc -l
       5
$ go mod why -m gopkg.in/yaml.v2
example.com/orders
gopkg.in/yaml.v2
$ go mod verify
all modules verified
```

خط‌به‌خط:

- `go list -m all` ماژول اصلی و همه‌ی ماژول‌های build را فهرست می‌کند. من دو وابستگی نوشته بودم، ولی سه وابستگی هست: `gopkg.in/check.v1` خودش آمده، چون `yaml.v2` به آن نیاز دارد. این همان وابستگی غیرمستقیم است، با گوشت و پوست.
- `go mod graph | wc -l` تعداد یال‌های گراف وابستگی را می‌شمارد. ۵ تاست (ماژول من به دو وابستگی‌اش، خط‌های نسخه‌ی Go، و `yaml.v2` به `check.v1`).
- `go mod why -m` جواب می‌دهد «این ماژول چرا اینجاست؟» و مسیری از کد شما تا آن را چاپ می‌کند. این‌جا `yaml.v2` را خود `main.go` مستقیم import کرده است.
- `go mod verify` ماژول‌های cache محلی را دوباره hash می‌کند و با `go.sum` می‌سنجد. همه‌چیز درست است.

«میخ‌کردن» کجاست؟ در `go.sum`. این فایل برای هر نسخه‌ی هر ماژول یک hash با پیشوند `h1:` نگه می‌دارد. اولین بار که ماژولی به پروژه اضافه می‌شود، Go این hash را با یک دفتر عمومی هم مقایسه می‌کند، یعنی {{< term "checksum-database" "پایگاه checksum" >}} در `sum.golang.org`. هدفش این است که همه‌ی دنیا برای یک نسخه‌ی مشخص همان بایت‌ها را بگیرند و نویسنده‌ی بسته نتواند به آدم‌های مختلف کد متفاوت بدهد. برای «رفع خطا» هرگز این بررسی را خاموش نکنید. یک نکته‌ی دیگر درباره‌ی Go: کمترین نسخه‌ای را برمی‌دارد که همه‌ی `go.mod`ها را راضی کند (به این می‌گویند minimal version selection). یعنی انتشار جدید یک وابستگی تا وقتی خودتان نخواهید وارد build شما نمی‌شود.

حالا خرابش کنیم. یک فایل از `uuid` را داخل cache خصوصی ماژول‌هایم ویرایش کردم، انگار چیزی روی ماشین کد دانلودشده را دست‌کاری کرده باشد:

```
$ go mod verify
github.com/google/uuid v1.3.0: dir has been modified (<tmp>/gomod/github.com/google/uuid@v1.3.0)
exit=1
```

hash آن پوشه دیگر با `go.sum` نمی‌خواند، پس `go mod verify` اسم ماژول را می‌گوید، دلیل را می‌گوید و با کد خروج ۱ تمام می‌شود، که یک job در CI را قرمز می‌کند.

آزمایش دوم برعکس است: بایت‌های روی شبکه درست‌اند ولی `go.sum` غلط است. چند کاراکتر اول hash مربوط به `uuid` را در `go.sum` عوض کردم و با cache خالی دوباره build کردم:

```
verifying github.com/google/uuid@v1.3.0: checksum mismatch
	downloaded: h1:t6JiXgmwXMjEs8VusXIJk2BXHsn+wx8BZdTaoZ5fu7I=
	go.sum:     h1:AAAAXgmwXMjEs8VusXIJk2BXHsn+wx8BZdTaoZ5fu7I=

SECURITY ERROR
This download does NOT match an earlier download recorded in go.sum.
```

(پیام کامل Go چند خط دیگر هم دارد، درباره‌ی سرور مبدأ و `go help module-auth`؛ این‌جا کوتاهش کرده‌ام.) Go build را قبول نمی‌کند. مهم نیست فایل «حق دارد» یا دانلود؛ نکته این است که هر اختلافی یک علامت ایست است و یک آدم باید نگاهش کند.

برای اینکه ببینیم نسخه‌ها قدیمی‌اند یا نه، `go list -m -u all` چاپ کرد `uuid v1.3.0 [v1.6.0]` و `yaml.v2 v2.2.2 [v2.4.0]`؛ داخل کروشه جدیدترین نسخه است. برای `check.v1` هم یک pseudo-version جدیدتر نشان داد که این‌جا نیاورده‌ام. قدیمی بودن یعنی آسیب‌پذیر بودن نیست. برای آن اسکنر آسیب‌پذیری لازم است، یعنی `govulncheck`. در اجرای اولیه نتوانستم از آن استفاده کنم (`fetching vulnerabilities: ... vuln.go.dev/index/modules.json.gz returned unexpected status: 403 Forbidden`). این بار هم که دوباره امتحان کردم، باینری `govulncheck` روی ماشین من با نسخه‌ی Go قدیمی‌تری از نسخه‌ی فعلی ساخته شده بود و پکیج‌ها را بار نکرد. پس هنوز یافته‌ای از Go برای نمایش ندارم. آن را در CI اجرا کنید، جایی که پایگاه آسیب‌پذیری در دسترس است و ابزار با toolchain خودتان ساخته می‌شود.

## npm: audit، integrity، ci و اسکریپت‌ها

برای npm نسخه‌ی `minimist@1.2.0` را دقیق در `package.json` pin کردم، نسخه‌ی قدیمی با advisoryهای شناخته‌شده، و `npm audit` را اجرا کردم:

```
minimist  1.0.0 - 1.2.5
Severity: critical
Prototype Pollution in minimist - https://github.com/advisories/GHSA-vh95-rmgr-6w4m
Prototype Pollution in minimist - https://github.com/advisories/GHSA-xvch-5gv4-984h
fix available via `npm audit fix --force`
Will install minimist@1.2.8, which is outside the stated dependency range
```

(سرتیتر و خط‌های خلاصه را نیاورده‌ام؛ گزارش واقعی `node_modules/minimist` و «1 critical severity vulnerability» را هم چاپ می‌کند.) خط اول می‌گوید کدام نسخه‌ها آسیب‌پذیرند، `1.0.0 - 1.2.5`، و `1.2.0` من داخل این بازه است. دو لینک advisory عمومی برای {{< term "prototype-pollution" "prototype pollution" >}} هستند؛ نوعی باگ که در آن کلیدی که مهاجم می‌فرستد، مثل `__proto__`، prototype مشترک همه‌ی آبجکت‌های پروسه را تغییر می‌دهد. دو خط آخر پیشنهاد اصلاح npm است، همراه با هشدار: نسخه‌ی اصلاح‌شده بیرون از بازه‌ای است که من نوشته بودم.

audit از وجود یک باگ خبر می‌دهد. چیزی که جلوی غافلگیری را می‌گیرد {{< term "lockfile" "lockfile" >}} است، یعنی `package-lock.json`. برای هر بسته نسخه، نشانی دقیق دانلود و یک hash به اسم `integrity` از tarball ثبت می‌کند:

```
"node_modules/minimist": {
  "version": "1.2.0",
  "resolved": "https://registry.npmjs.org/minimist/-/minimist-1.2.0.tgz",
  "integrity": "sha512-7Wl+Jz+IGWuSdgsQEJ4JunV0si/iMhg42MnQQG6h1R6TNeVenp4U9x5CC5v/gYqz/fENLQITAWXidNtVL0NNbw=="
}
```

`npm ci` دقیقاً همان چیزی را نصب می‌کند که lockfile می‌گوید، hashها را می‌سنجد و اگر `package.json` و lock با هم نخوانند ادامه نمی‌دهد. برای دیدنش، `package.json` را بدون دست‌زدن به lock به `1.2.8` تغییر دادم:

```
npm ERR! `npm ci` can only install packages when your package.json and package-lock.json or npm-shrinkwrap.json are in sync. Please update your lock file with `npm install` before continuing.
npm ERR! Invalid: lock file's minimist@1.2.0 does not satisfy minimist@1.2.8
```

در CI از `npm ci` استفاده کنید و `npm install` را فقط روزی که عمداً می‌خواهید وابستگی‌ها را عوض کنید. وگرنه «install» بی‌صدا lock را بازنویسی می‌کند و pin شما از بین می‌رود.

یک کار دیگر هم هست که مدیر بسته می‌کند و معمولاً یادمان می‌رود: وقت نصب کد اجرا می‌کند. بسته‌ی آزمایشی خودم در `package.json` این را داشت: `"postinstall": "echo postinstall ran on this machine"`. نصب آن با نمایش خروجی اسکریپت (`--foreground-scripts`) این را چاپ کرد:

```
> hook-demo@1.0.0 postinstall
> echo postinstall ran on this machine

postinstall ran on this machine
```

دو خط اول npm است که اعلام می‌کند چه اسکریپتی را می‌خواهد اجرا کند و خط آخر خروجی خود اسکریپت است. با `--ignore-scripts` هیچ‌کدام از این خط‌ها نیامد. این‌جا فقط یک `echo` بی‌خطر است، ولی همین قلاب می‌توانست با اختیارات شما هر دستوری را اجرا کند، روی لپ‌تاپ شما یا روی runner‌ی CI. پس در CI از `--ignore-scripts` استفاده کنید، مگر بسته‌ای واقعاً مرحله‌ی build لازم داشته باشد.

## Python: audit و hash

با pin کردن `jinja2==2.11.2`، ابزار `pip-audit` (نسخه‌ی 2.9.0، در اجرای اولیه) چاپ کرد:

```
Found 5 known vulnerabilities in 1 package
jinja2 2.11.2  PYSEC-2021-66   2.11.3
jinja2 2.11.2  PYSEC-2026-1473 3.1.3
(three more rows, fixes 3.1.4 to 3.1.6)
```

هر ردیف این است: بسته و نسخه‌ی من، شناسه‌ی advisory، و اولین نسخه‌ای که مشکل در آن حل شده. اینجا دو ردیف را آورده‌ام و سه ردیف دیگر را همان‌طور که در اجرای اولیه بود خلاصه کرده‌ام. برای این بازنویسی نتوانستم `pip-audit` را دوباره اجرا کنم، چون نصبش در زمانی که برای آن گذاشته بودم تمام نشد؛ پس این ردیف‌ها را عکسی از همان روز بدانید. پایگاه advisory با گذشت زمان بزرگ‌تر می‌شود.

برای pin کردن، `uv pip compile requirements.in --generate-hashes` فایل `requirements.txt` را می‌نویسد، با یک خط `--hash=sha256:...` برای هر فایل قابل‌دانلودِ هر بسته. وقتی با `--require-hashes` نصب می‌کنید، pip یا uv هر فایلی را که hashش در فهرست نباشد رد می‌کند. برای دیدن شکست، فایلی ساختم که hash بسته‌ی `markupsafe==1.1.1` در آن همه‌اش صفر است:

```
× Failed to download and build `markupsafe==1.1.1`
╰─▶ Hash mismatch for `markupsafe==1.1.1`
    Expected: sha256:0000...0000
    Computed: sha256:29872e92839765e546828bb7754a68c418d927cd064fd4708fab9fe9c8bb116b
```

`Expected` چیزی است که فایل گفته و `Computed` hash چیزی است که دانلود شده. (خروجی واقعی hashهای بلند را در خط‌های جدا می‌نویسد؛ من در یک خط گذاشتم.) این را با `uv pip install --require-hashes` دوباره اجرا کردم و hash محاسبه‌شده همان اجرای اولیه بود.

## مفاهیمی که اجرا نکردم

این‌ها هم بخشی از تصویرند، ولی نشانشان نداده‌ام و فقط توصیفشان می‌کنم.

- {{< term "typosquatting" "Typosquatting" >}} یعنی بسته‌ی مخرب با نامی شبیه یک بسته‌ی محبوب، به این امید که کسی اشتباه تایپ کند. ترفند مرتبط dependency confusion است: بسته‌ی عمومی با نامی که با یکی از بسته‌های داخلی شما یکی است. دفاعش خسته‌کننده است: نام بسته‌های تازه را قبل از افزودن نگاه کنید و registry خصوصی را طوری تنظیم کنید که نام‌های داخلی هرگز از registry عمومی حل نشوند.
- {{< term "sbom" "SBOM" >}} (فهرست مواد نرم‌افزار، با فرمت‌هایی مثل CycloneDX و SPDX) فهرست همه‌چیزی است که تحویل می‌دهید. وقتی آسیب‌پذیری تازه‌ای اعلام می‌شود، با آن می‌توانید با جست‌وجو در یک فایل بفهمید «آیا ما درگیریم؟». من آن را تولید نکردم.
- workflow در GitHub Actions که از تگ قابل‌جابه‌جایی استفاده کند می‌تواند زیر پایتان عوض شود. pin کردن action به commit SHA کامل جلویش را می‌گیرد. Dependabot یا Renovate می‌توانند برای بالابردن نسخه‌ها pull request باز کنند. هیچ‌کدام را اجرا نکردم.
- Reproducible build یعنی همان سورس همان بایت‌ها را بدهد، تا کس دیگری هم بتواند باینری شما را وارسی کند. مرتبط: مقاله‌ی طراحی pipeline برای CI/CD در نقشه‌ی راه.

| اکوسیستم | Pin | Verify | Scan |
|---|---|---|---|
| Go | `go.mod` + `go.sum` | `go mod verify` | `govulncheck` |
| npm | نسخه‌ی دقیق + lockfile | `npm ci` | `npm audit` |
| Python | `--generate-hashes` | `--require-hashes` | `pip-audit` |

## آنچه اسکنر به شما نمی‌گوید

- اسکنر فقط advisoryهای شناخته‌شده را گزارش می‌دهد. نبودن یافته اثبات امن‌بودن نیست؛ فقط یعنی هنوز کسی advisory ثبت نکرده است.
- `npm audit fix --force` ممکن است از یک نسخه‌ی major بپرد و برنامه را خراب کند. قبل از پذیرفتن بخوانید چه چیزی نصب می‌کند.
- به‌روزرسانی کورکورانه هم ریسک است. وقتی lockfile عوض می‌شود، diffش را مثل کد بازبینی کنید.
- registry و سیستم CI هم بخشی از زنجیره‌اند. توکن دزدیده‌شده‌ی انتشار یا CI به کسی اجازه می‌دهد چیزی را که تحویل می‌دهید عوض کند؛ مثل هر راز دیگری از آن‌ها محافظت کنید (مقاله‌ی قبل).

## تمرین

یکی از سرویس‌های خودتان را بردارید و اسکنر اکوسیستمش را اجرا کنید. بعد یک سیاست یک‌صفحه‌ای بنویسید: چه کسی وابستگی‌ها را به‌روز می‌کند، هر چند وقت یک‌بار، و کدام یافته جلوی release را می‌گیرد.

## قدم بعدی

مقاله‌ی بعد «SSRF و deserialization ناامن» است. از کدی که ننوشته‌اید به ورودی‌ای می‌رسیم که ننوشته‌اید: آدرسی که کاربر به سرور شما می‌دهد و مشتی بایت که سرور شما دوباره به آبجکت تبدیل می‌کند.
