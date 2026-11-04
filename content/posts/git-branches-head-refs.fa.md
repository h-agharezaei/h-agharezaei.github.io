+++
date = '2026-11-01T10:00:00+03:30'
draft = false
title = 'branch، HEAD و ref: فقط اشاره‌گر'
description = 'branch در گیت یک فایل ۴۱ بایتی است: HEAD، tag و remote-tracking branch همه ref هستند. با اجرای واقعی، detached HEAD و بازیابی commit گم‌شده.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "branches", "refs", "head"]
cover = { image = "/images/covers/git-branches-head-refs.fa.png", alt = "branch، HEAD و ref: فقط اشاره‌گر", hiddenInSingle = true }
+++

فایل `.git/refs/heads/main` را باز کنید. کل چیزی که می‌بینید ۴۰ کاراکتر hex است و یک خط جدید. همین است؛ این کل branch است.

branch سنگین به نظر می‌رسد، چون ما می‌گوییم «به branch برو»، «branch را کپی کن»، «branch را merge کن»، و آدم تصور می‌کند هر branch نسخه‌ی جدایی از پروژه است. اما در گیت {{< term "git-branch" "branch" >}} فقط یک نام است که به یک {{< term "commit" "commit" >}} اشاره می‌کند. برای همین ساختنش هزینه‌ای ندارد و branchی که پاک شده را معمولاً می‌شود برگرداند. [مقاله‌ی قبل](/fa/posts/git-index-staging/) مسیر یک تغییر را از working tree و index تا commit دنبال کرد؛ این مقاله می‌پرسد خود commitها به چه چیزی آویزان‌اند و گیت از کجا می‌داند الان کجا ایستاده‌اید.

> همه‌ی اجراهای زیر با Git نسخه‌ی 2.39.2 در یک پوشه‌ی موقت انجام شده‌اند. شناسه‌ی commitها مال همان اجراست و روی سیستم شما فرق می‌کند.

## branch یک فایل است

برای شروع یک repository با دو commit دارم. اول فهرست commitها، بعد محتوای فایل branch، و بعد تعداد بایت‌های آن فایل:

```text
$ git log --oneline
33cf254 second
7d52f5a first
$ cat .git/refs/heads/main
33cf25487ec218f465e614aa03dfb60f2827492f
$ wc -c < .git/refs/heads/main
      41
```

محتوای فایل `main` همان هش کامل آخرین commit است (`33cf254…` که در `git log` کوتاه‌شده‌اش را می‌بینیم). ۴۱ بایت هم یعنی ۴۰ کاراکتر hex به‌علاوه‌ی یک خط جدید. این کل branch است. هر بار که روی `main` commit می‌زنید، گیت فقط شناسه‌ی تازه‌ای در این فایل می‌نویسد.

به نامی که این‌طور به یک object اشاره می‌کند، {{< term "git-ref" "ref" >}} (کوتاه‌شده‌ی reference، یعنی ارجاع) می‌گویند. branchها در `refs/heads/` هستند و بعداً می‌بینیم tagها و چیزهای دیگر هم ref‌اند.

## HEAD می‌گوید کجا هستید

اگر branch فقط یک نام است، گیت از کجا می‌داند الان روی کدام نام کار می‌کنید و commit بعدی را به کجا اضافه کند؟ جوابش یک فایل دیگر است:

```text
$ cat .git/HEAD
ref: refs/heads/main
$ git symbolic-ref HEAD
refs/heads/main
```

{{< term "head" "HEAD" >}} هم یک فایل است. معمولاً به‌جای شناسه‌ی commit، نام یک branch در آن نوشته شده (به این **symbolic ref** می‌گویند، یعنی ref‌ای که به یک ref دیگر اشاره می‌کند). پس «branch فعلی» یعنی «branchی که HEAD اسمش را برده». وقتی commit می‌زنید، گیت از HEAD می‌خواند که به کدام branch اشاره می‌کند و شناسه‌ی commit تازه را در همان فایل می‌نویسد. دستور `git symbolic-ref HEAD` همین را بدون باز کردن فایل نشان می‌دهد.

## ساختن branch یعنی نوشتن یک فایل

حالا که می‌دانیم branch چیست، ساختن آن باید خیلی ساده باشد. دو راه را امتحان کردم: دستور معمولی `git branch feature` و دستور سطح‌پایین `git update-ref` که مستقیم یک ref می‌نویسد.

```text
$ git branch feature
$ cat .git/refs/heads/feature
33cf25487ec218f465e614aa03dfb60f2827492f
$ git update-ref refs/heads/other HEAD
$ git branch
  feature
* main
  other
```

فایل `feature` همان هش `main` را دارد، و `git branch` هر دو را کنار `main` فهرست می‌کند (ستاره‌ی کنار `main` یعنی HEAD الان به آن اشاره می‌کند). هر دو دستور نتیجه‌ی یکسان می‌دهند. چیزی کپی نمی‌شود، نه فایلی و نه تاریخچه‌ای، فقط ۴۱ بایت نوشته می‌شود. برای همین branch رایگان است.

`git switch -c work` هم branch می‌سازد و هم HEAD را به آن می‌برد. بعد از آن یک commit روی `work` زدم و `git branch -vv` (حالت پرجزئیات) را گرفتم:

```text
$ git switch -c work
Switched to a new branch 'work'
$ cat .git/HEAD
ref: refs/heads/work
$ git branch -vv
  feature 33cf254 second
  main    33cf254 second
  other   33cf254 second
* work    b9cdb9f third on work
```

فایل HEAD حالا `refs/heads/work` است. سه branch هنوز به `second` اشاره می‌کنند و فقط `work` یک commit جلوتر رفته: چون commit جدید در فایل `work` نوشته شد و فایل بقیه دست نخورد.

## Fast-forward

خب، commit جدید در `work` است و `main` عقب مانده. برای همین به `main` برگشتم و `work` را در آن merge کردم:

```text
$ git switch main
Switched to branch 'main'
$ git merge work
Updating 33cf254..b9cdb9f
Fast-forward
 a.txt | 1 +
 1 file changed, 1 insertion(+)
```

خط `Updating 33cf254..b9cdb9f` می‌گوید `main` از `33cf254` به `b9cdb9f` می‌رود. چون در `main` چیزی نبود که `work` نداشته باشد، گیت لازم نداشت دو تاریخچه را به هم گره بزند؛ فقط اشاره‌گر `main` را جلو برد. این یک {{< term "fast-forward" "fast-forward" >}} است (جلو بردن سریع)، و هیچ merge commitی ساخته نشد. اگر `git log --oneline --graph --all` را بزنیم، یک خط راست می‌بینیم: `third on work`، `second`، `first`. مقاله‌ی بعد درباره‌ی وقتی است که هر دو طرف commit تازه دارند و fast-forward ممکن نیست.

## Detached HEAD و برگرداندن یک commit

گفتیم معمولاً HEAD نام یک branch را دارد. اگر به‌جای آن مستقیم شناسه‌ی یک commit را داشته باشد، در حالت {{< term "detached-head" "detached HEAD" >}} هستید (HEAD از هر branch جدا شده):

```text
$ git switch -q --detach HEAD~1
$ cat .git/HEAD
33cf25487ec218f465e614aa03dfb60f2827492f
```

`HEAD~1` یعنی یک commit قبل از HEAD. حالا فایل HEAD دیگر `ref: …` ندارد و یک هش خالی است. کاری که اینجا انجام دهید به هیچ branchی اضافه نمی‌شود. برای امتحانش یک commit به اسم «experiment» زدم و بعد به `main` برگشتم. گیت هشدار داد:

```text
$ git switch main
Warning: you are leaving 1 commit behind, not connected to
any of your branches:

  936605f experiment

If you want to keep it by creating a new branch, this may be a good time
to do so with:

 git branch <new-branch-name> 936605f

Switched to branch 'main'
```

گیت می‌گوید یک commit را پشت سر می‌گذاری که هیچ branchی به آن وصل نیست، و حتی دستور نگه‌داشتنش را هم می‌دهد. اگر هشدار را نخوانده بودیم، commit از دید ما گم شده بود. اما {{< term "reflog" "reflog" >}} (دفترچه‌ای که گیت از جابه‌جایی‌های HEAD نگه می‌دارد) یادش هست:

```text
$ git reflog -3
b9cdb9f HEAD@{0}: checkout: moving from 936605f9f7b2665e474a43782d150fd05721086d to main
936605f HEAD@{1}: commit: experiment
33cf254 HEAD@{2}: checkout: moving from main to HEAD~1
$ git branch rescue HEAD@{1}
$ git log --oneline -2 rescue
936605f experiment
33cf254 second
```

خط‌ها از جدید به قدیم‌اند. `HEAD@{2}` وقتی است که به `HEAD~1` رفتیم، `HEAD@{1}` همان commit «experiment» است و `HEAD@{0}` برگشتن به `main`. با `git branch rescue HEAD@{1}` یک ref تازه به آن commit دادیم و حالا `rescue` آن را نگه داشته است؛ `git log` هم نشان می‌دهد commit سر جایش است.

یک ref تازه کافی است تا commit دوباره در دسترس باشد. ولی طبق مستندات گیت، commitهایی که هیچ refی به آن‌ها نمی‌رسد بالاخره با garbage collection پاک می‌شوند، پس این کار را زود بکنید.

## tagها هم ref هستند

tag هم مثل branch یک نام برای یک object است. دو tag ساختم، یکی با `git tag v1` و یکی با `git tag -a v2 -m "release two"`:

```text
$ cat .git/refs/tags/v1
b9cdb9f4f45a9b29b0212c54f49b83a17ec79149
$ cat .git/refs/tags/v2
676128add498eaa876a334d3006c831472d72d40
$ git cat-file -t v1
commit
$ git cat-file -t v2
tag
$ git rev-parse v2^{commit}
b9cdb9f4f45a9b29b0212c54f49b83a17ec79149
```

فایل `v1` مستقیم هش یک commit را دارد (`b9cdb9f…`) و `git cat-file -t` نوعش را `commit` می‌گوید. این یک tag سبک است: فقط یک ref به commit، درست مثل branch. فایل `v2` هش دیگری دارد و نوع آن `tag` است. این یک {{< term "annotated-tag" "annotated tag" >}} است: یک {{< term "git-object" "object" >}} جدا که خودش به commit اشاره می‌کند و (به‌جز اشاره‌گر) پیام و اطلاعات سازنده را هم نگه می‌دارد. دستور آخر، `v2^{commit}`، از روی tag به commit می‌رسد و همان `b9cdb9f…` را می‌دهد.

تفاوت اصلی با branch: tag با commit زدن جابه‌جا نمی‌شود. branch با هر commit جلو می‌رود، ولی tag همان‌جا که گذاشتید می‌ماند.

## Remote-tracking branch

تا اینجا همه‌چیز محلی بود. وقتی با یک remote کار می‌کنید چه refهایی داریم؟ کنار دمو یک مخزن bare (بدون working tree) ساختم، آن را به‌عنوان `origin` اضافه کردم و `main` را push کردم. یک clone دوم هم branchی به اسم `topic` به آن push کرد. اینجا remote یک پوشه روی همین دیسک بود و هیچ شبکه‌ای در کار نبود.

```text
$ git push -u origin main
To ../remote.git
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main'.
$ git fetch
From ../remote
 * [new branch]      topic      -> origin/topic
$ git branch -r
  origin/main
  origin/topic
$ cat .git/refs/remotes/origin/main
b9cdb9f4f45a9b29b0212c54f49b83a17ec79149
```

بعد از push، `origin/main` وجود دارد؛ بعد از `git fetch` (دانلود refهای تازه‌ی remote) `origin/topic` هم پیدا شد. `git branch -r` این‌ها را فهرست می‌کند و فایل `origin/main` در `.git/refs/remotes/` هم یک هش معمولی است.

`origin/main` یک {{< term "remote-tracking-branch" "remote-tracking branch" >}} است: ref محلی‌ای که نشان می‌دهد `main` روی remote در آخرین ارتباط ما کجا بود. خودش را فقط `fetch` و `push` جابه‌جا می‌کنند، نه commit زدن شما. `git for-each-ref` همه‌ی refها را یک‌جا فهرست می‌کند:

```text
$ git for-each-ref --format='%(refname)  %(objectname:short)'
refs/heads/feature  33cf254
refs/heads/main  b9cdb9f
refs/heads/other  33cf254
refs/heads/rescue  936605f
refs/heads/work  b9cdb9f
refs/remotes/origin/main  b9cdb9f
refs/tags/v1  b9cdb9f
refs/tags/v2  676128a
```

(این فهرست قبل از `git fetch` گرفته شده، برای همین `origin/topic` در آن نیست.) همه‌شان همان یک چیزند: یک نام و یک هش. فقط پوشه‌شان فرق می‌کند: `heads` برای branchهای محلی، `tags` برای tagها و `remotes` برای remote-tracking branchها.

## پاک کردن branch

آخر اینکه پاک کردن branch چه می‌کند؟ یک branch به اسم `wip` ساختم با یک commit که جای دیگری نیست و بعد به `main` برگشتم:

```text
$ git branch -d wip
error: The branch 'wip' is not fully merged.
If you are sure you want to delete it, run 'git branch -D wip'.
$ git branch -D wip
Deleted branch wip (was 75edf86).
```

`-d` قبول نمی‌کند، چون پاک کردن این اشاره‌گر commit را بی‌صاحب می‌کند و گیت می‌بیند آن commit هنوز در branch فعلی merge نشده. `-D` اجبار می‌کند. شناسه‌ای که چاپ می‌شود (`75edf86`) راه برگشت شماست: با `git branch wip 75edf86` اشاره‌گر دوباره ساخته می‌شود. (این شناسه هم مال همان اجراست.)

## دام‌های اشاره‌گرها

- **پاک کردن branch یعنی پاک کردن اشاره‌گر، نه commit.** ولی commitهای بی‌صاحب تا ابد نمی‌مانند و بالاخره garbage collection پاکشان می‌کند.
- **در detached HEAD بدون دادن نام branch به کار commit نزنید.** با رفتن به جای دیگر، commitهایتان بی‌صاحب می‌شوند، و فقط reflog یادشان می‌ماند.
- **`origin/main` ممکن است کهنه باشد.** این یک ref محلی است که فقط با `fetch` به‌روز می‌شود؛ قبل از قضاوت درباره‌اش `git fetch` بزنید.
- **فایل‌های `.git/refs/` را در مخزن واقعی دستی ویرایش نکنید.** ما برای فهمیدن خواندیمشان؛ برای تغییر از `git branch` یا `git update-ref` استفاده کنید.

## تمرین

در یک مخزن تازه سه commit بزنید. با `git branch old HEAD~2` روی commit اول branch بسازید و فایلی را که ساخته شده بخوانید. بعد به `old` بروید، `main` را با `git branch -D main` اجباری پاک کنید و فقط با شناسه‌ای که گیت چاپ کرد، یا با reflog، آن را برگردانید.

## قدم بعدی

مقاله‌ی بعد «merge یا rebase؟ دو تاریخچه‌ی واقعی» است. اینجا فقط یک fast-forward دیدیم؛ آنجا هر دو branch commit تازه دارند و گیت باید تصمیم بگیرد چطور آن‌ها را به هم وصل کند.
