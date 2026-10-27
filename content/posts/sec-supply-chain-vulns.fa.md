+++
date = '2027-05-05T10:00:00+03:30'
draft = false
title = 'زنجیره‌ی تأمین و آسیب‌پذیری وابستگی‌ها'
description = 'امنیت زنجیره‌ی تأمین نرم‌افزار با اجرای واقعی در Go، npm و Python: go.sum، npm audit، hash در lockfile، اسکریپت نصب و pip-audit.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "supply-chain", "dependencies", "go", "npm", "python"]
cover = { image = "/images/covers/sec-supply-chain-vulns.fa.png", alt = "زنجیره‌ی تأمین و آسیب‌پذیری وابستگی‌ها", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [مدیریت راز و کلید](/fa/posts/sec-secrets-management/)، از اعتبارنامه‌های خودتان محافظت می‌کرد. این مقاله درباره‌ی کدی است که شما ننوشته‌اید. بیشتر چیزی که یک سرویس سفارش‌ها اجرا می‌کند، مثل سرویس [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/)، یک {{< term "transitive-dependency" "وابستگی غیرمستقیم" >}} است که هرگز نخوانده‌اید. این همان {{< term "software-supply-chain" "زنجیره‌ی تأمین نرم‌افزار" >}} است. پیش‌زمینه: [بسته‌ها و ماژول‌ها](/fa/posts/go-packages-modules/)، [npm، package.json و lockfile](/fa/posts/node-npm-package-json/) و [محیط Python: venv و uv](/fa/posts/py-environment-uv-venv/).

> فقط دفاعی. همه‌چیز در پروژه‌های موقت با cache خصوصی اجرا شد و بعد پاک شد. بدون جزئیات اکسپلویت و بدون هیچ هدف بیرونی. خروجی advisoryها همان است که در تاریخ 2026-10-27 برگشت.

## Go: pin، verify و دستکاری

ماژولی با دو وابستگی عمداً قدیمی (`uuid v1.3.0` و `yaml.v2 v2.2.2`):

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

فایل `go.sum` برای هر نسخه‌ی ماژول یک hash با پیشوند `h1:` نگه می‌دارد. اولین بار که ماژولی اضافه می‌شود، Go این hash را با {{< term "checksum-database" "پایگاه checksum" >}} در `sum.golang.org` هم مقایسه می‌کند تا همه بایت‌های یکسان بگیرند. برای «رفع خطا» هرگز آن را خاموش نکنید. Go از minimal version selection استفاده می‌کند: کمترین نسخه‌ای را برمی‌دارد که همه‌ی `go.mod`ها را راضی کند، پس ارتقا فقط وقتی اتفاق می‌افتد که خودتان بخواهید.

بعد یک فایل در cache خصوصی ماژول را ویرایش کردم:

```
$ go mod verify
github.com/google/uuid v1.3.0: dir has been modified (<tmp>/gomod/github.com/google/uuid@v1.3.0)
exit=1
```

یک hash را هم در `go.sum` خراب کردم و با cache تمیز دوباره build کردم:

```
verifying github.com/google/uuid@v1.3.0: checksum mismatch
	downloaded: h1:t6JiXgmwXMjEs8VusXIJk2BXHsn+wx8BZdTaoZ5fu7I=
	go.sum:     h1:AAAAXgmwXMjEs8VusXIJk2BXHsn+wx8BZdTaoZ5fu7I=

SECURITY ERROR
This download does NOT match an earlier download recorded in go.sum.
```

بررسی قدیمی‌بودن: `go list -m -u all` نشان داد `uuid v1.3.0 [v1.6.0]` و `yaml.v2 v2.2.2 [v2.4.0]`. `govulncheck` (نسخه‌ی v1.9.0) را هم امتحان کردم و اینجا شکست خورد: `fetching vulnerabilities: ... vuln.go.dev/index/modules.json.gz returned unexpected status: 403 Forbidden`. پس یافته‌ی Go برای نمایش ندارم. آن را در CI‌ای اجرا کنید که به پایگاه دسترسی دارد.

## npm: audit، integrity، ci و اسکریپت‌ها

`minimist@1.2.0` را دقیق pin کردم. `npm audit` گزارش داد:

```
minimist  1.0.0 - 1.2.5
Severity: critical
Prototype Pollution in minimist - https://github.com/advisories/GHSA-vh95-rmgr-6w4m
Prototype Pollution in minimist - https://github.com/advisories/GHSA-xvch-5gv4-984h
fix available via `npm audit fix --force`
Will install minimist@1.2.8, which is outside the stated dependency range
```

برای این دسته از باگ، {{< term "prototype-pollution" "prototype pollution" >}} را ببینید. {{< term "lockfile" "lockfile" >}} مبدأ و hash هر بسته را ثبت می‌کند:

```
"node_modules/minimist": {
  "version": "1.2.0",
  "resolved": "https://registry.npmjs.org/minimist/-/minimist-1.2.0.tgz",
  "integrity": "sha512-7Wl+Jz+IGWuSdgsQEJ4JunV0si/iMhg42MnQQG6h1R6TNeVenp4U9x5CC5v/gYqz/fENLQITAWXidNtVL0NNbw=="
}
```

`npm ci` دقیقاً lockfile را نصب می‌کند و انحراف را نمی‌پذیرد. `package.json` را بدون به‌روزکردن lock به `1.2.8` تغییر دادم:

```
npm ERR! `npm ci` can only install packages when your package.json and package-lock.json or npm-shrinkwrap.json are in sync.
npm ERR! Invalid: lock file's minimist@1.2.0 does not satisfy minimist@1.2.8
```

در CI از `npm ci` استفاده کنید؛ `npm install` را فقط برای تغییر عمدی وابستگی‌ها.

کد زمان نصب هم اجرا می‌شود. بسته‌ی خودم `"postinstall": "echo postinstall ran on this machine"` داشت. نصب tarball آن با `--foreground-scripts`:

```
> hook-demo@1.0.0 postinstall
> echo postinstall ran on this machine
```

با `--ignore-scripts` آن خط نیامد. اینجا فقط یک echo بی‌خطر است، ولی می‌تواند هر دستوری باشد؛ پس در CI از `--ignore-scripts` استفاده کنید، مگر بسته واقعاً مرحله‌ی build لازم داشته باشد.

## Python: audit و hash

با pin کردن `jinja2==2.11.2`، ابزار `pip-audit 2.9.0` چاپ کرد:

```
Found 5 known vulnerabilities in 1 package
jinja2 2.11.2  PYSEC-2021-66   2.11.3
jinja2 2.11.2  PYSEC-2026-1473 3.1.3
(three more rows, fixes 3.1.4 to 3.1.6)
```

دستور `uv pip compile requirements.in --generate-hashes` برای هر فایل از هر بسته یک خط `--hash=sha256:...` می‌نویسد. نصب‌ها با `--require-hashes` بود؛ با hash عمداً صفرشده برای `markupsafe==1.1.1`:

```
× Failed to download and build `markupsafe==1.1.1`
╰─▶ Hash mismatch for `markupsafe==1.1.1`
    Expected: sha256:0000...0000
    Computed: sha256:29872e92839765e546828bb7754a68c418d927cd064fd4708fab9fe9c8bb116b
```

## مفاهیمی که اجرا نکردم

- {{< term "typosquatting" "Typosquatting" >}}: بسته‌ی مخرب با نامی شبیه بسته‌ی محبوب. Dependency confusion: بسته‌ی عمومی که جای نام داخلی را بگیرد. نام‌های تازه را بازبینی کنید و registry خصوصی را scope کنید.
- {{< term "sbom" "SBOM" >}} (فرمت‌های CycloneDX و SPDX): فهرست آنچه تحویل می‌دهید. من آن را تولید نکردم.
- GitHub Actions را به commit SHA کامل pin کنید، نه تگ قابل‌جابه‌جایی. Dependabot یا Renovate برای به‌روزرسانی pull request باز می‌کنند. هیچ‌کدام اجرا نشد.
- Reproducible build: همان سورس، همان بایت‌ها. مرتبط: مقاله‌ی برنامه‌ریزی‌شده‌ی طراحی pipeline برای CI/CD.

| اکوسیستم | Pin | Verify | Scan |
|---|---|---|---|
| Go | `go.mod` + `go.sum` | `go mod verify` | `govulncheck` |
| npm | نسخه‌ی دقیق + lockfile | `npm ci` | `npm audit` |
| Python | `--generate-hashes` | `--require-hashes` | `pip-audit` |

## چند نکته‌ی مهم

- اسکنر فقط advisoryهای شناخته‌شده را نشان می‌دهد؛ نبودن یافته اثبات امن‌بودن نیست.
- `npm audit fix --force` ممکن است از major عبور کند. قبل از اعمال بخوانید.
- به‌روزرسانی کورکورانه هم ریسک است: diff فایل lock را بازبینی کنید.
- registry و CI هم بخشی از زنجیره‌اند: توکن‌هایشان را حفاظت کنید (مقاله‌ی راز و کلید).

## تمرین

یکی از سرویس‌هایتان را بردارید، اسکنر اکوسیستمش را اجرا کنید و یک سیاست یک‌صفحه‌ای بنویسید: چه کسی، هر چند وقت یک‌بار به‌روز می‌کند و چه چیزی release را متوقف می‌کند.

## قدم بعدی

مقاله‌ی بعدی «SSRF و deserialization ناامن» است.
