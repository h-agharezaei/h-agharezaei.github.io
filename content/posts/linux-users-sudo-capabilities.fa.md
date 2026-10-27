+++
date = '2027-05-25T10:00:00+03:30'
draft = false
title = 'کاربر، sudo و capability'
description = 'کاربر، sudo و capabilityهای Linux از روی man pageها: passwd و shadow، تله‌های sudoers، تکه‌تکه شدن root و یک رمزگشای ماسک capability با Go.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "sudo", "capabilities", "security", "users", "least-privilege", "go", "macos"]
cover = { image = "/images/covers/linux-users-sudo-capabilities.fa.png", alt = "کاربر، sudo و capability", hiddenInSingle = true }
+++

این را روی یک مک نوشتم؛ هیچ‌چیز اینجا روی Linux اجرا نشده است. این یازدهمین پست سری Linux است، بعد از [SSH و کلیدها](/fa/posts/linux-ssh-keys/). آن ورود چه کارهایی می‌تواند بکند؟ واقعیت‌ها از man pageها و سورس Go است؛ نمونه‌ها با عبارت «ضبط‌نشده» علامت خورده‌اند. بیت‌های فایل در [فایل‌سیستم و دسترسی‌ها](/fa/posts/linux-filesystem-permissions/) آمده است.

## کاربر و گروه

طبق passwd(5)، فایل `/etc/passwd` برای هر حساب یک خط دارد با هفت فیلد جداشده با دونقطه: نام، جایگزین رمز، UID، GID، توضیح، home و shell. هش رمز آنجا نیست. طبق shadow(5)، فایل `/etc/shadow` رمز رمزنگاری‌شده را نگه می‌دارد و مقداری که با `!` شروع شود یعنی رمز قفل است. مود فایل را در آن صفحه پیدا نکردم؛ فقط می‌گویم برای کاربر عادی خواندنی نیست. هر پروسه علاوه بر گروه اصلی، گروه‌های مکمل (supplementary) هم دارد.

root همان UID صفر است. کرنل حالا capabilityها را بررسی می‌کند؛ root فقط کاربری است که همه‌ی آن‌ها را از اول دارد.

روی مک (BSD) اجرا کردم، با شناسه‌های جایگزین‌شده:

```
$ [ "$(id -u)" -eq 0 ] && echo root || echo "not root"
not root
$ stat -f '%Sp %u %g' file-i-created      # output: ids replaced
-rw-r----- <uid> <gid>
$ ls -l /usr/bin/sudo                      # owner and group replaced
-r-s--x--x <owner> <group> /usr/bin/sudo
```

`s` همان بیت {{< term "setuid" "setuid" >}} است: sudo با هویت مالکش اجرا می‌شود. `stat -f` مخصوص BSD است؛ GNU stat از `-c` استفاده می‌کند که اجرا نکردم.

## sudo و sudoers

{{< term "sudo" "sudo" >}} اگر سیاست {{< term "sudoers" "sudoers" >}} اجازه بدهد، دستور را با هویت کاربر دیگری اجرا می‌کند. از man pageها:

- با `visudo` ویرایش کنید؛ `visudo -c` نحو را بررسی می‌کند. `sudoedit` فایل را بدون اجرای ویرایشگر با root ویرایش می‌کند.
- `sudo -l` فهرست کارهایی را که مجازید نشان می‌دهد.
- `env_reset` به‌صورت پیش‌فرض روشن است و محیط فراخواننده را پاک می‌کند؛ man page نگه‌داشتنش را توصیه می‌کند.
- `NOPASSWD` رمزپرسی را برمی‌دارد: هرکس نشست شما را بگیرد، root می‌شود.

فایل sudoers این ماشین را نخواندم و sudo اجرا نکردم.

هسته‌ی {{< term "least-privilege" "حداقل دسترسی" >}} فهرست کوتاه دستورهاست، نه `ALL`. دو تله در sudoers(5) آمده است. wildcard در آرگومان‌ها می‌تواند هر چیزی از جمله فاصله را مطابقت دهد و صفحه می‌گوید با احتیاط استفاده شود. برنامه‌هایی که shell escape دارند (shell، ویرایشگر، pager) کاربر را از کنترل sudo بیرون می‌برند؛ صفحه `NOEXEC` را یک راه دفاع می‌نامد، بسته به پشتیبانی سیستم‌عامل. پس `sudo bash` فقط یک shell با root است. `su` با رمز کاربر مقصد هویت را عوض می‌کند و `doas` جایگزین کوچک‌تر OpenBSD برای sudo است؛ نشان نمی‌دهم.

## Capabilityها: root تکه‌تکه

طبق capabilities(7)، کرنل قدرت root را به {{< term "linux-capabilities" "capability" >}}های جدا تقسیم می‌کند. چند نمونه، با شماره‌ی `linux/capability.h`:

| شماره | نام | اجازه |
|---|---|---|
| 0 | CAP_CHOWN | تغییر مالک فایل |
| 1 | CAP_DAC_OVERRIDE | دور زدن بررسی دسترسی فایل |
| 10 | CAP_NET_BIND_SERVICE | bind روی پورت زیر ۱۰۲۴ |
| 13 | CAP_NET_RAW | سوکت خام |
| 21 | CAP_SYS_ADMIN | بسیار گسترده |

man page می‌گوید CAP_SYS_ADMIN را می‌توان «the new root» نامید؛ از آن دوری کنید. هر thread پنج مجموعه دارد: permitted، effective، inheritable، bounding و ambient (ambient از 4.3). فایل هم می‌تواند capability داشته باشد: `setcap cap_net_bind_service=+ep /path/to/bin` به یک وب‌سرور اجازه می‌دهد بدون root روی پورت ۸۰ گوش بدهد. نزدم. پرچم {{< term "no-new-privs" "no_new_privs" >}} جلوی گرفتن امتیاز با setuid یا file capability در execve را می‌گیرد.

## کاهش امتیاز و systemd

daemon کلاسیک پورت ۸۰ را با root می‌گیرد و بعد به کاربر عادی می‌رود. در Go سورس `syscall.Setuid` برای Linux را خواندم: بدون cgo از `AllThreadsSyscall` استفاده می‌کند و تغییر به همه‌ی threadها می‌رسد؛ با cgo از libc می‌گذرد. ترتیب مهم است: اول `Setgroups` و `Setgid`، آخر `Setuid`، و خطاها را بررسی کنید. در [systemd: واحدها و تایمرها](/fa/posts/linux-systemd-units-timers/) همین ایده اعلامی است: `CapabilityBoundingSet=`، `AmbientCapabilities=` و `NoNewPrivileges=` طبق مستندات systemd.exec. کانتینرها از مجموعه‌ای کوچک‌تر شروع می‌کنند، [cgroups و namespaces](/fa/posts/linux-cgroups-namespaces/) را ببینید.

## رمزگشایی که اجرا کردم

فایل `/proc/<pid>/status` مقدارهای `CapInh`، `CapPrm`، `CapEff`، `CapBnd` و `CapAmb` را به‌صورت ماسک hex چاپ می‌کند. برنامه‌ی Go من شماره‌ی بیت‌ها را با جدولی که از هدر کرنل برداشتم به نام تبدیل می‌کند. این‌ها **نمونه در قالب مستند، ضبط‌نشده** هستند؛ `go test -race` سبز شد:

```
$ lx11 status testdata/status_unprivileged.txt
CapPrm 0000000000000000: (none)
CapEff 0000000000000000: (none)
CapBnd 000001ffffffffff: 41 capabilities (CAP_CHOWN ... CAP_CHECKPOINT_RESTORE)
$ lx11 mask 00000000a80425fb
CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER CAP_FSETID CAP_KILL CAP_SETGID CAP_SETUID
CAP_SETPCAP CAP_NET_BIND_SERVICE CAP_NET_RAW CAP_SYS_CHROOT CAP_MKNOD
CAP_AUDIT_WRITE CAP_SETFCAP
```

(خط‌های دیگر حذف شده است.) ماسک دوم را خودم به‌عنوان مجموعه‌ای کانتینرمانند ساخته‌ام. دستور `self` با `//go:build linux` فایل `/proc/self/status` را می‌خواند؛ اینجا «Linux only» چاپ کرد. نسخه‌ی Linux با `GOOS=linux GOARCH=arm64 go vet ./... && go build` ساخته شد و هرگز اجرا نشد.

## چند نکته‌ی مهم

- هرگز `NOPASSWD: ALL` ننویسید.
- در فهرست دستورهای sudoers از wildcard و ویرایشگر پرهیز کنید.
- یک capability بهتر از root است؛ CAP_SYS_ADMIN را نگیرید.
- امتیاز را زود رها کنید.
- اجرا نکردم: sudo، setcap، getcap، capsh.

## تمرین

روی یک VM دورریختنی، `grep Cap /proc/self/status` را یک بار با کاربر عادی و یک بار با root بزنید و هر دو ماسک را با `lx11 mask` رمزگشایی کنید.

## قدم بعدی

پست بعدی «لاگ‌ها و journalctl» است.
