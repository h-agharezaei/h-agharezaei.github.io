+++
date = '2027-03-19T10:00:00+03:30'
draft = false
title = 'پوسته‌ی کاربردی: pipe، redirect و xargs'
description = 'pipe، redirect و xargs در پوسته با اجرای واقعی: کد خروج، pipefail، تله‌های quoting، find -print0 و process substitution، تست‌شده روی macOS.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "shell", "bash", "pipes", "redirects", "xargs"]
cover = { image = "/images/covers/linux-shell-practical.fa.png", alt = "پوسته‌ی کاربردی: pipe، redirect و xargs", hiddenInSingle = true }
+++

این اولین پست سری Linux است و از جایی شروع می‌کند که بیشتر روزم آنجا می‌گذرد: پوسته (**shell**). pipe، redirect و `xargs` ابزارهای کوچک را به برنامه‌های یک‌بارمصرف تبدیل می‌کنند و چند قاعده‌ی quoting تعیین می‌کند این برنامه‌ها امن‌اند یا نه. همین ابزارها در اشکال‌زدایی سوکت هم به کار می‌آیند، مثل [پست سرور TCP](/fa/posts/net-sockets-tcp-from-scratch/).

> توضیح صادقانه: این پست را روی **macOS** نوشتم که userland از نوع BSD دارد و هسته‌ی Linux ندارد. همه‌ی خروجی‌ها واقعی‌اند (`/bin/sh` و برای bash، نسخه‌ی 3.2.57). چیزی را روی Linux اجرا نکردم و `shellcheck` نصب نیست، پس اجرایش نکردم. هرجا GNU فرق دارد، از man page نقل می‌کنم. مسیر خانه با `<home>` جایگزین شده است.

## یک لاگ برای تمرین

لاگ نمونه خط‌های ساختگی و آدرس‌های مستندات (`203.0.113.x` و `198.51.100.x`) دارد. هر خط به شکل `client method path status` است.

```sh
cut -d' ' -f1 access.log | sort | uniq -c | sort -rn | head -2
```
```
   4 203.0.113.7
   2 203.0.113.9
```

یک {{< term "pipe" "pipe" >}} خروجی یک دستور را به ورودی دستور بعدی وصل می‌کند. `uniq` فقط خط‌های همسایه را یکی می‌کند، برای همین `sort` اول می‌آید.

## Redirect

هر پروسه با سه {{< term "file-descriptor" "file descriptor" >}} شروع می‌شود: 0 (stdin)، 1 (stdout) و 2 (stderr). redirect آن‌ها را جابه‌جا می‌کند.

```sh
echo one > out.txt; echo two >> out.txt    # > truncates, >> appends
ls nope 2> err.txt; echo "exit=$?"
ls nope out.txt > both.txt 2>&1            # stderr to wherever stdout goes
```
```
exit=1
ls: nope: No such file or directory
```

فایل `both.txt` هم خط خطا را داشت و هم `out.txt` را. ترتیب مهم است: `2>&1` مقصد *فعلی* stdout را کپی می‌کند، پس بعد از `> file` می‌آید. میان‌بر `&>` در bash همین کار را می‌کند (اینجا زیر bash 3.2 اجرا شد)، ولی POSIX نیست و اسکریپت‌های `/bin/sh` باید شکل بلند را بنویسند.

یک {{< term "here-document" "here-document" >}} متن ثابت را به stdin می‌دهد. بدون quote متغیرهای داخلش باز می‌شوند، با marker داخل quote نه. اجرای من برای `<<'EOT'` چاپ کرد: `literal $HOME`. عملگر `<<<` (فقط bash) یک رشته می‌دهد: `tr a-z A-Z <<< "hello"` چاپ کرد `HELLO`.

## کد خروج، && و ||

هر دستور با یک {{< term "exit-status" "کد خروج" >}} تمام می‌شود: 0 یعنی موفق.

```sh
grep -q 404 access.log; echo "found=$?"      # found=0
grep -q 500 access.log; echo "notfound=$?"   # notfound=1
grep -q 500 access.log && echo yes || echo no   # no
```

`a && b` فقط اگر `a` موفق بود `b` را اجرا می‌کند و `a || b` فقط اگر شکست خورد. جایگزینی دستور خروجی را می‌گیرد: `n=$(wc -l < access.log)` نتیجه‌ی `lines:        8` داد. این فاصله‌ها واقعی‌اند: `wc` در BSD عدد را padding می‌دهد. `tee` جریان را در فایل می‌نویسد و ادامه می‌دهد: `... | tee status-counts.txt | wc -l` عدد `3` را چاپ کرد و شمارش‌ها روی دیسک ماندند.

## pipefail

وضعیت یک pipeline معمولاً وضعیت آخرین دستور است، پس خرابی میانی پنهان می‌ماند.

```sh
false | true; echo "default: $?"      # default: 0
set -o pipefail
false | true; echo "pipefail: $?"     # pipefail: 1
```

`set -e` با اولین دستور ناموفق متوقف می‌کند: در یک subshell، `echo before; false; echo after` فقط `before` را چاپ کرد و با کد 1 خارج شد. `set -u` متغیر تعریف‌نشده را خطا می‌کند: `undefined_var: unbound variable`. `set -euo pipefail` سرآیند خوبی برای bash است، اما `-e` استثناهایی دارد (مثلاً داخل `if`) و `pipefail` را فقط در bash آزمودم.

## Quoting

```sh
f="my report.txt"; touch "$f"
ls -1 $f
ls -1 "$f"
```
```
ls: my: No such file or directory
ls: report.txt: No such file or directory
my report.txt
```

بدون quote، متغیر روی فاصله به دو آرگومان شکسته می‌شود. همه‌ی expansionها را quote کنید.

## xargs و نام‌های دارای فاصله

{{< term "xargs" "`xargs`" >}} خط‌های stdin را به آرگومان تبدیل می‌کند. با فایل‌های `a b.txt` و `c.txt` و `d e f.txt`:

```sh
find . -name '*.txt' | xargs ls -1
```
```
ls: ./a: No such file or directory
ls: ./d: No such file or directory
ls: b.txt: No such file or directory
...
```

راه‌حل جداکننده‌ی NUL است: `find . -name '*.txt' -print0 | xargs -0 ls -1` هر سه فایل را درست فهرست کرد. اجراهای دیگر: `xargs -n 2 echo batch:` روی `1..5` چاپ کرد `batch: 1 2` و `batch: 3 4` و `batch: 5`؛ و `xargs -0 -I{} echo "file=[{}]"` برای هر فایل یک‌بار اجرا شد. بدون xargs هم می‌شود: `find ... -exec echo {} +`.

## Linux کجا فرق دارد

آنچه روی macOS دیدم:

- `find -printf` اینجا نیست (`find: -printf: unknown primary or operator`). GNU find را اجرا نکردم.
- `sed -i 's/x/y/' file` با خطای `command c expects \ followed by text` شکست خورد، چون `sed` در BSD یک آرگومان پسوند می‌خواهد: `sed -i '' ...` کار کرد. در GNU، پسوند به `-i` چسبیده است، پس اسکریپت قابل‌حمل از `-i` پرهیز می‌کند.
- ورودی خالی: طبق man page خود macOS، `xargs` در GNU حتی با ورودی خالی دستور را یک‌بار اجرا می‌کند و گزینه‌ی `-r` جلوی آن را می‌گیرد. اینجا `printf '' | xargs echo ran` چیزی چاپ نکرد و `-r` پذیرفته می‌شود.

## چند نکته‌ی مهم

- به‌طور پیش‌فرض `"$var"` و `"$@"` را quote کنید.
- برای نام فایل از `-print0` و `-0` استفاده کنید، هرگز `find | xargs` خالی.
- `2>&1` بعد از redirect فایل می‌آید.
- {{< term "process-substitution" "process substitution" >}} یعنی `<(cmd)` (bash/zsh، نه POSIX) خروجی دستور را به شکل نام فایل می‌دهد: `diff <(...) <(...)` با کد 1 تمام شد و `3d2` نشان داد.
- bash-isms مثل `&>` و `<<<` و `<()` نیاز به `#!/bin/bash` دارند.

## تمرین

فایل `x y.log` و دو فایل `.log` دیگر بسازید. خط‌هایشان را با `find ... -print0 | xargs -0 wc -l` بشمارید، بعد `-print0` و `-0` را بردارید و خطا را بخوانید.

## قدم بعدی

پست بعدی «سیستم فایل و مجوزها» است.
