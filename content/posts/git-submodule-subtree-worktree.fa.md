+++
date = '2026-11-15T10:00:00+03:30'
draft = false
title = 'submodule، subtree و worktree'
description = 'مقایسه‌ی submodule، subtree و worktree در گیت با اجرای واقعی: gitlink، clone ناقص، pointer ناپوش‌شده، subtree split و دو branch همزمان.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "submodule", "subtree", "worktree"]
cover = { image = "/images/covers/git-submodule-subtree-worktree.fa.png", alt = "submodule، subtree و worktree", hiddenInSingle = true }
+++

فرض کنید repository شما به کد یک repository دیگر نیاز دارد، مثلاً یک کتابخانه‌ی مشترک یا یک پوسته‌ی وبلاگ. کپی‌کردن پوشه‌ی آن توی پروژه‌ی خودتان کار می‌کند، تا روزی که کتابخانه یک باگ را رفع کند و شما نفهمید کدام نسخه‌اش را دارید. گیت برای این وضع ابزار دارد، و یک مشکل مشابه هم هست: وسط کار روی یک branch، یک hotfix فوری می‌رسد و نمی‌خواهید کار نیمه‌تمامتان را stash کنید.

برای این‌ها سه ابزار هست که راحت با هم قاطی می‌شوند: {{< term "submodule" "submodule" >}}، {{< term "subtree" "subtree" >}} و {{< term "worktree" "worktree" >}}. دو تای اول برای وقتی‌اند که repository شما به repository دیگری نیاز دارد؛ سومی برای وقتی است که دو branch را همزمان روی دیسک می‌خواهید. بعد از [کنترل‌های دور commit](/fa/posts/git-hooks-commit-hygiene/)، این سمت دیگر کار روزمره است.

این وبلاگ هم از یکی از آن‌ها استفاده می‌کند. فایل `.gitmodules` این repo فقط یک ورودی دارد، `themes/PaperMod` که به repository پوسته‌ی PaperMod در GitHub اشاره می‌کند، و `git submodule status` این را چاپ می‌کند: `7d061d5... themes/PaperMod (v8.0-54-g7d061d5)`. یعنی یک commit پین‌شده از کد دیگران. این مقاله نشان می‌دهد پشت این یک خط چه می‌گذرد و کجاها گیر می‌افتید.

> همه‌ی دستورها با Git نسخه‌ی 2.39.2 در repositoryهای موقت اجرا شده‌اند و remoteها مسیر محلی بوده‌اند. hashها در هر اجرا فرق می‌کنند، پس مال شما یکی نخواهد بود. برای دمو `protocol.file.allow=always` را در محیط گذاشتم، چون گیت به‌صورت پیش‌فرض submodule با مسیر محلی را مسدود می‌کند. این فقط برای دموی محلی لازم است.

## submodule فقط یک pointer است

ایده‌ی submodule ساده است: repository والد خودِ کد کتابخانه را نگه نمی‌دارد، فقط یادداشتی دارد که می‌گوید «از آن repository، commit شماره‌ی فلان را بگیر». یعنی یک اشاره‌گر (pointer) به یک commit مشخص. برای دیدنش دو repo ساختم: `lib` (کتابخانه) و `app` (برنامه‌ای که از آن استفاده می‌کند). بعد کتابخانه را به برنامه اضافه کردم:

```bash
cd app
git submodule add ../lib lib
git commit -m "add lib submodule"
git ls-tree HEAD
```

دستور آخر محتوای commit را فهرست می‌کند، یعنی چیزی که Git واقعاً ذخیره کرده:

```text
100644 blob 008e8edaf3165b09395d7d5fe13cb3e657072b74	.gitmodules
100644 blob b80f0bd60822d4fa4893de455958ef32f6c521bf	README
160000 commit 390b441e850cdffb00b1fed3b0abb7551293e794	lib
```

دو خط اول فایل‌های معمولی‌اند. `.gitmodules` فایل متنی کوچکی است که نشانی repository کتابخانه را نگه می‌دارد. خط آخر جالب است: ورودی `lib` یک {{< term "gitlink" "gitlink" >}} است. mode آن `160000` است و به‌جای blob یا tree، یک id برای commit دارد. `app` هیچ فایلی از `lib` ندارد؛ فقط می‌گوید «commit شماره‌ی 390b441 را بگیر».

## فراموش کردن --recurse-submodules

نتیجه‌ی این طراحی اولین گیر کار است. clone معمولی فقط یادداشت را می‌آورد، نه کد را. من `app` را clone کردم و پوشه‌ی `lib` را شمردم:

```bash
git clone app app-plain
ls -A app-plain/lib | wc -l      # 0
git -C app-plain submodule status
```

```text
       0
-390b441e850cdffb00b1fed3b0abb7551293e794 lib
```

پوشه‌ی `lib` هست ولی خالی است (صفر فایل). در خروجی `submodule status`، علامت `-` اول خط یعنی «مقداردهی اولیه نشده»، یعنی Git هنوز آن commit را نگرفته. با `git submodule update --init` درستش می‌کنید، یا از همان اول با `git clone --recurse-submodules` clone کنید.

وقتی داخل submodule می‌روید، چیز دیگری هم می‌بینید: در حالت {{< term "detached-head" "detached HEAD" >}} هستید، یعنی روی یک commit ایستاده‌اید، نه روی یک branch:

```text
HEAD detached at 390b441
```

این عمدی است، چون والد یک commit را پین می‌کند، نه یک branch را. اما یک تله دارد: اگر آنجا commit بزنید و بعد branch را عوض کنید، commit جدید هیچ branchی ندارد که به آن اشاره کند. برای کار روی کتابخانه اول یک branch بسازید (یا `git switch main`).

## جابه‌جا کردن pointer

وقتی `lib` یک commit جدید می‌گیرد، والد خودش متوجه نمی‌شود، چون به یک commit مشخص اشاره می‌کند. باید خودتان pointer را جلو ببرید:

```bash
git submodule update --remote    # lib را fetch و آخرین main را checkout می‌کند
git status --short               #  M lib
git commit -am "bump lib to v2"
```

بعد از `update --remote`، `git status` پوشه‌ی `lib` را تغییرکرده نشان می‌دهد (`M lib`)، چون commitی که الان در آن است با آنچه والد ثبت کرده فرق دارد. با commit کردن، آن تغییر ثبت می‌شود. تغییر در `app` فقط یک خط است: gitlink حالا به commit دیگری اشاره می‌کند.

## اشتباه کلاسیک: pointer به commitی که هیچ‌کس نمی‌تواند بگیرد

حالا رایج‌ترین خطای این ابزار. داخل `app/lib` یک commit زدم، pointer جدید را در `app` commit کردم، ولی `lib` را push نکردم. بعد یک همکار (یک clone دیگر) `git pull` زد:

```text
Fetching submodule lib
fatal: git upload-pack: not our ref fcc7862444cb18d7efe83c7f6a4628e8208d70a1
fatal: remote error: upload-pack: not our ref fcc7862444cb18d7efe83c7f6a4628e8208d70a1
Errors during submodule fetch:
	lib
pull exit=1
```

commit والد معتبر است، ولی به commitی اشاره می‌کند که فقط روی دیسک من وجود دارد. سرور `lib` می‌گوید «چنین چیزی در اختیار ندارم» (`not our ref`) و pull خطا می‌دهد. قاعده این است: اول submodule را push کنید، بعد والد را. بعد از push کردن `lib`، همان pull و `git submodule update` درست کار کردند.

## subtree: فقط فایل

submodule یک اشاره‌گر است؛ {{< term "subtree" "subtree" >}} برعکس، خود فایل‌ها را داخل repository شما می‌آورد. `git subtree` روی این نصب گیت وجود دارد (بررسی کردم `git-subtree` در exec path هست؛ این دستور بخش contrib است و ممکن است در بعضی buildها نباشد). اول کتابخانه را به پوشه‌ی `vendor/lib` اضافه می‌کنیم. `--squash` یعنی کل تاریخچه‌ی کتابخانه به‌جای اینکه commit به commit بیاید، در یک commit جمع شود:

```bash
git subtree add --prefix=vendor/lib ../lib main --squash
```

```text
Added dir 'vendor/lib'
```

بعد کتابخانه یک نسخه‌ی جدید گرفت و با `pull` آن را آوردم، که در خروجی تغییر فایل را نشان می‌دهد:

```bash
git subtree pull --prefix=vendor/lib ../lib main --squash -m "pull lib"
```

```text
 vendor/lib/greet.txt | 2 +-
```

(بخشی از خروجی را برای کوتاه شدن حذف کرده‌ام.) فایل‌ها حالا فایل معمولی داخل `app` هستند: clone ساده آن‌ها را دارد و دستور اضافه‌ای نمی‌خواهد. بعد در `app` فایل `vendor/lib/greet.txt` را ویرایش و commit کردم و `split` زدم. این دستور تاریخچه‌ای می‌سازد که فقط تغییرهای زیر `vendor/lib` را دارد، و آن را در branch جدیدی به اسم `lib-only` می‌گذارد:

```bash
git subtree split --prefix=vendor/lib -b lib-only
git log --oneline lib-only
```

```text
861c90e app: tweak greet
e229a82 lib: v2
556dcb6 lib: first
```

commit بالا همان ویرایش من در `app` است و دو commit پایین از خود `lib` آمده‌اند. می‌توانید `lib-only` را به `lib` برگردانید. هزینه‌ی subtree تاریخچه‌ی شلوغ‌تر و دستورهایی است که سخت‌تر یادتان می‌مانند.

## worktree: دو branch همزمان

سومی مشکل دیگری را حل می‌کند: وسط کار روی یک branch، لازم است سراغ branch دیگری بروید. راه معمول stash یا commit موقت است. `git worktree` یک راه سوم می‌دهد: یک پوشه‌ی کاری دوم از همان repository، با branch دیگر، کنار اولی.

```bash
git worktree add -b hotfix ../app-hotfix
git worktree list
git worktree add ../app-again hotfix
```

```text
Preparing worktree (new branch 'hotfix')
HEAD is now at 8de0ccd app: tweak greet
<tmp>/app         8de0ccd [main]
<tmp>/app-hotfix  8de0ccd [hotfix]
fatal: 'hotfix' is already checked out at '<tmp>/app-hotfix'
```

دستور اول branch جدید `hotfix` را می‌سازد و در `../app-hotfix` checkout می‌کند. `worktree list` دو پوشه را با branchشان نشان می‌دهد. دستور سوم می‌خواست همان branch را در پوشه‌ی سومی هم باز کند و Git جلویش را گرفت. هر دو پوشه یک پایگاه object مشترک دارند، پس clone دومی لازم نیست. خطا همان قاعده‌ی ایمنی است: هر branch فقط در یک worktree. با `git worktree remove ../app-hotfix` پاک‌سازی می‌شود. (به‌جای مسیر طولانی temp من، `<tmp>` گذاشته‌ام.)

## کدام را انتخاب کنیم؟

| | submodule | subtree | worktree |
|---|---|---|---|
| چیست | commit پین‌شده از repo دیگر | فایل‌های repo دیگر که کپی شده | checkout اضافه از همان repo |
| قدم اضافه برای همکار | دارد (`--recurse-submodules`) | ندارد | بی‌مورد |
| تاریخچه | جدا | قاطی تاریخچه‌ی شما | همان |
| نظر من | برای چند وابستگی پین‌شده خوب است | وقتی می‌خواهید هیچ تشریفاتی نباشد | برای hotfix و review عالی است |

ردیف آخر نظر شخصی من است، نه اندازه‌گیری.

## دام‌های رایج

- **همیشه با `--recurse-submodules` clone کنید**، یا بعدش `git submodule update --init` بزنید. وگرنه پوشه‌ی خالی می‌گیرید.
- **اول submodule را push کنید، بعد والد را.** وگرنه همکارانتان به commitی اشاره می‌گیرند که روی سرور نیست.
- **داخل submodule روی detached HEAD commit نزنید**، مگر اینکه اول یک branch بسازید.
- **فایل‌های subtree را دستی کپی نکنید**؛ از `subtree pull` استفاده کنید تا تاریخچه قابل merge بماند.
- **`git worktree prune` و worktreeهای قفل‌شده را آزمایش نکردم.**

## تمرین

1. clone با پوشه‌ی خالی را بازتولید کنید و با `git submodule update --init` درستش کنید.
2. داخل یک submodule commit بزنید، pointer را جلو ببرید و از یک clone دوم خطای «not our ref» را ایجاد کنید.
3. برای یک branch از نوع hotfix یک worktree بسازید، آنجا commit بزنید، آن را پاک کنید و branch را merge کنید.

## قدم بعدی

مقاله‌ی بعد «workflowهای تیمی و درون packfile» آخرین مقاله‌ی سری است: تیم‌ها چطور با branch و pull request کار می‌کنند و objectها چطور در packfile ذخیره می‌شوند.
