+++
date = '2027-03-27T10:00:00+03:30'
draft = false
title = 'سیستم فایل و مجوزها'
description = 'سیستم فایل و مجوزها در Linux با اجرای واقعی: inode، هارد و سافت لینک، chmod، umask، بیت‌های پوشه و setuid، تست‌شده روی macOS.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "filesystem", "permissions", "chmod", "umask", "inode"]
cover = { image = "/images/covers/linux-filesystem-permissions.fa.png", alt = "سیستم فایل و مجوزها", hiddenInSingle = true }
+++

بعد از [پوسته‌ی کاربردی](/fa/posts/linux-shell-practical/)، چیز بعدی که هر اسکریپتی با آن کار دارد فایل است و بیشتر سورپرایزهای «permission denied» از چند قاعده می‌آیند. این پست آن‌ها را با اجراهای کوچک مرور می‌کند.

> توضیح صادقانه: همه‌چیز روی **macOS** و در یک پوشه‌ی موقت اجرا شد (userland از نوع BSD، بدون هسته‌ی Linux و بدون sudo). چیزی را روی Linux اجرا نکردم. `/proc` و `/sys` (وضعیت هسته به شکل فایل) فقط روی Linux هستند و به آن‌ها دست نزدم؛ ACLهای Linux (`getfacl`) هم اجرا نشد. نام کاربری، شناسه‌ها و مسیر خانه حذف شده‌اند.

## نام، inode و لینک

داده و فراداده‌ی فایل در یک {{< term "inode" "inode" >}} است؛ ورودی پوشه فقط نامی است که به شماره‌ی inode اشاره می‌کند.

```sh
echo hello > a.txt; ln a.txt hard.txt; ln -s a.txt soft.txt
ls -li a.txt hard.txt soft.txt
```
```
307806620 -rw-r--r--@ 2 <user>  staff  6 ... a.txt
307806620 -rw-r--r--@ 2 <user>  staff  6 ... hard.txt
307806623 lrwxr-xr-x@ 1 <user>  staff  5 ... soft.txt -> a.txt
```

یک {{< term "hard-link" "هارد لینک" >}} inode را به اشتراک می‌گذارد (شماره‌ی یکسان، شمارنده‌ی لینک 2). یک {{< term "symbolic-link" "لینک نمادین" >}} inode خودش را دارد و مسیر `a.txt` را نگه می‌دارد؛ `readlink soft.txt` چاپ کرد `a.txt`. بعد از `rm a.txt` هارد لینک هنوز `hello` را چاپ کرد (شمارنده 1)، ولی `cat soft.txt` خطای `No such file or directory` داد: symlink بی‌مقصد شده است.

روی macOS دستور `stat -f '%i %l %Lp %z %N' hard.txt` این را داد: `307806620 1 644 6 hard.txt` (inode، لینک، مجوز، اندازه، نام). در GNU از `-c` استفاده می‌شود؛ این را فقط از man page می‌دانم و اجرا نکردم.

## بیت‌های مجوز

{{< term "file-permissions" "مجوزها" >}} سه دسته‌اند: r/w/x برای user و group و other. در octal برای هر دسته 4 و 2 و 1 جمع می‌شود.

```sh
chmod 640 f            # -rw-r----- 
chmod u+x,g-r,o+r f    # -rwx---r--
chmod 755 f            # -rwxr-xr-x
```

کامنت‌ها همان رشته‌های `ls -l` هستند که گرفتم (`@` آخر در macOS یعنی extended attribute، پایین‌تر).

## umask

{{< term "umask" "umask" >}} از فایل و پوشه‌ی جدید بیت حذف می‌کند.

```sh
(umask 022; mkdir u022; touch u022/file)   # drwxr-xr-x  -rw-r--r--
(umask 077; mkdir u077; touch u077/file)   # drwx------  -rw-------
```

فایل از 666 و پوشه از 777 شروع می‌کند، منهای ماسک.

## پوشه: r و x فرق دارند

روی پوشه، `r` اجازه‌ی دیدن نام‌ها و `x` اجازه‌ی وارد شدن و رسیدن به ورودی‌ها با نام است. با `d/in.txt` داخلش:

| مجوز `d` | `ls d` | `cat d/in.txt` |
|---|---|---|
| 600 (r بدون x) | `ls: fts_read: Permission denied` و بعد `in.txt` | `Permission denied` |
| 300 (w و x بدون r) | `ls: d: Permission denied` | `x` را چاپ می‌کند |
| 500 (r و x بدون w) | `touch d/new` شکست می‌خورد: `Permission denied` | کار می‌کند |

ساختن یا حذف فایل به `w` و `x` روی پوشه نیاز دارد، نه روی فایل.

## setuid و setgid و sticky

```sh
chmod 4755 f; chmod 2775 s; chmod 1777 t
```
```
-rwsr-xr-x   f
drwxrwsr-x   s
drwxrwxrwt   t
```

اجرایی {{< term "setuid" "setuid" >}} با هویت مالکش اجرا می‌شود و setgid روی پوشه باعث می‌شود فایل‌های جدید گروه پوشه را بگیرند. {{< term "sticky-bit" "sticky bit" >}} یعنی `t` روی پوشه‌ی قابل‌نوشتن برای همه، فقط به مالک اجازه‌ی حذف ورودی خودش را می‌دهد، مثل `/tmp`. من فقط بیت‌ها را در پوشه‌ی موقت نشان دادم؛ اثر setuid را اجرا نکردم و فایل سیستمی را تغییر ندادم.

## مالکیت

`id` چاپ کرد: `uid=<uid>(<user>) gid=<gid>(<group>) groups=<list>`. با کاربر عادی، `chown root f` شکست خورد: `chown: f: Operation not permitted`. فقط root می‌تواند فایل را به دیگری بدهد.

## ممیزی فایل‌های قابل‌نوشتن برای همه

`find . -type l` فقط `./soft.txt` را فهرست کرد؛ `find . -perm -002 ! -type l` ورودی‌های قابل‌نوشتن برای همه را پیدا می‌کند و `-perm -4000` فایل‌های setuid را. یک اسکریپت ممیزی کوچک:

```sh
#!/bin/sh
dir=${1:?usage: audit.sh DIR}
find "$dir" ! -type l -perm -002 -print | while IFS= read -r p; do
  if [ -d "$p" ] && [ -k "$p" ]; then echo "ok(sticky)  $p"
  else echo "WRITABLE    $p"; fi
done
```

در آزمایشگاه من (`hard.txt` با 666 و `t` با 1777) چاپ کرد: `ok(sticky)  ./t` و `WRITABLE    ./hard.txt`.

## فقط macOS: xattr

`@` در `ls -l` یعنی extended attribute. `xattr` روی فایل‌های من `com.apple.provenance` را نشان داد. macOS ACL هم دارد (با `ls -le`) و پرچم quarantine برای دانلودها؛ آن‌ها را بررسی نکردم. معادل Linux آن `getfacl` و `setfacl` است که اجرا نکردم.

## چند نکته‌ی مهم

- هارد لینک از مرز سیستم فایل رد نمی‌شود؛ symlink می‌تواند بی‌مقصد شود.
- برای وارد شدن به پوشه `x` لازم است و برای تغییر آن `w` و `x`.
- `chmod 777` به‌ندرت راه‌حل است؛ پیدا کنید کدام بیت کم است.
- umask به پروسه تعلق دارد، پس `( umask 077; ... )` در subshell محلی می‌ماند.
- گزینه‌های `stat` و `sed -i` و `find` در BSD و GNU فرق دارند؛ man page را ببینید.

## تمرین

یک پوشه با یک فایل بسازید و همه‌ی مجوزهای 000 تا 700 را روی پوشه امتحان کنید و ثبت کنید `ls` و `cat` و `touch` کدام کار می‌کنند. بعد ممیزی را طوری گسترش دهید که فایل‌های setuid را هم فهرست کند.

## قدم بعدی

پست بعدی «پروسه و سیگنال» است.
