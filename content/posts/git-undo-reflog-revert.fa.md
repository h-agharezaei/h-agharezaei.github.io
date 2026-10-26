+++
date = '2026-11-07T10:00:00+03:30'
draft = false
title = 'برگرداندن کار: reflog، revert و cherry-pick'
description = 'برگرداندن کار در Git با reflog، reset، revert و cherry-pick: اثر هر دستور، نجات از hard reset و چیزهایی که Git نمی‌تواند برگرداند.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "reflog", "revert", "cherry-pick"]
cover = { image = "/images/covers/git-undo-reflog-revert.fa.png", alt = "برگرداندن کار: reflog، revert و cherry-pick", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/git-resolve-conflicts/) conflictها را حل کردیم. حالا سؤالی که هر برنامه‌نویسی دیر یا زود می‌پرسد: «یک دستور زدم و کارم پرید. برمی‌گردد؟» بیشتر وقت‌ها بله، چون Git تقریباً هیچ چیز را بلافاصله پاک نمی‌کند. فقط باید بدانید سراغ کدام ابزار بروید.

> همه‌ی دستورهای زیر با Git نسخه‌ی 2.39.2 در یک repository آزمایشی اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند.

## reset در سه سطح

**{{< term "git-reset" "git reset" >}}** branch فعلی را به یک commit دیگر می‌برد. اثرش روی **{{< term "staging-area" "index" >}}** و working tree به mode بستگی دارد. یک commit به اسم `add line 4` ساختم و هر بار `git reset --<mode> HEAD~1` زدم:

| Mode | حرکت branch | Index | Working tree | `git status -s` بعد از آن |
|---|---|---|---|---|
| `--soft` | بله | حفظ | حفظ | `M  notes.txt` (staged) |
| `--mixed` (پیش‌فرض) | بله | ریست | حفظ | ` M notes.txt` (unstaged) |
| `--hard` | بله | ریست | ریست | تمیز؛ `line 4` از فایل رفته |

یعنی `--soft` می‌گوید «commit را برگردان ولی همه‌چیز آماده‌ی commit دوباره بماند». فقط `--hard` محتوای فایل‌ها را دور می‌ریزد.

## «وای نه» و **{{< term "reflog" "reflog" >}}**

```bash
git reset --hard HEAD~2
```

```text
HEAD is now at 2ff9b35 add line 3
```

دو commit از `git log` ناپدید شدند. اما Git یک دفترچه‌ی محلی از جاهایی که `HEAD` رفته نگه می‌دارد:

```bash
git reflog | head -3
```

```text
2ff9b35 HEAD@{0}: reset: moving to HEAD~2
aeaffd1 HEAD@{1}: commit: add line 5
486542d HEAD@{2}: commit: add line 4
```

`HEAD@{1}` یعنی جایی که یک حرکت قبل بودیم. برگردید:

```bash
git reset --hard 'HEAD@{1}'
```

```text
HEAD is now at aeaffd1 add line 5
```

هر دو commit برگشتند. reflog فقط روی همین clone شماست و push نمی‌شود.

## amend: اصلاح آخرین commit

`add line 6 tpyo` را commit کردم و با `git commit --amend -m "add line 6"` درستش کردم. reflog نشان می‌دهد واقعاً چه شد: یک commit جدید جای قبلی آمد و قبلی هنوز مدتی در دسترس است.

```text
57b3951 HEAD@{0}: commit (amend): add line 6
c2eab17 HEAD@{1}: commit: add line 6 tpyo
```

amend تاریخچه را بازنویسی می‌کند، پس فقط برای commitهایی که push نکرده‌اید.

## **{{< term "git-revert" "revert" >}}**: برگرداندن امن روی branchهای مشترک

`git revert` چیزی را بازنویسی نمی‌کند. یک commit جدید می‌سازد که patch معکوس را اعمال می‌کند:

```text
6c01175 Revert "add b.txt (bug)"
7a8401b add c.txt
8d3aa62 add b.txt (bug)
84c3288 add a.txt
```

`b.txt` رفت، `c.txt` ماند و تاریخچه دست‌نخورده است. روی branchی که دیگران pull کرده‌اند همین را می‌خواهید.

برای revert کردن یک **{{< term "merge-commit" "merge commit" >}}** یک اشاره‌ی بیشتر لازم است، چون Git باید بداند کدام parent خط اصلی است:

```text
$ git revert --no-edit HEAD
error: commit 70591d9... is a merge but no -m option was given.
fatal: revert failed
$ git revert --no-edit -m 1 HEAD
[main 066c38f] Revert "Merge feature"
 1 file changed, 1 deletion(-)
 delete mode 100644 f.txt
```

`-m 1` یعنی «parent اول را نگه دار»، یعنی branchی که داخلش merge کرده بودید.

## **{{< term "cherry-pick" "cherry-pick" >}}**: برداشتن یک commit

روی branch به اسم `hotfix` یک commit ساختم و آن را روی `main` کپی کردم:

```bash
git cherry-pick -x 1e6057c
```

کپی hash جدید دارد (`68d45b5`) چون parent آن فرق می‌کند، ولی patch همان است. `git patch-id` این را ثابت می‌کند:

```text
3c5eb97fe2e9bbe1df3424ee1a5dcc36a36c7145 1e6057c...   (original)
3c5eb97fe2e9bbe1df3424ee1a5dcc36a36c7145 68d45b5...   (copy)
```

`-x` عبارت `(cherry picked from commit 1e6057c...)` را به پیام اضافه می‌کند؛ بعداً که بپرسند این commit از کجا آمده به کار می‌آید.

## reflog چه چیزی را نجات نمی‌دهد

یک خط به `a.txt` اضافه کردم، stage نکردم و `git restore a.txt` زدم:

```text
 M a.txt          (before)
                  (after: clean, the line is gone)
```

reflog هیچ ردی از آن تغییر ندارد، چون هیچ‌وقت commit نشده بود. Git فقط چیزی را به یاد دارد که ذخیره کرده باشد. فایل‌های untracked و تغییرات commit‌نشده محافظت نمی‌شوند؛ پیش از دستورهای خطرناک commit یا `git stash` کنید.

## commitهای dangling و fsck

branch را با `git branch -D tmp` پاک کردم و reflog را expire کردم. commit تا garbage collection هنوز وجود دارد:

```bash
git fsck --lost-found
```

```text
dangling commit 0b1fb07a5e6289f46c88e2cd5ceaf064d9e01737
```

با `git branch rescue 0b1fb07` برگشت. طبق مستندات، ورودی‌های reflog اگر reachable باشند بعد از ۹۰ روز و اگر نباشند بعد از ۳۰ روز منقضی می‌شوند (`gc.reflogExpire` و `gc.reflogExpireUnreachable`) و `git gc` بعد از آن می‌تواند objectها را پاک کند. این را خودم امتحان نکردم.

## چند نکته‌ی مهم

- پیش از `reset --hard` حتماً `git status` بزنید. کار commit‌نشده قابل بازیابی نیست.
- commitهایی را که push کرده‌اید amend یا reset نکنید؛ آنجا از `revert` استفاده کنید.
- وقتی هول شدید اول `git reflog` را بزنید و چیزی را تغییر ندهید.
- برای revert کردن merge commit همیشه `-m 1` (یا شماره‌ی درست parent) بدهید؛ بدون آن Git قبول نمی‌کند.
- reflog مخصوص هر clone است. clone تازه آن را ندارد.

## تمرین

در یک repo موقت سه commit بسازید، `git reset --hard HEAD~2` بزنید و با reflog برش گردانید. بعد commit وسطی را revert کنید و یک commit از branch دیگر را با `-x` cherry-pick کنید.

## قدم بعدی

مقاله‌ی بعدی «پیدا کردن باگ با git bisect» است.
