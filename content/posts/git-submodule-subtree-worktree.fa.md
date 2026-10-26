+++
date = '2026-11-15T10:00:00+03:30'
draft = false
title = 'submodule، subtree و worktree'
description = 'مقایسه‌ی submodule، subtree و worktree در گیت با اجرای واقعی: gitlink، clone ناقص، pointer ناپوش‌شده، subtree split و دو branch همزمان.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "submodule", "subtree", "worktree"]
cover = { image = "/images/covers/git-submodule-subtree-worktree.fa.png", alt = "submodule، subtree و worktree", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/git-hooks-commit-hygiene/) کنترل‌های دور commit را خودکار کردیم. این بار سراغ سمت دیگر کار روزمره با گیت می‌رویم: وقتی repository شما به یک repository دیگر نیاز دارد، و وقتی دو branch را همزمان روی دیسک می‌خواهید. گیت برای این کارها سه ابزار دارد که راحت با هم اشتباه گرفته می‌شوند: **{{< term "submodule" "submodule" >}}**، **{{< term "subtree" "subtree" >}}** و **{{< term "worktree" "worktree" >}}**.

همین بلاگ هم یکی از آن‌ها را استفاده می‌کند. فایل `.gitmodules` این repo فقط یک ورودی دارد، `themes/PaperMod` که به repository پوسته‌ی PaperMod در GitHub اشاره می‌کند، و `git submodule status` این را چاپ می‌کند: `7d061d5... themes/PaperMod (v8.0-54-g7d061d5)`. یعنی یک commit پین‌شده از کد دیگران.

> همه‌ی دستورها با Git نسخه‌ی 2.39.2 در repositoryهای موقت اجرا شده‌اند و remoteها مسیر محلی بوده‌اند. hashها در هر اجرا فرق می‌کنند، پس مال شما یکی نخواهد بود. برای دمو `protocol.file.allow=always` را در محیط گذاشتم، چون گیت به‌صورت پیش‌فرض submodule با مسیر محلی را مسدود می‌کند. این فقط برای دموی محلی لازم است.

## submodule فقط یک pointer است

آماده‌سازی: یک repo به نام `lib` و یکی به نام `app`. سپس:

```bash
cd app
git submodule add ../lib lib
git commit -m "add lib submodule"
git ls-tree HEAD
```

```text
100644 blob 008e8edaf3165b09395d7d5fe13cb3e657072b74	.gitmodules
100644 blob b80f0bd60822d4fa4893de455958ef32f6c521bf	README
160000 commit 390b441e850cdffb00b1fed3b0abb7551293e794	lib
```

ورودی `lib` یک **{{< term "gitlink" "gitlink" >}}** است: mode برابر `160000` و یک id برای commit، نه tree. `app` هیچ فایلی از `lib` ندارد، فقط می‌گوید «commit شماره‌ی 390b441 را بگیر». نشانی هم در `.gitmodules` است.

## فراموش کردن --recurse-submodules

```bash
git clone app app-plain
ls -A app-plain/lib | wc -l      # 0
git -C app-plain submodule status
```

```text
       0
-390b441e850cdffb00b1fed3b0abb7551293e794 lib
```

پوشه هست ولی خالی است، و علامت `-` یعنی «مقداردهی اولیه نشده». با `git submodule update --init` درستش می‌کنید، یا از همان اول با `git clone --recurse-submodules` clone کنید. داخل submodule در حالت **{{< term "detached-head" "detached HEAD" >}}** هستید:

```text
HEAD detached at 390b441
```

این عمدی است: والد یک commit را پین می‌کند، نه یک branch را. اگر آنجا commit بزنید و بعد branch را عوض کنید، commit جدید هیچ branchی ندارد که به آن اشاره کند.

## جابه‌جا کردن pointer

وقتی `lib` یک commit جدید می‌گیرد، والد خودش متوجه نمی‌شود:

```bash
git submodule update --remote    # lib را fetch و آخرین main را checkout می‌کند
git status --short               #  M lib
git commit -am "bump lib to v2"
```

تغییر در `app` فقط یک خط است: gitlink حالا به commit دیگری اشاره می‌کند.

## اشتباه کلاسیک: pointer به commitی که هیچ‌کس نمی‌تواند بگیرد

داخل `app/lib` یک commit زدم، pointer جدید را در `app` commit کردم، ولی `lib` را push نکردم. بعد یک همکار pull کرد:

```text
Fetching submodule lib
fatal: git upload-pack: not our ref fcc7862444cb18d7efe83c7f6a4628e8208d70a1
fatal: remote error: upload-pack: not our ref fcc7862444cb18d7efe83c7f6a4628e8208d70a1
Errors during submodule fetch:
	lib
pull exit=1
```

commit والد معتبر است ولی به commitی اشاره می‌کند که فقط روی دیسک من وجود دارد. قاعده: اول submodule را push کنید، بعد والد را. بعد از اینکه `lib` را push کردم، همان pull و `git submodule update` درست کار کردند.

## subtree: فقط فایل

`git subtree` روی این نصب گیت وجود دارد (بررسی کردم `git-subtree` در exec path هست؛ این دستور بخش contrib است و ممکن است در بعضی buildها نباشد):

```bash
git subtree add --prefix=vendor/lib ../lib main --squash
git subtree pull --prefix=vendor/lib ../lib main --squash -m "pull lib"
git subtree split --prefix=vendor/lib -b lib-only
git log --oneline lib-only
```

```text
Added dir 'vendor/lib'
 vendor/lib/greet.txt | 2 +-
861c90e app: tweak greet
e229a82 lib: v2
556dcb6 lib: first
```

فایل‌ها حالا فایل معمولی داخل `app` هستند: clone ساده آن‌ها را دارد و دستور اضافه‌ای نمی‌خواهد. `split` تاریخچه‌ای ساخت که فقط تغییرهای زیر `vendor/lib` را دارد و می‌توانید آن را به `lib` برگردانید. هزینه‌اش تاریخچه‌ی شلوغ‌تر و دستورهایی است که سخت‌تر یادتان می‌مانند.

## worktree: دو branch همزمان

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

هر دو پوشه یک پایگاه object مشترک دارند، پس clone دومی لازم نیست. خطا همان قاعده‌ی ایمنی است: یک branch، یک worktree. با `git worktree remove ../app-hotfix` پاک‌سازی می‌شود. (به‌جای مسیر طولانی temp من، `<tmp>` گذاشته‌ام.)

## کدام را انتخاب کنیم؟

| | submodule | subtree | worktree |
|---|---|---|---|
| چیست | commit پین‌شده از repo دیگر | فایل‌های repo دیگر که کپی شده | checkout اضافه از همان repo |
| قدم اضافه برای همکار | دارد (`--recurse-submodules`) | ندارد | بی‌مورد |
| تاریخچه | جدا | قاطی تاریخچه‌ی شما | همان |
| نظر من | برای چند وابستگی پین‌شده خوب است | وقتی می‌خواهید هیچ تشریفاتی نباشد | برای hotfix و review عالی است |

ردیف آخر نظر شخصی من است، نه اندازه‌گیری.

## چند نکته‌ی مهم

- همیشه با `--recurse-submodules` clone کنید، یا بعدش `git submodule update --init` بزنید.
- اول submodule را push کنید، بعد والد را.
- داخل submodule روی detached HEAD commit نزنید، مگر اینکه اول یک branch بسازید.
- فایل‌های subtree را دستی کپی نکنید؛ از `subtree pull` استفاده کنید تا تاریخچه قابل merge بماند.
- `git worktree prune` و worktreeهای قفل‌شده را آزمایش نکردم.

## تمرین

1. clone با پوشه‌ی خالی را بازتولید کنید و با `git submodule update --init` درستش کنید.
2. داخل یک submodule commit بزنید، pointer را جلو ببرید و از یک clone دوم خطای «not our ref» را ایجاد کنید.
3. برای یک branch از نوع hotfix یک worktree بسازید، آنجا commit بزنید، آن را پاک کنید و branch را merge کنید.

## قدم بعدی

در مقاله‌ی بعد، «workflowهای تیمی و درون packfile»، می‌بینیم تیم‌ها در عمل چطور با branch و pull request کار می‌کنند و گیت objectها را چطور در packfile ذخیره می‌کند.
