+++
date = '2026-11-09T10:00:00+03:30'
draft = false
title = 'پیدا کردن باگ با git bisect'
description = 'git bisect با جست‌وجوی دودویی commit خراب‌کننده را پیدا می‌کند، دستی یا کاملاً خودکار با git bisect run، با اجرای واقعی روی ریپوی ۳۰ commitی.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "bisect", "debugging", "beginner"]
cover = { image = "/images/covers/git-bisect.fa.png", alt = "پیدا کردن باگ با git bisect", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/git-undo-reflog-revert/) یاد گرفتیم کار انجام‌شده را چطور برگردانیم. حالا سؤال سخت‌تر: چیزی که ماه پیش درست کار می‌کرد امروز خراب است و ۳۰ commit بین این دو نقطه هست. کدام یکی خرابش کرده؟ این یک {{< term "regression" "regression" >}} است و `git bisect` ابزار مناسبش است.

> همه‌چیز با Git 2.39 در یک ریپوی دمو‌ی محلی اجرا شده و hashها خروجی واقعی همان اجرا هستند.

## آماده‌سازی

یک ریپو با ۳۰ commit ساختم. فایل `calc.sh` تابع `total()` را دارد که باید دو عدد را در هم ضرب کند. commit شماره‌ی ۱۹ («speed up total») بی‌صدا `*` را به `+` تغییر می‌دهد. بقیه‌ی commitها فقط یک فایل یادداشت اضافه می‌کنند. تست یک اسکریپت است که در حالت سالم 0 و در حالت خراب 1 برمی‌گرداند:

```sh
#!/bin/sh
[ "$(sh -c '. ./calc.sh; total 10 3')" = "30" ]
```

روی `main` فیل می‌شود و روی commit اول پاس.

## bisect دستی

{{< term "git-bisect" "git bisect" >}} یک {{< term "binary-search" "جست‌وجوی دودویی" >}} روی تاریخچه اجرا می‌کند. یک commit خراب و یک commit سالم به آن بدهید:

```text
$ git bisect start
$ git bisect bad
$ git bisect good <commit 1>
Bisecting: 14 revisions left to test after this (roughly 4 steps)
[5c39676...] commit 15: add note 15
```

Git وسط بازه را checkout کرد. من `./test.sh` را اجرا کردم، `git bisect good` یا `git bisect bad` زدم و تکرار کردم:

```text
commit 15 -> good   Bisecting: 7 revisions left (roughly 3 steps) -> commit 22
commit 22 -> bad    Bisecting: 3 revisions left (roughly 2 steps) -> commit 18
commit 18 -> good   Bisecting: 1 revision left  (roughly 1 step)  -> commit 20
commit 20 -> bad    Bisecting: 0 revisions left (roughly 0 steps) -> commit 19
commit 19 -> bad
8e5fe5f... is the first bad commit
    commit 19: speed up total
 calc.sh       | 2 +-
```

برای ۲۹ commit کاندیدا پنج تست لازم شد، یعنی log2(29) رو به بالا. با ۱۰۰۰ commit حدود ۱۰ تست می‌شد. این را با خواندن دستی ۳۰ diff مقایسه کنید: در بدترین حالت باید ۲۹ commit را باز می‌کردم و بیشترشان بی‌ربط‌اند.

## کاملاً خودکار: git bisect run

اگر اسکریپت بتواند سالم یا خراب بودن را تشخیص بدهد، بگذارید Git خودش پیش برود. exit code همان جواب است:

```text
$ git bisect start HEAD <commit 1>
$ git bisect run ./test.sh
running  './test.sh'
...
8e5fe5fb5fcb245d276ce9c7b4df8f29369b444e is the first bad commit
commit 8e5fe5f...
    commit 19: speed up total
 calc.sh       | 2 +-
bisect found first bad commit
```

همان پنج قدم بدون هیچ تایپی از طرف من. مزیت اصلی همین است: اول یک تست فیل‌شونده بنویسید، بعد bisect کنید.

## log و reset

`git bisect log` همه‌ی تصمیم‌ها را به شکل دستورهای قابل اجرای دوباره چاپ می‌کند (`git bisect good 5c39676...` و غیره، با پایان `# first bad commit: [8e5fe5f...]`). آن را در فایل ذخیره کنید و با `git bisect replay` دوباره اجرا کنید. همیشه با این تمام کنید:

```text
$ git bisect reset
Previous HEAD position was 8e5fe5f commit 19: speed up total
Switched to branch 'main'
```

تا reset نزده‌اید، وسط تاریخچه روی یک checkout جداشده (detached) هستید.

## commitهای غیرقابل تست

گاهی commit وسط اصلاً build نمی‌شود. در یک ریپوی دموی دوم، commit شماره‌ی ۱۵ در `calc.sh` خطای syntax دارد (در commit ۱۶ درست می‌شود). تست حالا با `sh -n calc.sh || exit 125` شروع می‌شود. دستی این را دیدم:

```text
calc.sh: line 1: unexpected EOF while looking for matching `)'
exit 125
$ git bisect skip
Bisecting: 13 revisions left to test after this (roughly 4 steps)
[51e8a2e...] commit 16
```

exit code ‏125 برای `git bisect run` معنای ویژه دارد: «این commit را رد کن». اجرای خودکار هم باز commit ۱۹ را پیدا کرد و `git bisect log` خط `# skip: [d55fa36...] commit 15` را ثبت کرد. اگر همه‌ی commitهای نزدیک مقصر غیرقابل تست باشند، Git فقط می‌تواند یک بازه بدهد، نه یک commit.

## git bisect visualize

`git bisect visualize` commitهای مظنون باقی‌مانده را در یک viewer گرافیکی نشان می‌دهد. چون UI می‌خواهد، اینجا اجرایش نکردم.

## چند نکته‌ی مهم

- exit codeها: 0 یعنی سالم، از 1 تا 127 به‌جز 125 یعنی خراب، 125 یعنی skip و 128 به بالا bisect را متوقف می‌کند. هر crash با کد بالا اجرا را قطع می‌کند.
- اسکریپت تست باید در هر commitی که Git checkout می‌کند وجود داشته باشد. مال من در commit اول commit شده؛ فایل untracked بیرون از تاریخچه هم کار می‌کند.
- bisect فرض می‌کند باگ بعد از ورود، باقی می‌ماند. تست flaky جواب غلط می‌دهد.
- قبل از ادامه‌ی کار عادی همیشه `git bisect reset` بزنید.
- bisect با {{< term "atomic-commit" "commitهای اتمیک" >}} می‌درخشد: commitهای کوچک و قابل build باعث می‌شوند «اولین commit خراب» یک diff باشد که در یک دقیقه می‌خوانید. یک commit غول‌آسای «fix stuff» جواب را بی‌فایده می‌کند.

## تمرین

1. با یک اسکریپت ریپویی با ۳۰ commit بسازید، در commit ۱۹ یک تابع را خراب کنید و `test.sh` بنویسید.
2. دستی bisect کنید و قدم‌ها را بشمارید. بعد با `git bisect run` اجرا کنید.
3. یک commit وسطی را غیرقابل build کنید و ببینید `exit 125` چطور آن را رد می‌کند.

## قدم بعدی

پست بعدی «hookها و commit message تمیز» است: چطور جلوی ورود commitهای بد به تاریخچه را بگیریم، که همان چیزی است که bisect را مفید نگه می‌دارد.
