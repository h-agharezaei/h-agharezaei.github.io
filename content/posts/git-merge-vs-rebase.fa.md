+++
date = '2026-11-03T10:00:00+03:30'
draft = false
title = 'merge یا rebase؟ دو تاریخچه‌ی واقعی'
description = 'تفاوت git merge و rebase با خروجی واقعی: merge commit، fast-forward، تغییر hashها، قانون طلایی، force-with-lease، pull --rebase و squash.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "merge", "rebase", "beginner"]
cover = { image = "/images/covers/git-merge-vs-rebase.fa.png", alt = "merge یا rebase؟ دو تاریخچه‌ی واقعی", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/git-branches-head-refs/) دیدیم که branch فقط یک اشاره‌گر به یک commit است. پس سؤال بعدی ساده است: وقتی دو branch از هم جدا شدند، چطور دوباره آن‌ها را کنار هم بگذاریم؟ گیت دو جواب دارد: **{{< term "merge" "merge" >}}** و **{{< term "rebase" "rebase" >}}**. هر دو در آخر فایل‌های یکسانی به شما می‌دهند، ولی تاریخچه‌ی متفاوتی باقی می‌گذارند.

> همه‌ی مثال‌های زیر با Git نسخه‌ی 2.39.2 در repoهای موقت اجرا شده‌اند. تاریخ commitها را ثابت کردم تا hashها تکرارپذیر باشند. مسیرها در خروجی کوتاه شده‌اند.

## نقطه‌ی شروع

بعد از جدا شدن، `main` دو commit دارد (M1 و M2) و `feature` هم دو commit (F1 و F2)، و هر دو از A شروع شده‌اند:

```text
* da67a24 F2: feature two
* 9dfc2e3 F1: feature one
| * 028a1d9 M2: main two
| * 1c4c0d2 M1: main one
|/
* 2cec988 A: first
```

این وضعیت را دو بار ساختم، تا هر روش repo خودش را داشته باشد.

## روش اول: merge

`main` جلو رفته، پس **{{< term "fast-forward" "fast-forward" >}}** ممکن نیست. اگر اصرار کنیم، خطا می‌گیریم:

```text
$ git merge --ff-only feature
fatal: Not possible to fast-forward, aborting.
```

merge معمولی یک **{{< term "merge-commit" "merge commit" >}}** می‌سازد:

```text
*   51bb97e Merge feature
|\
| * da67a24 F2: feature two
| * 9dfc2e3 F1: feature one
* | 028a1d9 M2: main two
* | 1c4c0d2 M1: main one
|/
* 2cec988 A: first
```

hashهای قبلی سر جایشان هستند. تاریخچه راست می‌گوید: دو خط کار بوده و بعد به هم وصل شده‌اند. هزینه‌اش گراف شلوغ‌تر است.

## روش دوم: rebase

در repo دوم، روی `feature` دستور `git rebase main` را زدم. قبل از آن `feature` برابر `da67a24` و `9dfc2e3` بود. بعد از آن:

```text
* 6b40805 F2: feature two
* c170ba7 F1: feature one
* 028a1d9 M2: main two
* 1c4c0d2 M1: main one
* 2cec988 A: first
```

تاریخچه یک خط مستقیم شد، ولی به idها نگاه کنید: F1 قبلاً `9dfc2e3` بود و حالا `c170ba7` است، و F2 از `da67a24` به `6b40805` رفته. rebase commitها را جابه‌جا نمی‌کند؛ روی پایه‌ی جدید از آن‌ها کپی می‌سازد. بعد `git merge --ff-only feature` روی `main` یک fast-forward خالص است (`Updating 028a1d9..6b40805` و `Fast-forward`) و merge commit ساخته نمی‌شود.

اگر حتی در حالتی که fast-forward ممکن است merge commit می‌خواهید، از `--no-ff` استفاده کنید. روی branchی که می‌توانست fast-forward شود امتحانش کردم و `Merge made by the 'ort' strategy` و یک لوزی در گراف دیدم.

## قانون طلایی

commitهایی را که دیگران دارند rebase نکنید. مشکل را با یک repo خالی (bare) و دو clone با نام‌های ali و sara بازسازی کردم؛ هر دو روی `feature` با F1 بودند. علی روی `main` جدیدتر rebase می‌کند. push معمولی رد می‌شود (`! [rejected] feature -> feature (non-fast-forward)`)، پس علی با **{{< term "force-push" "force push" >}}** می‌فرستد:

```text
 + 9e3e10c...2a3363a feature -> feature (forced update)
```

در این فاصله سارا روی F1 قدیمی commit به نام F2 زده بود. `git pull` او برای `origin/feature` عبارت `(forced update)` چاپ کرد و بعد یک merge commit ساخت. حالا تاریخچه‌اش یک تغییر را دو بار دارد:

```text
*   20db2d8 Merge branch 'feature' of origin into feature
|\
| * 2a3363a F1: feature one
| * 26aa3e9 M1: main one
* | 3569d28 F2: sara's work
* | 9e3e10c F1: feature one
|/
* f188366 A: first
```

`F1: feature one` دو بار با hashهای متفاوت آمده است. قانون برای جلوگیری از همین بی‌نظمی است.

## محافظت از خودتان

`--force-with-lease` فقط وقتی remote را بازنویسی می‌کند که هنوز همان جایی باشد که آخرین بار دیده‌اید. وقتی سارا F2 را push کرده بود و علی fetch نکرده بود، این را زدم:

```text
 ! [rejected]        feature -> feature (stale info)
```

`--force` ساده F2 را پاک می‌کرد.

اگر کار خودتان هنوز push نشده، `git pull --rebase` commitهای محلی را روی remote بازنویسی‌شده دوباره اجرا می‌کند. در همان سناریو خط تمیز داد و F1 تکراری نشد:

```text
* b5645b5 F2: sara's work
* 2a3363a F1: feature one
* 26aa3e9 M1: main one
* f188366 A: first
```

## Squash

`git merge --squash feature` مجموع تغییرات را stage می‌کند (`A f1.txt` و `A f2.txt`) و می‌ایستد؛ خودتان یک بار commit می‌کنید. لاگ فقط یک commit روی M2 دارد (`b395ae0 Add feature (squashed)`). توجه کنید که `git branch --no-merged` هنوز `feature` را نشان می‌دهد، چون گیت پیوندی به commitهایش نمی‌بیند.

## کدام را انتخاب کنیم

این جدول نظر خودم است، نه یک قانون:

| وضعیت | انتخاب من |
|---|---|
| به‌روز کردن branch شخصی از `main` | rebase |
| وارد کردن یک feature تمام‌شده به `main` | merge (یا squash اگر commitها نویز هستند) |
| branchی که دیگران هم روی آن push می‌کنند | merge، هرگز rebase |
| مرتب کردن چند commit محلی آخرم | rebase |

## چند نکته‌ی مهم

- rebase تاریخچه را بازنویسی می‌کند. بعد از آن `git push` به force نیاز دارد، پس از `--force-with-lease` استفاده کنید.
- conflict در rebase برای هر commit بازپخش‌شده جداگانه حل می‌شود، یعنی ممکن است یک بخش را چند بار حل کنید.
- squash commitهای جداگانه را از بین می‌برد و `git bisect` هم دقتش کمتر می‌شود.
- rebase همراه با conflict را این‌جا امتحان نکردم؛ موضوع مقاله‌ی بعد است.

## تمرین

یک repo با `main` و `feature` جداشده بسازید. یک بار merge کنید، بعد با `git reset --hard` به قبل از merge برگردید و این بار rebase کنید. خروجی `git log --graph --oneline` را مقایسه کنید و ببینید کدام hashها عوض شدند.

## قدم بعدی

مقاله‌ی بعد «حل conflict و rerere» است.
