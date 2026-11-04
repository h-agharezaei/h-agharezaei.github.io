+++
date = '2026-11-07T10:00:00+03:30'
draft = false
title = 'برگرداندن کار: reflog، revert و cherry-pick'
description = 'برگرداندن کار در Git با reflog، reset، revert و cherry-pick: اثر هر دستور، نجات از hard reset و چیزهایی که Git نمی‌تواند برگرداند.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "reflog", "revert", "cherry-pick"]
cover = { image = "/images/covers/git-undo-reflog-revert.fa.png", alt = "برگرداندن کار: reflog، revert و cherry-pick", hiddenInSingle = true }
+++

فرض کنید دیروقت است، خسته‌اید و `git reset --hard HEAD~2` را می‌زنید. دو commit از `git log` ناپدید می‌شوند. این لحظه‌ای است که هر برنامه‌نویسی دیر یا زود به آن می‌رسد: «یک دستور زدم و کارم پرید. برمی‌گردد؟»

خبر خوب این است که بیشتر وقت‌ها برمی‌گردد. دلیلش این است که Git تقریباً هیچ چیز را بلافاصله پاک نمی‌کند. استثنا کاری است که هرگز commit نشده؛ درباره‌ی آن آخر مقاله حرف می‌زنیم. بقیه‌اش فقط به این بستگی دارد که بدانید سراغ کدام ابزار بروید، چه خرابی از یک reset آمده باشد و چه از [حل یک conflict](/fa/posts/git-resolve-conflicts/) که درست پیش نرفته. در این مقاله چهار ابزار را می‌بینیم: `reset` برای جابه‌جا کردن branch، reflog برای پیدا کردن جایی که قبلاً بوده‌ایم، `revert` برای برگرداندن امن یک تغییر و `cherry-pick` برای برداشتن یک commit از جای دیگر.

> همه‌ی دستورهای زیر با Git نسخه‌ی 2.39.2 در یک repository آزمایشی اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند. شناسه‌ی commitها مال همان اجراست و روی سیستم شما فرق می‌کند.

## reset در سه سطح

اول ببینیم `reset` دقیقاً چه می‌کند. **{{< term "git-reset" "git reset" >}}** branch فعلی را به یک commit دیگر می‌برد؛ مثلاً دو commit عقب‌تر. اما یک سؤال می‌ماند: فایل‌های شما و {{< term "staging-area" "index" >}} (همان «صف commit بعدی» که در [مقاله‌ی index](/fa/posts/git-index-staging/) دیدیم) با آن حرکت چه می‌شوند؟ جوابش به گزینه‌ای بستگی دارد که می‌دهید.

برای دیدنش یک commit به اسم `add line 4` ساختم که یک خط به `notes.txt` اضافه می‌کند. بعد سه بار، هر بار با یک گزینه، `git reset --<mode> HEAD~1` زدم (و بین آن‌ها وضعیت را به حالت اول برگرداندم). این جدول نتیجه است:

| گزینه | branch حرکت می‌کند | Index | Working tree | `git status -s` بعد از آن |
|---|---|---|---|---|
| `--soft` | بله | حفظ | حفظ | `M  notes.txt` (staged) |
| `--mixed` (پیش‌فرض) | بله | ریست | حفظ | ` M notes.txt` (unstaged) |
| `--hard` | بله | ریست | ریست | تمیز؛ `line 4` از فایل رفته |

(ستون «ریست» یعنی به حالت commit جدید برگردانده می‌شود. ستون `git status -s` دو حرف اول هر خط دارد: حرف اول وضعیت index و حرف دوم وضعیت working tree است.)

خلاصه‌اش این است:

- `--soft` می‌گوید «commit را برگردان، ولی همه‌چیز آماده‌ی commit دوباره بماند». تغییر هنوز staged است.
- `--mixed` که پیش‌فرض است، commit را برمی‌گرداند و تغییر را در فایل نگه می‌دارد، ولی دیگر staged نیست.
- `--hard` فقط branch را جابه‌جا نمی‌کند؛ فایل‌ها را هم به آن commit برمی‌گرداند. فقط همین یکی محتوای فایل‌ها را دور می‌ریزد و برای همین خطرناک است.

## «وای نه» و {{< term "reflog" "reflog" >}}

حالا همان لحظه‌ی ترسناک. در این repository تا commit `add line 5` پیش رفته بودم و این را زدم:

```bash
git reset --hard HEAD~2
```

```text
HEAD is now at 2ff9b35 add line 3
```

دو commit از `git log` ناپدید شدند. اما Git یک دفترچه‌ی محلی دارد که هر جایی را که `HEAD` رفته است، یکی‌یکی می‌نویسد. اسمش reflog است. هر بار commit بزنید، branch عوض کنید یا reset کنید، یک خط به آن اضافه می‌شود:

```bash
git reflog | head -3
```

```text
2ff9b35 HEAD@{0}: reset: moving to HEAD~2
aeaffd1 HEAD@{1}: commit: add line 5
486542d HEAD@{2}: commit: add line 4
```

از بالا به پایین بخوانید؛ بالاترین خط تازه‌ترین است. خط اول همین reset است. خط دوم می‌گوید یک حرکت پیش از آن، `HEAD` روی commit `aeaffd1` یعنی `add line 5` بود. نوشته‌ی `HEAD@{1}` هم یعنی دقیقاً همین: «جایی که یک حرکت قبل بودیم». پس برای برگشتن کافی است دوباره به آنجا reset کنیم:

```bash
git reset --hard 'HEAD@{1}'
```

```text
HEAD is now at aeaffd1 add line 5
```

(علامت‌های `{}` را داخل quote گذاشتم تا shell با آن‌ها کاری نکند.) هر دو commit برگشتند. دلیلش این است که reset فقط اشاره‌گر branch را جابه‌جا کرده بود؛ خود commitها هنوز در پایگاه‌داده‌ی Git بودند و فقط کسی به آن‌ها اشاره نمی‌کرد. reflog همان اشاره‌گر را به شما پس می‌دهد. یادتان باشد reflog فقط روی همین clone شماست و push نمی‌شود.

## amend: اصلاح آخرین commit

یک مورد روزمره‌تر: commit زده‌اید و بعد می‌بینید پیامش غلط املایی دارد. `git commit --amend` آخرین commit را اصلاح می‌کند. من `add line 6 tpyo` را commit کردم و با `git commit --amend -m "add line 6"` درستش کردم. reflog نشان می‌دهد در واقع چه شد:

```text
57b3951 HEAD@{0}: commit (amend): add line 6
c2eab17 HEAD@{1}: commit: add line 6 tpyo
```

amend commit قبلی را ویرایش نمی‌کند. یک commit تازه (`57b3951`) می‌سازد و branch را به آن می‌برد؛ commit قبلی (`c2eab17`) هنوز مدتی از طریق reflog در دسترس است. چون تاریخچه عوض شده، amend را فقط برای commitهایی به کار ببرید که هنوز push نکرده‌اید.

## {{< term "git-revert" "revert" >}}: برگرداندن امن روی branchهای مشترک

حالا فرض کنید commit بد قبلاً push شده و همکارانتان آن را pull کرده‌اند. اینجا reset درست نیست، چون تاریخچه‌ای را عوض می‌کند که دیگران رویش کار می‌کنند. راه درست `git revert` است. این دستور چیزی را بازنویسی نمی‌کند؛ یک commit جدید می‌سازد که تغییرِ معکوسِ commit بد را اعمال می‌کند.

در یک repository آزمایشی سه commit ساختم: `add a.txt`، بعد `add b.txt (bug)`، بعد `add c.txt`. سپس commit دوم را revert کردم. نتیجه در `git log --oneline`:

```text
6c01175 Revert "add b.txt (bug)"
7a8401b add c.txt
8d3aa62 add b.txt (bug)
84c3288 add a.txt
```

بالاترین commit همان revert است. `b.txt` از پوشه رفت، `c.txt` که بعدتر آمده بود ماند و هیچ commit قدیمی‌ای دست نخورد. روی branchی که دیگران pull کرده‌اند دقیقاً همین را می‌خواهید.

revert کردن یک {{< term "merge-commit" "merge commit" >}} یک اشاره‌ی بیشتر لازم دارد. merge commit دو parent دارد (دو commit پیش از خودش)، و Git نمی‌داند «برگرداندن» نسبت به کدام‌یک حساب شود. باید بگویید خط اصلی کدام است:

```text
$ git revert --no-edit HEAD
error: commit 70591d9... is a merge but no -m option was given.
fatal: revert failed
$ git revert --no-edit -m 1 HEAD
[main 066c38f] Revert "Merge feature"
 1 file changed, 1 deletion(-)
 delete mode 100644 f.txt
```

بار اول Git خطا داد و دلیلش را نوشت. بار دوم با `-m 1` جواب داد. `-m 1` یعنی «parent اول را خط اصلی بدان»، یعنی branchی که داخلش merge کرده بودید. نتیجه این شد که `f.txt` که از branch `feature` آمده بود، حذف شد.

## {{< term "cherry-pick" "cherry-pick" >}}: برداشتن یک commit

گاهی نمی‌خواهید چیزی را برگردانید؛ فقط یک commit مشخص را از جای دیگر می‌خواهید. مثلاً روی branch به اسم `hotfix` یک اصلاح کوچک ساخته‌اید و فقط همان را روی `main` لازم دارید. `cherry-pick` همین کار را می‌کند. من commit مربوط به `hotfix` را این‌طور روی `main` آوردم:

```bash
git cherry-pick -x 1e6057c
```

نتیجه یک commit جدید روی `main` است که هش آن فرق دارد (`68d45b5`). دلیلش این است که هش commit از parent آن هم می‌آید و parent این commit جدید چیز دیگری است. اما تغییری که اعمال می‌کند همان است. `git patch-id` این را ثابت می‌کند؛ این دستور از خودِ تغییر یک امضا می‌سازد، بدون توجه به parent:

```text
3c5eb97fe2e9bbe1df3424ee1a5dcc36a36c7145 1e6057c...   (original)
3c5eb97fe2e9bbe1df3424ee1a5dcc36a36c7145 68d45b5...   (copy)
```

امضای هر دو یکی است. گزینه‌ی `-x` هم عبارت `(cherry picked from commit 1e6057c...)` را به پیام commit اضافه می‌کند. بعداً که کسی بپرسد این commit از کجا آمده، جواب در همان پیام است.

## reflog چه چیزی را نجات نمی‌دهد

حالا حد این ابزارها. یک خط به `a.txt` اضافه کردم، آن را stage نکردم و بعد `git restore a.txt` زدم:

```text
 M a.txt          (before)
                  (after: clean, the line is gone)
```

خط `M` اول یعنی فایل تغییر کرده بود. بعد از `restore` وضعیت تمیز است و آن خط رفته. reflog هیچ ردی از این تغییر ندارد، چون هیچ‌وقت commit نشده بود. Git فقط چیزی را به یاد دارد که ذخیره کرده باشد. فایل‌های untracked و تغییرات commit‌نشده محافظت نمی‌شوند؛ پیش از دستورهای خطرناک، commit کنید یا `git stash` بزنید.

## commitهای dangling و fsck

یک حالت دیگر: branch را پاک کرده‌اید و reflog هم دیگر چیزی ندارد. مثلاً من با `git branch -D tmp` یک branch را پاک کردم و reflog را expire کردم (یعنی ورودی‌های آن را دور ریختم). حالا هیچ نامی به commit آن branch اشاره نمی‌کند. ولی commit تا زمان garbage collection هنوز در پایگاه‌داده است و `git fsck` که دنبال objectهای بی‌صاحب می‌گردد، آن را پیدا می‌کند:

```bash
git fsck --lost-found
```

```text
dangling commit 0b1fb07a5e6289f46c88e2cd5ceaf064d9e01737
```

«dangling» یعنی commitی که هیچ ref یا commit دیگری به آن نمی‌رسد. با `git branch rescue 0b1fb07` یک نام تازه به آن دادم و برگشت.

این وضع همیشگی نیست. طبق مستندات Git، ورودی‌های reflog اگر commit هنوز از جایی قابل دسترس باشد بعد از ۹۰ روز و اگر نباشد بعد از ۳۰ روز منقضی می‌شوند (تنظیم‌های `gc.reflogExpire` و `gc.reflogExpireUnreachable`) و `git gc` بعد از آن می‌تواند objectها را پاک کند. این مدت‌ها را خودم امتحان نکردم.

## قواعد نجات

- پیش از `reset --hard` حتماً `git status` بزنید. کار commit‌نشده قابل بازیابی نیست.
- commitهایی را که push کرده‌اید amend یا reset نکنید. چون دیگران ممکن است رویشان کار کرده باشند، آنجا از `revert` استفاده کنید.
- وقتی هول شدید، اول `git reflog` را بزنید و چیزی را تغییر ندهید. فقط نگاه کنید و جای درست را پیدا کنید.
- برای revert کردن merge commit همیشه `-m 1` (یا شماره‌ی درست parent) بدهید؛ بدون آن Git قبول نمی‌کند.
- reflog مخصوص هر clone است. clone تازه آن را ندارد و reflog همکارتان هم به کار شما نمی‌آید.
- طبق مستندات Git، بعد از revert کردن یک merge، اگر همان branch را دوباره merge کنید تغییرهای آن برنمی‌گردند، چون Git فکر می‌کند قبلاً آورده شده‌اند. این را خودم امتحان نکردم.

## تمرین

در یک repo موقت سه commit بسازید، `git reset --hard HEAD~2` بزنید و با reflog برش گردانید. بعد commit وسطی را revert کنید و یک commit از branch دیگر را با `-x` cherry-pick کنید.

## قدم بعدی

مقاله‌ی بعدی «پیدا کردن باگ با git bisect» است؛ برگرداندن یک commit ساده است، سخت‌تر پیدا کردن همان commitی است که چیزی را خراب کرده.
