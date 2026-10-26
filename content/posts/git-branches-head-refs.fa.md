+++
date = '2026-11-01T10:00:00+03:30'
draft = false
title = 'branch، HEAD و ref: فقط اشاره‌گر'
description = 'branch در گیت یک فایل ۴۱ بایتی است: HEAD، tag و remote-tracking branch همه ref هستند. با اجرای واقعی، detached HEAD و بازیابی commit گم‌شده.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "branches", "refs", "head"]
cover = { image = "/images/covers/git-branches-head-refs.fa.png", alt = "branch، HEAD و ref: فقط اشاره‌گر", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/git-index-staging/) مسیر یک تغییر را از working tree به index و بعد مخزن دنبال کردیم. حالا سؤال این است که همه‌ی این {{< term "commit" "commitها" >}} از کجا آویزان‌اند. branch سنگین به نظر می‌رسد چون می‌گوییم «به branch برو» و «branch را کپی کن»، اما در گیت {{< term "git-branch" "branch" >}} فقط یک نام است که به یک commit اشاره می‌کند.

> همه‌ی اجراهای زیر با Git نسخه‌ی 2.39.2 در یک پوشه‌ی موقت انجام شده‌اند. شناسه‌ی commitها مال همان اجراست و روی سیستم شما فرق می‌کند.

## branch یک فایل است

```text
$ git log --oneline
33cf254 second
7d52f5a first
$ cat .git/refs/heads/main
33cf25487ec218f465e614aa03dfb60f2827492f
$ wc -c < .git/refs/heads/main
      41
```

همین است، کل branch: ۴۰ کاراکتر hex به‌علاوه‌ی یک خط جدید. هر commit روی `main` شناسه‌ی تازه‌ای در این فایل می‌نویسد. به نامی که این‌طور به یک object اشاره می‌کند، {{< term "git-ref" "ref" >}} می‌گویند.

## HEAD می‌گوید کجا هستید

```text
$ cat .git/HEAD
ref: refs/heads/main
$ git symbolic-ref HEAD
refs/heads/main
```

{{< term "head" "HEAD" >}} هم یک فایل است. معمولاً نام یک branch در آن نوشته شده (یک symbolic ref)، پس «branch فعلی» یعنی «branchی که HEAD اسمش را برده».

## ساختن branch یعنی نوشتن یک فایل

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

`git branch feature` و دستور سطح‌پایین `git update-ref` نتیجه‌ی یکسان می‌دهند. چیزی کپی نمی‌شود، پس branch رایگان است. `git switch -c work` هم branch می‌سازد و هم HEAD را به آن می‌برد:

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

## Fast-forward

یک commit روی `work` زدم، به `main` برگشتم و merge کردم:

```text
$ git switch main
$ git merge work
Updating 33cf254..b9cdb9f
Fast-forward
 a.txt | 1 +
 1 file changed, 1 insertion(+)
```

در `main` چیزی نبود که `work` نداشته باشد، پس گیت فقط اشاره‌گر `main` را جلو برد. این یک {{< term "fast-forward" "fast-forward" >}} است و merge commit ساخته نشد. مقاله‌ی بعد درباره‌ی وقتی است که هر دو طرف commit تازه دارند.

## Detached HEAD و برگرداندن یک commit

اگر HEAD به‌جای نام branch شناسه‌ی یک commit را داشته باشد، در حالت {{< term "detached-head" "detached HEAD" >}} هستید:

```text
$ git switch -q --detach HEAD~1
$ cat .git/HEAD
33cf25487ec218f465e614aa03dfb60f2827492f
```

اینجا یک commit به اسم «experiment» زدم و به `main` برگشتم. گیت هشدار داد:

```text
$ git switch main
Warning: you are leaving 1 commit behind, not connected to
any of your branches:

  936605f experiment
```

حالا هیچ branchی به آن اشاره نمی‌کند، اما {{< term "reflog" "reflog" >}} یادش هست:

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

یک ref تازه کافی است تا commit دوباره در دسترس باشد. طبق مستندات گیت، commitهای بی‌صاحب بالاخره با garbage collection پاک می‌شوند، پس زود این کار را بکنید.

## tagها هم ref هستند

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

`v1` با `git tag v1` ساخته شد و tag سبک است: یک ref مستقیم به commit. `v2` با `git tag -a v2 -m "release two"` ساخته شد؛ یک {{< term "annotated-tag" "annotated tag" >}} است، یعنی یک {{< term "git-object" "object" >}} جدا که به commit اشاره می‌کند. برخلاف branch، tag با commit زدن جابه‌جا نمی‌شود.

## Remote-tracking branch

کنار دمو یک مخزن bare ساختم (`git init --bare -b main remote.git`)، آن را به‌عنوان `origin` اضافه و push کردم. یک clone دوم هم branchی به اسم `topic` به آن push کرد.

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

`origin/main` یک {{< term "remote-tracking-branch" "remote-tracking branch" >}} است: ref محلی‌ای که نشان می‌دهد remote در آخرین ارتباط ما کجا بود. `git for-each-ref` همه‌ی refها را یکجا فهرست می‌کند: `refs/heads/...`، `refs/tags/...` و `refs/remotes/...`.

## پاک کردن branch

یک branch به اسم `wip` ساختم با یک commit که جای دیگری نیست:

```text
$ git branch -d wip
error: The branch 'wip' is not fully merged.
If you are sure you want to delete it, run 'git branch -D wip'.
$ git branch -D wip
Deleted branch wip (was 75edf86).
```

`-d` قبول نمی‌کند چون پاک کردن اشاره‌گر commit را بی‌صاحب می‌کند. `-D` اجبار می‌کند و شناسه‌ای که چاپ می‌شود راه برگشت شماست (`git branch wip 75edf86`).

## چند نکته‌ی مهم

- پاک کردن branch یعنی پاک کردن اشاره‌گر، نه commit؛ ولی commitهای بی‌صاحب تا ابد نمی‌مانند.
- در detached HEAD بدون دادن نام branch به کار commit نزنید.
- `origin/main` ممکن است کهنه باشد: قبل از قضاوت درباره‌اش `git fetch` بزنید.
- در مخزن واقعی فایل‌های `.git/refs/` را دستی ویرایش نکنید؛ از `git branch` یا `git update-ref` استفاده کنید.

## تمرین

در یک مخزن تازه سه commit بزنید. با `git branch old HEAD~2` روی commit اول branch بسازید و فایلی را که ساخته شده بخوانید. بعد به `old` بروید، `main` را با `git branch -D main` اجباری پاک کنید و فقط با شناسه‌ای که گیت چاپ کرد یا با reflog آن را برگردانید.

## قدم بعدی

مقاله‌ی بعد «merge یا rebase؟ دو تاریخچه‌ی واقعی» است؛ جایی که هر دو branch commit تازه دارند و گیت باید تصمیم بگیرد چطور آن‌ها را به هم وصل کند.
