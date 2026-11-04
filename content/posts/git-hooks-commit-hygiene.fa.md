+++
date = '2026-11-13T10:00:00+03:30'
draft = false
title = 'hookها و commit message تمیز'
description = 'Git hook در عمل: اسکریپت‌های pre-commit، commit-msg و pre-push، اشتراک‌گذاری با core.hooksPath و نوشتن commit message تمیز با fixup.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "hooks", "commit-messages", "beginner"]
cover = { image = "/images/covers/git-hooks-commit-hygiene.fa.png", alt = "hookها و commit message تمیز", hiddenInSingle = true }
+++

یک `print("here")` که وسط دیباگ نوشته‌اید، توی commit رفته و دو هفته بعد کسی آن را در لاگ production می‌بیند. یا یک commit با پیام «fix stuff» که بعدها هیچ‌کس نمی‌داند چه چیزی را درست کرده. هیچ‌کدام از این‌ها از بی‌دقتی بد نیست؛ آدم‌ها خسته می‌شوند و نیت خوب برای همیشه کافی نیست.

پیدا کردن باگ با [`git bisect`](/fa/posts/git-bisect/) هم فقط وقتی خوب جواب می‌دهد که تاریخچه خوانا باشد: commitهای کوچک با پیامی که می‌گوید «چرا». راه حل این است که بخشی از این انضباط را به ماشین بسپاریم. {{< term "git-hook" "hook" >}} همین کار را می‌کند. hook اسکریپتی است که Git روی یک رویداد (مثلاً درست قبل از commit) اجرا می‌کند و اگر اسکریپت با کد غیرصفر تمام شود، Git کار را متوقف می‌کند. بقیه‌ی این مقاله چند عادت برای خود پیام‌هاست و راهی برای اصلاح یک commit قدیمی.

> همه‌ی مثال‌ها در یک repo محلی با Git نسخه‌ی 2.39 و Python 3 اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند. hashها مال همان اجرا هستند و روی سیستم شما فرق می‌کنند.

## hook فقط یک اسکریپت است

ساز‌وکارش ساده است. Git دنبال فایل‌های اجرایی می‌گردد که اسمشان همان اسم رویداد است (مثلاً `pre-commit` برای قبل از commit). اگر چنین فایلی باشد، اجرایش می‌کند؛ اگر با کد غیرصفر خارج شود، آن عملیات متوقف می‌شود. به‌صورت پیش‌فرض این فایل‌ها در `.git/hooks` هستند، و آن پوشه version نمی‌شود، یعنی با repo به کسی منتقل نمی‌شود.

برای شروع یک hook از نوع `pre-commit`. من وقتی کدی را موقتی می‌نویسم که «قبل از commit باید پاک شود»، کنارش نشانه‌ی `TODO-REMOVE` می‌گذارم. این hook جلوی هر commit را می‌گیرد که آن نشانه در تغییرهای staged باشد:

```sh
#!/bin/sh
if git diff --cached -U0 | grep -q 'TODO-REMOVE'; then
  echo "pre-commit: found TODO-REMOVE in staged changes" >&2
  exit 1
fi
```

`git diff --cached -U0` تغییرهای staged را بدون خط‌های اطراف چاپ می‌کند، `grep -q` فقط بررسی می‌کند نشانه در آن هست یا نه، و `exit 1` کار را متوقف می‌کند. نتیجه:

```text
$ git commit -m "add debug"
pre-commit: found TODO-REMOVE in staged changes
$ echo $?
1
```

پیام ما چاپ شد و کد خروج ۱ است. commit انجام نشد و تغییر همچنان staged ماند. بعد از پاک کردن آن خط، commit رد شد.

## اشتراک‌گذاری با core.hooksPath

مشکل این است که `.git/hooks` version نمی‌شود، پس هم‌تیمی‌های شما این hookها را نمی‌گیرند. راهش این است که hookها را در یک پوشه‌ی معمولی داخل repo بگذارید (که commit می‌شود) و به Git بگویید آنجا را نگاه کند:

```text
$ git config core.hooksPath .githooks
```

هر نفر این را یک بار برای هر clone اجرا می‌کند (یک اسکریپت setup یا README می‌تواند یادآوری کند). حالا یک `pre-commit` جدی‌تر داریم که فایل‌های پایتونِ staged را کامپایل می‌کند تا خطای syntax وارد commit نشود:

```sh
#!/bin/sh
files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')
[ -z "$files" ] && exit 0
for f in $files; do
  python3 -m py_compile "$f" || { echo "pre-commit: $f does not compile" >&2; exit 1; }
done
```

خط اول اسم فایل‌های staged با پسوند `.py` را برمی‌دارد (`--diff-filter=ACM` یعنی فقط فایل‌های اضافه، کپی و تغییرکرده). اگر هیچ‌کدام نبود، بی‌صدا موفق می‌شود. وگرنه هر فایل را با `py_compile` امتحان می‌کند. من یک `bad.py` با محتوای `print(` را commit کردم:

```text
  File "bad.py", line 1
    print(
         ^
SyntaxError: '(' was never closed
pre-commit: bad.py does not compile
```

خط‌های اول گزارش خود Python از خطاست و خط آخر پیام hook ما. برای Go به همین شکل از `gofmt -l` استفاده می‌شود؛ من اینجا فقط نسخه‌ی Python را اجرا کردم.

## کنترل سبک پیام با commit-msg

hook دیگری هست که روی پیام کار می‌کند: `commit-msg`. Git پیش از ثبت commit پیام را در یک فایل موقت می‌نویسد و مسیر آن را به‌عنوان `$1` به hook می‌دهد. hook زیر یک پیشوند به سبک **{{< term "conventional-commits" "Conventional Commits" >}}** را اجباری می‌کند، یعنی عنوان باید شبیه `type: summary` باشد، مثلاً `fix: handle empty input`:

```sh
#!/bin/sh
subject=$(head -n 1 "$1")
if ! echo "$subject" | grep -Eq '^((fixup! |squash! )?)(feat|fix|docs|refactor|test|chore)(\([a-z0-9-]+\))?: .+'; then
  echo "commit-msg: subject must look like 'type: summary' (feat, fix, docs, refactor, test, chore)" >&2
  echo "got: $subject" >&2
  exit 1
fi
```

خط اول عنوان (سطر اول پیام) را می‌گیرد و `grep` آن را با الگو مقایسه می‌کند. دو پیام را امتحان کردم؛ اولی رد شد و دومی پذیرفته شد:

```text
$ git commit -m "added hooks"
commit-msg: subject must look like 'type: summary' (feat, fix, docs, refactor, test, chore)
got: added hooks
$ git commit -m "chore: add shared hooks"
[main 785e41e] chore: add shared hooks
```

به بخش `fixup! |squash! ` در الگو توجه کنید. نسخه‌ی اولِ regex من آن را نداشت و `fixup! feat: add greet` را رد کرد، و این جریان بخش آخر را خراب کرد. hook گاهی جلوی خودتان هم می‌ایستد.

## pre-push و اجرای تست‌ها

hook سوم قبل از `git push` اجرا می‌شود. جای خوبی برای اجرای تست‌هاست، چون فقط وقتی کدی می‌خواهد از ماشین شما برود بیرون جلویش را می‌گیرد:

```sh
#!/bin/sh
python3 -m unittest discover -s tests -q || { echo "pre-push: tests failed, push blocked" >&2; exit 1; }
```

با یک تست عمداً غلط (`assertEqual(1 + 1, 3)`) push را امتحان کردم:

```text
AssertionError: 2 != 3
FAILED (failures=1)
pre-push: tests failed, push blocked
error: failed to push some refs to '../remote.git'
```

دو خط اول از خود تست‌اند، خط سوم پیام hook ماست و خط آخر شکایت Git که push انجام نشد. (remote این‌جا یک repo محلی دیگر بود.) بعد از درست کردن تست، push موفق شد. این hook را سریع نگه دارید، وگرنه آدم‌ها دورش می‌زنند.

## hook حفاظ است، نه امنیت

دورزدن hook آسان است:

```text
$ git commit --no-verify -m "whatever"
[main d172ea1] whatever
```

`--no-verify` هر دو hook یعنی `pre-commit` و `commit-msg` را رد می‌کند و commit من با پیام نامناسب ثبت شد. علاوه بر این، hook فقط وقتی وجود دارد که آن شخص نصبش کرده باشد. پس hook را نرده‌ی کنار جاده بدانید، نه دیوار: جلوی اشتباه‌های ناخواسته را می‌گیرد. هر چیزی که واقعاً به آن تکیه دارید باید دوباره در {{< term "ci" "CI" >}} اجرا شود. ابزارهایی مثل Husky یا pre-commit نصب hook را مدیریت می‌کنند؛ فقط اسمشان را می‌آورم و اینجا امتحانشان نکردم.

## یک commit message خوب

حالا خود پیام. یک قرارداد رایج (نه قانون Git): خط عنوان حدود ۵۰ کاراکتر، یک خط خالی، و بدنه‌ای با عرض حدود ۷۲ کاراکتر که توضیح می‌دهد «چرا». «چه چیزی عوض شد» را diff می‌گوید؛ پیام باید دلیلش را بگوید.

```text
feat: add retry

Retry up to 3 times because the upstream
returns 503 during deploys.
```

دستور `git commit -v` تفاوت staged را در ویرایشگر نشان می‌دهد تا بتوانید دقیقاً همان چیزی را که تغییر داده‌اید توصیف کنید. دستور `git config commit.template <file>` ویرایشگر را از قبل با محتوای یک فایل پر می‌کند. من یک template ساختم که فقط خط‌های comment داشت؛ `git commit` ویرایشگر را با همان خط‌ها باز کرد. خط‌هایی که با `#` شروع می‌شوند از پیام نهایی حذف می‌شوند.

## اصلاح یک commit قدیمی با fixup

حالا فرض کنید در یک commit قدیمی‌تر (نه آخرین) غلط تایپی پیدا کردید. اصلاح را stage کنید و `git commit --fixup` را با commit هدف بزنید. Git یک commit تازه می‌سازد که پیامش `fixup! ` به‌علاوه‌ی عنوان هدف است:

```text
$ git commit --fixup 2f84e0a
$ git log --oneline -4
5cc2712 fixup! feat: add greet
7e55bd8 fix: let fixup commits through
e9528aa feat: add bye
2f84e0a feat: add greet
```

حالا خط اول همان اصلاح است که هنوز جدا نشسته. یک rebase با **{{< term "fixup-commit" "fixup" >}}** آن را داخل commit هدف ادغام می‌کند. گزینه‌ی `--autosquash` خودش commitهای `fixup!` را زیر هدفشان می‌چیند، و مقدار `GIT_SEQUENCE_EDITOR=true` لیست آماده را بدون باز کردن ویرایشگر می‌پذیرد:

```text
$ GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash HEAD~4
Successfully rebased and updated refs/heads/main.
b10a5cf fix: let fixup commits through
82e5be5 feat: add bye
be3de2d feat: add greet
```

(سه خط آخر `git log --oneline` بعد از rebase است.) خط fixup ناپدید شد و اصلاح داخل `feat: add greet` نشست. پیش از rebase باید index و working tree تمیز باشند؛ اولین تلاش من با پیام «Your index contains uncommitted changes» شکست خورد. بازنویسی تاریخچه فقط برای commitهایی امن است که هنوز با کسی به اشتراک نگذاشته‌اید.

## جایی که hookها گیر می‌اندازند

- **hookهای `.git/hooks` محلی‌اند.** برای اشتراک‌گذاری از `core.hooksPath` با یک پوشه‌ی ردیابی‌شده استفاده کنید.
- **اسکریپت را اجرایی کنید (`chmod +x`).** وگرنه Git اجرایش نمی‌کند؛ در امتحان من فقط یک hint چاپ کرد که hook نادیده گرفته شد و commit بدون هیچ بررسی انجام شد.
- **`pre-commit` را سریع نگه دارید و فقط فایل‌های staged را بررسی کنید.** hook کند را آدم‌ها با `--no-verify` دور می‌زنند.
- **hook را امنیت فرض نکنید.** `--no-verify` وجود دارد، پس بررسی‌ها را در CI تکرار کنید.
- **commitهایی را که push و به اشتراک گذاشته‌اید autosquash نکنید.** تاریخچه‌ی آن‌ها را دیگران دارند.

## تمرین

در یک repo آزمایشی، در `.githooks/` یک hook از نوع `commit-msg` بنویسید که subjectهای بلندتر از ۷۲ کاراکتر را رد کند. `core.hooksPath` را تنظیم کنید و بررسی کنید پیام بلند رد و پیام کوتاه پذیرفته می‌شود. بعد دو commit بسازید، برای اولی یک fixup اضافه کنید و با autosquash ادغامش کنید.

## قدم بعدی

مقاله‌ی بعدی «submodule، subtree و worktree» است؛ برای وقتی که repository شما به repository دیگری نیاز دارد یا دو branch را همزمان روی دیسک می‌خواهید.
