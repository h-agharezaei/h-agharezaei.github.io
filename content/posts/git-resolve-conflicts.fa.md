+++
date = '2026-11-05T10:00:00+03:30'
draft = false
title = 'حل conflict و rerere'
description = 'حل conflict در Git قدم‌به‌قدم: خواندن marker‌ها، abort امن، فرق ours و theirs در merge و rebase، و استفاده‌ی دوباره از حل‌ها با rerere.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "merge-conflict", "rerere", "beginner"]
cover = { image = "/images/covers/git-resolve-conflicts.fa.png", alt = "حل conflict و rerere", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/git-merge-vs-rebase/) merge و rebase را روی دو تاریخچه‌ی واقعی مقایسه کردیم. هر دو ممکن است وسط کار بایستند و از شما سؤال بپرسند، و همین لحظه بسیاری از مبتدی‌ها را می‌ترساند. **{{< term "merge-conflict" "Conflict" >}}** خطای repository شما نیست. Git می‌گوید «دو نفر یک جا را عوض کرده‌اند، تو تصمیم بگیر».

> همه‌ی دستورهای زیر با Git نسخه‌ی 2.39.2 روی یک repository آزمایشی اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند.

## ساختن یک conflict

شاخه‌های `main` و `feature` هر دو خط `status:` فایل `notes.txt` را (که اول `status: draft` بود) عوض کرده‌اند. بعد:

```text
$ git merge feature
Auto-merging notes.txt
CONFLICT (content): Merge conflict in notes.txt
Automatic merge failed; fix conflicts and then commit the result.
```

`git status` وضعیت را نشان می‌دهد:

```text
Unmerged paths:
  (use "git add <file>..." to mark resolution)
	both modified:   notes.txt
```

عبارت `both modified` یعنی conflict: فایل در هر دو طرف تغییر کرده است. Git راه خروج را هم می‌گوید: `git merge --abort`.

## خواندن marker‌ها

Git هر دو نسخه را داخل فایل نوشته است:

```text
title: Report
<<<<<<< HEAD
status: published
=======
status: review
>>>>>>> feature
owner: nobody
```

بین `<<<<<<<` و `=======` طرف شماست (`HEAD`، شاخه‌ای که رویش هستید). بین `=======` و `>>>>>>>` طرف دیگر است. در زمان conflict، `git diff` یک diff ترکیبی با دو ستون `+` و `-` نشان می‌دهد، یک ستون برای هر طرف.

## حل کردن

فایل را به متن نهایی ویرایش کنید، همه‌ی خط‌های marker را حذف کنید و به Git بگویید تمام شد:

```bash
printf 'title: Report\nstatus: published\nowner: nobody\n' > notes.txt
git add notes.txt
git commit
```

`git add` همان علامت «حل شد» است. marker‌ها فقط متن‌اند؛ اگر commit شوند در تاریخچه می‌مانند.

## عقب‌نشینی

اگر گم شدید، abort کنید. بعد از `git merge --abort` وضعیت دوباره تمیز و `## main` شد. برای rebase، دستور `git rebase --abort` مرا به `## feature` با همان commit اولیه‌ی `ea78c57` برگرداند.

## جابه‌جایی ours و theirs

دستور `git checkout --ours -- file` و `--theirs` یک طرف را انتخاب می‌کنند. اسم‌ها گیج‌کننده‌اند چون **{{< term "rebase" "rebase" >}}** commit‌های شما را روی شاخه‌ی دیگر دوباره اجرا می‌کند. در هر دو حالت روی `feature` بودم و دیدم `--ours` چه می‌دهد:

| عملیات روی `feature` | `--ours` | `--theirs` |
|---|---|---|
| `git merge main` | `status: review` (feature) | `status: published` (main) |
| `git rebase main` | `status: published` (main) | `status: review` (feature) |

در merge، «ours» شاخه‌ای است که رویش هستید. در rebase، Git روی `main` تاریخچه‌ی جدید می‌سازد، پس «ours» همان تاریخچه‌ی در حال ساخته شدن است و «theirs» commitی است که دوباره اجرا می‌شود، یعنی کار خودتان. پس «ours» پایه‌ای است که رویش می‌سازید.

## دیدن base با zdiff3

به‌طور پیش‌فرض فقط دو طرف را می‌بینید. با `git config merge.conflictStyle zdiff3` (از Git 2.35 به بعد؛ نسخه‌ی 2.39.2 من دارد) پدر مشترک **{{< term "three-way-merge" "three-way merge" >}}** هم در marker‌ها می‌آید:

```text
<<<<<<< HEAD
status: published
||||||| a4fb5af
status: draft
=======
status: review
>>>>>>> feature
```

حالا می‌بینید هر دو طرف `draft` را عوض کرده‌اند، یکی به `published` و دیگری به `review`.

## rerere: یک بار حل کن

اگر یک شاخه‌ی بلند را بارها rebase کنید، یا merge را بعد از برگرداندن دوباره انجام دهید، همان conflict دوباره می‌آید. **{{< term "rerere" "rerere" >}}** («reuse recorded resolution») یادش می‌ماند شما چطور حلش کرده‌اید:

```bash
git config rerere.enabled true
```

بار اول Git متن conflict را ثبت می‌کند:

```text
CONFLICT (content): Merge conflict in notes.txt
Recorded preimage for 'notes.txt'
```

من حلش کردم و commit زدم و Git نوشت `Recorded resolution for 'notes.txt'.`. بعد merge را با `git reset --hard HEAD~1` دور انداختم و دوباره merge کردم:

```text
Auto-merging notes.txt
CONFLICT (content): Merge conflict in notes.txt
Resolved 'notes.txt' using previous resolution.
Automatic merge failed; fix conflicts and then commit the result.
```

فایل از قبل جواب مرا داشت. توجه کنید `git status` هنوز `UU notes.txt` را نشان داد: rerere فایل را پر می‌کند ولی stage نمی‌کند. نتیجه را می‌بینید، `git add` می‌زنید و commit می‌کنید.

چه چیزی ذخیره می‌شود: برای هر conflict یک پوشه در `.git/rr-cache` که اسمش hash متن conflict است و `preimage` (خود conflict) و `postimage` (حل شما) را نگه می‌دارد. تا وقتی conflict باز است، `git rerere status` فایل‌های تحت نظر را فهرست می‌کند و `git rerere diff` وضعیت فعلی حل شما را نشان می‌دهد.

محدودیت‌ها: فقط وقتی کار می‌کند که متن conflict همان باشد، پس تغییر یک خط کناری یعنی conflict جدید. فقط در clone شما ذخیره می‌شود و فقط conflict محتوایی را ثبت می‌کند. اگر حل ثبت‌شده غلط بود، `git rerere forget <path>` آن را پاک می‌کند؛ این مرحله را تأیید نکردم. ابزار `git mergetool` یک ویرایشگر گرافیکی سه‌پنجره‌ای باز می‌کند؛ اینجا اجرایش نکردم.

## چند نکته‌ی مهم

- خط‌های marker را هرگز commit نکنید؛ قبلش `<<<<<<<` را جست‌وجو کنید.
- بعد از حل، تست‌ها را اجرا کنید. merge متنیِ تمیز هم می‌تواند از نظر معنایی غلط باشد.
- وسط rebase بعد از حل، `git add` و بعد `git rebase --continue`؛ خودتان `git commit` نزنید.
- در rebase بدون چک کردن فایل به «ours» و «theirs» اعتماد نکنید، مثل جدول بالا.
- نتیجه‌ی rerere را قبل از stage کردن بخوانید.

## تمرین

یک repository با دو شاخه بسازید که یک خط را عوض می‌کنند. با zdiff3 فعال merge و حل کنید. merge را reset کنید، rerere را روشن کنید، دوباره حل کنید، reset کنید و بار سوم merge کنید. داخل `.git/rr-cache` را ببینید. همین را با `git rebase` تکرار کنید و ببینید `--ours` چه می‌دهد.

## قدم بعدی

مقاله‌ی بعدی «برگرداندن کار: reflog، revert و cherry-pick» است.
