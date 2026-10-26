+++
date = '2026-10-30T10:00:00+03:30'
draft = false
title = 'index و staging: سه ناحیه‌ی گیت'
description = 'index و staging در گیت با اجرای واقعی: working tree، index و HEAD، کدهای status، انواع diff، git add -p، restore، .gitignore و stash.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "staging", "index"]
cover = { image = "/images/covers/git-index-staging.fa.png", alt = "index و staging: سه ناحیه‌ی گیت", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/git-how-git-thinks/) دیدیم که گیت عکس‌ها (snapshot) را به‌شکل object ذخیره می‌کند و اسمشان hash محتواست. این مقاله درباره‌ی مرحله‌ی قبل از ساخته شدن commit است، همان جایی که اکثر تازه‌واردها گیج می‌شوند: چرا اول `git add` و بعد `git commit`؟ جواب این است که گیت دو ناحیه ندارد، سه ناحیه دارد.

> همه‌ی دستورهای زیر با Git نسخه‌ی 2.39.2 در repositoryهای موقت اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند.

## سه ناحیه

1. **{{< term "working-tree" "Working tree" >}}**: فایل‌های روی دیسک که ویرایش می‌کنید.
2. **{{< term "staging-area" "Index" >}}** (به آن staging area هم می‌گویند): عکسی از چیزی که commit بعدی خواهد داشت.
3. **{{< term "head" "HEAD" >}}**: آخرین commit.

`git add` از working tree به index کپی می‌کند. `git commit` از index یک commit می‌سازد. ویرایش یک فایل هرگز خودبه‌خود index را عوض نمی‌کند.

## خواندن `git status -s`

فرمت کوتاه دو ستون دارد: ستون اول index را با HEAD مقایسه می‌کند و ستون دوم working tree را با index.

```text
?? app.txt          # new file, untracked
A  app.txt          # after git add: staged as a new file
 M app.txt          # after commit and an edit: modified, not staged
MM app.txt          # staged, then edited again
```

`MM` را یادتان بماند: فایل در هر دو جا فرق دارد و دو نسخه‌ی متفاوت از آن وجود دارد.

## سه نوع diff

`line 4` را stage کردم و بعد `line 5` را بدون stage اضافه کردم. حالا همان فایل سه نسخه دارد (HEAD، index، دیسک):

```text
$ git diff            # working tree vs index
+line 5
$ git diff --staged   # index vs HEAD
+line 4
$ git diff HEAD       # working tree vs HEAD
+line 4
+line 5
```

(هدرها را حذف کرده‌ام.) `git diff` ساده فقط بخش stage‌نشده را نشان می‌دهد؛ برای همین بلافاصله بعد از `git add` خالی به نظر می‌رسد.

## index واقعاً چه چیزی نگه می‌دارد

```text
$ git ls-files -s
100644 9c2a7090627d0fffa9ed001bf7be98f86c2c8068 0	app.txt
```

هر ورودی شامل mode فایل، شناسه‌ی یک **{{< term "blob" "blob" >}}**، شماره‌ی stage (صفر یعنی conflict ندارد) و مسیر است. blob همان لحظه‌ی `git add` در object database نوشته شده بود و `git cat-file -p 9c2a709...` خط‌های `line 1` تا `line 4` را چاپ می‌کند، بدون `line 5`. پس add کردن فایل محتوایش را فوراً ذخیره می‌کند و commit فقط index را ثبت می‌کند.

## stage کردن بخشی از فایل با `git add -p`

گیت diff را به **{{< term "hunk" "hunk" >}}** تقسیم می‌کند. در فایلی با ۲۰ خط، خط ۲ و خط ۱۹ را عوض کردم و دو hunk ساخته شد (`@@ -1,5 +1,5 @@` و `@@ -16,5 +16,5 @@`). جواب `y` و بعد `n` فقط اولی را stage می‌کند:

```text
$ printf 'y\nn\n' | git add -p
$ git status -s
MM f.txt
$ git commit -qm "change line 2"
$ git diff | grep '^[+-]line'
-line 19
+line 19 CHANGED
$ git commit -qam "change line 19"
```

دو تغییر مستقل شد دو commit، و در `git log --stat` هرکدام `1 insertion(+), 1 deletion(-)` دارند. این راهی است که حتی وقتی هم‌زمان روی دو کار کرده‌اید، commitها کوچک می‌مانند.

## برگرداندن: `restore`

```text
$ git restore --staged f.txt   # index back to HEAD, edits stay on disk
$ git restore f.txt            # disk back to the index
```

هر دو را روی فایلی اجرا کردم که یک خط stage‌شده و یک خط stage‌نشده داشت. اولی ` M f.txt` باقی گذاشت؛ دومی چیزی چاپ نکرد، با کد ۰ تمام شد و هر دو خط اضافه از بین رفتند. گیت هیچ سؤالی نپرسید. تغییری که نه stage شده نه commit، جای دیگری وجود ندارد، پس `git restore <file>` قابل برگشت نیست.

## `.gitignore` و `git rm --cached`

`.env` و `build/out` را اشتباهی commit کردم و بعد یک {{< term "gitignore" ".gitignore" >}} با محتوای `.env`، `build/` و `*.log` ساختم. `.env` هنوز ` M` نشان می‌داد و `git check-ignore -v .env` چیزی چاپ نکرد، چون ignore فقط روی فایل‌های untracked اثر دارد. برای اینکه گیت دیگر فایل را دنبال نکند ولی روی دیسک بماند:

```text
$ git rm --cached -q .env
$ git rm -r --cached -q build
$ git status -s
D  .env
D  build/out
?? .gitignore
$ git check-ignore -v .env a.log
.gitignore:1:.env	.env
.gitignore:3:*.log	a.log
```

`check-ignore -v` فایل، شماره‌ی خط و الگویی را که مطابقت کرده نشان می‌دهد. هر دو فایل بعد از آن هنوز روی دیسک بودند. یادتان باشد راز داخل تاریخچه می‌ماند؛ اگر واقعی بود عوضش کنید.

## کنار گذاشتن کار با `git stash`

```text
$ git stash
Saved working directory and index state WIP on main: 34282f1 stop tracking
$ git status -s
?? scratch.txt
$ git stash pop
```

{{< term "stash" "stash" >}} ساده `main.go` تغییریافته را برداشت اما `scratch.txt` (untracked) را جا گذاشت. `git stash -u` هر دو را برداشت و درخت تمیز شد؛ `git stash list` یک ورودی نشان داد و `pop` همه‌چیز را برگرداند.

## چند نکته‌ی مهم

- `git commit -a` فقط برای فایل‌های tracked مرحله‌ی staging را رد می‌کند؛ فایل جدید هنوز به `git add` نیاز دارد.
- `git add -p` فایل‌های untracked را پیشنهاد نمی‌دهد؛ آن‌ها را عادی add کنید.
- `git restore` روی تغییرهای stage‌نشده دائمی است. اگر مطمئن نیستید از `git stash` استفاده کنید.
- اضافه کردن یک مسیر به `.gitignore` هرگز آن را untrack نمی‌کند.
- `git stash pop` ممکن است conflict بدهد؛ در آن صورت ورودی نگه داشته می‌شود.

## تمرین

1. یک repo بسازید، فایلی ۱۰ خطی را commit کنید، خط ۱ و خط ۱۰ را عوض کنید و با `git add -p` دو commit بسازید.
2. عمداً به `MM` برسید و سه نوع `git diff` را ببینید.
3. یک فایل `.log` را commit کنید، `*.log` را ignore کنید و با `git rm --cached` آن را untrack کنید.

## قدم بعدی

در مقاله‌ی بعد: «branch، HEAD و ref: فقط اشاره‌گر».
