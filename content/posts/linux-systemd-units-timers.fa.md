+++
date = '2027-04-18T10:00:00+03:30'
draft = false
title = 'systemd: واحدها و timerها'
description = 'systemd برای سرویس Go: ساختار unit، SIGTERM و بعد SIGKILL، مقایسه‌ی timer با cron، سخت‌سازی و یک linter واقعاً اجراشده برای unitها.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "systemd", "timers", "services", "go", "devops"]
cover = { image = "/images/covers/linux-systemd-units-timers.fa.png", alt = "systemd: واحدها و timerها", hiddenInSingle = true }
+++

دیر یا زود برنامه‌ی Go یا Node.js شما باید روی سرور اجرا شود، و «اجرا شود» یعنی بیشتر از `./app &` در ترمینال. باید با بوت ماشین بالا بیاید. اگر ساعت 3 صبح کرش کرد، باید بی‌آن‌که کسی وارد سرور شود برگردد. وقتی نسخه‌ی تازه deploy می‌کنید، باید تمیز متوقف شود و نه وسط یک کار. و گزارش شبانه باید هر شب اجرا شود، حتی اگر سرور آن لحظه خاموش بوده. در بیشتر توزیع‌های Linux، همه‌ی این کارها را {{< term "systemd" "systemd" >}} انجام می‌دهد.

این پست ادامه‌ی [/proc و مشاهده‌ی سیستم](/fa/posts/linux-proc-observability/) در سری Linux است: آنجا پروسه‌ها را نگاه کردیم و اینجا می‌بینیم چه کسی آن‌ها را شروع می‌کند، دوباره راه می‌اندازد و زمان‌بندی می‌کند. ایده‌ی اصلی کوچک است. با systemd شما اسکریپتی نمی‌نویسید که برنامه را شروع کند و مراقبش باشد. یک فایل متنی کوتاه می‌نویسید که *اعلام می‌کند* برنامه چیست و چطور باید زندگی کند، و systemd به‌عنوان ناظر آن را برقرار می‌کند.

> این پست را روی Mac نوشتم و هیچ‌چیزش روی Linux اجرا نشد. systemd و `systemctl` و `journalctl` روی این ماشین نیستند و Docker خاموش ماند. واقعیت‌های مربوط به systemd از man pageهای freedesktop.org آمده‌اند (systemd.service و systemd.timer و systemd.exec و systemd.kill و systemd.time) و آن‌ها را مستندات نام می‌برم. آنچه اجرا شد با **اجرا شد** علامت خورده است: یک linter با Python و یک برنامه‌ی Go که فقط برای Linux cross-compile شد و هرگز اجرا نشد.

## systemd چه چیزی را مدیریت می‌کند

systemd همان PID 1 است، اولین پروسه‌ای که هسته راه می‌اندازد، و بقیه را شروع و نظارت می‌کند. هرچه مدیریت می‌کند **unit** نام دارد و هر unit با یک {{< term "unit-file" "unit file" >}} توصیف می‌شود، یک فایل متنی کوچک به سبک INI. پسوند فایل نوع unit را می‌گوید: `.service` (یک پروسه)، `.timer` (یک زمان‌بندی)، `.socket`، `.target` (گروهی از unitها، مثل «سیستم کاملاً بالا آمده»)، `.mount` و `.path`. در این پست دو تا لازم داریم: `.service` و `.timer`.

## کالبدشکافی یک service

این `good/worker.service` است، unit file یک worker کوچک Go (worker هم‌روح [خاموشی نرم برای workerهای Go](/fa/posts/go-graceful-shutdown-workers/) است). اول بخوانیدش و بعد خط‌به‌خط مرورش می‌کنیم:

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
KillSignal=SIGTERM
NoNewPrivileges=yes
ProtectSystem=strict
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

فایل سه بخش دارد. `[Unit]` می‌گوید این unit چیست و با بقیه چه رابطه‌ای دارد، `[Service]` می‌گوید پروسه چطور اجرا شود و `[Install]` می‌گوید وقتی unit را enable کنید چه می‌شود. طبق man pageها:

- `After=` فقط ترتیب است: «بعد از آن unit شروع کن». unit دیگر را شروع نمی‌کند. `Wants=` آن unit را نرم به همراه می‌آورد (اگر شکست خورد، ما باز شروع می‌شویم) و `Requires=` سخت. برای همین فایل هر دو را دارد.
- `Type=` می‌گوید systemd چه زمانی سرویس را «شروع‌شده» حساب کند. `simple` یعنی «بلافاصله بعد از fork شدن پروسه» و `exec` یعنی «بعد از این‌که برنامه واقعاً اجرا شد»، پس نبودن فایل اجرایی یا `User=` ناموجود به‌صورت شکست گزارش می‌شود. man page برای سرویس‌های طولانی‌مدت `exec` را توصیه می‌کند. `notify` منتظر می‌ماند تا خود سرویس به systemd بگوید آماده است و `oneshot` برای برنامه‌هایی است که اجرا می‌شوند و تمام می‌شوند.
- `ExecStart=` دستور است. کلمه‌ی اولش باید مسیر مطلق باشد، یا یک نام ساده که systemd آن را در فهرست ثابت پوشه‌های خودش پیدا کند. مسیر مطلق انتخاب امن است.
- `Restart=on-failure` سرویس را بعد از خروج ناتمیز دوباره راه می‌اندازد: کد خروج غیرصفر، سیگنال یا timeout. `RestartSec=` مکث پیش از راه‌اندازی دوباره است؛ طبق مستندات پیش‌فرضش 100 میلی‌ثانیه است.
- `User=` و `WorkingDirectory=` می‌گویند چه کسی و کجا برنامه را اجرا کند. `EnvironmentFile=-path` متغیرهای محیطی را از یک فایل می‌خواند و خط تیره یعنی نبودن فایل خطا نیست.
- `[Install]` فقط برای `systemctl enable` مهم است: `WantedBy=multi-user.target` unit را به بوت عادی وصل می‌کند، پس با هر بوت شروع می‌شود.

## توقف: اول SIGTERM، بعد SIGKILL

شروع کردن نیمه‌ی آسان است. وقتی سرویسی را متوقف می‌کنید (یا نسخه‌ی تازه deploy می‌کنید)، systemd {{< term "sigterm" "SIGTERM" >}} می‌فرستد (یا هر چیزی که `KillSignal=` بگوید)، تا `TimeoutStopSec=` صبر می‌کند و اگر پروسه‌ای مانده باشد {{< term "sigkill" "SIGKILL" >}} می‌فرستد. در [پروسه و سیگنال](/fa/posts/linux-processes-signals/) دیدیم معنایش چیست: SIGTERM را می‌شود گرفت و برای تمیزکاری به کار برد و SIGKILL را نه. پس worker باید SIGTERM را مدیریت کند.

`main.go` من این کار را با `signal.NotifyContext` روی `syscall.SIGTERM` می‌کند: چاپ می‌کند `worker: started`، هر 5 ثانیه یک «batch» انجام می‌دهد و وقتی سیگنال رسید یک خط چاپ می‌کند و با کد خروج 0 برمی‌گردد. این یک {{< term "graceful-shutdown" "خاموشی نرم" >}} (graceful shutdown) است. `TimeoutStopSec=` را بزرگ‌تر از کندترین batch بگذارید، وگرنه systemd باز هم worker را وسط کار می‌کشد.

**اجرا شد:** `GOOS=linux GOARCH=arm64 go vet ./...` و `go build` پاس شدند و `file` خروجی را یک فایل اجرایی ELF برای aarch64 نشان داد. **آن باینری را هرگز اجرا نکردم** و زیر systemd هم اجرا نکردم، پس نمی‌توانم نشان دهم `systemctl stop worker` چه چاپ می‌کند.

## Timerها

برای کار شبانه می‌شود از cron استفاده کرد، ولی systemd ابزار خودش را دارد. یک unit از نوع `.timer` خودش چیزی اجرا نمی‌کند: سرویسی را که هم‌نام آن است *فعال می‌کند* (`foo.timer` سرویس `foo.service` را شروع می‌کند، مگر `Unit=` چیز دیگری بگوید). کار در سرویس است و timer می‌گوید کی. از `good/worker-report.timer`:

```ini
[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
RandomizedDelaySec=5min
```

- `OnCalendar=` زمان ساعت دیواری است. `*-*-* 03:00:00` یعنی «هر سال و ماه و روز، ساعت 03:00:00»، پس هر شب ساعت 3. systemd.time(7) میان‌برهایی هم تعریف می‌کند: `minutely` برابر `*-*-* *:*:00`، `hourly` برابر `*-*-* *:00:00`، `daily` برابر `*-*-* 00:00:00` و `weekly` برابر `Mon *-*-* 00:00:00` است. ابزار `systemd-analyze calendar` یک عبارت را بررسی می‌کند؛ نتوانستم اجرایش کنم.
- `OnBootSec=` و `OnUnitActiveSec=` زمان‌های نسبی‌اند: از بوت و از آخرین فعال شدن unit.
- `Persistent=true` کاری را که در زمان خاموشی ماشین از دست رفته، به‌محض برگشتن اجرا می‌کند. فقط روی timerهای `OnCalendar=` اثر دارد.
- `RandomizedDelaySec=` تا آن مقدار تأخیر تصادفی اضافه می‌کند، که وقتی ماشین‌های زیادی زمان‌بندی یکسان دارند بار را پخش می‌کند. `AccuracySec=` (پیش‌فرض یک دقیقه) اجازه می‌دهد systemd بیدار شدن‌ها را کنار هم جمع کند، پس timerها تا ثانیه دقیق نیستند.

سرویسی که timer فعالش می‌کند معمولاً `Type=oneshot` است: کار را انجام می‌دهد و تمام می‌شود. (در `good/worker-report.service`، ExecStart برابر `/opt/worker/report` و `Restart=no` است.) در مقایسه با {{< term "cron" "cron" >}}، timerها جبران زمان خاموشی، وابستگی‌ها، لاگ جدا برای هر unit و `systemctl list-timers` را اضافه می‌کنند؛ cron ساده‌تر است، نوشتنش کوتاه‌تر است و روی سیستم‌های بدون systemd هم کار می‌کند. هیچ‌کدام برای همه‌ی موارد «بهتر» نیست.

## محدودسازی و لاگ

چون unit file اعلانی است، می‌تواند حدود کار سرویس را هم مشخص کند. طبق systemd.exec: `NoNewPrivileges=yes` جلوی گرفتن امتیاز بیشتر پروسه را می‌گیرد (مثلاً از راه فایل‌های setuid)، `ProtectSystem=strict` فایل‌سیستم را فقط‌خواندنی می‌کند جز مسیرهایی که با `ReadWritePaths=` اجازه می‌دهید، `PrivateTmp=yes` به سرویس `/tmp` خصوصی خودش را می‌دهد و `DynamicUser=yes` یک کاربر موقت می‌سازد و چند مورد از این‌ها را هم در بر می‌گیرد. هرچه سرویس در stdout یا stderr بنویسد به {{< term "journald" "journal" >}} می‌رود که با `journalctl -u worker` می‌خوانید.

دستورهای روزمره: بعد از ویرایش unit، `systemctl daemon-reload` را بزنید تا systemd دوباره بخواندش، بعد `systemctl start|stop|enable|status worker`. **هیچ‌کدام را اجرا نکردم.**

## یک linter که اجرا شد

چون نتوانستم systemd را اجرا کنم، یک بررسی‌کننده‌ی اسباب‌بازی نوشتم تا دست‌کم اشتباه‌های معمول را بگیرد. `unitlint.py` یک unit را می‌خواند (از جمله کلیدهای تکراری و ادامه‌ی خط با `\`) و چند قاعده را بررسی می‌کند. روی سه فایل خوب (**اجرا شد**):

```
good/worker-report.service: ok
good/worker-report.timer: ok
good/worker.service: ok
```

روی دو unit عمداً خراب، یعنی `bad/api.service` و `bad/cleanup.timer`:

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

سرویس اول فقط نام ساده‌ی `api` را به‌عنوان دستور دارد، `Restart=` ندارد و `[Install]` ندارد؛ آخرین یافته فقط یک یادآوری است چون چند خط `Environment=` معتبر است. timer به سرویسی اشاره می‌کند که کنارش وجود ندارد و نمی‌شود enable شود. دو محدودیت صادقانه: قاعده‌ی مسیر مطلق سخت‌گیرتر از خود systemd است، که نام ساده‌ای را هم که در پوشه‌های استانداردش پیدا کند می‌پذیرد. و این ابزار در برابر `systemd-analyze verify` اسباب‌بازی است، که نتوانستم اجرایش کنم. ارزیاب OnCalendar ننوشتم چون نمی‌توانستم آن را با systemd واقعی بسنجم.

## دام‌های unit file

- `After=` چیزی را شروع نمی‌کند؛ آن را با `Wants=` یا `Requires=` ترکیب کنید.
- بدون handler برای SIGTERM، هر توقف بعد از timeout با SIGKILL تمام می‌شود و تمیزکاری هرگز اجرا نمی‌شود.
- بعد از ویرایش unit، `daemon-reload` را بزنید. اگر فراموش کنید systemd همان تعریف قدیمی را اجرا می‌کند.
- timerها عمداً دیر اجرا می‌شوند (`AccuracySec=`)؛ جایی که ثانیه مهم است از آن‌ها استفاده نکنید.
- محدودسازی می‌تواند سرویسی را که بیرون از مسیرهای مجاز می‌نویسد خراب کند؛ گزینه‌ها را یکی‌یکی اضافه کنید و بعد از هرکدام آزمایش کنید.

## تمرین

روی یک ماشین Linux، worker نمونه را به‌عنوان سرویس نصب کنید، `systemctl stop` را بزنید و journal را بخوانید. آیا پیش از timeout خارج می‌شود؟ بعد یک timer با `OnCalendar=minutely` اضافه کنید، با `systemd-analyze calendar` بررسی‌اش کنید و با `systemctl list-timers` ببینیدش.

## قدم بعدی

بعدی «cgroup و namespace: پایه‌ی کانتینر» است، چون گزینه‌های محدودسازی و ایزوله‌سازی systemd بر پایه‌ی همان چیزی ساخته شده‌اند که هسته با آن تعیین می‌کند یک سرویس چه ببیند و چه مقدار مصرف کند.
