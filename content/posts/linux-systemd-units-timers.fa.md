+++
date = '2027-04-18T10:00:00+03:30'
draft = false
title = 'systemd: واحدها و timerها'
description = 'systemd برای سرویس Go: ساختار unit، SIGTERM و بعد SIGKILL، مقایسه‌ی timer با cron، سخت‌سازی و یک linter واقعاً اجراشده برای unitها.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "systemd", "timers", "services", "go", "devops"]
cover = { image = "/images/covers/linux-systemd-units-timers.fa.png", alt = "systemd: واحدها و timerها", hiddenInSingle = true }
+++

دیر یا زود برنامه‌ی Go یا Node.js شما باید روی سرور اجرا شود: با بوت بالا بیاید، بعد از کرش دوباره راه بیفتد، تمیز متوقف شود و هر شب کاری انجام دهد. در بیشتر توزیع‌های Linux این کار با {{< term "systemd" "systemd" >}} انجام می‌شود. این پنجمین پست سری Linux است، بعد از [/proc و مشاهده‌ی سیستم](/fa/posts/linux-proc-observability/).

> این پست را روی مک نوشتم؛ هیچ چیزش روی Linux اجرا نشد. systemd و `systemctl` و `journalctl` روی این دستگاه وجود ندارند و Docker خاموش ماند. واقعیت‌ها از man pageهای freedesktop.org آمده‌اند (systemd.service، systemd.timer، systemd.exec، systemd.kill، systemd.time). فقط آنچه **اجرا شد** واقعاً اجرا شده: یک linter پایتون و یک برنامه‌ی Go که فقط برای Linux cross-compile شد و هرگز اجرا نشد.

## systemd چه چیزی را مدیریت می‌کند

systemd همان PID 1 است، اولین پروسه، که بقیه را بالا می‌آورد و نظارت می‌کند. همه‌چیز یک **unit** است که با یک {{< term "unit-file" "unit file" >}} توصیف می‌شود و پسوندش نوعش را می‌گوید: `.service` و `.timer` و `.socket` و `.target` و `.mount` و `.path`. امروز `.service` و `.timer` را لازم داریم.

## ساختار یک سرویس

این `good/worker.service` برای یک worker کوچک Go است (ایده‌اش از [خاموشی تمیز برای workerهای Go](/fa/posts/go-graceful-shutdown-workers/)):

```ini
[Unit]
Description=Example batch worker
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
ExecStart=/opt/worker/worker
Restart=on-failure
RestartSec=5
User=worker
WorkingDirectory=/opt/worker
EnvironmentFile=-/etc/worker/worker.env
TimeoutStopSec=30
NoNewPrivileges=yes
ProtectSystem=strict
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

- `After=` فقط ترتیب را تعیین می‌کند؛ `Wants=` واحد دیگر را نرم و `Requires=` سخت به مجموعه می‌آورد.
- `Type=`: `simple` و `exec` برای پروسه‌های بلندمدت‌اند (مستندات `simple` را تا جای ممکن توصیه می‌کند)، `notify` منتظر اعلام آماده‌بودن سرویس می‌ماند و `oneshot` اجرا می‌شود و تمام می‌شود.
- `ExecStart=` باید مسیر مطلق باشد. `Restart=on-failure` بعد از خروج ناموفق دوباره راه می‌اندازد و `RestartSec=` فاصله است (طبق مستندات پیش‌فرض 100ms).
- `EnvironmentFile=-path`: خط تیره یعنی نبودن فایل خطا نیست.
- `[Install]` فقط برای `systemctl enable` مهم است: `WantedBy=multi-user.target` واحد را به بوت وصل می‌کند.

## توقف: اول SIGTERM، بعد SIGKILL

هنگام توقف، systemd ابتدا {{< term "sigterm" "SIGTERM" >}} (یا `KillSignal=`) را می‌فرستد و اگر بعد از `TimeoutStopSec=` پروسه‌ای مانده باشد {{< term "sigkill" "SIGKILL" >}} می‌فرستد. پس worker باید SIGTERM را مدیریت کند. `main.go` من مثل [پروسه و سیگنال](/fa/posts/linux-processes-signals/) از `signal.NotifyContext` با `syscall.SIGTERM` استفاده می‌کند و برمی‌گردد؛ این یعنی {{< term "graceful-shutdown" "خاموشی تمیز" >}}. `TimeoutStopSec=` را بلندتر از کندترین batch بگذارید. **اجرا شد:** `GOOS=linux GOARCH=arm64 go vet ./...` و `go build` موفق بودند و `file` خروجی ELF aarch64 نشان داد. **آن باینری را هرگز اجرا نکردم.**

## Timerها

یک `.timer` سرویسی با همان نام را فعال می‌کند. از `good/worker-report.timer`:

```ini
[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
RandomizedDelaySec=5min
```

- `OnCalendar=` زمان ساعت دیواری است. systemd.time(7) می‌گوید `daily` برابر `*-*-* 00:00:00` و `hourly` برابر `*-*-* *:00:00` و `weekly` برابر `Mon *-*-* 00:00:00` است. `systemd-analyze calendar` عبارت را بررسی می‌کند؛ نتوانستم اجرایش کنم.
- `OnBootSec=` و `OnUnitActiveSec=` نسبت به بوت و آخرین فعال‌سازی‌اند.
- `Persistent=true` کار از دست‌رفته‌ی زمان خاموشی را اجرا می‌کند و فقط روی timerهای `OnCalendar=` اثر دارد.
- `RandomizedDelaySec=` بار را پخش می‌کند و `AccuracySec=` اجازه می‌دهد systemd بیدارشدن‌ها را ادغام کند، پس timerها دقیق نیستند.

سرویسِ یک timer معمولاً `Type=oneshot` است. در مقایسه با {{< term "cron" "cron" >}}: timer جبران اجرای از دست‌رفته، وابستگی، لاگ جدا برای هر unit و `systemctl list-timers` دارد؛ cron ساده‌تر و کوتاه‌تر است و روی سیستم‌های بدون systemd هم کار می‌کند.

## سخت‌سازی و لاگ

`NoNewPrivileges=yes` جلوی گرفتن دسترسی بیشتر را می‌گیرد، `ProtectSystem=strict` فایل‌سیستم را جز مسیرهای مجاز (`ReadWritePaths=`) فقط‌خواندنی می‌کند، `PrivateTmp=yes` یک `/tmp` خصوصی می‌دهد و `DynamicUser=yes` یک کاربر موقت می‌سازد (طبق systemd.exec چند مورد از این‌ها را ضمناً فعال می‌کند). خروجی stdout/stderr در {{< term "journald" "ژورنال" >}} می‌نشیند: `journalctl -u worker`. بعد از ویرایش unit دستور `systemctl daemon-reload` و بعد `systemctl start|stop|enable|status worker`. **هیچ‌کدام را اجرا نکردم.**

## linter‌ای که اجرا شد

`unitlint.py` unitها را می‌خواند (کلید تکراری و ادامه‌ی خط با `\`) و چند قاعده را بررسی می‌کند. روی مجموعه‌ی سالم (**اجرا شد**):

```
good/worker-report.service: ok
good/worker-report.timer: ok
good/worker.service: ok
```

روی دو unit عمداً خراب:

```
bad/api.service: 4 finding(s)
  - ExecStart is not an absolute path: api --port 8080
  - Restart not set (service stays down after a crash)
  - no [Install]: `systemctl enable` has no effect
  - Environment given more than once (valid; all are applied)
bad/cleanup.timer: 2 finding(s)
  - matching service not found: cleanup.service
  - no [Install] WantedBy=timers.target
```

این در برابر `systemd-analyze verify` اسباب‌بازی است و آن را نتوانستم اجرا کنم. ارزیاب OnCalendar را ننوشتم چون نمی‌توانستم با systemd واقعی آزمایشش کنم.

## چند نکته‌ی مهم

- `After=` چیزی را راه نمی‌اندازد؛ با `Wants=` یا `Requires=` ترکیبش کنید.
- بدون handler برای SIGTERM هر توقف بعد از timeout با SIGKILL تمام می‌شود.
- unit را ویرایش کردید، `daemon-reload` بزنید؛ فراموشی‌اش تعریف قدیمی را اجرا می‌کند.
- timerها عمداً کمی دیر اجرا می‌شوند (`AccuracySec=`)؛ برای زمان دقیق مناسب نیستند.
- سخت‌سازی می‌تواند سرویسی را که بیرون از مسیرهای مجاز می‌نویسد خراب کند؛ مرحله‌به‌مرحله اضافه کنید.

## تمرین

روی یک ماشین Linux، worker نمونه را به‌صورت سرویس نصب کنید، `systemctl stop` بزنید و ژورنال را بخوانید. آیا قبل از timeout خارج می‌شود؟ بعد timer با `OnCalendar=minutely` اضافه کنید، با `systemd-analyze calendar` بررسی کنید و `list-timers` را ببینید.

## قدم بعدی

پست بعدی «cgroup و namespace: پایه‌ی کانتینر» است.
