+++
date = '2026-11-05T10:00:00+03:30'
draft = false
title = 'حل conflict و rerere'
description = 'حل conflict در Git قدم‌به‌قدم: خواندن marker‌ها، abort امن، فرق ours و theirs در merge و rebase، و استفاده‌ی دوباره از حل‌ها با rerere.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "merge-conflict", "rerere", "beginner"]
cover = { image = "/images/covers/git-resolve-conflicts.fa.png", alt = "حل conflict و rerere", hiddenInSingle = true }
+++

می‌زنید `git merge feature` و جواب می‌گیرید: `CONFLICT (content): Merge conflict in notes.txt`. فایل پر از علامت‌های عجیب شده و گیت می‌گوید «automatic merge failed». خیلی‌ها اولین باری که این را می‌بینند فکر می‌کنند چیزی خراب شده.

[merge و rebase](/fa/posts/git-merge-vs-rebase/) هر دو می‌توانند وسط کار بایستند و سؤال بپرسند. **{{< term "merge-conflict" "Conflict" >}}** خطای repository شما نیست. گیت دارد می‌گوید: «دو نفر یک جا را عوض کرده‌اند و من نمی‌توانم بدون نظر تو بین آن‌ها یکی را انتخاب کنم؛ تو تصمیم بگیر.» در این مقاله می‌بینیم گیت چه چیزی نشان می‌دهد، چطور آن را بخوانیم و حل کنیم، چطور در صورت گم شدن عقب‌نشینی کنیم، و چطور گیت یاد بگیرد حلی را که یک بار انجام داده‌ایم دوباره به‌کار ببرد (rerere).

> همه‌ی دستورهای زیر با Git نسخه‌ی 2.39.2 روی یک repository آزمایشی اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند. هش‌های commit (مثل `ea78c57` و `a4fb5af`) مال همان اجراهای اول‌اند و در اجرای شما فرق می‌کنند.

## ساختن یک conflict

برای اینکه conflict را ببینیم، یکی بسازیم. فایل `notes.txt` سه خط دارد و خط وسطش `status: draft` است. شاخه‌ی `feature` آن را به `status: review` تغییر داد و commit کرد، و شاخه‌ی `main` همان خط را به `status: published` تغییر داد. هر دو یک خط را از یک نقطه‌ی مشترک شروع و به دو شکل عوض کرده‌اند. حالا روی `main` می‌گوییم:

```text
$ git merge feature
Auto-merging notes.txt
CONFLICT (content): Merge conflict in notes.txt
Automatic merge failed; fix conflicts and then commit the result.
```

خط اول می‌گوید گیت تلاش کرد خودکار merge کند، خط دوم می‌گوید روی `notes.txt` نشد، و خط آخر راه ادامه را می‌دهد: حلش کن و commit بزن. `git status` وضعیت را نشان می‌دهد:

```text
Unmerged paths:
  (use "git add <file>..." to mark resolution)
	both modified:   notes.txt
```

(این فقط بخشی از خروجی `git status` است.) عبارت `both modified` یعنی conflict: فایل در هر دو طرف تغییر کرده است. بالاتر در همان خروجی گیت راه خروج را هم می‌گوید: `git merge --abort`. اگر خروجی کوتاه‌تر می‌خواهید، `git status -sb` برای همین فایل `UU notes.txt` چاپ می‌کند (`UU` یعنی unmerged در هر دو طرف).

## خواندن marker‌ها

حالا فایل را باز می‌کنیم. گیت هر دو نسخه را داخل خود فایل نوشته است:

```text
title: Report
<<<<<<< HEAD
status: published
=======
status: review
>>>>>>> feature
owner: nobody
```

سه خط marker داریم و بخش‌های بین آن‌ها:

- بین `<<<<<<<` و `=======` طرف شماست. `HEAD` یعنی شاخه‌ای که الان رویش هستید (اینجا `main`): `status: published`.
- بین `=======` و `>>>>>>>` طرف دیگر است، یعنی شاخه‌ی `feature`: `status: review`.
- خط‌های بیرون از marker‌ها (`title` و `owner`) conflict ندارند و گیت خودش حلشان کرده است.

در زمان conflict، `git diff` یک diff ترکیبی نشان می‌دهد:

```text
diff --cc notes.txt
index b48eb8f,994df04..0000000
--- a/notes.txt
+++ b/notes.txt
@@@ -1,3 -1,3 +1,7 @@@
  title: Report
++<<<<<<< HEAD
 +status: published
++=======
+ status: review
++>>>>>>> feature
  owner: nobody
```

به‌جای یک ستون `+` و `-`، دو ستون داریم، یکی برای هر طرف: ستون اول فایل فعلی را با `main` مقایسه می‌کند و ستون دوم با `feature`. خط `status: published` فقط در ستون دوم `+` دارد، چون نسبت به `feature` اضافه است ولی در `main` از قبل بود؛ و `status: review` برعکس. خط‌های marker در هر دو ستون `+` دارند، چون در هیچ‌کدام از دو طرف نبودند.

## حل کردن

حل کردن یعنی خودتان تصمیم بگیرید متن نهایی چیست. فایل را ویرایش کنید تا همان چیزی که می‌خواهید بماند، همه‌ی خط‌های marker را حذف کنید، و به گیت بگویید تمام شد. من تصمیم گرفتم `published` بماند:

```bash
printf 'title: Report\nstatus: published\nowner: nobody\n' > notes.txt
git add notes.txt
git commit
```

`git add` همان علامت «این فایل حل شد» است. بعد `git commit` merge commit را می‌سازد. به یاد داشته باشید که marker‌ها فقط متن‌اند؛ گیت جلوی commit کردنشان را نمی‌گیرد. اگر با marker commit شوند، در تاریخچه می‌مانند.

## عقب‌نشینی

اگر وسط حل گم شدید، لازم نیست ادامه بدهید. می‌توانید کل عملیات را لغو کنید و به حالت قبل از شروع برگردید. بعد از `git merge --abort`، وضعیت دوباره تمیز بود و `git status -sb` فقط `## main` چاپ کرد.

برای rebase هم همین‌طور است. وقتی `git rebase main` را روی `feature` زدم و conflict گرفتم، `git status -sb` نشان داد `## HEAD (no branch)` و `UU notes.txt`. یعنی وسط rebase هستیم و HEAD موقتاً به هیچ شاخه‌ای وصل نیست. با `git rebase --abort` به `## feature` با همان commit اولیه‌ی `ea78c57` برگشتم، بدون هیچ تغییری.

## جابه‌جایی ours و theirs

گیت دو اسم برای دو طرف دارد: «ours» (ما) و «theirs» (آن‌ها)، و دستور `git checkout --ours -- file` یا `--theirs` همان طرف را برای آن فایل انتخاب می‌کند. اسم‌ها گیج‌کننده‌اند، چون معنی‌شان بسته به عملیات عوض می‌شود. دلیلش این است که **{{< term "rebase" "rebase" >}}** کارِ شما را روی شاخه‌ی دیگر دوباره اجرا می‌کند.

برای دیدنش در هر دو حالت روی `feature` بودم (که `status: review` دارد) و `main` را با دو روش روی آن آوردم. بعد ببینیم `--ours` و `--theirs` چه نسخه‌ای می‌دهند:

| عملیات روی `feature` | `--ours` | `--theirs` |
|---|---|---|
| `git merge main` | `status: review` (feature) | `status: published` (main) |
| `git rebase main` | `status: published` (main) | `status: review` (feature) |

در merge، «ours» شاخه‌ای است که رویش هستید. در rebase قضیه برعکس می‌شود. گیت اول روی `main` می‌ایستد و بعد commitهای شما را یکی‌یکی روی آن دوباره اجرا می‌کند. پس در لحظه‌ی conflict، «ours» همان تاریخچه‌ی در حال ساخته شدن است (یعنی `main`) و «theirs» commitی است که دارد دوباره اجرا می‌شود، یعنی کار خودتان. اگر در rebase `--theirs` بزنید، نسخه‌ی خودتان را نگه داشته‌اید.

## دیدن base با zdiff3

در marker‌های پیش‌فرض فقط دو طرف را می‌بینید و نمی‌دانید هر کدام از چه چیزی شروع کرده است. با `git config merge.conflictStyle zdiff3` (طبق مستندات گیت از نسخه‌ی 2.35 به بعد؛ نسخه‌ی 2.39.2 من دارد) نسخه‌ی پدر مشترک، یعنی **{{< term "three-way-merge" "three-way merge" >}}**، هم در marker‌ها می‌آید. (merge سه‌طرفه یعنی گیت برای ترکیب، دو نسخه را با نسخه‌ی مشترکِ قبل از جدا شدن‌شان مقایسه می‌کند.)

```text
<<<<<<< HEAD
status: published
||||||| a4fb5af
status: draft
=======
status: review
>>>>>>> feature
```

بخش تازه بین `|||||||` و `=======` است، همان نسخه‌ی اصلی (`draft`). حالا معلوم می‌شود هر دو طرف `draft` را عوض کرده‌اند، یکی به `published` و دیگری به `review`. وقتی conflict بزرگ‌تر از یک خط است، دیدن این نسخه‌ی اصلی خیلی کمک می‌کند.

## rerere: یک بار حل کن

فرض کنید یک شاخه‌ی بلند را بارها rebase می‌کنید، یا merge را بعد از برگرداندنش دوباره انجام می‌دهید. هر بار همان conflict دوباره می‌آید و باید همان حل را از اول تایپ کنید. **{{< term "rerere" "rerere" >}}** («reuse recorded resolution»، یعنی حل ثبت‌شده را دوباره به‌کار ببر) یادش می‌ماند که شما conflict را چطور حل کرده‌اید. اول روشنش می‌کنیم:

```bash
git config rerere.enabled true
```

بار اول که conflict می‌آید، گیت متن conflict را ثبت می‌کند:

```text
CONFLICT (content): Merge conflict in notes.txt
Recorded preimage for 'notes.txt'
```

من حلش کردم و commit زدم، و گیت نوشت `Recorded resolution for 'notes.txt'.`، یعنی علاوه بر خود conflict، حل شما را هم ثبت کرد. حالا آزمایش: merge را با `git reset --hard HEAD~1` دور انداختم و دوباره merge کردم:

```text
Auto-merging notes.txt
CONFLICT (content): Merge conflict in notes.txt
Resolved 'notes.txt' using previous resolution.
Automatic merge failed; fix conflicts and then commit the result.
```

سطر سوم می‌گوید همان حل قبلی را به کار برد. فایل از قبل جواب مرا داشت و marker نداشت. ولی توجه کنید که `git status` هنوز `UU notes.txt` نشان داد: rerere فایل را پر می‌کند اما stage نمی‌کند. شما نتیجه را می‌بینید، `git add` می‌زنید و commit می‌کنید. این طراحی عمدی است، چون می‌خواهد نتیجه را خودتان بخوانید و تأیید کنید.

چه چیزی ذخیره می‌شود؟ برای هر conflict یک پوشه در `.git/rr-cache` هست که اسمش هش متن conflict است. در پوشه دو فایل است: `preimage` (خود conflict) و `postimage` (حل شما). تا وقتی conflict باز است، `git rerere status` فایل‌هایی را که rerere دنبال می‌کند فهرست می‌کند، و `git rerere diff` نشان می‌دهد فایل فعلی با conflict ثبت‌شده چه فرقی دارد. (درست بعد از conflict و قبل از حل، فقط خط‌های marker فرق دارند.)

اگر حل ثبت‌شده غلط بود، `git rerere forget notes.txt` آن را پاک می‌کند. این را هم امتحان کردم و گیت نوشت `Forgot resolution for 'notes.txt'`.

محدودیت‌ها:

- **فقط وقتی کار می‌کند که متن conflict همان باشد.** تغییر یک خط کناری یعنی conflict جدید.
- **فقط در clone شما ذخیره می‌شود.** هم‌تیمی‌هایتان حل شما را نمی‌بینند.
- **فقط conflict محتوایی را ثبت می‌کند.**
- **`git mergetool` را اینجا اجرا نکردم.** این ابزار یک ویرایشگر گرافیکی سه‌پنجره‌ای باز می‌کند.

## پیش از commit کردن حل

- **خط‌های marker را هرگز commit نکنید.** قبل از `git add`، در فایل دنبال `<<<<<<<` بگردید.
- **بعد از حل، تست‌ها را اجرا کنید.** یک merge متنیِ تمیز هم می‌تواند از نظر معنایی غلط باشد: هر دو طرف جدا درست‌اند ولی با هم نه.
- **وسط rebase بعد از حل، `git add` و بعد `git rebase --continue`.** خودتان `git commit` نزنید.
- **در rebase بدون چک کردن به «ours» و «theirs» اعتماد نکنید.** معنی‌شان برعکس merge است، مثل جدول بالا.
- **نتیجه‌ی rerere را قبل از stage کردن بخوانید.** فایل را پر می‌کند ولی درستی‌اش را تضمین نمی‌کند.

## تمرین

یک repository با دو شاخه بسازید که یک خط را عوض می‌کنند. با zdiff3 فعال merge و حل کنید. merge را reset کنید، rerere را روشن کنید، دوباره حل کنید، reset کنید و بار سوم merge کنید. داخل `.git/rr-cache` را ببینید. همین را با `git rebase` تکرار کنید و ببینید `--ours` چه می‌دهد.

## قدم بعدی

مقاله‌ی بعد «برگرداندن کار: reflog، revert و cherry-pick» است. اگر حلی که انجام داده‌اید بعداً خراب از آب دربیاید، آنجا ابزار برگرداندنش را می‌بینیم.
