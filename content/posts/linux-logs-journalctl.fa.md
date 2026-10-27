+++
date = '2027-05-30T10:00:00+03:30'
draft = false
title = 'لاگ‌ها و journalctl'
description = 'لاگ‌ها و journalctl از روی مستندات: فیلدهای ژورنال، اولویت‌ها، فیلترها، نگهداری، rate limit و logrotate، با نمونه‌های Go برای slog، parser و linter.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "logging", "journalctl", "journald", "logrotate", "slog", "go", "macos"]
cover = { image = "/images/covers/linux-logs-journalctl.fa.png", alt = "لاگ‌ها و journalctl", hiddenInSingle = true }
+++

این را روی یک مک نوشتم؛ هیچ‌چیز اینجا روی Linux اجرا نشده است. این دوازدهمین پست سری Linux است، بعد از [کاربر، sudo و capability](/fa/posts/linux-users-sudo-capabilities/). حقایق از man pageهای journalctl، journald.conf، systemd.journal-fields، syslog(3) و logrotate است؛ متن Linux‌مانند با عبارت «نمونه‌ی تصویری، ضبط‌نشده» علامت خورده. مرتبط: [systemd: واحدها و تایمرها](/fa/posts/linux-systemd-units-timers/) و [پیکربندی، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/).

## لاگ متنی و ژورنال

لاگ‌های کلاسیک فایل متنی زیر `/var/log` هستند. {{< term "journald" "journald" >}} به‌جایش رکوردهای ساختاریافته و ایندکس‌شده نگه می‌دارد؛ یعنی هر خط مجموعه‌ای از فیلد است. طبق systemd.journal-fields، `MESSAGE` متن خوانا، `PRIORITY` عددی از 0 تا 7، `SYSLOG_IDENTIFIER` برچسب برنامه، `_PID` پروسه و `_SYSTEMD_UNIT` واحد است. فیلدهای با پیشوند underscore را خود journald اضافه می‌کند، نه برنامه. هر چه سرویس {{< term "systemd" "systemd" >}} در stdout یا stderr بنویسد ثبت می‌شود؛ پس سرویس می‌تواند ساده در stdout لاگ کند. این نظر من است، نه قانون.

اولویت‌ها از {{< term "syslog-severity" "syslog(3)" >}} می‌آیند: emerg 0، alert 1، crit 2، err 3، warning 4، notice 5، info 6، debug 7. syslog «facility» هم دارد؛ journalctl گزینه‌ی `--facility` دارد.

## journalctl

طبق man page:

- `-u UNIT` خروجی را به یک واحد و `-b` به بوت فعلی محدود می‌کند.
- `-p err` همان سطح **و مهم‌تر از آن** را نشان می‌دهد؛ `-p warning..err` بازه است.
- `--since` و `--until` زمان می‌گیرند؛ `-f` ورودی‌های تازه را دنبال می‌کند.
- `-o json` هر ورودی را یک شیء JSON چاپ می‌کند، `-o json-pretty` همان را چندخطی و `-o cat` فقط پیام را.
- `--vacuum-size=` و `--vacuum-time=` قدیمی‌ترین فایل‌های بایگانی‌شده را پاک می‌کنند؛ `--disk-usage` حجم را نشان می‌دهد.

نمونه‌ی تصویری، ضبط‌نشده:

```
$ journalctl -u demo.service -p err -b -o cat
db timeout
```

## نگهداری و rate limit

`Storage=` در journald.conf یکی از `volatile`، `persistent`، `auto` یا `none` است. `auto` فقط اگر `/var/log/journal` وجود داشته باشد persistent رفتار می‌کند؛ وگرنه لاگ در حافظه است و با ریبوت می‌رود. محدودیت نرخ برای هر سرویس است: بیش از `RateLimitBurst` پیام در `RateLimitIntervalSec` دور ریخته می‌شود و یک پیام تعدادشان را گزارش می‌کند. پیش‌فرض مستند، 10000 پیام در 30 ثانیه است و 0 آن را خاموش می‌کند. پس حلقه‌ی کرش می‌تواند خطوط را از دست بدهد.

## لاگ از Go، واقعی

`log/slog` را با handler از نوع JSON اجرا کردم. `ReplaceAttr` یک فیلد را پنهان می‌کند و زمان را حذف می‌کند (فقط برای ثابت‌ماندن خروجی):

```
$ lx12 slog
{"level":"INFO","msg":"request","method":"GET","status":200,"token":"[REDACTED]"}
{"level":"ERROR","msg":"db failed","err":"timeout","attempt":3}
```

فراخوانی debug با سطح info فیلتر شد. این همان {{< term "structured-logging" "لاگ ساختاریافته" >}} است که collector را قادر می‌کند بر اساس فیلد فیلتر کند. پنهان‌سازی در handler شبکه‌ی ایمنی است، نه برنامه.

## چرخش لاگ، نوشته و linted

{{< term "log-rotation" "چرخش" >}} جلوی رشد بی‌پایان فایل را می‌گیرد. یک rotator ساده‌ی مبتنی بر اندازه نوشتم (وقتی نوشتن بعدی از 200 بایت بگذرد بچرخ، 2 فایل قدیمی نگه دار) و 12 رویداد نوشتم:

```
app.log      76 bytes
app.log.1   186 bytes
app.log.2   185 bytes
```

رویدادهای اولیه رفته‌اند؛ معنی `keep` همین است. `logrotate` واقعی فایل پیکربندی دارد؛ طبق man page، `rotate N` تعداد N فایل قدیمی نگه می‌دارد (پیش‌فرض 0، یعنی لاگ قدیمی پاک می‌شود)، `size`، `compress` و `delaycompress` هم هست، و {{< term "copytruncate" "copytruncate" >}} کپی می‌کند و همان‌جا خالی می‌کند، پس چند خط ممکن است از دست برود و `create` بی‌اثر می‌شود. linter من نام دستورها را با زیرمجموعه‌ای از man page، وجود `rotate`، جفت compress و همین تعارض را بررسی می‌کند. **logrotate نیست**. خروجی واقعی روی پیکربندی درست و بد:

```
$ lx12 lint testdata/good.conf
OK: no findings (this is not logrotate itself)
$ lx12 lint testdata/bad.conf
WARN: line 3: unknown directive "compres"
WARN: no 'rotate N': the man page says the default is 0, so old logs are removed, not kept
WARN: delaycompress without compress has no effect
WARN: copytruncate and create together: create has no effect (man page)
```

## خواندن JSON ژورنال

parser‌ای برای قالب `-o json` نوشتم (هر خط یک شیء، مقدارها رشته) و فیلتری شبیه `-u x -p err`. تست‌هایش از خطوط **ساختگی** در قالب مستند استفاده می‌کند و `go test -race` گذشت. با `GOOS=linux GOARCH=arm64 go vet` و build هم گذشت، ولی روی Linux اجرا نشد.

## مک چه چیزی نشان می‌دهد

نزدیک‌ترین چیز واقعی اینجا unified log در macOS است. با `logger` و یک نشانگر تصادفی خطی نوشتم و فقط همان نشانگر را با `log show --style compact` پرسیدم (زمان و شناسه‌های پروسه حذف شده):

```
<time> Df logger[<pid>:<tid>] marker-RAND hello
```

| | journald | unified log در macOS |
|---|---|---|
| خواندن | `journalctl` | `log show`، `log stream` |
| فیلتر | فیلد، `-p`، `-u` | `--predicate`، subsystem |
| نوشتن | stdout، `logger`، syslog | `os_log`، `logger` |

## چند نکته‌ی مهم

- `Storage=` را بررسی کنید: `auto` بدون `/var/log/journal` با ریبوت لاگ را از دست می‌دهد.
- زمان را UTC لاگ کنید.
- لاگ audit از لاگ برنامه جداست: خواننده و نگهداری متفاوت. پست امنیتی لاگ و audit را ببینید.
- دیسک پر هم مشکل لاگ است: نوشتن با ENOSPC شکست می‌خورد؛ با vacuum یا چرخش سقف بگذارید.
- پیش از لاگ، پنهان کنید؛ [مدیریت secretها و کلیدها](/fa/posts/sec-secrets-management/).

## تمرین

روی یک VM دورریختنی سرویسی بسازید که یک خطا لاگ کند، با `journalctl -u ... -p err -o json-pretty` پیدایش کنید، بعد `RateLimitBurst` را کم کنید و ببینید چه می‌شود.

## قدم بعدی

پست بعدی «strace و perf برای عیب‌یابی» است.
