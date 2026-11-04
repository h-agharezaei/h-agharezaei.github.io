+++
date = '2026-11-03T10:00:00+03:30'
draft = false
title = 'merge یا rebase؟ دو تاریخچه‌ی واقعی'
description = 'تفاوت git merge و rebase با خروجی واقعی: merge commit، fast-forward، تغییر hashها، قانون طلایی، force-with-lease، pull --rebase و squash.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "merge", "rebase", "beginner"]
cover = { image = "/images/covers/git-merge-vs-rebase.fa.png", alt = "merge یا rebase؟ دو تاریخچه‌ی واقعی", hiddenInSingle = true }
+++

فرض کنید برای یک feature از `main` یک branch جدا کرده‌اید و دو commit روی آن زده‌اید. در همین فاصله هم‌تیمی‌تان دو commit دیگر روی `main` گذاشته است. حالا branch شما از `main` عقب است و `main` هم commitهایی دارد که شما ندارید. چطور این دو را دوباره کنار هم بگذاریم؟

گیت دو جواب دارد: **{{< term "merge" "merge" >}}** و **{{< term "rebase" "rebase" >}}**. هر دو در آخر فایل‌های یکسانی به شما می‌دهند، ولی تاریخچه‌ی متفاوتی باقی می‌گذارند:

- **merge** یک commit تازه می‌سازد که کارِ دو طرف را به هم وصل می‌کند. commitهای قبلی دست نمی‌خورند و hashهایشان همان می‌ماند.
- **rebase** commitهای شما را برمی‌دارد و روی آخرین commit `main` دوباره می‌سازد. نتیجه یک خط مستقیم است، ولی commitهای بازسازی‌شده hash تازه دارند.

همین تفاوت تعیین می‌کند اگر تاریخچه را بازنویسی کنید و force push بزنید، به هم‌تیمی‌ها آسیب می‌رسد یا نه. branch فقط اشاره‌گری به یک commit است ([مقاله‌ی قبل](/fa/posts/git-branches-head-refs/))، پس هر دو روش در واقع می‌گویند اشاره‌گرها کجا بایستند و چه commitهایی بینشان باشد. در این مقاله هر دو را روی یک تاریخچه‌ی واقعی می‌بینیم.

> همه‌ی مثال‌های زیر با Git نسخه‌ی 2.39.2 در repoهای موقت اجرا شده‌اند. تاریخ commitها را ثابت کردم تا hashها تکرارپذیر باشند. مسیرها در خروجی کوتاه شده‌اند.

## نقطه‌ی شروع

برای مقایسه‌ی منصفانه، یک تاریخچه‌ی ساده ساختم. بعد از جدا شدن، `main` دو commit دارد (M1 و M2) و `feature` هم دو commit (F1 و F2)، و هر دو از commit اولیه‌ی A شروع شده‌اند:

```text
* da67a24 F2: feature two
* 9dfc2e3 F1: feature one
| * 028a1d9 M2: main two
| * 1c4c0d2 M1: main one
|/
* 2cec988 A: first
```

هر `*` یک commit است. دو خط موازی را می‌بینید که از A جدا شده‌اند. این وضعیت را دو بار ساختم، تا هر روش repo خودش را داشته باشد و روی کار دیگری اثر نگذارد.

## روش اول: merge

ساده‌ترین حالت merge همان است که در مقاله‌ی قبل دیدیم: اگر `main` چیزی نداشته باشد که `feature` ندارد، گیت فقط اشاره‌گر را جلو می‌برد (**{{< term "fast-forward" "fast-forward" >}}**). ولی اینجا `main` جلو رفته، پس fast-forward ممکن نیست. اگر با `--ff-only` اصرار کنیم، گیت قبول نمی‌کند:

```text
$ git merge --ff-only feature
fatal: Not possible to fast-forward, aborting.
```

بدون آن گزینه، گیت یک **{{< term "merge-commit" "merge commit" >}}** می‌سازد، یعنی commitی که دو والد دارد: آخر `main` و آخر `feature`.

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

بالا یک commit تازه (`51bb97e`) می‌بینیم که دو خط را به هم می‌رساند. hashهای قبلی (`da67a24`، `9dfc2e3` و بقیه) همه سر جایشان هستند. تاریخچه راست می‌گوید چه اتفاقی افتاده: دو خط کار بوده و بعد به هم وصل شده‌اند. هزینه‌اش گراف شلوغ‌تر است، مخصوصاً وقتی merge زیاد می‌شود.

## روش دوم: rebase

در repo دوم، روی `feature` دستور `git rebase main` را زدم. یعنی: «commitهای من را بردار و طوری بچین که انگار از آخر `main` شروع شده‌اند.» قبل از آن `feature` دو commit به hashهای `da67a24` و `9dfc2e3` داشت. بعد از rebase (خط اول پیام خود rebase است و بقیه خروجی `git log --graph --oneline`):

```text
Successfully rebased and updated refs/heads/feature.

* 6b40805 F2: feature two
* c170ba7 F1: feature one
* 028a1d9 M2: main two
* 1c4c0d2 M1: main one
* 2cec988 A: first
```

تاریخچه یک خط مستقیم شد و merge commit ندارد. ولی به idها نگاه کنید: F1 قبلاً `9dfc2e3` بود و حالا `c170ba7` است، و F2 از `da67a24` به `6b40805` رفته. چرا؟ یادتان هست در [مقاله‌ی اول](/fa/posts/git-how-git-thinks/) دیدیم هر commit هش والدش را در خودش دارد. F1 حالا والد دیگری دارد (M2 به‌جای A)، پس هر چند محتوای تغییرش همان است، commit دیگری است و hash دیگری می‌گیرد. F2 هم که والدش عوض شد، همین‌طور. پس rebase commitها را جابه‌جا نمی‌کند؛ روی پایه‌ی جدید از آن‌ها نسخه‌ی تازه می‌سازد و اشاره‌گر `feature` را به نسخه‌های تازه می‌برد.

برای وارد کردن کار در `main`، حالا `git merge --ff-only feature` را روی `main` می‌زنیم. چون `feature` دقیقاً از آخر `main` ادامه پیدا کرده، یک fast-forward خالص است (خروجی `Updating 028a1d9..6b40805` و `Fast-forward`) و merge commit ساخته نمی‌شود.

اگر حتی در حالتی که fast-forward ممکن است، یک merge commit می‌خواهید، گزینه‌ی `--no-ff` را بدهید. روی branchی که می‌توانست fast-forward شود امتحانش کردم: خروجی `Merge made by the 'ort' strategy` بود و در گراف یک لوزی (دو خط که به هم می‌رسند) ساخته شد.

## قانون طلایی

حالا مهم‌ترین قاعده‌ی rebase: **commitهایی را که دیگران هم دارند rebase نکنید.** چرا؟ چون rebase commitهای تازه با hashهای تازه می‌سازد. اگر کس دیگری روی نسخه‌ی قدیمی ادامه داده باشد، دو تاریخچه‌ی ناسازگار پیدا می‌کنید.

برای دیدن مشکل، با یک repo خالی (bare) و دو clone به نام‌های ali و sara صحنه را بازسازی کردم. هر دو روی `feature` بودند و commit F1 را داشتند. علی `main` را جلو برد و `feature` را روی آن rebase کرد. push معمولی را گیت رد می‌کند، چون تاریخچه‌ی علی دیگر ادامه‌ی نسخه‌ی روی remote نیست (`! [rejected] feature -> feature (non-fast-forward)`). پس علی با **{{< term "force-push" "force push" >}}** می‌فرستد، یعنی به remote می‌گوید نسخه‌ی قبلی را دور بینداز و این را بگذار:

```text
 + 9e3e10c...2a3363a feature -> feature (forced update)
```

علامت `+` و `(forced update)` یعنی remote از `9e3e10c` (F1 قدیمی) به `2a3363a` (F1 بازسازی‌شده) رفت.

در همین فاصله سارا روی F1 قدیمی یک commit به نام F2 زده بود. وقتی `git pull` می‌زند، `fetch` همان `(forced update)` را برای `origin/feature` چاپ می‌کند و بعد گیت می‌ایستد، چون تاریخچه‌ی او و remote از هم جدا شده‌اند و گیت نمی‌داند چطور آن‌ها را یکی کند. خروجی با این خط تمام می‌شود:

```text
fatal: Need to specify how to reconcile divergent branches.
```

(این رفتار با تنظیمات پیش‌فرض است. اگر `pull.rebase` را در config خود تنظیم کرده باشید، گیت همان را اجرا می‌کند و سؤالی نمی‌پرسد.) سارا اولین گزینه‌ی hint را انتخاب می‌کند و `git pull --no-rebase` می‌زند، یعنی merge. گیت یک merge commit می‌سازد و حالا تاریخچه‌ی سارا یک تغییر را دو بار دارد:

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

`F1: feature one` دو بار آمده، یک بار با hash قدیمی (`9e3e10c`) و یک بار با hash بازسازی‌شده (`2a3363a`). این همان بی‌نظمی است که قانون طلایی جلویش را می‌گیرد. (hash خودِ merge commit در اجرای شما فرق می‌کند، چون پیامش مسیر remote را دارد؛ من مسیر را در متن کوتاه کرده‌ام.)

## محافظت از خودتان

گاهی واقعاً لازم است force push بزنید، مثلاً بعد از rebase روی branch شخصی. دو ابزار می‌تواند آسیب را کم کند.

**`--force-with-lease`.** `--force` ساده remote را بی‌قید بازنویسی می‌کند. `--force-with-lease` فقط وقتی بازنویسی می‌کند که remote هنوز همان جایی باشد که شما آخرین بار دیده‌اید. برای امتحان، سارا F2 را push کرده بود و علی هنوز fetch نکرده بود. علی این را زد:

```text
 ! [rejected]        feature -> feature (stale info)
```

`stale info` یعنی اطلاعات علی از remote کهنه است و remote چیزی دارد که او ندیده. گیت push را رد کرد و کار سارا نجات پیدا کرد؛ `--force` ساده F2 را پاک می‌کرد.

**`git pull --rebase`.** اگر کار خودتان هنوز push نشده، این دستور commitهای محلی را روی remote بازنویسی‌شده دوباره اجرا می‌کند، به‌جای اینکه merge بسازد. در همان سناریو (این بار سارا F2 را push نکرده بود) نتیجه تمیز شد:

```text
* b5645b5 F2: sara's work
* 2a3363a F1: feature one
* 26aa3e9 M1: main one
* f188366 A: first
```

در خروجی `Rebasing (1/1)` را دیدم، یعنی فقط یک commit بازپخش شد (F2)، و F1 تکراری نشد. تاریخچه یک خط راست است.

## Squash

راه سوم این است که اصلاً commitهای `feature` را نگه ندارید. `git merge --squash feature` مجموع تغییرات را stage می‌کند (`A f1.txt` و `A f2.txt`) و می‌ایستد؛ خودتان یک بار commit می‌کنید. لاگ فقط یک commit روی M2 دارد (`b395ae0 Add feature (squashed)`) و خط‌های F1 و F2 در آن نیستند.

یک نکته: بعد از squash، `git branch --no-merged` هنوز `feature` را نشان می‌دهد. چون گیت پیوندی بین commit جدید و commitهای `feature` نمی‌بیند و فکر می‌کند این branch هنوز merge نشده.

## کدام را انتخاب کنیم

این جدول نظر خودم است، نه یک قانون:

| وضعیت | انتخاب من |
|---|---|
| به‌روز کردن branch شخصی از `main` | rebase |
| وارد کردن یک feature تمام‌شده به `main` | merge (یا squash اگر commitها نویز هستند) |
| branchی که دیگران هم روی آن push می‌کنند | merge، هرگز rebase |
| مرتب کردن چند commit محلی آخرم | rebase |

## هزینه‌های بازنویسی تاریخچه

- **rebase تاریخچه را بازنویسی می‌کند.** بعد از آن `git push` به force نیاز دارد، پس از `--force-with-lease` استفاده کنید.
- **conflict در rebase برای هر commit جداگانه حل می‌شود.** commitها یکی‌یکی بازپخش می‌شوند، پس ممکن است یک بخش را چند بار حل کنید.
- **squash commitهای جداگانه را از بین می‌برد.** در `git bisect` (پیدا کردن commit خراب) هم دقت کمتر می‌شود، چون به‌جای چند commit کوچک یک commit بزرگ دارید.
- **rebase همراه با conflict را اینجا امتحان نکردم.** موضوع مقاله‌ی بعد است.

## تمرین

یک repo با `main` و `feature` جداشده بسازید. یک بار merge کنید، بعد با `git reset --hard` به قبل از merge برگردید و این بار rebase کنید. خروجی `git log --graph --oneline` را مقایسه کنید و ببینید کدام hashها عوض شدند.

## قدم بعدی

مقاله‌ی بعد «حل conflict و rerere» است. هر دو روش ممکن است وسط راه روی conflict بایستند، و این حالت را اینجا امتحان نکردیم.
