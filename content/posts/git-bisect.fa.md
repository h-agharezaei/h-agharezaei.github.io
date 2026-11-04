+++
date = '2026-11-09T10:00:00+03:30'
draft = false
title = 'پیدا کردن باگ با git bisect'
description = 'git bisect با جست‌وجوی دودویی commit خراب‌کننده را پیدا می‌کند، دستی یا کاملاً خودکار با git bisect run، با اجرای واقعی روی ریپوی ۳۰ commitی.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "bisect", "debugging", "beginner"]
cover = { image = "/images/covers/git-bisect.fa.png", alt = "پیدا کردن باگ با git bisect", hiddenInSingle = true }
+++

فرض کنید ماه پیش همه‌چیز درست کار می‌کرد، امروز یک چیز خراب است و بین این دو نقطه ۳۰ commit ردیف شده است. کدام‌یک خرابش کرده؟ این مشکل اسم دارد: {{< term "regression" "regression" >}}، یعنی چیزی که قبلاً کار می‌کرد و حالا کار نمی‌کند.

راه بی‌تدبیر این است که commitها را یکی‌یکی باز کنید و diffشان را بخوانید؛ در بدترین حالت ۲۹ بار. `git bisect` همین را با حدود پنج تست جواب می‌دهد. [برگرداندن کار](/fa/posts/git-undo-reflog-revert/) وقتی ساده است که بدانید کدام commit را revert کنید؛ bisect همان commit را برایتان پیدا می‌کند.

> همه‌چیز با Git 2.39 در یک ریپوی دموی محلی اجرا شده و hashها خروجی واقعی همان اجرا هستند. روی سیستم شما hashها فرق می‌کنند.

## ایده: نصف کردن

تصور کنید یک کتاب ۳۰ صفحه‌ای دارید و می‌دانید صفحه‌ی اول سالم است و صفحه‌ی آخر لکه دارد. لکه از کدام صفحه شروع شد؟ لازم نیست صفحه‌ها را از اول ورق بزنید. صفحه‌ی ۱۵ را باز می‌کنید: اگر سالم بود، لکه جایی بین ۱۶ تا ۳۰ شروع شده؛ اگر لکه داشت، بین ۲ تا ۱۵. هر بار نصف احتمال‌ها کنار می‌رود.

`git bisect` همین کار را با تاریخچه می‌کند. این روش اسمی هم دارد: {{< term "binary-search" "جست‌وجوی دودویی" >}}. شما یک commit سالم و یک commit خراب به آن می‌دهید، Git commit وسط را checkout می‌کند، شما تست می‌کنید و جواب می‌دهید «سالم» یا «خراب»، و Git بازه را نصف می‌کند. این‌قدر ادامه می‌دهد تا به اولین commit خراب برسد. {{< term "git-bisect" "git bisect" >}} فقط یک شرط دارد: باید بتوانید در هر commit تشخیص بدهید سالم است یا خراب.

## آماده‌سازی

برای دیدنش یک ریپو با ۳۰ commit ساختم. فایل `calc.sh` تابع `total()` را دارد که باید دو عدد را در هم ضرب کند. commit شماره‌ی ۱۹ («speed up total») بی‌صدا `*` را به `+` تغییر می‌دهد. بقیه‌ی commitها فقط یک فایل یادداشت اضافه می‌کنند. پس باگ در یک commit مشخص و شناخته‌شده است و ما می‌خواهیم ببینیم bisect پیدایش می‌کند یا نه.

تست یک اسکریپت کوتاه است. `total 10 3` را اجرا می‌کند و اگر جواب `30` بود با کد خروج 0 (سالم) و در غیر این‌صورت با 1 (خراب) تمام می‌شود:

```sh
#!/bin/sh
[ "$(sh -c '. ./calc.sh; total 10 3')" = "30" ]
```

این تست روی `main` فیل می‌شود (چون ۱۰ + ۳ می‌شود ۱۳) و روی commit اول پاس.

## bisect دستی

اول bisect را شروع می‌کنیم و یک commit خراب (`main`، یعنی commit فعلی) و یک commit سالم (commit اول) معرفی می‌کنیم:

```text
$ git bisect start
$ git bisect bad
$ git bisect good <commit 1>
Bisecting: 14 revisions left to test after this (roughly 4 steps)
[5c39676...] commit 15: add note 15
```

(Git چند خط `status:` هم چاپ می‌کند که برای کوتاه شدن حذفشان کردم.) پیام می‌گوید بعد از این تست هنوز ۱۴ commit مشکوک می‌ماند و تقریباً ۴ قدم دیگر لازم است. بعد وسط بازه یعنی commit ۱۵ را checkout کرده است.

من در هر قدم `./test.sh` را اجرا کردم، با `git bisect good` یا `git bisect bad` جواب دادم و تکرار کردم. این خلاصه‌ی پنج قدم است؛ هر خط می‌گوید روی کدام commit بودم، جواب چه بود و Git بعدی را کجا گذاشت:

```text
commit 15 -> good   Bisecting: 7 revisions left (roughly 3 steps) -> commit 22
commit 22 -> bad    Bisecting: 3 revisions left (roughly 2 steps) -> commit 18
commit 18 -> good   Bisecting: 1 revision left  (roughly 1 step)  -> commit 20
commit 20 -> bad    Bisecting: 0 revisions left (roughly 0 steps) -> commit 19
commit 19 -> bad
8e5fe5f... is the first bad commit
    commit 19: speed up total
 calc.sh       | 2 +-
 notes/n19.txt | 1 +
```

بخوانیم: commit ۱۵ سالم بود، پس باگ بعد از آن است و Git رفت سراغ ۲۲. ۲۲ خراب بود، پس باگ بین ۱۶ و ۲۲ است و Git ۱۸ را انتخاب کرد. ۱۸ سالم بود، ۲۰ خراب. در نهایت ۱۹ خراب بود و چون commit قبلی‌اش (۱۸) سالم بود، Git اعلام کرد ۱۹ اولین commit خراب است. (خط‌های آخر diffstat هم هستند و بخشی از آن را برای کوتاه شدن آورده‌ام.)

برای ۲۹ commit کاندیدا پنج تست لازم شد، یعنی log2(29) رو به بالا. با ۱۰۰۰ commit هم حدود ۱۰ تست کافی بود. این را با خواندن دستی ۳۰ diff مقایسه کنید: در بدترین حالت باید ۲۹ commit را باز می‌کردم و بیشترشان بی‌ربط‌اند.

## کاملاً خودکار: git bisect run

اگر اسکریپت خودش می‌تواند سالم یا خراب بودن را تشخیص بدهد، چرا خودمان جواب بدهیم؟ `git bisect run` اسکریپت را در هر قدم اجرا می‌کند و از کد خروج آن جواب را می‌فهمد:

```text
$ git bisect start HEAD <commit 1>
$ git bisect run ./test.sh
running  './test.sh'
...
8e5fe5fb5fcb245d276ce9c7b4df8f29369b444e is the first bad commit
commit 8e5fe5f...
    commit 19: speed up total
 calc.sh       | 2 +-
 notes/n19.txt | 1 +
bisect found first bad commit
```

(نقطه‌چین‌ها جای قدم‌های میانی است که مثل بالا رد می‌شوند.) همان پنج قدم، بدون هیچ تایپی از طرف من. مزیت اصلی همین است: اول یک تست فیل‌شونده بنویسید، بعد bisect کنید. آن تست به شما می‌گوید مشکل چیست و هم bisect را کاملاً خودکار می‌کند.

## log و reset

`git bisect log` همه‌ی تصمیم‌ها را به شکل دستورهای قابل اجرای دوباره چاپ می‌کند (`git bisect good 5c39676...` و غیره، با پایان `# first bad commit: [8e5fe5f...]`). آن را در فایل ذخیره کنید و با `git bisect replay` دوباره اجرا کنید؛ مثلاً وقتی یک جواب را اشتباه داده‌اید. همیشه با این تمام کنید:

```text
$ git bisect reset
Previous HEAD position was 8e5fe5f commit 19: speed up total
Switched to branch 'main'
```

چون bisect وسط تاریخچه روی یک commit بدون branch (detached) می‌ایستد، تا reset نزده‌اید همان‌جا می‌مانید. `reset` شما را به branch قبلی برمی‌گرداند.

## commitهای غیرقابل تست

گاهی commit وسط اصلاً build نمی‌شود، پس تست نه می‌تواند بگوید سالم است و نه خراب. در یک ریپوی دموی دوم، commit شماره‌ی ۱۵ در `calc.sh` خطای syntax دارد (در commit ۱۶ درست می‌شود). تست حالا با `sh -n calc.sh || exit 125` شروع می‌شود؛ `sh -n` فقط syntax را بررسی می‌کند و اگر خطا داشت، کد 125 برمی‌گرداند. دستی این را دیدم:

```text
calc.sh: line 1: unexpected EOF while looking for matching `)'
exit 125
$ git bisect skip
Bisecting: 13 revisions left to test after this (roughly 4 steps)
[51e8a2e...] commit 16
```

خط اول شکایت `sh` از فایل خراب است. با `git bisect skip` به Git گفتم این commit را کنار بگذارد و Git commit بعدی (۱۶) را آورد.

exit code ‏125 برای `git bisect run` معنای ویژه دارد: «این commit را رد کن». اجرای خودکار هم باز commit ۱۹ را پیدا کرد و `git bisect log` خط `# skip: [d55fa36...] commit 15` را ثبت کرد. اگر همه‌ی commitهای نزدیک مقصر غیرقابل تست باشند، Git فقط می‌تواند یک بازه بدهد، نه یک commit.

## git bisect visualize

`git bisect visualize` commitهای مظنون باقی‌مانده را در یک viewer گرافیکی نشان می‌دهد. چون UI می‌خواهد، اینجا اجرایش نکردم.

## جایی که bisect گمراه می‌کند

- **کدهای خروج را بشناسید.** طبق مستندات Git، 0 یعنی سالم، از 1 تا 127 به‌جز 125 یعنی خراب، 125 یعنی skip و 128 به بالا bisect را متوقف می‌کند. پس اسکریپتی که با یک کد بالا crash کند، کل اجرا را قطع می‌کند.
- **اسکریپت تست باید در هر commitی که Git checkout می‌کند در دسترس باشد.** مال من در commit اول commit شده است. فایل untracked بیرون از تاریخچه هم کار می‌کند، چون checkout به آن دست نمی‌زند.
- **bisect فرض می‌کند باگ بعد از ورود، باقی می‌ماند.** اگر تست flaky باشد (گاهی پاس شود و گاهی فیل)، یک جواب اشتباه بازه را غلط نصف می‌کند و به commit بی‌گناهی می‌رسید.
- **قبل از ادامه‌ی کار عادی `git bisect reset` بزنید.** وگرنه روی یک commit وسط تاریخچه می‌مانید.
- **bisect با {{< term "atomic-commit" "commitهای اتمیک" >}} می‌درخشد.** commit اتمیک یعنی یک تغییر منطقی و کوچک که تنهایی build می‌شود. با چنین commitهایی «اولین commit خراب» یک diff است که در یک دقیقه می‌خوانید. یک commit غول‌آسای «fix stuff» جواب را بی‌فایده می‌کند.

## تمرین

1. با یک اسکریپت ریپویی با ۳۰ commit بسازید، در commit ۱۹ یک تابع را خراب کنید و `test.sh` بنویسید.
2. دستی bisect کنید و قدم‌ها را بشمارید. بعد با `git bisect run` اجرا کنید.
3. یک commit وسطی را غیرقابل build کنید و ببینید `exit 125` چطور آن را رد می‌کند.

## قدم بعدی

پست بعدی «hookها و commit message تمیز» است: چطور جلوی ورود commitهای بد به تاریخچه را بگیریم، که همان چیزی است که bisect را مفید نگه می‌دارد.
